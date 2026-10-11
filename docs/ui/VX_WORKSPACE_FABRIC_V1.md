# VX Workspace Fabric v1

## Purpose

This change adds a local-first workspace layer that links repository sources, a content index, durable work sessions, source lineage, bounded specialist-agent roles, and a single responsive dashboard.

## Screens and endpoints

- `GET /dashboard`: Arabic RTL responsive dashboard with overview, sources/index, sessions, agents, and audit screens.
- `GET /workspace/overview`: counts, configured root, index timestamp, operating boundary.
- `GET /workspace/sources?q=&limit=`: indexed source catalogue and status.
- `GET /workspace/search?q=&limit=`: local text search with short evidence excerpts and SHA-256 provenance.
- `POST /workspace/index/rebuild`: scan configured repository root and optional explicitly supplied local roots.
- `GET /workspace/sessions`, `POST /workspace/sessions`, `GET /workspace/sessions/{id}`.
- `POST /workspace/sessions/{id}/messages`: save a message and automatically link up to five matching indexed sources.
- `GET /workspace/agents`, `POST /workspace/agents/run`: list specialist roles and run a bounded local evidence search.

## Data model

The SQLite workspace database stores:
- sources: stable source IDs, relative paths, SHA-256, content, size, modification time, index time, and duplicate status;
- sessions and messages: durable conversation continuity and agent attribution;
- session_sources: explicit provenance links between sessions and source records;
- agents: named specialist roles, skill labels, mode, and registration status.

Stable source IDs are derived from relative paths. Re-indexing upserts existing source rows so session-source relationships survive a rebuild. Sources removed from the scan are removed from the current catalogue and their links are cascaded; preserve archival snapshots separately if long-term retention is required.

## Scope and safety boundaries

- Default scan root is the repository containing `api/server.py`; override with `VAIXLNS_REPO_ROOT`.
- Optional roots can be submitted to the index rebuild endpoint only if they are inside the repository root or are explicitly allowlisted in `VAIXLNS_ALLOWED_SOURCE_ROOTS` (absolute paths separated by the platform path separator). No automatic network crawling is implemented.
- Only allowlisted text suffixes are scanned; common build/vendor directories and obvious secret files are skipped. Files larger than 1 MB and files containing common API-token assignment patterns are skipped.
- This is a bounded local text index, not a vector database or a semantic embedding engine. Search matches terms and returns evidence excerpts; it does not prove semantic equivalence.
- Ten specialist roles are registered. Their current `bounded_local_workflow` mode is a deterministic local workflow/search role, not a claim that ten autonomous model agents are running.
- Agent runs do not edit files, execute shell commands, deploy, or call an LLM.
- If `VAIXLNS_API_TOKEN` is set, workspace mutation endpoints require a Bearer token; the dashboard has an ephemeral token field and does not store it. The dashboard HTML itself is served without a token, so do not expose the service publicly without TLS, authentication, and deployment hardening.
- Existing runtime configuration permits unauthenticated local use when `VAIXLNS_API_TOKEN` is unset. Production deployments must set a strong token and add network-level access controls.
- Source contents may be sensitive. Restrict the repository root and workspace database permissions and do not index unrelated personal directories.

## Setup and verification

1. Install the repository dependencies.
2. Start locally: `uvicorn api.server:app --host 127.0.0.1 --port 8000`.
3. Open `http://127.0.0.1:8000/dashboard`.
4. Select **إعادة بناء الفهرس**. Configure `VAIXLNS_REPO_ROOT` for a different source tree. Add extra local roots only when intentionally approved.
5. Create a session and add a message; inspect the linked source list.
6. Run the `tests/test_workspace_fabric.py` test module and the repository CI checks.

The workspace database defaults to a sibling of `VAIXLNS_DB_PATH` with `.workspace.db` appended to its stem. Override with `VAIXLNS_WORKSPACE_DB_PATH`.

## Status semantics

A successful CI run proves the tests for the committed code passed in CI. It does not prove that a target server is deployed, a browser dashboard is reachable outside the local host, external sources are connected, or model agents are live. Those need separate environment-level checks.
