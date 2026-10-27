from sqlalchemy import select
from app.models import Call
from test_telephony import dial, answer, hangup


def test_health(client):
    assert client.get("/health").json() == {"status": "healthy", "database": "connected", "version": "2.0.0"}
    assert client.get("/health?field=invalid").status_code == 400
    assert client.get("/asterisk/status").json()["state"] == "disabled"


def test_customer_and_agent(client):
    response = client.post("/customers", json={"name": "Test", "phone_number": "8765559999"})
    assert response.status_code == 201
    assert client.get(f'/customers/{response.json()["id"]}').json()["name"] == "Test"
    assert client.post("/customers", json={"name": "Missing phone"}).status_code == 422
    agent = {"name": "Agent", "extension": "103"}
    assert client.post("/agents", json=agent).status_code == 201
    assert client.post("/agents", json=agent).status_code == 409
    assert client.get("/agents/999").status_code == 404


def test_no_synthetic_calls(client):
    assert client.post("/calls", json={}).status_code == 409


def test_history_metadata_and_reports(client, tracker, sessions):
    agent = client.post("/agents", json={"name": "Called agent", "extension": "103"}).json()
    customer = client.post("/customers", json={"name": "Customer", "phone_number": "555"}).json()
    dial(tracker)
    answer(tracker)
    assert len(client.get("/calls/active").json()) == 1
    hangup(tracker)
    call = client.get("/calls?extension=103").json()[0]
    assert call["agent_id"] == agent["id"]
    assert call["customer_id"] is None
    assert client.patch(f'/calls/{call["id"]}', json={"status": "COMPLETED"}).status_code == 422
    assert client.patch(f'/calls/{call["id"]}', json={"customer_id": customer["id"], "notes": "Reviewed"}).status_code == 200
    assert client.delete(f'/calls/{call["id"]}').status_code == 409
    assert client.get("/calls/active").json() == []
    stats = client.get(f'/reports/agents/{agent["id"]}/statistics').json()
    assert stats["total_calls"] == stats["completed_calls"] == 1
    assert stats["average_call_duration_seconds"] == 10
    assert client.get("/reports/calls").json()["by_status"] == {"COMPLETED": 1}
    assert client.get("/reports/agents").json()[0]["total_calls"] == 1
    assert client.get("/calls?start=2027-01-01T00:00:00").json() == []
    assert client.get("/calls?limit=0").status_code == 422


def test_unknown_endpoint_is_not_available(client):
    client.post("/agents", json={"name": "Offline agent", "extension": "101"})
    endpoint = client.get("/asterisk/endpoints").json()[0]
    assert endpoint["contact_status"] == "UNKNOWN"
    assert endpoint["stale"] and not endpoint["available"]


def test_incomplete_duration_excluded(client, tracker, sessions):
    dial(tracker)
    answer(tracker)
    hangup(tracker)
    with sessions.begin() as db:
        db.scalar(select(Call)).tracking_incomplete = True
    assert client.get("/reports/calls").json()["average_call_duration_seconds"] is None


def test_live_connected_duration_includes_open_interval():
    from datetime import datetime, timedelta, timezone
    from app.models import Call
    call = Call(connected_seconds=4, connection_open_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(seconds=6))
    assert 10 <= call.measured_connected_seconds < 11


def test_database_rejects_invalid_relationship(sessions):
    import pytest
    from datetime import datetime
    from sqlalchemy.exc import IntegrityError
    with sessions() as db:
        db.add(Call(customer_id=999, source="AMI", direction="INTERNAL", status="INITIATED", started_at=datetime(2026, 1, 1)))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_database_health_failure_returns_503(client, monkeypatch):
    from unittest.mock import Mock
    from sqlalchemy.exc import OperationalError
    from app import main
    broken = Mock()
    broken.connect.side_effect = OperationalError('SELECT 1', {}, Exception('offline'))
    monkeypatch.setattr(main, 'engine', broken)
    assert client.get('/health').status_code == 503
    assert client.get('/asterisk/status').status_code == 200


def test_mixed_timezone_date_bounds_are_validated(client):
    response = client.get('/calls?start=2026-10-26T12:00:00&end=2026-10-26T11:00:00Z')
    assert response.status_code == 422
