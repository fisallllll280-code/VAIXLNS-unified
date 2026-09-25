import unittest

from evolution.architecture_lab import ArchitectureLab, ArchitectureSelfCritique, CausalArchitectureGraph


class ArchitectureLabTests(unittest.TestCase):
    def test_001_gap_and_002_three_designs(self):
        lab = ArchitectureLab()
        gap = lab.discover_gap(["math", "physics", "proof"], ["math"], source="mission:1")
        self.assertEqual(gap.missing, ("physics", "proof"))
        designs = lab.search_three(gap)
        self.assertEqual(len(designs), 3)
        self.assertTrue(all(d.isolated for d in designs))

    def test_004_blast_radius(self):
        graph = CausalArchitectureGraph()
        graph.add_edge("runtime", "ledger")
        graph.add_edge("ledger", "replay")
        graph.add_edge("runtime", "telemetry")
        self.assertEqual(graph.blast_radius("runtime"), ("ledger", "replay", "telemetry"))

    def test_005_assessment_and_011_012_self_critique(self):
        lab = ArchitectureLab()
        gap = lab.discover_gap(["sim"], [], source="mission:2")
        design = lab.search_three(gap)[0]
        assessment = lab.assess(
            design,
            {"correctness": 0.99, "reliability": 0.95},
            {"correctness": 0.9, "reliability": 0.9},
            ["sim:test-1"],
        )
        self.assertTrue(assessment.verified)
        critique = ArchitectureSelfCritique().critique(
            design.id, {"latency": 120, "error_rate": 0.2}, {"latency": 100, "error_rate": 0.05}
        )
        self.assertTrue(critique["drift"])
        revision = ArchitectureSelfCritique().propose_revision(design.id, critique["violations"])
        self.assertTrue(revision.isolated)
        self.assertNotEqual(revision.id, design.id)


if __name__ == "__main__":
    unittest.main()
