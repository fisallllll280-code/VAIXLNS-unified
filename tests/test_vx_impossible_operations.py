import unittest

from vx.invention_engine import Capability, CapabilityGenome, InnovationLoop, MemoryFabric, Mission
from vx.runtime_supervisor import Phase, VXSupervisor


class ImpossibleOperationsTests(unittest.TestCase):
    def test_capability_recombination_and_promotion(self):
        genome = CapabilityGenome([
            Capability(
                id="math.constraint_solver",
                kind="capability",
                domains=("mathematics", "cross-domain"),
                inputs=("equation",),
                outputs=("constraint",),
                invariants=("closed-form-or-proof",),
                evidence=("math-test-001",),
            ),
            Capability(
                id="physics.simulator",
                kind="capability",
                domains=("physics", "cross-domain"),
                inputs=("constraint",),
                outputs=("trajectory",),
                invariants=("energy-accounted",),
                evidence=("physics-test-001",),
            ),
        ])
        memory = MemoryFabric()

        def simulate(candidate):
            return {"simulated": True, "tested": True, "trajectory_error": 0.01}

        def verify(candidate, result):
            return {
                "verified": result["trajectory_error"] < 0.05,
                "evidence": ["sim-001", "test-001"],
                "metrics": {"error": result["trajectory_error"]},
            }

        loop = InnovationLoop(genome, memory, simulate, verify)
        results = loop.run(
            Mission(
                objective="solve coupled math-physics design",
                domains=("mathematics", "physics"),
                constraints=("energy-accounted",),
            ),
            limit=2,
        )
        self.assertTrue(results)
        self.assertTrue(any(r.verified for _, r in results))
        self.assertGreaterEqual(len(genome.snapshot()), 3)
        self.assertTrue(memory.snapshot())

    def test_memory_branch_and_invalidation(self):
        memory = MemoryFabric()
        root = memory.write("hypothesis", {"value": 3}, ["source:A"])
        child = memory.branch(root.id, {"value": 4}, ["experiment:B"])
        self.assertEqual(child.parent_id, root.id)
        self.assertEqual(child.value["value"], 4)
        memory.invalidate(root.id)
        self.assertEqual(memory.get(root.id).status, "invalid")
        self.assertEqual(memory.get(child.id).status, "active")

    def test_runtime_requires_authority_and_supports_replay_and_recovery(self):
        sup = VXSupervisor(
            authorizer=lambda op: True,
            executor=lambda op: {"ok": True},
            verifier=lambda op, result: result.get("ok") is True,
        )
        op = sup.prepare("op-1", "build verified prototype", {"workspace": "sandbox"})
        sup.simulate(op, {"simulated": True})
        sup.test(op, {"tested": True})
        self.assertTrue(sup.authorize(op))
        self.assertTrue(sup.execute(op)["ok"])
        self.assertEqual(op.phase, Phase.VERIFIED)
        self.assertGreaterEqual(len(sup.replay("op-1")), 5)

        failing = VXSupervisor(
            authorizer=lambda op: True,
            executor=lambda op: (_ for _ in ()).throw(RuntimeError("boom")),
            verifier=lambda op, result: False,
        )
        op2 = failing.prepare("op-2", "safe operation", {})
        failing.simulate(op2, {})
        failing.test(op2, {})
        self.assertTrue(failing.authorize(op2))
        self.assertFalse(failing.execute(op2)["ok"])
        self.assertEqual(op2.phase, Phase.FAILED)
        self.assertTrue(failing.recover(op2)["recovered"])


if __name__ == "__main__":
    unittest.main()
