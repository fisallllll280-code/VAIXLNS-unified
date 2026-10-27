"""Generic audit wrapper for VX multi-mind/provider adapters.

Wrap an existing MindAdapter to audit its call lifecycle without storing the
task prompt or raw adapter output. This wrapper is optional so existing callers
remain compatible; it should not be stacked around ClaudeAdapter when that
adapter already receives the same audit ledger.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _safe_result_status(result: Any) -> str | None:
    if isinstance(result, dict):
        status = result.get("status")
        return status.lower() if isinstance(status, str) else None
    return None


class VXAuditedMindAdapter:
    """Wrap any adapter implementing run(mind, task), using VXAIRequestAuditLedger."""

    def __init__(
        self,
        inner_adapter: Any,
        audit_ledger: Any,
        *,
        audit_actor_id: str = "VX:MultiMindOrchestrator",
        policy_version: str = "vx-mind-adapter-v1",
    ) -> None:
        if not callable(getattr(inner_adapter, "run", None)):
            raise ValueError("INNER_ADAPTER_RUN_REQUIRED")
        if not callable(getattr(audit_ledger, "create_request", None)):
            raise ValueError("AUDIT_LEDGER_CREATE_REQUEST_REQUIRED")
        if not isinstance(audit_actor_id, str) or not audit_actor_id.strip():
            raise ValueError("AUDIT_ACTOR_ID_REQUIRED")
        if not isinstance(policy_version, str) or not policy_version.strip():
            raise ValueError("POLICY_VERSION_REQUIRED")
        self.inner_adapter = inner_adapter
        self.audit_ledger = audit_ledger
        self.audit_actor_id = audit_actor_id.strip()
        self.policy_version = policy_version.strip()

    def run(self, mind: Any, task: Any) -> Any:
        """Invoke the inner adapter only after ledger admission; return safe status on audit failure."""
        canonical_input = {
            "mind_id": getattr(mind, "id", None),
            "role": getattr(mind, "role", None),
            "provider": getattr(mind, "provider", None),
            "endpoint": getattr(mind, "endpoint", None),
            "task_id": getattr(task, "id", None),
            "objective": getattr(task, "objective", None),
            "kind": getattr(task, "kind", None),
            "context": getattr(task, "context", None),
            "constraints": getattr(task, "constraints", None),
        }
        request_id = "vxreq-mind-" + uuid4().hex
        trace_id = "vxtrace-task-" + hashlib.sha256(str(canonical_input["task_id"]).encode()).hexdigest()[:24]
        prompt_digest = hashlib.sha256(_canonical_bytes(canonical_input)).hexdigest()
        provider = getattr(mind, "provider", None)
        model_id = getattr(mind, "id", None)
        if not isinstance(provider, str) or not provider.strip():
            provider = "unknown"
        if not isinstance(model_id, str) or not model_id.strip():
            model_id = "unknown"

        try:
            self.audit_ledger.create_request({
                "request_id": request_id,
                "trace_id": trace_id,
                "parent_request_id": None,
                "tenant_id": None,
                "actor_id": self.audit_actor_id,
                "agent_id": model_id,
                "purpose": str(getattr(task, "kind", "general") or "general"),
                "provider": provider,
                "model_id": model_id,
                "model_version": None,
                "policy_version": self.policy_version,
                "input_hash": prompt_digest,
                "input_ref": None,
                "input_tokens": None,
                "input_classification": "INTERNAL",
            })
            self.audit_ledger.transition_status(
                request_id, "VALIDATING", changed_by=self.audit_actor_id
            )
            self.audit_ledger.transition_status(
                request_id, "RUNNING", changed_by=self.audit_actor_id
            )
        except Exception as exc:
            return {
                "status": "audit_blocked",
                "reason": type(exc).__name__,
                "audit_request_id": request_id,
                "audit_trace_id": trace_id,
            }

        started_at = _utc_now()
        started_clock = perf_counter()
        try:
            result = self.inner_adapter.run(mind, task)
        except Exception as exc:
            reason = type(exc).__name__
            is_timeout = isinstance(exc, TimeoutError) or "timeout" in reason.lower()
            attempt_status = "TIMED_OUT" if is_timeout else "FAILED"
            terminal_status = "TIMED_OUT" if is_timeout else "FAILED"
            try:
                completed_at = _utc_now()
                self.audit_ledger.record_attempt(request_id, {
                    "attempt_id": "attempt-1",
                    "attempt_number": 1,
                    "provider": provider,
                    "model_id": model_id,
                    "status": attempt_status,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "latency_ms": round((perf_counter() - started_clock) * 1000, 3),
                    "finish_reason": reason,
                })
                self.audit_ledger.transition_status(
                    request_id, terminal_status, changed_by=self.audit_actor_id,
                    reason="ADAPTER_EXCEPTION:" + reason,
                )
            except Exception:
                return {
                    "status": "audit_evidence_pending",
                    "provider_status": "error",
                    "reason": "ADAPTER_FAILED_AND_AUDIT_WRITE_FAILED",
                    "audit_request_id": request_id,
                    "audit_trace_id": trace_id,
                }
            return {
                "status": "provider_error",
                "reason": reason,
                "audit_request_id": request_id,
                "audit_trace_id": trace_id,
            }

        result_status = _safe_result_status(result)
        if result_status in {"not_configured", "invalid_input"}:
            try:
                self.audit_ledger.transition_status(
                    request_id, "FAILED", changed_by=self.audit_actor_id,
                    reason="ADAPTER_" + result_status.upper(),
                )
            except Exception:
                return {
                    "status": "audit_evidence_pending",
                    "provider_status": result_status,
                    "audit_request_id": request_id,
                    "audit_trace_id": trace_id,
                }
            if isinstance(result, dict):
                output = dict(result)
                output.update({"audit_request_id": request_id, "audit_trace_id": trace_id})
                return output
            return {
                "status": result_status,
                "audit_request_id": request_id,
                "audit_trace_id": trace_id,
            }

        if result_status in {"error", "provider_error", "failed"}:
            reason = result.get("reason", result_status) if isinstance(result, dict) else result_status
            if not isinstance(reason, str) or not reason:
                reason = result_status
            try:
                completed_at = _utc_now()
                self.audit_ledger.record_attempt(request_id, {
                    "attempt_id": "attempt-1",
                    "attempt_number": 1,
                    "provider": provider,
                    "model_id": model_id,
                    "status": "FAILED",
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "latency_ms": round((perf_counter() - started_clock) * 1000, 3),
                    "finish_reason": "ADAPTER_REPORTED_ERROR",
                })
                self.audit_ledger.transition_status(
                    request_id, "FAILED", changed_by=self.audit_actor_id,
                    reason="ADAPTER_REPORTED_ERROR",
                )
            except Exception:
                return {
                    "status": "audit_evidence_pending",
                    "provider_status": result_status,
                    "audit_request_id": request_id,
                    "audit_trace_id": trace_id,
                }
            # Do not pass through potentially sensitive exception payloads.
            return {
                "status": "provider_error",
                "reason": "ADAPTER_REPORTED_ERROR",
                "audit_request_id": request_id,
                "audit_trace_id": trace_id,
            }

        try:
            normalized_result = result if isinstance(result, (dict, list, str, int, float, bool)) or result is None else repr(result)
            output_hash = hashlib.sha256(_canonical_bytes(normalized_result)).hexdigest()
            usage = result.get("usage") if isinstance(result, dict) else None
            if not isinstance(usage, dict):
                usage = {}
            input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
            output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
            if isinstance(input_tokens, bool) or not isinstance(input_tokens, int) or input_tokens < 0:
                input_tokens = None
            if isinstance(output_tokens, bool) or not isinstance(output_tokens, int) or output_tokens < 0:
                output_tokens = None
            response_id = result.get("response_id", result.get("id")) if isinstance(result, dict) else None
            if not isinstance(response_id, str) or not response_id.strip():
                response_id = None
            completed_at = _utc_now()
            self.audit_ledger.record_attempt(request_id, {
                "attempt_id": "attempt-1",
                "attempt_number": 1,
                "provider": provider,
                "model_id": model_id,
                "status": "SUCCEEDED",
                "started_at": started_at,
                "completed_at": completed_at,
                "latency_ms": round((perf_counter() - started_clock) * 1000, 3),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "finish_reason": result.get("finish_reason", result.get("stop_reason")) if isinstance(result, dict) else None,
                "provider_request_id": response_id,
            })
            self.audit_ledger.record_output(request_id, {
                "output_id": "output-1",
                "output_hash": output_hash,
                "output_ref": None,
                "output_tokens": output_tokens,
                "format": "json",
                "classification": "INTERNAL",
            })
            self.audit_ledger.transition_status(
                request_id, "SUCCEEDED", changed_by=self.audit_actor_id
            )
        except Exception as exc:
            return {
                "status": "audit_evidence_pending",
                "reason": type(exc).__name__,
                "audit_request_id": request_id,
                "audit_trace_id": trace_id,
            }

        if isinstance(result, dict):
            output = dict(result)
            output["audit_request_id"] = request_id
            output["audit_trace_id"] = trace_id
            return output
        return {
            "status": "ok",
            "output": result,
            "audit_request_id": request_id,
            "audit_trace_id": trace_id,
        }
