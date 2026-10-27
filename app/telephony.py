"""Single-consumer AMI event reducer. All times are naive UTC in SQLite."""
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Agent, Call, CallChannel, Endpoint

log = logging.getLogger(__name__)
CALL_EVENTS = {"Newchannel", "Newstate", "DialBegin", "DialEnd", "BridgeEnter", "BridgeLeave", "Hangup", "CoreShowChannel"}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def extension(channel):
    match = re.match(r"(?:PJSIP|SIP)/([^/]+?)-[0-9a-fA-F]+$", channel or "")
    return match.group(1) if match else None


def seconds(start, end):
    return max(0.0, (end - start).total_seconds()) if start and end else None


class CallTracker:
    def __init__(self, sessions):
        self.sessions = sessions
        self.snapshot_baseline = set()
        self.snapshot_seen = set()
        self.snapshot_active = False

    def begin_snapshot(self):
        with self.sessions() as db:
            self.snapshot_baseline = set(db.scalars(select(CallChannel.unique_id).where(CallChannel.ended_at.is_(None))))
        self.snapshot_seen = set()
        self.snapshot_active = True

    def mark_disconnected(self):
        with self.sessions.begin() as db:
            for call in db.scalars(select(Call).where(Call.source == "AMI", Call.ended_at.is_(None))):
                call.tracking_incomplete = True
                # Never count an unobserved interval across a connection gap.
                self._close_connection(call, utcnow())
            for endpoint in db.scalars(select(Endpoint)):
                endpoint.contact_status = endpoint.device_state = "UNKNOWN"
                endpoint.updated_at = utcnow()

    def reconcile(self, at=None):
        at = at or utcnow()
        with self.sessions.begin() as db:
            for uid in self.snapshot_baseline - self.snapshot_seen:
                channel = db.get(CallChannel, uid)
                if channel and channel.ended_at is None:
                    channel.ended_at = at
                    channel.bridge_id = None
                    channel.call.tracking_incomplete = True
            db.flush()
            for call in db.scalars(select(Call).where(Call.source == "AMI", Call.ended_at.is_(None))):
                if call.channels and all(c.ended_at for c in call.channels):
                    self._finish(call, at, "UNKNOWN")
        self.snapshot_active = False

    @staticmethod
    def _close_connection(call, at):
        if call.connection_open_at:
            call.connected_seconds += seconds(call.connection_open_at, at) or 0
            call.connection_open_at = None

    @staticmethod
    def _answer(call, at):
        if call.answered_at is None:
            call.answered_at = at
            call.setup_seconds = seconds(call.started_at, at)
            call.ringing_seconds = seconds(call.ringing_at, at)
        if call.status != "IN_PROGRESS":
            call.status = "ANSWERED"

    def _bridges(self, call, at):
        counts = {}
        for channel in call.channels:
            if channel.bridge_id and channel.ended_at is None:
                counts[channel.bridge_id] = counts.get(channel.bridge_id, 0) + 1
        if any(n >= 2 for n in counts.values()):
            if call.connection_open_at is None:
                self._answer(call, at)
                call.connection_open_at = at
                call.connected_at = call.connected_at or at
            call.status = "IN_PROGRESS"
        else:
            self._close_connection(call, at)
            if call.answered_at:
                call.status = "ANSWERED"

    def _finish(self, call, at, disposition=None):
        self._close_connection(call, at)
        call.ended_at = at
        call.total_seconds = seconds(call.started_at, at)
        call.ringing_seconds = seconds(call.ringing_at, call.answered_at or at)
        call.setup_seconds = seconds(call.started_at, call.answered_at or at)
        call.disposition = disposition or ("COMPLETED" if call.answered_at else call.disposition or "CANCELLED")
        call.status = "FAILED" if call.disposition == "UNKNOWN" else call.disposition

    def _merge(self, db, target, other):
        """An explicit DialBegin/DialEnd proves these channel groups are one call."""
        if target.id == other.id:
            return
        target.started_at = min(target.started_at, other.started_at)
        target.tracking_incomplete = target.tracking_incomplete or other.tracking_incomplete
        for name in ("ringing_at", "answered_at", "connected_at"):
            values = [v for v in (getattr(target, name), getattr(other, name)) if v]
            setattr(target, name, min(values) if values else None)
        for channel in list(other.channels):
            channel.call = target
        db.flush()
        db.delete(other)
        db.flush()

    def process(self, event, at=None):
        at = at or utcnow()
        kind = event.get("Event")
        with self.sessions.begin() as db:
            if kind in {"ContactStatus", "ContactList", "DeviceStateChange", "DeviceStateList"}:
                self._endpoint(db, event, at)
                return
            if kind not in CALL_EVENTS:
                log.debug("Ignoring AMI event %s", kind)
                return
            uid = event.get("Uniqueid")
            if not uid:
                log.warning("AMI %s missing Uniqueid", kind)
                return
            if self.snapshot_active:
                self.snapshot_seen.add(uid)
            channel = db.get(CallChannel, uid)
            linked = event.get("Linkedid") or uid
            call = channel.call if channel else db.scalar(select(Call).where(Call.linked_id == linked))
            if call is None:
                if kind in {"Hangup", "BridgeLeave", "DialEnd"}:
                    log.warning("Ignoring orphan terminal event %s for %s", kind, uid)
                    return
                call = Call(linked_id=linked, source="AMI", direction="INTERNAL", status="INITIATED",
                            started_at=at, connected_seconds=0, tracking_incomplete=kind != "Newchannel")
                db.add(call)
                db.flush()
            if call.ended_at:
                return  # repeated or late events cannot resurrect a finalized call
            if channel is None:
                channel = CallChannel(unique_id=uid, call=call, name=event.get("Channel", ""),
                                      extension=extension(event.get("Channel")))
                db.add(channel)
                db.flush()
            if channel.ended_at:
                return
            call.from_extension = call.from_extension or event.get("CallerIDNum") or channel.extension
            if kind in {"DialBegin", "DialEnd"} and event.get("DestUniqueid"):
                dest_uid = event["DestUniqueid"]
                dest = db.get(CallChannel, dest_uid)
                if dest and dest.call_id != call.id:
                    self._merge(db, call, dest.call)
                elif dest is None:
                    dest = CallChannel(unique_id=dest_uid, call=call, name=event.get("DestChannel", ""),
                                       extension=extension(event.get("DestChannel")))
                    db.add(dest)
                call.to_extension = dest.extension or event.get("DialString") or call.to_extension
                called_agent = db.scalar(select(Agent).where(Agent.extension == call.to_extension))
                if called_agent:
                    call.agent_id = called_agent.id
                if self.snapshot_active:
                    self.snapshot_seen.add(dest_uid)
            call.to_extension = call.to_extension or event.get("Exten")
            if call.agent_id is None:
                # Attribute the called agent first, otherwise the originating agent.
                agent = db.scalar(select(Agent).where(Agent.extension == call.to_extension))
                agent = agent or db.scalar(select(Agent).where(Agent.extension == call.from_extension))
                if agent:
                    call.agent_id = agent.id
            if kind == "Newstate" and event.get("ChannelStateDesc") in {"Ring", "Ringing"}:
                call.ringing_at = call.ringing_at or at
                if not call.answered_at:
                    call.status = "RINGING"
            if kind == "DialEnd":
                disposition = event.get("DialStatus", "")
                if disposition == "ANSWER":
                    self._answer(call, at)
                elif disposition in {"BUSY", "NOANSWER", "CANCEL", "CHANUNAVAIL", "CONGESTION"}:
                    call.disposition = {"BUSY": "BUSY", "NOANSWER": "NO_ANSWER", "CANCEL": "CANCELLED"}.get(disposition, "FAILED")
            if kind in {"BridgeEnter", "CoreShowChannel"}:
                channel.bridge_id = event.get("BridgeUniqueid") or event.get("BridgeId") or None
                if kind == "CoreShowChannel":
                    call.tracking_incomplete = True
                db.flush()
                self._bridges(call, at)
            if kind in {"BridgeLeave", "Hangup"}:
                channel.bridge_id = None
                if kind == "Hangup":
                    channel.ended_at = at
                    if not call.answered_at and not call.disposition:
                        call.disposition = {"17": "BUSY", "18": "NO_ANSWER", "19": "NO_ANSWER", "16": "CANCELLED"}.get(event.get("Cause"), "FAILED")
                db.flush()
                self._bridges(call, at)
                if all(c.ended_at for c in call.channels):
                    self._finish(call, max(c.ended_at for c in call.channels))

    @staticmethod
    def _endpoint(db, event, at):
        if event.get("Event") in {"DeviceStateChange", "DeviceStateList"} and not event.get("Device", "").startswith(("PJSIP/", "SIP/")):
            return  # MWI, custom hints, and other devices are not SIP endpoints.
        ext = event.get("EndpointName") or event.get("Endpoint") or event.get("Device", "").removeprefix("PJSIP/")
        ext = ext.removeprefix("SIP/")
        if not ext:
            return
        endpoint = db.get(Endpoint, ext)
        if endpoint is None:
            endpoint = Endpoint(extension=ext, contact_status="UNKNOWN", device_state="UNKNOWN", updated_at=at)
            db.add(endpoint)
        endpoint.updated_at = at
        if event.get("Event") in {"ContactStatus", "ContactList"}:
            status = event.get("ContactStatus") or event.get("Status", "UNKNOWN")
            if status != "Updated":
                endpoint.contact_status = status
        else:
            endpoint.device_state = event.get("State", "UNKNOWN")
