"""Canonical authority contract bridging VX execution with constitutional rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.identity import Identity, Permission
from core.sovereign_constitution import SovereignConstitution


@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    reason: str
    actor_id: str
    capability: str


class ConstitutionAuthorizer:
    def __init__(self, constitution: SovereignConstitution) -> None:
        self.constitution = constitution

    def decide(
        self,
        actor: Identity,
        capability: str,
        operation: Mapping[str, Any] | None = None,
    ) -> AuthorityDecision:
        if not actor.active:
            return AuthorityDecision(False, "INACTIVE_IDENTITY", actor.id, capability)
        if not actor.has_permission(Permission.EXECUTE):
            return AuthorityDecision(False, "EXECUTE_PERMISSION_REQUIRED", actor.id, capability)
        if not actor.has_capability(capability):
            return AuthorityDecision(False, "CAPABILITY_REQUIRED", actor.id, capability)
        for category in ("security", "execution", "governance", "data", "determinism"):
            if not self.constitution.verify_compliance(category):
                return AuthorityDecision(False, f"CONSTITUTION_NON_COMPLIANT:{category}", actor.id, capability)
        return AuthorityDecision(True, "AUTHORIZED", actor.id, capability)
