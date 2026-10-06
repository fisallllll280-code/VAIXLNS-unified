"""Typed canonical Nexus graph for VAIXLNS.

Entities and relations are first-class, provenance-carrying records. The graph
supports deterministic IDs plus an append-only JSONL journal for local durable
reconstruction. The journal is a runtime surface, not a claim of distributed
consensus or multi-node durability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _id(payload: Mapping[str, Any], prefix: str) -> str:
    return f"{prefix}_{sha256(_stable(payload).encode()).hexdigest()[:16]}"


@dataclass(frozen=True)
class Entity:
    id: str
    type: str
    meaning: str
    state: str = "active"
    provenance: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Relation:
    id: str
    source: str
    target: str
    relation_type: str
    semantics: str = ""
    provenance: Tuple[str, ...] = ()


class CanonicalNexus:
    def __init__(self, journal: str | Path | None = None) -> None:
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[str, Relation] = {}
        self.journal = Path(journal) if journal else None
        if self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            self.journal.touch(exist_ok=True)

    def _record(self, event_type: str, payload: Mapping[str, Any]) -> None:
        if not self.journal:
            return
        events = self.journal.read_text(encoding="utf-8").splitlines()
        previous = json.loads(events[-1])["hash"] if events else "GENESIS"
        body = {
            "event_type": event_type,
            "payload": dict(payload),
            "previous": previous,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        body["hash"] = sha256(_stable(body).encode()).hexdigest()
        with self.journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")

    def add_entity(self, entity: Entity) -> Entity:
        existing = self.entities.get(entity.id)
        if existing and existing != entity:
            raise ValueError(f"entity collision: {entity.id}")
        self.entities[entity.id] = entity
        self._record("ENTITY_UPSERT", asdict(entity))
        return entity

    def entity(self, entity_id: str) -> Entity:
        return self.entities[entity_id]

    def relate(
        self,
        source: str,
        target: str,
        relation_type: str,
        semantics: str = "",
        provenance: Iterable[str] = (),
    ) -> Relation:
        if source not in self.entities or target not in self.entities:
            raise KeyError("relation endpoints must exist")
        provenance_tuple = tuple(provenance)
        payload = {
            "source": source,
            "target": target,
            "relation_type": relation_type,
            "semantics": semantics,
            "provenance": list(provenance_tuple),
        }
        relation = Relation(
            id=_id(payload, "rel"),
            source=source,
            target=target,
            relation_type=relation_type,
            semantics=semantics,
            provenance=provenance_tuple,
        )
        existing = self.relations.get(relation.id)
        if existing and existing != relation:
            raise ValueError(f"relation collision: {relation.id}")
        self.relations[relation.id] = relation
        self._record("RELATION_UPSERT", asdict(relation))
        return relation

    def neighbors(self, entity_id: str, relation_type: str | None = None) -> List[Entity]:
        out = []
        for rel in self.relations.values():
            if rel.source != entity_id:
                continue
            if relation_type and rel.relation_type != relation_type:
                continue
            out.append(self.entities[rel.target])
        return out

    def snapshot(self) -> Dict[str, Any]:
        return {
            "entities": [asdict(e) for e in sorted(self.entities.values(), key=lambda x: x.id)],
            "relations": [asdict(r) for r in sorted(self.relations.values(), key=lambda x: x.id)],
        }

    def verify_journal(self) -> bool:
        if not self.journal:
            return True
        previous = "GENESIS"
        for line in self.journal.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            event = json.loads(line)
            body = {
                "event_type": event["event_type"],
                "payload": event["payload"],
                "previous": event["previous"],
                "created_at": event["created_at"],
            }
            if event["previous"] != previous or sha256(_stable(body).encode()).hexdigest() != event["hash"]:
                return False
            previous = event["hash"]
        return True

    def save_snapshot(self, path: str | Path) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot()
        digest = sha256(_stable(payload).encode()).hexdigest()
        target.write_text(
            json.dumps({"snapshot": payload, "digest": digest}, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return digest
