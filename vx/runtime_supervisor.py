"""VX operational supervisor V1.

Explicit state machine for prepare/simulate/test/authorize/execute/verify/
recover/replay. Execution is injected through a handler so the core never
silently gains authority over external systems.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional


class Phase(str, Enum):
    NEW = "new"
    PREPARED = "prepared"
    SIMULATED = "simulated"
    TESTED = "tested"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    VERIFIED = "verified"
    RECOVERED = "recovered"
    FAILED = "failed"


_ALLOWED = {
    Phase.NEW: {Phase.PREPARED, Phase.FAILED},
    Phase.PREPARED: {Phase.SIMULATED, Phase.FAILED},
    Phase.SIMULATED: {Phase.TESTED, Phase.FAILED},
    Phase.TESTED: {Phase.AUTHORIZED, Phase.FAILED},
    Phase.AUTHORIZED: {Phase.EXECUTING, Phase.FAILED},
    Phase.EXECUTING: {Phase.VERIFIED, Phase.RECOVERED, Phase.FAILED},
    Phase.VERIFIED: set(),
    Phase.RECOVERED: {Phase.PREPARED, Phase.FAILED},
    Phase.FAILED: {Phase.RECOVERED},
}


@dataclass(frozen=True)
class Event:
    seq: int
    phase: Phase
    name: str
    payload: Mapping[str, Any]


@dataclass
class Operation:
    operation_id: str
    objective: str
    phase: Phase = Phase.NEW
    events: List[Event] = field(default_factory=list)
    snapshot: Optional[Mapping[str, Any]] = None

    def transition(self, target: Phase, name: str, payload: Optional[Mapping[str, Any]] = None) -> None:
        if target not in _ALLOWED[self.phase]:
            raise RuntimeError(f"invalid transition {self.phase.value} -> {target.value}")
        self.phase = target
        self.events.append(Event(len(self.events) + 1, target, name, dict(payload or {})))


Authorizer = Callable[[Operation], bool]
Handler = Callable[[Operation], Mapping[str, Any]]
Verifier = Callable[[Operation, Mapping[str, Any]], bool]


class VXSupervisor:
    def __init__(
        self,
        authorizer: Authorizer,
        executor: Handler,
        verifier: Verifier,
        recoverer: Optional[Callable[[Operation], Mapping[str, Any]]] = None,
    ) -> None:
        self.authorizer = authorizer
        self.executor = executor
        self.verifier = verifier
        self.recoverer = recoverer or (lambda op: {"recovered": True, "operation_id": op.operation_id})
        self.operations: Dict[str, Operation] = {}

    def prepare(self, operation_id: str, objective: str, snapshot: Mapping[str, Any]) -> Operation:
        op = Operation(operation_id=operation_id, objective=objective, snapshot=dict(snapshot))
        self.operations[operation_id] = op
        op.transition(Phase.PREPARED, "prepare", {"objective": objective})
        return op

    def simulate(self, op: Operation, result: Mapping[str, Any]) -> None:
        op.transition(Phase.SIMULATED, "simulate", result)

    def test(self, op: Operation, result: Mapping[str, Any]) -> None:
        op.transition(Phase.TESTED, "test", result)

    def authorize(self, op: Operation) -> bool:
        allowed = bool(self.authorizer(op))
        op.transition(Phase.AUTHORIZED if allowed else Phase.FAILED, "authorize", {"allowed": allowed})
        return allowed

    def execute(
        self,
        op: Operation,
        *,
        executor: Optional[Handler] = None,
        additional_verifier: Optional[Verifier] = None,
    ) -> Mapping[str, Any]:
        """Execute an authorized operation with optional per-request trusted gates.

        Overrides are explicit call-scoped dependencies. The base VX verifier
        always runs; when supplied, the additional verifier must also pass.
        This permits governed adapters to supply a request-bound dispatcher
        without mutating the supervisor's shared executor.
        """
        if op.phase is not Phase.AUTHORIZED:
            raise RuntimeError("execution requires authorization")
        if executor is not None and not callable(executor):
            raise TypeError("EXECUTOR_NOT_CALLABLE")
        if additional_verifier is not None and not callable(additional_verifier):
            raise TypeError("ADDITIONAL_VERIFIER_NOT_CALLABLE")
        op.transition(Phase.EXECUTING, "execute_start")
        try:
            result = dict((executor or self.executor)(op))
            verified = bool(self.verifier(op, result))
            if additional_verifier is not None:
                verified = verified and bool(additional_verifier(op, result))
            if verified:
                op.transition(Phase.VERIFIED, "verify", result)
            else:
                op.transition(Phase.FAILED, "verify_failed", {
                    "ok": result.get("ok") is True,
                    "tool_status": result.get("tool_status", ""),
                    "reason_code": result.get("reason_code", ""),
                    "tool_event_hash": result.get("tool_event_hash", ""),
                    "output_sha256": result.get("output_sha256", ""),
                })
            return result
        except Exception as exc:
            op.transition(Phase.FAILED, "execute_error", {"error_type": type(exc).__name__})
            return {"ok": False, "error_type": type(exc).__name__}

    def recover(self, op: Operation) -> Mapping[str, Any]:
        if op.phase is not Phase.FAILED:
            raise RuntimeError("recovery is only valid after failure")
        result = dict(self.recoverer(op))
        op.transition(Phase.RECOVERED, "recover", result)
        return result

    def replay(self, operation_id: str) -> List[Dict[str, Any]]:
        op = self.operations[operation_id]
        return [{"seq": e.seq, "phase": e.phase.value, "name": e.name, "payload": dict(e.payload)} for e in op.events]
