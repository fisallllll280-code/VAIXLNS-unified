import unittest

from innovation_control.assurance import Freshness, ProofFreshness, VerificationDiversity, VerifierProfile


class InnovationAssuranceTests(unittest.TestCase):
    def profiles(self, shared=False):
        if shared:
            return [
                VerifierProfile("v1", "impl-a", "model-x", ("e1",), "rule"),
                VerifierProfile("v2", "impl-a", "model-x", ("e1",), "rule"),
                VerifierProfile("v3", "impl-a", "model-x", ("e1",), "rule"),
            ]
        return [
            VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
            VerifierProfile("v2", "impl-b", "replay", ("e2",), "hash"),
            VerifierProfile("v3", "impl-c", "statistical", ("e3",), "model"),
        ]

    def test_shared_verifiers_fail_diversity(self):
        result = VerificationDiversity().assess(self.profiles(shared=True), threshold=0.5)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)

    def test_structurally_different_verifiers_pass_diversity(self):
        result = VerificationDiversity().assess(self.profiles(shared=False), threshold=0.5)
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.score, 0.5)

    def test_proof_expires(self):
        validity = ProofFreshness.issue(
            evidence_fingerprint="ev1",
            issued_epoch=10,
            ttl_epochs=5,
            dependency_fingerprint="dep1",
            environment_fingerprint="env1",
        )
        checker = ProofFreshness()
        self.assertEqual(checker.evaluate(validity, now_epoch=12, dependency_fingerprint="dep1", environment_fingerprint="env1"), Freshness.FRESH)
        self.assertEqual(checker.evaluate(validity, now_epoch=15, dependency_fingerprint="dep1", environment_fingerprint="env1"), Freshness.EXPIRED)

    def test_dependency_or_environment_change_invalidates_proof(self):
        validity = ProofFreshness.issue(
            evidence_fingerprint="ev1",
            issued_epoch=10,
            ttl_epochs=50,
            dependency_fingerprint="dep1",
            environment_fingerprint="env1",
        )
        checker = ProofFreshness()
        self.assertEqual(checker.evaluate(validity, now_epoch=20, dependency_fingerprint="dep2", environment_fingerprint="env1"), Freshness.INVALIDATED)
        self.assertEqual(checker.evaluate(validity, now_epoch=20, dependency_fingerprint="dep1", environment_fingerprint="env2"), Freshness.INVALIDATED)


if __name__ == "__main__":
    unittest.main()
