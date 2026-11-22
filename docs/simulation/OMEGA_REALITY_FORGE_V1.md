# Ω Reality Forge V1 — Deterministic Adversarial Simulation

**State:** PROPOSAL / design contract. Do not describe this specification as an implemented simulator.
**Purpose:** add a deterministic simulation layer over existing VX/Pattern Foundry/Failure Genome concepts without duplicating their responsibilities.

## Core loop

Architecture Candidate → World Model → Scenario Set → Adversarial Run → Failure Genome → Counterfactual → Repair Candidate → Replay → Independent Verification

The Forge orchestrates candidate experiments; it does not define canonical reality, certify truth by itself, or grant production authority.

## Simulation boundary

All experiments default to synthetic fixtures and a sandbox. No production credentials, live payment rails, external write APIs, customer data, or deployment targets are permitted. A separate explicit human authorization and independently verified gate is required before any non-sandbox side effect.

## Determinism contract

Each run records:
- candidate commit SHA and dirty-tree status;
- scenario/input canonical JSON digest;
- simulator version, schema version, and dependency lock digest;
- explicit seed and deterministic clock;
- event sequence and previous-event hash;
- expected invariants, observed outputs, failure classification;
- output/artifact digests, exit status, and replay command.

Canonical serialization must reject non-finite numbers and ambiguous representations. Money values use integer minor units or decimal-safe strings, never binary floating-point. The same candidate, scenario, seed, simulator version, and declared environment should produce byte-stable normalized outputs. Any nondeterministic field must be isolated and declared rather than silently normalized away.

## Scenario families

1. **Contract drift:** missing/renamed fields, incompatible schema versions, unexpected properties.
2. **Authority attacks:** unauthorized actor, self-approval, privilege escalation, stale approval, changed payee after approval.
3. **Evidence attacks:** missing artifact, wrong commit, tampered digest, stale proof, broken hash chain, unsupported claim.
4. **Distributed-runtime faults:** worker loss, duplicate delivery, timeout ambiguity, out-of-order events, lease expiry, partial completion.
5. **Recovery/replay:** crash between state transitions, interrupted write, duplicate retry, restart from checkpoint, replay divergence.
6. **Federation faults:** unavailable repository, stale source snapshot, incompatible contract, denied integration, rate limit.
7. **Financial workflow faults:** duplicate idempotency key, stale balance, ledger mismatch, provider timeout with unknown outcome, approval separation.
8. **Prompt/tool boundary attacks:** retrieved instructions attempting to override policy, unexpected MCP tool, oversized output, secret-like output.

## Required safety properties

- **Fail closed:** unknown state, unknown capability, missing evidence, and policy conflict never imply approval.
- **No self-approval:** author/requester/preparer cannot be the independent approver for the same protected action.
- **Idempotency:** retries cannot silently create duplicate state transitions or transactions.
- **Evidence binding:** proof binds to exact candidate commit, scenario digest, tool/provider revision, and run identity.
- **No false promotion:** passing a simulation is not equivalent to verified production readiness.
- **Preserve prior state:** failed or interrupted experiments leave the canonical source and previous accepted state unchanged.
- **Bounded execution:** every run has time, memory/output, network, filesystem, and retry limits.
- **Reproducible failure:** a recorded failure can be replayed from its declared inputs or marked explicitly non-reproducible with a reason.

## State model

PROPOSED → CONTRACTED → SIMULATING → SIMULATED → REPLAYED → INDEPENDENTLY_VERIFIED → HUMAN_REVIEW

Terminal or blocking states: BLOCKED, FAILED, NON_REPRODUCIBLE, REJECTED. No simulation state transitions directly to production admission.

## Acceptance tests (minimum)

- identical inputs and seed produce identical normalized event/output digests;
- changed scenario input changes the input digest;
- changed candidate commit invalidates prior evidence binding;
- tampered event breaks chain verification;
- missing approval or authority fails closed;
- stale approval after payee/policy change is rejected;
- duplicate retry is idempotent;
- worker timeout with uncertain outcome becomes manual-review/unknown, not success;
- failure replay reproduces the same classified failure;
- failed experiment preserves canonical and previous accepted state;
- simulation cannot call production/mutating connectors;
- independent verifier identity differs from candidate author identity.

## Integration points

- Reuse existing Pattern Foundry, Failure Genome, VX runtime, execution-tool contracts, and evidence ledger where they already exist.
- Do not create parallel registries or shadow canonical indices.
- Emit candidate artifacts and evidence references for ARC-X/VV admission; only the canonical governance owner may approve canonical index changes.
- The initial implementation should be a pure deterministic harness with fixture providers and no network. External providers can be added only after separate integration admission.

## Evidence rule

Until executable code, test results, and replay artifacts exist, all claims in this document remain SPECIFIED/PROPOSAL. A green CI badge alone is not proof that every scenario family is covered.
