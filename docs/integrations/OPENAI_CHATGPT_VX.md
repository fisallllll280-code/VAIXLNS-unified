# OpenAI / ChatGPT model adapter for VX

## Purpose

`integrations.openai_vx_assistant.VXOpenAIAssistant` uses the OpenAI Responses API with three fixed read-only tools: `vx_health`, `vx_status`, and `vx_capabilities_list`. Tool calls are bounded to three. Unknown tools, non-empty arguments, arbitrary URLs, shell, filesystem, secrets, writes, deployment, and deletion are not exposed.

This uses the OpenAI API, not a direct connection to the ChatGPT consumer app. API access requires an API key and may be billed separately from a ChatGPT subscription. Store credentials in a local secret manager or environment injection; never commit them.

## Local setup

1. Install the repository dependencies in an isolated Python environment: `python -m pip install -r requirements.txt`.
2. Inject `OPENAI_API_KEY` through the local secret manager and set `VX_OPENAI_MODEL` (default: `gpt-4.1`).
3. Start the VX API locally: `uvicorn api.server:app --host 127.0.0.1 --port 8000`.
4. Invoke the adapter:

```python
from integrations.openai_vx_assistant import VXOpenAIAssistant

assistant = VXOpenAIAssistant()
print(assistant.respond("Check VX health and summarize only what the evidence supports."))
```

5. Run tests: `python -m unittest tests.test_openai_vx_assistant -v`.

For a remote VX API, set `VX_OPENAI_API_BASE_URL` to an HTTPS endpoint and inject `VAIXLNS_API_TOKEN` securely. Remote HTTP is rejected and a remote endpoint requires the token. Do not expose a local API port publicly to make the model reachable.

## Claude Code MCP setup

The existing MCP bridge is separate from the OpenAI adapter. In the Claude Code MCP configuration, add the following reviewed local server entry and replace the working directory with the real absolute repository path:

```json
{
  "mcpServers": {
    "vaixlns-vx-readonly": {
      "command": "python",
      "args": ["-m", "integrations.mcp_server"],
      "cwd": "/ABSOLUTE/PATH/TO/VAIXLNS-unified"
    }
  }
}
```

Start the VX API first. If token authentication is enabled, inject `VAIXLNS_API_TOKEN` into the MCP process securely. Review command, path and permissions before enabling it. The bridge remains read-only.

## Curated library adoption

The frontier registry is a candidate list, not evidence that every library is installed or approved. Adopt incrementally:

- `openai`: model API SDK; already declared in requirements and used lazily by this adapter.
- `mcp`: official MCP SDK; candidate for replacing the current standard-library protocol implementation after compatibility review.
- `openai-agents`: optional orchestration; not required here and must not replace VX governance.
- OpenTelemetry: tracing; review prompt/secret redaction before enabling exporters.
- Hypothesis: development-only property testing for policy and replay invariants.
- Temporal or LangGraph: evaluate only if they add measurable value without duplicating VX's existing supervisor.

For each new library, review provenance, license, supported Python versions, maintenance/security posture, transitive dependencies, failure/recovery behavior and tests. Do not mass-install candidates. Pin and lock accepted dependencies before production use.

## Status boundary

Unit tests do not prove API credentials, live endpoint reachability, Claude Code connection, production authentication, or production readiness. Verify those separately in the target environment. Write-capable tools remain out of scope until VX admission, audit evidence, least privilege and explicit approval are implemented and tested.
