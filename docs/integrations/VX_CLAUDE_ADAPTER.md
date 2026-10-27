# VX Claude provider adapter

`intelligence.claude_adapter.ClaudeAdapter` is an optional intelligence-plane adapter for the Anthropic Messages API. It returns a structured proposal and never executes model output, invokes tools, grants capabilities, or makes admission decisions.

## Configure

Install the optional provider SDK in the environment running VX:

```bash
python -m pip install anthropic
export ANTHROPIC_API_KEY="..."  # inject through your secret manager; do not commit it
export VX_CLAUDE_MODEL="claude-sonnet-4-5"  # optional model override
```

The default model is a configurable default, not a claim that the account has access to it. Use a model identifier enabled for your Anthropic account. When the SDK or key is absent, the adapter returns `not_configured` without making a network request.

## Use

```python
from intelligence.claude_adapter import ClaudeAdapter

adapter = ClaudeAdapter()
proposal = adapter.run(
    "Review the proposed architecture and list risks",
    {"repository_revision": "<pinned-commit-sha>"},
)
if proposal["status"] == "ok":
    # Send proposal through VX policy, authorization, execution, and evidence gates.
    # Never treat output_text as an executable command.
    print(proposal["output_text"])
```

An application may inject a compatible client for testing. The adapter uses bounded token output, a request timeout, no SDK retries, and avoids returning provider exception text. Provider failures are represented as a safe status object; callers must not promote failed or unverified responses.

## Optional VX audit ledger

Callers may inject an instance of `VXAIRequestAuditLedger` into `ClaudeAdapter(audit_ledger=ledger)`. When configured, the adapter records a SHA-256 digest of the assembled prompt, model/provider identity, provider attempt, token usage, output digest, response ID and state transitions. It never writes raw prompt or output text into the audit ledger.

The audited path fails closed before provider invocation if the initial audit event or RUNNING transition cannot be recorded. If the provider call succeeds but its audit evidence cannot be completed, the adapter returns `audit_evidence_pending` rather than a normal `ok` result. Provider response alone leaves verification at `PENDING`; an independent verifier must record evidence before the request may be considered VERIFIED.

Example:

```python
from infra.vx_ai_request_audit import VXAIRequestAuditLedger
from intelligence.claude_adapter import ClaudeAdapter

with VXAIRequestAuditLedger("var/vx-ai-audit.sqlite3") as ledger:
    adapter = ClaudeAdapter(audit_ledger=ledger)
    proposal = adapter.run(
        "Review the proposed architecture and list risks",
        {"repository_revision": "<pinned-commit-sha>"},
    )
    # Persist or display proposal only after checking proposal["status"].
```

The ledger stores usage but does not invent a cost from an unknown tariff. Cost entries must be supplied by a provider-specific price adapter or billing reconciliation job. A local SQLite hash chain is tamper-evident, not external WORM storage; deployment, backup, access control and retention still require separate admission.

## Validation

Run `python -m unittest tests.test_claude_adapter -v` and `python -m pytest -q tests/test_vx_ai_request_audit.py`. Tests cover missing configuration, invalid input, proposal-only output, provider failure redaction, audited success/error paths, fail-closed audit writes, ledger state transitions, cost reconciliation, source lineage, verification evidence, and tamper detection.

## Boundary with Claude Code

This module connects VX to the Claude model API; it does not connect the Claude Code CLI or register an MCP server. The repository's separate `integrations.mcp_server` remains the read-only VX-to-MCP bridge. A live end-to-end Claude Code session, API credentials, network reachability, and CI results must be verified separately before claiming the integration is live.
