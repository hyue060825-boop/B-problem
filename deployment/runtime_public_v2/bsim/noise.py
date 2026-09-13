"""Explicit, deterministic TEST functions, not estimates of the official field."""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, ROUND_HALF_EVEN
from dataclasses import dataclass
from typing import Protocol
import math
from .profiles import Blocked


class ErrorField(Protocol):
    def error(self, channel, x, y): ...


class OfficialError:
    def error(self, channel, x, y):
        raise Blocked('G02 G03 official fixed error field and position key unresolved')


class FixtureNoise:
    def __init__(self, spec):
        if spec.get('label') != 'TEST_INPUT':
            raise ValueError('noise requires TEST_INPUT label')
        self.kind = spec['kind']
        self.value = spec.get('value')
        self.table = {}
        if self.kind == 'constant':
            self._check(self.value)
        elif self.kind == 'table':
            for row in spec['entries']:
                self._check(row['error'])
                key = (row['channel'], float(row['x']), float(row['y']))
                if key in self.table:
                    raise ValueError('duplicate error key')
                self.table[key] = row['error']
        else:
            raise ValueError('unsupported TEST error field')

    @staticmethod
    def _check(value):
        if type(value) not in (int, float) or not math.isfinite(value) or not -1 <= value <= 1:
            raise ValueError('error must be finite and in [-1,1]')

    def error(self, channel, x, y):
        if self.kind == 'constant':
            return self.value
        try:
            return self.table[(channel, float(x), float(y))]
        except KeyError:
            raise Blocked('G02 G03: no explicit TEST error at this channel/position')


@dataclass(frozen=True)
class Numerics:
    label: str
    angle_rounding: str
    time_rounding: str
    directional_overlap: str
    boundary_epsilon: float

    def __post_init__(self):
        if self.label != 'TEST_INPUT':
            raise ValueError('numerics require TEST_INPUT label')
        if self.angle_rounding not in ('half_up', 'half_even', 'floor') or self.time_rounding not in ('half_up', 'half_even', 'floor'):
            raise ValueError('rounding policy')
        if self.directional_overlap not in ('blocked', 'visible', 'invisible'):
            raise ValueError('overlap policy')
        if type(self.boundary_epsilon) not in (int, float) or not math.isfinite(self.boundary_epsilon) or self.boundary_epsilon < 0:
            raise ValueError('boundary epsilon')

    @staticmethod
    def rounding(name):
        return {'half_up': ROUND_HALF_UP, 'half_even': ROUND_HALF_EVEN, 'floor': ROUND_FLOOR}[name]

    def angle(self, degrees):
        # Explicit fixture order: add error (caller), normalize, quantize, normalize.
        angle = Decimal(str(degrees % 360)).quantize(Decimal('.01'), rounding=self.rounding(self.angle_rounding)) % 360
        return float(angle)

    def movement_us(self, distance):
        return int((distance * Decimal(200000)).to_integral_value(rounding=self.rounding(self.time_rounding)))
