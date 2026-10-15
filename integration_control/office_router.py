"""Fail-closed, proposal-only routing against an explicitly pinned office registry.

This module never invokes a tool, calls an external endpoint, writes canonical state,
or grants execution authority. It only validates an operator-supplied registry and
returns a deterministic route preview with blockers and a request digest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from integration_control.gateway import (
    ExternalIntegration,
    ExternalIntegrationGate,
    IntegrationClass,
    IntegrationPolicy,
)

MAX_REGISTRY_BYTES = 2_000_000
KIND_MAP = {
    "registry_artifact": IntegrationClass.DATA_SOURCE,
    "system_capability": IntegrationClass.CONNECTOR,
    "source_script": IntegrationClass.TOOL,
    "external_api_adapter": IntegrationClass.API,
    "model_provider_adapter": IntegrationClass.MODEL,
    "server_endpoint": IntegrationClass.SERVER,
    "repository_adapter": IntegrationClass.REPOSITORY,
}


class OfficeRoutingError(ValueError):
    """A safe, stable error code for office-registry and route-preview failures."""


class OfficeRoutingService:
    def __init__(self, registry_path: str | Path | None) -> None:
        raw = str(registry_path).strip() if registry_path is not None else ""
        self._registry_path = Path(raw).expanduser() if raw else None

    def _load(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        path = self._registry_path
        if path is None:
            raise OfficeRoutingError("OFFICE_REGISTRY_NOT_CONFIGURED")
        if not path.is_absolute():
            raise OfficeRoutingError("OFFICE_REGISTRY_PATH_MUST_BE_ABSOLUTE")
        try:
            if not path.is_file():
                raise OfficeRoutingError("OFFICE_REGISTRY_NOT_CONFIGURED")
            if path.stat().st_size > MAX_REGISTRY_BYTES:
                raise OfficeRoutingError("OFFICE_REGISTRY_TOO_LARGE")
            registry = json.loads(path.read_text(encoding="utf-8"))
        except OfficeRoutingError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise OfficeRoutingError("OFFICE_REGISTRY_UNREADABLE") from None
        if not isinstance(registry, dict):
            raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
        semantics = registry.get("semantics")
        if (
            registry.get("schema_version") != "1.0.0"
            or registry.get("registry_id") != "VAIXLNS-OFFICE-FABRIC"
            or not isinstance(semantics, dict)
            or semantics.get("zero_loss") is not True
            or semantics.get("no_implicit_admission") is not True
        ):
            raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
        offices = registry.get("offices")
        systems = registry.get("systems")
        tools = registry.get("tool_integrations")
        if not all(isinstance(value, list) for value in (offices, systems, tools)):
            raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
        office_index = self._unique_index(offices, "office_id", "OFFICE_REGISTRY_INVALID")
        system_index = self._unique_index(systems, "system_id", "OFFICE_REGISTRY_INVALID")
        tool_index = self._unique_index(tools, "tool_id", "OFFICE_REGISTRY_INVALID")
        for office in offices:
            if any(item not in system_index for item in office.get("owner_system_ids", [])):
                raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
            if any(item not in tool_index for item in office.get("tool_ids", [])):
                raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
        for tool in tools:
            if tool.get("office_id") not in office_index:
                raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
            if tool.get("owner_system_id") not in system_index:
                raise OfficeRoutingError("OFFICE_REGISTRY_INVALID")
        return registry, office_index, system_index, tool_index

    @staticmethod
    def _unique_index(items: list[Any], key: str, error_code: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                raise OfficeRoutingError(error_code)
            value = item.get(key)
            if not isinstance(value, str) or not value or value in result:
                raise OfficeRoutingError(error_code)
            result[value] = item
        return result

    @staticmethod
    def _integration_decision(tool: dict[str, Any]) -> dict[str, Any]:
        kind = KIND_MAP.get(str(tool.get("kind", "")))
        if kind is None:
            return {
                "state": "QUARANTINED",
                "reasons": ["TOOL_KIND_UNRECOGNIZED"],
            }
        capabilities = tool.get("capabilities", [])
        if not isinstance(capabilities, list) or any(not isinstance(value, str) for value in capabilities):
            return {
                "state": "QUARANTINED",
                "reasons": ["TOOL_CAPABILITIES_INVALID"],
            }
        contract = tool.get("contract")
        contract = contract if isinstance(contract, dict) else {}
        contract_id = str(contract.get("contract_id", "")).strip()
        contract_version = str(contract.get("version", "")).strip()
        if contract_id and contract_version:
            contract_version = f"{contract_id}@{contract_version}"
        else:
            contract_version = ""
        endpoint = str(tool.get("endpoint") or tool.get("endpoint_ref") or "").strip()
        dependency_fingerprint = str(
            tool.get("dependency_fingerprint") or contract.get("dependency_fingerprint") or ""
        ).strip()
        environment_fingerprint = str(
            tool.get("environment_fingerprint") or contract.get("environment_fingerprint") or ""
        ).strip()
        integration = ExternalIntegration(
            integration_id=str(tool.get("tool_id", "")),
            name=str(tool.get("name", tool.get("tool_id", ""))),
            kind=kind,
            endpoint=endpoint,
            capabilities=tuple(capabilities),
            contract_version=contract_version,
            dependency_fingerprint=dependency_fingerprint,
            environment_fingerprint=environment_fingerprint,
            owner=str(tool.get("owner_system_id", "")),
            lineage=tuple(str(value) for value in tool.get("source_refs", []) if isinstance(value, str)),
        )
        allowed_capabilities = frozenset(
            value.strip()
            for value in os.getenv("VAIXLNS_OFFICE_ALLOWED_CAPABILITIES", "").split(",")
            if value.strip()
        )
        forbidden_endpoints = frozenset(
            value.strip()
            for value in os.getenv("VAIXLNS_OFFICE_FORBIDDEN_ENDPOINTS", "").split(",")
            if value.strip()
        )
        policy = IntegrationPolicy(
            allowed_kinds=frozenset(IntegrationClass),
            allowed_capabilities=allowed_capabilities,
            forbidden_endpoints=forbidden_endpoints,
            require_owner=True,
            require_contract=True,
            require_dependency_fingerprint=True,
            require_environment_fingerprint=True,
        )
        decision = ExternalIntegrationGate().admit(
            integration,
            policy,
            verified=False,
            explicit_authority=False,
        )
        reasons = list(decision.reasons)
        if decision.state.value != "ADMITTED":
            reasons.append("EXTERNAL_INTEGRATION_NOT_ADMITTED")
        if kind in {IntegrationClass.API, IntegrationClass.SERVER, IntegrationClass.MODEL, IntegrationClass.CONNECTOR} and not endpoint:
            reasons.append("ENDPOINT_MISSING")
        return {
            "state": decision.state.value if decision.state.value != "ADMITTED" else "ADMITTED",
            "reasons": sorted(set(reasons)),
        }

    def list_offices(self) -> dict[str, Any]:
        registry, offices, systems, tools = self._load()
        unresolved = sorted(
            system_id for system_id, system in systems.items()
            if system.get("status") == "IDENTITY_UNVERIFIED"
        )
        return {
            "status": "PROPOSAL_ONLY",
            "registry_id": registry["registry_id"],
            "registry_status": registry.get("status", "UNKNOWN"),
            "office_count": len(offices),
            "system_surface_count": len(systems),
            "tool_integration_count": len(tools),
            "unresolved_identity_systems": unresolved,
            "offices": [
                {
                    "office_id": office["office_id"],
                    "name": office.get("name", ""),
                    "status": office.get("status", "UNKNOWN"),
                    "tool_ids": list(office.get("tool_ids", [])),
                    "owner_system_ids": list(office.get("owner_system_ids", [])),
                }
                for office in registry["offices"]
            ],
            "dispatch_allowed": False,
            "external_calls_made": False,
        }

    def preview(self, office_id: str, intent: str) -> dict[str, Any]:
        if not isinstance(office_id, str) or not office_id.strip() or len(office_id) > 120:
            raise OfficeRoutingError("OFFICE_ID_INVALID")
        if not isinstance(intent, str) or not intent.strip() or len(intent) > 2000:
            raise OfficeRoutingError("INTENT_INVALID")
        registry, offices, systems, tools = self._load()
        office = offices.get(office_id.strip())
        if office is None:
            raise OfficeRoutingError("OFFICE_NOT_FOUND")
        blockers: list[str] = []
        if registry.get("status") != "CANONICAL":
            blockers.append("OFFICE_REGISTRY_NOT_ADMITTED")
        if office.get("status") not in {"ACTIVE", "ACTIVE_REFERENCE"}:
            blockers.append("OFFICE_NOT_ADMITTED")
        for system_id in office.get("owner_system_ids", []):
            if systems[system_id].get("status") == "IDENTITY_UNVERIFIED":
                blockers.append(f"SYSTEM_IDENTITY_UNVERIFIED:{system_id}")
        candidates = []
        for tool_id in office.get("tool_ids", []):
            tool = tools[tool_id]
            status = tool.get("status", "UNKNOWN")
            access_mode = tool.get("access_mode", "UNKNOWN")
            if status in {"NOT_CONFIGURED", "PROPOSED_NOT_ADMITTED", "SPECIFICATION_ONLY"}:
                blockers.append(f"TOOL_NOT_READY:{tool_id}:{status}")
            if access_mode == "GOVERNED_EXECUTION":
                blockers.append(f"EXECUTION_REQUIRES_SEPARATE_ADMISSION:{tool_id}")
            gate = self._integration_decision(tool)
            if gate["state"] != "ADMITTED":
                blockers.extend(
                    f"INTEGRATION_GATE:{tool_id}:{reason}"
                    for reason in gate["reasons"]
                )
            candidates.append({
                "tool_id": tool_id,
                "status": status,
                "access_mode": access_mode,
                "capabilities": list(tool.get("capabilities", [])),
                "integration_gate_state": gate["state"],
                "integration_gate_reasons": gate["reasons"],
                "candidate_only": True,
            })
        if not candidates:
            blockers.append("NO_REGISTERED_TOOLS")
        canonical_request = json.dumps(
            {"registry_id": registry["registry_id"], "office_id": office_id.strip(),
             "intent_sha256": hashlib.sha256(intent.strip().encode("utf-8")).hexdigest()},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        request_id = "office-route-" + hashlib.sha256(canonical_request).hexdigest()[:24]
        blockers = sorted(set(blockers))
        return {
            "status": "HOLD" if blockers else "PROPOSAL_ONLY",
            "request_id": request_id,
            "office_id": office_id.strip(),
            "intent_sha256": hashlib.sha256(intent.strip().encode("utf-8")).hexdigest(),
            "candidate_tools": candidates,
            "blockers": blockers,
            "authority_ceiling": "PROPOSE_ONLY",
            "dispatch_allowed": False,
            "external_calls_made": False,
            "canonical_write": False,
            "human_admission_required": True,
        }


__all__ = ["OfficeRoutingError", "OfficeRoutingService"]
