from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
        "version": "1.0.0"
    }


def test_create_customer():
    response = client.post(
        "/customers",
        json={
            "name": "Test Customer",
            "phone_number": "876-555-9999",
            "email": "test@example.com"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test Customer"
    assert data["phone_number"] == "876-555-9999"
    assert "id" in data




def test_create_customer_invalid_phone_missing():
    response = client.post(
        "/customers",
        json={
            "name": "Invalid Customer",
            "email": "invalid@example.com"
        }
    )

    assert response.status_code == 422





def test_create_call_with_invalid_customer():
    response = client.post(
        "/calls",
        json={
            "customer_id": 999999,
            "agent_id": 1,
            "direction": "INBOUND",
            "started_at": "2026-09-10T17:00:00",
            "notes": "Test call"
        }
    )

    assert response.status_code == 404



