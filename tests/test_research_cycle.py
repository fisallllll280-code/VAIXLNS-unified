import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from innovation_control.research_fabric import (
    DEFAULT_SPEC_FIELDS,
    EvidenceClass,
    SourceRecord,
)
from tools import research_cycle


class FakeGitHubProvider:
    def __init__(self, allowed_repositories, token="", max_sources=8):
        self.allowed_repositories = tuple(allowed_repositories)
        self.provider_id = "fake-pinned-github"
        self.max_sources = max_sources
        self.seen_scopes = []

    def search(self, query, scopes):
        self.seen_scopes.append(tuple(scopes))
        return (
            SourceRecord(
                title="primary implementation",
                uri="https://example.invalid/source-a",
                content="Implementation source with reproducible evidence.",
                evidence_class=EvidenceClass.IMPLEMENTATION,
                revision="a" * 40,
            ),
            SourceRecord(
                title="independent test",
                uri="https://example.invalid/source-b",
                content="Test source with an independent verification record.",
                evidence_class=EvidenceClass.TEST,
                revision="b" * 40,
            ),
        )


class ResearchCycleTests(unittest.TestCase):
    def complete_spec(self):
        return {field: "declared" for field in DEFAULT_SPEC_FIELDS}

    def test_run_cycle_executes_all_lanes_and_never_authorizes_promotion(self):
        with patch.object(research_cycle, "GitHubRepositorySearchProvider", FakeGitHubProvider):
            bundle = research_cycle.run_cycle(
                mission="Assess an engineering candidate with source evidence.",
                candidate_title="Candidate Alpha",
                repositories=("owner/vaixlns",),
                engineering_spec=self.complete_spec(),
                catalog_coverage_complete=True,
            )
        self.assertEqual(bundle["decision_state"], "READY_FOR_ENGINEERING_REVIEW")
        self.assertEqual(len(bundle["queries"]), 7)
        self.assertEqual(len(bundle["search_outcomes"]), 7)
        self.assertEqual(len(bundle["sources"]), 2)
        self.assertFalse(bundle["promotion_authorized"])
        self.assertEqual(len(bundle["bundle_sha256"]), 64)

    def test_run_cycle_is_deterministic_for_identical_evidence(self):
        with patch.object(research_cycle, "GitHubRepositorySearchProvider", FakeGitHubProvider):
            first = research_cycle.run_cycle(
                mission="Assess candidate beta.",
                candidate_title="Candidate Beta",
                repositories=("owner/vaixlns",),
                engineering_spec=self.complete_spec(),
                catalog_coverage_complete=True,
            )
            second = research_cycle.run_cycle(
                mission="Assess candidate beta.",
                candidate_title="Candidate Beta",
                repositories=("owner/vaixlns",),
                engineering_spec=self.complete_spec(),
                catalog_coverage_complete=True,
            )
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["bundle_sha256"], second["bundle_sha256"])

    def test_empty_repository_allowlist_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "EXPLICIT_REPOSITORY_ALLOWLIST_REQUIRED"):
            research_cycle.run_cycle(
                mission="Assess candidate.",
                candidate_title="Candidate",
                repositories=(),
            )

    def test_cli_requires_explicit_network_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "bundle.json")
            result = research_cycle.main([
                "--mission", "Assess candidate.",
                "--candidate-title", "Candidate",
                "--repositories", "owner/repository",
                "--output", output,
            ])
            self.assertEqual(result, 2)
            self.assertFalse(Path(output).exists())

    def test_evidence_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "bundle.json")
            self.assertEqual(research_cycle._write_bundle_create_only(output, {"run_id": "RSH-1"}), output)
            with self.assertRaises(FileExistsError):
                research_cycle._write_bundle_create_only(output, {"run_id": "RSH-2"})
            self.assertIn("RSH-1", Path(output).read_text(encoding="utf-8"))
            self.assertNotIn("RSH-2", Path(output).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
