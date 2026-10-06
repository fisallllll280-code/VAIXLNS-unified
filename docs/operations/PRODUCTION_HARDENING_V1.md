# VAIXLNS Production Hardening V1

The objective is to close implementation seams without turning documentation
into false production claims.

## Closed in this revision

1. Durable local event and snapshot storage using SQLite WAL and FULL sync.
2. Explicit HTTPS server connectivity boundary with environment-only secrets.
3. Optional OPA policy decision adapter with fail-closed behavior.
4. Optional NATS JetStream adapter for replicated events and application lease.
5. Isolated solver bridge for math/physics/engineering workloads.
6. CI coverage for durable restart/recovery and solver execution.
7. Optional OpenTelemetry SDK/exporter dependencies separated from core install.
8. Explicit SPIFFE/SPIRE workload-identity boundary.
9. Versioned server endpoint configuration.

## Still evidence-gated

- Actual multi-node NATS cluster run.
- Actual leader failover under node failure.
- Actual cross-node replay/recovery.
- Actual connection to a VLNS server.
- Signed supply-chain attestation beyond the internal provenance shape.
- Formal theorem proving backend.
- Full 0001–2750 atomic historical recovery.
- Full canonical UI/interface runtime.
- Full dynamic model/tool registry.

The adapters are implementation-complete at their boundaries; deployment proof is
a separate promotion gate.
