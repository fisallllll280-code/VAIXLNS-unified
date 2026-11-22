"""ARC-X Ω evidence compiler and fail-closed admission contract.

This package is a runtime-side implementation surface, not a new canonical
authority. The canonical specification remains in the VAIXLNS repository.
"""
from .core import (
    AdmissionDecision,
    AdmissionResult,
    AuthorityApproval,
    ClaimKind,
    ClaimRecord,
    CompilationResult,
    EvidenceKind,
    EvidenceRecord,
    ProofObligation,
    SourceReceipt,
    Stance,
    compile_eir,
    evaluate_admission,
)

__all__ = [
    "AdmissionDecision",
    "AdmissionResult",
    "AuthorityApproval",
    "ClaimKind",
    "ClaimRecord",
    "CompilationResult",
    "EvidenceKind",
    "EvidenceRecord",
    "ProofObligation",
    "SourceReceipt",
    "Stance",
    "compile_eir",
    "evaluate_admission",
]
