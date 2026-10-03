"""GitHub federation engine: discover, classify, audit and plan improvements across owned repositories."""
from __future__ import annotations
import json, os, urllib.request
from dataclasses import dataclass, asdict
from typing import Any

API = "https://api.github.com"
ROLE_RULES = (
    ("canonical", ("vaixlns", "vx", "nexent", "kernel", "runtime")),
    ("sdk-or-tooling", ("sdk", "tool", "adapter", "action", "workflow")),
    ("data", ("data", "dataset", "corpus", "memory")),
    ("experiment", ("test", "demo", "prototype", "experiment", "playground")),
)

@dataclass(frozen=True)
class RepositoryRecord:
    full_name: str
    name: str
    visibility: str
    default_branch: str
    archived: bool
    size_kb: int
    description: str
    role: str
    signals: tuple[str, ...]
    actions: tuple[str, ...]

class GitHubFederator:
    def __init__(self, token: str | None = None, owner: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.owner = owner or os.getenv("GITHUB_OWNER")
        if not self.token or not self.owner:
            raise ValueError("GITHUB_TOKEN and GITHUB_OWNER are required")

    def _get(self, path: str) -> Any:
        req = urllib.request.Request(
            API + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    def repositories(self) -> list[dict]:
        page, out = 1, []
        while True:
            batch = self._get(f"/user/repos?per_page=100&page={page}&affiliation=owner&sort=updated")
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return [r for r in out if r.get("owner", {}).get("login") == self.owner]

    @staticmethod
    def _role(repo: dict) -> tuple[str, tuple[str, ...]]:
        hay = (repo.get("name", "") + " " + (repo.get("description") or "")).lower()
        for role, keywords in ROLE_RULES:
            if any(k in hay for k in keywords):
                return role, tuple(k for k in keywords if k in hay)
        return "unclassified", ()

    @staticmethod
    def _actions(repo: dict, role: str) -> tuple[str, ...]:
        actions = []
        name = repo.get("name", "").lower()
        if not repo.get("description"):
            actions.append("add_repository_manifest")
        if not repo.get("has_issues"):
            actions.append("enable_issue_tracking_or_record_reason")
        if role == "unclassified":
            actions.append("assign_canonical_role")
        if any(x in name for x in ("vaixlns", "vx", "nexent")):
            actions.append("link_to_canonical_graph")
        actions += ["scan_dependencies", "scan_duplicate_capabilities", "generate_interface_candidate"]
        return tuple(dict.fromkeys(actions))

    def audit(self) -> list[RepositoryRecord]:
        records = []
        for repo in self.repositories():
            role, signals = self._role(repo)
            records.append(
                RepositoryRecord(
                    repo["full_name"], repo["name"], repo.get("visibility", "unknown"),
                    repo.get("default_branch", "main"), bool(repo.get("archived")),
                    int(repo.get("size", 0)), repo.get("description") or "",
                    role, signals, self._actions(repo, role),
                )
            )
        return records

    def write_catalog(self, path: str = ".vx/repository_catalog.json") -> list[dict]:
        records = [asdict(r) for r in self.audit()]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"version": "1.0", "owner": self.owner, "repositories": records},
                      handle, ensure_ascii=False, indent=2)
        return records

    @staticmethod
    def innovation_queue(records: list[RepositoryRecord]) -> list[dict]:
        return [{"repository": r.full_name, "proposals": list(r.actions)}
                for r in records if r.actions]
