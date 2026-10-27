from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from infra.vx_ai_request_audit import (
    AuditIntegrityError,
    AuditLedgerError,
    VXAIRequestAuditLedger,
)


def request_record(**overrides):
    data = {
        "request_id": "vxreq-test-001",
        "trace_id": "vxtrace-test-001",
        "parent_request_id": None,
        "tenant_id": "test-tenant",
        "actor_id": "test-actor",
        "agent_id": "VX-Research-01",
        "purpose": "technical_analysis",
        "provider": "provider-test",
        "model_id": "model-test",
        "model_version": "model-rev-001",
        "policy_version": "policy-v1",
        "input_hash": "a" * 64,
        "input_ref": "secure://input/test-001",
        "input_tokens": 120,
        "input_classification": "INTERNAL",
    }
    data.update(overrides)
    return data


def to_running(ledger: VXAIRequestAuditLedger, request_id: str) -> None:
    ledger.create_request(request_record(request_id=request_id))
    ledger.transition_status(request_id, "VALIDATING", changed_by="test-runner")
    ledger.transition_status(request_id, "RUNNING", changed_by="test-runner")


class VXAIRequestAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "vx-ai-audit.sqlite3")
        self.ledger = VXAIRequestAuditLedger(self.db_path)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_create_request_is_idempotent_and_does_not_store_prompt(self):
        record = request_record()
        first = self.ledger.create_request(record)
        second = self.ledger.create_request(record)
        self.assertEqual(first.event_hash, second.event_hash)
        view = self.ledger.request(record["request_id"])
        self.assertEqual(view["execution_status"], "RECEIVED")
        self.assertEqual(view["verification_status"], "PENDING")
        self.assertEqual(view["billing_status"], "NOT_AVAILABLE")
        serialized = repr(view)
        self.assertNotIn("raw prompt", serialized)
        self.assertNotIn("authorization", serialized)

    def test_raw_prompt_fields_are_rejected(self):
        with self.assertRaisesRegex(AuditLedgerError, "UNKNOWN_REQUEST_FIELDS"):
            self.ledger.create_request(request_record(prompt="raw prompt must not enter audit log"))

    def test_input_hash_and_timestamps_are_validated(self):
        with self.assertRaisesRegex(AuditLedgerError, "INPUT_HASH_MUST_BE_SHA256_HEX"):
            self.ledger.create_request(request_record(input_hash="not-a-hash"))
        with self.assertRaisesRegex(AuditLedgerError, "CREATED_AT_MUST_INCLUDE_TIMEZONE"):
            self.ledger.create_request(request_record(
                request_id="vxreq-naive-time",
                created_at="2026-10-27T12:00:00",
            ))

    def test_illegal_execution_transition_fails_closed(self):
        self.ledger.create_request(request_record())
        with self.assertRaisesRegex(AuditLedgerError, "ILLEGAL_EXECUTION_TRANSITION"):
            self.ledger.transition_status(
                "vxreq-test-001", "SUCCEEDED", changed_by="test-runner"
            )
        with self.assertRaisesRegex(AuditLedgerError, "TERMINAL_NON_SUCCESS_REQUIRES_REASON"):
            self.ledger.transition_status(
                "vxreq-test-001", "REJECTED", changed_by="policy-gate"
            )

    def test_success_requires_output_and_status_retry_is_idempotent(self):
        to_running(self.ledger, "vxreq-success")
        event = self.ledger.transition_status(
            "vxreq-success", "VALIDATING", changed_by="ignored"
        ) if False else None
        output = {
            "output_id": "out-001",
            "output_hash": "b" * 64,
            "output_ref": "secure://outputs/out-001",
            "output_tokens": 35,
            "format": "text",
            "classification": "INTERNAL",
        }
        recorded = self.ledger.record_output("vxreq-success", output)
        replayed = self.ledger.record_output("vxreq-success", output)
        self.assertEqual(recorded.event_hash, replayed.event_hash)
        succeeded = self.ledger.transition_status(
            "vxreq-success", "SUCCEEDED", changed_by="vx-runtime"
        )
        self.assertEqual(succeeded.event_type, "VX_AI_REQUEST_STATUS_CHANGED")
        self.assertEqual(
            self.ledger.transition_status(
                "vxreq-success", "SUCCEEDED", changed_by="vx-runtime"
            ).event_hash,
            succeeded.event_hash,
        )
        self.assertEqual(self.ledger.request("vxreq-success")["execution_status"], "SUCCEEDED")

    def test_attempt_times_and_source_lineage_are_recorded(self):
        to_running(self.ledger, "vxreq-lineage")
        attempt = {
            "attempt_id": "attempt-001",
            "attempt_number": 1,
            "provider": "provider-test",
            "model_id": "model-test",
            "status": "SUCCEEDED",
            "started_at": "2026-10-27T21:00:00Z",
            "first_token_at": "2026-10-27T21:00:00.200Z",
            "completed_at": "2026-10-27T21:00:01Z",
            "input_tokens": 120,
            "output_tokens": 35,
            "finish_reason": "stop",
            "provider_request_id": "provider-request-123",
            "route_id": "route-primary",
        }
        first = self.ledger.record_attempt("vxreq-lineage", attempt)
        replay = self.ledger.record_attempt("vxreq-lineage", attempt)
        self.assertEqual(first.event_hash, replay.event_hash)
        self.assertEqual(first.payload["attempt"]["latency_ms"], 1000.0)
        self.assertEqual(first.payload["attempt"]["time_to_first_token_ms"], 200.0)

        source = {
            "source_record_id": "source-001",
            "source_type": "RAG",
            "source_name": "internal_knowledge_base",
            "source_version": "kb-2026-10-27",
            "retrieved_at": "2026-10-27T20:59:59Z",
            "content_hash": "c" * 64,
            "source_uri_ref": "kb://docs/architecture",
            "usage_purpose": "ground_response",
            "trust_status": "VERIFIED",
            "usage_state": "USED",
            "contribution_ref": "output-span:1",
        }
        self.ledger.record_source("vxreq-lineage", source)
        view = self.ledger.request("vxreq-lineage")
        self.assertEqual(len(view["attempts"]), 1)
        self.assertEqual(view["metrics"]["time_to_first_token_ms"], [200.0])
        self.assertEqual(view["sources"][0]["content_hash"], "c" * 64)

    def test_used_source_requires_digest(self):
        self.ledger.create_request(request_record())
        with self.assertRaisesRegex(AuditLedgerError, "USED_SOURCE_REQUIRES_CONTENT_HASH"):
            self.ledger.record_source("vxreq-test-001", {
                "source_record_id": "source-no-digest",
                "source_type": "WEB",
                "source_name": "search-provider",
                "usage_purpose": "research",
                "trust_status": "NOT_VERIFIED",
                "usage_state": "USED",
            })

    def test_cost_is_decimal_and_requires_reconciliation(self):
        self.ledger.create_request(request_record())
        estimated = self.ledger.record_cost("vxreq-test-001", {
            "cost_record_id": "estimate-input",
            "category": "INPUT_TOKENS",
            "entry_type": "CHARGE",
            "basis": "ESTIMATE",
            "amount": "0.01000",
            "currency": "USD",
            "price_source": "provider-price-table",
            "tariff_version": "2026-10-01",
        })
        self.assertEqual(estimated.payload["cost"]["amount"], "0.01")
        with self.assertRaisesRegex(AuditLedgerError, "COST_AMOUNT_MUST_BE_DECIMAL"):
            self.ledger.record_cost("vxreq-test-001", {
                "cost_record_id": "float-cost",
                "category": "OUTPUT_TOKENS",
                "entry_type": "CHARGE",
                "basis": "PROVIDER_REPORTED",
                "amount": 0.012,
                "currency": "USD",
            })
        self.ledger.record_cost("vxreq-test-001", {
            "cost_record_id": "provider-actual",
            "category": "OUTPUT_TOKENS",
            "entry_type": "CHARGE",
            "basis": "PROVIDER_REPORTED",
            "amount": "0.0125",
            "currency": "USD",
            "price_source": "provider-usage-response",
        })
        view = self.ledger.request("vxreq-test-001")
        self.assertEqual(view["billing_status"], "PENDING_RECONCILIATION")
        self.ledger.set_billing_status(
            "vxreq-test-001", "RECONCILED", changed_by="billing-reconciler",
            reason="matched to provider usage record",
        )
        view = self.ledger.request("vxreq-test-001")
        self.assertEqual(view["billing_status"], "RECONCILED")
        self.assertEqual(view["cost_totals"]["USD"]["ESTIMATE"]["CHARGE"], "0.01")
        self.assertEqual(view["cost_totals"]["USD"]["PROVIDER_REPORTED"]["CHARGE"], "0.0125")

    def test_reconciled_without_actual_cost_is_rejected(self):
        self.ledger.create_request(request_record())
        self.ledger.record_cost("vxreq-test-001", {
            "cost_record_id": "estimate-only",
            "category": "OTHER",
            "entry_type": "CHARGE",
            "basis": "ESTIMATE",
            "amount": "1",
            "currency": "USD",
        })
        with self.assertRaisesRegex(AuditLedgerError, "RECONCILED_REQUIRES_NON_ESTIMATED_COST"):
            self.ledger.set_billing_status(
                "vxreq-test-001", "RECONCILED", changed_by="billing-reconciler"
            )

    def test_verified_requires_evidence_and_passed_checks(self):
        self.ledger.create_request(request_record())
        with self.assertRaisesRegex(AuditLedgerError, "VERIFIED_REQUIRES_PASSED_CHECKS_AND_EVIDENCE"):
            self.ledger.record_verification("vxreq-test-001", {
                "verification_id": "verify-bad",
                "status": "VERIFIED",
                "verifier_id": "independent-verifier",
                "policy_version": "policy-v1",
                "checks_passed": True,
                "evidence_refs": [],
            })
        self.ledger.record_verification("vxreq-test-001", {
            "verification_id": "verify-good",
            "status": "VERIFIED",
            "verifier_id": "independent-verifier",
            "policy_version": "policy-v1",
            "checks_passed": True,
            "evidence_refs": ["ci://run/123", "artifact://sha256/abcdef"],
            "reason": "all required checks passed",
        })
        view = self.ledger.request("vxreq-test-001")
        self.assertEqual(view["verification_status"], "VERIFIED")
        self.assertEqual(len(view["verifications"]), 1)

    def test_tampered_chain_fails_closed_on_restart(self):
        self.ledger.create_request(request_record())
        self.ledger.close()
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE events SET payload_json=? WHERE event_id=?",
                ('{"tampered":true}', "vx-ai-request:vxreq-test-001:created"),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(AuditIntegrityError, "EXISTING_DURABLE_EVENT_CHAIN_INVALID"):
            VXAIRequestAuditLedger(self.db_path)

    def test_integrity_and_event_references_are_present(self):
        to_running(self.ledger, "vxreq-integrity")
        self.ledger.record_output("vxreq-integrity", {
            "output_id": "output-001",
            "output_hash": "d" * 64,
            "output_tokens": 5,
        })
        self.ledger.transition_status("vxreq-integrity", "SUCCEEDED", changed_by="vx-runtime")
        view = self.ledger.request("vxreq-integrity")
        self.assertTrue(self.ledger.verify_integrity())
        self.assertTrue(view["event_refs"])
        self.assertTrue(all(item["event_hash"] for item in view["event_refs"]))
        self.assertGreaterEqual(view["metrics"]["observed_wall_clock_ms"], 0)


if __name__ == "__main__":
    unittest.main()
