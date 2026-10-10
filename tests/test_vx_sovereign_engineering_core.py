import unittest

from vx.sovereign_engineering_core import (
    discover, federation_candidates, inventory_digest, propose_evolution,
    prove_candidate, stable_digest, synthesize, understand,
)


def records():
    return [
        {"system_id": "VX", "revision": "abc123", "capabilities": ["execute", "verify"],
         "dependencies": ["ARC-X"], "conflicts": ["VX-Legacy"], "state": "CI_VERIFIED"},
        {"system_id": "VX-Legacy", "revision": "def456", "capabilities": ["execute"]},
    ]


class SovereignEngineeringCoreTests(unittest.TestCase):
    def test_inventory_is_deterministic_under_input_reordering(self):
        a = understand(records())
        b = understand(list(reversed(records())))
        self.assertEqual(a["inventory_digest"], b["inventory_digest"])

    def test_duplicate_system_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SYSTEM_ID"):
            understand(records() + [records()[0]])

    def test_unknown_evidence_state_is_rejected(self):
        item = records()[0] | {"state": "VERIFIED_BY_ASSERTION"}
        with self.assertRaisesRegex(ValueError, "INVALID_EVIDENCE_STATE"):
            understand([item])

    def test_discovery_reports_missing_dependency_overlap_and_conflict(self):
        inv = understand(records())
        result = discover(inv)
        self.assertEqual(result["state"], "FINDINGS_AVAILABLE")
        self.assertEqual(result["missing_dependencies"][0]["missing_dependency"], "ARC-X")
        self.assertTrue(result["capability_overlaps"])
        self.assertTrue(result["declared_conflicts"])
        self.assertFalse(result["resolution_performed"])

    def test_synthesis_rejects_stale_findings(self):
        inv = understand(records())
        findings = discover(inv)
        findings["inventory_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "INVENTORY_FINDINGS_DIGEST_MISMATCH"):
            synthesize(inv, findings, "integrate")

    def test_synthesis_is_deterministic_and_non_executing(self):
        inv = understand(records())
        plan = synthesize(inv, discover(inv), "integrate systems")
        self.assertEqual(plan["plan_digest"], synthesize(inv, discover(inv), "integrate systems")["plan_digest"])
        self.assertFalse(plan["execution_performed"])
        self.assertFalse(plan["authority_granted"])
        self.assertTrue(all(t["requires_human_review"] for t in plan["tasks"]))

    def test_proof_gate_requires_both_receipts(self):
        plan = synthesize(understand(records()), discover(understand(records())), "test")
        result = prove_candidate(plan, simulation_receipt="", test_receipt="t",
                                verifier=lambda _: True, authorizer=lambda _: True)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["execution_performed"])

    def test_proof_gate_denies_failed_verification_or_authorization(self):
        plan = synthesize(understand(records()), discover(understand(records())), "test")
        bad_verify = prove_candidate(plan, simulation_receipt="s", test_receipt="t",
                                     verifier=lambda _: False, authorizer=lambda _: True)
        bad_auth = prove_candidate(plan, simulation_receipt="s", test_receipt="t",
                                   verifier=lambda _: True, authorizer=lambda _: False)
        self.assertEqual(bad_verify["reason"], "INDEPENDENT_VERIFICATION_FAILED")
        self.assertEqual(bad_auth["reason"], "AUTHORIZATION_DENIED")

    def test_success_is_only_eligible_candidate_not_execution(self):
        inv = understand(records())
        plan = synthesize(inv, discover(inv), "integrate")
        result = prove_candidate(plan, simulation_receipt="sim-1", test_receipt="test-1",
                                 verifier=lambda _: True, authorizer=lambda _: True)
        self.assertEqual(result["state"], "ELIGIBLE_FOR_SEPARATE_EXECUTION_GATE")
        self.assertFalse(result["execution_performed"])
        self.assertFalse(result["authority_granted"])

    def test_federation_does_not_invoke_tools_and_reports_gaps(self):
        result = federation_candidates(understand(records()), ["execute", "cloud.deploy"])
        self.assertEqual(result["state"], "CAPABILITY_GAPS")
        self.assertFalse(result["network_calls_performed"])
        self.assertFalse(result["tools_invoked"])

    def test_evolution_requires_evidence_and_never_mutates_canon(self):
        self.assertEqual(propose_evolution({}, "improve replay")["state"], "BLOCKED")
        proposal = propose_evolution({"evidence_ref": "ci://run/1",
                                      "observation_digest": stable_digest({"test": "fail"})},
                                     "improve replay")
        self.assertEqual(proposal["state"], "EVOLUTION_PROPOSAL")
        self.assertTrue(proposal["approval_required"])
        self.assertFalse(proposal["canonical_write_performed"])


if __name__ == "__main__":
    unittest.main()
