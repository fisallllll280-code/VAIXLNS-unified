import json

from integration.boot import load_registry, run_smoke


def test_federation_registry_is_unique_and_canonical():
    registry = load_registry()
    repos = [entry["repository"] for entry in registry["repositories"]]
    assert len(repos) == len(set(repos))
    assert registry["canonical_namespace"] == "VAIXLNS"
    assert any(entry["system"] == "V" for entry in registry["repositories"])
    assert any(entry["system"] == "VX" for entry in registry["repositories"])


def test_federated_boot_smoke():
    report = run_smoke()
    assert report.smoke_passed is True
    assert report.execution_status == "success"
    assert report.replay_status == "success"
    assert report.ledger_integrity is True
    assert report.state == "active"
    assert report.operational_state == "PARTIAL"
