"""VAIXLNS Finality Gate V1 reference implementation.

This module is intentionally small: it evaluates a scope-bound certificate
without becoming a governance authority or a repository repair engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class FinalityStatus(str, Enum):
    OPERATIONALLY_FINAL = "OPERATIONALLY_FINAL"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class FinalityScope:
    environment: str
    authority_domain: str
    capability_scope: tuple[str, ...]
    dependency_set: tuple[str, ...]
    policy_set: tuple[str, ...]
    validity_not_after: str | None = None


@dataclass(frozen=True)
class FinalityCertificate:
    entity_uid: str
    canonical_version: str
    scope: FinalityScope
    checks: Mapping[str, bool]
    evidence_root: str
    proof_root: str
    verifier: str
    verification_version: str
    unresolved_conflicts: int = 0
    critical_findings: int = 0
    status: FinalityStatus = FinalityStatus.REVALIDATION_REQUIRED

    def is_complete(self) -> bool:
        return (
            bool(self.entity_uid)
            and bool(self.canonical_version)
            and bool(self.scope.environment)
            and bool(self.scope.authority_domain)
            and bool(self.scope.evidence_required())
            and bool(self.checks)
            and all(self.checks.values())
            and bool(self.evidence_root)
            and bool(self.proof_root)
            and bool(self.verifier)
            and bool(self.verification_version)
            and self.unresolved_conflicts == 0
            and self.critical_findings == 0
        )

    def with_evaluated_status(self) -> "FinalityCertificate":
        status = (
            FinalityStatus.OPERATIONALLY_FINAL
            if self.is_complete()
            else FinalityStatus.REVALIDATION_REQUIRED
        )
        return FinalityCertificate(
            **{**self.__dict__, "status": status}
        )


def _scope_items(value: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(value)))


def build_scope(
    *,
    environment: str,
    authority_domain: str,
    capability_scope: Sequence[str] = (),
    dependency_set: Sequence[str] = (),
    policy_set: Sequence[str] = (),
    validity_not_after: str | None = None,
) -> FinalityScope:
    return FinalityScope(
        environment=environment,
        authority_domain=authority_domain,
        capability_scope=_scope_items(capability_scope),
        dependency_set=_scope_items(dependency_set),
        policy_set=_scope_items(policy_set),
        validity_not_after=validity_not_after,
    )


def invalidate_on_material_change(
    certificate: FinalityCertificate,
    *,
    changed_fields: Sequence[str],
    invalidation_rules: Sequence[str] = (
        "implementation",
        "specification",
        "dependency",
        "environment",
        "policy",
        "contract",
        "authority_boundary",
        "security_baseline",
        "model_runtime",
        "critical_evidence",
    ),
) -> FinalityCertificate:
    changed = set(changed_fields)
    material = changed & set(invalidation_rules)
    if not material:
        return certificate

    return FinalityCertificate(
        **{**certificate.__dict__, "status": FinalityStatus.INVALIDATED}
    )


# Small helper kept on the scope object to make completeness explicit.
def _evidence_required(self: FinalityScope) -> bool:
    return bool(self.environment and self.authority_domain)


FinalityScope.evidence_required = _evidence_required  # type: ignore[attr-defined]
