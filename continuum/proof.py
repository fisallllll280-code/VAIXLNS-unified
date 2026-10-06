from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256
import json
from typing import Iterable

class ProofLevel(IntEnum):
    OBSERVATION=0
    DETERMINISTIC_REPLAY=1
    CRYPTOGRAPHIC_INTEGRITY=2
    MERKLE_STATE=3
    ATTESTATION=4
    ZK_EXECUTION=5
    FORMAL_VERIFICATION=6

def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

@dataclass(frozen=True)
class ProofPolicy:
    minimum_level:ProofLevel
    rationale:str=''
    require_independent_verifier:bool=False

@dataclass(frozen=True)
class ProofAtom:
    subject:str
    claim:str
    method:str
    preconditions:tuple[str,...]
    input_cids:tuple[str,...]
    execution_cid:str
    output_cids:tuple[str,...]
    verifier:str
    proof_type:ProofLevel
    proof_digest:str
    valid:bool
    parent_lineage:tuple[str,...]=()

    @classmethod
    def issue(cls,*,subject,claim,method,preconditions:Iterable[str],input_cids:Iterable[str],execution_cid,output_cids:Iterable[str],verifier,proof_type:ProofLevel,valid,parent_lineage:Iterable[str]=()):
        if not subject or not claim or not method or not verifier: raise ValueError('PROOF_ATOM_IDENTITY_REQUIRED')
        body={'subject':subject,'claim':claim,'method':method,'preconditions':tuple(preconditions),'input_cids':tuple(input_cids),'execution_cid':execution_cid,'output_cids':tuple(output_cids),'verifier':verifier,'proof_type':int(proof_type),'valid':valid,'parent_lineage':tuple(parent_lineage)}
        return cls(**body,proof_digest=_digest(body))

def select_proof_level(policy:ProofPolicy,*,available:Iterable[ProofLevel],verified:bool,independently_verified:bool=False):
    for level in sorted(set(available),reverse=True):
        if level < policy.minimum_level or not verified: continue
        if policy.require_independent_verifier and not independently_verified: continue
        return level
    return None
