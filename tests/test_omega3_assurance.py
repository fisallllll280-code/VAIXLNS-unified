"""Adversarial tests for the independent Ω³ decision checker."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from canon.assurance.omega3_assurance import (
    AssuranceVerdict,
    check_admission_decision,
    verify_assurance_receipt,
)
from canon.kernel.omega3_kernel import (
    AdmissionPolicy,
    AdmissionStatus,
    AuthorityGrant,
    EvidenceReceipt,
    SovereignState,
    TransitionCandidate,
    evaluate_transition,
)

NOW = "2026-10-10T12:00:00Z"
OBJECT_ID = "VS.81000.SUB.01"


def case():
    current = SovereignState(
        object_id=OBJECT_ID, revision=0,
        identity={"root_id": "Ω0_GENESIS_CORE", "genesis_hash": "b" * 64},
        contracts={"schema_version": "1.0", "constitution_hash": "c" * 64,
                   "ontology_hash": "d" * 64, "schema_major": 1},
        authority={"policy_version": "omega3-v1"},
        observations=({"kind": "INIT"},), evidence_refs=(),
    )
    proposed = SovereignState(
        object_id=OBJECT_ID, revision=1,
        identity={"root_id": "Ω0_GENESIS_CORE", "genesis_hash": "b" * 64},
        contracts={"schema_version": "1.0", "constitution_hash": "c" * 64,
                   "ontology_hash": "d" * 64, "schema_major": 1},
        authority={"policy_version": "omega3-v1"},
        observations=({"kind": "INIT"}, {"kind": "OBSERVATION"}),
        evidence_refs=("receipt-1",),
    )
    grant = AuthorityGrant(
        grant_id="grant-1", principal_id="release-controller", subject_id=OBJECT_ID,
        action="UPDATE", scopes=("UPDATE", f"object:{OBJECT_ID}"),
        policy_version="omega3-v1", issued_at="2026-10-10T11:00:00Z",
        expires_at="2026-10-10T13:00:00Z", verification_ref="signed-grant-ref",
    )
    evidence = EvidenceReceipt(
        receipt_id="receipt-1", source_id="source-A", claim_digest=proposed.digest,
        evidence_digest="e" * 64, observed_at="2026-10-10T11:30:00Z",
        expires_at="2026-10-10T13:00:00Z", verifier_id="witness-A",
        verification_ref="signed-receipt-ref",
    )
    candidate = TransitionCandidate("UPDATE", current.digest, grant, (evidence,))
    policy = AdmissionPolicy(
        version="omega3-v1", allowed_actions=("UPDATE",),
        trusted_principals=("release-controller",), trusted_verifiers=("witness-A",),
        max_evidence_age_seconds=7200, max_grant_age_seconds=7200,
    )
    return current, proposed, candidate, policy


def kernel_decision(inputs=None, **overrides):
    current, proposed, candidate, policy = inputs or case()
    options = {
        "evaluated_at": NOW,
        "authority_verifier": lambda _grant: True,
        "evidence_verifier": lambda _item: True,
    }
    options.update(overrides)
    decision = evaluate_transition(current, proposed, candidate, policy, **options)
    if options["evidence_verifier"] is None:
        evidence_verdicts = None
    else:
        evidence_verdicts = {}
        for item in candidate.evidence:
            try:
                evidence_verdicts[item.receipt_id] = options["evidence_verifier"](item)
            except Exception:
                evidence_verdicts[item.receipt_id] = "ERROR"
    if options["authority_verifier"] is None:
        authority_verdict = "UNAVAILABLE"
    else:
        try:
            authority_verdict = options["authority_verifier"](candidate.grant)
        except Exception:
            authority_verdict = "ERROR"
    return current, proposed, candidate, policy, decision, authority_verdict, evidence_verdicts


def check(values, decision=None, authority_verdict=None, evidence_verdicts=None):
    current, proposed, candidate, policy, original, auth, evidence = values
    return check_admission_decision(
        current, proposed, candidate, policy, decision or original,
        evaluated_at=NOW,
        authority_verdict=auth if authority_verdict is None else authority_verdict,
        evidence_verdicts=evidence if evidence_verdicts is None else evidence_verdicts,
    )


def test_independent_checker_accepts_consistent_candidate_not_commit():
    values = kernel_decision()
    receipt = check(values)
    assert values[4].status is AdmissionStatus.ADMIT
    assert receipt.verdict is AssuranceVerdict.CHECKED_ADMISSION_CANDIDATE
    assert receipt.commit_performed is False
    assert verify_assurance_receipt(receipt)


def test_checker_does_not_call_kernel_evaluator():
    values = kernel_decision()
    with patch("canon.kernel.omega3_kernel.evaluate_transition", side_effect=AssertionError("must not call")):
        receipt = check(values)
    assert receipt.verdict is AssuranceVerdict.CHECKED_ADMISSION_CANDIDATE


def test_status_disagreement_emits_counterexample():
    values = kernel_decision()
    forged = replace(values[4], status=AdmissionStatus.REJECT)
    receipt = check(values, decision=forged)
    assert receipt.verdict is AssuranceVerdict.DIVERGENT
    assert any(item.path == "decision.status" for item in receipt.counterexamples)
    assert verify_assurance_receipt(receipt)


def test_request_digest_mismatch_is_detected():
    values = kernel_decision()
    forged = replace(values[4], request_digest="0" * 64)
    receipt = check(values, decision=forged)
    assert receipt.verdict is AssuranceVerdict.DIVERGENT
    assert "BINDING_MISMATCH:decision.request_digest" in receipt.findings


def test_post_state_digest_mismatch_is_detected():
    values = kernel_decision()
    forged = replace(values[4], state_after_digest="0" * 64)
    receipt = check(values, decision=forged)
    assert receipt.verdict is AssuranceVerdict.DIVERGENT
    assert "BINDING_MISMATCH:decision.state_after_digest" in receipt.findings


def test_checker_rejects_constitution_mutation_even_if_kernel_decision_is_forged_admit():
    current, proposed, candidate, policy = case()
    changed_contracts = dict(proposed.contracts)
    changed_contracts["constitution_hash"] = "f" * 64
    altered = SovereignState(
        object_id=proposed.object_id, revision=proposed.revision,
        identity=proposed.identity, contracts=changed_contracts,
        authority=proposed.authority, observations=proposed.observations,
        evidence_refs=proposed.evidence_refs,
    )
    from dataclasses import replace as dc_replace
    altered_candidate = dc_replace(
        candidate,
        evidence=(dc_replace(candidate.evidence[0], claim_digest=altered.digest),),
    )
    decision = evaluate_transition(
        current, altered, altered_candidate, policy, evaluated_at=NOW,
        authority_verifier=lambda _grant: True, evidence_verifier=lambda _item: True,
    )
    receipt = check_admission_decision(
        current, altered, altered_candidate, policy, decision,
        evaluated_at=NOW, authority_verdict=True, evidence_verdicts={"receipt-1": True},
    )
    assert decision.status is AdmissionStatus.REJECT
    assert receipt.verdict is AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE


def test_missing_evidence_is_consistently_unknown():
    current, proposed, candidate, policy = case()
    from dataclasses import replace as dc_replace
    no_evidence = dc_replace(candidate, evidence=())
    proposed_without_refs = SovereignState(
        object_id=proposed.object_id, revision=proposed.revision,
        identity=proposed.identity, contracts=proposed.contracts,
        authority=proposed.authority, observations=proposed.observations,
        evidence_refs=(),
    )
    decision = evaluate_transition(
        current, proposed_without_refs, no_evidence, policy, evaluated_at=NOW,
        authority_verifier=lambda _grant: True, evidence_verifier=lambda _item: True,
    )
    receipt = check_admission_decision(
        current, proposed_without_refs, no_evidence, policy, decision,
        evaluated_at=NOW, authority_verdict=True, evidence_verdicts={},
    )
    assert decision.status is AdmissionStatus.UNKNOWN
    assert receipt.verdict is AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE


def test_non_boolean_verdict_does_not_count_as_admission():
    values = kernel_decision(evidence_verifier=lambda _item: "verified")
    receipt = check(values)
    assert values[4].status is AdmissionStatus.QUARANTINE
    assert receipt.verdict is AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE


def test_missing_authority_verdict_quarantines():
    values = kernel_decision(authority_verifier=None)
    receipt = check(values)
    assert values[4].status is AdmissionStatus.QUARANTINE
    assert receipt.verdict is AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE


def test_untrusted_evidence_verifier_is_rejected_by_both_paths():
    current, proposed, candidate, policy = case()
    from dataclasses import replace as dc_replace
    untrusted = dc_replace(candidate.evidence[0], verifier_id="unknown-witness")
    candidate = dc_replace(candidate, evidence=(untrusted,))
    decision = evaluate_transition(
        current, proposed, candidate, policy, evaluated_at=NOW,
        authority_verifier=lambda _grant: True, evidence_verifier=lambda _item: True,
    )
    receipt = check_admission_decision(
        current, proposed, candidate, policy, decision, evaluated_at=NOW,
        authority_verdict=True, evidence_verdicts={"receipt-1": True},
    )
    assert decision.status is AdmissionStatus.REJECT
    assert receipt.verdict is AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE


def test_receipt_digest_detects_payload_mutation():
    values = kernel_decision()
    receipt = check(values)
    mutated = replace(receipt, findings=receipt.findings + ("FAKE_FINDING",))
    assert verify_assurance_receipt(receipt)
    assert not verify_assurance_receipt(mutated)


def test_policy_version_mismatch_is_not_admissible():
    current, proposed, candidate, policy = case()
    from dataclasses import replace as dc_replace
    candidate = dc_replace(candidate, grant=dc_replace(candidate.grant, policy_version="older"))
    decision = evaluate_transition(
        current, proposed, candidate, policy, evaluated_at=NOW,
        authority_verifier=lambda _grant: True, evidence_verifier=lambda _item: True,
    )
    receipt = check_admission_decision(
        current, proposed, candidate, policy, decision, evaluated_at=NOW,
        authority_verdict=True, evidence_verdicts={"receipt-1": True},
    )
    assert decision.status is AdmissionStatus.REJECT
    assert receipt.verdict is AssuranceVerdict.CONSISTENT_NON_ADMISSIBLE


def test_checker_detects_forged_authority_verdict_field():
    values = kernel_decision()
    forged = replace(values[4], authority_verified=False)
    receipt = check(values, decision=forged)
    assert receipt.verdict is AssuranceVerdict.DIVERGENT
    assert "BINDING_MISMATCH:decision.authority_verified" in receipt.findings


def test_checker_detects_missing_verified_evidence_ids():
    values = kernel_decision()
    forged = replace(values[4], verified_evidence_ids=())
    receipt = check(values, decision=forged)
    assert receipt.verdict is AssuranceVerdict.DIVERGENT
    assert "BINDING_MISMATCH:decision.verified_evidence_ids" in receipt.findings


def test_checker_detects_warning_tampering():
    values = kernel_decision()
    current, proposed, candidate, policy = case()
    from dataclasses import replace as dc_replace
    stale = dc_replace(
        candidate.evidence[0],
        observed_at="2026-10-10T08:00:00Z",
        expires_at="2026-10-10T09:00:00Z",
    )
    candidate = dc_replace(candidate, evidence=(stale,))
    decision = evaluate_transition(
        current, proposed, candidate, policy, evaluated_at=NOW,
        authority_verifier=lambda _grant: True, evidence_verifier=lambda _item: True,
    )
    forged = replace(decision, warnings=())
    receipt = check_admission_decision(
        current, proposed, candidate, policy, forged, evaluated_at=NOW,
        authority_verdict=True, evidence_verdicts={"receipt-1": True},
    )
    assert receipt.verdict is AssuranceVerdict.DIVERGENT
    assert "BINDING_MISMATCH:decision.warnings" in receipt.findings
