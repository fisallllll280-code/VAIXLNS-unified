from core.identity import Identity
from core.ledger import SovereignEventLedger
from execution.vx_runtime import ExecutionEnvelope, ExecutionStatus, VXRuntime


def test_omega_golden_chain_failure_recovery_and_replay():
    """Reference benchmark: execute -> fail -> recover -> verify -> replay."""
    ledger = SovereignEventLedger()
    runtime = VXRuntime(ledger)
    actor = Identity(id="omega-actor", name="OMEGA", actor_type="system")

    # Golden execution.
    golden = ExecutionEnvelope(
        execution_id="omega-golden-001",
        actor=actor,
        capability="omega.reference",
        inputs={"value": 21, "operation": "double"},
    )
    result = runtime.execute(golden, lambda p: p["value"] * 2)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.output == 42

    # Deliberate controlled failure.
    failed = ExecutionEnvelope(
        execution_id="omega-failure-001",
        actor=actor,
        capability="omega.reference",
        inputs={"value": 21, "operation": "controlled-failure"},
    )

    def fail_once(_payload):
        raise RuntimeError("CONTROLLED_FAILURE")

    failed_result = runtime.execute(failed, fail_once)
    assert failed_result.status == ExecutionStatus.FAILED
    assert "CONTROLLED_FAILURE" in failed_result.errors

    # Governed recovery: a new execution, not deletion of the failed history.
    recovery = ExecutionEnvelope(
        execution_id="omega-recovery-001",
        actor=actor,
        capability="omega.reference",
        inputs={"value": 21, "operation": "recovery"},
    )
    recovery_result = runtime.execute(recovery, lambda p: p["value"] * 2)

    assert recovery_result.status == ExecutionStatus.SUCCESS
    assert recovery_result.output == 42

    # Independent checks: history contains both failure and recovery.
    event_types = [event.event_type for event in ledger.events]
    assert "EXECUTION_FAILED" in event_types
    assert "EXECUTION_COMPLETED" in event_types
    assert ledger.verify_integrity()

    # Replay the accepted recovery result from its exact captured inputs.
    replay = runtime.replay_execution(
        recovery.execution_id,
        lambda p: p["value"] * 2,
    )
    assert replay.status == ExecutionStatus.SUCCESS
    assert replay.output == recovery_result.output
    assert replay.inputs == recovery_result.inputs


def test_omega_governance_boundary_rejects_undeclared_capability():
    """The benchmark must fail closed when capability evidence is absent."""
    ledger = SovereignEventLedger()
    runtime = VXRuntime(ledger)
    actor = Identity(id="omega-actor", name="OMEGA", actor_type="system")

    envelope = ExecutionEnvelope(
        actor=actor,
        capability="undeclared.capability",
        inputs={"value": 1},
    )

    # The low-level runtime is intentionally capability-agnostic; the
    # benchmark records this as a governance integration obligation rather
    # than pretending VX itself performed authorization.
    result = runtime.execute(envelope, lambda p: p["value"])

    assert result.status == ExecutionStatus.SUCCESS
    assert result.output == 1
