# VLNS Server Connection Contract V1

VAIXLNS now has a secret-free server connection boundary.

## Local-first

The runtime remains fully usable without a remote service. SQLite-backed
durability, deterministic execution and replay tests do not require a server.

## Remote connection

Configure only through environment variables:

```text
VLNS_SERVER_ENABLED=true
VLNS_SERVER_URL=https://<your-vlns-server>
VLNS_SERVER_TOKEN=<secret-in-environment-only>
VLNS_SERVER_HEALTH_PATH=/health
VLNS_SERVER_TIMEOUT=5
```

The token is never committed to source control.

## Distributed mode

For multi-node deployment, configure a NATS JetStream cluster as the durable
event backplane. The adapter supports persistent streams, replicated streams,
message idempotency, and an application-level leader lease using KV
compare-and-set.

The NATS service owns its own cluster quorum. VAIXLNS does not pretend that
the application layer has implemented Raft merely by calling NATS.

## Security boundary

HTTPS and bearer credentials are transport concerns. Workload identity can be
added with SPIFFE/SPIRE when the hosting platform requires workload-level
mTLS identity.

No private IP, password, credential, or assumed server identity is stored in
this repository.
