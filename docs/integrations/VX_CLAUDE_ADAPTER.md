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

## Validation

Run `python -m unittest tests.test_claude_adapter -v`. Tests cover missing configuration, invalid input, proposal-only output, provider failure redaction, and limit validation.

## Boundary with Claude Code

This module connects VX to the Claude model API; it does not connect the Claude Code CLI or register an MCP server. The repository's separate `integrations.mcp_server` remains the read-only VX-to-MCP bridge. A live end-to-end Claude Code session, API credentials, network reachability, and CI results must be verified separately before claiming the integration is live.
