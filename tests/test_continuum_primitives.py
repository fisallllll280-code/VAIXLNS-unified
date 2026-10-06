from continuum import Atomaton, AtomatonState, FluxGrid, FluxNode, ProofAtom, ProofLevel, ProofPolicy, ContinuumCompiler, select_proof_level
from intent.v_ir import Intent

def test_atomaton_lifecycle_is_bounded_and_dissolves():
    a=Atomaton.spawn(execution_id='exec:1',parent_intent_id='intent:1',capability_id='search',contract_id='contract:search:v1',resource_boundary={'cpu':1})
    for state in (AtomatonState.BOUND,AtomatonState.VALIDATED,AtomatonState.EXECUTING,AtomatonState.OBSERVED): a=a.transition(state)
    a=a.transition(AtomatonState.PROVED,evidence_cids=('ev:1',)); a=a.transition(AtomatonState.DISSOLVED)
    assert a.state is AtomatonState.DISSOLVED and a.trace_digest

def test_flux_grid_is_not_an_authority_plane():
    grid=FluxGrid([FluxNode('n2',frozenset({'search'}),risk=.4),FluxNode('n1',frozenset({'search'}),risk=.2)])
    plan=grid.plan(intent_id='i1',capability='search')
    assert plan.node_ids==('n1',) and not hasattr(grid,'commit') and not hasattr(grid,'authorize')

def test_compiler_connects_v_ir_to_flux_and_atomaton():
    compiler=ContinuumCompiler(FluxGrid([FluxNode('n1',frozenset({'search'}))]))
    plan=compiler.compile(Intent('i1','actor','verify','search',{'q':'x'},('bounded','bounded')),invariants=('I1','I1'),resource_boundary={'cpu':1})
    assert plan.constraints==('bounded',) and plan.invariant_digest and plan.topology.node_ids==('n1',) and plan.atomaton.parent_intent_id=='i1'

def test_proof_policy_requires_admissible_level():
    assert select_proof_level(ProofPolicy(ProofLevel.MERKLE_STATE,'state mutation'),available=(ProofLevel.OBSERVATION,ProofLevel.MERKLE_STATE),verified=True) is ProofLevel.MERKLE_STATE
    assert select_proof_level(ProofPolicy(ProofLevel.ZK_EXECUTION,require_independent_verifier=True),available=(ProofLevel.ZK_EXECUTION,),verified=True,independently_verified=False) is None

def test_proof_atom_binds_claim_to_execution():
    atom=ProofAtom.issue(subject='artifact:1',claim='candidate is admissible',method='deterministic-replay',preconditions=('I1','I2'),input_cids=('in:1',),execution_cid='exec:1',output_cids=('out:1',),verifier='vv:local',proof_type=ProofLevel.DETERMINISTIC_REPLAY,valid=True,parent_lineage=('intent:1',))
    assert atom.valid and atom.proof_digest
