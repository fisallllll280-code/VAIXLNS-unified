# VX Resilient Multipath Fabric — v1

## Purpose

Provide best-effort fan-out delivery to multiple independent destinations so a
single endpoint outage does not prevent delivery attempts to healthy endpoints.
This is a delivery primitive for VX adapters, not a claim that network/server
availability is guaranteed.

## Flow

```text
VX Event / Broadcast Request
          |
          v
  Destination Registry
          |
          v
  Health Probe (optional)
          |
          v
 Per-Destination Circuit Breaker
          |
          v
 Bounded Retry + Backoff
          |
          v
 Sender Adapter (HTTP / MCP / WebSocket / Push)
          |
          v
 Per-Destination Result + Idempotency Key
          |
          v
 VX Evidence / Event Ledger
```

## Implemented in this change

- Fan-out to multiple destinations concurrently.
- Per-destination result reporting; one failed destination does not cancel others.
- Bounded retries with exponential backoff.
- Optional health probe before each attempt.
- Per-destination circuit breaker to suppress repeated calls to an unhealthy endpoint.
- Required idempotency key passed to the sender adapter.
- Disabled-destination handling and duplicate destination-ID rejection.

## Adapter contract

The caller injects a sender with the signature:

`sender(destination, payload, idempotency_key)`

The sender is responsible for actual transport, TLS/authentication, remote
acknowledgement semantics, and using the idempotency key at the destination
when supported. A sender response of `False` or an exception is considered
delivery failure. Other returned values are treated as acknowledgement.

## Operational constraints

- A broadcast report can be partial. Callers must inspect every destination result.
- Retries can duplicate side effects unless the remote endpoint honors idempotency.
- Circuit breakers are in-process and not shared across replicas.
- This component does not implement leader election, quorum, durable queues,
  cross-region replication, or automatic DNS/service discovery.
- A process crash can lose in-flight work; durable queue/outbox integration is
  a separate follow-up.
- Health probes are advisory and can race with a subsequent send.
- Secrets and full payloads should not be written to logs; store redacted evidence
  with trace IDs and outcome metadata.

## Verification

Run:

`python -m unittest tests.test_resilient_multipath`

Tests cover fan-out success, isolation of a failing destination, circuit-breaker
suppression, health-probe failure, and mandatory idempotency keys.

## Production follow-up

1. Add a durable outbox/queue and replay of unacknowledged deliveries.
2. Add transport-specific adapters with TLS, authentication, timeouts and
   response validation.
3. Persist delivery events to the canonical VX ledger.
4. Add cluster-wide rate limits and shared breaker state if multi-replica
   coordination is required.
5. Run controlled failover tests against a staging cluster before declaring
   production readiness.
