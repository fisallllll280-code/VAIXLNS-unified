"""Command-line entry point for the scoped execution tools."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import uuid

from tools.execution_fabric import Principal, build_default_gateway


ROLE_SCOPES = {
    "research": frozenset({"read:search", "read:public-repositories", "read:source-corpus"}),
    "archive": frozenset({"read:project-archives", "read:search", "read:provenance"}),
    "engineering": frozenset({"read:source-corpus", "read:engineering-contract", "read:implementation-plan"}),
    "verifier": frozenset({"read:test-results", "read:test-evidence", "read:provenance", "read:contracts", "request:sandbox-test"}),
    "governance": frozenset({"read:decision-package", "read:provenance"}),
}


def _json_default(value):
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VAIXLNS governed execution tools")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]),
                        help="repository root (default: this checkout)")
    parser.add_argument("--role", choices=tuple(ROLE_SCOPES), default="research",
                        help="fixed local role profile; arbitrary scopes cannot be supplied")
    parser.add_argument("--enable-tests", action="store_true",
                        help="explicitly enable only allowlisted unittest patterns; verifier role required")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list tools available to this profile")
    call = sub.add_parser("call", help="invoke one registered tool")
    call.add_argument("tool_id")
    call.add_argument("--args-json", required=True, help="JSON object with the exact tool inputs")
    call.add_argument("--request-id", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.enable_tests and args.role != "verifier":
        parser.error("--enable-tests requires --role verifier")
    root = Path(args.root).resolve()
    gateway = build_default_gateway(root, enable_test_runner=args.enable_tests)
    principal = Principal(f"cli:{args.role}", ROLE_SCOPES[args.role])
    if args.command == "list":
        available = []
        for spec in gateway.registry.list():
            available.append({
                "tool_id": spec.tool_id,
                "description": spec.description,
                "enabled": spec.enabled,
                "risk": spec.risk,
                "required_scopes": sorted(spec.required_scopes),
                "scope_groups": [sorted(group) for group in spec.scope_groups],
                "external_integration_id": spec.external_integration_id,
            })
        print(json.dumps({"principal": principal.principal_id, "tools": available},
                         ensure_ascii=False, indent=2))
        return 0
    try:
        call_args = json.loads(args.args_json)
    except json.JSONDecodeError:
        parser.error("--args-json must be valid JSON")
    if not isinstance(call_args, dict):
        parser.error("--args-json must decode to an object")
    request_id = args.request_id.strip() or str(uuid.uuid4())
    result = gateway.call(principal, args.tool_id, call_args, request_id=request_id)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=_json_default))
    return 0 if result.status == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
