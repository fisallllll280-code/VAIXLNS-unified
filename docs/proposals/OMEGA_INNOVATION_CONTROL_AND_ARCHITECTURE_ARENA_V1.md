# Ω Innovation Control & Architecture Arena — V1 (PROPOSED / EXPERIMENTAL)

Status: PROPOSED. This document is not a canonical innovation registry entry. Promotion is forbidden until executable proof gates pass.

## Objective

Close the remaining gap between NEXENT discovery, VAIXLNS canonicalization, VX execution, verification/proof, and governed adoption.

The design is intentionally stronger than conventional agent orchestration: invention is treated as a controlled experimental process with an explicit ability to kill its own candidates.

## New primitives

### 1. Proof-Before-Promotion Gate (PBPG)

IDEA → HYPOTHESIS → SPEC → SANDBOX → TEST → EVIDENCE → VERIFIED → REPRODUCED → PROVEN → ADMISSIBLE → CANONICAL

The registry may store historical/proposed records at any stage, but CANONICAL is forbidden unless all required proof gates pass.

### 2. Novelty Shield

Compare candidate and existing capability/architecture lineage using stable fingerprints over purpose, capability set, topology, contracts, invariants, execution path, verification path, and memory/lineage behavior.

Outcomes: NOVEL, COMPOSITE_NOVEL, REDUNDANT, UNKNOWN.

UNKNOWN blocks canonical promotion until uncertainty is resolved.

### 3. Counterfactual Architecture Arena

Generate multiple isolated architecture candidates from the same mission and compare them on correctness, reliability, proofability, recovery quality, blast radius, rollback cost, and resource efficiency.

Selection is evidence-driven. A language model cannot be the sole judge.

### 4. Falsification Gate

Every candidate receives explicit attempts to disprove it.

Required attack classes: invariant violation, malformed input, dependency failure, timeout/resource exhaustion, state divergence, replay mismatch, evidence mismatch, recovery failure, policy/authority violation, and adversarial or out-of-distribution cases.

A failed mandatory proof obligation blocks promotion.

### 5. Independent Verification Trio

Promotion requires three logically distinct checks:
1. Deterministic invariant verifier
2. Replay/reproduction verifier
3. Evidence/provenance consistency verifier

The same generative agent that proposed the design must not be the only authority deciding that it passed.

### 6. Evolution Firewall

Before a live architecture change: create an isolated candidate; compute causal blast radius; create rollback/checkpoint state; enumerate affected contracts and capabilities; require constitutional compatibility; and record the exact promotion decision.

No direct mutation of canonical state by an invention agent.

### 7. Unknowns Ledger

Unknowns are first-class records: question, uncertainty type, affected capability/architecture, current evidence, blocked decision, next experiment.

Unknowns cannot silently collapse into true or false.

### 8. Failure Memory

Failures become reusable learning objects: first unrecoverable step, failure class, causal chain, evidence, attempted recovery, counterfactual repair, regression test.

A later architecture must prove that previously known failure modes are either removed or intentionally bounded.

### 9. Evidence-Weighted Innovation Score

After mandatory gates, rank admissible candidates using evidence strength, reproducibility, reliability, proof coverage, novelty value, operational value, blast risk, rollback cost, and unresolved unknowns.

The score ranks admissible candidates; it never overrides a failed mandatory gate.

### 10. Self-Refuting Research Loop

NEXENT asks two symmetric questions:
- How can this design succeed?
- How can I make this design fail?

The second question is a first-class research operation, not an afterthought.

## Integration with existing VAIXLNS

Use existing surfaces rather than duplicating them:

- vx/invention_engine.py → candidate generation
- evolution/architecture_lab.py → gap discovery, candidate design, causal analysis
- proof/ → proof packages and proof state
- evidence/ → evidence bundle/fingerprint
- core/sovereign_constitution.py → immutable constraints
- operations/ → readiness/recovery boundaries
- NEXENT → external discovery/research source
- NEXUS → identity/lineage/dependency relationships

## Acceptance gates

A candidate is not promotion-ready until all of these are true:
- specification is deterministic and versioned
- candidate is isolated
- novelty status is resolved
- mandatory proof obligations are enumerated
- falsification suite has passed
- evidence is fingerprinted
- replay/reproduction succeeds
- independent verification trio succeeds
- blast radius is bounded and recorded
- rollback is proven
- constitutional checks pass
- lineage is complete

## First vertical slice

Build one executable slice:

mission → capability gap → 3 architecture candidates → sandbox scoring → falsification → independent verification → replay → proof package → admissibility decision → optional promotion

The first slice should deliberately include at least one candidate that fails, so the system demonstrates that it can reject an attractive but unsafe or incorrect invention.

## Non-goals

- no claim of formal theorem proving from hashes alone
- no claim that simulation equals physical validation
- no claim that model agreement equals independent verification
- no silent deletion of historical candidates
- no direct self-modification of canonical governance
- no use of external vendor patterns as copied architecture

## Research position

External frontier systems establish strong baselines around agent tooling, sandboxing, containment, evaluation, verification, and multi-agent research. VAIXLNS uses these as comparison inputs, then goes further by making failure, uncertainty, novelty, replay, blast radius, and proof coverage part of the promotion contract itself.

## Strengthening additions

### Verification Diversity Gate
Three verifier outputs are insufficient when all verifiers share the same implementation, model family, algorithm family, or evidence source. The executable gate therefore requires verifier profiles and rejects low structural diversity.

### Proof Freshness Contract
Proof is scoped, not eternal. A proof must carry an evidence fingerprint, dependency fingerprint, execution environment fingerprint, issue epoch and expiry policy. Material dependency or environment changes invalidate the proof.

### Causal Impact Budget
Blast radius is converted from a descriptive graph into a pre-admission budget. A proposed change can be blocked because its weighted criticality, forbidden surfaces, or number of state mutations exceeds policy.

### Deterministic Counterfactual Ranking
The Architecture Arena now supports ranking multiple candidates using deterministic score ordering. The ranking signal cannot override mandatory falsification, verification, replay, freshness or impact gates.
