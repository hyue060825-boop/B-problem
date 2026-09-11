import numpy as np
from shapely.geometry import Polygon
from solution.geometry.core import FeasibleRegion,RECV_RADIUS
from solution.planning.q2 import receive_region,choose_second,evaluate_point

def test_guaranteed_receipt():
    k=FeasibleRegion();k.direction([0,0],0)
    r=choose_second(k,[0,0],coarse=32,refine=False)
    assert r['status']=='OK'
    for c in r['candidates']:
        if c['guaranteed_receive']:
            assert np.max(np.linalg.norm(k.vertices-np.array(c['position']),axis=1))<=RECV_RADIUS
            assert c['posterior_kind']=='sampled_estimate'

def test_rotated_edge_and_wrap():
    for q,theta in [([1700,0],180),([0,1700],270),([0,0],359.995)]:
        k=FeasibleRegion();k.direction(q,theta)
        reg=receive_region(k)
        assert not reg.is_empty
        c=evaluate_point(k,reg.representative_point().coords[0],q)
        assert c['guaranteed_receive']

def test_empty_candidate_recovery():
    k=FeasibleRegion()
    assert choose_second(k,[0,0],coarse=32)['status']=='RECOVERY_NO_GUARANTEED_CANDIDATE'

def test_near_scenario():
    k=FeasibleRegion();k.geom=Polygon([(0,0),(1,0),(0,1)])
    r=evaluate_point(k,[0,0],[0,0],scenarios=np.array([[0,0]]))
    assert r['posterior_radius_m']==5 and np.isfinite(r['J_s'])
