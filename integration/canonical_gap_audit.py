"""Executable gap audit over the canonical VAIXLNS decomposition."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List
import json


@dataclass(frozen=True)
class Gap:
    id: str
    plane: str
    severity: str
    status: str
    evidence: str
    next_step: str


def load_decomposition(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit(path: str | Path) -> List[Gap]:
    data = load_decomposition(path)
    gaps: List[Gap] = []
    for plane in data.get("planes", []):
        status = plane.get("status", "unknown")
        if status == "partial":
            gaps.append(Gap(
                id=f"GAP-{plane['id'].upper()}-PARTIAL",
                plane=plane["id"],
                severity="high",
                status="open",
                evidence="The architecture is declared and only a subset is executable in the current unified repository.",
                next_step="Connect source-owned implementation to the canonical contract and add executable conformance tests.",
            ))
        elif status == "missing_runtime_bridge":
            gaps.append(Gap(
                id=f"GAP-{plane['id'].upper()}-RUNTIME-BRIDGE",
                plane=plane["id"],
                severity="critical",
                status="open",
                evidence="The four-domain simulation layer is declared but no canonical runtime bridge is registered.",
                next_step="Add pluggable math/physics/engineering backends, isolated execution, numerical validation and evidence capture.",
            ))
        elif status == "specified":
            gaps.append(Gap(
                id=f"GAP-{plane['id'].upper()}-IMPLEMENTATION",
                plane=plane["id"],
                severity="high",
                status="open",
                evidence="The plane is specified but the executable canonical surface is not yet established.",
                next_step="Implement a minimal vertical slice and bind it to tests and provenance.",
            ))
    return gaps


def report(path: str | Path) -> Dict[str, Any]:
    data = load_decomposition(path)
    gaps = audit(path)
    counts: Dict[str, int] = {}
    for gap in gaps:
        counts[gap.severity] = counts.get(gap.severity, 0) + 1
    return {
        "canonical_system": data.get("canonical_system"),
        "gap_count": len(gaps),
        "severity_counts": counts,
        "gaps": [asdict(g) for g in gaps],
    }
