# VAIXLNS Mind Federation Protocol v1

## Goal
Each participating system runs an independent local nucleus and mind runtime. The federation links minds without making one host a mandatory central brain. Platform adapters implement this contract on Windows, Linux, macOS, Android, iOS/iPadOS, containers, and server environments, subject to platform lifecycle and permission constraints.

## Node contract
Each node publishes a stable node ID, nucleus version, OS family, protocol version, endpoint when available, and declared capabilities. Capability advertisement is not proof that a task is authorized or currently executable.

## Message contract
The module distributed/mind_federation.py defines versioned typed envelopes, sender and recipient identity, bounded message lifetime, canonical JSON and HMAC-SHA256 integrity/authentication, replay rejection, and deterministic capability discovery. Initial message kinds: capability.announce, task.propose, task.accept, task.result, knowledge.reference, health.ping.

## Trust and execution boundaries
- Provision secrets out-of-band; never commit them. Production should use unique pairwise secrets or an asymmetric identity provider.
- A valid signature proves possession of a configured secret; it does not grant authority to execute a task.
- Proposals must pass existing governance/authority checks before VX execution.
- Do not transmit credentials, private memory, or unrestricted executable code in payloads.
- Network adapters must use authenticated TLS, timeouts, bounded payloads, and explicit peer allow-lists.
- Persist replay/idempotency state in production; the current replay guard is in-memory.
- HMAC is a bootstrap profile, not a public-key federation or complete key-rotation system.

## Implementation boundary
This change supplies protocol primitives and unit tests. It does not claim a network listener, service installer, discovery daemon, consensus, cross-device synchronization, or platform runtime is deployed. Those require transport/platform adapters and live integration tests.

## Validation
Run: python -m unittest tests.test_mind_federation
Then integrate with governance, ledger, VX execution, and VV/OIF verification before enabling remote task execution.
