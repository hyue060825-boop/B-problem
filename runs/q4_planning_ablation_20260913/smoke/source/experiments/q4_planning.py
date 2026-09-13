"""Public-state planning overlays for a frozen Q4 policy (no model inputs changed)."""
import math

import numpy as np

VARIANTS = ('baseline', 'route', 'schedule', 'combined')
TWO_OPT_PASSES = 12


def route_length(start, points):
    return sum(math.dist(a, b) for a, b in zip([start] + list(points), points))


def nearest_order(start, points, first=None):
    remaining = set(range(len(points)))
    order = []
    current = start
    while remaining:
        index = first if not order and first is not None else min(
            remaining, key=lambda i: (math.dist(current, points[i]), i))
        order.append(index)
        remaining.remove(index)
        current = points[index]
    return order


def improve_open_route(start, points, order, passes=TWO_OPT_PASSES):
    """Bounded best-improvement 2-opt, fixed start and free end; no return leg."""
    if len(order) < 2:
        return list(order)
    xy = np.asarray([start] + list(points), dtype=float)
    distance = np.linalg.norm(xy[:, None] - xy[None, :], axis=-1)
    order = np.asarray(order, dtype=int) + 1
    i, j = np.triu_indices(len(order), 1)
    for _ in range(passes):
        previous = np.concatenate(([0], order[:-1]))
        following = np.concatenate((order[1:], [0]))
        change = distance[previous[i], order[j]] - distance[previous[i], order[i]]
        change += np.where(j < len(order) - 1,
                           distance[order[i], following[j]] - distance[order[j], following[j]], 0.)
        best = int(np.argmin(change))
        if change[best] >= -1e-8:
            break
        left, right = int(i[best]), int(j[best])
        order[left:right + 1] = order[left:right + 1][::-1]
    return (order - 1).tolist()


def insert_clears(start, backbone, clear_actions):
    """Cheapest insertion; preserve the coverage backbone's relative order."""
    route = list(backbone)
    pending = sorted(clear_actions, key=lambda a: a.channel)
    while pending:
        costs = []
        for c, action in enumerate(pending):
            for slot in range(len(route) + 1):
                prev = start if slot == 0 else route[slot - 1].position
                extra = math.dist(prev, action.position)
                if slot < len(route):
                    nxt = route[slot].position
                    extra += math.dist(action.position, nxt) - math.dist(prev, nxt)
                # Every certified clear requires the same 5s service time.
                costs.append((extra, action.channel, slot, c))
        _, _, slot, index = min(costs)
        route.insert(slot, pending.pop(index))
    return route


def select_action(controller, actions, chosen, variant):
    """Only adjust a policy-selected COVER. Never invent clear/exit certificates."""
    if variant not in VARIANTS:
        raise ValueError(variant)
    if variant == 'baseline' or chosen.kind != 'COVER':
        return chosen
    station_ids = [i for i in range(len(controller.stations)) if i not in controller.visited]
    points = [tuple(controller.stations[i]) for i in station_ids]
    original_first = station_ids.index(chosen.station)
    backbone_order = nearest_order(controller.position, points, first=original_first)
    if variant in ('route', 'combined'):
        # Compare policy-first and nearest-first initial routes, both with 2-opt.
        orders = [improve_open_route(controller.position, points, initial) for initial in
                  (backbone_order, nearest_order(controller.position, points))]
        backbone_order = min(orders, key=lambda x: (route_length(controller.position, [points[i] for i in x]), x))
    backbone = [type(chosen)(
        'COVER', points[i], station=station_ids[i], channels=chosen.channels,
        cost=math.dist(controller.position, points[i]) / 5 + 6 * len(chosen.channels)) for i in backbone_order]
    if variant in ('schedule', 'combined'):
        safe = [a for a in actions if a.kind == 'CLEAR']
        backbone = insert_clears(controller.position, backbone, safe)
    return backbone[0]
