#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from solution.rl.training import train_bc

parser = argparse.ArgumentParser()
parser.add_argument('--config', required=True)
args = parser.parse_args()
status = train_bc(args.config)
print(json.dumps(status.__dict__, ensure_ascii=False, indent=2))
raise SystemExit(0 if status.status == 'NOT_RUN' else 2)
