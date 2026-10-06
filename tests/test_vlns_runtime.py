from vlns import ChangeState, LifecycleState, SystemContract, VLNSRuntime


def test_registry_lifecycle_and_capability_dispatch():
    runtime = VLNSRuntime()
    runtime.register(
        SystemContract(
            system_id="VX",
            version="0.1",
            interfaces=("execution",),
            capabilities=("math.add",),
            provenance="test",
        )
    )
    runtime.transition("VX", LifecycleState.INITIALIZING)
    runtime.transition("VX", LifecycleState.READY, health="HEALTHY")

    result = runtime.dispatch(
        "math.add",
        {"a": 20, "b": 22},
        {"VX": lambda payload: payload["a"] + payload["b"]},
    )
    assert result == 42
    assert runtime.registry.get("VX").state is LifecycleState.READY
    assert [o.event for o in runtime.observations][-2:] == ["DISPATCH", "DISPATCH_COMPLETED"]


def test_lifecycle_rejects_invalid_jump():
    runtime = VLNSRuntime()
    runtime.register(
        SystemContract(
            system_id="NEXENT",
            version="1",
            interfaces=("research",),
            capabilities=("discover",),
            provenance="test",
        )
    )
    try:
        runtime.transition("NEXENT", LifecycleState.ACTIVE)
    except ValueError as exc:
        assert "INVALID_LIFECYCLE" in str(exc)
    else:
        raise AssertionError("invalid lifecycle jump was accepted")


def test_development_gate_preserves_order():
    runtime = VLNSRuntime()
    state = ChangeState.PROPOSED
    for target in (
        ChangeState.ANALYZED,
        ChangeState.CANDIDATE,
        ChangeState.TESTED,
        ChangeState.VERIFIED,
        ChangeState.APPROVED,
        ChangeState.BUILT,
        ChangeState.DEPLOYED,
        ChangeState.OBSERVED,
        ChangeState.ACCEPTED,
    ):
        state = runtime.development_transition(state, target)
    assert state is ChangeState.ACCEPTED
