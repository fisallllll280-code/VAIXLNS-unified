import unittest
from copy import deepcopy

from federation.continuity_manifest import (
    ManifestValidationError,
    load_manifest,
    validate_manifest,
)


class VXVLNSContinuityManifestTests(unittest.TestCase):
    def test_repository_manifest_is_valid(self):
        manifest = load_manifest()
        self.assertEqual(manifest["manifest_id"], "VAIXLNS-VX-VLNS-FEDERATION-V1")
        self.assertGreaterEqual(len(manifest["repositories"]), 5)
        self.assertIn("OIF is operational assurance, not consensus.", manifest["invariants"])

    def test_duplicate_repository_ids_are_rejected(self):
        manifest = load_manifest()
        invalid = deepcopy(manifest)
        invalid["repositories"][1]["id"] = invalid["repositories"][0]["id"]
        with self.assertRaisesRegex(ManifestValidationError, "duplicate repository id"):
            validate_manifest(invalid)

    def test_unknown_evidence_state_is_rejected(self):
        manifest = load_manifest()
        invalid = deepcopy(manifest)
        invalid["repositories"][0]["evidence_state"] = "PRODUCTION_READY"
        with self.assertRaisesRegex(ManifestValidationError, "invalid evidence state"):
            validate_manifest(invalid)

    def test_non_https_repository_url_is_rejected(self):
        manifest = load_manifest()
        invalid = deepcopy(manifest)
        invalid["repositories"][0]["url"] = "http://github.com/fisallllll280-code/VAIXLNS"
        with self.assertRaisesRegex(ManifestValidationError, "HTTPS GitHub URL"):
            validate_manifest(invalid)

    def test_empty_canonical_flow_is_rejected(self):
        manifest = load_manifest()
        invalid = deepcopy(manifest)
        invalid["canonical_flow"] = []
        with self.assertRaisesRegex(ManifestValidationError, "canonical_flow"):
            validate_manifest(invalid)


if __name__ == "__main__":
    unittest.main()
