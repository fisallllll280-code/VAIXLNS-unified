# VX-runtime Effect-Boundary Audit — 2026-11-10

## Audit basis

Read-only inspection of the VX-runtime main branch at commit d6b2972239a1ea053b3ff695e6379eee8b9db39e.

Files inspected:
- vxruntime/core.py — blob 13a8b2586c2cbddc83b8afbf9fda541481d65fba
- vxruntime/admission.py — blob 48260dca955c00a796a69a63594c93223ce5f598
- vxruntime/agent_runner.py — blob 829d660fbeea44bd38d375c6d0e005cffdf211ae
- vxruntime/external_integration.py — blob ec06b1635b9776689fb82048115e185801997343
- vxruntime/repository_gateway.py — blob 2907959741635ea1a8914e3737d8dd5df888018c
- tests/test_core.py, tests/test_admission.py, tests/test_external_integration.py
- docs/RIRF_EXECUTION_BOUNDARY_V1.md
- docs/VAIXLNS_FEDERATION_ROLE_V1.md
- VAIXLNS_REPOSITORY_CONTRACT.md

This is a bounded source audit, not a complete repository-wide sink inventory or production penetration test. No file was changed in VX-runtime during this audit.

## 1. Observed implementation

### 1.1 Deterministic core — IMPLEMENTED + TESTED within the declared reference scope

vxruntime/core.py implements:
- capability allowlisting before worker invocation;
- immutable input snapshots using deep copies;
- deterministic input/output SHA-256 digests;
- an in-memory append-only event hash chain;
- replay against original captured inputs;
- failure and blocked-state recording.

tests/test_core.py covers policy denial before worker execution, replay agreement/divergence, execution identity reuse, nested input mutation, failed execution, and ledger-chain integrity.

Boundary: EventLedger is in-memory. Replay is a pure worker verification operation. These tests do not establish durable cross-process event recovery or exactly-once external provider effects.

### 1.2 Evidence admission — IMPLEMENTED as a local proof-bundle validator

vxruntime/admission.py checks:
- successful execution and valid ledger chain;
- exactly one matching completion event bound to execution ID, capability, input hash, output hash, and event hash;
- exact proof/execution identity fields;
- a non-empty source commit;
- verifier identity membership in a caller-supplied trusted set;
- verifier result equal to PASS;
- presence of four named evidence-hash fields.

It returns ADMITTED, HOLD, or BLOCKED. The module explicitly states that it does not grant permissions, execute tools, or merge branches.

Boundary: the inspected validator checks that evidence-hash values are present; it does not retrieve and hash the underlying evidence objects or verify cryptographic signatures over the proof bundle. A caller-supplied trusted-verifier set is a trust input, not proof of verifier independence. This is an admission-evidence check, not a provider effect gate.

### 1.3 Fixed local agent runner — IMPLEMENTED for a pure local task

vxruntime/agent_runner.py provides:
- one fixed local readiness worker;
- host-supplied grants and capability checks;
- minimised validated input;
- SQLite transaction serialization for duplicate task claims;
- idempotency conflict detection;
- receipt integrity hashing;
- bounded receipt retention (up to 24 hours);
- no automatic retry after unknown outcomes;
- cooperative cancellation/deadline checks.

The returned receipt explicitly records environment=LOCAL_TEST, external_calls=0, and production_gate=HOLD. The module docstring excludes HTTP, shell, plugin loading, model providers, and arbitrary worker registration.

Boundary: the worker is intentionally pure. Cooperative cancellation is not a provider-side fence. SQLite receipt handling must not be generalized into an exactly-once guarantee for external effects.

### 1.4 External integration gate — IMPLEMENTED as a predicate, not an execution mediator

vxruntime/external_integration.py checks explicit authority, integration identity, capability membership, endpoint/contract presence, dependency/environment fingerprints, proof identity/fingerprint matches, and proof expiry.

It returns a boolean. The inspected module does not itself:
- dispatch a provider request;
- wrap or mediate every effect sink;
- bind a final immutable request body to a provider commit;
- persist effect reservations or sink receipts;
- install a provider-side cancellation/recovery fence;
- reconcile ambiguous delivery.

Boundary: this gate is an eligibility predicate. It must not be represented as complete mediation or effect closure.

### 1.5 Repository gateway — IMPLEMENTED as read-only metadata retrieval

vxruntime/repository_gateway.py allows a fixed repository allowlist and one explicit read capability, performs a GitHub metadata GET, checks repository identity, and emits local hashes/ledger evidence. Its result explicitly reports federation_edge_activated=false, canonical_write=false, and live_connection_verified=false.

Boundary: it is a read-only metadata adapter, not a repository mutation or multi-repository execution gateway.

## 2. Epistemic status

| Capability | Evidence-based status | Scope / limitation |
|---|---|---|
| Deterministic local execution | IMPLEMENTED + TESTED | Pure local workers in the reference runtime |
| In-memory event hash chain | IMPLEMENTED + TESTED | No durable cross-process ledger demonstrated by core tests |
| Deterministic replay | IMPLEMENTED + TESTED | Pure worker replay against captured inputs |
| Proof-bundle admission | IMPLEMENTED + TESTED | Presence/identity checks; not a full cryptographic evidence verifier |
| Local SQLite task deduplication | IMPLEMENTED + TESTED | Fixed pure worker; bounded receipt retention |
| External integration eligibility predicate | IMPLEMENTED | Boolean checks only; not effect dispatch |
| Read-only GitHub metadata gateway | IMPLEMENTED | GET only; live connection explicitly not verified by returned receipt |
| Provider-side effect admission | NOT ESTABLISHED IN INSPECTED FILES | No provider commit mediator found in this bounded inspection |
| Commit-time authorization / request binding | NOT ESTABLISHED IN INSPECTED FILES | Requires provider adapter and exact request binding |
| Arrival and claim fences | NOT ESTABLISHED IN INSPECTED FILES | No sink-side recovery contract found in inspected paths |
| Distributed exactly-once effects | NOT CLAIMED | Current core and local runner do not prove it |
| Production deployment | NOT ESTABLISHED BY THIS AUDIT | Existing repository contract limits its own evidence scope |

NOT ESTABLISHED IN INSPECTED FILES is deliberately not a claim that no such code exists anywhere in the full repository. A bounded inspection cannot promote an unobserved capability to MISSING.

## 3. Required extension path — extend, do not duplicate

The existing VX core, admission validator, and external integration predicate should remain the base. Before any write-capable connector is introduced, the implementation must add a provider-aware effect boundary with explicit contracts.

### E1 — Effect identity and immutable request

Bind run ID, stable logical effect key, principal, capability, provider, operation, target, immutable request hash, approval epoch, policy version, provider precondition, and expiry. Replays must reuse the same logical effect key and exact request.

### E2 — Stateful lifecycle

Represent at least HELD, APPROVED, CLAIMED, SUBMITTED, UNCERTAIN, COMMITTED, REJECTED, and CANCELLED as distinct states. State changes must be durable, monotonic where required, and compare-and-swap protected. A timeout is not a NO_EFFECT result.

### E3 — Provider contract classes

Do not assume all providers support the same guarantee:
- ATOMIC: authorization, provider effect, and terminal receipt share one atomic transaction.
- CONTROLLED_IDEMPOTENT: provider supports stable request identity, exact-body idempotency, terminal lookup, and a delivery fence across the recovery horizon.
- UNSUPPORTED: ambiguous delivery remains HOLD/UNCERTAIN; no automatic retry, reservation release, or successor.

### E4 — Commit-time enforcement

The actual provider adapter must enforce the immutable request and current authorization at the last preventable effect boundary. A generic boolean predicate called earlier in the workflow is insufficient.

### E5 — Recovery evidence

Require authoritative sink-side per-operation acceptance records. Separate arrival fencing for delayed old requests from claim fencing for concurrent recovery workers. Declare retention limits for sink receipts, deduplication keys, source history, and fences.

### E6 — Complete-mediation inventory

Inventory every write path and credential: network clients, filesystem mutation, subprocesses, repository writes, model-provider writes, cloud APIs, queues, callbacks, and plugins. Any unwrapped path blocks a complete-mediation claim.

## 4. VX acceptance tests to add before external activation

1. Approval pause with a sibling worker attempting an effect: no pre-decision effect.
2. Sticky rejection replayed from another worker: still rejected.
3. Duplicate logical effect replay after a lost local receipt: one provider effect only.
4. Cancellation with delayed in-flight submission: provider-side fence prevents post-cancel effect.
5. Approved target/payload mutation before commit: stale request rejected.
6. Crash after provider acceptance but before local checkpoint: authoritative sink receipt resolves the outcome.
7. Delayed prior-generation request after recovery read: arrival fence blocks it.
8. Two concurrent recovery workers: only one claim can commit.
9. Deduplication/receipt retention expiry: guarantee is downgraded, never silently extended.
10. Alternate credential or direct route bypassing the mediator: complete mediation fails.
11. Incomplete effect-frontier contract: verdict is UNSUPPORTED.
12. Legitimate authorized operation: completes successfully; deny-all is not a pass.

Every test must retain the run/effect key, request hash, policy/approval epoch, provider request ID, sink receipt, fence generation, timestamps, recovery identity, and effect count.

## 5. Decision

The current VX runtime is a useful deterministic local execution and evidence base. The next meaningful step is not to add a large universal tool connector. It is to map the actual write-capable effect sinks, then extend the existing external-integration boundary with provider-specific admission and recovery contracts.

Until those controls are implemented and tested against real provider boundaries:
- keep external write capabilities disabled;
- do not claim complete mediation, effect closure, or exactly-once effects;
- keep ambiguous outcomes at HOLD/UNCERTAIN;
- preserve the existing local pure-worker lane as a separate capability;
- do not modify VAIXLNS canonical authority or the protected genome/index.
