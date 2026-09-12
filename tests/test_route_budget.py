import math
import random

import pytest

from solution.planning import route


def test_two_opt_open_endpoint_and_monotone_length():
    points = [(10., 0.), (1., 0.)]
    assert route._open_two_opt((0., 0.), [0, 1], points) == [1, 0]
    rng = random.Random(917)
    for n in (7, 31, 300):
        points = [(rng.uniform(-500, 500), rng.uniform(-500, 500)) for _ in range(n)]
        order = list(range(n))
        result = route._open_two_opt((0., 0.), order, points)
        assert sorted(result) == order
        assert route.route_length((0., 0.), result, points) <= route.route_length((0., 0.), order, points) + 1e-7


def test_trial_scoring_has_constant_distance_work(monkeypatch):
    calls = 0
    original = math.dist
    def counted(a, b):
        nonlocal calls
        calls += 1
        return original(a, b)
    monkeypatch.setattr(route.math, 'dist', counted)
    points = [(float(i), 0.) for i in range(2000)]
    result = route._open_two_opt((-1., 0.), list(range(2000)), points, max_checks=17)
    assert calls <= 4 * 17
    assert result == list(range(2000))


def test_deadline_checked_inside_nearest_scan_and_two_opt(monkeypatch):
    points = [(float(i), 0.) for i in range(2000)]
    ticks = iter([0., 0., 2.])
    monkeypatch.setattr(route.time, 'perf_counter', lambda: next(ticks, 2.))
    order = route._nearest_order((0., 0.), points, range(2000), 0, deadline=1.)
    assert sorted(order) == list(range(2000))
    # Expired deadline must not enter the distance-scoring loop.
    monkeypatch.setattr(route.math, 'dist', lambda *args: pytest.fail('expired search did work'))
    assert route._open_two_opt((0., 0.), order, points, deadline=1.) == order


def test_zero_budget_retains_every_required_point():
    points = [(float(i % 100), float(i // 100)) for i in range(20000)]
    mask = [i % 3 != 0 for i in range(len(points))]
    result = route.plan_open_route((0., 0.), points, mask, max_ms=0.)
    assert sorted(result.ordered_ids) == [i for i, required in enumerate(mask) if required]
    assert result.next_id == result.ordered_ids[0]
    assert result.length_m == pytest.approx(route.route_length((0., 0.), result.ordered_ids, points))
    assert route.plan_open_route((0., 0.), points, [False] * len(points), max_ms=0.).ordered_ids == ()
