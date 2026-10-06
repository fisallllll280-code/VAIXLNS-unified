"""Executable capability registry for the VAIXLNS-unified conformance spine."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class CapabilityState(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    REVOKED = "REVOKED"

@dataclass(frozen=True)
class Capability:
    capability_id: str
    provider: str = "internal"
    version: str = "1.0"
    constraints: dict[str, Any] = field(default_factory=dict)
    state: CapabilityState = CapabilityState.ACTIVE

class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> Capability:
        if not capability.capability_id:
            raise ValueError("CAPABILITY_ID_REQUIRED")
        self._items[capability.capability_id] = capability
        return capability

    def get(self, capability_id: str) -> Capability:
        try:
            return self._items[capability_id]
        except KeyError as exc:
            raise KeyError(f"UNKNOWN_CAPABILITY:{capability_id}") from exc

    def can_execute(self, capability_id: str) -> bool:
        return self.get(capability_id).state is CapabilityState.ACTIVE

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "capability_id": c.capability_id,
                "provider": c.provider,
                "version": c.version,
                "constraints": dict(c.constraints),
                "state": c.state.value,
            }
            for c in sorted(self._items.values(), key=lambda x: x.capability_id)
        ]
