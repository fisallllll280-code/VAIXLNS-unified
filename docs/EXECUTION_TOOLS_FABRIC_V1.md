# Ω Governed Execution Tools V1

**Status:** IMPLEMENTED / CI-TESTED  
**Runtime repository:** VAIXLNS-unified  
**Canonical owner:** VAIXLNS → Ω.000 → VAIXLNS.RESEARCH.DECISION.FABRIC.001  
**Integration boundary:** integration_control / External Integration Proof Boundary

## Purpose

Expose a concrete, auditable tool surface to research and engineering agents without giving them arbitrary shell, arbitrary filesystem write, arbitrary URL, dynamic import, or self-approval capabilities.

## Registered local tools

| Tool ID | Function | Required authority |
|---|---|---|
| \`repo.search\` | Search allowed text/source files below the configured checkout | One approved evidence-read scope |
| \`repo.read\` | Read a bounded line range from a file within the checkout | One approved evidence-read scope |
| \`repo.sha256\` | Compute a content SHA-256 | \`read:provenance\` |
| \`json.inspect\` | Parse JSON and report shape, keys, and content digest | One approved evidence-read scope |
| \`tests.run_unit\` | Run a preapproved unittest filename pattern under a low-environment subprocess | \`request:sandbox-test\` and explicit test-runner enablement |
| \`research.github.search\` | Read-only search over explicitly allowlisted GitHub repositories | \`read:public-repositories\` plus external integration admission |

The GitHub tool is not registered unless a provider is injected. If a provider is injected, it remains blocked until the trusted host supplies the integration ID returned from its separately verified/admitted integration process. Do not put tokens, credentials, or admission decisions in tool arguments.

## Execution gate

Every call must pass:
1. Principal active-state check.
2. Tool ID allowlist and tool enabled-state check.
3. External integration admission, where applicable.
4. Required scopes and scope-group policy.
5. Exact required/optional input validation (unexpected fields are rejected).
6. Handler execution with explicit output limits.
7. Append-only execution event with argument digest, output digest, status, and previous-event hash.

Denied calls are also audited. Raw tool arguments are not copied into the ledger. The event chain can be verified via \`AuditLedger.verify()\`.

## Filesystem controls

- All local file tools are read-only and confined to the configured repository root.
- Absolute paths, traversal segments, direct symlinks, sensitive filenames, and excluded build/dependency directories are rejected.
- Search is limited to known text/source suffixes, file-size thresholds, scan limits, and bounded result counts.
- JSON inspection parses the document; it does not claim JSON Schema conformance unless a separate schema validator runs.

## Unit-test execution

The test tool is disabled by default. It accepts only a fixed filename allowlist and a timeout capped at 60 seconds, invokes Python without a shell, and provides a minimal environment. This remains a code-execution capability and must be enabled only in an appropriate isolated repository runner. The subprocess is not a substitute for an OS-level sandbox.

## CLI

List available local tools:

\`\`\`bash
python -m tools.execution_cli --role research list
\`\`\`

Search this checkout:

\`\`\`bash
python -m tools.execution_cli --role research call repo.search --args-json '{"query":"innovation verification","max_results":10}'
\`\`\`

Read a bounded section:

\`\`\`bash
python -m tools.execution_cli --role engineering call repo.read --args-json '{"path":"docs/INNOVATION_EXECUTION_FABRIC.md","start_line":1,"end_line":40}'
\`\`\`

Run an allowlisted focused test in an isolated runner:

\`\`\`bash
python -m tools.execution_cli --role verifier --enable-tests call tests.run_unit --args-json '{"pattern":"test_research_fabric.py","timeout_seconds":30}'
\`\`\`

The CLI exposes fixed role profiles rather than accepting arbitrary authority scopes. It does not provision external integration admission.

## Research adapter integration

\`LocalRepositorySearchProvider\` implements the existing research \`SearchProvider\` contract against a fixed checkout and a fixed set of source directories. \`GitHubRepositorySearchProvider\`:
- requires an explicit repository allowlist;
- sends GET requests only to \`https://api.github.com\`;
- pins each repository snapshot to a commit SHA;
- retains source URL, revision, evidence class, content digest, and provider metadata;
- fails closed when the repository tree is truncated or content cannot be decoded;
- never writes to remote repositories.

The GitHub adapter is a read-only API adapter, not a general-purpose web search engine. Network failures and rate limits must remain visible in the enclosing research outcome.

## Current limits

- No live provider is auto-admitted.
- No public web search adapter is included here; web access needs its own declared provider contract and admission evidence.
- Test execution is opt-in and must run in an appropriate isolated environment.
- The gateway does not itself authorize production state changes. Any future mutating tool must have a separate contract, explicit approval boundary, rollback plan, and proof obligations.
