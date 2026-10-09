#!/usr/bin/env python3
"""Prepare or dispatch a governed VLNS activation request.

Exit codes: 0 = prepare-only or fully activated and recorded in the local VX ledger;
2 = policy/runtime/transport/receipt/evidence gate did not complete.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from infra.durable_store import DurableEventStore
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


def _record_vx_activation_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Append activation evidence to VX's local hash-linked SQLite ledger."""
    activation_id = event.get("activation_id")
    event_type = event.get("event_type")
    if not isinstance(activation_id, str) or not activation_id or event_type != "VLNS_MODEL_ACTIVATION_CONFIRMED":
        return {"ok": False, "status": "LOCAL_VX_EVENT_SCHEMA_INVALID"}
    db_path = os.getenv("VLNS_ACTIVATION_EVIDENCE_DB", "var/vx_activation_events.sqlite3")
    event_id = "vlns-activation:" + activation_id
    try:
        with DurableEventStore(db_path) as store:
            prior = next((stored for stored in store.events() if stored.event_id == event_id), None)
            if prior is not None:
                same_event = (
                    prior.event_type == event_type
                    and prior.aggregate_id == activation_id
                    and dict(prior.payload) == dict(event)
                )
                if same_event and store.verify_integrity():
                    return {
                        "ok": True,
                        "status": "LOCAL_VX_EVENT_ALREADY_RECORDED",
                        "data": {
                            "event_id": event_id,
                            "event_hash": prior.event_hash,
                            "sequence": prior.sequence,
                            "ledger_head": store.last_hash,
                        },
                    }
                return {"ok": False, "status": "LOCAL_VX_EVENT_ID_COLLISION_OR_LEDGER_INVALID"}
            stored = store.append(
                event_id=event_id,
                event_type=str(event_type),
                aggregate_id=activation_id,
                actor_id="VX:VLNSActivationBridge",
                capability="model_activation",
                payload=dict(event),
            )
            if not store.verify_integrity():
                return {"ok": False, "status": "LOCAL_VX_LEDGER_INTEGRITY_FAILED"}
            return {
                "ok": True,
                "status": "LOCAL_VX_EVENT_RECORDED",
                "data": {
                    "event_id": stored.event_id,
                    "event_hash": stored.event_hash,
                    "sequence": stored.sequence,
                    "ledger_head": store.last_hash,
                },
            }
    except Exception as exc:
        return {"ok": False, "status": "LOCAL_VX_EVIDENCE_WRITE_FAILED:" + type(exc).__name__}


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
                "vx_evidence_recorded": False,
                "envelope": envelope,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        client = VLNSServerClient(ServerConfig.from_env("VLNS"))
        outcome = VLNSActivationBridge(
            client, policy, key, evidence_recorder=_record_vx_activation_event
        ).activate(request)
        print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2))
        return 0 if outcome.status == "ACTIVATED_AND_RECORDED" else 2
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
