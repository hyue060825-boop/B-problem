"""仅依赖公开观测的宏动作控制器；接受响应后才推进覆盖，不读取模拟真值。"""
from dataclasses import dataclass,field
import math
import numpy as np
from solution.geometry.core import FeasibleRegion,mec
from solution.coverage.certificates import omni_skeleton,triangular_grid,verify_directional_certificate

STATES=('UNKNOWN','FOUND','LOCALIZING','CLEARABLE','CLEARED','ABSENT_CERTIFIED')
KINDS=('COVER','LOCALIZE','CLEAR','PROBE_CLEAR','EXIT')

@dataclass
class ChannelState:
    status:str='UNKNOWN'
    observations:list=field(default_factory=list)
    region:FeasibleRegion=field(default_factory=FeasibleRegion)
    covered_stations:set=field(default_factory=set)
    clear_attempts:int=0
    near_position:tuple|None=None
    localizations:int=0
    cert:dict|None=None
    cover_cache:list|None=None

@dataclass(frozen=True)
class Action:
    kind:str
    position:tuple
    channel:int=0
    station:int=-1
    channels:tuple=()
    cost:float=0.

class Controller:
    def __init__(self,problem=3,epsilon_deg=1.01):
        if problem not in (3,4): raise ValueError('problem')
        self.problem=problem;self.position=(0.,0.);self.current_channel=1
        self.virtual_time=0.;self.discovered=set();self.applied=set();self.steps=0
        self.channels={c:ChannelState(region=FeasibleRegion(epsilon_deg)) for c in range(1,21)}
        if problem==3:
            p,cert=omni_skeleton();assert cert.certified
            self.stations=list(p.values());self.station_names=list(p)
        else:
            grid=triangular_grid();assert verify_directional_certificate(grid)
            self.stations=list(grid['vertices']);self.station_names=list(range(len(self.stations)))
        self.visited=set();self.pending_action=None

    def observe(self,channel,position,result,svd_deg=None,station=None):
        s=self.channels[channel];self.position=tuple(position);self.current_channel=channel
        s.observations.append(dict(position=list(position),result=result,svd_deg=svd_deg))
        if station is not None and result=='no_signal': s.covered_stations.add(station)
        if s.status in ('CLEARED','ABSENT_CERTIFIED'): return s.status
        if result in ('near','direction'):
            self.discovered.add(channel);s.status='LOCALIZING';s.cover_cache=None
            if result=='near':
                s.near_position=tuple(position);s.region=FeasibleRegion(s.region.epsilon_deg);s.region.near(position)
            else:
                s.region.direction(position,svd_deg)
            s.cert=s.region.certificate()
            if s.cert is None: raise RuntimeError(f'几何异常: 正观测后频道{channel}空集，不可删除目标')
            if s.cert['safe']:s.status='CLEARABLE'
        elif result=='no_signal' and self.problem==3 and channel in self.discovered:
            s.region.exclude(position,1000);s.cover_cache=None;s.cert=s.region.certificate()
            if s.cert is None:raise RuntimeError('几何异常: 存活源可行域为空')
            if s.cert['safe']:s.status='CLEARABLE'
        if self.problem==3:
            self.certify_absent(channel)
        self.mark_all_remaining_absent_after_16()
        return s.status

    def certify_absent(self,channel):
        s=self.channels[channel]
        if self.problem==4:
            raise ValueError('Q4 no-signal cannot certify absence')
        # Q4 directional sources cannot be excluded by a no-signal cover result.
        if s.status=='UNKNOWN' and set(self.station_names)<=s.covered_stations:
            s.status='ABSENT_CERTIFIED'
        return s.status

    def mark_all_remaining_absent_after_16(self):
        if len(self.discovered)==16:
            for c,s in self.channels.items():
                if c not in self.discovered:s.status='ABSENT_CERTIFIED'

    def clear_result(self,channel,success,position=None,certified=False):
        s=self.channels[channel];s.clear_attempts+=1
        if position is not None:self.position=tuple(position)
        if success:s.status='CLEARED';s.near_position=None;s.cover_cache=None
        elif certified:raise RuntimeError('严重几何异常: 有证书的clear失败，停止本局并保留轨迹')
        elif channel in self.discovered and s.status!='CLEARED':
            s.region.exclude(self.position,20);s.cert=s.region.certificate();s.cover_cache=None
            if s.cert is None:raise RuntimeError('清除失败后可行域为空')
        return s.status

    def exit_allowed(self):return all(s.status in ('CLEARED','ABSENT_CERTIFIED') for s in self.channels.values())

    def legal_actions(self):
        if self.exit_allowed():return [Action('EXIT',self.position)]
        near=[Action('CLEAR',s.near_position,c,cost=5.) for c,s in self.channels.items() if s.near_position and s.status!='CLEARED']
        if near:return near
        out=[]
        # 未访问站点提供批量串行观测宏动作，candidate生成不推进站点指针。
        nearest=sorted((i for i in range(len(self.stations)) if i not in self.visited),key=lambda i:math.dist(self.position,self.stations[i]))[:3]
        for i in nearest:
            cs=tuple(c for c,s in self.channels.items() if s.status=='UNKNOWN' or (s.status in ('FOUND','LOCALIZING') and s.localizations<3))
            if cs:out.append(Action('COVER',tuple(self.stations[i]),station=i,channels=cs,cost=math.dist(self.position,self.stations[i])/5+6*len(cs)))
        # Q4 cannot certify absence from no-signal. If every station was visited
        # while unknown channels remain, revisit the nearest station to obtain
        # another observable measurement instead of dead-ending.
        if not out:
            remaining=tuple(c for c,s in self.channels.items() if s.status=='UNKNOWN')
            if remaining and self.stations:
                i=min(range(len(self.stations)),key=lambda j: math.dist(self.position,self.stations[j]))
                out.append(Action('COVER',tuple(self.stations[i]),station=i,channels=remaining,
                                  cost=math.dist(self.position,self.stations[i])/5+6*len(remaining)))
        for c,s in self.channels.items():
            if c not in self.discovered or s.status=='CLEARED':continue
            cert=s.cert or s.region.certificate()
            if not cert:raise RuntimeError('known source lacks feasible region')
            center=tuple(cert['center']);r=cert['radius_upper_m']
            if cert['safe']:
                out.append(Action('CLEAR',center,c,cost=math.dist(self.position,center)/5+5))
            else:
                if r<=70 or s.localizations>=3 or not nearest:
                    # cover成本是上界估计；执行每个底层clear后处理响应，成功立即停止。
                    if s.cover_cache is None:s.cover_cache=s.region.clear_cover()
                    cover=s.cover_cache
                    cost=math.dist(self.position,cover[0])/5+sum(math.dist(a,b)/5 for a,b in zip(cover,cover[1:]))+3*len(cover)+2
                    out.append(Action('PROBE_CLEAR',tuple(cover[0]),c,cost=cost))
                if s.localizations<3:
                    # 沿位置域主轴侧翼：利用全部顶点给接收界，Q4只标风险补测。
                    last=next((o for o in reversed(s.observations) if o['result']=='direction'),None)
                    theta=math.radians(last['svd_deg']) if last else 0.
                    for sign in (-1,1):
                        delta=np.array([-math.sin(theta),math.cos(theta)])*sign*min(350,max(30,r*.45))
                        q=np.array(center)+delta
                        out.append(Action('LOCALIZE',tuple(q),c,cost=math.dist(self.position,q)/5+6))
        return out

    def teacher_index(self,actions):
        def score(a):
            if a.kind=='EXIT':return -1e9
            if a.kind=='CLEAR':return a.cost-300
            if a.kind=='PROBE_CLEAR':return a.cost-160
            if a.kind=='COVER':return a.cost-10*sum(self.channels[c].status=='UNKNOWN' for c in a.channels)
            return a.cost+60+40*self.channels[a.channel].localizations
        return min(range(len(actions)),key=lambda i:score(actions[i]))

    def candidates(self):
        return [('/exit' if a.kind=='EXIT' else '/clear' if a.kind in ('CLEAR','PROBE_CLEAR') else '/measure',None if a.kind=='EXIT' else a.position,None if a.kind=='EXIT' else (a.channel or a.channels[0]),a.kind) for a in self.legal_actions()]
    def next_action(self):
        actions=self.legal_actions()
        if not actions:return None
        a=actions[self.teacher_index(actions)]
        return ('/exit' if a.kind=='EXIT' else '/clear' if a.kind in ('CLEAR','PROBE_CLEAR') else '/measure',None if a.kind=='EXIT' else a.position,None if a.kind=='EXIT' else (a.channel or a.channels[0]),a.kind)

    def execute(self,action,request):
        """request(path,position,channel)->公开已接受响应；每步可中断宏动作。"""
        def measure(q,c,station=None):
            r=request('/measure',q,c);self.virtual_time=r['virtual_time_s']
            self.observe(c,q,r['measure_result'],r.get('svd_deg'),station)
            if r['measure_result']=='near':
                r=request('/clear',q,c);self.virtual_time=r['virtual_time_s']
                self.clear_result(c,r['clear_result']=='success',q,True)
        if action.kind=='COVER':
            channels=sorted(action.channels,reverse=bool(action.station%2))
            if self.current_channel in channels:channels.remove(self.current_channel);channels.insert(0,self.current_channel)
            for c in channels:
                if self.channels[c].status in ('CLEARED','ABSENT_CERTIFIED'):continue
                measure(action.position,c,self.station_names[action.station])
            self.visited.add(action.station)
        elif action.kind=='LOCALIZE':
            self.channels[action.channel].localizations+=1
            measure(action.position,action.channel)
        elif action.kind=='CLEAR':
            cert=self.channels[action.channel].region.certificate(action.position)
            if not cert or not cert['safe']:raise RuntimeError('clear证书失效')
            r=request('/clear',action.position,action.channel);self.virtual_time=r['virtual_time_s']
            self.clear_result(action.channel,r['clear_result']=='success',action.position,True)
        elif action.kind=='PROBE_CLEAR':
            # 此处快照覆盖完整K，不因首次失败重新从第一个点开始。
            points=list(self.channels[action.channel].cover_cache or self.channels[action.channel].region.clear_cover())
            while points:
                index=min(range(len(points)),key=lambda i:math.dist(self.position,points[i]));q=points.pop(index)
                r=request('/clear',q,action.channel);self.virtual_time=r['virtual_time_s']
                self.clear_result(action.channel,r['clear_result']=='success',q)
                if r['clear_result']=='success':break
            else:raise RuntimeError('完整clear cover仍未清除，证书异常')
        elif action.kind=='EXIT':
            if not self.exit_allowed():raise RuntimeError('未取得退出证书')
            request('/exit',None,None)
        self.steps+=1
