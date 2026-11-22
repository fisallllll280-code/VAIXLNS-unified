# Effect-Boundary and Recovery Prior-Art Review — 2026-11-10

## Evidence provenance and scope

This note synthesizes four full-text papers read through the connected Undermind scholarly workspace, selected from the completed VAIXLNS Innovation Completion and Implementation Gap Research 2026-11-10 search (326 ranked papers). This is a targeted technical synthesis, not an exhaustive literature review, patentability opinion, or proof of VAIXLNS/VX implementation.

Workspace search: [VAIXLNS Innovation Completion and Implementation Gap Research](https://app.undermind.ai/projects/0d9eabfb-e9d8-49fc-aab5-a0383a9110ce?path=%2FVAIXLNS-INNOVATION-COMPLETION-WAVE-2026-11-10%2FVAIXLNS%20Innovation%20Completion%20and%20Implementation%20Gap%20Research%202026-11-10)

Full texts read:
- Sajjad Khan, *Stop Means Stop: Measuring and Repairing the Enforcement Gap in Agent-Framework Control Primitives*, arXiv:2607.14166v3. [DOI](https://doi.org/10.48550/arXiv.2607.14166)
- Yi Tong, Le-Yu Dai, Song-Hui Guo, *AID-Guard: Stateful Authorization for Delegated Agent Effects*, arXiv:2608.21159. [DOI](https://doi.org/10.48550/arXiv.2608.21159)
- Igor Santos-Grueiro, *When Does Authorization End? Effect Closure at Provider Boundaries*, arXiv:2609.02866. [arXiv](https://arxiv.org/abs/2609.02866)
- Andreas Andreakis, *Machine-Checked Dual-Write Recovery from a Commit Log*, arXiv:2608.00501v5. [arXiv](https://arxiv.org/abs/2608.00501)

These papers are prior art. Their reported experiments and proofs belong to their stated systems and models; they are not evidence that VAIXLNS or VX already implements these mechanisms.

## 1. Engineering conclusion

The critical control boundary is not the agent plan, tool-call proposal, approval screen, or execution log. It is the last point at which an externally visible effect can still be prevented.

A system must not infer:
- approval received means the effect is authorized at commit time;
- task paused means sibling workers cannot commit effects;
- cancellation acknowledged means earlier authorizations cannot produce effects;
- timeout or lost response means the provider performed no effect;
- checkpoint persisted means sink acceptance is known;
- empty queue or clean visible state means no dispatched callback remains capable of an effect;
- provider success means the exact reviewed request was committed.

The papers converge on one requirement: model the full path from authority issuance through in-flight work to the external effect frontier, and preserve authoritative evidence across retries and recovery.

## 2. Prior-art mechanisms

### 2.1 Effect admission and barrier safety — Khan et al.

The paper defines four barrier properties at the externally visible commit point:
- B1: no gated effect executes between an approval pause and its decision.
- B2: a rejected effect never executes.
- B3: each logical effect executes at most once across replay.
- B4: after cancellation/timeout is observed, no further effect from that run lands.

SOUNDGATE uses hold-until-decided, sticky rejection, deduplication by stable run/effect key, and a cancellation fence. Its guarantees are conditional on complete mediation: every side-effecting route must pass through the gate before the effect occurs.

The verification ladder distinguishes model proofs/checks from implementation conformance and deployed-path coverage. Verus proves properties of an abstract model; TLA+/TLC and TLAPS check/model the declared system; Loom and differential conformance test the Rust implementation's connection to that model. This is not one unqualified proof of every deployed route.

Reported experiments include 215/1,200 unmediated leaks in the paper's live end-to-end study and 0/1,200 mediated leaks for the tested setup; approximately 1.1 ms median per write in the reported task comparison. These results are bounded to the paper's harness and environment.

### 2.2 Authorization-to-effect lifecycle — Tong et al.

AID-Guard separates authority formation from effect commitment:
1. H1 binds an eligible evaluation to an authenticated actor session and validates the current context.
2. H2 reserves quota and issues one holder-bound capability; exact retries return the original issuance.
3. H3 claims the capability at the effect boundary using a durable compare-and-swap.
4. D2 reloads authority and provider contract state and binds dispatch to the exact immutable request and provider precondition.
5. The outcome is terminalized, or uncertainty is preserved until authoritative reconciliation.

For an atomic provider, effect and authority state share a transaction. For a controlled-idempotent provider, the capability is durably consumed into an immutable submitted attempt/outbox, and the provider must support stable idempotency and terminal lookup. If delivery is ambiguous and the provider cannot certify no effect, the system retains the reservation and does not automatically retry, release, or create a successor.

The paper reports 13/13 live mutations rejected or invalidated with zero unauthorized provider effects, 210 Stripe test-mode trials matching predeclared outcomes, and finite concurrency/recovery tests. Its claims are conditional on a complete declared effect-path domain, trusted components, exact request binding, and conformant provider contracts.

### 2.3 Effect closure, not merely revocation or quiescence — Santos-Grueiro

The paper distinguishes:
- Future-use closure: no future matching attempt can issue another derived authorization.
- Instance-effect closure: no already-issued authorization instance can still reach a policy-rejected effect.
- Lineage closure: both conditions hold for the full grant lineage.
- Quiescence: no carrier remains capable of crossing the effect frontier, even safely.

Quiescence is stronger than effect closure and is not required for closure. A system may still have active work after revocation if every remaining effect is safe; stopping new authorization does not close an old in-flight effect path.

The finite contract must include provider states, exposed controls, authorization origins, continuations/carriers, effect frontier, workload, and policy. Missing provider paths can produce a false safe result; missing controls can produce a false impossibility result. When evidence does not support the contract, the correct verdict is UNSUPPORTED, not a guessed success/failure.

The paper reports six challenge paths across GitHub MCP, NATS, Kubernetes, and Kafka, including late-bound GitHub merge targets and old Kafka requests that append after ACL convergence. Repairs bind the final SHA/request, re-enter final validation, or fence/drain earlier authorized work. Each result is bounded to the specified interface and workload.

### 2.4 Dual-write recovery impossibility — Andreakis

If a process crashes after a sink accepts an operation but before the source checkpoint is recorded, two executions can have identical durable source-side state but different sink acceptance records. Any recovery policy using only the source side must either duplicate an accepted effect in one execution or omit an undelivered effect in the other.

A source checkpoint, local WAL, or retry loop alone cannot resolve this ambiguity. Recovery requires an authoritative, complete, current sink-side per-operation acceptance record, plus appropriate fencing for in-flight old requests and concurrent recovery workers.

The paper separates arrival fencing for delayed requests from a prior process generation, and claim fencing for competing recovery workers that may have lost authority. These are distinct mechanisms and are not interchangeable. Bounded deduplication retention and source-history truncation limit how long the guarantee remains valid.

## 3. Proposed VX engineering requirements

The following are proposed acceptance requirements derived from prior art. They are not claims about the current VX runtime.

| ID | Requirement | Fail-closed behavior |
|---|---|---|
| FX-01 | Inventory every external effect sink and alternate route: network, filesystem, IPC, subprocess, cloud API, GitHub mutation, model-provider write. | Any unclassified route blocks a complete-mediation claim. |
| FX-02 | Require a stable logical effect key scoped to run and action, reused unchanged across retries/replay. | Missing or ambiguous key is rejected. |
| FX-03 | Place admission at the last preventable effect boundary. | No effect before an explicit release verdict. |
| FX-04 | Bind approval to exact actor, policy version, run, operation, immutable payload, target, and provider precondition. | Any changed field invalidates the approval. |
| FX-05 | Make rejection sticky and cancellation epoch-fenced. | Late workers, sibling branches, retries, and zombie tasks cannot commit after the fence. |
| FX-06 | Revalidate current authority at commit time. | A stale approval or provider version cannot authorize a new effect. |
| FX-07 | Preserve an uncertain state after response loss. | No automatic retry, reservation release, or successor without authoritative terminal evidence. |
| FX-08 | Require sink-side acceptance records and delivery/claim fencing for recovery. | Source-only checkpoints cannot certify no effect. |
| FX-09 | Declare retention horizons for source events, idempotency keys, sink receipts, approvals, and fences. | Expired evidence limits the guarantee; report UNKNOWN/UNSUPPORTED. |
| FX-10 | Keep proof/model evidence distinct from implementation conformance and deployment coverage. | No VERIFIED or RUNNING label from a model-only pass. |

## 4. Minimum adversarial test matrix

Every test must check both safety and required legitimate completion. A deny-all implementation is not a successful repair.

| Test | Adversarial schedule | Required assertion |
|---|---|---|
| FX-T01 Approval sibling leak | Pause one branch for approval while a sibling attempts a write. | Zero effects before approval; unrelated safe computation may continue. |
| FX-T02 Sticky rejection | Reject an effect, then replay/resubmit the same key from another worker. | Every attempt remains refused. |
| FX-T03 Duplicate replay | Commit an effect, crash before local receipt, then replay with the same key. | One sink effect only; original receipt is recovered. |
| FX-T04 Cancellation fence | Cancel while a worker is in flight; release its delayed submission after cancellation. | No post-fence effect. |
| FX-T05 Commit-time mutation | Approve target SHA/payload A, mutate target or payload to B before commit. | B is rejected; exact A can complete if still valid. |
| FX-T06 Lost response ambiguity | Crash after sink acceptance but before local checkpoint. | Sink receipt resolves commit; otherwise remain uncertain. |
| FX-T07 Arrival fence | Delay an old-generation request until after recovery reads sink state. | Old request cannot duplicate the recovery action. |
| FX-T08 Concurrent recovery | Start two recovery workers against the same missing effect. | At most one claim and one accepted effect. |
| FX-T09 Retention expiry | Replay after idempotency/receipt retention expires. | Guarantee is downgraded; no exactly-once claim is made. |
| FX-T10 Incomplete sink inventory | Add an alternate credential or direct network route outside the gate. | Complete mediation fails; route is surfaced as a blocker. |
| FX-T11 Effect frontier adequacy | Move the claimed boundary earlier than a remaining provider transition. | Contract is rejected as unsupported/incomplete. |
| FX-T12 Legitimate progress | Run a safe, authorized operation under the same controls. | Required operation completes; no blanket blocking. |

For each test, preserve the exact run ID, action key, approval/policy epoch, payload hash, provider request ID, sink receipt, timestamps, fence generation, recovery worker identity, and observed effect count. A test result without these bindings is insufficient evidence for FX-01 through FX-10.

## 5. Verification ladder

1. Specification: define state machine, trust assumptions, effect domain, provider contracts, frontiers, and failure schedules.
2. Model checking: exhaustively check bounded concurrency/replay/cancellation histories; preserve counterexamples.
3. Implementation tests: differential conformance between the model and deployed sink admission code; mutation tests for each invariant.
4. Sink integration: exercise each real provider adapter in sandbox/test mode with an independent effect recorder.
5. Recovery tests: crash before/after provider acceptance, checkpoint, receipt persistence, fence installation, and successor issuance.
6. Coverage audit: independently enumerate all effect paths and credentials; a wrapper-only test does not prove complete mediation.
7. Operational qualification: only after evidence, evaluate latency, throughput, fail-closed utility, recovery time, and retention horizon.

## 6. Status and non-claims

- Literature review: RESEARCHED for the four papers above.
- Mapping to VX: PROPOSED.
- Atomic engineering contract and test matrix: SPECIFIED in this note.
- VX implementation of these controls: NOT ESTABLISHED BY THIS REVIEW.
- VX runtime tests for these controls: NOT RUN IN THIS REVIEW.
- Production effect-path completeness: UNKNOWN.
- Novelty, ownership, legal patentability, and global superiority: NOT CLAIMED.

The next implementation step is to inventory actual VX effect handlers and provider boundaries, map each to FX-01 through FX-12, and implement only the smallest missing control in an isolated branch. Do not add another generic approval layer if an existing sink can be extended.
