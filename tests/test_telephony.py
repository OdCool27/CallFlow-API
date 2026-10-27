from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from app.models import Call, CallChannel

BASE = datetime(2026, 10, 26, 12)


def event(tracker, kind, t=0, uid="a", **fields):
    tracker.process({"Event": kind, "Uniqueid": uid, "Linkedid": "a",
                     "Channel": "PJSIP/102-00000001", **fields}, BASE + timedelta(seconds=t))


def dial(tracker):
    event(tracker, "Newchannel")
    event(tracker, "DialBegin", 1, DestUniqueid="b", DestChannel="PJSIP/103-00000002")
    event(tracker, "Newchannel", 1, uid="b", Channel="PJSIP/103-00000002")
    event(tracker, "Newstate", 2, uid="b", ChannelStateDesc="Ringing")


def answer(tracker):
    event(tracker, "DialEnd", 5, DestUniqueid="b", DialStatus="ANSWER")
    event(tracker, "BridgeEnter", 5, BridgeUniqueid="bridge")
    event(tracker, "BridgeEnter", 5, uid="b", BridgeUniqueid="bridge")


def hangup(tracker, t=15):
    event(tracker, "Hangup", t, uid="b", Cause="16")
    event(tracker, "Hangup", t + 1, Cause="16")


def test_lifecycle_and_duplicates(tracker, sessions):
    dial(tracker)
    with sessions() as db:
        assert db.scalar(select(Call)).status == "RINGING"
    answer(tracker)
    event(tracker, "BridgeEnter", 6, uid="b", BridgeUniqueid="bridge")
    with sessions() as db:
        assert db.scalar(select(Call)).status == "IN_PROGRESS"
    hangup(tracker)
    hangup(tracker, 20)
    event(tracker, "Newchannel", 30)
    with sessions() as db:
        calls = db.scalars(select(Call)).all()
        assert len(calls) == 1
        call = calls[0]
        assert len(call.channels) == 2
        assert call.status == "COMPLETED"
        assert call.connected_seconds == 10
        assert call.ringing_seconds == 3
        assert call.setup_seconds == 5
        assert call.total_seconds == 16


def test_wait_for_all_channels(tracker, sessions):
    dial(tracker)
    answer(tracker)
    event(tracker, "Hangup", 15, uid="b", Cause="16")
    with sessions() as db:
        assert db.scalar(select(Call)).ended_at is None
    event(tracker, "Hangup", 16, Cause="16")
    with sessions() as db:
        assert db.scalar(select(Call)).ended_at is not None


@pytest.mark.parametrize("dial_status,status", [("BUSY", "BUSY"), ("NOANSWER", "NO_ANSWER"),
                                                   ("CANCEL", "CANCELLED"), ("CHANUNAVAIL", "FAILED")])
def test_dispositions(tracker, sessions, dial_status, status):
    dial(tracker)
    event(tracker, "DialEnd", 5, DestUniqueid="b", DialStatus=dial_status)
    hangup(tracker)
    with sessions() as db:
        call = db.scalar(select(Call))
        assert call.status == status
        assert call.connected_seconds == 0
        assert call.answered_at is None


def test_bridge_leave_excludes_hold_time(tracker, sessions):
    dial(tracker)
    answer(tracker)
    event(tracker, "BridgeLeave", 10, uid="b", BridgeUniqueid="bridge")
    event(tracker, "BridgeEnter", 20, uid="b", BridgeUniqueid="bridge")
    hangup(tracker, 25)
    with sessions() as db:
        assert db.scalar(select(Call)).connected_seconds == 10


def test_reconnect_missing_channels(tracker, sessions):
    dial(tracker)
    tracker.mark_disconnected()
    tracker.begin_snapshot()
    tracker.reconcile(BASE + timedelta(seconds=40))
    with sessions() as db:
        call = db.scalar(select(Call))
        assert call.disposition == "UNKNOWN"
        assert call.status == "FAILED"
        assert call.tracking_incomplete
        assert call.ended_at is not None


def test_reconnect_retains_live_channels(tracker, sessions):
    dial(tracker)
    tracker.mark_disconnected()
    tracker.begin_snapshot()
    event(tracker, "CoreShowChannel", 40, BridgeId="x")
    event(tracker, "CoreShowChannel", 40, uid="b", BridgeId="x")
    tracker.reconcile(BASE + timedelta(seconds=41))
    with sessions() as db:
        call = db.scalar(select(Call))
        assert call.ended_at is None
        assert call.tracking_incomplete
        assert call.connection_open_at == BASE + timedelta(seconds=40)


def test_merge_explicit_dial_groups(tracker, sessions):
    event(tracker, "Newchannel")
    event(tracker, "Newchannel", uid="b", Linkedid="b", Channel="PJSIP/103-00000002")
    event(tracker, "DialBegin", 1, DestUniqueid="b", DestChannel="PJSIP/103-00000002")
    with sessions() as db:
        assert len(db.scalars(select(Call)).all()) == 1
        assert len(db.scalars(select(CallChannel)).all()) == 2


def test_endpoint_status_and_non_sip_devices(tracker, sessions):
    from app.models import Endpoint
    tracker.process({"Event": "ContactStatus", "EndpointName": "103", "ContactStatus": "Reachable"})
    tracker.process({"Event": "ContactStatus", "EndpointName": "103", "ContactStatus": "Updated"})
    tracker.process({"Event": "DeviceStateChange", "Device": "PJSIP/103", "State": "INUSE"})
    tracker.process({"Event": "DeviceStateChange", "Device": "MWI:1234@default", "State": "NOT_INUSE"})
    with sessions() as db:
        endpoint = db.get(Endpoint, "103")
        assert endpoint.contact_status == "Reachable"
        assert endpoint.device_state == "INUSE"
        assert len(db.scalars(select(Endpoint)).all()) == 1
    tracker.mark_disconnected()
    with sessions() as db:
        assert db.get(Endpoint, "103").contact_status == "UNKNOWN"


def test_unknown_hangup_does_not_manufacture_call(tracker, sessions):
    event(tracker, "Hangup", Cause="16")
    with sessions() as db:
        assert db.scalars(select(Call)).all() == []
