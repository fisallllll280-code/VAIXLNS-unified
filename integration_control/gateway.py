"""Ω External Integration Control V1.

No external model, provider, API, connector, server, tool, or remote service
may become part of VAIXLNS merely because it is reachable.

Every external integration is an untrusted capability crossing the canonical
boundary. It must be identified, contract-bound, policy-gated, sandboxed,
observed, verified, revocable, and prevented from self-promoting into canon.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence


class IntegrationClass(str, Enum):
    MODEL = "MODEL"
    API = "API"
    SERVER = "SERVER"
    TOOL = "TOOL"
    CONNECTOR = "CONNECTOR"
    REPOSITORY = "REPOSITORY"
    DATA_SOURCE = "DATA_SOURCE"


class IntegrationState(str, Enum):
    PROPOSED = "PROPOSED"
    DISCOVERED = "DISCOVERED"
    QUARANTINED = "QUARANTINED"
    VERIFIED = "VERIFIED"
    ADMITTED = "ADMITTED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ExternalIntegration:
    integration_id: str
    name: str
    kind: IntegrationClass
    endpoint: str
    capabilities: tuple[str, ...]
    contract_version: str
    dependency_fingerprint: str
    environment_fingerprint: str
    owner: str = ""
    lineage: tuple[str, ...] = ()

    @property
    def identity(self) -> str:
        payload = {
            "integration_id": self.integration_id,
            "name": self.name,
            "kind": self.kind.value,
            "endpoint": self.endpoint,
            "capabilities": self.capabilities,
            "contract_version": self.contract_version,
            "dependency_fingerprint": self.dependency_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "owner": self.owner,
            "lineage": self.lineage,
        }
        return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class IntegrationDecision:
    integration_id: str
    state: IntegrationState
    allowed_capabilities: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IntegrationPolicy:
    allowed_kinds: frozenset[IntegrationClass]
    allowed_capabilities: frozenset[str]
    forbidden_endpoints: frozenset[str] = frozenset()
    require_owner: bool = True
    require_contract: bool = True
    require_dependency_fingerprint: bool = True
    require_environment_fingerprint: bool = True


class ExternalIntegrationGate:
    """Default-deny admission boundary for every external dependency."""

    def admit(
        self,
        integration: ExternalIntegration,
        policy: IntegrationPolicy,
        *,
        verified: bool = False,
        explicit_authority: bool = False,
    ) -> IntegrationDecision:
        reasons: list[str] = []

        if integration.kind not in policy.allowed_kinds:
            reasons.append("KIND_FORBIDDEN")
        if integration.endpoint in policy.forbidden_endpoints:
            reasons.append("ENDPOINT_FORBIDDEN")
        if policy.require_owner and not integration.owner:
            reasons.append("OWNER_MISSING")
        if policy.require_contract and not integration.contract_version:
            reasons.append("CONTRACT_MISSING")
        if policy.require_dependency_fingerprint and not integration.dependency_fingerprint:
            reasons.append("DEPENDENCY_FINGERPRINT_MISSING")
        if policy.require_environment_fingerprint and not integration.environment_fingerprint:
            reasons.append("ENVIRONMENT_FINGERPRINT_MISSING")

        unauthorized = tuple(sorted(set(integration.capabilities) - set(policy.allowed_capabilities)))
        if unauthorized:
            reasons.extend(f"CAPABILITY_FORBIDDEN:{cap}" for cap in unauthorized)

        if reasons:
            return IntegrationDecision(
                integration.integration_id,
                IntegrationState.QUARANTINED,
                (),
                tuple(reasons),
            )

        if not verified:
            return IntegrationDecision(
                integration.integration_id,
                IntegrationState.DISCOVERED,
                (),
                ("VERIFICATION_REQUIRED",),
            )

        if not explicit_authority:
            return IntegrationDecision(
                integration.integration_id,
                IntegrationState.VERIFIED,
                tuple(sorted(integration.capabilities)),
                ("EXPLICIT_AUTHORITY_REQUIRED",),
            )

        return IntegrationDecision(
            integration.integration_id,
            IntegrationState.ADMITTED,
            tuple(sorted(integration.capabilities)),
            ("ADMITTED",),
        )


class ExternalCallBoundary:
    """Runtime boundary: only capabilities explicitly admitted may be invoked."""

    def authorize(
        self,
        integration: ExternalIntegration,
        decision: IntegrationDecision,
        capability: str,
    ) -> bool:
        return (
            decision.integration_id == integration.integration_id
            and decision.state is IntegrationState.ADMITTED
            and capability in decision.allowed_capabilities
        )


__all__ = [
    "ExternalCallBoundary",
    "ExternalIntegration",
    "ExternalIntegrationGate",
    "IntegrationClass",
    "IntegrationDecision",
    "IntegrationPolicy",
    "IntegrationState",
]
