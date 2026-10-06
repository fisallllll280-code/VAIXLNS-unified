"""Sovereign Cloud Contract Kernel V1.

The kernel is deliberately small and executable. It enforces the distinction:
Identity != Authority != Capability != Execution != Proof.

External adapters can produce observations, but they cannot finalize canonical
state. Final state is produced only by this kernel after read-back and evidence
verification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Optional

from governance.capability_registry import CapabilityRegistry
from governance.governance_engine import GovernanceEngine, Policy


def _stable(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )


def canonical_hash(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


class KernelState(str, Enum):
    PREPARED = "PREPARED"
    EXECUTING = "EXECUTING"
    OBSERVED = "OBSERVED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    content_cid: str
    schema_cid: str
    policy_cid: str
    authority_cid: str
    provenance_cid: str
    parent_cid: str
    contract_cid: str
    state: str
    version: int
    epoch: int
    nonce: str
    issued_by: str
    authorized_for: str
    payload: Mapping[str, Any]
    signature: str = ""
    proof_bundle: str = ""


@dataclass(frozen=True)
class Contract:
    contract_id: str
    version: str
    capability_id: str
    source_state: str
    target_state: str
    schema_cid: str = "schema:scck:v1"
    required_epoch: Optional[int] = None
    max_version_delta: int = 1
    require_observation_signature: bool = False

    def validate_artifact(self, artifact: Artifact) -> tuple[bool, str]:
        if artifact.contract_cid != self.contract_id:
            return False, "CONTRACT_MISMATCH"
        if artifact.state != self.source_state:
            return False, "SOURCE_STATE_MISMATCH"
        if self.required_epoch is not None and artifact.epoch != self.required_epoch:
            return False, "EPOCH_MISMATCH"
        if artifact.schema_cid != self.schema_cid:
            return False, "SCHEMA_MISMATCH"
        if self.max_version_delta != 1:
            return False, "VERSION_DELTA_POLICY_UNSUPPORTED"
        if artifact.authorized_for != self.capability_id:
            return False, "CAPABILITY_BINDING_MISMATCH"
        return True, "OK"


@dataclass(frozen=True)
class CommitIntent:
    intent_id: str
    artifact_id: str
    capability_id: str
    actor_id: str
    authority_id: str
    policy_id: str
    contract_id: str
    expected_state: str
    expected_version: int
    expected_epoch: int
    expected_schema_cid: str
    nonce: str
    created_at: str
    precondition_digest: str
    status: KernelState = KernelState.PREPARED


@dataclass(frozen=True)
class ExternalObservation:
    intent_id: str
    adapter_id: str
    success: bool
    payload: Any
    content_cid: str
    observed_state: str
    observed_version: int
    observed_epoch: int
    signature: str = ""
    external_reference: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class EvidenceRecord:
    intent_id: str
    artifact_id: str
    adapter_id: str
    observation_cid: str
    input_cid: str
    contract_cid: str
    policy_cid: str
    authority_cid: str
    verification_status: str
    created_at: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class CommitProof:
    intent_id: str
    artifact_id: str
    evidence_fingerprint: str
    previous_version: int
    committed_version: int
    epoch: int
    state: str
    issued_at: str
    proof_digest: str

    @classmethod
    def issue(
        cls, *, intent: CommitIntent, evidence: EvidenceRecord, artifact: Artifact
    ) -> "CommitProof":
        issued_at = datetime.now(timezone.utc).isoformat()
        body = {
            "intent_id": intent.intent_id,
            "artifact_id": artifact.artifact_id,
            "evidence": evidence.fingerprint,
            "previous_version": artifact.version - 1,
            "committed_version": artifact.version,
            "epoch": artifact.epoch,
            "state": artifact.state,
            "issued_at": issued_at,
        }
        return cls(
            intent_id=intent.intent_id,
            artifact_id=artifact.artifact_id,
            evidence_fingerprint=evidence.fingerprint,
            previous_version=artifact.version - 1,
            committed_version=artifact.version,
            epoch=artifact.epoch,
            state=artifact.state,
            issued_at=issued_at,
            proof_digest=canonical_hash(body),
        )


@dataclass(frozen=True)
class SCCKOutcome:
    state: KernelState
    artifact: Optional[Artifact] = None
    intent: Optional[CommitIntent] = None
    observation: Optional[ExternalObservation] = None
    evidence: Optional[EvidenceRecord] = None
    proof: Optional[CommitProof] = None
    reason: str = ""


class SovereignKeyDomain:
    """Reference boundary for sovereign signing operations.

    Real secrets remain outside source control. A caller may inject a signer
    backed by HSM/Secure Enclave/KMS. Adapters are explicitly outside KSD.
    """

    def __init__(self, signer: Optional[Callable[[bytes], str]] = None) -> None:
        self._signer = signer

    def seal(self, payload: Any) -> str:
        raw = _stable(payload).encode("utf-8")
        if self._signer is not None:
            return self._signer(raw)
        return sha256(raw).hexdigest()

    @staticmethod
    def assert_adapter_outside(adapter_id: str) -> None:
        if not adapter_id or adapter_id.upper().startswith("KSD:"):
            raise PermissionError("ADAPTER_MUST_REMAIN_OUTSIDE_KSD")


class SCCKKernel:
    """Executable contract and canonical-commit kernel for VX."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        governance: GovernanceEngine,
        *,
        authority_resolver: Optional[
            Callable[[str, str, Mapping[str, Any]], bool]
        ] = None,
        key_domain: Optional[SovereignKeyDomain] = None,
    ) -> None:
        self.capability_registry = capability_registry
        self.governance = governance
        self.authority_resolver = authority_resolver or (
            lambda actor_id, capability_id, _context: bool(actor_id and capability_id)
        )
        self.key_domain = key_domain or SovereignKeyDomain()
        self._committed: dict[str, SCCKOutcome] = {}

    def prepare(
        self,
        *,
        actor_id: str,
        permissions: set[str] | frozenset[str],
        capability_id: str,
        current: Artifact,
        contract: Contract,
        policy: Optional[Policy] = None,
        authority_id: Optional[str] = None,
        context: Optional[Mapping[str, Any]] = None,
        nonce: str = "",
    ) -> SCCKOutcome:
        ctx = dict(context or {})
        if not actor_id:
            return SCCKOutcome(KernelState.REJECTED, reason="IDENTITY_REQUIRED")
        if not self.capability_registry.can_execute(capability_id):
            return SCCKOutcome(KernelState.REJECTED, reason="CAPABILITY_UNAVAILABLE")
        valid_contract, contract_reason = contract.validate_artifact(current)
        if not valid_contract:
            return SCCKOutcome(KernelState.REJECTED, reason=contract_reason)

        governance = self.governance.evaluate(
            actor_id=actor_id,
            permissions=permissions,
            capability=capability_id,
            policy=policy,
            context=ctx,
        )
        if not governance.allowed:
            return SCCKOutcome(KernelState.REJECTED, reason=governance.reason)

        authority_key = authority_id or f"authority:{actor_id}"
        if not self.authority_resolver(actor_id, capability_id, ctx):
            return SCCKOutcome(KernelState.REJECTED, reason="AUTHORITY_DENIED")

        intent_seed = {
            "artifact_id": current.artifact_id,
            "actor_id": actor_id,
            "capability_id": capability_id,
            "authority_id": authority_key,
            "policy_id": governance.policy_id,
            "contract_id": contract.contract_id,
            "source_state": current.state,
            "target_state": contract.target_state,
            "version": current.version + 1,
            "epoch": current.epoch,
            "nonce": nonce,
        }
        intent_id = canonical_hash(intent_seed)[:24]
        intent = CommitIntent(
            intent_id=intent_id,
            artifact_id=current.artifact_id,
            capability_id=capability_id,
            actor_id=actor_id,
            authority_id=authority_key,
            policy_id=governance.policy_id,
            contract_id=contract.contract_id,
            expected_state=contract.target_state,
            expected_version=current.version + 1,
            expected_epoch=current.epoch,
            expected_schema_cid=contract.schema_cid,
            nonce=nonce or intent_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            precondition_digest=canonical_hash(asdict(current)),
        )
        return SCCKOutcome(
            KernelState.PREPARED, artifact=current, intent=intent, reason="COMMIT_INTENT_CREATED"
        )

    def execute(
        self,
        *,
        intent: CommitIntent,
        current: Artifact,
        adapter_id: str,
        adapter: Callable[[CommitIntent], ExternalObservation],
        contract: Contract,
        policy: Optional[Policy],
    ) -> SCCKOutcome:
        self.key_domain.assert_adapter_outside(adapter_id)
        if intent.status is not KernelState.PREPARED:
            return SCCKOutcome(KernelState.REJECTED, intent=intent, artifact=current, reason="INVALID_INTENT_STATE")
        observation = adapter(intent)
        return self.finalize(
            intent=intent,
            current=current,
            observation=observation,
            contract=contract,
            policy=policy,
        )

    def finalize(
        self,
        *,
        intent: CommitIntent,
        current: Artifact,
        observation: ExternalObservation,
        contract: Contract,
        policy: Optional[Policy],
    ) -> SCCKOutcome:
        cached = self._committed.get(intent.intent_id)
        if cached is not None:
            return cached
        if observation.intent_id != intent.intent_id:
            return SCCKOutcome(KernelState.REJECTED, intent=intent, artifact=current, observation=observation, reason="OBSERVATION_INTENT_MISMATCH")
        self.key_domain.assert_adapter_outside(observation.adapter_id)
        if not observation.success:
            return SCCKOutcome(
                KernelState.REJECTED,
                intent=intent,
                artifact=current,
                observation=observation,
                reason=observation.failure_reason or "ADAPTER_EXECUTION_FAILED",
            )
        if observation.observed_version != intent.expected_version:
            return SCCKOutcome(KernelState.QUARANTINED, intent=intent, observation=observation, reason="READBACK_VERSION_MISMATCH")
        if observation.observed_epoch != intent.expected_epoch:
            return SCCKOutcome(KernelState.QUARANTINED, intent=intent, observation=observation, reason="READBACK_EPOCH_MISMATCH")
        if observation.observed_state != intent.expected_state:
            return SCCKOutcome(KernelState.QUARANTINED, intent=intent, observation=observation, reason="READBACK_STATE_MISMATCH")
        if contract.require_observation_signature and not observation.signature:
            return SCCKOutcome(KernelState.QUARANTINED, intent=intent, observation=observation, reason="OBSERVATION_SIGNATURE_REQUIRED")

        if canonical_hash(observation.payload) != observation.content_cid:
            return SCCKOutcome(KernelState.QUARANTINED, intent=intent, observation=observation, reason="CID_MISMATCH")
        if current.schema_cid != intent.expected_schema_cid:
            return SCCKOutcome(KernelState.QUARANTINED, intent=intent, observation=observation, reason="SCHEMA_MISMATCH")

        evidence = EvidenceRecord(
            intent_id=intent.intent_id,
            artifact_id=current.artifact_id,
            adapter_id=observation.adapter_id,
            observation_cid=observation.content_cid,
            input_cid=canonical_hash(current.payload),
            contract_cid=contract.contract_id,
            policy_cid=policy.policy_id if policy else intent.policy_id,
            authority_cid=intent.authority_id,
            verification_status="VERIFIED",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        signature = self.key_domain.seal(
            {
                "intent": asdict(intent),
                "observation": asdict(observation),
                "evidence": asdict(evidence),
            }
        )
        payload = observation.payload if isinstance(observation.payload, Mapping) else {"value": observation.payload}
        updated = replace(
            current,
            content_cid=observation.content_cid,
            contract_cid=contract.contract_id,
            state=observation.observed_state,
            version=observation.observed_version,
            epoch=observation.observed_epoch,
            issued_by="VAIXLNS/SCCK",
            authorized_for=intent.capability_id,
            payload=payload,
            signature=signature,
            proof_bundle=evidence.fingerprint,
        )
        proof = CommitProof.issue(intent=intent, evidence=evidence, artifact=updated)
        outcome = SCCKOutcome(
            KernelState.COMMITTED,
            artifact=updated,
            intent=intent,
            observation=observation,
            evidence=evidence,
            proof=proof,
            reason="CANONICAL_STATE_FINALIZED",
        )
        self._committed[intent.intent_id] = outcome
        return outcome
