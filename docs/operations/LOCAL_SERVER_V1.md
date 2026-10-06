# Local Runtime Server V1.1.1

VAIXLNS-unified 1.1.1 includes an actual FastAPI server for local or hosted use.

Run:

```bash
uvicorn api.server:app --host 127.0.0.1 --port 8080
```

Available endpoints:

- GET /health
- GET /status
- GET /events
- POST /events
- POST /snapshots
- POST /federation/probe

Set `VAIXLNS_DB_PATH` to place the SQLite database on a durable volume.
Set `VAIXLNS_API_TOKEN` to require a bearer token for mutating/probe requests.

The server defaults to loopback and therefore does not expose a new network
surface unless the operator explicitly binds it to another interface.

Remote VLNS connectivity is configured separately through the server connection
environment variables documented in `VLNS_SERVER_CONNECTION_V1.md`.
