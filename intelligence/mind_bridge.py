"""Bridge mission-selected minds to the optional OpenAI Responses adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping

from intelligence.multi_mind_orchestrator import Mind, Proposal, Task
from intelligence.openai_responses_adapter import OpenAIResponsesAdapter


@dataclass(frozen=True)
class MindRun:
    mind_id: str
    role: str
    result: Mapping[str, Any]


class OpenAIMindAdapter:
    def __init__(self, adapter: OpenAIResponsesAdapter | None = None) -> None:
        self.adapter = adapter or OpenAIResponsesAdapter()

    def run(self, mind: Mind, task: Task) -> Dict[str, Any]:
        return self.adapter.run(
            objective=(
                f"Role: {mind.role}\n"
                f"Capabilities: {', '.join(mind.capabilities)}\n"
                f"Task kind: {task.kind}\n"
                f"Objective: {task.objective}"
            ),
            context={
                **task.context,
                "mind_id": mind.id,
                "constraints": task.constraints,
            },
        )


class MissionDeliberator:
    """Run only the minds selected for a customer mission."""

    def __init__(self, minds: Iterable[Mind], adapter: OpenAIMindAdapter | None = None) -> None:
        self.minds = {m.id: m for m in minds if m.enabled}
        self.adapter = adapter or OpenAIMindAdapter()

    def deliberate(self, task: Task, selected_mind_ids: Iterable[str]) -> List[MindRun]:
        out: List[MindRun] = []
        for mind_id in dict.fromkeys(selected_mind_ids):
            mind = self.minds.get(mind_id)
            if mind is None:
                continue
            out.append(MindRun(mind.id, mind.role, self.adapter.run(mind, task)))
        return out

    @staticmethod
    def proposals(task: Task, runs: Iterable[MindRun]) -> List[Proposal]:
        return [
            Proposal(mind_id=run.mind_id, task_id=task.id, output=run.result)
            for run in runs
        ]
