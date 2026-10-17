"""Deterministic orchestration for evidence-gated architecture experiments.

The runner composes existing discovery and promotion primitives. It does not
execute candidate code, manufacture evidence, mutate canonical state, or grant
runtime authority. Trial packages must be produced by a separately trusted
sandbox/test adapter.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Callable, Iterable, Mapping, Sequence

from evolution.architecture_lab import ArchitectureDesign, ArchitectureLab, CapabilityGap
from evolution.self_discovery import SelfDiscoveryEngine, UnknownRecord
from innovation_control.engine import (
    CounterfactualArena,
    Evidence,
    InnovationCandidate,
    ProofBeforePromotion,
    Stage,
)
from innovation_control.impact import ImpactNode


_SCORE_METRICS = (
    "correctness",
    "reliability",
    "proof_coverage",
    "reproducibility",
    "evidence_strength",
    "novelty_value",
    "operational_value",
    "blast_risk",
    "rollback_cost",
    "unresolved_unknowns",
)
_REQUIRED_OBLIGATIONS = (
    "deterministic",
    "replayable",
    "survives_adversarial_checks",
)


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _normalize_capabilities(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("CAPABILITY_NAME_REQUIRED")
        normalized.append(value.strip())
    return tuple(dict.fromkeys(normalized))


@dataclass(frozen=True)
class ArchitectureExperiment:
    """Immutable proposal set created from one mission and one capability gap."""

    mission: str
    gap: CapabilityGap
    unknowns: tuple[UnknownRecord, ...]
    designs: tuple[ArchitectureDesign, ...]
    candidates: tuple[InnovationCandidate, ...]

    @property
    def fingerprint(self) -> str:
        return _digest(
            {
                "mission": self.mission,
                "gap": asdict(self.gap),
                "unknowns": [asdict(item) for item in self.unknowns],
                "designs": [asdict(item) for item in self.designs],
                "candidates": [item.fingerprint for item in self.candidates],
            }
        )


@dataclass(frozen=True)
class ArchitectureTrial:
    """Evidence/results returned by an external isolated trial harness.

    A trial package is not proof merely because it is well-formed. The existing
    promotion gate checks evidence binding, falsification, independent
    verification, replay, proof freshness and causal impact.
    """

    metrics: Mapping[str, float]
    evidence: Evidence
    inputs: Mapping[str, Any]
    first_output: Any
    replay_fn: Callable[[Mapping[str, Any]], Any]
    proof_validity: Any | None
    now_epoch: int
    dependency_fingerprint: str
    environment_fingerprint: str
    impact_nodes: Sequence[ImpactNode]
    impact_budget: float
    forbidden_impact_nodes: frozenset[str] = frozenset()
    max_state_mutations: int = 1


@dataclass(frozen=True)
class ArchitectureCandidateOutcome:
    candidate_id: str
    variant: str
    stage: Stage
    accepted: bool
    novelty: str
    score: float | None
    arena_thresholds_passed: bool
    reasons: tuple[str, ...]
    proof_package: str | None


@dataclass(frozen=True)
class ArchitectureArenaReport:
    mission: str
    experiment_fingerprint: str
    gap_id: str
    outcomes: tuple[ArchitectureCandidateOutcome, ...]
    selected_candidate_id: str | None

    @property
    def fingerprint(self) -> str:
        return _digest(
            {
                "mission": self.mission,
                "experiment_fingerprint": self.experiment_fingerprint,
                "gap_id": self.gap_id,
                "outcomes": [
                    {
                        "candidate_id": item.candidate_id,
                        "variant": item.variant,
                        "stage": item.stage.value,
                        "accepted": item.accepted,
                        "novelty": item.novelty,
                        "score": item.score,
                        "arena_thresholds_passed": item.arena_thresholds_passed,
                        "reasons": item.reasons,
                        "proof_package": item.proof_package,
                    }
                    for item in self.outcomes
                ],
                "selected_candidate_id": self.selected_candidate_id,
            }
        )


class ArchitectureArenaRunner:
    """Connect gap discovery, 3-way search, evidence gates and admissible ranking.

    The runner's strongest state is ADMISSIBLE. Canonicalization remains a
    separate explicit governance action and is deliberately not exposed here.
    """

    def __init__(
        self,
        promotion_gate: ProofBeforePromotion,
        *,
        architecture_lab: ArchitectureLab | None = None,
        self_discovery: SelfDiscoveryEngine | None = None,
        arena: CounterfactualArena | None = None,
    ) -> None:
        self.promotion_gate = promotion_gate
        self.architecture_lab = architecture_lab or ArchitectureLab()
        self.self_discovery = self_discovery or SelfDiscoveryEngine()
        self.arena = arena or CounterfactualArena()

    def propose(
        self,
        mission: str,
        required_capabilities: Iterable[str],
        available_capabilities: Iterable[str],
        *,
        evidence_refs: Sequence[str] = (),
    ) -> ArchitectureExperiment:
        if not isinstance(mission, str) or not mission.strip():
            raise ValueError("MISSION_REQUIRED")
        mission = mission.strip()
        required = _normalize_capabilities(required_capabilities)
        available = _normalize_capabilities(available_capabilities)
        for reference in evidence_refs:
            if not isinstance(reference, str) or not reference.strip():
                raise ValueError("EVIDENCE_REFERENCE_MUST_BE_NONEMPTY")

        discovery = self.self_discovery.discover(
            mission,
            required,
            available,
            evidence=tuple(evidence_refs),
        )
        gap = discovery.gaps[0]
        designs = tuple(self.architecture_lab.search_three(gap))
        candidates = tuple(
            InnovationCandidate(
                candidate_id=f"candidate_{design.id}",
                mission=mission,
                architecture={
                    "kind": "isolated-architecture-design",
                    "design_id": design.id,
                    "gap_id": design.gap_id,
                    "variant": design.variant,
                    "components": design.components,
                    "assumptions": design.assumptions,
                    "isolated": design.isolated,
                },
                proof_obligations=_REQUIRED_OBLIGATIONS,
                lineage=("self-discovery", "nexent:architecture-search", mission, gap.id, design.id),
            )
            for design in designs
        )
        return ArchitectureExperiment(
            mission=mission,
            gap=gap,
            unknowns=discovery.unknowns,
            designs=designs,
            candidates=candidates,
        )

    @staticmethod
    def _metric_failures(metrics: Mapping[str, float]) -> tuple[str, ...]:
        failures: list[str] = []
        for key in _SCORE_METRICS:
            if key not in metrics:
                failures.append(f"METRICS:MISSING:{key}")
                continue
            value = metrics[key]
            if isinstance(value, bool):
                failures.append(f"METRICS:NON_NUMERIC:{key}")
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                failures.append(f"METRICS:NON_NUMERIC:{key}")
                continue
            if not math.isfinite(numeric):
                failures.append(f"METRICS:NON_FINITE:{key}")
            elif not 0.0 <= numeric <= 1.0:
                failures.append(f"METRICS:OUT_OF_RANGE:{key}")
        return tuple(failures)

    @staticmethod
    def _context_failures(trial: ArchitectureTrial) -> tuple[str, ...]:
        failures: list[str] = []
        if not trial.dependency_fingerprint:
            failures.append("TRIAL:DEPENDENCY_FINGERPRINT_MISSING")
        if not trial.environment_fingerprint:
            failures.append("TRIAL:ENVIRONMENT_FINGERPRINT_MISSING")
        if isinstance(trial.now_epoch, bool) or not isinstance(trial.now_epoch, int) or trial.now_epoch < 0:
            failures.append("TRIAL:INVALID_EPOCH")
        try:
            budget = float(trial.impact_budget)
        except (TypeError, ValueError):
            failures.append("TRIAL:INVALID_IMPACT_BUDGET")
        else:
            if not math.isfinite(budget) or budget < 0.0:
                failures.append("TRIAL:INVALID_IMPACT_BUDGET")
        if (
            isinstance(trial.max_state_mutations, bool)
            or not isinstance(trial.max_state_mutations, int)
            or trial.max_state_mutations < 0
        ):
            failures.append("TRIAL:INVALID_STATE_MUTATION_LIMIT")
        if not callable(trial.replay_fn):
            failures.append("TRIAL:REPLAY_FUNCTION_REQUIRED")
        return tuple(failures)

    def evaluate(
        self,
        experiment: ArchitectureExperiment,
        trials: Mapping[str, ArchitectureTrial],
        *,
        known_candidates: Sequence[InnovationCandidate] = (),
    ) -> ArchitectureArenaReport:
        """Evaluate each proposed candidate; missing/invalid trial data fails closed."""
        outcomes: list[ArchitectureCandidateOutcome] = []
        score_by_candidate: dict[str, float] = {}

        design_by_candidate = {
            f"candidate_{design.id}": design for design in experiment.designs
        }
        for candidate in experiment.candidates:
            design = design_by_candidate[candidate.candidate_id]
            novelty = self.promotion_gate.novelty.classify(candidate, known_candidates)
            trial = trials.get(candidate.candidate_id)
            if trial is None:
                outcomes.append(
                    ArchitectureCandidateOutcome(
                        candidate_id=candidate.candidate_id,
                        variant=design.variant,
                        stage=Stage.REJECTED,
                        accepted=False,
                        novelty=novelty,
                        score=None,
                        arena_thresholds_passed=False,
                        reasons=("TRIAL:PACKAGE_MISSING",),
                        proof_package=None,
                    )
                )
                continue

            failures = self._metric_failures(trial.metrics) + self._context_failures(trial)
            if failures:
                outcomes.append(
                    ArchitectureCandidateOutcome(
                        candidate_id=candidate.candidate_id,
                        variant=design.variant,
                        stage=Stage.REJECTED,
                        accepted=False,
                        novelty=novelty,
                        score=None,
                        arena_thresholds_passed=False,
                        reasons=failures,
                        proof_package=None,
                    )
                )
                continue

            decision = self.promotion_gate.evaluate(
                candidate,
                known_candidates,
                trial.metrics,
                trial.evidence,
                trial.inputs,
                trial.first_output,
                trial.replay_fn,
                trial.proof_validity,
                trial.now_epoch,
                trial.dependency_fingerprint,
                trial.environment_fingerprint,
                trial.impact_nodes,
                trial.impact_budget,
                trial.forbidden_impact_nodes,
                trial.max_state_mutations,
            )
            arena_result = self.arena.evaluate(candidate, trial.metrics)
            outcomes.append(
                ArchitectureCandidateOutcome(
                    candidate_id=candidate.candidate_id,
                    variant=design.variant,
                    stage=decision.stage,
                    accepted=decision.accepted and decision.stage is Stage.ADMISSIBLE,
                    novelty=decision.novelty,
                    score=arena_result.score,
                    arena_thresholds_passed=arena_result.mandatory_passed,
                    reasons=decision.reasons,
                    proof_package=decision.proof_package,
                )
            )
            if decision.accepted and decision.stage is Stage.ADMISSIBLE and arena_result.mandatory_passed:
                score_by_candidate[candidate.candidate_id] = arena_result.score

        selected = min(
            score_by_candidate,
            key=lambda candidate_id: (-score_by_candidate[candidate_id], candidate_id),
            default=None,
        )
        return ArchitectureArenaReport(
            mission=experiment.mission,
            experiment_fingerprint=experiment.fingerprint,
            gap_id=experiment.gap.id,
            outcomes=tuple(outcomes),
            selected_candidate_id=selected,
        )


__all__ = [
    "ArchitectureArenaReport",
    "ArchitectureArenaRunner",
    "ArchitectureCandidateOutcome",
    "ArchitectureExperiment",
    "ArchitectureTrial",
]
