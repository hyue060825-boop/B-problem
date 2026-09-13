"""One-step improvement over shared conditional worlds, public continuation."""
from copy import deepcopy
import hashlib
import math
import time

import numpy as np
import torch

from bsim.clocks import ManualClock
from bsim.reference import State
from bsim.session import Session
from solution.rl.environment import TrainingEnv, features, model_state, FEATURE_VERSION
from .belief import (BeliefScenarioSampler, action_dict, action_id, restore_controller,
                     calls_from, CANDIDATE_VERSION, BELIEF_VERSION)


def policy_probs(model,controller,actions):
    state=model_state(features(controller,actions))
    tensors={k:torch.from_numpy(v).unsqueeze(0) for k,v in state.items()}
    with torch.inference_mode():logits,_=model(tensors)
    return logits.softmax(-1)[0].numpy(),state


def branch_env(public,kernel,controller=None,max_macros=400):
    env=object.__new__(TrainingEnv)
    env.controller=deepcopy(controller) if controller is not None else restore_controller(public)
    env.profile={'seed':None,'hypothesis':True}
    env.session=Session(deepcopy(kernel),ManualClock(),'LOCAL-TRAIN');env.session.ready_fixture()
    env.rid=0;env.max_macros=max_macros;env.started=time.perf_counter()
    env.path_length=0.;env.measure_count=0;env.switches=0;env.failures=0;env.probes=0;env.max_decision_s=0.
    env.decision_times=[];env.error=None;env.done=False;env.success=False
    env._request('/enter',None,None)
    state=State()
    for row in calls_from(public):
        if row['path'] in ('/measure','/clear'):
            state,_=env.session.kernel.transition(state,row['path'],tuple(row['position']),row['channel'])
    env.session.state=state
    return env


def branch_rollout(public,kernel,first,model,controller=None,max_macros=400,deadline=math.inf):
    env=branch_env(public,kernel,controller,max_macros);start=env.controller.virtual_time;trace=[]
    actions=env.controller.legal_actions();lookup={action_id(a):a for a in actions}
    if first not in lookup:return dict(completion=False,cost_s=None,reason='invalid_candidate',trace=[])
    action=lookup[first]
    while not env.done:
        if time.perf_counter()>deadline:return dict(completion=False,cost_s=None,reason='search_timeout',trace=trace)
        env.step(action)
        trace.append(dict(action=action_dict(action),virtual_time_s=env.controller.virtual_time,error=env.error))
        if not env.done:
            actions=env.controller.legal_actions()
            if not actions:return dict(completion=False,cost_s=None,reason='no_actions',trace=trace)
            if model is None:action=actions[env.controller.teacher_index(actions)]
            else:
                prob,_=policy_probs(model,env.controller,actions);action=actions[int(prob.argmax())]
    return dict(completion=env.success,cost_s=env.controller.virtual_time-start,
                reason=env.error or 'certified_exit',trace=trace)


class RolloutTeacher:
    def __init__(self,model,config=None):
        self.model=model.eval();self.config={
            'worlds':8,'candidate_limit':6,'state_seconds':20.,'sampler_seconds':8.,
            'max_expansions':20000,'max_macros':400,'temperature_s':40.,
            'min_gain_s':5.,'confidence_z':1.0,**(config or {})}

    def recommend(self,public,teacher_seed,candidate_order=None):
        started=time.perf_counter();cfg=self.config;deadline=started+cfg['state_seconds']
        controller=restore_controller(public);actions=controller.legal_actions()
        probs,state=policy_probs(self.model,controller,actions);current=int(probs.argmax())
        ids=[action_id(a) for a in actions]
        record=dict(version='q3-rollout-label-v1',belief_version=BELIEF_VERSION,features=FEATURE_VERSION,
                    candidate_version=CANDIDATE_VERSION,public=public,candidates=[action_dict(a) for a in actions],
                    candidate_ids=ids,current=current,current_probabilities=probs.tolist(),teacher_seed=int(teacher_seed),
                    accepted=False,target=probs.tolist(),weight=0.,budget=cfg,branches=[],expansions=0)
        def finish(reason):
            record.update(reason=reason,seconds=time.perf_counter()-started)
            return record,state
        if len(actions)==1:return finish('single_candidate')
        # Estimated seconds only: travel + explicit macro cost + open-route
        # lower-cost proxy to public safe centers. Geometry alone certifies safety.
        safe=[s.cert['center'] for s in controller.channels.values() if s.status=='CLEARABLE' and s.cert]
        heuristics=[a.cost+(min(math.dist(a.position,p) for p in safe)/5 if safe else 0.) for a in actions]
        mandatory={current}|{i for i,a in enumerate(actions) if a.kind in ('CLEAR','EXIT')}
        if len(mandatory)>cfg['candidate_limit']:return finish('mandatory_exceeds_candidate_budget')
        selected=sorted(mandatory)
        for i in sorted(range(len(actions)),key=lambda i:(heuristics[i],ids[i])):
            if i not in selected and len(selected)<cfg['candidate_limit']:selected.append(i)
        record['heuristic_cost_s']=heuristics;record['selected_candidates']=selected
        worlds,stats=BeliefScenarioSampler().sample(public,teacher_seed,cfg['worlds'],
                                                   min(cfg['sampler_seconds'],max(0.,deadline-time.perf_counter())))
        record['sampling']=stats
        if stats['uncertain']:return finish('insufficient_compatible_worlds')
        if candidate_order is not None:selected=sorted(selected,key=lambda i:candidate_order.index(ids[i]))
        costs={};success={};example_traces={}
        for i in selected:
            values=[];outcomes=[]
            for j,world in enumerate(worlds):
                if record['expansions']>=cfg['max_expansions']:return finish('expansion_budget')
                result=branch_rollout(public,world,ids[i],self.model,controller,cfg['max_macros'],deadline)
                record['expansions']+=len(result['trace'])
                if result['reason']=='search_timeout':return finish('search_timeout')
                values.append(result['cost_s']);outcomes.append(result['completion'])
                if j==0:example_traces[i]=result['trace']
            success[i]=sum(outcomes)
            costs[i]=np.array(values,dtype=float)
            record['branches'].append(dict(candidate_id=ids[i],index=i,successes=success[i],effective=len(worlds),
                                           rollout_estimated_cost_s=float(costs[i].mean()),std_s=float(costs[i].std()),
                                           costs_s=values,completion=outcomes))
        eligible=[i for i in selected if success[i]==len(worlds)]
        if current not in eligible:return finish('baseline_branch_incomplete')
        if not eligible:return finish('no_reliable_action')
        best=min(eligible,key=lambda i:(float(costs[i].mean()),ids[i]))
        delta=costs[current]-costs[best];gain=float(delta.mean())
        se=float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else math.inf
        record.update(recommended=best,estimated_gain_s=gain,paired_se_s=se,
                      examples={'current':example_traces[current],'recommended':example_traces[best]})
        if best==current or gain<=max(cfg['min_gain_s'],cfg['confidence_z']*se):return finish('no_confident_improvement')
        # Include statistically tied reliable actions with a negative-cost softmax.
        target=np.zeros(len(actions));v=np.array([-costs[i].mean()/cfg['temperature_s'] for i in eligible]);v-=v.max()
        target[eligible]=np.exp(v)/np.exp(v).sum()
        record.update(accepted=True,target=target.tolist(),weight=float(np.clip(gain/max(1.,se),.25,4.)))
        return finish('accepted')
