"""Conformance tests for ARC-X's deterministic EIR and fail-closed gate."""
from __future__ import annotations

import unittest

from arc_x.core import (
    AdmissionDecision,
    AuthorityApproval,
    ClaimKind,
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    ProofObligation,
    SourceReceipt,
    Stance,
    compile_eir,
    evaluate_admission,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


def source(source_id: str = "SRC-1", digest: str = HASH_A) -> SourceReceipt:
    return SourceReceipt(
        source_id=source_id,
        repository="owner/repo",
        revision="1" * 40,
        path="src/module.py",
        content_sha256=digest,
        retrieved_at="2026-10-09T10:00:00Z",
        source_uri="https://example.invalid/pinned/source",
    )


def fully_supported():
    claim = ClaimRecord("CLM-1", "The declared check passed", ClaimKind.IMPLEMENTATION)
    evidence = EvidenceRecord(
        "EVD-1", "SRC-1", EvidenceKind.TEST_RESULT, "Test suite passed",
        claim_id="CLM-1", stance=Stance.SUPPORTS, result="PASS", artifact_sha256=HASH_B,
    )
    obligation = ProofObligation("PO-1", "CLM-1", "Run and retain test evidence", evidence_ids=("EVD-1",))
    return compile_eir([source()], [evidence], [claim], [obligation])


class ArcXCoreTests(unittest.TestCase):
    def test_eir_hash_is_deterministic_and_input_order_independent(self):
        s1, s2 = source("SRC-1"), source("SRC-2", HASH_B)
        c1 = ClaimRecord("CLM-1", "Claim one", ClaimKind.IMPLEMENTATION)
        c2 = ClaimRecord("CLM-2", "Claim two", ClaimKind.OBSERVATION)
        e1 = EvidenceRecord("EVD-1", "SRC-1", EvidenceKind.SOURCE_EXTRACT, "Supports one", "CLM-1", Stance.SUPPORTS)
        e2 = EvidenceRecord("EVD-2", "SRC-2", EvidenceKind.SOURCE_EXTRACT, "Supports two", "CLM-2", Stance.SUPPORTS)
        a = compile_eir([s1, s2], [e1, e2], [c1, c2], [])
        b = compile_eir([s2, s1], [e2, e1], [c2, c1], [])
        self.assertEqual(a.eir_sha256, b.eir_sha256)
        self.assertEqual(a.eir, b.eir)

    def test_mutable_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_REVISION_MUST_BE_IMMUTABLE_PIN"):
            SourceReceipt("SRC", "owner/repo", "main", "README.md", HASH_A, "2026-10-09T10:00:00Z")

    def test_invalid_source_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_CONTENT_HASH_MUST_BE_SHA256"):
            SourceReceipt("SRC", "owner/repo", "1" * 40, "README.md", "not-a-hash", "now")

    def test_dangling_source_reference_blocks(self):
        claim = ClaimRecord("CLM-1", "Runtime is safe", ClaimKind.RUNTIME)
        evidence = EvidenceRecord("EVD-1", "MISSING", EvidenceKind.SOURCE_EXTRACT, "Observed", "CLM-1", Stance.SUPPORTS)
        result = compile_eir([], [evidence], [claim])
        self.assertEqual(result.epistemic_state, "MISSING")
        self.assertIn("DANGLING_SOURCE_REFERENCE", {item["code"] for item in result.findings})

    def test_contradictory_evidence_is_preserved_not_silently_merged(self):
        claim = ClaimRecord("CLM-1", "The runtime is deterministic", ClaimKind.RUNTIME)
        evidence = [
            EvidenceRecord("EVD-1", "SRC-1", EvidenceKind.SOURCE_EXTRACT, "Supports", "CLM-1", Stance.SUPPORTS),
            EvidenceRecord("EVD-2", "SRC-2", EvidenceKind.SOURCE_EXTRACT, "Refutes", "CLM-1", Stance.REFUTES),
        ]
        result = compile_eir([source("SRC-1"), source("SRC-2", HASH_B)], evidence, [claim])
        self.assertEqual(result.epistemic_state, "CONFLICT")
        self.assertEqual(result.claim_results["CLM-1"], "CONFLICT")
        self.assertEqual(sum(item["code"] == "CONTRADICTORY_EVIDENCE" for item in result.findings), 1)

    def test_inference_without_linked_support_is_not_verified(self):
        claim = ClaimRecord("CLM-1", "A new capability exists", ClaimKind.INFERENCE)
        result = compile_eir([source()], [], [claim])
        self.assertEqual(result.claim_results["CLM-1"], "UNSUPPORTED")
        self.assertFalse(result.proof_scope_complete)

    def test_open_required_obligation_blocks_verification(self):
        claim = ClaimRecord("CLM-1", "Check passed", ClaimKind.IMPLEMENTATION)
        result = compile_eir([source()], [], [claim], [ProofObligation("PO-1", "CLM-1", "Test", evidence_ids=())])
        self.assertIn("PROOF_OBLIGATION_OPEN", {item["code"] for item in result.findings})
        self.assertFalse(result.proof_scope_complete)

    def test_failed_test_cannot_satisfy_proof_obligation(self):
        claim = ClaimRecord("CLM-1", "Check passed", ClaimKind.IMPLEMENTATION)
        evidence = EvidenceRecord(
            "EVD-1", "SRC-1", EvidenceKind.TEST_RESULT, "Test failed", "CLM-1",
            Stance.SUPPORTS, result="FAIL", artifact_sha256=HASH_B,
        )
        result = compile_eir([source()], [evidence], [claim], [ProofObligation("PO-1", "CLM-1", "Passing test", evidence_ids=("EVD-1",))])
        self.assertEqual(result.obligation_results["PO-1"], "OPEN")
        self.assertFalse(result.proof_scope_complete)

    def test_passing_declared_scope_does_not_auto_authorize_execution(self):
        result = fully_supported()
        self.assertTrue(result.proof_scope_complete)
        denied = evaluate_admission(result, "EXECUTE")
        self.assertEqual(denied.decision, AdmissionDecision.BLOCKED)
        self.assertIn("TRUSTED_EVIDENCE_VERIFIER_REQUIRED", denied.reason_codes)
        evidence_checked = evaluate_admission(result, "EXECUTE", evidence_verifier=lambda _: True)
        self.assertIn("TRUSTED_AUTHORITY_VERIFIER_REQUIRED", evidence_checked.reason_codes)

    def test_wrong_approval_scope_is_denied(self):
        result = fully_supported()
        approval = AuthorityApproval("APR-1", "operator-1", "canonical-admission")
        denied = evaluate_admission(
            result, "EXECUTE", approval,
            evidence_verifier=lambda _: True,
            authority_verifier=lambda *_: True,
        )
        self.assertEqual(denied.decision, AdmissionDecision.BLOCKED)
        self.assertIn("AUTHORITY_SCOPE_OR_DECISION_MISMATCH", denied.reason_codes)

    def test_untrusted_or_failed_authority_verification_is_denied(self):
        result = fully_supported()
        approval = AuthorityApproval("APR-1", "operator-1", "execution")
        denied = evaluate_admission(
            result, "EXECUTE", approval,
            evidence_verifier=lambda _: True,
            authority_verifier=lambda *_: False,
        )
        self.assertEqual(denied.decision, AdmissionDecision.BLOCKED)
        self.assertIn("AUTHORITY_VERIFICATION_FAILED", denied.reason_codes)

    def test_only_verified_scope_and_trusted_approval_admit_action(self):
        result = fully_supported()
        approval = AuthorityApproval("APR-1", "operator-1", "execution")
        admitted = evaluate_admission(
            result, "EXECUTE", approval,
            evidence_verifier=lambda compiled: compiled.eir_sha256 == result.eir_sha256,
            authority_verifier=lambda item, scope: item.actor_id == "operator-1" and scope == "execution",
        )
        self.assertEqual(admitted.decision, AdmissionDecision.ADMITTED)
        self.assertEqual(admitted.eir_sha256, result.eir_sha256)

    def test_verify_requires_trusted_evidence_verifier(self):
        result = fully_supported()
        denied = evaluate_admission(result, "VERIFY")
        self.assertEqual(denied.decision, AdmissionDecision.BLOCKED)
        self.assertIn("TRUSTED_EVIDENCE_VERIFIER_REQUIRED", denied.reason_codes)
        verified = evaluate_admission(result, "VERIFY", evidence_verifier=lambda item: item.eir_sha256 == result.eir_sha256)
        self.assertEqual(verified.decision, AdmissionDecision.VERIFIED)
        self.assertIn("DECLARED_SCOPE_VERIFIED_BY_TRUSTED_EVIDENCE_VERIFIER", verified.reason_codes)

    def test_evidence_verifier_failure_blocks_even_with_valid_looking_approval(self):
        result = fully_supported()
        approval = AuthorityApproval("APR-1", "operator-1", "execution")
        denied = evaluate_admission(
            result, "EXECUTE", approval,
            evidence_verifier=lambda _: False,
            authority_verifier=lambda *_: True,
        )
        self.assertEqual(denied.decision, AdmissionDecision.BLOCKED)
        self.assertIn("EVIDENCE_ATTESTATION_FAILED", denied.reason_codes)

    def test_proof_for_another_claim_cannot_satisfy_obligation(self):
        claims = [
            ClaimRecord("CLM-1", "First claim", ClaimKind.IMPLEMENTATION),
            ClaimRecord("CLM-2", "Second claim", ClaimKind.IMPLEMENTATION),
        ]
        evidence = [
            EvidenceRecord("EVD-1", "SRC-1", EvidenceKind.TEST_RESULT, "Test for second claim",
                           "CLM-2", Stance.SUPPORTS, result="PASS", artifact_sha256=HASH_B),
        ]
        obligations = [ProofObligation("PO-1", "CLM-1", "Proof for first claim", evidence_ids=("EVD-1",))]
        result = compile_eir([source()], evidence, claims, obligations)
        self.assertEqual(result.obligation_results["PO-1"], "OPEN")
        self.assertIn("PROOF_OBLIGATION_OPEN", {item["code"] for item in result.findings})
        self.assertFalse(result.proof_scope_complete)

    def test_each_required_claim_needs_a_required_obligation(self):
        claims = [
            ClaimRecord("CLM-1", "First claim", ClaimKind.IMPLEMENTATION),
            ClaimRecord("CLM-2", "Second claim", ClaimKind.IMPLEMENTATION),
        ]
        evidence = [
            EvidenceRecord("EVD-1", "SRC-1", EvidenceKind.TEST_RESULT, "Passing check",
                           "CLM-1", Stance.SUPPORTS, result="PASS", artifact_sha256=HASH_B),
            EvidenceRecord("EVD-2", "SRC-1", EvidenceKind.SOURCE_EXTRACT, "Supports second",
                           "CLM-2", Stance.SUPPORTS),
        ]
        obligations = [ProofObligation("PO-1", "CLM-1", "Proof for first", evidence_ids=("EVD-1",))]
        result = compile_eir([source()], evidence, claims, obligations)
        self.assertIn("REQUIRED_CLAIM_WITHOUT_PROOF_OBLIGATION", {item["code"] for item in result.findings})
        self.assertFalse(result.proof_scope_complete)

    def test_revision_tag_is_not_accepted_as_immutable_pin(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_REVISION_MUST_BE_IMMUTABLE_PIN"):
            SourceReceipt("SRC", "owner/repo", "v1.0.0", "README.md", HASH_A, "2026-10-09T10:00:00Z")

    def test_retrieval_timestamp_must_be_timezone_aware_iso8601(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_RETRIEVAL_TIMESTAMP_MUST_BE_AWARE_ISO8601"):
            SourceReceipt("SRC", "owner/repo", "1" * 40, "README.md", HASH_A, "2026-10-09 10:00:00")

    def test_research_can_inspect_conflicts_but_execution_cannot(self):
        claim = ClaimRecord("CLM-1", "The runtime is deterministic", ClaimKind.RUNTIME)
        evidence = [
            EvidenceRecord("EVD-1", "SRC-1", EvidenceKind.SOURCE_EXTRACT, "Supports", "CLM-1", Stance.SUPPORTS),
            EvidenceRecord("EVD-2", "SRC-2", EvidenceKind.SOURCE_EXTRACT, "Refutes", "CLM-1", Stance.REFUTES),
        ]
        result = compile_eir([source("SRC-1"), source("SRC-2", HASH_B)], evidence, [claim])
        research = evaluate_admission(result, "RESEARCH")
        execution = evaluate_admission(result, "EXECUTE")
        self.assertEqual(research.decision, AdmissionDecision.ELIGIBLE_FOR_REVIEW)
        self.assertIn("CONFLICT_PRESERVED_FOR_RESEARCH", research.reason_codes)
        self.assertEqual(execution.decision, AdmissionDecision.BLOCKED)

    def test_unknown_action_fails_closed(self):
        result = fully_supported()
        denied = evaluate_admission(result, "DELETE_EVERYTHING")
        self.assertEqual(denied.decision, AdmissionDecision.BLOCKED)
        self.assertIn("UNKNOWN_ACTION", denied.reason_codes)

    def test_duplicate_ids_are_detected(self):
        s = source()
        result = compile_eir([s, s], [], [])
        self.assertIn("DUPLICATE_SOURCE_ID", {item["code"] for item in result.findings})
        self.assertTrue(result.has_blocking_findings)


if __name__ == "__main__":
    unittest.main()
