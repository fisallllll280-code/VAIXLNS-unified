"""Runtime governance telemetry; observation only, no commit authority."""
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class GovernanceSnapshot:
    ready: bool
    blocked: bool
    checks: dict[str, bool]
    reason: str = ""

def inspect(*, capability_available: bool, policy_allowed: bool,
            topology_available: bool, proof_admitted: bool) -> GovernanceSnapshot:
    checks = {
        "capability": capability_available,
        "policy": policy_allowed,
        "topology": topology_available,
        "proof": proof_admitted,
    }
    ok = all(checks.values())
    return GovernanceSnapshot(
        ready=ok,
        blocked=not ok,
        checks=checks,
        reason="READY" if ok else "GOVERNANCE_GATE_BLOCKED",
    )
