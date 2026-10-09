# ARC-X Ω Boundary — Unified Fabric Integration v1

**Status:** SPECIFIED — runtime implementation candidate tracked separately

VAIXLNS-unified is an integrated runtime/fabric surface. ARC-X is kept as a canonical tool specification in VAIXLNS and is integrated through explicit contracts rather than copied into the runtime as a second source of truth.

## Integration role
- consume ARC-X reconstruction and admission artifacts;
- compile claims/evidence/proof obligations through `arc_x.core` while retaining the VAIXLNS canonical specification as the sole source of truth;
- route candidate execution through `arc_x.vx_bridge`;
- route registered server/tool calls through `vx.tool_fabric` and the existing `tools.execution_fabric.ExecutionGateway`;
- require protocol/version/contract/health checks, an explicit ARC-X policy decision, and separate VX authorization and verification;
- preserve evidence digests, tool audit hashes, replay, and lineage;
- expose operational status without promoting it to canonical truth.

## Rule

```text
VAIXLNS canonical tool contract
          ↓
ARC-X artifacts / requests
          ↓
Unified fabric
      ↙           ↘
  verify          execute
      ↘           ↙
       evidence
          ↓
        ARC-X
```

The unified fabric MUST NOT fork the ARC-X canonical specification into an independently authoritative copy.

Implementation surfaces and conformance tests:
- `arc_x/core.py` and `tests/test_arc_x_core.py`
- `arc_x/vx_bridge.py` and `tests/test_arc_x_vx_bridge.py`
- `vx/tool_fabric.py` and `tests/test_vx_tool_fabric.py`
- `docs/integration/ARC_X_RUNTIME_CONTRACT_V1.md`
- `docs/integration/VX_FEDERATED_TOOL_FABRIC_V1.md`

These are runtime implementation candidates. A registered connector is not considered connected until its real adapter is admitted, its policy callback validates the EIR/evidence, and a real invocation has evidence from both the execution gateway and VX verification.

See the canonical ARC-X specification in the VAIXLNS repository:
https://github.com/fisallllll280-code/VAIXLNS/blob/main/docs/tools/ARC_X_EPISTEMIC_REALITY_COMPILER_V1.md