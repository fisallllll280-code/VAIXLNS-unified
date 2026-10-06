from governance.capability_registry import Capability, CapabilityRegistry
from governance.governance_engine import GovernanceEngine
from scck import Artifact, Contract, ExternalObservation, KernelState, SCCKKernel, canonical_hash
from continuum import ProofAtom, ProofLevel, ProofPolicy, select_proof_level
from evolution.governed_change import create_proposal, admit_proposal


def test_scck_commit_precedes_proof_atom_and_proof_atom_does_not_authorize():
    registry=CapabilityRegistry(); registry.register(Capability('continuum.execute'))
    kernel=SCCKKernel(registry,GovernanceEngine(),authority_resolver=lambda *_: True)
    contract=Contract('contract:continuum','1.0','continuum.execute','READY','EXECUTED')
    current=Artifact('artifact:continuum',canonical_hash({'x':1}),contract.schema_cid,'default','authority:a','local','','contract:continuum','READY',0,1,'n','VAIXLNS','continuum.execute',{'x':1})
    prepared=kernel.prepare(actor_id='a',permissions={'execute'},capability_id='continuum.execute',current=current,contract=contract)
    assert prepared.state is KernelState.PREPARED
    payload={'ok':True}
    observation=ExternalObservation(prepared.intent.intent_id,'atom:worker',True,payload,canonical_hash(payload),'EXECUTED',1,1)
    committed=kernel.finalize(intent=prepared.intent,current=current,observation=observation,contract=contract,policy=None)
    assert committed.state is KernelState.COMMITTED
    level=select_proof_level(ProofPolicy(ProofLevel.DETERMINISTIC_REPLAY),available=(ProofLevel.DETERMINISTIC_REPLAY,),verified=True)
    atom=ProofAtom.issue(subject=committed.artifact.artifact_id,claim='execution produced admissible state',method='scck-readback',preconditions=('I1','I3'),input_cids=(current.content_cid,),execution_cid=prepared.intent.intent_id,output_cids=(committed.artifact.content_cid,),verifier='VV',proof_type=level,valid=True,parent_lineage=(prepared.intent.intent_id,))
    assert atom.valid and atom.proof_type is ProofLevel.DETERMINISTIC_REPLAY
    assert not hasattr(atom,'authorize') and not hasattr(atom,'commit')


def test_evolution_gate_remains_independent_boundary():
    proposal=create_proposal(candidate_id='continuum:candidate',base_branch='main',proposed_branch='feat/candidate',required_checks=('functional','security','replay'),impact_nodes=('VX', 'SCCK'),verified=True,independent=True,replayable=True)
    accepted=admit_proposal(proposal,explicit_authority=True)
    blocked=admit_proposal(proposal,explicit_authority=False)
    assert accepted.accepted
    assert not blocked.accepted and 'EXPLICIT_AUTHORITY_REQUIRED' in blocked.reasons
