import unittest

from language.vxsl import VXSLCompiler
from media.engineering_video_forge import EngineeringVideoForge


class VXSLMediaProjectTests(unittest.TestCase):
    def test_vxsl_is_source_of_truth_and_polyglot(self):
        source = """system TestSystem {
          domain mathematics
          domain physics
          quantity mass: kg
          law F = m * a
          prove equation_consistent
        }"""
        ir=VXSLCompiler().compile(source)
        self.assertEqual(ir["source_of_truth"],"VXSL")
        self.assertEqual(ir["implementation_target_policy"],"polyglot")
        self.assertIn("Julia",ir["compiler"]["targets"])
        self.assertIn("Modelica",ir["compiler"]["targets"])

    def test_engineering_video_plan_has_evidence_flow(self):
        plan=EngineeringVideoForge().build(
            "Evolution",
            "coupled four-domain system",
            ["F=m*a"],
            ["sim:1","test:1"],
            ["arch:A","arch:B"],
        )
        self.assertEqual(len(plan.shots),6)
        self.assertIn("ltx-2",plan.backend_candidates)
        self.assertIn("sim:1",plan.shots[2].evidence_refs)

if __name__ == "__main__":
    unittest.main()
