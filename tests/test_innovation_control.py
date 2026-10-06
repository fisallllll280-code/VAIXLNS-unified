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
)


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
        trio = IndependentVerificationTrio([
            lambda c, e: verifier_ok,
            lambda c, e: verifier_ok,
            lambda c, e: verifier_ok,
        ])
        return ProofBeforePromotion(
            NoveltyShield(),
            CounterfactualArena(),
            FalsificationGate(attacks),
            trio,
            ReplayVerifier(),
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
        d = gate.evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2)
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
        d = self.make_gate(attack_ok=False).evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2)
        self.assertFalse(d.accepted)
        self.assertEqual(d.stage, Stage.REJECTED)
        self.assertIn("FALSIFICATION:deterministic", d.reasons)

    def test_independent_verifier_failure_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        d = self.make_gate(verifier_ok=False).evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 2)
        self.assertFalse(d.accepted)
        self.assertEqual(d.stage, Stage.REJECTED)
        self.assertIn("INDEPENDENT:verifier-1:FAIL", d.reasons)

    def test_replay_failure_blocks_promotion(self):
        c = self.make_candidate()
        e = self.make_evidence(c)
        d = self.make_gate().evaluate(c, [], self.good_metrics(), e, {"x": 21}, 42, lambda p: p["x"] * 3)
        self.assertFalse(d.accepted)
        self.assertIn("REPLAY:FAIL", d.reasons)

    def test_exact_duplicate_is_redundant(self):
        c = self.make_candidate()
        self.assertEqual(NoveltyShield().classify(c, [c]), "REDUNDANT")


if __name__ == "__main__":
    unittest.main()
