import unittest

from innovation_control.research_fabric import (
    CatalogEntry,
    ClaimEvidence,
    DecisionState,
    EvidenceClass,
    QueryPurpose,
    ResearchClaim,
    ResearchDecisionOrchestrator,
    ResearchRequest,
    SourceRecord,
    Stance,
)


class StaticProvider:
    provider_id = "static-test-corpus"

    def __init__(self, records=(), fail_purpose=None):
        self.records = tuple(records)
        self.fail_purpose = fail_purpose

    def search(self, query, scopes):
        if query.purpose is self.fail_purpose:
            raise RuntimeError("injected provider failure")
        # Each record is returned on each lane to exercise deterministic deduplication.
        return self.records


def complete_spec():
    return {
        "problem_statement": "Avoid duplicate and unverified innovations",
        "assumptions": ["sources are supplied by adapters"],
        "invariants": ["no self-promotion"],
        "architecture": {"research": "multi-lane"},
        "interfaces": ["SearchProvider"],
        "dependencies": ["innovation_control"],
        "security_boundary": "read-only research; no deployment authority",
        "failure_modes": ["provider failure", "contradictory claims"],
        "implementation_plan": ["run search", "review evidence"],
        "acceptance_tests": ["contradictions block"],
        "verification_plan": ["replay deterministic input"],
        "rollback_plan": ["revert branch"],
        "operational_metrics": ["source coverage", "failed search lanes"],
        "owner": "VAIXLNS",
        "evidence_refs": ["repository/test-fixture"],
        "known_unknowns": ["historical catalog completeness"],
    }


class ResearchFabricTests(unittest.TestCase):
    def test_query_plan_has_counterevidence_and_implementation_lanes(self):
        request = ResearchRequest("prevent duplication", "Innovation Research Fabric")
        purposes = {q.purpose for q in __import__(
            "innovation_control.research_fabric", fromlist=["build_query_plan"]
        ).build_query_plan(request)}
        self.assertTrue({QueryPurpose.COUNTEREVIDENCE, QueryPurpose.IMPLEMENTATION,
                         QueryPurpose.NOVELTY, QueryPurpose.FAILURE_ANALYSIS}.issubset(purposes))

    def test_unknown_catalog_completeness_never_claims_novelty(self):
        request = ResearchRequest("find overlap", "New Capability", catalog=(
            CatalogEntry("OLD-1", "Unrelated Capability"),
        ), catalog_coverage_complete=False)
        bundle = ResearchDecisionOrchestrator().run(request, [StaticProvider()])
        self.assertEqual(bundle.novelty_state, "CATALOG_INCOMPLETE")
        self.assertFalse(bundle.canonical_eligible)
        self.assertFalse(bundle.promotion_authorized)

    def test_exact_catalog_match_blocks_duplicate_creation(self):
        request = ResearchRequest("duplicate check", "Replay Safety", catalog=(
            CatalogEntry("VX-REPLAY-1", "Replay Safety", aliases=("Replay safety",)),
        ), catalog_coverage_complete=True)
        bundle = ResearchDecisionOrchestrator().run(request, [StaticProvider()])
        self.assertEqual(bundle.decision_state, DecisionState.BLOCKED)
        self.assertEqual(bundle.novelty_state, "EXACT_CATALOG_MATCH")

    def test_source_hash_tampering_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_CONTENT_HASH_MISMATCH"):
            SourceRecord(title="T", uri="repo/file", content="tampered", content_sha256="0" * 64)

    def test_claim_with_support_and_refutation_blocks(self):
        record = SourceRecord(
            title="Primary source", uri="repo/spec.md", content="spec evidence",
            evidence_class=EvidenceClass.IMPLEMENTATION,
            claims=(ClaimEvidence("C-1", Stance.SUPPORTS, "supports claim"),
                    ClaimEvidence("C-1", Stance.REFUTES, "refutes claim")),
        )
        request = ResearchRequest(
            "check contradiction", "Claim review", claims=(ResearchClaim("C-1", "the runtime is deterministic"),),
            catalog_coverage_complete=True, engineering_spec=complete_spec(),
            require_counterevidence=False,
        )
        bundle = ResearchDecisionOrchestrator().run(request, [StaticProvider([record])])
        findings = [f.code for r in bundle.agent_reports for f in r.findings]
        self.assertIn("UNRESOLVED_CLAIM_CONTRADICTION", findings)
        self.assertEqual(bundle.decision_state, DecisionState.BLOCKED)

    def test_missing_spec_fields_are_engineering_gaps_not_verified(self):
        record = SourceRecord(title="Implementation", uri="repo/source.py", content="implementation",
                              evidence_class=EvidenceClass.IMPLEMENTATION)
        request = ResearchRequest(
            "plan engineering", "Candidate", catalog_coverage_complete=True,
            engineering_spec={"problem_statement": "specified"},
            min_source_records=1, min_primary_sources=1, required_spec_fields=("problem_statement", "rollback_plan"),
        )
        bundle = ResearchDecisionOrchestrator().run(request, [StaticProvider([record])])
        self.assertEqual(bundle.decision_state, DecisionState.ENGINEERING_GAPS)
        self.assertFalse(bundle.promotion_authorized)

    def test_provider_errors_remain_visible_and_block_readiness(self):
        record = SourceRecord(title="Implementation", uri="repo/source.py", content="implementation",
                              evidence_class=EvidenceClass.IMPLEMENTATION)
        request = ResearchRequest(
            "run coverage", "Candidate", catalog_coverage_complete=True,
            engineering_spec=complete_spec(), min_source_records=1, min_primary_sources=1,
        )
        bundle = ResearchDecisionOrchestrator().run(request, [StaticProvider([record], QueryPurpose.COUNTEREVIDENCE)])
        self.assertTrue(any(o.status == "ERROR" for o in bundle.search_outcomes))
        self.assertNotEqual(bundle.decision_state, DecisionState.READY_FOR_ENGINEERING_REVIEW)

    def test_research_run_is_deterministic_for_same_corpus(self):
        record = SourceRecord(title="Implementation", uri="repo/source.py", content="implementation",
                              evidence_class=EvidenceClass.IMPLEMENTATION)
        request = ResearchRequest("same mission", "same candidate", catalog_coverage_complete=True,
                                  engineering_spec=complete_spec(), min_source_records=1, min_primary_sources=1)
        a = ResearchDecisionOrchestrator().run(request, [StaticProvider([record])])
        b = ResearchDecisionOrchestrator().run(request, [StaticProvider([record])])
        self.assertEqual(a.run_id, b.run_id)
        self.assertEqual(a.bundle_sha256, b.bundle_sha256)

    def test_same_uri_and_revision_with_different_content_is_detected(self):
        records = [
            SourceRecord(title="Source A", uri="repo/source.py", revision="r1", content="version a",
                         evidence_class=EvidenceClass.IMPLEMENTATION),
            SourceRecord(title="Source B", uri="repo/source.py", revision="r1", content="version b",
                         evidence_class=EvidenceClass.IMPLEMENTATION),
        ]
        request = ResearchRequest("check lineage", "Source conflict", catalog_coverage_complete=True,
                                  engineering_spec=complete_spec(), min_source_records=1, min_primary_sources=1,
                                  required_spec_fields=("problem_statement",))
        bundle = ResearchDecisionOrchestrator().run(request, [StaticProvider(records)])
        findings = [f.code for r in bundle.agent_reports for f in r.findings]
        self.assertIn("SOURCE_REVISION_CONFLICT", findings)
        self.assertEqual(bundle.decision_state, DecisionState.BLOCKED)


if __name__ == "__main__":
    unittest.main()
