"""Adversarial tests for the SQLite atomic commit boundary."""
from __future__ import annotations

from dataclasses import replace
import json
import sqlite3
import pytest

from canon.assurance.omega3_assurance import check_admission_decision
from canon.kernel.omega3_commit import (
    CommitRejected,
    IdempotencyConflictError,
    SQLiteAtomicCommitStore,
    StaleStateError,
    StoreIntegrityError,
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

PREPARED_AT = "2026-10-10T12:00:00Z"
COMMITTED_AT = "2026-10-10T12:05:00Z"
OBJECT_ID = "VS.81000.SUB.01"


def build_package(result_tag="candidate"):
    current = SovereignState(
        object_id=OBJECT_ID,
        revision=0,
        identity={"root_id": "Ω0_GENESIS_CORE", "genesis_hash": "b" * 64},
        contracts={"schema_version": "1.0", "constitution_hash": "c" * 64,
                   "ontology_hash": "d" * 64, "schema_major": 1},
        authority={"policy_version": "omega3-v1"},
        observations=({"kind": "GENESIS", "sequence": 0},),
        evidence_refs=(),
    )
    proposed = SovereignState(
        object_id=OBJECT_ID,
        revision=1,
        identity=dict(current.identity),
        contracts=dict(current.contracts),
        authority=dict(current.authority),
        observations=(
            {"kind": "GENESIS", "sequence": 0},
            {"kind": "OBSERVATION", "sequence": 1, "value": result_tag},
        ),
        evidence_refs=("receipt-1",),
    )
    grant = AuthorityGrant(
        grant_id="grant-1",
        principal_id="runtime-controller",
        subject_id=OBJECT_ID,
        action="UPDATE",
        scopes=("UPDATE", f"object:{OBJECT_ID}"),
        policy_version="omega3-v1",
        issued_at="2026-10-10T11:00:00Z",
        expires_at="2026-10-10T13:00:00Z",
        verification_ref="signed-grant-ref",
    )
    receipt = EvidenceReceipt(
        receipt_id="receipt-1",
        source_id="source-A",
        claim_digest=proposed.digest,
        evidence_digest="e" * 64,
        observed_at="2026-10-10T11:30:00Z",
        expires_at="2026-10-10T13:00:00Z",
        verifier_id="witness-A",
        verification_ref="signed-evidence-ref",
    )
    candidate = TransitionCandidate(
        action="UPDATE",
        expected_state_digest=current.digest,
        grant=grant,
        evidence=(receipt,),
    )
    policy = AdmissionPolicy(
        version="omega3-v1",
        allowed_actions=("UPDATE",),
        trusted_principals=("runtime-controller",),
        trusted_verifiers=("witness-A",),
        required_evidence_count=1,
        minimum_distinct_source_ids=1,
        max_evidence_age_seconds=7200,
        max_grant_age_seconds=7200,
    )
    decision = evaluate_transition(
        current, proposed, candidate, policy,
        evaluated_at=PREPARED_AT,
        authority_verifier=lambda _grant: True,
        evidence_verifier=lambda _receipt: True,
    )
    assurance = check_admission_decision(
        current, proposed, candidate, policy, decision,
        evaluated_at=PREPARED_AT,
        authority_verdict=True,
        evidence_verdicts={"receipt-1": True},
    )
    assert decision.status is AdmissionStatus.ADMIT
    return current, proposed, candidate, policy, decision, assurance


def commit_package(store, package, *, key="idempotency-1", committed_at=COMMITTED_AT, **kwargs):
    current, proposed, candidate, policy, decision, assurance = package
    store.initialize_state(current, initialized_at=PREPARED_AT)
    return store.commit(
        current, proposed, candidate, policy, decision, assurance,
        idempotency_key=key,
        committed_at=committed_at,
        authority_verifier=kwargs.get("authority_verifier", lambda _grant: True),
        evidence_verifier=kwargs.get("evidence_verifier", lambda _receipt: True),
        fault_hook=kwargs.get("fault_hook"),
    )


def test_commit_atomically_updates_state_receipt_and_event_chain(tmp_path):
    path = str(tmp_path / "state.db")
    package = build_package()
    with SQLiteAtomicCommitStore(path) as store:
        receipt, live_decision, live_assurance = commit_package(store, package)
        stored = store.read_state(OBJECT_ID)
        assert stored.digest == package[1].digest
        assert stored.revision == 1
        assert receipt.status == "COMMITTED"
        assert receipt.revision == 1
        assert live_decision.status is AdmissionStatus.ADMIT
        assert verify_receipt_pair(receipt, live_decision, live_assurance)
        valid, errors = store.verify_event_chain(OBJECT_ID)
        assert valid is True
        assert errors == ()
        assert len(store.list_commit_receipts(OBJECT_ID)) == 1


def verify_receipt_pair(receipt, decision, assurance):
    return (
        receipt.state_digest == decision.state_after_digest
        and receipt.request_digest == decision.request_digest
        and receipt.commit_assurance_digest == assurance.receipt_digest
        and assurance.decision_digest
    )


def test_commit_requires_live_verifiers_even_if_preflight_was_admissible(tmp_path):
    package = build_package()
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        current = package[0]
        store.initialize_state(current, initialized_at=PREPARED_AT)
        with pytest.raises(CommitRejected, match="LIVE_ADMISSION_OR_ASSURANCE_GATE_FAILED"):
            commit_package(store, package, authority_verifier=None)


def test_expired_or_failed_live_evidence_cannot_be_committed(tmp_path):
    package = build_package()
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        with pytest.raises(CommitRejected):
            commit_package(store, package, evidence_verifier=lambda _receipt: False)
        # The prepared state is still genesis even though commit was rejected.
        assert store.read_state(OBJECT_ID).revision == 0


def test_retry_with_same_idempotency_key_returns_original_commit_receipt(tmp_path):
    package = build_package()
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        first, _, _ = commit_package(store, package, key="retry-key")
        second, _, _ = commit_package(store, package, key="retry-key")
        assert second == first
        assert store.read_state(OBJECT_ID).revision == 1
        assert len(store.list_commit_receipts(OBJECT_ID)) == 1


def test_same_idempotency_key_cannot_be_reused_for_a_different_transition(tmp_path):
    package = build_package("first")
    alternative = build_package("different")
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        first, _, _ = commit_package(store, package, key="reused-key")
        with pytest.raises(IdempotencyConflictError):
            commit_package(store, alternative, key="reused-key")
        assert store.read_state(OBJECT_ID).digest == package[1].digest
        assert len(store.list_commit_receipts(OBJECT_ID)) == 1


def test_concurrent_stale_transition_loses_compare_and_swap(tmp_path):
    first_package = build_package("winner")
    second_package = build_package("loser")
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        commit_package(store, first_package, key="winner-key")
        with pytest.raises(StaleStateError):
            commit_package(store, second_package, key="loser-key")
        assert store.read_state(OBJECT_ID).digest == first_package[1].digest
        assert len(store.list_commit_receipts(OBJECT_ID)) == 1


@pytest.mark.parametrize("stage", ["after_state_update", "after_event_insert", "after_receipt_insert"])
def test_injected_crash_rolls_back_state_receipt_and_event_together(tmp_path, stage):
    package = build_package()
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        def crash(current_stage):
            if current_stage == stage:
                raise RuntimeError(f"injected crash at {stage}")

        with pytest.raises(RuntimeError, match="injected crash"):
            commit_package(store, package, fault_hook=crash)
        assert store.read_state(OBJECT_ID).digest == package[0].digest
        valid, errors = store.verify_event_chain(OBJECT_ID)
        assert valid is True
        assert errors == ()
        assert store.list_commit_receipts(OBJECT_ID) == ()


def test_live_policy_rejection_does_not_mutate_state(tmp_path):
    package = build_package()
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        with pytest.raises(CommitRejected):
            commit_package(store, package, authority_verifier=lambda _grant: False)
        assert store.read_state(OBJECT_ID).digest == package[0].digest
        assert store.list_commit_receipts(OBJECT_ID) == ()


def test_modified_prepared_assurance_is_rejected(tmp_path):
    from dataclasses import replace as dc_replace
    package = list(build_package())
    package[5] = dc_replace(package[5], expected_status=AdmissionStatus.REJECT.value)
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        store.initialize_state(package[0], initialized_at=PREPARED_AT)
        with pytest.raises(CommitRejected, match="PREPARED_ASSURANCE_INVALID"):
            store.commit(
                *package[:5], package[5],
                idempotency_key="bad-assurance",
                committed_at=COMMITTED_AT,
                authority_verifier=lambda _grant: True,
                evidence_verifier=lambda _receipt: True,
            )
        assert store.read_state(OBJECT_ID).revision == 0


def test_event_chain_detects_payload_tampering(tmp_path):
    package = build_package()
    path = str(tmp_path / "state.db")
    with SQLiteAtomicCommitStore(path) as store:
        commit_package(store, package)
        store._connection.execute(
            "UPDATE commit_events SET event_payload = ? WHERE object_id = ? AND sequence = 1",
            (json.dumps({"sequence": 1, "tampered": True}), OBJECT_ID),
        )
        valid, errors = store.verify_event_chain(OBJECT_ID)
        assert valid is False
        assert errors


def test_state_write_cannot_overwrite_genesis(tmp_path):
    package = build_package()
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        store.initialize_state(package[0], initialized_at=PREPARED_AT)
        with pytest.raises(Exception, match="OBJECT_ALREADY_INITIALIZED"):
            store.initialize_state(package[1], initialized_at=COMMITTED_AT)


def test_store_rejects_unknown_admission_before_db_mutation(tmp_path):
    current, proposed, candidate, policy, decision, assurance = build_package()
    from dataclasses import replace as dc_replace
    unknown = dc_replace(decision, status=AdmissionStatus.UNKNOWN)
    with SQLiteAtomicCommitStore(str(tmp_path / "state.db")) as store:
        store.initialize_state(current, initialized_at=PREPARED_AT)
        with pytest.raises(CommitRejected, match="PREPARED_DECISION_NOT_ADMISSIBLE"):
            store.commit(
                current, proposed, candidate, policy, unknown, assurance,
                idempotency_key="unknown-key",
                committed_at=COMMITTED_AT,
                authority_verifier=lambda _grant: True,
                evidence_verifier=lambda _receipt: True,
            )
        assert store.read_state(OBJECT_ID).revision == 0
