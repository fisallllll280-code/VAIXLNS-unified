import unittest

from governance.capability_registry import Capability, CapabilityRegistry
from governance.governance_engine import GovernanceEngine
from scck import Artifact, Contract, ExternalObservation, KernelState, SCCKKernel, canonical_hash


class SCCKTests(unittest.TestCase):
    def setUp(self):
        registry = CapabilityRegistry()
        registry.register(Capability("integration.smoke"))
        self.kernel = SCCKKernel(
            registry,
            GovernanceEngine(),
            authority_resolver=lambda actor, capability, ctx: actor == "actor-1" and capability == "integration.smoke",
        )
        self.current = Artifact(
            artifact_id="artifact-1",
            content_cid=canonical_hash({"seed": 1}),
            schema_cid="schema:scck:v1",
            policy_cid="default",
            authority_cid="authority:actor-1",
            provenance_cid="local",
            parent_cid="",
            contract_cid="contract:smoke",
            state="READY",
            version=0,
            epoch=7,
            nonce="n0",
            issued_by="VAIXLNS",
            authorized_for="integration.smoke",
            payload={"seed": 1},
        )
        self.contract = Contract(
            contract_id="contract:smoke",
            version="1.0",
            capability_id="integration.smoke",
            source_state="READY",
            target_state="EXECUTED",
        )

    def _prepare(self):
        return self.kernel.prepare(
            actor_id="actor-1",
            permissions={"execute"},
            capability_id="integration.smoke",
            current=self.current,
            contract=self.contract,
        )

    def test_happy_path_requires_readback_and_creates_proof(self):
        prepared = self._prepare()
        self.assertEqual(prepared.state, KernelState.PREPARED)
        self.assertIsNotNone(prepared.intent)

        def adapter(intent):
            payload = {"result": 42}
            return ExternalObservation(
                intent_id=intent.intent_id,
                adapter_id="worker:local",
                success=True,
                payload=payload,
                content_cid=canonical_hash(payload),
                observed_state="EXECUTED",
                observed_version=intent.expected_version,
                observed_epoch=intent.expected_epoch,
            )

        outcome = self.kernel.execute(
            intent=prepared.intent,
            current=self.current,
            adapter_id="worker:local",
            adapter=adapter,
            contract=self.contract,
            policy=None,
        )
        self.assertEqual(outcome.state, KernelState.COMMITTED)
        self.assertEqual(outcome.artifact.version, 1)
        self.assertTrue(outcome.evidence.fingerprint)
        self.assertTrue(outcome.proof.proof_digest)

    def test_wrong_readback_is_quarantined(self):
        prepared = self._prepare()
        payload = {"result": 42}
        observation = ExternalObservation(
            intent_id=prepared.intent.intent_id,
            adapter_id="worker:local",
            success=True,
            payload=payload,
            content_cid=canonical_hash(payload),
            observed_state="EXECUTED",
            observed_version=99,
            observed_epoch=prepared.intent.expected_epoch,
        )
        outcome = self.kernel.finalize(
            intent=prepared.intent,
            current=self.current,
            observation=observation,
            contract=self.contract,
            policy=None,
        )
        self.assertEqual(outcome.state, KernelState.QUARANTINED)
        self.assertEqual(outcome.reason, "READBACK_VERSION_MISMATCH")

    def test_adapter_cannot_enter_key_domain(self):
        with self.assertRaises(PermissionError):
            self.kernel.key_domain.assert_adapter_outside("KSD:master")

    def test_authority_is_not_capability(self):
        denied = self.kernel.prepare(
            actor_id="actor-2",
            permissions={"execute"},
            capability_id="integration.smoke",
            current=self.current,
            contract=self.contract,
        )
        self.assertEqual(denied.state, KernelState.REJECTED)
        self.assertEqual(denied.reason, "AUTHORITY_DENIED")


if __name__ == "__main__":
    unittest.main()
