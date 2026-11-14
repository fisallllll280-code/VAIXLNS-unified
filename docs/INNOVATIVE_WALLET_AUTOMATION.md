# VAIXLNS Innovative Wallet: Automated Pooling and Reconciliation

## Status and boundary

This is an executable reference implementation for internal ledger movements and pooled-fund accounting. The ledger store is in-memory, so it is a development/test component, not a production custody system. No bank, card, payment gateway, crypto network, or external transfer is initiated by this feature.

VAIXLNS may record a deposit only after a trusted adapter has verified the provider's signature and confirmed settlement. The adapter, database durability, authentication, regulatory/compliance decisions, and production deployment remain separate work items.

## Flow

1. Receive an internal contribution intent or a verified settlement event.
2. Validate actor, account identity, currency, positive integer minor-unit amount, and required references.
3. Check idempotency and reject key reuse with different payloads.
4. For verified funding, post a balanced journal entry: debit the wallet, credit the provider-clearing account.
5. For a contribution, evaluate the configured per-currency auto-approval limit.
6. If the amount is within the explicit limit, post one internal wallet-to-pool transfer. If above the limit, persist a pending approval request and do not move the balance.
7. On approval, re-check the current balance and currency, then post exactly once.
8. Recalculate wallet/pool totals from the journal; create contributor breakdowns without counting pending requests.
9. Reconcile with trusted provider/account snapshots. Any mismatch must quarantine the affected operation/account and alert an operator.
10. Emit an audit event to the VAIXLNS event ledger in the production adapter; retain request, approver, provider reference, transaction ID, and evidence lineage.

## Double-entry convention

Balances for wallet and pool accounts are debits minus credits. Each transaction must have equal total debits and credits. Amounts use integer minor units only: for SAR, 100 halalas represents SAR 1.00. Never use floating-point arithmetic for money.

A contribution from wallet W to pool P is:
- Credit W by amount A (reduce W's balance).
- Debit P by amount A (increase P's balance).

The accounting move is internal. It is not a bank transfer and does not prove that external funds exist.

## Automation policy

- No hard-coded amount limit: configure auto_approval_limit_minor separately for each supported currency.
- Above-limit contributions require an independent approval.
- Never post an amount greater than the wallet's available ledger balance.
- Use a unique idempotency key for every intent and enforce uniqueness in durable storage.
- Provider settlement references must be unique per provider.
- Do not accept unsigned webhooks or treat a client-submitted "paid" flag as settlement proof.
- Keep external money movement disabled until a separately reviewed provider adapter and deployment policy exist.
- Reconciliation mismatches pause the affected workflow; never silently repair balances or overwrite historical entries.
- A posted transaction is immutable; corrections must be compensating entries with their own evidence and authorization.

## Integration with VAIXLNS / VX

The production adapter should route requests through the existing identity and capability checks, then governance policy, then the wallet service. It should append a corresponding event to the sovereign event ledger and bind the event hash/transaction ID to the request lineage. Verification must independently check balanced entries, idempotency, state transition legality, reconciliation status, and replay behavior before any workflow is labeled VERIFIED or RUNNING.

Recommended capability names:
- wallet.read_balance
- wallet.request_contribution
- wallet.approve_contribution
- wallet.record_settled_funding
- wallet.reconcile
- wallet.freeze_account

Separate requestor and approver identities for high-value requests. Never grant all wallet capabilities to a general-purpose reasoning agent.

## Productionization gate

Before any real-money deployment, require:
- Durable transactional database with unique constraints on idempotency and provider references.
- Atomic balance checks and postings under serializable transactions or equivalent row-level locking.
- Signed provider webhook validation, replay defense, and settlement state validation.
- Authentication, authorization, independent approval, rate limits, fraud/AML and jurisdictional review as applicable.
- Encryption, secrets management, audit retention, backup/restore, monitoring, and incident/rollback runbooks.
- Property-based, concurrency, replay, recovery, and reconciliation tests.
- Independent security review and explicit owner sign-off.

Until these gates pass, status is IMPLEMENTED_FOR_TESTING, not VERIFIED_FOR_PRODUCTION, DEPLOYED, or RUNNING.
