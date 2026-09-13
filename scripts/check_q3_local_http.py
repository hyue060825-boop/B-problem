#!/usr/bin/env python3
"""Launch our own ephemeral loopback server and run the real deployment CLI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
from bsim.research import make_research_session
from bsim.http_server import LocalServer
from solution.rl.training import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True)
    p.add_argument('--seed',type=int,default=100200000);a=p.parse_args()
    session,_=make_research_session(3,a.seed)
    server=LocalServer(('127.0.0.1',0),session);port=server.server_address[1]
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});thread.start()
    try:
        cmd=[sys.executable,str(Path(__file__).resolve().with_name('run_policy_research.py')),'--problem','3','--checkpoint',a.checkpoint,
             '--robot-id','LOCAL-TRAIN','--base-url',f'http://127.0.0.1:{port}','--device','cpu','--max-macros','400']
        result=subprocess.run(cmd,text=True,capture_output=True,timeout=120)
    finally:server.shutdown();server.server_close();thread.join()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    (out/'client.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stderr)
    rows=[json.loads(s) for s in result.stdout.splitlines() if s.startswith('{')]
    remaining=[r['remaining_real_s'] for r in rows if r.get('status')=='ACTION']
    assert remaining and remaining[-1]<remaining[0] and all(b<=a for a,b in zip(remaining,remaining[1:]))
    assert rows[-1]['status']=='EXITED' and session.reason=='user_exit'
    assert len(session.state.cleared)==len(session.kernel.scenario.sources)
    report=dict(status='PASS',checkpoint=a.checkpoint,command=cmd,server='new LOCAL-RESEARCH ephemeral port; not official service',
                exit_reason=session.reason,source_count=len(session.kernel.scenario.sources),cleared=len(session.state.cleared),
                first_remaining_real_s=remaining[0],last_remaining_real_s=remaining[-1],requests=len(session.events),
                virtual_time_s=session.state.virtual_us/1e6,seed=a.seed)
    atomic_json(out/'summary.json',report);print(json.dumps(report))


if __name__=='__main__':main()
