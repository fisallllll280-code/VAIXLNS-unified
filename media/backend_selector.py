"""Evidence-driven selector for open-weight video backends."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Mapping

class VideoBackendSelector:
    def __init__(self, registry_path: str | Path = 'media/open_video_backend_registry.json'):
        self.registry=json.loads(Path(registry_path).read_text(encoding='utf-8'))['backends']

    def select(self, required: Iterable[str]) -> list[dict]:
        required=set(required)
        scored=[]
        for backend in self.registry:
            capabilities=set(backend.get('capabilities',[]))
            score=len(required & capabilities)
            if score:
                scored.append((score,backend))
        scored.sort(key=lambda item:(-item[0],item[1]['id']))
        return [b for _,b in scored]

    def describe(self, backend_id: str) -> Mapping[str, object]:
        for backend in self.registry:
            if backend['id']==backend_id:
                return backend
        raise KeyError(backend_id)