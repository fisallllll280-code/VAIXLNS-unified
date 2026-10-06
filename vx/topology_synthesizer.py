"""Deterministic topology synthesis over the existing Flux Grid."""
from continuum.flux_grid import FluxGrid, FluxNode, FluxPlan

def synthesize(intent_id: str, capability: str, nodes: list[dict],
               *, parallel: bool = False, max_nodes: int = 1) -> FluxPlan:
    grid = FluxGrid(
        FluxNode(
            node_id=n["node_id"],
            capabilities=frozenset(n.get("capabilities", [])),
            healthy=bool(n.get("healthy", True)),
            capacity=int(n.get("capacity", 1)),
            risk=float(n.get("risk", 1.0)),
        )
        for n in nodes
    )
    return grid.plan(
        intent_id=intent_id,
        capability=capability,
        parallel=parallel,
        max_nodes=max_nodes,
    )
