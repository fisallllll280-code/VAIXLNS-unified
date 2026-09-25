"""VX Invention Engine V1.

Turns agents, models, interfaces, workflows and repositories into first-class
invention components. The engine is provider-neutral: intelligence proposes;
explicit verification gates decide promotion.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
import json
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(payload: Mapping[str, Any], prefix: str) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return f"{prefix}_{sha256(raw).hexdigest()[:16]}"


@dataclass(frozen=True)
class Mission:
    objective: str
    domains: Tuple[str, ...]
    constraints: Tuple[str, ...] = ()
    output_type: str = "capability"


@dataclass(frozen=True)
class Capability:
    id: str
    kind: str
    domains: Tuple[str, ...]
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    invariants: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()
    lineage: Tuple[str, ...] = ()


@dataclass(frozen=True)
class InventionCandidate:
    id: str
    mission: Mission
    components: Tuple[str, ...]
    transformation: str
    proof_obligations: Tuple[str, ...]
    novelty_axes: Tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class ExperimentResult:
    candidate_id: str
    simulated: bool
    tested: bool
    verified: bool
    evidence: Tuple[str, ...]
    failures: Tuple[str, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    kind: str
    value: Mapping[str, Any]
    provenance: Tuple[str, ...]
    parent_id: Optional[str]
    status: str
    created_at: str


class CapabilityGenome:
    """Append-only registry of reusable capabilities and their lineage."""

    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self._items: Dict[str, Capability] = {c.id: c for c in capabilities}

    def register(self, capability: Capability) -> None:
        existing = self._items.get(capability.id)
        if existing and existing != capability:
            raise ValueError(f"capability collision: {capability.id}")
        self._items[capability.id] = capability

    def get(self, capability_id: str) -> Capability:
        return self._items[capability_id]

    def compatible(self, domains: Sequence[str]) -> List[Capability]:
        requested = set(domains)
        return [
            c for c in self._items.values()
            if requested.intersection(c.domains)
            or "cross-domain" in c.domains
        ]

    def snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(c) for c in sorted(self._items.values(), key=lambda x: x.id)]


class MemoryFabric:
    """Versioned, provenance-aware memory with explicit invalidation/branching."""

    def __init__(self) -> None:
        self._records: Dict[str, MemoryRecord] = {}

    def write(
        self,
        kind: str,
        value: Mapping[str, Any],
        provenance: Sequence[str],
        parent_id: Optional[str] = None,
    ) -> MemoryRecord:
        payload = {
            "kind": kind,
            "value": value,
            "provenance": list(provenance),
            "parent_id": parent_id,
        }
        record = MemoryRecord(
            id=stable_id(payload, "mem"),
            kind=kind,
            value=dict(value),
            provenance=tuple(provenance),
            parent_id=parent_id,
            status="active",
            created_at=utc_now(),
        )
        self._records[record.id] = record
        return record

    def branch(self, record_id: str, patch: Mapping[str, Any], provenance: Sequence[str]) -> MemoryRecord:
        parent = self._records[record_id]
        merged = dict(parent.value)
        merged.update(patch)
        return self.write(parent.kind, merged, provenance, parent_id=record_id)

    def invalidate(self, record_id: str) -> None:
        old = self._records[record_id]
        self._records[record_id] = MemoryRecord(
            id=old.id,
            kind=old.kind,
            value=old.value,
            provenance=old.provenance,
            parent_id=old.parent_id,
            status="invalid",
            created_at=old.created_at,
        )

    def get(self, record_id: str) -> MemoryRecord:
        return self._records[record_id]

    def snapshot(self) -> List[Dict[str, Any]]:
        return [asdict(x) for x in self._records.values()]


Simulator = Callable[[InventionCandidate], Mapping[str, Any]]
Verifier = Callable[[InventionCandidate, Mapping[str, Any]], Mapping[str, Any]]


class InventionForge:
    """Generate cross-domain candidates from reusable capabilities."""

    TRANSFORMATIONS = (
        "compose",
        "invert_constraint",
        "swap_solver",
        "cross_domain_bridge",
        "proof_carrying_variant",
        "counterfactual_variant",
    )

    NOVELTY_AXES = (
        "new_composition",
        "new_constraint_mapping",
        "new_execution_path",
        "new_verification_path",
        "new_memory_lineage",
        "new_interface_projection",
    )

    def __init__(self, genome: CapabilityGenome) -> None:
        self.genome = genome

    def generate(self, mission: Mission, limit: int = 24) -> List[InventionCandidate]:
        available = self.genome.compatible(mission.domains)
        candidates: List[InventionCandidate] = []

        for left, right in combinations(available, 2):
            if not set(left.outputs).intersection(right.inputs) and "cross-domain" not in mission.domains:
                continue
            for transformation in self.TRANSFORMATIONS:
                payload = {
                    "mission": asdict(mission),
                    "components": [left.id, right.id],
                    "transformation": transformation,
                }
                candidate = InventionCandidate(
                    id=stable_id(payload, "inv"),
                    mission=mission,
                    components=(left.id, right.id),
                    transformation=transformation,
                    proof_obligations=tuple(sorted(set(mission.constraints) | set(left.invariants) | set(right.invariants))),
                    novelty_axes=self.NOVELTY_AXES[:3 if transformation == "compose" else 4],
                    created_at=utc_now(),
                )
                candidates.append(candidate)
                if len(candidates) >= limit:
                    return candidates
        return candidates


class InnovationLoop:
    """Closed-loop invention: generate -> simulate -> test -> verify -> promote."""

    def __init__(
        self,
        genome: CapabilityGenome,
        memory: MemoryFabric,
        simulator: Simulator,
        verifier: Verifier,
    ) -> None:
        self.genome = genome
        self.memory = memory
        self.simulator = simulator
        self.verifier = verifier
        self.forge = InventionForge(genome)

    def run(self, mission: Mission, limit: int = 12) -> List[Tuple[InventionCandidate, ExperimentResult]]:
        candidates = self.forge.generate(mission, limit=limit)
        results: List[Tuple[InventionCandidate, ExperimentResult]] = []
        for candidate in candidates:
            sim = dict(self.simulator(candidate))
            simulated = bool(sim.get("simulated", False))
            tested = bool(sim.get("tested", simulated))
            verification = dict(self.verifier(candidate, sim)) if tested else {}
            verified = bool(verification.get("verified", False))
            evidence = tuple(str(x) for x in verification.get("evidence", ()))
            failures = tuple(str(x) for x in verification.get("failures", ()))
            result = ExperimentResult(
                candidate_id=candidate.id,
                simulated=simulated,
                tested=tested,
                verified=verified,
                evidence=evidence,
                failures=failures,
                metrics={str(k): float(v) for k, v in verification.get("metrics", {}).items()},
            )
            self.memory.write(
                "invention-experiment",
                {"candidate": asdict(candidate), "result": asdict(result)},
                provenance=list(candidate.components) + list(evidence),
            )
            if verified:
                promoted = Capability(
                    id=stable_id({"candidate": candidate.id, "result": asdict(result)}, "cap"),
                    kind=mission.output_type,
                    domains=mission.domains,
                    inputs=("mission",),
                    outputs=("verified-capability",),
                    invariants=mission.constraints,
                    evidence=evidence,
                    lineage=(candidate.id,),
                )
                self.genome.register(promoted)
            results.append((candidate, result))
        return results
