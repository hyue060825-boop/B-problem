"""真实BC/DAgger/PPO：完整回合采样，有限任务gamma=1，版本化特征及原子断点。"""
import os,time,json,random,hashlib,platform,subprocess
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import numpy as np
import torch
from solution.rl.model import CandidatePolicy,masked_distribution
from solution.rl.environment import TrainingEnv,model_state,FEATURE_VERSION
from bsim.research import PROFILE_VERSION

@dataclass(frozen=True)
class TrainingStatus:
    status:str
    reason:str
    checkpoint:str|None=None

def require_authorized_research(config):
    if config.get('profile')!='compatible_research' or not config.get('authorized',False):
        return TrainingStatus('BLOCKED','需用户明确授权使用相容研究分布')
    return None

def atomic_json(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False));tmp.replace(p)

def provenance():
    root=Path(__file__).resolve().parents[3]
    paths=list((root/'src/solution').rglob('*.py'))+list((root/'src/bsim').glob('*.py'))+list((root/'scripts').glob('*.py'))
    return dict(files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,profile=PROFILE_VERSION,features=FEATURE_VERSION)

def init_worker():
    torch.set_num_threads(1)
    global worker_model
    worker_model=CandidatePolicy().eval()

def rollout(job):
    problem,seed,weights,behavior,max_macros=job
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if 'worker_model' not in globals():init_worker()
    if weights is not None:worker_model.load_state_dict(weights)
    env=TrainingEnv(problem,seed,max_macros=max_macros);steps=[]
    while not env.done:
        started=time.perf_counter()
        state,actions=env.observe()
        teacher=env.controller.teacher_index(actions)
        if weights is None:
            chosen=teacher;logp=0.;value=0.
        else:
            tensors={k:torch.from_numpy(v).unsqueeze(0) for k,v in model_state(state).items()}
            with torch.no_grad():
                logits,val=worker_model(tensors)
                dist=masked_distribution(logits,torch.ones_like(logits,dtype=torch.bool))
                chosen=int(logits.argmax(-1)) if behavior=='greedy' else int(dist.sample())
                logp=float(dist.log_prob(torch.tensor([chosen])));value=float(val)
        env.decision_times.append(time.perf_counter()-started)
        reward,done=env.step(actions[chosen])
        steps.append(dict(state=model_state(state),action=chosen,teacher=teacher,old_logp=logp,value=value,reward=reward,done=done))
    # 宏动作奖励是该宏动作所有底层-DeltaT/100之和；失败包括限额耗尽，罚1000。
    return steps,env.metrics()

def collect(pool,problem,seeds,model=None,behavior='sample',max_macros=400):
    weights=None if model is None else {k:v.detach().cpu() for k,v in model.state_dict().items()}
    jobs=[(problem,int(seed),weights,behavior,max_macros) for seed in seeds]
    results=list(pool.map(rollout,jobs)) if pool else [rollout(j) for j in jobs]
    return results

def summarize(results):
    ms=[m for _,m in results];times=np.array([m['virtual_time_s'] for m in ms])
    return dict(episodes=len(ms),completion_rate=float(np.mean([m['completion'] for m in ms])),
                mean_virtual_s=float(times.mean()),median_virtual_s=float(np.median(times)),p95_virtual_s=float(np.percentile(times,95)),
                macro_steps=sum(len(s) for s,_ in results),failures=[m for m in ms if not m['completion']])

def collate(rows,device):
    max_a=max(len(r['state']['candidates']) for r in rows)
    state={key:torch.from_numpy(np.stack([r['state'][key] for r in rows])).to(device) for key in ('global','channels')}
    c=np.zeros((len(rows),max_a,11),np.float32);mask=np.zeros((len(rows),max_a),bool)
    for i,r in enumerate(rows):
        n=len(r['state']['candidates']);c[i,:n]=r['state']['candidates'];mask[i,:n]=True
    state['candidates']=torch.from_numpy(c).to(device)
    return state,torch.from_numpy(mask).to(device)

def checked_step(loss,model,optimizer):
    if not torch.isfinite(loss):raise FloatingPointError('nonfinite loss')
    optimizer.zero_grad(set_to_none=True);loss.backward()
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),.5,error_if_nonfinite=True)
    optimizer.step()
    if not all(torch.isfinite(p).all() for p in model.parameters()):raise FloatingPointError('nonfinite weights')
    return float(norm)

def bc_update(model,opt,rows,device,epochs=4,batch_size=128):
    losses=[];norms=[];model.train()
    for _ in range(epochs):
        for start in range(0,len(rows),batch_size):
            batch=rows[start:start+batch_size];state,mask=collate(batch,device)
            logits,_=model(state,mask);target=torch.tensor([r['teacher'] for r in batch],device=device)
            loss=torch.nn.functional.cross_entropy(logits,target)
            norms.append(checked_step(loss,model,opt));losses.append(float(loss.detach()))
        random.shuffle(rows)
    return dict(loss=float(np.mean(losses)),gradient_norm_max=max(norms),batches=len(losses))

def advantages(episodes,gamma=1.,lam=.95,normalize=True):
    out=[]
    for steps,_ in episodes:
        gae=0.;next_value=0.
        for row in reversed(steps):
            continuation=0. if row['done'] else 1.
            delta=row['reward']+gamma*next_value*continuation-row['value']
            gae=delta+gamma*lam*continuation*gae
            row['advantage']=gae;row['return']=gae+row['value'];next_value=row['value']
        out.extend(steps)
    if normalize:
        a=np.array([r['advantage'] for r in out]);mean=float(a.mean());std=float(a.std())+1e-8
        for r in out:r['advantage']=(r['advantage']-mean)/std
    return out

def ppo_update(model,opt,episodes,device,epochs=3,batch_size=128,entropy=.01):
    rows=advantages(episodes);stats=[];model.train()
    for _ in range(epochs):
        random.shuffle(rows)
        for start in range(0,len(rows),batch_size):
            batch=rows[start:start+batch_size];state,mask=collate(batch,device)
            logits,values=model(state,mask);dist=masked_distribution(logits,mask)
            ts=lambda key:torch.tensor([r[key] for r in batch],device=device,dtype=torch.float32)
            chosen=torch.tensor([r['action'] for r in batch],device=device)
            logp=dist.log_prob(chosen);ratio=(logp-ts('old_logp')).exp();adv=ts('advantage')
            policy=-torch.minimum(ratio*adv,ratio.clamp(.8,1.2)*adv).mean()
            # value目标量纲为真实时间奖励；系数1e-3防止初始大return淹没actor。
            value_loss=(values-ts('return')).square().mean()
            ent=dist.entropy().mean();loss=policy+.001*value_loss-entropy*ent
            norm=checked_step(loss,model,opt)
            stats.append([float(loss.detach()),float(policy.detach()),float(value_loss.detach()),float(ent.detach()),norm,
                          float(((ratio-1)-(logp-ts('old_logp'))).mean().detach())])
    avg=np.mean(stats,axis=0)
    return dict(zip(('loss','policy_loss','value_loss','entropy','gradient_norm','approx_kl'),map(float,avg)))

def save_checkpoint(path,model,opt,config,stage,update,metrics,extra=None):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    data=dict(model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),
              config=config,stage=stage,update=update,metrics=metrics,features=FEATURE_VERSION,profile=PROFILE_VERSION,
              rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),
                       cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []),extra=extra or {},provenance=provenance())
    tmp=p.with_suffix('.tmp');torch.save(data,tmp);tmp.replace(p)

def verify_checkpoint_code(data):
    root=Path(__file__).resolve().parents[2]
    recorded=data.get('provenance',{}).get('files',{})
    critical=('solution/control/controller.py','solution/coverage/certificates.py',
              'solution/geometry/core.py','solution/rl/environment.py','solution/rl/model.py','bsim/research.py')
    # 旧交付记录使用 solution/、bsim/；main 新记录使用 src/，均严格核验内容。
    mismatch=[]
    for p in critical:
        hashes=[recorded[key] for key in (p, 'src/'+p) if key in recorded]
        actual=hashlib.sha256((root/p).read_bytes()).hexdigest()
        if not hashes or any(value!=actual for value in hashes):mismatch.append(p)
    if mismatch:raise ValueError(f'checkpoint/code mismatch; requires explicit diagnostic re-evaluation: {mismatch}')


def load_checkpoint(path,model,opt=None,restore_rng=False,allow_code_mismatch=False):
    data=torch.load(path,map_location='cpu',weights_only=False)
    if data['features']!=FEATURE_VERSION or data['profile']!=PROFILE_VERSION:raise ValueError('checkpoint version mismatch')
    if not allow_code_mismatch:verify_checkpoint_code(data)
    model.load_state_dict(data['model'])
    if opt is not None:opt.load_state_dict(data['optimizer'])
    if restore_rng:
        random.setstate(data['rng']['python']);np.random.set_state(data['rng']['numpy']);torch.set_rng_state(data['rng']['torch'])
        if data['rng']['cuda'] and torch.cuda.is_available():torch.cuda.set_rng_state_all(data['rng']['cuda'])
    return data

def paired_evaluation(pool,problem,seeds,model,max_macros=400):
    teacher=collect(pool,problem,seeds,max_macros=max_macros);student=collect(pool,problem,seeds,model,'greedy',max_macros)
    a=summarize(teacher);b=summarize(student)
    differences=np.array([s[1]['virtual_time_s']-t[1]['virtual_time_s'] for t,s in zip(teacher,student)])
    eligible=a['completion_rate']==1.0 and b['completion_rate']==1.0
    ci=float(1.96*differences.std(ddof=1)/np.sqrt(len(seeds))) if len(seeds)>1 else None
    return dict(baseline=a,student=b,eligible=eligible,mean_paired_delta_s=float(differences.mean()),
                approximate_95ci_halfwidth_s=ci,selection_pass=bool(eligible and float(differences.mean())<0),
                rows=[dict(seed=t[1]['seed'],baseline=t[1],student=s[1]) for t,s in zip(teacher,student)])

def run_training(config):
    blocked=require_authorized_research(config)
    if blocked:raise RuntimeError(blocked.reason)
    torch.set_num_threads(1);device=torch.device(config.get('device','cuda:0'))
    if device.type=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA unavailable; no silent CPU fallback')
    seed=config['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    output=Path(config['output']);output.mkdir(parents=True,exist_ok=True)
    atomic_json(output/'config.json',config);atomic_json(output/'provenance.json',provenance())
    model=CandidatePolicy().to(device);opt=torch.optim.Adam(model.parameters(),lr=config.get('lr',3e-4))
    started=time.perf_counter();events=[];problem=config['problem'];n=config['episodes_per_update'];resume=config.get('resume')
    def event(stage,**data):
        row=dict(stage=stage,elapsed_s=time.perf_counter()-started,**data)
        with (output/'metrics.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        events.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        atomic_json(output/'status.json',row)
    workers=config.get('workers',8)
    with ProcessPoolExecutor(workers,mp_context=mp.get_context('spawn'),initializer=init_worker) as pool:
        first_update=0;best_delta=float('inf')
        if resume:
            data=load_checkpoint(resume,model,opt,True);first_update=data['update']+1
            best_delta=data.get('extra',{}).get('best_delta',float('inf'))
            event('RESUMED',update=first_update,checkpoint=str(resume))
        else:
            base=collect(pool,problem,range(seed,seed+config['bc_episodes']),max_macros=config.get('max_macros',400))
            summary=summarize(base);atomic_json(output/'baseline_episodes.json',[m for _,m in base])
            event('BASELINE',**summary)
            if summary['completion_rate'] < 1.0:
                raise RuntimeError('teacher baseline incomplete; stop before training')
            rows=[row for episode,_ in base for row in episode]
            update=bc_update(model,opt,rows,device,config.get('bc_epochs',6))
            event('BC',**update)
            save_checkpoint(output/'bc.pt',model,opt,config,'BC',-1,update)
            dagger=collect(pool,problem,range(seed+10000,seed+10000+config['dagger_episodes']),model,'greedy',config.get('max_macros',400))
            atomic_json(output/'dagger_episodes.json',[m for _,m in dagger])
            rows.extend(row for episode,_ in dagger for row in episode)
            update=bc_update(model,opt,rows,device,config.get('dagger_epochs',3))
            event('DAGGER',**update,rollout_completion=summarize(dagger)['completion_rate'])
            save_checkpoint(output/'dagger.pt',model,opt,config,'DAGGER',-1,update)
        recent=[]
        for update_index in range(first_update,config['ppo_updates']):
            t=time.perf_counter()
            seeds=range(seed+20000+update_index*n,seed+20000+(update_index+1)*n)
            episodes=collect(pool,problem,seeds,model,'sample',config.get('max_macros',400));sample_s=time.perf_counter()-t
            summary=summarize(episodes)
            # 几何/协议异常不通过增加失败罚分掩盖，立即停训；纯任务预算失败计入奖励。
            anomalies=[m for _,m in episodes if m['error'] not in (None,'macro_budget','virtual_timeout')]
            if anomalies:
                atomic_json(output/'fatal_episodes.json',anomalies);raise RuntimeError('rollout invariant failed')
            stats=ppo_update(model,opt,episodes,device,config.get('ppo_epochs',3),config.get('batch_size',128),.01*(1-update_index/max(config['ppo_updates'],1)))
            elapsed=time.perf_counter()-t;recent.append(elapsed)
            eta=float(np.mean(recent[-5:]))*(config['ppo_updates']-update_index-1)
            event('PPO',update=update_index+1,total_updates=config['ppo_updates'],sample_s=sample_s,update_s=elapsed-sample_s,
                  macros_per_s=summary['macro_steps']/elapsed,eta_s=eta,**summary,**stats)
            atomic_json(output/f'episodes_{update_index+1:04d}.json',[m for _,m in episodes])
            save_checkpoint(output/'latest.pt',model,opt,config,'PPO',update_index,stats,dict(best_delta=best_delta))
            if (update_index+1)%config.get('eval_every',8)==0 or update_index+1==config['ppo_updates']:
                val=paired_evaluation(pool,problem,range(seed+100000,seed+100000+config.get('eval_episodes',8)),model,config.get('max_macros',400))
                atomic_json(output/f'validation_{update_index+1:04d}.json',val)
                event('VALIDATION',update=update_index+1,completion=val['student']['completion_rate'],paired_delta_s=val['mean_paired_delta_s'],selection_pass=val['selection_pass'])
                if val['selection_pass'] and val['mean_paired_delta_s']<best_delta:
                    best_delta=val['mean_paired_delta_s']
                    save_checkpoint(output/'best.pt',model,opt,config,'PPO',update_index,val,dict(best_delta=best_delta))
        event('COMPLETE',updates=config['ppo_updates'],best_selected=(output/'best.pt').exists(),
              checkpoint=str(output/'latest.pt'),note='研究训练；best缺失时保留确定性策略，latest不自动部署')
    return output

def train_bc(config_path):
    config=json.loads(Path(config_path).read_text());blocked=require_authorized_research(config)
    if blocked:return blocked
    config={**config,'ppo_updates':0,'dagger_episodes':config.get('dagger_episodes',4)}
    out=run_training(config);return TrainingStatus('COMPLETE','BC/DAgger已实际更新',str(out/'bc.pt'))
def train_dagger(config_path):return train_bc(config_path)
def train_ppo(config_path):
    config=json.loads(Path(config_path).read_text());blocked=require_authorized_research(config)
    if blocked:return blocked
    out=run_training(config);return TrainingStatus('COMPLETE','实际PPO训练结束',str(out/'latest.pt'))
