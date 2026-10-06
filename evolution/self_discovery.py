"""VAIXLNS self-discovery kernel.

Turns unexplained architectural gaps into first-class, lineage-preserving
unknowns and hypothesis candidates. It does not promote anything to Canonical.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from evolution.architecture_lab import ArchitectureLab, CapabilityGap
from innovation_control.engine import InnovationCandidate


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class UnknownRecord:
    id: str
    question: str
    uncertainty_type: str
    affected_architecture: tuple[str, ...]
    evidence: tuple[str, ...]
    blocked_decision: str
    next_experiment: str
    status: str = "OPEN"

    @property
    def fingerprint(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class DiscoveryReport:
    mission: str
    gaps: tuple[CapabilityGap, ...]
    unknowns: tuple[UnknownRecord, ...]
    hypotheses: tuple[InnovationCandidate, ...]


class SelfDiscoveryEngine:
    """Discover missing structure without silently promoting it."""

    def __init__(self) -> None:
        self.architecture = ArchitectureLab()

    def discover(
        self,
        mission: str,
        required_capabilities: Iterable[str],
        available_capabilities: Iterable[str],
        *,
        evidence: Sequence[str] = (),
    ) -> DiscoveryReport:
        gap = self.architecture.discover_gap(
            required_capabilities,
            available_capabilities,
            source=f"mission:{mission}",
        )
        unknowns: list[UnknownRecord] = []
        for missing in gap.missing:
            payload = {
                "mission": mission,
                "missing": missing,
                "gap": gap.id,
            }
            uid = "unknown_" + _digest(payload)[:16]
            unknowns.append(
                UnknownRecord(
                    id=uid,
                    question=f"What canonical capability/structure satisfies '{missing}'?",
                    uncertainty_type="MISSING_CAPABILITY",
                    affected_architecture=(gap.id, missing),
                    evidence=tuple(evidence),
                    blocked_decision="CANONICAL_ADOPTION",
                    next_experiment=f"Generate and falsify isolated architectures for '{missing}'.",
                )
            )

        hypotheses: list[InnovationCandidate] = []
        for unknown in unknowns:
            missing = unknown.affected_architecture[-1]
            hypotheses.append(
                InnovationCandidate(
                    candidate_id="hypothesis_" + unknown.id,
                    mission=mission,
                    architecture={
                        "unknown_id": unknown.id,
                        "gap_id": gap.id,
                        "missing_capability": missing,
                        "generation": "self-discovery-v1",
                    },
                    proof_obligations=(
                        "deterministic",
                        "replayable",
                        "independently_verifiable",
                    ),
                    lineage=("self-discovery", mission, gap.id, unknown.id),
                )
            )

        return DiscoveryReport(
            mission=mission,
            gaps=(gap,),
            unknowns=tuple(unknowns),
            hypotheses=tuple(hypotheses),
        )

    @staticmethod
    def unresolved(report: DiscoveryReport) -> tuple[UnknownRecord, ...]:
        return tuple(u for u in report.unknowns if u.status == "OPEN")
