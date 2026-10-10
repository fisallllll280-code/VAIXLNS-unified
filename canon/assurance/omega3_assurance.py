"""Ω-REFLEXIVE ASSURANCE: independent checking of Ω³ admission decisions.

This module intentionally does not import or invoke evaluate_transition().
It recomputes contract-level expectations in a separate code path and emits a
replayable, content-addressed receipt. It is not a separately deployed trust
domain, formal proof, signature verifier, or authorization to commit state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping

from canon.kernel.omega3_kernel import (
    AdmissionDecision,
    AdmissionPolicy,
    AdmissionStatus,
    AuthorityGrant,
    EvidenceReceipt,
    SovereignState,
    TransitionCandidate,
)

_CHECKER_VERSION = "omega3-reflexive-assurance/1.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GENESIS = "GENESIS"


class AssuranceVerdict(str, Enum):
    CHECKED_ADMISSION_CANDIDATE = "CHECKED_ADMISSION_CANDIDATE"
    CONSISTENT_NON_ADMISSIBLE = "CONSISTENT_NON_ADMISSIBLE"
    DIVERGENT = "DIVERGENT"
    INDETERMINATE = "INDETERMINATE"


def _plain(value: Any) -> Any:
    """Independent JSON normalization; do not call Ω³ kernel internals."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("NON_STRING_OBJECT_KEY")
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NON_FINITE_CANONICAL_NUMBER")
        return value
    raise TypeError(f"NON_JSON_TYPE:{type(value).__name__}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("TIMESTAMP_REQUIRED")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _utc_text(value: str) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _state_body(state: SovereignState) -> dict[str, Any]:
    return {
        "object_id": state.object_id,
        "revision": state.revision,
        "identity": _plain(state.identity),
        "contracts": _plain(state.contracts),
        "authority": _plain(state.authority),
        "observations": _plain(state.observations),
        "evidence_refs": list(state.evidence_refs),
    }


def _state_hash(state: SovereignState) -> str:
    return _hash(_state_body(state))


def _grant_body(grant: AuthorityGrant) -> dict[str, Any]:
    return {
        "grant_id": grant.grant_id,
        "principal_id": grant.principal_id,
        "subject_id": grant.subject_id,
        "action": grant.action,
        "scopes": list(grant.scopes),
        "policy_version": grant.policy_version,
        "issued_at": grant.issued_at,
        "expires_at": grant.expires_at,
        "verification_ref": grant.verification_ref,
    }


def _evidence_body(item: EvidenceReceipt) -> dict[str, Any]:
    return {
        "receipt_id": item.receipt_id,
        "source_id": item.source_id,
        "claim_digest": item.claim_digest,
        "evidence_digest": item.evidence_digest,
        "observed_at": item.observed_at,
        "expires_at": item.expires_at,
        "verifier_id": item.verifier_id,
        "verification_ref": item.verification_ref,
    }


def _candidate_body(candidate: TransitionCandidate) -> dict[str, Any]:
    return {
        "action": candidate.action,
        "expected_state_digest": candidate.expected_state_digest,
        "grant": _grant_body(candidate.grant),
        "evidence": [_evidence_body(item) for item in candidate.evidence],
    }


def _policy_body(policy: AdmissionPolicy) -> dict[str, Any]:
    return {
        "version": policy.version,
        "allowed_actions": list(policy.allowed_actions),
        "trusted_principals": list(policy.trusted_principals),
        "trusted_verifiers": list(policy.trusted_verifiers),
        "required_evidence_count": policy.required_evidence_count,
        "minimum_distinct_source_ids": policy.minimum_distinct_source_ids,
        "max_evidence_age_seconds": policy.max_evidence_age_seconds,
        "max_grant_age_seconds": policy.max_grant_age_seconds,
        "required_identity_keys": list(policy.required_identity_keys),
        "required_contract_keys": list(policy.required_contract_keys),
        "protected_identity_fields": list(policy.protected_identity_fields),
        "protected_contract_fields": list(policy.protected_contract_fields),
    }


def _request_hash(
    current: SovereignState,
    proposed: SovereignState,
    candidate: TransitionCandidate,
    policy: AdmissionPolicy,
    evaluated_at: str,
) -> str:
    now = _utc_text(evaluated_at)
    return _hash({
        "current_state_digest": _state_hash(current),
        "proposed_state_digest": _state_hash(proposed),
        "candidate": _candidate_body(candidate),
        "policy": _policy_body(policy),
        "evaluated_at": now,
    })


@dataclass(frozen=True)
class CounterexampleReceipt:
    path: str
    expected: str
    observed: str
    input_digest: str
    counterexample_digest: str

    def payload(self) -> dict[str, str]:
        return {
            "path": self.path,
            "expected": self.expected,
            "observed": self.observed,
            "input_digest": self.input_digest,
        }


@dataclass(frozen=True)
class AssuranceReceipt:
    checker_version: str
    verdict: AssuranceVerdict
    expected_status: str
    observed_status: str
    input_digest: str
    decision_digest: str
    evaluated_at: str
    findings: tuple[str, ...]
    counterexamples: tuple[CounterexampleReceipt, ...]
    declared_limitations: tuple[str, ...]
    commit_performed: bool
    receipt_digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "checker_version": self.checker_version,
            "verdict": self.verdict.value,
            "expected_status": self.expected_status,
            "observed_status": self.observed_status,
            "input_digest": self.input_digest,
            "decision_digest": self.decision_digest,
            "evaluated_at": self.evaluated_at,
            "findings": list(self.findings),
            "counterexamples": [
                {**item.payload(), "counterexample_digest": item.counterexample_digest}
                for item in self.counterexamples
            ],
            "declared_limitations": list(self.declared_limitations),
            "commit_performed": self.commit_performed,
        }


@dataclass(frozen=True)
class _ReferenceResult:
    status: AdmissionStatus
    findings: tuple[str, ...]
    warnings: tuple[str, ...]
    authority_verified: bool | None = None
    verified_evidence_ids: tuple[str, ...] = ()


def _reference_adjudication(
    current: SovereignState,
    proposed: SovereignState,
    candidate: TransitionCandidate,
    policy: AdmissionPolicy,
    *,
    evaluated_at: str,
    authority_verdict: Any,
    evidence_verdicts: Mapping[str, Any] | None,
) -> _ReferenceResult:
    """Separate contract implementation; deliberately does not consult kernel checks."""
    failures: list[str] = []
    unresolved: list[str] = []
    warnings: list[str] = []
    accepted_receipts: list[EvidenceReceipt] = []

    try:
        now = _utc(evaluated_at)
    except (TypeError, ValueError, OverflowError):
        return _ReferenceResult(AdmissionStatus.REJECT, ("EVALUATION_TIME_INVALID",), ())

    old_hash = _state_hash(current)
    next_hash = _state_hash(proposed)

    if current.object_id != proposed.object_id:
        failures.append("OBJECT_IDENTITY_MISMATCH")
    if not isinstance(candidate.expected_state_digest, str) or not _SHA256.fullmatch(
        candidate.expected_state_digest
    ) or candidate.expected_state_digest != old_hash:
        failures.append("STALE_OR_INVALID_EXPECTED_STATE_DIGEST")
    if isinstance(proposed.revision, bool) or proposed.revision != current.revision + 1:
        failures.append("REVISION_MUST_ADVANCE_BY_ONE")

    for key in policy.required_identity_keys:
        if not current.identity.get(key) or not proposed.identity.get(key):
            failures.append(f"REQUIRED_IDENTITY_MISSING:{key}")
    for key in policy.required_contract_keys:
        if not current.contracts.get(key) or not proposed.contracts.get(key):
            failures.append(f"REQUIRED_CONTRACT_MISSING:{key}")
    for key in policy.protected_identity_fields:
        before, after = key in current.identity, key in proposed.identity
        if before != after or (before and current.identity[key] != proposed.identity[key]):
            failures.append(f"PROTECTED_IDENTITY_MUTATION:{key}")
    for key in policy.protected_contract_fields:
        before, after = key in current.contracts, key in proposed.contracts
        if before != after or (before and current.contracts[key] != proposed.contracts[key]):
            failures.append(f"PROTECTED_CONTRACT_MUTATION:{key}")

    old_observations = _plain(current.observations)
    new_observations = _plain(proposed.observations)
    if new_observations[:len(old_observations)] != old_observations:
        failures.append("OBSERVATION_HISTORY_REWRITE")
    if list(proposed.evidence_refs[:len(current.evidence_refs)]) != list(current.evidence_refs):
        failures.append("EVIDENCE_HISTORY_REWRITE")

    receipt_ids = [item.receipt_id for item in candidate.evidence]
    if len(set(receipt_ids)) != len(receipt_ids):
        failures.append("DUPLICATE_EVIDENCE_RECEIPT_ID")
    for item in candidate.evidence:
        if item.receipt_id not in proposed.evidence_refs:
            failures.append(f"EVIDENCE_REFERENCE_NOT_IN_PROPOSED_STATE:{item.receipt_id}")
        if not isinstance(item.evidence_digest, str) or not _SHA256.fullmatch(item.evidence_digest):
            failures.append(f"EVIDENCE_DIGEST_INVALID:{item.receipt_id}")
        if not isinstance(item.claim_digest, str) or not _SHA256.fullmatch(item.claim_digest) or item.claim_digest != next_hash:
            failures.append(f"EVIDENCE_NOT_BOUND_TO_PROPOSED_STATE:{item.receipt_id}")
        if not item.receipt_id or not item.source_id or not item.verifier_id or not item.verification_ref:
            failures.append(f"EVIDENCE_IDENTITY_OR_VERIFICATION_REFERENCE_INCOMPLETE:{item.receipt_id}")

    if candidate.action not in policy.allowed_actions:
        failures.append("ACTION_NOT_ALLOWED_BY_POLICY")

    grant = candidate.grant
    if not grant.grant_id or not grant.verification_ref:
        failures.append("GRANT_ID_OR_VERIFICATION_REFERENCE_MISSING")
    if grant.principal_id not in policy.trusted_principals:
        failures.append("GRANT_PRINCIPAL_NOT_TRUSTED")
    if grant.subject_id != current.object_id:
        failures.append("GRANT_SUBJECT_MISMATCH")
    if grant.action != candidate.action:
        failures.append("GRANT_ACTION_MISMATCH")
    if not {candidate.action, f"object:{current.object_id}"}.issubset(set(grant.scopes)):
        failures.append("GRANT_SCOPES_INSUFFICIENT")
    if grant.policy_version != policy.version:
        failures.append("GRANT_POLICY_VERSION_MISMATCH")
    try:
        issued, expires = _utc(grant.issued_at), _utc(grant.expires_at)
        if not issued <= now < expires:
            failures.append("GRANT_NOT_CURRENT")
        if (now - issued).total_seconds() > policy.max_grant_age_seconds:
            failures.append("GRANT_TOO_OLD")
    except (TypeError, ValueError, OverflowError):
        failures.append("GRANT_TIME_INVALID")

    # Reject modeled contract violations before checking opaque verifier results.
    if failures:
        return _ReferenceResult(
            AdmissionStatus.REJECT, tuple(sorted(set(failures))), ()
        )

    if authority_verdict is False:
        return _ReferenceResult(
            AdmissionStatus.REJECT, ("AUTHORITY_VERIFICATION_FAILED",), (),
            authority_verified=False,
        )
    if authority_verdict is not True:
        reason = (
            "AUTHORITY_VERIFICATION_INDETERMINATE"
            if authority_verdict is None or type(authority_verdict) is not bool
            else "AUTHORITY_VERIFICATION_FAILED"
        )
        if reason == "AUTHORITY_VERIFICATION_FAILED":
            return _ReferenceResult(
                AdmissionStatus.REJECT, (reason,), (), authority_verified=False
            )
        return _ReferenceResult(
            AdmissionStatus.QUARANTINE, (reason,), (), authority_verified=None
        )

    if not candidate.evidence:
        return _ReferenceResult(
            AdmissionStatus.UNKNOWN, ("VERIFIED_EVIDENCE_INSUFFICIENT",), (),
            authority_verified=True,
        )
    if evidence_verdicts is None:
        return _ReferenceResult(
            AdmissionStatus.QUARANTINE, ("EVIDENCE_VERIFIER_UNAVAILABLE",), (),
            authority_verified=True,
        )

    for item in candidate.evidence:
        if item.verifier_id not in policy.trusted_verifiers:
            failures.append(f"EVIDENCE_VERIFIER_NOT_TRUSTED:{item.receipt_id}")
            continue
        try:
            observed, expires_at = _utc(item.observed_at), _utc(item.expires_at)
        except (TypeError, ValueError, OverflowError):
            failures.append(f"EVIDENCE_TIME_INVALID:{item.receipt_id}")
            continue
        if observed > now or expires_at <= observed:
            failures.append(f"EVIDENCE_TIME_RANGE_INVALID:{item.receipt_id}")
            continue
        if expires_at <= now or (now - observed).total_seconds() > policy.max_evidence_age_seconds:
            warnings.append(f"EVIDENCE_STALE_EXCLUDED:{item.receipt_id}")
            continue
        verdict = evidence_verdicts.get(item.receipt_id, _MISSING)
        if verdict is False:
            failures.append(f"EVIDENCE_VERIFICATION_FAILED:{item.receipt_id}")
        elif verdict is True:
            accepted_receipts.append(item)
        elif type(verdict) is str and verdict == "ERROR":
            unresolved.append(f"EVIDENCE_VERIFIER_ERROR:{item.receipt_id}")
        else:
            unresolved.append(f"EVIDENCE_VERIFICATION_INDETERMINATE:{item.receipt_id}")

    accepted_ids = tuple(item.receipt_id for item in accepted_receipts)
    warning_ids = tuple(sorted(set(warnings)))
    if failures:
        return _ReferenceResult(
            AdmissionStatus.REJECT, tuple(sorted(set(failures))),
            warning_ids, authority_verified=True, verified_evidence_ids=accepted_ids,
        )
    if unresolved:
        return _ReferenceResult(
            AdmissionStatus.QUARANTINE, tuple(sorted(set(unresolved))),
            warning_ids, authority_verified=True, verified_evidence_ids=accepted_ids,
        )
    if len(accepted_receipts) < policy.required_evidence_count:
        return _ReferenceResult(
            AdmissionStatus.UNKNOWN, ("VERIFIED_EVIDENCE_INSUFFICIENT",),
            warning_ids, authority_verified=True, verified_evidence_ids=accepted_ids,
        )
    if len({item.source_id for item in accepted_receipts}) < policy.minimum_distinct_source_ids:
        return _ReferenceResult(
            AdmissionStatus.UNKNOWN, ("VERIFIED_EVIDENCE_INSUFFICIENT",),
            warning_ids, authority_verified=True, verified_evidence_ids=accepted_ids,
        )
    return _ReferenceResult(
        AdmissionStatus.ADMIT, (), warning_ids,
        authority_verified=True, verified_evidence_ids=accepted_ids,
    )


_MISSING = object()


def check_admission_decision(
    current: SovereignState,
    proposed: SovereignState,
    candidate: TransitionCandidate,
    policy: AdmissionPolicy,
    decision: AdmissionDecision,
    *,
    evaluated_at: str,
    authority_verdict: Any,
    evidence_verdicts: Mapping[str, Any] | None,
) -> AssuranceReceipt:
    """Recompute expected status and validate decision bindings independently."""
    findings: list[str] = []
    counterexamples: list[CounterexampleReceipt] = []
    try:
        normalized_time = _utc_text(evaluated_at)
        input_digest = _hash({
            "current": _state_body(current),
            "proposed": _state_body(proposed),
            "candidate": _candidate_body(candidate),
            "policy": _policy_body(policy),
            "evaluated_at": normalized_time,
            "authority_verdict": authority_verdict if authority_verdict in (True, False, None) else repr(type(authority_verdict).__name__),
            "evidence_verdicts": {
                key: value if value in (True, False, None) else repr(type(value).__name__)
                for key, value in sorted((evidence_verdicts or {}).items())
            },
        })
        expected = _reference_adjudication(
            current, proposed, candidate, policy, evaluated_at=normalized_time,
            authority_verdict=authority_verdict, evidence_verdicts=evidence_verdicts,
        )
        expected_status = expected.status.value
        observed_status = decision.status.value if isinstance(decision.status, AdmissionStatus) else str(decision.status)
        decision_digest = _hash({
            "status": observed_status,
            "object_id": decision.object_id,
            "action": decision.action,
            "state_before_digest": decision.state_before_digest,
            "state_after_digest": decision.state_after_digest,
            "request_digest": decision.request_digest,
            "evaluated_at": decision.evaluated_at,
            "reasons": list(decision.reasons),
            "warnings": list(decision.warnings),
            "checks": _plain(decision.checks),
            "authority_verified": decision.authority_verified,
            "verified_evidence_ids": list(decision.verified_evidence_ids),
            "commit_performed": decision.commit_performed,
        })
        expected_bindings = {
            "decision.object_id": (current.object_id, decision.object_id),
            "decision.action": (candidate.action, decision.action),
            "decision.state_before_digest": (_state_hash(current), decision.state_before_digest),
            "decision.state_after_digest": (_state_hash(proposed), decision.state_after_digest),
            "decision.request_digest": (
                _request_hash(current, proposed, candidate, policy, normalized_time),
                decision.request_digest,
            ),
            "decision.evaluated_at": (normalized_time, decision.evaluated_at),
            "decision.commit_performed": (False, decision.commit_performed),
            "decision.authority_verified": (expected.authority_verified, decision.authority_verified),
            "decision.verified_evidence_ids": (expected.verified_evidence_ids, tuple(decision.verified_evidence_ids)),
            "decision.reasons": (tuple(sorted(set(expected.findings))), tuple(sorted(set(decision.reasons)))),
            "decision.warnings": (expected.warnings, tuple(sorted(set(decision.warnings)))),
            "decision.status": (expected_status, observed_status),
        }
        for path, (expected_value, observed_value) in expected_bindings.items():
            if expected_value != observed_value:
                findings.append(f"BINDING_MISMATCH:{path}")
                payload = {
                    "path": path,
                    "expected": str(expected_value),
                    "observed": str(observed_value),
                    "input_digest": input_digest,
                }
                counterexamples.append(CounterexampleReceipt(
                    path=path, expected=str(expected_value), observed=str(observed_value),
                    input_digest=input_digest, counterexample_digest=_hash(payload),
                ))
        findings.extend(expected.findings)
        verdict = (
            AssuranceVerdict.DIVERGENT if counterexamples
            else AssuranceVerdict.CHECKED_ADMISSION_CANDIDATE
            if expected.status is AdmissionStatus.ADMIT
            else AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE
        )
        limitations = (
            "Same-process checker; not an independently deployed trust domain.",
            "Verifier verdict inputs must be authenticated by production adapters.",
            "Consistency is not proof that external claims are true.",
            "No canonical commit, storage CAS, or runtime enforcement is performed.",
        )
        body = {
            "checker_version": _CHECKER_VERSION,
            "verdict": verdict.value,
            "expected_status": expected_status,
            "observed_status": observed_status,
            "input_digest": input_digest,
            "decision_digest": decision_digest,
            "evaluated_at": normalized_time,
            "findings": sorted(set(findings)),
            "counterexamples": [
                {**item.payload(), "counterexample_digest": item.counterexample_digest}
                for item in counterexamples
            ],
            "declared_limitations": list(limitations),
            "commit_performed": False,
        }
        return AssuranceReceipt(
            checker_version=_CHECKER_VERSION,
            verdict=verdict,
            expected_status=expected_status,
            observed_status=observed_status,
            input_digest=input_digest,
            decision_digest=decision_digest,
            evaluated_at=normalized_time,
            findings=tuple(sorted(set(findings))),
            counterexamples=tuple(counterexamples),
            declared_limitations=limitations,
            commit_performed=False,
            receipt_digest=_hash(body),
        )
    except Exception as exc:
        input_digest = _hash({
            "checker_version": _CHECKER_VERSION,
            "failure_type": type(exc).__name__,
        })
        body = {
            "checker_version": _CHECKER_VERSION,
            "verdict": AssuranceVerdict.INDETERMINATE.value,
            "expected_status": "INDETERMINATE",
            "observed_status": str(getattr(getattr(decision, "status", None), "value", "UNKNOWN")),
            "input_digest": input_digest,
            "decision_digest": "UNAVAILABLE",
            "evaluated_at": str(evaluated_at),
            "findings": [f"CHECKER_ERROR:{type(exc).__name__}"],
            "counterexamples": [],
            "declared_limitations": ["Checker could not complete; no admission inference is permitted."],
            "commit_performed": False,
        }
        return AssuranceReceipt(
            checker_version=_CHECKER_VERSION,
            verdict=AssuranceVerdict.INDETERMINATE,
            expected_status="INDETERMINATE",
            observed_status=str(getattr(getattr(decision, "status", None), "value", "UNKNOWN")),
            input_digest=input_digest,
            decision_digest="UNAVAILABLE",
            evaluated_at=str(evaluated_at),
            findings=(f"CHECKER_ERROR:{type(exc).__name__}",),
            counterexamples=(),
            declared_limitations=("Checker could not complete; no admission inference is permitted.",),
            commit_performed=False,
            receipt_digest=_hash(body),
        )


def verify_assurance_receipt(receipt: AssuranceReceipt) -> bool:
    """Verify receipt/counterexample content hashes; this does not authenticate authorship."""
    for item in receipt.counterexamples:
        if item.counterexample_digest != _hash(item.payload()):
            return False
    body = receipt.payload()
    body.pop("receipt_digest", None)
    return receipt.receipt_digest == _hash(body)
