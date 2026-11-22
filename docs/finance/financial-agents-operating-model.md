# VAIXLNS Ω — Governed Financial Agent Operating Model

**Document ID:** `FIN-OPS-001`  
**Version:** `1.0.0`  
**State:** `PROPOSAL`  
**Authority:** Non-canonical engineering specification; it does not grant financial authority or prove live integrations.

## Objective

Provide a single governed workflow for financial operations across VAIXLNS, VLNS, VX and connected systems: discover and index capabilities, collect authorized data, reconcile ledgers, forecast liquidity, prepare budget and payment proposals, enforce risk controls, capture approvals, and retain reproducible evidence.

## Agent boundaries

| Agent | Allowed work | Forbidden work |
|---|---|---|
| Financial Orchestrator | Coordinate tasks, assign work, track state and evidence | Approve its own workflow or move money |
| Treasury Analyst | Authorized balance reads, cash-flow forecasting, scenario analysis | Transfer funds or change source records |
| Controller | Reconciliation, close checks, variance reporting | Delete evidence or approve its own adjustments |
| Payment Preparer | Draft instructions, validate payee details, idempotency checks | Release or submit live payments |
| Risk & Compliance | Screen permitted metadata, flag anomalies, place holds | Clear its own hold or bypass policy |
| Independent Auditor | Verify immutable events, hash chains and reconciliation | Mutate transactions or approve payments |

## End-to-end workflow

1. **Discover:** enumerate systems and connectors from approved manifests; do not infer connectivity from a name or configuration alone.
2. **Authorize:** verify actor identity, system owner, tenant, scopes, data minimization and purpose.
3. **Collect:** use read-only interfaces first; record source, revision, timestamp, currency and freshness.
4. **Normalize:** validate schemas and currency/precision; use integer minor units or decimal-safe arithmetic, never binary floating-point for money.
5. **Reconcile:** compare source ledger, provider statement and internal event ledger; produce exceptions rather than silently repairing discrepancies.
6. **Analyze:** forecast liquidity, budgets and cash flow with assumptions, confidence ranges and provenance.
7. **Prepare:** create an immutable proposal fingerprint, idempotency key, payee fingerprint, amount, currency, purpose and supporting evidence.
8. **Review:** run policy, fraud, sanctions and limit checks where legally applicable. Any unresolved signal becomes `RISK_HOLD`.
9. **Approve:** require two distinct authorized human approvers for money movement. The requester, preparer and risk reviewer cannot approve their own request. Approval binds to the exact proposal fingerprint; any material change invalidates it.
10. **Execute:** live payment execution is disabled by default. If separately admitted in the future, an authorized human must release the transaction through a vetted provider with least-privilege credentials and a strict allowlist.
11. **Verify:** record provider receipt, reconcile the resulting transaction, and verify idempotency, event integrity and final state.
12. **Close:** emit a signed or otherwise tamper-evident evidence bundle; preserve failures and superseded proposals; never erase history.

## State machine

`DRAFT → VALIDATED → PENDING_APPROVAL → APPROVED → SUBMITTED_BY_AUTHORIZED_HUMAN → PROVIDER_ACCEPTED → RECONCILED`

Alternative terminal or hold states: `RISK_HOLD`, `REJECTED`, `CANCELLED`, `FAILED`, `MANUAL_REVIEW`.

No state transition grants authority by itself. State changes must be validated against the policy and actor permissions.

## Indexing and traceability

Every financial capability must have a stable `capability_id`, owner system, source path, contract/version, access mode, data classification, dependency and environment fingerprints, test evidence, operational status, last-verified timestamp and evidence reference. The inventory in `financial-capability-index.v1.json` is a local proposal index; it does not replace or edit canonical `project.genome` or `Ω.000`.

Use these evidence labels consistently:

- `VERIFIED`: reproducible execution evidence exists for the exact revision.
- `SPECIFIED`: contract or behavior is documented but not proven in execution.
- `PARTIAL`: only part of the capability is proven.
- `MISSING`: required artifact or evidence is absent.
- `CONFLICT`: authoritative sources disagree.
- `PROPOSAL`: design-only; not admitted for production.

## Required acceptance tests

- No configured credentials: fail closed before mutation.
- Unauthorized actor or insufficient scope: deny and emit an audit event.
- Requester attempts self-approval: deny.
- Same person occupies both approval roles: deny.
- Amount, currency, payee or proposal fingerprint changes after approval: invalidate approval.
- Duplicate idempotency key: do not create a second payment.
- Stale balance, stale policy, missing contract or unknown provider: hold.
- Risk/compliance alert: hold; only an independent authorized reviewer can resolve it.
- Provider timeout or uncertain outcome: query status and reconcile before retry; never blindly resubmit.
- Ledger mismatch or hash-chain failure: stop and escalate.
- Evidence bundle is reproducible and links the source revision, policy version and actor approvals.
- Sandbox test suite passes before any separate request to enable live execution.

## Rollout gates

1. Documentation and index review.
2. Read-only source connectors and data-quality checks.
3. Deterministic simulation with synthetic fixtures.
4. Security, authorization, replay, idempotency and reconciliation tests.
5. Independent finance/security review.
6. Explicit human authorization for any production connector.
7. Gradual, monitored admission with an immediate disable switch and documented incident response.

## Non-goals and safeguards

This specification does not connect to a bank, custody assets, initiate a payment, provide legal/tax/investment advice, or certify regulatory compliance. Use a vetted provider and obtain jurisdiction-specific finance, security and compliance review before any live funds movement. Never commit API keys, bank credentials, account numbers or customer financial data to Git.

## Change control

All implementation changes must be made on a branch and reviewed through a pull request. Preserve `project.genome` and `Ω.000`; changes to canonical sources require a separate explicit approval and evidence-backed migration plan. No automatic merge or production deployment.
