# Ω-REFLEXIVE ASSURANCE v1

Status: IMPLEMENTED CANDIDATE. The checker is same-process, not a separately
deployed independent trust domain. A receipt digest is not a digital signature.

## Contract

`check_admission_decision` uses a separate implementation path
from `evaluate_transition`. It independently reconstructs the
state, candidate, policy, and request bindings, evaluates the declared core
invariants, predicts the expected admission classification from supplied
authority/evidence verifier verdicts, and compares that classification with the
kernel's decision.

On disagreement, it emits a counterexample receipt naming the mismatched path,
expected value, observed value, and input digest. The enclosing assurance receipt
is content-addressed and can be rechecked with `verify_assurance_receipt`.

## Verdicts

- `CHECKED_ADMISSION_CANDIDATE`: the independent checker agrees
  that the transition satisfies the modeled contract. This is not a commit or
  a proof of external truth.
- `CONSISTENT_NON_ADMISSIBLE`: the kernel and checker agree on
  `REJECT`, `UNKNOWN`, or `QUARANTINE`.
- `DIVERGENT`: a decision binding or status disagrees; quarantine
  the transition and preserve the counterexample.
- `INDETERMINATE`: the checker itself could not complete;
  no admission inference is permitted.

## Boundary conditions

The checker does not call `evaluate_transition` and does not
trust the kernel's `checks` dictionary as its reference result.
It does share the state and policy data types, the same process, Python runtime,
and SHA-256 primitive; it is therefore logically separate but not operationally
independent. An independent process with a separately managed release policy,
pinned trust roots, signed verifier outputs, and a separately controlled deploy
boundary remains a future requirement.

Authority/evidence verdicts passed into the checker must come from independently
authenticated verifier receipts in production. Tests use deterministic mock
verdicts. Receipt fingerprints detect content changes relative to the recorded
digest; they do not establish who authored the receipt or whether its contents
are true.

## Verification

Run:

`python -m pytest -q tests/test_omega3_kernel.py tests/test_omega3_assurance.py`

Passing tests proves the tested behaviors only. It does not establish atomic
commit, full-system noninterference, production signing, or runtime enforcement.
