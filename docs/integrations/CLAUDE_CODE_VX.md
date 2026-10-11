# Claude Code + VX Integration Plan

## Goal

Use Claude Code as an external engineering agent for the VX development workflow while keeping VAIXLNS governance authoritative. Claude Code is not itself the VX runtime, proof authority, or production admission controller.

## Integration surfaces

1. **Project instructions** — repository-root `CLAUDE.md` defines the operating contract.
2. **Skills** — focused, versioned procedures for tasks such as repository audit, test repair, dependency review, and evidence reporting. Skills must be reviewed before use.
3. **Hooks** — deterministic local checks (format, lint, test, secret scan) around tool actions. Hooks are not a substitute for CI or authorization.
4. **MCP** — expose narrow VX capabilities to Claude Code through a reviewed MCP server. Begin read-only.
5. **CI evidence** — GitHub Actions remains the source for reproducible test outcomes; local agent claims are not CI proof.

## Safe rollout sequence

- **Stage 0 — documented:** this file and root `CLAUDE.md`.
- **Stage 1 — inspect:** review the current VX API and decide which read-only operations can be exposed.
- **Stage 2 — prototype:** implement an isolated MCP adapter with typed inputs/outputs, request IDs, timeouts, audit events, and deny-by-default tool policy.
- **Stage 3 — tests:** cover schema validation, unauthorized calls, timeout, malformed output, duplicate requests, replay, and audit provenance.
- **Stage 4 — local opt-in:** provide a user-reviewed Claude Code MCP configuration example using a local command; do not enable it by default.
- **Stage 5 — governed writes:** expose mutation tools only behind explicit VX admission, scope checks, and human approval.
- **Stage 6 — CI verification:** run the full test suite and attach evidence to the pull request.

## MCP configuration template

Do not paste this template into an active config until the adapter exists and its command has been reviewed. Replace the placeholders with the real, tested executable and arguments.

```json
{
  "mcpServers": {
    "vx-readonly": {
      "command": "<reviewed-local-executable>",
      "args": ["<reviewed-entrypoint>"],
      "env": {
        "VX_MODE": "read-only"
      }
    }
  }
}
```

Do not put API keys or tokens directly in the committed file. Use the approved local secret manager or environment injection.

## Initial read-only tools to consider

- `vx.health`: report local adapter health only; do not infer cluster health.
- `vx.capabilities.list`: list admitted capability metadata.
- `vx.evidence.get`: retrieve evidence by stable identifier.
- `vx.plan.preview`: produce a non-executable plan preview.
- `vx.tests.status`: read CI status from an authorized integration.

Each tool needs a JSON schema, explicit scope, timeout, output limit, audit event, and negative tests. Do not expose arbitrary shell execution, arbitrary file reads, secret retrieval, unrestricted repository writes, or production deployment.

## Acceptance criteria

- No credentials in source, logs, prompts, or artifacts.
- All tools are deny-by-default and read-only in the first stage.
- Invalid or unauthorized requests fail closed.
- Every result carries request identity and provenance.
- CI tests demonstrate behavior and failure modes.
- README/status wording does not claim the adapter is live until a real server process and end-to-end test exist.

## References

- Claude Code documentation: https://docs.anthropic.com/en/docs/claude-code/overview
- MCP specification and SDKs: https://modelcontextprotocol.io/
- Official Python MCP SDK: https://github.com/modelcontextprotocol/python-sdk
