"""Provider-neutral model/tool capability registry."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str
    capabilities: Tuple[str, ...]
    context_window: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class ToolSpec:
    id: str
    kind: str
    capabilities: Tuple[str, ...]
    risk_class: str = "normal"
    enabled: bool = True


class CapabilityRegistry:
    def __init__(self) -> None:
        self.models: Dict[str, ModelSpec] = {}
        self.tools: Dict[str, ToolSpec] = {}

    def register_model(self, model: ModelSpec) -> None:
        if model.id in self.models and self.models[model.id] != model:
            raise ValueError(f"model collision: {model.id}")
        self.models[model.id] = model

    def register_tool(self, tool: ToolSpec) -> None:
        if tool.id in self.tools and self.tools[tool.id] != tool:
            raise ValueError(f"tool collision: {tool.id}")
        self.tools[tool.id] = tool

    def models_for(self, capability: str) -> List[ModelSpec]:
        return [m for m in self.models.values() if m.enabled and capability in m.capabilities]

    def tools_for(self, capability: str) -> List[ToolSpec]:
        return [t for t in self.tools.values() if t.enabled and capability in t.capabilities]

    def manifest(self) -> dict:
        return {
            "models": [asdict(m) for m in self.models.values()],
            "tools": [asdict(t) for t in self.tools.values()],
        }
