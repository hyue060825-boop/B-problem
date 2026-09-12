#!/usr/bin/env python3
import argparse,json,multiprocessing as mp,time,sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.rl.environment import TrainingEnv,structural_model_state
from solution.rl.model import StructuralCandidatePolicy

MODEL=None
def init(path):
 global MODEL
 torch.set_num_threads(1); MODEL=StructuralCandidatePolicy().eval()
 d=torch.load(path,map_location='cpu',weights_only=False); MODEL.load_state_dict(d['model'])
def run(seed):
 e=TrainingEnv(4,int(seed),max_macros=400)
 while not e.done:
  st,aa=e.observe(structural=True); t={k:torch.from_numpy(v).unsqueeze(0) for k,v in st.items()}
  with torch.inference_mode(): logits,_=MODEL(t)
  e.step(aa[int(logits.argmax(-1).item())])
 return e.metrics()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--episodes',type=int,default=3000);p.add_argument('--seed',type=int,default=320000000);p.add_argument('--workers',type=int,default=32);p.add_argument('--checkpoint',required=True);a=p.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=False); seeds=list(range(a.seed,a.seed+a.episodes)); started=time.perf_counter()
 with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn'),initializer=init,initargs=(a.checkpoint,)) as pool:
  rows=list(pool.map(run,seeds,chunksize=4))
 old=json.load(open('runs/q34_3000_test_20260912/q4_best_samples.json'))
 om={int(x['seed']):x for x in old}; delta=np.array([r['virtual_time_s']-om[int(s)]['virtual_time_s'] for s,r in zip(seeds,rows)])
 report=dict(episodes=a.episodes,completed=sum(r['completion'] for r in rows),new_mean_virtual_s=float(np.mean([r['virtual_time_s'] for r in rows])),old_mean_virtual_s=float(np.mean([om[s]['virtual_time_s'] for s in seeds])),mean_delta_s=float(delta.mean()),ci95_s=float(1.96*delta.std(ddof=1)/np.sqrt(len(delta))),faster=int((delta<0).sum()),slower=int((delta>0).sum()),elapsed_s=time.perf_counter()-started,checkpoint=a.checkpoint)
 (out/'summary.json').write_text(json.dumps(report,indent=2)); (out/'samples.json').write_text(json.dumps(rows)); print(json.dumps(report,indent=2))
if __name__=='__main__':main()
