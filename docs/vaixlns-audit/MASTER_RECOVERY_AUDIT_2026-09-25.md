# VAIXLNS System Recovery Audit — 2026-09-25

## Purpose

This document is the recovery/canonicalization layer for VAIXLNS/VX. It separates:
- VERIFIED: executable repository evidence was inspected.
- SPECIFIED: documented architecture/specification exists but executable proof was not found in the inspected repository.
- PARTIAL: a real fragment exists, but the claimed subsystem is incomplete.
- MISSING: the concept is referenced/required but no implementation was found in the inspected target.
- CONFLICT: documentation claims exceed the repository evidence or multiple repositories disagree.
- PROPOSAL: required upgrade not yet implemented.

## Executive finding

The connected GitHub account contains several VAIXLNS/VX fragments, not one canonical implementation. The most substantive executable vertical slice is `VAIXLNS-unified`; `vaixlns-core`, `VX-runtime`, `VAIXLNS-Intent-to-Reality`, `VX50_COMPLETE_BUILD`, and `vaixlns-csd-kernel` are currently small documentation/specification or foundation repositories. A separate public VAIXLNS repository contains additional canonical-event/state/replay/intelligence artifacts, and a public VAIXLNS Builder repository contains a substantially richer parser → AST → IR → graph → planner → generator → evidence → Lean pipeline. These are recovery sources, not automatically authoritative.

## 1. Current developed state

### A. VAIXLNS-unified — VERIFIED/PARTIAL

Verified repository structure:
- `core/identity.py`
- `core/ledger.py`
- `core/sovereign_constitution.py`
- `execution/vx_runtime.py`
- `execution/determinism.py`
- `execution/state_machine.py`
- `execution/worker.py`
- `tests/test_vx_runtime_replay.py`
- `.github/workflows/verification.yml`

Verified behavior:
- Append-only event ledger with hash chaining and Merkle-root calculation.
- VX execution envelope/result model.
- Captured execution inputs used for replay.
- Replay compares output hashes for determinism.
- State-machine lifecycle including READY, ACTIVE, DEGRADED, RECOVERING and SAFE_MODE.
- CI verification workflow and replay/determinism regression work are present in git history.

Important gap:
- The README describes governance, capability registry, CVL, intelligence, knowledge, evolution, recovery and other layers, but the current tree does not contain the corresponding `governance/` implementation directory. Therefore those claims are not accepted as VERIFIED for this repository.

### B. vaixlns-core — CONFLICT / SPECIFIED

README claims a complete tested sovereign loop:
`INTENT → V-IR → VERIFY → PROOF → CAPABILITY → LEASE → VX → EVIDENCE → LEDGER → REPLAY → IDENTICAL STATE`.

Current repository tree inspected at `main` contains primarily:
- README
- ARCHITECTURE.md
- docs/manuals

The executable tree required to substantiate the README claim was not present in the inspected main tree. Status: CONFLICT until executable evidence is restored or the claim is narrowed.

### C. VX-runtime — SPECIFIED

The repository defines the integrated operating model and explicit runtime invariants, but its current tree is README + manuals. The README itself states that runtime implementation must be added behind the contracts and verified by executable tests. Status: SPECIFIED, not IMPLEMENTED.

### D. VAIXLNS-Intent-to-Reality — PARTIAL

Current tree is primarily documentation:
- INTENT_PIPELINE_V1
- activation/publication manuals

Recent history includes an implementation-foundation commit and merged development branch, but the current main tree inspected here does not expose the full implementation. Status: PARTIAL.

### E. VX50_COMPLETE_BUILD — PARTIAL

Current main tree contains publication/activation/implementation-foundation documentation. Recent history includes an implementation-foundation merge. The inspected tree does not establish a complete VX50 implementation. Status: PARTIAL.

### F. vaixlns-csd-kernel — SPECIFIED/PARTIAL

Current tree contains:
- `VAIXLNS_ROOT.lns`
- documentation/manuals

This is valuable constitutional/genesis evidence, but not a complete executable CSD kernel in the current tree.

## 2. Recovered external VAIXLNS evidence

### Public VAIXLNS/VAIXLNS repository — RECOVERY SOURCE

The inspected public repository contains real artifacts including:
- `docs/MASTER_SPECIFICATION.md`
- `canonical_event.py`
- `canonical_state.py`
- `replay_engine.py`
- `intelligence_fabric.py`
- `transition.py`
- `vx.py`
- tests

This is strong evidence that concepts such as canonical event/state, replay, intelligence fabric and VX implementation existed in a concrete form. It must be reconciled into the user's canonical repository rather than copied blindly.

### Public VAIXLNS Builder v0.1 — RECOVERY SOURCE

The inspected builder contains:
- lexer
- parser
- AST
- IR
- graph
- planner
- generator
- evidence
- verification/Lean integration
- fixtures
- tests
- CI
- Genesis/canonical-state reports

Its audit reports demonstrate a real parser/AST/IR/graph/hash/Lean/deterministic-generation path, while also exposing test-coverage limitations and evidence-model limitations. It is a recovery source for missing compiler/genesis functionality, not a substitute for the VAIXLNS canonical source of truth.

## 3. What is developed vs developing vs lost

### DEVELOPED / RECOVERABLE

1. VX execution/event ledger vertical slice.
2. Deterministic replay boundary concept.
3. State-machine lifecycle.
4. Sovereign constitution model.
5. Identity and event-ledger foundations.
6. Canonical event/state/replay artifacts in the public VAIXLNS repository.
7. LNS/genesis root artifact in `vaixlns-csd-kernel`.
8. Parser → AST → IR → graph → planner → generator pipeline in the public Builder repository.
9. Lean proof integration in the public Builder repository.
10. Evidence/finality model in the public Builder repository.

### DEVELOPING / PARTIAL

1. Governance/capability/policy layer.
2. CVL formal verification integration.
3. V-IR/intent-to-runtime path.
4. VX50 complete build.
5. CSD kernel execution.
6. Intelligence gateway/fabric.
7. Knowledge/causal/pattern layers.
8. Evolution engine.
9. Operational readiness/OIF.
10. Cross-runtime conformance.

### LOST / NOT PRESENT IN THE CURRENT CANONICAL TARGET

These are not declared permanently deleted; they are classified as LOST/UNRESTORED because no authoritative implementation/spec was found in the current target tree:
1. Canonical Semantic Engine (CSE).
2. Deterministic Causal Execution Graph (DCEG).
3. Evidence DNA (eDNA).
4. Adversarial Mutation Framework (AMF).
5. Cross-Runtime Equivalence Matrix (CREM).
6. Formal Proof Orchestrator (FPO).
7. Operational Integrity Fabric (OIF).
8. Master Capability Indexer (MCI).
9. Semantic Fingerprint Canonicalizer (SFC).
10. Replay Determinism Verifier (RDV).
11. Full Ω Master Index / 0001–2750 Recovery Canon.
12. Full VV knowledge/discovery fabric.
13. Full XV intelligence/planning/evolution layer.
14. SUF / Intelligence Gateway / Collective Intelligence integration.
15. Full VSG/System Genome implementation.

These items are RECOVERY CANDIDATES, not invented from zero: several are represented in prior VAIXLNS design history and adjacent repositories, but their canonical executable integration is absent from the inspected target.

## 4. Critical architectural conflicts

### Conflict 1 — README completeness vs repository evidence

A subsystem MUST NOT be labelled IMPLEMENTED merely because a README describes it. Implementation status requires executable code plus reproducible evidence.

### Conflict 2 — Multiple repositories act as de facto sources of truth

The project currently has multiple centers:
- VAIXLNS-unified
- vaixlns-core
- VX-runtime
- VAIXLNS-Intent-to-Reality
- VX50_COMPLETE_BUILD
- vaixlns-csd-kernel
- public VAIXLNS repository
- public VAIXLNS Builder

This creates canonical drift.

### Conflict 3 — Evidence is not yet one chain

The project has event hashes, replay, proofs, and evidence concepts, but no single canonical Evidence DNA + semantic fingerprint + conformance chain joins:
SPEC → SIR → DCEG → EXECUTION → EVIDENCE → PROOF → REPLAY → OIF.

### Conflict 4 — Determinism is not yet semantic determinism

Current VX replay verifies output equality for captured inputs. That is useful but narrower than proving canonical semantic equivalence across runtimes. CSE/SFC/CREM/RDV are required for that stronger claim.

## 5. Canonical recovery rule

No recovered artifact becomes canonical by age, repository name, README claim, or apparent sophistication.

Promotion rule:

`RECOVERY → RECONCILE → SPECIFY → IMPLEMENT → TEST → VERIFY → EVIDENCE → CANON`

Every promoted artifact receives:
- Canonical ID
- source repository
- source commit
- source path
- status
- dependencies
- invariant coverage
- tests
- evidence fingerprint
- promotion decision

## 6. Immediate upgrade target

The canonical integration target is `VAIXLNS-unified` until a dedicated `vlns-vx-conformance` repository becomes available. No repository named `vlns-vx-conformance` was found in the connected GitHub installations during this audit.

The first upgrade spine is:

`Constitution → Genome → SIR/CSE → DCEG → VX → Evidence/eDNA → SFC → RDV → CREM → FPO → OIF → MCI → Nexus`

This does not replace VV/XV/SUF; it provides the conformance/assurance spine on which they can be attached.

## 7. Non-negotiable status policy

- VERIFIED = executable evidence inspected.
- SPECIFIED = specification exists.
- PARTIAL = executable fragment exists but closure is incomplete.
- MISSING = required but not found.
- CONFLICT = claim/evidence disagreement.
- PROPOSAL = planned upgrade.

No other status is canonical.
