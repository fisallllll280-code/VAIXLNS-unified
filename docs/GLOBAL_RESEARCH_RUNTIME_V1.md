# VX Global Research Runtime v1

## Purpose

This runtime extends the existing REDF research-decision fabric. It does not create a parallel innovation registry, and it does not replace VAIXLNS governance, VX execution controls, or the canonical `project.genome` / `Ω.000` records.

## Current scope

- Read-only GitHub repository discovery against an explicit allowlist.
- Seven complementary REDF lanes: discovery, novelty, counterevidence, implementation, contradiction, and failure analysis (plus the second discovery lane).
- Commit-pinned source records and SHA-256 content digests through the existing adapter.
- Per-run cache for commit-pinned source reads so repeated query lanes do not refetch identical blobs.
- Local innovation-index ingestion as an incomplete comparison catalog.
- Deterministic research bundle and machine-readable metrics.
- Report artifacts preserve source URI, revision, and SHA-256 while omitting raw source file bodies.
- Fail-closed network gate and bounded remote file reads.

## Execution

Plan-only is the default. Live read-only GitHub research requires both an explicit command flag and an explicit environment gate:

```bash
export VX_RESEARCH_NETWORK_ENABLED=1
export GITHUB_TOKEN=<optional-read-only-token>
python scripts/run_global_research.py --execute \
  --repositories fisallllll280-code/VAIXLNS \
                 fisallllll280-code/VAIXLNS-unified \
                 fisallllll280-code/VX-runtime \
  --catalog /path/to/innovation-operation-index.v1.json \
  --output research-cycle.json
```

Without `--execute`, the runtime refuses to start network access. Without `VX_RESEARCH_NETWORK_ENABLED=1`, it fails closed. Use a read-only token with the narrowest available repository permissions. The adapter rejects repositories outside the allowlist, excludes known secret filenames, rejects truncated trees, pins each query to a commit SHA, and performs GET requests only.

The default allowlist is the three core repositories. Add NEXENT, VX50_COMPLETE_BUILD, datasets, or VAIXLNS-Intent-to-Reality explicitly when the research scope requires them. The candidate-read cap defaults to two files per repository per query to bound API usage; raise it deliberately when broader coverage is needed. A bounded scan is not an exhaustive audit.

## Manual GitHub Actions execution

A manual-only workflow is included at `.github/workflows/vx-global-research-runtime.yml`. It has no push, pull-request, or scheduled trigger. It becomes available in the Actions tab only after this PR is approved and merged to the default branch. A human must then open **Actions → VX Global Research Runtime → Run workflow** and supply the mission and explicit repository allowlist. The workflow grants only `contents: read`, performs GitHub GET requests, and uploads the JSON report as a 30-day artifact. It does not write the report into a repository or execute candidate code.

## Decision semantics

- A successful search is not proof that a candidate is novel.
- An incomplete catalog always yields `CATALOG_INCOMPLETE` rather than a novelty claim.
- Missing sources, failed lanes, contradictions, and incomplete engineering specifications remain visible.
- Research readiness is not implementation readiness.
- `promotion_authorized` remains false and `canonical_eligible` remains false.
- No candidate code is executed. No repository file, branch, issue, release, or canonical record is written by the runtime.

## Verification

Run:

```bash
python -m unittest discover -s tests -p "test_global_research_runtime.py" -v
python -m unittest discover -s tests -p "test_research_adapters.py" -v
python -m unittest discover -s tests -p "test_research_fabric.py" -v
```

The GitHub Actions research-fabric workflow runs the runtime tests on pull requests that touch these files. A green test suite validates the bounded software contract only; it does not prove that external research servers, multi-agent model services, physics solvers, distributed compute, or VX production endpoints are connected.

## Next integration gates

1. Add independent, source-cited web/archive providers behind the existing `SearchProvider` protocol.
2. Add an explicit read-only adapter for the VAIXLNS innovation index and historical recovery sources.
3. Add contract-tested A2A/MCP tool discovery with capability-scoped principals.
4. Connect VCRE only after a real numerical solver, benchmark fixtures, and independent error bounds exist.
5. Connect VX runtime only through a pinned, isolated execution contract with replayable logs and rollback evidence.

No gate advances automatically. Preserve source history and require explicit authorization for any promotion, merge, deployment, external connection, or spending.
