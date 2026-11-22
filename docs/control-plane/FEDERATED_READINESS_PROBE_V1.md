# VAIXLNS Ω — Federated Readiness Probe V1

**State:** PROPOSAL / IMPLEMENTED IN A REVIEW BRANCH; live endpoints remain unverified.
**Canonical:** false.
**Mode:** explicitly enabled, bounded, read-only HTTP GET only.

## What the probe establishes

The probe is an operator tool for checking explicitly configured service endpoints. HEALTHY requires all of:
- a per-target opt-in switch set to true,
- a valid HTTPS URL (plain HTTP is allowed only for loopback fixtures),
- HTTP 2xx without following redirects,
- a bounded JSON object response,
- an exact expected service identity,
- an exact typed healthy signal.

A reachable IP or 200 response alone is not enough. Errors and evidence reports never include raw bodies, full URLs, query values, or bearer tokens.

## Configured targets and current contract boundaries

- **VAIXLNS**: expects service=VAIXLNS-runtime and boolean ok=true from the existing /health API.
- **NEXENT**: expects service=nexent-web and boolean ok=true from its /api/health route.
- **VLNS**: uses VLNS_SERVER_URL, VLNS_SERVER_HEALTH_PATH, VLNS_SERVER_ENABLED, optional VLNS_SERVER_TOKEN, and requires VLNS_SERVER_EXPECTED_SERVICE to be pinned before any request. The current VLNS document identifies the runtime as not yet implemented, so absence is expected unless an independently deployed service exists.
- **VX-runtime**: the repository reference runtime is not treated as an HTTP server by assumption. A separately deployed read-only adapter must expose service=VX-runtime and status=READY; without an explicitly enabled configured endpoint the result is MISSING/BLOCKED.
- **NEXNET**: kept as a separate target from NEXENT until repository identity and owner/contract mapping reconcile their relationship. No alias is inferred.

The health probe does not create service deployments, start processes, connect MCP offices, validate subscription entitlements, or grant integration authority. It is only the first read-only reachability/identity/readiness gate.

## Run

Generate a report without requiring every system to be online:

    python -m operations.federation_probe --output var/federation-readiness.json

Use it as a strict precondition for a controlled stage:

    python -m operations.federation_probe --strict

Strict mode returns exit code 2 unless all five configured target definitions report HEALTHY. With absent endpoints, missing enablement, identity mismatch, or invalid response, strict mode fails by design.

Example environment names (set in the service manager or secret store, never committed):
- VAIXLNS_RUNTIME_PROBE_ENABLED=true, VAIXLNS_RUNTIME_HEALTH_URL=https://.../health
- VX_RUNTIME_PROBE_ENABLED=true, VX_RUNTIME_HEALTH_URL=https://.../health
- VLNS_SERVER_ENABLED=true, VLNS_SERVER_URL=https://..., VLNS_SERVER_EXPECTED_SERVICE=<contract-pinned-id>
- NEXENT_PROBE_ENABLED=true, NEXENT_HEALTH_URL=https://.../api/health
- NEXNET_PROBE_ENABLED=true, NEXNET_HEALTH_URL=https://.../health

The placeholders above are not real endpoints. Do not enable any target until its actual deployment URL and identity contract are verified. Supply credentials through the environment/secret manager; do not place them in source, reports, shell history, or chat.

## Acceptance

Run:

    python -m unittest tests.test_federation_probe -v

Tests use fake transports only; they make no external network calls. A successful test proves the guard behavior in the test environment, not that external systems are connected. Once this branch is reviewed, run the probe only in the target deployment environment, inspect its redacted report and independent service logs, and retain failures as MISSING, BLOCKED, DEGRADED, or UNKNOWN.
