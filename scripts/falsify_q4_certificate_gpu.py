#!/usr/bin/env python3
"""GPU angular-gap counterexample search for Q4 directional layouts.

NO_COUNTEREXAMPLE_FOUND is empirical and is never promoted to a proof.
"""
import argparse,json,math,time
from fractions import Fraction
from pathlib import Path
import torch


def number(value):
    return float(Fraction(value)) if isinstance(value,str) else float(value)


def confirm(stations,p,radius):
    vectors=[]
    for sx,sy in stations:
        dx,dy=sx-p[0],sy-p[1];d=math.hypot(dx,dy)
        if 0<d<=radius:vectors.append((math.atan2(dy,dx)%(2*math.pi),dx,dy,d))
    if len(vectors)<2:return dict(confirmed=True,near_count=len(vectors),reason='fewer_than_two_noncoincident_stations')
    vectors.sort();angles=[v[0] for v in vectors];gaps=[angles[i+1]-angles[i] for i in range(len(angles)-1)]+[angles[0]+2*math.pi-angles[-1]]
    i=max(range(len(gaps)),key=gaps.__getitem__);gap=gaps[i]
    heading=(angles[i]+gap/2)%(2*math.pi)
    dots=[math.cos(heading)*v[1]+math.sin(heading)*v[2] for v in vectors]
    confirmed=gap>math.pi+1e-12 and max(dots)<-1e-9
    return dict(confirmed=confirmed,near_count=len(vectors),max_angle_gap_rad=gap,
                heading_deg=math.degrees(heading),max_dot_margin=max(dots),
                station_margins=[dict(distance_m=v[3],dot=dots[j]) for j,v in enumerate(vectors)])


def main():
    ap=argparse.ArgumentParser();ap.add_argument('layout');ap.add_argument('--samples',type=int,default=1000000)
    ap.add_argument('--seed',type=int,default=0);ap.add_argument('--chunk-size',type=int,default=200000)
    ap.add_argument('--device',default='cuda:0');ap.add_argument('--source-radius',type=float,default=1800.)
    ap.add_argument('--receive-radius',type=float,default=1000.);ap.add_argument('--output');a=ap.parse_args()
    raw=json.loads(Path(a.layout).read_text());station_list=[(number(s['x']),number(s['y'])) for s in raw['stations']]
    device=torch.device(a.device if torch.cuda.is_available() else 'cpu');stations=torch.tensor(station_list,dtype=torch.float64,device=device)
    generator=torch.Generator(device=device).manual_seed(a.seed);checked=0;worst_gap=0.;worst_point=None;min_near=len(station_list);found=None
    started=time.perf_counter()
    while checked<a.samples and found is None:
        n=min(a.chunk_size,a.samples-checked)
        angle=torch.rand(n,generator=generator,device=device,dtype=torch.float64)*(2*math.pi)
        radius=torch.sqrt(torch.rand(n,generator=generator,device=device,dtype=torch.float64))*a.source_radius
        # Reserve a fifth of every chunk for exact-circle boundary attacks.
        boundary=max(1,n//5);radius[:boundary]=a.source_radius
        p=torch.stack((radius*torch.cos(angle),radius*torch.sin(angle)),1)
        delta=stations[None,:,:]-p[:,None,:];distance=torch.linalg.vector_norm(delta,dim=-1)
        valid=(distance<=a.receive_radius)&(distance>0)
        theta=torch.atan2(delta[:,:,1],delta[:,:,0])
        theta=torch.where(valid,theta,torch.full_like(theta,float('nan')))
        sorted_theta,_=torch.sort(theta,dim=1);count=valid.sum(1)
        differences=sorted_theta[:,1:]-sorted_theta[:,:-1]
        valid_gap=torch.arange(theta.shape[1]-1,device=device)[None,:]<(count-1).clamp(min=0)[:,None]
        consecutive=torch.where(valid_gap,differences,torch.full_like(differences,-torch.inf))
        # Avoid clever indexing for the wrap gap: gather first/last valid angle.
        first=sorted_theta[:,0];last=sorted_theta.gather(1,(count-1).clamp(min=0).unsqueeze(1)).squeeze(1)
        gap=torch.maximum(consecutive.max(1).values,first+2*math.pi-last)
        gap=torch.where(count>=2,gap,torch.full_like(gap,2*math.pi))
        value,index=gap.max(0);near_min=int(count.min().item());min_near=min(min_near,near_min)
        if float(value)>worst_gap:worst_gap=float(value);worst_point=p[int(index)].cpu().tolist()
        candidates=(gap>math.pi+1e-10).nonzero()
        if len(candidates):
            for ci in candidates[:32,0].tolist():
                point=p[ci].cpu().tolist();detail=confirm(station_list,point,a.receive_radius)
                if detail['confirmed']:
                    found=dict(position=point,**detail);break
        checked+=n
    status='FALSIFIED' if found else 'NO_COUNTEREXAMPLE_FOUND'
    result=dict(status=status,samples=checked,source_radius_m=a.source_radius,receive_radius_m=a.receive_radius,
        min_noncoincident_near_station_count=min_near,worst_max_angle_gap_rad=worst_gap,worst_point=worst_point,
        counterexample=found,device=str(device),dtype='float64',seed=a.seed,elapsed_s=time.perf_counter()-started,
        meaning='empirical attack only; NO_COUNTEREXAMPLE_FOUND is not a continuous-domain proof')
    encoded=json.dumps(result,indent=2)
    if a.output:Path(a.output).write_text(encoded)
    print(encoded);return 1 if found else 0
if __name__=='__main__':raise SystemExit(main())
