"""Append-only JSONL memory fabric with verifiable hash-chain events."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    memory_id: str
    payload: Mapping[str, Any]
    created_at: str
    previous_event_hash: str = ""
    event_hash: str = ""


class DurableMemoryFabric:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def _events(self) -> list[MemoryEvent]:
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line:
                events.append(MemoryEvent(**json.loads(line)))
        return events

    def append(self, event_type: str, memory_id: str, payload: Mapping[str, Any]) -> MemoryEvent:
        existing = self._events()
        previous_hash = existing[-1].event_hash if existing else "GENESIS"
        created_at = _now()
        event_id = _digest({
            "event_type": event_type,
            "memory_id": memory_id,
            "payload": payload,
            "created_at": created_at,
            "previous_event_hash": previous_hash,
        })[:24]
        body = {
            "event_id": event_id,
            "event_type": event_type,
            "memory_id": memory_id,
            "payload": dict(payload),
            "created_at": created_at,
            "previous_event_hash": previous_hash,
        }
        event_hash = _digest(body)
        event = MemoryEvent(**body, event_hash=event_hash)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def write(self, memory_id: str, value: Mapping[str, Any], provenance: Iterable[str] = ()) -> MemoryEvent:
        return self.append("write", memory_id, {
            "value": dict(value), "provenance": list(provenance), "status": "active"
        })

    def branch(self, memory_id: str, parent_id: str, patch: Mapping[str, Any], provenance: Iterable[str] = ()) -> MemoryEvent:
        return self.append("branch", memory_id, {
            "parent_id": parent_id, "patch": dict(patch), "provenance": list(provenance), "status": "active"
        })

    def invalidate(self, memory_id: str, reason: str) -> MemoryEvent:
        return self.append("invalidate", memory_id, {"reason": reason, "status": "invalid"})

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            body = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "memory_id": event.memory_id,
                "payload": dict(event.payload),
                "created_at": event.created_at,
                "previous_event_hash": previous,
            }
            if event.previous_event_hash != previous or _digest(body) != event.event_hash:
                return False
            previous = event.event_hash
        return True

    def events(self) -> list[MemoryEvent]:
        return self._events()
