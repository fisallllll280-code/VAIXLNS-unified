"""Dynamic execution topology for VX-CONTINUUM.

Flux Grid chooses execution topology; it has no canonical, identity, sovereign
key, or commit authority. It can schedule work but cannot promote truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class FluxNode:
    node_id: str
    capabilities: frozenset[str]
    healthy: bool = True
    capacity: int = 1
    risk: float = 1.0


@dataclass(frozen=True)
class FluxPlan:
    intent_id: str
    capability: str
    node_ids: tuple[str, ...]
    parallel: bool
    topology_digest: str


class FluxGrid:
    """Deterministic topology planner, not an authority plane."""

    def __init__(self, nodes: Iterable[FluxNode] = ()) -> None:
        self._nodes = {node.node_id: node for node in nodes}

    def add(self, node: FluxNode) -> None:
        if not node.node_id:
            raise ValueError("NODE_ID_REQUIRED")
        self._nodes[node.node_id] = node

    def plan(self, *, intent_id: str, capability: str, parallel: bool = False,
             max_nodes: int = 1) -> FluxPlan:
        if not intent_id or not capability:
            raise ValueError("INTENT_AND_CAPABILITY_REQUIRED")
        if max_nodes < 1:
            raise ValueError("MAX_NODES_INVALID")
        eligible = [
            n for n in self._nodes.values()
            if n.healthy and capability in n.capabilities and n.capacity > 0
        ]
        eligible.sort(key=lambda n: (n.risk, n.node_id))
        selected = tuple(n.node_id for n in eligible[:max_nodes])
        if not selected:
            raise LookupError("NO_ELIGIBLE_FLUX_NODE")
        body = {
            "intent_id": intent_id,
            "capability": capability,
            "nodes": selected,
            "parallel": parallel,
        }
        return FluxPlan(intent_id, capability, selected, parallel, _digest(body))
