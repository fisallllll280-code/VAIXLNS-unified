# Ω³ Atomic Reality Commit v1

Status: IMPLEMENTED CANDIDATE on a stacked branch. Merge and production deployment
are not implied by the local SQLite acceptance slice.

## Atomicity contract

The store persists the current state snapshot, a commit receipt, and a hash-linked
event row in a single SQLite transaction. The commit operation uses BEGIN IMMEDIATE,
checks the exact expected revision and state digest, performs a conditional
compare-and-swap update, and writes its event and idempotency record before COMMIT.

The store's configured clock supplies verification and commit timestamps;
the API does not accept a caller-selected commit time. The live admission evaluator
and reflexive checker run immediately before the database transaction. During that
transaction, the stored state is compared with the exact pre-state supplied by the
caller; another writer that wins first causes StaleStateError. The transaction
reads the store clock again and rejects grants/evidence that have expired or become
stale before the state update. Verifier callbacks are not run while holding the
database write lock, to avoid blocking on remote latency. External trust revocation
still cannot be made atomic with SQLite: production adapters must define
revocation-epoch and short-lived-attestation guarantees and document the remaining
time-of-check/time-of-use window.

## Required preflight

- A prepared Ω³ decision has status ADMIT and binds the exact object, previous
  state digest, proposed state digest, and action.
- A content-addressed assurance receipt has verdict CHECKED_ADMISSION_CANDIDATE,
  matches the decision digest, and passes its integrity check.
- The current authority grant and evidence callbacks are re-run at commit time.
- A new decision and assurance receipt are computed at that time.
- Only a live ADMIT plus a matching reflexive assurance candidate can continue.

## Transaction contents

- Conditional state compare-and-swap by object ID, revision, and old state digest.
- Update current state snapshot and state digest.
- Append a hash-linked STATE_COMMITTED event bound to previous/new digests and
  the commit-time request/assurance fingerprints.
- Persist the idempotency key and commit receipt.
- Commit all database changes together; exceptions before COMMIT roll back all
  three record families.

The idempotency key identifies a logical operation excluding evaluation time.
Retries of an already committed operation return the prior receipt; reuse for a
different operation is rejected. A second transition based on a stale revision
cannot overwrite the committed state.

## Evidence and recovery limits

The event chain is tamper-evident relative to the trusted database state. It is
not an externally immutable witness, digital signature, or proof that an event
represents external truth. A restored/modified database requires a separately
trusted checkpoint or witness to detect rollback to an older but internally
consistent database snapshot. Production deployment must add backup/recovery
tests against the chosen database and storage/permission boundary.

The verifier callbacks must independently check signatures/attestations,
subject binding, trust roots, expiry, and revocation. The reference test callbacks
are deterministic fakes. The store does not run external commands, invoke agents,
or deploy systems.

## Verification

Run:

`python -m pytest -q tests/test_omega3_kernel.py tests/test_omega3_assurance.py tests/test_omega3_commit.py`

The tests cover idempotent retry, stale concurrent candidates, live rejection,
content-addressed receipts, event-chain tampering, and injected failures at
transaction boundaries. Passing them does not prove production storage safety,
external trust atomicity, or full-system write-path noninterference.
