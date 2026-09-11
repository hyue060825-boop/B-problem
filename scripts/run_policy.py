#!/usr/bin/env python3
"""Run a trained policy against a loopback simulator endpoint."""
import argparse, json, sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bsim.client import RobotClient
from solution.control.controller import Controller
from solution.rl.environment import features, model_state
from solution.rl.model import CandidatePolicy

def load_policy(path, device):
    data = torch.load(path, map_location=device, weights_only=False)
    if data.get('features') != 'normalized-public-v2':
        raise ValueError('checkpoint feature version mismatch')
    if data.get('profile') != 'research-v1-20260911':
        raise ValueError('checkpoint research profile mismatch')
    model = CandidatePolicy().to(device)
    model.load_state_dict(data['model'])
    model.eval()
    return model, data.get('config', {})

def main():
    ap = argparse.ArgumentParser(description='Run a trained policy on a loopback endpoint')
    ap.add_argument('--problem', type=int, choices=(3, 4), required=True)
    ap.add_argument('--checkpoint', type=Path, required=True)
    ap.add_argument('--base-url', default='http://127.0.0.1:2026')
    ap.add_argument('--robot-id', required=True)
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--max-macros', type=int, default=400)
    args = ap.parse_args()
    if not args.base_url.startswith('http://127.0.0.1:'):
        raise SystemExit('BLOCKED: only a local loopback endpoint is permitted')
    if not args.checkpoint.is_file():
        raise SystemExit(f'checkpoint not found: {args.checkpoint}')
    device = torch.device(args.device)
    if device.type == 'cuda' and not torch.cuda.is_available():
        raise SystemExit('CUDA requested but unavailable')
    model, train_config = load_policy(args.checkpoint, device)
    if int(train_config.get('problem', args.problem)) != args.problem:
        raise SystemExit('checkpoint problem does not match --problem')
    client = RobotClient(args.base_url, args.robot_id, timeout=5, retries=2)
    controller = Controller(args.problem)
    code, entered = client.act('/enter')
    if code != 200 or entered.get('accepted') is not True:
        raise SystemExit(f'/enter rejected: HTTP {code} {entered}')
    controller.remaining_real_s = float(entered['remaining_real_duration_s'])
    print(json.dumps({'status': 'ENTERED', 'remaining_real_duration_s': controller.remaining_real_s}, ensure_ascii=False), flush=True)
    with torch.inference_mode():
        for macro in range(args.max_macros):
            actions = controller.legal_actions()
            if not actions:
                raise RuntimeError('controller has no legal action before exit')
            state = model_state(features(controller, actions))
            tensors = {k: torch.from_numpy(v).unsqueeze(0).to(device) for k, v in state.items()}
            logits, _ = model(tensors, torch.ones((1, len(actions)), dtype=torch.bool, device=device))
            action = actions[int(logits.argmax(dim=-1).item())]
            def request(path, position, channel):
                status, body = client.act(path, position, channel)
                if status != 200 or body.get('accepted') is not True:
                    raise RuntimeError(f'{path} rejected: HTTP {status} {body}')
                controller.virtual_time = float(body['virtual_time_s'])
                return body
            controller.execute(action, request)
            print(json.dumps({'status': 'ACTION', 'macro': macro + 1, 'kind': action.kind,
                              'position': action.position, 'channel': action.channel,
                              'virtual_time_s': controller.virtual_time}, ensure_ascii=False), flush=True)
            if action.kind == 'EXIT':
                print(json.dumps({'status': 'EXITED', 'history_entries': len(client.history())}, ensure_ascii=False), flush=True)
                return
    raise SystemExit('macro budget exhausted before a certified exit')

if __name__ == '__main__':
    main()
