"""Minimal contract-first VLNS operating and development runtime.

This implementation covers the first executable vertical slice of the VLNS
specification: registry, lifecycle, capability routing, observation, and
controlled change progression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class LifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    REGISTERED = "REGISTERED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    RETIRED = "RETIRED"


class ChangeState(str, Enum):
    PROPOSED = "PROPOSED"
    ANALYZED = "ANALYZED"
    CANDIDATE = "CANDIDATE"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    BUILT = "BUILT"
    DEPLOYED = "DEPLOYED"
    OBSERVED = "OBSERVED"
    ACCEPTED = "ACCEPTED"


@dataclass(frozen=True)
class SystemContract:
    system_id: str
    version: str
    interfaces: tuple[str, ...]
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    required_resources: tuple[str, ...] = ()
    provided_resources: tuple[str, ...] = ()
    governance_requirements: tuple[str, ...] = ()
    verification_status: str = "UNVERIFIED"
    provenance: str = ""
    state: LifecycleState = LifecycleState.DISCOVERED
    health: str = "UNKNOWN"
    compatibility: tuple[str, ...] = ()

    def with_state(self, state: LifecycleState, health: str | None = None) -> "SystemContract":
        return SystemContract(
            **{
                **self.__dict__,
                "state": state,
                "health": self.health if health is None else health,
            }
        )


@dataclass(frozen=True)
class Observation:
    system_id: str
    state: LifecycleState
    health: str
    event: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SystemRegistry:
    """Canonical in-process registry keyed by system identity."""

    def __init__(self) -> None:
        self._systems: dict[str, SystemContract] = {}

    def register(self, contract: SystemContract) -> SystemContract:
        if not contract.system_id:
            raise ValueError("SYSTEM_ID_REQUIRED")
        if contract.system_id in self._systems:
            raise ValueError("SYSTEM_ALREADY_REGISTERED")
        stored = contract.with_state(LifecycleState.REGISTERED, "UNKNOWN")
        self._systems[stored.system_id] = stored
        return stored

    def get(self, system_id: str) -> SystemContract:
        return self._systems[system_id]

    def update(self, contract: SystemContract) -> SystemContract:
        if contract.system_id not in self._systems:
            raise KeyError("SYSTEM_NOT_REGISTERED")
        self._systems[contract.system_id] = contract
        return contract

    def all(self) -> tuple[SystemContract, ...]:
        return tuple(self._systems.values())

    def capability(self, capability: str) -> tuple[SystemContract, ...]:
        return tuple(
            s for s in self._systems.values()
            if capability in s.capabilities and s.state not in {LifecycleState.RETIRED}
        )


class VLNSRuntime:
    """Cross-system coordination boundary without owning participant internals."""

    _allowed = {
        LifecycleState.REGISTERED: {LifecycleState.INITIALIZING, LifecycleState.RETIRED},
        LifecycleState.INITIALIZING: {LifecycleState.READY, LifecycleState.DEGRADED, LifecycleState.RETIRED},
        LifecycleState.READY: {LifecycleState.ACTIVE, LifecycleState.DEGRADED, LifecycleState.RETIRED},
        LifecycleState.ACTIVE: {LifecycleState.DEGRADED, LifecycleState.RECOVERING, LifecycleState.RETIRED},
        LifecycleState.DEGRADED: {LifecycleState.RECOVERING, LifecycleState.RETIRED},
        LifecycleState.RECOVERING: {LifecycleState.READY, LifecycleState.DEGRADED, LifecycleState.RETIRED},
    }

    def __init__(self, registry: SystemRegistry | None = None) -> None:
        self.registry = registry or SystemRegistry()
        self.observations: list[Observation] = []

    def register(self, contract: SystemContract) -> SystemContract:
        stored = self.registry.register(contract)
        self.observe(stored.system_id, "REGISTERED", "UNKNOWN", {"version": stored.version})
        return stored

    def transition(self, system_id: str, target: LifecycleState, health: str = "UNKNOWN") -> SystemContract:
        current = self.registry.get(system_id)
        if target not in self._allowed.get(current.state, set()):
            raise ValueError(f"INVALID_LIFECYCLE:{current.state.value}->{target.value}")
        updated = current.with_state(target, health)
        self.registry.update(updated)
        self.observe(system_id, target.value, health)
        return updated

    def route_capability(self, capability: str) -> SystemContract:
        candidates = self.registry.capability(capability)
        active = [s for s in candidates if s.state in {LifecycleState.READY, LifecycleState.ACTIVE}]
        if not active:
            raise LookupError(f"CAPABILITY_UNAVAILABLE:{capability}")
        return sorted(active, key=lambda s: (s.state is not LifecycleState.ACTIVE, s.system_id))[0]

    def dispatch(
        self,
        capability: str,
        payload: dict[str, Any],
        handlers: dict[str, Callable[[dict[str, Any]], Any]],
    ) -> Any:
        target = self.route_capability(capability)
        handler = handlers.get(target.system_id)
        if handler is None:
            raise LookupError(f"HANDLER_UNAVAILABLE:{target.system_id}")
        self.observe(target.system_id, "DISPATCH", target.health, {"capability": capability})
        result = handler(dict(payload))
        self.observe(target.system_id, "DISPATCH_COMPLETED", target.health, {"capability": capability})
        return result

    def observe(self, system_id: str, event: str, health: str, metadata: dict[str, Any] | None = None) -> Observation:
        state = self.registry.get(system_id).state if system_id in {s.system_id for s in self.registry.all()} else LifecycleState.DISCOVERED
        item = Observation(system_id, state, health, event, metadata or {})
        self.observations.append(item)
        return item

    def development_transition(self, current: ChangeState, target: ChangeState) -> ChangeState:
        allowed = {
            ChangeState.PROPOSED: ChangeState.ANALYZED,
            ChangeState.ANALYZED: ChangeState.CANDIDATE,
            ChangeState.CANDIDATE: ChangeState.TESTED,
            ChangeState.TESTED: ChangeState.VERIFIED,
            ChangeState.VERIFIED: ChangeState.APPROVED,
            ChangeState.APPROVED: ChangeState.BUILT,
            ChangeState.BUILT: ChangeState.DEPLOYED,
            ChangeState.DEPLOYED: ChangeState.OBSERVED,
            ChangeState.OBSERVED: ChangeState.ACCEPTED,
        }
        if allowed.get(current) != target:
            raise ValueError(f"INVALID_CHANGE_TRANSITION:{current.value}->{target.value}")
        return target
