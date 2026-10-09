import base64
import json
from pathlib import Path
import tempfile
import unittest

from tools.execution_fabric import (
    AuditLedger,
    ExecutionGateway,
    Principal,
    ToolRegistry,
    ToolSpec,
    build_default_gateway,
)


READ_PRINCIPAL = Principal("AG-01-SOURCE-DISCOVERY", frozenset({"read:search", "read:public-repositories"}))


class ExecutionFabricTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "docs" / "architecture.md").write_text(
            "innovation execution contract and verification evidence\n", encoding="utf-8"
        )
        (self.root / "docs" / "registry.json").write_text(
            json.dumps({"index_id": "OMEGA", "status": "CANONICAL"}), encoding="utf-8"
        )
        (self.root / "tests" / "test_research_fabric.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self.gateway = build_default_gateway(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def call_tool(self, tool_id, args, principal=READ_PRINCIPAL, request_id="test-1"):
        return self.gateway.call(principal, tool_id, args, request_id=request_id)

    def test_repo_search_returns_source_path_and_digest(self):
        result = self.call_tool("repo.search", {"query": "innovation verification"})
        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(result.output["results"])
        self.assertIn("file_sha256", result.output["results"][0])

    def test_repo_read_is_bounded_and_hashes_full_content(self):
        result = self.call_tool("repo.read", {"path": "docs/architecture.md", "start_line": 1, "end_line": 1})
        self.assertEqual(result.status, "SUCCESS")
        self.assertIn("innovation execution", result.output["content"])
        self.assertEqual(len(result.output["sha256"]), 64)

    def test_repo_hash_returns_sha256(self):
        result = self.call_tool("repo.sha256", {"path": "docs/architecture.md"},
                                principal=Principal("proof", frozenset({"read:provenance"})))
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(result.output["sha256"]), 64)

    def test_json_inspect_parses_document_and_reports_shape(self):
        result = self.call_tool("json.inspect", {"path": "docs/registry.json"})
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.output["shape"], "object")
        self.assertIn("index_id", result.output["keys"])

    def test_path_traversal_is_blocked(self):
        result = self.call_tool("repo.read", {"path": "../outside.txt"})
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "PATH_TRAVERSAL_DENIED")

    def test_absolute_path_is_blocked(self):
        result = self.call_tool("repo.read", {"path": str(self.root / "docs" / "architecture.md")})
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "PATH_TRAVERSAL_DENIED")

    def test_sensitive_file_is_blocked(self):
        (self.root / "docs" / ".env").write_text("SECRET=do-not-read", encoding="utf-8")
        result = self.call_tool("repo.read", {"path": "docs/.env"})
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "SENSITIVE_FILE_DENIED")

    def test_wrong_scope_is_blocked_before_handler(self):
        result = self.call_tool("repo.read", {"path": "docs/architecture.md"}, principal=Principal("untrusted", frozenset()))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "SCOPE_GROUP_NOT_SATISFIED")

    def test_unknown_tool_is_blocked_and_audited(self):
        result = self.call_tool("os.shell", {"command": "echo unsafe"})
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "TOOL_UNKNOWN")
        self.assertTrue(self.gateway.ledger.verify())

    def test_extra_input_is_rejected(self):
        result = self.call_tool("repo.read", {"path": "docs/architecture.md", "write": True})
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "UNDECLARED_INPUT")

    def test_inactive_principal_is_blocked(self):
        result = self.call_tool("repo.search", {"query": "innovation"},
                                principal=Principal("disabled-agent", READ_PRINCIPAL.scopes, active=False))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "PRINCIPAL_INACTIVE")

    def test_execution_ledger_hash_chain_verifies(self):
        self.call_tool("repo.search", {"query": "innovation"}, request_id="first")
        self.call_tool("repo.read", {"path": "docs/architecture.md"}, request_id="second")
        events = self.gateway.ledger.events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].previous_hash, events[0].event_hash)
        self.assertTrue(self.gateway.ledger.verify())

    def test_duplicate_tool_registration_is_rejected(self):
        registry = ToolRegistry()
        spec = ToolSpec("echo.safe", "test")
        registry.register(spec, lambda args: {"ok": True})
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TOOL_ID"):
            registry.register(spec, lambda args: {"other": True})

    def test_test_execution_is_disabled_by_default(self):
        result = self.call_tool("tests.run_unit", {"pattern": "test_research_fabric.py"},
                                principal=Principal("test-agent", frozenset({"request:sandbox-test"})))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "TOOL_DISABLED")

    def test_test_execution_requires_both_enablement_and_scope(self):
        def fake_executor(root, args, allowlist):
            return {"pattern": args["pattern"], "passed": True, "fake": True}
        gateway = build_default_gateway(self.root, enable_test_runner=True, test_executor=fake_executor)
        no_scope = gateway.call(READ_PRINCIPAL, "tests.run_unit", {"pattern": "test_research_fabric.py"}, request_id="no-scope")
        self.assertEqual(no_scope.status, "BLOCKED")
        self.assertEqual(no_scope.reason_code, "REQUIRED_SCOPE_MISSING")
        permitted = gateway.call(
            Principal("test-agent", frozenset({"request:sandbox-test"})),
            "tests.run_unit", {"pattern": "test_research_fabric.py"}, request_id="permit",
        )
        self.assertEqual(permitted.status, "SUCCESS")
        self.assertTrue(permitted.output["passed"])

    def test_unknown_integration_does_not_run_external_handler(self):
        calls = []
        registry = ToolRegistry()
        registry.register(
            ToolSpec("remote.read", "external", frozenset({"query"}),
                     required_scopes=frozenset({"read:public-repositories"}),
                     external_integration_id="github-readonly"),
            lambda args: calls.append(args) or {"results": []},
        )
        gateway = ExecutionGateway(registry)
        result = gateway.call(READ_PRINCIPAL, "remote.read", {"query": "x"}, request_id="external")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "INTEGRATION_NOT_ADMITTED")
        self.assertEqual(calls, [])

    def test_admitted_integration_still_requires_capability_scope(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec("remote.read", "external", frozenset({"query"}),
                     required_scopes=frozenset({"read:public-repositories"}),
                     external_integration_id="github-readonly"),
            lambda args: {"read": args["query"]},
        )
        gateway = ExecutionGateway(registry, admitted_integrations=("github-readonly",))
        result = gateway.call(Principal("wrong-role", frozenset()), "remote.read", {"query": "x"}, request_id="scope")
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_code, "REQUIRED_SCOPE_MISSING")


if __name__ == "__main__":
    unittest.main()
