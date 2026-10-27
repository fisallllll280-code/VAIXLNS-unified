"""Provider-neutral, append-only audit ledger for AI requests routed through VX.

The ledger records references and hashes, not raw prompts or model outputs.
It uses the existing hash-linked DurableEventStore and fails closed if the
existing chain is invalid when this ledger instance starts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
import sqlite3
import threading
from typing import Any, Mapping
from uuid import uuid4

from infra.durable_store import DurableEventStore, StoredEvent


_HEX_256 = re.compile(r"^[0-9a-fA-F]{64}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_TERMINAL_EXECUTION = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "REJECTED"}
_EXECUTION_TRANSITIONS = {
    "RECEIVED": {"VALIDATING", "REJECTED", "CANCELLED"},
    "VALIDATING": {"QUEUED", "RUNNING", "FAILED", "REJECTED", "CANCELLED"},
    "QUEUED": {"RUNNING", "FAILED", "TIMED_OUT", "REJECTED", "CANCELLED"},
    "RUNNING": {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
    "TIMED_OUT": set(),
    "CANCELLED": set(),
    "REJECTED": set(),
}
_VERIFICATION_STATUSES = {"VERIFIED", "FAILED", "INCONCLUSIVE", "NOT_REQUIRED"}
_BILLING_STATUSES = {
    "NOT_AVAILABLE", "ESTIMATED", "PENDING_RECONCILIATION", "RECONCILED", "DISPUTED"
}
_BILLING_TRANSITIONS = {
    "NOT_AVAILABLE": {"ESTIMATED", "PENDING_RECONCILIATION", "DISPUTED"},
    "ESTIMATED": {"PENDING_RECONCILIATION", "RECONCILED", "DISPUTED"},
    "PENDING_RECONCILIATION": {"RECONCILED", "DISPUTED"},
    "RECONCILED": {"PENDING_RECONCILIATION", "DISPUTED"},
    "DISPUTED": {"PENDING_RECONCILIATION", "RECONCILED"},
}
_SOURCE_TYPES = {"WEB", "RAG", "DATABASE", "API", "TOOL", "FILE", "MEMORY", "OTHER"}
_SOURCE_USAGE_STATES = {"REQUESTED", "RETURNED", "USED", "BLOCKED", "FAILED"}
_SOURCE_TRUST_STATES = {"NOT_VERIFIED", "VERIFIED", "UNTRUSTED", "BLOCKED", "NOT_APPLICABLE"}
_ATTEMPT_STATES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}
_COST_CATEGORIES = {
    "INPUT_TOKENS", "OUTPUT_TOKENS", "TOOL", "RETRIEVAL", "STORAGE", "FEE", "OTHER"
}
_COST_ENTRY_TYPES = {"CHARGE", "CREDIT"}
_COST_BASES = {"ESTIMATE", "PROVIDER_REPORTED", "INVOICE", "MANUAL"}


class AuditLedgerError(ValueError):
    """Invalid audit record or illegal state transition."""


class AuditIntegrityError(RuntimeError):
    """The durable audit chain failed integrity validation."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditLedgerError(f"{field.upper()}_REQUIRED")
    return value.strip()


def _nonnegative_int(value: Any, field: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AuditLedgerError(f"{field.upper()}_MUST_BE_NONNEGATIVE_INTEGER")
    return value


def _sha256(value: Any, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _HEX_256.fullmatch(value):
        raise AuditLedgerError(f"{field.upper()}_MUST_BE_SHA256_HEX")
    return value.lower()


def _timestamp(value: Any = None, *, field: str = "timestamp") -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuditLedgerError(f"{field.upper()}_MUST_BE_ISO8601") from exc
    else:
        raise AuditLedgerError(f"{field.upper()}_MUST_BE_ISO8601")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuditLedgerError(f"{field.upper()}_MUST_INCLUDE_TIMEZONE")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _elapsed_ms(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    delta = (_datetime(end) - _datetime(start)).total_seconds() * 1000
    if delta < 0:
        raise AuditLedgerError("TIMESTAMP_ORDER_INVALID")
    return round(delta, 3)


def _amount_string(value: Any) -> str:
    # Float is rejected to avoid silently persisting binary floating-point rounding.
    if isinstance(value, bool) or isinstance(value, float):
        raise AuditLedgerError("COST_AMOUNT_MUST_BE_DECIMAL_STRING_OR_INTEGER")
    if not isinstance(value, (str, int, Decimal)):
        raise AuditLedgerError("COST_AMOUNT_MUST_BE_DECIMAL_STRING_OR_INTEGER")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AuditLedgerError("COST_AMOUNT_INVALID") from exc
    if not amount.is_finite() or amount < 0:
        raise AuditLedgerError("COST_AMOUNT_MUST_BE_FINITE_AND_NONNEGATIVE")
    return format(amount.normalize(), "f")


def _amount_decimal(value: str) -> Decimal:
    return Decimal(value)


class VXAIRequestAuditLedger:
    """Audit facade over DurableEventStore.

    A separate aggregate is created for each request_id. Event identifiers are
    deterministic for creation, attempt, output, source, cost, and verification
    records so callers can safely retry those writes.
    """

    SYSTEM_ACTOR = "VX:AIRequestAuditLedger"

    def __init__(self, store: DurableEventStore | str) -> None:
        self._owns_store = not isinstance(store, DurableEventStore)
        self.store = DurableEventStore(store) if self._owns_store else store
        self._lock = threading.RLock()
        if not self.store.verify_integrity():
            if self._owns_store:
                self.store.close()
            raise AuditIntegrityError("EXISTING_DURABLE_EVENT_CHAIN_INVALID")
        self._events_by_id = {event.event_id: event for event in self.store.events()}

    def close(self) -> None:
        if self._owns_store:
            self.store.close()

    def __enter__(self) -> "VXAIRequestAuditLedger":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def verify_integrity(self) -> bool:
        return self.store.verify_integrity()

    def _append(
        self,
        *,
        event_id: str,
        event_type: str,
        request_id: str,
        payload: Mapping[str, Any],
        capability: str,
        created_at: str | None = None,
    ) -> StoredEvent:
        actor_id = self.SYSTEM_ACTOR
        known = self._events_by_id.get(event_id)
        if known is not None:
            same = (
                known.event_type == event_type
                and known.aggregate_id == request_id
                and known.actor_id == actor_id
                and known.capability == capability
                and dict(known.payload) == dict(payload)
            )
            if same and self.store.verify_integrity():
                return known
            raise AuditIntegrityError("EVENT_ID_COLLISION_OR_LEDGER_INVALID")
        try:
            stored = self.store.append(
                event_id=event_id,
                event_type=event_type,
                aggregate_id=request_id,
                actor_id=actor_id,
                capability=capability,
                payload=dict(payload),
                created_at=created_at,
            )
        except sqlite3.IntegrityError:
            # Another writer may have inserted the same id after this instance
            # initialized. Refresh the in-memory index and only accept an exact replay.
            self._events_by_id = {event.event_id: event for event in self.store.events()}
            known = self._events_by_id.get(event_id)
            if known is not None and (
                known.event_type == event_type
                and known.aggregate_id == request_id
                and known.actor_id == actor_id
                and known.capability == capability
                and dict(known.payload) == dict(payload)
                and self.store.verify_integrity()
            ):
                return known
            raise AuditIntegrityError("EVENT_ID_COLLISION_OR_CONCURRENT_WRITE") from None
        self._events_by_id[stored.event_id] = stored
        return stored

    def create_request(self, record: Mapping[str, Any]) -> StoredEvent:
        """Create a request using hashes/references; raw prompt or output fields are rejected."""
        allowed = {
            "request_id", "trace_id", "parent_request_id", "tenant_id", "actor_id",
            "agent_id", "purpose", "provider", "model_id", "model_version",
            "policy_version", "input_hash", "input_ref", "input_tokens",
            "input_classification", "created_at",
        }
        unknown = set(record) - allowed
        if unknown:
            raise AuditLedgerError("UNKNOWN_REQUEST_FIELDS:" + ",".join(sorted(unknown)))
        request_id = _required_text(record.get("request_id"), "request_id")
        request = {
            "request_id": request_id,
            "trace_id": _required_text(record.get("trace_id"), "trace_id"),
            "parent_request_id": record.get("parent_request_id"),
            "tenant_id": record.get("tenant_id"),
            "actor_id": _required_text(record.get("actor_id"), "actor_id"),
            "agent_id": record.get("agent_id"),
            "purpose": _required_text(record.get("purpose"), "purpose"),
            "provider": _required_text(record.get("provider"), "provider"),
            "model_id": _required_text(record.get("model_id"), "model_id"),
            "model_version": record.get("model_version"),
            "policy_version": _required_text(record.get("policy_version"), "policy_version"),
            "created_at": _timestamp(record.get("created_at"), field="created_at"),
            "input_hash": _sha256(record.get("input_hash"), "input_hash"),
            "input_ref": record.get("input_ref"),
            "input_tokens": _nonnegative_int(record.get("input_tokens"), "input_tokens", optional=True),
            "input_classification": _required_text(record.get("input_classification"), "input_classification"),
        }
        for name in ("parent_request_id", "tenant_id", "agent_id", "model_version", "input_ref"):
            value = request[name]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise AuditLedgerError(f"{name.upper()}_MUST_BE_NONEMPTY_STRING_OR_NULL")
        payload = {
            "schema_version": "vx.ai-request-audit.v1",
            "request": request,
            "execution_status": "RECEIVED",
            "verification_status": "PENDING",
            "billing_status": "NOT_AVAILABLE",
        }
        with self._lock:
            return self._append(
                event_id=f"vx-ai-request:{request_id}:created",
                event_type="VX_AI_REQUEST_CREATED",
                request_id=request_id,
                payload=payload,
                capability="ai_request_audit:create",
            )

    def request(self, request_id: str) -> dict[str, Any]:
        request_id = _required_text(request_id, "request_id")
        with self._lock:
            events = self.store.events(aggregate_id=request_id)
            if not events or events[0].event_type != "VX_AI_REQUEST_CREATED":
                raise AuditLedgerError("REQUEST_NOT_FOUND")
            created = events[0].payload
            view: dict[str, Any] = {
                "schema_version": created.get("schema_version"),
                "request": dict(created["request"]),
                "execution_status": "RECEIVED",
                "verification_status": "PENDING",
                "billing_status": "NOT_AVAILABLE",
                "attempts": [],
                "outputs": [],
                "sources": [],
                "cost_entries": [],
                "verifications": [],
                "status_history": [],
                "event_refs": [],
                "cost_totals": {},
                "metrics": {},
            }
            status_times: dict[str, str] = {"RECEIVED": events[0].created_at}
            for event in events:
                view["event_refs"].append({
                    "sequence": event.sequence,
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "created_at": event.created_at,
                    "event_hash": event.event_hash,
                })
                payload = dict(event.payload)
                if event.event_type == "VX_AI_REQUEST_STATUS_CHANGED":
                    view["execution_status"] = payload["to_status"]
                    status_times.setdefault(payload["to_status"], event.created_at)
                    view["status_history"].append({
                        "from_status": payload["from_status"],
                        "to_status": payload["to_status"],
                        "reason": payload["reason"],
                        "changed_by": payload["changed_by"],
                        "created_at": event.created_at,
                    })
                elif event.event_type == "VX_AI_ATTEMPT_RECORDED":
                    view["attempts"].append(payload["attempt"])
                elif event.event_type == "VX_AI_OUTPUT_RECORDED":
                    view["outputs"].append(payload["output"])
                elif event.event_type == "VX_AI_SOURCE_RECORDED":
                    view["sources"].append(payload["source"])
                elif event.event_type == "VX_AI_COST_RECORDED":
                    cost = payload["cost"]
                    view["cost_entries"].append(cost)
                    currency = cost["currency"]
                    basis = cost["basis"]
                    bucket = view["cost_totals"].setdefault(currency, {})
                    basis_total = bucket.setdefault(basis, {"CHARGE": Decimal("0"), "CREDIT": Decimal("0")})
                    basis_total[cost["entry_type"]] += _amount_decimal(cost["amount"])
                    if basis == "ESTIMATE":
                        if view["billing_status"] == "NOT_AVAILABLE":
                            view["billing_status"] = "ESTIMATED"
                    else:
                        view["billing_status"] = "PENDING_RECONCILIATION"
                elif event.event_type == "VX_AI_BILLING_STATUS_CHANGED":
                    view["billing_status"] = payload["to_status"]
                elif event.event_type == "VX_AI_VERIFICATION_RECORDED":
                    view["verification_status"] = payload["verification"]["status"]
                    view["verifications"].append(payload["verification"])
            for currency, bases in view["cost_totals"].items():
                view["cost_totals"][currency] = {
                    basis: {entry_type: format(amount.normalize(), "f") for entry_type, amount in totals.items()}
                    for basis, totals in bases.items()
                }
            created_at = events[0].created_at
            terminal_time = next(
                (event.created_at for event in reversed(events)
                 if event.event_type == "VX_AI_REQUEST_STATUS_CHANGED"
                 and event.payload.get("to_status") in _TERMINAL_EXECUTION),
                None,
            )
            view["metrics"] = {
                "observed_wall_clock_ms": _elapsed_ms(created_at, terminal_time),
                "queue_wait_ms": _elapsed_ms(status_times.get("QUEUED"), status_times.get("RUNNING")),
                "time_to_first_token_ms": [
                    attempt["time_to_first_token_ms"]
                    for attempt in view["attempts"]
                    if attempt.get("time_to_first_token_ms") is not None
                ],
                "attempt_latency_ms": [
                    attempt["latency_ms"] for attempt in view["attempts"]
                    if attempt.get("latency_ms") is not None
                ],
            }
            return view

    def transition_status(
        self,
        request_id: str,
        to_status: str,
        *,
        changed_by: str,
        reason: str = "",
    ) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        to_status = _required_text(to_status, "to_status").upper()
        changed_by = _required_text(changed_by, "changed_by")
        if to_status not in _EXECUTION_TRANSITIONS:
            raise AuditLedgerError("EXECUTION_STATUS_UNKNOWN")
        with self._lock:
            view = self.request(request_id)
            from_status = view["execution_status"]
            if from_status == to_status:
                last = next((e for e in reversed(self.store.events(aggregate_id=request_id))
                             if e.event_type == "VX_AI_REQUEST_STATUS_CHANGED"), None)
                if last is not None and last.payload.get("to_status") == to_status \
                        and last.payload.get("reason", "") == reason:
                    return last
                raise AuditLedgerError("DUPLICATE_STATUS_WITH_DIFFERENT_REASON")
            if to_status not in _EXECUTION_TRANSITIONS[from_status]:
                raise AuditLedgerError(f"ILLEGAL_EXECUTION_TRANSITION:{from_status}->{to_status}")
            reason = reason.strip() if isinstance(reason, str) else ""
            if to_status in {"FAILED", "TIMED_OUT", "CANCELLED", "REJECTED"} and not reason:
                raise AuditLedgerError("TERMINAL_NON_SUCCESS_REQUIRES_REASON")
            if to_status == "SUCCEEDED" and not view["outputs"]:
                raise AuditLedgerError("SUCCESS_REQUIRES_RECORDED_OUTPUT")
            payload = {
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
                "changed_by": changed_by,
            }
            event_id = f"vx-ai-status:{request_id}:{from_status}:{to_status}"
            return self._append(
                event_id=event_id,
                event_type="VX_AI_REQUEST_STATUS_CHANGED",
                request_id=request_id,
                payload=payload,
                capability="ai_request_audit:status_transition",
            )

    def record_attempt(self, request_id: str, attempt: Mapping[str, Any]) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        allowed = {
            "attempt_id", "attempt_number", "provider", "model_id", "model_version",
            "status", "started_at", "first_token_at", "completed_at", "latency_ms",
            "time_to_first_token_ms", "input_tokens", "output_tokens", "finish_reason",
            "provider_request_id", "route_id",
        }
        if set(attempt) - allowed:
            raise AuditLedgerError("UNKNOWN_ATTEMPT_FIELDS")
        normalized = dict(attempt)
        attempt_id = _required_text(normalized.get("attempt_id"), "attempt_id")
        normalized["attempt_number"] = normalized.get("attempt_number")
        if isinstance(normalized["attempt_number"], bool) or not isinstance(normalized["attempt_number"], int) or normalized["attempt_number"] < 1:
            raise AuditLedgerError("ATTEMPT_NUMBER_MUST_BE_POSITIVE_INTEGER")
        normalized["provider"] = _required_text(normalized.get("provider"), "provider")
        normalized["model_id"] = _required_text(normalized.get("model_id"), "model_id")
        normalized["status"] = _required_text(normalized.get("status"), "status").upper()
        if normalized["status"] not in _ATTEMPT_STATES:
            raise AuditLedgerError("ATTEMPT_STATUS_UNKNOWN")
        normalized["started_at"] = _timestamp(normalized.get("started_at"), field="started_at")
        normalized["completed_at"] = _timestamp(normalized.get("completed_at"), field="completed_at")
        if _datetime(normalized["completed_at"]) < _datetime(normalized["started_at"]):
            raise AuditLedgerError("ATTEMPT_TIMESTAMP_ORDER_INVALID")
        first_token_at = normalized.get("first_token_at")
        normalized["first_token_at"] = _timestamp(first_token_at, field="first_token_at") if first_token_at is not None else None
        if normalized["first_token_at"] is not None:
            if _datetime(normalized["first_token_at"]) < _datetime(normalized["started_at"]) or _datetime(normalized["first_token_at"]) > _datetime(normalized["completed_at"]):
                raise AuditLedgerError("FIRST_TOKEN_TIMESTAMP_OUT_OF_ATTEMPT_RANGE")
        computed_latency = _elapsed_ms(normalized["started_at"], normalized["completed_at"])
        latency = normalized.get("latency_ms")
        if latency is not None and (isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0):
            raise AuditLedgerError("LATENCY_MS_MUST_BE_NONNEGATIVE_NUMBER")
        normalized["latency_ms"] = round(float(latency), 3) if latency is not None else computed_latency
        ttf = normalized.get("time_to_first_token_ms")
        computed_ttf = _elapsed_ms(normalized["started_at"], normalized["first_token_at"])
        if ttf is not None and (isinstance(ttf, bool) or not isinstance(ttf, (int, float)) or ttf < 0):
            raise AuditLedgerError("TIME_TO_FIRST_TOKEN_MS_INVALID")
        normalized["time_to_first_token_ms"] = round(float(ttf), 3) if ttf is not None else computed_ttf
        for token_field in ("input_tokens", "output_tokens"):
            normalized[token_field] = _nonnegative_int(normalized.get(token_field), token_field, optional=True)
        for text_field in ("model_version", "finish_reason", "provider_request_id", "route_id"):
            value = normalized.get(text_field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise AuditLedgerError(f"{text_field.upper()}_MUST_BE_NONEMPTY_STRING_OR_NULL")
        with self._lock:
            self.request(request_id)
            if self.request(request_id)["execution_status"] != "RUNNING":
                raise AuditLedgerError("ATTEMPT_CAN_ONLY_BE_RECORDED_WHILE_RUNNING")
            return self._append(
                event_id=f"vx-ai-attempt:{request_id}:{attempt_id}",
                event_type="VX_AI_ATTEMPT_RECORDED",
                request_id=request_id,
                payload={"attempt": normalized},
                capability="ai_request_audit:attempt",
            )

    def record_output(self, request_id: str, output: Mapping[str, Any]) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        allowed = {"output_id", "output_hash", "output_ref", "output_tokens", "format", "classification"}
        if set(output) - allowed:
            raise AuditLedgerError("UNKNOWN_OUTPUT_FIELDS")
        normalized = {
            "output_id": _required_text(output.get("output_id"), "output_id"),
            "output_hash": _sha256(output.get("output_hash"), "output_hash"),
            "output_ref": output.get("output_ref"),
            "output_tokens": _nonnegative_int(output.get("output_tokens"), "output_tokens", optional=True),
            "format": output.get("format"),
            "classification": output.get("classification", "INTERNAL"),
        }
        for field in ("output_ref", "format", "classification"):
            value = normalized[field]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise AuditLedgerError(f"{field.upper()}_MUST_BE_NONEMPTY_STRING_OR_NULL")
        with self._lock:
            if self.request(request_id)["execution_status"] != "RUNNING":
                raise AuditLedgerError("OUTPUT_CAN_ONLY_BE_RECORDED_WHILE_RUNNING")
            return self._append(
                event_id=f"vx-ai-output:{request_id}:{normalized['output_id']}",
                event_type="VX_AI_OUTPUT_RECORDED",
                request_id=request_id,
                payload={"output": normalized},
                capability="ai_request_audit:output",
            )

    def record_source(self, request_id: str, source: Mapping[str, Any]) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        allowed = {
            "source_record_id", "source_type", "source_name", "source_version",
            "retrieved_at", "content_hash", "source_uri_ref", "usage_purpose",
            "trust_status", "usage_state", "contribution_ref",
        }
        if set(source) - allowed:
            raise AuditLedgerError("UNKNOWN_SOURCE_FIELDS")
        normalized = {
            "source_record_id": _required_text(source.get("source_record_id"), "source_record_id"),
            "source_type": _required_text(source.get("source_type"), "source_type").upper(),
            "source_name": _required_text(source.get("source_name"), "source_name"),
            "source_version": source.get("source_version"),
            "retrieved_at": _timestamp(source.get("retrieved_at"), field="retrieved_at") if source.get("retrieved_at") is not None else None,
            "content_hash": _sha256(source.get("content_hash"), "content_hash", optional=True),
            "source_uri_ref": source.get("source_uri_ref"),
            "usage_purpose": _required_text(source.get("usage_purpose"), "usage_purpose"),
            "trust_status": _required_text(source.get("trust_status"), "trust_status").upper(),
            "usage_state": _required_text(source.get("usage_state"), "usage_state").upper(),
            "contribution_ref": source.get("contribution_ref"),
        }
        if normalized["source_type"] not in _SOURCE_TYPES:
            raise AuditLedgerError("SOURCE_TYPE_UNKNOWN")
        if normalized["usage_state"] not in _SOURCE_USAGE_STATES:
            raise AuditLedgerError("SOURCE_USAGE_STATE_UNKNOWN")
        if normalized["trust_status"] not in _SOURCE_TRUST_STATES:
            raise AuditLedgerError("SOURCE_TRUST_STATUS_UNKNOWN")
        if normalized["usage_state"] == "USED" and normalized["content_hash"] is None:
            raise AuditLedgerError("USED_SOURCE_REQUIRES_CONTENT_HASH")
        for field in ("source_version", "source_uri_ref", "contribution_ref"):
            value = normalized[field]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise AuditLedgerError(f"{field.upper()}_MUST_BE_NONEMPTY_STRING_OR_NULL")
        with self._lock:
            self.request(request_id)
            return self._append(
                event_id=f"vx-ai-source:{request_id}:{normalized['source_record_id']}",
                event_type="VX_AI_SOURCE_RECORDED",
                request_id=request_id,
                payload={"source": normalized},
                capability="ai_request_audit:source",
            )

    def record_cost(self, request_id: str, cost: Mapping[str, Any]) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        allowed = {
            "cost_record_id", "category", "entry_type", "basis", "amount", "currency",
            "price_source", "tariff_version", "occurred_at", "external_invoice_ref",
        }
        if set(cost) - allowed:
            raise AuditLedgerError("UNKNOWN_COST_FIELDS")
        normalized = {
            "cost_record_id": _required_text(cost.get("cost_record_id"), "cost_record_id"),
            "category": _required_text(cost.get("category"), "category").upper(),
            "entry_type": _required_text(cost.get("entry_type"), "entry_type").upper(),
            "basis": _required_text(cost.get("basis"), "basis").upper(),
            "amount": _amount_string(cost.get("amount")),
            "currency": _required_text(cost.get("currency"), "currency").upper(),
            "price_source": cost.get("price_source"),
            "tariff_version": cost.get("tariff_version"),
            "occurred_at": _timestamp(cost.get("occurred_at"), field="occurred_at") if cost.get("occurred_at") is not None else None,
            "external_invoice_ref": cost.get("external_invoice_ref"),
        }
        if normalized["category"] not in _COST_CATEGORIES:
            raise AuditLedgerError("COST_CATEGORY_UNKNOWN")
        if normalized["entry_type"] not in _COST_ENTRY_TYPES:
            raise AuditLedgerError("COST_ENTRY_TYPE_UNKNOWN")
        if normalized["basis"] not in _COST_BASES:
            raise AuditLedgerError("COST_BASIS_UNKNOWN")
        if not _CURRENCY.fullmatch(normalized["currency"]):
            raise AuditLedgerError("CURRENCY_MUST_BE_THREE_LETTERS")
        for field in ("price_source", "tariff_version", "external_invoice_ref"):
            value = normalized[field]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise AuditLedgerError(f"{field.upper()}_MUST_BE_NONEMPTY_STRING_OR_NULL")
        with self._lock:
            self.request(request_id)
            return self._append(
                event_id=f"vx-ai-cost:{request_id}:{normalized['cost_record_id']}",
                event_type="VX_AI_COST_RECORDED",
                request_id=request_id,
                payload={"cost": normalized},
                capability="ai_request_audit:cost",
            )

    def set_billing_status(
        self,
        request_id: str,
        to_status: str,
        *,
        changed_by: str,
        reason: str = "",
    ) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        to_status = _required_text(to_status, "billing_status").upper()
        changed_by = _required_text(changed_by, "changed_by")
        if to_status not in _BILLING_STATUSES:
            raise AuditLedgerError("BILLING_STATUS_UNKNOWN")
        with self._lock:
            view = self.request(request_id)
            from_status = view["billing_status"]
            if from_status == to_status:
                last = next((e for e in reversed(self.store.events(aggregate_id=request_id))
                             if e.event_type == "VX_AI_BILLING_STATUS_CHANGED"), None)
                if last and last.payload.get("to_status") == to_status and last.payload.get("reason", "") == reason:
                    return last
                raise AuditLedgerError("DUPLICATE_BILLING_STATUS")
            if to_status not in _BILLING_TRANSITIONS[from_status]:
                raise AuditLedgerError(f"ILLEGAL_BILLING_TRANSITION:{from_status}->{to_status}")
            if to_status == "RECONCILED" and not any(
                item["basis"] != "ESTIMATE" for item in view["cost_entries"]
            ):
                raise AuditLedgerError("RECONCILED_REQUIRES_NON_ESTIMATED_COST")
            reason = reason.strip() if isinstance(reason, str) else ""
            if to_status == "DISPUTED" and not reason:
                raise AuditLedgerError("DISPUTED_COST_REQUIRES_REASON")
            payload = {
                "from_status": from_status,
                "to_status": to_status,
                "changed_by": changed_by,
                "reason": reason,
            }
            return self._append(
                event_id=f"vx-ai-billing:{request_id}:{from_status}:{to_status}",
                event_type="VX_AI_BILLING_STATUS_CHANGED",
                request_id=request_id,
                payload=payload,
                capability="ai_request_audit:billing_status",
            )

    def record_verification(self, request_id: str, verification: Mapping[str, Any]) -> StoredEvent:
        request_id = _required_text(request_id, "request_id")
        allowed = {
            "verification_id", "status", "verifier_id", "policy_version",
            "checks_passed", "evidence_refs", "reason", "completed_at",
        }
        if set(verification) - allowed:
            raise AuditLedgerError("UNKNOWN_VERIFICATION_FIELDS")
        status = _required_text(verification.get("status"), "status").upper()
        if status not in _VERIFICATION_STATUSES:
            raise AuditLedgerError("VERIFICATION_STATUS_UNKNOWN")
        checks_passed = verification.get("checks_passed")
        if checks_passed is not None and not isinstance(checks_passed, bool):
            raise AuditLedgerError("CHECKS_PASSED_MUST_BE_BOOLEAN_OR_NULL")
        evidence_refs = verification.get("evidence_refs", [])
        if not isinstance(evidence_refs, (list, tuple)) or any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
            raise AuditLedgerError("EVIDENCE_REFS_MUST_BE_NONEMPTY_STRINGS")
        evidence_refs = list(dict.fromkeys(ref.strip() for ref in evidence_refs))
        if status == "VERIFIED" and (checks_passed is not True or not evidence_refs):
            raise AuditLedgerError("VERIFIED_REQUIRES_PASSED_CHECKS_AND_EVIDENCE")
        if status == "FAILED" and checks_passed is not False:
            raise AuditLedgerError("FAILED_VERIFICATION_REQUIRES_CHECKS_PASSED_FALSE")
        if status == "NOT_REQUIRED" and not _required_text(verification.get("reason"), "reason"):
            raise AuditLedgerError("NOT_REQUIRED_REQUIRES_REASON")
        normalized = {
            "verification_id": _required_text(verification.get("verification_id"), "verification_id"),
            "status": status,
            "verifier_id": _required_text(verification.get("verifier_id"), "verifier_id"),
            "policy_version": _required_text(verification.get("policy_version"), "policy_version"),
            "checks_passed": checks_passed,
            "evidence_refs": evidence_refs,
            "reason": verification.get("reason", ""),
            "completed_at": _timestamp(verification.get("completed_at"), field="completed_at"),
        }
        if not isinstance(normalized["reason"], str):
            raise AuditLedgerError("VERIFICATION_REASON_MUST_BE_STRING")
        with self._lock:
            self.request(request_id)
            return self._append(
                event_id=f"vx-ai-verification:{request_id}:{normalized['verification_id']}",
                event_type="VX_AI_VERIFICATION_RECORDED",
                request_id=request_id,
                payload={"verification": normalized},
                capability="ai_request_audit:verification",
            )
