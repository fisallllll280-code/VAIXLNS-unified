"""Ω Innovation Control V1.
Evidence-gated invention promotion with deterministic novelty, falsification,
independent verification, replay, and admission decisions.

This module deliberately does NOT claim formal theorem proving. It is a
small executable gate that can be used by NEXENT/VX as a promotion boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

from innovation_control.assurance import Freshness, ProofFreshness, VerificationDiversity, VerifierProfile
from innovation_control.impact import CausalImpactBudget, ImpactNode


class Stage(str, Enum):
    IDEA = "IDEA"
    HYPOTHESIS = "HYPOTHESIS"
    SPEC = "SPEC"
    SANDBOX = "SANDBOX"
    TEST = "TEST"
    EVIDENCE = "EVIDENCE"
    VERIFIED = "VERIFIED"
    REPRODUCED = "REPRODUCED"
    PROVEN = "PROVEN"
    ADMISSIBLE = "ADMISSIBLE"
    CANONICAL = "CANONICAL"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class InnovationCandidate:
    candidate_id: str
    mission: str
    architecture: Mapping[str, Any]
    proof_obligations: tuple[str, ...]
    lineage: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        """Identity of the exact candidate record, including lineage."""
        return _digest({
            "mission": self.mission,
            "architecture": self.architecture,
            "proof_obligations": self.proof_obligations,
            "lineage": self.lineage,
        })

    @property
    def novelty_fingerprint(self) -> str:
        """Architecture identity used for duplicate detection; lineage is not novelty."""
        return _digest({
            "mission": self.mission,
            "architecture": self.architecture,
            "proof_obligations": self.proof_obligations,
        })


@dataclass(frozen=True)
class Evidence:
    candidate_id: str
    execution_digest: str
    test_ids: tuple[str, ...]
    environment: Mapping[str, str]
    observations: Mapping[str, Any]
    source_refs: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class ArenaResult:
    candidate_id: str
    metrics: Mapping[str, float]
    score: float
    mandatory_passed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    verifier_id: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    stage: Stage
    accepted: bool
    novelty: str
    proof_package: str | None
    reasons: tuple[str, ...]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_stable_json(value).encode()).hexdigest()


class NoveltyShield:
    """Reject exact duplicates and expose unresolved novelty as a blocker."""

    def classify(self, candidate: InnovationCandidate, known: Sequence[InnovationCandidate]) -> str:
        fp = candidate.novelty_fingerprint
        if any(k.novelty_fingerprint == fp for k in known):
            return "REDUNDANT"
        if any(set(candidate.architecture.keys()).intersection(k.architecture.keys()) for k in known):
            return "COMPOSITE_NOVEL"
        if not candidate.architecture or not candidate.proof_obligations:
            return "UNKNOWN"
        return "NOVEL"


class CounterfactualArena:
    """Compare isolated candidates by evidence-weighted metrics, not prose preference."""

    DEFAULT_THRESHOLDS = {
        "correctness": 0.95,
        "reliability": 0.90,
        "proof_coverage": 0.90,
        "reproducibility": 0.95,
    }

    def evaluate(self, candidate: InnovationCandidate, metrics: Mapping[str, float], thresholds: Mapping[str, float] | None = None) -> ArenaResult:
        limits = dict(thresholds or self.DEFAULT_THRESHOLDS)
        reasons = tuple(
            f"{key}<{limits[key]}"
            for key in limits
            if float(metrics.get(key, 0.0)) < float(limits[key])
        )
        score = (
            float(metrics.get("evidence_strength", 0.0))
            * float(metrics.get("reproducibility", 0.0))
            * float(metrics.get("reliability", 0.0))
            * float(metrics.get("proof_coverage", 0.0))
            * float(metrics.get("novelty_value", 0.0))
            * float(metrics.get("operational_value", 0.0))
            - float(metrics.get("blast_risk", 0.0))
            - float(metrics.get("rollback_cost", 0.0))
            - float(metrics.get("unresolved_unknowns", 0.0))
        )
        return ArenaResult(candidate.candidate_id, dict(metrics), score, not reasons, reasons)

    def rank(
        self,
        candidates: Sequence[tuple[InnovationCandidate, Mapping[str, float]]],
        thresholds: Mapping[str, float] | None = None,
    ) -> tuple[ArenaResult, ...]:
        """Deterministically rank alternative architectures by measured score."""
        results = tuple(self.evaluate(candidate, metrics, thresholds) for candidate, metrics in candidates)
        return tuple(sorted(results, key=lambda item: (-item.score, item.candidate_id)))


class FalsificationGate:
    """Execute explicit attempts to disprove every mandatory proof obligation."""

    def __init__(self, attacks: Mapping[str, Callable[[InnovationCandidate, Evidence], bool]]):
        self.attacks = dict(attacks)

    def run(self, candidate: InnovationCandidate, evidence: Evidence) -> tuple[str, ...]:
        failures: list[str] = []
        for obligation in candidate.proof_obligations:
            attack = self.attacks.get(obligation)
            if attack is None or not bool(attack(candidate, evidence)):
                failures.append(obligation)
        return tuple(failures)


class IndependentVerificationTrio:
    """Three verifiers plus an independence check; count alone is not independence."""

    def __init__(
        self,
        verifiers: Sequence[Callable[[InnovationCandidate, Evidence], bool]],
        profiles: Sequence[VerifierProfile],
        diversity_threshold: float = 0.5,
    ):
        if len(verifiers) != 3:
            raise ValueError("VERIFIER_TRIO_REQUIRED")
        if len(profiles) != 3:
            raise ValueError("VERIFIER_PROFILE_TRIO_REQUIRED")
        self.verifiers = tuple(verifiers)
        self.diversity = VerificationDiversity().assess(profiles, threshold=diversity_threshold)

    def verify(self, candidate: InnovationCandidate, evidence: Evidence) -> tuple[VerificationResult, ...]:
        results: list[VerificationResult] = []
        for i, fn in enumerate(self.verifiers, start=1):
            passed = bool(fn(candidate, evidence))
            results.append(VerificationResult(f"verifier-{i}", passed, "PASS" if passed else "FAIL"))
        return tuple(results)


class ReplayVerifier:
    """Verify deterministic replay by comparing execution digests."""

    def verify(self, inputs: Mapping[str, Any], first_output: Any, replay_fn: Callable[[Mapping[str, Any]], Any]) -> bool:
        replay_output = replay_fn(dict(inputs))
        return _digest(first_output) == _digest(replay_output)


class ProofBeforePromotion:
    """Final gate: PROVEN first, then ADMISSIBLE; CANONICAL is explicit and separate."""

    def __init__(self, novelty: NoveltyShield, arena: CounterfactualArena, falsifier: FalsificationGate, trio: IndependentVerificationTrio, replay: ReplayVerifier):
        self.novelty = novelty
        self.arena = arena
        self.falsifier = falsifier
        self.trio = trio
        self.replay = replay

    def evaluate(
        self,
        candidate: InnovationCandidate,
        known: Sequence[InnovationCandidate],
        metrics: Mapping[str, float],
        evidence: Evidence,
        inputs: Mapping[str, Any],
        first_output: Any,
        replay_fn: Callable[[Mapping[str, Any]], Any],
        proof_validity: Any | None = None,
        proof_now_epoch: int | None = None,
        dependency_fingerprint: str | None = None,
        environment_fingerprint: str | None = None,
        impact_nodes: Sequence[ImpactNode] | None = None,
        impact_budget: float | None = None,
        forbidden_impact_nodes: frozenset[str] = frozenset(),
        max_state_mutations: int = 1,
    ) -> PromotionDecision:
        reasons: list[str] = []
        novelty = self.novelty.classify(candidate, known)
        arena = self.arena.evaluate(candidate, metrics)
        if novelty in {"REDUNDANT", "UNKNOWN"}:
            reasons.append(f"NOVELTY:{novelty}")
        if not arena.mandatory_passed:
            reasons.extend(f"ARENA:{r}" for r in arena.reasons)
        if not self.trio.diversity.passed:
            reasons.append("INDEPENDENT:DIVERSITY:FAIL")
        failures = self.falsifier.run(candidate, evidence)
        if failures:
            reasons.extend(f"FALSIFICATION:{x}" for x in failures)
        verifications = self.trio.verify(candidate, evidence)
        if not all(v.passed for v in verifications):
            reasons.extend(f"INDEPENDENT:{v.verifier_id}:FAIL" for v in verifications if not v.passed)
        if not self.replay.verify(inputs, first_output, replay_fn):
            reasons.append("REPLAY:FAIL")
        if evidence.candidate_id != candidate.candidate_id:
            reasons.append("EVIDENCE:CANDIDATE_MISMATCH")
        if impact_nodes is None or impact_budget is None:
            reasons.append("IMPACT:CONTEXT_MISSING")
        else:
            impact = CausalImpactBudget().assess(
                impact_nodes,
                budget=impact_budget,
                forbidden_nodes=forbidden_impact_nodes,
                max_state_mutations=max_state_mutations,
            )
            if not impact.passed:
                reasons.extend(f"IMPACT:{item}" for item in impact.blocked)
        if proof_validity is None:
            reasons.append("PROOF:FRESHNESS_CONTEXT_MISSING")
        elif proof_now_epoch is None or dependency_fingerprint is None or environment_fingerprint is None:
            reasons.append("PROOF:FRESHNESS_CONTEXT_MISSING")
        else:
            freshness = ProofFreshness().evaluate(
                proof_validity,
                now_epoch=proof_now_epoch,
                dependency_fingerprint=dependency_fingerprint,
                environment_fingerprint=environment_fingerprint,
            )
            if freshness is not Freshness.FRESH:
                reasons.append(f"PROOF:{freshness.value}")
        if reasons:
            return PromotionDecision(candidate.candidate_id, Stage.REJECTED, False, novelty, None, tuple(reasons))
        proof_payload = {
            "candidate": candidate.fingerprint,
            "evidence": evidence.fingerprint,
            "arena": arena.score,
            "verifiers": [asdict(v) for v in verifications],
            "verification_diversity": self.trio.diversity.score,
            "replay": True,
            "proof_freshness": "FRESH",
            "impact_budget": impact_budget,

        }
        proof = _digest(proof_payload)
        return PromotionDecision(candidate.candidate_id, Stage.ADMISSIBLE, True, novelty, proof, ("PROVEN", "ADMISSIBLE"))

    @staticmethod
    def canonicalize(decision: PromotionDecision, explicit_authority: bool) -> PromotionDecision:
        if decision.stage is not Stage.ADMISSIBLE or not decision.accepted or not explicit_authority:
            raise ValueError("CANONICAL_PROMOTION_REQUIRES_ADMISSIBLE_AND_EXPLICIT_AUTHORITY")
        return PromotionDecision(decision.candidate_id, Stage.CANONICAL, True, decision.novelty, decision.proof_package, decision.reasons + ("CANONICAL",))


__all__ = [
    "ArenaResult", "CounterfactualArena", "Evidence", "FalsificationGate", "IndependentVerificationTrio",
    "InnovationCandidate", "NoveltyShield", "ProofBeforePromotion", "PromotionDecision", "ReplayVerifier", "Stage", "VerificationResult",
]
