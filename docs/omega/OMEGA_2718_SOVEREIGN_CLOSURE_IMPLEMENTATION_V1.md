# Ω.2718 — Sovereign Closure Evidence Gate V1

**Implementation state:** PARTIAL — executable evidence-bundle evaluator and adversarial tests.
**Canonical:** false. This proposal does not modify project.genome or Ω.000.
**Decision rule:** missing, stale, malformed, untrusted, or contradictory evidence means BLOCKED.

## Purpose

Turn the eleven HM-1 layers into an executable, reviewable acceptance gate. The gate evaluates evidence at a bounded subject and revision; it does not claim that all future gaps are impossible or that every external runtime is active.

## Layer-to-check mapping

1. Constitutional Binding — binds the subject to an immutable, hashed source reference.
2. Meta Proof — verifies claim digests, parent ordering, distinct proof author/verifier roles, and both signatures.
3. Sovereign Closure Engine — requires structural, semantic, temporal, and constitutional modes plus deterministic fail-closed behavior.
4. Historical Ratification Ledger — checks contiguous sequence numbers, monotonic timezone-aware timestamps, hash links, distinct signatures, and required governance roles.
5. Failure Sovereignty — requires the F1–F5 failure classes and preservation of the previous accepted state.
6. Dominion Conflict Resolver — requires declared priority, authority, proof, and override rules; unverified overrides are denied.
7. Proof Obligations — every claim must reference verified proof IDs and content-hashed evidence.
8. Constitutional Evolution Control — enforces threshold, independent roles, human approval, separation of requester/preparer/approver, and amendment delay rules.
9. Trust Root Registry — requires an out-of-band pinned root fingerprint, non-revoked root, and an injected signature-verification implementation.
10. Semantic Drift Detection — recomputes the snapshot digest; any drift other than none blocks final closure pending review.
11. Sovereign Audit Domain — verifies an audit digest and signature and rejects an auditor who owns any controlled engine.

## Trust and cryptographic boundary

The caller must provide the trusted-root fingerprint separately from the evidence bundle and inject a real cryptographic verifier. If either is absent, the gate cannot close. The verifier must validate signature algorithms, key identity, revocation/trust chain, key usage, and signature encoding against an approved trust configuration. The repository includes only a synthetic verifier inside unit tests; it is explicitly test-only.

The ledger verifier validates a signed hash chain supplied in the evidence. Storage-level append-only or WORM enforcement, key custody, trusted time, trusted-root distribution, and independent organizational identity must be supplied by the deployment environment and verified separately.

## Evidence semantics

CLOSED means only that the provided bundle passed all eleven checks with the supplied trust inputs. It does not automatically mean a system is running, production-ready, authorized to mutate canonical sources, or cleared for financial/external side effects. Those capabilities require their own live probes, capability tests, and human approval.

The phrase “every proof must itself be provable” is implemented as a bounded verification chain anchored to a pinned trust root, not as an unbounded infinite regress. Ω.2718 cannot truthfully guarantee zero possible future gaps; changes in code, keys, dependencies, ontology, or environment can invalidate prior evidence.

## Test command

Run the new tests with:

    python -m unittest tests.test_omega_2718_sovereign_closure

The existing repository CI remains the integration verifier. No result is accepted as VERIFIED until the new commit's CI has completed successfully and its test logs are inspected.

## Acceptance gates still outside this slice

- No production cryptographic adapter or managed trust-root service is bundled here.
- No WORM ledger or trusted timestamp authority is provisioned.
- No external system, office, MCP provider, or phone UI is declared live by this module.
- No canonical registry promotion, merge, or deployment is authorized by this proposal.
