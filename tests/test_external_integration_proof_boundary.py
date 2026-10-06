import unittest

from integration_control.assurance import ProofFreshness, VerifierProfile
from integration_control.gateway import ExternalIntegration, IntegrationClass, IntegrationPolicy, IntegrationState
from integration_control.proof_boundary import ExternalIntegrationProofBoundary
from innovation_control.engine import Evidence
from innovation_control.impact import ImpactNode


class ExternalIntegrationProofBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.integration = ExternalIntegration(
            "model:test",
            "External Model",
            IntegrationClass.MODEL,
            "provider://model",
            ("inference", "structured_output"),
            "v1",
            "dep:v1",
            "env:v1",
            owner="vaixlns",
        )
        self.policy = IntegrationPolicy(
            allowed_kinds=frozenset({IntegrationClass.MODEL}),
            allowed_capabilities=frozenset({"inference", "structured_output"}),
        )
        self.evidence = Evidence(
            candidate_id="integration:model:test",
            execution_digest="exec:model:test",
            test_ids=("functional", "failure-recovery", "replay"),
            environment={"mode": "sandbox"},
            observations={"passed": True},
        )
        self.metrics = {
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
        self.validity = ProofFreshness.issue(
            evidence_fingerprint=self.evidence.fingerprint,
            issued_epoch=100,
            ttl_epochs=100,
            dependency_fingerprint="dep:v1",
            environment_fingerprint="env:v1",
        )
        self.profiles = [
            VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
            VerifierProfile("v2", "impl-b", "replay", ("e2",), "hash"),
            VerifierProfile("v3", "impl-c", "statistical", ("e3",), "model"),
        ]

    def proof_inputs(self):
        attacks = {
            key: (lambda c, e: True)
            for key in ("contract", "functional", "failure_recovery", "security_boundary", "replay")
        }
        verifiers = [lambda c, e: True, lambda c, e: True, lambda c, e: True]
        return attacks, verifiers

    def test_proven_external_model_requires_explicit_authority(self):
        attacks, verifiers = self.proof_inputs()
        result = ExternalIntegrationProofBoundary().admit(
            self.integration, self.policy,
            metrics=self.metrics, evidence=self.evidence,
            inputs={"x": 3}, first_output=6, replay_fn=lambda p: p["x"] * 2,
            attacks=attacks, verifiers=verifiers, verifier_profiles=self.profiles,
            proof_validity=self.validity, now_epoch=120,
            impact_nodes=[ImpactNode("sandbox", 0.2, False)], impact_budget=0.5,
        )
        self.assertEqual(result.promotion.stage.value, "ADMISSIBLE")
        self.assertEqual(result.decision.state, IntegrationState.VERIFIED)
        self.assertIsNone(result.proof)

    def test_admitted_integration_is_runtime_allowed_while_fresh(self):
        attacks, verifiers = self.proof_inputs()
        result = ExternalIntegrationProofBoundary().admit(
            self.integration, self.policy,
            metrics=self.metrics, evidence=self.evidence,
            inputs={"x": 3}, first_output=6, replay_fn=lambda p: p["x"] * 2,
            attacks=attacks, verifiers=verifiers, verifier_profiles=self.profiles,
            proof_validity=self.validity, now_epoch=120,
            impact_nodes=[ImpactNode("sandbox", 0.2, False)], impact_budget=0.5,
            explicit_authority=True,
        )
        self.assertEqual(result.decision.state, IntegrationState.ADMITTED)
        self.assertIsNotNone(result.proof)
        self.assertTrue(ExternalIntegrationProofBoundary.runtime_allowed(
            self.integration, result, "inference",
            now_epoch=120, current_dependency_fingerprint="dep:v1",
            current_environment_fingerprint="env:v1",
        ))

    def test_dependency_drift_revokes_runtime_use(self):
        attacks, verifiers = self.proof_inputs()
        result = ExternalIntegrationProofBoundary().admit(
            self.integration, self.policy,
            metrics=self.metrics, evidence=self.evidence,
            inputs={"x": 3}, first_output=6, replay_fn=lambda p: p["x"] * 2,
            attacks=attacks, verifiers=verifiers, verifier_profiles=self.profiles,
            proof_validity=self.validity, now_epoch=120,
            impact_nodes=[ImpactNode("sandbox", 0.2, False)], impact_budget=0.5,
            explicit_authority=True,
        )
        self.assertFalse(ExternalIntegrationProofBoundary.runtime_allowed(
            self.integration, result, "inference",
            now_epoch=120, current_dependency_fingerprint="dep:v2",
            current_environment_fingerprint="env:v1",
        ))

    def test_endpoint_or_capability_change_invalidates_identity(self):
        attacks, verifiers = self.proof_inputs()
        result = ExternalIntegrationProofBoundary().admit(
            self.integration, self.policy,
            metrics=self.metrics, evidence=self.evidence,
            inputs={"x": 3}, first_output=6, replay_fn=lambda p: p["x"] * 2,
            attacks=attacks, verifiers=verifiers, verifier_profiles=self.profiles,
            proof_validity=self.validity, now_epoch=120,
            impact_nodes=[ImpactNode("sandbox", 0.2, False)], impact_budget=0.5,
            explicit_authority=True,
        )
        changed = ExternalIntegration(
            **{**self.integration.__dict__, "endpoint": "provider://changed"}
        )
        self.assertFalse(ExternalIntegrationProofBoundary.runtime_allowed(
            changed, result, "inference",
            now_epoch=120, current_dependency_fingerprint="dep:v1",
            current_environment_fingerprint="env:v1",
        ))


if __name__ == "__main__":
    unittest.main()
