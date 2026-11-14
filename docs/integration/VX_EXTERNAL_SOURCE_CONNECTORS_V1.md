# VX External Source Connectors v1

## Status and scope

This change adds a read-only GitHub repository connector to the local-first workspace. It reuses the existing `GitHubRepositorySearchProvider`, pins retrieved files to commit SHAs, stores provenance and content hashes in the workspace catalogue, and exposes sync results through the workspace API.

It does **not** crawl arbitrary repositories, write to GitHub, ingest every file in every repository, access ChatGPT conversation history automatically, or claim live model-agent execution.

## Configure the allowlist

Set an administrator-owned comma-separated repository allowlist.

```bash
export VAIXLNS_GITHUB_REPOSITORIES="fisallllll280-code/VAIXLNS,fisallllll280-code/VAIXLNS-unified"
export GITHUB_TOKEN="optional-read-only-github-token"
```

A token is optional for public repositories, but authenticated access is recommended for rate limits and private repositories. Use a fine-grained, read-only token limited to the listed repositories. Do not commit tokens.

## API

`POST /workspace/connectors/github/sync`

```json
{
  "query": "architecture source provenance sessions",
  "repositories": ["fisallllll280-code/VAIXLNS-unified"]
}
```

- `query`: 3–300 characters; ranks candidate paths and scores their content in the selected repositories.
- `repositories`: optional subset of `VAIXLNS_GITHUB_REPOSITORIES`; max 5 per request.
- Result includes file URLs, commit revisions, SHA-256, count of changed files, and duplicate count.

## Freshness and conflicts

- Retrieved source URLs are pinned to immutable commit SHAs.
- Stable workspace IDs use the repository/path; a changed file records the previous SHA and marks `changed_since_last_sync`.
- Previous matches not returned by a successful sync are marked `stale` only within the same stable query result set; unrelated query results are not invalidated.
- A failed provider/API request aborts before the local catalogue transaction.
- Rebuilding the local filesystem index preserves connector-managed GitHub rows.
- A stale source remains historical evidence; it must not be treated as current without a successful refresh.

## Security boundary

- HTTPS requests go only to `api.github.com` through the existing host-restricted transport.
- Read-only GET operations only; no commits, pull requests, shell execution, arbitrary URLs, or automatic deployment.
- Repository allowlist is configured by the server, not trusted from request input.
- File suffixes, exclusions, and size caps are enforced by the existing research adapter.
- Provider results are treated as untrusted content, never as executable instructions.
- API mutation route uses `VAIXLNS_API_TOKEN` when configured. Production also requires TLS, private network controls, secret management, and access logging.

## Verification

Run `pytest -q tests/test_workspace_connectors.py tests/test_workspace_fabric.py`.

Tests cover allowlist enforcement, commit-pinned provenance metadata, API configuration errors, and preservation of external source rows during local re-indexing. Live GitHub connectivity requires a separate environment-level integration test with network access and configured repositories.


## Local archive workflow

The workspace index endpoint also accepts an explicit list of local archive directories in `extra_roots`. Each path must be inside the configured repository root or within a path listed in `VAIXLNS_ALLOWED_SOURCE_ROOTS` (platform path separator-delimited). The dashboard's **فهرسة الأرشيف** control submits those paths to the same guarded indexer. This supports locally available text exports and archives; it does not grant access to ChatGPT's private conversation store or other provider accounts.
