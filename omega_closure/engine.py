"""Evidence-gated Ω.2718 closure evaluation.

This module evaluates a bounded evidence bundle. It does not confer authority,
manufacture signatures, or establish that an external system is live. A real
signature verifier and an out-of-band pinned trust-root fingerprint are required
before a bundle can receive CLOSED status.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODES = {"structural", "semantic", "temporal", "constitutional"}
_FAILURE_CLASSES = {
    "F1_STORAGE_FAILURE",
    "F2_SIGNATURE_FAILURE",
    "F3_CLOCK_FAILURE",
    "F4_ACTIVATION_FAILURE",
    "F5_INTEGRITY_FAILURE",
}
_ZERO_HASH = "0" * 64
SignatureVerifier = Callable[[Mapping[str, Any], Mapping[str, Any], str], bool]


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ClosureReport:
    subject: str
    status: str
    checks: tuple[CheckResult, ...]
    report_digest: str

    @property
    def closed(self) -> bool:
        return self.status == "CLOSED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "status": self.status,
            "closed": self.closed,
            "checks": [asdict(item) for item in self.checks],
            "passed_checks": sum(item.passed for item in self.checks),
            "total_checks": len(self.checks),
            "report_digest": self.report_digest,
        }


def canonical_sha256(value: Any) -> str:
    """SHA-256 over deterministic, JSON-only UTF-8 serialization."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _verify_signature(
    verifier: SignatureVerifier | None,
    signer: Mapping[str, Any] | None,
    payload: Mapping[str, Any],
    signature: Any,
) -> bool:
    if verifier is None or not isinstance(signer, Mapping) or not _has_text(signature):
        return False
    try:
        return bool(verifier(signer, payload, str(signature)))
    except Exception:
        return False


def _proofs(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    value = bundle.get("meta_proof")
    if not isinstance(value, Mapping):
        return {}
    records = value.get("proofs")
    if not isinstance(records, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for item in records:
        if isinstance(item, Mapping) and _has_text(item.get("proof_id")):
            result[str(item["proof_id"])] = item
    return result


def _safe_check(check_id: str, fn: Callable[[], tuple[bool, str]]) -> CheckResult:
    try:
        passed, detail = fn()
        return CheckResult(check_id, bool(passed), str(detail))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return CheckResult(check_id, False, f"INVALID_EVIDENCE: {type(exc).__name__}")
    except Exception as exc:
        return CheckResult(check_id, False, f"VALIDATOR_ERROR: {type(exc).__name__}")


def evaluate_closure(
    bundle: Mapping[str, Any],
    *,
    canonical_source_hash: str | None = None,
    trusted_root_hash: str | None = None,
    signature_verifier: SignatureVerifier | None = None,
) -> ClosureReport:
    """Evaluate all eleven Ω.2718 layers. Missing evidence always fails closed.

    canonical_source_hash and trusted_root_hash must be supplied independently
    of the evidence bundle. signature_verifier must perform real cryptographic
    and identity validation;
    test-only verifiers must never be used for production decisions.
    """
    if not isinstance(bundle, Mapping):
        bundle = {}

    subject_value = bundle.get("subject", "Ω.2718")
    subject = str(subject_value) if _has_text(subject_value) else "Ω.2718"
    signers = bundle.get("signers", {})
    if not isinstance(signers, Mapping):
        signers = {}

    def constitutional_binding() -> tuple[bool, str]:
        item = bundle.get("constitutional_binding")
        if not isinstance(item, Mapping):
            return False, "CONSTITUTIONAL_BINDING_MISSING"
        if not _is_hash(canonical_source_hash):
            return False, "CANONICAL_SOURCE_HASH_NOT_PINNED"
        if item.get("source_hash") != canonical_source_hash:
            return False, "CANONICAL_SOURCE_HASH_MISMATCH"
        valid = (
            item.get("source_id") == "CONST-ROOT"
            and item.get("immutable") is True
            and _has_text(item.get("authority"))
            and _has_text(item.get("source_ref"))
            and _is_hash(item.get("source_hash"))
        )
        return valid, "CONSTITUTIONAL_SOURCE_BOUND" if valid else "CONSTITUTIONAL_BINDING_INVALID"

    def meta_proof() -> tuple[bool, str]:
        section = bundle.get("meta_proof")
        records = section.get("proofs") if isinstance(section, Mapping) else None
        if not isinstance(records, list) or not records:
            return False, "META_PROOF_MISSING"
        seen: set[str] = set()
        for item in records:
            if not isinstance(item, Mapping):
                return False, "PROOF_RECORD_INVALID"
            proof_id = item.get("proof_id")
            statement = item.get("statement")
            parents = item.get("parent_proof_ids", [])
            if not _has_text(proof_id) or proof_id in seen:
                return False, "PROOF_ID_MISSING_OR_DUPLICATED"
            if not isinstance(statement, Mapping) or not isinstance(parents, list):
                return False, "PROOF_STATEMENT_INVALID"
            if any(parent not in seen for parent in parents):
                return False, "PROOF_PARENT_MISSING_OR_CYCLIC"
            digest = canonical_sha256(statement)
            if item.get("digest") != digest:
                return False, f"PROOF_DIGEST_MISMATCH:{proof_id}"
            signer_id = item.get("signer_id")
            verifier_id = item.get("verified_by")
            if not _has_text(signer_id) or not _has_text(verifier_id) or signer_id == verifier_id:
                return False, f"PROOF_ROLE_SEPARATION_FAILED:{proof_id}"
            signed_payload = {
                "proof_id": proof_id,
                "digest": digest,
                "statement": dict(statement),
                "parent_proof_ids": list(parents),
            }
            verification_payload = {
                "proof_id": proof_id,
                "digest": digest,
                "signer_id": signer_id,
                "proof_signature": item.get("signature"),
            }
            if not _verify_signature(signature_verifier, signers.get(str(signer_id)), signed_payload, item.get("signature")):
                return False, f"PROOF_SIGNATURE_INVALID:{proof_id}"
            if not _verify_signature(signature_verifier, signers.get(str(verifier_id)), verification_payload, item.get("verification_signature")):
                return False, f"META_VERIFICATION_SIGNATURE_INVALID:{proof_id}"
            seen.add(str(proof_id))
        return True, "META_PROOF_CHAIN_VALID"

    def closure_engine() -> tuple[bool, str]:
        item = bundle.get("closure_engine")
        modes = item.get("completed_modes") if isinstance(item, Mapping) else None
        if not isinstance(modes, list):
            return False, "CLOSURE_ENGINE_MODES_MISSING"
        if not _MODES.issubset(set(modes)):
            return False, "CLOSURE_ENGINE_MODES_INCOMPLETE"
        if item.get("deterministic") is not True or item.get("fail_closed") is not True:
            return False, "CLOSURE_ENGINE_SAFETY_POLICY_MISSING"
        return True, "CLOSURE_ENGINE_MODES_COMPLETE"

    def historical_ledger() -> tuple[bool, str]:
        section = bundle.get("historical_ratification_ledger")
        entries = section.get("entries") if isinstance(section, Mapping) else None
        if not isinstance(entries, list) or not entries:
            return False, "RATIFICATION_LEDGER_MISSING"
        previous_hash = _ZERO_HASH
        previous_time: datetime | None = None
        for expected_sequence, entry in enumerate(entries, start=1):
            if not isinstance(entry, Mapping):
                return False, "LEDGER_ENTRY_INVALID"
            if entry.get("sequence") != expected_sequence:
                return False, "LEDGER_SEQUENCE_GAP"
            if entry.get("previous_hash") != previous_hash:
                return False, "LEDGER_CHAIN_MISMATCH"
            timestamp = _timestamp(entry.get("timestamp"))
            if timestamp is None or (previous_time is not None and timestamp < previous_time):
                return False, "LEDGER_TIMESTAMP_INVALID_OR_NON_MONOTONIC"
            previous_time = timestamp
            body = {key: value for key, value in entry.items() if key not in {"entry_hash", "signatures"}}
            entry_hash = canonical_sha256(body)
            if entry.get("entry_hash") != entry_hash:
                return False, "LEDGER_ENTRY_HASH_MISMATCH"
            signatures = entry.get("signatures")
            if not isinstance(signatures, list) or len(signatures) < 2:
                return False, "LEDGER_DUAL_SIGNATURES_REQUIRED"
            signer_ids: list[str] = []
            for signature_record in signatures:
                if not isinstance(signature_record, Mapping):
                    return False, "LEDGER_SIGNATURE_RECORD_INVALID"
                signer_id = signature_record.get("signer_id")
                if not _has_text(signer_id):
                    return False, "LEDGER_SIGNER_ID_MISSING"
                signer_ids.append(str(signer_id))
            if len(set(signer_ids)) != len(signer_ids):
                return False, "LEDGER_SIGNER_SEPARATION_FAILED"
            roles = {
                str(signers.get(signer_id, {}).get("role", ""))
                for signer_id in signer_ids
                if isinstance(signers.get(signer_id), Mapping)
            }
            if not {"constitutional_council", "proof_engine"}.issubset(roles):
                return False, "LEDGER_REQUIRED_ROLES_MISSING"
            signed_payload = {
                "entry_hash": entry_hash,
                "sequence": expected_sequence,
                "previous_hash": previous_hash,
            }
            for signature_record in signatures:
                signer_id = str(signature_record["signer_id"])
                if not _verify_signature(
                    signature_verifier,
                    signers.get(signer_id),
                    signed_payload,
                    signature_record.get("signature"),
                ):
                    return False, "LEDGER_SIGNATURE_INVALID"
            previous_hash = entry_hash
        return True, "RATIFICATION_LEDGER_CHAIN_VALID"

    def failure_model() -> tuple[bool, str]:
        item = bundle.get("failure_sovereignty")
        if not isinstance(item, Mapping):
            return False, "FAILURE_MODEL_MISSING"
        classes = item.get("failure_classes")
        normalized = {str(value).upper().replace(" ", "_") for value in classes} if isinstance(classes, list) else set()
        invariant = str(item.get("failure_invariant", "")).strip().lower().rstrip(".")
        valid = (
            _FAILURE_CLASSES.issubset(normalized)
            and invariant == "no failure may alter historical truth"
            and item.get("preserve_previous_accepted_state") is True
        )
        return valid, "FAILURE_MODEL_COMPLETE" if valid else "FAILURE_MODEL_INCOMPLETE"

    def conflict_resolution() -> tuple[bool, str]:
        item = bundle.get("conflict_resolution")
        if not isinstance(item, Mapping):
            return False, "CONFLICT_RESOLVER_MISSING"
        required = ("priority", "authority", "proof", "override_rules")
        valid = (
            all(_has_text(item.get(key)) for key in required)
            and item.get("deterministic") is True
            and item.get("fail_closed") is True
            and item.get("unverified_override_denied") is True
        )
        return valid, "CONFLICT_RESOLVER_VALID" if valid else "CONFLICT_RESOLVER_POLICY_INVALID"

    def proof_obligations() -> tuple[bool, str]:
        section = bundle.get("proof_obligations")
        claims = section.get("claims") if isinstance(section, Mapping) else None
        proof_ids = set(_proofs(bundle))
        if not isinstance(claims, list) or not claims:
            return False, "PROOF_OBLIGATIONS_MISSING"
        seen_claims: set[str] = set()
        for claim in claims:
            if not isinstance(claim, Mapping):
                return False, "CLAIM_RECORD_INVALID"
            claim_id = claim.get("claim_id")
            required = claim.get("required_proof_ids")
            evidence = claim.get("evidence_refs")
            if not _has_text(claim_id) or claim_id in seen_claims:
                return False, "CLAIM_ID_MISSING_OR_DUPLICATED"
            if claim.get("status") != "SATISFIED":
                return False, f"CLAIM_NOT_SATISFIED:{claim_id}"
            if not isinstance(required, list) or not required or not set(required).issubset(proof_ids):
                return False, f"CLAIM_PROOF_MISSING:{claim_id}"
            if not isinstance(evidence, list) or not evidence:
                return False, f"CLAIM_EVIDENCE_MISSING:{claim_id}"
            for ref in evidence:
                if not isinstance(ref, Mapping) or not _has_text(ref.get("ref")) or not _is_hash(ref.get("sha256")):
                    return False, f"CLAIM_EVIDENCE_INVALID:{claim_id}"
            seen_claims.add(str(claim_id))
        return True, "PROOF_OBLIGATIONS_SATISFIED"

    def amendment_control() -> tuple[bool, str]:
        item = bundle.get("constitutional_evolution_control")
        if not isinstance(item, Mapping):
            return False, "AMENDMENT_POLICY_MISSING"
        threshold = item.get("approval_threshold")
        roles = item.get("required_signatures")
        policy_valid = (
            isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and 0 < threshold <= 1
            and isinstance(roles, list)
            and len(roles) >= 2
            and len(set(roles)) == len(roles)
            and all(_has_text(role) for role in roles)
            and item.get("human_approval_required") is True
            and item.get("requester_cannot_approve") is True
            and item.get("preparer_cannot_approve") is True
            and isinstance(item.get("effective_after_seconds"), int)
            and item.get("effective_after_seconds") >= 0
        )
        if not policy_valid:
            return False, "AMENDMENT_POLICY_INVALID"
        active = item.get("active_amendment")
        if active is None:
            return True, "AMENDMENT_POLICY_VALID_NO_ACTIVE_AMENDMENT"
        if not isinstance(active, Mapping):
            return False, "ACTIVE_AMENDMENT_INVALID"
        amendment_id = active.get("amendment_id")
        requester = active.get("requester_id")
        preparer = active.get("preparer_id")
        approvals = active.get("approvals")
        if not _has_text(amendment_id) or not isinstance(approvals, list):
            return False, "ACTIVE_AMENDMENT_FIELDS_MISSING"
        approval_roles: set[str] = set()
        approval_signers: set[str] = set()
        for approval in approvals:
            if not isinstance(approval, Mapping):
                return False, "AMENDMENT_APPROVAL_INVALID"
            signer_id = approval.get("signer_id")
            role = approval.get("role")
            if (
                not _has_text(signer_id)
                or not _has_text(role)
                or signer_id in {requester, preparer}
                or role not in roles
                or role in approval_roles
                or signer_id in approval_signers
            ):
                return False, "AMENDMENT_SEPARATION_OF_DUTIES_FAILED"
            approval_time = _timestamp(approval.get("signed_at"))
            if approval_time is None:
                return False, "AMENDMENT_APPROVAL_TIMESTAMP_INVALID"
            payload = {
                "amendment_id": amendment_id,
                "signer_id": signer_id,
                "role": role,
                "signed_at": approval.get("signed_at"),
                "affected_omegaids": active.get("affected_omegaids", []),
            }
            if not _verify_signature(
                signature_verifier,
                signers.get(str(signer_id)),
                payload,
                approval.get("signature"),
            ):
                return False, "AMENDMENT_APPROVAL_SIGNATURE_INVALID"
            approval_roles.add(str(role))
            approval_signers.add(str(signer_id))
        if len(approval_roles) / len(roles) < float(threshold):
            return False, "AMENDMENT_APPROVAL_THRESHOLD_NOT_MET"
        proposed_at = _timestamp(active.get("proposed_at"))
        effective_at = _timestamp(active.get("effective_at"))
        if proposed_at is None or effective_at is None:
            return False, "AMENDMENT_EFFECTIVE_TIMES_MISSING"
        if (effective_at - proposed_at).total_seconds() < item["effective_after_seconds"]:
            return False, "AMENDMENT_COOLDOWN_NOT_MET"
        return True, "ACTIVE_AMENDMENT_RATIFIED"

    def trust_root() -> tuple[bool, str]:
        item = bundle.get("trust_root")
        if not isinstance(item, Mapping):
            return False, "TRUST_ROOT_MISSING"
        fingerprint = item.get("public_key_fingerprint")
        if not _is_hash(fingerprint) or not _is_hash(trusted_root_hash):
            return False, "TRUST_ANCHOR_NOT_PINNED"
        if fingerprint != trusted_root_hash:
            return False, "TRUST_ROOT_MISMATCH"
        if item.get("revoked") is not False or not _timestamp(item.get("issued_at")):
            return False, "TRUST_ROOT_REVOKED_OR_INVALID"
        if signature_verifier is None:
            return False, "CRYPTOGRAPHIC_VERIFIER_UNAVAILABLE"
        payload = {
            "root_id": item.get("root_id"),
            "public_key_fingerprint": fingerprint,
            "issued_at": item.get("issued_at"),
            "revoked": item.get("revoked"),
        }
        if not _verify_signature(signature_verifier, item, payload, item.get("signature")):
            return False, "TRUST_ROOT_REGISTRATION_SIGNATURE_INVALID"
        return True, "TRUST_ROOT_PINNED_AND_VERIFIED"

    def semantic_drift() -> tuple[bool, str]:
        item = bundle.get("semantic_drift")
        snapshot = item.get("semantic_snapshot") if isinstance(item, Mapping) else None
        if not isinstance(snapshot, Mapping):
            return False, "SEMANTIC_SNAPSHOT_MISSING"
        drift = item.get("drift_level")
        if drift not in {"none", "low", "medium", "critical"}:
            return False, "SEMANTIC_DRIFT_LEVEL_INVALID"
        generated = _timestamp(snapshot.get("generated_at"))
        if not _has_text(snapshot.get("invariant_id")) or not _has_text(snapshot.get("ontology_version")) or generated is None:
            return False, "SEMANTIC_SNAPSHOT_FIELDS_INVALID"
        body = {key: value for key, value in snapshot.items() if key != "semantic_hash"}
        if snapshot.get("semantic_hash") != canonical_sha256(body):
            return False, "SEMANTIC_SNAPSHOT_HASH_MISMATCH"
        if drift == "critical":
            return False, "CRITICAL_SEMANTIC_DRIFT_RATIFICATION_BLOCKED"
        if drift != "none":
            return False, "SEMANTIC_DRIFT_REQUIRES_REVIEW"
        return True, "SEMANTIC_SNAPSHOT_STABLE"

    def sovereign_audit() -> tuple[bool, str]:
        item = bundle.get("sovereign_audit")
        if not isinstance(item, Mapping):
            return False, "SOVEREIGN_AUDIT_MISSING"
        auditor = item.get("auditor_id")
        owners = item.get("controlled_engine_owner_ids")
        scope = item.get("scope")
        if not _has_text(auditor) or not isinstance(owners, list) or not isinstance(scope, list) or not scope:
            return False, "SOVEREIGN_AUDIT_FIELDS_MISSING"
        if auditor in owners:
            return False, "SELF_AUDIT_FORBIDDEN"
        if item.get("independent") is not True or str(item.get("result", "")).upper() != "PASS":
            return False, "INDEPENDENT_AUDIT_NOT_PASSED"
        report_body = {key: value for key, value in item.items() if key not in {"audit_hash", "signature"}}
        if item.get("audit_hash") != canonical_sha256(report_body):
            return False, "AUDIT_DIGEST_MISMATCH"
        if _timestamp(item.get("timestamp")) is None:
            return False, "AUDIT_TIMESTAMP_INVALID"
        payload = {
            "audit_hash": item.get("audit_hash"),
            "auditor_id": auditor,
            "scope": scope,
            "result": item.get("result"),
            "timestamp": item.get("timestamp"),
        }
        if not _verify_signature(signature_verifier, signers.get(str(auditor)), payload, item.get("signature")):
            return False, "AUDIT_SIGNATURE_INVALID"
        return True, "INDEPENDENT_AUDIT_VALID"

    validators = [
        ("L01_CONSTITUTIONAL_BINDING", constitutional_binding),
        ("L02_META_PROOF", meta_proof),
        ("L03_SOVEREIGN_CLOSURE_ENGINE", closure_engine),
        ("L04_HISTORICAL_RATIFICATION_LEDGER", historical_ledger),
        ("L05_FAILURE_SOVEREIGNTY", failure_model),
        ("L06_CONFLICT_RESOLUTION", conflict_resolution),
        ("L07_PROOF_OBLIGATIONS", proof_obligations),
        ("L08_CONSTITUTIONAL_EVOLUTION_CONTROL", amendment_control),
        ("L09_TRUST_ROOT_REGISTRY", trust_root),
        ("L10_SEMANTIC_DRIFT_DETECTION", semantic_drift),
        ("L11_SOVEREIGN_AUDIT_DOMAIN", sovereign_audit),
    ]
    checks = tuple(_safe_check(check_id, validator) for check_id, validator in validators)
    status = "CLOSED" if all(item.passed for item in checks) else "BLOCKED"
    report_body = {
        "subject": subject,
        "status": status,
        "checks": [asdict(item) for item in checks],
    }
    return ClosureReport(
        subject=subject,
        status=status,
        checks=checks,
        report_digest=canonical_sha256(report_body),
    )
