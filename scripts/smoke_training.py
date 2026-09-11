#!/usr/bin/env python3
"""正式研究实训前必须通过：闭环、CUDA梯度、BC/PPO、断点、CPU/GPU一致性。"""
import sys,os,json,time,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('MKL_NUM_THREADS','1')
import numpy as np
import torch
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from solution.rl.training import (init_worker,collect,summarize,collate,bc_update,ppo_update,
 save_checkpoint,load_checkpoint,atomic_json,paired_evaluation,provenance)
from solution.rl.model import CandidatePolicy
from solution.rl.environment import TrainingEnv

def main():
    output=Path('results/training/smoke_20260911');output.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1);torch.manual_seed(2026);random.seed(2026);np.random.seed(2026)
    started=time.perf_counter();report={'status':'RUNNING','torch':torch.__version__,'cuda':torch.cuda.is_available(),'problems':{},'provenance':provenance()}
    if not report['cuda']:raise RuntimeError('CUDA unavailable')
    report['devices']=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    with ProcessPoolExecutor(4,mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        for problem in (3,4):
            t=time.perf_counter();device=torch.device(f'cuda:{problem-3}')
            base=collect(pool,problem,range(16));summary=summarize(base)
            atomic_json(output/f'q{problem}_baseline.json',[m for _,m in base])
            if summary['completion_rate']!=1:raise RuntimeError(f'Q{problem} teacher baseline failure: {summary["failures"]}')
            print(f'Q{problem} teacher 16/16 complete, {time.perf_counter()-t:.2f}s',flush=True)
            model=CandidatePolicy().to(device);opt=torch.optim.Adam(model.parameters(),lr=3e-4)
            rows=[r for ep,_ in base for r in ep];s,mask=collate(rows[:64],device)
            target=torch.tensor([r['teacher'] for r in rows[:64]],device=device)
            with torch.no_grad():before=float(torch.nn.functional.cross_entropy(model(s,mask)[0],target))
            old={k:v.detach().clone() for k,v in model.state_dict().items()}
            bc=bc_update(model,opt,rows,device,3,128)
            with torch.no_grad():after=float(torch.nn.functional.cross_entropy(model(s,mask)[0],target))
            assert after<before,(before,after)
            assert any(not torch.equal(v,model.state_dict()[k]) for k,v in old.items())
            samples=collect(pool,problem,range(500,504),model)
            sampled=summarize(samples)
            if sampled['failures']:raise RuntimeError(f'Q{problem} sampled failure {sampled["failures"]}')
            ppo=ppo_update(model,opt,samples,device,2,128)
            config=dict(profile='compatible_research',authorized=True,problem=problem,seed=2026)
            cp=output/f'q{problem}_functional.pt';save_checkpoint(cp,model,opt,config,'SMOKE_ONLY',0,ppo)
            clone=CandidatePolicy().to(device);clone_opt=torch.optim.Adam(clone.parameters(),lr=3e-4)
            load_checkpoint(cp,clone,clone_opt,True)
            assert all(torch.equal(v,clone.state_dict()[k]) for k,v in model.state_dict().items())
            assert len(clone_opt.state)==len(opt.state)>0
            # 恢复之后同一批次执行相同更新，模型与optimizer状态必须一致。
            batch=list(samples[0][0][:32]);random.seed(10);bc_update(model,opt,list(batch),device,1,32)
            random.seed(10);bc_update(clone,clone_opt,list(batch),device,1,32)
            assert all(torch.allclose(v,clone.state_dict()[k],atol=1e-7,rtol=1e-6) for k,v in model.state_dict().items())
            cpu=CandidatePolicy().eval();cpu.load_state_dict(model.state_dict());model.eval()
            with torch.no_grad():
                gpu_logits=model(s,mask)[0].cpu();cpu_logits=cpu({k:v.cpu() for k,v in s.items()},mask.cpu())[0]
            finite=mask.cpu();difference=float((gpu_logits[finite]-cpu_logits[finite]).abs().max())
            assert difference<1e-4,difference
            assert torch.equal(gpu_logits.argmax(-1),cpu_logits.argmax(-1))
            evaluation=paired_evaluation(pool,problem,range(900,904),model)
            atomic_json(output/f'q{problem}_paired.json',evaluation)
            if evaluation['student']['completion_rate']!=1:raise RuntimeError('smoke validation incomplete')
            elapsed=time.perf_counter()-t
            report['problems'][str(problem)]=dict(status='PASS',baseline=summary,bc=bc,bc_loss_before=before,bc_loss_after=after,
                ppo=ppo,sampled=sampled,checkpoint_resume='PASS',cpu_gpu_logit_max_error=difference,cpu_gpu_actions_equal=True,
                paired_delta_s=evaluation['mean_paired_delta_s'],elapsed_s=elapsed,parameters=sum(p.numel() for p in model.parameters()),
                note='SMOKE_ONLY，不用于正式结果；此处通过不等于策略收益通过')
            atomic_json(output/'report.json',report);print(json.dumps(report['problems'][str(problem)],ensure_ascii=False),flush=True)
    report.update(status='PASS',elapsed_s=time.perf_counter()-started)
    atomic_json(output/'report.json',report)
    print('SMOKE PASS',flush=True)
if __name__=='__main__':main()
