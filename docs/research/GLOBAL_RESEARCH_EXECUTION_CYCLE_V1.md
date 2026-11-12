# VAIXLNS Global Research Execution Cycle v1

## Status

- Implementation: added on an isolated feature branch.
- Research core: reuses the existing REDF `ResearchDecisionOrchestrator`.
- Repository adapter: read-only GitHub API adapter; each repository is pinned to a commit SHA per run.
- Writes: the CLI writes one local JSON evidence bundle using create-only semantics. It does not write to GitHub.
- Promotion: always false. The result is a research decision packet, not implementation approval, certification, or canonical authority.
- External web/archive providers: not connected by this entrypoint yet.
- Distributed execution / physics solvers: not part of this runner and not claimed as operational.

## Execution flow

1. Accept a mission, candidate, and explicit `owner/repository` allowlist.
2. Build seven complementary REDF lanes: discovery, prior-work discovery, novelty, counterevidence, implementation, contradiction, and failure analysis.
3. Read repository trees and file contents through HTTPS GET only.
4. Pin every source URI to the commit SHA used for the run.
5. Classify evidence, compute content SHA-256 digests, consolidate exact duplicates, and retain conflicting revisions.
6. Run the existing source-coverage, novelty/lineage, claim-adversary, engineering-completeness, and evidence-integrity agents.
7. Export a deterministic JSON bundle. The bundle hash is computed over the bundle before adding the hash field.

## CLI

From a checked-out repository:

```bash
python -m tools.research_cycle \
  --mission "Assess candidate engineering system X" \
  --candidate-title "Candidate X" \
  --repositories "fisallllll280-code/VAIXLNS,fisallllll280-code/VX-runtime" \
  --output "artifacts/research/RSH-candidate-x.json" \
  --allow-network
```

Optional inputs:

- `--candidate-summary`: short candidate description.
- `--engineering-spec path.json`: JSON object containing the REDF engineering contract fields.
- `--catalog path.json`: JSON array of existing innovation records with `innovation_id`, `name`, optional `summary`, and optional string-list `aliases`.
- `--catalog-coverage-complete`: only when completeness has been independently established.
- `--min-sources`, `--min-primary-sources`, `--max-sources`: explicit evidence thresholds and retrieval bound.

Set `GITHUB_TOKEN` in the process environment to use authenticated GitHub API access. The token is never included in the evidence bundle. Public repositories may be readable without a token, subject to GitHub rate limits.

## Safety and evidence rules

- Network access is opt-in through `--allow-network`.
- The repository allowlist is mandatory; wildcards and implicit repository discovery are not supported.
- The GitHub adapter uses HTTPS GET requests only and rejects repositories outside the allowlist.
- A truncated repository tree is a hard failure, not an empty search result.
- Sensitive filenames and oversized files are excluded by the existing adapter.
- Output paths are create-only. Existing evidence files are never overwritten.
- Provider failures remain explicit in the REDF outcomes; they are not converted into successful empty searches.
- A missing or incomplete catalog cannot establish novelty.
- No result from this runner can set `promotion_authorized=true`, modify `project.genome` or `Ω.000`, merge a pull request, deploy, or spend funds.

## Known limitations

The GitHub adapter ranks a bounded set of candidate files before reading contents. This is a repository research adapter, not a general web search engine. The runner does not yet connect Crossref, OpenAlex, arXiv, standards catalogs, patent databases, web search, Undermind, MagicPath, remote simulation clusters, CAD solvers, or laboratory systems. Those integrations must be added as separate, independently tested providers behind the existing REDF `SearchProvider` contract.

The current run is sequential inside the REDF orchestrator. Parallel execution, retries with backoff, persistent checkpoints, multi-provider arbitration, and physics/HPC execution require separate contracts and tests before being enabled.

## Acceptance checks

- Adapter tests prove content-only matches are not skipped merely because a filename lacks query terms.
- Cycle tests prove seven research lanes are emitted, the result is deterministic for identical evidence, promotion remains false, the network opt-in is enforced, and prior evidence output cannot be overwritten.
- CI must pass before this branch is considered verified.
