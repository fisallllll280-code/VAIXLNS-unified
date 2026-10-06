"""Prediction-vs-reality diff with deterministic canonical ordering."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class VDiff:
    equal: bool
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    unexpected: tuple[str, ...]

def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten(value[key], path))
        return out
    return {prefix: value}

def compare(predicted: Any, actual: Any) -> VDiff:
    p, a = _flatten(predicted), _flatten(actual)
    missing = sorted(set(p) - set(a))
    unexpected = sorted(set(a) - set(p))
    changed = sorted(k for k in set(p) & set(a) if p[k] != a[k])
    return VDiff(not (missing or changed or unexpected), tuple(missing), tuple(changed), tuple(unexpected))

class VDiffEngine:
    compare = staticmethod(compare)
