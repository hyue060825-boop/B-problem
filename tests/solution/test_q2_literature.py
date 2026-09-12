"""LIT-Q2-01：一致观测、几何保证、实际计费与边界验证。"""
import importlib.util
import json
from pathlib import Path
import math
import numpy as np
from shapely.geometry import Point
from bsim.evaluation import create_fixture_session
from bsim.reference import State
from solution.geometry.core import FeasibleRegion, RECV_RADIUS

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('q2_lit_test',ROOT/'scripts/experiment_q2_literature.py')
lit=importlib.util.module_from_spec(spec);spec.loader.exec_module(lit)
CFG=json.loads((ROOT/'experiments/q2/lit_q2_01.json').read_text())


def test_fixture_first_and_second_observations_agree_with_truth():
    session=create_fixture_session(ROOT/'tests/fixtures/solution/q2_source_lit.json')
    inp=json.loads((ROOT/'tests/fixtures/solution/q2_example_lit.json').read_text())
    first=session.kernel.observe(State(),tuple(inp['position']),1)
    assert first['svd_deg']==inp['svd_deg']
    k=FeasibleRegion();k.direction(inp['position'],first['svd_deg'])
    best,_,_=lit.select(k,inp['position'],first['svd_deg'],'shape',CFG)
    q=best['position'];obs=session.kernel.observe(State(),tuple(q),1)
    k.direction(q,obs['svd_deg'])
    assert k.geom.covers(Point(900,30))


def test_shape_candidates_receive_whole_envelope_and_rotation():
    for pos,theta in [([0,0],0),([1700,0],180),([0,0],359.99)]:
        k=FeasibleRegion();k.direction(pos,theta)
        candidates=lit.shape_points(k,CFG)
        assert candidates
        assert all(np.max(np.linalg.norm(k.vertices-q,axis=1))<=RECV_RADIUS+1e-6 for q in candidates)


def test_paired_actual_rollout_costs_and_fixed_field():
    case=lit.make_case(419001,15)  # 平滑场，与正式评估种子分离。
    kernel=lit.kernel_for(case)
    assert kernel.noise.error(1,12.3,45.6)==kernel.noise.error(1,12.3,45.6)
    records=[lit.run_method(case,m,CFG) for m in ['fixed_flank','shape']]
    assert records[0]['trace'][0]==records[1]['trace'][0]
    for record in records:
        r=record['metrics'];trace=record['trace'];pos=case['start'];cost=0
        for step in trace:
            cost+=math.dist(pos,step['position'])/5
            cost+=5 if step['path']=='/measure' or step['response'].get('clear_result')=='success' else 3
            pos=step['position']
        assert abs(cost-r['total_virtual_s'])<len(trace)*1e-6
        assert r['posterior_contains_truth'] and r['completed']
        assert trace[-1]['response']['clear_result']=='success'


def test_near_clear_and_receive_thresholds():
    kernel=lit.kernel_for(dict(seed=1,source=[0.,0.],radius=1000.,field='zero'))
    assert kernel.observe(State(),(5.,0.),1)['measure_result']=='near'
    assert kernel.observe(State(),(5.0001,0.),1)['measure_result']=='direction'
    assert kernel.observe(State(),(1000.,0.),1)['measure_result']=='direction'
    assert kernel.observe(State(),(1000.0001,0.),1)['measure_result']=='no_signal'
    assert kernel.transition(State(),'/clear',(20.,0.),1)[1]['clear_result']=='success'
    assert kernel.transition(State(),'/clear',(20.0001,0.),1)[1]['clear_result']=='no_target_in_range'


def test_empty_shape_candidates_explicit_recovery():
    from shapely.geometry import GeometryCollection
    k=FeasibleRegion();k.geom=GeometryCollection()
    best,n,_=lit.select(k,[0,0],0,'shape',CFG)
    assert best is None and n==0
