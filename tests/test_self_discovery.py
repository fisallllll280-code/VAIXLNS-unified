import unittest

from evolution.self_discovery import SelfDiscoveryEngine


class SelfDiscoveryTests(unittest.TestCase):
    def test_unknowns_are_first_class_and_not_canonical(self):
        report = SelfDiscoveryEngine().discover(
            "four-domain-room",
            ["math", "physics", "proof"],
            ["math"],
            evidence=("registry:v1",),
        )
        self.assertEqual(report.gaps[0].missing, ("physics", "proof"))
        self.assertEqual(len(report.unknowns), 2)
        self.assertEqual(len(report.hypotheses), 2)
        self.assertTrue(all(u.status == "OPEN" for u in report.unknowns))
        self.assertTrue(all(h.lineage[0] == "self-discovery" for h in report.hypotheses))

    def test_empty_gap_produces_no_unknown_or_hypothesis(self):
        report = SelfDiscoveryEngine().discover(
            "known-capability",
            ["math"],
            ["math"],
        )
        self.assertEqual(report.gaps[0].missing, ())
        self.assertEqual(report.unknowns, ())
        self.assertEqual(report.hypotheses, ())

    def test_unknown_fingerprint_is_stable(self):
        engine = SelfDiscoveryEngine()
        a = engine.discover("m", ["x"], [], evidence=("e",)).unknowns[0]
        b = engine.discover("m", ["x"], [], evidence=("e",)).unknowns[0]
        self.assertEqual(a.id, b.id)
        self.assertEqual(a.fingerprint, b.fingerprint)


if __name__ == "__main__":
    unittest.main()
