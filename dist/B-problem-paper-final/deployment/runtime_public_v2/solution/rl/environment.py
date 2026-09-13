"""研究训练环境适配器：复用bsim参考内核和四接口Session；评价真值不交给策略。"""
import time
import numpy as np
from bsim.protocol import encode
from bsim.client import public_response
from bsim.research import make_research_session
from solution.control.controller import Controller,STATES,KINDS

FEATURE_VERSION='normalized-public-v2'

def features(controller,actions):
    ctrl=controller
    global_row=[ctrl.position[0]/2000,ctrl.position[1]/2000,ctrl.current_channel/20,ctrl.virtual_time/10000,
                getattr(ctrl,'remaining_real_s',1200.)/1200,len(ctrl.discovered)/16,
                sum(s.status=='CLEARED' for s in ctrl.channels.values())/16,
                sum(s.status not in ('CLEARED','ABSENT_CERTIFIED') for s in ctrl.channels.values())/20,
                ctrl.problem-3,len(ctrl.visited)/len(ctrl.stations)]
    rows=[]
    for c,s in ctrl.channels.items():
        obs=next((o for o in reversed(s.observations) if o['result']=='direction'),None)
        theta=np.radians(obs['svd_deg']) if obs else 0.
        cert=s.cert
        rows.append([STATES.index(s.status)/5,len(s.observations)/50,np.sin(theta) if obs else 0,np.cos(theta) if obs else 0,
                     s.region.geom.area/1e7,(cert['radius_upper_m']/1500 if cert else 1),
                     float(s.localizations)/3,float(s.status=='CLEARABLE'),len(s.covered_stations)/len(ctrl.stations)])
    candidates=[]
    for a in actions:
        c=a.channel;s=ctrl.channels.get(c)
        candidates.append([KINDS.index(a.kind)/4,a.position[0]/2000,a.position[1]/2000,c/20,
                           a.cost/1000,len(a.channels)/20,float(c==ctrl.current_channel),float(a.kind=='CLEAR'),
                           float(a.kind=='COVER'),(s.cert['radius_upper_m']/1500 if s and s.cert else 0),
                           (s.localizations/3 if s else 0)])
    return dict(global_=np.asarray(global_row,dtype=np.float32),channels=np.asarray(rows,dtype=np.float32),
                candidates=np.asarray(candidates,dtype=np.float32))

def model_state(state):return {'global':state['global_'],'channels':state['channels'],'candidates':state['candidates']}

class TrainingEnv:
    def __init__(self,problem,seed,max_macros=400,**scenario_args):
        self.session,self.profile=make_research_session(problem,seed,**scenario_args)
        self.controller=Controller(problem);self.rid=0;self.max_macros=max_macros;self.started=time.perf_counter()
        self.path_length=0.;self.measure_count=0;self.switches=0;self.failures=0;self.probes=0;self.max_decision_s=0.
        self.decision_times=[];self.error=None;self.done=False;self.success=False
        self._request('/enter',None,None)
    def _request(self,path,position,channel):
        self.rid+=1;p=dict(arena_id='default',robot_id='LOCAL-TRAIN',request_id=str(self.rid))
        if position is not None:p.update(position=dict(x=float(position[0]),y=float(position[1])),channel=int(channel))
        old=self.session.state
        status,response=self.session.request('POST',path,{'Content-Type':'application/json'},encode(p))
        public_response(path,response)
        if status!=200 or response['accepted'] is not True:raise RuntimeError(f'HTTP {status}: {self.session.last_error}')
        if position is not None:self.path_length+=float(np.linalg.norm(np.asarray(position)-np.asarray(old.position)))
        if path=='/measure':self.measure_count+=1;self.switches+=int(old.channel!=channel)
        if path=='/clear' and response['clear_result']=='no_target_in_range':self.failures+=1
        return response
    def observe(self):
        self.controller.remaining_real_s=max(0.,1200-(time.perf_counter()-self.started))
        actions=self.controller.legal_actions()
        if not actions:raise RuntimeError('控制器无合法动作且未退出')
        return features(self.controller,actions),actions
    def step(self,action):
        prev=self.session.state.virtual_us/1e6
        if action.kind=='PROBE_CLEAR':self.probes+=1
        try:
            self.controller.execute(action,self._request)
            if action.kind=='EXIT':
                self.done=True
                # 评价端真值仅决定奖励/指标，不参与controller或actor动作。
                self.success=len(self.session.state.cleared)==len(self.session.kernel.scenario.sources)
            elif self.controller.steps>=self.max_macros:
                self.done=True;self.error='macro_budget'
            if self.session.phase=='ended' and not self.done:self.done=True;self.error=self.session.reason
        except Exception as exc:
            self.error=f'{type(exc).__name__}: {exc}';self.done=True
        reward=-(self.session.state.virtual_us/1e6-prev)/100
        if self.done and not self.success:reward-=1000
        return reward,self.done
    def metrics(self):
        n=len(self.session.kernel.scenario.sources);c=len(self.session.state.cleared);t=self.session.state.virtual_us/1e6
        d=np.asarray(self.decision_times or [0.])
        return dict(problem=self.controller.problem,seed=self.profile['seed'],profile=self.profile,N=n,C=c,
                    completion=self.success,cleared_fraction=c/n,virtual_time_s=t,time_per_clear_s=t/c if c else None,
                    elapsed_s=time.perf_counter()-self.started,path_length_m=self.path_length,measures=self.measure_count,
                    switches=self.switches,clear_failures=self.failures,probe_macros=self.probes,macro_steps=self.controller.steps,
                    decision_max_s=float(max(d)),decision_p95_s=float(np.percentile(d,95)),error=self.error)
