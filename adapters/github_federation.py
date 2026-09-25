"""Source-owned GitHub federation adapter.

Reads repository metadata and files through GitHub's REST API using a token
supplied at runtime. It preserves repository identity and revision as provenance.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RepositorySource:
    repository: str
    ref: str
    path: str
    content: str
    provenance: str


class GitHubFederationAdapter:
    def __init__(self, token: str | None = None, api_base: str = "https://api.github.com") -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.api_base = api_base.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _get(self, path: str) -> Dict[str, Any]:
        if not self.configured:
            raise RuntimeError("GITHUB_TOKEN_NOT_CONFIGURED")
        request = Request(
            self.api_base + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "VAIXLNS-federation",
            },
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def repository_metadata(self, repository: str) -> Dict[str, Any]:
        return self._get(f"/repos/{repository}")

    def file(self, repository: str, path: str, ref: str | None = None) -> RepositorySource:
        suffix = "" if ref is None else f"?ref={ref}"
        data = self._get(f"/repos/{repository}/contents/{path}{suffix}")
        if data.get("type") != "file":
            raise ValueError("PATH_IS_NOT_FILE")
        import base64
        content = base64.b64decode(data["content"]).decode("utf-8")
        actual_ref = ref or self.repository_metadata(repository).get("default_branch", "")
        provenance = f"github:{repository}@{actual_ref}:{path}"
        return RepositorySource(repository, actual_ref, path, content, provenance)

    def inventory(self, repositories: Iterable[str]) -> list[Dict[str, Any]]:
        return [
            {
                "repository": repo,
                "metadata": self.repository_metadata(repo),
                "source_system": "GitHub",
            }
            for repo in repositories
        ]
