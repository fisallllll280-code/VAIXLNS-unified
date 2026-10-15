import json
from pathlib import Path

from knowledge.indexer import build_index, search_index


def test_index_links_sources_and_explicit_session_exports_and_redacts_secrets(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "sessions").mkdir()
    (tmp_path / "docs" / "design.md").write_text("# VX design\nUse api_key=sk-abcdefghijklmnopqrstuvwxyz012345\n", encoding="utf-8")
    (tmp_path / "sessions" / "session-001.jsonl").write_text(
        json.dumps({"session_id": "session-001", "summary": "Indexing and source links"}) + "\\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("API_KEY=do-not-index", encoding="utf-8")
    output = tmp_path / "var" / "knowledge" / "index.json"
    index = build_index(tmp_path, output)
    assert index["record_count"] == 2
    assert output.exists()
    paths = {record["path"] for record in index["records"]}
    assert paths == {"docs/design.md", "sessions/session-001.jsonl"}
    doc = next(record for record in index["records"] if record["path"] == "docs/design.md")
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in doc["excerpt"]
    assert "[REDACTED]" in doc["excerpt"]
    results = search_index(index, "indexing source")
    assert results
    assert results[0]["score"] >= 1


def test_search_empty_query_returns_no_results(tmp_path: Path):
    (tmp_path / "README.md").write_text("# VAIXLNS\n", encoding="utf-8")
    index = build_index(tmp_path)
    assert search_index(index, "   ") == []


def test_index_is_deterministically_ordered_and_limits_results(tmp_path: Path):
    (tmp_path / "b.md").write_text("shared token", encoding="utf-8")
    (tmp_path / "a.md").write_text("shared token", encoding="utf-8")
    index = build_index(tmp_path)
    results = search_index(index, "shared token", limit=1)
    assert len(results) == 1
    assert results[0]["path"] == "a.md"
