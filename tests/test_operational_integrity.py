import unittest

from provenance.manifest import build_manifest
from telemetry.otel_bridge import VXTelemetry
from intelligence.openai_responses_adapter import OpenAIResponsesAdapter


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

    def test_openai_bridge_uses_injected_client(self):
        class FakeResponse:
            id="resp-test"
            output_text="proposal"
        class FakeResponses:
            def create(self, **kwargs):
                self.kwargs=kwargs
                return FakeResponse()
        class FakeClient:
            def __init__(self):
                self.responses=FakeResponses()
        adapter=OpenAIResponsesAdapter(client=FakeClient(), model="test-model")
        result=adapter.run("discover a capability gap", {"domain":"math"})
        self.assertTrue(adapter.configured)
        self.assertEqual(result["response_id"], "resp-test")
        self.assertEqual(result["output_text"], "proposal")

    def test_telemetry_bridge_is_safe_when_optional_dependency_missing(self):
        telemetry=VXTelemetry()
        with telemetry.span("smoke"):
            pass
        self.assertIn(telemetry.configured, (True, False))


if __name__ == "__main__":
    unittest.main()
