from fastapi.testclient import TestClient

from api.server import create_app


def test_health_and_events_are_durable(tmp_path, monkeypatch):
    monkeypatch.setenv("VAIXLNS_API_TOKEN", "test-secret")
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
    auth = {"Authorization": "Bearer test-secret"}
    response = client.post("/events", headers=auth, json=event)
    assert response.status_code == 201
    listed = client.get("/events", headers=auth).json()
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



def test_protected_mutations_fail_closed_without_api_token(monkeypatch, tmp_path):
    monkeypatch.delenv("VAIXLNS_API_TOKEN", raising=False)
    client = TestClient(create_app(tmp_path / "no-token.db"))

    assert client.get("/health").status_code == 200
    cases = [
        ("/events", {"event_id": "no-token-1", "event_type": "TEST",
                     "aggregate_id": "agg", "actor_id": "tester", "payload": {}}),
        ("/snapshots", {"snapshot_id": "snapshot-no-token", "state": {}, "lineage": []}),
        ("/federation/probe", None),
        ("/workspace/index/rebuild", {"extra_roots": []}),
        ("/workspace/sessions", {"title": "no-token session"}),
        ("/workspace/sessions/missing/messages", {"role": "user", "content": "test"}),
        ("/workspace/agents/run", {"agent_id": "missing", "task": "test"}),
    ]
    for path, payload in cases:
        response = client.post(path, json=payload) if payload is not None else client.post(path)
        assert response.status_code == 503, (path, response.status_code, response.text)
        assert response.json()["detail"] == "AUTHENTICATION_NOT_CONFIGURED"
