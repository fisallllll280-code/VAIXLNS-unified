import unittest

from innovation_control.self_test import run_self_test


class InnovationControlSelfTest(unittest.TestCase):
    def test_control_subjects_itself_to_its_own_gates(self):
        results = run_self_test()
        self.assertEqual(len(results), 7)
        self.assertTrue(all(result.passed for result in results), results)


if __name__ == "__main__":
    unittest.main()
