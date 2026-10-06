from fastapi.testclient import TestClient

from api.server import create_app


def test_health_and_events_are_durable(tmp_path):
    client = TestClient(create_app(tmp_path / "events.db"))
    assert client.get("/health").status_code == 200
    event = {
        "event_id": "api-1",
        "event_type": "TEST",
        "aggregate_id": "agg-1",
        "actor_id": "tester",
        "capability": "test",
        "payload": {"value": 42},
    }
    response = client.post("/events", json=event)
    assert response.status_code == 201
    listed = client.get("/events").json()
    assert listed["integrity"] is True
    assert listed["events"][0]["event_id"] == "api-1"


def test_api_token_guard(monkeypatch, tmp_path):
    monkeypatch.setenv("VAIXLNS_API_TOKEN", "unit-secret")
    from importlib import import_module
    module = import_module("api.server")
    client = TestClient(module.create_app(tmp_path / "secure.db"))
    assert client.post(
        "/events",
        json={
            "event_id": "secure-1",
            "event_type": "TEST",
            "aggregate_id": "agg",
            "actor_id": "tester",
            "payload": {},
        },
    ).status_code == 401
    assert client.post(
        "/events",
        headers={"Authorization": "Bearer unit-secret"},
        json={
            "event_id": "secure-1",
            "event_type": "TEST",
            "aggregate_id": "agg",
            "actor_id": "tester",
            "payload": {},
        },
    ).status_code == 201
