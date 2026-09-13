"""Q3 batched float64 physics with Decimal fallback at discrete boundaries.

Bounded fast domain: coordinates <= 1e6 m; IEEE double arithmetic errors in
distance/time scaling are guarded with 128 ulps (incl. decimal-input conversion).
Angle half-cent boundaries use 1e-7 degrees, audited against CPU libm/Decimal.
Outside the domain or inside a guard, use the complete reference transition.
No approximate result is used to eliminate candidates.
"""
from dataclasses import asdict
import hashlib
import json
import time
import numpy as np
import torch
from bsim.reference import State

BACKEND_VERSION='q3-tensor-f64-guarded-v1'


def hypothesis_hash(kernel):
    field=kernel.noise;fallback=getattr(field,'fallback',field)
    value=dict(sources=[asdict(s) for s in kernel.scenario.sources],
               phases=fallback.phases.tolist(),k=fallback.k.tolist(),kind=fallback.kind,
               observed=sorted([list(k)+[v] for k,v in getattr(field,'observed',{}).items()]))
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


class Q3TensorKernel:
    def __init__(self,kernels,device='cuda:0',states=None):
        self.device=torch.device(device);self.kernels=kernels;n=len(kernels)
        xy=np.zeros((n,20,2));radius=np.zeros((n,20));exists=np.zeros((n,20),bool)
        phases=np.zeros((n,20));freq=np.zeros((n,2));kind=np.zeros(n,np.int64)
        self.overrides=[]
        for i,kernel in enumerate(kernels):
            if any(s.kind!='omni' for s in kernel.scenario.sources):raise ValueError('Q3 only')
            if len(kernel.sources)!=len(kernel.scenario.sources):raise ValueError('duplicate channels')
            for s in kernel.scenario.sources:xy[i,s.channel-1]=[s.x,s.y];radius[i,s.channel-1]=s.radius;exists[i,s.channel-1]=True
            f=getattr(kernel.noise,'fallback',kernel.noise)
            phases[i]=f.phases;freq[i]=f.k;kind[i]={'smooth':0,'zero':1,'extreme':2}[f.kind]
            self.overrides.append(getattr(kernel.noise,'observed',{}))
        tensor=lambda x:torch.as_tensor(x,device=self.device)
        self.xy=tensor(xy);self.radius=tensor(radius);self.source_exists=tensor(exists)
        self.phases=tensor(phases);self.freq=tensor(freq);self.kind=tensor(kind)
        states=states or [State() for _ in kernels]
        self.host_states=list(states)
        self.position=tensor(np.array([s.position for s in states],np.float64))
        self.channel=tensor(np.array([s.channel-1 for s in states],np.int64))
        self.virtual_us=tensor(np.array([s.virtual_us for s in states],np.int64))
        self.cleared=tensor(np.array([[c+1 in s.cleared for c in range(20)] for s in states],bool))
        self.active=tensor(np.array([s.virtual_us<360000000000 for s in states],bool))
        self.stats=dict(operations=0,reference_fallbacks=0,kernel_s=0.,transfer_and_decode_s=0.,reference_s=0.,batch_sizes=[])

    def step(self,ids,requests):
        """One physical operation per active branch; only public response leaves."""
        if len(set(ids))!=len(ids):raise ValueError('duplicate branch in batch')
        if not ids:return []
        t=time.perf_counter();dev=self.device
        idx=torch.as_tensor(ids,device=dev,dtype=torch.long)
        q_np=np.array([r[1] for r in requests],np.float64)
        ch_np=np.array([r[2]-1 for r in requests],np.int64)
        if not np.isfinite(q_np).all() or np.any((ch_np<0)|(ch_np>=20)):raise ValueError('invalid request')
        ops=np.array([0 if r[0]=='/measure' else 1 if r[0]=='/clear' else -1 for r in requests],np.int64)
        if np.any(ops<0):raise ValueError('kernel supports measure/clear; certified exit handled by controller')
        q=torch.as_tensor(q_np,device=dev);ch=torch.as_tensor(ch_np,device=dev);op=torch.as_tensor(ops,device=dev)
        over=np.array([self.overrides[i].get((int(c)+1,float(p[0]),float(p[1])),np.nan) for i,c,p in zip(ids,ch_np,q_np)])
        overrides=torch.as_tensor(over,device=dev)
        if dev.type=='cuda':begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True);begin.record()
        old=self.position[idx];alive=self.active[idx]
        delta=self.xy[idx,ch]-q;distance=torch.linalg.vector_norm(delta,dim=-1)
        movement=torch.linalg.vector_norm(q-old,dim=-1)*200000
        phase=self.phases[idx,ch]
        error=.65*torch.sin(q[:,0]*self.freq[idx,0]+phase)+.35*torch.cos(q[:,1]*self.freq[idx,1]-phase)
        error=torch.where(self.kind[idx]==1,0.,error)
        error=torch.where(self.kind[idx]==2,torch.sign(torch.sin(phase)),error)
        error=torch.where(torch.isfinite(overrides),overrides,error)
        angle=torch.remainder(torch.rad2deg(torch.atan2(delta[:,1],delta[:,0]))+error,360.)
        rounded=torch.remainder(torch.floor(angle*100+.5)/100,360.)
        present=self.source_exists[idx,ch]&~self.cleared[idx,ch]
        visible=present&(distance<=self.radius[idx,ch]);near=visible&(distance<=5)
        success=present&(distance<=20)
        # codes: 0 no_signal, 1 near, 2 direction, 3 failed clear, 4 success.
        code=torch.where(op==0,torch.where(visible,torch.where(near,1,2),0),torch.where(success,4,3))
        dt=torch.floor(movement+.5).long()+torch.where(op==0,5000000+1000000*(ch!=self.channel[idx]),torch.where(success,5000000,3000000))
        eps=torch.finfo(torch.float64).eps
        scale=torch.maximum(q.abs().amax(-1),torch.maximum(old.abs().amax(-1),self.xy[idx,ch].abs().amax(-1))).clamp_min(1.)
        guard=128*eps*scale
        distance_guard=((distance-5).abs()<=guard)|((distance-20).abs()<=guard)|((distance-self.radius[idx,ch]).abs()<=guard)
        round_guard=(torch.remainder(movement,1)-.5).abs()<=128*eps*(scale*200000).clamp_min(1.)
        angle_guard=(torch.remainder(angle*100,1)-.5).abs()<=1e-5
        fallback=distance_guard|round_guard|((code==2)&angle_guard)|(scale>1e6)|~torch.isfinite(movement)
        elapsed=self.virtual_us[idx]+torch.where(alive,dt,0)
        packed=torch.stack([code.double(),rounded,elapsed.double(),fallback.double(),alive.double()],-1)
        if dev.type=='cuda':end.record()
        host=packed.cpu().numpy()
        if dev.type=='cuda':self.stats['kernel_s']+=begin.elapsed_time(end)/1000
        responses=[];new_cleared=[];corrected=[];ref_started=time.perf_counter()
        for j,(i,request) in enumerate(zip(ids,requests)):
            path,p,c=request;state=self.host_states[i];code_i,ang,us,fallback_i,is_alive=host[j]
            if not is_alive:
                responses.append(None);new_cleared.append(list(c0+1 in state.cleared for c0 in range(20)));corrected.append(state);continue
            if fallback_i:
                state,result=self.kernels[i].transition(state,path,tuple(p),int(c));self.stats['reference_fallbacks']+=1
            else:
                code_i=int(code_i)
                result=({'measure_result':['no_signal','near','direction'][code_i]} if path=='/measure'
                        else {'clear_result':'success' if code_i==4 else 'no_target_in_range'})
                if code_i==2:result['svd_deg']=round(float(ang),2)
                state=State(tuple(p),int(c) if path=='/measure' else state.channel,int(us),state.cleared|{int(c)} if code_i==4 else state.cleared)
            corrected.append(state);new_cleared.append([c0+1 in state.cleared for c0 in range(20)])
            responses.append(dict(accepted=True,real_timestamp_ms=0,virtual_time_s=state.virtual_us/1e6,**result))
        self.stats['reference_s']+=time.perf_counter()-ref_started
        for i,state in zip(ids,corrected):self.host_states[i]=state
        self.position[idx]=torch.as_tensor(np.array([s.position for s in corrected]),device=dev)
        self.channel[idx]=torch.as_tensor([s.channel-1 for s in corrected],device=dev)
        self.virtual_us[idx]=torch.as_tensor([s.virtual_us for s in corrected],device=dev)
        self.cleared[idx]=torch.as_tensor(new_cleared,device=dev)
        self.active[idx]=alive& (self.virtual_us[idx]<360000000000)
        self.stats['operations']+=sum(int(row[4]) for row in host);self.stats['batch_sizes'].append(len(ids))
        self.stats['transfer_and_decode_s']+=time.perf_counter()-t
        return responses


class BatchedHistoryConsistency:
    def __init__(self,device='cuda:0'):self.device=device;self.stats={}

    def validate(self,kernels,histories):
        if len(kernels)!=len(histories):raise ValueError('history batch length')
        engine=Q3TensorKernel(kernels,self.device);valid=np.ones(len(kernels),bool)
        physical=[[r for r in h if r['path'] in ('/measure','/clear')] for h in histories]
        for step in range(max(map(len,physical),default=0)):
            ids=[i for i,h in enumerate(physical) if step<len(h)]
            rows=[physical[i][step] for i in ids]
            answers=engine.step(ids,[(r['path'],tuple(r['position']),r['channel']) for r in rows])
            for i,row,answer in zip(ids,rows,answers):
                if answer is None:valid[i]=False;continue
                keys=('measure_result','svd_deg') if row['path']=='/measure' else ('clear_result',)
                if any(answer.get(k)!=row['response'].get(k) for k in keys) or round(answer['virtual_time_s']*1e6)!=round(row['response']['virtual_time_s']*1e6):valid[i]=False
        self.stats=engine.stats
        return valid.tolist(),engine.host_states
