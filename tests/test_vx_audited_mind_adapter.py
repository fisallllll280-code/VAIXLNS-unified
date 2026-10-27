from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass, field
from typing import Any

from infra.vx_ai_request_audit import VXAIRequestAuditLedger
from intelligence.audited_mind_adapter import VXAuditedMindAdapter


@dataclass
class FakeMind:
    id: str = "mind-research-01"
    role: str = "research"
    capabilities: list[str] = field(default_factory=lambda: ["research"])
    provider: str = "provider-test"
    endpoint: str | None = "https://provider.invalid"


@dataclass
class FakeTask:
    id: str = "task-audit-01"
    objective: str = "Do not persist this raw objective"
    kind: str = "research"
    context: dict[str, Any] = field(default_factory=lambda: {"secret_free": "context"})
    constraints: list[str] = field(default_factory=lambda: ["propose-only"])


class FakeAdapter:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {
            "status": "ok",
            "id": "provider-response-01",
            "output_text": "Do not persist this raw model result",
            "usage": {"input_tokens": 8, "output_tokens": 5},
            "stop_reason": "end_turn",
        }
        self.error = error
        self.calls = 0

    def run(self, mind, task):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class BrokenLedger:
    def create_request(self, record):
        raise RuntimeError("audit storage unavailable")


class VXAuditedMindAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "vx-audit.sqlite3")
        self.ledger = VXAIRequestAuditLedger(self.db_path)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_success_is_recorded_without_persisting_prompt_or_output(self):
        inner = FakeAdapter()
        adapter = VXAuditedMindAdapter(inner, self.ledger)
        result = adapter.run(FakeMind(), FakeTask())

        self.assertEqual(result["status"], "ok")
        self.assertIn("audit_request_id", result)
        view = self.ledger.request(result["audit_request_id"])
        self.assertEqual(view["execution_status"], "SUCCEEDED")
        self.assertEqual(view["verification_status"], "PENDING")
        self.assertEqual(view["attempts"][0]["input_tokens"], 8)
        self.assertEqual(view["attempts"][0]["output_tokens"], 5)
        serialized = repr(view)
        self.assertNotIn("Do not persist this raw objective", serialized)
        self.assertNotIn("Do not persist this raw model result", serialized)
        self.assertTrue(self.ledger.verify_integrity())

    def test_audit_failure_before_call_blocks_inner_adapter(self):
        inner = FakeAdapter()
        adapter = VXAuditedMindAdapter(inner, BrokenLedger())
        result = adapter.run(FakeMind(), FakeTask())
        self.assertEqual(result["status"], "audit_blocked")
        self.assertEqual(inner.calls, [])

    def test_not_configured_adapter_is_recorded_as_failed_without_provider_attempt(self):
        inner = FakeAdapter(result={"status": "not_configured", "reason": "missing settings"})
        adapter = VXAuditedMindAdapter(inner, self.ledger)
        result = adapter.run(FakeMind(), FakeTask())
        self.assertEqual(result["status"], "not_configured")
        view = self.ledger.request(result["audit_request_id"])
        self.assertEqual(view["execution_status"], "FAILED")
        self.assertEqual(view["attempts"], [])

    def test_adapter_exception_is_recorded_without_exception_text(self):
        inner = FakeAdapter(error=RuntimeError("raw secret must not be logged"))
        adapter = VXAuditedMindAdapter(inner, self.ledger)
        result = adapter.run(FakeMind(), FakeTask())
        self.assertEqual(result["status"], "provider_error")
        view = self.ledger.request(result["audit_request_id"])
        self.assertEqual(view["execution_status"], "FAILED")
        self.assertEqual(view["attempts"][0]["status"], "FAILED")
        self.assertNotIn("raw secret must not be logged", repr(view))
        self.assertNotIn("raw secret must not be logged", repr(result))

    def test_timeout_is_a_distinct_terminal_status(self):
        inner = FakeAdapter(error=TimeoutError("deadline exceeded"))
        adapter = VXAuditedMindAdapter(inner, self.ledger)
        result = adapter.run(FakeMind(), FakeTask())
        view = self.ledger.request(result["audit_request_id"])
        self.assertEqual(view["execution_status"], "TIMED_OUT")
        self.assertEqual(view["attempts"][0]["status"], "TIMED_OUT")

    def test_adapter_reported_error_is_not_passed_through(self):
        inner = FakeAdapter(result={"status": "provider_error", "reason": "credentials were bad"})
        adapter = VXAuditedMindAdapter(inner, self.ledger)
        result = adapter.run(FakeMind(), FakeTask())
        self.assertEqual(result["status"], "provider_error")
        self.assertEqual(result["reason"], "ADAPTER_REPORTED_ERROR")
        self.assertNotIn("credentials were bad", repr(result))
        self.assertEqual(self.ledger.request(result["audit_request_id"])["execution_status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
