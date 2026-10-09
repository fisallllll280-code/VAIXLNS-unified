"""Governed VLNS model activation envelope and fail-closed VX bridge.

This module prepares a deterministic activation request. A model is not considered
activated until a configured VLNS endpoint returns a receipt bound to the exact
signed envelope and VAIXLNS records the corresponding evidence event.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
from typing import Any, Mapping, Protocol


SCHEMA_VERSION = "vlns.activation-envelope.v1"
SIGNATURE_ALGORITHM = "HMAC-SHA256"
KNOWN_PERMISSIONS = frozenset({"read", "propose", "execute", "modify"})
NON_DELEGABLE_PERMISSIONS = frozenset({
    "external_action", "canonical_write", "governance_override", "unrestricted_network"
})
ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    role: frozenset({"read", "propose"})
    for role in (
        "reasoning_mind", "architecture_mind", "adversary_mind", "verifier_mind",
        "recovery_mind", "security_mind", "innovation_mind", "research_mind",
    )
}
IDENTITY_FIELDS = (
    "schema_version", "model_id", "provider", "model_version", "role",
    "capability_profile", "context_hash", "tool_profile", "permission_profile",
    "constraints", "provenance",
)
ENVELOPE_FIELDS = frozenset((*IDENTITY_FIELDS, "activation_id", "status", "signature_algorithm", "signature"))


class ActivationError(ValueError):
    """An activation request violates the contract or configured policy."""


class ActivationTransport(Protocol):
    @property
    def configured(self) -> bool: ...
    def activate_model(self, envelope: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def emit_event(self, event: Mapping[str, Any]) -> Mapping[str, Any]: ...


def canonical_json(value: Any) -> str:
    """Serialize only JSON data in a stable, non-lossy form."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ActivationError("NON_CANONICAL_JSON_INPUT") from exc


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def envelope_hash(envelope: Mapping[str, Any]) -> str:
    return content_hash(dict(envelope))


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActivationError(f"{name.upper()}_REQUIRED")
    return value.strip()


def _string_tuple(values: Any, name: str, *, required: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple, set, frozenset)):
        raise ActivationError(f"{name.upper()}_MUST_BE_STRING_LIST")
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ActivationError(f"{name.upper()}_CONTAINS_INVALID_VALUE")
        cleaned.append(value.strip())
    result = tuple(sorted(set(cleaned)))
    if required and not result:
        raise ActivationError(f"{name.upper()}_REQUIRED")
    return result


def _mapping_copy(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ActivationError(f"{name.upper()}_MUST_BE_OBJECT")
    try:
        return json.loads(canonical_json(dict(value)))
    except (json.JSONDecodeError, ActivationError) as exc:
        raise ActivationError(f"{name.upper()}_MUST_BE_JSON_DATA") from exc


@dataclass(frozen=True)
class ActivationPolicy:
    """Allowlist policy. Dangerous authority is deliberately non-delegable to models."""

    allowed_providers: frozenset[str]
    allowed_capabilities: frozenset[str]
    allowed_tools: frozenset[str] = frozenset()
    role_permissions: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: dict(ROLE_DEFAULT_PERMISSIONS)
    )

    def __post_init__(self) -> None:
        providers = frozenset(_string_tuple(self.allowed_providers, "allowed_providers"))
        capabilities = frozenset(_string_tuple(self.allowed_capabilities, "allowed_capabilities"))
        tools = frozenset(_string_tuple(self.allowed_tools, "allowed_tools"))
        if not isinstance(self.role_permissions, Mapping) or not self.role_permissions:
            raise ActivationError("ROLE_PERMISSION_POLICY_REQUIRED")
        normalized: dict[str, frozenset[str]] = {}
        for role, permissions in self.role_permissions.items():
            role_name = _required_text(role, "role")
            granted = frozenset(_string_tuple(permissions, "role_permissions"))
            unknown = granted - KNOWN_PERMISSIONS
            if unknown:
                raise ActivationError("UNKNOWN_ROLE_PERMISSION:" + ",".join(sorted(unknown)))
            if granted & NON_DELEGABLE_PERMISSIONS:
                raise ActivationError("NON_DELEGABLE_PERMISSION_IN_ROLE_POLICY")
            normalized[role_name] = granted
        object.__setattr__(self, "allowed_providers", providers)
        object.__setattr__(self, "allowed_capabilities", capabilities)
        object.__setattr__(self, "allowed_tools", tools)
        object.__setattr__(self, "role_permissions", normalized)

    def validate_request(self, request: "ActivationRequest") -> dict[str, Any]:
        model_id = _required_text(request.model_id, "model_id")
        provider = _required_text(request.provider, "provider")
        version = _required_text(request.model_version, "model_version")
        role = _required_text(request.role, "role")
        if provider not in self.allowed_providers:
            raise ActivationError("PROVIDER_NOT_ALLOWLISTED")
        if role not in self.role_permissions:
            raise ActivationError("ROLE_NOT_ALLOWLISTED")
        capabilities = _string_tuple(request.capability_profile, "capability_profile", required=True)
        forbidden_capabilities = set(capabilities) - set(self.allowed_capabilities)
        if forbidden_capabilities:
            raise ActivationError("CAPABILITY_NOT_ALLOWLISTED:" + ",".join(sorted(forbidden_capabilities)))
        tools = _string_tuple(request.tool_profile, "tool_profile")
        forbidden_tools = set(tools) - set(self.allowed_tools)
        if forbidden_tools:
            raise ActivationError("TOOL_NOT_ALLOWLISTED:" + ",".join(sorted(forbidden_tools)))
        requested = _string_tuple(request.requested_permissions, "requested_permissions", required=True)
        granted = self.role_permissions[role]
        if set(requested) - set(granted):
            raise ActivationError("ROLE_PERMISSION_ESCALATION")
        if set(requested) & NON_DELEGABLE_PERMISSIONS:
            raise ActivationError("NON_DELEGABLE_PERMISSION_REQUESTED")
        constraints = _string_tuple(request.constraints, "constraints", required=True)
        provenance = _mapping_copy(request.provenance, "provenance")
        for required_key in ("task_id", "source_id", "source_digest"):
            _required_text(provenance.get(required_key), "provenance." + required_key)
        context_hash = content_hash(request.context_payload)
        return {
            "schema_version": SCHEMA_VERSION,
            "model_id": model_id,
            "provider": provider,
            "model_version": version,
            "role": role,
            "capability_profile": list(capabilities),
            "context_hash": context_hash,
            "tool_profile": list(tools),
            "permission_profile": list(requested),
            "constraints": list(constraints),
            "provenance": provenance,
        }


@dataclass(frozen=True)
class ActivationRequest:
    model_id: str
    provider: str
    model_version: str
    role: str
    capability_profile: tuple[str, ...]
    context_payload: Any
    tool_profile: tuple[str, ...] = ()
    requested_permissions: tuple[str, ...] = ("read", "propose")
    constraints: tuple[str, ...] = ("no_unreviewed_execution", "no_canonical_mutation")
    provenance: Mapping[str, Any] = field(default_factory=dict)


def prepare_activation(
    request: ActivationRequest,
    policy: ActivationPolicy,
    signing_key: bytes,
) -> dict[str, Any]:
    """Create a deterministic, signed envelope; do not send it to a remote service."""
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise ActivationError("SIGNING_KEY_MUST_BE_AT_LEAST_32_BYTES")
    identity = policy.validate_request(request)
    activation_id = "VLNS-ACT-" + content_hash(identity)[:24]
    envelope: dict[str, Any] = {
        **identity,
        "activation_id": activation_id,
        "status": "PREPARED",
        "signature_algorithm": SIGNATURE_ALGORITHM,
    }
    envelope["signature"] = hmac.new(
        signing_key, canonical_json(envelope).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return envelope


def verify_activation_envelope(envelope: Mapping[str, Any], signing_key: bytes) -> bool:
    """Verify schema boundary, deterministic identity, and HMAC signature."""
    if not isinstance(envelope, Mapping) or set(envelope) != ENVELOPE_FIELDS:
        return False
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        return False
    if envelope.get("schema_version") != SCHEMA_VERSION:
        return False
    if envelope.get("status") != "PREPARED" or envelope.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        return False
    signature = envelope.get("signature")
    if not isinstance(signature, str) or len(signature) != 64:
        return False
    identity = {key: envelope.get(key) for key in IDENTITY_FIELDS}
    if envelope.get("activation_id") != "VLNS-ACT-" + content_hash(identity)[:24]:
        return False
    unsigned = dict(envelope)
    unsigned.pop("signature", None)
    expected = hmac.new(
        signing_key, canonical_json(unsigned).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class ActivationOutcome:
    status: str
    activation_id: str
    envelope_hash: str
    activated: bool = False
    evidence_recorded: bool = False
    reason: str = ""
    envelope: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VLNSActivationBridge:
    """Prepare, authorize, dispatch, bind the remote receipt, then record evidence."""

    def __init__(
        self,
        client: ActivationTransport,
        policy: ActivationPolicy,
        signing_key: bytes,
    ) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ActivationError("SIGNING_KEY_MUST_BE_AT_LEAST_32_BYTES")
        self.client = client
        self.policy = policy
        self.signing_key = signing_key

    def activate(self, request: ActivationRequest) -> ActivationOutcome:
        envelope = prepare_activation(request, self.policy, self.signing_key)
        digest = envelope_hash(envelope)
        activation_id = str(envelope["activation_id"])
        if not self.client.configured:
            return ActivationOutcome(
                "PREPARED_NOT_DISPATCHED", activation_id, digest,
                reason="VLNS_SERVER_NOT_CONFIGURED", envelope=envelope,
            )
        try:
            response = self.client.activate_model(envelope)
        except Exception as exc:
            return ActivationOutcome(
                "TRANSPORT_FAILED", activation_id, digest,
                reason="ACTIVATION_TRANSPORT_EXCEPTION:" + type(exc).__name__, envelope=envelope,
            )
        if not isinstance(response, Mapping) or not response.get("ok"):
            status = str(response.get("status", "TRANSPORT_FAILED")) if isinstance(response, Mapping) else "INVALID_TRANSPORT_RESPONSE"
            return ActivationOutcome(
                "TRANSPORT_FAILED", activation_id, digest,
                reason=status, envelope=envelope,
            )
        data = response.get("data")
        if not isinstance(data, Mapping):
            return ActivationOutcome(
                "RECEIPT_INVALID", activation_id, digest,
                reason="REMOTE_RECEIPT_MUST_BE_OBJECT", envelope=envelope,
            )
        if data.get("status") != "ACTIVATED":
            return ActivationOutcome(
                "REMOTE_REJECTED", activation_id, digest,
                reason=str(data.get("reason", data.get("status", "REMOTE_DID_NOT_ACTIVATE"))),
                envelope=envelope,
            )
        if data.get("activation_id") != activation_id or data.get("envelope_hash") != digest:
            return ActivationOutcome(
                "RECEIPT_INVALID", activation_id, digest,
                reason="RECEIPT_ID_OR_ENVELOPE_HASH_MISMATCH", envelope=envelope,
            )

        event = {
            "event_type": "VLNS_MODEL_ACTIVATION_CONFIRMED",
            "activation_id": activation_id,
            "envelope_hash": digest,
            "provider": envelope["provider"],
            "model_id": envelope["model_id"],
            "model_version": envelope["model_version"],
            "role": envelope["role"],
            "context_hash": envelope["context_hash"],
            "provenance": envelope["provenance"],
            "evidence_status": "REMOTE_RECEIPT_VALIDATED",
        }
        try:
            recorded = self.client.emit_event(event)
        except Exception as exc:
            recorded = {"ok": False, "status": "EVENT_TRANSPORT_EXCEPTION:" + type(exc).__name__}
        if not isinstance(recorded, Mapping) or not recorded.get("ok"):
            reason = str(recorded.get("status", "EVENT_RECORDING_FAILED")) if isinstance(recorded, Mapping) else "INVALID_EVENT_RESPONSE"
            return ActivationOutcome(
                "ACTIVATED_EVIDENCE_PENDING", activation_id, digest,
                activated=True, evidence_recorded=False, reason=reason, envelope=envelope,
            )
        return ActivationOutcome(
            "ACTIVATED_AND_RECORDED", activation_id, digest,
            activated=True, evidence_recorded=True, reason="REMOTE_RECEIPT_AND_EVIDENCE_CONFIRMED",
            envelope=envelope,
        )


__all__ = [
    "ActivationError", "ActivationOutcome", "ActivationPolicy", "ActivationRequest",
    "ROLE_DEFAULT_PERMISSIONS", "VLNSActivationBridge", "canonical_json", "content_hash",
    "envelope_hash", "prepare_activation", "verify_activation_envelope",
]
