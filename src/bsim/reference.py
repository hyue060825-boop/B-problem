"""Pure reference transitions. Decimal distance; float64 trigonometry, G06 qualified."""
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from typing import FrozenSet, Tuple
import math
from .profiles import Blocked


def distance(a, b):
    with localcontext() as ctx:
        ctx.prec = 60
        dx, dy = (Decimal(str(a[i])) - Decimal(str(b[i])) for i in (0, 1))
        return (dx * dx + dy * dy).sqrt()


@dataclass(frozen=True)
class State:
    position: Tuple[float, float] = (0, 0)
    channel: int = 1
    virtual_us: int = 0
    cleared: FrozenSet[int] = frozenset()


class ReferenceKernel:
    def __init__(self, scenario, noise, numerics):
        self.scenario, self.noise, self.numerics = scenario, noise, numerics
        self.sources = {s.channel: s for s in scenario.sources}

    def within(self, a, b, radius):
        return distance(a, b) <= Decimal(str(radius))

    def visible(self, source, p):
        if not self.within(p, (source.x, source.y), source.radius):
            return False
        if source.kind == 'omni':
            return True
        dx, dy = p[0] - source.x, p[1] - source.y
        if dx == dy == 0:
            if self.numerics.directional_overlap == 'blocked':
                raise Blocked('G06 directional coincident point unresolved')
            return self.numerics.directional_overlap == 'visible'
        # Exact cardinal directions avoid cos(pi/2) sign artefacts.
        cardinal = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
        u = cardinal.get(source.heading)
        if u is None:
            angle = math.radians(source.heading)
            u = (math.cos(angle), math.sin(angle))
        return u[0] * dx + u[1] * dy >= -self.numerics.boundary_epsilon

    def observe(self, state, p, channel):
        s = self.sources.get(channel)
        if s is None or channel in state.cleared or not self.visible(s, p):
            return {'measure_result': 'no_signal'}
        if self.within(p, (s.x, s.y), 5):
            return {'measure_result': 'near'}
        error = self.noise.error(channel, *p)
        if not math.isfinite(error) or not -1 <= error <= 1:
            raise ValueError('invalid error field output')
        angle = math.degrees(math.atan2(s.y - p[1], s.x - p[0])) + error
        return {'measure_result': 'direction', 'svd_deg': self.numerics.angle(angle)}

    def transition(self, state, path, p, channel):
        move_us = self.numerics.movement_us(distance(state.position, p))
        if path == '/measure':
            result = self.observe(state, p, channel)
            dt = move_us + 5000000 + 1000000 * (channel != state.channel)
            return replace(state, position=p, channel=channel, virtual_us=state.virtual_us + dt), result
        if path != '/clear':
            raise ValueError('unknown physical action')
        s = self.sources.get(channel)
        success = s is not None and channel not in state.cleared and self.within(p, (s.x, s.y), 20)
        dt = move_us + (5000000 if success else 3000000)
        cleared = state.cleared | {channel} if success else state.cleared
        return replace(state, position=p, virtual_us=state.virtual_us + dt, cleared=frozenset(cleared)), {'clear_result': 'success' if success else 'no_target_in_range'}
