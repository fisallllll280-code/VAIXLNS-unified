"""Federated VAIXLNS boot and conformance smoke runner.

This layer does not pretend that specification repositories are executable.
It composes the executable vertical slice that currently exists in
VAIXLNS-unified and reports the remaining federation gaps explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from core.identity import Identity, IdentityService, Permission
from core.ledger import Event, SovereignEventLedger
from core.sovereign_constitution import SovereignConstitution
from execution.state_machine import Event as StateEvent, StateMachine, State
from execution.vx_runtime import ExecutionEnvelope, ExecutionStatus, VXRuntime


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "integration" / "federation_registry.json"


@dataclass
class BootReport:
    federation_entries: int
    local_modules: dict[str, bool]
    constitutional_checks: dict[str, bool]
    state: str
    execution_status: str
    replay_status: str
    ledger_integrity: bool
    smoke_passed: bool
    operational_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GovernedVX:
    """Small constitutional adapter around the existing VX runtime."""

    def __init__(self, constitution: SovereignConstitution, ledger: SovereignEventLedger):
        self.constitution = constitution
        self.ledger = ledger
        self.runtime = VXRuntime(ledger)

    def execute(
        self,
        actor: Identity,
        capability: str,
        inputs: dict[str, Any],
        worker: Callable[[dict[str, Any]], Any],
    ):
        if not actor.active:
            raise PermissionError("INACTIVE_IDENTITY")
        if not actor.has_permission(Permission.EXECUTE):
            raise PermissionError("EXECUTE_PERMISSION_REQUIRED")
        if not actor.has_capability(capability):
            raise PermissionError("CAPABILITY_REQUIRED")
        for category in ("security", "execution", "governance", "data", "determinism"):
            if not self.constitution.verify_compliance(category):
                raise RuntimeError(f"CONSTITUTION_NON_COMPLIANT:{category}")

        envelope = ExecutionEnvelope(
            actor=actor,
            capability=capability,
            inputs=dict(inputs),
        )
        return self.runtime.execute(envelope, worker)


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def check_local_modules() -> dict[str, bool]:
    required = {
        "core.identity": "core.identity",
        "core.ledger": "core.ledger",
        "core.sovereign_constitution": "core.sovereign_constitution",
        "execution.state_machine": "execution.state_machine",
        "execution.determinism": "execution.determinism",
        "execution.vx_runtime": "execution.vx_runtime",
    }
    return {name: importlib.util.find_spec(module) is not None for name, module in required.items()}


def run_smoke() -> BootReport:
    registry = load_registry()
    local_modules = check_local_modules()

    constitution = SovereignConstitution()
    constitutional_checks = {
        category: constitution.verify_compliance(category)
        for category in ("security", "execution", "governance", "data", "determinism")
    }

    state = StateMachine("VAIXLNS-FEDERATED")
    state.transition(StateEvent.BOOT, "genesis")
    state.transition(StateEvent.INITIALIZE, "federation registry loaded")
    state.transition(StateEvent.CHECK, "local executable surface discovered")
    state.transition(StateEvent.READY, "readiness gate")
    state.transition(StateEvent.ACTIVATE, "constitutional checks passed")

    identity_service = IdentityService()
    actor = identity_service.create_identity(
        name="VAIXLNS-SMOKE",
        actor_type="system",
        permissions={Permission.EXECUTE, Permission.AUDIT, Permission.VERIFY},
    )
    actor.grant_capability("integration.smoke")

    ledger = SovereignEventLedger()
    governed = GovernedVX(constitution, ledger)

    result = governed.execute(
        actor=actor,
        capability="integration.smoke",
        inputs={"a": 21, "b": 21, "mode": "deterministic"},
        worker=lambda payload: payload["a"] + payload["b"],
    )

    replay = governed.runtime.replay_execution(
        result.execution_id,
        lambda payload: payload["a"] + payload["b"],
    )

    ledger.append(
        Event(
            aggregate_id="VAIXLNS-SMOKE",
            event_type="INTEGRATION_VERIFIED",
            actor_id=actor.id,
            capability_used="integration.smoke",
            payload={"execution_id": result.execution_id, "replay_status": replay.status.value},
        )
    )

    smoke_passed = all(local_modules.values()) and all(constitutional_checks.values())
    smoke_passed = smoke_passed and state.get_state() == State.ACTIVE
    smoke_passed = smoke_passed and result.status == ExecutionStatus.SUCCESS
    smoke_passed = smoke_passed and replay.status == ExecutionStatus.SUCCESS
    smoke_passed = smoke_passed and ledger.verify_integrity()

    return BootReport(
        federation_entries=len(registry["repositories"]),
        local_modules=local_modules,
        constitutional_checks=constitutional_checks,
        state=state.get_state().value,
        execution_status=result.status.value,
        replay_status=replay.status.value,
        ledger_integrity=ledger.verify_integrity(),
        smoke_passed=smoke_passed,
        operational_state="PARTIAL" if smoke_passed else "FAILED",
    )
