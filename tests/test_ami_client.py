import asyncio
from unittest.mock import AsyncMock, Mock, patch
import pytest

from app.ami import AMIClient, encode_action, read_frame
from app.config import Settings


def config(**overrides):
    return Settings(ami_enabled=True, ami_secret="test-only", ami_timeout=0.05,
                    ami_reconnect_delay=0, ami_reconnect_attempts=2, **overrides)


def test_framing_and_injection():
    async def check():
        reader = asyncio.StreamReader()
        reader.feed_data(b"Event: Newchannel\r\nUniqueid: a\r\n\r")
        task = asyncio.create_task(read_frame(reader))
        await asyncio.sleep(0)
        assert not task.done()
        reader.feed_data(b"\nResponse: Success\r\n\r\n")
        assert (await task)["Uniqueid"] == "a"
        assert (await read_frame(reader))["Response"] == "Success"
    asyncio.run(check())
    with pytest.raises(ValueError):
        encode_action("Login", Secret="bad\r\nAction: Command")


def test_authenticated_snapshot_and_endpoint_events(tracker, sessions):
    async def check():
        reader = asyncio.StreamReader()
        reader.feed_data(b"Asterisk Call Manager/9.0.0\r\n")
        for frame in [
            {"Response": "Success", "ActionID": "login"},
            {"Event": "CoreShowChannelsComplete", "ActionID": "snapshot"},
            {"Event": "ContactList", "Endpoint": "103", "ObjectName": "103/sip:103@host", "Status": "Reachable"},
            {"Event": "DeviceStateChange", "Device": "PJSIP/103", "State": "NOT_INUSE"},
        ]:
            reader.feed_data(encode_action("unused", **frame))
        reader.feed_eof()
        writer = Mock()
        writer.drain = AsyncMock()
        client = AMIClient(config(), tracker)
        with patch("asyncio.open_connection", new=AsyncMock(return_value=(reader, writer))):
            with pytest.raises(asyncio.IncompleteReadError):
                await client._session()
        assert client.connected and client.synchronized
        sent = b"".join(c.args[0] for c in writer.write.call_args_list)
        assert b"Action: CoreShowChannels" in sent
        assert b"Action: PJSIPShowContacts" in sent
    asyncio.run(check())
    from app.models import Endpoint
    with sessions() as db:
        assert db.get(Endpoint, "103").device_state == "NOT_INUSE"
        assert db.get(Endpoint, "103").contact_status == "Reachable"


def test_retries_are_bounded_and_offline_api_survives(tracker, client):
    async def check():
        ami = AMIClient(config(), tracker)
        ami._session = AsyncMock(side_effect=ConnectionError("offline"))
        with patch.object(ami, "_acquire_owner"):
            await ami.run()
        assert ami.attempts == 2
        assert ami.state == "exhausted"
        assert not ami.connected and not ami.synchronized
    asyncio.run(check())
    assert client.get("/health").status_code == 200
    assert client.get("/customers").status_code == 200


def test_clean_shutdown(tracker):
    async def check():
        ami = AMIClient(config(), tracker)
        ready = asyncio.Event()
        writer = Mock()
        writer.wait_closed = AsyncMock()
        async def session():
            ami.writer = writer
            ami.connected = True
            ready.set()
            await asyncio.Future()
        ami._session = session
        with patch.object(ami, "_acquire_owner"):
            await ami.start()
            await asyncio.wait_for(ready.wait(), 2)
            await ami.stop()
        writer.close.assert_called_once()
        assert ami.task is None
        assert not ami.connected
        assert ami.state == "stopped"
    asyncio.run(check())


@pytest.mark.parametrize("response,exception", [
    ({"Response": "Error", "ActionID": "login"}, PermissionError),
    ({"Response": "Error", "ActionID": "snapshot"}, PermissionError),
])
def test_rejected_authentication_or_snapshot(tracker, response, exception):
    async def check():
        reader = asyncio.StreamReader()
        reader.feed_data(b"Asterisk Call Manager/9.0.0\r\n")
        if response["ActionID"] != "login":
            reader.feed_data(encode_action("unused", Response="Success", ActionID="login"))
        reader.feed_data(encode_action("unused", **response))
        reader.feed_eof()
        writer = Mock(drain=AsyncMock())
        ami = AMIClient(config(), tracker)
        with patch("asyncio.open_connection", new=AsyncMock(return_value=(reader, writer))):
            with pytest.raises(exception):
                await ami._session()
    asyncio.run(check())


def test_missing_heartbeat_disconnects(tracker):
    async def check():
        reader = asyncio.StreamReader()
        reader.feed_data(b"Asterisk Call Manager/9.0.0\r\n")
        reader.feed_data(encode_action("unused", Response="Success", ActionID="login"))
        reader.feed_data(encode_action("unused", Event="CoreShowChannelsComplete", ActionID="snapshot"))
        writer = Mock(drain=AsyncMock())
        ami = AMIClient(config(), tracker)
        with patch("asyncio.open_connection", new=AsyncMock(return_value=(reader, writer))):
            with pytest.raises(TimeoutError, match="heartbeat"):
                await asyncio.wait_for(ami._session(), 3)
        assert any(b"Action: Ping" in call.args[0] for call in writer.write.call_args_list)
    asyncio.run(check())


def test_listener_ownership_lock(tmp_path, tracker):
    cfg = config(database_url=f"sqlite:///{tmp_path / 'owner.db'}")
    first, second = AMIClient(cfg, tracker), AMIClient(cfg, tracker)
    try:
        first._acquire_owner()
        with pytest.raises(OSError):
            second._acquire_owner()
    finally:
        first._owner.close()
        second._owner.close()
    second._acquire_owner()
    second._owner.close()
