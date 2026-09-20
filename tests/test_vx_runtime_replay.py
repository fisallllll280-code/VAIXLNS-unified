from core.identity import Identity
from core.ledger import SovereignEventLedger
from execution.vx_runtime import ExecutionEnvelope, ExecutionStatus, VXRuntime


def test_execution_captures_hashes_and_replays_exact_inputs():
    ledger = SovereignEventLedger()
    runtime = VXRuntime(ledger)
    actor = Identity(id="actor-1", name="test", actor_type="system")

    envelope = ExecutionEnvelope(
        actor=actor,
        capability="sum",
        inputs={"a": 2, "b": 3},
    )

    result = runtime.execute(envelope, lambda p: p["a"] + p["b"])

    assert result.status == ExecutionStatus.SUCCESS
    assert result.inputs == {"a": 2, "b": 3}
    event = ledger.events[-1]
    assert event.input_hash
    assert event.output_hash
    assert event.input_hash == runtime._hash(envelope.inputs)
    assert event.output_hash == runtime._hash(result.output)

    replay = runtime.replay_execution(
        envelope.execution_id,
        lambda p: p["a"] + p["b"],
    )
    assert replay.status == ExecutionStatus.SUCCESS
    assert replay.output == result.output


def test_replay_detects_non_deterministic_output():
    ledger = SovereignEventLedger()
    runtime = VXRuntime(ledger)
    envelope = ExecutionEnvelope(inputs={"value": 7})

    result = runtime.execute(envelope, lambda p: p["value"] * 2)
    assert result.status == ExecutionStatus.SUCCESS

    replay = runtime.replay_execution(
        envelope.execution_id,
        lambda p: p["value"] * 3,
    )
    assert replay.status == ExecutionStatus.FAILED
    assert "NON_DETERMINISTIC_OUTPUT" in replay.errors
