"""Cross-platform federation primitives for independent VAIXLNS mind nodes.

Defines authenticated, replay-resistant protocol primitives and a local peer
registry. Does not claim to provide network transport, consensus, or remote execution.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import hashlib, hmac, json, time
from typing import Any, Iterable

PROTOCOL_VERSION = "1.0"
ALLOWED_KINDS = frozenset({"capability.announce", "task.propose", "task.accept", "task.result", "knowledge.reference", "health.ping"})

def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

@dataclass(frozen=True)
class MindNodeDescriptor:
    node_id: str
    nucleus_version: str
    os_family: str
    endpoint: str | None = None
    capabilities: tuple[str, ...] = ()
    protocol_version: str = PROTOCOL_VERSION
    public_metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("node_id", self.node_id), ("nucleus_version", self.nucleus_version), ("os_family", self.os_family)):
            if not value or not value.strip(): raise ValueError(f"{name.upper()}_REQUIRED")
        if self.protocol_version != PROTOCOL_VERSION: raise ValueError("UNSUPPORTED_PROTOCOL_VERSION")
        if len(set(self.capabilities)) != len(self.capabilities): raise ValueError("DUPLICATE_CAPABILITY")
        if any(not cap or not cap.strip() for cap in self.capabilities): raise ValueError("EMPTY_CAPABILITY")

@dataclass(frozen=True)
class MindEnvelope:
    message_id: str
    sender_node_id: str
    recipient_node_id: str
    kind: str
    created_at: int
    expires_at: int
    payload: dict[str, Any]
    protocol_version: str = PROTOCOL_VERSION
    signature: str = ""
    def unsigned_dict(self) -> dict[str, Any]:
        result = asdict(self); result.pop("signature", None); return result
    def to_dict(self) -> dict[str, Any]: return asdict(self)
    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MindEnvelope": return cls(**value)

class FederationError(ValueError):
    """A message or node failed federation policy."""

class ReplayGuard:
    """Bounded in-memory replay guard; production deployments should persist state."""
    def __init__(self, max_entries: int = 100_000) -> None:
        if max_entries < 1: raise ValueError("MAX_ENTRIES_MUST_BE_POSITIVE")
        self.max_entries = max_entries; self._seen: dict[str, int] = {}
    def accept(self, message_id: str, expires_at: int, now: int) -> bool:
        self._seen = {key: expiry for key, expiry in self._seen.items() if expiry >= now}
        if message_id in self._seen: return False
        if len(self._seen) >= self.max_entries: raise FederationError("REPLAY_GUARD_CAPACITY_REACHED")
        self._seen[message_id] = expires_at; return True

class MindFederation:
    """Policy-enforcing protocol core shared by platform-specific node adapters.

    The node secret must be provisioned out-of-band. HMAC is a bootstrap
    service-to-service profile, not a complete public-key identity system.
    """
    def __init__(self, descriptor: MindNodeDescriptor, node_secret: bytes, *, max_ttl_seconds: int = 300, clock_skew_seconds: int = 30, replay_guard: ReplayGuard | None = None) -> None:
        if len(node_secret) < 32: raise ValueError("NODE_SECRET_MUST_BE_AT_LEAST_32_BYTES")
        if max_ttl_seconds < 1 or clock_skew_seconds < 0: raise ValueError("INVALID_TIME_POLICY")
        self.descriptor = descriptor; self._secret = bytes(node_secret); self.max_ttl_seconds = max_ttl_seconds
        self.clock_skew_seconds = clock_skew_seconds; self.replay_guard = replay_guard or ReplayGuard()
        self.peers: dict[str, MindNodeDescriptor] = {}
    def register_peer(self, peer: MindNodeDescriptor) -> None:
        if peer.node_id == self.descriptor.node_id: raise FederationError("SELF_PEER_NOT_ALLOWED")
        if peer.protocol_version != self.descriptor.protocol_version: raise FederationError("PROTOCOL_VERSION_MISMATCH")
        current = self.peers.get(peer.node_id)
        if current is not None and current != peer: raise FederationError("PEER_IDENTITY_CONFLICT")
        self.peers[peer.node_id] = peer
    def discover(self, required_capabilities: Iterable[str] = ()) -> list[MindNodeDescriptor]:
        required = set(required_capabilities)
        return sorted((p for p in self.peers.values() if required.issubset(set(p.capabilities))), key=lambda p: p.node_id)
    def create_message(self, recipient_node_id: str, kind: str, payload: dict[str, Any], *, ttl_seconds: int = 60, now: int | None = None) -> MindEnvelope:
        if recipient_node_id != "*" and recipient_node_id not in self.peers: raise FederationError("UNKNOWN_RECIPIENT")
        if kind not in ALLOWED_KINDS: raise FederationError("MESSAGE_KIND_NOT_ALLOWED")
        if ttl_seconds < 1 or ttl_seconds > self.max_ttl_seconds: raise FederationError("MESSAGE_TTL_OUT_OF_POLICY")
        timestamp = int(time.time()) if now is None else int(now)
        unique = hashlib.sha256(f"{self.descriptor.node_id}:{timestamp}:{time.time_ns()}".encode()).hexdigest()
        envelope = MindEnvelope(unique, self.descriptor.node_id, recipient_node_id, kind, timestamp, timestamp + ttl_seconds, payload)
        signature = hmac.new(self._secret, _canonical_json(envelope.unsigned_dict()), hashlib.sha256).hexdigest()
        return MindEnvelope(**{**envelope.to_dict(), "signature": signature})
    def verify_message(self, message: MindEnvelope, *, now: int | None = None) -> None:
        timestamp = int(time.time()) if now is None else int(now)
        if message.protocol_version != self.descriptor.protocol_version: raise FederationError("PROTOCOL_VERSION_MISMATCH")
        if message.kind not in ALLOWED_KINDS: raise FederationError("MESSAGE_KIND_NOT_ALLOWED")
        if message.recipient_node_id not in (self.descriptor.node_id, "*"): raise FederationError("WRONG_RECIPIENT")
        if message.sender_node_id not in self.peers: raise FederationError("UNKNOWN_SENDER")
        if message.expires_at < timestamp: raise FederationError("MESSAGE_EXPIRED")
        if message.created_at > timestamp + self.clock_skew_seconds: raise FederationError("MESSAGE_FROM_FUTURE")
        if message.expires_at <= message.created_at: raise FederationError("INVALID_MESSAGE_WINDOW")
        if message.expires_at - message.created_at > self.max_ttl_seconds: raise FederationError("MESSAGE_TTL_OUT_OF_POLICY")
        expected = hmac.new(self._secret, _canonical_json(message.unsigned_dict()), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, message.signature): raise FederationError("MESSAGE_SIGNATURE_INVALID")
        if not self.replay_guard.accept(message.message_id, message.expires_at, timestamp): raise FederationError("MESSAGE_REPLAYED")

__all__ = ["ALLOWED_KINDS", "FederationError", "MindEnvelope", "MindFederation", "MindNodeDescriptor", "PROTOCOL_VERSION", "ReplayGuard"]
