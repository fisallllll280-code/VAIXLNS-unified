# Ω³ Sovereign Reality Kernel v1

Status: IMPLEMENTED CANDIDATE — merge and production enforcement are not implied.

## Scope

This implementation adds a deterministic admission evaluator and tamper-evident
decision-audit primitives under **canon/kernel**. It extends the existing
VAIXLNS-unified constitution, ledger, proof, provenance, evidence, and VX
components. It does not replace those components, and it does not make this
directory the canonical source of project authority. The project genome and
approved constitutional records remain the authority anchor.

The evaluator is pure with respect to external systems. It performs no network
calls, tool invocation, filesystem writes, canonical commit, or deployment.

## State contract

A state snapshot is represented as:

**S = (G, C, R, O, E)**

- **G**: immutable object identity and root identity fields.
- **C**: versioned contracts and constitution/ontology fingerprints.
- **R**: policy/authority metadata.
- **O**: append-only observation history.
- **E**: evidence references bound to state claims.

The state digest is SHA-256 over canonical JSON (sorted keys, compact encoding,
UTF-8, and rejection of non-finite numeric values). SHA-256 provides a
content fingerprint; it does not establish authorship, correctness, or truth.

## Admission conditions

A candidate is **ADMIT** only when all of the following hold:

1. Object identity and expected pre-state digest match.
2. Revision increments exactly once.
3. Required identity and contract fields remain present.
4. Protected identity and constitutional contract fields do not change silently.
5. Observation and evidence histories preserve their previous prefixes.
6. Action, principal, object scope, policy version, and grant time satisfy policy.
7. An injected authority verifier independently accepts the authority artifact.
8. Required evidence receipts are current, bound to the proposed state digest,
   use policy-trusted verifier identities, and pass the injected evidence verifier.
9. The policy's minimum receipt count and distinct source-label count are met.

**ADMIT means eligible for a separately controlled commit, not committed.**
Every decision sets **commit_performed=false**. Canonical storage must perform an
atomic compare-and-swap and persist a commit receipt before declaring a state
transition committed. That adapter is outside this v1 slice.

**REJECT** means a modeled condition failed. **UNKNOWN** means the available
evidence did not meet a configured threshold. **QUARANTINE** means an independent
verification path was missing or unable to reach a conclusion.

## Cryptographic and epistemic boundaries

The callbacks are trust boundaries, not magic booleans. Production adapters must
verify real signatures or attestations against pinned trust roots, bind signed
claims to exact canonical payload digests, check revocation and freshness, and
produce independently retrievable verification receipts. The test callbacks in
the unit tests are deterministic fakes, not cryptographic verification.

Distinct source identifiers do not prove statistical or organizational
independence. A malicious or misconfigured adapter can lie. A hash chain detects
changes relative to a trusted checkpoint; it is not, by itself, a signature,
an immutable external ledger, or proof that an event was true.

The audit-chain replay reconstructs the ordered decision record only. It does
not replay decisions into canonical state or infer that an **ADMIT** event was
committed. State replay requires a separately authenticated commit-event format
and a durable commit adapter.

A constitutional or ontology change is rejected in this slice when it alters
protected fields. A future constitutional-change protocol must use an explicit,
versioned amendment path with independent authorities; it must not bypass these
checks by renaming or deleting protected fields.

## Mapping to the master consolidation

| Concern | Existing/target integration point | Status of this slice |
|---|---|---|
| Canon and constitution | project genome, core/sovereign_constitution.py | Read-only boundary; no canon writes |
| State and admission | canon/kernel/omega3_kernel.py | Implemented candidate evaluator |
| Event history | core/ledger.py plus external storage adapter | Standalone hash-linked decision audit; not yet wired |
| Evidence and provenance | evidence/, provenance/, proof/ | Verifier callbacks only; no automatic connector |
| Runtime | vx/ and the supervised VX bootstrap work | No command execution; no runtime integration yet |
| ARC-X / Ω-PRE | assurance integration work in VAIXLNS | No direct call or PR-chain merge implied |
| Agents / NEXENT | synthesis and orchestration components | No provider/tool invocation |
| Ω-ECO | separate economic-kernel proposal | Economics not implemented here |
| Physics / chemistry | boundedness and state/transition constraints | Inspiration for tests; no claim of new physical law |

## Initial invariant mapping

- INV-001: No Proof = No Commit — no commit occurs in the evaluator.
- INV-002: Observation is not proof — observations are never accepted as evidence automatically.
- INV-003: Capability is not authority — action scopes and a separately verified grant are required.
- INV-004: Intent is not execution — this module executes no action.
- INV-005: Execution is not verification — callbacks verify artifacts independently.
- INV-006: Evidence is not truth — digests bind content but do not establish truth.
- INV-007: Extension is not replacement — prior state history must remain a prefix.
- INV-008: No unverified state promotion — missing verification fails closed.
- INV-009: Unknown is not failure — insufficient evidence yields UNKNOWN.
- INV-010: Authority is explicit — principal, target, scopes, policy version, and validity are checked.

## How to verify locally

Run **python -m pytest -q tests/test_omega3_kernel.py**.

The dedicated GitHub Actions workflow runs the focused test suite. Passing unit
tests establishes the tested behavior of this module only; it does not prove
production enforcement or correctness of any external verifier.
