from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping
from intent.v_ir import CandidatePlan, Intent, compile_intent
from .atomaton import Atomaton
from .flux_grid import FluxGrid, FluxPlan

def _digest(value:Any)->str:
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

@dataclass(frozen=True)
class ContinuumPlan:
    intent:CandidatePlan
    constraints:tuple[str,...]
    invariant_digest:str
    topology:FluxPlan
    atomaton:Atomaton
    plan_digest:str

class ContinuumCompiler:
    def __init__(self,flux:FluxGrid): self.flux=flux
    def compile(self,intent:Intent,*,invariants:tuple[str,...]=(),resource_boundary:Mapping[str,Any]|None=None,input_cids:tuple[str,...]=())->ContinuumPlan:
        vir=compile_intent(intent)
        constraints=tuple(dict.fromkeys(vir.constraints))
        invariant_digest=_digest(tuple(dict.fromkeys(invariants)))
        topology=self.flux.plan(intent_id=vir.intent_id,capability=vir.capability,max_nodes=1)
        atomaton=Atomaton.spawn(execution_id=f'atom:{vir.plan_digest[:16]}',parent_intent_id=vir.intent_id,capability_id=vir.capability,contract_id=f'contract:{vir.capability}:v1',resource_boundary=resource_boundary or {},input_cids=input_cids)
        body={'intent':vir.plan_digest,'constraints':constraints,'invariants':invariant_digest,'topology':topology.topology_digest,'atomaton':atomaton.execution_id}
        return ContinuumPlan(vir,constraints,invariant_digest,topology,atomaton,_digest(body))
