from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Iterable

def canonical_hash(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    return sha256(raw).hexdigest()

@dataclass(frozen=True)
class VIR:
    intent_id:str
    actor_id:str
    capability:str
    inputs:Mapping[str,Any]
    constraints:tuple[str,...]
    digest:str

class IntentCompiler:
    def compile(self,intent_id:str,actor_id:str,capability:str,inputs:Mapping[str,Any],constraints:Iterable[str]=()) -> VIR:
        c=tuple(dict.fromkeys(constraints))
        body={"intent_id":intent_id,"actor_id":actor_id,"capability":capability,"inputs":dict(inputs),"constraints":c}
        return VIR(**body,digest=canonical_hash(body))

class IdempotencyStore:
    def __init__(self): self._done={}
    def get_or_run(self,key:str,fn):
        if key in self._done:return self._done[key]
        value=fn(); self._done[key]=value; return value

@dataclass(frozen=True)
class ReadinessCertificate:
    subject:str
    checks:Mapping[str,bool]
    evidence:tuple[str,...]
    final:bool
    digest:str

def readiness(subject:str,checks:Mapping[str,bool],evidence:Iterable[str]=()) -> ReadinessCertificate:
    ev=tuple(evidence); final=bool(checks) and all(checks.values()) and bool(ev)
    body={"subject":subject,"checks":dict(checks),"evidence":ev,"final":final}
    return ReadinessCertificate(**body,digest=canonical_hash(body))

@dataclass(frozen=True)
class Provenance:
    artifact:str
    source:str
    build:str
    digest:str

def provenance(artifact:str,source:str,build:str,content:bytes) -> Provenance:
    return Provenance(artifact,source,build,sha256(content).hexdigest())

class CausalBlastRadius:
    def __init__(self): self.edges={}
    def add(self,source:str,target:str): self.edges.setdefault(source,set()).add(target)
    def impact(self,root:str):
        seen=set(); q=[root]
        while q:
            cur=q.pop()
            for nxt in self.edges.get(cur,set()):
                if nxt not in seen: seen.add(nxt); q.append(nxt)
        return tuple(sorted(seen))

@dataclass(frozen=True)
class EvolutionDecision:
    candidate:str
    allowed:bool
    reasons:tuple[str,...]
    blast_radius:tuple[str,...]

class EvolutionGovernor:
    def admit(self,candidate:str,verified:bool,isolated:bool,independently_verified:bool,blast_radius:Iterable[str]) -> EvolutionDecision:
        reasons=[]
        if not verified: reasons.append("VERIFICATION_REQUIRED")
        if not isolated: reasons.append("ISOLATION_REQUIRED")
        if not independently_verified: reasons.append("INDEPENDENT_VERIFICATION_REQUIRED")
        return EvolutionDecision(candidate,not reasons,tuple(reasons),tuple(sorted(set(blast_radius))))

@dataclass(frozen=True)
class ToolRecord:
    name:str
    server:str
    scope:tuple[str,...]
    approved:bool
    health:str
    provenance:str

class MCPTrustRegistry:
    def __init__(self): self._tools={}
    def register(self,record:ToolRecord): self._tools[(record.server,record.name)]=record
    def authorize(self,server:str,name:str,scope:str)->bool:
        r=self._tools.get((server,name))
        return bool(r and r.approved and r.health=="healthy" and scope in r.scope and r.provenance)

def change_fingerprint(snapshot:Mapping[str,Any])->str:return canonical_hash(snapshot)
def detect_change(previous:str|None,snapshot:Mapping[str,Any]):
    current=change_fingerprint(snapshot); return current!=previous,current
