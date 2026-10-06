# VAIXLNS Intelligence Architecture Search v1

Status: IMPLEMENTED PRIMITIVE / NOT YET VERIFIED IN CI

## Purpose

Move the system from "choose a model" to "search, score, verify, and promote an
architecture of intelligence".

The unit being evaluated is a composition of model + agent + skill + tool +
workflow + verification, not a model in isolation.

## External execution sources incorporated as design inputs

- Anthropic Agent Skills: composable, dynamically loaded skills; the public
  repository includes a specification, templates, and example skills.
- Anthropic Knowledge Work Plugins: bundles of skills, connectors, commands,
  and sub-agents for role-specific workflows.
- OpenAI Agents SDK/API: tools, handoffs, guardrails, state, sandbox, tracing,
  MCP, and agent workflow evaluation.
- A2A: open interoperability between independent agent systems.
- MCP: tool/resource integration boundary.

These are external capability providers. They are not absorbed as VAIXLNS
projects and are not treated as evidence of local integration.

## Canonical search loop

Intent
-> Problem decomposition
-> Capability discovery
-> Candidate architecture generation
-> Deterministic fitness scoring
-> Sandbox execution
-> Evidence collection
-> Independent verification
-> Proof package
-> Promotion gate
-> VX execution
-> Runtime telemetry
-> Failure/causal analysis
-> Candidate mutation
-> Regression
-> Re-evaluation

## Candidate architecture record

Each candidate should eventually carry:

- candidate_id and immutable version
- models/providers
- agents
- skills/plugins
- MCP/A2A interfaces
- tools and permissions
- workflow/state machine
- dependencies
- evidence references
- verification references
- proof references
- cost/latency/reliability/security measurements
- failure modes and recovery strategy
- lineage to the originating intent

## Promotion invariant

A high score is not sufficient.

Promotion requires:

1. explicit evidence;
2. independent verification;
3. proof package;
4. fitness threshold;
5. reproducible lineage.

The current implementation enforces the first four. Reproducible lineage remains
an integration task with the existing evidence/provenance surfaces.

## Why this is deeper than an agent marketplace

A marketplace answers "what capabilities exist?".
A capability genome answers "what can each capability do?".
Architecture search answers "what composition should solve this problem?".
Proof-gated promotion answers "what is allowed to become authoritative?".

Together they create a controlled search space for intelligence.

## Non-claims

This module does not yet:
- call Claude/OpenAI/Gemini;
- execute remote agents;
- perform distributed consensus;
- provide formal mathematical proof;
- replace VX runtime;
- claim CI verification.

Those require separate integration and evidence.
