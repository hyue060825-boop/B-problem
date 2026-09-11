#!/usr/bin/env python3
"""Deployment guard: endpoint and algorithm must be explicitly selected."""
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('--problem', choices=['3', '4'], required=True)
parser.add_argument('--policy', choices=['heuristic', 'bc', 'ppo'], required=True)
parser.add_argument('--base-url', required=True)
parser.add_argument('--robot-id', required=True)
args = parser.parse_args()
if not args.base_url.startswith('http://127.0.0.1:'):
    raise SystemExit('BLOCKED: deployment entry only permits an explicitly selected local loopback endpoint')
if args.policy != 'heuristic':
    raise SystemExit('NOT_RUN: no trained BC/PPO checkpoint is available')
print(json.dumps({'status': 'READY_FOR_LOCAL_CLIENT', 'problem': int(args.problem), 'policy': args.policy, 'base_url': args.base_url, 'robot_id': args.robot_id}, ensure_ascii=False, indent=2))
