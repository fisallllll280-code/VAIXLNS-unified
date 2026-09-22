# VAIXLNS Verification Manifest v1

This manifest separates architectural claims from executable evidence.

| Area | Contract | Evidence required | Status |
|---|---|---|---|
| Identity | stable identity boundary | executable tests | SPECIFIED |
| Ledger | append-only authoritative history | persistence + replay tests | SPECIFIED |
| Governance | policy before execution | negative/positive tests | SPECIFIED |
| Determinism | replay fidelity | deterministic golden execution | SPECIFIED |
| Verification | failed work cannot become verified | invariant tests | SPECIFIED |
| Recovery | restart without semantic policy | recovery tests | SPECIFIED |
| Knowledge | updates are provenance-linked | provenance tests | SPECIFIED |

## Rule

A row may move from SPECIFIED to IMPLEMENTED only when code and reproducible tests exist in this repository. Documentation alone is not evidence of implementation.

## Integration boundary

NEXENT may discover and propose architecture changes. VAIXLNS-unified remains the controlled execution/verification surface. Proposal is not adoption.
