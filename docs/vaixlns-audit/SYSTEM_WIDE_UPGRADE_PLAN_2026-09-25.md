# VAIXLNS System-Wide Upgrade Plan — Recovery to Canon

## Objective

Recover missing VAIXLNS concepts, prevent architectural drift, and create one auditable execution/conformance spine without deleting existing work.

## Upgrade waves

### Wave 1 — Canonical Recovery
- Create Recovery Canon registry.
- Register every repository/artifact with source commit/path.
- Separate ORIGINAL, DERIVED, RECOVERED, PROPOSAL.
- Establish `project.genome` as canonical source-of-truth target.
- Map Ω Master Index and the 0001–2750 capability space.

### Wave 2 — Semantic Spine
Implement:
- CSE
- SFC
- canonical SIR schema
- semantic fingerprint rules
- canonical serialization

Invariant:
same specification + same canonical semantics ⇒ same fingerprint.

### Wave 3 — Causal/Replay Spine
Implement:
- DCEG
- RDV
- replay trace schema
- execution lineage
- temporal/causal edges

Invariant:
replay must reference the original execution boundary and prove equality/divergence explicitly.

### Wave 4 — Evidence/Proof Spine
Implement:
- eDNA
- evidence bundle schema
- FPO adapters for Lean/TLA+/Z3
- proof/evidence lineage
- signed evidence roots

Invariant:
no VERIFIED state without a machine-checkable evidence chain.

### Wave 5 — Cross-Runtime Conformance
Implement:
- CREM
- runtime adapters
- verdict schema
- semantic/replay diff
- conformance vectors

Invariant:
runtime compatibility is semantic, not merely byte/output equality.

### Wave 6 — Operational Assurance
Implement:
- OIF
- readiness state machine
- evidence thresholds
- certification gate
- recovery/safe-mode checks

Invariant:
READY is a proven state, not a configuration value.

### Wave 7 — Nexus / Master Index
Implement:
- MCI
- capability graph
- artifact registry
- dependency graph
- traceability matrix
- canonical links into VV/VX/XV/SUF

Invariant:
every canonical capability resolves to specification, implementation, test, evidence and owner.

## Ten invention integration map

| ID | System | First canonical role | Status |
|---|---|---|---|
| INV-001 | CSE | semantic authority | PROPOSAL |
| INV-002 | DCEG | causal execution authority | PROPOSAL |
| INV-003 | eDNA | evidence lineage | PROPOSAL |
| INV-004 | AMF | adversarial assurance | PROPOSAL |
| INV-005 | CREM | cross-runtime conformance | PROPOSAL |
| INV-006 | FPO | formal proof orchestration | PROPOSAL |
| INV-007 | OIF | operational readiness | PROPOSAL |
| INV-008 | MCI | Nexus capability index | PROPOSAL |
| INV-009 | SFC | semantic fingerprint authority | PROPOSAL |
| INV-010 | RDV | replay determinism authority | PROPOSAL |

## Definition of closure

A subsystem moves from PARTIAL to VERIFIED only when all are present:

1. canonical specification
2. executable implementation
3. deterministic or explicitly bounded semantics
4. tests
5. negative/adversarial tests where applicable
6. evidence artifact
7. replay/conformance evidence where applicable
8. traceability record
9. CI verification
10. source commit recorded in the Recovery Canon

## Forbidden shortcuts

- Do not mark README-only components as implemented.
- Do not merge recovered artifacts without provenance.
- Do not make OIF depend on a human assertion alone.
- Do not equate hash equality with semantic equivalence.
- Do not call a runtime deterministic when external inputs are uncaptured.
- Do not delete older concepts merely because a newer repository has a cleaner name.
