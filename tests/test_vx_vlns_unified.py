from __future__ import annotations

from vlns import ActivationOutcome, ActivationRequest, LifecycleState, SystemContract, VLNSRuntime
from integration.vx_vlns_unified import VXVLNSUnifiedCore


class FakeActivationBridge:
    def __init__(self, outcome):
        self.outcome = outcome

    def activate(self, request):
        return self.outcome


def make_request():
    return ActivationRequest(
        model_id="test-model",
        provider="test-provider",
        model_version="v1",
        role="engineering_mind",
        capability_profile=("engineering",),
        context_payload={"task": "test"},
    )


def ready_runtime():
    runtime = VLNSRuntime()
    runtime.register(SystemContract(
        system_id="VX",
        version="test",
        interfaces=("execution",),
        capabilities=("test.echo",),
        provenance="unit-test",
    ))
    runtime.transition("VX", LifecycleState.INITIALIZING)
    runtime.transition("VX", LifecycleState.READY, health="HEALTHY")
    return runtime


def test_dispatch_requires_activation_and_evidence():
    bridge = FakeActivationBridge(ActivationOutcome(
        status="ACTIVATED_AND_RECORDED",
        activation_id="act-123",
        envelope_hash="a" * 64,
        activated=True,
        evidence_recorded=True,
    ))
    core = VXVLNSUnifiedCore(ready_runtime(), bridge)
    called = []
    outcome = core.run(
        request=make_request(),
        capability="test.echo",
        payload={"value": 42},
        handlers={"VX": lambda data: called.append(data) or data["value"]},
    )
    assert outcome.status == "EXECUTED"
    assert outcome.result == 42
    assert outcome.activation_id == "act-123"
    assert called == [{"value": 42}]


def test_unrecorded_activation_holds_and_never_dispatches():
    bridge = FakeActivationBridge(ActivationOutcome(
        status="ACTIVATED_EVIDENCE_PENDING",
        activation_id="act-456",
        envelope_hash="b" * 64,
        activated=True,
        evidence_recorded=False,
        reason="LEDGER_UNAVAILABLE",
    ))
    core = VXVLNSUnifiedCore(ready_runtime(), bridge)
    called = []
    outcome = core.run(
        request=make_request(),
        capability="test.echo",
        payload={"value": 42},
        handlers={"VX": lambda data: called.append(data) or data["value"]},
    )
    assert outcome.status == "HOLD"
    assert outcome.reason == "LEDGER_UNAVAILABLE"
    assert called == []


def test_missing_capability_holds():
    bridge = FakeActivationBridge(ActivationOutcome(
        status="ACTIVATED_AND_RECORDED",
        activation_id="act-789",
        envelope_hash="c" * 64,
        activated=True,
        evidence_recorded=True,
    ))
    core = VXVLNSUnifiedCore(VLNSRuntime(), bridge)
    called = []
    outcome = core.run(
        request=make_request(),
        capability="missing.capability",
        payload={},
        handlers={"VX": lambda data: called.append(data)},
    )
    assert outcome.status == "HOLD"
    assert "CAPABILITY_UNAVAILABLE" in outcome.reason
    assert called == []
