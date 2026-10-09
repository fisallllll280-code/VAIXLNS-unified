"""Contract-first connector fabric for routing registered tools through VX.

This module does not create network clients or grant permissions. The host must
supply health probes, integration admission, and an already-governed
ExecutionGateway/VXSupervisor. A new connector is deny-by-default until those
boundaries independently allow it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from arc_x.core import canonical_json
from tools.execution_fabric import ExecutionGateway, Principal, ToolSpec
from vx.runtime_supervisor import Operation, Phase, VXSupervisor


HealthProbe = Callable[["ServerContract"], Mapping[str, Any]]
IntegrationAdmission = Callable[[str], bool]
ArcXPolicyGate = Callable[[\"ServerContract\", ToolSpec, Principal, Mapping[str, Any]], Mapping[str, Any]]


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def tool_contract_digest(spec: ToolSpec) -> str:
    """Canonical fingerprint of the executable ToolSpec (no handler/code disclosure)."""
    payload = {
        "tool_id": spec.tool_id,
        "description": spec.description,
        "required_inputs": sorted(spec.required_inputs),
        "optional_inputs": sorted(spec.optional_inputs),
        "required_scopes": sorted(spec.required_scopes),
        "scope_groups": sorted([sorted(group) for group in spec.scope_groups]),
        "enabled": spec.enabled,
        "risk": spec.risk,
        "external_integration_id": spec.external_integration_id,
        "max_output_bytes": spec.max_output_bytes,
    }
    return _sha256(canonical_json(payload))


@dataclass(frozen=True)
class ServerContract:
    server_id: str
    integration_id: str | None
    protocol: str
    protocol_version: str
    contract_version: str
    tool_ids: tuple[str, ...]
    tool_contract_digests: Mapping[str, str]
    endpoint_ref: str = "local://host-managed"
    max_latency_ms: int = 5000

    def __post_init__(self) -> None:
        for field_name in ("server_id", "protocol", "protocol_version", "contract_version", "endpoint_ref"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"SERVER_{field_name.upper()}_REQUIRED")
        if not self.tool_ids or len(set(self.tool_ids)) != len(self.tool_ids):
            raise ValueError("SERVER_TOOL_IDS_MUST_BE_NONEMPTY_AND_UNIQUE")
        if set(self.tool_contract_digests) != set(self.tool_ids):
            raise ValueError("SERVER_TOOL_CONTRACT_DIGEST_SET_MISMATCH")
        if isinstance(self.max_latency_ms, bool) or not isinstance(self.max_latency_ms, int) or self.max_latency_ms <= 0:
            raise ValueError("SERVER_MAX_LATENCY_MUST_BE_POSITIVE_INTEGER")
        for tool_id, fingerprint in self.tool_contract_digests.items():
            if not tool_id.strip() or not isinstance(fingerprint, str) or len(fingerprint) != 64:
                raise ValueError("SERVER_TOOL_CONTRACT_DIGEST_INVALID")
            if any(ch not in "0123456789abcdef" for ch in fingerprint.lower()):
                raise ValueError("SERVER_TOOL_CONTRACT_DIGEST_INVALID")


@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    server_id: str
    tool_id: str
    reasons: tuple[str, ...]
    contract_sha256: str = ""
    latency_ms: float | None = None
    health_status: str = "NOT_CHECKED"
    arcx_decision: str = "PENDING"
    eir_sha256: str = ""


@dataclass(frozen=True)
class VXToolResult:
    status: str
    request_id: str
    operation_id: str
    server_id: str
    tool_id: str
    reasons: tuple[str, ...]
    vx_phase: str
    output: Any = None
    output_sha256: str = ""
    tool_event_hash: str = ""
    compatibility: CompatibilityReport | None = None
    replay: tuple[Mapping[str, Any], ...] = ()
    eir_sha256: str = ""


@dataclass(frozen=True)
class _RegisteredServer:
    contract: ServerContract
    health_probe: HealthProbe


def _replay(operation: Operation) -> tuple[Mapping[str, Any], ...]:
    """Return supervisor replay with payloads already restricted by this fabric."""
    return tuple(
        {"seq": event.seq, "phase": event.phase.value, "name": event.name, "payload": dict(event.payload)}
        for event in operation.events
    )


def _operation_id(server_id: str, tool_id: str, principal_id: str, request_id: str) -> str:
    return "vx-tool-" + _sha256(canonical_json({
        "protocol": "vx.tool-fabric.v1",
        "server_id": server_id,
        "tool_id": tool_id,
        "principal_id": principal_id,
        "request_id": request_id,
    }))[:24]


class VXToolFabric:
    """Register compatible server/tool contracts and route invocations through VX.

    It deliberately delegates argument/scope/integration enforcement and
    hash-chained tool auditing to the existing ExecutionGateway. VXSupervisor
    remains the final authority/execution/verification state machine.
    """

    def __init__(
        self,
        gateway: ExecutionGateway,
        supervisor: VXSupervisor,
        *,
        health_probe: HealthProbe,
        integration_admission: IntegrationAdmission,
        arc_x_gate: ArcXPolicyGate,
    ) -> None:
        if not callable(health_probe) or not callable(integration_admission) or not callable(arc_x_gate):
            raise ValueError("TRUSTED_HEALTH_ARCX_AND_ADMISSION_CALLBACKS_REQUIRED")
        self.gateway = gateway
        self.supervisor = supervisor
        self.health_probe = health_probe
        self.integration_admission = integration_admission
        self.arc_x_gate = arc_x_gate
        self._servers: dict[str, _RegisteredServer] = {}
        self._request_fingerprints: dict[tuple[str, str, str, str], str] = {}

    def register_server(self, contract: ServerContract) -> None:
        """Register a declared contract only; registration is not admission."""
        if contract.server_id in self._servers:
            raise ValueError("DUPLICATE_SERVER_ID:" + contract.server_id)
        # Verify declarations against the actual registered tool specs before accepting the connector.
        for tool_id in contract.tool_ids:
            try:
                spec, _ = self.gateway.registry.get(tool_id)
            except KeyError as exc:
                raise ValueError("SERVER_REFERENCES_UNKNOWN_TOOL:" + tool_id) from exc
            if spec.external_integration_id != contract.integration_id:
                raise ValueError("TOOL_INTEGRATION_ID_MISMATCH:" + tool_id)
            if tool_contract_digest(spec) != contract.tool_contract_digests[tool_id]:
                raise ValueError("TOOL_CONTRACT_DIGEST_MISMATCH:" + tool_id)
        self._servers[contract.server_id] = _RegisteredServer(contract, self.health_probe)

    def list_servers(self) -> tuple[Mapping[str, Any], ...]:
        return tuple({
            "server_id": item.contract.server_id,
            "integration_id": item.contract.integration_id,
            "protocol": item.contract.protocol,
            "protocol_version": item.contract.protocol_version,
            "contract_version": item.contract.contract_version,
            "tool_ids": list(item.contract.tool_ids),
            "status": "DECLARED_NOT_ADMITTED",
        } for item in sorted(self._servers.values(), key=lambda value: value.contract.server_id))

    def check_compatibility(
        self,
        server_id: str,
        principal: Principal,
        tool_id: str,
        args: Mapping[str, Any],
    ) -> CompatibilityReport:
        reasons: list[str] = []
        registered = self._servers.get(server_id)
        if registered is None:
            return CompatibilityReport(False, server_id, tool_id, ("SERVER_UNKNOWN",))
        contract = registered.contract
        if tool_id not in contract.tool_ids:
            reasons.append("TOOL_NOT_DECLARED_BY_SERVER")
        try:
            spec, _ = self.gateway.registry.get(tool_id)
        except KeyError:
            return CompatibilityReport(False, server_id, tool_id, ("TOOL_UNKNOWN",))
        fingerprint = tool_contract_digest(spec)
        if contract.tool_contract_digests.get(tool_id) != fingerprint:
            reasons.append("TOOL_CONTRACT_DRIFT")
        if spec.external_integration_id != contract.integration_id:
            reasons.append("INTEGRATION_ID_MISMATCH")
        if not principal.active:
            reasons.append("PRINCIPAL_INACTIVE")
        missing_scopes = sorted(spec.required_scopes - principal.scopes)
        if missing_scopes:
            reasons.append("REQUIRED_SCOPE_MISSING:" + ",".join(missing_scopes))
        if any(not (group & principal.scopes) for group in spec.scope_groups):
            reasons.append("SCOPE_GROUP_NOT_SATISFIED")
        if not isinstance(args, Mapping):
            reasons.append("ARGUMENTS_NOT_OBJECT")
            arg_keys: set[str] = set()
        else:
            arg_keys = set(args)
        missing_inputs = sorted(spec.required_inputs - arg_keys)
        extra_inputs = sorted(arg_keys - spec.required_inputs - spec.optional_inputs)
        if missing_inputs:
            reasons.append("REQUIRED_INPUT_MISSING:" + ",".join(missing_inputs))
        if extra_inputs:
            reasons.append("UNDECLARED_INPUT:" + ",".join(extra_inputs))
        if not spec.enabled:
            reasons.append("TOOL_DISABLED")
        arcx_decision = "BLOCKED"
        eir_sha256 = ""
        try:
            policy = self.arc_x_gate(contract, spec, principal, args if isinstance(args, Mapping) else {})
            if not isinstance(policy, Mapping):
                reasons.append("ARC_X_POLICY_RESPONSE_NOT_OBJECT")
            else:
                arcx_decision = str(policy.get("decision", "PENDING"))
                eir_sha256 = str(policy.get("eir_sha256", ""))
                if policy.get("allowed") is not True or arcx_decision != "ADMITTED":
                    raw_codes = policy.get("reason_codes", ())
                    codes = [str(value) for value in raw_codes] if isinstance(raw_codes, (list, tuple)) else []
                    reasons.append("ARC_X_ADMISSION_REQUIRED" + (":" + ",".join(codes) if codes else ""))
                if len(eir_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in eir_sha256.lower()):
                    reasons.append("ARC_X_EIR_SHA256_REQUIRED")
        except Exception as exc:
            reasons.append("ARC_X_POLICY_GATE_FAILED:" + type(exc).__name__)
        if contract.integration_id:
            try:
                allowed = bool(self.integration_admission(contract.integration_id))
            except Exception:
                allowed = False
            if not allowed:
                reasons.append("INTEGRATION_NOT_ADMITTED")

        latency: float | None = None
        health_status = "FAILED"
        try:
            health = registered.health_probe(contract)
            if not isinstance(health, Mapping):
                reasons.append("HEALTH_RESPONSE_NOT_OBJECT")
            else:
                healthy = health.get("healthy") is True
                protocol_ok = health.get("protocol") == contract.protocol
                protocol_version_ok = health.get("protocol_version") == contract.protocol_version
                contract_version_ok = health.get("contract_version") == contract.contract_version
                raw_latency = health.get("latency_ms")
                valid_latency = (
                    isinstance(raw_latency, (int, float))
                    and not isinstance(raw_latency, bool)
                    and raw_latency >= 0
                )
                latency = float(raw_latency) if valid_latency else None
                if not healthy:
                    reasons.append("SERVER_UNHEALTHY")
                if not protocol_ok:
                    reasons.append("PROTOCOL_MISMATCH")
                if not protocol_version_ok:
                    reasons.append("PROTOCOL_VERSION_MISMATCH")
                if not contract_version_ok:
                    reasons.append("SERVER_CONTRACT_VERSION_MISMATCH")
                if not valid_latency:
                    reasons.append("LATENCY_MEASUREMENT_INVALID")
                elif latency > contract.max_latency_ms:
                    reasons.append("LATENCY_BUDGET_EXCEEDED")
                if healthy and protocol_ok and protocol_version_ok and contract_version_ok and valid_latency and latency <= contract.max_latency_ms:
                    health_status = "HEALTHY"
                else:
                    health_status = "INCOMPATIBLE"
        except Exception as exc:
            reasons.append("HEALTH_PROBE_FAILED:" + type(exc).__name__)
        return CompatibilityReport(
            compatible=not reasons,
            server_id=server_id,
            tool_id=tool_id,
            reasons=tuple(reasons),
            contract_sha256=fingerprint,
            latency_ms=latency,
            health_status=health_status,
            arcx_decision=arcx_decision,
            eir_sha256=eir_sha256,
        )

    def invoke(
        self,
        server_id: str,
        principal: Principal,
        tool_id: str,
        args: Mapping[str, Any],
        *,
        request_id: str,
        objective: str,
    ) -> VXToolResult:
        """Invoke one registered tool through preflight, VX authorization and VX verification.

        Request IDs are at-most-once per connector/tool/principal. Failed or repeated
        operations are never silently replayed, and raw args/tool outputs are not copied
        into VX event payloads. ExecutionGateway still records its own args/output hashes.
        """
        if not isinstance(request_id, str) or not request_id.strip():
            return VXToolResult("BLOCKED", str(request_id), "", server_id, tool_id, ("REQUEST_ID_REQUIRED",), "")
        if not objective.strip():
            return VXToolResult("BLOCKED", request_id, "", server_id, tool_id, ("OBJECTIVE_REQUIRED",), "")
        operation_id = _operation_id(server_id, tool_id, principal.principal_id, request_id)
        request_key = (server_id, tool_id, principal.principal_id, request_id)
        args_hash = _sha256(canonical_json(args if isinstance(args, Mapping) else {"invalid_args_type": type(args).__name__}))
        prior = self._request_fingerprints.get(request_key)
        if prior is not None:
            reason = "DUPLICATE_REQUEST_REPLAY_BLOCKED" if prior == args_hash else "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
            operation = self.supervisor.operations.get(operation_id)
            return VXToolResult(
                "BLOCKED", request_id, operation_id, server_id, tool_id, (reason,),
                operation.phase.value if operation else "",
                replay=_replay(operation) if operation else (),
            )
        self._request_fingerprints[request_key] = args_hash

        op = self.supervisor.prepare(
            operation_id,
            objective,
            {
                "fabric": "vx.tool-fabric.v1",
                "server_id": server_id,
                "tool_id": tool_id,
                "principal_id": principal.principal_id,
                "request_id": request_id,
                "args_sha256": args_hash,
            },
        )
        report = self.check_compatibility(server_id, principal, tool_id, args)
        op.snapshot["contract_sha256"] = report.contract_sha256
        op.snapshot["arcx_eir_sha256"] = report.eir_sha256
        op.snapshot["arcx_decision"] = report.arcx_decision
        if not report.compatible:
            op.transition(Phase.FAILED, "tool_compatibility_blocked", {
                "reasons": list(report.reasons),
                "contract_sha256": report.contract_sha256,
                "health_status": report.health_status,
            })
            return VXToolResult(
                "BLOCKED", request_id, operation_id, server_id, tool_id, report.reasons,
                op.phase.value, compatibility=report, replay=_replay(op), eir_sha256=report.eir_sha256,
            )

        self.supervisor.simulate(op, {
            "simulation_kind": "PREFLIGHT_ONLY",
            "compatible": True,
            "contract_sha256": report.contract_sha256,
        })
        self.supervisor.test(op, {
            "contract_test": "PASS",
            "health_status": report.health_status,
            "latency_ms": report.latency_ms,
        })

        if not self.supervisor.authorize(op):
            return VXToolResult(
                "BLOCKED", request_id, operation_id, server_id, tool_id,
                ("VX_AUTHORIZER_DENIED",), op.phase.value,
                compatibility=report, replay=_replay(op), eir_sha256=report.eir_sha256,
            )

        tool_result_box: dict[str, Any] = {}

        def dispatch(_operation: Operation) -> Mapping[str, Any]:
            result = self.gateway.call(
                principal, tool_id, args,
                request_id="vx:" + request_id,
            )
            tool_result_box["result"] = result
            output_digest = _sha256(canonical_json(result.output)) if result.output is not None else ""
            return {
                "ok": result.status == "SUCCESS",
                "tool_status": result.status,
                "reason_code": result.reason_code,
                "tool_event_hash": result.event_hash,
                "output_sha256": output_digest,
            }

        def verify(_operation: Operation, result: Mapping[str, Any]) -> bool:
            if result.get("ok") is not True or result.get("tool_status") != "SUCCESS":
                return False
            event_hash = result.get("tool_event_hash")
            if not isinstance(event_hash, str) or len(event_hash) != 64:
                return False
            output_hash = result.get("output_sha256")
            return isinstance(output_hash, str) and (output_hash == "" or (
                len(output_hash) == 64 and all(ch in "0123456789abcdef" for ch in output_hash.lower())
            ))

        # Use a per-operation dispatcher rather than mutating the supervisor's
        # shared executor. Both VX's base verifier and this request-bound gate run.
        runtime_result = self.supervisor.execute(op, executor=dispatch, additional_verifier=verify)
        tool_result = tool_result_box.get("result")
        replay = _replay(op)
        if (
            op.phase is not Phase.VERIFIED
            or tool_result is None
            or not isinstance(runtime_result, Mapping)
            or runtime_result.get("tool_status") != "SUCCESS"
        ):
            return VXToolResult(
                "EXECUTION_FAILED", request_id, operation_id, server_id, tool_id,
                ("VX_RUNTIME_DID_NOT_VERIFY_EXECUTION",), op.phase.value,
                compatibility=report, replay=replay, eir_sha256=report.eir_sha256,
            )
        # Return output to the authorized caller, but do not insert it into VX event payloads.
        return VXToolResult(
            "VX_TOOL_COMPLETED", request_id, operation_id, server_id, tool_id,
            ("VX_SUPERVISOR_VERIFIED", "EXECUTION_GATEWAY_SUCCESS"),
            op.phase.value, output=tool_result.output,
            output_sha256=_sha256(canonical_json(tool_result.output)) if tool_result.output is not None else "",
            tool_event_hash=tool_result.event_hash,
            compatibility=report, replay=replay, eir_sha256=report.eir_sha256,
        )


__all__ = [
    "CompatibilityReport", "ServerContract", "VXToolFabric", "VXToolResult",
    "tool_contract_digest",
]
