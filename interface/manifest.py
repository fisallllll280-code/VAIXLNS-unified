"""Mission-derived interface manifests.

The manifest is UI-agnostic and can be consumed by a web, desktop or embedded
renderer. It makes an interface a first-class, reproducible artifact.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, List, Mapping, Tuple


@dataclass(frozen=True)
class InterfaceInvention:
    id: str
    mission: str
    domains: Tuple[str, ...]
    panels: Tuple[str, ...]
    controls: Tuple[str, ...]
    semantic_tokens: Mapping[str, str]
    lineage: Tuple[str, ...]


class InterfaceFactory:
    def build(self, mission: str, domains: Iterable[str], lineage: Iterable[str] = ()) -> InterfaceInvention:
        selected=tuple(dict.fromkeys(d.lower() for d in domains))
        panels=["mission","multi_mind","architecture","evidence","runtime","memory","github","innovation"]
        controls=["prepare","simulate","test","authorize","execute","pause","replay","recover","verify"]
        if "mathematics" in selected:
            panels += ["equations","proofs","solvers"]
        if "physics" in selected:
            panels += ["models","simulation","parameters"]
        if "engineering" in selected:
            panels += ["topology","constraints","resources"]
        if "computing" in selected:
            panels += ["code","build","runtime"]
        identity_payload=json.dumps({"mission":mission,"domains":selected},sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
        stable_id=sha256(identity_payload).hexdigest()[:16]
        return InterfaceInvention(
            id=f"ui:{stable_id}",
            mission=mission,
            domains=selected,
            panels=tuple(dict.fromkeys(panels)),
            controls=tuple(controls),
            semantic_tokens={
                "control":"graphite",
                "computation":"electric-cyan",
                "intelligence":"violet",
                "innovation":"amber",
                "verified":"green",
                "blocked":"red",
                "neutral":"white",
            },
            lineage=tuple(lineage),
        )

    @staticmethod
    def to_dict(invention: InterfaceInvention) -> Dict[str, Any]:
        return asdict(invention)
