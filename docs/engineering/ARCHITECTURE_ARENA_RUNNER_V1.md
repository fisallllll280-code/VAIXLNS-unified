# Architecture Arena Runner V1

Status: **IMPLEMENTED REFERENCE ORCHESTRATOR / NOT A LIVE SANDBOX**

## Purpose

`evolution/architecture_arena.py` closes the orchestration gap between the existing capability-gap detector, three-way architecture search, self-discovery unknown records, Ω Innovation Control, and admissible-candidate ranking.

The vertical slice is:

`mission → gap → 3 isolated design candidates → external trial package → metrics validation → falsification → independent verification → replay → proof freshness → causal impact → ADMISSIBLE → deterministic selection`

## What it does

- Derives a deterministic experiment identity from one mission, required/available capabilities, and the gap.
- Preserves open unknown records and generates three isolated design variants via the existing `ArchitectureLab`.
- Creates lineage-bound `InnovationCandidate` records with explicit proof obligations.
- Requires an external trial package for each candidate; missing packages fail closed.
- Rejects missing, non-finite, non-numeric, or out-of-range score metrics before ranking.
- Delegates novelty, mandatory arena thresholds, falsification, verification diversity, replay, evidence binding, proof freshness, and causal impact to the existing Ω Innovation Control gate.
- Selects only candidates that reach `ADMISSIBLE` and pass mandatory arena thresholds. Ties resolve by candidate ID.
- Produces a deterministic report fingerprint for the experiment and its decisions.

## Hard boundaries

- This module does **not** execute untrusted code or create an OS sandbox. The trial package must be returned by an independently configured and trusted test/simulation adapter.
- Test fixtures are synthetic conformance evidence only; they do not demonstrate production behavior.
- A successful result is `ADMISSIBLE`, never `CANONICAL`. This runner exposes no canonicalization call and has no authority to mutate `Ω.000`, `project.genome`, or runtime state.
- The proof digest is a traceability fingerprint, not a formal theorem or cryptographic attestation from a trusted key.
- The same verifier functions remain subject to the existing profile-diversity check; passing tests does not establish real-world statistical or organizational independence.
- The candidate score ranks already-admissible candidates. It cannot override a failed mandatory gate.

## Required trial metrics

Every trial must report these finite values in `[0, 1]`:

- `correctness`, `reliability`, `proof_coverage`, `reproducibility`
- `evidence_strength`, `novelty_value`, `operational_value`
- `blast_risk`, `rollback_cost`, `unresolved_unknowns`

Thresholds are still controlled by `CounterfactualArena`; the runner adds completeness/range validation so absent or non-finite metrics cannot quietly turn into a score.

## Example integration

Create a runner using the existing configured `ProofBeforePromotion`, call `propose(...)`, execute each returned isolated candidate using the trusted sandbox adapter, convert its observations and receipts into an `ArchitectureTrial`, then call `evaluate(experiment, trials)`. The key for `trials` is the exact returned candidate ID.

Do not synthesize trial metrics from the candidate description. The adapter must supply measured observations, test identifiers, matching candidate-bound evidence, dependency/environment fingerprints, replay input/output, a fresh proof context, and bounded impact nodes.

## Verification

```bash
python -m unittest discover -s tests -p 'test_architecture_arena.py' -v
python -m unittest discover -s tests -p 'test_self_discovery.py' -v
python -m unittest discover -s tests -p 'test_innovation_control.py' -v
```

These checks validate local orchestration invariants and mocked gate behavior only. They are not evidence that a live sandbox, remote research provider, or production runtime is connected.
