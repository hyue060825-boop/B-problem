#!/usr/bin/env python3
import argparse,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from solution.rl.training import run_training
p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
def main():
    c=json.loads(Path(a.config).read_text()); out=Path(c['output']);out.mkdir(parents=True,exist_ok=True)
    try:
        run_training(c)
    except Exception as e:
        (out/'FATAL.txt').write_text(type(e).__name__+': '+str(e)+'\n'+traceback.format_exc())
        raise

if __name__ == '__main__':
    main()
