"""Ω³ Sovereign Reality Kernel: deterministic, fail-closed admission primitives.

This module evaluates a proposed state transition. It does not persist state,
invoke tools, execute commands, or commit a canonical transition. Cryptographic
authenticity must be supplied by independent verifier callbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


GENESIS_HASH = "GENESIS"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AdmissionStatus(str, Enum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"
    QUARANTINE = "QUARANTINE"


def _freeze(value: Any) -> Any:
    """Recursively freeze JSON-compatible values to prevent caller mutation."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JSON_OBJECT_KEYS_MUST_BE_STRINGS")
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NON_FINITE_NUMBER_NOT_CANONICAL")
        return value
    raise TypeError(f"NON_JSON_VALUE:{type(value).__name__}")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically; NaN/Infinity are rejected."""
    return json.dumps(
        _thaw(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def is_sha256(value: str) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def parse_timestamp(value: str) -> datetime:
    """Parse a timezone-aware ISO-8601 timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not value:
        raise ValueError("TIMESTAMP_REQUIRED")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SovereignState:
    """Versioned state S=(G,C,R,O,E); this object is a proposal/snapshot only."""

    object_id: str
    revision: int
    identity: Mapping[str, Any]
    contracts: Mapping[str, Any]
    authority: Mapping[str, Any]
    observations: tuple[Mapping[str, Any], ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id.strip():
            raise ValueError("OBJECT_ID_REQUIRED")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise ValueError("REVISION_MUST_BE_NONNEGATIVE_INTEGER")
        for name in ("identity", "contracts", "authority"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{name.upper()}_MUST_BE_OBJECT")
            object.__setattr__(self, name, _freeze(value))
        frozen_observations = tuple(_freeze(item) for item in self.observations)
        if any(not isinstance(item, Mapping) for item in frozen_observations):
            raise TypeError("OBSERVATIONS_MUST_BE_OBJECTS")
        object.__setattr__(self, "observations", frozen_observations)
        refs = tuple(self.evidence_refs)
        if any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValueError("EVIDENCE_REFERENCE_REQUIRED")
        if len(set(refs)) != len(refs):
            raise ValueError("DUPLICATE_EVIDENCE_REFERENCE")
        object.__setattr__(self, "evidence_refs", refs)

    def to_payload(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "revision": self.revision,
            "identity": _thaw(self.identity),
            "contracts": _thaw(self.contracts),
            "authority": _thaw(self.authority),
            "observations": _thaw(self.observations),
            "evidence_refs": list(self.evidence_refs),
        }

    @property
    def digest(self) -> str:
        return digest_json(self.to_payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SovereignState":
        return cls(
            object_id=payload["object_id"],
            revision=payload["revision"],
            identity=payload["identity"],
            contracts=payload["contracts"],
            authority=payload["authority"],
            observations=tuple(payload.get("observations", ())),
            evidence_refs=tuple(payload.get("evidence_refs", ())),
        )


@dataclass(frozen=True)
class AuthorityGrant:
    grant_id: str
    principal_id: str
    subject_id: str
    action: str
    scopes: tuple[str, ...]
    policy_version: str
    issued_at: str
    expires_at: str
    verification_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "scopes", tuple(self.scopes))

    def to_payload(self) -> dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "principal_id": self.principal_id,
            "subject_id": self.subject_id,
            "action": self.action,
            "scopes": list(self.scopes),
            "policy_version": self.policy_version,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "verification_ref": self.verification_ref,
        }


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    source_id: str
    claim_digest: str
    evidence_digest: str
    observed_at: str
    expires_at: str
    verifier_id: str
    verification_ref: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "source_id": self.source_id,
            "claim_digest": self.claim_digest,
            "evidence_digest": self.evidence_digest,
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "verifier_id": self.verifier_id,
            "verification_ref": self.verification_ref,
        }


@dataclass(frozen=True)
class AdmissionPolicy:
    version: str
    allowed_actions: tuple[str, ...]
    trusted_principals: tuple[str, ...]
    trusted_verifiers: tuple[str, ...]
    required_evidence_count: int = 1
    minimum_distinct_source_ids: int = 1
    max_evidence_age_seconds: int = 86_400
    max_grant_age_seconds: int = 86_400
    required_identity_keys: tuple[str, ...] = ("root_id",)
    required_contract_keys: tuple[str, ...] = ("schema_version",)
    protected_identity_fields: tuple[str, ...] = ("root_id", "genesis_hash")
    protected_contract_fields: tuple[str, ...] = (
        "constitution_hash",
        "ontology_hash",
        "schema_major",
    )

    def __post_init__(self) -> None:
        tuple_fields = (
            "allowed_actions",
            "trusted_principals",
            "trusted_verifiers",
            "required_identity_keys",
            "required_contract_keys",
            "protected_identity_fields",
            "protected_contract_fields",
        )
        for name in tuple_fields:
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not self.version:
            raise ValueError("POLICY_VERSION_REQUIRED")
        if self.required_evidence_count < 1 or self.minimum_distinct_source_ids < 1:
            raise ValueError("EVIDENCE_THRESHOLDS_MUST_BE_POSITIVE")
        if self.max_evidence_age_seconds <= 0 or self.max_grant_age_seconds <= 0:
            raise ValueError("FRESHNESS_LIMITS_MUST_BE_POSITIVE")

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "allowed_actions": list(self.allowed_actions),
            "trusted_principals": list(self.trusted_principals),
            "trusted_verifiers": list(self.trusted_verifiers),
            "required_evidence_count": self.required_evidence_count,
            "minimum_distinct_source_ids": self.minimum_distinct_source_ids,
            "max_evidence_age_seconds": self.max_evidence_age_seconds,
            "max_grant_age_seconds": self.max_grant_age_seconds,
            "required_identity_keys": list(self.required_identity_keys),
            "required_contract_keys": list(self.required_contract_keys),
            "protected_identity_fields": list(self.protected_identity_fields),
            "protected_contract_fields": list(self.protected_contract_fields),
        }


@dataclass(frozen=True)
class TransitionCandidate:
    action: str
    expected_state_digest: str
    grant: AuthorityGrant
    evidence: tuple[EvidenceReceipt, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))

    def to_payload(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "expected_state_digest": self.expected_state_digest,
            "grant": self.grant.to_payload(),
            "evidence": [receipt.to_payload() for receipt in self.evidence],
        }

    @property
    def digest(self) -> str:
        return digest_json(self.to_payload())


@dataclass(frozen=True)
class AdmissionDecision:
    status: AdmissionStatus
    object_id: str
    action: str
    state_before_digest: str
    state_after_digest: str
    request_digest: str
    evaluated_at: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    checks: Mapping[str, bool]
    authority_verified: bool | None
    verified_evidence_ids: tuple[str, ...]
    commit_performed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))
        object.__setattr__(self, "checks", _freeze(self.checks))
        object.__setattr__(self, "verified_evidence_ids", tuple(self.verified_evidence_ids))
        if self.commit_performed:
            raise ValueError("ADMISSION_KERNEL_MUST_NOT_CLAIM_COMMIT")

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "object_id": self.object_id,
            "action": self.action,
            "state_before_digest": self.state_before_digest,
            "state_after_digest": self.state_after_digest,
            "request_digest": self.request_digest,
            "evaluated_at": self.evaluated_at,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "checks": _thaw(self.checks),
            "authority_verified": self.authority_verified,
            "verified_evidence_ids": list(self.verified_evidence_ids),
            "commit_performed": self.commit_performed,
        }

    @property
    def digest(self) -> str:
        return digest_json(self.to_payload())


AuthorityVerifier = Callable[[AuthorityGrant], bool | None]
EvidenceVerifier = Callable[[EvidenceReceipt], bool | None]


def evaluate_transition(
    current: SovereignState,
    proposed: SovereignState,
    candidate: TransitionCandidate,
    policy: AdmissionPolicy,
    *,
    evaluated_at: str,
    authority_verifier: AuthorityVerifier | None,
    evidence_verifier: EvidenceVerifier | None,
) -> AdmissionDecision:
    """Evaluate a transition without mutating or persisting canonical state.

    A verifier returns True only after independently validating its artifact,
    False for a verified failure, and None when it cannot reach a conclusion.
    Exceptions from a verifier are treated as an unavailable verification path.
    """
    checks: dict[str, bool] = {}
    hard: list[str] = []
    quarantine: list[str] = []
    warnings: list[str] = []
    verified_receipts: list[EvidenceReceipt] = []
    authority_verified: bool | None = None

    try:
        now = parse_timestamp(evaluated_at)
        normalized_now = now.isoformat().replace("+00:00", "Z")
        checks["evaluation_time_valid"] = True
    except (TypeError, ValueError, OverflowError):
        now = None
        normalized_now = str(evaluated_at)
        checks["evaluation_time_valid"] = False
        hard.append("EVALUATION_TIME_INVALID")

    checks["object_identity"] = current.object_id == proposed.object_id
    if not checks["object_identity"]:
        hard.append("OBJECT_IDENTITY_MISMATCH")

    checks["expected_state_digest"] = (
        is_sha256(candidate.expected_state_digest)
        and candidate.expected_state_digest == current.digest
    )
    if not checks["expected_state_digest"]:
        hard.append("STALE_OR_INVALID_EXPECTED_STATE_DIGEST")

    checks["revision_step"] = proposed.revision == current.revision + 1
    if not checks["revision_step"]:
        hard.append("REVISION_MUST_ADVANCE_BY_ONE")

    for key in policy.required_identity_keys:
        ok = bool(current.identity.get(key)) and bool(proposed.identity.get(key))
        checks[f"required_identity:{key}"] = ok
        if not ok:
            hard.append(f"REQUIRED_IDENTITY_MISSING:{key}")

    for key in policy.required_contract_keys:
        ok = bool(current.contracts.get(key)) and bool(proposed.contracts.get(key))
        checks[f"required_contract:{key}"] = ok
        if not ok:
            hard.append(f"REQUIRED_CONTRACT_MISSING:{key}")

    for key in policy.protected_identity_fields:
        old_present, new_present = key in current.identity, key in proposed.identity
        ok = old_present == new_present and (
            not old_present or current.identity[key] == proposed.identity[key]
        )
        checks[f"protected_identity:{key}"] = ok
        if not ok:
            hard.append(f"PROTECTED_IDENTITY_MUTATION:{key}")

    for key in policy.protected_contract_fields:
        old_present, new_present = key in current.contracts, key in proposed.contracts
        ok = old_present == new_present and (
            not old_present or current.contracts[key] == proposed.contracts[key]
        )
        checks[f"protected_contract:{key}"] = ok
        if not ok:
            hard.append(f"PROTECTED_CONTRACT_MUTATION:{key}")

    checks["observation_history_preserved"] = (
        proposed.observations[: len(current.observations)] == current.observations
    )
    if not checks["observation_history_preserved"]:
        hard.append("OBSERVATION_HISTORY_REWRITE")

    checks["evidence_history_preserved"] = (
        proposed.evidence_refs[: len(current.evidence_refs)] == current.evidence_refs
    )
    if not checks["evidence_history_preserved"]:
        hard.append("EVIDENCE_HISTORY_REWRITE")

    duplicate_receipts = len({item.receipt_id for item in candidate.evidence}) != len(candidate.evidence)
    checks["evidence_receipt_ids_unique"] = not duplicate_receipts
    if duplicate_receipts:
        hard.append("DUPLICATE_EVIDENCE_RECEIPT_ID")

    for receipt in candidate.evidence:
        if receipt.receipt_id not in proposed.evidence_refs:
            hard.append(f"EVIDENCE_REFERENCE_NOT_IN_PROPOSED_STATE:{receipt.receipt_id}")
        if not is_sha256(receipt.evidence_digest):
            hard.append(f"EVIDENCE_DIGEST_INVALID:{receipt.receipt_id}")
        if not is_sha256(receipt.claim_digest) or receipt.claim_digest != proposed.digest:
            hard.append(f"EVIDENCE_NOT_BOUND_TO_PROPOSED_STATE:{receipt.receipt_id}")
        if not receipt.receipt_id or not receipt.source_id or not receipt.verifier_id:
            hard.append(f"EVIDENCE_IDENTITY_INCOMPLETE:{receipt.receipt_id}")

    checks["action_allowed"] = candidate.action in policy.allowed_actions
    if not checks["action_allowed"]:
        hard.append("ACTION_NOT_ALLOWED_BY_POLICY")

    grant = candidate.grant
    checks["grant_principal_trusted"] = grant.principal_id in policy.trusted_principals
    if not checks["grant_principal_trusted"]:
        hard.append("GRANT_PRINCIPAL_NOT_TRUSTED")

    checks["grant_subject_matches"] = grant.subject_id == current.object_id
    if not checks["grant_subject_matches"]:
        hard.append("GRANT_SUBJECT_MISMATCH")

    checks["grant_action_matches"] = grant.action == candidate.action
    if not checks["grant_action_matches"]:
        hard.append("GRANT_ACTION_MISMATCH")

    required_scopes = {candidate.action, f"object:{current.object_id}"}
    checks["grant_scopes_sufficient"] = required_scopes.issubset(set(grant.scopes))
    if not checks["grant_scopes_sufficient"]:
        hard.append("GRANT_SCOPES_INSUFFICIENT")

    checks["grant_policy_version_matches"] = grant.policy_version == policy.version
    if not checks["grant_policy_version_matches"]:
        hard.append("GRANT_POLICY_VERSION_MISMATCH")

    if now is not None:
        try:
            issued = parse_timestamp(grant.issued_at)
            expires = parse_timestamp(grant.expires_at)
            valid_time = issued <= now < expires
            checks["grant_time_valid"] = valid_time
            if not valid_time:
                hard.append("GRANT_NOT_CURRENT")
            if (now - issued).total_seconds() > policy.max_grant_age_seconds:
                checks["grant_fresh"] = False
                hard.append("GRANT_TOO_OLD")
            else:
                checks["grant_fresh"] = True
        except (TypeError, ValueError, OverflowError):
            checks["grant_time_valid"] = False
            checks["grant_fresh"] = False
            hard.append("GRANT_TIME_INVALID")
    else:
        checks["grant_time_valid"] = False
        checks["grant_fresh"] = False

    request_digest = digest_json({
        "current_state_digest": current.digest,
        "proposed_state_digest": proposed.digest,
        "candidate": candidate.to_payload(),
        "policy": policy.to_payload(),
        "evaluated_at": normalized_now,
    })

    def decision(status: AdmissionStatus) -> AdmissionDecision:
        reasons = hard + quarantine
        if status is AdmissionStatus.UNKNOWN:
            reasons.append("VERIFIED_EVIDENCE_INSUFFICIENT")
        return AdmissionDecision(
            status=status,
            object_id=current.object_id,
            action=candidate.action,
            state_before_digest=current.digest,
            state_after_digest=proposed.digest,
            request_digest=request_digest,
            evaluated_at=normalized_now,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
            checks=checks,
            authority_verified=authority_verified,
            verified_evidence_ids=tuple(receipt.receipt_id for receipt in verified_receipts),
            commit_performed=False,
        )

    if hard:
        return decision(AdmissionStatus.REJECT)

    if authority_verifier is None:
        quarantine.append("AUTHORITY_VERIFIER_UNAVAILABLE")
        checks["authority_verifier_available"] = False
        return decision(AdmissionStatus.QUARANTINE)
    checks["authority_verifier_available"] = True
    try:
        result = authority_verifier(grant)
        if result is None:
            quarantine.append("AUTHORITY_VERIFICATION_INDETERMINATE")
            checks["authority_signature_valid"] = False
            return decision(AdmissionStatus.QUARANTINE)
        authority_verified = result is True
        checks["authority_signature_valid"] = authority_verified
        if not authority_verified:
            hard.append("AUTHORITY_VERIFICATION_FAILED")
            return decision(AdmissionStatus.REJECT)
    except Exception:
        quarantine.append("AUTHORITY_VERIFIER_ERROR")
        checks["authority_signature_valid"] = False
        return decision(AdmissionStatus.QUARANTINE)

    if not candidate.evidence:
        checks["evidence_verifier_available"] = evidence_verifier is not None
        checks["verified_evidence_count"] = False
        checks["distinct_source_count"] = False
        return decision(AdmissionStatus.UNKNOWN)

    if evidence_verifier is None:
        quarantine.append("EVIDENCE_VERIFIER_UNAVAILABLE")
        checks["evidence_verifier_available"] = False
        return decision(AdmissionStatus.QUARANTINE)
    checks["evidence_verifier_available"] = True

    for receipt in candidate.evidence:
        if receipt.verifier_id not in policy.trusted_verifiers:
            hard.append(f"EVIDENCE_VERIFIER_NOT_TRUSTED:{receipt.receipt_id}")
            continue
        if now is None:
            quarantine.append("EVIDENCE_TIME_UNAVAILABLE")
            continue
        try:
            observed = parse_timestamp(receipt.observed_at)
            expires = parse_timestamp(receipt.expires_at)
        except (TypeError, ValueError, OverflowError):
            hard.append(f"EVIDENCE_TIME_INVALID:{receipt.receipt_id}")
            continue
        if observed > now or expires <= observed:
            hard.append(f"EVIDENCE_TIME_RANGE_INVALID:{receipt.receipt_id}")
            continue
        if expires <= now or (now - observed).total_seconds() > policy.max_evidence_age_seconds:
            warnings.append(f"EVIDENCE_STALE_EXCLUDED:{receipt.receipt_id}")
            continue
        try:
            verified = evidence_verifier(receipt)
            if verified is None:
                quarantine.append(f"EVIDENCE_VERIFICATION_INDETERMINATE:{receipt.receipt_id}")
            elif verified is False:
                hard.append(f"EVIDENCE_VERIFICATION_FAILED:{receipt.receipt_id}")
            else:
                verified_receipts.append(receipt)
        except Exception:
            quarantine.append(f"EVIDENCE_VERIFIER_ERROR:{receipt.receipt_id}")

    checks["verified_evidence_count"] = len(verified_receipts) >= policy.required_evidence_count
    checks["distinct_source_count"] = (
        len({receipt.source_id for receipt in verified_receipts})
        >= policy.minimum_distinct_source_ids
    )

    if hard:
        return decision(AdmissionStatus.REJECT)
    if quarantine:
        return decision(AdmissionStatus.QUARANTINE)
    if not checks["verified_evidence_count"] or not checks["distinct_source_count"]:
        return decision(AdmissionStatus.UNKNOWN)
    return decision(AdmissionStatus.ADMIT)


@dataclass(frozen=True)
class AdmissionAuditEvent:
    """Hash-linked decision record. It is not a canonical state commit receipt."""

    sequence: int
    event_id: str
    previous_hash: str
    decision_payload: Mapping[str, Any]
    event_hash: str

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("EVENT_SEQUENCE_MUST_BE_NONNEGATIVE")
        object.__setattr__(self, "decision_payload", _freeze(self.decision_payload))

    def hash_payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "previous_hash": self.previous_hash,
            "decision_payload": _thaw(self.decision_payload),
        }


def create_audit_event(
    admission: AdmissionDecision,
    *,
    sequence: int,
    previous_hash: str,
) -> AdmissionAuditEvent:
    """Build a tamper-evident record of a decision, not a state-changing commit."""
    if sequence < 0:
        raise ValueError("EVENT_SEQUENCE_MUST_BE_NONNEGATIVE")
    if sequence == 0 and previous_hash != GENESIS_HASH:
        raise ValueError("FIRST_EVENT_MUST_USE_GENESIS_HASH")
    if sequence > 0 and not is_sha256(previous_hash):
        raise ValueError("PREVIOUS_EVENT_HASH_INVALID")
    event_id = digest_json({"sequence": sequence, "decision_digest": admission.digest})
    provisional = AdmissionAuditEvent(
        sequence=sequence,
        event_id=event_id,
        previous_hash=previous_hash,
        decision_payload=admission.to_payload(),
        event_hash="",
    )
    return AdmissionAuditEvent(
        sequence=sequence,
        event_id=event_id,
        previous_hash=previous_hash,
        decision_payload=admission.to_payload(),
        event_hash=digest_json(provisional.hash_payload()),
    )


def verify_event_chain(events: Sequence[AdmissionAuditEvent]) -> tuple[bool, tuple[str, ...]]:
    """Verify sequence, hash linkage, event hashes, and decision non-commit semantics."""
    errors: list[str] = []
    previous = GENESIS_HASH
    for expected_sequence, event in enumerate(events):
        if event.sequence != expected_sequence:
            errors.append(f"EVENT_SEQUENCE_GAP:{expected_sequence}")
        if event.previous_hash != previous:
            errors.append(f"PREVIOUS_HASH_MISMATCH:{expected_sequence}")
        if not is_sha256(event.event_hash) or event.event_hash != digest_json(event.hash_payload()):
            errors.append(f"EVENT_HASH_INVALID:{expected_sequence}")
        if event.decision_payload.get("commit_performed") is not False:
            errors.append(f"DECISION_CLAIMS_COMMIT:{expected_sequence}")
        previous = event.event_hash
    return not errors, tuple(errors)


def replay_audit_events(events: Sequence[AdmissionAuditEvent]) -> tuple[dict[str, Any], ...]:
    """Replay the ordered decision audit trail after integrity verification; never promote state."""
    valid, errors = verify_event_chain(events)
    if not valid:
        raise ValueError("AUDIT_CHAIN_INVALID:" + ",".join(errors))
    return tuple(_thaw(event.decision_payload) for event in events)


@dataclass(frozen=True)
class ProofDebtItem:
    obligation_id: str
    risk_weight: float
    unresolved_fraction: float

    def __post_init__(self) -> None:
        if not self.obligation_id:
            raise ValueError("OBLIGATION_ID_REQUIRED")
        if not math.isfinite(self.risk_weight) or self.risk_weight < 0:
            raise ValueError("RISK_WEIGHT_MUST_BE_FINITE_AND_NONNEGATIVE")
        if (
            not math.isfinite(self.unresolved_fraction)
            or not 0 <= self.unresolved_fraction <= 1
        ):
            raise ValueError("UNRESOLVED_FRACTION_MUST_BE_IN_RANGE_0_1")


def calculate_proof_debt(items: Sequence[ProofDebtItem]) -> float:
    """Compute Σ(risk_weight × unresolved_fraction); this is prioritization, not proof."""
    return math.fsum(item.risk_weight * item.unresolved_fraction for item in items)
