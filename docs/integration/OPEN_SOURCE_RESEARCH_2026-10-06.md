# Open-Source Infrastructure Review — 2026-10-06

The review selected existing mature projects by responsibility, not by branding.
The application boundary remains explicit and provider-neutral.

| Area | Reference | Decision |
|---|---|---|
| Replicated event stream / coordination substrate | NATS JetStream | Use through adapter; server owns distributed quorum |
| Embedded Raft alternative | etcd-io/raft | Keep as research option; do not duplicate it in the app |
| Policy decision point | Open Policy Agent | Use through fail-closed HTTP adapter |
| Telemetry | OpenTelemetry | Use API/SDK/Collector path without locking the core to a backend |
| Workload identity | SPIFFE/SPIRE | Keep at deployment/security boundary |
| Local persistence | SQLite WAL | Use for zero-cost single-node durability and restart tests |

## Evidence boundary

Open-source capability is not proof of a VAIXLNS deployment.
The federation still requires environment-specific tests for health, persistence,
reconnection, failover, recovery, replay and security before promotion to
VERIFIED.

## Upstream references

- https://nats.io/
- https://docs.nats.io/
- https://github.com/etcd-io/raft
- https://www.openpolicyagent.org/docs
- https://opentelemetry.io/docs/collector/
- https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/
