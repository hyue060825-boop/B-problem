"""Detached one-hour continuation of the frozen Q4 baseline, with smoke gates."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    temp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output',required=True)
    args = ap.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    source = out/'source'
    shutil.copytree(ROOT/'deployment/runtime_public_v2',source,ignore=shutil.ignore_patterns('__pycache__'))
    (source/'scripts').mkdir()
    shutil.copy2(ROOT/'scripts/train_legacy_deadline_ddp.py',source/'scripts/train.py')
    # Include detailed GPU update timings in the frozen run's telemetry.
    trainer = source/'scripts/train.py'
    text = trainer.read_text()
    text = text.replace("global_samples=stats['global_samples'],per_rank_samples=stats['per_rank_samples'],last_global_kl=stats['last_global_kl'])",
                        "global_samples=stats['global_samples'],per_rank_samples=stats['per_rank_samples'],last_global_kl=stats['last_global_kl'],rank_timings=stats['rank_timings'])")
    trainer.write_text(text)
    parent = ROOT/'runs/q4_legacy_deadline_20260913/best.pt'
    (out/'parent').mkdir()
    shutil.copy2(parent,out/'parent/best.pt')
    weight_hash = hashlib.sha256(parent.read_bytes()).hexdigest()
    if weight_hash != 'e8a525f78d176d9073372394b324bd585f4445fbf9cd1515141c483f38d5bd90':
        raise RuntimeError('Requested baseline changed; refusing a different starting model')
    env = dict(os.environ,CUDA_VISIBLE_DEVICES='0,1,2,3,4,5,6,7',
               OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUNBUFFERED='1',
               TORCH_NCCL_ASYNC_ERROR_HANDLING='1')
    lib = ROOT/'.venv/lib/python3.11/site-packages/nvidia'
    env['LD_LIBRARY_PATH'] = ':'.join(str(lib/x/'lib') for x in ('nvjitlink','cusparse','cublas','cudnn','cuda_runtime','cuda_nvrtc'))+':'+env.get('LD_LIBRARY_PATH','')
    cfg = dict(problem=4,world_size=8,checkpoint=str(out/'parent/best.pt'),
               baseline_checkpoint=str(out/'parent/best.pt'),output=str(out/'train'),
               seed=1810000000,validation_seed=1820000000,test_seed=1830000000,
               wall_seconds=3600,train_deadline_epoch=0,max_updates=20000,
               episodes_per_update=256,validation_episodes=512,test_episodes=3000,
               workers_per_rank=4,lr=1e-5,ppo_epochs=2,per_rank_batch_size=64,
               grad_accum_steps=1,entropy=.001,target_kl=.02,max_macros=400,
               save_every=5,eval_every=40,restore_initial_optimizer=True,
               validate_initial=False,defer_final_test=False,test_latest_if_no_best=True)
    write(out/'launch_manifest.json',dict(parent_checkpoint=str(parent),parent_sha256=weight_hash,
          cuda_visible_devices=env['CUDA_VISIBLE_DEVICES'],world_size=8,
          planner='original frozen baseline; no route/scheduling overlays',
          train_budget_s=3600,post_training_test='3000 paired scenes; best by validation, latest if no new best; parent recommendation retained unless validation passes',
          process='tmux -> launcher -> torchrun -> 8 synchronized NCCL ranks',
          created_at=datetime.now().astimezone().isoformat()))
    def run(config,log_name,extra=()):
        config_path=out/(log_name+'.config.json')
        write(config_path,config)
        cmd=[sys.executable,'-m','torch.distributed.run','--standalone','--nproc_per_node=8',
             str(trainer),'--config',str(config_path),*extra]
        with (out/(log_name+'.console.log')).open('a') as log:
            child=subprocess.Popen(cmd,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
            write(out/'supervisor.json',dict(stage=log_name,torchrun_pid=child.pid,launcher_pid=os.getpid(),
                  command=cmd,started_at=datetime.now().astimezone().isoformat(),config=str(config_path)))
            code=child.wait()
        if code:
            write(out/'supervisor.json',dict(stage='FAILED',step=log_name,exit_code=code,
                  ended_at=datetime.now().astimezone().isoformat(),log=str(out/(log_name+'.console.log'))))
            raise RuntimeError(f'{log_name} exited {code}; see console log')
    smoke=dict(cfg,output=str(out/'smoke'),seed=1800000000,validation_seed=1801000000,
               test_seed=1802000000,validation_episodes=64,test_episodes=64,
               wall_seconds=600,train_deadline_epoch=time.time()+900,save_every=1,eval_every=2)
    run(smoke,'smoke',('--stop-after','3'))
    run(smoke,'smoke_resume',('--resume',str(out/'smoke/latest.pt'),'--stop-after','4'))
    metrics=[json.loads(line) for line in (out/'smoke/metrics.jsonl').read_text().splitlines()]
    updates=[r for r in metrics if r['stage']=='PPO']
    if len(updates)!=4 or not all(r['sync'] and r['optimizer_steps']>0 and len(r['per_rank_samples'])==8 for r in updates):
        raise RuntimeError('Eight-rank update/resume smoke did not pass')
    initial=[r for r in metrics if r['stage']=='INIT']
    if len(initial)!=2 or initial[1]['state_sha256']!=updates[2]['state_sha256']:
        raise RuntimeError('Smoke resume did not restore exact model/optimizer state')
    baseline=json.loads((out/'smoke/baseline_validation.json').read_text())
    if not all(r['completion'] for key in ('baseline','teacher') for r in baseline[key]):
        raise RuntimeError('Baseline/teacher completion gate failed')
    write(out/'smoke_gate.json',dict(passed=True,updates=4,world_size=8,exact_optimizer_resume=True,
          all_rank_sync=True,baseline_completed=len(baseline['baseline']),teacher_completed=len(baseline['teacher'])))
    launched=time.time()
    cfg['train_deadline_epoch']=launched+4200
    write(out/'training_schedule.json',dict(training_budget_s=3600,
          launched_at=datetime.fromtimestamp(launched).astimezone().isoformat(),
          expected_train_stop_at=datetime.fromtimestamp(launched+3600).astimezone().isoformat(),
          note='Budget starts after process setup; finish active update and checkpoint before paired final evaluation.'))
    run(cfg,'train')
    if hashlib.sha256(parent.read_bytes()).hexdigest()!=weight_hash:
        raise RuntimeError('Original baseline file changed externally')
    write(out/'supervisor.json',dict(stage='COMPLETE',ended_at=datetime.now().astimezone().isoformat(),
          result=str(out/'train/final_test.json'),status=str(out/'train/status.json')))


if __name__=='__main__':main()
