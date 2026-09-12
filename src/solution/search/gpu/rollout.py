"""Active-branch batching; CPU geometric coroutines, GPU physics and policy."""
from copy import deepcopy
import math
import time
import numpy as np
import torch
from bsim.reference import State
from solution.rl.environment import features,model_state
from solution.rl.training import collate
from solution.search.belief import action_dict,action_id,calls_from,restore_controller
from .kernel import Q3TensorKernel,BatchedHistoryConsistency


def macro_requests(controller,action):
    """Same primitive order/early stopping as Controller.execute; tested in replay."""
    c=controller
    def measure(p,ch,station=None):
        r=yield ('/measure',p,ch)
        c.virtual_time=r['virtual_time_s'];c.observe(ch,p,r['measure_result'],r.get('svd_deg'),station)
        if r['measure_result']=='near':
            r=yield ('/clear',p,ch);c.virtual_time=r['virtual_time_s'];c.clear_result(ch,r['clear_result']=='success',p,True)
    if action.kind=='COVER':
        channels=sorted(action.channels,reverse=bool(action.station%2))
        if c.current_channel in channels:channels.remove(c.current_channel);channels.insert(0,c.current_channel)
        for ch in channels:
            if c.channels[ch].status not in ('CLEARED','ABSENT_CERTIFIED'):
                yield from measure(action.position,ch,c.station_names[action.station])
        c.visited.add(action.station)
    elif action.kind=='LOCALIZE':
        c.channels[action.channel].localizations+=1
        yield from measure(action.position,action.channel)
    elif action.kind=='CLEAR':
        cert=c.channels[action.channel].region.certificate(action.position)
        if not cert or not cert['safe']:raise RuntimeError('clear certificate invalid')
        r=yield ('/clear',action.position,action.channel);c.virtual_time=r['virtual_time_s']
        c.clear_result(action.channel,r['clear_result']=='success',action.position,True)
    elif action.kind=='PROBE_CLEAR':
        points=list(c.channels[action.channel].cover_cache or c.channels[action.channel].region.clear_cover())
        while points:
            j=min(range(len(points)),key=lambda i:math.dist(c.position,points[i]));p=points.pop(j)
            r=yield ('/clear',p,action.channel);c.virtual_time=r['virtual_time_s']
            c.clear_result(action.channel,r['clear_result']=='success',p)
            if r['clear_result']=='success':break
        else:raise RuntimeError('clear cover exhausted')
    elif action.kind=='EXIT':
        if not c.exit_allowed():raise RuntimeError('missing public exit certificate')
    else:raise ValueError('macro kind')
    c.steps+=1


class BatchedPolicyEvaluator:
    def __init__(self,model,device):
        self.device=torch.device(device);self.model=deepcopy(model).to(self.device).eval()
        self.cpu=deepcopy(model).cpu().eval();self.stats=dict(batches=[],inference_s=0.,transfer_s=0.,ties=0)

    def choose(self,controllers,actions):
        rows=[dict(state=model_state(features(c,a))) for c,a in zip(controllers,actions)]
        t=time.perf_counter();state,mask=collate(rows,self.device);self.stats['transfer_s']+=time.perf_counter()-t
        if self.device.type=='cuda':start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True);start.record()
        with torch.inference_mode():logits,_=self.model(state,mask)
        if self.device.type=='cuda':end.record()
        values=logits.cpu().numpy()
        if self.device.type=='cuda':self.stats['inference_s']+=start.elapsed_time(end)/1000
        else:self.stats['inference_s']+=time.perf_counter()-t
        result=[]
        for i,aa in enumerate(actions):
            x=values[i,:len(aa)];order=np.argsort(x)
            # Float32 batch/CUDA roundoff: near ties use identical CPU single-row
            # baseline inference. Tolerance is checked in the batch parity suite.
            if len(x)>1 and x[order[-1]]-x[order[-2]]<=2e-5:
                single,one_mask=collate([rows[i]],'cpu')
                with torch.inference_mode():cpu_logits,_=self.cpu(single,one_mask)
                result.append(int(cpu_logits.argmax(-1)));self.stats['ties']+=1
            else:result.append(int(x.argmax()))
        self.stats['batches'].append(len(rows));return result


def batched_rollouts(specs,model,device='cuda:0',physics='tensor',max_macros=400,max_seconds=120.,max_expansions=20000):
    """spec=(public,hypothesis,first_action_id,stable_branch_id), no actual world."""
    started=time.perf_counter();controllers=[restore_controller(s[0]) for s in specs]
    kernels=[s[1] for s in specs];histories=[calls_from(s[0]) for s in specs]
    if physics=='tensor':
        checker=BatchedHistoryConsistency(device);valid,states=checker.validate(kernels,histories)
        if not all(valid):raise ValueError('GPU full public history consistency failed')
        engine=Q3TensorKernel(kernels,device,states)
    else:
        from solution.search.belief import validate_world
        states=[]
        for k,h in zip(kernels,histories):
            if not validate_world(k,h):raise ValueError('CPU history inconsistent')
            state=State()
            for r in h:
                if r['path'] in ('/measure','/clear'):state,_=k.transition(state,r['path'],tuple(r['position']),r['channel'])
            states.append(state)
        checker=None;engine=None
    evaluator=BatchedPolicyEvaluator(model,device);n=len(specs);traces=[[] for _ in specs];primitives=[[] for _ in specs]
    pending={};generators={};current={};finished={};geometry_s=0.;cpu_physics_s=0.
    roots=[s[3][0] for s in specs];expanded={r:0 for r in roots}
    def finish(i,reason,success=False):
        state=engine.host_states[i] if engine else states[i]
        success=success and len(state.cleared)==len(kernels[i].sources)
        finished[i]=dict(branch_id=specs[i][3],completion=success,cost_s=controllers[i].virtual_time-restore_start[i],
                         reason=reason,trace=traces[i],primitives=primitives[i])
        pending.pop(i,None);generators.pop(i,None)
    restore_start=[c.virtual_time for c in controllers]
    def begin_macro(i,a):
        c=controllers[i];current[i]=a;g=macro_requests(c,a);generators[i]=g
        try:pending[i]=next(g)
        except StopIteration:
            traces[i].append(dict(action=action_dict(a),virtual_time_s=c.virtual_time,error=None))
            finish(i,'certified_exit',a.kind=='EXIT')
    for i,c in enumerate(controllers):
        aa=c.legal_actions();a=next((a for a in aa if action_id(a)==specs[i][2]),None)
        if a is None:finish(i,'invalid_candidate')
        else:begin_macro(i,a)
    while len(finished)<n:
        if time.perf_counter()-started>max_seconds:
            for i in range(n):
                if i not in finished:finish(i,'search_timeout')
            break
        ids=sorted(pending);requests=[pending[i] for i in ids]
        if engine:responses=engine.step(ids,requests)
        else:
            t=time.perf_counter();responses=[]
            for i,(path,p,ch) in zip(ids,requests):
                if states[i].virtual_us>=360000000000:responses.append(None);continue
                states[i],result=kernels[i].transition(states[i],path,tuple(p),int(ch))
                responses.append(dict(accepted=True,real_timestamp_ms=0,virtual_time_s=states[i].virtual_us/1e6,**result))
            cpu_physics_s+=time.perf_counter()-t
        need_policy=[];t=time.perf_counter()
        for i,request,response in zip(ids,requests,responses):
            if response is None:finish(i,'virtual_timeout');continue
            primitives[i].append(dict(path=request[0],position=list(request[1]),channel=request[2],response=response))
            try:pending[i]=generators[i].send(response)
            except StopIteration:
                pending.pop(i,None);c=controllers[i]
                traces[i].append(dict(action=action_dict(current[i]),virtual_time_s=c.virtual_time,error=None));expanded[roots[i]]+=1
                if c.steps>=max_macros:finish(i,'macro_budget')
                elif expanded[roots[i]]>max_expansions:finish(i,'expansion_budget')
                else:need_policy.append(i)
        if need_policy:
            aa=[controllers[i].legal_actions() for i in need_policy];geometry_s+=time.perf_counter()-t
            if any(not a for a in aa):raise RuntimeError('empty candidate set')
            choices=evaluator.choose([controllers[i] for i in need_policy],aa)
            t=time.perf_counter()
            for i,actions,choice in zip(need_policy,aa,choices):begin_macro(i,actions[choice])
        geometry_s+=time.perf_counter()-t
    stats=dict(elapsed_s=time.perf_counter()-started,branches=n,geometry_s=geometry_s,cpu_physics_s=cpu_physics_s,
               kernel=engine.stats if engine else None,history=checker.stats if checker else None,policy=evaluator.stats,
               device=str(device),physics=physics,peak_cuda_bytes=torch.cuda.max_memory_allocated(device) if torch.device(device).type=='cuda' else 0)
    return [finished[i] for i in range(n)],stats
