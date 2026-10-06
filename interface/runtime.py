"""Executable mission-interface command boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from interface.manifest import InterfaceFactory, InterfaceInvention


@dataclass(frozen=True)
class InterfaceCommand:
    session_id: str
    control: str
    intent: str
    allowed: bool
    reason: str


@dataclass(frozen=True)
class InterfaceSession:
    session_id: str
    manifest: InterfaceInvention


class InterfaceRuntime:
    def __init__(self, factory: InterfaceFactory | None = None) -> None:
        self.factory = factory or InterfaceFactory()

    def open(self, session_id: str, mission: str, domains: Tuple[str, ...]) -> InterfaceSession:
        return InterfaceSession(session_id=session_id, manifest=self.factory.build(mission, domains))

    def command(
        self,
        session: InterfaceSession,
        control: str,
        *,
        intent: str,
        permitted_controls: Mapping[str, bool] | None = None,
    ) -> InterfaceCommand:
        allowed_by_manifest = control in session.manifest.controls
        allowed_by_policy = (permitted_controls or {}).get(control, True)
        allowed = allowed_by_manifest and allowed_by_policy
        if not allowed_by_manifest:
            reason = "CONTROL_NOT_IN_MANIFEST"
        elif not allowed_by_policy:
            reason = "CONTROL_DENIED_BY_POLICY"
        else:
            reason = "UI_COMMAND_READY"
        return InterfaceCommand(session.session_id, control, intent, allowed, reason)
