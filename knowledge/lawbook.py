"""LawBook: provenance-aware formalization of domain laws."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Iterable, List, Mapping, Tuple

@dataclass(frozen=True)
class LawRecord:
    id: str
    domain: str
    statement: str
    normalized_expression: str
    source: str
    provenance: Tuple[str, ...]
    validation_backends: Tuple[str, ...]
    status: str = 'unverified'

class LawBook:
    def __init__(self) -> None:
        self._laws: dict[str, LawRecord] = {}

    @staticmethod
    def _id(payload: Mapping[str, object]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
        return 'law_' + sha256(raw).hexdigest()[:20]

    def ingest(self, domain: str, statement: str, normalized_expression: str, source: str, provenance: Iterable[str], validation_backends: Iterable[str]) -> LawRecord:
        payload = {'domain': domain, 'statement': statement, 'normalized_expression': normalized_expression, 'source': source, 'provenance': list(provenance), 'validation_backends': list(validation_backends)}
        law = LawRecord(self._id(payload), domain, statement, normalized_expression, source, tuple(provenance), tuple(validation_backends))
        self._laws[law.id] = law
        return law

    def validate(self, law_id: str, backend: str, passed: bool) -> LawRecord:
        old = self._laws[law_id]
        status = 'verified' if passed and backend in old.validation_backends else old.status
        updated = LawRecord(**{**asdict(old), 'status': status})
        self._laws[law_id] = updated
        return updated

    def get(self, law_id: str) -> LawRecord:
        return self._laws[law_id]

    def snapshot(self) -> List[dict]:
        return [asdict(x) for x in self._laws.values()]
