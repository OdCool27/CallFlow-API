"""Minimal AMI client: one reader, one ordered event consumer, bounded retries."""
import asyncio
import contextlib
import logging
import os
from pathlib import Path
from time import monotonic

from app.telephony import utcnow

log = logging.getLogger(__name__)


def encode_action(action, **fields):
    values = {"Action": action, **fields}
    if any("\r" in str(v) or "\n" in str(v) for v in values.values()):
        raise ValueError("AMI fields cannot contain newlines")
    return ("\r\n".join(f"{k}: {v}" for k, v in values.items()) + "\r\n\r\n").encode()


async def read_frame(reader):
    raw = await reader.readuntil(b"\r\n\r\n")
    result = {}
    for line in raw.decode("utf-8", errors="replace").split("\r\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            result[key] = value.strip()
    return result


class AMIClient:
    def __init__(self, settings, tracker):
        self.settings = settings
        self.tracker = tracker
        self.connected = False
        self.synchronized = False
        self.state = "disabled" if not settings.ami_enabled else "starting"
        self.attempts = 0
        self.last_event_at = None
        self.writer = None
        self.task = None
        self._owner = None

    def status(self):
        return {"enabled": self.settings.ami_enabled, "connected": self.connected,
                "synchronized": self.synchronized, "state": self.state,
                "attempts": self.attempts, "last_event_at": self.last_event_at}

    def _acquire_owner(self):
        # OS lock is released even after a crash. Prevent duplicate listeners on reload/workers.
        db_path = self.settings.database_url.removeprefix("sqlite:///")
        lock_path = Path(db_path + ".ami.lock").resolve()
        self._owner = open(lock_path, "a+b")
        self._owner.seek(0)
        if os.name == "nt":
            import msvcrt
            if lock_path.stat().st_size == 0:
                self._owner.write(b"0")
                self._owner.flush()
            self._owner.seek(0)
            msvcrt.locking(self._owner.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)

    async def start(self):
        if self.settings.ami_enabled and self.task is None:
            self.task = asyncio.create_task(self.run(), name="callflow-ami")

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        self.state = "stopped"

    async def send(self, action, **fields):
        self.writer.write(encode_action(action, **fields))
        await self.writer.drain()

    async def run(self):
        try:
            try:
                self._acquire_owner()
            except OSError:
                self.state = "listener_owned_elsewhere"
                log.error("Another process owns this database's AMI listener; use one API worker")
                return
            # Also flags unfinished calls from a previous process crash.
            await asyncio.to_thread(self.tracker.mark_disconnected)
            for attempt in range(1, self.settings.ami_reconnect_attempts + 1):
                self.attempts = attempt
                self.state = "connecting"
                try:
                    await self._session()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Do not log credentials or raw protocol responses.
                    log.warning("AMI session failed (%s), attempt %s/%s", type(exc).__name__, attempt,
                                self.settings.ami_reconnect_attempts)
                finally:
                    self.connected = self.synchronized = False
                    if self.writer:
                        self.writer.close()
                        with contextlib.suppress(Exception):
                            await asyncio.wait_for(self.writer.wait_closed(), self.settings.ami_timeout)
                        self.writer = None
                    await asyncio.to_thread(self.tracker.mark_disconnected)
                if attempt < self.settings.ami_reconnect_attempts:
                    self.state = "reconnecting"
                    await asyncio.sleep(min(30, self.settings.ami_reconnect_delay * 2 ** (attempt - 1)))
            self.state = "exhausted"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.state = "error"
            log.error("AMI observer stopped unexpectedly (%s)", type(exc).__name__)
        finally:
            self.connected = self.synchronized = False
            if self._owner:
                self._owner.close()
                self._owner = None

    async def _session(self):
        cfg = self.settings
        if not cfg.ami_secret:
            raise ValueError("AMI_SECRET is required when AMI is enabled")
        reader, self.writer = await asyncio.wait_for(asyncio.open_connection(cfg.ami_host, cfg.ami_port), cfg.ami_timeout)
        banner = await asyncio.wait_for(reader.readline(), cfg.ami_timeout)
        if not banner.startswith(b"Asterisk Call Manager/"):
            raise ConnectionError("Unexpected AMI greeting")
        await self.send("Login", Username=cfg.ami_username, Secret=cfg.ami_secret, Events="on", ActionID="login")
        while True:
            response = await asyncio.wait_for(read_frame(reader), cfg.ami_timeout)
            if response.get("ActionID") == "login" and "Response" in response:
                if response["Response"] != "Success":
                    raise PermissionError("AMI authentication rejected")
                break
        self.connected = True
        self.state = "synchronizing"
        await asyncio.to_thread(self.tracker.begin_snapshot)
        await self.send("CoreShowChannels", ActionID="snapshot")
        await self.send("PJSIPShowContacts", ActionID="contacts")
        await self.send("DeviceStateList", ActionID="devices")
        snapshot_deadline = monotonic() + max(15, cfg.ami_timeout * 3)
        ping_at = monotonic() + cfg.ami_timeout
        ping_deadline = None
        while True:
            # Heartbeats detect a half-open socket even when unsolicited events keep arriving.
            now = monotonic()
            if not self.synchronized and now > snapshot_deadline:
                raise TimeoutError("AMI channel snapshot incomplete")
            if ping_deadline and now > ping_deadline:
                raise TimeoutError("AMI heartbeat failed")
            if now >= ping_at and ping_deadline is None:
                await self.send("Ping", ActionID="heartbeat")
                ping_deadline = now + cfg.ami_timeout
            try:
                frame = await asyncio.wait_for(read_frame(reader), min(1, cfg.ami_timeout))
            except asyncio.TimeoutError:
                continue
            if frame.get("ActionID") == "heartbeat" and frame.get("Response") == "Success":
                ping_deadline = None
                ping_at = monotonic() + cfg.ami_timeout
            if frame.get("Response") == "Error":
                if frame.get("ActionID") == "snapshot":
                    raise PermissionError("AMI channel snapshot rejected")
                log.warning("AMI action rejected: %s", frame.get("ActionID", "unknown"))
            if "Event" in frame:
                self.last_event_at = utcnow()
                if frame["Event"] == "CoreShowChannelsComplete" and frame.get("ActionID") == "snapshot":
                    await asyncio.to_thread(self.tracker.reconcile)
                    self.synchronized = True
                    self.state = "connected"
                    log.info("AMI authenticated and channel snapshot reconciled")
                else:
                    # Await each transaction to preserve wire order and apply backpressure.
                    await asyncio.to_thread(self.tracker.process, frame)
