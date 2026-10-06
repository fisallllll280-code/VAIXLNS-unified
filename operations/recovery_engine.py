"""In-process recovery contract.

This is a deterministic recovery seam, not a durable distributed recovery
system. The caller is responsible for persisting snapshots when needed.
"""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
from typing import Any

@dataclass(frozen=True)
class RecoverySnapshot:
    snapshot_id: str
    state: dict[str, Any]
    ledger_root: str | None
    lineage: tuple[str, ...]

class RecoveryEngine:
    def checkpoint(self, *, snapshot_id: str, state: dict[str, Any], ledger_root: str | None, lineage: list[str] | tuple[str, ...] = ()) -> RecoverySnapshot:
        return RecoverySnapshot(snapshot_id, deepcopy(state), ledger_root, tuple(lineage))

    def restore(self, snapshot: RecoverySnapshot) -> dict[str, Any]:
        return deepcopy(snapshot.state)
