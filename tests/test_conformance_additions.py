import unittest

from governance.capability_registry import Capability, CapabilityRegistry
from governance.governance_engine import GovernanceEngine, Policy
from governance.cvl_verifier import CVLVerifier
from governance.v_diff import compare
from evidence.evidence_collector import EvidenceCollector
from proof.proof_layer import ProofLayer
from operations.boot_controller import BootController
from operations.health_monitor import HealthMonitor
from operations.recovery_engine import RecoveryEngine
from distributed.coordination_contract import IdempotencyStore, quorum_size


class ConformanceAdditionTests(unittest.TestCase):
    def test_governance_capability_evidence_proof_chain(self):
        registry = CapabilityRegistry()
        registry.register(Capability("integration.smoke"))
        decision = GovernanceEngine().evaluate(
            actor_id="actor-1",
            permissions={"execute"},
            capability="integration.smoke",
            policy=Policy(
                "p1",
                allowed_capabilities=frozenset({"integration.smoke"}),
                required_permissions=frozenset({"execute"}),
            ),
        )
        evidence = EvidenceCollector().collect(
            execution_id="exec-1",
            inputs={"x": 1},
            output={"y": 2},
            capability="integration.smoke",
            contract={"name": "smoke"},
            policy={"id": "p1"},
            runtime_identity="VX",
            verification_status="VERIFIED",
        )
        proof = ProofLayer().issue(
            proof_id="proof-1",
            evidence=evidence,
            statement="smoke execution is evidenced",
            verified=True,
        )
        result = CVLVerifier().verify(
            decision=decision,
            capability_registry=registry,
            capability="integration.smoke",
            evidence=evidence,
            proof=proof,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(result.status, "VERIFIED")

    def test_vdiff_detects_changed_value(self):
        diff = compare({"a": 1, "b": 2}, {"a": 1, "b": 3})
        self.assertFalse(diff.equal)
        self.assertEqual(diff.changed, ("b",))

    def test_boot_and_recovery_contracts(self):
        self.assertTrue(HealthMonitor().evaluate({"ledger": True, "runtime": True}).ready)
        boot = BootController().boot({"ledger": True, "runtime": True})
        self.assertEqual(boot.status, "READY")

        snapshot = RecoveryEngine().checkpoint(
            snapshot_id="s1",
            state={"mode": "ACTIVE", "v": 7},
            ledger_root="abc",
            lineage=["e1"],
        )
        self.assertEqual(RecoveryEngine().restore(snapshot)["v"], 7)

    def test_idempotency_and_quorum(self):
        store = IdempotencyStore()
        self.assertTrue(store.accept("m1"))
        self.assertFalse(store.accept("m1"))
        self.assertEqual(quorum_size(5), 3)


if __name__ == "__main__":
    unittest.main()
