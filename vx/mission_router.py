"""Mission router for the four-domain VX room.

The router turns a customer mission into a bounded workspace manifest. It does
not execute anything and does not grant authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple
import json


DOMAIN_MIND_MAP = {
    "mathematics": ("architect", "math", "researcher", "reviewer"),
    "physics": ("physics", "math", "researcher", "reviewer"),
    "engineering": ("architect", "developer", "optimizer", "security", "reviewer"),
    "computing": ("developer", "architect", "tester", "security", "operator"),
}

DOMAIN_UI_MAP = {
    "mathematics": ("equation_workspace", "proof_workspace", "solver_workspace"),
    "physics": ("model_workspace", "simulation_workspace", "parameter_workspace"),
    "engineering": ("topology_workspace", "constraint_workspace", "resource_workspace"),
    "computing": ("code_workspace", "build_workspace", "runtime_workspace"),
}


@dataclass(frozen=True)
class MissionRoom:
    mission: str
    domains: Tuple[str, ...]
    minds: Tuple[str, ...]
    workspaces: Tuple[str, ...]
    gates: Tuple[str, ...]


class MissionRouter:
    def __init__(self, profile_path: str | Path):
        self.profile_path = Path(profile_path)
        data = json.loads(self.profile_path.read_text(encoding="utf-8"))
        self.profiles: Mapping[str, Any] = data.get("profiles", {})

    def compose(
        self,
        mission: str,
        domains: Iterable[str],
        mode: str = "solve",
    ) -> MissionRoom:
        selected = tuple(dict.fromkeys(d.lower() for d in domains if d))
        unknown = [d for d in selected if d not in DOMAIN_MIND_MAP]
        if unknown:
            raise ValueError(f"unsupported four-domain room member(s): {unknown}")

        minds: List[str] = []
        ui: List[str] = []
        for domain in selected:
            minds.extend(DOMAIN_MIND_MAP[domain])
            ui.extend(DOMAIN_UI_MAP[domain])

        profile = self.profiles.get(mode, {})
        priorities = tuple(str(x) for x in profile.get("priority", ()))
        gates = tuple(dict.fromkeys(("simulate", "test", "verify") + priorities))

        return MissionRoom(
            mission=mission,
            domains=selected,
            minds=tuple(dict.fromkeys(minds)),
            workspaces=tuple(dict.fromkeys(ui)),
            gates=gates,
        )
