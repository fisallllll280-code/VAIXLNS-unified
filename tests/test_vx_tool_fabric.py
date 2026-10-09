"""Conformance tests for generic server/tool -> VX orchestration."""
from __future__ import annotations

import unittest

from tools.execution_fabric import (
    ExecutionGateway, Principal, ToolRegistry, ToolSpec,
)
from vx.runtime_supervisor import Phase, VXSupervisor
from vx.tool_fabric import ServerContract, VXToolFabric, tool_contract_digest


class VXToolFabricTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.registry = ToolRegistry()
        spec = ToolSpec(
            "server.read", "Read-only server operation",
            required_inputs=frozenset({"query"}),
            optional_inputs=frozenset({"limit"}),
            required_scopes=frozenset({"read:server"}),
            external_integration_id="server-alpha",
            risk="LOW",
        )
        self.spec = spec
        self.registry.register(spec, lambda args: self.calls.append(dict(args)) or {"items": [args["query"]]})
        self.gateway = ExecutionGateway(self.registry, admitted_integrations=("server-alpha",))
        self.supervisor = VXSupervisor(
            authorizer=lambda op: op.snapshot.get("tool_id") == "server.read",
            executor=lambda op: op.snapshot["dispatch"]() if callable(op.snapshot.get("dispatch")) else {"ok": True},
            verifier=lambda op, result: result.get("ok") is True,
        )
        # Supervisor snapshots are kept data-only by the fabric, so inject the
        # gateway dispatch via a subclass-like executor replacement below.
        original_prepare = self.supervisor.prepare
        def prepare_with_dispatch(operation_id, objective, snapshot):
            safe = dict(snapshot)
            safe["dispatch"] = self._dispatch_placeholder
            return original_prepare(operation_id, objective, safe)
        self.supervisor.prepare = prepare_with_dispatch
        self.contract = ServerContract(
            server_id="server-alpha",
            integration_id="server-alpha",
            protocol="json-rpc",
            protocol_version="1.0",
            contract_version="read.v1",
            tool_ids=("server.read",),
            tool_contract_digests={"server.read": tool_contract_digest(spec)},
            max_latency_ms=100,
        )
        self.fabric = VXToolFabric(
            self.gateway, self.supervisor,
            health_probe=lambda contract: {
                "healthy": True, "protocol": contract.protocol,
                "protocol_version": contract.protocol_version,
                "contract_version": contract.contract_version, "latency_ms": 3,
            },
            integration_admission=lambda integration_id: integration_id == "server-alpha",
        )
        self.fabric.register_server(self.contract)
        self._last_dispatch = None
        # Use the real gateway call, while the VX event records only a safe summary.
        self.supervisor.executor = lambda op: self._execute_from_box(op)

    def _dispatch_placeholder(self):
        return {"ok": True}

    def _execute_from_box(self, op):
        return self._last_dispatch(op)

    def test_registered_compatible_tool_executes_through_vx_and_gateway(self):
        # Re-bind to the actual invocation dispatch via supervisor wrapper.
        original_execute = self.supervisor.execute
        def execute_with_current_dispatch(op):
            original_executor = self.supervisor.executor
            self.supervisor.executor = lambda active: self._pending_dispatch(active)
            try:
                return original_execute(op)
            finally:
                self.supervisor.executor = original_executor
        self.supervisor.execute = execute_with_current_dispatch
        result = self.fabric.invoke(
            "server-alpha", Principal("reader", frozenset({"read:server"})),
            "server.read", {"query": "status"}, request_id="req-1", objective="Read server status",
        )
        self.assertEqual(result.status, "VX_TOOL_COMPLETED")
        self.assertEqual(result.vx_phase, Phase.VERIFIED.value)
        self.assertEqual(result.output, {"items": ["status"]})
        self.assertEqual(self.calls, [{"query": "status"}])
        self.assertTrue(self.gateway.ledger.verify())
        self.assertEqual([event["phase"] for event in result.replay], [
            "prepared", "simulated", "tested", "authorized", "executing", "verified",
        ])

    def _pending_dispatch(self, op):
        raise AssertionError("pending dispatch was not bound")

    def test_incompatible_protocol_blocks_before_tool_handler(self):
        broken = VXToolFabric(
            self.gateway, self.supervisor,
            health_probe=lambda contract: {
                "healthy": True, "protocol": "wrong",
                "protocol_version": contract.protocol_version,
                "contract_version": contract.contract_version, "latency_ms": 3,
            },
            integration_admission=lambda _: True,
        )
        broken.register_server(self.contract)
        result = broken.invoke(
            "server-alpha", Principal("reader", frozenset({"read:server"})),
            "server.read", {"query": "status"}, request_id="req-2", objective="Test protocol mismatch",
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("PROTOCOL_MISMATCH", result.reasons)
        self.assertEqual(self.calls, [])

    def test_missing_scope_blocks_before_handler(self):
        result = self.fabric.invoke(
            "server-alpha", Principal("no-scope", frozenset()),
            "server.read", {"query": "status"}, request_id="req-3", objective="Test authorization",
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(any(item.startswith("REQUIRED_SCOPE_MISSING") for item in result.reasons))
        self.assertEqual(self.calls, [])

    def test_unadmitted_integration_blocks_before_handler(self):
        blocked = VXToolFabric(
            self.gateway, self.supervisor,
            health_probe=lambda contract: {
                "healthy": True, "protocol": contract.protocol,
                "protocol_version": contract.protocol_version,
                "contract_version": contract.contract_version, "latency_ms": 3,
            },
            integration_admission=lambda _: False,
        )
        blocked.register_server(self.contract)
        result = blocked.invoke(
            "server-alpha", Principal("reader", frozenset({"read:server"})),
            "server.read", {"query": "status"}, request_id="req-4", objective="Test integration allowlist",
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("INTEGRATION_NOT_ADMITTED", result.reasons)
        self.assertEqual(self.calls, [])

    def test_contract_drift_is_rejected_at_registration(self):
        bad = ServerContract(
            "bad-server", "server-alpha", "json-rpc", "1.0", "read.v1",
            ("server.read",), {"server.read": "0" * 64},
        )
        with self.assertRaisesRegex(ValueError, "TOOL_CONTRACT_DIGEST_MISMATCH"):
            self.fabric.register_server(bad)

    def test_duplicate_server_and_duplicate_request_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SERVER_ID"):
            self.fabric.register_server(self.contract)
        original_execute = self.supervisor.execute
        def execute_with_current_dispatch(op):
            original_executor = self.supervisor.executor
            self.supervisor.executor = lambda active: self._actual_dispatch(active)
            try:
                return original_execute(op)
            finally:
                self.supervisor.executor = original_executor
        self.supervisor.execute = execute_with_current_dispatch
        first = self.fabric.invoke(
            "server-alpha", Principal("reader", frozenset({"read:server"})),
            "server.read", {"query": "once"}, request_id="req-dup", objective="Check at-most-once",
        )
        second = self.fabric.invoke(
            "server-alpha", Principal("reader", frozenset({"read:server"})),
            "server.read", {"query": "once"}, request_id="req-dup", objective="Check at-most-once",
        )
        self.assertEqual(first.status, "VX_TOOL_COMPLETED")
        self.assertIn("DUPLICATE_REQUEST_REPLAY_BLOCKED", second.reasons)
        self.assertEqual(self.calls, [{"query": "once"}])

    def _actual_dispatch(self, op):
        args = self._current_args
        result = self.gateway.call(
            self._current_principal, "server.read", args,
            request_id="vx:" + self._current_request_id,
        )
        return {
            "ok": result.status == "SUCCESS",
            "tool_status": result.status,
            "reason_code": result.reason_code,
            "tool_event_hash": result.event_hash,
            "output_sha256": "f" * 64,
        }


if __name__ == "__main__":
    unittest.main()
