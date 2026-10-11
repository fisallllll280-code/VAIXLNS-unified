"""Local-first source/session/index/agent fabric for the VX workspace.

The fabric indexes only explicitly allowed text files under the configured repository
root. It does not crawl the network, execute indexed code, or send source content to
a model provider. Agent entries are bounded workflow roles, not claims of autonomous
LLM execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yml", ".yaml", ".toml", ".ini", ".rst", ".html", ".js", ".ts", ".sql", ".sh"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build", ".next"}
SKIP_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
MAX_FILE_BYTES = 1_000_000
MAX_FILES_PER_SCAN = 5000
MAX_RESULTS = 50


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


class WorkspaceFabric:
    """SQLite-backed, auditable links between repository sources and work sessions."""

    def __init__(self, db_path: str | Path, repo_root: str | Path):
        self.db_path = Path(db_path)
        self.repo_root = Path(repo_root).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.register_default_agents()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
              id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
              title TEXT NOT NULL, content_sha256 TEXT NOT NULL, content TEXT NOT NULL,
              bytes INTEGER NOT NULL, modified_at REAL NOT NULL, indexed_at TEXT NOT NULL,
              status TEXT NOT NULL, duplicate_of TEXT, metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
              role TEXT NOT NULL, content TEXT NOT NULL, source_ids_json TEXT NOT NULL DEFAULT '[]',
              agent_id TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS session_sources (
              session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
              source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
              relation TEXT NOT NULL DEFAULT 'referenced', created_at TEXT NOT NULL,
              PRIMARY KEY(session_id, source_id)
            );
            CREATE TABLE IF NOT EXISTS agents (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
              skills_json TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sources_sha ON sources(content_sha256);
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_session_sources_source ON session_sources(source_id);
            """)

    def register_default_agents(self) -> None:
        agents = [
            ("source_curator", "Source Curator", "catalogue sources and report provenance", ["source discovery", "provenance", "scope control"]),
            ("session_linker", "Session Linker", "connect session messages to relevant indexed sources", ["session lineage", "source links", "continuity"]),
            ("index_engineer", "Index Engineer", "rebuild and validate the local text index", ["indexing", "deduplication", "freshness"]),
            ("semantic_editor", "Semantic Editor", "identify duplicate or conflicting passages for human review", ["normalization", "duplicate review", "terminology"]),
            ("evidence_auditor", "Evidence Auditor", "separate source-backed statements from assumptions", ["evidence traceability", "uncertainty", "audit"]),
            ("architecture_analyst", "Architecture Analyst", "map modules, contracts, dependencies, and integration gaps", ["architecture", "dependency mapping", "gap analysis"]),
            ("security_reviewer", "Security Reviewer", "flag sensitive paths and unsafe integration boundaries", ["least privilege", "secrets hygiene", "trust boundaries"]),
            ("ui_observer", "UI Observer", "summarize available workspace screens and workflow states", ["dashboard", "workflow visibility", "accessibility"]),
            ("test_engineer", "Test Engineer", "recommend targeted regression tests from changed components", ["test planning", "regression coverage", "failure cases"]),
            ("workflow_coordinator", "Workflow Coordinator", "sequence bounded review stages and preserve provenance", ["orchestration", "handoffs", "status tracking"]),
        ]
        with self._connect() as db:
            for agent_id, name, role, skills in agents:
                db.execute("""INSERT INTO agents(id,name,role,skills_json,mode,status,updated_at)
                  VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name, role=excluded.role, skills_json=excluded.skills_json,
                  mode=excluded.mode, status=excluded.status, updated_at=excluded.updated_at""",
                  (agent_id, name, role, _json(skills), "bounded_local_workflow", "registered", utcnow()))

    def rebuild_index(self, extra_roots: list[str] | None = None) -> dict[str, Any]:
        roots = [self.repo_root]
        for item in extra_roots or []:
            candidate = Path(item).expanduser().resolve()
            # Explicit extra roots are accepted only when the operator supplies them;
            # they are recorded as external-local sources with a stable label.
            if candidate.is_dir() and candidate not in roots:
                roots.append(candidate)
        seen_files = 0
        indexed = 0
        skipped = 0
        duplicate_count = 0
        seen_hashes: dict[str, str] = {}
        scanned: list[tuple[str, str, str, str, int, float, str, str | None, str]] = []
        for root_no, root in enumerate(roots):
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if any(part in SKIP_DIRS for part in path.parts) or path.name in SKIP_NAMES:
                    continue
                if path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                try:
                    if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
                        skipped += 1
                        continue
                    rel = _safe_rel(path, root)
                    if root_no:
                        rel = f"external-local/{root_no}/{rel}"
                    seen_files += 1
                    if seen_files > MAX_FILES_PER_SCAN:
                        skipped += 1
                        break
                    raw = path.read_bytes()
                    text = raw.decode("utf-8")
                    # Exclude likely credential material without discarding ordinary config.
                    if re.search(r"(?im)^(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|VAIXLNS_API_TOKEN|AWS_SECRET_ACCESS_KEY)\s*=", text):
                        skipped += 1
                        continue
                    digest = hashlib.sha256(raw).hexdigest()
                    source_id = "src_" + hashlib.sha256(rel.encode()).hexdigest()[:20]
                    duplicate_of = seen_hashes.get(digest)
                    if duplicate_of:
                        duplicate_count += 1
                    else:
                        seen_hashes[digest] = source_id
                    stat = path.stat()
                    title = path.name
                    kind = "repository_file" if root_no == 0 else "external_local_file"
                    status = "duplicate" if duplicate_of else "indexed"
                    scanned.append((source_id, rel, kind, title, digest, len(raw), stat.st_mtime, status, duplicate_of, text))
                    indexed += 1
                except (OSError, UnicodeDecodeError, ValueError):
                    skipped += 1
        now = utcnow()
        with self._connect() as db:
            for source_id, rel, kind, title, digest, size, modified, status, duplicate_of, text in scanned:
                db.execute("""INSERT INTO sources
                  (id,path,kind,title,content_sha256,content,bytes,modified_at,indexed_at,status,duplicate_of,metadata_json)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(id) DO UPDATE SET path=excluded.path,kind=excluded.kind,title=excluded.title,
                  content_sha256=excluded.content_sha256,content=excluded.content,bytes=excluded.bytes,
                  modified_at=excluded.modified_at,indexed_at=excluded.indexed_at,status=excluded.status,
                  duplicate_of=excluded.duplicate_of,metadata_json=excluded.metadata_json""",
                  (source_id, rel, kind, title, digest, text, size, modified, now, status, duplicate_of, "{}"))
            # Delete only sources that disappeared; stable source IDs preserve session lineage.
            active_ids = [row[0] for row in scanned]
            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                db.execute(f"DELETE FROM sources WHERE id NOT IN ({placeholders})", active_ids)
            else:
                db.execute("DELETE FROM sources")
        return {"ok": True, "scanned": seen_files, "indexed": indexed, "skipped": skipped,
                "duplicates": duplicate_count, "roots": len(roots), "indexed_at": now}

    def list_sources(self, query: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), MAX_RESULTS))
        with self._connect() as db:
            if query and query.strip():
                needle = "%" + query.strip()[:200].replace("%", "\\%").replace("_", "\\_") + "%"
                rows = db.execute("""SELECT id,path,kind,title,content_sha256,bytes,modified_at,indexed_at,status,duplicate_of
                  FROM sources WHERE path LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'
                  ORDER BY CASE status WHEN 'indexed' THEN 0 ELSE 1 END, path LIMIT ?""",
                  (needle, needle, needle, limit)).fetchall()
            else:
                rows = db.execute("""SELECT id,path,kind,title,content_sha256,bytes,modified_at,indexed_at,status,duplicate_of
                  FROM sources ORDER BY path LIMIT ?""", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [x for x in re.findall(r"[\w.-]{2,}", query.lower())][:12]
        if not terms:
            return []
        limit = max(1, min(int(limit), 20))
        clauses = " OR ".join(["lower(content) LIKE ?" for _ in terms])
        args = ["%" + term + "%" for term in terms]
        with self._connect() as db:
            rows = db.execute(f"""SELECT id,path,title,content_sha256,status,duplicate_of,content
                FROM sources WHERE {clauses} ORDER BY CASE status WHEN 'indexed' THEN 0 ELSE 1 END, path LIMIT ?""",
                (*args, limit)).fetchall()
        results = []
        for row in rows:
            body = row["content"]
            lower = body.lower()
            at = min([lower.find(term) for term in terms if lower.find(term) >= 0] or [0])
            excerpt = re.sub(r"\s+", " ", body[max(0, at-160):at+360]).strip()
            results.append({"id": row["id"], "path": row["path"], "title": row["title"],
                            "content_sha256": row["content_sha256"], "status": row["status"],
                            "duplicate_of": row["duplicate_of"], "excerpt": excerpt})
        return results

    def create_session(self, title: str) -> dict[str, Any]:
        title = re.sub(r"\s+", " ", title).strip()[:200]
        if not title:
            raise ValueError("SESSION_TITLE_REQUIRED")
        session_id = "ses_" + uuid.uuid4().hex[:20]
        now = utcnow()
        with self._connect() as db:
            db.execute("INSERT INTO sessions(id,title,status,created_at,updated_at) VALUES(?,?,?,?,?)",
                       (session_id, title, "active", now, now))
        return {"id": session_id, "title": title, "status": "active", "created_at": now, "updated_at": now}

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT s.id,s.title,s.status,s.created_at,s.updated_at,
                COUNT(m.id) AS message_count, COUNT(DISTINCT ss.source_id) AS source_count
                FROM sessions s LEFT JOIN messages m ON m.session_id=s.id
                LEFT JOIN session_sources ss ON ss.session_id=s.id
                GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?""",
                (max(1, min(int(limit), MAX_RESULTS)),)).fetchall()
        return [dict(row) for row in rows]

    def add_message(self, session_id: str, role: str, content: str, agent_id: str | None = None) -> dict[str, Any]:
        if role not in {"user", "assistant", "system", "agent"}:
            raise ValueError("INVALID_MESSAGE_ROLE")
        content = content.strip()
        if not content or len(content) > 20000:
            raise ValueError("MESSAGE_EMPTY_OR_TOO_LARGE")
        now = utcnow()
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
                raise KeyError("SESSION_NOT_FOUND")
        related = self.search(content, limit=5)
        source_ids = [item["id"] for item in related if item["status"] == "indexed"]
        message_id = "msg_" + uuid.uuid4().hex[:20]
        with self._connect() as db:
            db.execute("""INSERT INTO messages(id,session_id,role,content,source_ids_json,agent_id,created_at)
              VALUES(?,?,?,?,?,?,?)""", (message_id, session_id, role, content, _json(source_ids), agent_id, now))
            for source_id in source_ids:
                db.execute("""INSERT INTO session_sources(session_id,source_id,relation,created_at)
                  VALUES(?,?,?,?) ON CONFLICT(session_id,source_id) DO UPDATE SET relation=excluded.relation""",
                  (session_id, source_id, "auto-linked-by-text", now))
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        return {"id": message_id, "session_id": session_id, "role": role, "content": content,
                "source_ids": source_ids, "related_sources": related, "agent_id": agent_id, "created_at": now}

    def session_detail(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not session:
                return None
            messages = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY created_at", (session_id,)).fetchall()
            sources = db.execute("""SELECT s.id,s.path,s.title,s.content_sha256,ss.relation
                FROM session_sources ss JOIN sources s ON s.id=ss.source_id WHERE ss.session_id=? ORDER BY s.path""",
                (session_id,)).fetchall()
        return {"session": dict(session), "messages": [{**dict(m), "source_ids": json.loads(m["source_ids_json"])} for m in messages],
                "sources": [dict(s) for s in sources]}

    def list_agents(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM agents ORDER BY id").fetchall()
        return [{**dict(row), "skills": json.loads(row["skills_json"])} for row in rows]

    def run_agent(self, agent_id: str, task: str, session_id: str | None = None) -> dict[str, Any]:
        agent = next((item for item in self.list_agents() if item["id"] == agent_id), None)
        if not agent:
            raise KeyError("AGENT_NOT_FOUND")
        task = task.strip()[:4000]
        if not task:
            raise ValueError("TASK_REQUIRED")
        matches = self.search(task, limit=8)
        summary = {
            "agent": {"id": agent["id"], "name": agent["name"], "mode": agent["mode"]},
            "task": task,
            "status": "completed_local_analysis",
            "evidence": matches,
            "limitations": ["Deterministic local text matching only; no LLM was called.",
                            "No repository files were modified by this agent run.",
                            "Matches are leads for review, not proof of semantic equivalence."],
            "next_steps": ["Review source excerpts and provenance", "Confirm missing sources are indexed",
                           "Add regression tests before changing runtime behavior"],
            "completed_at": utcnow(),
        }
        if session_id:
            saved = self.add_message(session_id, "agent", _json(summary), agent_id=agent_id)
            summary["session_message_id"] = saved["id"]
        return summary

    def overview(self) -> dict[str, Any]:
        with self._connect() as db:
            counts = {
                "sources": db.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                "indexed_sources": db.execute("SELECT COUNT(*) FROM sources WHERE status='indexed'").fetchone()[0],
                "duplicate_sources": db.execute("SELECT COUNT(*) FROM sources WHERE status='duplicate'").fetchone()[0],
                "sessions": db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
                "active_sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE status='active'").fetchone()[0],
                "messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
                "agents": db.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
            }
            latest = db.execute("SELECT MAX(indexed_at) FROM sources").fetchone()[0]
        return {"ok": True, "counts": counts, "repo_root": str(self.repo_root), "index_last_built_at": latest,
                "mode": "local-first; no automatic external crawling or model calls"}
