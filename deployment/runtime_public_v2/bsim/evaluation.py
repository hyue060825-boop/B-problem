"""Manager-only evaluation and replay. Never attached to actor input."""
import hashlib
import json
from pathlib import Path
from .scenarios import load_fixture
from .reference import ReferenceKernel
from .session import Session, InterfaceClosed
from .clocks import ManualClock
from .protocol import encode


def create_fixture_session(path, kernel_cls=ReferenceKernel):
    data, scenario, noise, numerics = load_fixture(path)
    session = Session(kernel_cls(scenario, noise, numerics), ManualClock(**data['clock']), data['robot_id'])
    session.ready_fixture()
    return session


def score(session):
    n, c = len(session.kernel.scenario.sources), len(session.state.cleared)
    t = session.state.virtual_us / 1000000
    return {'label': 'LOCAL-evaluation', 'N': n, 'C': c, 'cleared_fraction': c/n if n else None,
            'virtual_time_s': t, 'time_per_clear_s': t/c if c else None,
            'all_cleared': n > 0 and c == n, 'ended': session.phase == 'ended', 'reason': session.reason}


def replay(fixture_path, trace_path, kernel_cls=ReferenceKernel):
    session = create_fixture_session(fixture_path, kernel_cls)
    trace = json.loads(Path(trace_path).read_text())
    if not trace['label'].startswith('LOCAL-'):
        raise ValueError('trace must have LOCAL label')
    records, mismatches = [], []
    for i, step in enumerate(trace['steps']):
        session.clock.advance(step.get('advance_s',0))
        if 'abort' in step:
            session.abort()
        try:
            code, body = session.request(step.get('method','POST'), step['path'],
                                         step.get('headers',{'Content-Type':'application/json'}),
                                         encode(step['request']))
        except InterfaceClosed:
            code, body = None, None
        records.append({'path':step['path'], 'request':step['request'], 'status':code, 'response':body})
        expected_status=step.get('expected_status',200)
        if code != expected_status:
            mismatches.append({'step':i+1,'field':'status','expected':expected_status,'actual':code})
        for key, val in step.get('expected',{}).items():
            actual=(body or {}).get(key)
            if actual != val:
                mismatches.append({'step':i+1,'field':key,'expected':val,'actual':actual})
    return {'label':'LOCAL-replay', 'profile':'fixture_conformance',
            'fixture_sha256':hashlib.sha256(Path(fixture_path).read_bytes()).hexdigest(),
            'trace_sha256':hashlib.sha256(Path(trace_path).read_bytes()).hexdigest(),
            'status':'FAIL' if mismatches else 'PASS', 'mismatches':mismatches,
            'records':records,'evaluation':score(session)}


def compare_records(left, right, include_real_time=False):
    differences=[]
    for i in range(max(len(left),len(right))):
        if i>=len(left) or i>=len(right):
            differences.append({'step':i+1,'field':'missing_record'});continue
        a,b=json.loads(json.dumps(left[i])),json.loads(json.dumps(right[i]))
        if not include_real_time:
            for row in (a,b):
                if row.get('response'):row['response'].pop('real_timestamp_ms',None)
        if a!=b:differences.append({'step':i+1,'left':a,'right':b})
    return differences


def audit_public_trace(records):
    """Unknown official truth: check ONLY observable invariants; no hidden alignment."""
    from .client import public_response
    errors=[]; last=0; cached={}; pos=(0,0);channel=1;started=False
    from .reference import distance
    for i,row in enumerate(records):
        path,req,body=row['path'],row['request'],row.get('response')
        if body is None:continue
        try:public_response(path,body)
        except ValueError as e:errors.append({'step':i+1,'error':str(e)});continue
        if row['status']!=200 or not body['accepted']:
            if not body['accepted'] and body['virtual_time_s']!=0:
                errors.append({'step':i+1,'error':'rejection clock must be zero'})
            continue
        rid=req['request_id'];fingerprint=(path,req)
        if rid in cached:
            if cached[rid]!=(fingerprint,body):errors.append({'step':i+1,'error':'replay response/content differs'})
            continue
        cached[rid]=(fingerprint,body)
        current=body['virtual_time_s']
        if path=='/enter':
            started=True
            if current!=0:errors.append({'step':i+1,'error':'enter virtual time'})
        elif path=='/exit':
            if current!=last:errors.append({'step':i+1,'error':'exit advances clock'})
        elif started:
            p=(req['position']['x'],req['position']['y'])
            fixed=5+(req['channel']!=channel) if path=='/measure' else (5 if body['clear_result']=='success' else 3)
            estimate=float(distance(pos,p))/5+fixed
            # Unknown G05: tolerance only tests coarse invariant, not official rounding.
            if abs((current-last)-estimate)>2e-6:
                errors.append({'step':i+1,'error':'public movement/action time invariant'})
            pos=p
            if path=='/measure':channel=req['channel']
        if current<last:errors.append({'step':i+1,'error':'clock decreased'})
        last=current
    return {'label':'LOCAL-observable-invariants','status':'FAIL' if errors else 'PASS',
            'records':len(records),'errors':errors,'qualification':'G05 microsecond rounding not resolved; no hidden-state equivalence claim'}
