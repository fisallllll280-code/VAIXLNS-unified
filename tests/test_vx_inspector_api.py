"""Integration tests of the VX Inspector HTTP read boundary."""
import os

from fastapi.testclient import TestClient
from api.server import create_app


def test_inspector_ui_and_api_are_connected(tmp_path, monkeypatch):
    monkeypatch.delenv("VAIXLNS_API_TOKEN", raising=False)
    (tmp_path / "project.genome").write_text("read-only", encoding="utf-8")
    client = TestClient(create_app(tmp_path / "events.db", workspace_root=tmp_path))
    html = client.get("/inspector")
    assert html.status_code == 200
    assert "Registry & Execution Inspector" in html.text
    r = client.get("/workspace/vx-inspector")
    assert r.status_code == 200
    result = r.json()
    assert result["g0"] == "NOT_CERTIFIED"
    assert result["release_decision"] == "HOLD"
    assert len(result["models"]) == 5
    assert result["protected"][0]["state"] == "OBSERVED"
    assert (tmp_path / "project.genome").read_text() == "read-only"


def test_inspector_requires_token_when_api_token_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("VAIXLNS_API_TOKEN", "synthetic-guard-token")
    client = TestClient(create_app(tmp_path / "secure.db", workspace_root=tmp_path))
    assert client.get("/workspace/vx-inspector").status_code == 401
    assert client.get(
        "/workspace/vx-inspector",
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401
    assert client.get(
        "/workspace/vx-inspector",
        headers={"Authorization": "Bearer synthetic-guard-token"},
    ).status_code == 200
