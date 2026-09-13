#!/usr/bin/env python3
"""Windows/Linux loopback runner with checkpoint-matched public-v2 runtime."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import unicodedata
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_policy(path, device):
    import torch
    # Only load trusted training/export artifacts. Original checkpoints contain
    # NumPy and RNG metadata, so explicitly request the full checkpoint format.
    data = torch.load(path, map_location='cpu', weights_only=False)
    if data.get('features') != 'normalized-public-v2':
        raise ValueError('此部署入口要求 normalized-public-v2 权重；不能混用新版结构化模型。')
    if data.get('profile') != 'research-v1-20260911':
        raise ValueError('checkpoint research profile mismatch')
    runtime = ROOT/'deployment/runtime_public_v2'
    if not (runtime/'manifest.json').is_file():
        raise ValueError('缺少 deployment/runtime_public_v2；请复制完整部署包，不能只替换 pt。')
    declared = json.loads((runtime/'manifest.json').read_text(encoding='utf-8'))['files']
    recorded = data.get('provenance', {}).get('files', {})
    checked = 0
    for name, digest in declared.items():
        if sha(runtime/name) != digest:
            raise ValueError(f'部署代码校验失败：{name}；请从原 ZIP 重新解压。')
        if name in recorded and recorded[name] != digest:
            raise ValueError(f'权重与部署代码不匹配：{name}。')
        checked += name in recorded
    missing = [name for name in recorded if name.startswith(('solution/', 'bsim/')) and name not in declared]
    if missing or checked == 0:
        raise ValueError(f'权重没有匹配的运行源码：{missing}')
    # Prevent importing the current development controller/features by accident.
    sys.path.insert(0, str(runtime))
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('solution', 'bsim') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(runtime.resolve()):
                raise ValueError('进程已经导入其他版本的策略代码；请单独运行 scripts/run_policy.py。')
    from solution.rl.model import CandidatePolicy
    model = CandidatePolicy().to(device)
    model.load_state_dict(data['model'], strict=True)
    model.eval()
    if not all(torch.isfinite(p).all() for p in model.parameters()):
        raise ValueError('模型包含非有限参数。')
    return model, data.get('config', {})


def rejection_message(path, code, body, robot_id):
    base = f'{path} rejected: HTTP {code} {body}'
    if path == '/enter' and code == 200 and body.get('accepted') is False:
        return (base + '\n模型已加载；模拟器拒绝进入，本局尚未开始模型决策。\n'
                f'本次发送 arena_id="default", robot_id={robot_id!r}。\n'
                '请核对 robot_id 与官方软件当前登录参赛队号逐字一致；如本局已有程序成功 /enter，'
                '请在官方界面结束该局并新开一局，等待倒计时结束、接口就绪后只启动一个策略进程。\n'
                '官方此响应未给出具体原因，程序无法判断是队号不符还是重复进入；不要只反复重跑同一局。')
    return base


def run(args, model, config, emit):
    import torch
    from bsim.client import RobotClient
    from solution.control.controller import Controller
    from solution.rl.environment import features, model_state
    ctrl = Controller(args.problem)
    ctrl.remaining_real_s = 1200.
    # A real public initial state validates model/feature compatibility offline.
    actions = ctrl.legal_actions()
    state = model_state(features(ctrl, actions))
    tensors = {k: torch.from_numpy(v).unsqueeze(0).to(args.device) for k,v in state.items()}
    with torch.inference_mode():
        logits, value = model(tensors)
    if not torch.isfinite(logits).all() or not torch.isfinite(value).all():
        raise ValueError('初始模型输出非有限。')
    emit('MODEL_READY', problem=args.problem, checkpoint=str(args.checkpoint.resolve()),
         checkpoint_sha256=sha(args.checkpoint), candidate_dim=state['candidates'].shape[-1],
         feature_version='normalized-public-v2', device=str(args.device),
         initial_logits=logits.cpu().tolist()[0])
    if args.check_only:
        fixture_path=ROOT/'deployment/inference_fixtures.json'
        if fixture_path.exists():
            cases=json.loads(fixture_path.read_text(encoding='utf-8'))
            cases=[case for case in cases if case['checkpoint_sha256']==sha(args.checkpoint)]
            max_error=0.;near_ties=0
            for case in cases:
                ts={k:torch.tensor(v,dtype=torch.float32,device=args.device).unsqueeze(0) for k,v in case['state'].items()}
                with torch.inference_mode():actual,_=model(ts)
                expected=torch.tensor(case['logits'],device=args.device)
                if not torch.isfinite(actual).all() or not torch.allclose(actual[0],expected,atol=1e-4,rtol=1e-4):
                    raise ValueError('本地推理与服务器参考输出不一致。')
                max_error=max(max_error,float((actual[0]-expected).abs().max()))
                chosen=int(actual.argmax(-1).item())
                if chosen!=case['action']:
                    if float(expected.max()-expected[chosen])>2e-4+2e-4*float(expected.abs().max()):
                        raise ValueError('本地动作与服务器参考动作不一致。')
                    near_ties+=1
            emit('PARITY_CHECK',cases=len(cases),max_logit_error=max_error,near_tied_choices=near_ties,
                 message='匹配权重的参考观测回放' if cases else '无此权重的参考回放；仅基础自检')
        emit('CHECK_ONLY_OK', message='离线自检通过；未连接或进入模拟器。')
        return
    client = RobotClient(args.base_url, args.robot_id, timeout=args.timeout, retries=2)
    http = client._transport
    def logged_transport(path, raw):
        # Record before sending; retain the request_id even after an ambiguous
        # network result. RobotClient retries exactly the same raw bytes.
        emit('REQUEST', path=path, request=json.loads(raw))
        try:
            status, body = http(path, raw)
        except Exception as exc:
            emit('TRANSPORT_ERROR', path=path, error=str(exc))
            raise
        emit('RESPONSE', path=path, http_status=status, response=body)
        return status, body
    client._transport = logged_transport
    before_enter = time.monotonic()
    code, entered = client.act('/enter')
    if code != 200 or entered.get('accepted') is not True:
        raise RuntimeError(rejection_message('/enter', code, entered, args.robot_id))
    remaining = float(entered['remaining_real_duration_s'])
    if not math.isfinite(remaining) or not 0 <= remaining <= 1200:
        raise ValueError('模拟器 remaining_real_duration_s 不合法。')
    deadline = before_enter + remaining  # conservatively include response latency
    emit('ENTERED', remaining_real_duration_s=remaining)
    def request(path, position, channel):
        ctrl.remaining_real_s = max(0., deadline-time.monotonic())
        if ctrl.remaining_real_s <= 0:
            raise RuntimeError('现实时间预算已耗尽。')
        status, body = client.act(path, position, channel)
        if status != 200 or body.get('accepted') is not True:
            raise RuntimeError(rejection_message(path, status, body, args.robot_id))
        ctrl.virtual_time = float(body['virtual_time_s'])
        return body
    with torch.inference_mode():
        for macro in range(args.max_macros):
            ctrl.remaining_real_s = max(0., deadline-time.monotonic())
            if ctrl.remaining_real_s <= 0:
                raise RuntimeError('现实时间预算已耗尽。')
            actions = ctrl.legal_actions()
            if not actions:
                raise RuntimeError('控制器无合法动作；保留日志。')
            state = model_state(features(ctrl, actions))
            ts = {k: torch.from_numpy(v).unsqueeze(0).to(args.device) for k,v in state.items()}
            logits, value = model(ts)
            if not torch.isfinite(logits).all() or not torch.isfinite(value).all():
                raise RuntimeError('模型输出非有限；停止发送动作。')
            action = actions[int(logits.argmax(-1).item())]
            ctrl.execute(action, request)
            emit('ACTION', macro=macro+1, kind=action.kind, position=action.position,
                 channel=action.channel, virtual_time_s=ctrl.virtual_time)
            if action.kind == 'EXIT':
                emit('EXITED', requests=len(client.history()), virtual_time_s=ctrl.virtual_time)
                return
    raise RuntimeError('宏动作预算耗尽，尚未取得退出证书。')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    p = argparse.ArgumentParser(description='Q3/Q4 Windows 本地官方接口策略程序')
    p.add_argument('--problem', type=int, choices=(3,4), required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--base-url', default='http://127.0.0.1:2026')
    p.add_argument('--robot-id', required=True)
    p.add_argument('--device', default='cpu')
    p.add_argument('--max-macros', type=int, default=400)
    p.add_argument('--timeout', type=float, default=5.)
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--log-dir', type=Path, default=Path('results/rehearsal/policy-logs'))
    a = p.parse_args()
    url = urlsplit(a.base_url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path not in ('','/') or url.query or url.fragment or url.username:
        p.error('base-url 必须是本机回环 HTTP 地址。')
    if a.robot_id != a.robot_id.strip() or not 1 <= len(a.robot_id.encode('utf-8')) <= 64 or any(unicodedata.category(c) in ('Cc','Cf','Cs') for c in a.robot_id):
        p.error('robot-id 含空白或不可见字符，或长度非法；请使用当前登录参赛队号。')
    if a.max_macros < 1 or not math.isfinite(a.timeout) or a.timeout <= 0:
        p.error('max-macros 和 timeout 必须为正数。')
    a.log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    log = a.log_dir/f'q{a.problem}_{stamp}.jsonl'
    with log.open('x', encoding='utf-8') as stream:
        def emit(status, **data):
            line = json.dumps(dict(status=status, **data), ensure_ascii=False, allow_nan=False)
            stream.write(line+'\n');stream.flush()
            if status not in ('REQUEST', 'RESPONSE'):
                print(line, flush=True)
        try:
            import torch
            torch.set_num_threads(1)
            a.device = torch.device(a.device)
            if a.device.type == 'cuda' and not torch.cuda.is_available():
                raise RuntimeError('本机 CUDA 不可用，请用 --device cpu。')
            model, cfg = load_policy(a.checkpoint, a.device)
            if cfg.get('problem') != a.problem:
                raise ValueError(f'权重题号 {cfg.get("problem")} 与 --problem {a.problem} 不符。')
            run(a, model, cfg, emit)
            return 0
        except Exception as exc:
            emit('ERROR', message=str(exc), log=str(log.resolve()))
            return 2
        finally:
            print(f'日志：{log.resolve()}', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
