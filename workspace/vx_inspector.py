"""VX read-only inspector for canonical sources, test gates and model proposals.

No network, provider requests, external expenses, canonical writes, or release
admission. A passing inspection is NOT a G0 or T01-T15 certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

PROTECTED = ("project.genome", "registry/omega/omega-000-master-index.json")
PROFILES = (
    ("openai", "OpenAI", "OPENAI_API_KEY", "VX_OPENAI_MODEL", "intelligence/openai_responses_adapter.py", ["reasoning", "coding"]),
    ("claude", "Claude", "ANTHROPIC_API_KEY", "VX_CLAUDE_MODEL", "intelligence/claude_adapter.py", ["reasoning", "review"]),
    ("gemini", "Gemini", "GEMINI_API_KEY", "VX_GEMINI_MODEL", None, ["multimodal", "research"]),
    ("grok", "Grok", "XAI_API_KEY", "VX_XAI_MODEL", None, ["research", "reasoning"]),
    ("mistral", "Mistral", "MISTRAL_API_KEY", "VX_MISTRAL_MODEL", None, ["coding", "reasoning"]),
)
GROUPS = (("G1", ["T01","T02","T03","T04","T05"]),
          ("G2", ["T06","T07","T08","T09","T10"]),
          ("G3", ["T15"]), ("G4", ["T11","T12","T13","T14"]))
SOURCE_PATHS = ("integration/federation_registry.json",
                "config/vx_mission_profiles.json",
                "intelligence/open_model_registry.json",
                "workspace/fabric.py", "api/server.py")


def _safe_file(root: Path, rel: str) -> Path | None:
    """Refuse symlink files/ancestors and path traversal."""
    root = root.resolve()
    candidate = root / rel
    if candidate.is_symlink() or ".." in Path(rel).parts or Path(rel).is_absolute():
        return None
    for parent in candidate.parents:
        if parent == root:
            break
        if parent.is_symlink():
            return None
    try:
        if not candidate.resolve().is_relative_to(root):
            return None
    except (OSError, RuntimeError):
        return None
    return candidate if candidate.is_file() and candidate.stat().st_size <= 2_000_000 else None


def _file_record(root: Path, rel: str) -> dict:
    path = _safe_file(root, rel)
    if path is None:
        return {"path": rel, "state": "MISSING_OR_UNSAFE", "sha256": None}
    return {"path": rel, "state": "OBSERVED",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def inspect(root: str | Path, *, env: dict | None = None) -> dict:
    """Read-only metadata snapshot; zero external API calls."""
    root = Path(root).resolve()
    environment = os.environ if env is None else env
    protected = [_file_record(root, p) for p in PROTECTED]
    sources = [_file_record(root, p) for p in SOURCE_PATHS]
    models = []
    for ident, provider, key, model_var, adapter, capabilities in PROFILES:
        models.append({
            "id": ident, "provider": provider,
            "model": environment.get(model_var) or None,
            "credentials_present": bool(environment.get(key)),
            "adapter_state": "SOURCE_PRESENT" if adapter and _safe_file(root, adapter) else "NOT_VERIFIED",
            "connection": "NOT_TESTED",
            "execution": "DISABLED_ZERO_BUDGET",
            "capabilities": capabilities,
        })
    registry_path = _safe_file(root, "integration/federation_registry.json")
    repository_records = []
    registry_state = "UNAVAILABLE"
    if registry_path:
        try:
            doc = json.loads(registry_path.read_text(encoding="utf-8"))
            repository_records = [{
                "repository": r.get("repository"), "system": r.get("system"),
                "role": r.get("role"), "declared_status": r.get("status"),
                "identity_status": r.get("identity_status", "NOT_IN_RECORD"),
            } for r in doc.get("repositories", []) if isinstance(r, dict)]
            registry_state = "PARSED"
        except (ValueError, OSError, TypeError):
            registry_state = "INVALID"
    return {
        "schema": "VAIXLNS.VXInspector.v1",
        "mode": "READ_ONLY", "network_calls": 0, "external_budget_sar": 0,
        "release_decision": "HOLD", "g0": "NOT_CERTIFIED",
        "tests": [{"gate": name, "tests": [{"id": t, "status": "NOT_RUN"} for t in test_ids],
                   "status": "NOT_OPEN"} for name, test_ids in GROUPS],
        "protected": protected, "sources": sources, "models": models,
        "federation": {"state": registry_state, "records": repository_records,
                       "warning": "A registry declaration is not a live connection."},
        "warning": "Observation is not proof of runtime health, T01-T15, deployment or multi-model connectivity.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    args = ap.parse_args()
    print(json.dumps(inspect(args.root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
