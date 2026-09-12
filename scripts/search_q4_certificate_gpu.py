#!/usr/bin/env python3
"""Bounded GPU search for smaller Q4 directional station layouts.

The objective is an empirical angular-gap attack score. Returned layouts are
CANDIDATE until the independent exact witness verifier accepts a proof.
"""
import argparse,hashlib,json,math,time
from fractions import Fraction
from pathlib import Path
import random
import torch


def value(x):return float(Fraction(x)) if isinstance(x,str) else float(x)


def panel(generator,n,radius,device):
    angle=torch.rand(n,generator=generator,device=device,dtype=torch.float64)*2*math.pi
    radial=torch.sqrt(torch.rand(n,generator=generator,device=device,dtype=torch.float64))*radius
    radial[:max(1,n//4)]=radius
    return torch.stack((radial*torch.cos(angle),radial*torch.sin(angle)),1)


def score(points,stations,receive_radius=999.):
    delta=stations[None]-points[:,None];distance=torch.linalg.vector_norm(delta,dim=-1)
    valid=(distance<=receive_radius)&(distance>0);angles=torch.atan2(delta[:,:,1],delta[:,:,0])
    angles=torch.where(valid,angles,torch.full_like(angles,float('nan')));angles,_=torch.sort(angles,dim=1)
    count=valid.sum(1);diff=angles[:,1:]-angles[:,:-1]
    ok=torch.arange(angles.shape[1]-1,device=points.device)[None,:]<(count-1).clamp(min=0)[:,None]
    consecutive=torch.where(ok,diff,torch.full_like(diff,-torch.inf)).max(1).values
    last=angles.gather(1,(count-1).clamp(min=0).unsqueeze(1)).squeeze(1)
    gap=torch.maximum(consecutive,angles[:,0]+2*math.pi-last)
    gap=torch.where(count>=2,gap,torch.full_like(gap,2*math.pi))
    violation=torch.relu(gap-math.pi)
    return dict(violations=int((violation>1e-10).sum()),worst_gap=float(gap.max()),
                mean_violation=float(violation.mean()),min_near=int(count.min()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('base_layout');ap.add_argument('--output',required=True)
    ap.add_argument('--k',type=int,required=True);ap.add_argument('--population',type=int,default=32)
    ap.add_argument('--iterations',type=int,default=100);ap.add_argument('--samples',type=int,default=100000)
    ap.add_argument('--seed',type=int,default=0);ap.add_argument('--time-budget-s',type=float,default=600)
    ap.add_argument('--jitter-m',type=float,default=30.);ap.add_argument('--device',default='cuda:0');a=ap.parse_args()
    raw=json.loads(Path(a.base_layout).read_text());base=[(value(s['x']),value(s['y'])) for s in raw['stations']]
    if not 3<=a.k<=len(base):raise ValueError('K must be between 3 and base station count')
    device=torch.device(a.device if torch.cuda.is_available() else 'cpu');gen=torch.Generator(device=device).manual_seed(a.seed)
    rng=random.Random(a.seed);points=panel(gen,a.samples,1800.,device);started=time.perf_counter();best=None;done=0
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    for iteration in range(a.iterations):
        if time.perf_counter()-started>=a.time_budget_s:break
        for member in range(a.population):
            candidate_index=iteration*a.population+member
            if a.k==len(base)-1 and candidate_index<len(base):
                ids=[i for i in range(len(base)) if i!=candidate_index]
                xy=torch.tensor([base[i] for i in ids],dtype=torch.float64,device=device)
            elif best is not None and member<a.population//2:
                ids=list(best['source_ids']);xy=torch.tensor([[value(s['x']),value(s['y'])] for s in best['stations']],dtype=torch.float64,device=device)
            else:
                ids=sorted(rng.sample(range(len(base)),a.k));xy=torch.tensor([base[i] for i in ids],dtype=torch.float64,device=device)
            if candidate_index>=len(base) and a.jitter_m:
                xy=xy+torch.randn(xy.shape,generator=gen,device=device,dtype=torch.float64)*(a.jitter_m/math.sqrt(iteration+1))
            metrics=score(points,xy)
            objective=(metrics['violations'],metrics['mean_violation'],metrics['worst_gap'])
            if best is None or objective<best['objective']:
                stations=[dict(id=i,x=str(float(p[0])),y=str(float(p[1]))) for i,p in enumerate(xy.cpu().tolist())]
                best=dict(objective=objective,metrics=metrics,iteration=iteration,member=member,stations=stations,source_ids=ids)
        done=iteration+1
        checkpoint=dict(schema='q4-layout-search-v1',status='CANDIDATE' if best['metrics']['violations']==0 else 'FALSIFIED_ON_SEARCH_PANEL',
            k=a.k,stations=best['stations'],source_domain_radius_m=1800,radius_search_m=999,
            best={k:v for k,v in best.items() if k!='stations'},search=dict(seed=a.seed,samples=a.samples,population=a.population,
            iterations_completed=done,time_budget_s=a.time_budget_s,elapsed_s=time.perf_counter()-started,device=str(device),dtype='float64',
            base_layout=str(Path(a.base_layout).resolve()),base_sha256=hashlib.sha256(Path(a.base_layout).read_bytes()).hexdigest(),
            meaning='empirical search only; requires independent attack and exact proof'))
        (output/'checkpoint.json').write_text(json.dumps(checkpoint,indent=2))
        print(json.dumps(dict(iteration=done,**best['metrics'])),flush=True)
    final=json.loads((output/'checkpoint.json').read_text());final['search']['complete']=done==a.iterations
    (output/'best_layout.json').write_text(json.dumps(final,indent=2));
    print(json.dumps(dict(status=final['status'],k=a.k,**final['best']['metrics'],elapsed_s=final['search']['elapsed_s'])))
    return 0
if __name__=='__main__':raise SystemExit(main())
