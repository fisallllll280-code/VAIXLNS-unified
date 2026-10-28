"""Executable, fail-closed evidence gate for Ω.2718 sovereign closure."""
from .engine import (
    CheckResult,
    ClosureReport,
    canonical_sha256,
    evaluate_closure,
)

__all__ = [
    "CheckResult",
    "ClosureReport",
    "canonical_sha256",
    "evaluate_closure",
]
