"""Conformance verification over governance + capability + evidence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from governance.capability_registry import CapabilityRegistry
from governance.governance_engine import GovernanceDecision
from evidence.evidence_collector import EvidenceBundle

@dataclass(frozen=True)
class VerificationResult:
    status: str
    violations: tuple[str, ...]
    evidence_fingerprint: str | None = None

class CVLVerifier:
    def verify(
        self,
        *,
        decision: GovernanceDecision,
        capability_registry: CapabilityRegistry,
        capability: str,
        evidence: EvidenceBundle | None,
        proof: Any | None = None,
    ) -> VerificationResult:
        violations: list[str] = []
        if not decision.allowed:
            violations.append("GOVERNANCE_DENIED")
        if not capability_registry.can_execute(capability):
            violations.append("CAPABILITY_INACTIVE")
        if evidence is None:
            violations.append("EVIDENCE_MISSING")
        else:
            if evidence.capability != capability:
                violations.append("EVIDENCE_CAPABILITY_MISMATCH")
            if evidence.verification_status not in {"VERIFIED", "PASSED"}:
                violations.append("EVIDENCE_NOT_VERIFIED")
        if proof is None:
            violations.append("PROOF_MISSING")
        elif getattr(proof, "evidence_fingerprint", None) != getattr(evidence, "fingerprint", None):
            violations.append("PROOF_EVIDENCE_MISMATCH")
        status = "VERIFIED" if not violations else "REJECTED"
        return VerificationResult(
            status=status,
            violations=tuple(violations),
            evidence_fingerprint=getattr(evidence, "fingerprint", None),
        )
