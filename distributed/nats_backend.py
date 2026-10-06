"""Optional NATS JetStream backend for durable events and application leases.

The local runtime remains usable without NATS. In distributed mode, durable
streams, replication and cluster quorum are delegated to NATS JetStream.
VAIXLNS does not reimplement Raft inside the application.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping


@dataclass(frozen=True)
class LeaseClaim:
    acquired: bool
    node_id: str
    revision: int | None = None
    expires_at: int | None = None


class NatsJetStreamBackend:
    def __init__(
        self,
        servers: str | list[str],
        *,
        stream_name: str = "VLNS_EVENTS",
        event_subject: str = "vlns.events",
        lease_bucket: str = "VLNS_LEASES",
        replicas: int = 3,
    ) -> None:
        if replicas < 1:
            raise ValueError("REPLICAS_MUST_BE_POSITIVE")
        self.servers = servers
        self.stream_name = stream_name
        self.event_subject = event_subject
        self.lease_bucket = lease_bucket
        self.replicas = replicas
        self._nc = None
        self._js = None
        self._kv = None

    async def connect(self) -> None:
        try:
            import nats  # type: ignore
        except ImportError as exc:
            raise RuntimeError("NATS_OPTIONAL_DEPENDENCY_MISSING") from exc

        self._nc = await nats.connect(self.servers)
        self._js = self._nc.jetstream()
        try:
            await self._js.add_stream(
                name=self.stream_name,
                subjects=[self.event_subject],
                storage="file",
                replicas=self.replicas,
            )
        except Exception as exc:
            if "already" not in str(exc).lower():
                raise
        try:
            self._kv = await self._js.create_key_value(bucket=self.lease_bucket)
        except Exception as exc:
            if "already" not in str(exc).lower():
                raise
            self._kv = await self._js.key_value(self.lease_bucket)

    @property
    def connected(self) -> bool:
        return self._js is not None and self._kv is not None

    async def publish_event(self, event_id: str, event: Mapping[str, Any]) -> int | None:
        if self._js is None:
            raise RuntimeError("NATS_NOT_CONNECTED")
        ack = await self._js.publish(
            self.event_subject,
            json.dumps(dict(event), sort_keys=True, ensure_ascii=False).encode("utf-8"),
            headers={"Nats-Msg-Id": event_id},
        )
        return getattr(ack, "seq", getattr(ack, "sequence", None))

    async def claim_leader(
        self,
        *,
        key: str,
        node_id: str,
        ttl_seconds: int = 30,
    ) -> LeaseClaim:
        if self._kv is None:
            raise RuntimeError("NATS_NOT_CONNECTED")
        if ttl_seconds < 1:
            raise ValueError("LEASE_TTL_MUST_BE_POSITIVE")

        now = int(time.time())
        expires_at = now + ttl_seconds
        value = json.dumps(
            {"node_id": node_id, "expires_at": expires_at},
            sort_keys=True,
        ).encode("utf-8")

        try:
            revision = await self._kv.create(key, value)
            return LeaseClaim(True, node_id, revision, expires_at)
        except Exception:
            try:
                entry = await self._kv.get(key)
            except Exception:
                return LeaseClaim(False, node_id)

            try:
                current = json.loads((entry.value or b"{}").decode("utf-8"))
            except (TypeError, ValueError, AttributeError):
                current = {}

            if int(current.get("expires_at", 0)) > now and current.get("node_id") != node_id:
                return LeaseClaim(False, node_id, entry.revision, int(current["expires_at"]))

            try:
                revision = await self._kv.update(key, value, last=entry.revision)
            except Exception:
                return LeaseClaim(False, node_id, entry.revision, int(current.get("expires_at", 0) or 0))
            return LeaseClaim(True, node_id, revision, expires_at)

    async def renew_leader(
        self,
        *,
        key: str,
        node_id: str,
        revision: int,
        ttl_seconds: int = 30,
    ) -> LeaseClaim:
        if self._kv is None:
            raise RuntimeError("NATS_NOT_CONNECTED")
        entry = await self._kv.get(key)
        try:
            current = json.loads((entry.value or b"{}").decode("utf-8"))
        except (TypeError, ValueError, AttributeError):
            current = {}

        if current.get("node_id") != node_id or entry.revision != revision:
            return LeaseClaim(False, node_id, entry.revision, int(current.get("expires_at", 0) or 0))

        expires_at = int(time.time()) + ttl_seconds
        value = json.dumps(
            {"node_id": node_id, "expires_at": expires_at},
            sort_keys=True,
        ).encode("utf-8")
        new_revision = await self._kv.update(key, value, last=revision)
        return LeaseClaim(True, node_id, new_revision, expires_at)

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
        self._nc = None
        self._js = None
        self._kv = None
