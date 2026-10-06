import unittest

from integration.final_closure_audit import audit_local_closure


class FinalClosureAuditTests(unittest.TestCase):
    def test_local_closure_passes(self):
        report = audit_local_closure()
        self.assertEqual(report["status"], "LOCAL_CLOSURE_PASS")
        self.assertTrue(all(item["status"] == "PASS" for item in report["items"]))
        self.assertGreaterEqual(len(report["external_evidence_required"]), 1)


if __name__ == "__main__":
    unittest.main()
