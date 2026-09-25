"""Executable architecture discovery/search laboratory.

This module implements a small deterministic kernel for TEST-001, TEST-002,
TEST-004, TEST-011 and TEST-012 from the project acceptance sequence.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Dict, Iterable, List, Mapping, Set, Tuple


def stable_id(payload: Mapping[str, object], prefix: str = "arch") -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return f"{prefix}_{sha256(raw).hexdigest()[:16]}"


@dataclass(frozen=True)
class CapabilityGap:
    id: str
    required: Tuple[str, ...]
    missing: Tuple[str, ...]
    source: str


@dataclass(frozen=True)
class ArchitectureDesign:
    id: str
    gap_id: str
    variant: str
    components: Tuple[str, ...]
    assumptions: Tuple[str, ...]
    isolated: bool = True


@dataclass(frozen=True)
class ArchitectureAssessment:
    architecture_id: str
    metrics: Mapping[str, float]
    verified: bool
    evidence: Tuple[str, ...]
    failures: Tuple[str, ...] = ()


class ArchitectureLab:
    def discover_gap(
        self,
        required_capabilities: Iterable[str],
        available_capabilities: Iterable[str],
        source: str = "mission",
    ) -> CapabilityGap:
        required = tuple(dict.fromkeys(required_capabilities))
        available = set(available_capabilities)
        missing = tuple(x for x in required if x not in available)
        payload = {"required": required, "available": sorted(available), "source": source}
        return CapabilityGap(stable_id(payload, "gap"), required, missing, source)

    def search_three(self, gap: CapabilityGap) -> List[ArchitectureDesign]:
        if not gap.missing:
            return []
        core = gap.missing
        variants = (
            ("minimal", core),
            ("redundant", core + ("independent-verifier",)),
            ("adaptive", core + ("feedback-controller",)),
        )
        return [
            ArchitectureDesign(
                id=stable_id({"gap": gap.id, "variant": name, "components": comps}),
                gap_id=gap.id,
                variant=name,
                components=tuple(comps),
                assumptions=("isolated candidate", "explicit verification gate"),
            )
            for name, comps in variants
        ]

    def assess(
        self,
        design: ArchitectureDesign,
        metrics: Mapping[str, float],
        thresholds: Mapping[str, float],
        evidence: Iterable[str] = (),
    ) -> ArchitectureAssessment:
        failures = tuple(
            f"{key}<{thresholds[key]}"
            for key in thresholds
            if float(metrics.get(key, 0.0)) < float(thresholds[key])
        )
        return ArchitectureAssessment(
            architecture_id=design.id,
            metrics=dict(metrics),
            verified=not failures,
            evidence=tuple(evidence),
            failures=failures,
        )


class CausalArchitectureGraph:
    def __init__(self) -> None:
        self._edges: Dict[str, Set[str]] = {}

    def add_edge(self, source: str, target: str, relation: str = "CAUSES") -> None:
        self._edges.setdefault(source, set()).add(target)

    def blast_radius(self, changed_node: str) -> Tuple[str, ...]:
        seen: Set[str] = set()
        frontier = [changed_node]
        while frontier:
            current = frontier.pop()
            for target in self._edges.get(current, set()):
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
        seen.discard(changed_node)
        return tuple(sorted(seen))


class ArchitectureSelfCritique:
    """Detect architecture drift from measurable constraints and propose a fork."""

    def critique(
        self,
        architecture_id: str,
        observed: Mapping[str, float],
        limits: Mapping[str, float],
    ) -> Mapping[str, object]:
        violations = {
            key: {"observed": float(observed.get(key, 0.0)), "limit": float(limit)}
            for key, limit in limits.items()
            if float(observed.get(key, 0.0)) > float(limit)
        }
        return {
            "architecture_id": architecture_id,
            "drift": bool(violations),
            "violations": violations,
        }

    def propose_revision(
        self,
        architecture_id: str,
        violations: Mapping[str, object],
    ) -> ArchitectureDesign:
        return ArchitectureDesign(
            id=stable_id({"parent": architecture_id, "violations": violations}, "archrev"),
            gap_id=f"revision-of:{architecture_id}",
            variant="self-critique-fork",
            components=("diagnostic-controller", "alternative-topology"),
            assumptions=tuple(f"repair:{k}" for k in sorted(violations)),
            isolated=True,
        )
