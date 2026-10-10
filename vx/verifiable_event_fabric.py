"""VX Verifiable Event Fabric v1: hash-chained events, Merkle proofs, replay, capabilities.

Security note: hashes detect changes relative to a trusted checkpoint; they do not
authenticate event authors or make storage immutable against an operator who can
rewrite the entire log and its checkpoint. Use signed, externally witnessed roots
for that threat model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Iterable, Mapping, Sequence


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def digest(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


@dataclass(frozen=True)
class LedgerEvent:
    seq: int
    event_id: str
    kind: str
    payload: Mapping[str, Any]
    previous_hash: str
    event_hash: str

    @classmethod
    def create(cls, seq: int, event_id: str, kind: str,
               payload: Mapping[str, Any], previous_hash: str) -> "LedgerEvent":
        if seq < 1 or not event_id.strip() or not kind.strip():
            raise ValueError("INVALID_EVENT_IDENTITY")
        body = {"seq": seq, "event_id": event_id, "kind": kind,
                "payload": payload, "previous_hash": previous_hash}
        return cls(seq, event_id, kind, dict(payload), previous_hash, digest(body))

    def hash_body(self) -> dict[str, Any]:
        return {"seq": self.seq, "event_id": self.event_id, "kind": self.kind,
                "payload": dict(self.payload), "previous_hash": self.previous_hash}


GENESIS_HASH = "0" * 64


def append_event(events: Sequence[LedgerEvent], event_id: str, kind: str,
                 payload: Mapping[str, Any]) -> list[LedgerEvent]:
    if any(e.event_id == event_id for e in events):
        raise ValueError("DUPLICATE_EVENT_ID")
    expected_seq = len(events) + 1
    previous = events[-1].event_hash if events else GENESIS_HASH
    if events and not verify_chain(events)["valid"]:
        raise ValueError("EXISTING_CHAIN_INVALID")
    return [*events, LedgerEvent.create(expected_seq, event_id, kind, payload, previous)]


def verify_chain(events: Sequence[LedgerEvent], trusted_head: str | None = None) -> dict[str, Any]:
    previous = GENESIS_HASH
    seen: set[str] = set()
    for expected_seq, event in enumerate(events, 1):
        if event.seq != expected_seq:
            return {"valid": False, "reason": "SEQUENCE_GAP", "index": expected_seq - 1}
        if event.event_id in seen:
            return {"valid": False, "reason": "DUPLICATE_EVENT_ID", "index": expected_seq - 1}
        if event.previous_hash != previous:
            return {"valid": False, "reason": "PREVIOUS_HASH_MISMATCH", "index": expected_seq - 1}
        if digest(event.hash_body()) != event.event_hash:
            return {"valid": False, "reason": "EVENT_HASH_MISMATCH", "index": expected_seq - 1}
        previous = event.event_hash
        seen.add(event.event_id)
    if trusted_head is not None and previous != trusted_head:
        return {"valid": False, "reason": "TRUSTED_HEAD_MISMATCH", "head": previous}
    return {"valid": True, "count": len(events), "head": previous}


def merkle_root(leaves: Sequence[str]) -> str:
    if not leaves:
        return digest_bytes(b"VX-MERKLE-EMPTY-v1")
    level = [digest_bytes(b"VX-LEAF-v1:" + leaf.encode("ascii")) for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [digest_bytes(b"VX-NODE-v1:" + level[i].encode("ascii") + level[i+1].encode("ascii"))
                 for i in range(0, len(level), 2)]
    return level[0]


def merkle_proof(leaves: Sequence[str], index: int) -> dict[str, Any]:
    if index < 0 or index >= len(leaves):
        raise IndexError("MERKLE_INDEX_OUT_OF_RANGE")
    level = [digest_bytes(b"VX-LEAF-v1:" + leaf.encode("ascii")) for leaf in leaves]
    cursor = index
    path: list[dict[str, str]] = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling = cursor - 1 if cursor % 2 else cursor + 1
        path.append({"side": "left" if cursor % 2 else "right", "hash": level[sibling]})
        level = [digest_bytes(b"VX-NODE-v1:" + level[i].encode("ascii") + level[i+1].encode("ascii"))
                 for i in range(0, len(level), 2)]
        cursor //= 2
    return {"index": index, "leaf": leaves[index], "path": path, "root": level[0], "leaf_count": len(leaves)}


def verify_merkle_proof(proof: Mapping[str, Any], expected_root: str) -> bool:
    try:
        node = digest_bytes(b"VX-LEAF-v1:" + str(proof["leaf"]).encode("ascii"))
        for item in proof["path"]:
            sibling = item["hash"]
            if item["side"] == "left":
                node = digest_bytes(b"VX-NODE-v1:" + sibling.encode("ascii") + node.encode("ascii"))
            elif item["side"] == "right":
                node = digest_bytes(b"VX-NODE-v1:" + node.encode("ascii") + sibling.encode("ascii"))
            else:
                return False
        return node == expected_root == proof["root"]
    except (KeyError, TypeError, ValueError, UnicodeEncodeError):
        return False


def replay(events: Sequence[LedgerEvent], reducer: Callable[[dict[str, Any], LedgerEvent], dict[str, Any]],
           initial_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    check = verify_chain(events)
    if not check["valid"]:
        raise ValueError("REPLAY_REFUSED_INVALID_LEDGER:" + check["reason"])
    state = dict(initial_state or {})
    for event in events:
        state = reducer(state, event)
        if not isinstance(state, dict):
            raise TypeError("REDUCER_MUST_RETURN_DICT")
    return {"state": state, "ledger_head": check["head"], "event_count": check["count"],
            "replay_digest": digest({"state": state, "ledger_head": check["head"], "event_count": check["count"]})}


@dataclass(frozen=True)
class CapabilityGrant:
    principal: str
    capability: str
    resource: str
    expires_at_epoch: int
    policy_version: str
    grant_id: str


def authorize(grant: CapabilityGrant | None, *, principal: str, capability: str,
              resource: str, now_epoch: int, policy_version: str,
              revoked_grant_ids: Iterable[str] = ()) -> dict[str, Any]:
    if grant is None:
        return {"allowed": False, "reason": "NO_GRANT"}
    checks = [
        (grant.principal == principal, "PRINCIPAL_MISMATCH"),
        (grant.capability == capability, "CAPABILITY_MISMATCH"),
        (grant.resource == resource, "RESOURCE_MISMATCH"),
        (now_epoch < grant.expires_at_epoch, "GRANT_EXPIRED"),
        (grant.policy_version == policy_version, "POLICY_VERSION_MISMATCH"),
        (grant.grant_id not in set(revoked_grant_ids), "GRANT_REVOKED"),
    ]
    for ok, reason in checks:
        if not ok:
            return {"allowed": False, "reason": reason, "grant_id": grant.grant_id}
    return {"allowed": True, "reason": "EXACT_CAPABILITY_MATCH", "grant_id": grant.grant_id}
