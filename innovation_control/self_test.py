"""Ω Innovation Control self-adversarial conformance suite.

This suite treats Innovation Control as a candidate and subjects it to the
same promotion boundary it enforces on other innovations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from innovation_control.assurance import ProofFreshness
from innovation_control.engine import (
    CounterfactualArena,
    Evidence,
    FalsificationGate,
    IndependentVerificationTrio,
    InnovationCandidate,
    NoveltyShield,
    ProofBeforePromotion,
    ReplayVerifier,
    Stage,
)
from innovation_control.impact import CausalImpactBudget, ImpactNode
from innovation_control.assurance import VerifierProfile


@dataclass(frozen=True)
class SelfTestResult:
    scenario: str
    passed: bool
    reasons: tuple[str, ...]


def _candidate() -> InnovationCandidate:
    return InnovationCandidate(
        candidate_id="innovation-control-self",
        mission="validate the innovation admission mechanism against itself",
        architecture={
            "novelty": "shield",
            "arena": "counterfactual",
            "falsification": "mandatory",
            "verification": "diverse",
            "replay": "mandatory",
            "freshness": "scoped",
            "impact": "budgeted",
        },
        proof_obligations=("deterministic", "replayable", "survives_adversarial_checks"),
        lineage=("vaixlns:self-test",),
    )


def _evidence(candidate: InnovationCandidate) -> Evidence:
    return Evidence(
        candidate_id=candidate.candidate_id,
        execution_digest="self-test-execution-v1",
        test_ids=("success", "falsification", "replay", "freshness", "impact"),
        environment={"suite": "innovation-control-self-test", "version": "v1"},
        observations={"all_required_controls_exercised": True},
    )


def _metrics() -> dict[str, float]:
    return {
        "correctness": 0.99,
        "reliability": 0.99,
        "proof_coverage": 1.0,
        "reproducibility": 1.0,
        "evidence_strength": 1.0,
        "novelty_value": 0.95,
        "operational_value": 0.95,
        "blast_risk": 0.01,
        "rollback_cost": 0.01,
        "unresolved_unknowns": 0.0,
    }


def _gate(*, shared_verifiers: bool = False) -> ProofBeforePromotion:
    profiles = (
        [
            VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
            VerifierProfile("v2", "impl-a", "symbolic", ("e1",), "rule"),
            VerifierProfile("v3", "impl-a", "symbolic", ("e1",), "rule"),
        ]
        if shared_verifiers
        else [
            VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
            VerifierProfile("v2", "impl-b", "replay", ("e2",), "hash"),
            VerifierProfile("v3", "impl-c", "statistical", ("e3",), "model"),
        ]
    )
    return ProofBeforePromotion(
        NoveltyShield(),
        CounterfactualArena(),
        FalsificationGate({
            "deterministic": lambda c, e: True,
            "replayable": lambda c, e: True,
            "survives_adversarial_checks": lambda c, e: True,
        }),
        IndependentVerificationTrio(
            [lambda c, e: True, lambda c, e: True, lambda c, e: True],
            profiles,
        ),
        ReplayVerifier(),
    )


def _fresh(candidate: InnovationCandidate) -> Any:
    evidence = _evidence(candidate)
    return ProofFreshness.issue(
        evidence_fingerprint=evidence.fingerprint,
        issued_epoch=100,
        ttl_epochs=100,
        dependency_fingerprint="dep:v1",
        environment_fingerprint="env:v1",
    )


def _impact() -> tuple[list[ImpactNode], float, frozenset[str], int]:
    return ([ImpactNode("self-test-sandbox", 0.2, False)], 0.5, frozenset({"constitution"}), 1)


def run_self_test() -> tuple[SelfTestResult, ...]:
    candidate = _candidate()
    evidence = _evidence(candidate)
    impact_nodes, budget, forbidden, mutation_limit = _impact()
    results: list[SelfTestResult] = []

    # 1. Positive proof path must reach ADMISSIBLE, never CANONICAL automatically.
    decision = _gate().evaluate(
        candidate, [], _metrics(), evidence, {"x": 21}, 42, lambda p: p["x"] * 2,
        _fresh(candidate), 120, "dep:v1", "env:v1",
        impact_nodes, budget, forbidden, mutation_limit,
    )
    results.append(SelfTestResult(
        "positive-path", decision.accepted and decision.stage is Stage.ADMISSIBLE,
        decision.reasons,
    ))

    # 2. Falsification must kill a candidate.
    kill = ProofBeforePromotion(
        NoveltyShield(),
        CounterfactualArena(),
        FalsificationGate({
            "deterministic": lambda c, e: False,
            "replayable": lambda c, e: True,
            "survives_adversarial_checks": lambda c, e: True,
        }),
        IndependentVerificationTrio(
            [lambda c, e: True, lambda c, e: True, lambda c, e: True],
            [
                VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
                VerifierProfile("v2", "impl-b", "replay", ("e2",), "hash"),
                VerifierProfile("v3", "impl-c", "statistical", ("e3",), "model"),
            ],
        ),
        ReplayVerifier(),
    )
    decision = kill.evaluate(
        candidate, [], _metrics(), evidence, {"x": 21}, 42, lambda p: p["x"] * 2,
        _fresh(candidate), 120, "dep:v1", "env:v1",
        impact_nodes, budget, forbidden, mutation_limit,
    )
    results.append(SelfTestResult(
        "falsification-kill", not decision.accepted and decision.stage is Stage.REJECTED
        and "FALSIFICATION:deterministic" in decision.reasons,
        decision.reasons,
    ))

    # 3. Shared verifier mechanism must fail the independence gate.
    decision = _gate(shared_verifiers=True).evaluate(
        candidate, [], _metrics(), evidence, {"x": 21}, 42, lambda p: p["x"] * 2,
        _fresh(candidate), 120, "dep:v1", "env:v1",
        impact_nodes, budget, forbidden, mutation_limit,
    )
    results.append(SelfTestResult(
        "shared-verifier-kill", not decision.accepted
        and "INDEPENDENT:DIVERSITY:FAIL" in decision.reasons,
        decision.reasons,
    ))

    # 4. Stale proof must fail.
    decision = _gate().evaluate(
        candidate, [], _metrics(), evidence, {"x": 21}, 201, lambda p: p["x"] * 2,
        _fresh(candidate), 201, "dep:v1", "env:v1",
        impact_nodes, budget, forbidden, mutation_limit,
    )
    results.append(SelfTestResult(
        "stale-proof-kill", not decision.accepted and "PROOF:EXPIRED" in decision.reasons,
        decision.reasons,
    ))

    # 5. Dependency mutation must invalidate proof.
    decision = _gate().evaluate(
        candidate, [], _metrics(), evidence, {"x": 21}, 42, lambda p: p["x"] * 2,
        _fresh(candidate), 120, "dep:v2", "env:v1",
        impact_nodes, budget, forbidden, mutation_limit,
    )
    results.append(SelfTestResult(
        "dependency-change-kill", not decision.accepted and "PROOF:INVALIDATED" in decision.reasons,
        decision.reasons,
    ))

    # 6. Impact budget must block unsafe mutation.
    decision = _gate().evaluate(
        candidate, [], _metrics(), evidence, {"x": 21}, 42, lambda p: p["x"] * 2,
        _fresh(candidate), 120, "dep:v1", "env:v1",
        [ImpactNode("ledger", 1.0, True), ImpactNode("constitution", 1.0, True)],
        1.0, frozenset({"constitution"}), 1,
    )
    results.append(SelfTestResult(
        "impact-budget-kill", not decision.accepted and any(r.startswith("IMPACT:") for r in decision.reasons),
        decision.reasons,
    ))

    return tuple(results)


def assert_self_test() -> None:
    results = run_self_test()
    failed = tuple(r for r in results if not r.passed)
    if failed:
        raise AssertionError(f"INNOVATION_CONTROL_SELF_TEST_FAILED:{failed}")


if __name__ == "__main__":
    assert_self_test()
    print("INNOVATION_CONTROL_SELF_TEST:PASS")
