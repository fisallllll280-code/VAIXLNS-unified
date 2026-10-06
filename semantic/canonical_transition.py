from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Tuple


class AdmissionState(str, Enum):
    UNKNOWN = "UNKNOWN"
    HYPOTHESIZED = "HYPOTHESIZED"
    DESIGNED = "DESIGNED"
    IMPLEMENTED = "IMPLEMENTED"
    BOOTABLE = "BOOTABLE"
    RUNNING = "RUNNING"
    OBSERVED = "OBSERVED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    PROVEN = "PROVEN"
    ADMITTED = "ADMITTED"
    CANONICAL = "CANONICAL"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    kind: str
    digest: str


@dataclass(frozen=True)
class ProofRef:
    proof_id: str
    kind: str
    digest: str


@dataclass(frozen=True)
class AuthorityRef:
    authority_id: str
    decision: str
    digest: str


@dataclass(frozen=True)
class CanonicalSemanticTransition:
    identity: str
    subject: str
    intent: str
    semantic_context: Mapping[str, Any]
    pre_state: Mapping[str, Any]
    constraints: Tuple[str, ...]
    capability: str
    plan: Mapping[str, Any]
    operation: str
    inputs: Mapping[str, Any]
    expected_post_state: Mapping[str, Any]
    observed_post_state: Mapping[str, Any]
    transition_time: str
    causal_parents: Tuple[str, ...] = ()
    evidence: Tuple[EvidenceRef, ...] = ()
    verification: Tuple[str, ...] = ()
    proof: Tuple[ProofRef, ...] = ()
    authority: AuthorityRef | None = None
    lineage: Tuple[str, ...] = ()
    replay_recipe: Mapping[str, Any] = None
    admission_state: AdmissionState = AdmissionState.UNKNOWN

    def validate(self) -> None:
        required = {
            "identity": self.identity,
            "subject": self.subject,
            "intent": self.intent,
            "capability": self.capability,
            "operation": self.operation,
            "transition_time": self.transition_time,
        }
        missing = tuple(k for k, v in required.items() if not v)
        if missing:
            raise ValueError("MISSING_REQUIRED_FIELDS:" + ",".join(missing))
        if self.admission_state in {
            AdmissionState.VERIFIED,
            AdmissionState.PROVEN,
            AdmissionState.ADMITTED,
            AdmissionState.CANONICAL,
        } and not self.verification:
            raise ValueError("VERIFICATION_REQUIRED")
        if self.admission_state in {
            AdmissionState.PROVEN,
            AdmissionState.ADMITTED,
            AdmissionState.CANONICAL,
        } and not self.proof:
            raise ValueError("PROOF_REQUIRED")
        if self.admission_state in {
            AdmissionState.ADMITTED,
            AdmissionState.CANONICAL,
        } and self.authority is None:
            raise ValueError("AUTHORITY_REQUIRED")
        if self.admission_state == AdmissionState.CANONICAL and not self.evidence:
            raise ValueError("EVIDENCE_REQUIRED")
        if self.replay_recipe is None and self.admission_state in {
            AdmissionState.PROVEN,
            AdmissionState.ADMITTED,
            AdmissionState.CANONICAL,
        }:
            raise ValueError("REPLAY_RECONSTRUCTION_REQUIRED")

    def fingerprint(self) -> str:
        self.validate()
        payload = {
            "identity": self.identity,
            "subject": self.subject,
            "intent": self.intent,
            "semantic_context": dict(self.semantic_context),
            "pre_state": dict(self.pre_state),
            "constraints": list(self.constraints),
            "capability": self.capability,
            "plan": dict(self.plan),
            "operation": self.operation,
            "inputs": dict(self.inputs),
            "expected_post_state": dict(self.expected_post_state),
            "observed_post_state": dict(self.observed_post_state),
            "transition_time": self.transition_time,
            "causal_parents": list(self.causal_parents),
            "evidence": [e.__dict__ for e in self.evidence],
            "verification": list(self.verification),
            "proof": [p.__dict__ for p in self.proof],
            "authority": self.authority.__dict__ if self.authority else None,
            "lineage": list(self.lineage),
            "replay_recipe": dict(self.replay_recipe or {}),
            "admission_state": self.admission_state.value,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        return sha256(raw).hexdigest()
