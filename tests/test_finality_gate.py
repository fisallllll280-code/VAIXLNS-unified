from closure.finality_gate import (
    FinalityStatus,
    build_scope,
    invalidate_on_material_change,
    FinalityCertificate,
)


def make_certificate(**checks):
    scope = build_scope(
        environment="ci",
        authority_domain="vaixlns",
        capability_scope=("repo.read",),
        dependency_set=("python",),
        policy_set=("policy-v1",),
    )
    return FinalityCertificate(
        entity_uid="repo:test",
        canonical_version="v1",
        scope=scope,
        checks=checks,
        evidence_root="evidence:1",
        proof_root="proof:1",
        verifier="independent-verifier",
        verification_version="v1",
    )


def test_all_required_checks_produce_operational_finality():
    cert = make_certificate(
        structural=True,
        functional=True,
        integration=True,
        security=True,
        adversarial=True,
        runtime=True,
        replay=True,
        evidence_integrity=True,
        provenance_integrity=True,
        independent_verification=True,
    ).with_evaluated_status()
    assert cert.status is FinalityStatus.OPERATIONALLY_FINAL


def test_failed_check_cannot_be_final():
    cert = make_certificate(
        structural=True,
        functional=False,
        integration=True,
    ).with_evaluated_status()
    assert cert.status is FinalityStatus.REVALIDATION_REQUIRED


def test_unresolved_conflict_blocks_finality():
    cert = make_certificate(structural=True)
    cert = FinalityCertificate(**{**cert.__dict__, "unresolved_conflicts": 1}).with_evaluated_status()
    assert cert.status is FinalityStatus.REVALIDATION_REQUIRED


def test_material_change_invalidates_finality():
    cert = make_certificate(structural=True).with_evaluated_status()
    invalid = invalidate_on_material_change(
        cert, changed_fields=("dependency",)
    )
    assert invalid.status is FinalityStatus.INVALIDATED


def test_non_material_change_does_not_invalidate():
    cert = make_certificate(structural=True).with_evaluated_status()
    same = invalidate_on_material_change(
        cert, changed_fields=("documentation",)
    )
    assert same.status is FinalityStatus.OPERATIONALLY_FINAL
