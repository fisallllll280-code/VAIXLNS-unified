"""Integration and adversarial tests for the ARC-X -> VX gate."""
from __future__ import annotations

import unittest

from arc_x.core import (
    AuthorityApproval, ClaimKind, ClaimRecord, EvidenceKind, EvidenceRecord,
    ProofObligation, SourceReceipt, Stance, compile_eir,
)
from arc_x.vx_bridge import ArcXVXBridge
from vx.runtime_supervisor import Phase, VXSupervisor


HASH_SRC = "a" * 64
HASH_SIM = "b" * 64
HASH_TEST = "c" * 64


def compilation():
    source = SourceReceipt(
        source_id="SRC-VX", repository="owner/repo", revision="1" * 40,
        path="src/candidate.py", content_sha256=HASH_SRC,
        retrieved_at="2026-10-09T10:00:00Z",
        source_uri="https://example.invalid/source",
    )
    claim = ClaimRecord("CLM-VX", "The declared VX candidate passes its tests", ClaimKind.IMPLEMENTATION)
    evidence = [
        EvidenceRecord(
            "EVD-SIM", "SRC-VX", EvidenceKind.SIMULATION_TRACE, "Sandbox simulation succeeded",
            "CLM-VX", Stance.SUPPORTS, "PASS", HASH_SIM,
        ),
        EvidenceRecord(
            "EVD-TEST", "SRC-VX", EvidenceKind.TEST_RESULT, "Conformance test succeeded",
            "CLM-VX", Stance.SUPPORTS, "PASS", HASH_TEST,
        ),
    ]
    obligation = ProofObligation(
        "PO-VX", "CLM-VX", "Require source-linked test evidence", evidence_ids=("EVD-TEST",)
    )
    return compile_eir([source], evidence, [claim], [obligation])


class ArcXVXBridgeTests(unittest.TestCase):
    def make_bridge(self, *, vx_authorized=True, vx_verified=True, evidence_ok=True, authority_ok=True,
                    sim_hash=HASH_SIM, test_hash=HASH_TEST):
        supervisor = VXSupervisor(
            authorizer=lambda op: vx_authorized and op.snapshot["requested_action"] == "EXECUTE",
            executor=lambda op: {
                "ok": True,
                "operation_id": op.operation_id,
                "eir_sha256": op.snapshot["eir_sha256"],
            },
            verifier=lambda op, result: vx_verified and result.get("ok") is True
                and result.get("eir_sha256") == op.snapshot["eir_sha256"],
        )
        bridge = ArcXVXBridge(
            supervisor,
            evidence_verifier=lambda result: evidence_ok and result.eir_sha256 == compilation().eir_sha256,
            authority_verifier=lambda approval, scope: authority_ok and approval.scope == scope
                and approval.actor_id == "operator-1",
            simulation_runner=lambda eir: {
                "ok": True, "evidence_id": "EVD-SIM", "artifact_sha256": sim_hash,
            },
            test_runner=lambda eir, simulation: {
                "ok": simulation.get("ok") is True, "evidence_id": "EVD-TEST",
                "artifact_sha256": test_hash,
            },
        )
        return supervisor, bridge

    def approval(self, scope="execution"):
        return AuthorityApproval("APR-VX-001", "operator-1", scope)

    def test_success_runs_simulate_test_authorize_execute_and_verify_in_vx(self):
        supervisor, bridge = self.make_bridge()
        result = bridge.execute(compilation(), self.approval(), objective="Run ARC-X admitted candidate")
        self.assertEqual(result.status, "EXECUTED_AND_VX_VERIFIED")
        self.assertEqual(result.vx_phase, Phase.VERIFIED.value)
        self.assertEqual([event["phase"] for event in result.replay], [
            "prepared", "simulated", "tested", "authorized", "executing", "verified",
        ])
        self.assertEqual(supervisor.operations[result.operation_id].snapshot["eir_sha256"], result.eir_sha256)

    def test_simulation_artifact_mismatch_stops_before_test_and_execution(self):
        supervisor, bridge = self.make_bridge(sim_hash="d" * 64)
        result = bridge.execute(compilation(), self.approval(), objective="Reject mismatched simulation evidence")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("SIMULATION_EVIDENCE_MISMATCH_OR_FAILURE", result.reason_codes)
        op = supervisor.operations[result.operation_id]
        self.assertEqual(op.phase, Phase.FAILED)
        self.assertNotIn("execute_start", [event.name for event in op.events])

    def test_test_artifact_mismatch_stops_before_authorization_and_execution(self):
        supervisor, bridge = self.make_bridge(test_hash="d" * 64)
        result = bridge.execute(compilation(), self.approval(), objective="Reject mismatched test evidence")
        self.assertIn("TEST_EVIDENCE_MISMATCH_OR_FAILURE", result.reason_codes)
        self.assertNotIn("execute_start", [event.name for event in supervisor.operations[result.operation_id].events])

    def test_failed_independent_evidence_attestation_blocks_vx_execution(self):
        supervisor, bridge = self.make_bridge(evidence_ok=False)
        result = bridge.execute(compilation(), self.approval(), objective="Reject untrusted evidence")
        self.assertIn("ARC_X_GATE:EVIDENCE_ATTESTATION_FAILED", result.reason_codes)
        self.assertNotIn("execute_start", [event.name for event in supervisor.operations[result.operation_id].events])

    def test_authority_scope_mismatch_blocks_vx(self):
        supervisor, bridge = self.make_bridge()
        result = bridge.execute(compilation(), self.approval("canonical-admission"), objective="Reject wrong approval scope")
        self.assertTrue(any(code.startswith("ARC_X_GATE:") for code in result.reason_codes))
        self.assertNotIn("execute_start", [event.name for event in supervisor.operations[result.operation_id].events])

    def test_vx_authorizer_remains_an_independent_gate(self):
        supervisor, bridge = self.make_bridge(vx_authorized=False)
        result = bridge.execute(compilation(), self.approval(), objective="Respect VX governance")
        self.assertIn("VX_AUTHORIZER_DENIED", result.reason_codes)
        self.assertEqual(result.vx_phase, Phase.FAILED.value)
        self.assertNotIn("execute_start", [event["name"] for event in result.replay])

    def test_vx_verifier_remains_an_independent_gate(self):
        supervisor, bridge = self.make_bridge(vx_verified=False)
        result = bridge.execute(compilation(), self.approval(), objective="Respect VX runtime verification")
        self.assertEqual(result.status, "EXECUTION_FAILED")
        self.assertEqual(result.vx_phase, Phase.FAILED.value)

    def test_same_approval_and_eir_cannot_execute_twice(self):
        supervisor, bridge = self.make_bridge()
        first = bridge.execute(compilation(), self.approval(), objective="Idempotent operation")
        second = bridge.execute(compilation(), self.approval(), objective="Idempotent operation")
        self.assertEqual(first.status, "EXECUTED_AND_VX_VERIFIED")
        self.assertEqual(second.status, "BLOCKED")
        self.assertIn("DUPLICATE_OPERATION_ID_REPLAY_BLOCKED", second.reason_codes)
        self.assertEqual(len(supervisor.operations), 1)

    def test_runner_exception_fails_closed(self):
        supervisor = VXSupervisor(
            authorizer=lambda _: True, executor=lambda _: {"ok": True},
            verifier=lambda _op, result: result.get("ok") is True,
        )
        bridge = ArcXVXBridge(
            supervisor, evidence_verifier=lambda _: True, authority_verifier=lambda *_: True,
            simulation_runner=lambda _: (_ for _ in ()).throw(RuntimeError("sim failure")),
            test_runner=lambda *_: {"ok": True, "evidence_id": "EVD-TEST", "artifact_sha256": HASH_TEST},
        )
        result = bridge.execute(compilation(), self.approval(), objective="Runner must fail closed")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_codes, ("SIMULATION_EXCEPTION:RuntimeError",))
        self.assertNotIn("execute_start", [event["name"] for event in result.replay])


if __name__ == "__main__":
    unittest.main()
