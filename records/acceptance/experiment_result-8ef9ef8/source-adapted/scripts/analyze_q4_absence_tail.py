"""Post-hoc Q4 tail attribution; hidden N used only by evaluator statistics."""
import argparse,csv,hashlib,json,sys,time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deployment/runtime_public_v2'))
import torch
from solution.rl.environment import TrainingEnv,model_state
from solution.rl.model import CandidatePolicy


def init(checkpoint):
    global MODEL
    torch.set_num_threads(1)
    d=torch.load(checkpoint,map_location='cpu',weights_only=False)
    runtime=ROOT/'deployment/runtime_public_v2'
    for p,h in d['provenance']['files'].items():
        if p.startswith(('solution/','bsim/')):
            assert hashlib.sha256((runtime/p).read_bytes()).hexdigest()==h,p
    MODEL=CandidatePolicy().eval();MODEL.load_state_dict(d['model'])


def summarize_events(events,total,n):
    successes=[e for e in events if e['kind']=='clear_success']
    discoveries={}
    for e in events:
        if e['kind'] in ('near','direction'):discoveries.setdefault(e['channel'],e['end'])
    last_clear=successes[-1]['end'] if successes else 0.
    last_find=max(discoveries.values(),default=0.)
    tail=[e for e in events if e['start']>=last_clear-1e-8 and e not in successes]
    # /exit contributes zero virtual time; intervals classify exact primitive costs.
    out=dict(N=n,total_s=total,last_clear_s=last_clear,last_discovery_s=last_find,
             tail_s=total-last_clear,tail_fraction=(total-last_clear)/total,
             last_discovery_to_end_s=total-last_find,discovered_by_6000=sum(t<=6000 for t in discoveries.values()),
             cleared_by_6000=sum(e['end']<=6000 for e in successes),
             all_found_by_6000=len(discoveries)==n and last_find<=6000,
             all_cleared_by_6000=len(successes)==n and last_clear<=6000,
             all_done_5000_6000=5000<=total<=6000,
             tail_measures=sum(e['kind'] in ('near','direction','no_signal') for e in tail),
             tail_no_signal=sum(e['kind']=='no_signal' for e in tail),
             after_6000_measures=sum(e['end']>6000 and e['kind'] in ('near','direction','no_signal') for e in events),
             after_6000_no_signal=sum(e['end']>6000 and e['kind']=='no_signal' for e in events),
             discovered_total=len(discoveries),cleared_total=len(successes))
    for prefix,subset in (('all',events),('tail',tail)):
        for key in ('move_s','measure_s','switch_s','clear_s'):
            out[prefix+'_'+key]=sum(e[key] for e in subset)
    out['after_6000_s']=max(0.,total-6000.)
    out['after_6000_tail_s']=max(0.,total-max(6000.,last_clear))
    out['cost_accounting_error']=sum(out['all_'+k] for k in ('move_s','measure_s','switch_s','clear_s'))-total
    # Negative measurements on actually absent channels include early coverage,
    # and cannot all be called pure tail (robot may still need to find real sources).
    real_channels=set(discoveries)
    out['absent_channel_measures']=sum(e['kind']=='no_signal' and e['channel'] not in real_channels for e in events)
    out['after_6000_absent_channel_measures']=sum(e['end']>6000 and e['kind']=='no_signal' and e['channel'] not in real_channels for e in events)
    out['after_6000_clear_successes']=sum(e['end']>6000 and e['kind']=='clear_success' for e in events)
    out['after_6000_clear_failures']=sum(e['end']>6000 and e['kind']=='clear_failed' for e in events)
    out['after6000_discovery_count']=sum(t>6000 for t in discoveries.values())
    return out


def log_events(path):
    rows=[json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    events=[];pending=None;position=(0.,0.);channel=1;vt=0.;seen=set()
    for r in rows:
        if r['status']=='REQUEST':pending=r
        elif r['status']=='RESPONSE' and r['response'].get('accepted') and pending:
            req=pending['request'];response=r['response'];rid=req['request_id']
            if rid in seen:continue
            seen.add(rid)
            if r['path'] not in ('/measure','/clear'):continue
            kind=response.get('measure_result') or ('clear_success' if response['clear_result']=='success' else 'clear_failed')
            end=response['virtual_time_s'];ms=5. if r['path']=='/measure' else 0.;ss=float(r['path']=='/measure' and req['channel']!=channel)
            cs=0. if r['path']=='/measure' else 5. if kind=='clear_success' else 3.
            e=dict(start=vt,end=end,kind=kind,channel=req['channel'],move_s=end-vt-ms-ss-cs,measure_s=ms,switch_s=ss,clear_s=cs,position=req['position']);events.append(e)
            vt=end
            if r['path']=='/measure':channel=req['channel']
    n=len({e['channel'] for e in events if e['kind']=='clear_success'})
    return rows,events,summarize_events(events,vt,n)


def replay(original):
    env=TrainingEnv(4,original['seed'],max_macros=400);events=[];request=env._request
    def traced(path,pos,ch):
        old=env.session.state;response=request(path,pos,ch)
        if path in ('/measure','/clear'):
            end=env.session.state.virtual_us/1e6;start=old.virtual_us/1e6
            ms=5. if path=='/measure' else 0.;ss=float(path=='/measure' and ch!=old.channel)
            kind=response.get('measure_result') or ('clear_success' if response['clear_result']=='success' else 'clear_failed')
            cs=0. if path=='/measure' else 5. if kind=='clear_success' else 3.
            events.append(dict(start=start,end=end,kind=kind,channel=ch,move_s=end-start-ms-ss-cs,measure_s=ms,switch_s=ss,clear_s=cs))
        return response
    env._request=traced
    while not env.done:
        state,actions=env.observe();ts={k:torch.from_numpy(v).unsqueeze(0) for k,v in model_state(state).items()}
        with torch.inference_mode():logits,_=MODEL(ts)
        env.step(actions[int(logits.argmax(-1))])
    metrics=env.metrics();out=summarize_events(events,metrics['virtual_time_s'],metrics['N'])
    from dataclasses import asdict
    digest=hashlib.sha256(json.dumps(asdict(env.session.kernel.scenario),sort_keys=True).encode()).hexdigest()
    assert digest==original['scenario_sha256']
    out.update(seed=original['seed'],completion=metrics['completion'],error=metrics['error'],original_total_s=original['virtual_time_s'],replay_delta_s=metrics['virtual_time_s']-original['virtual_time_s'],distribution=metrics['profile']['distribution'])
    return out


def aggregate(rows):
    keys=['total_s','last_clear_s','last_discovery_s','tail_s','tail_fraction','tail_move_s','tail_measure_s','tail_switch_s','tail_clear_s','all_move_s','all_measure_s','all_switch_s','all_clear_s','tail_measures','absent_channel_measures']
    out=dict(episodes=len(rows),**{k:float(np.mean([r[k] for r in rows])) for k in keys})
    for k in ('all_found_by_6000','all_cleared_by_6000','all_done_5000_6000'):
        out[k]=sum(r[k] for r in rows)
    for k in ('total_s','last_clear_s','tail_s'):out[k+'_p50_p95']=[float(np.percentile([r[k] for r in rows],p)) for p in (50,95)]
    for prefix in ('tail','after_6000'):
        measures=sum(r[prefix+'_measures'] for r in rows);neg=sum(r[prefix+'_no_signal'] for r in rows)
        out[prefix+'_pooled_negative_rate']=neg/measures if measures else None
        out[prefix+'_measure_count']=measures
    out['after_6000_time_pure_tail_fraction']=sum(r['after_6000_tail_s'] for r in rows)/max(1e-9,sum(r['after_6000_s'] for r in rows))
    out['episodes_with_late_discovery']=sum(r['after6000_discovery_count']>0 for r in rows)
    out['after_6000_absent_channel_measures']=sum(r['after_6000_absent_channel_measures'] for r in rows)
    out['after_6000_clear_successes']=sum(r['after_6000_clear_successes'] for r in rows)
    out['after_6000_clear_failures']=sum(r['after_6000_clear_failures'] for r in rows)
    out['pooled_tail_time_fraction']=sum(r['tail_s'] for r in rows)/sum(r['total_s'] for r in rows)
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'runs/q34_deadline_test3000_20260913/q4_best_samples.json';original=json.loads(source.read_text());checkpoint=ROOT/'runs/q4_legacy_deadline_20260913/best.pt'
    log,ev,official=log_events(ROOT/'paper/official_logs/logQ4.jsonl')
    (out/'official_log_summary.json').write_text(json.dumps(official,indent=2));(out/'official_events.json').write_text(json.dumps(ev,indent=2))
    assert log[0]['checkpoint_sha256']==hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (out/'manifest.json').write_text(json.dumps(dict(checkpoint=str(checkpoint),sha256=log[0]['checkpoint_sha256'],original_samples=str(source),samples_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),official_log_sha256=hashlib.sha256(Path(ROOT/'paper/official_logs/logQ4.jsonl').read_bytes()).hexdigest(),note='original aggregate data lack primitive timestamps; same scenarios replayed with instrumentation; live wall feature retained'),indent=2))
    rows=[];start=time.perf_counter()
    with ProcessPoolExecutor(32,mp_context=mp.get_context('spawn'),initializer=init,initargs=(checkpoint,)) as pool:
        with (out/'replay.jsonl').open('w') as f:
            for r in pool.map(replay,original,chunksize=4):
                rows.append(r);f.write(json.dumps(r)+'\n')
                if len(rows)%250==0:print(json.dumps(dict(done=len(rows),elapsed_s=time.perf_counter()-start)),flush=True)
    summary=dict(overall=aggregate(rows),lt16=aggregate([r for r in rows if r['N']<16]),by_N={str(n):aggregate([r for r in rows if r['N']==n]) for n in range(10,17)},by_distribution_N={d:{str(n):aggregate([r for r in rows if r['N']==n and r['distribution']==d]) for n in range(10,17)} for d in sorted({r['distribution'] for r in rows})},replay_validation=dict(completed=sum(r['completion'] for r in rows),exact_total_matches=sum(abs(r['replay_delta_s'])<1e-6 for r in rows),max_absolute_delta_s=max(abs(r['replay_delta_s']) for r in rows),mean_delta_s=float(np.mean([r['replay_delta_s'] for r in rows])),max_cost_error=max(abs(r['cost_accounting_error']) for r in rows)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    with (out/'samples.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(17,5),dpi=170);ns=list(range(10,17));g=[summary['by_N'][str(n)] for n in ns]
    ax[0].bar(ns,[r['last_clear_s'] for r in g],label='Before last successful clear');ax[0].bar(ns,[r['tail_s'] for r in g],bottom=[r['last_clear_s'] for r in g],label='After last clear');ax[0].set(xlabel='Source count N',ylabel='Mean virtual seconds',title='Q4: 3000 scenarios');ax[0].legend(fontsize=8)
    ax[1].boxplot([[r['tail_s'] for r in rows if r['N']==n] for n in ns],tick_labels=ns,showfliers=False);ax[1].set(xlabel='N',ylabel='Tail virtual seconds',title='Post-clear tail distribution')
    xs=[0]+[e['end'] for e in ev];clears=[0];found=set();disc=[0]
    for e in ev:
        clears.append(clears[-1]+int(e['kind']=='clear_success'))
        if e['kind'] in ('direction','near'):found.add(e['channel'])
        disc.append(len(found))
    ax[2].step(xs,disc,where='post',label='Discovered');ax[2].step(xs,clears,where='post',label='Cleared');ax[2].axvline(6000,c='gray',ls='--');ax[2].axvspan(official['last_clear_s'],official['total_s'],alpha=.2,color='orange');ax[2].set(xlabel='Virtual seconds',ylabel='Public source count',title='Provided official log');ax[2].legend()
    fig.tight_layout();fig.savefig(out/'tail_analysis.png');fig.savefig(out/'tail_analysis.pdf')
    print(json.dumps(dict(official=official,replay_validation=summary['replay_validation'],overall=summary['overall'],lt16=summary['lt16']),indent=2))

if __name__=='__main__':main()
