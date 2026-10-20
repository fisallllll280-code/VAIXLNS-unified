"""Adversarial acceptance tests for the Ω.2718 evidence gate.

The verifier in this file is deliberately synthetic and test-only. It is not a
cryptographic implementation and must not be reused for production authority.
"""
from __future__ import annotations

import copy
import unittest

from omega_closure.engine import canonical_sha256, evaluate_closure


TEST_ROOT_HASH = "a" * 64
NOW = "2026-10-15T12:00:00Z"


def _test_only_verifier(signer, payload, signature):
    signer_id = signer.get("signer_id") or signer.get("root_id")
    return signature == f"test:{signer_id}"


def _build_bundle():
    signers = {
        "COUNCIL": {"signer_id": "COUNCIL", "role": "constitutional_council"},
        "PROOF-ENGINE": {"signer_id": "PROOF-ENGINE", "role": "proof_engine"},
        "CLAIM-AUTHOR": {"signer_id": "CLAIM-AUTHOR", "role": "claim_author"},
        "PROOF-VERIFIER": {"signer_id": "PROOF-VERIFIER", "role": "independent_verifier"},
        "AUDITOR-EXTERNAL": {"signer_id": "AUDITOR-EXTERNAL", "role": "independent_auditor"},
    }

    statement = {"claim": "fixture evidence exists", "scope": "test-only"}
    proof_digest = canonical_sha256(statement)
    proof = {
        "proof_id": "MP-001",
        "statement": statement,
        "digest": proof_digest,
        "parent_proof_ids": [],
        "signer_id": "CLAIM-AUTHOR",
        "signature": "test:CLAIM-AUTHOR",
        "verified_by": "PROOF-VERIFIER",
        "verification_signature": "test:PROOF-VERIFIER",
    }

    ledger_body = {
        "sequence": 1,
        "event": "RATIFICATION_RECORDED",
        "actor_id": "COUNCIL",
        "timestamp": NOW,
        "payload_digest": "b" * 64,
        "previous_hash": "0" * 64,
    }
    ledger_entry = {
        **ledger_body,
        "entry_hash": canonical_sha256(ledger_body),
        "signatures": [
            {"signer_id": "COUNCIL", "signature": "test:COUNCIL"},
            {"signer_id": "PROOF-ENGINE", "signature": "test:PROOF-ENGINE"},
        ],
    }

    root = {
        "root_id": "ROOT-001",
        "public_key_fingerprint": TEST_ROOT_HASH,
        "issued_at": NOW,
        "revoked": False,
        "signature": "test:ROOT-001",
    }

    snapshot_body = {
        "invariant_id": "INV-001",
        "ontology_version": "Ω.ontology.v1",
        "generated_at": NOW,
        "meaning": "the agreed test ontology remains stable",
    }
    semantic_snapshot = {
        **snapshot_body,
        "semantic_hash": canonical_sha256(snapshot_body),
    }

    audit_body = {
        "auditor_id": "AUDITOR-EXTERNAL",
        "controlled_engine_owner_ids": ["ENGINE-OWNER-A", "ENGINE-OWNER-B"],
        "scope": ["closure_engine", "proof_engine", "ratification_ledger"],
        "result": "PASS",
        "independent": True,
        "timestamp": NOW,
    }
    audit = {
        **audit_body,
        "audit_hash": canonical_sha256(audit_body),
        "signature": "test:AUDITOR-EXTERNAL",
    }

    return {
        "subject": "Ω.2718",
        "signers": signers,
        "constitutional_binding": {
            "source_id": "CONST-ROOT",
            "immutable": True,
            "authority": "Ω0_GENESIS_CORE",
            "source_ref": "project.genome::v1.0.0",
            "source_hash": "c" * 64,
        },
        "meta_proof": {"proofs": [proof]},
        "closure_engine": {
            "completed_modes": ["structural", "semantic", "temporal", "constitutional"],
            "deterministic": True,
            "fail_closed": True,
        },
        "historical_ratification_ledger": {"entries": [ledger_entry]},
        "failure_sovereignty": {
            "failure_classes": [
                "F1 Storage Failure",
                "F2 Signature Failure",
                "F3 Clock Failure",
                "F4 Activation Failure",
                "F5 Integrity Failure",
            ],
            "failure_invariant": "No failure may alter historical truth.",
            "preserve_previous_accepted_state": True,
        },
        "conflict_resolution": {
            "priority": "PriorityLevel",
            "authority": "AuthorityScore",
            "proof": "ProofScore",
            "override_rules": "OverrideRules",
            "deterministic": True,
            "fail_closed": True,
            "unverified_override_denied": True,
        },
        "proof_obligations": {
            "claims": [{
                "claim_id": "C-001",
                "status": "SATISFIED",
                "required_proof_ids": ["MP-001"],
                "evidence_refs": [{"ref": "evidence://fixture/001", "sha256": "d" * 64}],
            }]
        },
        "constitutional_evolution_control": {
            "approval_threshold": 0.8,
            "required_signatures": ["constitutional_council", "dominion_authority"],
            "human_approval_required": True,
            "requester_cannot_approve": True,
            "preparer_cannot_approve": True,
            "effective_after_seconds": 30 * 24 * 60 * 60,
            "active_amendment": None,
        },
        "trust_root": root,
        "semantic_drift": {
            "semantic_snapshot": semantic_snapshot,
            "drift_level": "none",
        },
        "sovereign_audit": audit,
    }


def _evaluate(
    bundle,
    verifier=_test_only_verifier,
    root_hash=TEST_ROOT_HASH,
    source_hash="c" * 64,
):
    return evaluate_closure(
        bundle,
        canonical_source_hash=source_hash,
        trusted_root_hash=root_hash,
        signature_verifier=verifier,
    )


class Omega2718SovereignClosureTests(unittest.TestCase):
    def test_complete_fixture_closes_only_with_explicit_trust_inputs(self):
        report = _evaluate(_build_bundle())
        self.assertEqual(report.status, "CLOSED")
        self.assertEqual(len(report.checks), 11)
        self.assertTrue(all(item.passed for item in report.checks))
        self.assertEqual(len(report.report_digest), 64)

    def test_no_verifier_fails_closed(self):
        report = _evaluate(_build_bundle(), verifier=None)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("CRYPTOGRAPHIC_VERIFIER_UNAVAILABLE", [c.detail for c in report.checks])


    def test_canonical_source_hash_must_be_pinned_out_of_band(self):
        bundle = _build_bundle()
        report = _evaluate(bundle, source_hash=None)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("CANONICAL_SOURCE_HASH_NOT_PINNED", [c.detail for c in report.checks])

    def test_canonical_source_hash_mismatch_is_detected(self):
        bundle = _build_bundle()
        report = _evaluate(bundle, source_hash="f" * 64)
        self.assertIn("CANONICAL_SOURCE_HASH_MISMATCH", [c.detail for c in report.checks])

    def test_unpinned_or_mismatched_trust_root_fails(self):
        report = _evaluate(_build_bundle(), root_hash="e" * 64)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("TRUST_ROOT_MISMATCH", [c.detail for c in report.checks])

    def test_revoked_trust_root_fails(self):
        bundle = _build_bundle()
        bundle["trust_root"]["revoked"] = True
        self.assertEqual(_evaluate(bundle).status, "BLOCKED")

    def test_critical_semantic_drift_blocks_ratification(self):
        bundle = _build_bundle()
        bundle["semantic_drift"]["drift_level"] = "critical"
        report = _evaluate(bundle)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("CRITICAL_SEMANTIC_DRIFT_RATIFICATION_BLOCKED", [c.detail for c in report.checks])

    def test_semantic_snapshot_tampering_is_detected(self):
        bundle = _build_bundle()
        bundle["semantic_drift"]["semantic_snapshot"]["meaning"] = "silently changed"
        report = _evaluate(bundle)
        self.assertIn("SEMANTIC_SNAPSHOT_HASH_MISMATCH", [c.detail for c in report.checks])

    def test_self_audit_is_forbidden(self):
        bundle = _build_bundle()
        bundle["sovereign_audit"]["controlled_engine_owner_ids"].append("AUDITOR-EXTERNAL")
        bundle["sovereign_audit"]["audit_hash"] = canonical_sha256({
            key: value for key, value in bundle["sovereign_audit"].items()
            if key not in {"audit_hash", "signature"}
        })
        self.assertIn("SELF_AUDIT_FORBIDDEN", [c.detail for c in _evaluate(bundle).checks])

    def test_ledger_tampering_is_detected(self):
        bundle = _build_bundle()
        bundle["historical_ratification_ledger"]["entries"][0]["event"] = "ALTERED"
        self.assertIn("LEDGER_ENTRY_HASH_MISMATCH", [c.detail for c in _evaluate(bundle).checks])

    def test_missing_claim_evidence_blocks_closure(self):
        bundle = _build_bundle()
        bundle["proof_obligations"]["claims"][0]["evidence_refs"] = []
        self.assertIn("CLAIM_EVIDENCE_MISSING:C-001", [c.detail for c in _evaluate(bundle).checks])

    def test_proof_signer_and_verifier_must_be_distinct(self):
        bundle = _build_bundle()
        bundle["meta_proof"]["proofs"][0]["verified_by"] = "CLAIM-AUTHOR"
        self.assertIn("PROOF_ROLE_SEPARATION_FAILED:MP-001", [c.detail for c in _evaluate(bundle).checks])

    def test_closure_requires_all_four_modes(self):
        bundle = _build_bundle()
        bundle["closure_engine"]["completed_modes"].remove("temporal")
        self.assertIn("CLOSURE_ENGINE_MODES_INCOMPLETE", [c.detail for c in _evaluate(bundle).checks])

    def test_failure_model_must_preserve_previous_accepted_state(self):
        bundle = _build_bundle()
        bundle["failure_sovereignty"]["preserve_previous_accepted_state"] = False
        self.assertIn("FAILURE_MODEL_INCOMPLETE", [c.detail for c in _evaluate(bundle).checks])

    def test_report_is_deterministic_for_same_evidence(self):
        bundle = _build_bundle()
        first = _evaluate(bundle).report_digest
        second = _evaluate(copy.deepcopy(bundle)).report_digest
        self.assertEqual(first, second)

    def test_canonical_hash_rejects_non_json_nan(self):
        with self.assertRaises(ValueError):
            canonical_sha256({"not_finite": float("nan")})


if __name__ == "__main__":
    unittest.main()
