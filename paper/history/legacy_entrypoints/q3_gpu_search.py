#!/usr/bin/env python3
"""Recoverable root task queue: one frozen policy, configurable GPU workers."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import queue
import sys
import time
import traceback
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.model import CandidatePolicy
from solution.rl.training import atomic_json,provenance
from solution.search.belief import action_id,action_dict,restore_controller,BeliefScenarioSampler,calls_from
from solution.search.teacher import policy_probs,branch_rollout
from solution.search.gpu.kernel import hypothesis_hash,BACKEND_VERSION
from solution.search.gpu.rollout import batched_rollouts


def prepare_task(job):
    public,seed,weights,cfg=job;torch.set_num_threads(1)
    model=CandidatePolicy().eval();model.load_state_dict(weights);c=restore_controller(public);aa=c.legal_actions()
    prob,state=policy_probs(model,c,aa);current=int(prob.argmax());ids=[action_id(a) for a in aa]
    root_id=hashlib.sha256(json.dumps(public,sort_keys=True).encode()+str(seed).encode()).hexdigest()
    safe=[s.cert['center'] for s in c.channels.values() if s.status=='CLEARABLE' and s.cert]
    import math
    costs=[a.cost+(min(math.dist(a.position,p) for p in safe)/5 if safe else 0.) for a in aa]
    required={current}|{i for i,a in enumerate(aa) if a.kind in ('CLEAR','EXIT')}
    selected=sorted(required)
    for i in sorted(range(len(aa)),key=lambda i:(costs[i],ids[i])):
        if len(selected)<cfg['candidate_limit'] and i not in selected:selected.append(i)
    reason=None
    if len(aa)==1:reason='single_candidate'
    if len(required)>cfg['candidate_limit']:reason='mandatory_exceeds_candidate_budget'
    start=time.perf_counter()
    worlds,sampling=BeliefScenarioSampler().sample(public,seed,cfg['worlds'],cfg['sampler_seconds']) if reason is None else ([],{})
    if len(worlds)!=cfg['worlds'] and reason is None:reason='insufficient_compatible_worlds'
    return dict(root_id=root_id,public=public,teacher_seed=seed,worlds=worlds,sampling=sampling,proposal_s=time.perf_counter()-start,
                selected=selected,current=current,probabilities=prob.tolist(),state=state,candidate_ids=ids,
                candidates=[action_dict(a) for a in aa],hypothesis_hashes=[hypothesis_hash(k) for k in worlds],
                reason=reason,config=cfg,heuristic_cost_s=costs)


def label(task,results):
    cfg=task['config'];current=task['current'];ids=task['candidate_ids'];by={};branches=[]
    record={k:v for k,v in task.items() if k not in ('worlds','state')}
    record.update(accepted=False,target=task['probabilities'],weight=0.,branches=[],backend_version=BACKEND_VERSION)
    if task['reason']:return record
    for i in task['selected']:
        rr=[r for r in results if r['branch_id'][1]==ids[i]]
        if len(rr)!=cfg['worlds']:raise RuntimeError('partial root cannot be committed')
        rr=sorted(rr,key=lambda r:r['branch_id'][2]);values=np.array([r['cost_s'] for r in rr])
        by[i]=values;branches.append(dict(index=i,candidate_id=ids[i],costs_s=values.tolist(),successes=sum(r['completion'] for r in rr),
                                         effective=len(rr),completion=[r['completion'] for r in rr],mean_s=float(values.mean()),std_s=float(values.std())))
    record['branches']=branches
    if any(r['reason'] in ('search_timeout','expansion_budget') for r in results):record['reason']='incomplete_search';return record
    eligible=[r['index'] for r in branches if r['successes']==cfg['worlds']]
    if current not in eligible:record['reason']='baseline_incomplete';return record
    best=min(eligible,key=lambda i:(by[i].mean(),ids[i]));delta=by[current]-by[best]
    gain=float(delta.mean());se=float(delta.std(ddof=1)/np.sqrt(len(delta)))
    record.update(recommended=best,estimated_gain_s=gain,paired_se_s=se)
    if best==current or gain<=max(cfg['min_gain_s'],cfg['confidence_z']*se):record['reason']='no_confident_improvement';return record
    target=np.zeros(len(ids));v=np.array([-by[i].mean()/cfg['temperature_s'] for i in eligible]);v-=v.max();target[eligible]=np.exp(v)/np.exp(v).sum()
    record.update(accepted=True,target=target.tolist(),weight=float(np.clip(gain/max(1.,se),.25,4.)),reason='accepted')
    return record


def search_worker(device,mode,tasks_queue,events,task_path,checkpoint,out,batch_roots):
    try:
        torch.set_num_threads(1)
        if device!='cpu':torch.cuda.set_device(torch.device(device))
        started=time.perf_counter();model=CandidatePolicy().eval();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=False)['model'])
        tasks=torch.load(task_path,weights_only=False);index={t['root_id']:t for t in tasks['tasks']}
        # Warm up batch policy and float64 numeric ops before measuring tasks.
        if device!='cpu':
            gpu=deepcopy(model).to(device);fixture={'global':torch.zeros(8,10,device=device),'channels':torch.zeros(8,20,9,device=device),'candidates':torch.zeros(8,6,11,device=device)}
            with torch.inference_mode():gpu(fixture)
            torch.linalg.vector_norm(torch.ones(64,2,device=device,dtype=torch.float64),dim=-1);torch.cuda.synchronize();del gpu
        init_s=time.perf_counter()-started;completed=0
        while True:
            roots=[]
            for _ in range(batch_roots):
                try:roots.append(tasks_queue.get_nowait())
                except queue.Empty:break
            if not roots:break
            batch=[index[r] for r in roots];specs=[]
            for task in batch:
                if task['reason']:continue
                for i in task['selected']:
                    for j,k in enumerate(task['worlds']):specs.append((task['public'],k,task['candidate_ids'][i],(task['root_id'],task['candidate_ids'][i],j,0)))
            t=time.perf_counter()
            if mode=='reference':
                results=[]
                for public,k,first,identity in specs:
                    r=branch_rollout(public,k,first,model,max_macros=batch[0]['config']['max_macros'],deadline=t+batch[0]['config']['state_seconds']*len(batch))
                    r['branch_id']=identity;results.append(r)
                stats=dict(elapsed_s=time.perf_counter()-t,device='cpu',physics='reference',branches=len(specs))
            elif specs:
                results,stats=batched_rollouts(specs,model,device,physics='cpu' if mode=='policy' else 'tensor',
                                               max_macros=batch[0]['config']['max_macros'],max_seconds=batch[0]['config']['state_seconds']*len(batch),
                                               max_expansions=batch[0]['config']['max_expansions'])
            else:results=[];stats=dict(elapsed_s=0,branches=0)
            for task in batch:
                rr=[r for r in results if r['branch_id'][0]==task['root_id']];record=label(task,rr)
                record.update(policy_sha256=tasks['policy_sha256'],search_stats=stats,full_branches=rr)
                atomic_json(Path(out)/(task['root_id']+'.json'),record)
                completed+=1;events.put(dict(kind='ROOT',root=task['root_id'],device=device,accepted=record['accepted']))
        events.put(dict(kind='DONE',device=device,roots=completed,initialization_s=init_s))
    except Exception:
        events.put(dict(kind='ERROR',device=device,error=traceback.format_exc()));raise


def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--records',required=True);prep.add_argument('--checkpoint',required=True);prep.add_argument('--output',required=True)
    prep.add_argument('--roots',type=int,default=32);prep.add_argument('--workers',type=int,default=8)
    run=sub.add_parser('run');run.add_argument('--tasks',required=True);run.add_argument('--checkpoint',required=True);run.add_argument('--output',required=True)
    run.add_argument('--devices',default='0,1,2,3');run.add_argument('--mode',choices=['reference','policy','tensor'],default='tensor');run.add_argument('--batch-roots',type=int,default=2)
    run.add_argument('--max-roots',type=int);run.add_argument('--cpu-workers',type=int,default=4)
    a=ap.parse_args()
    if a.command=='prepare':
        files=sorted(Path(a.records).glob('*.json'));inputs=[]
        for path in files:
            d=json.loads(path.read_text())
            for r in d.get('records',[]):
                inputs.append((r['public'],r['teacher_seed']))
                if len(inputs)>=a.roots:break
            if len(inputs)>=a.roots:break
        cfg=dict(worlds=8,candidate_limit=6,sampler_seconds=30.,state_seconds=120.,max_macros=400,max_expansions=20000,
                 min_gain_s=5.,confidence_z=1.,temperature_s=40.)
        weights=torch.load(a.checkpoint,map_location='cpu',weights_only=False)['model'];started=time.perf_counter()
        with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn')) as pool:tasks=list(pool.map(prepare_task,[(p,s,weights,cfg) for p,s in inputs]))
        output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
        torch.save(dict(tasks=tasks,policy_sha256=hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest(),config=cfg,
                        provenance=provenance(),proposal_wall_s=time.perf_counter()-started),output)
        print(json.dumps(dict(roots=len(tasks),seconds=time.perf_counter()-started)));return
    task_path=Path(a.tasks);data=torch.load(task_path,weights_only=False)
    if hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest()!=data['policy_sha256']:raise ValueError('frozen policy mismatch')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    manifest=dict(tasks_sha256=hashlib.sha256(task_path.read_bytes()).hexdigest(),policy_sha256=data['policy_sha256'],
                  backend=BACKEND_VERSION,mode=a.mode,provenance=provenance())
    if (out/'manifest.json').exists() and json.loads((out/'manifest.json').read_text())!=manifest:raise ValueError('resume version mismatch')
    atomic_json(out/'manifest.json',manifest)
    all_tasks=[t['root_id'] for t in data['tasks']];pending=[r for r in all_tasks if not (out/(r+'.json')).exists()]
    selected=pending[:a.max_roots] if a.max_roots else pending
    devices=['cpu']*a.cpu_workers if a.mode=='reference' else ['cuda:'+d for d in a.devices.split(',')]
    ctx=mp.get_context('spawn');q=ctx.Queue();events=ctx.Queue()
    for r in selected:q.put(r)
    time.sleep(.1);started=time.perf_counter()
    workers=[ctx.Process(target=search_worker,args=(dev,a.mode,q,events,str(task_path),a.checkpoint,str(out),a.batch_roots)) for dev in devices]
    for p in workers:p.start()
    logs=[];done=0
    while done<len(workers):
        try:event=events.get(timeout=10)
        except queue.Empty:
            if any(p.exitcode not in (None,0) for p in workers):raise RuntimeError('worker failed; committed roots preserved; rerun resumes pending roots')
            continue
        logs.append(event)
        if event['kind']=='ERROR':
            atomic_json(out/'error.json',event);raise RuntimeError(event['error'])
        if event['kind']=='DONE':done+=1
        print(json.dumps(event),flush=True)
    for p in workers:p.join()
    rows=[json.loads((out/(r+'.json')).read_text()) for r in all_tasks if (out/(r+'.json')).exists()]
    summary=dict(status='COMPLETE' if len(rows)==len(all_tasks) else 'PARTIAL',roots=len(rows),expected_roots=len(all_tasks),new_roots=len(selected),
                 elapsed_s=time.perf_counter()-started,proposal_wall_s=data['proposal_wall_s'],devices=devices,batch_roots=a.batch_roots,
                 accepted=sum(r['accepted'] for r in rows),branches=sum(len(r['full_branches']) for r in rows),events=logs,
                 duplicate_roots=0,mode=a.mode)
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
