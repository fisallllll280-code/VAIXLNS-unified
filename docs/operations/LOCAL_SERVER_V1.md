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
Set `VAIXLNS_API_TOKEN` before using any mutating or federation-probe endpoint.
When the token is missing or blank, those endpoints fail closed with
`503 AUTHENTICATION_NOT_CONFIGURED`; when the token is configured, absent or
invalid bearer credentials are rejected with `401 AUTHORIZATION_REQUIRED`.
The local health endpoint remains unauthenticated and must not be treated as
proof of federation connectivity.

The server defaults to loopback. Keep it on loopback until TLS, gateway,
network restrictions, and deployment authentication have been independently
verified. Do not expose this API publicly as a way to test federation links.

Remote VLNS connectivity is configured separately through the server connection
environment variables documented in `VLNS_SERVER_CONNECTION_V1.md`.
