import math
import numpy as np
import pytest
from shapely.geometry import Point, Polygon
from solution.geometry.core import *

@pytest.mark.parametrize('theta',[0,359.99,180,90])
def test_forward_wedge(theta):
    A,b=wedge([0,0],theta,1)
    u=np.array([math.cos(math.radians(theta)),math.sin(math.radians(theta))])
    assert np.all(A@(100*u)<=b+1e-9)
    assert not np.all(A@(-100*u)<=b+1e-9)

def test_region_classification():
    A=np.array([[1,0],[-1,0],[0,1],[0,-1]])
    for b,kind in [([1,1,1,1],'polygon'),([0,0,1,1],'segment'),([0,0,0,0],'point'),([-1,0,1,1],'empty')]:
        assert halfplane_intersection(A,b)['kind']==kind
    assert halfplane_intersection([[1,0]],[1])['kind']=='unbounded'
    assert solve_q1([])['kind']=='unbounded'
    assert solve_q1([dict(position=[0,0],svd_deg=0)])['kind']=='unbounded'

def test_calipers_and_mec():
    rng=np.random.default_rng(22)
    for n in [3,4,10,50,100]:
        for _ in range(10):
            v=ordered_hull(rng.normal(size=(n,2)))
            assert abs(diameter(v)[0]-diameter_brute(v)[0])<1e-8
            c,r=mec(v)
            assert np.max(np.linalg.norm(v-c,axis=1))<=r+1e-9
            # 独立SLSQP求解凸minimax，与随机增量算法核对。
            from scipy.optimize import minimize
            res=minimize(lambda z:z[2],[*c,r+.1],constraints=[dict(type='ineq',fun=lambda z:z[2]-np.linalg.norm(v-z[:2],axis=1))],bounds=[(None,None),(None,None),(0,None)],method='SLSQP',options={'ftol':1e-10})
            assert abs(res.x[2]-r)<1e-5

def triangle_observations():
    v=np.array([[0.,0.],[40.,0.],[20.,20*math.sqrt(3)]])
    obs=[]
    for a,b in zip(v,np.roll(v,-1,axis=0)):
        u=(b-a)/40
        obs.append(dict(position=(a-1000*u).tolist(),svd_deg=(math.degrees(math.atan2(u[1],u[0]))+1)%360,epsilon_deg=1.))
    return obs

def test_actual_wedge_counterexample():
    r=solve_q1(triangle_observations())
    assert r['kind']=='polygon' and len(r['vertices'])==3
    assert abs(r['diameter_m']-40)<1e-7
    assert not r['diameter_circle_covers']
    assert abs(r['mec']['radius_m']-40/math.sqrt(3))<1e-7

def test_nonconvex_conservative_and_cover():
    k=FeasibleRegion(); k.geom=Polygon([(-30,-15),(30,-15),(30,15),(-30,15)])
    k.exclude((0,0),10)
    assert len(k.geom.interiors)==1
    cover=k.clear_cover()
    disks=[circle_polygon(q,CLEAR_RADIUS,n=512,outer=False) for q in cover]
    from shapely.ops import unary_union
    assert k.geom.difference(unary_union(disks)).area<1e-7
    assert k.geom.covers(Point(10.001,0))

def test_true_source_not_deleted():
    x=np.array([500,350])
    k=FeasibleRegion()
    for q in ([0,0],[0,1000],[1000,0]):
        angle=math.degrees(math.atan2(*(x-np.array(q))[::-1]))
        k.direction(q,round(angle+1,2)%360)
        assert k.geom.covers(Point(x))
    cert=k.certificate()
    assert cert['radius_upper_m']>=np.linalg.norm(x-np.array(cert['center']))

def test_safe_boundary():
    k=FeasibleRegion(); k.geom=Polygon([(-19.99,0),(0,0.1),(19.99,0)])
    assert not k.certificate()['safe']
    k.geom=Polygon([(-19.9,0),(0,0.1),(19.9,0)])
    q=k.safe_point((500,0))
    assert k.certificate(q)['safe']

def test_nearly_parallel_and_redundant():
    A=[[1,0],[-1,0],[0,1],[0,-1],[1,1e-10],[1,0]]
    r=halfplane_intersection(A,[1,1,1,1,1,2])
    assert r['kind']=='polygon'
