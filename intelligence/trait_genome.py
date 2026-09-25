"""Intelligence Trait Genome: portable, measured capability traits."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Tuple

TRAITS = ('reasoning','math','physics','coding','planning','research','tool_use','vision','audio','long_context','multilingual','security','optimization','creativity','spatial','teaching')

@dataclass(frozen=True)
class TraitEvidence:
    trait: str
    score: float
    benchmark: str
    evidence_ref: str

@dataclass(frozen=True)
class IntelligenceProfile:
    id: str
    provider: str
    model: str
    traits: Tuple[TraitEvidence, ...]
    provenance: Tuple[str, ...] = ()

class TraitGenome:
    def __init__(self) -> None:
        self.profiles: Dict[str, IntelligenceProfile] = {}

    def register(self, profile: IntelligenceProfile) -> None:
        if any(t.trait not in TRAITS for t in profile.traits):
            raise ValueError('unknown intelligence trait')
        self.profiles[profile.id] = profile

    def candidates(self, required_traits: Iterable[str], min_score: float = 0.5) -> List[IntelligenceProfile]:
        required = set(required_traits)
        out = []
        for profile in self.profiles.values():
            scores = {t.trait: t.score for t in profile.traits}
            if all(scores.get(t, 0.0) >= min_score for t in required):
                out.append(profile)
        return out

    def compose_mind(self, name: str, required_traits: Iterable[str], min_score: float = 0.5) -> dict:
        required = tuple(dict.fromkeys(required_traits))
        return {'mind_id': name, 'required_traits': required, 'model_candidates': [{'profile_id': p.id, 'provider': p.provider, 'model': p.model} for p in self.candidates(required, min_score)], 'strategy': 'route-per-trait-and-cross-check'}

    def snapshot(self) -> list[dict]:
        return [asdict(p) for p in self.profiles.values()]
