import unittest
from dataclasses import replace
from distributed.mind_federation import FederationError, MindFederation, MindNodeDescriptor

SECRET = b"v" * 32
def descriptor(node_id, capabilities=()):
    return MindNodeDescriptor(node_id=node_id, nucleus_version="1.0", os_family="test", capabilities=tuple(capabilities))

class MindFederationTests(unittest.TestCase):
    def setUp(self):
        self.a = MindFederation(descriptor("node-a", ["research"]), SECRET)
        self.b = MindFederation(descriptor("node-b", ["verification"]), SECRET)
        self.a.register_peer(self.b.descriptor); self.b.register_peer(self.a.descriptor)
    def test_capability_discovery_is_deterministic(self):
        self.a.register_peer(descriptor("node-c", ["research", "simulation"]))
        self.assertEqual([p.node_id for p in self.a.discover(["research"])], ["node-c"])
    def test_signed_message_verifies_once(self):
        message = self.a.create_message("node-b", "task.propose", {"task_id": "t-1"}, now=100, ttl_seconds=30)
        self.b.verify_message(message, now=101)
        with self.assertRaisesRegex(FederationError, "MESSAGE_REPLAYED"): self.b.verify_message(message, now=101)
    def test_tampered_payload_is_rejected(self):
        message = self.a.create_message("node-b", "task.propose", {"task_id": "t-1"}, now=100)
        with self.assertRaisesRegex(FederationError, "MESSAGE_SIGNATURE_INVALID"): self.b.verify_message(replace(message, payload={"task_id": "tampered"}), now=101)
    def test_unknown_sender_is_rejected(self):
        rogue = MindFederation(descriptor("rogue"), SECRET); message = rogue.create_message("*", "health.ping", {}, now=100)
        with self.assertRaisesRegex(FederationError, "UNKNOWN_SENDER"): self.b.verify_message(message, now=101)
    def test_ttl_policy_is_enforced(self):
        with self.assertRaisesRegex(FederationError, "MESSAGE_TTL_OUT_OF_POLICY"): self.a.create_message("node-b", "health.ping", {}, ttl_seconds=301, now=100)
    def test_unknown_recipient_is_rejected(self):
        with self.assertRaisesRegex(FederationError, "UNKNOWN_RECIPIENT"): self.a.create_message("node-x", "health.ping", {}, now=100)
    def test_short_secret_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NODE_SECRET_MUST_BE_AT_LEAST_32_BYTES"): MindFederation(descriptor("weak"), b"short")
    def test_wrong_recipient_is_rejected(self):
        self.a.register_peer(descriptor("node-c")); message = self.a.create_message("node-c", "health.ping", {}, now=100)
        with self.assertRaisesRegex(FederationError, "WRONG_RECIPIENT"): self.b.verify_message(message, now=101)

if __name__ == "__main__": unittest.main()
