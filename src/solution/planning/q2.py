"""Q2保证接收内近似 + 有限场景后验评价；不声称连续全局最优。"""
import json
import math
import time
from pathlib import Path
import numpy as np
from shapely.geometry import Point, GeometryCollection
from solution.geometry.core import (FeasibleRegion, RECV_RADIUS, circle_polygon,
                                    clip,wedge,mec,vertices_of)
from solution.evaluation.artifacts import dump,hash_files,plot_polygon


def receive_region(k,radius=RECV_RADIUS):
    v=k.vertices
    if not len(v):
        return GeometryCollection()
    region=circle_polygon(v[0],radius,n=128,outer=False)
    for x in v[1:]:
        region=region.intersection(circle_polygon(x,radius,n=128,outer=False))
    return region


def source_scenarios(k,count=7):
    """显式几何场景点，不假设官方均匀分布。"""
    v=k.vertices
    if not len(v):
        return []
    center=np.array(k.geom.representative_point().coords[0])
    indices=np.linspace(0,len(v)-1,min(count,len(v))).astype(int)
    candidates=[center]+[v[i] for i in indices]
    lo,hi=v[np.argmin(v[:,0])],v[np.argmax(v[:,0])]
    candidates.extend((1-t)*lo+t*hi for t in np.linspace(.1,.9,count))
    return np.array([x for x in candidates if k.geom.buffer(1e-6).covers(Point(x))])


def evaluate_point(k,q,current,channel=1,current_channel=1,lambda_radius=.5,lambda_remaining=1.,scenarios=None):
    start=time.perf_counter();q=np.asarray(q,float);v=k.vertices
    bound=float(np.max(np.linalg.norm(v-q,axis=1))) if len(v) else math.inf
    if bound>RECV_RADIUS-1e-7:
        return dict(position=q.tolist(),guaranteed_receive=False,receive_bound_m=bound if math.isfinite(bound) else None)
    if scenarios is None:
        scenarios=source_scenarios(k)
    worst=0.;remaining=0.;post_area=0.
    for x in scenarios:
        d=float(np.linalg.norm(x-q))
        if d<=5:
            worst=max(worst,5.)
            remaining=max(remaining,5.)
            continue
        angle=math.degrees(math.atan2(*(x-q)[::-1]))
        for error in (-1.,0.,1.):
            A,b=wedge(q,round(angle+error,2)%360,k.epsilon_deg)
            p=v.copy()
            for n,c in zip(A,b):
                p=clip(p,n,c+1e-7)
            if not len(p):
                continue
            center,r=mec(p)
            worst=max(worst,r)
            # 米/5转秒；清除覆盖数量仅是排序估计，不签发清除保证。
            count=max(1,math.ceil(r/19.98))
            rem=np.linalg.norm(center-q)/5+5+3*(count-1)
            remaining=max(remaining,float(rem))
            from shapely.geometry import MultiPoint
            post_area=max(post_area,MultiPoint(p).convex_hull.area)
    movement=float(np.linalg.norm(q-np.asarray(current)))
    score=movement/5+5+(channel!=current_channel)+lambda_radius*worst+lambda_remaining*remaining
    return dict(position=q.tolist(),guaranteed_receive=True,receive_bound_m=bound,
                receive_bound_kind='certified_upper_bound',posterior_radius_m=worst,
                posterior_kind='sampled_estimate',remaining_time_s=remaining,
                remaining_kind='sampled_estimate',posterior_area_m2=post_area,
                movement_m=movement,J_s=float(score),evaluation_s=time.perf_counter()-start)


def choose_second(k,current,channel=1,current_channel=1,coarse=64,top_k=8,refine=True):
    started=time.perf_counter();region=receive_region(k)
    if region.is_empty:
        return dict(status='RECOVERY_NO_GUARANTEED_CANDIDATE',best=None,candidates=[],elapsed_s=time.perf_counter()-started)
    xmin,ymin,xmax,ymax=region.bounds
    # 先从较密格点中抽取最多64个有效粗候选；接收保证最终由所有顶点复核。
    n=math.ceil(math.sqrt(coarse*4))
    grid=[(x,y) for x in np.linspace(xmin,xmax,n) for y in np.linspace(ymin,ymax,n) if region.covers(Point(x,y))]
    if len(grid)>coarse:
        grid=[grid[i] for i in np.linspace(0,len(grid)-1,coarse).astype(int)]
    grid.append(region.representative_point().coords[0])
    scenarios=source_scenarios(k)
    candidates=[evaluate_point(k,q,current,channel,current_channel,scenarios=scenarios) for q in grid]
    good=[c for c in candidates if c['guaranteed_receive']]
    good.sort(key=lambda c:c['J_s'])
    if refine:
        dx,dy=(xmax-xmin)/n,(ymax-ymin)/n
        for base in good[:top_k]:
            for ux in (-.5,0,.5):
                for uy in (-.5,0,.5):
                    if ux==uy==0:
                        continue
                    q=np.array(base['position'])+[ux*dx,uy*dy]
                    if region.covers(Point(q)):
                        c=evaluate_point(k,q,current,channel,current_channel,scenarios=scenarios)
                        candidates.append(c)
        good=sorted((c for c in candidates if c['guaranteed_receive']),key=lambda c:c['J_s'])
    return dict(status='OK' if good else 'RECOVERY_NO_GUARANTEED_CANDIDATE',
        best=good[0] if good else None,candidates=candidates,elapsed_s=time.perf_counter()-started,
        coarse_grid_spacing_m=[(xmax-xmin)/(n-1),(ymax-ymin)/(n-1)],
        high_quality_tolerance_s=10.,scenario_count=len(scenarios),error_scenarios_deg=[-1,0,1],
        lambda_radius_s_per_m=.5,lambda_remaining=1.,receive_polygon=vertices_of(region).tolist())


def q2_artifacts(input_path,output):
    from matplotlib import pyplot as plt
    inp=json.loads(Path(input_path).read_text());output=Path(output);output.mkdir(parents=True,exist_ok=True)
    k=FeasibleRegion(inp.get('epsilon_impl_deg',1.01));k.direction(inp['position'],inp['svd_deg'])
    result=choose_second(k,inp.get('current_position',inp['position']),inp.get('channel',1),inp.get('current_channel',1))
    a=math.radians(inp['svd_deg']);u=np.array([math.cos(a),math.sin(a)]);side=np.array([-u[1],u[0]])
    base=np.array(inp['position'])+750*u
    result['comparisons']={name:evaluate_point(k,q,inp['position']) for name,q in [('on_bearing',base),('fixed_flank',base+450*side)]}
    dump(output/'input.json',inp);dump(output/'result.json',result)
    dump(output/'provenance.json',hash_files(['src/solution/planning/q2.py','src/solution/geometry/core.py']))
    if result['best']:
        fig,axes=plt.subplots(1,2,figsize=(12,5))
        ax=axes[0];plot_polygon(ax,k.vertices,'Initial feasible envelope')
        plot_polygon(ax,result['receive_polygon'],'Guaranteed receive inner region',color='#4B9B76')
        cs=[c for c in result['candidates'] if c['guaranteed_receive']]
        xy=np.array([c['position'] for c in cs]);js=np.array([c['J_s'] for c in cs]);threshold=result['best']['J_s']+10
        scatter=ax.scatter(xy[:,0],xy[:,1],c=js,cmap='viridis',s=16)
        good=js<=threshold;ax.scatter(xy[good,0],xy[good,1],facecolors='none',edgecolors='red',s=48,label='J <= best + 10 s')
        ax.scatter(*result['best']['position'],marker='*',c='red',s=120,label='Best evaluated')
        fig.colorbar(scatter,ax=ax,label='Sampled J (s)');ax.legend(fontsize=7);ax.set_title('Explicit fixture; candidates, not global optimum')
        ax=axes[1];plot_polygon(ax,k.vertices,'Before')
        if 'posterior_fixture' in inp:
            from bsim.evaluation import create_fixture_session
            from bsim.reference import State
            session=create_fixture_session(inp['posterior_fixture'])
            q=result['best']['position'];obs=session.kernel.observe(State(),tuple(q),inp.get('channel',1))
            if obs['measure_result']=='direction':k.direction(q,obs['svd_deg'])
            elif obs['measure_result']=='near':k.near(q)
            dump(output/'posterior.json',dict(fixture=inp['posterior_fixture'],observation=obs,vertices=k.vertices.tolist()))
            plot_polygon(ax,k.vertices,'After fixture observation',color='#D65A31')
        ax.legend();ax.set_title('Posterior shown only for named fixture')
        fig.tight_layout();fig.savefig(output/'q2.png',dpi=170);fig.savefig(output/'q2.pdf');plt.close(fig)
    return {k:v for k,v in result.items() if k not in ('candidates','receive_polygon')}
