"""Deterministic architecture-of-intelligence search primitives.

This module does not call model providers. It ranks already-described candidate
architectures using explicit evidence and fitness criteria, then refuses
promotion unless verification evidence is present.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class ArchitectureCandidate:
    candidate_id: str
    capabilities: Tuple[str, ...]
    evidence_score: float
    verification_score: float
    reliability_score: float
    cost_score: float
    latency_score: float
    security_score: float
    notes: str = ""


@dataclass(frozen=True)
class ArchitectureFitness:
    candidate_id: str
    score: float
    dimensions: Dict[str, float]


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    promoted: bool
    reason: str


class ArchitectureSearch:
    """Select the best evidenced candidate without pretending it is proven."""

    WEIGHTS = {
        "evidence": 0.20,
        "verification": 0.25,
        "reliability": 0.20,
        "security": 0.15,
        "cost": 0.10,
        "latency": 0.10,
    }

    def evaluate(self, candidate: ArchitectureCandidate) -> ArchitectureFitness:
        dimensions = {
            "evidence": candidate.evidence_score,
            "verification": candidate.verification_score,
            "reliability": candidate.reliability_score,
            "security": candidate.security_score,
            "cost": candidate.cost_score,
            "latency": candidate.latency_score,
        }
        score = sum(dimensions[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return ArchitectureFitness(candidate.candidate_id, round(score, 6), dimensions)

    def rank(self, candidates: List[ArchitectureCandidate]) -> List[ArchitectureFitness]:
        return sorted(
            (self.evaluate(c) for c in candidates),
            key=lambda x: (-x.score, x.candidate_id),
        )

    def promote(self, fitness: ArchitectureFitness, *, proof_present: bool,
                independent_verification: bool, threshold: float = 0.80) -> PromotionDecision:
        if not proof_present:
            return PromotionDecision(fitness.candidate_id, False, "missing_proof")
        if not independent_verification:
            return PromotionDecision(fitness.candidate_id, False, "missing_independent_verification")
        if fitness.score < threshold:
            return PromotionDecision(fitness.candidate_id, False, "fitness_below_threshold")
        return PromotionDecision(fitness.candidate_id, True, "promotion_gate_passed")
