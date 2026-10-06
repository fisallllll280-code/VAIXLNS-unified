from integration_control.assurance import ProofFreshness, VerifierProfile
from integration_control.gateway import ExternalIntegration, IntegrationClass, IntegrationPolicy
from integration_control.proof_boundary import ExternalIntegrationProofBoundary
from innovation_control.engine import Evidence
from innovation_control.impact import ImpactNode


def test_evidence_drift_cannot_reuse_proof():
    integration = ExternalIntegration(
        "model:edge", "Edge Model", IntegrationClass.MODEL, "provider://edge",
        ("inference",), "v1", "dep:v1", "env:v1", owner="vaixlns"
    )
    policy = IntegrationPolicy(
        allowed_kinds=frozenset({IntegrationClass.MODEL}),
        allowed_capabilities=frozenset({"inference"}),
    )
    evidence = Evidence(
        candidate_id="integration:model:edge",
        execution_digest="exec-1",
        test_ids=("functional","failure_recovery","replay"),
        environment={"mode":"sandbox"},
        observations={"ok":True},
    )
    mismatched = Evidence(
        candidate_id=evidence.candidate_id,
        execution_digest="exec-2",
        test_ids=evidence.test_ids,
        environment=evidence.environment,
        observations=evidence.observations,
    )
    validity = ProofFreshness.issue(
        evidence_fingerprint=mismatched.fingerprint,
        issued_epoch=100,
        ttl_epochs=100,
        dependency_fingerprint="dep:v1",
        environment_fingerprint="env:v1",
    )
    profiles=[
        VerifierProfile("v1","impl-a","a",("e1",),"rule"),
        VerifierProfile("v2","impl-b","b",("e2",),"hash"),
        VerifierProfile("v3","impl-c","c",("e3",),"model"),
    ]
    attacks={k:(lambda c,e: True) for k in ("contract","functional","failure_recovery","security_boundary","replay")}
    result=ExternalIntegrationProofBoundary().admit(
        integration, policy,
        metrics={
            "correctness":.99,"reliability":.99,"proof_coverage":.99,"reproducibility":1.0,
            "evidence_strength":1.0,"novelty_value":.95,"operational_value":.95,
        },
        evidence=evidence, inputs={"x":1}, first_output=2, replay_fn=lambda p:p["x"]*2,
        attacks=attacks, verifiers=[lambda c,e:True]*3,
        verifier_profiles=profiles, proof_validity=validity, now_epoch=120,
        impact_nodes=[ImpactNode("sandbox",.2,False)], impact_budget=.5,
        explicit_authority=True,
    )
    assert result.decision.state.value == "QUARANTINED"
    assert "PROOF_REJECTED:EVIDENCE_FINGERPRINT_MISMATCH" in result.decision.reasons
