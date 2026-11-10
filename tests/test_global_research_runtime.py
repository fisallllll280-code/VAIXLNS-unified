import unittest

from innovation_control.research_fabric import EvidenceClass, SourceRecord
from tools.global_research_runtime import (
    ResearchCycleConfig,
    build_research_request,
    catalog_from_payload,
    require_network_authorization,
    run_research_cycle,
)


class StaticProvider:
    provider_id = "static-research-test"

    def search(self, query, scopes):
        return (
            SourceRecord(
                title="Primary implementation",
                uri="https://example.invalid/repo/implementation.py",
                content="Read-only research implementation with deterministic evidence hashes.",
                evidence_class=EvidenceClass.IMPLEMENTATION,
                revision="a" * 40,
            ),
            SourceRecord(
                title="Test evidence",
                uri="https://example.invalid/repo/test.py",
                content="Independent tests preserve failure evidence and block promotion.",
                evidence_class=EvidenceClass.TEST,
                revision="b" * 40,
            ),
        )


class GlobalResearchRuntimeTests(unittest.TestCase):
    def test_network_gate_fails_closed_without_both_explicit_flags(self):
        with self.assertRaisesRegex(PermissionError, "EXECUTION_NOT_REQUESTED"):
            require_network_authorization(False, True)
        with self.assertRaisesRegex(PermissionError, "NETWORK_GATE_DISABLED"):
            require_network_authorization(True, False)
        require_network_authorization(True, True)

    def test_repository_allowlist_is_required_and_unique(self):
        with self.assertRaisesRegex(ValueError, "EXPLICIT_REPOSITORY_ALLOWLIST_REQUIRED"):
            ResearchCycleConfig("research", repositories=())
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REPOSITORY_SCOPE"):
            ResearchCycleConfig("research", repositories=("owner/repo", "owner/repo"))
        with self.assertRaisesRegex(ValueError, "INVALID_REPOSITORY_SCOPE"):
            ResearchCycleConfig("research", repositories=("../secret",))

    def test_catalog_parser_preserves_canonical_identity_and_aliases(self):
        entries = catalog_from_payload({
            "items": [{
                "canonical_id": "INNOV-001",
                "name": "Proof Fabric",
                "description": "Evidence-linked verification",
                "native_ids": ["I-001", "PF"],
            }]
        })
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].innovation_id, "INNOV-001")
        self.assertEqual(entries[0].aliases, ("I-001", "PF"))

    def test_catalog_conflicting_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "CATALOG_ID_CONFLICT"):
            catalog_from_payload([
                {"canonical_id": "X-1", "name": "First"},
                {"canonical_id": "X-1", "name": "Different"},
            ])

    def test_request_never_claims_catalog_completeness(self):
        request = build_research_request(ResearchCycleConfig("find gaps"))
        self.assertFalse(request.catalog_coverage_complete)
        self.assertTrue(request.require_counterevidence)
        self.assertEqual(len(request.scopes), 3)

    def test_cycle_is_deterministic_read_only_and_never_promotes(self):
        config = ResearchCycleConfig("inspect engineering evidence")
        first = run_research_cycle(config, (StaticProvider(),))
        second = run_research_cycle(config, (StaticProvider(),))
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["sources"], second["sources"])
        self.assertEqual(first["cycle_metrics"]["query_lanes"], 7)
        self.assertEqual(first["cycle_metrics"]["unique_sources"], 2)
        self.assertTrue(first["cycle_control"]["read_only"])
        self.assertFalse(first["cycle_control"]["canonical_mutation"])
        self.assertFalse(first["cycle_control"]["promotion_authorized"])
        self.assertFalse(first["promotion_authorized"])
        self.assertFalse(first["canonical_eligible"])


if __name__ == "__main__":
    unittest.main()
