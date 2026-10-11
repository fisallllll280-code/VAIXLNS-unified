import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from workspace.fabric import WorkspaceFabric


def test_index_deduplicates_and_links_session_sources(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "architecture.md").write_text("VX architecture connects source provenance and session continuity.", encoding="utf-8")
    (repo / "copy.txt").write_text("VX architecture connects source provenance and session continuity.", encoding="utf-8")
    (repo / ".env").write_text("OPENAI_API_KEY=must-not-be-indexed", encoding="utf-8")
    fabric = WorkspaceFabric(tmp_path / "workspace.db", repo)

    result = fabric.rebuild_index()
    assert result["indexed"] == 2
    assert result["duplicates"] == 1
    sources = fabric.list_sources()
    assert len(sources) == 2
    assert all("must-not-be-indexed" not in row["path"] for row in sources)
    assert sum(row["status"] == "duplicate" for row in sources) == 1

    session = fabric.create_session("Architecture review")
    message = fabric.add_message(session["id"], "user", "Review VX architecture and source provenance.")
    assert message["source_ids"]
    detail = fabric.session_detail(session["id"])
    assert detail is not None
    assert len(detail["sources"]) == 1
    assert detail["messages"][0]["source_ids"] == message["source_ids"]


def test_agents_are_bounded_and_report_no_llm_execution(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "security.md").write_text("Security review requires least privilege and audit trails.", encoding="utf-8")
    fabric = WorkspaceFabric(tmp_path / "workspace.db", repo)
    fabric.rebuild_index()

    result = fabric.run_agent("security_reviewer", "Review security least privilege.")
    assert result["status"] == "completed_local_analysis"
    assert result["evidence"]
    assert any("no LLM was called" in item for item in result["limitations"])
    assert len(fabric.list_agents()) >= 10


def test_workspace_api_and_dashboard(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "readme.md").write_text("session index evidence source", encoding="utf-8")
    client = TestClient(create_app(tmp_path / "events.db", workspace_root=repo))

    assert client.get("/dashboard").status_code == 200
    overview = client.get("/workspace/overview")
    assert overview.status_code == 200
    assert overview.json()["counts"]["agents"] >= 10

    indexed = client.post("/workspace/index/rebuild", json={})
    assert indexed.status_code == 200
    session = client.post("/workspace/sessions", json={"title": "Test session"})
    assert session.status_code == 201
    session_id = session.json()["session"]["id"]
    message = client.post(
        f"/workspace/sessions/{session_id}/messages",
        json={"role": "user", "content": "Find the source index evidence."},
    )
    assert message.status_code == 201
    assert message.json()["source_ids"]
    assert client.get(f"/workspace/sessions/{session_id}").json()["sources"]



def test_external_roots_require_explicit_allowlist(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "private"
    repo.mkdir()
    outside.mkdir()
    (outside / "notes.txt").write_text("private external notes", encoding="utf-8")
    fabric = WorkspaceFabric(tmp_path / "workspace.db", repo)

    with pytest.raises(ValueError, match="EXTRA_SOURCE_ROOT_NOT_ALLOWLISTED"):
        fabric.rebuild_index([str(outside)])

    monkeypatch.setenv("VAIXLNS_ALLOWED_SOURCE_ROOTS", str(outside))
    result = fabric.rebuild_index([str(outside)])
    assert result["roots"] == 2
    assert any(source["path"].startswith("external-local/1/") for source in fabric.list_sources())
