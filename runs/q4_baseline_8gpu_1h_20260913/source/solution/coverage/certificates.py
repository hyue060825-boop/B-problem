"""连续域覆盖；采样只能辅助验证，不能代替覆盖证明。"""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from solution.geometry.core import circle_polygon

@dataclass(frozen=True)
class OmniCertificate:
    radius_m: float
    station_radius_m: float
    max_distance_m: float
    margin_m: float
    certified: bool

def omni_skeleton(a_m=1135., safe_radius_m=999.98):
    if not 0 < safe_radius_m <= 1000 or not 0 < a_m < 1800:
        raise ValueError('invalid coverage parameter')
    points={'origin': (0.,0.)}
    points.update({f'v{k}':(a_m*math.cos(k*math.pi/3),a_m*math.sin(k*math.pi/3)) for k in range(6)})
    # 中心覆盖到safe_radius，外圈覆盖剩余环带；凸函数同时核验交接端点。
    bound=max(math.sqrt(r*r+a_m*a_m-2*r*a_m*math.cos(math.pi/6)) for r in (safe_radius_m,1800.))
    return points,OmniCertificate(1800.,a_m,bound,safe_radius_m-bound,bound<=safe_radius_m)

def check_omni_parameters(values=(1130.,1135.,1140.,1150.,1200.),safe_radius_m=999.98):
    result=[]
    for a in values:
        p,c=omni_skeleton(a,safe_radius_m)
        result.append(dict(a_m=a,points=p,max_distance_m=c.max_distance_m,margin_m=c.margin_m,certified=c.certified))
    return result

@lru_cache(maxsize=8)
def triangular_grid(spacing_m=995.,target_radius_m=1800.,margin_m=1e-6):
    if not 0 < spacing_m < 1000: raise ValueError('spacing must be below guaranteed reception radius')
    h=spacing_m*math.sqrt(3)/2
    def point(index):
        i,j=index
        return (spacing_m*(i+j/2),h*j)
    # 斜坐标i,j整数网格：两个三角形恰好铺满每个基本平行四边形。
    n=math.ceil(2*target_radius_m/spacing_m)+3
    cells=[];indices=set(); distances=[]
    for i in range(-n,n):
        for j in range(-n,n):
            for ids in (((i,j),(i+1,j),(i,j+1)),((i+1,j+1),(i,j+1),(i+1,j))):
                tri=tuple(point(v) for v in ids)
                d=Polygon(tri).distance(Point(0,0))
                if d <= target_radius_m+margin_m:
                    cells.append(tri);indices.update(ids);distances.append(d)
    # 重合源：保留圆内网格顶点的六个非重合相邻顶点，不依赖零向量可见性。
    neighbors=((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1))
    guards=[]
    for i,j in list(indices):
        if math.hypot(*point((i,j)))<=target_radius_m+margin_m:
            ring=[(i+di,j+dj) for di,dj in neighbors]
            indices.update(ring);guards.append(dict(vertex=point((i,j)),neighbors=[point(k) for k in ring]))
    v=sorted(point(k) for k in indices)
    union=unary_union([Polygon(t) for t in cells])
    # 外包圆多边形是额外连续域审计，证明主线仍是无限格铺砌和完整相交选取。
    covered=union.covers(circle_polygon((0,0),target_radius_m,n=512,outer=True))
    diameter_ok=all(max(math.dist(a,b) for a in t for b in t)<=spacing_m+margin_m for t in cells)
    return dict(spacing_m=spacing_m,target_radius_m=target_radius_m,vertices=v,triangles=cells,
                triangle_count=len(cells),vertex_count=len(v),diameter_checks=diameter_ok,
                continuous_domain_covered=covered,coincident_guards=guards,intersection_distances_m=distances,
                certificate='完整相交三角形铺砌圆域；凸组合闭半平面证明；重合处六非零邻点补证')

def verify_directional_certificate(grid):
    return bool(grid['diameter_checks'] and grid['continuous_domain_covered'] and grid['coincident_guards'] and grid['spacing_m']<1000)
