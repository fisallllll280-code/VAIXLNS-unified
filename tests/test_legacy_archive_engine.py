import json
import unittest

from innovation_control.legacy_archive_engine import (
    SourceDocument, build_extraction_report, extract_atomic_records,
    export_jsonl, propose_similarity_links, search_records,
)


class LegacyArchiveEngineTests(unittest.TestCase):
    def test_source_hash_and_record_ids_are_deterministic(self):
        a = SourceDocument("archive/a.md", "# Alpha\nfirst\n\n# Beta\nsecond")
        b = SourceDocument("archive/a.md", "# Alpha\nfirst\n\n# Beta\nsecond")
        self.assertEqual(a.content_sha256, b.content_sha256)
        self.assertEqual([r.record_uid for r in extract_atomic_records(a)],
                         [r.record_uid for r in extract_atomic_records(b)])

    def test_heading_atomization_preserves_all_chunks(self):
        source = SourceDocument("archive/a.md", "# One\nalpha\n\n# Two\nbeta")
        records = extract_atomic_records(source)
        self.assertEqual(len(records), 2)
        self.assertIn("alpha", records[0].body)
        self.assertIn("beta", records[1].body)

    def test_no_heading_falls_back_to_single_lossless_record(self):
        content = "Legacy prose\nthat must remain intact."
        records = extract_atomic_records(SourceDocument("archive/a.txt", content))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].body, content)

    def test_exact_duplicates_are_reported_not_deleted(self):
        a = SourceDocument("archive/a.md", "# Same\nidentical content")
        b = SourceDocument("archive/b.md", "# Same\nidentical content")
        report = build_extraction_report((a, b))
        self.assertEqual(report.record_count, 2)
        self.assertEqual(len(report.repeated_content_groups), 1)
        self.assertEqual(len(report.repeated_content_groups[0]), 2)

    def test_missing_expected_ids_are_explicit(self):
        report = build_extraction_report(
            (SourceDocument("archive/a.md", "# ID: OLD-1\nrecord"),),
            expected_legacy_ids=("OLD-1", "OLD-2"),
        )
        self.assertEqual(report.missing_legacy_ids, ("OLD-2",))
        self.assertIn("EXPECTED_LEGACY_IDS_NOT_FOUND", report.warnings)

    def test_similarity_links_are_review_only(self):
        records = extract_atomic_records(SourceDocument(
            "archive/a.md", "# Alpha Engine\nsearch evidence archive\n\n"
                            "# Alpha Engine v2\nsearch evidence archive"
        ))
        links = propose_similarity_links(records, threshold=0.5)
        self.assertTrue(links)
        self.assertTrue(all(link.action == "HUMAN_REVIEW_ONLY" for link in links))

    def test_search_is_ranked_and_deterministic(self):
        records = extract_atomic_records(SourceDocument(
            "archive/a.md", "# Semantic Search\nsearch index evidence\n\n"
                            "# Financial Ledger\ncapital record"
        ))
        first = search_records(records, "semantic search", limit=5)
        second = search_records(records, "semantic search", limit=5)
        self.assertEqual(first, second)
        self.assertEqual(first[0][1].title, "Semantic Search")

    def test_jsonl_is_parseable(self):
        records = extract_atomic_records(SourceDocument("archive/a.md", "# Alpha\nbody"))
        rows = export_jsonl(records).splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0])["title"], "Alpha")

    def test_invalid_threshold_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "THRESHOLD_OUT_OF_RANGE"):
            propose_similarity_links((), threshold=1.1)


if __name__ == "__main__":
    unittest.main()
