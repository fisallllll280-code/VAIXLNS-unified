# VX Verifiable Event Fabric v1

Status: PROPOSAL. This document defines the next implementation slice: append-only hash-linked events, Merkle inclusion proofs, deterministic replay, exact capability grants, and independent checkpoint witnessing.

## Invariants
- Every event binds sequence, event ID, kind, payload, and previous hash.
- Replay rejects invalid chain history.
- Merkle inclusion proves membership under a specified root, not truth of payload.
- Capabilities bind principal, action, resource, expiry, policy version, and revocation.
- Hashes alone do not authenticate authors or prevent whole-ledger replacement. Production needs signed checkpoints and an independent witness.
- Tool enforcement must happen at the adapter boundary; this design does not itself authorize production execution.
