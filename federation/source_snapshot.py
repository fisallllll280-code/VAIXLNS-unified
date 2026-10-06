"""Deterministic source snapshot and change-detection contract.

This module does not contact GitHub. It gives the canonical system a typed
manifest format that a GitHub adapter can populate and a deterministic
comparator can verify.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Tuple


def _hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class SnapshotEntry:
    path: str
    digest: str
    size: int = 0


@dataclass(frozen=True)
class SnapshotManifest:
    repository: str
    ref: str
    commit: str
    tree: str
    entries: Tuple[SnapshotEntry, ...]
    captured_at: str = ""

    @property
    def fingerprint(self) -> str:
        return _hash(asdict(self))

    @classmethod
    def from_entries(
        cls,
        repository: str,
        ref: str,
        commit: str,
        tree: str,
        entries: Iterable[SnapshotEntry],
        captured_at: str = "",
    ) -> "SnapshotManifest":
        normalized = tuple(sorted(entries, key=lambda item: item.path))
        return cls(repository, ref, commit, tree, normalized, captured_at)


@dataclass(frozen=True)
class SnapshotDelta:
    changed: Tuple[str, ...]
    added: Tuple[str, ...]
    removed: Tuple[str, ...]
    commit_changed: bool
    tree_changed: bool

    @property
    def changed_count(self) -> int:
        return len(self.changed) + len(self.added) + len(self.removed)


class SnapshotDetector:
    @staticmethod
    def compare(previous: SnapshotManifest, current: SnapshotManifest) -> SnapshotDelta:
        before = {entry.path: entry.digest for entry in previous.entries}
        after = {entry.path: entry.digest for entry in current.entries}
        changed = tuple(sorted(path for path in before.keys() & after.keys() if before[path] != after[path]))
        added = tuple(sorted(after.keys() - before.keys()))
        removed = tuple(sorted(before.keys() - after.keys()))
        return SnapshotDelta(
            changed=changed,
            added=added,
            removed=removed,
            commit_changed=previous.commit != current.commit,
            tree_changed=previous.tree != current.tree,
        )
