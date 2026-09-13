"""CPU data workers: actual public trajectories, separate search hypotheses."""
from copy import deepcopy
import hashlib
import json
import time

import numpy as np
import torch

from solution.rl.environment import TrainingEnv
from solution.rl.model import CandidatePolicy
from .belief import action_dict, public_snapshot, action_id
from .teacher import RolloutTeacher, policy_probs


def init_search_worker():
    torch.set_num_threads(1)


def collect_search_episode(job):
    seed,weights,config=job
    model=CandidatePolicy().eval();model.load_state_dict(weights)
    env=TrainingEnv(3,int(seed),max_macros=config.get('max_macros',400));macros=[];states=[];anchors=[]
    original=env._request;current_calls=[]
    def request(path,position,channel):
        response=original(path,position,channel)
        current_calls.append(dict(path=path,position=list(position) if position is not None else None,
                                  channel=channel,response=deepcopy(response)))
        return response
    env._request=request
    while not env.done:
        _,actions=env.observe();probs,state=policy_probs(model,env.controller,actions);chosen=int(probs.argmax())
        anchors.append(dict(state=state,target=probs,anchor=probs,weight=1.,kind='retention'))
        if len(actions)>1 and env.controller.discovered:
            kinds={a.kind for a in actions}
            priority=(2 if chosen!=env.controller.teacher_index(actions) else 0)+len(kinds)
            states.append((priority,env.controller.steps,public_snapshot(macros,env.controller.remaining_real_s)))
        action=actions[chosen];current_calls=[];env.step(action)
        macros.append(dict(action=action_dict(action),calls=deepcopy(current_calls)))
    metrics=env.metrics();records=[];rows=[]
    # Public-only priority, deterministic tie breaks; no truth-based state filter.
    states=sorted(states,key=lambda s:(-s[0],s[1]))[:config.get('states_per_episode',8)]
    teacher=RolloutTeacher(model,config.get('search',{}));started=time.perf_counter()
    for _,step,public in states:
        if time.perf_counter()-started>config.get('episode_search_seconds',180.):break
        # RNG depends on public history + fixed teacher salt, never actual scene seed.
        key=json.dumps(public,sort_keys=True).encode()+str(config.get('teacher_salt',1701)).encode()
        teacher_seed=int.from_bytes(hashlib.sha256(key).digest()[:4],'little')
        record,state=teacher.recommend(public,teacher_seed)
        record['public_macro_index']=step
        records.append(record)
        if record['accepted']:
            rows.append(dict(state=state,target=np.asarray(record['target'],np.float32),
                             anchor=np.asarray(record['current_probabilities'],np.float32),
                             weight=record['weight'],kind='search',candidate_ids=record['candidate_ids']))
    # Retain a declared 1:1 number of old-policy rows; labels have confidence weights.
    n=min(len(anchors),max(1,len(rows)))
    retain=[anchors[i] for i in np.linspace(0,len(anchors)-1,n).astype(int)]
    return dict(metrics=metrics,records=records,rows=rows+retain,search_labels=len(rows),
                retention_rows=len(retain),search_seconds=time.perf_counter()-started,
                requested_states=len(states),completed_states=len(records))


def evaluate_policy_episode(job):
    seed,weights,max_macros,search_config=job
    model=None
    if weights is not None:model=CandidatePolicy().eval();model.load_state_dict(weights)
    env=TrainingEnv(3,int(seed),max_macros=max_macros);macros=[];current_calls=[];search_rows=[]
    teacher=RolloutTeacher(model,search_config) if search_config is not None else None
    original=env._request
    def request(path,position,channel):
        r=original(path,position,channel)
        current_calls.append(dict(path=path,position=list(position) if position is not None else None,channel=channel,response=deepcopy(r)))
        return r
    env._request=request
    while not env.done:
        t=time.perf_counter();_,actions=env.observe()
        if model is None:chosen=env.controller.teacher_index(actions)
        else:probs,_=policy_probs(model,env.controller,actions);chosen=int(probs.argmax())
        if teacher and len(search_rows)<search_config.get('states_per_episode',8) and len(actions)>1 and env.controller.discovered:
            public=public_snapshot(macros,env.controller.remaining_real_s)
            key=json.dumps(public,sort_keys=True).encode()+b'validation-teacher'
            rec,_=teacher.recommend(public,int.from_bytes(hashlib.sha256(key).digest()[:4],'little'))
            search_rows.append({k:v for k,v in rec.items() if k not in ('public','examples')})
            if rec['accepted']:chosen=rec['recommended']
        env.decision_times.append(time.perf_counter()-t)
        action=actions[chosen];current_calls=[];env.step(action)
        macros.append(dict(action=action_dict(action),calls=deepcopy(current_calls)))
    metrics=env.metrics();metrics['decision_p50_s']=float(np.median(env.decision_times))
    metrics['decision_times_s']=env.decision_times
    metrics['search']=search_rows
    # Evaluation-only strata: never passed back into a controller/teacher.
    metrics['radius_class']=('1000','1500','uniform')[int(seed)%3]
    return metrics
