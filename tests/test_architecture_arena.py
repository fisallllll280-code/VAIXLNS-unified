import unittest

from evolution.architecture_arena import ArchitectureArenaRunner, ArchitectureTrial
from innovation_control.assurance import ProofFreshness, VerifierProfile
from innovation_control.engine import (
    CounterfactualArena,
    Evidence,
    FalsificationGate,
    IndependentVerificationTrio,
    NoveltyShield,
    ProofBeforePromotion,
    ReplayVerifier,
    Stage,
)
from innovation_control.impact import ImpactNode


def make_gate():
    profiles = (
        VerifierProfile("symbolic-v1", "impl-symbolic", "symbolic", ("source-rule",), "rules"),
        VerifierProfile("replay-v1", "impl-replay", "replay", ("event-log",), "hash"),
        VerifierProfile("statistical-v1", "impl-stat", "statistical", ("measurements",), "model"),
    )
    return ProofBeforePromotion(
        NoveltyShield(),
        CounterfactualArena(),
        FalsificationGate({
            "deterministic": lambda candidate, evidence: True,
            "replayable": lambda candidate, evidence: True,
            "survives_adversarial_checks": lambda candidate, evidence: True,
        }),
        IndependentVerificationTrio(
            [
                lambda candidate, evidence: True,
                lambda candidate, evidence: True,
                lambda candidate, evidence: True,
            ],
            profiles,
        ),
        ReplayVerifier(),
    )


def good_metrics():
    return {
        "correctness": 0.99,
        "reliability": 0.97,
        "proof_coverage": 0.98,
        "reproducibility": 1.0,
        "evidence_strength": 0.90,
        "novelty_value": 0.80,
        "operational_value": 0.90,
        "blast_risk": 0.10,
        "rollback_cost": 0.10,
        "unresolved_unknowns": 0.10,
    }


def make_trial(candidate, metrics=None, replay_fn=None):
    evidence = Evidence(
        candidate_id=candidate.candidate_id,
        execution_digest="sandbox-execution-" + candidate.candidate_id,
        test_ids=("smoke", "falsification", "replay"),
        environment={"runner": "isolated-test-fixture", "version": "1"},
        observations={"fixture_only": True},
        source_refs=("fixture://architecture-arena-tests",),
    )
    proof_validity = ProofFreshness.issue(
        evidence_fingerprint=evidence.fingerprint,
        issued_epoch=100,
        ttl_epochs=100,
        dependency_fingerprint="dependencies:v1",
        environment_fingerprint="sandbox:v1",
    )
    return ArchitectureTrial(
        metrics=dict(metrics or good_metrics()),
        evidence=evidence,
        inputs={"n": 21},
        first_output={"result": 42},
        replay_fn=replay_fn or (lambda payload: {"result": payload["n"] * 2}),
        proof_validity=proof_validity,
        now_epoch=120,
        dependency_fingerprint="dependencies:v1",
        environment_fingerprint="sandbox:v1",
        impact_nodes=(ImpactNode("candidate-sandbox", 0.2, False),),
        impact_budget=0.5,
        forbidden_impact_nodes=frozenset({"constitution", "canonical-registry"}),
        max_state_mutations=1,
    )


class ArchitectureArenaRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = ArchitectureArenaRunner(make_gate())

    def experiment(self):
        return self.runner.propose(
            "four-domain-room",
            ("math", "physics", "proof"),
            ("math",),
            evidence_refs=("registry-snapshot:fixture-v1",),
        )

    def test_proposal_is_deterministic_and_generates_three_isolated_candidates(self):
        first = self.experiment()
        second = self.experiment()
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(
            tuple(c.candidate_id for c in first.candidates),
            tuple(c.candidate_id for c in second.candidates),
        )
        self.assertEqual(len(first.designs), 3)
        self.assertEqual(len(first.unknowns), 2)
        self.assertTrue(all(design.isolated for design in first.designs))
        self.assertTrue(all(c.lineage[0] == "self-discovery" for c in first.candidates))
        self.assertTrue(all(c.proof_obligations for c in first.candidates))

    def test_only_admissible_candidates_can_be_selected_and_never_canonicalized(self):
        experiment = self.experiment()
        trials = {}
        for index, candidate in enumerate(experiment.candidates):
            metrics = good_metrics()
            metrics.update({
                "evidence_strength": 0.80 + index * 0.08,
                "novelty_value": 0.70 + index * 0.10,
                "operational_value": 0.80 + index * 0.08,
                "blast_risk": 0.10 - index * 0.04,
                "rollback_cost": 0.10 - index * 0.04,
                "unresolved_unknowns": 0.10 - index * 0.05,
            })
            trials[candidate.candidate_id] = make_trial(candidate, metrics)

        report = self.runner.evaluate(experiment, trials)
        self.assertIsNotNone(report.selected_candidate_id)
        outcomes = {outcome.candidate_id: outcome for outcome in report.outcomes}
        self.assertTrue(all(item.accepted for item in outcomes.values()))
        self.assertTrue(all(item.stage is Stage.ADMISSIBLE for item in outcomes.values()))
        self.assertTrue(all(item.proof_package for item in outcomes.values()))
        self.assertEqual(
            report.selected_candidate_id,
            max(report.outcomes, key=lambda item: item.score or float("-inf")).candidate_id,
        )
        self.assertNotIn(Stage.CANONICAL, {item.stage for item in report.outcomes})
        self.assertEqual(report.fingerprint, self.runner.evaluate(experiment, trials).fingerprint)

    def test_replay_failure_rejects_candidate_and_excludes_it_from_selection(self):
        experiment = self.experiment()
        trials = {
            candidate.candidate_id: make_trial(
                candidate,
                replay_fn=(
                    (lambda payload: {"result": payload["n"] * 3})
                    if index == 0
                    else None
                ),
            )
            for index, candidate in enumerate(experiment.candidates)
        }
        report = self.runner.evaluate(experiment, trials)
        rejected = report.outcomes[0]
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.stage, Stage.REJECTED)
        self.assertIn("REPLAY:FAIL", rejected.reasons)
        self.assertNotEqual(report.selected_candidate_id, rejected.candidate_id)

    def test_missing_trial_package_fails_closed(self):
        experiment = self.experiment()
        report = self.runner.evaluate(experiment, {})
        self.assertIsNone(report.selected_candidate_id)
        self.assertTrue(all(not item.accepted for item in report.outcomes))
        self.assertTrue(all("TRIAL:PACKAGE_MISSING" in item.reasons for item in report.outcomes))

    def test_non_finite_metric_fails_closed(self):
        experiment = self.experiment()
        candidate = experiment.candidates[0]
        metrics = good_metrics()
        metrics["reliability"] = float("nan")
        report = self.runner.evaluate(experiment, {candidate.candidate_id: make_trial(candidate, metrics)})
        outcome = report.outcomes[0]
        self.assertFalse(outcome.accepted)
        self.assertEqual(outcome.stage, Stage.REJECTED)
        self.assertIn("METRICS:NON_FINITE:reliability", outcome.reasons)
        self.assertIsNone(outcome.proof_package)

    def test_no_gap_returns_no_candidates_or_selection(self):
        experiment = self.runner.propose("known-mission", ("math",), ("math",))
        self.assertEqual(experiment.candidates, ())
        report = self.runner.evaluate(experiment, {})
        self.assertEqual(report.outcomes, ())
        self.assertIsNone(report.selected_candidate_id)

    def test_invalid_mission_or_blank_capability_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSION_REQUIRED"):
            self.runner.propose(" ", ("math",), ("math",))
        with self.assertRaisesRegex(ValueError, "CAPABILITY_NAME_REQUIRED"):
            self.runner.propose("m", (" ",), ())


if __name__ == "__main__":
    unittest.main()
