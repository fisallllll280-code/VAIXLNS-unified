# VAIXLNS Repository Federation Inventory v1

**Status:** public-scope inventory and proposed federation plan; not a claim that repositories have been merged or all source trees inspected.
**Snapshot:** 2026-10-09.
**Purpose:** create a traceable, non-destructive federation view for public VAIXLNS-related repositories.

## 1. Non-loss federation rules

1. Do not delete, rename, archive, or overwrite source repositories during inventory or federation.
2. Preserve source repository, branch, commit SHA, path, license, ownership, and provenance for every imported artifact.
3. Inspect before merging; repository names alone do not establish equivalence or implementation status.
4. Check licenses and redistribution conditions before copying code into a distributed bundle.
5. Keep canonical governance, NEXENT discovery/design, VX execution, verification/proof, and source repositories as distinct roles until evidence supports tighter coupling.
6. Never copy secrets, tokens, credentials, private keys, or environment files into a federation bundle.
7. Visibility through GitHub integration is not evidence that a repository has been fully inspected, built, or tested.
8. Make imports reversible and record exact upstream commit and source path.

## 2. Public VAIXLNS-related repositories identified

These public repositories are first-pass candidates for inspection, not a declaration that each is canonical or safe to merge.

| Repository | Default branch | GitHub-reported size (KB) | Initial role hypothesis |
|---|---|---:|---|
| [VAIXLNS](https://github.com/fisallllll280-code/VAIXLNS) | main | 816 | Canonical architecture, registry, recovery and governance |
| [VAIXLNS-unified](https://github.com/fisallllll280-code/VAIXLNS-unified) | main | 497 | Integrated executable/runtime surface |
| [NEXENT](https://github.com/fisallllll280-code/NEXENT) | main | 378 | Discovery, research, architecture search |
| [vaixlns-nexent-vx](https://github.com/fisallllll280-code/vaixlns-nexent-vx) | main | 102 | Combined NEXENT/VX integration candidate |
| [VX-runtime](https://github.com/fisallllll280-code/VX-runtime) | main | 49 | Runtime / execution contract candidate |
| [vaixlns-core](https://github.com/fisallllll280-code/vaixlns-core) | main | 31 | Focused core vertical slice candidate |
| [vaixlns-csd-kernel](https://github.com/fisallllll280-code/vaixlns-csd-kernel) | main | 23 | Specialized CSD kernel / replay candidate |
| [vx-agents-fabric](https://github.com/fisallllll280-code/vx-agents-fabric) | main | 231 | Specialist-agent coordination fabric candidate |
| [vx-agents-system](https://github.com/fisallllll280-code/vx-agents-system) | main | 0 | Agent-system repository; inspect for empty/template status |

## 3. Account-level inventory scope

The connected GitHub account returned **51 repositories visible to the authenticated account** at this snapshot. This public document enumerates **9 public VAIXLNS-related candidates**. Private-repository names and metadata are deliberately not published here; they require a separate private inventory. The remaining public repositories were not classified as VAIXLNS components in this pass. That is not proof they contain no reusable assets.

## 4. Target federation layout (proposed, not implemented)

```text
VAIXLNS FEDERATION
├── Canonical governance and identity
├── NEXENT discovery / research / architecture search
├── VX execution and runtime contracts
├── Agent coordination fabric
├── Verification / evidence / proof
├── Domain-specific capabilities
├── Integration surface (VAIXLNS-unified)
└── Historical sources and variants (preserve lineage)
```

## 5. Required stages

### Stage A — read-only repository X-ray
For every candidate, capture repository URL, default branch, HEAD SHA, file tree, language breakdown, manifests, tests, CI workflows, license, security-sensitive paths, and last update. Do not modify source repositories.

### Stage B — semantic mapping
Map every discovered artifact to a stable federation ID and record source repository + commit SHA + path, artifact type, canonical role, dependencies, duplicate candidates, implementation state, license status, evidence links, and unresolved questions.

Use explicit states: `DISCOVERED`, `SPECIFIED`, `IMPLEMENTED`, `TESTED`, `VERIFIED_FOR_SCOPE`. Do not infer implementation from README claims alone.

### Stage C — compatibility and duplicate analysis
Compare source and contracts before deciding whether components are duplicates, versions, adapters, or independent systems. Preserve historical versions and alias mappings.

### Stage D — reversible integration
Import only approved, licensed, tested components into a dedicated integration branch or subdirectory. Prefer explicit adapters and versioned packages over flattening all repositories into one directory. Never force-push or auto-merge into `main`.

### Stage E — proof gates
Require reproducible build/tests, dependency/license review, secret scan, provenance check, integration tests, rollback plan, and governance approval before promoting any imported component.

## 6. Current status

- Account-visible repository metadata inventory: completed for 51 repositories.
- Public VAIXLNS-related candidates listed here: 9.
- Private repository inventory: intentionally not included in this public document.
- Full source inspection: not completed.
- Source-code imports/merges: not performed by this document.
- All-repository tests/CI: not run.
- Canonical federation runtime: not claimed to exist yet.

This inventory is the public, non-destructive starting point for repository federation. The canonical source of governance and recovery remains the VAIXLNS repository's existing federation indexes.
