"""Ω Causal Impact Budget V1.

Pre-execution impact control: a candidate must stay within an explicit
causal-impact budget before it can affect canonical surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ImpactNode:
    node_id: str
    criticality: float = 1.0
    state_mutating: bool = False


@dataclass(frozen=True)
class ImpactAssessment:
    weighted_impact: float
    budget: float
    passed: bool
    affected: tuple[str, ...]
    blocked: tuple[str, ...]


class CausalImpactBudget:
    """Turn blast radius from a list into a risk budget."""

    def assess(
        self,
        affected_nodes: Sequence[ImpactNode],
        *,
        budget: float,
        forbidden_nodes: frozenset[str] = frozenset(),
        max_state_mutations: int = 1,
    ) -> ImpactAssessment:
        if budget < 0:
            raise ValueError("IMPACT_BUDGET_MUST_BE_NON_NEGATIVE")
        affected = tuple(node.node_id for node in affected_nodes)
        blocked = tuple(node.node_id for node in affected_nodes if node.node_id in forbidden_nodes)
        state_mutations = sum(1 for node in affected_nodes if node.state_mutating)
        weighted = sum(max(0.0, min(1.0, node.criticality)) for node in affected_nodes)
        passed = weighted <= budget and not blocked and state_mutations <= max_state_mutations
        if state_mutations > max_state_mutations:
            blocked = blocked + ("STATE_MUTATION_LIMIT",)
        if weighted > budget:
            blocked = blocked + ("IMPACT_BUDGET_EXCEEDED",)
        return ImpactAssessment(weighted, budget, passed, affected, blocked)


__all__ = ["CausalImpactBudget", "ImpactAssessment", "ImpactNode"]
