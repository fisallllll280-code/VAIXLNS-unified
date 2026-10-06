"""Executable VX-CONTINUUM vertical slice.

Usage:
  python scripts/vx_continuum_run.py
"""
from __future__ import annotations
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuum.atomaton import AtomatonState
from continuum.proof import ProofLevel, ProofPolicy
from vx.atomaton_factory import spawn
from vx.topology_synthesizer import synthesize
from vx.proof_spectral_gate import evaluate
from vx.governance_monitor import inspect

def run() -> dict:
    intent_id = "intent:continuum-smoke"
    execution_id = f"exec:{uuid.uuid4()}"
    plan = synthesize(
        intent_id, "compute",
        [{"node_id": "node-01", "capabilities": ["compute"], "risk": 0.1}],
    )
    atom = spawn(
        execution_id=execution_id,
        intent_id=intent_id,
        capability_id="compute",
        contract_id="contract:continuum:v1",
        resource_boundary={"network": False, "filesystem": "workspace"},
    )
    atom = atom.transition(AtomatonState.BOUND)
    atom = atom.transition(AtomatonState.VALIDATED)
    atom = atom.transition(AtomatonState.EXECUTING)
    atom = atom.transition(AtomatonState.OBSERVED, output_cids=("cid:output",))
    proof = evaluate(
        ProofPolicy(ProofLevel.DETERMINISTIC_REPLAY),
        [ProofLevel.OBSERVATION, ProofLevel.DETERMINISTIC_REPLAY],
        verified=True,
    )
    governance = inspect(
        capability_available=True,
        policy_allowed=True,
        topology_available=bool(plan.node_ids),
        proof_admitted=proof.admitted,
    )
    return {
        "system": "VAIXLNS/VX-CONTINUUM",
        "intent_id": intent_id,
        "execution_id": execution_id,
        "atomaton_state": atom.state.value,
        "topology": {
            "nodes": list(plan.node_ids),
            "parallel": plan.parallel,
            "digest": plan.topology_digest,
        },
        "proof": {
            "admitted": proof.admitted,
            "level": proof.level.name if proof.level is not None else None,
            "reason": proof.reason,
        },
        "governance": {
            "ready": governance.ready,
            "checks": governance.checks,
            "reason": governance.reason,
        },
        "trace_digest": atom.trace_digest,
    }

if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
