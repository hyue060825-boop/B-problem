"""Weighted public-history Q4 planning belief.

This module is advisory. It never mutates feasible regions or issues CLEAR,
ABSENT, or EXIT certificates. Entropy below is explicitly the Bernoulli
entropy of a reception event, not full posterior entropy.
"""
from dataclasses import dataclass
import math

import numpy as np
try:
    import torch
except Exception:  # pragma: no cover - CPU-only deployment fallback
    torch = None


@dataclass(frozen=True)
class Hypothesis:
    position: tuple[float, float]
    radius: float
    kind: str
    heading: float | None
    weight: float = 1.0


@dataclass(frozen=True)
class BeliefSummary:
    valid: bool
    particle_count: int
    effective_sample_size: float
    age: int
    degenerate: bool
    reception_probability: float
    near_probability: float
    receive_entropy: float
    directional_fraction: float
    dispersion: float
    heading_sin: float
    heading_cos: float
    heading_concentration: float

    @property
    def effective_hypotheses(self):
        return self.particle_count

    @property
    def entropy(self):
        return self.receive_entropy


def _cross2(a, b):
    return float(a[0]*b[1] - a[1]*b[0])


def _inside_convex(vertices, point):
    signs = [_cross2(vertices[(i+1) % len(vertices)]-vertices[i], point-vertices[i])
             for i in range(len(vertices))]
    return min(signs) >= -1e-7 or max(signs) <= 1e-7


def _sample_convex_polygon(rng, vertices, count):
    """Uniform area samples from an ordered convex polygon, without bbox rejection."""
    triangles=np.stack([np.repeat(vertices[:1],len(vertices)-2,axis=0),vertices[1:-1],vertices[2:]],axis=1)
    ab=triangles[:,1]-triangles[:,0];ac=triangles[:,2]-triangles[:,0]
    twice_area=np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])
    if not np.isfinite(twice_area).all() or twice_area.sum()<=0:
        return np.empty((0,2),dtype=float)
    chosen=triangles[rng.choice(len(triangles),size=count,p=twice_area/twice_area.sum())]
    root=np.sqrt(rng.random(count));other=rng.random(count)
    return ((1-root)[:,None]*chosen[:,0]+(root*(1-other))[:,None]*chosen[:,1]+
            (root*other)[:,None]*chosen[:,2])


def _unit(heading):
    cardinal = {0.0:(1.,0.),90.0:(0.,1.),180.0:(-1.,0.),270.0:(0.,-1.)}
    key = float(heading) % 360
    if key in cardinal:
        return cardinal[key]
    angle = math.radians(key)
    return math.cos(angle), math.sin(angle)


def _visible(hypothesis, point, *, overlap='invisible', boundary_epsilon=0.):
    distance = math.dist(hypothesis.position, point)
    if distance > hypothesis.radius:
        return False
    if hypothesis.kind == 'omni':
        return True
    dx, dy = point[0]-hypothesis.position[0], point[1]-hypothesis.position[1]
    if dx == 0 and dy == 0:
        return overlap == 'visible'
    ux,uy = _unit(hypothesis.heading)
    return ux*dx + uy*dy >= -boundary_epsilon


def _consistent(hypothesis, observation):
    point = tuple(observation['position'])
    visible = _visible(hypothesis, point)
    result = observation['result']
    if result == 'no_signal':
        return not visible
    if not visible:
        return False
    distance = math.dist(hypothesis.position, point)
    if result == 'near':
        return distance <= 5.
    if result == 'direction':
        if distance <= 5.:
            return False
        predicted = math.degrees(math.atan2(hypothesis.position[1]-point[1],
                                             hypothesis.position[0]-point[0])) % 360
        observed = float(observation['svd_deg']) % 360
        delta = abs((predicted-observed+180) % 360-180)
        # The research field is fixed but only bounded in [-1,1]. This is a
        # compatibility likelihood, not an independent-noise assumption.
        return delta <= 1.011
    return True


class Q4DirectionalBelief:
    def __init__(self, hypotheses=(), *, age=0, requested_count=128):
        self.hypotheses = tuple(hypotheses)
        self.age = int(age)
        self.requested_count = int(requested_count)
        raw = np.asarray([max(0.,h.weight) for h in self.hypotheses], dtype=float)
        self.weights = raw/raw.sum() if raw.size and raw.sum() else np.zeros(raw.shape)

    @staticmethod
    def from_public_history(region_vertices, observations, *, seed=0, count=128,
                            source_domain_radius=1800., initial=()):
        rng = np.random.default_rng(seed)
        vertices = np.asarray(region_vertices, dtype=float)
        if len(vertices) < 3:
            return Q4DirectionalBelief(age=len(observations),requested_count=count)
        candidates=[h for h in initial if np.dot(h.position,h.position)<=source_domain_radius**2
                    and _inside_convex(vertices,np.asarray(h.position))
                    and all(_consistent(h,obs) for obs in observations)]
        candidates=candidates[:count];attempts=0
        while len(candidates)<count and attempts<24:
            attempts += 1
            batch=max(256,4*(count-len(candidates)))
            for p in _sample_convex_polygon(rng,vertices,batch):
                if np.dot(p,p)>source_domain_radius**2:continue
                radius=float(rng.uniform(1000.,1500.));kind='directional' if bool(rng.integers(0,2)) else 'omni'
                heading=float(rng.uniform(0.,360.)) if kind=='directional' else None
                h=Hypothesis(tuple(map(float,p)),radius,kind,heading)
                if all(_consistent(h,obs) for obs in observations):candidates.append(h)
                if len(candidates)>=count:break
        return Q4DirectionalBelief(candidates,age=len(observations),requested_count=count)

    def _summary(self, reception, near):
        if not self.hypotheses:
            return BeliefSummary(False,0,0.,self.age,True,0.,0.,0.,0.,0.,0.,0.,0.)
        w=self.weights
        p=float(np.clip(w@np.asarray(reception,float),0.,1.));pn=float(np.clip(w@np.asarray(near,float),0.,1.))
        entropy=0. if p in (0.,1.) else float(-(p*math.log(p)+(1-p)*math.log(1-p)))
        positions=np.asarray([h.position for h in self.hypotheses])
        center=(positions*w[:,None]).sum(0)
        dispersion=float(w@np.linalg.norm(positions-center,axis=1))
        directional=np.asarray([h.kind=='directional' for h in self.hypotheses],float)
        angles=np.asarray([math.radians(h.heading or 0.) for h in self.hypotheses])
        dw=w*directional; mass=dw.sum()
        hs=float(dw@np.sin(angles)/mass) if mass else 0.; hc=float(dw@np.cos(angles)/mass) if mass else 0.
        ess=float(1/(w@w)); valid=len(w)>=max(8,min(32,self.requested_count//4))
        return BeliefSummary(valid,len(w),ess,self.age,not valid,p,pn,entropy,
                             float(w@directional),dispersion,hs,hc,math.hypot(hs,hc))

    def summary_at(self, point, device=None):
        reception=[_visible(h,point) for h in self.hypotheses]
        near=[math.dist(h.position,point)<=20. for h in self.hypotheses]
        return self._summary(reception,near)

    def summary_many(self, points, device='cpu'):
        # Small online candidate sets are faster through the NumPy reference.
        # Batched training services can explicitly request a CUDA device.
        if torch is None or device == 'cpu' or not self.hypotheses:
            return [self.summary_at(p) for p in points]
        dev=torch.device(device if torch.cuda.is_available() else 'cpu')
        hp=torch.tensor([h.position for h in self.hypotheses],dtype=torch.float64,device=dev)
        rad=torch.tensor([h.radius for h in self.hypotheses],dtype=torch.float64,device=dev)
        kind=torch.tensor([h.kind=='directional' for h in self.hypotheses],device=dev)
        heading=torch.tensor([math.radians(h.heading or 0.) for h in self.hypotheses],dtype=torch.float64,device=dev)
        pp=torch.as_tensor(points,dtype=torch.float64,device=dev)
        delta=pp[:,None,:]-hp[None,:,:];d=torch.linalg.vector_norm(delta,dim=-1)
        dot=torch.cos(heading)[None,:]*delta[:,:,0]+torch.sin(heading)[None,:]*delta[:,:,1]
        overlap=(delta[:,:,0]==0)&(delta[:,:,1]==0)
        vis=(d<=rad[None,:])&((~kind)[None,:]|((dot>=0)&~overlap))
        near=d<=20.
        return [self._summary(v,n) for v,n in zip(vis.cpu().numpy(),near.cpu().numpy())]

    def best_localize_points(self,candidates):
        summaries=self.summary_many(candidates)
        scored=[((s.receive_entropy+0.25*s.reception_probability)/(1+s.dispersion/1000),tuple(p))
                for s,p in zip(summaries,candidates)]
        return [p for _,p in sorted(scored,key=lambda item:(-item[0],item[1]))]

    def probe_scores(self,points,bandwidth=60.):
        """Weighted particle-kernel score for ordering probe candidates."""
        if not self.hypotheses:return np.zeros(len(points),dtype=float)
        p=np.asarray(points,float);h=np.asarray([x.position for x in self.hypotheses])
        squared=((p[:,None,:]-h[None,:,:])**2).sum(-1)
        return np.exp(-squared/(2*bandwidth**2))@self.weights
