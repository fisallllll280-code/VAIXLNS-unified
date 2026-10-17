"""ARC-X -> VX governed execution bridge.

ARC-X compiles evidence and policy eligibility; VX remains the execution
supervisor. Simulation and test runners must be supplied by a trusted host and
confined to an approved sandbox. This adapter never creates an executor or
authority callback itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from arc_x.core import (
    AdmissionDecision,
    AuthorityApproval,
    CompilationResult,
    EvidenceKind,
    evaluate_admission,
)
from vx.runtime_supervisor import Operation, Phase, VXSupervisor


StageRunner = Callable[[Mapping[str, Any]], Mapping[str, Any]]
TestRunner = Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class VXBridgeResult:
    status: str
    operation_id: str
    eir_sha256: str
    reason_codes: tuple[str, ...] = ()
    vx_phase: str = ""
    execution_result: Mapping[str, Any] | None = None
    replay: tuple[Mapping[str, Any], ...] = ()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _operation_id(eir_sha256: str, approval_id: str) -> str:
    material = _canonical_json({"eir_sha256": eir_sha256, "approval_id": approval_id, "protocol": "arc-x-vx.v1"})
    return "arcx-vx-" + sha256(material.encode("utf-8")).hexdigest()[:24]


def _replay(op: Operation) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {"seq": e.seq, "phase": e.phase.value, "name": e.name, "payload": dict(e.payload)}
        for e in op.events
    )


def _fail(op: Operation, reason: str, eir_sha256: str) -> VXBridgeResult:
    if op.phase not in {Phase.FAILED, Phase.VERIFIED, Phase.RECOVERED}:
        op.transition(Phase.FAILED, "arc_x_vx_blocked", {"reason": reason, "eir_sha256": eir_sha256})
    return VXBridgeResult("BLOCKED", op.operation_id, eir_sha256, (reason,), op.phase.value, replay=_replay(op))


class ArcXVXBridge:
    """Route an ARC-X EIR through VX's existing state machine and authorizer."""

    def __init__(
        self,
        supervisor: VXSupervisor,
        *,
        evidence_verifier: Callable[[CompilationResult], bool],
        authority_verifier: Callable[[AuthorityApproval, str], bool],
        simulation_runner: StageRunner,
        test_runner: TestRunner,
    ) -> None:
        if not callable(evidence_verifier) or not callable(authority_verifier):
            raise ValueError("TRUSTED_VERIFIERS_REQUIRED")
        if not callable(simulation_runner) or not callable(test_runner):
            raise ValueError("SANDBOX_STAGE_RUNNERS_REQUIRED")
        self.supervisor = supervisor
        self.evidence_verifier = evidence_verifier
        self.authority_verifier = authority_verifier
        self.simulation_runner = simulation_runner
        self.test_runner = test_runner

    @staticmethod
    def _match_stage_evidence(
        compilation: CompilationResult,
        result: Mapping[str, Any],
        accepted_kinds: set[str],
    ) -> bool:
        if not isinstance(result, Mapping) or result.get("ok") is not True:
            return False
        evidence_id = result.get("evidence_id")
        artifact_sha256 = result.get("artifact_sha256")
        if not isinstance(evidence_id, str) or not isinstance(artifact_sha256, str):
            return False
        if len(artifact_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in artifact_sha256.lower()):
            return False
        matches = [
            row for row in compilation.eir.get("evidence", [])
            if row.get("evidence_id") == evidence_id
        ]
        return (
            len(matches) == 1
            and matches[0].get("kind") in accepted_kinds
            and matches[0].get("result") == "PASS"
            and matches[0].get("artifact_sha256", "").lower() == artifact_sha256.lower()
            and matches[0].get("source_id") in {s.get("source_id") for s in compilation.eir.get("sources", [])}
        )

    def execute(
        self,
        compilation: CompilationResult,
        approval: AuthorityApproval,
        *,
        objective: str,
    ) -> VXBridgeResult:
        """Run sandbox simulation/tests, then request governed VX execution.

        The sandbox runners must be trusted host-owned harnesses. Results must
        match source-linked, hash-pinned evidence records already in the EIR.
        VX's own authorizer, executor and verifier remain active after ARC-X's gate.
        """
        if not objective.strip():
            return VXBridgeResult("BLOCKED", "", compilation.eir_sha256, ("OBJECTIVE_REQUIRED",))
        if not compilation.integrity_valid:
            return VXBridgeResult("BLOCKED", "", compilation.eir_sha256, ("EIR_INTEGRITY_HASH_MISMATCH",))
        if compilation.epistemic_state == "CONFLICT" or compilation.has_conflicts:
            return VXBridgeResult("BLOCKED", "", compilation.eir_sha256, ("UNRESOLVED_CONFLICT",))
        if not compilation.proof_scope_complete:
            return VXBridgeResult("BLOCKED", "", compilation.eir_sha256, ("DECLARED_PROOF_SCOPE_INCOMPLETE",))

        operation_id = _operation_id(compilation.eir_sha256, approval.approval_id)
        if operation_id in self.supervisor.operations:
            existing = self.supervisor.operations[operation_id]
            return VXBridgeResult(
                "BLOCKED", operation_id, compilation.eir_sha256,
                ("DUPLICATE_OPERATION_ID_REPLAY_BLOCKED",), existing.phase.value,
                replay=_replay(existing),
            )

        op = self.supervisor.prepare(
            operation_id,
            objective,
            {
                "protocol": "arc-x-vx.v1",
                "eir_sha256": compilation.eir_sha256,
                "eir": compilation.eir,
                "approval_id": approval.approval_id,
                "requested_action": "EXECUTE",
            },
        )

        try:
            simulation = dict(self.simulation_runner(compilation.eir))
        except Exception as exc:
            return _fail(op, "SIMULATION_EXCEPTION:" + type(exc).__name__, compilation.eir_sha256)
        self.supervisor.simulate(op, {
            "ok": simulation.get("ok") is True,
            "evidence_id": simulation.get("evidence_id", ""),
            "artifact_sha256": simulation.get("artifact_sha256", ""),
        })
        if not self._match_stage_evidence(compilation, simulation, {EvidenceKind.SIMULATION_TRACE.value}):
            return _fail(op, "SIMULATION_EVIDENCE_MISMATCH_OR_FAILURE", compilation.eir_sha256)

        try:
            test_result = dict(self.test_runner(compilation.eir, simulation))
        except Exception as exc:
            return _fail(op, "TEST_EXCEPTION:" + type(exc).__name__, compilation.eir_sha256)
        self.supervisor.test(op, {
            "ok": test_result.get("ok") is True,
            "evidence_id": test_result.get("evidence_id", ""),
            "artifact_sha256": test_result.get("artifact_sha256", ""),
        })
        if not self._match_stage_evidence(
            compilation, test_result,
            {EvidenceKind.TEST_RESULT.value, EvidenceKind.PROOF_ARTIFACT.value},
        ):
            return _fail(op, "TEST_EVIDENCE_MISMATCH_OR_FAILURE", compilation.eir_sha256)

        gate = evaluate_admission(
            compilation, "EXECUTE", approval,
            evidence_verifier=self.evidence_verifier,
            authority_verifier=self.authority_verifier,
        )
        if gate.decision is not AdmissionDecision.ADMITTED:
            return _fail(op, "ARC_X_GATE:" + ",".join(gate.reason_codes), compilation.eir_sha256)

        if not self.supervisor.authorize(op):
            return VXBridgeResult(
                "BLOCKED", operation_id, compilation.eir_sha256,
                ("VX_AUTHORIZER_DENIED",), op.phase.value, replay=_replay(op),
            )

        def verify_arcx_binding(operation: Operation, output: Mapping[str, Any]) -> bool:
            return (
                output.get("ok") is True
                and output.get("operation_id") == operation_id
                and output.get("eir_sha256") == compilation.eir_sha256
                and operation.snapshot.get("eir_sha256") == compilation.eir_sha256
            )

        try:
            output = dict(self.supervisor.execute(op, additional_verifier=verify_arcx_binding))
        except Exception as exc:
            output = {"ok": False, "error_type": type(exc).__name__}
        replay = _replay(op)
        if op.phase is not Phase.VERIFIED:
            return VXBridgeResult(
                "EXECUTION_FAILED", operation_id, compilation.eir_sha256,
                ("VX_RUNTIME_DID_NOT_VERIFY_EXECUTION",), op.phase.value, output, replay,
            )
        return VXBridgeResult(
            "EXECUTED_AND_VX_VERIFIED", operation_id, compilation.eir_sha256,
            ("ARC_X_EVIDENCE_GATE_PASSED", "VX_AUTHORITY_GATE_PASSED", "VX_RUNTIME_VERIFIER_PASSED"),
            op.phase.value, output, replay,
        )


__all__ = ["ArcXVXBridge", "VXBridgeResult"]
