# VAIXLNS Repository Federation Inventory v1

**Status:** INVENTORY / PROPOSED FEDERATION PLAN — not a claim that repositories have been merged or that every codebase has been inspected.
**Inventory source:** GitHub repositories visible to the connected account on 2026-10-09.
**Purpose:** Establish one traceable catalog for VAIXLNS-related repositories before any code consolidation.

## 1. Non-loss federation rules

1. Do not delete, rename, archive, or overwrite source repositories as part of inventory or federation.
2. Preserve source repository, branch, commit SHA, path, license, ownership, and provenance for every imported artifact.
3. Inventory and inspect before merging; repository names alone do not establish equivalence or implementation status.
4. Do not copy third-party code into a consolidated distribution until its license and redistribution conditions are checked.
5. Keep canonical governance, NEXENT discovery/design, VX execution, verification/proof, and source repositories as distinct roles until evidence supports a tighter coupling.
6. No secrets, tokens, credentials, private keys, or environment files may be copied into the federation bundle.
7. A repository being visible to GitHub integration is not evidence that its contents have been fully cloned, tested, or integrated.
8. All imports must be reversible and record the exact upstream commit and source path.

## 2. First-pass VAIXLNS-related repository inventory

The following entries matched VAIXLNS/NEXENT/VX/kernel/agent/fabric/assurance naming in the accessible account inventory. They are **candidates for inspection**, not a declaration that each is canonical or safe to merge.

| Repository | Default branch | Visibility | Size (GitHub-reported KB) | Initial role hypothesis |
|---|---|---:|---:|---|
| [VAIXLNS](https://github.com/fisallllll280-code/VAIXLNS) | main | public | 816 | Canonical / governance / source of architectural rules |
| [VAIXLNS-unified](https://github.com/fisallllll280-code/VAIXLNS-unified) | main | public | 497 | Integration / unified runtime candidate |
| [NEXENT](https://github.com/fisallllll280-code/NEXENT) | main | public | 378 | Discovery, research, architecture search |
| [vaixlns-nexent-vx](https://github.com/fisallllll280-code/vaixlns-nexent-vx) | main | public | 102 | Combined NEXENT/VX integration candidate |
| [VX-runtime](https://github.com/fisallllll280-code/VX-runtime) | main | public | 49 | Runtime / execution candidate |
| [vaixlns-core](https://github.com/fisallllll280-code/vaixlns-core) | main | public | 31 | Core vertical slice candidate |
| [vaixlns-csd-kernel](https://github.com/fisallllll280-code/vaixlns-csd-kernel) | main | public | 23 | CSD kernel / replay / cryptographic execution candidate |
| [vx-agents-fabric](https://github.com/fisallllll280-code/vx-agents-fabric) | main | public | 231 | Agent execution fabric candidate |
| [vx-agents-system](https://github.com/fisallllll280-code/vx-agents-system) | main | public | 0 | Agent-system repository; inspect for empty/template status |
| [VX50_COMPLETE_BUILD](https://github.com/fisallllll280-code/VX50_COMPLETE_BUILD) | main | private | 169 | VX build artifacts / implementation candidate |
| [-VAIXLNS](https://github.com/fisallllll280-code/-VAIXLNS) | main | private | 150 | Historical/variant VAIXLNS source; preserve lineage |
| [VAIXLNS-](https://github.com/fisallllll280-code/VAIXLNS-) | main | private | 140 | Historical/variant VAIXLNS source; preserve lineage |
| [NAXLNS](https://github.com/fisallllll280-code/NAXLNS) | main | private | 35 | Related project; relationship to VAIXLNS requires inspection |
| [VAIXLNS-Intent-to-Reality](https://github.com/fisallllll280-code/VAIXLNS-Intent-to-Reality) | main | private | 16 | Intent-to-reality architecture specification |
| [VAIXLNS_OPERATIONAL_ASSURANCE.md](https://github.com/fisallllll280-code/VAIXLNS_OPERATIONAL_ASSURANCE.md) | VAIXLNS | private | 14 | Operational assurance specification |
| [VAIXLNS-Naming-Constitution-v1.0](https://github.com/fisallllll280-code/VAIXLNS-Naming-Constitution-v1.0) | main | private | 2 | Naming and identity rules |
| [VX_EXECUTION_BUILD_CONTRACT_V0_1.yaml](https://github.com/fisallllll280-code/VX_EXECUTION_BUILD_CONTRACT_V0_1.yaml) | main | private | 1 | Execution contract artifact |
| [tools-vaixlns-meta-core-v0.3.ts](https://github.com/fisallllll280-code/tools-vaixlns-meta-core-v0.3.ts) | main | private | 0 | Meta-core tool artifact; inspect repository structure |
| [vx-financial-kernel](https://github.com/fisallllll280-code/vx-financial-kernel) | main | private | 5 | Financial kernel candidate; isolate high-risk financial operations |

## 3. Scope and completeness

The connected account inventory returned **51 repositories total**. The table above contains **19 first-pass candidates** based on project-related names. The other repositories were not classified as VAIXLNS components in this pass; this is not proof that they contain no reusable assets.

Private repositories are listed because they are visible to the connected GitHub account. Access visibility does not mean they have been copied or inspected.

## 4. Canonical federation layout (target, not yet implemented)

```text
VAIXLNS FEDERATION ROOT
├── 00-governance
│   ├── naming-constitution
│   ├── canonical-rules
│   └── admission-policies
├── 10-canonical-core
│   ├── vaixlns-core
│   └── intent-to-reality-spec
├── 20-discovery
│   └── NEXENT
├── 30-execution
│   ├── VX-runtime
│   ├── CSD-kernel
│   └── execution-contracts
├── 40-agent-fabric
│   ├── vx-agents-fabric
│   └── vx-agents-system
├── 50-assurance-proof
│   └── operational-assurance
├── 60-domain-kernels
│   └── financial-kernel (isolated, separately authorized)
├── 70-integration
│   ├── VAIXLNS-unified
│   └── vaixlns-nexent-vx
└── 90-legacy-and-variants
    ├── -VAIXLNS
    ├── VAIXLNS-
    └── all source snapshots and lineage records
```

## 5. Required next steps

### Stage A — read-only repository X-ray
For each candidate, capture: repository URL, default branch, current HEAD SHA, tree inventory, language breakdown, manifests, tests, CI workflows, license, security-sensitive paths, and last update. Do not modify source repositories.

### Stage B — semantic mapping
Map each discovered artifact to a stable federation ID and record:
- source repository + commit SHA + path
- artifact type and canonical role
- imports/dependencies and duplicate candidates
- implementation state: `DISCOVERED`, `SPECIFIED`, `IMPLEMENTED`, `TESTED`, `VERIFIED_FOR_SCOPE`
- license and redistribution status
- evidence links and unresolved questions

### Stage C — compatibility and duplicate analysis
Compare code and contracts before deciding whether components are duplicates, versions, adapters, or independent systems. Keep historical versions and alias mappings.

### Stage D — reversible integration
Import only approved, licensed, tested components into a dedicated integration branch or subdirectory. Prefer explicit adapters and versioned packages over flattening all repositories into one directory. Never force-push or merge automatically into `main`.

### Stage E — proof gates
Require reproducible build/tests, dependency/license review, secret scan, provenance check, integration tests, rollback plan, and governance approval before promoting any imported component.

## 6. Current status

- **Inventory pass:** completed for account-visible repository metadata.
- **Full source inspection:** not completed.
- **Repository code imports/merges:** not performed by this document.
- **Tests/CI of all repositories:** not run.
- **Canonical federation runtime:** not claimed to exist yet.

This inventory is the non-destructive starting point for gathering the repositories into one traceable VAIXLNS federation without erasing source history.
