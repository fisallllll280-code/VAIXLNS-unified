"""Minimal, dependency-free HTTP client for a VLNS server endpoint.

Connectivity is opt-in and configured only through environment variables.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ServerConfig:
    server_id: str
    base_url: str
    health_path: str = "/health"
    token: str | None = None
    timeout_seconds: float = 5.0
    enabled: bool = True

    @classmethod
    def from_env(cls, server_id: str, prefix: str = "VLNS_SERVER") -> "ServerConfig":
        return cls(
            server_id=server_id,
            base_url=os.getenv(f"{prefix}_URL", "").rstrip("/"),
            health_path=os.getenv(f"{prefix}_HEALTH_PATH", "/health"),
            token=os.getenv(f"{prefix}_TOKEN") or None,
            timeout_seconds=float(os.getenv(f"{prefix}_TIMEOUT", "5")),
            enabled=os.getenv(f"{prefix}_ENABLED", "false").lower() in {"1","true","yes"},
        )


class VLNSServerClient:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config

    @property
    def configured(self) -> bool:
        return bool(self.config.enabled and self.config.base_url)

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "status": "NOT_CONFIGURED", "server_id": self.config.server_id}
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        try:
            with urlopen(
                Request(url, data=body, headers=headers, method=method.upper()),
                timeout=self.config.timeout_seconds,
            ) as response:
                raw = response.read()
                data = json.loads(raw.decode("utf-8")) if raw else {}
                return {"ok": True, "status_code": response.status, "server_id": self.config.server_id, "data": data}
        except HTTPError as exc:
            return {"ok": False, "status": "HTTP_ERROR", "status_code": exc.code, "server_id": self.config.server_id}
        except URLError as exc:
            return {"ok": False, "status": "CONNECTION_ERROR", "server_id": self.config.server_id, "reason": str(exc.reason)}
        except (TimeoutError, OSError, ValueError) as exc:
            return {"ok": False, "status": "REQUEST_ERROR", "server_id": self.config.server_id, "reason": str(exc)}

    def health(self) -> dict[str, Any]:
        return self._request("GET", self.config.health_path)

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def emit_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/events", event)


def probe(configs: list[ServerConfig]) -> dict[str, Any]:
    results = {c.server_id: VLNSServerClient(c).health() for c in configs}
    return {
        "configured": sum(1 for c in configs if c.enabled and c.base_url),
        "healthy": sum(1 for r in results.values() if r.get("ok")),
        "servers": results,
    }
