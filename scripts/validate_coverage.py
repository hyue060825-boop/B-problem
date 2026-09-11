#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from solution.coverage.certificates import check_omni_parameters, triangular_grid, verify_directional_certificate

parser = argparse.ArgumentParser()
parser.add_argument('--problem', choices=['3', '4'], required=True)
args = parser.parse_args()
if args.problem == '3':
    output = {'problem': 3, 'parameters': check_omni_parameters()}
else:
    grid = triangular_grid()
    output = {'problem': 4, 'grid_summary': {k: grid[k] for k in ('spacing_m', 'triangle_count', 'vertex_count', 'diameter_checks')}, 'certified': verify_directional_certificate(grid)}
print(json.dumps(output, ensure_ascii=False, indent=2))
