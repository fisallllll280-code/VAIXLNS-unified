"""Append-only JSONL memory fabric with branching and invalidation events."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(payload: Mapping[str, Any]) -> str:
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    memory_id: str
    payload: Mapping[str, Any]
    created_at: str
    previous_event_hash: str = ""


class DurableMemoryFabric:
    def __init__(self, path: str | Path) -> None:
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if not self.path.exists():
            self.path.write_text("",encoding="utf-8")

    def _events(self) -> list[MemoryEvent]:
        out=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            data=json.loads(line)
            out.append(MemoryEvent(**data))
        return out

    def append(self, event_type: str, memory_id: str, payload: Mapping[str, Any]) -> MemoryEvent:
        previous=self._events()[-1].event_id if self._events() else ""
        raw={"type":event_type,"memory_id":memory_id,"payload":payload,"created_at":_now(),"previous":previous}
        event=MemoryEvent(
            event_id=_hash(raw)[:24],
            event_type=event_type,
            memory_id=memory_id,
            payload=dict(payload),
            created_at=raw["created_at"],
            previous_event_hash=previous,
        )
        with self.path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(asdict(event),ensure_ascii=False,sort_keys=True)+"\n")
        return event

    def write(self, memory_id: str, value: Mapping[str, Any], provenance: Iterable[str]=()) -> MemoryEvent:
        return self.append("write",memory_id,{"value":dict(value),"provenance":list(provenance),"status":"active"})

    def branch(self, memory_id: str, parent_id: str, patch: Mapping[str, Any], provenance: Iterable[str]=()) -> MemoryEvent:
        return self.append("branch",memory_id,{"parent_id":parent_id,"patch":dict(patch),"provenance":list(provenance),"status":"active"})

    def invalidate(self, memory_id: str, reason: str) -> MemoryEvent:
        return self.append("invalidate",memory_id,{"reason":reason,"status":"invalid"})

    def events(self) -> list[MemoryEvent]:
        return self._events()
