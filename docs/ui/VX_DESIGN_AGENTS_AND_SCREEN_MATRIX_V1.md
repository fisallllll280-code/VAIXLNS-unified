# VAIXLNS × VX — Design Agents, Screens and UX Quality Gates v1

**Status:** SOURCE-BASED DESIGN PLAN; no third-party skill installed or run, no UI redesign claimed. **Authority:** VAIXLNS. **Execution boundary:** VX. **Branch:** feat/vx-design-agent-screen-map-v1.

## Existing interface evidence
- `workspace/dashboard.html`: Arabic RTL responsive workspace with overview, source/index, sessions, agent and audit sections. Current CSS declares dark palette `--bg:#0b1020`, `--panel:#131b2f`, `--accent:#77d6bd`, `--text:#f2f5fb`.
- `web/vx-console.html`: VX English control console with agent role configuration, not a live-agent fleet; a separate accent `#83b7ff` and status text warn that runtime is not connected.
- `docs/ui/VX_WORKSPACE_FABRIC_V1.md`: registered endpoints for workspace search, agent roles and sessions. Do not reinterpret registration as live AI operation.
- The two interfaces currently disagree on brand accent, language and some presentation patterns; unify only after selecting the authoritative shell and testing RTL/iPhone.

## Agent-to-screen and responsibility matrix

| VX agent role (design specialization, not a newly deployed model) | Existing VX ownership | Screen | Source/inspiration | Deliverable | Acceptance |
|---|---|---|---|---|---|
| Design Evidence Curator | source-cartographer | Design System | create-design-md (ibelick/ui-skills) | SOURCE-BACKED root DESIGN.md, known tokens, documented variants | all tokens trace to rendered consumer/source |
| Palette & Typography Analyst | architecture-auditor | Design System | palette/font UX skills (exact nextlevelbuild repo unverified) | accessible color roles, Arabic/Latin type scale | measured contrast and responsive typography |
| UX Critic | architecture-auditor | Ω Reality Forge / Home | impeccable critique | hierarchy and task-flow findings | issue IDs tied to screenshots, tasks and severity |
| Copy & Clarity Reviewer | session-curator | all screens | impeccable clarify | Arabic UI labels, empty states, actionable errors | human review for terminology and intent |
| Accessibility Auditor | security-reviewer + test-engineer | all screens | impeccable audit | keyboard/focus/contrast/motion issues | automated + human screen inspection |
| Interaction Engineer | console-designer | Agents & Tasks | emil-design-eng | buttons, microinteractions, feedback | tap targets/focus/reduced-motion coverage |
| Motion Reviewer | test-engineer | all animated surfaces | review-animations | inventory of transitions and inappropriate motion | prefers-reduced-motion respected; measured durations |
| Final Polish Coordinator | release-coordinator | cross-screen | impeccable polish | consolidated review with blockers and proof | zero critical unresolved defects before owner approval |

**Policy:** specialist design roles are capability assignments to current VX agent contracts. Do not create duplicate sovereign agent IDs; real activation requires adapter/configuration, authorization, versioned skill provenance and runtime probe.

## Screen inventory and priorities

| Screen | User's question it must answer | Concrete primary components | Source/current state | Owner |
|---|---|---|---|---|
| Ω Reality Forge | What is running, why, and what may I authorize? | sovereign status, task DAG, blockers, evidence, actions requiring approval | PROPOSED as distinct shell | UX Critic + VX |
| Agents & Tasks | Which agent, capability, task and permission? | agent directory, role vs live-state, task execution trace, evidence panel | PARTIAL: workspace/dashboard and VX console | Interaction Engineer |
| Master Index Ω.000 | Which innovation came from where and what is proven? | source index, coverage, status disagreements, lineage view | PARTIAL via workspace indexes | Design Evidence Curator |
| ARC-X Evidence Lab | Are the sources and proofs sufficient? | claims/counterevidence, stale evidence, verification | SPECIFIED UI | Accessibility Auditor |
| Intelligence Bridge | Which models and tools are really connected? | configured vs probed vs active, version, latency, cost | SPECIFIED UI | Copy Reviewer |
| Repository Engineering | What changed and did it pass tests? | repository/commit, test matrix, policy gate, rollback | SPECIFIED UI | Final Polish Coordinator |
| Design System | What visual/interaction rules are authoritative? | tokens, components, typography, motion, audit issues | NEW DESIGN CONTRACT | Design Evidence Curator |

## Design direction — derived from current CSS, not a replacement palette
- Preserve dark navy basis; select a single semantic accent only after contrast and perception checks. Existing `#77d6bd` and `#83b7ff` are **observed alternatives**.
- Arabic first and RTL for sovereign command surfaces; LTR only for code, hashes and technical identifiers.
- Avoid unrelated decorative cards and excessive transitions. Provide mobile-first single-column navigation and persistent task/evidence context.
- Buttons need meaningful loading, disabled, error and success states. Animation must be interruptible and respect reduced motion.

## External skill due diligence
- `pbakaus/impeccable` verified upstream source: https://github.com/pbakaus/impeccable ; commands `critique`, `clarify`, `audit`, `polish`.
- `ibelick/ui-skills` verified upstream source: https://github.com/ibelick/ui-skills ; `create-design-md` is provenance-first and intended to modify DESIGN.md alone.
- `emil-design-eng` and `review-animations` were found in community-derived repository references, but the truncated user URL is **not** sufficient to identify an authoritative upstream commit: do not pin or execute until exact origin/licence/revision review.
- `nextlevelbuild...` was truncated; **UNRESOLVED SOURCE**, no inferred repository or code installation.
- No external `npx` install, remote shell, release, budget spend or publication in this change.

## Acceptance gates
1. Pin external URLs, source SHA, license and supported installation mode; treat dependencies as untrusted.
2. Inspect existing rendered UI at phone and desktop sizes; capture verifiable baseline and CSS token evidence.
3. Prepare design token proposal, UX issue list and agent-to-screen contracts in isolation.
4. Run accessibility/motion/visual regression and CI with reproducible receipts; separate static detector pass from user-tested UX.
5. Human approval required for visual identity selection, main merge and publication. No changes to project.genome or Ω.000.
