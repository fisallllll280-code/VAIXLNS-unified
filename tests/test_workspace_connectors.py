import json

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from innovation_control.research_fabric import EvidenceClass, SourceRecord
from workspace.connectors import sync_github_sources


class FakeProvider:
    def __init__(self, allowed_repositories, token="", max_sources=12, timeout_seconds=12.0):
        self.allowed = allowed_repositories

    def search(self, query, scopes):
        assert set(scopes) <= set(self.allowed)
        return (
            SourceRecord(
                title=f"{scopes[0]}:docs/architecture.md",
                uri=f"https://github.com/{scopes[0]}/blob/" + "a" * 40 + "/docs/architecture.md",
                content="VX source provenance and connector freshness.",
                evidence_class=EvidenceClass.SECONDARY,
                revision="a" * 40,
                metadata={"repository": scopes[0]},
            ),
        )


def test_github_sync_uses_allowlist_and_persists_revision_metadata(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    from workspace.fabric import WorkspaceFabric
    fabric = WorkspaceFabric(tmp_path / "workspace.db", repo)
    monkeypatch.setenv("VAIXLNS_GITHUB_REPOSITORIES", "owner/project")
    monkeypatch.setattr("workspace.connectors.GitHubRepositorySearchProvider", FakeProvider)

    result = sync_github_sources(fabric, "architecture provenance")
    assert result["fetched"] == 1
    source = fabric.list_sources(query="architecture.md")[0]
    assert source["kind"] == "github_repository_file"
    assert source["path"] == "github/owner/project/docs/architecture.md"
    with fabric._connect() as db:
        row = db.execute("SELECT metadata_json FROM sources WHERE id=?", (source["id"],)).fetchone()
    metadata = json.loads(row["metadata_json"])
    assert metadata["revision"] == "a" * 40
    assert metadata["read_only"] is True

    with pytest.raises(PermissionError, match="GITHUB_REPOSITORY_NOT_ALLOWLISTED"):
        sync_github_sources(fabric, "architecture provenance", ["someone/else"])


def test_local_reindex_preserves_external_sources(tmp_path):
    import hashlib
    from workspace.fabric import WorkspaceFabric
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "readme.md").write_text("local source", encoding="utf-8")
    fabric = WorkspaceFabric(tmp_path / "workspace.db", repo)
    fabric.rebuild_index()
    raw = b"remote source"
    with fabric._connect() as db:
        db.execute("""INSERT INTO sources
          (id,path,kind,title,content_sha256,content,bytes,modified_at,indexed_at,status,duplicate_of,metadata_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
          ("remote1", "github/owner/repo/docs/a.md", "github_repository_file", "a.md",
           hashlib.sha256(raw).hexdigest(), raw.decode(), len(raw), 1.0, "now", "indexed", None,
           json.dumps({"repository": "owner/repo"})))
    fabric.rebuild_index()
    with fabric._connect() as db:
        assert db.execute("SELECT 1 FROM sources WHERE id='remote1'").fetchone()


def test_connector_api_requires_explicit_allowlist(tmp_path, monkeypatch):
    monkeypatch.delenv("VAIXLNS_API_TOKEN", raising=False)
    monkeypatch.delenv("VAIXLNS_GITHUB_REPOSITORIES", raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    client = TestClient(create_app(tmp_path / "events.db", workspace_root=repo))
    response = client.post("/workspace/connectors/github/sync",
                           json={"query": "architecture provenance"})
    assert response.status_code == 422
    assert response.json()["detail"] == "GITHUB_REPOSITORY_ALLOWLIST_NOT_CONFIGURED"



def test_freshness_only_marks_the_same_query_result_set_stale(tmp_path, monkeypatch):
    from workspace.fabric import WorkspaceFabric
    repo = tmp_path / "repo"
    repo.mkdir()
    fabric = WorkspaceFabric(tmp_path / "workspace.db", repo)
    monkeypatch.setenv("VAIXLNS_GITHUB_REPOSITORIES", "owner/project")
    monkeypatch.setattr("workspace.connectors.GitHubRepositorySearchProvider", FakeProvider)
    sync_github_sources(fabric, "architecture provenance")
    source = fabric.list_sources(query="architecture.md")[0]

    class EmptyProvider:
        def __init__(self, **kwargs):
            pass

        def search(self, query, scopes):
            return ()

    monkeypatch.setattr("workspace.connectors.GitHubRepositorySearchProvider", EmptyProvider)
    sync_github_sources(fabric, "architecture provenance")
    stale = next(row for row in fabric.list_sources() if row["id"] == source["id"])
    assert stale["status"] == "stale"
