"""Evidence bundle construction for executable conformance checks."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any

def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class EvidenceBundle:
    execution_id: str
    input_hash: str
    output_hash: str
    capability: str
    contract_hash: str
    policy_hash: str
    runtime_identity: str
    verification_status: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(asdict(self))

class EvidenceCollector:
    def collect(
        self,
        *,
        execution_id: str,
        inputs: Any,
        output: Any,
        capability: str,
        contract: Any,
        policy: Any,
        runtime_identity: str,
        verification_status: str,
    ) -> EvidenceBundle:
        return EvidenceBundle(
            execution_id=execution_id,
            input_hash=canonical_hash(inputs),
            output_hash=canonical_hash(output),
            capability=capability,
            contract_hash=canonical_hash(contract),
            policy_hash=canonical_hash(policy),
            runtime_identity=runtime_identity,
            verification_status=verification_status,
        )
