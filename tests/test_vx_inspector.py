"""Unit tests for the zero-budget, read-only VX inspector."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.vx_inspector import inspect, _safe_file


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "integration").mkdir()
        (self.root / "integration/federation_registry.json").write_text(
            json.dumps({"repositories": [{"repository": "org/VX-runtime",
                                         "system": "VX", "status": "PARTIAL"}]}),
            encoding="utf-8")
        (self.root / "project.genome").write_bytes(b"genome-baseline")

    def tearDown(self):
        self.tmp.cleanup()

    def test_observation_does_not_promote_or_execute(self):
        result = inspect(self.root, env={"OPENAI_API_KEY": "test-key",
                                         "VX_OPENAI_MODEL": "operator-selected"})
        self.assertEqual(result["g0"], "NOT_CERTIFIED")
        self.assertEqual(result["release_decision"], "HOLD")
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["external_budget_sar"], 0)
        self.assertEqual([x["id"] for g in result["tests"] for x in g["tests"]],
                         ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08",
                          "T09", "T10", "T15", "T11", "T12", "T13", "T14"])
        self.assertTrue(all(t["status"] == "NOT_RUN" for g in result["tests"] for t in g["tests"]))
        self.assertEqual(result["federation"]["state"], "PARSED")
        self.assertTrue(result["models"][0]["credentials_present"])
        self.assertEqual(result["models"][0]["connection"], "NOT_TESTED")
        self.assertNotIn("test-key", json.dumps(result))

    def test_file_hash_and_missing_protected_reference(self):
        a = inspect(self.root, env={})
        self.assertEqual(a["protected"][0]["state"], "OBSERVED")
        self.assertEqual(a["protected"][1]["state"], "MISSING_OR_UNSAFE")
        (self.root / "project.genome").write_bytes(b"changed")
        b = inspect(self.root, env={})
        self.assertNotEqual(a["protected"][0]["sha256"], b["protected"][0]["sha256"])

    def test_symlink_outside_root_is_not_read(self):
        with tempfile.TemporaryDirectory() as outer:
            secret = Path(outer) / "outside.txt"
            secret.write_text("private")
            (self.root / "config").symlink_to(Path(outer), target_is_directory=True)
            self.assertIsNone(_safe_file(self.root, "config/outside.txt"))

    def test_invalid_registry_is_not_claimed(self):
        (self.root / "integration/federation_registry.json").write_text("{broken")
        self.assertEqual(inspect(self.root, env={})["federation"]["state"], "INVALID")

    def test_read_only_preserves_original_bytes(self):
        source = self.root / "project.genome"
        before = source.read_bytes()
        inspect(self.root, env={})
        self.assertEqual(before, source.read_bytes())


if __name__ == "__main__":
    unittest.main()
