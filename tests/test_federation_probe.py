"""Safety tests for the read-only federation health probe."""
from __future__ import annotations

import io
import json
import unittest
from urllib.error import HTTPError, URLError

from operations.federation_probe import build_report, probe_target


def target(**overrides):
    value = {
        "system_id": "fixture",
        "url_env": "FIXTURE_URL",
        "enabled_env": "FIXTURE_ENABLED",
        "identity_field": "service",
        "expected_identity": "fixture-service",
        "health_field": "ok",
        "healthy_value": True,
    }
    value.update(overrides)
    return value


class FakeResponse:
    def __init__(self, payload, status=200):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.status = status
        self.closed = False

    def getcode(self):
        return self.status

    def read(self, amount=-1):
        return self.body[:amount] if amount >= 0 else self.body

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class FederationProbeTests(unittest.TestCase):
    def test_missing_endpoint_never_performs_network_io(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": True}))
        result = probe_target(target(), env={"FIXTURE_ENABLED": "true"}, opener=opener)
        self.assertEqual(result["state"], "MISSING")
        self.assertEqual(result["reason"], "ENDPOINT_NOT_CONFIGURED")
        self.assertEqual(opener.calls, [])

    def test_probe_must_be_explicitly_enabled(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": True}))
        result = probe_target(target(), env={"FIXTURE_URL": "https://example.test/health"}, opener=opener)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "PROBE_NOT_ENABLED")
        self.assertEqual(opener.calls, [])

    def test_remote_cleartext_http_is_rejected(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": True}))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "http://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "ENDPOINT_URL_INVALID")
        self.assertEqual(opener.calls, [])

    def test_healthy_response_requires_matching_identity_and_health(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": True}))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "HEALTHY")
        self.assertTrue(result["identity_match"])
        self.assertTrue(result["health_match"])
        self.assertEqual(opener.calls[0][0].get_method(), "GET")

    def test_loopback_http_is_permitted_for_local_fixture(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": True}))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "yes", "FIXTURE_URL": "http://127.0.0.1:8000/health"
        }, opener=opener)
        self.assertEqual(result["state"], "HEALTHY")

    def test_service_identity_mismatch_blocks_response(self):
        opener = FakeOpener(FakeResponse({"service": "other-service", "ok": True}))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "SERVICE_IDENTITY_MISMATCH")

    def test_unhealthy_signal_is_degraded_not_healthy(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": False}))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "DEGRADED")
        self.assertEqual(result["reason"], "HEALTH_SIGNAL_NOT_READY")

    def test_non_boolean_true_does_not_pass_health_gate(self):
        opener = FakeOpener(FakeResponse({"service": "fixture-service", "ok": 1}))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "DEGRADED")

    def test_invalid_json_is_unknown(self):
        opener = FakeOpener(FakeResponse(b"not-json"))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "HEALTH_RESPONSE_INVALID_JSON")

    def test_oversized_response_is_unknown(self):
        opener = FakeOpener(FakeResponse(b"x" * 20))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener, max_response_bytes=10)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "RESPONSE_TOO_LARGE")

    def test_redirect_is_refused_and_never_followed(self):
        opener = FakeOpener(error=HTTPError("https://example.test/health", 302, "redirect", {}, io.BytesIO(b"")))
        result = probe_target(target(), env={
            "FIXTURE_ENABLED": "true", "FIXTURE_URL": "https://example.test/health"
        }, opener=opener)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "REDIRECT_REFUSED")
        self.assertEqual(len(opener.calls), 1)

    def test_vlns_expected_identity_must_be_pinned_before_request(self):
        t = target(
            url_env=None,
            base_url_env="VLNS_SERVER_URL",
            path_env="VLNS_SERVER_HEALTH_PATH",
            default_path="/health",
            expected_identity=None,
            expected_identity_env="VLNS_SERVER_EXPECTED_SERVICE",
        )
        opener = FakeOpener(FakeResponse({"service": "vlns-control", "ok": True}))
        result = probe_target(t, env={
            "FIXTURE_ENABLED": "true",
            "VLNS_SERVER_URL": "https://vlns.example.test",
        }, opener=opener)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "EXPECTED_SERVICE_IDENTITY_NOT_PINNED")
        self.assertEqual(opener.calls, [])

    def test_tokens_and_endpoint_urls_are_not_echoed(self):
        secret = "do-not-log-this-token"
        opener = FakeOpener(error=URLError(secret))
        result = probe_target(target(token_env="FIXTURE_TOKEN"), env={
            "FIXTURE_ENABLED": "true",
            "FIXTURE_URL": "https://private.example.test/health",
            "FIXTURE_TOKEN": secret,
        }, opener=opener)
        serialized = json.dumps(result)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("private.example.test", serialized)
        self.assertEqual(result["state"], "UNKNOWN")

    def test_default_federation_report_is_fail_closed_without_endpoints(self):
        policy = {
            "schema_version": "1.0",
            "timeout_seconds": 3,
            "max_response_bytes": 65536,
            "targets": [
                target(),
                target(system_id="second", url_env="SECOND_URL", enabled_env="SECOND_ENABLED"),
            ],
        }
        report = build_report(policy, env={})
        self.assertEqual(report["overall"], "BLOCKED")
        self.assertEqual(report["healthy_count"], 0)
        self.assertEqual([x["state"] for x in report["targets"]], ["MISSING", "MISSING"])
        self.assertEqual(len(report["report_sha256"]), 64)

    def test_repository_policy_declares_all_five_targets_without_network_defaults(self):
        from operations.federation_probe import DEFAULT_POLICY
        policy = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))
        report = build_report(policy, env={})
        self.assertEqual(
            [item["system_id"] for item in report["targets"]],
            ["VAIXLNS", "VX-runtime", "VLNS", "NEXENT", "NEXNET"],
        )
        self.assertEqual([item["state"] for item in report["targets"]], ["MISSING"] * 5)
        self.assertEqual(report["overall"], "BLOCKED")

    def test_url_query_credentials_and_path_traversal_are_rejected(self):
        env = {"FIXTURE_ENABLED": "true"}
        cases = [
            "https://user:password@example.test/health",
            "https://example.test/health?token=secret",
            "https://example.test/../admin",
            "https://example.test/%2e%2e/admin",
        ]
        for url in cases:
            with self.subTest(url=url):
                result = probe_target(target(), env={**env, "FIXTURE_URL": url}, opener=FakeOpener())
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(result["reason"], "ENDPOINT_URL_INVALID")
