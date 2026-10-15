# VX read-only MCP bridge

This adapter implements a minimal MCP stdio JSON-RPC surface using the Python standard library. It connects to the existing VAIXLNS Runtime API; it does not start the API or install a model/agent.

## Exposed tools

- `vx.health`: GET `/health`
- `vx.status`: GET `/status`
- `vx.offices.list`: authenticated GET `/offices` using the operator-configured office registry
- `vx.office.route.preview`: authenticated POST `/office-routing/preview` with only `office_id` and `intent`
- `vx.capabilities.list`: static bridge capability description

Office inventory and route preview are strictly **proposal-only**. The route preview never dispatches a tool, calls a third-party endpoint, writes canonical state, or grants execution authority. A non-canonical registry, unresolved identity, unconfigured tool, or unadmitted office produces `HOLD` with explicit blockers and `dispatch_allowed: false`.

Configure `VAIXLNS_OFFICE_REGISTRY_PATH` on the API host to an absolute path for a pinned copy of the reviewed office registry. The current registry proposal is not itself canonical or evidence of live offices; until approved and installed, the office APIs return `OFFICE_REGISTRY_NOT_CONFIGURED` or hold all proposals. Configure `VAIXLNS_API_TOKEN` on both API and bridge hosts. The office endpoints require a configured token even on loopback and fail closed when it is absent.

The bridge does **not** expose shell execution, arbitrary URLs, filesystem access, event writes, dispatch, deployment, or deletion. Tool inputs are schema-bounded; API requests have a three-second timeout, a one-megabyte response limit, and a fixed method/path allowlist. HTTP is permitted only for loopback; remote API endpoints must use HTTPS.

## Run locally

1. Start the existing VAIXLNS API, for example `uvicorn api.server:app --host 127.0.0.1 --port 8000`.
2. Configure `VX_MCP_API_BASE_URL` if needed (default `http://127.0.0.1:8000`).
3. If the API uses `VAIXLNS_API_TOKEN`, provide the same environment variable to the bridge process.
4. Run `python -m integrations.mcp_server` as an MCP stdio server.

Example Claude Code MCP configuration (adjust the absolute repository path):

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

## Verification and limitations

Run `python -m unittest tests.test_mcp_server -v` and `python -m pytest -q tests/test_office_router.py tests/test_api_server.py`. Tests cover protocol initialization, route allowlisting, schema rejection, registry identity, authentication, proposal-only output, and the absence of dispatch side effects. A passing unit suite does not establish a live Claude Code connection or production readiness. This bridge is an initial integration seam; authentication is inherited from the API token, and transport/process supervision remains the operator's responsibility.
