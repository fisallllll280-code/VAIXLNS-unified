# VAIXLNS Deep Integration Audit — 2026-09-25

## Executive finding

The federation contains a real executable vertical slice, plus several canonical specification/build surfaces. The correct integration strategy is **federated composition with evidence states**, not blind source merging.

## Executable evidence currently present in `VAIXLNS-unified`

- Identity service and permission/capability primitives.
- Sovereign constitution model with security, execution, governance, data, and determinism rule sets.
- Append-only event ledger with chained event hashes and Merkle-root verification.
- VX runtime that captures input/output hashes and supports replay checks.
- Explicit state machine with boot/initialization/check/ready/active/degraded/recovery/safe-mode lifecycle.
- Deterministic-boundary component for captured time/random/I/O inputs.
- Existing replay tests and GitHub Actions verification workflow.

## Federation surfaces

| Repository | Role | Evidence state | Integration treatment |
|---|---|---|---|
| `VAIXLNS` | canonical architecture, registry, recovery, innovation | CANONICAL | source of canonical meaning |
| `VAIXLNS-unified` | executable integration surface | PARTIAL | current boot/runtime projection |
| `vaixlns-core` | constitutional/core vertical-slice specification | SPECIFIED / RECONCILE CLAIMS | do not claim source execution from current tree |
| `vaixlns-csd-kernel` | CSD root ontology / DSL | SPECIFIED | contract input to future compiler |
| `VX-runtime` | runtime contracts and invariants | SPECIFIED | contract boundary for runtime implementation |
| `VX50_COMPLETE_BUILD` | VX50 build surface | INCOMPLETE | recovery/build source |
| `VAIXLNS-Intent-to-Reality` | intent-to-reality boundary | INCOMPLETE | future pipeline adapter |
| `VAIXLNS-Naming-Constitution-v1.0` | naming / identity support | SPECIFIED | constitutional support |
| `VAIXLNS_OPERATIONAL_ASSURANCE.md` | assurance artifact | SPECIFIED | assurance evidence |
| `VAIXLNS-` | historical variant | QUARANTINED | no automatic promotion |
| `NEXENT` | discovery / architecture research | DISCOVERY | proposal/research boundary |
| `VX_EXECUTION_BUILD_CONTRACT_V0_1.yaml` | execution contract | CONTRACT | contract reference |

## Critical reconciliation

Several READMEs describe capabilities as implemented, while the current repository trees expose only documentation/specification for those claims.

Example: `vaixlns-core` currently exposes `README.md`, `ARCHITECTURE.md`, and `docs/`; no executable `vx/`, `vir/`, `verifier/`, `governance/`, or API source tree is present in the current GitHub tree observed on 2026-09-25.

Therefore:
- README claims are preserved as source assertions.
- They are not promoted to VERIFIED runtime evidence.
- The canonical registry records the discrepancy for reconciliation.

## Current integrated boot path

```
VAIXLNS Federation Registry
        |
        v
Identity
        |
        v
Constitution
        |
        v
Lifecycle State Machine
        |
        v
Governed VX Adapter
        |
        v
VX Execution
        |
        v
Replay
        |
        v
Event Ledger
        |
        v
Integrity Verification
```

## Current operational result

The new smoke runner is designed to return:

- `FAILED` when the executable vertical slice fails.
- `PARTIAL` when the executable slice passes but the full federation still contains specification/incomplete surfaces.

This is intentional. A passing smoke test is evidence for the implemented vertical slice, not proof that all VAIXLNS systems are production-complete.

## Next integration boundary

The next safe promotion target is to turn the following declarations into executable contracts, one family at a time:

1. CSD root DSL parser + ontology validator.
2. V-IR / contract / capability model.
3. Governance/policy layer.
4. Evidence + proof layer.
5. Intent-to-Reality orchestration.
6. Knowledge/VV adapters.
7. XV intelligence gateway and evolution proposals.
8. Distributed execution and recovery.

Each promotion must add code + tests + reproducible CI evidence before its state becomes VERIFIED.
