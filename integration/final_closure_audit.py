"""Executable local closure audit for the VAIXLNS-unified implementation surface.

The audit intentionally separates local executable evidence from external
deployment evidence. A local PASS never promotes the project to production.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from tempfile import TemporaryDirectory
from pathlib import Path
import importlib
from typing import Any

from federation.source_snapshot import SnapshotDetector, SnapshotEntry, SnapshotManifest
from governance.capability_registry import Capability, CapabilityRegistry
from governance.governance_engine import GovernanceEngine
from intent.v_ir import Intent, compile_intent
from nexus.typed_graph import CanonicalNexus, Entity
from operations.telemetry import InMemoryTelemetry, Telemetry
from provenance.attestation import build_attestation
from scck import Artifact, Contract, ExternalObservation, KernelState, SCCKKernel, canonical_hash
from tools.productivity_router import ProductivityRouter, ToolCandidate


@dataclass(frozen=True)
class AuditItem:
    id: str
    status: str
    evidence: str
    blocking: bool = False


def audit_local_closure() -> dict[str, Any]:
    items: list[AuditItem] = []

    modules = (
        "scck.kernel",
        "nexus.typed_graph",
        "intent.v_ir",
        "federation.source_snapshot",
        "provenance.attestation",
        "operations.telemetry",
        "tools.productivity_router",
        "evolution.governed_change",
        "interface.runtime",
    )
    missing = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:
            missing.append(f"{name}:{exc}")
    items.append(AuditItem(
        "LOCAL-MODULE-SURFACE",
        "PASS" if not missing else "FAIL",
        "all closure modules import" if not missing else "; ".join(missing),
        blocking=True,
    ))

    registry = CapabilityRegistry()
    registry.register(Capability("audit.smoke"))
    kernel = SCCKKernel(registry, GovernanceEngine(), authority_resolver=lambda a, c, ctx: True)
    contract = Contract("contract:audit", "1.0", "audit.smoke", "READY", "EXECUTED")
    current = Artifact(
        "artifact:audit", canonical_hash({"seed": 1}), contract.schema_cid, "default",
        "authority:audit", "local", "", contract.contract_id, "READY", 0, 1, "nonce",
        "VAIXLNS", "audit.smoke", {"seed": 1}
    )
    prepared = kernel.prepare(
        actor_id="audit", permissions={"execute"}, capability_id="audit.smoke",
        current=current, contract=contract
    )

    def adapter(intent):
        payload = {"ok": True}
        return ExternalObservation(
            intent_id=intent.intent_id, adapter_id="audit:worker", success=True,
            payload=payload, content_cid=canonical_hash(payload),
            observed_state="EXECUTED", observed_version=intent.expected_version,
            observed_epoch=intent.expected_epoch
        )

    commit = kernel.execute(
        intent=prepared.intent, current=current, adapter_id="audit:worker",
        adapter=adapter, contract=contract, policy=None
    )
    items.append(AuditItem(
        "SCCK-READBACK-COMMIT",
        "PASS" if commit.state is KernelState.COMMITTED else "FAIL",
        commit.reason,
        blocking=True,
    ))
    items.append(AuditItem(
        "SCCK-PROOF",
        "PASS" if commit.proof and commit.evidence else "FAIL",
        "Evidence + CommitProof emitted" if commit.proof and commit.evidence else "missing proof/evidence",
        blocking=True,
    ))

    router = ProductivityRouter()
    selection = router.select("search", [
        ToolCandidate("approved", "local", frozenset({"search"}), True, "healthy", .99, .99, 20, .1, .1),
        ToolCandidate("untrusted", "local", frozenset({"search"}), False, "healthy", 1, 1, 1),
    ])
    items.append(AuditItem(
        "TOOL-TRUST-FIRST",
        "PASS" if selection.selected and selection.selected[0].name == "approved" else "FAIL",
        "approved healthy tool selected before faster untrusted tool",
        blocking=True,
    ))

    graph = CanonicalNexus()
    graph.add_entity(Entity("e1", "SYSTEM", "audit"))
    graph.add_entity(Entity("e2", "CAPABILITY", "audit"))
    graph.relate("e1", "e2", "HAS_CAPABILITY", provenance=("audit",))
    with TemporaryDirectory() as tmp:
        journal = Path(tmp) / "nexus.jsonl"
        durable = CanonicalNexus(journal)
        durable.add_entity(Entity("x1", "SYSTEM", "durable"))
        durable.add_entity(Entity("x2", "CAPABILITY", "durable"))
        durable.relate("x1", "x2", "HAS_CAPABILITY", provenance=("audit",))
        durable_ok = durable.verify_journal()
    items.append(AuditItem(
        "NEXUS-DURABLE-JOURNAL",
        "PASS" if durable_ok else "FAIL",
        "append-only hash-chain journal verifies" if durable_ok else "journal integrity failed",
        blocking=True,
    ))

    old = SnapshotManifest.from_entries("repo", "main", "c1", "t1", [SnapshotEntry("a", "1")])
    new = SnapshotManifest.from_entries("repo", "main", "c2", "t2", [SnapshotEntry("a", "2")])
    delta = SnapshotDetector.compare(old, new)
    items.append(AuditItem(
        "FEDERATION-CHANGE-DETECTION",
        "PASS" if delta.changed == ("a",) and delta.commit_changed else "FAIL",
        "source snapshot delta is deterministic" if delta.changed == ("a",) else "snapshot delta mismatch",
        blocking=True,
    ))

    plan = compile_intent(Intent("intent:audit", "audit", " verify ", "audit.smoke", {"b": 2, "a": 1}, ("x", "x")))
    items.append(AuditItem(
        "INTENT-VIR",
        "PASS" if plan.objective == "verify" and plan.constraints == ("x",) and plan.plan_digest else "FAIL",
        "normalized intent produced a content digest" if plan.plan_digest else "V-IR failed",
        blocking=True,
    ))

    sink = InMemoryTelemetry()
    Telemetry([sink]).event("scck.commit", kind="trace", trace_id="t1", span_id="s1", attributes={"state": "COMMITTED"})
    items.append(AuditItem(
        "OBSERVABILITY-CONTRACT",
        "PASS" if sink.names() == ("scck.commit",) else "FAIL",
        "vendor-neutral telemetry event captured" if sink.names() == ("scck.commit",) else "telemetry event missing",
        blocking=True,
    ))

    attestation = build_attestation(
        subject_name="audit-artifact", subject_digest=commit.artifact.content_cid,
        builder_id="vaixlns-local-audit", build_type="vaixlns/closure-test"
    )
    items.append(AuditItem(
        "PROVENANCE-ATTESTATION",
        "PASS" if attestation.attestation_digest and attestation.signature_status == "UNSIGNED" else "FAIL",
        "SLSA/in-toto-shaped unsigned attestation emitted" if attestation.attestation_digest else "attestation failed",
        blocking=True,
    ))

    blocking = [item for item in items if item.blocking and item.status != "PASS"]
    return {
        "status": "LOCAL_CLOSURE_PASS" if not blocking else "LOCAL_CLOSURE_FAIL",
        "items": [asdict(item) for item in items],
        "external_evidence_required": [
            "multi-node consensus/leader election/replication/failover",
            "live telemetry collector deployment",
            "live MCP inventory and health",
            "artifact signing/attestation authority",
            "full historical 0001-2750 atomic recovery",
            "production readiness and operational finality",
        ],
    }
