#!/usr/bin/env python3
"""LIT-Q2-01：四种选点方法的配对观测与统一后续清除实验。"""
import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from shapely.geometry import Point
from shapely.ops import nearest_points
from bsim.noise import FixtureNoise, Numerics
from bsim.research import FixedField
from bsim.reference import ReferenceKernel, State
from bsim.scenarios import Scenario, Source
from solution.geometry.core import FeasibleRegion, RECV_RADIUS, diameter, mec
from solution.planning.q2 import choose_second, evaluate_point, receive_region, source_scenarios

METHODS = ['on_bearing', 'fixed_flank', 'current', 'shape']


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader(); w.writerows(rows)


def make_case(seed, index):
    """五类几何×四类误差，每20局一轮；显式与官方分布分开。"""
    rng = np.random.default_rng(seed)
    group = ['center', 'edge', 'rotated', 'wrap', 'short_range'][index % 5]
    field = ['zero', 'positive', 'negative', 'smooth'][(index // 5) % 4]
    radius = [1000., 1250., 1500.][(index // 20) % 3]
    if group == 'edge':
        ang = float(rng.uniform(0, 2*math.pi))
        source = np.array([math.cos(ang), math.sin(ang)]) * float(rng.uniform(1720, 1799))
        start = source * float(rng.uniform(.22, .55))
        if np.linalg.norm(source-start) > radius:
            start = source - (source-start)/np.linalg.norm(source-start)*(radius-1.)
    else:
        start = np.zeros(2) if group in ('center', 'wrap') else rng.uniform(-300, 300, 2)
        angle = float(rng.uniform(-.15, .15)) if group == 'wrap' else float(rng.uniform(0, 360))
        dist = float(rng.uniform(8, 80)) if group == 'short_range' else float(rng.uniform(400, radius-1))
        source = start + dist*np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
    return dict(seed=seed, group=group, field=field, source=source.tolist(), start=start.tolist(), radius=radius)


def kernel_for(case):
    source = Source(1, *case['source'], case['radius'], 'omni')
    scene = Scenario(f"LOCAL-Q2-LIT-{case['seed']}", 3, 'test_fixture', (source,))
    noise = FixedField(case['seed']+917, 'smooth') if case['field'] == 'smooth' else FixtureNoise(
        dict(label='TEST_INPUT', kind='constant', value={'zero': 0., 'positive': 1., 'negative': -1.}[case['field']]))
    return ReferenceKernel(scene, noise, Numerics('TEST_INPUT', 'half_up', 'half_up', 'invisible', 0.))


def shape_points(k, cfg):
    """仅使用公开可行域，沿直径垂向与少量纵向偏移生成候选。"""
    region = receive_region(k)
    if region.is_empty:
        return []
    center, radius = mec(k.vertices)
    length, pair = diameter(k.vertices)
    axis = (np.asarray(pair[1])-pair[0])/length if length > 1e-9 else np.array([1., 0.])
    side = np.array([-axis[1], axis[0]])
    candidates = [np.array(region.representative_point().coords[0])]
    for scale in cfg['shape_radii']:
        for offset in cfg['shape_longitudinal_offsets']:
            for sign in (-1, 1):
                q = center + max(radius, 5.)*(offset*axis+sign*scale*side)
                if not region.covers(Point(q)):
                    q = np.array(nearest_points(region, Point(q))[0].coords[0])
                candidates.append(q)
    return list({tuple(np.round(q, 8)): q for q in candidates}.values())


def select(k, current, theta, method, cfg):
    """选点接口不接受场景、源坐标、误差场或模拟器对象。"""
    started = time.perf_counter()
    if method == 'current':
        result = choose_second(k, current)
        best = result['best']; count = len(result['candidates'])
    elif method == 'shape':
        points = shape_points(k, cfg)
        scenarios = source_scenarios(k)
        scores = [evaluate_point(k, q, current, scenarios=scenarios,
                                 lambda_radius=cfg['lambda_radius'], lambda_remaining=cfg['lambda_remaining'])
                  for q in points]
        valid = [s for s in scores if s['guaranteed_receive']]
        best = min(valid, key=lambda s:s['J_s']) if valid else None
        count = len(scores)
    else:
        ang = math.radians(theta); u = np.array([math.cos(ang), math.sin(ang)])
        q = np.asarray(current)+750*u
        if method == 'fixed_flank': q += 450*np.array([-u[1], u[0]])
        best = evaluate_point(k, q, current); count = 1
    return best, count, time.perf_counter()-started


def run_method(case, method, cfg):
    kernel = kernel_for(case)
    # Q2以已处于首检测点为起点；不加入Q3从原点到首点的搜索成本。
    state = State(position=tuple(case['start']))
    trace = []
    def request(path, q):
        nonlocal state
        previous = state.virtual_us
        state, response = kernel.transition(state, path, tuple(float(x) for x in q), 1)
        trace.append(dict(path=path, position=list(q), channel=1, response=response,
                          delta_s=(state.virtual_us-previous)/1e6, virtual_s=state.virtual_us/1e6))
        return response
    first = request('/measure', case['start'])
    assert first['measure_result'] == 'direction', case
    k = FeasibleRegion(cfg['epsilon_deg']); k.direction(case['start'], first['svd_deg'])
    assert k.geom.buffer(1e-6).covers(Point(case['source']))
    initial_vertices = k.vertices.tolist()
    best, count, select_s = select(k, case['start'], first['svd_deg'], method, cfg)
    row = dict(seed=case['seed'], group=case['group'], field=case['field'], radius=case['radius'], method=method,
               available=best is not None, guaranteed_receive=False, second_received=False,
               posterior_contains_truth=False, posterior_radius_m=None, posterior_diameter_m=None,
               posterior_area_m2=None, clear_ready=False, second_action_s=None, predicted_radius_m=None,
               predicted_J_s=None, selection_s=select_s, evaluated_candidates=count, completed=False,
               total_virtual_s=state.virtual_us/1e6, measures=1, clear_attempts=0, error=None)
    posterior_vertices = None
    if best is None:
        row['error'] = 'no_candidate'
    else:
        q = best['position']; row['guaranteed_receive'] = best['guaranteed_receive']
        row['predicted_radius_m'] = best.get('posterior_radius_m'); row['predicted_J_s'] = best.get('J_s')
        obs = request('/measure', q); row['second_action_s'] = trace[-1]['delta_s']
        theta = first['svd_deg']
        if obs['measure_result'] == 'direction':
            k.direction(q, obs['svd_deg']); theta = obs['svd_deg']
        elif obs['measure_result'] == 'near':
            k.near(q)
        else:
            # 非保证基线可能无信号；全向场景可排除1000 m内区。
            k.exclude(q, RECV_RADIUS)
        row['second_received'] = obs['measure_result'] != 'no_signal'
        row['posterior_contains_truth'] = k.geom.buffer(1e-6).covers(Point(case['source']))
        if not row['posterior_contains_truth'] or k.geom.is_empty:
            raise AssertionError(('invalid_posterior', case, method))
        center, radius = mec(k.vertices)
        row.update(posterior_radius_m=radius, posterior_diameter_m=diameter(k.vertices)[0],
                   posterior_area_m2=k.geom.area, clear_ready=k.certificate()['safe'])
        posterior_vertices = k.vertices.tolist()
        # 统一延续规则：至多3次近侧翼补测；方向来自最后一次公开测向。
        for _ in range(cfg['continuation_measurements']):
            if k.certificate()['safe']: break
            center, radius = mec(k.vertices)
            a = math.radians(theta); side = np.array([-math.sin(a), math.cos(a)])
            options = [center+sign*min(350., max(30., radius*.45))*side for sign in (-1, 1)]
            pos = min(options, key=lambda x:np.linalg.norm(x-state.position))
            obs = request('/measure', pos)
            if obs['measure_result'] == 'direction':
                k.direction(pos, obs['svd_deg']); theta = obs['svd_deg']
            elif obs['measure_result'] == 'near': k.near(pos)
            else: k.exclude(pos, RECV_RADIUS)
            if k.geom.is_empty or not k.geom.buffer(1e-6).covers(Point(case['source'])):
                raise AssertionError(('invalid_continuation', case, method))
        # 分块覆盖一次生成，失败继续下一点；不读取真值选择清除位置。
        points = k.clear_cover()
        for _ in range(cfg['max_clear_attempts']):
            if not points: break
            idx = min(range(len(points)), key=lambda i:math.dist(state.position, points[i]))
            if request('/clear', points.pop(idx))['clear_result'] == 'success':
                row['completed'] = True; break
        if not row['completed']: row['error'] = 'clear_budget_or_cover_exhausted'
    row.update(total_virtual_s=state.virtual_us/1e6, measures=sum(t['path']=='/measure' for t in trace),
               clear_attempts=sum(t['path']=='/clear' for t in trace))
    assert row['completed'] == (1 in state.cleared)
    return dict(metrics=row, case=case, initial=initial_vertices, posterior=posterior_vertices, selection=best, trace=trace)


def episode(job):
    case, cfg, methods = job
    return [run_method(case, method, cfg) for method in methods]


def summarize(records):
    rows = [r['metrics'] for r in records]
    summary = []
    for method in dict.fromkeys(r['method'] for r in rows):
        rs = [r for r in rows if r['method']==method]
        valid = [r for r in rs if r['posterior_radius_m'] is not None]
        s = dict(method=method, episodes=len(rs), available=sum(r['available'] for r in rs),
                 guaranteed=sum(r['guaranteed_receive'] for r in rs), received=sum(r['second_received'] for r in rs),
                 contains_truth=sum(r['posterior_contains_truth'] for r in rs),
                 clear_ready=sum(r['clear_ready'] for r in rs), completed=sum(r['completed'] for r in rs))
        for key in ('posterior_radius_m', 'second_action_s', 'total_virtual_s', 'selection_s', 'measures', 'clear_attempts', 'evaluated_candidates'):
            vals = [r[key] for r in rs if r[key] is not None]
            s['mean_'+key] = float(np.mean(vals)) if vals else None
        s['p95_total_virtual_s'] = float(np.percentile([r['total_virtual_s'] for r in rs],95))
        summary.append(s)
    paired=[]
    base={r['seed']:r for r in rows if r['method']=='current'}
    for method in METHODS:
        if method=='current' or not base: continue
        rs=[r for r in rows if r['method']==method]
        if not rs: continue
        for key in ('posterior_radius_m','total_virtual_s'):
            deltas=np.array([r[key]-base[r['seed']][key] for r in rs if r[key] is not None and base[r['seed']][key] is not None])
            paired.append(dict(method=method, metric=key, pairs=len(deltas), mean_delta=float(deltas.mean()),
                               ci95_halfwidth=float(1.96*deltas.std(ddof=1)/math.sqrt(len(deltas))) if len(deltas)>1 else None,
                               better=int(sum(deltas < -1e-7)), equal=int(sum(abs(deltas)<=1e-7)), worse=int(sum(deltas>1e-7))))
    return summary, paired


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='experiments/q2/lit_q2_01.json')
    parser.add_argument('--phase',choices=['pilot','evaluation','sensitivity'],required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args(); cfg=json.loads(Path(args.config).read_text())
    out=Path(args.output); out.mkdir(parents=True,exist_ok=False)
    phase=cfg[args.phase]
    cases=[make_case(phase['seed']+i,i) for i in range(phase['episodes'])]
    dump(out/'cases.json',cases); dump(out/'config.json',cfg)
    paths=[Path(__file__).relative_to(ROOT).as_posix(),args.config]+[p.relative_to(ROOT).as_posix() for p in (ROOT/'src').rglob('*.py')]
    manifest=dict(batch=cfg['batch'],phase=args.phase,base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  command=sys.argv,python=platform.python_version(),numpy=np.__version__,workers=args.workers,
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                  semantics='初始位置为首检测点；总虚拟时间含首测5秒；选点计算墙钟另报；ReferenceKernel进程内物理实验，不检验HTTP或现实截止',
                  design='评估配置在pilot后冻结；独立sensitivity不用于回选评估结果；CI为研究样本配对均值的近似区间')
    dump(out/'manifest.json',manifest)
    started=time.perf_counter(); records=[]
    if args.phase=='sensitivity':
        for density in cfg['sensitivity_densities']:
            for weight in cfg['sensitivity_weights']:
                variant=dict(cfg,shape_radii=np.linspace(.15,1.,density).tolist(),lambda_radius=weight)
                for case in cases:
                    r=run_method(case,'shape',variant)
                    r['metrics']['density']=density; r['metrics']['weight']=weight
                    records.append(r)
                print(f'density={density} weight={weight} complete',flush=True)
    else:
        jobs=[(c,cfg,cfg['methods']) for c in cases]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, result in enumerate(pool.map(episode,jobs),1):
                records.extend(result)
                if i%5==0 or i==len(cases): print(f'{args.phase} {i}/{len(cases)} elapsed={time.perf_counter()-started:.1f}s',flush=True)
    dump(out/'records.json',records)
    write_csv(out/'samples.csv',[r['metrics'] for r in records])
    summary,paired=summarize(records)
    dump(out/'summary.json',dict(methods=summary,paired=paired,elapsed_s=time.perf_counter()-started))
    if args.phase=='sensitivity':
        groups=[]
        for density in cfg['sensitivity_densities']:
            for weight in cfg['sensitivity_weights']:
                part=[r for r in records if r['metrics']['density']==density and r['metrics']['weight']==weight]
                s,_=summarize(part);groups.append(dict(density=density,weight=weight,**s[0]))
        write_csv(out/'sensitivity.csv',groups)
    dump(out/'outputs.sha256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps(dict(status='COMPLETE',records=len(records),elapsed_s=time.perf_counter()-started)))


if __name__=='__main__':main()
