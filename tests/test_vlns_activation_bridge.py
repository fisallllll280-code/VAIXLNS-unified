from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from infra.vlns_server_client import ServerConfig, VLNSServerClient
from vlns.activation import (
    ActivationError,
    ActivationPolicy,
    ActivationRequest,
    VLNSActivationBridge,
    envelope_hash,
    prepare_activation,
    verify_activation_envelope,
)


KEY = b"unit-test-signing-key-with-32-bytes-minimum"
POLICY = ActivationPolicy(
    allowed_providers=frozenset({"ollama", "openai-compatible"}),
    allowed_capabilities=frozenset({"reasoning", "research", "engineering", "verification"}),
    allowed_tools=frozenset({"repository.read", "web.search"}),
)


def request(**changes):
    values = {
        "model_id": "qwen3:8b",
        "provider": "ollama",
        "model_version": "sha256:model-revision-001",
        "role": "research_mind",
        "capability_profile": ("reasoning", "research"),
        "context_payload": {"task": "inspect architecture", "input_refs": ["repo://VAIXLNS"]},
        "tool_profile": ("repository.read",),
        "requested_permissions": ("read", "propose"),
        "constraints": ("no_canonical_mutation", "no_unreviewed_execution"),
        "provenance": {
            "task_id": "task-001",
            "source_id": "repo://VAIXLNS",
            "source_digest": "a" * 64,
        },
    }
    values.update(changes)
    return ActivationRequest(**values)


class FakeClient:
    def __init__(self, configured=True, response=None, event_response=None):
        self.configured = configured
        self.response = response
        self.event_response = event_response or {"ok": True, "status_code": 200, "data": {"recorded": True}}
        self.activated_envelopes = []
        self.events = []

    def activate_model(self, envelope):
        self.activated_envelopes.append(dict(envelope))
        if self.response is not None:
            return self.response
        return {
            "ok": True,
            "status_code": 200,
            "data": {
                "status": "ACTIVATED",
                "activation_id": envelope["activation_id"],
                "envelope_hash": envelope_hash(envelope),
            },
        }

    def emit_event(self, event):
        self.events.append(dict(event))
        return self.event_response


class VlnsActivationTests(unittest.TestCase):
    def test_envelope_is_deterministic_and_does_not_leak_context(self):
        first = prepare_activation(request(), POLICY, KEY)
        second = prepare_activation(request(), POLICY, KEY)
        self.assertEqual(first, second)
        self.assertEqual(first["context_hash"], second["context_hash"])
        self.assertNotIn("inspect architecture", json.dumps(first))
        self.assertTrue(verify_activation_envelope(first, KEY))

    def test_tampering_is_detected(self):
        envelope = prepare_activation(request(), POLICY, KEY)
        envelope["model_version"] = "mutable-other-version"
        self.assertFalse(verify_activation_envelope(envelope, KEY))

    def test_signing_key_must_be_strong_enough(self):
        with self.assertRaisesRegex(ActivationError, "SIGNING_KEY"):
            prepare_activation(request(), POLICY, b"short")

    def test_unallowlisted_provider_is_rejected(self):
        with self.assertRaisesRegex(ActivationError, "PROVIDER_NOT_ALLOWLISTED"):
            prepare_activation(request(provider="unknown"), POLICY, KEY)

    def test_unallowlisted_capability_is_rejected(self):
        with self.assertRaisesRegex(ActivationError, "CAPABILITY_NOT_ALLOWLISTED"):
            prepare_activation(request(capability_profile=("root_shell",)), POLICY, KEY)

    def test_unallowlisted_tool_is_rejected(self):
        with self.assertRaisesRegex(ActivationError, "TOOL_NOT_ALLOWLISTED"):
            prepare_activation(request(tool_profile=("filesystem.delete",)), POLICY, KEY)

    def test_role_cannot_escalate_permissions(self):
        with self.assertRaisesRegex(ActivationError, "ROLE_PERMISSION_ESCALATION"):
            prepare_activation(request(requested_permissions=("read", "execute")), POLICY, KEY)

    def test_non_delegable_authority_cannot_be_granted_to_model_role(self):
        with self.assertRaisesRegex(ActivationError, "NON_DELEGABLE"):
            ActivationPolicy(
                allowed_providers=frozenset({"ollama"}),
                allowed_capabilities=frozenset({"research"}),
                role_permissions={"research_mind": frozenset({"read", "canonical_write"})},
            )

    def test_unconfigured_server_never_claims_activation(self):
        client = FakeClient(configured=False)
        result = VLNSActivationBridge(client, POLICY, KEY).activate(request())
        self.assertEqual(result.status, "PREPARED_NOT_DISPATCHED")
        self.assertFalse(result.activated)
        self.assertFalse(result.evidence_recorded)
        self.assertEqual(client.activated_envelopes, [])

    def test_valid_remote_receipt_and_evidence_event_complete_bridge(self):
        client = FakeClient()
        result = VLNSActivationBridge(client, POLICY, KEY).activate(request())
        self.assertEqual(result.status, "ACTIVATED_AND_RECORDED")
        self.assertTrue(result.activated)
        self.assertTrue(result.evidence_recorded)
        self.assertEqual(client.events[0]["activation_id"], result.activation_id)
        self.assertEqual(client.events[0]["envelope_hash"], result.envelope_hash)

    def test_receipt_for_other_envelope_is_rejected(self):
        client = FakeClient(response={
            "ok": True,
            "data": {"status": "ACTIVATED", "activation_id": "VLNS-ACT-else", "envelope_hash": "b" * 64},
        })
        result = VLNSActivationBridge(client, POLICY, KEY).activate(request())
        self.assertEqual(result.status, "RECEIPT_INVALID")
        self.assertFalse(result.activated)
        self.assertEqual(client.events, [])

    def test_remote_rejection_is_not_overridden(self):
        client = FakeClient(response={"ok": True, "data": {"status": "QUARANTINED", "reason": "policy"}})
        result = VLNSActivationBridge(client, POLICY, KEY).activate(request())
        self.assertEqual(result.status, "REMOTE_REJECTED")
        self.assertFalse(result.activated)
        self.assertEqual(client.events, [])

    def test_activation_without_durable_event_is_not_full_success(self):
        client = FakeClient(event_response={"ok": False, "status": "CONNECTION_ERROR"})
        result = VLNSActivationBridge(client, POLICY, KEY).activate(request())
        self.assertEqual(result.status, "ACTIVATED_EVIDENCE_PENDING")
        self.assertTrue(result.activated)
        self.assertFalse(result.evidence_recorded)

    def test_server_client_posts_activation_to_configured_path(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b'{"status":"ACTIVATED"}'

        client = VLNSServerClient(ServerConfig(
            server_id="VLNS-test",
            base_url="https://vlns.example",
            token="test-token",
            enabled=True,
            activation_path="/contract/activations",
        ))
        with patch("infra.vlns_server_client.urlopen", return_value=Response()) as mocked:
            result = client.activate_model({"activation_id": "VLNS-ACT-test"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["status"], "ACTIVATED")
        self.assertEqual(mocked.call_args.args[0].full_url, "https://vlns.example/contract/activations")
        self.assertEqual(mocked.call_args.args[0].get_header("Authorization"), "Bearer test-token")


if __name__ == "__main__":
    unittest.main()
