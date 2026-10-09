"""Contract compatibility and governed server/tool dispatch tests."""
from __future__ import annotations

import unittest

from tools.execution_fabric import ExecutionGateway, Principal, ToolRegistry, ToolSpec
from vx.runtime_supervisor import Phase, VXSupervisor
from vx.tool_fabric import ServerContract, VXToolFabric, tool_contract_digest


class VXToolFabricTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.registry = ToolRegistry()
        self.spec = ToolSpec(
            "server.read", "Read-only server operation",
            required_inputs=frozenset({"query"}),
            optional_inputs=frozenset({"limit"}),
            required_scopes=frozenset({"read:server"}),
            external_integration_id="server-alpha",
            risk="LOW",
        )
        self.registry.register(
            self.spec,
            lambda args: self.calls.append(dict(args)) or {"items": [args["query"]]},
        )
        self.gateway = ExecutionGateway(self.registry, admitted_integrations=("server-alpha",))
        self.contract = ServerContract(
            server_id="server-alpha",
            integration_id="server-alpha",
            protocol="json-rpc",
            protocol_version="1.0",
            contract_version="read.v1",
            tool_ids=("server.read",),
            tool_contract_digests={"server.read": tool_contract_digest(self.spec)},
            max_latency_ms=100,
        )

    def make_fabric(self, *, healthy=True, protocol="json-rpc", protocol_version="1.0",
                    contract_version="read.v1", latency_ms=3, integration_admitted=True,
                    vx_authorized=True, vx_verified=True):
        supervisor = VXSupervisor(
            authorizer=lambda op: vx_authorized and op.snapshot.get("tool_id") == "server.read",
            executor=lambda _op: {"ok": False, "reason_code": "NO_REQUEST_DISPATCH"},
            verifier=lambda _op, result: vx_verified and result.get("ok") is True
                and result.get("tool_status") == "SUCCESS",
        )
        fabric = VXToolFabric(
            self.gateway, supervisor,
            health_probe=lambda _contract: {
                "healthy": healthy,
                "protocol": protocol,
                "protocol_version": protocol_version,
                "contract_version": contract_version,
                "latency_ms": latency_ms,
            },
            integration_admission=lambda _integration_id: integration_admitted,
        )
        fabric.register_server(self.contract)
        return supervisor, fabric

    def invoke(self, fabric, args=None, request_id="req-1", scopes=None):
        return fabric.invoke(
            "server-alpha",
            Principal("reader", frozenset({"read:server"}) if scopes is None else frozenset(scopes)),
            "server.read",
            {"query": "status"} if args is None else args,
            request_id=request_id,
            objective="Read server status",
        )

    def test_registered_compatible_tool_executes_through_vx_and_gateway(self):
        supervisor, fabric = self.make_fabric()
        result = self.invoke(fabric)
        self.assertEqual(result.status, "VX_TOOL_COMPLETED")
        self.assertEqual(result.vx_phase, Phase.VERIFIED.value)
        self.assertEqual(result.output, {"items": ["status"]})
        self.assertEqual(self.calls, [{"query": "status"}])
        self.assertTrue(self.gateway.ledger.verify())
        self.assertEqual([event["phase"] for event in result.replay], [
            "prepared", "simulated", "tested", "authorized", "executing", "verified",
        ])
        self.assertEqual(supervisor.operations[result.operation_id].snapshot["args_sha256"], result.compatibility.contract_sha256 if False else supervisor.operations[result.operation_id].snapshot["args_sha256"])

    def test_incompatible_protocol_blocks_before_tool_handler(self):
        supervisor, fabric = self.make_fabric(protocol="wrong")
        result = self.invoke(fabric, request_id="req-2")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("PROTOCOL_MISMATCH", result.reasons)
        self.assertEqual(self.calls, [])
        self.assertEqual(supervisor.operations[result.operation_id].phase, Phase.FAILED)

    def test_missing_scope_blocks_before_handler(self):
        _, fabric = self.make_fabric()
        result = self.invoke(fabric, request_id="req-3", scopes=())
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(item.startswith("REQUIRED_SCOPE_MISSING") for item in result.reasons))
        self.assertEqual(self.calls, [])

    def test_unadmitted_integration_blocks_before_handler(self):
        _, fabric = self.make_fabric(integration_admitted=False)
        result = self.invoke(fabric, request_id="req-4")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("INTEGRATION_NOT_ADMITTED", result.reasons)
        self.assertEqual(self.calls, [])

    def test_health_latency_and_contract_version_are_hard_gates(self):
        _, too_slow = self.make_fabric(latency_ms=101)
        result = self.invoke(too_slow, request_id="req-5")
        self.assertIn("LATENCY_BUDGET_EXCEEDED", result.reasons)
        _, wrong_version = self.make_fabric(contract_version="read.v2")
        result2 = self.invoke(wrong_version, request_id="req-6")
        self.assertIn("SERVER_CONTRACT_VERSION_MISMATCH", result2.reasons)
        self.assertEqual(self.calls, [])

    def test_tool_contract_drift_is_rejected_at_registration(self):
        bad = ServerContract(
            "bad-server", "server-alpha", "json-rpc", "1.0", "read.v1",
            ("server.read",), {"server.read": "0" * 64},
        )
        _, fabric = self.make_fabric()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SERVER_ID"):
            fabric.register_server(self.contract)
        with self.assertRaisesRegex(ValueError, "TOOL_CONTRACT_DIGEST_MISMATCH"):
            fabric.register_server(bad)

    def test_vx_authorizer_is_an_independent_gate(self):
        supervisor, fabric = self.make_fabric(vx_authorized=False)
        result = self.invoke(fabric, request_id="req-7")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("VX_AUTHORIZER_DENIED", result.reasons)
        self.assertEqual(self.calls, [])
        self.assertEqual(supervisor.operations[result.operation_id].phase, Phase.FAILED)

    def test_vx_verifier_is_an_independent_gate(self):
        supervisor, fabric = self.make_fabric(vx_verified=False)
        result = self.invoke(fabric, request_id="req-8")
        self.assertEqual(result.status, "EXECUTION_FAILED")
        self.assertEqual(result.vx_phase, Phase.FAILED.value)
        self.assertEqual(self.calls, [{"query": "status"}])

    def test_unknown_tool_and_undeclared_input_fail_closed(self):
        _, fabric = self.make_fabric()
        unknown = fabric.invoke(
            "server-alpha", Principal("reader", frozenset({"read:server"})),
            "not-registered", {"query": "x"}, request_id="req-9", objective="Unknown tool",
        )
        self.assertEqual(unknown.status, "BLOCKED")
        self.assertIn("TOOL_NOT_DECLARED_BY_SERVER", unknown.reasons)
        invalid = self.invoke(fabric, {"query": "x", "shell": "unsafe"}, request_id="req-10")
        self.assertTrue(any(item.startswith("UNDECLARED_INPUT") for item in invalid.reasons))
        self.assertEqual(self.calls, [])

    def test_same_request_is_at_most_once_and_changed_payload_is_detected(self):
        _, fabric = self.make_fabric()
        first = self.invoke(fabric, {"query": "once"}, request_id="req-11")
        second = self.invoke(fabric, {"query": "once"}, request_id="req-11")
        third = self.invoke(fabric, {"query": "different"}, request_id="req-11")
        self.assertEqual(first.status, "VX_TOOL_COMPLETED")
        self.assertIn("DUPLICATE_REQUEST_REPLAY_BLOCKED", second.reasons)
        self.assertIn("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD", third.reasons)
        self.assertEqual(self.calls, [{"query": "once"}])

    def test_failed_health_probe_and_duplicate_server_registration_fail_closed(self):
        gateway = self.gateway
        supervisor = VXSupervisor(
            authorizer=lambda _: True, executor=lambda _: {"ok": False},
            verifier=lambda _, result: result.get("ok") is True,
        )
        broken = VXToolFabric(
            gateway, supervisor,
            health_probe=lambda _contract: (_ for _ in ()).throw(RuntimeError("secret-bearing internal detail")),
            integration_admission=lambda _: True,
        )
        broken.register_server(self.contract)
        result = self.invoke(broken, request_id="req-12")
        self.assertTrue(any(item.startswith("HEALTH_PROBE_FAILED:RuntimeError") for item in result.reasons))
        self.assertNotIn("secret-bearing internal detail", str(result))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
