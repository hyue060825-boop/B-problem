"""Immutable, replayable certified-clear probe plans."""
from dataclasses import dataclass
import hashlib
import json
import math

from solution.planning.route import plan_open_route


PROBE_PLAN_VERSION = "certified-probe-plan-v1"


@dataclass(frozen=True)
class ProbePlan:
    channel: int
    points: tuple[tuple[float, float], ...]
    estimated_move_s: float
    worst_case_clear_s: float
    version: str
    plan_id: str

    @property
    def first_point(self):
        return self.points[0]


def build_probe_plan(channel, region, current):
    raw = tuple(tuple(map(float, point)) for point in region.clear_cover())
    if not raw:
        raise RuntimeError("certified clear cover is empty")
    route = plan_open_route(current, raw, max_ms=10.0)
    points = tuple(raw[i] for i in route.ordered_ids)
    payload = {
        "channel": int(channel),
        "points": [[round(x, 9), round(y, 9)] for x, y in points],
        "region_version": int(region.version),
        "version": PROBE_PLAN_VERSION,
    }
    plan_id = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    move_s = route.length_m / 5.0
    # Failed clears cost 3 s and the final successful clear costs 5 s.
    worst = move_s + 3.0 * max(0, len(points) - 1) + 5.0
    return ProbePlan(int(channel), points, move_s, worst, PROBE_PLAN_VERSION, plan_id)


def plan_route_matches(plan, calls):
    actual = tuple(tuple(map(float, row["position"])) for row in calls)
    return actual == plan.points[:len(actual)]


def reorder_probe_plan(plan,current,first_index):
    """Return the same finite cover with a public-heuristic first point."""
    if not 0<=first_index<len(plan.points):raise IndexError(first_index)
    first=plan.points[first_index]
    remaining=plan.points[:first_index]+plan.points[first_index+1:]
    route=plan_open_route(first,remaining,max_ms=3.0)
    points=(first,)+tuple(remaining[i] for i in route.ordered_ids)
    payload={'channel':plan.channel,'points':[[round(x,9),round(y,9)] for x,y in points],
             'parent_plan_id':plan.plan_id,'version':PROBE_PLAN_VERSION}
    plan_id=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    move_s=math.dist(current,first)/5+route.length_m/5
    return ProbePlan(plan.channel,points,move_s,move_s+3*max(0,len(points)-1)+5,
                     PROBE_PLAN_VERSION,plan_id)
