"""Optional OpenAI Responses API bridge for VX.

This adapter belongs to the intelligence plane. It never grants execution
authority and keeps the API key outside source control.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping

try:
    from openai import OpenAI
except ImportError:  # optional dependency
    OpenAI = None  # type: ignore[assignment]


class OpenAIResponsesAdapter:
    def __init__(self, model: str | None = None, client: Any | None = None) -> None:
        self.model = model or os.getenv("VX_OPENAI_MODEL", "gpt-5.6-luna")
        if client is not None:
            self.client = client
        elif OpenAI is not None and os.getenv("OPENAI_API_KEY"):
            self.client = OpenAI()
        else:
            self.client = None

    @property
    def configured(self) -> bool:
        return self.client is not None

    def run(self, objective: str, context: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        if not self.configured:
            return {
                "status": "not_configured",
                "reason": "install openai and provide OPENAI_API_KEY",
                "model": self.model,
            }

        input_text = objective
        if context:
            input_text += "\nContext:\n" + json.dumps(dict(context), ensure_ascii=False, sort_keys=True)

        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "You are a specialist mind inside VAIXLNS. "
                "Propose work only; do not assume execution authority. "
                "Return concise evidence-oriented reasoning."
            ),
            input=input_text,
        )
        return {
            "status": "ok",
            "model": self.model,
            "response_id": getattr(response, "id", None),
            "output_text": getattr(response, "output_text", ""),
        }
