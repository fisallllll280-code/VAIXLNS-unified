"""Read-only research adapters for the governed innovation research fabric.

The local adapter is confined to a configured checkout. The GitHub adapter
uses the official API over HTTPS, reads only an explicit repository allowlist,
pins each query to a commit SHA, and never writes to GitHub.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from innovation_control.research_fabric import (
    EvidenceClass,
    ResearchQuery,
    SearchProvider,
    SourceRecord,
)

TEXT_SUFFIXES = frozenset({".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".rs", ".ts", ".tsx", ".js", ".jsx", ".sql", ".xml", ".csv"})
EXCLUDED_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build"})
SENSITIVE_NAMES = frozenset({".env", ".env.local", ".env.production", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"})
MAX_LOCAL_FILE_BYTES = 192 * 1024
MAX_REMOTE_FILE_BYTES = 192 * 1024
MAX_LOCAL_SCAN_FILES = 2500
MAX_REMOTE_CANDIDATES = 8
DEFAULT_SOURCE_LIMIT = 5
STOP_WORDS = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "into", "about", "when",
    "what", "where", "does", "have", "has", "are", "how", "under", "over", "should",
    "search", "source", "sources", "find", "research", "analysis", "investigation",
    "repository", "repositories", "current", "existing",
})


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(sorted({
        token.casefold() for token in re.findall(r"[A-Za-z0-9_Ωω.-]+", text)
        if len(token) >= 3 and token.casefold() not in STOP_WORDS
    }))


def _classify(relative_path: str) -> EvidenceClass:
    normalized = relative_path.casefold()
    name = Path(relative_path).name.casefold()
    if name == "project.genome" or normalized.startswith("registry/omega/"):
        return EvidenceClass.CANONICAL_SOURCE
    if "archive" in normalized or "recovery" in normalized or normalized.endswith(".txt"):
        return EvidenceClass.ARCHIVE
    if normalized.startswith("tests/") or "/tests/" in normalized:
        return EvidenceClass.TEST
    if normalized.startswith(("scripts/", "tools/", "agents/", "innovation_control/", "execution/")) or name.endswith((".py", ".rs", ".ts", ".js")):
        return EvidenceClass.IMPLEMENTATION
    if normalized.startswith(("artifacts/", "evidence/", "logs/")):
        return EvidenceClass.RUNTIME
    if normalized.startswith(("docs/", "schemas/", "config/")) or name.endswith((".md", ".yaml", ".yml")):
        return EvidenceClass.SECONDARY
    return EvidenceClass.UNKNOWN


def _source_record(title: str, uri: str, content: str, evidence_class: EvidenceClass,
                   revision: str, metadata: Mapping[str, str] | None = None) -> SourceRecord:
    origin = sha256(f"{uri}\n{revision}".encode("utf-8")).hexdigest()
    return SourceRecord(
        title=title,
        uri=uri,
        content=content,
        evidence_class=evidence_class,
        revision=revision,
        origin_digest=origin,
        metadata=dict(metadata or {}),
    )


@dataclass
class LocalRepositorySearchProvider:
    """Search a fixed local checkout; never traverses symlinks or secret files."""

    root: str | Path
    provider_id: str = "local-repository-readonly-v1"
    allowed_roots: tuple[str, ...] = (
        "docs", "registry", "schemas", "agents", "tests", "tools",
        "innovation_control", "integration_control", "execution", "scripts",
    )
    max_sources: int = DEFAULT_SOURCE_LIMIT
    _root: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._root = Path(self.root).resolve()
        if not self._root.is_dir():
            raise ValueError("LOCAL_REPOSITORY_ROOT_MUST_BE_DIRECTORY")
        if not 1 <= self.max_sources <= 20:
            raise ValueError("MAX_SOURCES_OUT_OF_RANGE")
        for relative in self.allowed_roots:
            resolved = (self._root / relative).resolve()
            if resolved != self._root and self._root not in resolved.parents:
                raise ValueError("LOCAL_ALLOWED_ROOT_OUTSIDE_REPOSITORY")

    def search(self, query: ResearchQuery, scopes: Sequence[str]) -> Sequence[SourceRecord]:
        terms = _tokens(query.text)
        if not terms:
            return ()
        matches: list[tuple[float, str, str, str]] = []
        scanned = 0
        for root_name in self.allowed_roots:
            base = self._root / root_name
            if not base.exists() or not base.is_dir() or base.is_symlink():
                continue
            for directory, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = sorted(
                    name for name in dirs
                    if name not in EXCLUDED_DIRS and not (Path(directory) / name).is_symlink()
                )
                for filename in sorted(files):
                    path = Path(directory) / filename
                    if path.is_symlink() or filename.casefold() in SENSITIVE_NAMES:
                        continue
                    if path.suffix.casefold() not in TEXT_SUFFIXES:
                        continue
                    try:
                        size = path.stat().st_size
                        if size > MAX_LOCAL_FILE_BYTES:
                            continue
                        content = path.read_text(encoding="utf-8")
                    except (OSError, UnicodeError):
                        continue
                    scanned += 1
                    relative = path.relative_to(self._root).as_posix()
                    path_lower = relative.casefold()
                    path_score = sum(2 for term in terms if term in path_lower)
                    content_lower = content.casefold()
                    content_score = sum(min(content_lower.count(term), 8) for term in terms)
                    score = path_score + content_score
                    if score > 0:
                        matches.append((float(score), relative, content, sha256(content.encode("utf-8")).hexdigest()))
                    if scanned >= MAX_LOCAL_SCAN_FILES:
                        break
                if scanned >= MAX_LOCAL_SCAN_FILES:
                    break
            if scanned >= MAX_LOCAL_SCAN_FILES:
                break
        matches.sort(key=lambda item: (-item[0], item[1]))
        records = []
        for score, relative, content, _ in matches[:self.max_sources]:
            records.append(_source_record(
                title=relative,
                uri=f"local://{relative}",
                content=content,
                evidence_class=_classify(relative),
                revision="working-tree",
                metadata={
                    "provider": self.provider_id,
                    "query_id": query.query_id,
                    "query_purpose": query.purpose.value,
                    "relevance_score": str(score),
                    "scan_limit_reached": str(scanned >= MAX_LOCAL_SCAN_FILES).lower(),
                },
            ))
        return tuple(records)


class JsonTransport(Protocol):
    def get_json(self, url: str, headers: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
        ...


class UrllibJsonTransport:
    """HTTPS-only JSON client for api.github.com. No arbitrary host is accepted."""

    allowed_host = "api.github.com"

    def get_json(self, url: str, headers: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
        if not url.startswith("https://api.github.com/"):
            raise PermissionError("GITHUB_TRANSPORT_HOST_DENIED")
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"GITHUB_HTTP_STATUS_{response.status}")
                raw = response.read(4 * 1024 * 1024 + 1)
        except HTTPError as exc:
            raise RuntimeError(f"GITHUB_HTTP_STATUS_{exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("GITHUB_NETWORK_ERROR") from exc
        if len(raw) > 4 * 1024 * 1024:
            raise RuntimeError("GITHUB_RESPONSE_SIZE_LIMIT")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("GITHUB_RESPONSE_INVALID_JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("GITHUB_RESPONSE_NOT_OBJECT")
        return value


@dataclass
class GitHubRepositorySearchProvider:
    """Search allowlisted GitHub repositories at a pinned commit using read-only GETs."""

    allowed_repositories: tuple[str, ...]
    token: str = ""
    provider_id: str = "github-readonly-research-v1"
    transport: JsonTransport = field(default_factory=UrllibJsonTransport)
    timeout_seconds: float = 12.0
    max_sources: int = DEFAULT_SOURCE_LIMIT
    _snapshots: dict[str, tuple[str, tuple[Mapping[str, Any], ...]]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        valid = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
        if not self.allowed_repositories or any(not valid.fullmatch(repo) for repo in self.allowed_repositories):
            raise ValueError("EXPLICIT_GITHUB_REPOSITORY_ALLOWLIST_REQUIRED")
        if len(set(self.allowed_repositories)) != len(self.allowed_repositories):
            raise ValueError("DUPLICATE_GITHUB_REPOSITORY")
        if not 1 <= self.max_sources <= 12:
            raise ValueError("MAX_SOURCES_OUT_OF_RANGE")
        if not 1 <= self.timeout_seconds <= 30:
            raise ValueError("TIMEOUT_OUT_OF_RANGE")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "VAIXLNS-ReadOnly-Research-Fabric",
        }
        token = self.token or os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = "Bearer " + token
        return headers

    def _get(self, suffix: str) -> Mapping[str, Any]:
        if not suffix.startswith("/repos/") or "://" in suffix:
            raise PermissionError("GITHUB_API_PATH_DENIED")
        url = "https://api.github.com" + suffix
        result = self.transport.get_json(url, self._headers(), self.timeout_seconds)
        if not isinstance(result, Mapping):
            raise RuntimeError("GITHUB_RESPONSE_NOT_MAPPING")
        return result

    def _snapshot(self, repository: str) -> tuple[str, tuple[Mapping[str, Any], ...]]:
        if repository not in self.allowed_repositories:
            raise PermissionError("GITHUB_REPOSITORY_NOT_ALLOWLISTED")
        if repository in self._snapshots:
            return self._snapshots[repository]
        meta = self._get(f"/repos/{repository}")
        branch = meta.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise RuntimeError("GITHUB_DEFAULT_BRANCH_MISSING")
        commit = self._get(f"/repos/{repository}/commits/{quote(branch, safe='')}")
        commit_sha = commit.get("sha")
        if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
            raise RuntimeError("GITHUB_COMMIT_SHA_INVALID")
        tree = self._get(f"/repos/{repository}/git/trees/{commit_sha}?recursive=1")
        if tree.get("truncated") is True:
            raise RuntimeError("GITHUB_TREE_TRUNCATED")
        entries = tree.get("tree")
        if not isinstance(entries, list):
            raise RuntimeError("GITHUB_TREE_MISSING")
        files = tuple(
            item for item in entries
            if isinstance(item, Mapping)
            and item.get("type") == "blob"
            and isinstance(item.get("path"), str)
            and Path(str(item["path"])).suffix.casefold() in TEXT_SUFFIXES
            and Path(str(item["path"])).name.casefold() not in SENSITIVE_NAMES
            and isinstance(item.get("size", 0), int)
            and item.get("size", 0) <= MAX_REMOTE_FILE_BYTES
            and not any(part in EXCLUDED_DIRS for part in Path(str(item["path"])).parts)
        )
        result = (commit_sha, files)
        self._snapshots[repository] = result
        return result

    def _read_blob(self, repository: str, path: str, revision: str) -> str:
        encoded_path = quote(path, safe="/")
        record = self._get(f"/repos/{repository}/contents/{encoded_path}?ref={revision}")
        if record.get("type") != "file" or record.get("encoding") != "base64":
            raise RuntimeError("GITHUB_FILE_ENCODING_UNSUPPORTED")
        content_field = record.get("content")
        if not isinstance(content_field, str):
            raise RuntimeError("GITHUB_FILE_CONTENT_MISSING")
        try:
            raw = base64.b64decode(content_field, validate=False)
            content = raw.decode("utf-8")
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("GITHUB_FILE_CONTENT_INVALID") from exc
        if len(raw) > MAX_REMOTE_FILE_BYTES:
            raise RuntimeError("GITHUB_FILE_SIZE_LIMIT")
        return content

    def search(self, query: ResearchQuery, scopes: Sequence[str]) -> Sequence[SourceRecord]:
        repositories = tuple(dict.fromkeys(scopes))
        if not repositories:
            raise ValueError("GITHUB_SEARCH_SCOPES_REQUIRED")
        unauthorized = set(repositories) - set(self.allowed_repositories)
        if unauthorized:
            raise PermissionError("GITHUB_REPOSITORY_NOT_ALLOWLISTED")
        terms = _tokens(query.text)
        if not terms:
            return ()
        selected: list[tuple[float, str, str, str, str]] = []
        for repository in repositories:
            revision, paths = self._snapshot(repository)
            scored = []
            for item in paths:
                path = str(item["path"])
                lower_path = path.casefold()
                score = sum(3 for term in terms if term in lower_path)
                if score:
                    scored.append((score, path, revision))
            scored.sort(key=lambda item: (-item[0], item[1]))
            for path_score, path, rev in scored[:MAX_REMOTE_CANDIDATES]:
                try:
                    content = self._read_blob(repository, path, rev)
                except RuntimeError as exc:
                    # Do not turn a failed read into an authoritative empty result.
                    if str(exc) in {"GITHUB_FILE_ENCODING_UNSUPPORTED", "GITHUB_FILE_CONTENT_MISSING"}:
                        continue
                    raise
                lower_content = content.casefold()
                content_score = sum(min(lower_content.count(term), 8) for term in terms)
                score = path_score + content_score
                if score:
                    uri = f"https://github.com/{repository}/blob/{rev}/{quote(path, safe='/')}"
                    selected.append((float(score), repository, path, content, rev))
        selected.sort(key=lambda item: (-item[0], item[1], item[2]))
        records = []
        for score, repository, path, content, revision in selected[:self.max_sources]:
            uri = f"https://github.com/{repository}/blob/{revision}/{quote(path, safe='/')}"
            records.append(_source_record(
                title=f"{repository}:{path}",
                uri=uri,
                content=content,
                evidence_class=_classify(path),
                revision=revision,
                metadata={
                    "provider": self.provider_id,
                    "repository": repository,
                    "query_id": query.query_id,
                    "query_purpose": query.purpose.value,
                    "relevance_score": str(score),
                    "read_only": "true",
                },
            ))
        return tuple(records)


__all__ = ["GitHubRepositorySearchProvider", "JsonTransport", "LocalRepositorySearchProvider", "UrllibJsonTransport"]
