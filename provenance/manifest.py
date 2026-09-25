"""Internal provenance manifest compatible in shape with supply-chain attestations.

This is a project provenance record, not a claim of SLSA compliance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ProvenanceManifest:
    predicate_type: str
    repository: str
    commit: str
    workflow: str
    materials: tuple[str, ...]
    builder: str
    generated_at: str
    artifact_digest: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_manifest(
    repository: str,
    commit: str,
    workflow: str,
    materials: Iterable[str],
    artifact_payload: bytes,
    builder: str = "github-actions",
) -> ProvenanceManifest:
    digest=sha256(artifact_payload).hexdigest()
    return ProvenanceManifest(
        predicate_type="https://slsa.dev/provenance/v1",
        repository=repository,
        commit=commit,
        workflow=workflow,
        materials=tuple(materials),
        builder=builder,
        generated_at=datetime.now(timezone.utc).isoformat(),
        artifact_digest=f"sha256:{digest}",
    )
