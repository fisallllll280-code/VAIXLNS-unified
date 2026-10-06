"""VX-CONTINUUM executable primitives.

Adaptive execution remains subordinate to VX/SCCK canonical authority.
The package is intentionally small: Atomaton, Flux Grid, Proof Spectrum,
Proof Atom, and Intent-to-topology compilation.
"""
from .atomaton import Atomaton, AtomatonState
from .flux_grid import FluxGrid, FluxNode, FluxPlan
from .proof import ProofAtom, ProofLevel, ProofPolicy, select_proof_level
from .compiler import ContinuumCompiler, ContinuumPlan

__all__ = [
    "Atomaton", "AtomatonState",
    "FluxGrid", "FluxNode", "FluxPlan",
    "ProofAtom", "ProofLevel", "ProofPolicy", "select_proof_level",
    "ContinuumCompiler", "ContinuumPlan",
]
