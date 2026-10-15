"""Contract tests for deterministic, non-dispatching office route previews."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from integration_control.office_router import OfficeRoutingError, OfficeRoutingService


def registry_fixture() -> dict:
    return {
        "schema_version": "1.0.0",
        "registry_id": "VAIXLNS-OFFICE-FABRIC",
        "status": "PROPOSED_IMPLEMENTATION_SEED",
        "semantics": {"zero_loss": True, "no_implicit_admission": True},
        "offices": [{
            "office_id": "OFF-TEST", "name": "Test Office", "status": "ACTIVE_REFERENCE",
            "owner_system_ids": ["SYS-VAIXLNS"], "tool_ids": ["TOOL-READ"],
        }],
        "systems": [{"system_id": "SYS-VAIXLNS", "status": "CANONICAL"}],
        "tool_integrations": [{
            "tool_id": "TOOL-READ", "office_id": "OFF-TEST",
            "owner_system_id": "SYS-VAIXLNS", "status": "SOURCE_IMPLEMENTED",
            "access_mode": "READ_ONLY", "capabilities": ["read_status"],
        }],
    }


def write_registry(tmp_path: Path, data: dict | None = None) -> Path:
    path = tmp_path / "office-registry.json"
    path.write_text(json.dumps(data or registry_fixture()), encoding="utf-8")
    return path


def test_preview_is_deterministic_and_never_dispatches(tmp_path):
    router = OfficeRoutingService(write_registry(tmp_path))
    first = router.preview("OFF-TEST", "Review readiness")
    second = router.preview("OFF-TEST", "Review readiness")

    assert first == second
    assert first["status"] == "HOLD"
    assert first["request_id"].startswith("office-route-")
    assert first["candidate_tools"][0]["tool_id"] == "TOOL-READ"
    assert first["dispatch_allowed"] is False
    assert first["external_calls_made"] is False
    assert first["canonical_write"] is False
    assert "OFFICE_REGISTRY_NOT_ADMITTED" in first["blockers"]


def test_unresolved_identity_blocks_route(tmp_path):
    data = registry_fixture()
    data["systems"][0]["status"] = "IDENTITY_UNVERIFIED"
    result = OfficeRoutingService(write_registry(tmp_path, data)).preview("OFF-TEST", "Find a source")
    assert "SYSTEM_IDENTITY_UNVERIFIED:SYS-VAIXLNS" in result["blockers"]
    assert result["dispatch_allowed"] is False


def test_unknown_office_is_rejected(tmp_path):
    router = OfficeRoutingService(write_registry(tmp_path))
    with pytest.raises(OfficeRoutingError, match="OFFICE_NOT_FOUND"):
        router.preview("OFF-MISSING", "Review readiness")


def test_missing_registry_fails_closed():
    with pytest.raises(OfficeRoutingError, match="OFFICE_REGISTRY_NOT_CONFIGURED"):
        OfficeRoutingService(None).list_offices()


def test_relative_registry_path_is_rejected():
    with pytest.raises(OfficeRoutingError, match="OFFICE_REGISTRY_PATH_MUST_BE_ABSOLUTE"):
        OfficeRoutingService("registry/office_fabric.integration.v1.json").list_offices()


def test_duplicate_office_identity_rejected(tmp_path):
    data = registry_fixture()
    data["offices"].append(dict(data["offices"][0]))
    with pytest.raises(OfficeRoutingError, match="OFFICE_REGISTRY_INVALID"):
        OfficeRoutingService(write_registry(tmp_path, data)).list_offices()
