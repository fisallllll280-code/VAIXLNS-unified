# VX–VLNS Unified Core — Integration Contract v1

**Implementation surface:** VAIXLNS-unified
**Status:** additive reference implementation; tests must pass before admission
**Canonical authority:** VAIXLNS / project.genome / Ω.000
**Unified entry point:** integration.vx_vlns_unified.VXVLNSUnifiedCore

## Objective

Present VX and VLNS as one governed task system through a single orchestration entry point, while preserving clear internal responsibilities and existing source ownership.

- **VLNS activation:** model/provider identity, role and capability allowlists, signed activation envelope, remote receipt validation.
- **VX execution:** capability routing, execution handlers, verification, and task result.
- **Evidence gate:** activation must be confirmed remotely and recorded locally before capability dispatch.
- **Canonical governance:** VAIXLNS remains authoritative. This facade cannot grant canonical-write, unrestricted-network, external-action, or governance-override permissions.

## Unified flow

```text
Task Request
    ↓
VLNS policy + signed activation envelope
    ↓
Remote activation receipt validation
    ↓
VX evidence acknowledgement
    ↓ only when ACTIVATED_AND_RECORDED
VX capability routing → admitted handler
    ↓
UnifiedRunResult + activation_id + reason
```

Any missing, rejected, mismatched, or unrecorded activation returns HOLD and the handler is not invoked. An unavailable capability also returns HOLD. A handler exception is reported as EXECUTION_FAILED, not success.

## API

VXVLNSUnifiedCore.run(request, capability, payload, handlers) is the single task entry point. The runtime and activation bridge are injected dependencies, so tests can use deterministic fakes without claiming remote connectivity.

The caller must supply handlers that have already passed the surrounding VX governance and execution admission checks. This facade composes existing controls; it does not replace the constitutional authorizer, VX runtime, SCCK commit boundary, or canonical admission process.

## Compatibility and safety

- Existing vlns and vx modules remain in place behind one public workflow.
- No repository identity is silently renamed or merged.
- No canonical file, master index, historical artifact, or deployment configuration is modified by this contract.
- No secrets are stored in source code.
- Local tests with fake activation receipts prove control-flow behavior only; they do not prove a live VLNS endpoint, production readiness, or cross-repository evidence federation.

## Acceptance checks

1. Valid activation receipt and evidence acknowledgement permit dispatch.
2. ACTIVATED_EVIDENCE_PENDING returns HOLD and invokes no handler.
3. Remote rejection, invalid receipt, or transport failure returns HOLD.
4. Missing capability returns HOLD.
5. Handler exceptions return EXECUTION_FAILED.
6. Canonical authority remains outside this facade.

Run the focused tests with:

```bash
python -m pytest -q tests/test_vx_vlns_unified.py tests/test_vlns_activation_bridge.py tests/test_vlns_runtime.py
```

Test execution is required in CI before this change can be marked verified.
