# ARC-X Ω Runtime Contract v1

**Status:** IMPLEMENTED CANDIDATE — requires CI evidence and review  
**Canonical owner:** VAIXLNS  
**Runtime projection:** VAIXLNS-unified  
**Canonical specification:** [ARC-X Ω v1](https://github.com/fisallllll280-code/VAIXLNS/blob/main/docs/tools/ARC_X_EPISTEMIC_REALITY_COMPILER_V1.md)

This document defines an executable runtime-side contract. It does not replace or fork the canonical ARC-X specification.

## 1. Executable surface

- Package: `arc_x/`
- API: `compile_eir(sources, evidence, claims, proof_obligations)`
- Gate: `evaluate_admission(compilation, action, approval, authority_verifier)`
- Conformance tests: `tests/test_arc_x_core.py`

The implementation uses only the Python standard library. It is deterministic for identical input records and does not fetch network data or run supplied code.

## 2. Input types

- **SourceReceipt:** repository, immutable revision, source path, content SHA-256, retrieval timestamp, parser version, and URI.
- **EvidenceRecord:** source reference, evidence type, statement, optional linked claim, stance, test/proof result, and artifact SHA-256.
- **ClaimRecord:** stable ID, statement, type, and whether it is in the required scope.
- **ProofObligation:** claim link, verification requirement, required/optional flag, and evidence IDs.

Mutable revisions such as `main`, `master`, `HEAD`, `latest`, and `default` are rejected. A SHA-shaped value is not proof that a source is trustworthy; retrieval and hash calculation must be performed by a trusted adapter.

## 3. Compilation invariants

1. Canonical JSON uses sorted keys, compact separators, UTF-8, and rejects non-finite numbers/opaque values.
2. Every evidence item must reference a known source; claim and obligation references must resolve.
3. Contradictory supporting and refuting evidence remains visible and blocks promotion.
4. A claim with support is marked `SUPPORTED_NOT_PROVEN`, not `VERIFIED`.
5. Required proof obligations accept only source-linked passing test, runtime-trace, or proof-artifact records with artifact hashes.
6. Missing support, invalid references, duplicate IDs, and open proof obligations are explicit findings.
7. Compilation produces an EIR digest; the digest excludes no fields from the EIR payload.

## 4. Admission boundary

`READ` and `RESEARCH` can be marked eligible for review because they do not create external effects. `VERIFY` checks the explicitly declared scope. `EXECUTE` and `CANONICAL_COMMIT` require all declared claim/proof conditions plus a scope-matched approval verified by a trusted host-supplied callback.

The callback is a trust boundary: the caller must ensure it authenticates the actor, approval artifact, revocation state, and requested scope. Passing a lambda that returns true is suitable only for a unit test and grants no real-world authority. This package itself does not authenticate users, sign approvals, execute code, deploy systems, or write to the canonical registry.

## 5. State semantics

- `MISSING`: an invalid/missing reference or required evidence prevents safe continuation.
- `CONFLICT`: the same claim has both supporting and refuting evidence.
- `PARTIAL`: the declared proof scope is incomplete.
- `READY_FOR_REVIEW`: required declared obligations have been assembled without blocking findings; this is not production readiness.
- `VERIFIED` is not assigned by raw compilation. `verified_for_declared_scope` is a bounded predicate over explicit claims and proof obligations, not a claim that the whole project/system is verified.

## 6. Fail-closed rules

Unknown actions, unpinned revisions, contradictory evidence, missing proof, wrong approval scope, missing verifier, and verifier exceptions must not result in admission. The previous canonical state must remain unchanged unless a separate trusted authority layer commits a reviewed change.

## 7. Validation

Run:

```bash
python -m unittest tests.test_arc_x_core -v
python -m pytest -q
```

CI pass on this branch is required before changing this candidate's state from `IMPLEMENTED` to `VERIFIED`.
