"""Minimal executable policy/authority gate.

This is intentionally narrow: it answers whether an already-identified actor
may invoke a registered capability. It does not claim constitutional
completeness or distributed consensus.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Policy:
    policy_id: str
    allowed_capabilities: frozenset[str] = frozenset()
    denied_capabilities: frozenset[str] = frozenset()
    required_permissions: frozenset[str] = frozenset()

@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    reason: str
    policy_id: str

class GovernanceEngine:
    def __init__(self, default_policy: Policy | None = None) -> None:
        self.default_policy = default_policy or Policy(policy_id="default")

    def evaluate(
        self,
        *,
        actor_id: str,
        permissions: set[str] | frozenset[str],
        capability: str,
        policy: Policy | None = None,
        context: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        if not actor_id:
            return GovernanceDecision(False, "IDENTITY_REQUIRED", (policy or self.default_policy).policy_id)

        active = policy or self.default_policy
        if capability in active.denied_capabilities:
            return GovernanceDecision(False, "CAPABILITY_DENIED", active.policy_id)
        if active.allowed_capabilities and capability not in active.allowed_capabilities:
            return GovernanceDecision(False, "CAPABILITY_NOT_IN_POLICY", active.policy_id)
        if not set(active.required_permissions).issubset(set(permissions)):
            return GovernanceDecision(False, "REQUIRED_PERMISSION_MISSING", active.policy_id)

        return GovernanceDecision(True, "ALLOW", active.policy_id)
