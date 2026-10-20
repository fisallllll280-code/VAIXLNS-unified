# VAIXLNS — Public Project Brief v1

**Publication state:** DRAFT_PENDING_HUMAN_APPROVAL  
**Project stage:** Open engineering initiative; selected components and a candidate kernel are under development.

## The problem

AI-enabled systems can blur important boundaries: having a capability is not the same as having authority to use it; a command completing does not prove its outcome; and a content hash does not prove that a claim is true. As systems become more automated, teams need explicit state-transition rules, inspectable evidence, and a way to report unknowns instead of silently promoting them to success.

## The engineering direction

VAIXLNS explores a governed lifecycle for systems and agents, from identity and contracts through scoped authority, execution, observations, evidence, verification, and controlled evolution.

The current repository includes separate components for:
- A sovereign constitution model.
- Event-ledger and hash-linked history primitives.
- Proof-package and evidence-fingerprint primitives.
- Provenance and evidence modules.
- VX runtime and engineering components.

Repository: https://github.com/fisallllll280-code/VAIXLNS-unified

## The current Ω³ work

The Ω³ Sovereign Reality Kernel is an implementation candidate under draft review in PR #31. The work models a proposed state transition and evaluates declared identity, revision, protected-contract, authority, and evidence conditions. A reflexive-assurance checker recomputes the expected classification through a separate code path and can emit a counterexample when the kernel decision or its bindings disagree.

The tested contract is intentionally bounded:
- ADMIT means the transition is eligible for a separately controlled commit; it does not commit state.
- The checker shares the same process and data types; it is not an independently deployed trust domain.
- Verifier callbacks in the reference implementation are not a substitute for production signature verification.
- A SQLite-backed atomic-commit candidate is available in draft PR #33. Its focused workflow reports 54 tests passed at commit a7052357428e30e4632c8d7643597e8be9fd1669.
- PR #33 is stacked on PR #31; neither is merged into main. The atomicity claim is limited to the tested SQLite transaction boundary.
- Production signatures/trust-root pinning, external revocation consistency, signed external checkpoints, and complete enforcement of every protected write path remain open integration requirements.

Review the kernel and its limits:
https://github.com/fisallllll280-code/VAIXLNS-unified/pull/31

Review the atomic-commit candidate and its limits:
https://github.com/fisallllll280-code/VAIXLNS-unified/pull/33

## What we are looking for

We welcome reproducible technical review from engineers working on AI infrastructure, agent platforms, platform security, reliability, and evidence/provenance systems.

Useful contributions include:
- A minimal reproduction that violates a documented invariant.
- A review of authority-scope and evidence-freshness boundaries.
- A concurrency or recovery counterexample.
- A concrete proposal with tests and acceptance criteria.

## What this is not

This brief does not claim universal security, formal proof, production readiness, a hosted service, paying customers, or complete autonomous operation. Such claims require separate evidence and will not be inferred from a diagram, code presence, or a passing unit-test run.

## Proposed next milestones

1. Review and merge the bounded kernel only after all required checks and code review pass.
2. Review and merge the SQLite compare-and-swap candidate only after all checks and crash-recovery tests pass.
3. Add real signature verification, pinned trust roots, freshness and revocation checks, and independently retrievable verification receipts.
4. Integrate the admission boundary with VX and ARC-X and test protected write paths for bypasses.
5. Publish a pinned reproducible demo with accepted, rejected, and unknown/quarantined outcomes.

**Working principle:** every public engineering claim must point to a current artifact, a reproducible test, or a clearly labelled proposal.
