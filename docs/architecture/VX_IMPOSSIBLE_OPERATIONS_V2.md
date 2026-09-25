# VX Impossible Operations V2

## What changes

VX is upgraded from a multi-agent coordinator into an **invention-operating substrate**.

The key unit is no longer an answer, agent, model or repository alone. It is a
versioned **capability with lineage, invariants, evidence and an executable
promotion path**.

### Six differentiators

| Capability | Ordinary assistant UX | VX target |
|---|---|---|
| Cross-domain synthesis | Agents work as separate turns | Recombination of reusable math/physics/engineering/computing capabilities |
| Counterfactual engineering | One proposed answer | Multiple executable design branches |
| Proof-carrying invention | Explanation attached after the fact | Candidate carries proof obligations before promotion |
| Evolving memory | Chat history / static retrieval | Branch, invalidate and preserve provenance |
| Capability genome | Skills stay inside one task | Verified inventions become reusable building blocks |
| Reversible operations | Tool call with limited context | Explicit state machine with replay/recovery hooks |

These are architectural targets implemented in this branch; they should not be
read as a claim that no existing AI research system has any related component.

## Operational loop

MISSION -> ROUTE -> COMPOSE -> SIMULATE -> TEST -> VERIFY -> PROMOTE -> EXECUTE -> RECORD -> REUSE -> EVOLVE

The split is intentional:

- **Intelligence plane:** proposes decompositions, candidates and transformations.
- **Evidence plane:** simulation, test results, provenance and proof obligations.
- **Authority plane:** an explicit authorizer decides whether external execution is allowed.
- **Execution plane:** the supervisor performs the authorized operation.
- **Memory plane:** successful and failed hypotheses are versioned, not silently overwritten.

## Customer-selected multiplication of roles

A mission can request any mix of:

mathematics + physics + engineering + computing + research + optimization

The engine selects compatible capabilities and can create cross-domain candidates.
The same mechanism also supports different output types: interface, workflow,
model, agent, architecture or verified capability.

## Impossible-maker design patterns

1. **Constraint inversion:** treat a hard constraint as a design variable and generate a counterfactual branch.
2. **Solver swapping:** reuse the same problem representation with a different solver family.
3. **Proof-first construction:** attach invariants and proof obligations before implementation.
4. **Capability recombination:** compose previously verified building blocks into a new candidate.
5. **Memory branching:** fork assumptions instead of mutating historical memory.
6. **Operational reversibility:** require replay/recovery hooks for runtime work.
7. **Repository lineage:** preserve which GitHub sources contributed to a capability.

## Full-operation boundary

“Full operation” here means the repository contains the executable control-plane
primitives and CI validation for the lifecycle. External execution still requires
explicit adapters, credentials, infrastructure and authorization outside this library.

## GitHub source federation

The canonical project repositories remain separate sources. VX records repository
references rather than silently merging unrelated codebases. This preserves
ownership and provenance while allowing a federated engineering view.

## Definition of done for an invention

A candidate is not promoted merely because an agent generated it. Promotion requires:

- deterministic identity
- explicit components and lineage
- proof obligations / invariants
- simulation result
- test result
- verification result
- evidence references
- reusable capability registration
