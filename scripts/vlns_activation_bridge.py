#!/usr/bin/env python3
"""Prepare or dispatch a governed VLNS activation request.

Exit codes: 0 = prepared-only or fully activated and evidence-recorded;
2 = policy/runtime/transport/receipt/evidence gate did not complete.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from infra.vlns_server_client import ServerConfig, VLNSServerClient
from vlns.activation import (
    ActivationPolicy,
    ActivationRequest,
    ROLE_DEFAULT_PERMISSIONS,
    VLNSActivationBridge,
    prepare_activation,
)


def _csv(env: dict[str, str], name: str) -> frozenset[str]:
    return frozenset(part.strip() for part in env.get(name, "").split(",") if part.strip())


def _request_from_json(data: Any) -> ActivationRequest:
    if not isinstance(data, dict):
        raise ValueError("REQUEST_ROOT_MUST_BE_OBJECT")
    return ActivationRequest(
        model_id=data.get("model_id", ""),
        provider=data.get("provider", ""),
        model_version=data.get("model_version", ""),
        role=data.get("role", ""),
        capability_profile=tuple(data.get("capability_profile", ())),
        context_payload=data.get("context_payload"),
        tool_profile=tuple(data.get("tool_profile", ())),
        requested_permissions=tuple(data.get("requested_permissions", ("read", "propose"))),
        constraints=tuple(data.get("constraints", ("no_unreviewed_execution", "no_canonical_mutation"))),
        provenance=data.get("provenance", {}),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VAIXLNS governed VLNS activation bridge")
    parser.add_argument("request", help="JSON request file; never put secrets in this file")
    parser.add_argument("--prepare-only", action="store_true", help="sign and print the envelope without remote activation")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    try:
        request = _request_from_json(json.loads(Path(args.request).read_text(encoding="utf-8")))
        policy = ActivationPolicy(
            allowed_providers=_csv(env, "VLNS_ALLOWED_PROVIDERS"),
            allowed_capabilities=_csv(env, "VLNS_ALLOWED_CAPABILITIES"),
            allowed_tools=_csv(env, "VLNS_ALLOWED_TOOLS"),
            role_permissions=ROLE_DEFAULT_PERMISSIONS,
        )
        raw_key = env.get("VLNS_ACTIVATION_SIGNING_KEY", "")
        if not raw_key or len(raw_key.encode("utf-8")) < 32:
            raise ValueError("VLNS_ACTIVATION_SIGNING_KEY_MUST_BE_CONFIGURED_WITH_32_BYTES_MINIMUM")
        key = raw_key.encode("utf-8")
        if args.prepare_only:
            envelope = prepare_activation(request, policy, key)
            output = {
                "status": "PREPARED_ONLY",
                "activation_confirmed": False,
                "evidence_recorded": False,
                "envelope": envelope,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        client = VLNSServerClient(ServerConfig.from_env("VLNS"))
        outcome = VLNSActivationBridge(client, policy, key).activate(request)
        print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2))
        return 0 if outcome.status == "ACTIVATED_AND_RECORDED" else 2
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
