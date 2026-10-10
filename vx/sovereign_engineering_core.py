"""VX Sovereign Engineering Core v1.

A deterministic, proposal-first engineering coordinator. It inventories declared
systems, discovers structural gaps and overlaps, synthesizes reviewable plans,
and admits execution only through injected proof and authorization callbacks.
It does not discover the network, call model providers, or execute tools itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Iterable, Mapping, Sequence

SCHEMA_VERSION = "vx-sovereign-engineering-core/v1"
VALID_STATES = {"SPECIFIED", "IMPLEMENTED", "CI_VERIFIED", "RUNNING", "PROVEN"}
FORBIDDEN_AUTONOMOUS_ACTIONS = {
    "canonical-write", "production-deploy", "self-promote", "financial-transfer",
    "destructive-delete", "secret-export",
}


def stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SystemRecord:
    system_id: str
    revision: str
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    state: str = "SPECIFIED"
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> "SystemRecord":
        required = ("system_id", "revision", "capabilities")
        if any(not isinstance(item.get(key), str) or not item[key].strip()
               for key in required[:2]):
            raise ValueError("SYSTEM_ID_AND_REVISION_REQUIRED")
        capabilities = item.get("capabilities")
        if not isinstance(capabilities, (list, tuple)) or not all(
            isinstance(x, str) and x.strip() for x in capabilities
        ):
            raise ValueError("CAPABILITIES_MUST_BE_NONEMPTY_STRINGS")
        state = item.get("state", "SPECIFIED")
        if state not in VALID_STATES:
            raise ValueError("INVALID_EVIDENCE_STATE")
        def strings(key: str) -> tuple[str, ...]:
            value = item.get(key, ())
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(x, str) and x.strip() for x in value
            ):
                raise ValueError(f"{key.upper()}_MUST_BE_STRINGS")
            return tuple(sorted(set(value)))
        return cls(
            system_id=item["system_id"].strip(),
            revision=item["revision"].strip(),
            capabilities=tuple(sorted(set(capabilities))),
            dependencies=strings("dependencies"),
            conflicts=strings("conflicts"),
            state=state,
            evidence_refs=strings("evidence_refs"),
        )


def inventory_digest(records: Sequence[SystemRecord]) -> str:
    return stable_digest([asdict(r) for r in sorted(records, key=lambda x: x.system_id)])


def understand(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Normalize a declared inventory; duplicate IDs fail closed."""
    records = [SystemRecord.from_mapping(item) for item in items]
    ids = [r.system_id for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_SYSTEM_ID")
    records.sort(key=lambda x: x.system_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "INVENTORY_NORMALIZED",
        "records": [asdict(r) for r in records],
        "inventory_digest": inventory_digest(records),
        "external_discovery_performed": False,
    }


def discover(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Report gaps/overlaps as candidates; never auto-delete or merge systems."""
    raw = inventory.get("records")
    if not isinstance(raw, list):
        raise ValueError("NORMALIZED_INVENTORY_REQUIRED")
    records = [SystemRecord.from_mapping(x) for x in raw]
    ids = {r.system_id for r in records}
    owners: dict[str, list[str]] = {}
    for record in records:
        for capability in record.capabilities:
            owners.setdefault(capability, []).append(record.system_id)
    gaps = [
        {"system_id": r.system_id, "missing_dependency": dep}
        for r in records for dep in r.dependencies if dep not in ids
    ]
    overlaps = [
        {"capability": cap, "providers": sorted(set(provider_ids))}
        for cap, provider_ids in sorted(owners.items()) if len(set(provider_ids)) > 1
    ]
    conflicts = [
        {"system_id": r.system_id, "conflicting_system": other}
        for r in records for other in r.conflicts if other in ids
    ]
    return {
        "state": "FINDINGS_AVAILABLE" if (gaps or overlaps or conflicts) else "NO_STRUCTURAL_FINDINGS",
        "inventory_digest": inventory.get("inventory_digest"),
        "missing_dependencies": gaps,
        "capability_overlaps": overlaps,
        "declared_conflicts": conflicts,
        "resolution_performed": False,
    }


def synthesize(inventory: Mapping[str, Any], findings: Mapping[str, Any],
               objective: str) -> dict[str, Any]:
    """Produce a deterministic review plan, not executable commands."""
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("OBJECTIVE_REQUIRED")
    if inventory.get("inventory_digest") != findings.get("inventory_digest"):
        raise ValueError("INVENTORY_FINDINGS_DIGEST_MISMATCH")
    tasks: list[dict[str, Any]] = []
    for i, gap in enumerate(findings.get("missing_dependencies", []), 1):
        tasks.append({"task_id": f"T{i:04d}", "kind": "RESOLVE_DEPENDENCY",
                      "target": gap["system_id"], "detail": gap["missing_dependency"],
                      "requires_human_review": True})
    offset = len(tasks)
    for i, overlap in enumerate(findings.get("capability_overlaps", []), offset + 1):
        tasks.append({"task_id": f"T{i:04d}", "kind": "COMPARE_CAPABILITY_PROVIDERS",
                      "target": overlap["capability"], "detail": overlap["providers"],
                      "requires_human_review": True})
    offset = len(tasks)
    for i, conflict in enumerate(findings.get("declared_conflicts", []), offset + 1):
        tasks.append({"task_id": f"T{i:04d}", "kind": "RECONCILE_DECLARED_CONFLICT",
                      "target": conflict["system_id"], "detail": conflict["conflicting_system"],
                      "requires_human_review": True})
    plan = {
        "schema_version": SCHEMA_VERSION,
        "objective": objective.strip(),
        "inventory_digest": inventory["inventory_digest"],
        "tasks": tasks,
        "state": "REVIEWABLE_PLAN" if tasks else "NO_CHANGE_PROPOSED",
        "execution_performed": False,
        "canonical_write_performed": False,
        "authority_granted": False,
    }
    plan["plan_digest"] = stable_digest(plan)
    return plan


def prove_candidate(plan: Mapping[str, Any], *, simulation_receipt: str,
                    test_receipt: str, verifier: Callable[[Mapping[str, Any]], bool],
                    authorizer: Callable[[Mapping[str, Any]], bool]) -> dict[str, Any]:
    """Require receipts and independent callbacks; return a candidate only."""
    if not simulation_receipt or not test_receipt:
        return {"state": "BLOCKED", "reason": "SIMULATION_AND_TEST_RECEIPTS_REQUIRED",
                "execution_performed": False, "authority_granted": False}
    if not verifier(plan):
        return {"state": "BLOCKED", "reason": "INDEPENDENT_VERIFICATION_FAILED",
                "execution_performed": False, "authority_granted": False}
    if not authorizer(plan):
        return {"state": "BLOCKED", "reason": "AUTHORIZATION_DENIED",
                "execution_performed": False, "authority_granted": False}
    return {
        "state": "ELIGIBLE_FOR_SEPARATE_EXECUTION_GATE",
        "plan_digest": plan.get("plan_digest"),
        "simulation_receipt_digest": stable_digest(simulation_receipt),
        "test_receipt_digest": stable_digest(test_receipt),
        "verification_callback_passed": True,
        "authorization_callback_passed": True,
        "execution_performed": False,
        "authority_granted": False,
    }


def federation_candidates(inventory: Mapping[str, Any],
                          required_capabilities: Iterable[str]) -> dict[str, Any]:
    """Resolve only declared capabilities; no connector is invoked."""
    records = [SystemRecord.from_mapping(x) for x in inventory.get("records", [])]
    required = sorted(set(required_capabilities))
    matches = {
        capability: sorted(r.system_id for r in records if capability in r.capabilities)
        for capability in required
    }
    unresolved = [cap for cap, providers in matches.items() if not providers]
    return {
        "state": "CAPABILITY_GAPS" if unresolved else "CANDIDATES_AVAILABLE",
        "matches": matches,
        "unresolved_capabilities": unresolved,
        "network_calls_performed": False,
        "tools_invoked": False,
    }


def propose_evolution(observation: Mapping[str, Any], objective: str) -> dict[str, Any]:
    """Convert a measured observation into a reviewable, non-mutating proposal."""
    if not observation.get("evidence_ref") or not observation.get("observation_digest"):
        return {"state": "BLOCKED", "reason": "OBSERVATION_EVIDENCE_REQUIRED",
                "canonical_write_performed": False}
    proposal = {
        "schema_version": SCHEMA_VERSION,
        "objective": objective,
        "observation_digest": observation["observation_digest"],
        "evidence_ref": observation["evidence_ref"],
        "state": "EVOLUTION_PROPOSAL",
        "approval_required": True,
        "canonical_write_performed": False,
        "self_promotion_performed": False,
    }
    proposal["proposal_digest"] = stable_digest(proposal)
    return proposal
