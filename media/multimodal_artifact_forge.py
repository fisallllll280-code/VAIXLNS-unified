"""Multimodal artifact forge from one VXSL/system IR."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Tuple

@dataclass(frozen=True)
class Artifact:
    id: str
    kind: str
    source_system_id: str
    content_plan: Tuple[str, ...]
    provenance: Tuple[str, ...] = ()

class MultimodalArtifactForge:
    def build(self, system_id: str, domains: Iterable[str], provenance: Iterable[str] = ()) -> list[Artifact]:
        d=set(domains)
        common=('architecture_graph','system_timeline','evidence_overlay')
        artifacts=[
            Artifact(f'{system_id}:diagram','engineering-diagram',system_id,common,tuple(provenance)),
            Artifact(f'{system_id}:story','technical-storyboard',system_id,('problem','laws','simulation','architecture','verification','evolution'),tuple(provenance)),
            Artifact(f'{system_id}:video','engineering-video',system_id,('keyframes','simulation-footage','narration','evidence-overlay'),tuple(provenance)),
            Artifact(f'{system_id}:interactive','interactive-exploration',system_id,('3d-scene','parameters','state-controls','proof-view'),tuple(provenance)),
        ]
        if {'physics','engineering'} & d:
            artifacts.append(Artifact(f'{system_id}:twin','digital-twin-view',system_id,('state','geometry','time','parameters'),tuple(provenance)))
        return artifacts

    @staticmethod
    def to_dict(artifact: Artifact) -> dict:
        return asdict(artifact)