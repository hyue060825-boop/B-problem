"""Deterministic open-route planning using public task points only."""
from dataclasses import dataclass
import math
import time


@dataclass(frozen=True)
class OpenRoute:
    ordered_ids: tuple[int, ...]
    length_m: float
    next_id: int | None
    nearest_lower_bound_m: float
    compute_ms: float


def route_length(current, order, points):
    total = 0.0
    position = tuple(current)
    for index in order:
        total += math.dist(position, points[index])
        position = points[index]
    return total


def _nearest_order(current, points, ids, first, deadline=math.inf):
    remaining = set(ids)
    order = []
    position = tuple(current)
    if first is not None:
        order.append(first)
        remaining.remove(first)
        position = points[first]
    while remaining:
        if time.perf_counter() >= deadline:
            return order + sorted(remaining)
        best = None
        for count, i in enumerate(remaining):
            if count % 64 == 0 and time.perf_counter() >= deadline:
                return order + sorted(remaining)
            key = (math.dist(position, points[i]), i)
            if best is None or key < best:
                best = key
        chosen = best[1]
        order.append(chosen)
        remaining.remove(chosen)
        position = points[chosen]
    return order


def _open_two_opt(current, order, points, *, deadline=math.inf,
                  max_passes=4, max_checks=20000, max_reversals=64):
    """Bounded open-path 2-opt; score a reversal from boundary edges only.

    Fixed pass/reversal caps bound work even without a wall-clock deadline.
    Each trial is O(1); only accepted reversals copy their segment.
    """
    order = list(order)
    checks = reversals = 0
    for _ in range(max_passes):
        improved = False
        for left in range(len(order) - 1):
            for right in range(left + 1, len(order)):
                if (checks >= max_checks or reversals >= max_reversals
                        or time.perf_counter() >= deadline):
                    return order
                checks += 1
                previous = current if left == 0 else points[order[left - 1]]
                a, b = points[order[left]], points[order[right]]
                delta = math.dist(previous, b) - math.dist(previous, a)
                # This is an open path: the last point has no return edge.
                if right + 1 < len(order):
                    following = points[order[right + 1]]
                    delta += math.dist(a, following) - math.dist(b, following)
                if delta < -1e-9:
                    order[left:right + 1] = reversed(order[left:right + 1])
                    reversals += 1
                    improved = True
        if not improved:
            break
    return order


def plan_open_route(current, points, mask=None, *, max_ms=20.0):
    """Budgeted heuristic open path; ``mask`` means task remains.

    The deadline bounds optional search, including nearest-neighbor scans.
    On expiry we still materialize and measure a complete route (O(n log n)
    at worst); this is not a hard real-time guarantee under OS scheduling.
    """
    started = time.perf_counter()
    if not math.isfinite(max_ms) or max_ms < 0:
        raise ValueError('max_ms must be finite and nonnegative')
    deadline = started + max_ms / 1000.
    if mask is None:
        ids = tuple(range(len(points)))
    else:
        if len(mask) != len(points):
            raise ValueError("route mask length mismatch")
        ids = tuple(i for i, required in enumerate(mask) if required)
    if not ids:
        return OpenRoute((), 0.0, None, 0.0, (time.perf_counter() - started) * 1000)
    nearest = min(math.dist(current, points[i]) for i in ids)
    starts = sorted(ids, key=lambda i: (math.dist(current, points[i]), i))
    # Always retain a complete fallback; even a zero budget cannot drop tasks.
    best = ((route_length(current, starts, points), tuple(starts)), starts)
    for first in starts[:4]:
        if time.perf_counter() >= deadline:
            break
        order = _nearest_order(current, points, ids, first, deadline)
        order = _open_two_opt(current, order, points, deadline=deadline)
        key = (route_length(current, order, points), tuple(order))
        if key < best[0]:
            best = (key, order)
        if (time.perf_counter() - started) * 1000 >= max_ms:
            break
    order = tuple(best[1])
    return OpenRoute(order, best[0][0], order[0], nearest, (time.perf_counter() - started) * 1000)


def insertion_detour(current, task, route, points):
    """Minimum open-route insertion detour for one public task point."""
    order = tuple(route.ordered_ids if isinstance(route, OpenRoute) else route)
    if not order:
        return math.dist(current, task), 0
    best = None
    for slot in range(len(order) + 1):
        previous = tuple(current) if slot == 0 else points[order[slot - 1]]
        if slot == len(order):
            delta = math.dist(previous, task)
        else:
            following = points[order[slot]]
            delta = math.dist(previous, task) + math.dist(task, following) - math.dist(previous, following)
        key = (delta, slot)
        if best is None or key < best:
            best = key
    return best
