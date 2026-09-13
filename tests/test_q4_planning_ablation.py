from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from experiments.q4_planning import improve_open_route, insert_clears, nearest_order, route_length, select_action


@dataclass(frozen=True)
class Action:
    kind: str
    position: tuple
    channel: int = 0
    station: int = -1
    channels: tuple = ()
    cost: float = 0.


def test_open_route_preserves_all_stations_and_never_increases_length():
    rng = np.random.default_rng(61)
    for n in (0, 1, 2, 8, 31):
        points = rng.normal(size=(n, 2)).tolist()
        start = (3., -7.)
        initial = nearest_order(start, points)
        optimized = improve_open_route(start, points, initial)
        assert sorted(optimized) == list(range(n))
        assert route_length(start, [points[i] for i in optimized]) <= route_length(start, [points[i] for i in initial]) + 1e-8


def test_cheapest_insertion_picks_on_the_way_clear_without_reordering_coverage():
    cover = [Action('COVER', (10., 0.), station=0), Action('COVER', (20., 0.), station=1)]
    clear = Action('CLEAR', (5., 0.), channel=7)
    route = insert_clears((0., 0.), cover, [clear])
    assert route == [clear] + cover
    assert route_length((0., 0.), [a.position for a in route]) == 20


@pytest.mark.parametrize('variant', ['baseline', 'route', 'schedule', 'combined'])
def test_public_only_overlay_preserves_noncover_and_never_invents_clear(variant):
    ctrl = SimpleNamespace(position=(0., 0.), stations=[(10., 0.), (20., 0.)], visited=set())
    cover = Action('COVER', (10., 0.), station=0, channels=(1, 2))
    probe = Action('PROBE_CLEAR', (5., 0.), channel=4)
    assert select_action(ctrl, [cover, probe], probe, variant) is probe
    result = select_action(ctrl, [cover, probe], cover, variant)
    assert result.kind == 'COVER' and result.channels == cover.channels
    assert ctrl.visited == set()
    safe = Action('CLEAR', (5., 0.), channel=7)
    result = select_action(ctrl, [cover, safe], cover, variant)
    if variant in ('schedule', 'combined'):
        assert result is safe
    if variant == 'baseline':
        assert result is cover
