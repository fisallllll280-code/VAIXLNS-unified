import unittest
from continuum.atomaton import AtomatonState
from continuum.proof import ProofLevel, ProofPolicy
from vx.atomaton_factory import spawn
from vx.proof_spectral_gate import evaluate
from vx.topology_synthesizer import synthesize

class VXContinuumVerticalSliceTests(unittest.TestCase):
    def test_bounded_atomaton_lifecycle(self):
        a = spawn(execution_id="e1", intent_id="i1", capability_id="compute",
                  contract_id="c1")
        for state in (AtomatonState.BOUND, AtomatonState.VALIDATED,
                      AtomatonState.EXECUTING, AtomatonState.OBSERVED):
            a = a.transition(state)
        self.assertEqual(a.state, AtomatonState.OBSERVED)
        self.assertTrue(a.trace_digest)

    def test_topology_is_deterministic(self):
        p = synthesize("i1", "compute", [
            {"node_id": "b", "capabilities": ["compute"], "risk": .2},
            {"node_id": "a", "capabilities": ["compute"], "risk": .1},
        ])
        self.assertEqual(p.node_ids, ("a",))

    def test_proof_gate_does_not_upgrade_unverified_claims(self):
        d = evaluate(ProofPolicy(ProofLevel.DETERMINISTIC_REPLAY),
                     [ProofLevel.FORMAL_VERIFICATION], verified=False)
        self.assertFalse(d.admitted)

if __name__ == "__main__":
    unittest.main()
