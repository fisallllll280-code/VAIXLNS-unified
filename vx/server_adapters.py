"""Concrete adapters for already-defined VAIXLNS server boundaries.

Adapters register a typed ToolSpec only. They do not enable the integration,
grant ARC-X admission, configure secrets, or bypass VX/ExecutionGateway gates.
"""
from __future__ import annotations

from typing import Any, Mapping

from tools.execution_fabric import ToolRegistry, ToolSpec
from vlns.activation import ActivationRequest, VLNSActivationBridge


VLNS_ACTIVATION_TOOL_ID = "vlns.activation.activate_model"
VLNS_ACTIVATION_INTEGRATION_ID = "vlns-control"

_VLNS_REQUIRED_INPUTS = frozenset({
    "model_id",
    "provider",
    "model_version",
    "role",
    "capability_profile",
    "context_payload",
    "tool_profile",
    "requested_permissions",
    "constraints",
    "provenance",
})


def _strings(value: Any, field: str, *, required: bool = False) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(field.upper() + "_MUST_BE_STRING_ARRAY")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(field.upper() + "_CONTAINS_INVALID_STRING")
    result = tuple(value)
    if required and not result:
        raise ValueError(field.upper() + "_REQUIRED")
    return result


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field.upper() + "_REQUIRED")
    return value.strip()


def register_vlns_activation_tool(
    registry: ToolRegistry,
    bridge: VLNSActivationBridge,
    *,
    tool_id: str = VLNS_ACTIVATION_TOOL_ID,
    integration_id: str = VLNS_ACTIVATION_INTEGRATION_ID,
    required_scopes: frozenset[str] = frozenset({"request:vlns-activation"}),
    enabled: bool = False,
) -> ToolSpec:
    """Register VLNS activation behind VX with opt-in enablement.

    A successful handler result requires both a validated remote activation
    receipt and a successful local VX evidence-recorder acknowledgment. Pending,
    rejected, unconfigured, and transport-failure outcomes become BLOCKED at the
    gateway boundary rather than a misleading SUCCESS.
    """
    if not callable(getattr(bridge, "activate", None)):
        raise ValueError("VLNS_ACTIVATION_BRIDGE_REQUIRED")
    spec = ToolSpec(
        tool_id=tool_id,
        description="Request a policy-governed VLNS model activation and record its receipt.",
        required_inputs=_VLNS_REQUIRED_INPUTS,
        required_scopes=required_scopes,
        enabled=enabled,
        risk="CRITICAL",
        external_integration_id=integration_id,
        max_output_bytes=4096,
        read_only=False,
    )

    def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        request = ActivationRequest(
            model_id=_required_text(args["model_id"], "model_id"),
            provider=_required_text(args["provider"], "provider"),
            model_version=_required_text(args["model_version"], "model_version"),
            role=_required_text(args["role"], "role"),
            capability_profile=_strings(args["capability_profile"], "capability_profile", required=True),
            context_payload=args["context_payload"],
            tool_profile=_strings(args["tool_profile"], "tool_profile"),
            requested_permissions=_strings(args["requested_permissions"], "requested_permissions", required=True),
            constraints=_strings(args["constraints"], "constraints", required=True),
            provenance=args["provenance"],
        )
        outcome = bridge.activate(request)
        if (
            getattr(outcome, "status", "") != "ACTIVATED_AND_RECORDED"
            or getattr(outcome, "activated", False) is not True
            or getattr(outcome, "evidence_recorded", False) is not True
        ):
            status = str(getattr(outcome, "status", "INVALID_ACTIVATION_OUTCOME"))
            raise PermissionError("VLNS_ACTIVATION_NOT_FULLY_RECORDED:" + status)
        # Do not return the signed envelope, context, tokens or arbitrary remote payload.
        return {
            "status": "ACTIVATED_AND_RECORDED",
            "activation_id": str(outcome.activation_id),
            "envelope_hash": str(outcome.envelope_hash),
            "activated": True,
            "evidence_recorded": True,
        }

    registry.register(spec, handler)
    return spec


__all__ = [
    "VLNS_ACTIVATION_INTEGRATION_ID",
    "VLNS_ACTIVATION_TOOL_ID",
    "register_vlns_activation_tool",
]
