# VX-CONTINUUM V1 — Executable Primitive Contract

VX-CONTINUUM is an adaptive execution substrate inside VX. VAIXLNS defines canonical truth and governance; NEXENT discovers and proposes; XV prepares decisions; VX executes; VV verifies; SCCK controls canonical commit.

## Compiler
Intent -> V-IR -> Constraint Set -> Invariant Digest -> Topology -> Atomaton

The compiler creates an executable plan. It does not authorize or commit it.

## Atomaton
SPAWN -> BIND -> VALIDATE -> EXECUTE -> OBSERVE -> PROVE -> DISSOLVE

An Atomaton has ephemeral execution identity, parent intent, capability, contract, resource boundary, CIDs, evidence and execution trace. Ephemeral does not mean anonymous.

## Flux Grid
Flux Grid is a deterministic topology planner. It may select healthy nodes and bounded topology. It has no canonical authority, identity authority, sovereign keys or commit authority.

## Proof Spectrum
0 Observation; 1 Deterministic Replay; 2 Cryptographic Integrity; 3 Merkle/State Proof; 4 Attestation; 5 ZK Execution; 6 Formal Verification.

ZK is a proof tier, not a universal execution requirement.

## Proof Atom
CLAIM -> ProofAtom -> Evidence Bundle -> SCCK -> Canonical State

Proof Atom binds subject, claim, preconditions, input CIDs, execution CID, output CIDs, method, verifier, proof type, proof digest, validity and parent lineage.

## Sovereign invariants
I1: Execution != Canonical Authority.
I2: Ephemeral Execution Identity != Permanent Sovereign Identity.
I3: Canonical Commit requires an admissible proof level.
I4: Mutation cannot bypass Fitness + Sovereignty + SCCK.

## Research boundary
HSL remains a research/benchmark track. This implementation does not establish O(1) retrieval/update, distributed consensus, universal ZK execution, production finality, or formal theorem proving for all generated code.
