"""float64 几何；证书保守裕量独立于物理阈值。"""
from collections import deque
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import linprog
from shapely.geometry import Polygon, MultiPoint, Point, GeometryCollection, box

EPS = 1e-8
CLEAR_RADIUS = 19.98
RECV_RADIUS = 999.98


def cross(a, b):
    return float(a[0]*b[1]-a[1]*b[0])


def wrap_to_180(deg):
    return (deg+180) % 360-180


def wedge(position, theta_deg, epsilon_deg=1.01):
    if not (0 < epsilon_deg < 90) or not np.isfinite([*position,theta_deg,epsilon_deg]).all():
        raise ValueError('角度或位置非法')
    lo, hi = np.radians([theta_deg-epsilon_deg,theta_deg+epsilon_deg])
    # n.x <= b：下界右侧法向、上界左侧法向。
    A=np.array([[math.sin(lo),-math.cos(lo)],[-math.sin(hi),math.cos(hi)]])
    return A, A@np.asarray(position,float)


def clip(vertices, n, b):
    """有限凸多边形增量裁剪；仅在有物理有限初域时使用。"""
    v=np.asarray(vertices,float).reshape(-1,2)
    if len(v)==0:
        return v
    out=[]
    for p,q in zip(v,np.roll(v,-1,axis=0)):
        fp,fq=float(n@p-b),float(n@q-b)
        if fp<=EPS:
            out.append(p)
        if (fp<=EPS)!=(fq<=EPS):
            t=fp/(fp-fq)
            out.append(p+t*(q-p))
    return np.asarray(out,float).reshape(-1,2)


def ordered_hull(points):
    p=np.asarray(points,float).reshape(-1,2)
    if not len(p):
        return p
    h=MultiPoint(p).convex_hull
    if h.geom_type=='Point':
        return np.array(h.coords)
    if h.geom_type=='LineString':
        return np.array(h.coords)
    v=np.array(h.exterior.coords[:-1])
    if sum(cross(a,b) for a,b in zip(v,np.roll(v,-1,axis=0)))<0:
        v=v[::-1]
    return v


def halfplane_intersection(A,b):
    """排序双端队列 O(n log n) 主路径，退化/近平行用LP诊断。

    LP只用于诊断及退化集合，不用任意大框替代无界区域。
    """
    A=np.asarray(A,float).reshape(-1,2); b=np.asarray(b,float)
    if len(A)==0:
        return dict(kind='unbounded',vertices=[],method='no_constraints')
    norms=np.linalg.norm(A,axis=1)
    if np.any(norms==0) or not np.isfinite(A).all() or not np.isfinite(b).all():
        raise ValueError('半平面输入非法')
    A,b=A/norms[:,None],b/norms
    # 可行性和四个极值的辅助LP，避免浮点近平行/零面积的错误分类。
    feasible=linprog([0.,0.],A_ub=A,b_ub=b,bounds=[(None,None)]*2,method='highs')
    if feasible.status==2:
        return dict(kind='empty',vertices=[],method='lp_diagnostic')
    if not feasible.success:
        raise ArithmeticError(feasible.message)
    extrema=[linprog(d,A_ub=A,b_ub=b,bounds=[(None,None)]*2,method='highs') for d in ([1,0],[-1,0],[0,1],[0,-1])]
    if any(r.status==3 for r in extrema):
        return dict(kind='unbounded',vertices=[],method='lp_diagnostic')
    if any(not r.success for r in extrema):
        raise ArithmeticError('LP极值诊断失败')
    order=np.argsort(np.mod(np.arctan2(A[:,1],A[:,0]),2*np.pi),kind='stable')
    lines=[]
    for i in order:
        if lines and abs(cross(lines[-1][0],A[i]))<1e-12 and lines[-1][0]@A[i]>0:
            if b[i]<lines[-1][1]:
                lines[-1]=(A[i],b[i])
        else:
            lines.append((A[i],b[i]))
    def meet(l1,l2):
        n1,c1=l1; n2,c2=l2
        det=cross(n1,n2)
        if abs(det)<1e-12:
            raise ArithmeticError('近平行')
        return np.array([(c1*n2[1]-n1[1]*c2)/det,(n1[0]*c2-c1*n2[0])/det])
    def outside(l,p):
        return l[0]@p>l[1]+EPS
    dq=deque()
    try:
        for l in lines:
            while len(dq)>1 and outside(l,meet(dq[-2],dq[-1])):
                dq.pop()
            while len(dq)>1 and outside(l,meet(dq[0],dq[1])):
                dq.popleft()
            dq.append(l)
        while len(dq)>2 and outside(dq[0],meet(dq[-2],dq[-1])):
            dq.pop()
        while len(dq)>2 and outside(dq[-1],meet(dq[0],dq[1])):
            dq.popleft()
        if len(dq)<3:
            raise ArithmeticError('退化')
        ls=list(dq)
        v=ordered_hull([meet(ls[i],ls[(i+1)%len(ls)]) for i in range(len(ls))])
        if np.max(A@v.T-b[:,None])>1e-6:
            raise ArithmeticError('残差过大')
        method='sorted_deque_with_lp_diagnostics'
    except ArithmeticError:
        # 有界性已由LP证明，极值构成的是数据导出的精确有限包络。
        xs=[r.x[0] for r in extrema]; ys=[r.x[1] for r in extrema]
        lo=np.array([min(xs),min(ys)]); hi=np.array([max(xs),max(ys)])
        v=np.array([lo,[hi[0],lo[1]],hi,[lo[0],hi[1]]])
        for n,c in zip(A,b):
            v=clip(v,n,c)
        v=ordered_hull(v)
        method='bounded_lp_degenerate_clip'
    if len(v)==0:
        return dict(kind='empty',vertices=[],method=method)
    if np.max(np.linalg.norm(v-v[0],axis=1))<=1e-7:
        v=v[:1]; kind='point'
    elif len(v)==2 or abs(sum(cross(a,z) for a,z in zip(v,np.roll(v,-1,axis=0))))<=1e-8:
        _,pair=diameter_brute(v); v=np.array(pair); kind='segment'
    else:
        kind='polygon'
    return dict(kind=kind,vertices=v.tolist(),method=method)


def diameter_brute(vertices):
    v=np.asarray(vertices,float)
    if not len(v):
        return None,None
    d=np.linalg.norm(v[:,None,:]-v[None,:,:],axis=2)
    i,j=np.unravel_index(np.argmax(d),d.shape)
    return float(d[i,j]),[v[i].tolist(),v[j].tolist()]


def diameter(vertices):
    v=np.asarray(vertices,float); n=len(v)
    if n<=2:
        return diameter_brute(v)
    best=(-1.,None); j=1
    def update(i,j,best):
        d=float(np.linalg.norm(v[i]-v[j]))
        return (d,[v[i].tolist(),v[j].tolist()]) if d>best[0] else best
    for i in range(n):
        nxt=(i+1)%n
        area=lambda k:abs(cross(v[nxt]-v[i],v[k%n]-v[i]))
        steps=0
        while area(j+1)>area(j)+1e-10 and steps<n:
            j=(j+1)%n; steps+=1
        best=update(i,j,best); best=update(nxt,j,best)
        if abs(area(j+1)-area(j))<=1e-10:
            best=update(i,(j+1)%n,best); best=update(nxt,(j+1)%n,best)
    return best


def mec(vertices):
    """随机增量最小包围圆；局部固定随机序不依赖环境真值。"""
    p=np.asarray(vertices,float).reshape(-1,2)
    if len(p)==0:
        raise ValueError('空区域没有清除证书')
    p=p[np.random.default_rng(20260911).permutation(len(p))]
    center=p[0].copy(); radius=0.
    for i,a in enumerate(p):
        if np.linalg.norm(a-center)<=radius+1e-9:
            continue
        center=a.copy();radius=0.
        for j,b in enumerate(p[:i]):
            if np.linalg.norm(b-center)<=radius+1e-9:
                continue
            center=(a+b)/2;radius=np.linalg.norm(a-b)/2
            for c in p[:j]:
                if np.linalg.norm(c-center)<=radius+1e-9:
                    continue
                mat=2*np.array([b-a,c-a]); rhs=np.array([b@b-a@a,c@c-a@a])
                if abs(np.linalg.det(mat))<1e-10:
                    _,pair=diameter_brute([a,b,c]); center=np.mean(pair,axis=0)
                else:
                    center=np.linalg.solve(mat,rhs)
                radius=max(np.linalg.norm(x-center) for x in (a,b,c))
    # 证书半径必须重新对全体顶点核验。
    return center,float(np.max(np.linalg.norm(p-center,axis=1)))


def circle_polygon(center,radius,n=256,outer=True):
    """外切正n边形/严格内缩内接正n边形。"""
    a=np.arange(n)*2*np.pi/n
    r=(radius+1e-7)/math.cos(math.pi/n) if outer else max(0.,radius-1e-7)
    return Polygon(np.asarray(center)+r*np.column_stack([np.cos(a),np.sin(a)]))


def vertices_of(geom):
    h=geom.convex_hull
    if h.is_empty:
        return np.empty((0,2))
    if h.geom_type=='Polygon':
        return ordered_hull(h.exterior.coords[:-1])
    return ordered_hull(h.coords)


class FeasibleRegion:
    def __init__(self, epsilon_deg=1.01):
        self.geom=circle_polygon((0,0),1800)
        self.epsilon_deg=epsilon_deg
        self.version=0

    def direction(self,q,theta):
        A,b=wedge(q,theta,self.epsilon_deg)
        for n,c in zip(A,b):
            v=np.array([[-4000,-4000],[4000,-4000],[4000,4000],[-4000,4000]])
            poly=clip(v,n,c+1e-7)
            self.geom=self.geom.intersection(Polygon(poly)) if len(poly)>=3 else GeometryCollection()
        self.geom=self.geom.intersection(circle_polygon(q,1500))
        self.geom=self.geom.difference(circle_polygon(q,5,outer=False))
        self.version+=1

    def near(self,q):
        self.geom=self.geom.intersection(circle_polygon(q,5))
        self.version+=1

    def exclude(self,q,radius):
        self.geom=self.geom.difference(circle_polygon(q,radius,outer=False))
        self.version+=1

    @property
    def vertices(self):
        return vertices_of(self.geom)

    def certificate(self,position=None,radius=CLEAR_RADIUS):
        v=self.vertices
        if not len(v):
            return None
        center,r=mec(v)
        if position is not None:
            center=np.asarray(position,float);r=float(np.max(np.linalg.norm(v-center,axis=1)))
        return dict(center=center.tolist(),radius_upper_m=r+1e-7,
                    safe=bool(r+1e-7<=radius),version=self.version)

    def safe_point(self,current,radius=CLEAR_RADIUS):
        cert=self.certificate(radius=radius)
        if cert is None or not cert['safe']:
            return None
        current=np.asarray(current,float); c=np.array(cert['center']); v=self.vertices
        if np.max(np.linalg.norm(v-current,axis=1))<=radius-1e-7:
            return current
        # MEC到当前位置线段上最远的安全点；是路线启发式，不声称欧式投影最优。
        lo,hi=0.,1.
        for _ in range(45):
            t=(lo+hi)/2; q=c+t*(current-c)
            if np.max(np.linalg.norm(v-q,axis=1))<=radius-1e-7:
                lo=t
            else:
                hi=t
        q=c+lo*(current-c)
        return q if self.certificate(q,radius)['safe'] else c

    def clear_cover(self,radius=CLEAR_RADIUS,max_cells=20000):
        """递归切分包围盒；每块完整矩形由其中心圆覆盖，覆盖内部和孔周围。

        同时尝试1/2/3条带分块，窄长定位区域通常只需少量圆。
        """
        if self.geom.is_empty:
            raise ValueError('空区域不可作为成功证书')
        v=self.vertices
        center,r=mec(v)
        if r<=radius-1e-7:
            return [center.tolist()]
        axis=int(np.ptp(v,axis=0).argmax())
        bounds=self.geom.bounds
        for n in (2,3):
            parts=[]
            edges=np.linspace(bounds[axis],bounds[axis+2],n+1)
            valid=True
            for a,b in zip(edges[:-1],edges[1:]):
                rect=box(a-1e-8,bounds[1]-1,b+1e-8,bounds[3]+1) if axis==0 else box(bounds[0]-1,a-1e-8,bounds[2]+1,b+1e-8)
                part=self.geom.intersection(rect)
                if part.is_empty:
                    continue
                c,r=mec(vertices_of(part))
                if r>radius-1e-6:
                    valid=False;break
                parts.append(c.tolist())
            if valid:
                return parts
        pending=[bounds]; points=[]
        while pending:
            xmin,ymin,xmax,ymax=pending.pop()
            if self.geom.disjoint(box(xmin,ymin,xmax,ymax)):
                continue
            if math.hypot(xmax-xmin,ymax-ymin)/2<=radius-1e-6:
                points.append([(xmin+xmax)/2,(ymin+ymax)/2])
                if len(points)>max_cells:
                    raise RuntimeError('clear cover预算超限')
            elif xmax-xmin>=ymax-ymin:
                m=(xmin+xmax)/2
                pending.extend([(xmin,ymin,m,ymax),(m,ymin,xmax,ymax)])
            else:
                m=(ymin+ymax)/2
                pending.extend([(xmin,ymin,xmax,m),(xmin,m,xmax,ymax)])
        return points


def solve_q1(observations):
    A=[]; b=[]
    for obs in observations:
        ai,bi=wedge(obs['position'],obs['svd_deg'],obs.get('epsilon_deg',1.))
        A.extend(ai); b.extend(bi)
    result=halfplane_intersection(A,b)
    if result['kind'] in ('empty','unbounded'):
        return dict(result,diameter_m=None,mec=None,diameter_circle_covers=None)
    v=result['vertices']; d,pair=diameter(v); center,r=mec(v)
    mid=np.mean(pair,axis=0)
    covered=bool(np.max(np.linalg.norm(np.asarray(v)-mid,axis=1))<=d/2+1e-7)
    return dict(result,diameter_m=d,farthest_pair=pair,diameter_circle_center=mid.tolist(),
                diameter_circle_covers=covered,mec=dict(center=center.tolist(),radius_m=r))
