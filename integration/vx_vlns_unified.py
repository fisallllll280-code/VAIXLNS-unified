"""Single entry point for the governed VX + VLNS workflow.

This facade composes the existing VLNS activation gate and capability router with
VX's execution handlers. It does not replace either subsystem or grant authority.
A task is dispatched only after remote activation and local evidence recording
both succeed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from vlns import ActivationOutcome, ActivationRequest, VLNSActivationBridge, VLNSRuntime


@dataclass(frozen=True)
class UnifiedRunResult:
    """Auditable outcome for one VX–VLNS task attempt."""

    status: str
    capability: str
    activation_id: str = ""
    activation_status: str = ""
    reason: str = ""
    result: Any = None

    @property
    def executed(self) -> bool:
        return self.status == "EXECUTED"


class VXVLNSUnifiedCore:
    """Unified task API over VLNS activation and VX capability dispatch.

    runtime owns lifecycle and capability routing. activation_bridge owns the
    signed VLNS activation handshake and evidence acknowledgement. The caller
    supplies handlers already admitted by the surrounding VX governance layer.
    """

    def __init__(
        self,
        runtime: VLNSRuntime,
        activation_bridge: VLNSActivationBridge,
    ) -> None:
        self.runtime = runtime
        self.activation_bridge = activation_bridge

    def run(
        self,
        *,
        request: ActivationRequest,
        capability: str,
        payload: Mapping[str, Any],
        handlers: Mapping[str, Callable[[dict[str, Any]], Any]],
    ) -> UnifiedRunResult:
        """Activate a model, require evidence, then dispatch one capability.

        Fail-closed rule: no handler is called unless activation status is
        ACTIVATED_AND_RECORDED and both confirmation flags are true.
        """
        activation: ActivationOutcome = self.activation_bridge.activate(request)
        if not (
            activation.status == "ACTIVATED_AND_RECORDED"
            and activation.activated
            and activation.evidence_recorded
            and activation.activation_id
            and activation.envelope_hash
        ):
            return UnifiedRunResult(
                status="HOLD",
                capability=capability,
                activation_id=activation.activation_id,
                activation_status=activation.status,
                reason=activation.reason or "ACTIVATION_OR_EVIDENCE_NOT_CONFIRMED",
            )

        try:
            result = self.runtime.dispatch(
                capability,
                dict(payload),
                dict(handlers),
            )
        except (LookupError, KeyError, ValueError) as exc:
            return UnifiedRunResult(
                status="HOLD",
                capability=capability,
                activation_id=activation.activation_id,
                activation_status=activation.status,
                reason=str(exc) or type(exc).__name__,
            )
        except Exception as exc:
            return UnifiedRunResult(
                status="EXECUTION_FAILED",
                capability=capability,
                activation_id=activation.activation_id,
                activation_status=activation.status,
                reason="HANDLER_EXCEPTION:" + type(exc).__name__,
            )

        return UnifiedRunResult(
            status="EXECUTED",
            capability=capability,
            activation_id=activation.activation_id,
            activation_status=activation.status,
            reason="ACTIVATION_EVIDENCE_CONFIRMED_AND_CAPABILITY_DISPATCHED",
            result=result,
        )
