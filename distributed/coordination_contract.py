"""Distributed coordination contract (no consensus implementation).

This file makes the boundary explicit so the project can depend on stable
types without falsely claiming Raft/consensus/replication is implemented.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

@dataclass(frozen=True)
class NodeIdentity:
    node_id: str
    endpoint: str
    incarnation: int = 0

@dataclass(frozen=True)
class MessageEnvelope:
    message_id: str
    sender: str
    kind: str
    payload_hash: str
    sequence: int

class IdempotencyStore:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def accept(self, key: str) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

def quorum_size(node_count: int) -> int:
    if node_count < 1:
        raise ValueError("NODE_COUNT_REQUIRED")
    return node_count // 2 + 1

def payload_hash(payload: Any) -> str:
    return sha256(repr(payload).encode("utf-8")).hexdigest()

class ConsensusNotImplemented(RuntimeError):
    pass

__all__ = ["NodeIdentity", "MessageEnvelope", "IdempotencyStore", "quorum_size", "payload_hash", "ConsensusNotImplemented"]
