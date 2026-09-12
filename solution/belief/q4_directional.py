"""Public-history Q4 directional planning belief.

The belief is intentionally conservative and advisory. A no-signal observation
is represented as the disjunction of out-of-radius and directional back-side
explanations; it never mutates the certified feasible region.
"""
from dataclasses import dataclass
import math
import numpy as np
import torch


@dataclass(frozen=True)
class Hypothesis:
    position: tuple[float, float]
    radius: float
    kind: str
    heading: float | None


@dataclass(frozen=True)
class BeliefSummary:
    effective_hypotheses: int
    reception_probability: float
    entropy: float
    directional_fraction: float
    dispersion: float


def _visible(hypothesis, point):
    distance = math.dist(hypothesis.position, point)
    if distance > hypothesis.radius:
        return False
    if hypothesis.kind == "omni":
        return True
    dx, dy = point[0] - hypothesis.position[0], point[1] - hypothesis.position[1]
    theta = math.radians(float(hypothesis.heading))
    return math.cos(theta) * dx + math.sin(theta) * dy >= 0.0


class Q4DirectionalBelief:
    def __init__(self, hypotheses=()):
        self.hypotheses = tuple(hypotheses)

    @staticmethod
    def from_public_history(region_vertices, observations, *, seed=0, count=256):
        """Sample only public feasible geometry and observation constraints."""
        rng = np.random.default_rng(seed)
        vertices = np.asarray(region_vertices, dtype=float)
        if len(vertices) == 0:
            return Q4DirectionalBelief()
        lo, hi = vertices.min(axis=0), vertices.max(axis=0)
        candidates = []
        attempts = 0
        while len(candidates) < count and attempts < count * 30:
            attempts += 1
            p = rng.uniform(lo, hi)
            if not all(np.cross(vertices[(i + 1) % len(vertices)] - vertices[i], p - vertices[i]) >= -1e-6 for i in range(len(vertices))):
                continue
            radius = float(rng.uniform(1000., 1500.))
            kind = "directional" if bool(rng.integers(0, 2)) else "omni"
            heading = float(rng.uniform(0., 360.)) if kind == "directional" else None
            valid = True
            for obs in observations:
                visible = _visible(Hypothesis(tuple(p), radius, kind, heading), tuple(obs["position"]))
                result = obs["result"]
                if result in ("direction", "near") and not visible:
                    valid = False; break
                if result == "no_signal" and visible:
                    # The alternative remains explicit: no-signal may be due
                    # to out-of-radius OR to a directional back side.
                    if kind == "directional":
                        dx, dy = obs["position"][0] - p[0], obs["position"][1] - p[1]
                        theta = math.radians(float(heading))
                        back_side = math.cos(theta) * dx + math.sin(theta) * dy < 0
                        if not back_side: valid = False; break
                    else:
                        valid = False; break
            if valid: candidates.append(Hypothesis(tuple(map(float, p)), radius, kind, heading))
        return Q4DirectionalBelief(candidates)

    def summary_at(self, point, device=None):
        if not self.hypotheses:
            return BeliefSummary(0, 0.0, 0.0, 0.0, 0.0)
        reception = np.asarray([_visible(h, point) for h in self.hypotheses], dtype=float)
        p = float(reception.mean())
        entropy = 0.0 if p in (0.0, 1.0) else float(-(p * math.log(p) + (1 - p) * math.log(1 - p)))
        positions = np.asarray([h.position for h in self.hypotheses])
        dispersion = float(np.mean(np.linalg.norm(positions - positions.mean(axis=0), axis=1)))
        return BeliefSummary(len(self.hypotheses), p, entropy,
                             float(np.mean([h.kind == "directional" for h in self.hypotheses])), dispersion)

    def summary_many(self, points, device='cuda'):
        """Batch belief scoring on GPU; returns summaries in input order."""
        if not self.hypotheses:
            return [self.summary_at(p) for p in points]
        dev=torch.device(device if torch.cuda.is_available() else 'cpu')
        hp=torch.tensor([h.position for h in self.hypotheses],dtype=torch.float64,device=dev)
        rad=torch.tensor([h.radius for h in self.hypotheses],dtype=torch.float64,device=dev)
        kind=torch.tensor([h.kind == 'directional' for h in self.hypotheses],device=dev)
        heading=torch.tensor([math.radians(h.heading or 0.) for h in self.hypotheses],dtype=torch.float64,device=dev)
        pp=torch.tensor(points,dtype=torch.float64,device=dev)
        d=torch.linalg.vector_norm(pp[:,None,:]-hp[None,:,:],dim=-1)
        vis=d<=rad[None,:]
        dx=pp[:,None,0]-hp[None,:,0]; dy=pp[:,None,1]-hp[None,:,1]
        vis=vis & ((~kind)[None,:] | (torch.cos(heading)[None,:]*dx+torch.sin(heading)[None,:]*dy>=0))
        prob=vis.double().mean(1).cpu().numpy(); pos=hp.cpu().numpy()
        disp=float(np.mean(np.linalg.norm(pos-pos.mean(0),axis=1)))
        out=[]
        for p in prob:
            ent=0. if p in (0.,1.) else float(-(p*math.log(p)+(1-p)*math.log(1-p)))
            out.append(BeliefSummary(len(self.hypotheses),float(p),ent,float(kind.double().mean().cpu()),disp))
        return out

    def best_localize_points(self, candidates):
        summaries=self.summary_many(candidates)
        scored = [(s.entropy, tuple(point)) for s,point in zip(summaries,candidates)]
        return [point for _, point in sorted(scored, key=lambda item: (-item[0], item[1]))]
