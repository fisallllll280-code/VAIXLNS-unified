"""Read-only stdio MCP bridge for the existing VAIXLNS HTTP API.

No shell, arbitrary URL, filesystem, write, or deployment tool is exposed.
Run with: python -m integrations.mcp_server
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PROTOCOL_VERSION = "2024-11-05"
MAX_RESPONSE_BYTES = 1_000_000
TOOLS = [
    {
        "name": "vx.health",
        "description": "Read VAIXLNS runtime health and durable-store integrity.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "vx.status",
        "description": "Read runtime event count, latest hash, snapshot ID, and remote configuration status.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "vx.offices.list",
        "description": "Read the explicitly configured VAIXLNS office registry. Does not dispatch work.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "vx.office.route.preview",
        "description": "Preview a proposal-only route through a registered office. Never executes tools or writes canonical state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "office_id": {"type": "string", "minLength": 1, "maxLength": 120},
                "intent": {"type": "string", "minLength": 1, "maxLength": 2000},
            },
            "required": ["office_id", "intent"],
            "additionalProperties": False,
        },
    },
    {
        "name": "vx.capabilities.list",
        "description": "List the read and preview operations exposed by this MCP bridge.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


class BridgeError(RuntimeError):
    """A safe, user-presentable bridge failure."""


def _base_url() -> str:
    raw = os.getenv("VX_MCP_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    parsed = urlparse(raw)
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise BridgeError("API_BASE_URL_MUST_USE_HTTPS_UNLESS_LOOPBACK")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BridgeError("INVALID_API_BASE_URL")
    return raw


def _request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Only a finite route/method allowlist is accepted. Caller data never selects
    # a URL, host, path, or method.
    allowed = {
        ("GET", "/health"),
        ("GET", "/status"),
        ("GET", "/offices"),
        ("POST", "/office-routing/preview"),
    }
    if (method, path) not in allowed:
        raise BridgeError("ENDPOINT_NOT_ALLOWED")
    url = _base_url() + path
    headers = {"Accept": "application/json"}
    token = os.getenv("VAIXLNS_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=3.0) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise BridgeError("API_RESPONSE_TOO_LARGE")
            parsed = json.loads(body.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise BridgeError("API_RESPONSE_MUST_BE_OBJECT")
            return parsed
    except HTTPError as exc:
        if exc.code == 401:
            raise BridgeError("AUTHORIZATION_REQUIRED") from None
        if exc.code == 404 and path == "/office-routing/preview":
            raise BridgeError("OFFICE_NOT_FOUND") from None
        if exc.code == 503:
            # Surface only known, non-sensitive policy codes; never echo raw server
            # bodies, stack traces, tokens, or arbitrary provider errors.
            try:
                detail = json.loads(exc.read(4096).decode("utf-8")).get("detail")
            except Exception:
                detail = None
            known = {
                "AUTHENTICATION_NOT_CONFIGURED",
                "OFFICE_REGISTRY_NOT_CONFIGURED",
                "OFFICE_REGISTRY_PATH_MUST_BE_ABSOLUTE",
                "OFFICE_REGISTRY_TOO_LARGE",
                "OFFICE_REGISTRY_UNREADABLE",
            }
            if detail in known:
                raise BridgeError(detail) from None
        raise BridgeError(f"API_HTTP_ERROR_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise BridgeError("API_UNAVAILABLE") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BridgeError("API_INVALID_JSON") from None


def _get_json(path: str) -> dict[str, Any]:
    return _request_json(path, method="GET")


def _tool_result(name: str, arguments: Any) -> dict[str, Any]:
    if name in {"vx.health", "vx.status", "vx.offices.list", "vx.capabilities.list"}:
        if not isinstance(arguments, dict) or arguments:
            raise BridgeError("TOOL_ACCEPTS_NO_ARGUMENTS")
        if name == "vx.health":
            value = _get_json("/health")
        elif name == "vx.status":
            value = _get_json("/status")
        elif name == "vx.offices.list":
            value = _get_json("/offices")
        else:
            value = {
                "mode": "read-only-and-route-preview",
                "tools": [tool["name"] for tool in TOOLS],
                "not_exposed": [
                    "shell", "arbitrary_url", "filesystem", "write",
                    "dispatch", "deploy", "delete", "external_tool_invocation",
                ],
            }
    elif name == "vx.office.route.preview":
        if not isinstance(arguments, dict) or set(arguments) != {"office_id", "intent"}:
            raise BridgeError("INVALID_ROUTE_PREVIEW_ARGUMENTS")
        office_id = arguments.get("office_id")
        intent = arguments.get("intent")
        if not isinstance(office_id, str) or not office_id.strip() or len(office_id) > 120:
            raise BridgeError("OFFICE_ID_INVALID")
        if not isinstance(intent, str) or not intent.strip() or len(intent) > 2000:
            raise BridgeError("INTENT_INVALID")
        value = _request_json(
            "/office-routing/preview",
            method="POST",
            payload={"office_id": office_id, "intent": intent},
        )
    else:
        raise BridgeError("UNKNOWN_TOOL")
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message; return None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None,
                "error": {"code": -32600, "message": "Invalid Request"}}
    method = message.get("method")
    request_id = message.get("id")
    if not isinstance(method, str):
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32600, "message": "Invalid Request"}}
    if request_id is None:
        # MCP notifications have no response.
        return None
    try:
        params = message.get("params") or {}
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "vaixlns-vx-readonly-bridge", "version": "0.1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            if not isinstance(params, dict):
                raise BridgeError("INVALID_TOOL_PARAMETERS")
            result = _tool_result(params.get("name"), params.get("arguments", {}))
        else:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except BridgeError as exc:
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
    except Exception:
        # Never emit exception details, request headers, or tokens to the MCP client.
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": "INTERNAL_BRIDGE_ERROR"}], "isError": True}}


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = handle_message(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
