# RIRF + Finality Gate — Implementation Boundary V1

## Ownership

- `VAIXLNS`: canonical policy, Finality Gate specification, certificate schema.
- `NEXENT`: repository discovery, Repository Genome, anomaly classification, Semantic Impact Cone, repair-candidate planning.
- `VAIXLNS-unified`: executable integration, governed mutation coordination, evidence plumbing, finality evaluation.
- `VX-runtime`: bounded execution boundary for admitted mutations.

## Required mutation lifecycle

REQUEST → SNAPSHOT → X-RAY → GENOME/NEXUS → ANOMALY → IMPACT → DECISION → ISOLATED MUTATION → BUILD → TEST → SECURITY → REPLAY → EVIDENCE → INDEPENDENT VERIFICATION → GOVERNANCE → FINALITY → MERGE

## Non-negotiable boundaries

1. No direct mutation of the default branch from an AI proposal.
2. A repair candidate is not an approved mutation.
3. RIRF cannot grant authority.
4. Finality Gate cannot grant repository repair authority.
5. Proof does not equal authority.
6. Material changes can invalidate a previous finality certificate.

## Reference implementation

`closure/finality_gate.py` implements only the evaluation and invalidation primitives. It does not call GitHub, merge branches, sign releases, or grant authority.

## Evidence

Each finality decision must point to an evidence root and proof root. The final decision is scope-bound to the subject version, environment, capabilities, dependencies, and policies.

## Verification

The module is covered by `tests/test_finality_gate.py`. The repository verification workflow must execute the complete test suite before promotion.
