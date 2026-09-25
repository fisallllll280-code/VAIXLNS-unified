"""Desired-state reconciliation loop for VX operations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Tuple


@dataclass(frozen=True)
class ReconcileResult:
    desired: Mapping[str, Any]
    actual: Mapping[str, Any]
    drift: Tuple[str, ...]
    actions: Tuple[str, ...]
    converged: bool


class Reconciler:
    def __init__(self, observe: Callable[[], Mapping[str, Any]], converge: Callable[[str, Any], str]) -> None:
        self.observe = observe
        self.converge = converge

    def run_once(self, desired: Mapping[str, Any]) -> ReconcileResult:
        actual=dict(self.observe())
        drift=tuple(sorted(
            key for key,value in desired.items()
            if actual.get(key) != value
        ))
        actions=tuple(self.converge(key, desired[key]) for key in drift)
        final=dict(self.observe()) if actions else actual
        return ReconcileResult(
            desired=dict(desired),
            actual=final,
            drift=drift,
            actions=actions,
            converged=all(final.get(k) == v for k,v in desired.items()),
        )
