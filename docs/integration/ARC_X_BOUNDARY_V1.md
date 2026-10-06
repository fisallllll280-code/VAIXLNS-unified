# ARC-X Ω Boundary — Unified Fabric Integration v1

**Status:** SPECIFIED

VAIXLNS-unified is an integrated runtime/fabric surface. ARC-X is kept as a canonical tool specification in VAIXLNS and is integrated through explicit contracts rather than copied into the runtime as a second source of truth.

## Integration role
- consume ARC-X reconstruction and admission artifacts;
- route verification to VV-compatible verification surfaces;
- route execution to VX-compatible runtime surfaces;
- preserve evidence, replay, and lineage;
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

See the canonical ARC-X specification in the VAIXLNS repository:
https://github.com/fisallllll280-code/VAIXLNS/blob/main/docs/tools/ARC_X_EPISTEMIC_REALITY_COMPILER_V1.md