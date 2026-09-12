from copy import deepcopy
import inspect
import numpy as np
import pytest
import torch

from solution.rl.environment import TrainingEnv,features,model_state
from solution.rl.model import CandidatePolicy
from solution.search.belief import (BeliefScenarioSampler,public_snapshot,restore_controller,
                                    action_dict,action_id,calls_from,validate_world)
from solution.search.teacher import RolloutTeacher,branch_rollout,branch_env


@pytest.fixture(scope='module')
def public_state():
    env=TrainingEnv(3,100000006);macros=[];original=env._request;calls=[]
    def request(path,p,ch):
        r=original(path,p,ch);calls.append(dict(path=path,position=list(p) if p is not None else None,channel=ch,response=r));return r
    env._request=request
    for _ in range(5):
        _,actions=env.observe();a=actions[env.controller.teacher_index(actions)];calls=[];env.step(a)
        macros.append(dict(action=action_dict(a),calls=deepcopy(calls)))
    return public_snapshot(macros),env


def test_public_schema_and_actor_features(public_state):
    public,env=public_state;c=restore_controller(public)
    env.controller.remaining_real_s=1200
    actions=c.legal_actions();state=model_state(features(c,actions))
    assert set(state)=={'global','channels','candidates'}
    assert [action_id(a) for a in actions]==[action_id(a) for a in env.controller.legal_actions()]
    for k,v in state.items():np.testing.assert_array_equal(v,model_state(features(env.controller,actions))[k])
    bad=deepcopy(public);bad['actual_seed']=17
    with pytest.raises(ValueError):restore_controller(bad)
    bad=deepcopy(public);bad['macros'][0]['calls'][0]['response']['sources']=[]
    with pytest.raises(ValueError):restore_controller(bad)
    assert list(inspect.signature(BeliefScenarioSampler.sample).parameters)==['self','public','seed','count','max_seconds','position_attempts']


def test_hypotheses_full_history_fixed_error_and_branch_isolation(public_state):
    public,_=public_state;worlds,stats=BeliefScenarioSampler().sample(public,121,2,30)
    assert len(worlds)==2,stats
    c=restore_controller(public);actions=c.legal_actions();first=action_id(actions[0])
    for world in worlds:
        assert validate_world(world,calls_from(public))
        for s in world.scenario.sources:assert world.noise.error(s.channel,23.,79.)==world.noise.error(s.channel,23.,79.)
    a=branch_env(public,worlds[0]);b=branch_env(public,worlds[0])
    before=b.session.state;a.step(a.controller.legal_actions()[0]);assert b.session.state==before
    assert a.controller is not b.controller and a.session.kernel.noise is not b.session.kernel.noise
    result=branch_rollout(public,worlds[0],first,None);assert result['completion']
    # Fresh independent execution starts at the beginning, replays the public
    # macro prefix on the hypothesis, then executes the recorded full continuation.
    independent=branch_env(public_snapshot([]),worlds[0])
    from solution.search.belief import decode_action
    for macro in public['macros']:independent.step(decode_action(macro['action']))
    prefix=independent.controller.virtual_time
    for item in result['trace']:independent.step(decode_action(item['action']))
    assert independent.success and independent.controller.virtual_time-prefix==result['cost_s']


def test_nonanticipation_order_and_fallback(public_state,monkeypatch):
    public,actual=public_state;torch.set_num_threads(1);torch.manual_seed(91)
    model=CandidatePolicy().eval();teacher=RolloutTeacher(model,{'worlds':2,'candidate_limit':6,'state_seconds':60.,'sampler_seconds':30.})
    result,_=teacher.recommend(public,818)
    # Mutating the real environment cannot be consulted by this public-only API.
    saved=actual.session.kernel;actual.session.kernel=object()
    reverse=list(reversed(result['candidate_ids']))
    again,_=teacher.recommend(deepcopy(public),818,candidate_order=reverse)
    actual.session.kernel=saved
    assert result['target']==again['target'] and result['accepted']==again['accepted']
    one={r['candidate_id']:r['costs_s'] for r in result['branches']}
    two={r['candidate_id']:r['costs_s'] for r in again['branches']};assert one==two and one
    assert result['current'] in result['selected_candidates']
    timeout=RolloutTeacher(model,{'state_seconds':0.});r,_=timeout.recommend(public,1)
    assert not r['accepted'] and r['reason']=='insufficient_compatible_worlds'
    incomplete=RolloutTeacher(model,{'worlds':2,'max_macros':6,'state_seconds':60.})
    r,_=incomplete.recommend(public,818);assert not r['accepted']


@pytest.mark.parametrize('count',range(10,17))
@pytest.mark.parametrize('distribution',['area','edge','cluster','outward'])
def test_q3_complete_counts_and_boundaries(count,distribution):
    env=TrainingEnv(3,100100000+count,count=count,distribution=distribution,field='extreme')
    while not env.done:
        _,actions=env.observe();env.step(actions[env.controller.teacher_index(actions)])
    assert env.success,env.metrics()
