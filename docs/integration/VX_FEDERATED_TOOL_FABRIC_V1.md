# VX Federated Tool and Server Fabric v1

**Status:** IMPLEMENTED CANDIDATE — CI and review are the promotion gates  
**Owner:** VAIXLNS  
**Execution authority:** VX  
**Evidence and policy boundary:** ARC-X Ω  
**Dispatch boundary:** `tools.execution_fabric.ExecutionGateway`

## Purpose

Provide one governed route for a host-registered tool to reach VX without creating a parallel permission system or an unreviewed path around the existing gateway.

This is a connector fabric, not an automatic adapter for every protocol. Each server or tool still needs a host-owned adapter/handler, a declared contract, an explicit admission decision, and tests. Registering a connector does not activate it.

## Components

- `vx/tool_fabric.py`: `ServerContract`, `tool_contract_digest`, `VXToolFabric`, `CompatibilityReport`, and `VXToolResult`.
- `tools/execution_fabric.py`: retains argument allowlisting, actor scopes, integration allowlists, bounded results, handler dispatch, and the existing hash-chained audit ledger.
- `vx/runtime_supervisor.py`: retains the state machine, authorizer, executor boundary, base verifier, and replay. Per-request executors do not replace its authorizer or base verifier; an additional verifier must pass too.
- `arc_x/core.py`: compiles source-bound EIR and requires independent evidence/authority verification for governed actions.
- `arc_x/vx_bridge.py`: route for EIR-carrying candidates that need simulation and tests before VX authorization/execution.

## Connector contract

A `ServerContract` declares:

- stable server/integration identity;
- protocol, protocol version, and contract version;
- the exact tool IDs exposed by that connector;
- the SHA-256 fingerprint for each registered `ToolSpec`;
- endpoint reference and maximum acceptable health-probe latency.

Registration fails if a tool does not exist, its external integration ID disagrees, or its contract fingerprint differs. Contract fingerprints include inputs, scopes, scope-groups, risk, output limits, enabled state, and whether the tool is explicitly read-only.

## Admission and invocation path

```text
Tool request + request ID
        ↓
VX operation created (argument digest only)
        ↓
Tool identity / schema / scope compatibility
        ↓
ARC-X host policy gate + EIR digest
        ↓
Integration admission + server health/protocol/version/latency
        ↓
VX preflight → contract test → VX authorizer
        ↓
Existing ExecutionGateway (second capability/scope/integration check)
        ↓
VX base verifier AND per-request result verifier
        ↓
Result digest + gateway audit hash + VX replay
```

The ordering is fail-closed. No registered handler is called when contract, ARC-X, integration, health, argument, scope, or VX authorization fails.

## Host callbacks are security boundaries

The caller must supply:

- `health_probe(contract)`: host-owned, bounded, preferably read-only health check returning `healthy`, `protocol`, `protocol_version`, `contract_version`, and measured `latency_ms`.
- `integration_admission(integration_id)`: trusted policy/registry check. It must agree with the separate allowlist configured on `ExecutionGateway`; neither one replaces the other.
- `arc_x_gate(contract, tool_spec, principal, args)`: trusted host integration that compiles or retrieves the relevant EIR, checks `CompilationResult.integrity_valid`, calls the appropriate ARC-X admission operation with trusted evidence and authority verifiers, and returns `allowed`, `decision`, `eir_sha256`, and `reason_codes`.

The fabric accepts `ADMITTED` for normal tool execution. Explicitly declared low-risk read-only tools may also use an allowed `ELIGIBLE_FOR_REVIEW` decision; medium-risk read-only tools require `VERIFIED`. Mutating tools are not allowed to rely on a read-only/review decision. A correct 64-character EIR digest is required for every invocation. The fabric validates format and binds the digest into the VX operation and result, but the trusted ARC-X callback must verify the actual EIR and evidence; a syntactically valid hash is not proof by itself.

## Runtime behavior

- Contract and health are checked before the tool handler is invoked.
- Tool inputs and full output are not copied into VX event payloads. The VX replay records bounded status/digest metadata; the authorized caller receives the output separately.
- The execution gateway records its own request/argument/output digest event. Its ledger remains independently verifiable.
- Request IDs are at-most-once per connector/tool/principal in this process. Replays are blocked; reuse with a different argument payload is rejected.
- Health responses and verifier errors are normalized to reason codes to avoid exposing raw exception messages.
- If VX's authorizer denies, the handler never runs. If the gateway rejects the request, VX's additional verifier prevents a success state. If the VX verifier rejects the result, the tool call is reported as failed even if the handler returned.
- `PREFLIGHT_ONLY` is only a compatibility check, not a claim that workload simulation was performed.
- The in-memory request deduplication map is process-local. Distributed idempotency requires durable shared storage before multi-worker or production use.

## Example registration

```python
from vx.tool_fabric import ServerContract, VXToolFabric, tool_contract_digest

spec, _handler = execution_gateway.registry.get("repo.search")

contract = ServerContract(
    server_id="local-repository-tools",
    integration_id=None,
    protocol="python-tool-contract",
    protocol_version="1",
    contract_version="repo-search.v1",
    tool_ids=("repo.search",),
    tool_contract_digests={"repo.search": tool_contract_digest(spec)},
)

fabric.register_server(contract)
```

Use the tool's exact registered integration ID for remote providers and a host-configured health probe. Do not change the integration allowlist merely to make a failing connector pass.

## Validation

```bash
python -m unittest tests.test_arc_x_core -v
python -m unittest tests.test_arc_x_vx_bridge -v
python -m unittest tests.test_vx_tool_fabric -v
python -m pytest -q
```

CI success is necessary but does not prove production compatibility with a real server. Real-server claims require environment fingerprints, real health/contract results, authenticated integrations, successful end-to-end calls, replay/audit checks, and failure/recovery evidence.

## Promotion rule

Until the relevant CI runs and host integration are reviewed, this remains an implemented candidate. Do not label every possible tool as connected: only the registered tool IDs with matching contracts, admitted integration, valid ARC-X decision, and verified VX execution have an evidenced connection.
