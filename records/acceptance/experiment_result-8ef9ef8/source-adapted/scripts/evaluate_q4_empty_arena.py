"""Zero-source diagnostic fixture: measure the original Q4 absence certificate cost."""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import torch

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'deployment/runtime_public_v2'
sys.path.insert(0,str(RUNTIME))
from bsim.clocks import ManualClock
from bsim.client import public_response
from bsim.noise import Numerics
from bsim.protocol import encode
from bsim.reference import ReferenceKernel
from bsim.research import FixedField
from bsim.scenarios import Scenario
from bsim.session import Session
from solution.control.controller import Controller
from solution.rl.environment import features,model_state
from solution.rl.model import CandidatePolicy
from solution.rl.training import verify_checkpoint_code


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint',default=str(ROOT/'runs/q4_legacy_deadline_20260913/best.pt'))
    ap.add_argument('--output',default=str(ROOT/'runs/q4_empty_arena_20260913'))
    args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    checkpoint=Path(args.checkpoint)
    torch.set_num_threads(1)
    data=torch.load(checkpoint,map_location='cpu',weights_only=False)
    verify_checkpoint_code(data)
    for p,h in data['provenance']['files'].items():
        if p.startswith(('solution/','bsim/')):
            assert hashlib.sha256((RUNTIME/p).read_bytes()).hexdigest()==h,p
    model=CandidatePolicy().eval();model.load_state_dict(data['model'],strict=True)
    # Explicit fixture: the research generator intentionally requires at least
    # two sources for a mixed directional/omni Q4 draw and is not used here.
    scenario=Scenario('LOCAL-Q4-EMPTY-ARENA-DIAGNOSTIC',4,'test_fixture',())
    numerics=Numerics('TEST_INPUT','half_up','half_up','invisible',0.)
    session=Session(ReferenceKernel(scenario,FixedField(20260913,'zero'),numerics),ManualClock(),'LOCAL-EMPTY')
    session.ready_fixture()
    controller=Controller(4)
    events=[];actions=[];rid=0;exit_verified=False
    started=time.perf_counter()
    def request(path,position,channel):
        nonlocal rid,exit_verified
        rid+=1
        if path=='/exit':
            assert controller.exit_allowed()
            assert all(s.status=='ABSENT_CERTIFIED' and set(controller.station_names)<=s.covered_stations for s in controller.channels.values())
            exit_verified=True
        packet=dict(arena_id='default',robot_id='LOCAL-EMPTY',request_id=str(rid))
        if position is not None:packet.update(position=dict(x=float(position[0]),y=float(position[1])),channel=int(channel))
        old=session.state
        status,response=session.request('POST',path,{'Content-Type':'application/json'},encode(packet))
        public_response(path,response)
        assert status==200 and response['accepted'] is True
        end=session.state.virtual_us/1e6;begin=old.virtual_us/1e6
        distance=math.dist(old.position,position) if position is not None else 0.
        measure=5. if path=='/measure' else 0.
        switch=float(path=='/measure' and channel!=old.channel)
        assert path!='/clear','No source means no positive observation or legal clear'
        events.append(dict(path=path,request=packet,response=response,start_s=begin,end_s=end,
                           path_length_m=distance,move_s=end-begin-measure-switch,measure_s=measure,switch_s=switch))
        return response
    request('/enter',None,None)
    for step in range(400):
        controller.remaining_real_s=max(0.,1200-(time.perf_counter()-started))
        legal=controller.legal_actions()
        state=model_state(features(controller,legal))
        with torch.inference_mode():
            logits,_=model({k:torch.from_numpy(v).unsqueeze(0) for k,v in state.items()})
        assert torch.isfinite(logits).all()
        chosen=legal[int(logits.argmax(-1))]
        before=controller.virtual_time
        controller.execute(chosen,request)
        actions.append(dict(index=step,kind=chosen.kind,station=chosen.station,position=chosen.position,
                            channels=chosen.channels,start_s=before,end_s=controller.virtual_time))
        if chosen.kind=='EXIT':break
    assert exit_verified and not controller.discovered
    measures=[e for e in events if e['path']=='/measure']
    assert all(e['response']['measure_result']=='no_signal' for e in measures)
    assert len(measures)==len(controller.stations)*20
    summary=dict(checkpoint=str(checkpoint.resolve()),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                 scenario=asdict(scenario),note='Zero sources is a diagnostic test fixture, outside official 10–16-source cases; hidden zero count not given to policy.',
                 completed_with_full_absence_certificate=exit_verified,source_count=0,
                 station_count=len(controller.stations),visited_station_count=len(controller.visited),
                 certified_channels=sum(s.status=='ABSENT_CERTIFIED' for s in controller.channels.values()),
                 measurements=len(measures),no_signal_measurements=len(measures),
                 channel_switches=int(sum(e['switch_s'] for e in events)),
                 path_length_m=sum(e['path_length_m'] for e in events),
                 move_s=sum(e['move_s'] for e in events),measure_s=sum(e['measure_s'] for e in events),
                 switch_s=sum(e['switch_s'] for e in events),total_virtual_s=session.state.virtual_us/1e6,
                 macro_actions=len(actions),wall_s=time.perf_counter()-started,
                 covered_stations_per_channel={str(c):sorted(s.covered_stations) for c,s in controller.channels.items()},
                 inference_device='cpu',remaining_wall_feature='live; matching the original baseline runtime')
    assert abs(summary['total_virtual_s']-sum(summary[k] for k in ('move_s','measure_s','switch_s'))) < 1e-6
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events),encoding='utf-8')
    (out/'actions.json').write_text(json.dumps(actions,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'scenario.json').write_text(json.dumps(asdict(scenario),indent=2,ensure_ascii=False),encoding='utf-8')
    report=f'''# Q4 无干扰源样例：完整无源确认成本

使用原最佳基线 `runs/q4_legacy_deadline_20260913/best.pt`，未使用正在续训的中间权重。原冻结控制器、原证书和 greedy 模型选择均保留。

这个样例的源数为 0，标记为 test_fixture，不属于官方 10–16 源的常规样例。零源真值仅供模拟器和事后核验，策略只收到公开反馈。

取得完整无源证书并退出的虚拟时间：**{summary['total_virtual_s']:.6f} 秒**，约 {summary['total_virtual_s']/60:.2f} 虚拟分钟。

| 项目 | 结果 |
|---|---:|
| 认证站点访问数 | {summary['visited_station_count']} |
| 全部认证无源的频道 | {summary['certified_channels']} |
| 无信号测量次数 | {summary['measurements']} |
| 换频道次数 | {summary['channel_switches']} |
| 移动距离 | {summary['path_length_m']:.3f} 米 |
| 移动耗时 | {summary['move_s']:.6f} 秒 |
| 测量耗时 | {summary['measure_s']:.0f} 秒 |
| 换频耗时 | {summary['switch_s']:.0f} 秒 |

核验了 20 个频道分别在全部 31 个认证站点取得 no_signal，随后才接受退出。全程没有清除动作，总时间全部用于覆盖与无源确认。

这里的“保守”指继续完成现有充分证书，没有使用连续无信号提前退出；该单例实测不是所有路线/策略状态的数学最坏时间上界。零源诊断也不意味着常规样例可以直接从总耗时扣除这个数，因为发现、定位、清除和覆盖会共享路线。

逐请求轨迹保存在 events.jsonl，宏动作路线保存在 actions.json，场景及完整证书统计保存在 scenario.json 和 summary.json。正在运行的一小时八卡训练未修改或中断。
'''
    (out/'report.md').write_text(report,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='covered_stations_per_channel'},indent=2,ensure_ascii=False))


if __name__=='__main__':main()
