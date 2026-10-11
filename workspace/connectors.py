"""Governed, read-only external source connectors for VX Workspace Fabric.

The first connector syncs text files from an explicit GitHub repository allowlist.
It uses the existing pinned-revision research adapter and never writes to GitHub.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Sequence

from innovation_control.research_fabric import QueryPurpose, ResearchQuery
from tools.research_adapters import GitHubRepositorySearchProvider

MAX_REPOSITORIES_PER_SYNC = 5
MAX_QUERY_LENGTH = 300
MAX_CONTENT_BYTES = 192 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def configured_github_repositories() -> tuple[str, ...]:
    """Read the administrator-owned allowlist; request payloads cannot expand it."""
    raw = os.getenv("VAIXLNS_GITHUB_REPOSITORIES", "")
    return tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))


def sync_github_sources(
    fabric: Any,
    query_text: str,
    repositories: Sequence[str] | None = None,
) -> dict[str, Any]:
    allowed = configured_github_repositories()
    if not allowed:
        raise ValueError("GITHUB_REPOSITORY_ALLOWLIST_NOT_CONFIGURED")
    selected = tuple(dict.fromkeys(repositories or allowed[:MAX_REPOSITORIES_PER_SYNC]))
    if not selected or len(selected) > MAX_REPOSITORIES_PER_SYNC:
        raise ValueError("GITHUB_REPOSITORY_COUNT_OUT_OF_RANGE")
    if set(selected) - set(allowed):
        raise PermissionError("GITHUB_REPOSITORY_NOT_ALLOWLISTED")
    query_text = query_text.strip()
    if len(query_text) < 3 or len(query_text) > MAX_QUERY_LENGTH:
        raise ValueError("GITHUB_QUERY_LENGTH_OUT_OF_RANGE")

    provider = GitHubRepositorySearchProvider(
        allowed_repositories=allowed,
        token=os.getenv("GITHUB_TOKEN", ""),
        max_sources=12,
        timeout_seconds=12.0,
    )
    query = ResearchQuery(
        query_id="workspace-sync-" + hashlib.sha256(
            (query_text + "\n" + ",".join(selected)).encode("utf-8")
        ).hexdigest()[:16],
        text=query_text,
        purpose=QueryPurpose.DISCOVERY,
    )
    # Any transport/API failure aborts the sync before changing the local catalogue.
    records = provider.search(query, selected)
    now = _now()
    epoch = time.time()
    prepared: list[dict[str, Any]] = []
    for record in records:
        repo = str(record.metadata.get("repository", ""))
        if repo not in selected:
            raise PermissionError("CONNECTOR_RETURNED_UNREQUESTED_REPOSITORY")
        uri = record.uri
        marker = f"https://github.com/{repo}/blob/"
        if not uri.startswith(marker):
            raise ValueError("CONNECTOR_SOURCE_URI_INVALID")
        relative = uri[len(marker):].split("/", 1)
        if len(relative) != 2:
            raise ValueError("CONNECTOR_SOURCE_PATH_INVALID")
        revision, path = relative
        if not revision or not path or ".." in PurePosixPath(path).parts:
            raise ValueError("CONNECTOR_SOURCE_PATH_INVALID")
        raw = record.content.encode("utf-8")
        if len(raw) > MAX_CONTENT_BYTES:
            continue
        digest = hashlib.sha256(raw).hexdigest()
        source_path = f"github/{repo}/{path}"
        source_id = "src_" + hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:20]
        prepared.append({
            "id": source_id,
            "path": source_path,
            "kind": "github_repository_file",
            "title": record.title,
            "content_sha256": digest,
            "content": record.content,
            "bytes": len(raw),
            "modified_at": epoch,
            "indexed_at": now,
            "status": "indexed",
            "duplicate_of": None,
            "metadata": {
                "provider": "github-readonly-research-v1",
                "repository": repo,
                "revision": revision,
                "uri": uri,
                "read_only": True,
                "synced_at": now,
                "query_id": query.query_id,
                "evidence_class": record.evidence_class.value,
            },
        })

    changed = 0
    duplicates = 0
    with fabric._connect() as db:
        # Mark old records stale first. Successful records below are reactivated;
        # failed provider calls never reach this transaction.
        for repo in selected:
            rows = db.execute(
                "SELECT id,metadata_json FROM sources WHERE kind='github_repository_file'"
            ).fetchall()
            for row in rows:
                try:
                    meta = json.loads(row["metadata_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    meta = {}
                # Query-scoped results must not make unrelated repository files stale.
                # Only refresh the previous result set for this exact stable query ID.
                if meta.get("repository") == repo and meta.get("query_id") == query.query_id:
                    meta["stale_since_sync"] = now
                    db.execute("UPDATE sources SET status='stale',metadata_json=? WHERE id=?",
                               (_json(meta), row["id"]))

        seen_hashes: dict[str, str] = {}
        for item in prepared:
            prior = db.execute(
                "SELECT content_sha256,metadata_json FROM sources WHERE id=?", (item["id"],)
            ).fetchone()
            meta = item["metadata"]
            if prior:
                old_digest = prior["content_sha256"]
                if old_digest != item["content_sha256"]:
                    changed += 1
                    meta["changed_since_last_sync"] = True
                    meta["previous_sha256"] = old_digest
                else:
                    try:
                        old_meta = json.loads(prior["metadata_json"] or "{}")
                    except (TypeError, json.JSONDecodeError):
                        old_meta = {}
                    meta["changed_since_last_sync"] = False
                    if old_meta.get("revision"):
                        meta["previous_revision"] = old_meta.get("revision")
            duplicate = db.execute(
                "SELECT id FROM sources WHERE content_sha256=? AND id<>? AND status IN ('indexed','duplicate') ORDER BY id LIMIT 1",
                (item["content_sha256"], item["id"]),
            ).fetchone()
            if item["content_sha256"] in seen_hashes:
                item["status"] = "duplicate"
                item["duplicate_of"] = seen_hashes[item["content_sha256"]]
                duplicates += 1
            elif duplicate:
                item["status"] = "duplicate"
                item["duplicate_of"] = duplicate["id"]
                duplicates += 1
            else:
                seen_hashes[item["content_sha256"]] = item["id"]
            db.execute("""INSERT INTO sources
                (id,path,kind,title,content_sha256,content,bytes,modified_at,indexed_at,status,duplicate_of,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                path=excluded.path,kind=excluded.kind,title=excluded.title,
                content_sha256=excluded.content_sha256,content=excluded.content,bytes=excluded.bytes,
                modified_at=excluded.modified_at,indexed_at=excluded.indexed_at,status=excluded.status,
                duplicate_of=excluded.duplicate_of,metadata_json=excluded.metadata_json""",
                (item["id"], item["path"], item["kind"], item["title"], item["content_sha256"],
                 item["content"], item["bytes"], item["modified_at"], item["indexed_at"],
                 item["status"], item["duplicate_of"], _json(meta)))
    return {
        "ok": True,
        "provider": "github-readonly-research-v1",
        "mode": "read_only",
        "query_id": query.query_id,
        "repositories": list(selected),
        "fetched": len(prepared),
        "changed": changed,
        "duplicates": duplicates,
        "freshness": "revision-pinned; absent prior matches marked stale within selected repositories",
        "synced_at": now,
        "sources": [
            {"id": item["id"], "path": item["path"], "sha256": item["content_sha256"],
             "revision": item["metadata"]["revision"], "uri": item["metadata"]["uri"],
             "status": item["status"]}
            for item in prepared
        ],
    }


__all__ = ["configured_github_repositories", "sync_github_sources"]
