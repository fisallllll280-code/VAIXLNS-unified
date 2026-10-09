"""Deterministic evidence compilation and fail-closed admission primitives.

ARC-X normalizes source receipts, evidence, claims, and proof obligations into
an Epistemic Intermediate Representation (EIR). Compilation never grants
authority. External effects require a trusted host-supplied authority verifier.
The caller is responsible for authenticating that verifier and its inputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = "arc-x.eir.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_PINNED_REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})$", re.IGNORECASE)


class Stance(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    QUALIFIES = "QUALIFIES"
    NEUTRAL = "NEUTRAL"


class ClaimKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    INFERENCE = "INFERENCE"
    DESIGN = "DESIGN"
    IMPLEMENTATION = "IMPLEMENTATION"
    RUNTIME = "RUNTIME"


class EvidenceKind(str, Enum):
    SOURCE_EXTRACT = "SOURCE_EXTRACT"
    SECONDARY_SOURCE = "SECONDARY_SOURCE"
    TEST_RESULT = "TEST_RESULT"
    RUNTIME_TRACE = "RUNTIME_TRACE"
    PROOF_ARTIFACT = "PROOF_ARTIFACT"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"


class AdmissionDecision(str, Enum):
    BLOCKED = "BLOCKED"
    ELIGIBLE_FOR_REVIEW = "ELIGIBLE_FOR_REVIEW"
    VERIFIED = "VERIFIED"
    ADMITTED = "ADMITTED"


@dataclass(frozen=True)
class SourceReceipt:
    """Pinned source identity. Mutable refs such as main/latest are rejected."""

    source_id: str
    repository: str
    revision: str
    path: str
    content_sha256: str
    retrieved_at: str
    retrieval_status: str = "SUCCESS"
    parser_version: str = "1.0.0"
    source_uri: str = ""

    def __post_init__(self) -> None:
        for name in ("source_id", "repository", "revision", "path", "retrieved_at"):
            if not getattr(self, name).strip():
                raise ValueError(f"SOURCE_{name.upper()}_REQUIRED")
        if not _PINNED_REVISION.fullmatch(self.revision):
            raise ValueError("SOURCE_REVISION_MUST_BE_IMMUTABLE_PIN")
        if not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("SOURCE_CONTENT_HASH_MUST_BE_SHA256")
        object.__setattr__(self, "content_sha256", self.content_sha256.lower())
        try:
            parsed_time = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
            if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("SOURCE_RETRIEVAL_TIMESTAMP_MUST_BE_AWARE_ISO8601") from exc
        if self.retrieval_status != "SUCCESS":
            raise ValueError("SOURCE_RETRIEVAL_NOT_SUCCESSFUL")
        if not self.parser_version.strip():
            raise ValueError("PARSER_VERSION_REQUIRED")


@dataclass(frozen=True)
class EvidenceRecord:
    """Evidence binds a claim to an immutable source receipt and a typed result."""

    evidence_id: str
    source_id: str
    kind: EvidenceKind
    statement: str
    claim_id: str = ""
    stance: Stance = Stance.NEUTRAL
    result: str = "UNKNOWN"
    artifact_sha256: str = ""

    def __post_init__(self) -> None:
        for name in ("evidence_id", "source_id", "statement"):
            if not getattr(self, name).strip():
                raise ValueError(f"EVIDENCE_{name.upper()}_REQUIRED")
        if self.result not in {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}:
            raise ValueError("EVIDENCE_RESULT_INVALID")
        if self.artifact_sha256 and not _SHA256.fullmatch(self.artifact_sha256):
            raise ValueError("EVIDENCE_ARTIFACT_HASH_MUST_BE_SHA256")
        if self.artifact_sha256:
            object.__setattr__(self, "artifact_sha256", self.artifact_sha256.lower())
        if self.kind in {EvidenceKind.TEST_RESULT, EvidenceKind.PROOF_ARTIFACT}:
            if self.result in {"PASS", "FAIL"} and not self.artifact_sha256:
                raise ValueError("TEST_OR_PROOF_RESULT_REQUIRES_ARTIFACT_HASH")


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    statement: str
    kind: ClaimKind
    required: bool = True

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.statement.strip():
            raise ValueError("CLAIM_ID_AND_STATEMENT_REQUIRED")


@dataclass(frozen=True)
class ProofObligation:
    obligation_id: str
    claim_id: str
    description: str
    required: bool = True
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("obligation_id", "claim_id", "description"):
            if not getattr(self, name).strip():
                raise ValueError(f"PROOF_OBLIGATION_{name.upper()}_REQUIRED")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("DUPLICATE_PROOF_EVIDENCE_ID")


@dataclass(frozen=True)
class AuthorityApproval:
    """Approval assertion; authenticity must be checked by the trusted host."""

    approval_id: str
    actor_id: str
    scope: str
    decision: str = "APPROVE"

    def __post_init__(self) -> None:
        if not self.approval_id.strip() or not self.actor_id.strip() or not self.scope.strip():
            raise ValueError("AUTHORITY_APPROVAL_FIELDS_REQUIRED")


@dataclass(frozen=True)
class CompilationResult:
    eir: Mapping[str, Any]
    eir_sha256: str
    epistemic_state: str
    findings: tuple[Mapping[str, Any], ...]
    claim_results: Mapping[str, str]
    obligation_results: Mapping[str, str]

    @property
    def has_conflicts(self) -> bool:
        return any(item.get("code") == "CONTRADICTORY_EVIDENCE" for item in self.findings)

    @property
    def has_blocking_findings(self) -> bool:
        return any(item.get("blocking", False) for item in self.findings)

    @property
    def required_obligations_satisfied(self) -> bool:
        claims = [item["claim_id"] for item in self.eir.get("claims", []) if item["required"]]
        obligations = self.eir.get("proof_obligations", [])
        required = [item for item in obligations if item["required"]]
        covered = {item["claim_id"] for item in required}
        return (
            bool(claims)
            and bool(required)
            and set(claims) <= covered
            and all(self.obligation_results.get(item["obligation_id"]) == "SATISFIED" for item in required)
        )

    @property
    def proof_scope_complete(self) -> bool:
        """Structural completeness only; external evidence authenticity is not checked here."""
        required_claims = [
            item["claim_id"] for item in self.eir.get("claims", []) if item["required"]
        ]
        return (
            self.epistemic_state == "READY_FOR_REVIEW"
            and not self.has_blocking_findings
            and not self.has_conflicts
            and bool(required_claims)
            and all(self.claim_results.get(cid) == "SUPPORTED_NOT_PROVEN" for cid in required_claims)
            and self.required_obligations_satisfied
        )


@dataclass(frozen=True)
class AdmissionResult:
    decision: AdmissionDecision
    action: str
    reason_codes: tuple[str, ...]
    eir_sha256: str
    approval_id: str = ""


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible values deterministically; reject opaque objects."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _record(record: Any) -> dict[str, Any]:
    result = asdict(record)
    for key, value in tuple(result.items()):
        if isinstance(value, Enum):
            result[key] = value.value
        elif isinstance(value, tuple):
            result[key] = [
                item.value if isinstance(item, Enum) else item for item in value
            ]
    return result


def _finding(code: str, message: str, *, blocking: bool = True, refs: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "blocking": blocking,
        "source_refs": sorted(set(refs)),
    }


def compile_eir(
    sources: Sequence[SourceReceipt],
    evidence: Sequence[EvidenceRecord],
    claims: Sequence[ClaimRecord],
    proof_obligations: Sequence[ProofObligation] = (),
) -> CompilationResult:
    """Compile evidence without silently resolving contradictions or granting authority.

    Identical inputs produce identical EIR JSON and SHA-256. Timestamps are
    caller-supplied receipt data, never generated by this function.
    """
    findings: list[dict[str, Any]] = []
    source_rows = [_record(item) for item in sources]
    evidence_rows = [_record(item) for item in evidence]
    claim_rows = [_record(item) for item in claims]
    obligation_rows = [_record(item) for item in proof_obligations]

    def index_unique(rows: list[dict[str, Any]], key: str, kind: str) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for row in rows:
            ident = row[key]
            if ident in indexed:
                findings.append(_finding(f"DUPLICATE_{kind}_ID", f"Duplicate {kind.lower()} identifier: {ident}."))
            else:
                indexed[ident] = row
        return indexed

    source_index = index_unique(source_rows, "source_id", "SOURCE")
    evidence_index = index_unique(evidence_rows, "evidence_id", "EVIDENCE")
    claim_index = index_unique(claim_rows, "claim_id", "CLAIM")
    obligation_index = index_unique(obligation_rows, "obligation_id", "OBLIGATION")

    for row in evidence_rows:
        if row["source_id"] not in source_index:
            findings.append(_finding("DANGLING_SOURCE_REFERENCE", f"Evidence {row['evidence_id']} references missing source {row['source_id']}.", refs=(row["evidence_id"],)))
        if row["claim_id"] and row["claim_id"] not in claim_index:
            findings.append(_finding("DANGLING_CLAIM_REFERENCE", f"Evidence {row['evidence_id']} references missing claim {row['claim_id']}.", refs=(row["evidence_id"],)))

    claim_results: dict[str, str] = {}
    for claim_id, claim in sorted(claim_index.items()):
        attached = [
            row for row in evidence_rows
            if row["claim_id"] == claim_id and row["source_id"] in source_index
        ]
        stances = {row["stance"] for row in attached}
        if "SUPPORTS" in stances and "REFUTES" in stances:
            claim_results[claim_id] = "CONFLICT"
            findings.append(_finding(
                "CONTRADICTORY_EVIDENCE",
                f"Claim {claim_id} has both supporting and refuting evidence; reconciliation is required.",
                refs=[row["evidence_id"] for row in attached],
            ))
        elif "SUPPORTS" in stances:
            claim_results[claim_id] = "SUPPORTED_NOT_PROVEN"
        else:
            claim_results[claim_id] = "UNSUPPORTED"
            findings.append(_finding(
                "CLAIM_WITHOUT_SUPPORT",
                f"Claim {claim_id} has no source-linked supporting evidence.",
                blocking=bool(claim["required"]),
                refs=[row["evidence_id"] for row in attached],
            ))

    obligation_results: dict[str, str] = {}
    accepted_proof_kinds = {EvidenceKind.TEST_RESULT.value, EvidenceKind.PROOF_ARTIFACT.value, EvidenceKind.RUNTIME_TRACE.value}
    for obligation_id, obligation in sorted(obligation_index.items()):
        claim_id = obligation["claim_id"]
        if claim_id not in claim_index:
            obligation_results[obligation_id] = "INVALID"
            findings.append(_finding("OBLIGATION_CLAIM_MISSING", f"Obligation {obligation_id} references missing claim {claim_id}."))
            continue
        if not obligation["evidence_ids"]:
            obligation_results[obligation_id] = "OPEN"
        else:
            refs_exist = all(eid in evidence_index for eid in obligation["evidence_ids"])
            proof_rows = [evidence_index[eid] for eid in obligation["evidence_ids"] if eid in evidence_index]
            eligible = refs_exist and bool(proof_rows) and all(
                item["source_id"] in source_index
                and item["claim_id"] == claim_id
                and item["kind"] in accepted_proof_kinds
                and item["result"] == "PASS"
                and bool(item["artifact_sha256"])
                for item in proof_rows
            )
            obligation_results[obligation_id] = "SATISFIED" if eligible else "OPEN"
        if obligation_results[obligation_id] != "SATISFIED" and obligation["required"]:
            findings.append(_finding(
                "PROOF_OBLIGATION_OPEN",
                f"Required obligation {obligation_id} lacks valid passing test/runtime/proof evidence.",
                refs=obligation["evidence_ids"],
            ))

    required_claim_ids = {ident for ident, item in claim_index.items() if item["required"]}
    claims_with_required_obligations = {
        item["claim_id"] for item in obligation_rows if item["required"]
    }
    for claim_id in sorted(required_claim_ids - claims_with_required_obligations):
        findings.append(_finding(
            "REQUIRED_CLAIM_WITHOUT_PROOF_OBLIGATION",
            f"Required claim {claim_id} has no required proof obligation.",
        ))

    # References and claims are sorted to ensure the compilation is input-order independent.
    eir = {
        "schema_version": SCHEMA_VERSION,
        "epistemic_rule": "OBSERVATION != EVIDENCE != INFERENCE != PROOF != AUTHORITY",
        "sources": sorted(source_rows, key=lambda row: (row["source_id"], row["path"])),
        "evidence": sorted(evidence_rows, key=lambda row: (row["evidence_id"], row["source_id"])),
        "claims": sorted(claim_rows, key=lambda row: row["claim_id"]),
        "proof_obligations": sorted(obligation_rows, key=lambda row: row["obligation_id"]),
        "claim_results": dict(sorted(claim_results.items())),
        "obligation_results": dict(sorted(obligation_results.items())),
        "findings": sorted(findings, key=lambda item: (item["code"], item["message"], item["source_refs"])),
        "authority": {"decision": "PENDING", "authority_granted_by_compiler": False},
    }
    severe = any(item["blocking"] for item in findings)
    conflict = any(item["code"] == "CONTRADICTORY_EVIDENCE" for item in findings)
    if conflict:
        state = "CONFLICT"
    elif severe:
        state = "MISSING"
    elif findings or not obligation_rows:
        state = "PARTIAL"
    else:
        state = "READY_FOR_REVIEW"
    encoded = canonical_json(eir)
    return CompilationResult(
        eir=eir,
        eir_sha256=sha256_text(encoded),
        epistemic_state=state,
        findings=tuple(eir["findings"]),
        claim_results=claim_results,
        obligation_results=obligation_results,
    )


def evaluate_admission(
    compilation: CompilationResult,
    action: str,
    approval: AuthorityApproval | None = None,
    evidence_verifier: Callable[[CompilationResult], bool] | None = None,
    authority_verifier: Callable[[AuthorityApproval, str], bool] | None = None,
) -> AdmissionResult:
    """Fail-closed gate with separate evidence-authenticity and authority checks.

    The trusted evidence verifier must independently validate source hashes,
    artifact hashes, evidence origin/signatures, and the declared proof scope.
    The trusted authority verifier must authenticate the approver and requested
    scope. Both callbacks are host trust boundaries, not user-supplied policies.
    This module never executes code, authenticates actors, or commits canonical state.
    """
    action = action.strip().upper()
    safe_actions = {"READ", "RESEARCH", "VERIFY", "EXECUTE", "CANONICAL_COMMIT"}
    if action not in safe_actions:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("UNKNOWN_ACTION",), compilation.eir_sha256)

    if action in {"READ", "RESEARCH"}:
        codes = ["NO_EXTERNAL_EFFECT"]
        if compilation.has_conflicts:
            codes.append("CONFLICT_PRESERVED_FOR_RESEARCH")
        return AdmissionResult(AdmissionDecision.ELIGIBLE_FOR_REVIEW, action, tuple(codes), compilation.eir_sha256)

    if compilation.epistemic_state == "CONFLICT" or compilation.has_conflicts:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("UNRESOLVED_CONFLICT",), compilation.eir_sha256)
    if compilation.has_blocking_findings or compilation.epistemic_state in {"MISSING", "PARTIAL"}:
        codes = tuple(sorted({str(item["code"]) for item in compilation.findings if item.get("blocking")}))
        return AdmissionResult(AdmissionDecision.BLOCKED, action, codes or ("EVIDENCE_INCOMPLETE",), compilation.eir_sha256)
    if not compilation.proof_scope_complete:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("DECLARED_PROOF_SCOPE_INCOMPLETE",), compilation.eir_sha256)
    if evidence_verifier is None:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("TRUSTED_EVIDENCE_VERIFIER_REQUIRED",), compilation.eir_sha256)
    try:
        evidence_ok = bool(evidence_verifier(compilation))
    except Exception:
        evidence_ok = False
    if not evidence_ok:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("EVIDENCE_ATTESTATION_FAILED",), compilation.eir_sha256)

    if action == "VERIFY":
        return AdmissionResult(
            AdmissionDecision.VERIFIED, action,
            ("DECLARED_SCOPE_VERIFIED_BY_TRUSTED_EVIDENCE_VERIFIER",),
            compilation.eir_sha256,
        )

    expected_scope = "execution" if action == "EXECUTE" else "canonical-admission"
    if approval is None or authority_verifier is None:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("TRUSTED_AUTHORITY_VERIFIER_REQUIRED",), compilation.eir_sha256)
    if approval.decision != "APPROVE" or approval.scope != expected_scope:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("AUTHORITY_SCOPE_OR_DECISION_MISMATCH",), compilation.eir_sha256, approval.approval_id)
    try:
        authority_ok = bool(authority_verifier(approval, expected_scope))
    except Exception:
        authority_ok = False
    if not authority_ok:
        return AdmissionResult(AdmissionDecision.BLOCKED, action, ("AUTHORITY_VERIFICATION_FAILED",), compilation.eir_sha256, approval.approval_id)
    return AdmissionResult(AdmissionDecision.ADMITTED, action, ("EVIDENCE_AND_AUTHORITY_GATES_PASSED",), compilation.eir_sha256, approval.approval_id)
