# Frontier Engineering Survey → VAIXLNS Design Inputs (2026-10-06)

## Purpose

This is a research input, not an Innovation Registry entry. External systems are studied as evidence about strong engineering patterns; VAIXLNS does not copy their implementation.

## Observed frontier patterns

### OpenAI
Public agent tooling emphasizes a code-owned agent loop, tools/MCP, sandboxed execution, guardrails, approvals, resumable state, tracing, and evaluation.

Design input for VAIXLNS:
- Treat external model/tool systems as capability providers.
- Keep authority, state, approval, and evidence outside the model.
- Make risky side effects pass explicit gates.

### Anthropic
Anthropic's 2026 engineering work emphasizes capping agent blast radius, and decoupling the agent "brain" from the execution "hands" so harness assumptions can evolve without coupling to the model.

Design input for VAIXLNS:
- Separate reasoning from effectful execution.
- Quantify and constrain blast radius before execution.
- Treat harness assumptions as versioned, testable contracts.

### Google DeepMind
Recent work includes multi-agent scientific hypothesis generation/refinement and an AI Control Roadmap for increasingly capable agents.

Design input for VAIXLNS:
- Make research a search loop, not a single answer.
- Treat validation as a bottleneck and a first-class system.
- Require controls that scale with capability and autonomy.

### Microsoft Research
Recent verifier research emphasizes real-time verification, process-vs-outcome separation, controllable-vs-uncontrollable failures, and executable constraints for root-cause localization.

Design input for VAIXLNS:
- Verify during execution, not only after it.
- Keep process evidence separate from outcome evidence.
- Preserve first-failure/root-cause evidence.

### Meta AI
AIRA² uses asynchronous multi-GPU research workers, reliable hidden evaluation, and interactive debugging to scale research agents.

Design input for VAIXLNS:
- Use parallel asynchronous search where appropriate.
- Protect selection from noisy/overfit evaluation.
- Make experiment throughput and evaluation quality jointly measurable.

### NVIDIA
Current agent runtime work emphasizes sandboxing and policy-managed execution boundaries.

Design input for VAIXLNS:
- Make the execution boundary explicit.
- Treat isolation and policy as runtime primitives, not UI options.

## VAIXLNS differentiation

These inputs are intentionally transformed into a stricter system:

1. Candidate ideas do not become canonical innovations merely because a model proposes them.
2. A candidate must survive sandbox execution, falsification, independent verification, replay/reproduction, and proof-coverage checks.
3. Competing architectures are evaluated by measurable evidence, not by model preference.
4. Novelty is checked against lineage and existing capability structure before adoption.
5. Architecture changes require blast-radius analysis, rollback evidence, and constitutional compatibility.
6. Unknowns and failed hypotheses remain first-class historical objects instead of being silently discarded.

## Source references

- OpenAI Agents SDK: https://developers.openai.com/api/docs/guides/agents/sdk
- OpenAI guardrails and approvals: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- Anthropic containment: https://www.anthropic.com/engineering/how-we-contain-claude
- Anthropic managed agents: https://www.anthropic.com/engineering/managed-agents
- Google DeepMind Co-Scientist: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/
- Google DeepMind AI Control: https://deepmind.google/blog/securing-the-future-of-ai-agents/
- Microsoft Universal Verifier: https://www.microsoft.com/en-us/research/articles/the-art-of-building-verifiers-for-computer-use-agents/
- Microsoft AgentRx: https://www.microsoft.com/en-us/research/blog/systematic-debugging-for-ai-agents-introducing-the-agentrx-framework/
- Microsoft Agentic Verifiers: https://www.microsoft.com/en-us/research/project/agentic-verifiers-provably-safe-test-time-scaling-for-reasoning-models/
- Meta AIRA²: https://ai.meta.com/research/publications/aira-overcoming-bottlenecks-in-ai-research-agents/
- NVIDIA/Microsoft sandbox runtime: https://developer.nvidia.com/blog/build-personal-ai-agents-on-windows-pcs-with-new-tools-from-microsoft-and-nvidia/
