# VAIXLNS Authority-Driven Merge and Remediation Policy

## Rule

A change may merge automatically only when VAIXLNS has authorized that exact pull request and all required repository checks pass. Authorization is represented in this repository by the `vaixlns-authorized` label. The label is an authority signal, not proof by itself: repository permissions must restrict who can apply it to trusted VAIXLNS-reviewed changes.

## Automated flow

1. Discover a defect or vulnerability from tests, dependency alerts, static analysis, or runtime evidence.
2. Create a narrowly scoped remediation branch/PR with a linked finding, affected component, severity, and evidence.
3. Prefer the smallest compatible upgrade or patch; pin/lock versions where the project supports it.
4. Run unit/integration tests, security scanning, compatibility checks, and regression tests.
5. Apply `vaixlns-authorized` only after the VAIXLNS authorization decision is recorded.
6. The trusted-base GitHub workflow enables squash auto-merge. GitHub must still wait for all required checks and branch protections.
7. Re-check the deployed/runtime evidence after merge. If verification fails, stop promotion and open a rollback/recovery action.

## Mandatory stop conditions

Do not auto-merge if checks fail or are pending, the patch changes authority/security boundaries without a reviewed proof, the dependency is unmaintained or license/provenance is unclear, the change broadens permissions, or rollback cannot be demonstrated. Critical vulnerabilities may require immediate isolation while the repair is validated.

## Trust boundary

The auto-merge workflow uses `pull_request_target` so it can read the trusted base-branch workflow, but it deliberately does not check out or execute pull-request code. It only asks GitHub to enable native auto-merge. Never add PR-controlled scripts, checkout steps, secrets exposure, or arbitrary shell execution to this workflow.

## Scope and honest status

- Dependabot is configured to propose weekly Python and GitHub Actions updates, including security updates supported by GitHub.
- This policy workflow does not itself invent or patch arbitrary source-code defects. A detector/remediator must produce a reviewed PR and evidence.
- Automatic merge requires the repository to allow auto-merge and have suitable required status checks/branch protection configured.
- A label-based gate is only as strong as repository permissions and the VAIXLNS process that applies the label. A cryptographically signed machine attestation can replace the label in a later hardened iteration.
