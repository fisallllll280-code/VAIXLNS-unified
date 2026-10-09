# Ω Research-to-Engineering Decision Fabric V1

**Status:** PROPOSED / IMPLEMENTATION-BOUND  
**Canonical authority:** \`VAIXLNS/project.genome::v1.0.0\`  
**Integration target:** \`Ω.000 → NEXENT discovery → research/investigation agents → engineering decision packet → VX sandbox/replay → innovation control → explicit governance admission\`

## 1. Purpose

Turn research from disconnected search results into a traceable engineering decision. The fabric is an evidence-collection and decision-preparation boundary, not an authority to canonize its own output.

## 2. Non-negotiable invariants

1. No source, claim, or test without a traceable identity and provenance.
2. A missing search result is not evidence of absence; a missing counterexample is not proof of correctness.
3. Exact and likely overlaps trigger lineage review, not silent renaming or deletion.
4. Supporting and refuting evidence are both retained. An unresolved contradiction blocks the affected decision.
5. Search/reasoning agents may discover, classify, compare, propose, and falsify. They may not self-authorize, self-promote, or change canonical policy.
6. \`READY_FOR_ENGINEERING_REVIEW\` is not \`IMPLEMENTED\`, \`VERIFIED\`, \`CANONICAL\`, or \`RUNNING\`.
7. Novelty is never asserted while the relevant historical catalog is known to be incomplete.
8. A canonical promotion must separately pass the repository's innovation proof gate and receive explicit authority.

## 3. Agent roles

| Agent | Responsibility | Required output |
|---|---|---|
| INV-RESEARCH-01 Source Coverage | Run complementary search lanes and report incomplete sources/providers | query plan, coverage findings, failed lanes |
| INV-RESEARCH-02 Novelty & Lineage | Compare titles, aliases, summaries and historical IDs; detect possible reuse | candidate matches, lineage review tasks, novelty state |
| INV-RESEARCH-03 Claim Adversary | Link claims to source excerpts and seek counterevidence | claim/evidence map, contradictions, unknowns |
| INV-RESEARCH-04 Research-to-Engineering | Translate the finding into contracts, invariants, interfaces, failure modes, tests and rollback | missing spec fields and implementation work items |
| INV-RESEARCH-05 Provenance Integrity | Check content digests and URI/revision collisions | source identity checks and provenance blockers |
| Human/constitutional authority | Decide canonical adoption after the independent gate | signed or otherwise auditable authority record |

Provider-specific search workers (GitHub, archive, web, local repository, test/runtime evidence) implement the \`SearchProvider\` contract. Provider failures must remain visible in the result.

## 4. Mandatory investigation lanes

- Historical/archive recovery and exact-name search.
- Cross-repository discovery and dependency/owner search.
- Existing implementation, tests, workflow and runtime-evidence search.
- Novelty, aliases, lineage and likely duplication.
- Counterevidence, attack surface, known failures and alternative explanations.
- Contradiction resolution and unknowns registration.

The query plan is generated deterministically from the mission and candidate. A provider returning no records counts as a completed empty search; a provider exception is an explicit error. Neither may be silently represented as success.

## 5. Engineering-decision contract

Each run produces a stable \`ResearchBundle\` with:
- mission and candidate identity;
- deterministic query IDs and purposes;
- source URIs, revisions, content hashes, evidence classes and source-bound claim excerpts;
- per-provider/per-query outcomes and error records;
- agent reports and blocking findings;
- novelty state and unresolved lineage;
- missing engineering contract fields;
- open questions and next actions;
- deterministic run ID and bundle digest.

Engineering specifications should include the problem, assumptions, invariants, architecture, interfaces, dependencies, security boundary, failure modes, implementation plan, acceptance tests, verification plan, rollback plan, operational metrics, owner, evidence references and known unknowns.

## 6. Decision states

\`BLOCKED\` — integrity failure, unresolved support/refutation contradiction, exact duplicate proposed as a new record, or other hard blocker.

\`NEEDS_INVESTIGATION\` — insufficient source coverage, failed mandatory query lanes, unclassified evidence, possible overlap, incomplete historical catalog, or missing counterevidence.

\`ENGINEERING_GAPS\` — research coverage is adequate, but required contract/specification fields are missing.

\`READY_FOR_ENGINEERING_REVIEW\` — research and declared specification checks pass. This is only a handoff to independent engineering review.

There is no \`VERIFIED\`, \`CANONICAL\`, or \`RUNNING\` output state in this research layer. Those are separate downstream decisions.

## 7. Federation and placement

- **VAIXLNS / Ω.000:** canonical identity, ownership, records, historical lineage, policy and admission boundary.
- **NEXENT:** discovery, research, synthesis and candidate generation; discoveries remain non-canonical until admitted.
- **VLNS:** semantic/model activation boundary; repository identity and live integration must be verified before assuming operational connectivity.
- **VX:** isolated candidate execution, simulation, deterministic replay, failure containment and postcondition verification.
- **Ω Innovation Control:** novelty screening, falsification, verifier diversity, proof freshness, replay and causal-impact checks before admission.
- **Ω-Pattern Foundry:** candidate pattern generation, adversarial testing, provenance and packaging.
- **Event/evidence ledger:** preserve search decisions, outcomes, failures, changes, rejected candidates and approval history.

Adapters and repository mappings are integration contracts. Documentation describing a connection is not proof of a live connection.

## 8. Proposed flow

\`\`\`text
Mission
  → Query Plan
  → Source Search / Archive Recovery
  → Content Identity + Provenance
  → Claim Atomization
  → Support / Counterevidence / Contradiction Analysis
  → Novelty + Historical Lineage Screen
  → Engineering Contract Completeness
  → Research Decision Bundle
  → VX isolated simulation / tests / replay
  → Innovation Control proof gate
  → Explicit authority decision
  → Ω.000 canonical record + event ledger
\`\`\`

## 9. Acceptance criteria

- A source hash mismatch is rejected.
- Provider errors and missing query lanes stay visible.
- Same URI/revision with different content is flagged as a provenance conflict.
- Supporting and refuting evidence for the same claim blocks readiness until adjudicated.
- Incomplete historical coverage never yields a claim of proven novelty.
- An exact catalog match blocks creation of a second independent innovation record.
- Missing engineering fields produce explicit gaps rather than fabricated completion.
- Identical request/corpus inputs produce the same run ID and decision bundle.
- Research output cannot promote itself to canonical authority.

## 10. Current limits

The included package defines the orchestration and provider interface; deployment-grade adapters to live GitHub, external web search, historical archives, model services and runtime evidence remain separate integrations. The system must report an unavailable adapter instead of pretending research was performed. The historical \`0001–2750\` atomic catalog remains incomplete until every original row is exposed and reconciled.

## 11. Implementation plan

1. Add provider adapters with scoped credentials and read-only defaults.
2. Connect source records to \`project.genome\`, \`Ω.000\` and the atomic-system-record schema.
3. Add a versioned decision-record schema and append-only event evidence.
4. Connect simulation and replay evidence from VX without granting research agents execution authority.
5. Exercise every failure and refusal path in CI before enabling any production admission flow.
