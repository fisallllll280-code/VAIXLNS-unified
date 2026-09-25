import unittest

from provenance.manifest import build_manifest
from telemetry.otel_bridge import VXTelemetry


class OperationalIntegrityTests(unittest.TestCase):
    def test_provenance_manifest_has_digest_and_source(self):
        manifest=build_manifest(
            "fisallllll280-code/VAIXLNS-unified",
            "abc123",
            "vx-invention-engine",
            ["repo:file-a", "repo:file-b"],
            b"artifact",
        )
        self.assertTrue(manifest.artifact_digest.startswith("sha256:"))
        self.assertEqual(manifest.predicate_type, "https://slsa.dev/provenance/v1")

    def test_telemetry_bridge_is_safe_when_optional_dependency_missing(self):
        telemetry=VXTelemetry()
        with telemetry.span("smoke"):
            pass
        self.assertIn(telemetry.configured, (True, False))


if __name__ == "__main__":
    unittest.main()
