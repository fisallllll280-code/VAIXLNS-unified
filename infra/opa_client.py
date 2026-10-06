"""Optional HTTP client for Open Policy Agent with fail-closed defaults."""
from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OPAClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 3.0,
        token: str | None = None,
        fail_closed: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.token = token
        self.fail_closed = fail_closed

    def evaluate(self, policy_path: str, input_data: Mapping[str, Any]) -> bool:
        path = "/".join(p.strip("/") for p in policy_path.split("/") if p.strip("/"))
        url = f"{self.base_url}/v1/data/{path}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            url,
            data=json.dumps({"input": dict(input_data)}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result: Any = payload.get("result")
            if isinstance(result, bool):
                return result
            if isinstance(result, dict) and "allow" in result:
                return bool(result["allow"])
            raise ValueError("OPA_RESULT_SHAPE_UNSUPPORTED")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return False if self.fail_closed else True
