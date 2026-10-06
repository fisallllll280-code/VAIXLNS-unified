import unittest

from innovation_control.engine import InnovationCandidate, IndependentVerificationTrio, NoveltyShield
from innovation_control.assurance import VerifierProfile


class InnovationControlRegressionTests(unittest.TestCase):
    def test_lineage_does_not_hide_duplicate_architecture(self):
        base = InnovationCandidate(
            "a", "m", {"runtime": "vx", "proof": "trio"}, ("p",), ("legacy:a",)
        )
        same_architecture_new_lineage = InnovationCandidate(
            "b", "m", {"runtime": "vx", "proof": "trio"}, ("p",), ("legacy:b",)
        )
        self.assertEqual(
            NoveltyShield().classify(same_architecture_new_lineage, [base]),
            "REDUNDANT",
        )

    def test_each_independent_verifier_is_called_once(self):
        calls = []
        def verifier(label):
            def f(candidate, evidence):
                calls.append(label)
                return True
            return f

        trio = IndependentVerificationTrio(
            [verifier("a"), verifier("b"), verifier("c")],
            [
                VerifierProfile("v1", "impl-a", "symbolic", ("e1",), "rule"),
                VerifierProfile("v2", "impl-b", "replay", ("e2",), "hash"),
                VerifierProfile("v3", "impl-c", "statistical", ("e3",), "model"),
            ],
        )
        candidate = InnovationCandidate("a", "m", {"runtime": "vx"}, ("p",))
        evidence = type("E", (), {})()
        results = trio.verify(candidate, evidence)
        self.assertTrue(all(r.passed for r in results))
        self.assertEqual(calls, ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
