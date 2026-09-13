"""CPU broad-phase acceleration; exact reference fallback near thresholds.

Movement time always uses the reference Decimal path, because microsecond
rounding can change at arbitrary locations. No CUDA claims or low precision.
"""
import math
from dataclasses import replace
from .reference import ReferenceKernel, distance


class FastKernel(ReferenceKernel):
    def within(self, a, b, radius):
        d = math.hypot(a[0]-b[0],a[1]-b[1])
        # Guard comfortably exceeds float64 error over allowed coordinate range.
        margin = 1e-8 * max(1, abs(a[0]),abs(a[1]),abs(b[0]),abs(b[1]),radius)
        if abs(d-radius) <= margin:
            return super().within(a,b,radius)
        return d <= radius

    def transition(self, state, path, p, channel):
        move_us=self.numerics.movement_us(distance(state.position,p))
        if path == '/measure':
            result=self.observe(state,p,channel)
            cost=5000000+(0 if channel==state.channel else 1000000)
            new=replace(state,position=p,channel=channel,virtual_us=state.virtual_us+move_us+cost)
        elif path == '/clear':
            src=self.sources.get(channel)
            success=src is not None and channel not in state.cleared and self.within(p,(src.x,src.y),20)
            cost=5000000 if success else 3000000
            new=replace(state,position=p,virtual_us=state.virtual_us+move_us+cost,
                        cleared=state.cleared.union((channel,)) if success else state.cleared)
            result={'clear_result':'success' if success else 'no_target_in_range'}
        else:raise ValueError('unknown physical action')
        return new,result
