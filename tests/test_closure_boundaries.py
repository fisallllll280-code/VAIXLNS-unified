import tempfile
import unittest
from pathlib import Path

from evolution.governed_change import admit_proposal, create_proposal
from federation.source_snapshot import SnapshotDetector, SnapshotEntry, SnapshotManifest
from intent.v_ir import Intent, compile_intent
from interface.runtime import InterfaceRuntime
from operations.telemetry import InMemoryTelemetry, Telemetry
from provenance.attestation import Material, build_attestation
from tools.productivity_router import ProductivityRouter, ToolCandidate
from closure.operational_closure import MCPTrustRegistry, ToolRecord


class ClosureBoundaryTests(unittest.TestCase):
    def test_intent_is_deterministically_normalized(self):
        intent = Intent(
            intent_id="i1",
            actor_id="actor",
            objective="  solve  ",
            capability="math.solve",
            inputs={"b": 2, "a": 1},
            constraints=(" x ", "x", ""),
        )
        plan = compile_intent(intent)
        self.assertEqual(plan.objective, "solve")
        self.assertEqual(plan.constraints, ("x",))
        self.assertTrue(plan.plan_digest)

    def test_tool_router_is_trust_first(self):
        router = ProductivityRouter()
        tools = [
            ToolCandidate("fast", "s1", frozenset({"search"}), approved=False, health="healthy", reliability=1, evidence_strength=1),
            ToolCandidate("good", "s2", frozenset({"search"}), approved=True, health="healthy", reliability=.99, evidence_strength=.99, latency_ms=20),
            ToolCandidate("bad-health", "s3", frozenset({"search"}), approved=True, health="down", reliability=1, evidence_strength=1),
        ]
        selection = router.select("search", tools)
        self.assertEqual(selection.selected[0].name, "good")
        self.assertEqual({name for name, _ in selection.rejected}, {"fast", "bad-health"})

    def test_snapshot_change_detection(self):
        old = SnapshotManifest.from_entries("r", "main", "c1", "t1", [SnapshotEntry("a", "1"), SnapshotEntry("b", "2")])
        new = SnapshotManifest.from_entries("r", "main", "c2", "t2", [SnapshotEntry("a", "9"), SnapshotEntry("c", "3")])
        delta = SnapshotDetector.compare(old, new)
        self.assertEqual(delta.changed, ("a",))
        self.assertEqual(delta.added, ("c",))
        self.assertEqual(delta.removed, ("b",))
        self.assertTrue(delta.commit_changed)

    def test_attestation_is_explicitly_unsigned(self):
        att = build_attestation(
            subject_name="artifact",
            subject_digest="abc",
            builder_id="local-ci",
            build_type="vaixlns:test",
            materials=(Material("git:repo@c1", {"sha256": "def"}),),
        )
        self.assertEqual(att.signature_status, "UNSIGNED")
        self.assertTrue(att.attestation_digest)

    def test_telemetry_sink(self):
        sink = InMemoryTelemetry()
        telemetry = Telemetry([sink])
        telemetry.event("commit", kind="trace", trace_id="t1", span_id="s1", attributes={"status": "ok"})
        self.assertEqual(sink.names(), ("commit",))

    def test_interface_runtime_exposes_only_manifest_controls(self):
        session = InterfaceRuntime().open("s1", "mission", ("mathematics",))
        ok = InterfaceRuntime().command(session, "verify", intent="check")
        bad = InterfaceRuntime().command(session, "erase", intent="x")
        self.assertTrue(ok.allowed)
        self.assertFalse(bad.allowed)

    def test_mcp_registry_recommendation_uses_productivity_router(self):
        registry = MCPTrustRegistry()
        registry.register(ToolRecord(
            name="slow", server="s1", scope=("search",), approved=True,
            health="healthy", provenance="p1", reliability=.9,
            evidence_strength=.9, latency_ms=300
        ))
        registry.register(ToolRecord(
            name="fast-untrusted", server="s2", scope=("search",), approved=False,
            health="healthy", provenance="p2", reliability=1,
            evidence_strength=1, latency_ms=1
        ))
        result = registry.recommend("search")
        self.assertEqual(result.selected[0].name, "slow")

    def test_governed_change_requires_real_gates(self):
        proposal = create_proposal(
            candidate_id="c1",
            base_branch="main",
            proposed_branch="feature/c1",
            required_checks=("tests", "replay"),
            impact_nodes=("vx", "ledger"),
            verified=True,
            independent=True,
            replayable=True,
        )
        self.assertFalse(admit_proposal(proposal, explicit_authority=False).accepted)
        self.assertTrue(admit_proposal(proposal, explicit_authority=True).accepted)


if __name__ == "__main__":
    unittest.main()
