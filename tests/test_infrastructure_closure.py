import json
import subprocess
import sys
from pathlib import Path

from infra.durable_store import DurableEventStore
from simulation.worker_bridge import SolverBridge


def test_durable_store_survives_reopen(tmp_path: Path) -> None:
    db = tmp_path / "events.db"
    with DurableEventStore(db) as store:
        event = store.append(
            event_id="e1",
            event_type="EXECUTION_COMPLETED",
            aggregate_id="op-1",
            actor_id="VX",
            capability="sum",
            payload={"state": {"value": 42}},
        )
        snapshot = store.save_snapshot(
            snapshot_id="s1",
            state={"value": 42},
            lineage=[event.event_id],
        )
        assert store.verify_integrity()
        assert store.verify_snapshot(snapshot)

    with DurableEventStore(db) as reopened:
        assert reopened.verify_integrity()
        latest = reopened.latest_snapshot()
        assert latest is not None
        assert latest.state == {"value": 42}
        assert latest.ledger_root == event.event_hash
        assert reopened.verify_snapshot(latest)


def test_solver_bridge_isolated_json_roundtrip() -> None:
    code = (
        "import json,sys; "
        "p=json.loads(sys.stdin.read()); "
        "print(json.dumps({'value': p['a'] + p['b']}))"
    )
    bridge = SolverBridge([sys.executable, "-c", code])
    result = bridge.run({"a": 20, "b": 22})
    assert result.ok
    assert result.output == {"value": 42}


def test_server_config_is_secret_free() -> None:
    data = json.loads(Path("config/server_endpoints.v1.json").read_text(encoding="utf-8"))
    text = json.dumps(data)
    assert "172." not in text
    assert "password" not in text.lower()
    assert "token_env" in text


def test_nats_adapter_is_optional_at_import() -> None:
    subprocess.run(
        [sys.executable, "-c", "from distributed.nats_backend import NatsJetStreamBackend"],
        check=True,
    )
