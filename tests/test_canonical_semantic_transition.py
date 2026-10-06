import unittest

from semantic.canonical_transition import (
    AdmissionState,
    AuthorityRef,
    CanonicalSemanticTransition,
    EvidenceRef,
    ProofRef,
)


def base(state=AdmissionState.OBSERVED):
    return CanonicalSemanticTransition(
        identity="actor-1",
        subject="system-1",
        intent="execute objective",
        semantic_context={"domain": "test"},
        pre_state={"status": "ready"},
        constraints=("safe",),
        capability="demo.execute",
        plan={"steps": ["run"]},
        operation="run",
        inputs={"x": 21},
        expected_post_state={"status": "done"},
        observed_post_state={"status": "done"},
        transition_time="2026-10-06T00:00:00Z",
        evidence=(EvidenceRef("e1", "runtime", "h1"),),
        verification=("independent-v1",),
        proof=(ProofRef("p1", "hash", "h2"),),
        authority=AuthorityRef("a1", "ADMIT", "h3"),
        lineage=("src-1",),
        replay_recipe={"inputs": {"x": 21}},
        admission_state=state,
    )


class CanonicalSemanticTransitionTests(unittest.TestCase):
    def test_unknown_transition_can_exist(self):
        t = base(AdmissionState.UNKNOWN)
        t.validate()

    def test_verified_requires_verification(self):
        t = base(AdmissionState.VERIFIED)
        t = t.__class__(**{**t.__dict__, "verification": ()})
        with self.assertRaisesRegex(ValueError, "VERIFICATION_REQUIRED"):
            t.validate()

    def test_proven_requires_proof_and_replay(self):
        t = base(AdmissionState.PROVEN)
        t = t.__class__(**{**t.__dict__, "proof": ()})
        with self.assertRaisesRegex(ValueError, "PROOF_REQUIRED"):
            t.validate()

    def test_admitted_requires_authority(self):
        t = base(AdmissionState.ADMITTED)
        t = t.__class__(**{**t.__dict__, "authority": None})
        with self.assertRaisesRegex(ValueError, "AUTHORITY_REQUIRED"):
            t.validate()

    def test_canonical_requires_evidence(self):
        t = base(AdmissionState.CANONICAL)
        t = t.__class__(**{**t.__dict__, "evidence": ()})
        with self.assertRaisesRegex(ValueError, "EVIDENCE_REQUIRED"):
            t.validate()

    def test_fingerprint_is_stable(self):
        a = base(AdmissionState.ADMITTED)
        b = base(AdmissionState.ADMITTED)
        self.assertEqual(a.fingerprint(), b.fingerprint())


if __name__ == "__main__":
    unittest.main()
