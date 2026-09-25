"""Engineering Video Forge.

Builds a reproducible storyboard from system lineage, equations, simulation
evidence and architecture state. Rendering is delegated to selectable
open-weight video backends.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Mapping, Tuple


@dataclass(frozen=True)
class VideoShot:
    index: int
    purpose: str
    visual: str
    narration: str
    evidence_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class VideoPlan:
    title: str
    format: str
    shots: Tuple[VideoShot, ...]
    backend_candidates: Tuple[str, ...]
    provenance: Tuple[str, ...]


class EngineeringVideoForge:
    BACKENDS = (
        "ltx-2",
        "wan-2.2",
        "hunyuanvideo-1.5",
        "cogvideox",
    )

    def build(
        self,
        title: str,
        architecture: str,
        equations: Iterable[str] = (),
        simulation_evidence: Iterable[str] = (),
        lineage: Iterable[str] = (),
    ) -> VideoPlan:
        eq=tuple(equations)
        ev=tuple(simulation_evidence)
        shots=(
            VideoShot(1,"problem","technical system overview",f"Problem: {architecture}",ev),
            VideoShot(2,"laws","animated equations and variables","Show the governing equations.",eq),
            VideoShot(3,"simulation","parameterized simulation with overlays","Show simulated states and measured error.",ev),
            VideoShot(4,"architecture","exploded engineering view with dependency lines","Show components, contracts and interfaces."),
            VideoShot(5,"verification","proof/evidence overlay","Show what passed, what failed and why."),
            VideoShot(6,"evolution","before/after architecture lineage","Show how the system changed through evidence."),
        )
        return VideoPlan(
            title=title,
            format="16:9",
            shots=shots,
            backend_candidates=self.BACKENDS,
            provenance=tuple(lineage),
        )

    @staticmethod
    def to_dict(plan: VideoPlan) -> dict:
        return asdict(plan)
