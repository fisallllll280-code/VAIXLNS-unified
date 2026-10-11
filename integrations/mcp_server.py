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
        "description": "Read the VAIXLNS runtime health and durable-store integrity status.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "vx.status",
        "description": "Read runtime event count, last event hash, snapshot ID, and remote configuration status.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "vx.capabilities.list",
        "description": "List the operations exposed by this read-only MCP bridge.",
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


def _get_json(path: str) -> dict[str, Any]:
    # Call sites use fixed paths; user input is never used to construct a URL.
    if path not in {"/health", "/status"}:
        raise BridgeError("ENDPOINT_NOT_ALLOWED")
    url = _base_url() + path
    headers = {"Accept": "application/json"}
    token = os.getenv("VAIXLNS_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers, method="GET")
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
        raise BridgeError(f"API_HTTP_ERROR_{exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise BridgeError("API_UNAVAILABLE") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BridgeError("API_INVALID_JSON") from None


def _tool_result(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict) or arguments:
        raise BridgeError("TOOL_ACCEPTS_NO_ARGUMENTS")
    if name == "vx.health":
        value = _get_json("/health")
    elif name == "vx.status":
        value = _get_json("/status")
    elif name == "vx.capabilities.list":
        value = {
            "mode": "read-only",
            "tools": [tool["name"] for tool in TOOLS],
            "not_exposed": ["shell", "arbitrary_url", "filesystem", "write", "deploy", "delete"],
        }
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
