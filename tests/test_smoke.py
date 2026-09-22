from core.identity import Identity
from core.ledger import SovereignEventLedger
from execution.vx_runtime import ExecutionEnvelope, VXRuntime

def test_full_smoke_cycle():
    ledger = SovereignEventLedger()
    runtime = VXRuntime(ledger)
    actor = Identity(id="smoke-test", name="smoke", actor_type="system")
    envelope = ExecutionEnvelope(
        actor=actor,
        capability="echo",
        inputs={"message": "ok"},
    )
    result = runtime.execute(envelope, lambda payload: payload["message"])
    replay = runtime.replay_execution(
        envelope.execution_id,
        lambda payload: payload["message"],
    )

    assert result.is_success()
    assert replay.is_success()
    assert replay.output == result.output
    assert ledger.verify_integrity()
