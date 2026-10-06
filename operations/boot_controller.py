"""Readiness gate for the executable surface."""
from __future__ import annotations
from dataclasses import dataclass
from operations.health_monitor import HealthMonitor, HealthStatus

@dataclass(frozen=True)
class BootResult:
    status: str
    health: HealthStatus

class BootController:
    def __init__(self) -> None:
        self.health = HealthMonitor()

    def boot(self, checks: dict[str, bool]) -> BootResult:
        health = self.health.evaluate(checks)
        return BootResult("READY" if health.ready else "BLOCKED", health)
