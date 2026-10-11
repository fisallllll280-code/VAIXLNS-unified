# VX read-only MCP bridge

This adapter implements a minimal MCP stdio JSON-RPC surface using the Python standard library. It connects to the existing VAIXLNS Runtime API; it does not start the API or install a model/agent.

## Exposed tools

- `vx.health`: GET `/health`
- `vx.status`: GET `/status`
- `vx.capabilities.list`: static bridge capability description

The bridge does **not** expose shell execution, arbitrary URLs, filesystem access, event writes, deployment, or deletion. Tool inputs must be empty objects. API requests have a three-second timeout, a one-megabyte response limit, and fixed paths. HTTP is permitted only for loopback; remote API endpoints must use HTTPS.

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

Run `python -m unittest tests.test_mcp_server -v`. The tests cover protocol initialization, read-only tool listing, notification handling, unknown methods, argument rejection, and remote HTTP restrictions. A passing unit suite does not establish a live Claude Code connection or production readiness. This bridge is an initial integration seam; authentication is inherited from the API token, and transport/process supervision remains the operator's responsibility.
