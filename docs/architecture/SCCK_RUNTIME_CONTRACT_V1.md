# SCCK Runtime Contract V1

## Canonical position

`VAIXLNS` defines canonical truth and governance. `VX` owns execution.
`SCCK` is the contract/commit kernel inside the VX boundary.

`NEXENT` may discover and propose. It does not canonicalize its own result.

## State path

```text
REQUEST
  -> IDENTIFY
  -> LOAD CANONICAL STATE
  -> AUTHORIZE
  -> RESOLVE CAPABILITY
  -> EVALUATE POLICY
  -> VERIFY CONTRACT
  -> CHECK PRECONDITIONS / INVARIANTS
  -> CREATE COMMIT INTENT
  -> ADAPTER EXECUTION
  -> OBSERVATION
  -> READ-BACK
  -> VERIFY CID / STATE / VERSION / EPOCH
  -> RECORD EVIDENCE
  -> FINALIZE CANONICAL STATE
  -> ISSUE COMMIT PROOF
```

## Sovereignty rules

1. Identity does not imply authority.
2. Authority does not imply capability.
3. Capability does not imply execution.
4. Execution success does not imply proof.
5. Adapter acknowledgement does not imply canonical truth.
6. Adapters remain outside the Sovereign Key Domain.
7. Canonical promotion requires explicit authority.

## Artifact contract

Every committed artifact carries:

```text
ArtifactID
ContentCID
SchemaCID
PolicyCID
AuthorityCID
ProvenanceCID
ParentCID
ContractCID
State
Version
Epoch
Nonce
IssuedBy
AuthorizedFor
Payload
Signature
ProofBundle
```

## External boundary

Adapters return observations. They cannot call the canonical finalization path
without passing through SCCK verification.

## Failure semantics

- missing identity/capability/authority/policy -> REJECTED
- execution failure -> REJECTED
- intent/observation mismatch -> REJECTED
- CID/state/version/epoch mismatch -> QUARANTINED
- required observation signature missing -> QUARANTINED
- accepted observation -> COMMITTED + EvidenceRecord + CommitProof

## Evidence classification

The implementation deliberately distinguishes:

`IMPLEMENTED_LOCAL` -> executable code and repository tests

`RUNNING` -> active deployment/runtime evidence

`PROVEN` -> reproducible evidence sufficient for the claim being made

External deployment claims remain blocked until their evidence exists.
