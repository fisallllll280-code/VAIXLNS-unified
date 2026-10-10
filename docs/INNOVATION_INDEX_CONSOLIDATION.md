# VAIXLNS — Consolidated Innovation Index Fabric

## Scope

This consolidates the existing index families and registries as views over **one canonical Nexus identity and lineage substrate**. It does not replace or discard historical indexes. The implementation separates source mentions, derived decomposition labels, proposed innovations, test implementations and production claims.

## Current inventory

- Uploaded archive inventory: **69 text sources**, 786,341 bytes.
- Catalogued index views and registries/graphs: **48**.
- Named innovation/architecture records compiled: **59**.
- Source-local atomic decomposition headings extracted: **570**, labelled A-001 through A-570 from `قسم · التفكيك الهرمي لـ VAIXLNS.txt`.
- Historical numeric registry expected: `0001–2750`. Its complete element-by-element ID/name mapping remains **UNPROVEN**.

**Important:** A-001..A-570 are labels introduced by the decomposition source. They are not mapped to the original numeric registry. No missing legacy IDs have been fabricated.

## Canonical arrangement

```text
ARCHIVE SOURCES + OLD INDEXES
           │
           ▼
Source Inventory (SHA-256 + Source ID)
           │
           ▼
Atomic Entities ── Status + Lineage + Legacy ID (only when proven)
           │
           ▼
Canonical Nexus Identity & Typed Relations
           ├── Master Entity / System / Architecture / Mechanism
           ├── Execution / Intelligence / Knowledge / Governance
           ├── Verification / Evidence / Proof / Simulation
           ├── Generation / Genome / Evolution / Operations
           ├── Project / Repository / File / Artifact / Version
           └── Innovation / Idea / Capability / Agent / Authority
           │
           ▼
Architecture → Contracts → Test → Proof → Deployment → Operations
```

All index categories are views over shared canonical records. Each record keeps its source-specific UID and lineage. Similar titles alone are not a merge key.

## Innovation record rule

Each innovation should carry: canonical UID, original name, aliases, source IDs and line/section, legacy ID only if proven, type/domain, parent/children, relationships, dependencies, prior art, novelty analysis, specification, implementation, tests, evidence, proof, owner, lifecycle, and current canonical form.

A concept mentioned in historical text is marked `RECOVERED_MENTION`, not `VERIFIED`. A concept in a design document remains `DESIGNED` or `PROPOSED`. The wallet has a working test implementation but is explicitly `NOT_PRODUCTION`.

## Wallet cross-link

`INNO-WALLET-AUTOMATION-001` is registered as a financial workflow innovation and linked to the internal wallet ledger, pooling tests, and PR #24. That PR is currently Draft/unmerged. The current in-memory engine passed its eight focused CI tests; this does not enable bank transfers or establish production custody.

## Files

- `registry/index_catalog.json`: consolidated index families and graph views.
- `registry/innovation_registry.json`: innovation and architecture records with status distinctions.
- `registry/index_coverage_manifest.json`: evidence-aware coverage and explicit gaps.
- Full downloaded bundle: archive source manifest with SHA-256 digests and the 570 source-local atomic entries.
- `tools/expand_index_bundle.py`: decodes compressed `.json.gz.b64` source artifacts into JSON.
- `tests/test_innovation_index_registry.py`: validates identity, counts, lineages and evidence boundaries.

## Next promotion gate

Do not declare full recovery until every historical numeric ID from 0001 to 2750 is linked to an exact source record or explicitly marked MISSING/CONFLICT/UNRESOLVED, with a coverage matrix and independent validation.
