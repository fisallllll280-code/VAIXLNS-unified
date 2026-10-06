# VAIXLNS Open-Source Backend Integration V1

This record separates implementation adapters from verified deployment evidence.

| Concern | Open-source backend | VAIXLNS boundary | State |
|---|---|---|---|
| Durable replicated event stream | NATS JetStream | `distributed/nats_backend.py` | ADAPTER IMPLEMENTED / SERVER OPTIONAL |
| Application leader lease | NATS JetStream KV + CAS | `distributed/nats_backend.py` | ADAPTER IMPLEMENTED / SERVER OPTIONAL |
| Policy decision point | Open Policy Agent | `infra/opa_client.py` | ADAPTER IMPLEMENTED / SERVER OPTIONAL |
| Telemetry | OpenTelemetry SDK/Collector | `telemetry/otel_bridge.py` + optional deps | ADAPTER READY |
| Workload identity | SPIFFE/SPIRE | deployment/security boundary | INTEGRATION TARGET |
| Local durability/recovery | SQLite WAL | `infra/durable_store.py` | IMPLEMENTED + TESTED |
| Domain solver isolation | subprocess JSON bridge | `simulation/worker_bridge.py` | IMPLEMENTED + TESTED |

## Boundary rules

NATS is used as the distributed durability and coordination substrate; the
application does not claim that its own Python process implements Raft.

OPA is a policy decision point. The VAIXLNS execution boundary remains the
enforcement point and the adapter fails closed when the remote policy service
is unavailable.

OpenTelemetry remains vendor-neutral. The local runtime does not require a
collector.

SPIFFE/SPIRE belongs at the workload identity boundary for multi-host
deployment. It is not silently embedded into the core runtime.

## Promotion gate

Adapters are not automatically VERIFIED. Promotion requires reproducible
server/cluster evidence covering health, persistence, restart, reconnection,
failover, replay and recovery.
