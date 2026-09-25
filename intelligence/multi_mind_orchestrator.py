"""
VX Multi-Mind Orchestrator.
Provider-neutral, local-first coordination for development and operations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Protocol
import json, os, subprocess, urllib.request

@dataclass
class Mind:
    id: str
    role: str
    capabilities: List[str]
    provider: str = "local"
    endpoint: str | None = None
    enabled: bool = True

@dataclass
class Task:
    id: str
    objective: str
    kind: str
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)

@dataclass
class Proposal:
    mind_id: str
    task_id: str
    output: Any
    evidence: List[str] = field(default_factory=list)

class MindAdapter(Protocol):
    def run(self, mind: Mind, task: Task) -> Any: ...

class LocalCommandAdapter:
    """Zero-cost adapter for locally installed AI CLIs/tools."""
    def run(self, mind: Mind, task: Task) -> Any:
        command = os.environ.get(f"VX_MIND_{mind.id.upper()}_COMMAND")
        if not command:
            return {"status": "not_configured", "mind": mind.id}
        payload = json.dumps({"task": task.objective, "kind": task.kind, "context": task.context, "constraints": task.constraints})
        proc = subprocess.run(command, input=payload, text=True, shell=True, capture_output=True, timeout=300)
        return {"status": "ok" if proc.returncode == 0 else "error", "stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}

class OpenAICompatibleAdapter:
    """Adapter for any operator-configured OpenAI-compatible endpoint."""
    def run(self, mind: Mind, task: Task) -> Any:
        if not mind.endpoint:
            return {"status": "not_configured", "mind": mind.id}
        body = json.dumps({"model": mind.id, "messages": [{"role": "user", "content": f"Objective: {task.objective}\nKind: {task.kind}\nContext: {json.dumps(task.context, ensure_ascii=False)}\nConstraints: {json.dumps(task.constraints, ensure_ascii=False)}"}]}).encode()
        req = urllib.request.Request(mind.endpoint.rstrip("/") + "/chat/completions", data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get("VX_AI_API_KEY", "")}"}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as response:
            return json.loads(response.read().decode())

class MultiMindOrchestrator:
    """Intelligence proposes; policy authorizes; VX executes; VV/OIF verifies."""
    def __init__(self, minds: Iterable[Mind], adapter: MindAdapter):
        self.minds = {m.id: m for m in minds if m.enabled}
        self.adapter = adapter

    def select(self, task: Task) -> List[Mind]:
        selected = [m for m in self.minds.values() if not task.kind or task.kind in m.capabilities or "general" in m.capabilities]
        return selected or list(self.minds.values())

    def deliberate(self, task: Task) -> List[Proposal]:
        return [Proposal(mind_id=m.id, task_id=task.id, output=self.adapter.run(m, task)) for m in self.select(task)]

    @staticmethod
    def synthesize(task: Task, proposals: List[Proposal]) -> Dict[str, Any]:
        return {"task_id": task.id, "objective": task.objective, "status": "PROPOSALS_READY", "proposals": [{"mind": p.mind_id, "output": p.output, "evidence": p.evidence} for p in proposals], "next_gate": "POLICY_AUTHORIZATION"}

def load_minds(path: str) -> List[Mind]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [Mind(**item) for item in data["minds"]]
