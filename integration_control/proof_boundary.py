"""Ω Universal External Integration Proof Boundary V1.

Every model/API/server/tool/connector/repository/data source must pass the
same evidence-gated promotion path used for innovation before runtime use.

The adapter intentionally requires an explicit proof package and never
self-promotes an integration to CANONICAL.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from innovation_control.assurance import ProofFreshness, ProofValidity, VerifierProfile, Freshness
from innovation_control.engine import (
    CounterfactualArena,
    Evidence,
    FalsificationGate,
    IndependentVerificationTrio,
    InnovationCandidate,
    NoveltyShield,
    ProofBeforePromotion,
    PromotionDecision,
    ReplayVerifier,
    Stage,
)
from innovation_control.impact import CausalImpactBudget, ImpactNode
from .gateway import (
    ExternalIntegration,
    ExternalIntegrationGate,
    IntegrationDecision,
    IntegrationPolicy,
    IntegrationState,
)


@dataclass(frozen=True)
class IntegrationProofBinding:
    integration_id: str
    integration_identity: str
    proof_package: str
    validity: ProofValidity
    candidate_id: str
    stage: Stage = Stage.ADMISSIBLE

    def is_fresh(
        self,
        *,
        now_epoch: int,
        dependency_fingerprint: str,
        environment_fingerprint: str,
        current_identity: str,
    ) -> Freshness:
        if current_identity != self.integration_identity:
            return Freshness.INVALIDATED
        return ProofFreshness().evaluate(
            self.validity,
            now_epoch=now_epoch,
            dependency_fingerprint=dependency_fingerprint,
            environment_fingerprint=environment_fingerprint,
        )


@dataclass(frozen=True)
class IntegrationAdmission:
    decision: IntegrationDecision
    proof: IntegrationProofBinding | None
    promotion: PromotionDecision


class ExternalIntegrationProofBoundary:
    """Full promotion gate for external integrations."""

    def __init__(self) -> None:
        self._gate = ExternalIntegrationGate()

    @staticmethod
    def _candidate(integration: ExternalIntegration) -> InnovationCandidate:
        return InnovationCandidate(
            candidate_id=f"integration:{integration.integration_id}",
            mission=f"admit external integration {integration.name}",
            architecture={
                "kind": integration.kind.value,
                "endpoint": integration.endpoint,
                "capabilities": integration.capabilities,
                "contract_version": integration.contract_version,
            },
            proof_obligations=(
                "contract",
                "functional",
                "failure_recovery",
                "security_boundary",
                "replay",
            ),
            lineage=integration.lineage,
        )

    def admit(
        self,
        integration: ExternalIntegration,
        policy: IntegrationPolicy,
        *,
        known_candidates: Sequence[InnovationCandidate] = (),
        metrics: Mapping[str, float],
        evidence: Evidence,
        inputs: Mapping[str, Any],
        first_output: Any,
        replay_fn: Callable[[Mapping[str, Any]], Any],
        attacks: Mapping[str, Callable[[InnovationCandidate, Evidence], bool]],
        verifiers: Sequence[Callable[[InnovationCandidate, Evidence], bool]],
        verifier_profiles: Sequence[VerifierProfile],
        proof_validity: ProofValidity,
        now_epoch: int,
        impact_nodes: Sequence[ImpactNode],
        impact_budget: float,
        forbidden_impact_nodes: frozenset[str] = frozenset(),
        max_state_mutations: int = 1,
        explicit_authority: bool = False,
    ) -> IntegrationAdmission:
        base = self._gate.admit(
            integration,
            policy,
            verified=False,
            explicit_authority=False,
        )
        if base.state is IntegrationState.QUARANTINED:
            rejected = PromotionDecision(
                f"integration:{integration.integration_id}",
                Stage.REJECTED,
                False,
                "UNKNOWN",
                None,
                tuple(f"BOUNDARY:{reason}" for reason in base.reasons),
            )
            return IntegrationAdmission(base, None, rejected)

        candidate = self._candidate(integration)
        if evidence.candidate_id != candidate.candidate_id:
            rejected = PromotionDecision(
                candidate.candidate_id,
                Stage.REJECTED,
                False,
                "NOVEL",
                None,
                ("EVIDENCE:CANDIDATE_MISMATCH",),
            )
            decision = IntegrationDecision(
                integration.integration_id,
                IntegrationState.QUARANTINED,
                (),
                ("PROOF_REJECTED:EVIDENCE_CANDIDATE_MISMATCH",),
            )
            return IntegrationAdmission(decision, None, rejected)

        trio = IndependentVerificationTrio(verifiers, verifier_profiles)
        proof_gate = ProofBeforePromotion(
            NoveltyShield(),
            CounterfactualArena(),
            FalsificationGate(attacks),
            trio,
            ReplayVerifier(),
        )
        promotion = proof_gate.evaluate(
            candidate,
            known_candidates,
            metrics,
            evidence,
            inputs,
            first_output,
            replay_fn,
            proof_validity,
            now_epoch,
            integration.dependency_fingerprint,
            integration.environment_fingerprint,
            impact_nodes,
            impact_budget,
            forbidden_impact_nodes,
            max_state_mutations,
        )
        if not promotion.accepted or promotion.stage is not Stage.ADMISSIBLE:
            decision = IntegrationDecision(
                integration.integration_id,
                IntegrationState.QUARANTINED,
                (),
                tuple(f"PROOF_REJECTED:{reason}" for reason in promotion.reasons),
            )
            return IntegrationAdmission(decision, None, promotion)

        if not explicit_authority:
            decision = IntegrationDecision(
                integration.integration_id,
                IntegrationState.VERIFIED,
                tuple(sorted(integration.capabilities)),
                ("EXPLICIT_AUTHORITY_REQUIRED", "PROVEN_BUT_NOT_ADMITTED"),
            )
            return IntegrationAdmission(decision, None, promotion)

        final = self._gate.admit(
            integration,
            policy,
            verified=True,
            explicit_authority=True,
        )
        if final.state is not IntegrationState.ADMITTED:
            return IntegrationAdmission(final, None, promotion)

        binding = IntegrationProofBinding(
            integration_id=integration.integration_id,
            integration_identity=integration.identity,
            proof_package=promotion.proof_package or "",
            validity=proof_validity,
            candidate_id=candidate.candidate_id,
        )
        return IntegrationAdmission(final, binding, promotion)

    @staticmethod
    def runtime_allowed(
        integration: ExternalIntegration,
        admission: IntegrationAdmission,
        capability: str,
        *,
        now_epoch: int,
        current_dependency_fingerprint: str,
        current_environment_fingerprint: str,
    ) -> bool:
        if admission.decision.state is not IntegrationState.ADMITTED:
            return False
        if admission.proof is None or admission.proof.stage is not Stage.ADMISSIBLE:
            return False
        if capability not in admission.decision.allowed_capabilities:
            return False
        freshness = admission.proof.is_fresh(
            now_epoch=now_epoch,
            dependency_fingerprint=current_dependency_fingerprint,
            environment_fingerprint=current_environment_fingerprint,
            current_identity=integration.identity,
        )
        return freshness is Freshness.FRESH


__all__ = ["ExternalIntegrationProofBoundary", "IntegrationAdmission", "IntegrationProofBinding"]
