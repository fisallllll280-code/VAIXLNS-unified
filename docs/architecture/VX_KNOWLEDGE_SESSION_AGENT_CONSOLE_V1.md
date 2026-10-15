# VX Knowledge, Session, Agent, and Console Fabric v1

## Purpose and current implementation boundary

This change adds a local-first metadata index, a source registry, a role/capability registry for nine specialist agents, a browser console, and tests. The agent registry defines governed roles; it does not claim nine autonomous model processes are running. The indexer reads repository text files and explicitly imported session exports. It does not scrape ChatGPT/Claude accounts, fetch arbitrary URLs, or establish provider connectivity.

## Unified information model

Every indexed record has a stable path-derived ID, kind, repository-relative path, title, content digest, bounded excerpt, and repo:path provenance reference. Source registry entries point to existing repository paths or optional import locations. Session exports are opt-in: an operator places an export under sessions/ after reviewing its privacy and licensing implications. The indexer never reads environment files or common credential filenames, skips generated var/ output, limits source file size, and redacts common credential patterns from excerpts.

## Pipeline

1. Discover tracked/local text sources (docs/, config/, tests/, code and repository guides).
2. Normalize each source into a provenance record with a SHA-256 content digest.
3. Include explicitly imported session exports from sessions/ only.
4. Generate var/knowledge/index.json; generated index output is not source-of-truth and should not be committed if it contains sensitive excerpts.
5. Search the index lexically with deterministic scoring; advanced semantic/vector retrieval is a later opt-in backend.
6. Route work to a specialist role using config/vx_agents.v1.json; preserve least privilege, evidence references, and review gates.
7. Present source/agent coverage and indexing boundaries in web/vx-console.html.
8. Verify changes with unit tests and CI. Live provider calls and production runtime state require separate environment-backed checks.

## Agent roles

- Source Cartographer: source discovery and provenance.
- Session Curator: explicit export normalization and session references.
- Index Engineer: indexing and broken-link detection.
- Architecture Auditor: contract conflicts and unsupported claims.
- Security Reviewer: auth, tools, secrets, and supply-chain review.
- Verification Engineer: requirement-to-test traceability.
- Integration Engineer: API/MCP/provider boundary map.
- Operations Console Designer: evidence-backed screens and status.
- Release Coordinator: test/approval/release checklist.

Roles are contracts, not independent agents until a governed runner, model credentials, tool sandbox, task queue, audit events, and evaluation harness are configured. No role can bypass VX authorization or self-approve a release.

## Run locally

From the repository root:

    python -m knowledge.indexer --root . --output var/knowledge/index.json
    python -m knowledge.indexer --root . --output var/knowledge/index.json --query "MCP session source"
    python -m unittest tests.test_knowledge_indexer -v

Open web/vx-console.html in a browser. It shows registry-backed configuration, not live server metrics. The generated index can be loaded into a local static HTTP server if desired; do not expose private session exports publicly.

## Source/session integration contract

- Repository documents and code: discovered locally and linked by repo: references.
- Configuration/policies: indexed as machine-readable records; they remain authoritative at their canonical paths.
- Tests/CI: test files are discoverable; CI status is only verified by reading the actual run evidence.
- Sessions: opt-in imported JSON/JSONL/TXT/Markdown files under sessions/; each import should carry a source/session identifier and date if known. Do not invent missing metadata.
- External URLs, cloud drives, ChatGPT history, Claude history, MCP servers, and remote repositories: require explicit connectors and permissions; registry entries alone do not mean they are connected.
- Index refresh: rerun the indexer after repository or session changes. Automated scheduling is not enabled by this module.

## Acceptance criteria

- Every indexed record has a stable ID, digest, path and provenance reference.
- Secret-like values are redacted in excerpts and common credential files are excluded.
- Session imports are opt-in and remain local.
- Search returns bounded, deterministic results.
- Agent roles expose explicit inputs, outputs, tools and denials.
- Console never infers a live runtime state from registry metadata.
- Tests pass in CI before merging.
