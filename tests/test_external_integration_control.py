import unittest

from integration_control.gateway import (
    ExternalCallBoundary,
    ExternalIntegration,
    ExternalIntegrationGate,
    IntegrationClass,
    IntegrationPolicy,
    IntegrationState,
)


class ExternalIntegrationControlTests(unittest.TestCase):
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

    def test_unverified_model_cannot_enter_runtime(self):
        d = ExternalIntegrationGate().admit(self.integration, self.policy)
        self.assertEqual(d.state, IntegrationState.DISCOVERED)
        self.assertFalse(ExternalCallBoundary().authorize(self.integration, d, "inference"))

    def test_verified_without_authority_cannot_be_admitted(self):
        d = ExternalIntegrationGate().admit(self.integration, self.policy, verified=True)
        self.assertEqual(d.state, IntegrationState.VERIFIED)
        self.assertFalse(ExternalCallBoundary().authorize(self.integration, d, "inference"))

    def test_explicitly_admitted_capability_can_cross_boundary(self):
        d = ExternalIntegrationGate().admit(self.integration, self.policy, verified=True, explicit_authority=True)
        self.assertEqual(d.state, IntegrationState.ADMITTED)
        self.assertTrue(ExternalCallBoundary().authorize(self.integration, d, "inference"))

    def test_unapproved_capability_is_quarantined(self):
        bad = ExternalIntegration(
            **{**self.integration.__dict__, "capabilities": ("inference", "filesystem_write")}
        )
        d = ExternalIntegrationGate().admit(bad, self.policy, verified=True, explicit_authority=True)
        self.assertEqual(d.state, IntegrationState.QUARANTINED)
        self.assertIn("CAPABILITY_FORBIDDEN:filesystem_write", d.reasons)

    def test_missing_environment_identity_is_quarantined(self):
        bad = ExternalIntegration(
            **{**self.integration.__dict__, "environment_fingerprint": ""}
        )
        d = ExternalIntegrationGate().admit(bad, self.policy, verified=True, explicit_authority=True)
        self.assertEqual(d.state, IntegrationState.QUARANTINED)
        self.assertIn("ENVIRONMENT_FINGERPRINT_MISSING", d.reasons)


if __name__ == "__main__":
    unittest.main()
