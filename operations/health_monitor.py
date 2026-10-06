"""Dependency-free health/readiness monitor."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    checks: dict[str, bool]
    reason: str

class HealthMonitor:
    def evaluate(self, checks: dict[str, bool]) -> HealthStatus:
        normalized = {str(k): bool(v) for k, v in sorted(checks.items())}
        ready = all(normalized.values()) if normalized else False
        return HealthStatus(ready, normalized, "READY" if ready else "NOT_READY")
