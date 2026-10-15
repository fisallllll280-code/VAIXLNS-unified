"""Validation helpers for the static VX/VLNS continuity manifest.

This module validates repository identity and evidence-state declarations. It
does not contact GitHub, probe endpoints, or claim that listed capabilities
are running.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ALLOWED_STATES = frozenset({
    "CANONICAL",
    "PARTIAL",
    "IMPLEMENTED_TESTED",
    "SPECIFIED",
    "CONTRACT",
    "DISCOVERY",
    "INCOMPLETE",
    "QUARANTINED",
    "OPEN",
})


class ManifestValidationError(ValueError):
    """Raised when the continuity manifest violates its structural contract."""


def validate_manifest(data: Mapping[str, Any]) -> None:
    if data.get("schema_version") != "1.0.0":
        raise ManifestValidationError("unsupported schema_version")
    if not data.get("manifest_id"):
        raise ManifestValidationError("manifest_id is required")

    repositories = data.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ManifestValidationError("repositories must be a non-empty list")

    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for index, repository in enumerate(repositories):
        if not isinstance(repository, dict):
            raise ManifestValidationError(f"repositories[{index}] must be an object")
        for field in ("id", "name", "url", "role", "evidence_state", "promotion_policy"):
            if not isinstance(repository.get(field), str) or not repository[field].strip():
                raise ManifestValidationError(f"repositories[{index}].{field} is required")
        if repository["id"] in seen_ids:
            raise ManifestValidationError(f"duplicate repository id: {repository['id']}")
        if repository["name"] in seen_names:
            raise ManifestValidationError(f"duplicate repository name: {repository['name']}")
        seen_ids.add(repository["id"])
        seen_names.add(repository["name"])
        if not repository["url"].startswith("https://github.com/"):
            raise ManifestValidationError(f"repository URL must be an HTTPS GitHub URL: {repository['id']}")
        if repository["evidence_state"] not in ALLOWED_STATES:
            raise ManifestValidationError(f"invalid evidence state for {repository['id']}")

    if not isinstance(data.get("canonical_flow"), list) or not data["canonical_flow"]:
        raise ManifestValidationError("canonical_flow must be a non-empty list")
    if not isinstance(data.get("invariants"), list) or not data["invariants"]:
        raise ManifestValidationError("invariants must be a non-empty list")
    if not isinstance(data.get("known_open_gaps"), list):
        raise ManifestValidationError("known_open_gaps must be a list")


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path is not None else (
        Path(__file__).resolve().parents[1] / "config" / "vx_vlns_federation.v1.json"
    )
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(f"cannot load manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestValidationError("manifest root must be an object")
    validate_manifest(data)
    return data
