"""SQLite-backed atomic commit boundary for the Ω³ candidate state machine.

The store performs compare-and-swap and persists state, commit receipt, and a
hash-linked event in one SQLite transaction. It is a reference implementation:
hash linkage is not a signature or externally immutable witness.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import sqlite3
from threading import RLock
from typing import Any, Callable, Iterator, Mapping

from canon.assurance.omega3_assurance import (
    AssuranceReceipt,
    AssuranceVerdict,
    check_admission_decision,
    verify_assurance_receipt,
)
from canon.kernel.omega3_kernel import (
    AdmissionDecision,
    AdmissionPolicy,
    AdmissionStatus,
    AuthorityVerifier,
    EvidenceReceipt,
    EvidenceVerifier,
    SovereignState,
    TransitionCandidate,
    canonical_json,
    digest_json,
    evaluate_transition,
)

_GENESIS = "GENESIS"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CommitError(RuntimeError):
    """Base class for atomic-commit failures."""


class CommitRejected(CommitError):
    """The prepared/live assurance gate did not permit a state commit."""

    def __init__(
        self,
        message: str,
        *,
        decision: AdmissionDecision | None = None,
        assurance: AssuranceReceipt | None = None,
    ) -> None:
        super().__init__(message)
        self.decision = decision
        self.assurance = assurance


class StaleStateError(CommitError):
    """The database state differs from the exact state used to prepare the transition."""


class IdempotencyConflictError(CommitError):
    """An idempotency key was reused for a different logical transition."""


class StoreIntegrityError(CommitError):
    """Stored state, receipt, or event-chain integrity checks failed."""


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("TIMESTAMP_REQUIRED")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _utc_text(value: str) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _decision_digest(decision: AdmissionDecision) -> str:
    """Match the assurance receipt's stable payload shape, without calling its checker."""
    return digest_json({
        "status": decision.status.value if isinstance(decision.status, AdmissionStatus) else str(decision.status),
        "object_id": decision.object_id,
        "action": decision.action,
        "state_before_digest": decision.state_before_digest,
        "state_after_digest": decision.state_after_digest,
        "request_digest": decision.request_digest,
        "evaluated_at": decision.evaluated_at,
        "reasons": list(decision.reasons),
        "warnings": list(decision.warnings),
        "checks": decision.checks,
        "authority_verified": decision.authority_verified,
        "verified_evidence_ids": list(decision.verified_evidence_ids),
        "commit_performed": decision.commit_performed,
    })


@dataclass(frozen=True)
class CommitReceipt:
    receipt_id: str
    object_id: str
    previous_revision: int
    revision: int
    previous_state_digest: str
    state_digest: str
    operation_digest: str
    request_digest: str
    prepared_assurance_digest: str
    commit_assurance_digest: str
    idempotency_key: str
    verified_at: str
    committed_at: str
    event_sequence: int
    previous_event_hash: str
    event_hash: str
    status: str = "COMMITTED"

    def payload(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "object_id": self.object_id,
            "previous_revision": self.previous_revision,
            "revision": self.revision,
            "previous_state_digest": self.previous_state_digest,
            "state_digest": self.state_digest,
            "operation_digest": self.operation_digest,
            "request_digest": self.request_digest,
            "prepared_assurance_digest": self.prepared_assurance_digest,
            "commit_assurance_digest": self.commit_assurance_digest,
            "idempotency_key": self.idempotency_key,
            "verified_at": self.verified_at,
            "committed_at": self.committed_at,
            "event_sequence": self.event_sequence,
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
            "status": self.status,
        }

    @property
    def receipt_digest(self) -> str:
        return digest_json(self.payload())

    def to_record(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_digest": self.receipt_digest}

    @classmethod
    def from_record(cls, value: Mapping[str, Any]) -> "CommitReceipt":
        record = dict(value)
        expected_digest = record.pop("receipt_digest", None)
        try:
            receipt = cls(**record)
        except (TypeError, ValueError) as exc:
            raise StoreIntegrityError("COMMIT_RECEIPT_MALFORMED") from exc
        if not isinstance(expected_digest, str) or receipt.receipt_digest != expected_digest:
            raise StoreIntegrityError("COMMIT_RECEIPT_DIGEST_MISMATCH")
        return receipt


class SQLiteAtomicCommitStore:
    """Durable state store with atomic compare-and-swap and idempotent commits.

    The store uses a configured clock rather than accepting commit time from a
    request. It re-evaluates the transition with live verifier callbacks, then
    checks state revision/digest and commits state, receipt, and event together.

    External verifier state cannot be transactionally locked by SQLite. Production
    adapters must use short-lived signed receipts, pinned trust roots, revocation
    epochs, and a trust service whose consistency guarantees are documented.
    """

    def __init__(
        self,
        database_path: str,
        *,
        timeout_seconds: float = 5.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(database_path, str) or not database_path:
            raise ValueError("DATABASE_PATH_REQUIRED")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("TIMEOUT_MUST_BE_POSITIVE_AND_FINITE")
        self.database_path = database_path
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._connection = sqlite3.connect(
            database_path,
            timeout=float(timeout_seconds),
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        if database_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._create_schema()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteAtomicCommitStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _create_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS state_current (
                    object_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    state_digest TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commit_records (
                    object_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    operation_digest TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    PRIMARY KEY (object_id, revision),
                    UNIQUE (object_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS commit_events (
                    object_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_payload TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY (object_id, sequence)
                );
                """
            )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cursor = self._connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                yield cursor
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
            finally:
                cursor.close()

    @staticmethod
    def _event_hash(payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(canonical_json(dict(payload)).encode("utf-8")).hexdigest()

    def initialize_state(
        self,
        state: SovereignState,
        *,
        initialized_at: str = "2026-01-01T00:00:00Z",
    ) -> str:
        """Register a genesis state once; this method cannot overwrite existing state."""
        timestamp = _utc_text(initialized_at)
        state_json = canonical_json(state.to_payload())
        with self._transaction() as cursor:
            existing = cursor.execute(
                "SELECT revision, state_digest FROM state_current WHERE object_id = ?",
                (state.object_id,),
            ).fetchone()
            if existing is not None:
                if existing["revision"] == state.revision and existing["state_digest"] == state.digest:
                    return state.digest
                raise CommitError("OBJECT_ALREADY_INITIALIZED_WITH_DIFFERENT_STATE")
            cursor.execute(
                "INSERT INTO state_current(object_id, revision, state_digest, state_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (state.object_id, state.revision, state.digest, state_json, timestamp),
            )
            genesis_payload = {
                "sequence": 0,
                "event_type": "GENESIS",
                "object_id": state.object_id,
                "revision": state.revision,
                "state_digest": state.digest,
                "committed_at": timestamp,
                "previous_event_hash": _GENESIS,
            }
            cursor.execute(
                "INSERT INTO commit_events(object_id, sequence, event_payload, event_hash) VALUES (?, ?, ?, ?)",
                (
                    state.object_id, 0, canonical_json(genesis_payload),
                    self._event_hash(genesis_payload),
                ),
            )
        return state.digest

    def read_state(self, object_id: str) -> SovereignState:
        with self._lock:
            row = self._connection.execute(
                "SELECT revision, state_digest, state_json FROM state_current WHERE object_id = ?",
                (object_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"STATE_NOT_FOUND:{object_id}")
        try:
            payload = json.loads(row["state_json"])
            state = SovereignState.from_payload(payload)
        except Exception as exc:
            raise StoreIntegrityError("STORED_STATE_MALFORMED") from exc
        if (
            state.object_id != object_id
            or state.revision != row["revision"]
            or state.digest != row["state_digest"]
        ):
            raise StoreIntegrityError("STORED_STATE_DIGEST_MISMATCH")
        return state

    @staticmethod
    def _operation_digest(
        current: SovereignState,
        proposed: SovereignState,
        candidate: TransitionCandidate,
        policy: AdmissionPolicy,
    ) -> str:
        # Exclude evaluation time so a retried idempotency key identifies the same logical operation.
        return digest_json({
            "object_id": current.object_id,
            "state_before_digest": current.digest,
            "state_after_digest": proposed.digest,
            "candidate": candidate.to_payload(),
            "policy": policy.to_payload(),
        })

    @staticmethod
    def _validate_prepared(
        current: SovereignState,
        proposed: SovereignState,
        candidate: TransitionCandidate,
        decision: AdmissionDecision,
        assurance: AssuranceReceipt,
    ) -> None:
        if decision.status is not AdmissionStatus.ADMIT or decision.commit_performed:
            raise CommitRejected("PREPARED_DECISION_NOT_ADMISSIBLE", decision=decision, assurance=assurance)
        if (
            decision.object_id != current.object_id
            or proposed.object_id != current.object_id
            or decision.action != candidate.action
            or decision.state_before_digest != current.digest
            or decision.state_after_digest != proposed.digest
            or candidate.expected_state_digest != current.digest
        ):
            raise CommitRejected("PREPARED_DECISION_BINDING_MISMATCH", decision=decision, assurance=assurance)
        if (
            assurance.verdict is not AssuranceVerdict.CHECKED_ADMISSION_CANDIDATE
            or assurance.expected_status != AdmissionStatus.ADMIT.value
            or assurance.observed_status != decision.status.value
            or assurance.commit_performed
            or not verify_assurance_receipt(assurance)
            or assurance.decision_digest != _decision_digest(decision)
            or not _SHA256.fullmatch(assurance.input_digest)
        ):
            raise CommitRejected("PREPARED_ASSURANCE_INVALID", decision=decision, assurance=assurance)

    @staticmethod
    def _run_live_assurance(
        current: SovereignState,
        proposed: SovereignState,
        candidate: TransitionCandidate,
        policy: AdmissionPolicy,
        *,
        committed_at: str,
        authority_verifier: AuthorityVerifier | None,
        evidence_verifier: EvidenceVerifier | None,
    ) -> tuple[AdmissionDecision, AssuranceReceipt]:
        authority_observations: list[Any] = []
        evidence_observations: dict[str, Any] = {}

        def auth_wrapper(grant: Any) -> bool | None:
            if authority_verifier is None:
                raise RuntimeError("UNAVAILABLE_AUTHORITY_VERIFIER")
            try:
                verdict = authority_verifier(grant)
                authority_observations.append(verdict)
                return verdict
            except Exception:
                authority_observations.append("ERROR")
                raise

        def evidence_wrapper(receipt: EvidenceReceipt) -> bool | None:
            if evidence_verifier is None:
                raise RuntimeError("UNAVAILABLE_EVIDENCE_VERIFIER")
            try:
                verdict = evidence_verifier(receipt)
                evidence_observations[receipt.receipt_id] = verdict
                return verdict
            except Exception:
                evidence_observations[receipt.receipt_id] = "ERROR"
                raise

        decision = evaluate_transition(
            current, proposed, candidate, policy,
            evaluated_at=committed_at,
            authority_verifier=None if authority_verifier is None else auth_wrapper,
            evidence_verifier=None if evidence_verifier is None else evidence_wrapper,
        )

        if authority_verifier is None:
            authority_verdict: Any = "UNAVAILABLE"
        elif authority_observations:
            authority_verdict = authority_observations[-1]
        else:
            # Structural rejection occurs before authority is consulted.
            authority_verdict = "UNAVAILABLE"

        evidence_verdicts: Mapping[str, Any] | None = (
            None if evidence_verifier is None else evidence_observations
        )
        assurance = check_admission_decision(
            current, proposed, candidate, policy, decision,
            evaluated_at=committed_at,
            authority_verdict=authority_verdict,
            evidence_verdicts=evidence_verdicts,
        )
        return decision, assurance

    def commit(
        self,
        current: SovereignState,
        proposed: SovereignState,
        candidate: TransitionCandidate,
        policy: AdmissionPolicy,
        prepared_decision: AdmissionDecision,
        prepared_assurance: AssuranceReceipt,
        *,
        idempotency_key: str,
        authority_verifier: AuthorityVerifier | None,
        evidence_verifier: EvidenceVerifier | None,
        fault_hook: Callable[[str], None] | None = None,
    ) -> tuple[CommitReceipt, AdmissionDecision, AssuranceReceipt]:
        """Revalidate then atomically compare-and-swap state + receipt + event chain."""
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("IDEMPOTENCY_KEY_REQUIRED")
        verification_time = _utc_text(self._clock().isoformat())
        self._validate_prepared(
            current, proposed, candidate, prepared_decision, prepared_assurance
        )

        # Run potentially external verification before opening the database transaction.
        # The state CAS below closes state-version TOCTOU; trust revocation consistency
        # is bounded by the verifier's documented receipt/epoch guarantees.
        live_decision, live_assurance = self._run_live_assurance(
            current, proposed, candidate, policy,
            committed_at=verification_time,
            authority_verifier=authority_verifier,
            evidence_verifier=evidence_verifier,
        )
        if (
            live_decision.status is not AdmissionStatus.ADMIT
            or live_assurance.verdict is not AssuranceVerdict.CHECKED_ADMISSION_CANDIDATE
            or not verify_assurance_receipt(live_assurance)
            or live_assurance.decision_digest != _decision_digest(live_decision)
        ):
            raise CommitRejected(
                "LIVE_ADMISSION_OR_ASSURANCE_GATE_FAILED",
                decision=live_decision,
                assurance=live_assurance,
            )

        operation_digest = self._operation_digest(current, proposed, candidate, policy)
        with self._transaction() as cursor:
            prior = cursor.execute(
                "SELECT operation_digest, receipt_json FROM commit_records "
                "WHERE object_id = ? AND idempotency_key = ?",
                (current.object_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["operation_digest"] != operation_digest:
                    raise IdempotencyConflictError("IDEMPOTENCY_KEY_REUSED_FOR_DIFFERENT_OPERATION")
                try:
                    record = json.loads(prior["receipt_json"])
                    return CommitReceipt.from_record(record), live_decision, live_assurance
                except (json.JSONDecodeError, StoreIntegrityError) as exc:
                    raise StoreIntegrityError("STORED_IDEMPOTENT_RECEIPT_INVALID") from exc

            row = cursor.execute(
                "SELECT revision, state_digest, state_json FROM state_current WHERE object_id = ?",
                (current.object_id,),
            ).fetchone()
            if row is None:
                raise StaleStateError("CANONICAL_STATE_NOT_INITIALIZED")
            if row["state_digest"] != current.digest or row["revision"] != current.revision:
                raise StaleStateError("CANONICAL_STATE_CHANGED_SINCE_PREPARATION")
            if row["state_json"] != canonical_json(current.to_payload()):
                raise StoreIntegrityError("CANONICAL_STATE_PAYLOAD_MISMATCH")

            # Recheck local temporal boundaries against the store clock immediately before write.
            normalized_commit_time = _utc_text(self._clock().isoformat())
            now = _utc(normalized_commit_time)
            grant = candidate.grant
            try:
                issued = _utc(grant.issued_at)
                expires = _utc(grant.expires_at)
            except (TypeError, ValueError, OverflowError) as exc:
                raise CommitRejected(
                    "AUTHORITY_GRANT_TIME_INVALID_AT_COMMIT",
                    decision=live_decision, assurance=live_assurance,
                ) from exc
            if (
                not (issued <= now < expires)
                or (now - issued).total_seconds() > policy.max_grant_age_seconds
            ):
                raise CommitRejected(
                    "AUTHORITY_GRANT_WINDOW_CLOSED_BEFORE_COMMIT",
                    decision=live_decision, assurance=live_assurance,
                )
            for item in candidate.evidence:
                try:
                    observed = _utc(item.observed_at)
                    evidence_expires = _utc(item.expires_at)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise CommitRejected(
                        f"EVIDENCE_TIME_INVALID_AT_COMMIT:{item.receipt_id}",
                        decision=live_decision, assurance=live_assurance,
                    ) from exc
                if (
                    evidence_expires <= now
                    or observed > now
                    or (now - observed).total_seconds() > policy.max_evidence_age_seconds
                ):
                    raise CommitRejected(
                        f"EVIDENCE_NOT_CURRENT_AT_COMMIT:{item.receipt_id}",
                        decision=live_decision, assurance=live_assurance,
                    )

            last = cursor.execute(
                "SELECT sequence, event_hash FROM commit_events WHERE object_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (current.object_id,),
            ).fetchone()
            if last is None:
                raise StoreIntegrityError("GENESIS_EVENT_MISSING")
            event_sequence = int(last["sequence"]) + 1
            previous_event_hash = str(last["event_hash"])
            receipt_id = digest_json({
                "object_id": current.object_id,
                "idempotency_key": idempotency_key,
                "operation_digest": operation_digest,
            })
            event_payload = {
                "sequence": event_sequence,
                "event_type": "STATE_COMMITTED",
                "receipt_id": receipt_id,
                "object_id": current.object_id,
                "previous_revision": current.revision,
                "revision": proposed.revision,
                "previous_state_digest": current.digest,
                "state_digest": proposed.digest,
                "operation_digest": operation_digest,
                "request_digest": live_decision.request_digest,
                "prepared_assurance_digest": prepared_assurance.receipt_digest,
                "commit_assurance_digest": live_assurance.receipt_digest,
                "idempotency_key": idempotency_key,
                "verified_at": live_decision.evaluated_at,
                "committed_at": normalized_commit_time,
                "previous_event_hash": previous_event_hash,
            }
            event_hash = self._event_hash(event_payload)
            receipt = CommitReceipt(
                receipt_id=receipt_id,
                object_id=current.object_id,
                previous_revision=current.revision,
                revision=proposed.revision,
                previous_state_digest=current.digest,
                state_digest=proposed.digest,
                operation_digest=operation_digest,
                request_digest=live_decision.request_digest,
                prepared_assurance_digest=prepared_assurance.receipt_digest,
                commit_assurance_digest=live_assurance.receipt_digest,
                idempotency_key=idempotency_key,
                verified_at=live_decision.evaluated_at,
                committed_at=normalized_commit_time,
                event_sequence=event_sequence,
                previous_event_hash=previous_event_hash,
                event_hash=event_hash,
            )

            cursor.execute(
                "UPDATE state_current SET revision = ?, state_digest = ?, state_json = ?, updated_at = ? "
                "WHERE object_id = ? AND revision = ? AND state_digest = ?",
                (
                    proposed.revision, proposed.digest,
                    canonical_json(proposed.to_payload()), normalized_commit_time,
                    current.object_id, current.revision, current.digest,
                ),
            )
            if cursor.rowcount != 1:
                raise StaleStateError("COMPARE_AND_SWAP_FAILED")
            if fault_hook is not None:
                fault_hook("after_state_update")

            cursor.execute(
                "INSERT INTO commit_events(object_id, sequence, event_payload, event_hash) VALUES (?, ?, ?, ?)",
                (current.object_id, event_sequence, canonical_json(event_payload), event_hash),
            )
            if fault_hook is not None:
                fault_hook("after_event_insert")

            cursor.execute(
                "INSERT INTO commit_records(object_id, revision, idempotency_key, operation_digest, receipt_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    current.object_id, proposed.revision, idempotency_key,
                    operation_digest, canonical_json(receipt.to_record()),
                ),
            )
            if fault_hook is not None:
                fault_hook("after_receipt_insert")

        return receipt, live_decision, live_assurance

    def verify_event_chain(self, object_id: str) -> tuple[bool, tuple[str, ...]]:
        errors: list[str] = []
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence, event_payload, event_hash FROM commit_events "
                "WHERE object_id = ? ORDER BY sequence ASC",
                (object_id,),
            ).fetchall()
            state_row = self._connection.execute(
                "SELECT revision, state_digest, state_json FROM state_current WHERE object_id = ?",
                (object_id,),
            ).fetchone()

        if not rows:
            return False, ("EVENT_CHAIN_MISSING",)
        previous = _GENESIS
        last_payload: Mapping[str, Any] | None = None
        for expected_sequence, row in enumerate(rows):
            try:
                payload = json.loads(row["event_payload"])
                if canonical_json(payload) != row["event_payload"]:
                    errors.append(f"EVENT_ENCODING_NONCANONICAL:{expected_sequence}")
                if payload.get("sequence") != expected_sequence:
                    errors.append(f"EVENT_SEQUENCE_GAP:{expected_sequence}")
                if payload.get("previous_event_hash") != previous:
                    errors.append(f"PREVIOUS_EVENT_HASH_MISMATCH:{expected_sequence}")
                recomputed = self._event_hash(payload)
                if not _SHA256.fullmatch(row["event_hash"]) or recomputed != row["event_hash"]:
                    errors.append(f"EVENT_HASH_MISMATCH:{expected_sequence}")
                previous = row["event_hash"]
                last_payload = payload
            except Exception:
                errors.append(f"EVENT_PAYLOAD_INVALID:{expected_sequence}")

        if state_row is None:
            errors.append("CURRENT_STATE_MISSING")
        elif last_payload is not None:
            if (
                last_payload.get("revision") != state_row["revision"]
                or last_payload.get("state_digest") != state_row["state_digest"]
            ):
                errors.append("CURRENT_STATE_NOT_BOUND_TO_LAST_EVENT")
        return not errors, tuple(errors)

    def list_commit_receipts(self, object_id: str) -> tuple[CommitReceipt, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT receipt_json FROM commit_records WHERE object_id = ? ORDER BY revision ASC",
                (object_id,),
            ).fetchall()
        receipts: list[CommitReceipt] = []
        for row in rows:
            try:
                receipts.append(CommitReceipt.from_record(json.loads(row["receipt_json"])))
            except Exception as exc:
                raise StoreIntegrityError("COMMIT_RECEIPT_INVALID") from exc
        return tuple(receipts)
