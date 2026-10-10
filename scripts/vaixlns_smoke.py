from core.identity import Identity
from core.ledger import SovereignEventLedger
from execution.vx_runtime import ExecutionEnvelope, VXRuntime

def main() -> None:
    ledger = SovereignEventLedger()
    runtime = VXRuntime(ledger)
    actor = Identity(id="smoke-system", name="VAIXLNS Smoke", actor_type="system")
    envelope = ExecutionEnvelope(
        actor=actor,
        capability="echo",
        inputs={"message": "VAIXLNS"},
    )
    result = runtime.execute(envelope, lambda payload: payload["message"])
    if not result.is_success():
        raise SystemExit(f"execution failed: {result.to_dict()}")

    replay = runtime.replay_execution(
        envelope.execution_id,
        lambda payload: payload["message"],
    )
    if not replay.is_success() or replay.output != result.output:
        raise SystemExit(f"replay failed: {replay.to_dict()}")

    if not ledger.verify_integrity():
        raise SystemExit("ledger integrity verification failed")

    print("VAIXLNS_UNIFIED_SMOKE=PASS")
    print(f"execution_id={envelope.execution_id}")
    print(f"output={result.output}")
    print(f"events={len(ledger.events)}")

if __name__ == "__main__":
    main()
