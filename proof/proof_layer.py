"""Proof package builder.

Hashes are evidence fingerprints; this module does not claim formal theorem
proving. Formal verification remains a separate capability.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any

@dataclass(frozen=True)
class ProofPackage:
    proof_id: str
    evidence_fingerprint: str
    statement: str
    status: str

    @property
    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

class ProofLayer:
    def issue(self, *, proof_id: str, evidence: Any, statement: str, verified: bool) -> ProofPackage:
        fingerprint = getattr(evidence, "fingerprint", None)
        if not fingerprint:
            raise ValueError("EVIDENCE_FINGERPRINT_REQUIRED")
        return ProofPackage(
            proof_id=proof_id,
            evidence_fingerprint=fingerprint,
            statement=statement,
            status="VERIFIED" if verified else "UNPROVEN",
        )
