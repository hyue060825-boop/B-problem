#!/usr/bin/env python3
"""Build a finite rational quadtree witness proof for a frozen Q4 layout."""
import argparse,json,time
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.q4.exact import (cell_outside_disk,cell_vertices,hull,
    in_closed_convex_polygon,point,q,squared_distance,witness_valid)


def text(x):
    x=q(x)
    return str(x.numerator) if x.denominator==1 else f'{x.numerator}/{x.denominator}'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('layout');ap.add_argument('--output',required=True)
    ap.add_argument('--max-depth',type=int,default=10);ap.add_argument('--radius-cert',default='999')
    ap.add_argument('--time-budget-s',type=float,default=300);a=ap.parse_args()
    raw=json.loads(Path(a.layout).read_text());stations=[point((str(s['x']),str(s['y']))) for s in raw['stations']]
    radius=q(a.radius_cert);domain=q(str(raw.get('source_domain_radius_m',1800)))
    started=time.perf_counter();stack=[(0,0,0)];leaves=[];unknown=[];max_active=1
    while stack:
        if time.perf_counter()-started>a.time_budget_s:
            unknown.extend(stack);break
        depth,ix,iy=stack.pop();vertices=cell_vertices(depth,ix,iy,domain)
        if cell_outside_disk(vertices,domain):
            leaves.append(dict(depth=depth,ix=ix,iy=iy,status='OUTSIDE'));continue
        nearby=[i for i,s in enumerate(stations) if all(squared_distance(v,s)<=radius*radius for v in vertices)]
        if len(nearby)>=3:
            hs=hull([stations[i] for i in nearby])
            witness=[stations.index(p) for p in hs]
            if witness_valid(vertices,stations,witness,radius):
                leaves.append(dict(depth=depth,ix=ix,iy=iy,status='WITNESS',witness=witness));continue
        if depth>=a.max_depth:
            unknown.append((depth,ix,iy));continue
        for dy in (0,1):
            for dx in (0,1):stack.append((depth+1,2*ix+dx,2*iy+dy))
        max_active=max(max_active,len(stack))
    guards=[]
    for station_id,p in enumerate(stations):
        if squared_distance(p,(Fraction(0),Fraction(0)))>domain*domain:continue
        nearby=[i for i,s in enumerate(stations) if i!=station_id and squared_distance(p,s)<=radius*radius]
        hs=hull([stations[i] for i in nearby]);witness=[stations.index(v) for v in hs]
        guards.append(dict(station_id=station_id,witness=witness))
    artifact=dict(schema='q4-rational-quadtree-proof-v1',status='CANDIDATE',
        source_layout=str(Path(a.layout).resolve()),source_domain_radius=text(domain),radius_cert=text(radius),
        stations=[dict(id=i,x=text(p[0]),y=text(p[1])) for i,p in enumerate(stations)],
        leaves=leaves,unknown=[dict(depth=d,ix=x,iy=y) for d,x,y in unknown],overlap_guards=guards,
        build=dict(max_depth=a.max_depth,time_budget_s=a.time_budget_s,elapsed_s=time.perf_counter()-started,
                   max_active=max_active,leaf_count=len(leaves),unknown_count=len(unknown)))
    Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(artifact,indent=2))
    print(json.dumps(artifact['build']));return 0 if not unknown else 3
if __name__=='__main__':raise SystemExit(main())
