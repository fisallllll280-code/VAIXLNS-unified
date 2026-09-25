"""Typed canonical Nexus graph for VAIXLNS.

Entities and relations are first-class, provenance-carrying records. This is a
runtime bridge for the graph concepts described in the architecture archive.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, List, Mapping, Tuple


def _id(payload: Mapping[str, Any], prefix: str) -> str:
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    return f"{prefix}_{sha256(raw).hexdigest()[:16]}"


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
    def __init__(self) -> None:
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[str, Relation] = {}

    def add_entity(self, entity: Entity) -> Entity:
        existing=self.entities.get(entity.id)
        if existing and existing != entity:
            raise ValueError(f"entity collision: {entity.id}")
        self.entities[entity.id]=entity
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
        payload={"source":source,"target":target,"relation_type":relation_type,
                 "semantics":semantics,"provenance":list(provenance)}
        relation=Relation(
            id=_id(payload,"rel"),
            source=source,
            target=target,
            relation_type=relation_type,
            semantics=semantics,
            provenance=tuple(provenance),
        )
        self.relations[relation.id]=relation
        return relation

    def neighbors(self, entity_id: str, relation_type: str | None = None) -> List[Entity]:
        out=[]
        for rel in self.relations.values():
            if rel.source != entity_id:
                continue
            if relation_type and rel.relation_type != relation_type:
                continue
            out.append(self.entities[rel.target])
        return out

    def snapshot(self) -> Dict[str, Any]:
        return {
            "entities":[asdict(e) for e in self.entities.values()],
            "relations":[asdict(r) for r in self.relations.values()],
        }
