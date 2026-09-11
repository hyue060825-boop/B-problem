#!/usr/bin/env python3
"""Evaluate one checkpoint on independent LOCAL-RESEARCH seeds."""
import argparse, json, multiprocessing as mp, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from solution.rl.model import CandidatePolicy
from solution.rl.training import load_checkpoint, paired_evaluation

def main():
    p=argparse.ArgumentParser();p.add_argument('--problem',type=int,required=True)
    p.add_argument('--checkpoint',required=True);p.add_argument('--seed',type=int,default=900000)
    p.add_argument('--episodes',type=int,default=32);p.add_argument('--output')
    a=p.parse_args();model=CandidatePolicy();load_checkpoint(a.checkpoint,model)
    with ProcessPoolExecutor(4,mp_context=mp.get_context('spawn')) as pool:
        result=paired_evaluation(pool,a.problem,range(a.seed,a.seed+a.episodes),model)
    summary={'checkpoint':a.checkpoint,'problem':a.problem,'seed_start':a.seed,'episodes':a.episodes,
             'baseline_completion':result['baseline']['completion_rate'],
             'student_completion':result['student']['completion_rate'],
             'baseline_mean_virtual_s':result['baseline']['mean_virtual_s'],
             'student_mean_virtual_s':result['student']['mean_virtual_s'],
             'paired_delta_s':result['mean_paired_delta_s'],'selection_pass':result['selection_pass']}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if a.output: Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
