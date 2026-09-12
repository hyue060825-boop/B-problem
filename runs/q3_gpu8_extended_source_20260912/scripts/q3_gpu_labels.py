#!/usr/bin/env python3
"""Collect public roots, run GPU search separately, and freeze weighted SFT data."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time

import numpy as np
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.environment import TrainingEnv
from solution.rl.model import CandidatePolicy
from solution.rl.training import atomic_json,load_checkpoint,provenance
from solution.search.belief import action_dict,public_snapshot
from solution.search.teacher import policy_probs
from q3_gpu_search import prepare_task


def collect_roots(job):
    seed,weights,count,salt=job
    torch.set_num_threads(1)
    model=CandidatePolicy().eval();model.load_state_dict(weights)
    env=TrainingEnv(3,seed,max_macros=400);macros=[];states=[];anchors=[];calls=[]
    original=env._request
    def request(path,position,channel):
        response=original(path,position,channel)
        calls.append(dict(path=path,position=list(position) if position is not None else None,
                          channel=channel,response=deepcopy(response)))
        return response
    env._request=request
    while not env.done:
        _,actions=env.observe();prob,state=policy_probs(model,env.controller,actions);chosen=int(prob.argmax())
        anchors.append(dict(state=state,target=prob,anchor=prob,weight=1.,kind='retention'))
        if len(actions)>1 and env.controller.discovered:
            priority=(2 if chosen!=env.controller.teacher_index(actions) else 0)+len({a.kind for a in actions})
            public=public_snapshot(macros,env.controller.remaining_real_s)
            key=json.dumps(public,sort_keys=True).encode()+str(salt).encode()
            teacher_seed=int.from_bytes(hashlib.sha256(key).digest()[:4],'little')
            states.append((priority,env.controller.steps,public,teacher_seed))
        action=actions[chosen];calls=[];env.step(action)
        macros.append(dict(action=action_dict(action),calls=deepcopy(calls)))
    if not env.success:raise RuntimeError(f'public trajectory incomplete: {env.metrics()}')
    chosen=sorted(states,key=lambda r:(-r[0],r[1]))[:count]
    return dict(metrics=env.metrics(),roots=[(r[2],r[3]) for r in chosen],anchors=anchors)


def export_labels(tasks,search_dir,anchors,policy_sha):
    rows=[];reasons={};seen=set()
    for task in tasks:
        root=task['root_id']
        if root in seen:raise ValueError('duplicate root')
        seen.add(root)
        rec=json.loads((Path(search_dir)/(root+'.json')).read_text())
        if rec['root_id']!=root or rec['policy_sha256']!=policy_sha:raise ValueError('root/policy version mismatch')
        if rec['candidate_ids']!=task['candidate_ids']:raise ValueError('candidate order mismatch')
        reasons[rec['reason']]=reasons.get(rec['reason'],0)+1
        if not rec['accepted']:continue
        expected={(root,task['candidate_ids'][i],j,0) for i in task['selected'] for j in range(task['config']['worlds'])}
        branches=rec['full_branches']
        if len(branches)!=len(expected) or {tuple(r['branch_id']) for r in branches}!=expected:
            raise ValueError('partial or duplicate branches in accepted label')
        if any(r['reason'] in ('search_timeout','expansion_budget') for r in branches):raise ValueError('truncated label')
        target=np.asarray(rec['target'],np.float32)
        if not np.isfinite(target).all() or (target<0).any() or not np.isclose(target.sum(),1):raise ValueError('invalid label probabilities')
        if len(target)!=len(task['candidate_ids']) or not np.isfinite(rec['weight']) or rec['weight']<=0:raise ValueError('invalid label weight/shape')
        rows.append(dict(state=task['state'],target=target,anchor=np.asarray(task['probabilities'],np.float32),
                         weight=rec['weight'],kind='search',candidate_ids=task['candidate_ids'],root_id=root))
    labels=len(rows)
    if not labels:raise ValueError('no accepted GPU search labels; cannot claim search fine-tuning')
    count=min(len(anchors),labels)
    rows.extend(anchors[i] for i in np.linspace(0,len(anchors)-1,count).astype(int))
    return rows,dict(roots=len(tasks),search_labels=labels,retention_rows=count,filter_reasons=reasons)


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['collect','export'])
    p.add_argument('--output',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--seed',type=int,default=410000000);p.add_argument('--episodes',type=int,default=256)
    p.add_argument('--states',type=int,default=4);p.add_argument('--workers',type=int,default=32)
    p.add_argument('--search-dir');a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    policy_sha=hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest()
    if a.command=='export':
        data=torch.load(out/'tasks.pt',map_location='cpu',weights_only=False)
        if data['policy_sha256']!=policy_sha:raise ValueError('frozen policy mismatch')
        rows,summary=export_labels(data['tasks'],a.search_dir,torch.load(out/'anchors.pt',weights_only=False),policy_sha)
        tmp=out/'data.tmp';torch.save(rows,tmp);tmp.replace(out/'data.pt')
        summary.update(status='COMPLETE',policy_sha256=policy_sha,data_sha256=hashlib.sha256((out/'data.pt').read_bytes()).hexdigest())
        atomic_json(out/'labels_summary.json',summary);print(json.dumps(summary),flush=True);return
    if (out/'tasks.pt').exists():raise ValueError('use a new collection directory')
    model=CandidatePolicy();load_checkpoint(a.checkpoint,model);weights=model.state_dict()
    cfg=dict(worlds=8,candidate_limit=6,sampler_seconds=30.,state_seconds=120.,max_macros=400,max_expansions=20000,
             min_gain_s=5.,confidence_z=1.,temperature_s=40.)
    started=time.perf_counter();roots=[];anchors=[];metrics=[]
    seeds=list(range(a.seed,a.seed+a.episodes))
    atomic_json(out/'collection_manifest.json',dict(seeds=seeds,states_per_episode=a.states,teacher_salt=91703,
                policy_sha256=policy_sha,provenance=provenance(),search_config=cfg))
    with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn')) as pool:
        for i,result in enumerate(pool.map(collect_roots,[(s,weights,a.states,91703) for s in seeds]),1):
            roots.extend(result['roots']);anchors.extend(result['anchors']);metrics.append(result['metrics'])
            if i%16==0:print(json.dumps(dict(stage='PUBLIC_ROOTS',episodes=i,roots=len(roots),elapsed_s=time.perf_counter()-started)),flush=True)
        atomic_json(out/'collection_episodes.json',metrics)
        torch.save(anchors,out/'anchors.pt')
        tasks=[]
        for i,task in enumerate(pool.map(prepare_task,[(p,s,weights,cfg) for p,s in roots]),1):
            tasks.append(task)
            if i%32==0:print(json.dumps(dict(stage='HYPOTHESES',roots=i,total=len(roots),elapsed_s=time.perf_counter()-started)),flush=True)
    if len({t['root_id'] for t in tasks})!=len(tasks):raise ValueError('duplicate task IDs')
    tmp=out/'tasks.tmp';torch.save(dict(tasks=tasks,policy_sha256=policy_sha,config=cfg,provenance=provenance(),
                                   proposal_wall_s=time.perf_counter()-started),tmp);tmp.replace(out/'tasks.pt')
    atomic_json(out/'collection_summary.json',dict(status='COMPLETE',episodes=a.episodes,roots=len(tasks),elapsed_s=time.perf_counter()-started))


if __name__=='__main__':main()
