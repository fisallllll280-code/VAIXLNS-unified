"""End-to-end governed server adapter tests for VLNS activation -> VX."""
from __future__ import annotations

import unittest

from tools.execution_fabric import ExecutionGateway, Principal, ToolRegistry
from vlns.activation import ActivationPolicy, VLNSActivationBridge, envelope_hash
from vx.runtime_supervisor import Phase, VXSupervisor
from vx.server_adapters import (
    VLNS_ACTIVATION_INTEGRATION_ID,
    VLNS_ACTIVATION_TOOL_ID,
    register_vlns_activation_tool,
)
from vx.tool_fabric import VXToolFabric


SIGNING_KEY = b"unit-test-signing-key-with-32-bytes-minimum"
POLICY = ActivationPolicy(
    allowed_providers=frozenset({"ollama"}),
    allowed_capabilities=frozenset({"reasoning", "research"}),
    allowed_tools=frozenset({"repository.read"}),
)


def activation_args():
    return {
        "model_id": "qwen3:8b",
        "provider": "ollama",
        "model_version": "sha256:model-revision-001",
        "role": "research_mind",
        "capability_profile": ["reasoning", "research"],
        "context_payload": {
            "task": "inspect architecture",
            "input_refs": ["repo://VAIXLNS"],
        },
        "tool_profile": ["repository.read"],
        "requested_permissions": ["read", "propose"],
        "constraints": ["no_canonical_mutation", "no_unreviewed_execution"],
        "provenance": {
            "task_id": "task-001",
            "source_id": "repo://VAIXLNS",
            "source_digest": "a" * 64,
        },
    }


class FakeVLNSServer:
    configured = True

    def __init__(self, *, status="ACTIVATED"):
        self.status = status
        self.envelopes = []

    def activate_model(self, envelope):
        self.envelopes.append(dict(envelope))
        return {
            "ok": True,
            "status_code": 200,
            "data": {
                "status": self.status,
                "activation_id": envelope["activation_id"],
                "envelope_hash": envelope_hash(envelope),
            },
        }


class FakeEvidenceRecorder:
    def __init__(self, *, ok=True):
        self.ok = ok
        self.events = []

    def record(self, event):
        self.events.append(dict(event))
        return {
            "ok": self.ok,
            "status": "LOCAL_VX_EVENT_RECORDED" if self.ok else "LOCAL_VX_EVIDENCE_WRITE_FAILED",
            "data": {"recorded": self.ok},
        }


class VLNSServerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.remote = FakeVLNSServer()
        self.recorder = FakeEvidenceRecorder()
        self.bridge = VLNSActivationBridge(
            self.remote,
            POLICY,
            SIGNING_KEY,
            evidence_recorder=self.recorder.record,
        )
        self.registry = ToolRegistry()
        self.spec = register_vlns_activation_tool(self.registry, self.bridge, enabled=True)
        self.gateway = ExecutionGateway(
            self.registry,
            admitted_integrations=(VLNS_ACTIVATION_INTEGRATION_ID,),
        )
        self.supervisor = VXSupervisor(
            authorizer=lambda op: (
                op.snapshot.get("tool_id") == VLNS_ACTIVATION_TOOL_ID
                and op.snapshot.get("arcx_decision") == "ADMITTED"
            ),
            executor=lambda _op: {"ok": False, "reason_code": "DISPATCH_NOT_BOUND"},
            verifier=lambda _op, result: (
                result.get("ok") is True
                and result.get("tool_status") == "SUCCESS"
                and result.get("tool_event_hash") is not None
            ),
        )
        self.fabric = VXToolFabric(
            self.gateway,
            self.supervisor,
            health_probe=lambda contract: {
                "healthy": True,
                "protocol": contract.protocol,
                "protocol_version": contract.protocol_version,
                "contract_version": contract.contract_version,
                "latency_ms": 2,
            },
            integration_admission=lambda identity: identity == VLNS_ACTIVATION_INTEGRATION_ID,
            arc_x_gate=lambda *_: {
                "allowed": True,
                "decision": "ADMITTED",
                "eir_sha256": "d" * 64,
                "reason_codes": ["TEST_FIXTURE_ONLY"],
            },
        )
        self.fabric.register_tool(
            VLNS_ACTIVATION_TOOL_ID,
            server_id=VLNS_ACTIVATION_INTEGRATION_ID,
            protocol="https-json",
            protocol_version="1",
            contract_version="activation-envelope.v1",
        )

    def invoke(self, *, request_id="activation-001"):
        return self.fabric.invoke(
            VLNS_ACTIVATION_INTEGRATION_ID,
            Principal("operator-1", frozenset({"request:vlns-activation"})),
            VLNS_ACTIVATION_TOOL_ID,
            activation_args(),
            request_id=request_id,
            objective="Activate a policy-approved model through VLNS and record VX evidence",
        )

    def test_activation_runs_through_arcx_vx_gateway_and_records_receipt(self):
        result = self.invoke()
        self.assertEqual(result.status, "VX_TOOL_COMPLETED")
        self.assertEqual(result.vx_phase, Phase.VERIFIED.value)
        self.assertEqual(len(self.remote.envelopes), 1)
        self.assertEqual(len(self.recorder.events), 1)
        self.assertEqual(result.output["status"], "ACTIVATED_AND_RECORDED")
        self.assertTrue(result.output["activated"])
        self.assertTrue(result.output["evidence_recorded"])
        self.assertNotIn("context_payload", result.output)
        self.assertNotIn("signature", result.output)
        self.assertTrue(self.gateway.ledger.verify())
        self.assertEqual(result.eir_sha256, "d" * 64)

    def test_adapter_is_disabled_by_default(self):
        registry = ToolRegistry()
        disabled_spec = register_vlns_activation_tool(registry, self.bridge)
        self.assertFalse(disabled_spec.enabled)
        self.assertEqual(disabled_spec.risk, "CRITICAL")
        self.assertFalse(disabled_spec.read_only)
        gateway = ExecutionGateway(
            registry,
            admitted_integrations=(VLNS_ACTIVATION_INTEGRATION_ID,),
        )
        result = gateway.call(
            Principal("operator-1", frozenset({"request:vlns-activation"})),
            VLNS_ACTIVATION_TOOL_ID,
            activation_args(),
            request_id="disabled-test",
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "TOOL_DISABLED")
        self.assertEqual(self.remote.envelopes, [])

    def test_missing_vx_evidence_recording_cannot_return_success(self):
        recorder = FakeEvidenceRecorder(ok=False)
        bridge = VLNSActivationBridge(self.remote, POLICY, SIGNING_KEY, evidence_recorder=recorder.record)
        registry = ToolRegistry()
        register_vlns_activation_tool(registry, bridge, enabled=True)
        gateway = ExecutionGateway(
            registry,
            admitted_integrations=(VLNS_ACTIVATION_INTEGRATION_ID,),
        )
        result = gateway.call(
            Principal("operator-1", frozenset({"request:vlns-activation"})),
            VLNS_ACTIVATION_TOOL_ID,
            activation_args(),
            request_id="no-evidence-test",
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("VLNS_ACTIVATION_NOT_FULLY_RECORDED", result.reason_code)
        self.assertEqual(len(self.remote.envelopes), 2)

    def test_remote_rejection_cannot_be_promoted_to_success(self):
        remote = FakeVLNSServer(status="QUARANTINED")
        bridge = VLNSActivationBridge(remote, POLICY, SIGNING_KEY, evidence_recorder=self.recorder.record)
        registry = ToolRegistry()
        register_vlns_activation_tool(registry, bridge, enabled=True)
        gateway = ExecutionGateway(
            registry,
            admitted_integrations=(VLNS_ACTIVATION_INTEGRATION_ID,),
        )
        result = gateway.call(
            Principal("operator-1", frozenset({"request:vlns-activation"})),
            VLNS_ACTIVATION_TOOL_ID,
            activation_args(),
            request_id="remote-reject-test",
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("VLNS_ACTIVATION_NOT_FULLY_RECORDED", result.reason_code)
        self.assertEqual(self.recorder.events, [])


if __name__ == "__main__":
    unittest.main()
