"""Deterministic, local-first index for repository sources and imported sessions.

The index records metadata and excerpts, not secrets or full session transcripts.
It never fetches remote URLs. Session files are only read from the explicit
sessions/ directory after the user/operator imports them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {".md", ".txt", ".rst", ".py", ".json", ".yaml", ".yml", ".toml"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}
SKIP_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519", "credentials.json"}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*['\"]?([^\s'\"\x60,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
]
MAX_FILE_BYTES = 1_000_000
MAX_EXCERPT_CHARS = 1200


def _redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or path.name in SKIP_NAMES:
            continue
        if rel.parts and rel.parts[0] == "var":
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _record(root: Path, path: Path, kind: str) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    rel = path.relative_to(root).as_posix()
    safe = _redact(raw)
    title = next((line.lstrip("# ").strip() for line in safe.splitlines() if line.strip()), path.name)
    return {
        "id": hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16],
        "kind": kind,
        "path": rel,
        "title": title[:180],
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "bytes": len(raw.encode("utf-8")),
        "excerpt": safe[:MAX_EXCERPT_CHARS],
        "source_ref": f"repo:{rel}",
    }


def build_index(root: Path, output: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    records: list[dict[str, Any]] = []
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("sessions/"):
            kind = "session_export"
        elif rel.startswith(("docs/", "README", "CLAUDE.md")):
            kind = "document"
        elif rel.startswith("tests/"):
            kind = "verification"
        elif rel.startswith("config/"):
            kind = "registry_or_policy"
        elif rel.startswith("integrations/"):
            kind = "integration_code"
        else:
            kind = "source_code"
        record = _record(root, path, kind)
        if record:
            records.append(record)

    index = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_root_name": root.name,
        "mode": "local_metadata_index",
        "network_access": False,
        "session_policy": "only explicitly imported files under sessions/ are indexed",
        "record_count": len(records),
        "records": records,
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def search_index(index: dict[str, Any], query: str, limit: int = 10) -> list[dict[str, Any]]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    if not terms:
        return []
    ranked = []
    for record in index.get("records", []):
        haystack = " ".join(str(record.get(key, "")) for key in ("path", "title", "excerpt", "kind")).casefold()
        score = sum(haystack.count(term) for term in terms)
        if score:
            ranked.append((score, record))
    ranked.sort(key=lambda item: (-item[0], item[1].get("path", "")))
    return [{**record, "score": score} for score, record in ranked[:max(1, min(limit, 100))]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/search a local-first VAIXLNS knowledge index")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("var/knowledge/index.json"))
    parser.add_argument("--query")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    index = build_index(args.root, output)
    if args.query:
        print(json.dumps(search_index(index, args.query), ensure_ascii=False, indent=2))
    else:
        print(f"Indexed {index['record_count']} text sources; output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
