"""Deterministic productivity routing for approved tools.

Trust, health, scope and risk gates are evaluated before utility. A faster tool
never outranks an unauthorized or unhealthy tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class ToolCandidate:
    name: str
    server: str
    capabilities: frozenset[str]
    approved: bool = False
    health: str = "unknown"
    reliability: float = 0.0
    evidence_strength: float = 0.0
    latency_ms: float = 1000.0
    cost: float = 0.0
    risk: float = 1.0
    parallel_safe: bool = True

    def utility(self, capability: str) -> float:
        if capability not in self.capabilities:
            return -1.0
        trust = max(0.0, min(1.0, self.reliability))
        evidence = max(0.0, min(1.0, self.evidence_strength))
        latency_factor = 1.0 / (1.0 + max(0.0, self.latency_ms) / 1000.0)
        cost_factor = 1.0 / (1.0 + max(0.0, self.cost))
        risk_factor = 1.0 / (1.0 + max(0.0, self.risk))
        return trust * evidence * latency_factor * cost_factor * risk_factor


@dataclass(frozen=True)
class ToolSelection:
    capability: str
    selected: Tuple[ToolCandidate, ...]
    rejected: Tuple[Tuple[str, str], ...]


class ProductivityRouter:
    """Trust-first deterministic selector."""

    def select(
        self,
        capability: str,
        candidates: Iterable[ToolCandidate],
        *,
        max_tools: int = 1,
        require_parallel: bool = False,
    ) -> ToolSelection:
        usable = []
        rejected = []
        for candidate in candidates:
            if not candidate.approved:
                rejected.append((candidate.name, "NOT_APPROVED"))
                continue
            if candidate.health.lower() != "healthy":
                rejected.append((candidate.name, "UNHEALTHY"))
                continue
            if capability not in candidate.capabilities:
                rejected.append((candidate.name, "CAPABILITY_MISMATCH"))
                continue
            if require_parallel and not candidate.parallel_safe:
                rejected.append((candidate.name, "NOT_PARALLEL_SAFE"))
                continue
            usable.append(candidate)

        usable.sort(key=lambda c: (-c.utility(capability), c.latency_ms, c.cost, c.name))
        chosen = tuple(usable[: max(0, max_tools)])
        return ToolSelection(capability, chosen, tuple(rejected))

    @staticmethod
    def throughput_estimate(selection: ToolSelection, batch_size: int) -> float:
        if batch_size <= 0 or not selection.selected:
            return 0.0
        total_latency = sum(max(1.0, t.latency_ms) for t in selection.selected)
        return float(batch_size) * 1000.0 / total_latency
