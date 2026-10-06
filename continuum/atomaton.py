"""Ephemeral execution identity for VX-CONTINUUM.

An Atomaton is not a sovereign Agent identity. It is a bounded execution
instance whose lifetime ends after observation/proof. Canonical authority
remains outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


class AtomatonState(str, Enum):
    SPAWNED = "SPAWNED"
    BOUND = "BOUND"
    VALIDATED = "VALIDATED"
    EXECUTING = "EXECUTING"
    OBSERVED = "OBSERVED"
    PROVED = "PROVED"
    DISSOLVED = "DISSOLVED"
    FAILED = "FAILED"


_ALLOWED = {
    AtomatonState.SPAWNED: {AtomatonState.BOUND, AtomatonState.FAILED},
    AtomatonState.BOUND: {AtomatonState.VALIDATED, AtomatonState.FAILED},
    AtomatonState.VALIDATED: {AtomatonState.EXECUTING, AtomatonState.FAILED},
    AtomatonState.EXECUTING: {AtomatonState.OBSERVED, AtomatonState.FAILED},
    AtomatonState.OBSERVED: {AtomatonState.PROVED, AtomatonState.FAILED},
    AtomatonState.PROVED: {AtomatonState.DISSOLVED},
    AtomatonState.DISSOLVED: set(),
    AtomatonState.FAILED: {AtomatonState.DISSOLVED},
}


@dataclass(frozen=True)
class Atomaton:
    execution_id: str
    parent_intent_id: str
    capability_id: str
    contract_id: str
    resource_boundary: Mapping[str, Any]
    input_cids: tuple[str, ...]
    output_cids: tuple[str, ...] = ()
    state: AtomatonState = AtomatonState.SPAWNED
    evidence_cids: tuple[str, ...] = ()
    trace_digest: str = ""

    @classmethod
    def spawn(
        cls,
        *,
        execution_id: str,
        parent_intent_id: str,
        capability_id: str,
        contract_id: str,
        resource_boundary: Mapping[str, Any],
        input_cids: tuple[str, ...] = (),
    ) -> "Atomaton":
        if not execution_id or not parent_intent_id:
            raise ValueError("EXECUTION_AND_PARENT_INTENT_REQUIRED")
        if not capability_id or not contract_id:
            raise ValueError("CAPABILITY_AND_CONTRACT_REQUIRED")
        return cls(
            execution_id=execution_id,
            parent_intent_id=parent_intent_id,
            capability_id=capability_id,
            contract_id=contract_id,
            resource_boundary=dict(resource_boundary),
            input_cids=tuple(input_cids),
        )

    def transition(self, target: AtomatonState, *, evidence_cids=(), output_cids=()) -> "Atomaton":
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"INVALID_ATOMATON_TRANSITION:{self.state}->{target}")
        updated = replace(
            self,
            state=target,
            evidence_cids=self.evidence_cids + tuple(evidence_cids),
            output_cids=self.output_cids + tuple(output_cids),
        )
        trace = {
            "execution_id": updated.execution_id,
            "parent_intent_id": updated.parent_intent_id,
            "state": updated.state.value,
            "inputs": updated.input_cids,
            "outputs": updated.output_cids,
            "evidence": updated.evidence_cids,
        }
        return replace(updated, trace_digest=_digest(trace))
