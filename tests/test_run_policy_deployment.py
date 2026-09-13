"""Run the actual CLI against loopback protocol fixtures, not the official app."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import pytest
from bsim.research import make_research_session
from bsim.http_server import LocalServer

ROOT=Path(__file__).resolve().parents[1]


def command(problem, logs):
    return [sys.executable,str(ROOT/'scripts/run_policy.py'),'--problem',str(problem),
            '--checkpoint',str(ROOT/('runs/q3_legacy_deadline_20260913/best.pt' if problem==3 else 'runs/q4_baseline_8gpu_1h_20260913/train/best.pt')),
            '--robot-id','202619002320','--log-dir',str(logs)]


@pytest.mark.parametrize('problem',[3,4])
def test_offline_check(problem,tmp_path):
    result=subprocess.run(command(problem,tmp_path)+['--check-only'],capture_output=True,text=True,encoding='utf-8',timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    records=[json.loads(s) for s in next(tmp_path.glob('*.jsonl')).read_text().splitlines()]
    assert records[-1]['status']=='CHECK_ONLY_OK'
    assert records[0]['candidate_dim']==11
    assert not any(r['status']=='REQUEST' for r in records)


@pytest.mark.parametrize('problem,mode',[(3,'success'),(4,'success'),(3,'wrong_team'),(4,'already_entered')])
def test_http_run(problem,mode,tmp_path):
    session,_=make_research_session(problem,1390000000+problem,count=10)
    session.robot_id='202619002320' if mode!='wrong_team' else 'OTHER-TEAM'
    if mode=='already_entered':
        from bsim.protocol import encode
        status,body=session.request('POST','/enter',{'Content-Type':'application/json'},encode(dict(arena_id='default',robot_id=session.robot_id,request_id='prior-enter')))
        assert body['accepted']
    server=LocalServer(('127.0.0.1',0),session)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
    try:
        r=subprocess.run(command(problem,tmp_path)+['--base-url',f'http://127.0.0.1:{server.server_address[1]}'],capture_output=True,text=True,encoding='utf-8',timeout=90)
    finally:
        server.shutdown();server.server_close();thread.join()
    rows=[json.loads(s) for s in next(tmp_path.glob('*.jsonl')).read_text().splitlines()]
    requests=[x for x in rows if x['status']=='REQUEST']
    assert set(requests[0]['request'])=={'arena_id','robot_id','request_id'}
    if mode=='success':
        assert r.returncode==0,r.stdout+r.stderr
        assert rows[-1]['status']=='EXITED'
        assert len(session.state.cleared)==10
        assert requests[-1]['path']=='/exit'
        ids=[x['request']['request_id'] for x in requests];assert len(ids)==len(set(ids))
    else:
        assert r.returncode==2,r.stdout
        assert len(requests)==1  # no new enter retries after an explicit rejection
        assert '模型已加载' in rows[-1]['message']
        assert 'robot_id' in rows[-1]['message']


def test_wrong_checkpoint_problem_stops_before_enter(tmp_path):
    cmd=command(3,tmp_path);cmd[cmd.index('--problem')+1]='4'
    r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=40)
    assert r.returncode==2
    rows=[json.loads(s) for s in next(tmp_path.glob('*.jsonl')).read_text().splitlines()]
    assert not any(r['status']=='REQUEST' for r in rows)
    assert '权重题号' in rows[-1]['message']
