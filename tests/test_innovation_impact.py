import unittest

from innovation_control.impact import CausalImpactBudget, ImpactNode


class CausalImpactBudgetTests(unittest.TestCase):
    def test_budget_blocks_wide_high_criticality_change(self):
        result = CausalImpactBudget().assess(
            [
                ImpactNode("runtime", 1.0, True),
                ImpactNode("ledger", 1.0, True),
                ImpactNode("replay", 0.5, False),
            ],
            budget=1.5,
            max_state_mutations=1,
        )
        self.assertFalse(result.passed)
        self.assertIn("IMPACT_BUDGET_EXCEEDED", result.blocked)
        self.assertIn("STATE_MUTATION_LIMIT", result.blocked)

    def test_forbidden_canonical_surface_blocks_change(self):
        result = CausalImpactBudget().assess(
            [ImpactNode("constitution", 0.2, False)],
            budget=1.0,
            forbidden_nodes=frozenset({"constitution"}),
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.blocked, ("constitution",))

    def test_small_change_stays_inside_budget(self):
        result = CausalImpactBudget().assess(
            [ImpactNode("telemetry", 0.2, False)],
            budget=0.5,
        )
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
