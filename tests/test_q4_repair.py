import pytest
from solution.control.controller import Controller
from solution.rl.environment import TrainingEnv
from solution.rl import training


def test_q4_full_channel_coverage_is_required():
    c=Controller(4)
    for i,p in enumerate(c.stations[:-1]):
        c.observe(1,p,'no_signal',station=i)
        assert c.channels[1].status=='UNKNOWN'
    # Wrong location must not count as the final station.
    c.observe(1,(99999,99999),'no_signal',station=len(c.stations)-1)
    assert c.channels[1].status=='UNKNOWN'
    c.observe(1,c.stations[-1],'no_signal',station=len(c.stations)-1)
    assert c.channels[1].status=='ABSENT_CERTIFIED'
    assert c.channels[2].status=='UNKNOWN'
    assert not c.exit_allowed()


@pytest.mark.parametrize('count',range(10,17))
@pytest.mark.parametrize('distribution',['area','edge','cluster','outward'])
@pytest.mark.parametrize('field',['zero','smooth','extreme'])
def test_q4_teacher_complete_scene(count,distribution,field):
    env=TrainingEnv(4,30000000+count,count=count,distribution=distribution,field=field)
    seen=set()
    while not env.done:
        _,actions=env.observe()
        a=actions[env.controller.teacher_index(actions)]
        if a.kind=='COVER':
            assert a.station not in seen
            seen.add(a.station)
        env.step(a)
    assert env.success,env.metrics()
    assert len(env.session.state.cleared)==count


@pytest.mark.parametrize('seed',[504000,505000,507000,1620002,1620004])
def test_q4_old_deadlocks_terminate(seed):
    env=TrainingEnv(4,seed)
    while not env.done:
        _,actions=env.observe()
        env.step(actions[env.controller.teacher_index(actions)])
    assert env.success,env.metrics()


def test_macro_budget_is_honored():
    env=TrainingEnv(4,1620002,max_macros=1)
    _,aa=env.observe();env.step(aa[env.controller.teacher_index(aa)])
    assert env.done and env.error=='macro_budget' and env.controller.steps==1


def test_successful_episode_reward_sum_is_time_per_source_objective():
    env=TrainingEnv(4,30000012,count=12,distribution='area',field='zero')
    total=0.
    while not env.done:
        _,actions=env.observe();reward,_=env.step(actions[env.controller.teacher_index(actions)])
        total+=reward
    assert env.success
    assert total==pytest.approx(-env.metrics()['virtual_time_s']/(100*12),abs=1e-9)


def test_failure_penalty_prevents_early_failure_from_ranking_as_fast():
    env=TrainingEnv(4,30000012,count=12,distribution='area',field='zero',max_macros=1)
    _,actions=env.observe();reward,done=env.step(actions[env.controller.teacher_index(actions)])
    assert done and not env.success and reward < -1000


def test_incomplete_teacher_cannot_select_faster_model(monkeypatch):
    def fake_collect(pool,problem,seeds,model=None,*args,**kwargs):
        return [([],dict(seed=1,N=10,completion=False,virtual_time_s=100 if model is None else 1))]
    monkeypatch.setattr(training,'collect',fake_collect)
    result=training.paired_evaluation(None,4,[1],object())
    assert result['mean_paired_delta_s']<0
    assert not result['selection_pass'] and not result['eligible']
