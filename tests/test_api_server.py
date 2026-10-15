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



def _office_registry_fixture(path):
    import json
    registry = {
        "schema_version": "1.0.0",
        "registry_id": "VAIXLNS-OFFICE-FABRIC",
        "status": "PROPOSED_IMPLEMENTATION_SEED",
        "semantics": {"zero_loss": True, "no_implicit_admission": True},
        "offices": [{
            "office_id": "OFF-TEST",
            "name": "Test Office",
            "status": "ACTIVE_REFERENCE",
            "owner_system_ids": ["SYS-VAIXLNS"],
            "tool_ids": ["TOOL-READ"],
        }],
        "systems": [{"system_id": "SYS-VAIXLNS", "status": "CANONICAL"}],
        "tool_integrations": [{
            "tool_id": "TOOL-READ",
            "name": "Read-only status",
            "kind": "source_script",
            "office_id": "OFF-TEST",
            "owner_system_id": "SYS-VAIXLNS",
            "status": "SOURCE_IMPLEMENTED",
            "access_mode": "READ_ONLY",
            "capabilities": ["read_status"],
            "contract": {"contract_id": "TEST-READ-V1", "version": "1.0.0"},
            "source_refs": ["TEST-READ-SOURCE"],
        }],
    }
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def test_office_inventory_and_route_preview_require_auth_and_never_dispatch(monkeypatch, tmp_path):
    registry_path = _office_registry_fixture(tmp_path / "office-registry.json")
    monkeypatch.setenv("VAIXLNS_OFFICE_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("VAIXLNS_API_TOKEN", "office-test-secret")
    client = TestClient(create_app(tmp_path / "office.db"))

    assert client.get("/offices").status_code == 401
    assert client.post(
        "/office-routing/preview",
        json={"office_id": "OFF-TEST", "intent": "Review readiness"},
    ).status_code == 401

    auth = {"Authorization": "Bearer office-test-secret"}
    inventory = client.get("/offices", headers=auth)
    assert inventory.status_code == 200
    assert inventory.json()["status"] == "PROPOSAL_ONLY"
    assert inventory.json()["dispatch_allowed"] is False
    assert inventory.json()["office_count"] == 1

    preview = client.post(
        "/office-routing/preview",
        headers=auth,
        json={"office_id": "OFF-TEST", "intent": "Review readiness"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["status"] == "HOLD"
    assert body["candidate_tools"][0]["tool_id"] == "TOOL-READ"
    assert body["dispatch_allowed"] is False
    assert body["external_calls_made"] is False
    assert body["canonical_write"] is False
    assert body["candidate_tools"][0]["integration_gate_state"] == "QUARANTINED"
    assert "DEPENDENCY_FINGERPRINT_MISSING" in body["candidate_tools"][0]["integration_gate_reasons"]
    assert "OFFICE_REGISTRY_NOT_ADMITTED" in body["blockers"]


def test_office_routes_fail_closed_without_token_or_registry(monkeypatch, tmp_path):
    monkeypatch.delenv("VAIXLNS_API_TOKEN", raising=False)
    monkeypatch.delenv("VAIXLNS_OFFICE_REGISTRY_PATH", raising=False)
    client = TestClient(create_app(tmp_path / "office-no-token.db"))

    response = client.get("/offices")
    assert response.status_code == 503
    assert response.json()["detail"] == "AUTHENTICATION_NOT_CONFIGURED"

    monkeypatch.setenv("VAIXLNS_API_TOKEN", "office-test-secret")
    auth = {"Authorization": "Bearer office-test-secret"}
    response = client.get("/offices", headers=auth)
    assert response.status_code == 503
    assert response.json()["detail"] == "OFFICE_REGISTRY_NOT_CONFIGURED"
