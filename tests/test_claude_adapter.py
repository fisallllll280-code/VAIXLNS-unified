import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from infra.vx_ai_request_audit import VXAIRequestAuditLedger
from intelligence import claude_adapter
from intelligence.claude_adapter import ClaudeAdapter


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class ClaudeAdapterTests(unittest.TestCase):
    def test_unconfigured_adapter_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(claude_adapter, "Anthropic", None):
            adapter = ClaudeAdapter()
        result = adapter.run("inspect repository")
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["provider"], "anthropic.claude")

    def test_empty_objective_is_rejected_without_provider_call(self):
        messages = FakeMessages()
        adapter = ClaudeAdapter(client=SimpleNamespace(messages=messages))
        result = adapter.run("  ")
        self.assertEqual(result["status"], "invalid_input")
        self.assertEqual(messages.calls, [])

    def test_run_returns_proposal_and_never_exposes_execution_authority(self):
        response = SimpleNamespace(
            id="msg_test",
            content=[
                SimpleNamespace(type="text", text="Proposed change"),
                SimpleNamespace(type="tool_use", text=None),
            ],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        )
        messages = FakeMessages(response=response)
        adapter = ClaudeAdapter(model="claude-test", client=SimpleNamespace(messages=messages))
        result = adapter.run("Review", {"repo": "example"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output_text"], "Proposed change")
        self.assertEqual(result["authority"], "proposal_only")
        self.assertEqual(result["usage"]["input_tokens"], 12)
        self.assertEqual(messages.calls[0]["model"], "claude-test")
        self.assertEqual(messages.calls[0]["messages"][0]["role"], "user")
        self.assertIn("untrusted reference data", messages.calls[0]["messages"][0]["content"])

    def test_provider_failure_does_not_leak_exception_message(self):
        messages = FakeMessages(error=RuntimeError("secret token must not leak"))
        adapter = ClaudeAdapter(client=SimpleNamespace(messages=messages))
        result = adapter.run("Review")
        self.assertEqual(result["status"], "provider_error")
        self.assertEqual(result["reason"], "RuntimeError")
        self.assertNotIn("secret token", str(result))


    def test_audited_success_records_hashes_usage_and_keeps_verification_pending(self):
        response = SimpleNamespace(
            id="msg_audited",
            content=[SimpleNamespace(type="text", text="Private proposal text")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=18, output_tokens=9),
        )
        messages = FakeMessages(response=response)
        with tempfile.TemporaryDirectory() as tmp:
            with VXAIRequestAuditLedger(os.path.join(tmp, "audit.sqlite3")) as ledger:
                adapter = ClaudeAdapter(
                    model="claude-test",
                    client=SimpleNamespace(messages=messages),
                    audit_ledger=ledger,
                )
                result = adapter.run("Review secret-free architecture", {"revision": "abc123"})
                self.assertEqual(result["status"], "ok")
                request_id = result["audit_request_id"]
                view = ledger.request(request_id)
                self.assertEqual(view["execution_status"], "SUCCEEDED")
                self.assertEqual(view["verification_status"], "PENDING")
                self.assertEqual(view["attempts"][0]["input_tokens"], 18)
                self.assertEqual(view["attempts"][0]["output_tokens"], 9)
                self.assertEqual(len(view["outputs"]), 1)
                self.assertNotIn("Private proposal text", str(view))
                self.assertNotIn("Review secret-free architecture", str(view))
                self.assertTrue(ledger.verify_integrity())

    def test_audited_provider_error_is_recorded_without_exception_text(self):
        messages = FakeMessages(error=RuntimeError("secret token must not leak"))
        with tempfile.TemporaryDirectory() as tmp:
            with VXAIRequestAuditLedger(os.path.join(tmp, "audit.sqlite3")) as ledger:
                adapter = ClaudeAdapter(
                    client=SimpleNamespace(messages=messages),
                    audit_ledger=ledger,
                )
                result = adapter.run("Review an architecture")
                self.assertEqual(result["status"], "provider_error")
                view = ledger.request(result["audit_request_id"])
                self.assertEqual(view["execution_status"], "FAILED")
                self.assertEqual(view["attempts"][0]["status"], "FAILED")
                self.assertNotIn("secret token", str(view))

    def test_audited_unconfigured_provider_is_marked_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=True), patch.object(claude_adapter, "Anthropic", None):
                with VXAIRequestAuditLedger(os.path.join(tmp, "audit.sqlite3")) as ledger:
                    adapter = ClaudeAdapter(audit_ledger=ledger)
                    result = adapter.run("Review an architecture")
                    self.assertEqual(result["status"], "not_configured")
                    self.assertEqual(
                        ledger.request(result["audit_request_id"])["execution_status"],
                        "REJECTED",
                    )

    def test_audit_write_failure_blocks_provider_call(self):
        class BrokenLedger:
            def create_request(self, _record):
                raise RuntimeError("safe internal failure")

        messages = FakeMessages()
        adapter = ClaudeAdapter(
            client=SimpleNamespace(messages=messages),
            audit_ledger=BrokenLedger(),
        )
        result = adapter.run("Review an architecture")
        self.assertEqual(result["status"], "audit_blocked")
        self.assertEqual(messages.calls, [])

    def test_invalid_limits_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "TIMEOUT_MUST_BE_POSITIVE"):
            ClaudeAdapter(timeout_seconds=0)
        with self.assertRaisesRegex(ValueError, "MAX_TOKENS_OUT_OF_RANGE"):
            ClaudeAdapter(max_tokens=9000)


if __name__ == "__main__":
    unittest.main()
