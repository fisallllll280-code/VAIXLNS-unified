"""Adversarial acceptance tests for the Ω³ bounded admission kernel."""
from __future__ import annotations

from dataclasses import replace
import pytest

from canon.kernel.omega3_kernel import (
    AdmissionPolicy,
    AdmissionStatus,
    AuthorityGrant,
    EvidenceReceipt,
    ProofDebtItem,
    SovereignState,
    TransitionCandidate,
    calculate_proof_debt,
    canonical_json,
    create_audit_event,
    evaluate_transition,
    replay_audit_events,
    verify_event_chain,
)

NOW = "2026-10-10T12:00:00Z"
OBJECT_ID = "VS.81000.SUB.01"
CONSTITUTION_HASH = "c" * 64
ONTOLOGY_HASH = "d" * 64
GENESIS_HASH = "b" * 64


def build_case(source_ids=("source-A",)):
    current = SovereignState(
        object_id=OBJECT_ID,
        revision=0,
        identity={"root_id": "Ω0_GENESIS_CORE", "genesis_hash": GENESIS_HASH},
        contracts={
            "schema_version": "1.0",
            "constitution_hash": CONSTITUTION_HASH,
            "ontology_hash": ONTOLOGY_HASH,
            "schema_major": 1,
        },
        authority={"policy_version": "omega3-v1"},
        observations=({"kind": "INITIALIZED", "sequence": 0},),
        evidence_refs=(),
    )
    receipt_ids = tuple(f"receipt-{index + 1}" for index in range(len(source_ids)))
    proposed = SovereignState(
        object_id=OBJECT_ID,
        revision=1,
        identity={"root_id": "Ω0_GENESIS_CORE", "genesis_hash": GENESIS_HASH},
        contracts={
            "schema_version": "1.0",
            "constitution_hash": CONSTITUTION_HASH,
            "ontology_hash": ONTOLOGY_HASH,
            "schema_major": 1,
        },
        authority={"policy_version": "omega3-v1"},
        observations=(
            {"kind": "INITIALIZED", "sequence": 0},
            {"kind": "OBSERVATION", "sequence": 1, "result": "candidate"},
        ),
        evidence_refs=receipt_ids,
    )
    grant = AuthorityGrant(
        grant_id="grant-1",
        principal_id="release-controller",
        subject_id=OBJECT_ID,
        action="UPDATE",
        scopes=("UPDATE", f"object:{OBJECT_ID}"),
        policy_version="omega3-v1",
        issued_at="2026-10-10T11:00:00Z",
        expires_at="2026-10-10T13:00:00Z",
        verification_ref="signature:grant-1",
    )
    verifiers = ("witness-A", "witness-B", "witness-C")
    evidence = tuple(
        EvidenceReceipt(
            receipt_id=receipt_id,
            source_id=source_id,
            claim_digest=proposed.digest,
            evidence_digest=(str(index + 1) * 64),
            observed_at="2026-10-10T11:30:00Z",
            expires_at="2026-10-10T13:00:00Z",
            verifier_id=verifiers[index],
            verification_ref=f"witness:{receipt_id}",
        )
        for index, (receipt_id, source_id) in enumerate(zip(receipt_ids, source_ids))
    )
    candidate = TransitionCandidate(
        action="UPDATE",
        expected_state_digest=current.digest,
        grant=grant,
        evidence=evidence,
    )
    policy = AdmissionPolicy(
        version="omega3-v1",
        allowed_actions=("UPDATE",),
        trusted_principals=("release-controller",),
        trusted_verifiers=verifiers,
        required_evidence_count=1,
        minimum_distinct_source_ids=1,
        max_evidence_age_seconds=7200,
        max_grant_age_seconds=7200,
    )
    return current, proposed, candidate, policy


def auth_ok(grant):
    return grant.verification_ref == "signature:grant-1"


def evidence_ok(receipt):
    return receipt.verification_ref == f"witness:{receipt.receipt_id}"


def evaluate(case, **overrides):
    current, proposed, candidate, policy = case
    kwargs = {
        "evaluated_at": NOW,
        "authority_verifier": auth_ok,
        "evidence_verifier": evidence_ok,
    }
    kwargs.update(overrides)
    return evaluate_transition(current, proposed, candidate, policy, **kwargs)


def test_admissible_transition_is_only_a_candidate_not_a_commit():
    result = evaluate(build_case())
    assert result.status is AdmissionStatus.ADMIT
    assert result.authority_verified is True
    assert result.verified_evidence_ids == ("receipt-1",)
    assert result.commit_performed is False


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})


def test_non_finite_json_numbers_are_rejected():
    with pytest.raises(ValueError):
        canonical_json({"untrusted": float("nan")})


def test_state_payload_is_deeply_immutable():
    current, _, _, _ = build_case()
    with pytest.raises(TypeError):
        current.identity["root_id"] = "changed"
    with pytest.raises(TypeError):
        current.observations[0]["kind"] = "rewritten"


def test_missing_authority_verifier_quarantines():
    result = evaluate(build_case(), authority_verifier=None)
    assert result.status is AdmissionStatus.QUARANTINE
    assert "AUTHORITY_VERIFIER_UNAVAILABLE" in result.reasons


def test_missing_evidence_verifier_quarantines():
    result = evaluate(build_case(), evidence_verifier=None)
    assert result.status is AdmissionStatus.QUARANTINE
    assert "EVIDENCE_VERIFIER_UNAVAILABLE" in result.reasons


def test_authority_verifier_failure_rejects():
    result = evaluate(build_case(), authority_verifier=lambda grant: False)
    assert result.status is AdmissionStatus.REJECT
    assert "AUTHORITY_VERIFICATION_FAILED" in result.reasons


def test_authority_verifier_exception_quarantines():
    def unavailable(_grant):
        raise RuntimeError("verifier service unavailable")

    result = evaluate(build_case(), authority_verifier=unavailable)
    assert result.status is AdmissionStatus.QUARANTINE
    assert "AUTHORITY_VERIFIER_ERROR" in result.reasons


def test_unsupported_action_is_rejected():
    current, proposed, candidate, policy = build_case()
    changed = replace(candidate, action="DELETE")
    result = evaluate_transition(
        current, proposed, changed, policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "ACTION_NOT_ALLOWED_BY_POLICY" in result.reasons


def test_stale_compare_and_swap_digest_is_rejected():
    current, proposed, candidate, policy = build_case()
    changed = replace(candidate, expected_state_digest="0" * 64)
    result = evaluate_transition(
        current, proposed, changed, policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "STALE_OR_INVALID_EXPECTED_STATE_DIGEST" in result.reasons


def test_revision_must_advance_by_one():
    current, _, candidate, policy = build_case()
    proposed = SovereignState(
        object_id=current.object_id,
        revision=3,
        identity=current.identity,
        contracts=current.contracts,
        authority=current.authority,
        observations=current.observations + ({"kind": "OBSERVATION"},),
        evidence_refs=("receipt-1",),
    )
    receipt = replace(candidate.evidence[0], claim_digest=proposed.digest)
    candidate = replace(candidate, evidence=(receipt,))
    result = evaluate_transition(
        current, proposed, candidate, policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "REVISION_MUST_ADVANCE_BY_ONE" in result.reasons


def test_protected_constitutional_contract_cannot_change_silently():
    current, proposed, candidate, policy = build_case()
    altered_contracts = dict(proposed.contracts)
    altered_contracts["constitution_hash"] = "e" * 64
    proposed = SovereignState(
        object_id=proposed.object_id,
        revision=proposed.revision,
        identity=proposed.identity,
        contracts=altered_contracts,
        authority=proposed.authority,
        observations=proposed.observations,
        evidence_refs=proposed.evidence_refs,
    )
    candidate = replace(
        candidate,
        evidence=(replace(candidate.evidence[0], claim_digest=proposed.digest),),
    )
    result = evaluate_transition(
        current, proposed, candidate, policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "PROTECTED_CONTRACT_MUTATION:constitution_hash" in result.reasons


def test_observation_history_cannot_be_rewritten():
    current, proposed, candidate, policy = build_case()
    proposed = SovereignState(
        object_id=proposed.object_id,
        revision=proposed.revision,
        identity=proposed.identity,
        contracts=proposed.contracts,
        authority=proposed.authority,
        observations=({"kind": "REPLACED"},),
        evidence_refs=proposed.evidence_refs,
    )
    candidate = replace(
        candidate,
        evidence=(replace(candidate.evidence[0], claim_digest=proposed.digest),),
    )
    result = evaluate_transition(
        current, proposed, candidate, policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "OBSERVATION_HISTORY_REWRITE" in result.reasons


def test_wrongly_bound_evidence_is_rejected():
    current, proposed, candidate, policy = build_case()
    bad = replace(candidate.evidence[0], claim_digest="0" * 64)
    result = evaluate_transition(
        current, proposed, replace(candidate, evidence=(bad,)), policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "EVIDENCE_NOT_BOUND_TO_PROPOSED_STATE:receipt-1" in result.reasons


def test_stale_evidence_leads_to_unknown_not_success_or_failure():
    current, proposed, candidate, policy = build_case()
    stale = replace(
        candidate.evidence[0],
        observed_at="2026-10-10T08:00:00Z",
        expires_at="2026-10-10T09:00:00Z",
    )
    result = evaluate_transition(
        current, proposed, replace(candidate, evidence=(stale,)), policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.UNKNOWN
    assert "EVIDENCE_STALE_EXCLUDED:receipt-1" in result.warnings


def test_unique_source_labels_do_not_imply_independence():
    case = build_case(source_ids=("shared-source", "shared-source"))
    current, proposed, candidate, policy = case
    stricter_policy = replace(
        policy, required_evidence_count=2, minimum_distinct_source_ids=2
    )
    result = evaluate_transition(
        current, proposed, candidate, stricter_policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.UNKNOWN
    assert result.checks["verified_evidence_count"] is True
    assert result.checks["distinct_source_count"] is False


def test_missing_evidence_is_unknown():
    current, proposed, candidate, policy = build_case(source_ids=())
    result = evaluate((current, proposed, candidate, policy))
    assert result.status is AdmissionStatus.UNKNOWN
    assert "VERIFIED_EVIDENCE_INSUFFICIENT" in result.reasons


def test_proof_debt_is_a_bounded_weighted_prioritization_metric():
    items = (
        ProofDebtItem("critical-authority", risk_weight=10.0, unresolved_fraction=0.5),
        ProofDebtItem("low-impact-doc", risk_weight=2.0, unresolved_fraction=0.25),
    )
    assert calculate_proof_debt(items) == 5.5


def test_proof_debt_rejects_out_of_range_gap():
    with pytest.raises(ValueError):
        ProofDebtItem("bad-gap", risk_weight=1.0, unresolved_fraction=1.1)


def test_audit_chain_verifies_and_replays_without_committing_state():
    decision = evaluate(build_case())
    first = create_audit_event(decision, sequence=0, previous_hash="GENESIS")
    second = create_audit_event(
        decision, sequence=1, previous_hash=first.event_hash
    )
    valid, errors = verify_event_chain((first, second))
    assert valid is True
    assert errors == ()
    replayed = replay_audit_events((first, second))
    assert [item["status"] for item in replayed] == ["ADMIT", "ADMIT"]
    assert all(item["commit_performed"] is False for item in replayed)


def test_tampered_audit_payload_fails_integrity_check():
    decision = evaluate(build_case())
    event = create_audit_event(decision, sequence=0, previous_hash="GENESIS")
    tampered = replace(
        event,
        decision_payload={**event.decision_payload, "action": "DELETE"},
    )
    valid, errors = verify_event_chain((tampered,))
    assert valid is False
    assert "EVENT_HASH_INVALID:0" in errors


def test_audit_replay_refuses_invalid_chain():
    decision = evaluate(build_case())
    event = create_audit_event(decision, sequence=0, previous_hash="GENESIS")
    tampered = replace(event, previous_hash="f" * 64)
    with pytest.raises(ValueError, match="AUDIT_CHAIN_INVALID"):
        replay_audit_events((tampered,))


def test_non_boolean_authority_verdict_quarantines():
    result = evaluate(build_case(), authority_verifier=lambda _grant: "verified")
    assert result.status is AdmissionStatus.QUARANTINE
    assert "AUTHORITY_VERIFICATION_INDETERMINATE" in result.reasons


def test_non_boolean_evidence_verdict_quarantines():
    result = evaluate(build_case(), evidence_verifier=lambda _receipt: "verified")
    assert result.status is AdmissionStatus.QUARANTINE
    assert "EVIDENCE_VERIFICATION_INDETERMINATE:receipt-1" in result.reasons


def test_untrusted_verifier_is_rejected_before_admission():
    current, proposed, candidate, policy = build_case()
    bad = replace(candidate.evidence[0], verifier_id="unlisted-witness")
    result = evaluate_transition(
        current, proposed, replace(candidate, evidence=(bad,)), policy,
        evaluated_at=NOW, authority_verifier=auth_ok, evidence_verifier=evidence_ok,
    )
    assert result.status is AdmissionStatus.REJECT
    assert "EVIDENCE_VERIFIER_NOT_TRUSTED:receipt-1" in result.reasons
