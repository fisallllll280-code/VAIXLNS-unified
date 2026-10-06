# VAIXLNS Research-Before-Build Gate V1

## Rule

No new project, subsystem, integration, architectural promotion, or major refactor is eligible for implementation until its research packet is complete.

## Research packet

1. Source inventory and source hashes.
2. Source lineage and version/duplication analysis.
3. Canonical terminology and semantic normalization.
4. Existing-project and existing-capability match analysis.
5. External standards and implementation-pattern research.
6. Contradiction and uncertainty register.
7. Threat and failure model.
8. State-transition model.
9. Authority boundary.
10. Evidence plan.
11. Verification plan.
12. Replay/reconstruction plan.
13. Causal/blast-radius analysis.
14. Acceptance tests.
15. External-infrastructure dependencies.
16. Explicit unknowns that remain unresolved.

## Evidence classes

SOURCE = historical or documentary evidence.
CODE = implementation evidence.
TEST = executable test evidence.
RUNTIME = observed execution evidence.
INDEPENDENT = verification independent of the implementation path.
PROOF = durable proof artifact.
AUTHORITY = explicit admission decision.
EXTERNAL = evidence dependent on a real external system.

No lower class may be silently promoted into a stronger class.

## Research verdicts

UNKNOWN -> SOURCE_SUPPORTED -> CODE_SUPPORTED -> TESTED -> RUNTIME_VERIFIED -> INDEPENDENTLY_VERIFIED -> PROVEN -> ADMITTED -> CANONICAL

## Contradiction handling

Contradictions are first-class research objects. Do not silently reconcile two sources. Preserve both source claims, record the contradiction, identify the authority required to resolve it, and create a resolution experiment or explicit decision record.

## Project-family deduplication

A new project name is not sufficient reason to create a new system.

candidate capability -> existing capability scan -> duplicate scan -> inheritance/reuse analysis -> integration choice -> implementation

## Research-to-build gate

COLLECT -> HASH -> CLASSIFY -> NORMALIZE -> LINK -> DEDUPLICATE -> EXTERNAL RESEARCH -> CONTRADICTION ANALYSIS -> FAILURE MODEL -> SEMANTIC TRANSITION MODEL -> ACCEPTANCE PLAN -> AUTHORITY REVIEW -> BUILD

## Current research scope

The current workspace contains 58 uploaded text sources. Duplicate-content groups were detected and remain linked rather than treated as independent discoveries.

The accessible GitHub account contains multiple VAIXLNS, VX and NEXENT repositories plus adjacent systems. Repository autonomy is preserved; federation records identity, role, lineage, dependencies and integration status instead of flattening all code into one repository.

The canonical executable integration surface is VAIXLNS-unified. Its backlog is evidence-driven and distinguishes implementation from live external infrastructure.

## Non-negotiable closure rule

IMPLEMENTED != RUNNING != VERIFIED != PROVEN != ADMITTED

A project moves upward only by generating the next evidence class.
