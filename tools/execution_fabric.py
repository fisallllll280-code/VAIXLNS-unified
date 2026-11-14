"""Scoped execution gateway for read-only tools and explicitly admitted operations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Mapping, Sequence

GENESIS = "0" * 64
READ_SCOPES = frozenset({
    "read:assigned-evidence", "read:search", "read:public-repositories",
    "read:project-archives", "read:source-corpus", "read:innovation-registry",
    "read:research-bundle", "read:architecture-candidates", "read:engineering-contract",
    "read:implementation-plan", "read:decision-package", "read:test-results",
    "read:test-evidence", "read:provenance", "read:contracts",
})
TEXT_SUFFIXES = frozenset({".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".rs", ".ts", ".js", ".sh", ".sql", ".xml", ".csv"})
EXCLUDED_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build"})
SENSITIVE_NAMES = frozenset({".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"})
SAFE_TEST_PATTERNS = frozenset({"test_research_fabric.py", "test_external_integration_control.py", "test_external_integration_proof_boundary.py", "test_external_integration_proof_edge_cases.py", "test_federated_integration.py"})


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def resolve_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("PATH_REQUIRED")
    supplied = Path(relative)
    if supplied.is_absolute() or any(part in {"..", ""} for part in supplied.parts):
        raise PermissionError("PATH_TRAVERSAL_DENIED")
    if any(part in EXCLUDED_DIRS for part in supplied.parts):
        raise PermissionError("EXCLUDED_PATH_DENIED")
    if supplied.name.casefold() in SENSITIVE_NAMES:
        raise PermissionError("SENSITIVE_FILE_DENIED")
    unresolved = root / supplied
    if unresolved.is_symlink():
        raise PermissionError("SYMLINK_PATH_DENIED")
    path = unresolved.resolve()
    if path != root and root not in path.parents:
        raise PermissionError("PATH_OUTSIDE_REPOSITORY")
    if not path.is_file():
        raise FileNotFoundError("REPOSITORY_FILE_NOT_FOUND")
    return path


@dataclass(frozen=True)
class Principal:
    principal_id: str
    scopes: frozenset[str]
    active: bool = True


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    description: str
    required_inputs: frozenset[str] = frozenset()
    optional_inputs: frozenset[str] = frozenset()
    required_scopes: frozenset[str] = frozenset()
    scope_groups: tuple[frozenset[str], ...] = ()
    enabled: bool = True
    risk: str = "LOW"
    external_integration_id: str | None = None
    max_output_bytes: int = 262144
    read_only: bool = False

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("TOOL_ID_REQUIRED")
        if self.required_inputs & self.optional_inputs:
            raise ValueError("OVERLAPPING_INPUT_RULES")
        if any(not group for group in self.scope_groups):
            raise ValueError("EMPTY_SCOPE_GROUP")
        if self.risk not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("INVALID_RISK")
        if not isinstance(self.read_only, bool):
            raise ValueError("READ_ONLY_MUST_BE_BOOLEAN")


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    request_id: str
    principal_id: str
    tool_id: str
    status: str
    reason_code: str
    args_hash: str
    output_hash: str
    timestamp_ns: int
    previous_hash: str
    event_hash: str


@dataclass(frozen=True)
class ToolResult:
    request_id: str
    tool_id: str
    status: str
    reason_code: str
    output: Any = None
    event_hash: str = ""


class AuditLedger:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.RLock()

    def append(self, principal: Principal, tool_id: str, request_id: str, status: str,
               reason: str, args_hash: str, output_hash: str = "") -> AuditEvent:
        with self._lock:
            previous = self._events[-1].event_hash if self._events else GENESIS
            body = {
                "sequence": len(self._events) + 1, "request_id": request_id,
                "principal_id": principal.principal_id, "tool_id": tool_id,
                "status": status, "reason_code": reason, "args_hash": args_hash,
                "output_hash": output_hash, "timestamp_ns": time.time_ns(),
                "previous_hash": previous,
            }
            event = AuditEvent(**body, event_hash=digest(body))
            self._events.append(event)
            return event

    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def verify(self) -> bool:
        previous = GENESIS
        for expected, event in enumerate(self.events(), start=1):
            body = asdict(event)
            event_hash = body.pop("event_hash")
            if event.sequence != expected or event.previous_hash != previous or digest(body) != event_hash:
                return False
            previous = event_hash
        return True


Handler = Callable[[Mapping[str, Any]], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._items: dict[str, tuple[ToolSpec, Handler]] = {}

    def register(self, spec: ToolSpec, handler: Handler) -> None:
        if spec.tool_id in self._items:
            raise ValueError("DUPLICATE_TOOL_ID:" + spec.tool_id)
        if not callable(handler):
            raise TypeError("HANDLER_NOT_CALLABLE")
        self._items[spec.tool_id] = (spec, handler)

    def get(self, tool_id: str) -> tuple[ToolSpec, Handler]:
        if tool_id not in self._items:
            raise KeyError("UNKNOWN_TOOL_ID")
        return self._items[tool_id]

    def list(self) -> tuple[ToolSpec, ...]:
        return tuple(self._items[key][0] for key in sorted(self._items))


class ExecutionGateway:
    def __init__(self, registry: ToolRegistry, *, ledger: AuditLedger | None = None,
                 admitted_integrations: Sequence[str] = ()) -> None:
        self.registry = registry
        self.ledger = ledger or AuditLedger()
        # Only the trusted host may populate this after the integration proof gate.
        self._admitted_integrations = frozenset(admitted_integrations)

    def _result(self, principal: Principal, tool_id: str, request_id: str, status: str,
                reason: str, args: Mapping[str, Any], output: Any = None) -> ToolResult:
        event = self.ledger.append(principal, tool_id, request_id, status, reason,
                                   digest(args), digest(output) if output is not None else "")
        return ToolResult(request_id, tool_id, status, reason, output, event.event_hash)

    def call(self, principal: Principal, tool_id: str, args: Mapping[str, Any],
             *, request_id: str) -> ToolResult:
        if not request_id.strip():
            raise ValueError("REQUEST_ID_REQUIRED")
        safe_args = args if isinstance(args, Mapping) else {}
        if not principal.active:
            return self._result(principal, tool_id, request_id, "BLOCKED", "PRINCIPAL_INACTIVE", safe_args)
        try:
            spec, handler = self.registry.get(tool_id)
        except KeyError:
            return self._result(principal, tool_id, request_id, "BLOCKED", "TOOL_UNKNOWN", safe_args)
        if not spec.enabled:
            return self._result(principal, tool_id, request_id, "BLOCKED", "TOOL_DISABLED", safe_args)
        if spec.external_integration_id and spec.external_integration_id not in self._admitted_integrations:
            return self._result(principal, tool_id, request_id, "BLOCKED", "INTEGRATION_NOT_ADMITTED", safe_args)
        if not spec.required_scopes <= principal.scopes:
            return self._result(principal, tool_id, request_id, "BLOCKED", "REQUIRED_SCOPE_MISSING", safe_args)
        if any(not (group & principal.scopes) for group in spec.scope_groups):
            return self._result(principal, tool_id, request_id, "BLOCKED", "SCOPE_GROUP_NOT_SATISFIED", safe_args)
        if not isinstance(args, Mapping):
            return self._result(principal, tool_id, request_id, "BLOCKED", "ARGUMENTS_NOT_OBJECT", {})
        if spec.required_inputs - set(args):
            return self._result(principal, tool_id, request_id, "BLOCKED", "REQUIRED_INPUT_MISSING", args)
        if set(args) - spec.required_inputs - spec.optional_inputs:
            return self._result(principal, tool_id, request_id, "BLOCKED", "UNDECLARED_INPUT", args)
        try:
            output = handler(args)
            if len(canonical_json(output).encode("utf-8")) > spec.max_output_bytes:
                return self._result(principal, tool_id, request_id, "BLOCKED", "OUTPUT_LIMIT_EXCEEDED", args)
            return self._result(principal, tool_id, request_id, "SUCCESS", "OK", args, output)
        except PermissionError as exc:
            return self._result(principal, tool_id, request_id, "BLOCKED", str(exc)[:120] or "PERMISSION_DENIED", args)
        except Exception as exc:
            return self._result(principal, tool_id, request_id, "FAILED", "HANDLER_ERROR_" + type(exc).__name__.upper(), args)


def _search(root: Path, args: Mapping[str, Any]) -> dict[str, Any]:
    query = str(args["query"]).strip()
    if len(query) < 2:
        raise ValueError("QUERY_TOO_SHORT")
    limit = args.get("max_results", 10)
    if not is_int(limit) or not 1 <= limit <= 50:
        raise ValueError("MAX_RESULTS_OUT_OF_RANGE")
    tokens = [x.casefold() for x in __import__("re").findall(r"[A-Za-z0-9_Ωω.-]+", query) if len(x) > 1]
    results: list[dict[str, Any]] = []
    scanned = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or name.casefold() in SENSITIVE_NAMES or path.suffix.casefold() not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > 512 * 1024:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            scanned += 1
            relative = path.relative_to(root).as_posix()
            path_hits = sum(t in relative.casefold() for t in tokens)
            found = []
            for line_no, line in enumerate(text.splitlines(), 1):
                hits = sum(line.casefold().count(t) for t in tokens)
                if hits:
                    found.append({"line": line_no, "snippet": line.strip()[:300], "score": hits + 2 * path_hits})
            if found or path_hits:
                results.append({"path": relative, "sha256": sha256(text.encode("utf-8")).hexdigest(),
                                "matches": sorted(found, key=lambda x: (-x["score"], x["line"]))[:5],
                                "score": sum(x["score"] for x in found) + 3 * path_hits})
            if scanned >= 5000:
                break
        if scanned >= 5000:
            break
    results.sort(key=lambda x: (-x["score"], x["path"]))
    return {"query": query, "files_scanned": scanned, "truncated": scanned >= 5000, "results": results[:limit]}


def _read(root: Path, args: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_file(root, str(args["path"]))
    if path.stat().st_size > 512 * 1024:
        raise ValueError("FILE_SIZE_LIMIT_EXCEEDED")
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    start = args.get("start_line", 1)
    end = args.get("end_line", min(len(lines), start + 199))
    if not is_int(start) or not is_int(end) or start < 1 or end < start or end - start >= 200:
        raise ValueError("INVALID_LINE_RANGE")
    return {"path": path.relative_to(root).as_posix(), "start_line": start,
            "end_line": min(end, len(lines)), "total_lines": len(lines),
            "content": "\n".join(lines[start - 1:end]),
            "sha256": sha256(content.encode("utf-8")).hexdigest()}


def _hash_file(root: Path, args: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_file(root, str(args["path"]))
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("FILE_SIZE_LIMIT_EXCEEDED")
    raw = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def _inspect_json(root: Path, args: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_file(root, str(args["path"]))
    raw = path.read_bytes()
    if len(raw) > 512 * 1024:
        raise ValueError("JSON_SIZE_LIMIT_EXCEEDED")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_JSON_DOCUMENT") from exc
    if isinstance(value, dict):
        shape = {"shape": "object", "keys": sorted(map(str, value.keys()))[:200], "key_count": len(value)}
    elif isinstance(value, list):
        shape = {"shape": "array", "item_count": len(value)}
    else:
        shape = {"shape": "scalar", "python_type": type(value).__name__}
    return {"path": path.relative_to(root).as_posix(), "valid_json": True, "sha256": sha256(raw).hexdigest(), **shape}


def _run_unit_tests(root: Path, args: Mapping[str, Any], allowlist: frozenset[str]) -> dict[str, Any]:
    pattern = args["pattern"]
    timeout = args.get("timeout_seconds", 30)
    if pattern not in allowlist:
        raise PermissionError("TEST_PATTERN_NOT_ALLOWLISTED")
    if not is_int(timeout) or not 1 <= timeout <= 60:
        raise ValueError("TEST_TIMEOUT_OUT_OF_RANGE")
    if not (root / "tests" / pattern).is_file():
        raise FileNotFoundError("ALLOWLISTED_TEST_NOT_FOUND")
    with tempfile.TemporaryDirectory(prefix="vaixl-tools-home-") as home:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": home,
               "PYTHONPATH": str(root), "PYTHONIOENCODING": "utf-8"}
        command = ["python", "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"]
        try:
            completed = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                       text=True, timeout=timeout, check=False, shell=False)
            stdout, stderr = completed.stdout, completed.stderr
            code, timed_out = completed.returncode, False
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            code, timed_out = None, True
    return {"pattern": pattern, "command": command, "return_code": code,
            "passed": code == 0 and not timed_out, "timed_out": timed_out,
            "timeout_seconds": timeout, "output_tail": (stdout + "\n" + stderr)[-12000:]}


def build_default_gateway(
    repository_root: str | Path, *, admitted_integrations: Sequence[str] = (),
    github_provider: Any = None, github_integration_id: str = "github-readonly-research-v1",
    enable_test_runner: bool = False, test_executor: Callable[..., Any] | None = None,
) -> ExecutionGateway:
    """Create read-only local tools. External search and test execution are opt-in."""
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ValueError("REPOSITORY_ROOT_MUST_BE_DIRECTORY")
    registry = ToolRegistry()
    scope_groups = (READ_SCOPES,)
    registry.register(ToolSpec("repo.search", "Search local text/source files.",
        frozenset({"query"}), frozenset({"max_results"}), scope_groups=scope_groups, read_only=True),
        lambda args: _search(root, args))
    registry.register(ToolSpec("repo.read", "Read a bounded range from one local file.",
        frozenset({"path"}), frozenset({"start_line", "end_line"}), scope_groups=scope_groups, read_only=True),
        lambda args: _read(root, args))
    registry.register(ToolSpec("repo.sha256", "Compute a file content digest.",
        frozenset({"path"}), required_scopes=frozenset({"read:provenance"}), read_only=True),
        lambda args: _hash_file(root, args))
    registry.register(ToolSpec("json.inspect", "Parse JSON and report its shape and digest.",
        frozenset({"path"}), scope_groups=scope_groups, read_only=True),
        lambda args: _inspect_json(root, args))
    def test_handler(args: Mapping[str, Any]) -> Any:
        executor = test_executor or _run_unit_tests
        return executor(root, args, SAFE_TEST_PATTERNS)
    registry.register(ToolSpec("tests.run_unit", "Run only an allowlisted unittest pattern.",
        frozenset({"pattern"}), frozenset({"timeout_seconds"}),
        required_scopes=frozenset({"request:sandbox-test"}), enabled=enable_test_runner,
        risk="HIGH", max_output_bytes=48 * 1024), test_handler)
    if github_provider is not None:
        registry.register(ToolSpec("research.github.search", "Read-only GitHub search using an admitted provider.",
            frozenset({"query", "purpose", "repositories"}), frozenset({"max_sources"}),
            required_scopes=frozenset({"read:public-repositories"}), risk="MEDIUM", read_only=True,
            external_integration_id=github_integration_id),
            lambda args: _github_search(github_provider, args))
    return ExecutionGateway(registry, admitted_integrations=admitted_integrations)


def _github_search(provider: Any, args: Mapping[str, Any]) -> dict[str, Any]:
    from innovation_control.research_fabric import QueryPurpose, ResearchQuery
    query_text = str(args["query"]).strip()
    if not query_text:
        raise ValueError("QUERY_REQUIRED")
    purpose = QueryPurpose(str(args["purpose"]).upper())
    repositories = args["repositories"]
    if not isinstance(repositories, list) or not repositories or not all(isinstance(x, str) for x in repositories):
        raise ValueError("REPOSITORIES_MUST_BE_NONEMPTY_STRING_ARRAY")
    maximum = args.get("max_sources", 5)
    if not is_int(maximum) or not 1 <= maximum <= 12:
        raise ValueError("MAX_SOURCES_OUT_OF_RANGE")
    query_id = "Q-" + digest({"query": query_text, "purpose": purpose.value})[:12]
    records = tuple(provider.search(ResearchQuery(query_id, query_text, purpose), tuple(repositories)))[:maximum]
    return {"query_id": query_id, "purpose": purpose.value, "source_count": len(records),
            "sources": [{"source_id": x.source_id, "title": x.title, "uri": x.uri,
                         "revision": x.revision, "evidence_class": x.evidence_class.value,
                         "content_sha256": x.content_sha256, "excerpt": x.content[:1200]}
                        for x in records]}


__all__ = ["AuditEvent", "AuditLedger", "ExecutionGateway", "Principal", "SAFE_TEST_PATTERNS",
           "ToolRegistry", "ToolResult", "ToolSpec", "build_default_gateway", "canonical_json", "digest"]
