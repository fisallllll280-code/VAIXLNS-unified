# VX AI Request Audit Ledger v1

**Status:** Initial implementation slice on a feature branch; not yet merged or production-admitted  
**Runtime surface:** infra/vx_ai_request_audit.py  
**Storage:** Existing hash-linked infra.durable_store.DurableEventStore (SQLite, local/single-node)  
**Request schema:** schemas/vx-ai-request-audit.v1.schema.json

## 1. Purpose and boundary

The ledger provides a provider-neutral, append-only event history for a model request that passes through VX. It covers request identity, execution transitions, provider attempts, output references, auxiliary data sources, cost entries, verification evidence, and billing reconciliation.

This slice is an audit module, not an HTTP API server and not a provider integration. It does not call OpenAI, Anthropic, Google, Ollama, or any other provider. A router or adapter must call the ledger explicitly at the relevant lifecycle points.

The module uses the existing DurableEventStore rather than introducing a competing SQLite schema. Its request aggregates share the store's global hash-linked sequence with existing VX evidence events.

## 2. Data protection rules

- Raw prompts, model outputs, credentials, bearer tokens, and API keys are not accepted in the request, attempt, output, source, or cost records.
- Store hashes and restricted artifact references. Artifact access controls and retention policies remain the responsibility of the referenced store.
- The request-creation method rejects unknown fields; callers must not pass an unfiltered provider payload.
- Used auxiliary sources require a SHA-256 content digest. Source retrieval, returned data, use in the output, blocking, and failure are distinct states.
- Currency totals are derived using decimal strings. Binary floating-point values are rejected for monetary amounts.
- No request is VERIFIED solely because a provider returned data. VERIFIED requires checks_passed=true and at least one evidence reference.

## 3. Event contract

Every event has a unique ID, an aggregate ID equal to request_id, the actor VX:AIRequestAuditLedger, a capability label, an ingestion timestamp, a sequence number, and a hash linked to the preceding durable event.

| Event type | Purpose |
|---|---|
| VX_AI_REQUEST_CREATED | Immutable request/model/policy identity and input digest |
| VX_AI_REQUEST_STATUS_CHANGED | Validated execution-state transition with actor and reason |
| VX_AI_ATTEMPT_RECORDED | Provider/model attempt, request ID, token counts, latency and outcome |
| VX_AI_OUTPUT_RECORDED | Output digest, restricted reference, format and token count |
| VX_AI_SOURCE_RECORDED | Auxiliary source lineage, digest, retrieval time and contribution link |
| VX_AI_COST_RECORDED | Estimated/reported/invoice/manual cost item |
| VX_AI_BILLING_STATUS_CHANGED | Explicit reconciliation or dispute decision |
| VX_AI_VERIFICATION_RECORDED | Independent verification result and evidence references |

Event IDs for request creation, attempts, outputs, sources, cost items, and verification records are deterministic. Replaying the same ID and same payload is idempotent; reusing an ID with different content fails closed. Status transitions use a deterministic from/to key, and invalid transitions are rejected.

## 4. Lifecycle and three independent states

Execution, verification, and billing are separate dimensions.

Execution starts at RECEIVED and follows a constrained transition graph. A request cannot transition to SUCCEEDED until at least one output digest has been recorded. Non-success terminal states require an explicit reason. Terminal execution states cannot be silently rewritten.

Verification starts at PENDING. A later verification event may record VERIFIED, FAILED, INCONCLUSIVE, or NOT_REQUIRED. A failed or inconclusive verification remains visible in history even if a later independent verification is performed.

Billing starts at NOT_AVAILABLE. Estimates move it to ESTIMATED; a provider-reported, invoice, or manual cost item moves it to PENDING_RECONCILIATION. RECONCILED requires at least one non-estimated cost item. A dispute requires a reason. A new actual cost item after reconciliation returns the status to pending reconciliation.

## 5. Time semantics

Two times must not be confused:

- The durable event's created_at is when VX recorded the audit event.
- Nested timestamps such as started_at, first_token_at, completed_at, retrieved_at, and occurred_at describe the activity being recorded.

All supplied timestamps must include a timezone and are normalized to UTC. The adapter should use a monotonic clock to measure durations inside a process, then persist measured durations such as latency_ms and time_to_first_token_ms. UTC wall-clock differences are reported separately as observed metrics and can be affected by clock skew across machines.

## 6. Cost semantics

Each cost entry includes a unique cost_record_id, category, CHARGE or CREDIT, a basis (ESTIMATE, PROVIDER_REPORTED, INVOICE, or MANUAL), exact decimal amount, three-letter currency, pricing source, tariff version, occurrence time, and optional invoice reference.

Do not aggregate different currencies into a single total without an explicit FX source, timestamp, and conversion policy. Distinguish cost entries for each attempt and tool. Reconciliation should compare provider-reported usage with invoice or billing exports and protect against duplicate provider request IDs or duplicated cost records.

## 7. API surface

The module exports VXAIRequestAuditLedger with these operations:

- create_request(record): writes initial identity and input hash; rejects unknown fields.
- transition_status(request_id, to_status, changed_by=..., reason=...): validates the execution graph.
- record_attempt(request_id, attempt): records provider/model attempt metadata and timing.
- record_output(request_id, output): stores output hash/reference, never raw output.
- record_source(request_id, source): records auxiliary-source lineage.
- record_cost(request_id, cost) and set_billing_status(...): retain itemized costs and reconciliation decisions.
- record_verification(request_id, verification): requires evidence and passed checks before VERIFIED.
- request(request_id): reconstructs the current summary and event references.
- verify_integrity(): verifies the backing hash chain.

Example request creation:

    ledger.create_request({
        "request_id": "vxreq-example-001",
        "trace_id": "vxtrace-example-001",
        "actor_id": "VX-Research-01",
        "purpose": "technical_analysis",
        "provider": "openai-compatible",
        "model_id": "configured-model-id",
        "policy_version": "policy-v1",
        "input_hash": "<64-character SHA-256 digest>",
        "input_ref": "secure://restricted-artifacts/input-001",
        "input_classification": "INTERNAL"
    })

The example digest is a placeholder and must be replaced with a real digest. Pass only fields accepted by the request schema.

## 8. Tests and acceptance

Run the local, deterministic tests with:

    python -m pytest -q tests/test_vx_ai_request_audit.py

The tests cover request creation and replay, rejected raw-prompt fields, timezone and digest validation, legal/illegal status transitions, output-before-success, attempt timings, source lineage, exact decimal cost, reconciliation, verification evidence, and detection of a modified SQLite event.

Acceptance for this slice means the audit module and its tests pass in CI and the hash chain validates. It does not establish live provider connectivity, production persistence/backup, distributed multi-writer safety, external tamper-proof storage, API authentication, or deployment readiness.

## 9. Required next integration steps

1. Connect VX's model router and every provider adapter to this interface; ensure every attempt and retry gets its own attempt_id.
2. Wire source adapters so only actually retrieved/used/blocked/failed sources are recorded, with digests and authorized references.
3. Ingest provider usage responses and invoice exports; define per-provider tariff/version adapters and reconciliation reports.
4. Add request/tenant budgets, redaction tests, retention and access controls, durable backup/restore tests, and replay checks.
5. Run adapter integration tests and an independent review before marking the feature admitted or production-ready.
