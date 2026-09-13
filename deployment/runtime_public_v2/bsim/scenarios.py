"""Administrative data only. Never import this module into a strategy."""
import json
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, Protocol
from .profiles import Blocked, require_profile


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


@dataclass(frozen=True)
class Source:
    channel: int
    x: float
    y: float
    radius: float
    kind: str
    heading: Optional[float] = None

    def __post_init__(self):
        if type(self.channel) is not int or not 1 <= self.channel <= 20:
            raise ValueError('source channel')
        if not all(number(v) for v in (self.x, self.y, self.radius)):
            raise ValueError('nonfinite source')
        if math.hypot(self.x, self.y) > 1800 or not 1000 <= self.radius <= 1500:
            raise ValueError('source geometry')
        if self.kind not in ('omni', 'directional'):
            raise ValueError('source kind')
        if self.kind == 'omni' and self.heading is not None:
            raise ValueError('omni heading must be null')
        if self.kind == 'directional' and (not number(self.heading) or not 0 <= self.heading < 360):
            raise ValueError('directional heading')


@dataclass(frozen=True)
class Scenario:
    label: str
    problem: int
    scope: str
    sources: Tuple[Source, ...]

    def __post_init__(self):
        if not self.label.startswith('LOCAL-'):
            raise ValueError('LOCAL label required')
        if self.problem not in (3, 4) or self.scope not in ('official_constraints', 'test_fixture'):
            raise ValueError('problem/scope')
        if len(set(s.channel for s in self.sources)) != len(self.sources):
            raise ValueError('duplicate channel')
        if self.scope == 'official_constraints':
            if not 10 <= len(self.sources) <= 16:
                raise ValueError('N outside 10..16')
            kinds = {s.kind for s in self.sources}
            if self.problem == 3 and kinds != {'omni'}:
                raise ValueError('problem 3 requires omni')
            if self.problem == 4 and kinds != {'omni', 'directional'}:
                raise ValueError('problem 4 requires both kinds')


class ScenarioGenerator(Protocol):
    def generate(self, seed: int) -> Scenario: ...


class OfficialGenerator:
    def generate(self, seed):
        raise Blocked('G01 official joint scenario distribution unresolved')


def load_fixture(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require_profile(data['profile'])
    spec = data['scenario']
    scenario = Scenario(spec['label'], spec['problem'], spec['scope'],
                        tuple(Source(**s) for s in spec['sources']))
    # Every unknown numerical convention must be supplied explicitly.
    from .noise import FixtureNoise, Numerics
    noise = FixtureNoise(data['noise'])
    numerics = Numerics(**data['numerics'])
    return data, scenario, noise, numerics
