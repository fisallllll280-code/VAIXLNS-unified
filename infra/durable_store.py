"""Durable, dependency-free SQLite event and snapshot store.

Local-first: no external server is required. Events are append-only and
hash-linked; snapshots are crash-safe checkpoints for restart/recovery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StoredEvent:
    sequence: int
    event_id: str
    event_type: str
    aggregate_id: str
    actor_id: str
    capability: str
    payload: Mapping[str, Any]
    created_at: str
    previous_hash: str
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DurableSnapshot:
    snapshot_id: str
    created_at: str
    state: Mapping[str, Any]
    ledger_root: str
    lineage: tuple[str, ...]
    state_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DurableEventStore:
    """SQLite-backed event/snapshot store suitable for local and single-node use."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                state_json TEXT NOT NULL,
                ledger_root TEXT NOT NULL,
                lineage_json TEXT NOT NULL,
                state_hash TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    @property
    def last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else "GENESIS"

    def append(
        self,
        *,
        event_id: str,
        event_type: str,
        aggregate_id: str,
        actor_id: str,
        capability: str = "",
        payload: Mapping[str, Any] | None = None,
        created_at: str | None = None,
    ) -> StoredEvent:
        body = {
            "event_id": event_id,
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "actor_id": actor_id,
            "capability": capability,
            "payload": dict(payload or {}),
            "created_at": created_at or _now(),
        }
        with self._conn:
            previous_hash = self.last_hash
            event_hash = _digest({**body, "previous_hash": previous_hash})
            cur = self._conn.execute(
                """
                INSERT INTO events(
                    event_id,event_type,aggregate_id,actor_id,capability,
                    payload_json,created_at,previous_hash,event_hash
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    body["event_id"],
                    body["event_type"],
                    body["aggregate_id"],
                    body["actor_id"],
                    body["capability"],
                    _canonical(body["payload"]),
                    body["created_at"],
                    previous_hash,
                    event_hash,
                ),
            )
            sequence = int(cur.lastrowid)
        return StoredEvent(
            sequence=sequence,
            event_id=body["event_id"],
            event_type=body["event_type"],
            aggregate_id=body["aggregate_id"],
            actor_id=body["actor_id"],
            capability=body["capability"],
            payload=dict(body["payload"]),
            created_at=body["created_at"],
            previous_hash=previous_hash,
            event_hash=event_hash,
        )

    def events(self, aggregate_id: str | None = None) -> list[StoredEvent]:
        query = (
            "SELECT sequence,event_id,event_type,aggregate_id,actor_id,capability,"
            "payload_json,created_at,previous_hash,event_hash FROM events"
        )
        params: tuple[Any, ...] = ()
        if aggregate_id is not None:
            query += " WHERE aggregate_id=?"
            params = (aggregate_id,)
        query += " ORDER BY sequence"
        rows = self._conn.execute(query, params).fetchall()
        return [
            StoredEvent(
                sequence=row[0], event_id=row[1], event_type=row[2],
                aggregate_id=row[3], actor_id=row[4], capability=row[5],
                payload=json.loads(row[6]), created_at=row[7],
                previous_hash=row[8], event_hash=row[9],
            )
            for row in rows
        ]

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        for event in self.events():
            body = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_id": event.aggregate_id,
                "actor_id": event.actor_id,
                "capability": event.capability,
                "payload": dict(event.payload),
                "created_at": event.created_at,
                "previous_hash": previous,
            }
            if event.previous_hash != previous or _digest(body) != event.event_hash:
                return False
            previous = event.event_hash
        return True

    def save_snapshot(
        self,
        *,
        snapshot_id: str,
        state: Mapping[str, Any],
        lineage: Iterable[str] = (),
    ) -> DurableSnapshot:
        state_dict = dict(state)
        created_at = _now()
        ledger_root = self.last_hash
        lineage_tuple = tuple(lineage)
        state_hash = _digest({
            "snapshot_id": snapshot_id,
            "state": state_dict,
            "ledger_root": ledger_root,
            "lineage": list(lineage_tuple),
        })
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO snapshots(
                    snapshot_id,created_at,state_json,ledger_root,lineage_json,state_hash
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    snapshot_id, created_at, _canonical(state_dict), ledger_root,
                    _canonical(list(lineage_tuple)), state_hash,
                ),
            )
        return DurableSnapshot(
            snapshot_id=snapshot_id, created_at=created_at, state=state_dict,
            ledger_root=ledger_root, lineage=lineage_tuple, state_hash=state_hash,
        )

    def latest_snapshot(self) -> DurableSnapshot | None:
        row = self._conn.execute(
            "SELECT snapshot_id,created_at,state_json,ledger_root,lineage_json,state_hash "
            "FROM snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return DurableSnapshot(
            snapshot_id=row[0], created_at=row[1], state=json.loads(row[2]),
            ledger_root=row[3], lineage=tuple(json.loads(row[4])), state_hash=row[5],
        )

    def verify_snapshot(self, snapshot: DurableSnapshot) -> bool:
        return _digest({
            "snapshot_id": snapshot.snapshot_id,
            "state": dict(snapshot.state),
            "ledger_root": snapshot.ledger_root,
            "lineage": list(snapshot.lineage),
        }) == snapshot.state_hash

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DurableEventStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
