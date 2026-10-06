"""Factory for bounded VX-CONTINUUM Atomatons."""
from __future__ import annotations
from typing import Any, Mapping
from continuum.atomaton import Atomaton

def spawn(*, execution_id: str, intent_id: str, capability_id: str,
          contract_id: str, resource_boundary: Mapping[str, Any] | None = None,
          input_cids: tuple[str, ...] = ()) -> Atomaton:
    return Atomaton.spawn(
        execution_id=execution_id,
        parent_intent_id=intent_id,
        capability_id=capability_id,
        contract_id=contract_id,
        resource_boundary=resource_boundary or {},
        input_cids=input_cids,
    )
