"""Deterministic simulation runtime bridge for the four-domain room."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Protocol, Tuple
import math


@dataclass(frozen=True)
class SimulationCase:
    simulation_id: str
    domain: str
    parameters: Mapping[str, float]
    initial_state: Tuple[float, ...]
    steps: int
    dt: float
    constraints: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulationResult:
    simulation_id: str
    backend: str
    state: Tuple[float, ...]
    metrics: Mapping[str, float]
    evidence: Tuple[str, ...]
    deterministic: bool
    success: bool


class SimulationBackend(Protocol):
    name: str
    def run(self, case: SimulationCase) -> SimulationResult: ...


class EulerBackend:
    """Small deterministic reference backend for dX/dt = acceleration."""

    name = "euler-reference"

    def run(self, case: SimulationCase) -> SimulationResult:
        if case.steps < 0 or case.dt <= 0:
            return SimulationResult(
                case.simulation_id, self.name, case.initial_state, {}, ("invalid-parameters",), True, False
            )
        if len(case.initial_state) < 2:
            raise ValueError("initial_state requires position and velocity")
        x, v = case.initial_state[0], case.initial_state[1]
        a = float(case.parameters.get("acceleration", 0.0))
        for _ in range(case.steps):
            x = x + v * case.dt
            v = v + a * case.dt
            if not (math.isfinite(x) and math.isfinite(v)):
                return SimulationResult(
                    case.simulation_id, self.name, (x, v), {}, ("non-finite-state",), True, False
                )
        metrics={"position":x,"velocity":v,"steps":float(case.steps),"dt":case.dt}
        evidence=(f"simulation:{case.simulation_id}", f"backend:{self.name}")
        return SimulationResult(case.simulation_id,self.name,(x,v),metrics,evidence,True,True)


class SimulationRegistry:
    def __init__(self) -> None:
        self.backends: Dict[str, SimulationBackend] = {}

    def register(self, backend: SimulationBackend) -> None:
        if backend.name in self.backends:
            raise ValueError(f"backend collision: {backend.name}")
        self.backends[backend.name]=backend

    def run(self, backend_name: str, case: SimulationCase) -> SimulationResult:
        return self.backends[backend_name].run(case)
