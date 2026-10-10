import unittest
from dataclasses import replace

from vx.verifiable_event_fabric import (
    CapabilityGrant, append_event, authorize, merkle_proof, merkle_root,
    replay, verify_chain, verify_merkle_proof,
)


def reducer(state, event):
    state = dict(state)
    if event.kind == "set":
        state[event.payload["key"]] = event.payload["value"]
    return state


class VerifiableEventFabricTests(unittest.TestCase):
    def ledger(self):
        events = []
        events = append_event(events, "e1", "set", {"key": "x", "value": 1})
        events = append_event(events, "e2", "set", {"key": "y", "value": 2})
        events = append_event(events, "e3", "set", {"key": "x", "value": 3})
        return events

    def test_chain_verifies_and_trusted_head_is_checked(self):
        events = self.ledger()
        self.assertTrue(verify_chain(events)["valid"])
        self.assertFalse(verify_chain(events, trusted_head="f" * 64)["valid"])

    def test_payload_tampering_is_detected(self):
        events = self.ledger()
        altered = [events[0], replace(events[1], payload={"y": 999}), events[2]]
        self.assertEqual(verify_chain(altered)["reason"], "EVENT_HASH_MISMATCH")

    def test_reordering_is_detected(self):
        self.assertFalse(verify_chain(list(reversed(self.ledger())))["valid"])

    def test_duplicate_event_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EVENT_ID"):
            append_event(self.ledger(), "e1", "set", {"key": "x", "value": 4})

    def test_replay_is_deterministic(self):
        events = self.ledger()
        a, b = replay(events, reducer), replay(events, reducer)
        self.assertEqual(a, b)
        self.assertEqual(a["state"], {"x": 3, "y": 2})

    def test_replay_refuses_tampered_history(self):
        events = self.ledger()
        altered = [events[0], replace(events[1], payload={"y": 999}), events[2]]
        with self.assertRaisesRegex(ValueError, "REPLAY_REFUSED_INVALID_LEDGER"):
            replay(altered, reducer)

    def test_merkle_inclusion_proofs_verify(self):
        leaves = [e.event_hash for e in self.ledger()]
        root = merkle_root(leaves)
        for index in range(len(leaves)):
            self.assertTrue(verify_merkle_proof(merkle_proof(leaves, index), root))

    def test_merkle_proof_rejects_wrong_root(self):
        leaves = [e.event_hash for e in self.ledger()]
        self.assertFalse(verify_merkle_proof(merkle_proof(leaves, 0), "0" * 64))

    def test_capability_is_exact_and_resource_scoped(self):
        grant = CapabilityGrant("agent-1", "READ_REPO", "repo:VX", 500, "p1", "g1")
        self.assertTrue(authorize(grant, principal="agent-1", capability="READ_REPO",
                                  resource="repo:VX", now_epoch=100, policy_version="p1")["allowed"])
        self.assertEqual(authorize(grant, principal="agent-1", capability="WRITE_REPO",
                                   resource="repo:VX", now_epoch=100, policy_version="p1")["reason"],
                         "CAPABILITY_MISMATCH")

    def test_expired_revoked_and_stale_policy_grants_fail_closed(self):
        grant = CapabilityGrant("agent-1", "READ_REPO", "repo:VX", 100, "p1", "g1")
        base = dict(principal="agent-1", capability="READ_REPO", resource="repo:VX",
                    now_epoch=100, policy_version="p1")
        self.assertEqual(authorize(grant, **base)["reason"], "GRANT_EXPIRED")
        self.assertEqual(authorize(grant, **(base | {"now_epoch": 50, "revoked_grant_ids": ["g1"]}))["reason"],
                         "GRANT_REVOKED")
        self.assertEqual(authorize(grant, **(base | {"now_epoch": 50, "policy_version": "p2"}))["reason"],
                         "POLICY_VERSION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
