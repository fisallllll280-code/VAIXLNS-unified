"""Proof admission gate; it never upgrades weak evidence by itself."""
from dataclasses import dataclass
from continuum.proof import ProofLevel, ProofPolicy, select_proof_level

@dataclass(frozen=True)
class ProofDecision:
    admitted: bool
    level: ProofLevel | None
    reason: str

def evaluate(policy: ProofPolicy, available: list[ProofLevel], *,
             verified: bool, independently_verified: bool = False) -> ProofDecision:
    level = select_proof_level(
        policy,
        available=available,
        verified=verified,
        independently_verified=independently_verified,
    )
    if level is None:
        return ProofDecision(False, None, "PROOF_LEVEL_INSUFFICIENT")
    return ProofDecision(True, level, "PROOF_ADMITTED")
