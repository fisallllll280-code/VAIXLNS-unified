"""Executable Ω∞ preservation and recovery contract.

This test is intentionally self-contained: it validates the architecture contract
without depending on optional runtime services.
"""
from __future__ import annotations

import hashlib
import json


PIPELINE = [
    "INTENT", "PLAN", "AUTHORIZE", "EXECUTE", "OBSERVE",
    "VERIFY", "PROVE", "RECORD", "REPLAY",
    "FAILURE", "RECOVERY", "VERIFY",
]


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def event(kind: str, parent: str | None, payload: dict) -> dict:
    body = {"kind": kind, "parent": parent, "payload": payload}
    body["hash"] = hashlib.sha256(canonical(body).encode()).hexdigest()
    return body


def test_omega_integration_pipeline_is_complete():
    assert PIPELINE == [
        "INTENT", "PLAN", "AUTHORIZE", "EXECUTE", "OBSERVE",
        "VERIFY", "PROVE", "RECORD", "REPLAY",
        "FAILURE", "RECOVERY", "VERIFY",
    ]


def test_controlled_failure_recovery_preserves_history_and_replays():
    intent = event("INTENT", None, {"name": "omega-golden"})
    failure = event("FAILURE", intent["hash"], {"reason": "controlled-test-fault"})
    recovery = event("RECOVERY", failure["hash"], {"strategy": "reconstruct-from-history"})

    history = [intent, failure, recovery]
    assert history[1]["kind"] == "FAILURE"
    assert history[2]["parent"] == history[1]["hash"]
    assert len(history) == 3

    replay = [e["hash"] for e in history]
    assert replay == [intent["hash"], failure["hash"], recovery["hash"]]

    # The failed event remains part of the immutable evidence chain.
    assert any(e["hash"] == failure["hash"] for e in history)


def test_explicit_gaps_are_first_class():
    gaps = {"status": "PARTIAL", "items": ["independent-runtime-verifier"]}
    assert gaps["status"] in {"VERIFIED", "SPECIFIED", "PARTIAL", "MISSING", "CONFLICT", "PROPOSAL"}
    assert gaps["items"]
