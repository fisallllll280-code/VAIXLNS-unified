import unittest

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
    VerifierProfile,
)
from innovation_control.assurance import ProofFreshness
from innovation_control.impact import ImpactNode


class InnovationControlTests(unittest.TestCase):
    def make_candidate(self):
        return InnovationCandidate(
            candidate_id="inv-001",
            mission="prove deterministic architecture candidate",
            architecture={"runtime": "vx", "verification": "trio", "replay": True},
            proof_obligations=("deterministic", "replayable"),
            lineage=("nexent:gap-1",),
        )

    def make_evidence(self, candidate):
        return Evidence(
            candidate_id=candidate.candidate_id,
            execution_digest="exec-001",
            test_ids=("test-success", "test-replay"),
            environment={"python": "3.x", "mode": "sandbox"},
            observations={"correct": True},
        )

    def make_gate(self, attack_ok=True, verifier_ok=True):
        attacks = {
            "deterministic": lambda c, e: attack_ok,
            "replayable": lambda c, e: attack_ok,
        }
        trio = IndependentVerificationTrio(
            [
                lambda c, e: verifier_ok,
                lambda c, e: verifier_ok,
                lambda c, e: verifier_ok,
            ],
            [
                VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
                VerifierProfile("v2", "impl-b", "replay", ("e2",), "hash"),
                VerifierProfile("v3", "impl-c", "statistical", ("e3",), "model"),
            ],
        )
        return ProofBeforePromotion(
            NoveltyShield(),
            CounterfactualArena(),
            FalsificationGate(attacks),
            trio,
            ReplayVerifier(),
        )

    def fresh_context(self, candidate):
        evidence = self.make_evidence(candidate)
        validity = ProofFreshness.issue(
            evidence_fingerprint=evidence.fingerprint,
            issued_epoch=100,
            ttl_epochs=100,
            dependency_fingerprint="dep:v1",
            environment_fingerprint="env:v1",
        )
        return validity

    def impact_context(self):
        return (
            [ImpactNode("candidate-sandbox", 0.2, False)],
            0.5,
            frozenset({"constitution"}),
            1,
        )

    def good_metrics(self):
        return {
            "correctness": 0.99,
            "reliability": 0.98,
            "proof_coverage": 0.99,
            "reproducibility": 1.0,
            "evidence_strength": 1.0,
            "novelty_value": 0.95,
            "operational_value": 0.95,
            "blast_risk": 0.01,
            "rollback_cost": 0.01,
            "unresolved_unknowns": 0.0,
        }

    def test_success_reaches_admissible_but_not_automatic_canonical(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        gate = self.make_gate()
        d = gate.evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2, self.fresh_context(c), 120, "dep:v1", "env:v1", *self.impact_context())
        self.assertTrue(d.accepted)
        self.assertEqual(d.stage, Stage.ADMISSIBLE)
        self.assertTrue(d.proof_package)
        with self.assertRaises(ValueError):
            ProofBeforePromotion.canonicalize(d, explicit_authority=False)
        canonical = ProofBeforePromotion.canonicalize(d, explicit_authority=True)
        self.assertEqual(canonical.stage, Stage.CANONICAL)

    def test_falsification_kills_candidate(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        d = self.make_gate(attack_ok=False).evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2, self.fresh_context(c), 120, "dep:v1", "env:v1", *self.impact_context())
        self.assertFalse(d.accepted)
        self.assertEqual(d.stage, Stage.REJECTED)
        self.assertIn("FALSIFICATION:deterministic", d.reasons)

    def test_independent_verifier_failure_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        d = self.make_gate(verifier_ok=False).evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2, self.fresh_context(c), 120, "dep:v1", "env:v1", *self.impact_context())
        self.assertFalse(d.accepted)
        self.assertEqual(d.stage, Stage.REJECTED)
        self.assertIn("INDEPENDENT:verifier-1:FAIL", d.reasons)

    def test_replay_failure_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        d = self.make_gate().evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 3, self.fresh_context(c), 120, "dep:v1", "env:v1", *self.impact_context())
        self.assertFalse(d.accepted)
        self.assertIn("REPLAY:FAIL", d.reasons)

    def test_exact_duplicate_is_redundant(self):
        c = self.make_candidate()
        self.assertEqual(NoveltyShield().classify(c, [c]), "REDUNDANT")

    def test_shared_verification_mechanism_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        shared = [
            VerifierProfile("v1", "impl-a", "model-x", ("e1",), "rule"),
            VerifierProfile("v2", "impl-a", "model-x", ("e1",), "rule"),
            VerifierProfile("v3", "impl-a", "model-x", ("e1",), "rule"),
        ]
        gate = ProofBeforePromotion(
            NoveltyShield(),
            CounterfactualArena(),
            FalsificationGate({
                "deterministic": lambda c, e: True,
                "replayable": lambda c, e: True,
            }),
            IndependentVerificationTrio(
                [lambda c, e: True, lambda c, e: True, lambda c, e: True],
                shared,
            ),
            ReplayVerifier(),
        )
        d = gate.evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2, self.fresh_context(c), 120, "dep:v1", "env:v1", *self.impact_context())
        self.assertFalse(d.accepted)
        self.assertIn("INDEPENDENT:DIVERSITY:FAIL", d.reasons)

    def test_stale_proof_context_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        gate = self.make_gate()
        d = gate.evaluate(
            c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2,
            self.fresh_context(c), 201, "dep:v1", "env:v1", *self.impact_context()
        )
        self.assertFalse(d.accepted)
        self.assertIn("PROOF:EXPIRED", d.reasons)

    def test_dependency_change_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        gate = self.make_gate()
        d = gate.evaluate(
            c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2,
            self.fresh_context(c), 120, "dep:v2", "env:v1", *self.impact_context()
        )
        self.assertFalse(d.accepted)
        self.assertIn("PROOF:INVALIDATED", d.reasons)

    def test_counterfactual_arena_ranks_alternatives_deterministically(self):
        c1 = self.make_candidate()
        c2 = InnovationCandidate(
            "inv-002",
            c1.mission,
            {"runtime": "vx", "verification": "trio", "replay": "strict"},
            c1.proof_obligations,
            c1.lineage,
        )
        ranked = CounterfactualArena().rank([
            (c1, {
                "correctness": 0.99, "reliability": 0.95, "proof_coverage": 0.95, "reproducibility": 1.0,
                "evidence_strength": 1.0, "novelty_value": 0.90, "operational_value": 0.90,
                "blast_risk": 0.05, "rollback_cost": 0.02, "unresolved_unknowns": 0.0,
            }),
            (c2, {
                "correctness": 0.99, "reliability": 0.99, "proof_coverage": 0.99, "reproducibility": 1.0,
                "evidence_strength": 1.0, "novelty_value": 0.95, "operational_value": 0.95,
                "blast_risk": 0.01, "rollback_cost": 0.01, "unresolved_unknowns": 0.0,
            }),
        ])
        self.assertEqual(ranked[0].candidate_id, "inv-002")


if __name__ == "__main__":
    unittest.main()
