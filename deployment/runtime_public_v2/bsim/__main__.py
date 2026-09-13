import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest
from .profiles import Blocked,require_profile

ROOT=Path(__file__).resolve().parents[1]


def emit(data,output=None):
    text=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if output:
        path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    print(text,end='')


def main(argv=None):
    parser=argparse.ArgumentParser(description='LOCAL simulator: fixture conformance only; official hidden mechanisms unresolved')
    sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('audit-rules');a.add_argument('--sources',type=Path,required=True);a.add_argument('--output')
    a=sub.add_parser('validate-fixtures');a.add_argument('--profile',default='fixture_conformance')
    a=sub.add_parser('serve');a.add_argument('--profile',default='strict_official');a.add_argument('--fixture',type=Path);a.add_argument('--host',default='127.0.0.1');a.add_argument('--port',type=int,default=2026);a.add_argument('--robot-id',default='LOCAL-TEAM')
    a=sub.add_parser('replay');a.add_argument('--fixture',type=Path,required=True);a.add_argument('--trace',type=Path,required=True);a.add_argument('--output')
    a=sub.add_parser('compare-kernels');a.add_argument('--profile',default='fixture_conformance');a.add_argument('--fixture',type=Path,default=ROOT/'fixtures/timing.json');a.add_argument('--steps',type=int,default=5000);a.add_argument('--output')
    a=sub.add_parser('benchmark');a.add_argument('--device',default='cpu');a.add_argument('--fixture',type=Path,default=ROOT/'fixtures/timing.json');a.add_argument('--num-envs',type=int,default=64);a.add_argument('--steps',type=int,default=128);a.add_argument('--output')
    a=sub.add_parser('audit-trace');a.add_argument('--trace',type=Path,required=True);a.add_argument('--output')
    a=sub.add_parser('compare-traces');a.add_argument('--left',type=Path,required=True);a.add_argument('--right',type=Path,required=True);a.add_argument('--include-real-time',action='store_true');a.add_argument('--output')
    a=sub.add_parser('smoke-client');a.add_argument('--url',required=True,help='Explicit LOCAL simulator URL; no default official port');a.add_argument('--robot-id',default='LOCAL-TEAM');a.add_argument('--output')
    a=sub.add_parser('web');a.add_argument('--port',type=int,default=8765);a.add_argument('--robot-port',type=int,default=20260)
    args=parser.parse_args(argv)
    try:
        if hasattr(args,'profile'):require_profile(args.profile)
        if args.command=='web':
            from .web_dashboard import serve_dashboard
            serve_dashboard(args.port,args.robot_port);return 0
        if args.command=='audit-rules':
            entries=json.loads((ROOT/'rules/source_manifest.json').read_text());rows=[]
            for entry in entries:
                name=Path(entry['path']).name
                matches=list(args.sources.rglob(name))
                if len(matches)!=1:
                    rows.append({'file':name,'status':'MISSING_OR_AMBIGUOUS','matches':[str(p) for p in matches]});continue
                sha=hashlib.sha256(matches[0].read_bytes()).hexdigest()
                rows.append({'file':name,'expected':entry['sha256'],'actual':sha,'status':'PASS' if sha==entry['sha256'] else 'CHANGED_REVIEW_REQUIRED'})
            report={'label':'LOCAL-source-audit','sources':rows};emit(report,args.output)
            return 0 if all(r['status']=='PASS' for r in rows) else 1
        if args.command=='validate-fixtures':
            suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
            return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
        if args.command=='serve':
            if not args.fixture:raise ValueError('--fixture required for fixture_conformance')
            from .scenarios import load_fixture
            from .reference import ReferenceKernel
            from .session import Session
            from .clocks import SystemClock
            from .http_server import serve_session
            data,scenario,noise,numerics=load_fixture(args.fixture)
            session=Session(ReferenceKernel(scenario,noise,numerics),SystemClock(),args.robot_id)
            session.prepare();session.data_ready()
            print('LOCAL fixture session: five-second countdown; no official test started.',flush=True)
            serve_session(session,args.host,args.port)
            if session.last_error:print('ADMIN error: '+session.last_error,file=sys.stderr)
            return 0
        if args.command=='replay':
            from .evaluation import replay
            report=replay(args.fixture,args.trace);emit(report,args.output);return int(report['status']!='PASS')
        if args.command=='compare-kernels':
            from .validation import compare_kernels
            if not 1<=args.steps<=100000:raise ValueError('bounded TEST comparison requires 1..100000 steps')
            report=compare_kernels(args.fixture,args.steps);emit(report,args.output);return int(report['status']!='PASS')
        if args.command=='benchmark':
            from .validation import benchmark
            emit(benchmark(args.fixture,args.device,args.num_envs,args.steps),args.output);return 0
        if args.command=='audit-trace':
            from .evaluation import audit_public_trace
            report=audit_public_trace(json.loads(args.trace.read_text())['records']);emit(report,args.output);return int(report['status']!='PASS')
        if args.command=='compare-traces':
            from .evaluation import compare_records
            differences=compare_records(json.loads(args.left.read_text())['records'],json.loads(args.right.read_text())['records'],args.include_real_time)
            emit({'label':'LOCAL-trace-comparison','status':'FAIL' if differences else 'PASS','differences':differences},args.output);return int(bool(differences))
        if args.command=='smoke-client':
            from .client import RobotClient
            client=RobotClient(args.url,args.robot_id)
            for path,p,c in [('/enter',None,None),('/measure',(300,400),1),('/measure',(300,400),2),('/clear',(300,0),3),('/measure',(300,0),2),('/exit',None,None)]:
                code,body=client.act(path,p,c)
                if code!=200 or not body['accepted']:raise RuntimeError('smoke action rejected')
            emit({'label':'LOCAL-client-trace','records':client.history()},args.output);return 0
    except Blocked as err:
        print('BLOCKED: '+str(err),file=sys.stderr);return 2
    except (ValueError,KeyError,OSError,RuntimeError) as err:
        print('ERROR: '+str(err),file=sys.stderr);return 1


if __name__=='__main__':
    sys.exit(main())
