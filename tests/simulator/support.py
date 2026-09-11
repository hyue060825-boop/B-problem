from bsim.scenarios import load_fixture, Source, Scenario
from bsim.reference import ReferenceKernel
from bsim.clocks import ManualClock
from bsim.session import Session
from bsim.protocol import encode
from bsim.paths import ROOT
HEADERS = {'Content-Type': 'application/json'}


def make(sources=None, capacity=None, kernel_cls=ReferenceKernel):
    data, scenario, noise, numerics = load_fixture(ROOT / 'tests/fixtures/simulator/timing.json')
    if sources is not None:
        scenario = Scenario('LOCAL-test', 4, 'test_fixture', tuple(sources))
    clock = ManualClock(**data['clock'])
    session = Session(kernel_cls(scenario, noise, numerics), clock, data['robot_id'], capacity)
    session.ready_fixture()
    return session


def payload(rid='x', position=None, channel=None):
    d = {'arena_id': 'default', 'robot_id': 'LOCAL-TEAM', 'request_id': rid}
    if position is not None:
        d['position'] = dict(zip(('x', 'y'), position))
    if channel is not None:
        d['channel'] = channel
    return d


def call(session, path, rid='x', position=None, channel=None):
    return session.request('POST', path, HEADERS, encode(payload(rid, position, channel)))
