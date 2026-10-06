"""Deterministic Intent -> V-IR -> Candidate Plan compiler."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Tuple


class VIRError(ValueError):
    pass


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class Intent:
    intent_id: str
    actor_id: str
    objective: str
    capability: str
    inputs: Mapping[str, Any]
    constraints: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidatePlan:
    intent_id: str
    actor_id: str
    objective: str
    capability: str
    normalized_inputs: Mapping[str, Any]
    constraints: Tuple[str, ...]
    plan_digest: str
    authority_required: bool = True


def compile_intent(intent: Intent) -> CandidatePlan:
    if not intent.intent_id:
        raise VIRError("INTENT_ID_REQUIRED")
    if not intent.actor_id:
        raise VIRError("ACTOR_ID_REQUIRED")
    if not intent.objective.strip():
        raise VIRError("OBJECTIVE_REQUIRED")
    if not intent.capability:
        raise VIRError("CAPABILITY_REQUIRED")
    normalized_inputs = json.loads(
        json.dumps(
            dict(intent.inputs),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    )
    constraints = tuple(dict.fromkeys(c.strip() for c in intent.constraints if c.strip()))
    body = {
        "intent_id": intent.intent_id,
        "actor_id": intent.actor_id,
        "objective": intent.objective.strip(),
        "capability": intent.capability,
        "normalized_inputs": normalized_inputs,
        "constraints": constraints,
        "authority_required": True,
    }
    return CandidatePlan(
        intent_id=intent.intent_id,
        actor_id=intent.actor_id,
        objective=body["objective"],
        capability=intent.capability,
        normalized_inputs=normalized_inputs,
        constraints=constraints,
        plan_digest=_digest(body),
    )
