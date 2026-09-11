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
    """核对一局公开轨迹；缺少上下文或动作确认时返回 INCOMPLETE。"""
    from .client import public_response
    from .protocol import validate
    from .reference import distance

    if not isinstance(records, list):
        raise ValueError('records must be a list')
    errors, gaps = [], []
    cached, pending = {}, {}
    last, pos, channel = None, None, None
    entered = ended = observed_action = False
    virtual_limit = None
    checked_steps = 0
    for i, row in enumerate(records, 1):
        if not isinstance(row, dict) or not {'path', 'request', 'status', 'response'} <= row.keys():
            errors.append({'step': i, 'error': 'invalid trace record'})
            continue
        path, req, body, status = row['path'], row['request'], row['response'], row['status']
        if body is None:
            if status is not None:
                errors.append({'step': i, 'error': 'HTTP status without JSON response'})
            if isinstance(req, dict) and isinstance(req.get('request_id'), str):
                rid = req['request_id']
                fingerprint = (path, req)
                if rid in pending and pending[rid] != fingerprint:
                    errors.append({'step': i, 'error': 'unconfirmed request ID changed content'})
                pending[rid] = fingerprint
            else:
                gaps.append({'step': i, 'reason': 'unidentified request without response'})
            continue
        try:
            if status is None:
                raise ValueError('JSON response without HTTP status')
            public_response(path, body, status)
        except ValueError as exc:
            errors.append({'step': i, 'error': str(exc)})
            continue
        if not body['accepted']:
            continue
        try:
            if not isinstance(req, dict) or 'robot_id' not in req:
                raise ValueError('invalid accepted request')
            validate('POST', path, {'Content-Type': 'application/json'}, encode(req), req['robot_id'])
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            errors.append({'step': i, 'error': 'invalid accepted request: ' + str(exc)})
            continue
        rid = req['request_id']
        fingerprint = (path, req)
        if rid in pending:
            if pending[rid] != fingerprint:
                errors.append({'step': i, 'error': 'unconfirmed request ID changed content'})
            else:
                del pending[rid]
        if rid in cached:
            if cached[rid] != (fingerprint, body):
                errors.append({'step': i, 'error': 'replay response/content differs'})
            continue
        cached[rid] = (fingerprint, body)
        if ended:
            errors.append({'step': i, 'error': 'new accepted action after session ended'})
        if pending:
            gaps.append({'step': i, 'reason': 'unconfirmed earlier action; transition context unknown'})
            last, pos, channel = None, None, None
        current = body['virtual_time_s']
        if path == '/enter':
            if observed_action:
                errors.append({'step': i, 'error': 'enter must be the first unique accepted action'})
            entered = True
            pos, channel = (0, 0), 1
            virtual_limit = body['max_virtual_duration_s']
        elif path == '/exit':
            if last is not None and current != last:
                errors.append({'step': i, 'error': 'exit advances clock'})
            ended = True
        else:
            p = (req['position']['x'], req['position']['y'])
            if last is not None and pos is not None and (path == '/clear' or channel is not None):
                fixed = (5 + (req['channel'] != channel) if path == '/measure'
                         else (5 if body['clear_result'] == 'success' else 3))
                estimate = float(distance(pos, p)) / 5 + fixed
                if abs((current - last) - estimate) > 2e-6:
                    errors.append({'step': i, 'error': 'public movement/action time invariant'})
                checked_steps += 1
            else:
                gaps.append({'step': i, 'reason': 'missing position/channel/clock context for transition'})
            pos = p
            if path == '/measure':
                channel = req['channel']
            if virtual_limit is not None and current >= virtual_limit:
                ended = True
        if last is not None and current < last:
            errors.append({'step': i, 'error': 'clock decreased'})
        last = current
        observed_action = True
    if not entered:
        gaps.append({'reason': 'missing accepted enter'})
    if not ended:
        gaps.append({'reason': 'missing accepted exit or observable virtual-time limit'})
    if pending:
        gaps.append({'reason': 'requests without confirmed outcomes', 'request_ids': sorted(pending)})
    return {'label': 'LOCAL-observable-invariants',
            'status': 'FAIL' if errors else ('INCOMPLETE' if gaps else 'PASS'),
            'records': len(records), 'checked_transitions': checked_steps,
            'errors': errors, 'unverified': gaps,
            'qualification': '仅核对公开响应与可观测状态；微秒计时允许 2 微秒差异，不证明隐藏场景一致或全部清除。'}
