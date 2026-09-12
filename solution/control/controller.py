"""Public-observation controller with certified safety and planning state."""
from dataclasses import dataclass, field, replace
import math
import numpy as np
from solution.coverage.certificates import omni_skeleton, triangular_grid, verify_directional_certificate
from solution.geometry.core import FeasibleRegion
from solution.planning.probe import ProbePlan, build_probe_plan, plan_route_matches, reorder_probe_plan
from solution.planning.route import insertion_detour, plan_open_route
from solution.belief.q4_directional import Q4DirectionalBelief

STATES=('UNKNOWN','FOUND','LOCALIZING','CLEARABLE','CLEARED','ABSENT_CERTIFIED')
KINDS=('COVER','LOCALIZE','CLEAR','PROBE_STEP','FULL_PROBE_FALLBACK','EXIT')

def exact_position(p): return (float(p[0]),float(p[1]))

@dataclass
class ChannelState:
    status='UNKNOWN'; observations:list=field(default_factory=list); observation_positions:set=field(default_factory=set)
    region:FeasibleRegion=field(default_factory=FeasibleRegion); covered_stations:set=field(default_factory=set)
    clear_attempts:int=0; near_position:tuple|None=None; localizations:int=0; cert:dict|None=None
    probe_plan:ProbePlan|None=None

@dataclass(frozen=True)
class Action:
    kind:str; position:tuple; channel:int=0; station:int=-1; channels:tuple=(); cost:float=0.
    scan_mode:str=''; route_detour_m:float=0.; route_rank:int=-1; plan:ProbePlan|None=None

class Controller:
    def __init__(self,problem=3,epsilon_deg=1.01):
        if problem not in (3,4): raise ValueError('problem')
        self.problem=problem; self.position=(0.,0.); self.current_channel=1; self.virtual_time=0.
        self.discovered=set(); self.applied=set(); self.steps=0
        self.channels={c:ChannelState(region=FeasibleRegion(epsilon_deg)) for c in range(1,21)}
        if problem==3:
            points,cert=omni_skeleton(); assert cert.certified; self.stations=list(points.values()); self.station_names=list(points)
        else:
            grid=triangular_grid(); assert verify_directional_certificate(grid); self.stations=list(grid['vertices']); self.station_names=list(range(len(self.stations)))
        self.physical_station_visited=set(); self.visited=self.physical_station_visited; self.pending_action=None
        self.last_route=plan_open_route(self.position,self.stations,[True]*len(self.stations))
        self.q4_beliefs={}
        self.diagnostics={'duplicate_exact_measure_candidates':0,'duplicate_exact_measure_executed':0,'active_localize_count':0,
            'active_localize_no_signal_count':0,'active_localize_positive_count':0,'cover_unknown_measure_count':0,
            'cover_known_measure_count':0,'cover_known_no_signal_count':0,'probe_macros':0,'probe_points':0,
            'probe_failed_clear_count':0,'probe_plan_first_point_match':True,'probe_plan_route_match':True,'probe_move_m':0.,
            'coverage_route_length_planned_m':0.,'coverage_route_actual_m':0.,'route_detour_m':0.,'clear_insertion_count':0,
            'localize_insertion_count':0,'station_visits':0,'station_revisits':0,'per_channel_certificate_measurements':0}

    def _update_q4_belief(self, channel):
        """Refresh advisory particles from this channel's public history."""
        s=self.channels[channel]
        previous=self.q4_beliefs.get(channel)
        self.q4_beliefs[channel]=Q4DirectionalBelief.from_public_history(
            s.region.vertices,s.observations,seed=104729*len(s.observations)+9176,count=128,
            initial=previous.hypotheses if previous else ())

    def observe(self,channel,position,result,svd_deg=None,station=None,source='ACTIVE'):
        s=self.channels[channel]; key=exact_position(position); self.position=key; self.current_channel=channel
        s.observations.append({'position':list(key),'result':result,'svd_deg':svd_deg,'source':source}); s.observation_positions.add(key)
        if station in self.station_names and result=='no_signal':
            i=self.station_names.index(station)
            if math.dist(key,self.stations[i])<=1e-6:
                before=len(s.covered_stations); s.covered_stations.add(station); self.diagnostics['per_channel_certificate_measurements']+=len(s.covered_stations)-before
        if source=='LOCALIZE':
            self.diagnostics['active_localize_count']+=1; self.diagnostics['active_localize_no_signal_count']+=int(result=='no_signal'); self.diagnostics['active_localize_positive_count']+=int(result!='no_signal')
        elif source=='COVER':
            if s.status=='UNKNOWN': self.diagnostics['cover_unknown_measure_count']+=1
            else: self.diagnostics['cover_known_measure_count']+=1; self.diagnostics['cover_known_no_signal_count']+=int(result=='no_signal')
        if s.status in ('CLEARED','ABSENT_CERTIFIED'): return s.status
        if result in ('near','direction'):
            self.discovered.add(channel); s.status='LOCALIZING'; s.probe_plan=None
            if result=='near': s.near_position=key; s.region=FeasibleRegion(s.region.epsilon_deg); s.region.near(key)
            else: s.region.direction(key,svd_deg)
            s.cert=s.region.certificate()
            if s.cert is None: raise RuntimeError('positive observation left empty feasible region')
            if s.cert['safe']: s.status='CLEARABLE'
            if self.problem == 4:
                self._update_q4_belief(channel)
        elif result=='no_signal' and self.problem==3 and channel in self.discovered:
            s.region.exclude(key,1000); s.probe_plan=None; s.cert=s.region.certificate()
            if s.cert is None: raise RuntimeError('known source has empty feasible region')
            if s.cert['safe']: s.status='CLEARABLE'
        elif result == 'no_signal' and self.problem == 4 and channel in self.discovered:
            # Preserve the disjunctive planning belief; no certified exclusion.
            self._update_q4_belief(channel)
        if self.problem==3 or set(self.station_names)<=s.covered_stations: self.certify_absent(channel)
        self.mark_all_remaining_absent_after_16(); return s.status

    def certify_absent(self,channel):
        s=self.channels[channel]
        if self.problem==4 and not set(self.station_names)<=s.covered_stations: raise ValueError('Q4 absence requires every certified grid station')
        if s.status=='UNKNOWN' and set(self.station_names)<=s.covered_stations: s.status='ABSENT_CERTIFIED'
        return s.status
    def mark_all_remaining_absent_after_16(self):
        if len(self.discovered)==16:
            for c,s in self.channels.items():
                if c not in self.discovered: s.status='ABSENT_CERTIFIED'
    def clear_result(self,channel,success,position=None,certified=False):
        s=self.channels[channel]; s.clear_attempts+=1
        if position is not None: self.position=exact_position(position)
        if success: s.status='CLEARED'; s.near_position=None; s.probe_plan=None
        elif certified: raise RuntimeError('certified clear failed')
        elif channel in self.discovered and s.status!='CLEARED':
            s.region.exclude(self.position,20); s.cert=s.region.certificate(); s.probe_plan=None
            if s.cert is None: raise RuntimeError('failed clear left empty feasible region')
            if s.cert['safe']: s.status='CLEARABLE'
        return s.status
    def exit_allowed(self): return all(s.status in ('CLEARED','ABSENT_CERTIFIED') for s in self.channels.values())
    def _coverage_required(self,i):
        name=self.station_names[i]; return tuple(c for c,s in self.channels.items() if s.status=='UNKNOWN' and name not in s.covered_stations)
    def _coverage_route(self):
        mask=[bool(self._coverage_required(i)) for i in range(len(self.stations))]; self.last_route=plan_open_route(self.position,self.stations,mask); self.diagnostics['coverage_route_length_planned_m']=self.last_route.length_m; return self.last_route
    def _safe_action(self,c,s,route):
        p=s.region.safe_point(self.position)
        if p is None: return None
        p=exact_position(p); cert=s.region.certificate(p)
        if not cert or not cert['safe']: return None
        detour,_=insertion_detour(self.position,p,route,self.stations); self.diagnostics['clear_insertion_count']+=1
        return Action('CLEAR',p,c,cost=math.dist(self.position,p)/5+5,route_detour_m=detour)
    def _localize_points(self,channel,s,center,radius):
        v=s.region.vertices
        if len(v)>=2:
            _,_,vh=np.linalg.svd(v-np.mean(v,axis=0),full_matrices=False); axis=vh[0]; flank=np.array([-axis[1],axis[0]])
        else:
            last=next((o for o in reversed(s.observations) if o['result']=='direction'),None); t=math.radians(last['svd_deg']) if last else 0.; flank=np.array([-math.sin(t),math.cos(t)])
        d=min(420.,max(35.,radius*.45))
        points=[exact_position(np.asarray(center)+sign*flank*d) for sign in (-1,1)]
        if self.problem==4:
            # Add a bounded, diverse public-geometry pool. Belief only ranks
            # candidates; it cannot certify clear/absence or remove fallback.
            for scale in (.25,.6):
                radius2=min(650.,max(45.,radius*scale))
                for angle in np.linspace(0,2*math.pi,8,endpoint=False):
                    points.append(exact_position(np.asarray(center)+radius2*np.array([math.cos(angle),math.sin(angle)])))
            belief=self.q4_beliefs.get(channel)
            if belief and belief.summary_at(center).valid:
                points=belief.best_localize_points(points)
        unique=[]
        for p in points:
            if p not in unique: unique.append(p)
        return unique[:8]
    def legal_actions(self):
        if self.exit_allowed(): return [Action('EXIT',self.position)]
        near=[]
        for c,s in self.channels.items():
            if s.near_position and s.status!='CLEARED':
                cert=s.region.certificate(s.near_position)
                if cert and cert['safe']: near.append(Action('CLEAR',s.near_position,c,cost=5.))
        if near:return near
        out=[]; route=self._coverage_route(); station_ids=[]
        if route.next_id is not None: station_ids.append(route.next_id)
        nearest=sorted((i for i in range(len(self.stations)) if self._coverage_required(i)),key=lambda i:(math.dist(self.position,self.stations[i]),i))[:3]
        station_ids.extend(i for i in nearest if i not in station_ids); ranks={i:k for k,i in enumerate(route.ordered_ids)}
        for i in station_ids:
            required=self._coverage_required(i)
            if not required: continue
            known=[c for c,s in self.channels.items() if s.status in ('FOUND','LOCALIZING') and exact_position(self.stations[i]) not in s.observation_positions]
            known.sort(key=lambda c:(-self.q4_beliefs[c].summary_at(self.stations[i]).receive_entropy
                                     if c in self.q4_beliefs else 0.,c))
            known=tuple(known)
            sets=[('CERT_REQUIRED',required)]+([('CERT_PLUS_HIGH_VALUE_KNOWN',required+known[:3])] if known else [])
            for mode,chs in sets:
                p=exact_position(self.stations[i]); out.append(Action('COVER',p,station=i,channels=tuple(dict.fromkeys(chs)),cost=math.dist(self.position,p)/5+6*len(chs),scan_mode=mode,route_rank=ranks.get(i,-1)))
        for c,s in self.channels.items():
            if c not in self.discovered or s.status=='CLEARED': continue
            cert=s.cert or s.region.certificate()
            if not cert: raise RuntimeError('known source lacks feasible region')
            center=exact_position(cert['center']); r=cert['radius_upper_m']
            if cert['safe']:
                a=self._safe_action(c,s,route)
                if a: out.append(a)
                continue
            belief=self.q4_beliefs.get(c)
            probe_probability=belief.summary_at(center).near_probability if belief else 0.
            if r<=90 or probe_probability>=.35 or s.localizations>=6 or not station_ids:
                # Probe geometry is deterministic for a region version. Reuse
                # the cached plan across policy observations; rebuilding the
                # recursive cover dominated Q4 rollout time.
                plan=s.probe_plan
                if plan is None:
                    plan=build_probe_plan(c,s.region,self.position); s.probe_plan=plan
                else:
                    # Keep the certified cover points, but cheaply reorder
                    # them from the current position as the robot moves.
                    order=plan_open_route(self.position,plan.points,max_ms=2.0)
                    points=tuple(plan.points[i] for i in order.ordered_ids)
                    plan=replace(plan,points=points,estimated_move_s=order.length_m/5.0,
                                 worst_case_clear_s=order.length_m/5.0+3.0*max(0,len(points)-1)+5.0)
                plans=[plan]
                if belief and belief.summary_at(center).valid and len(plan.points)>1:
                    scores=belief.probe_scores(plan.points)
                    for index in np.argsort(-scores,kind='stable')[:2]:
                        if int(index)!=0:plans.append(reorder_probe_plan(plan,self.position,int(index)))
                for candidate_plan in plans:
                    out.append(Action('PROBE_STEP',candidate_plan.first_point,c,
                                      cost=math.dist(self.position,candidate_plan.first_point)/5+3,plan=candidate_plan))
                if s.clear_attempts>=3 or len(plan.points)<=2: out.append(Action('FULL_PROBE_FALLBACK',plan.first_point,c,cost=plan.worst_case_clear_s,plan=plan))
            if s.localizations<6:
                for p in self._localize_points(c,s,center,r):
                    if p in s.observation_positions: self.diagnostics['duplicate_exact_measure_candidates']+=1; continue
                    self.diagnostics['localize_insertion_count']+=1; out.append(Action('LOCALIZE',p,c,cost=math.dist(self.position,p)/5+6))
        return out
    def teacher_index(self,actions):
        def score(a):
            if a.kind=='EXIT':return -1e9
            if a.kind=='CLEAR':return a.cost-300
            if a.kind=='PROBE_STEP':
                belief=self.q4_beliefs.get(a.channel)
                probability=belief.summary_at(a.position).near_probability if belief else 0.
                return a.cost-155-500*probability
            if a.kind=='FULL_PROBE_FALLBACK':
                # After bounded public failed clears, finish the finite certified
                # cover instead of repeatedly preferring its cheap first step.
                return -1e8 if self.channels[a.channel].clear_attempts>=3 else a.cost-145
            if a.kind=='COVER':return a.cost-10*sum(self.channels[c].status=='UNKNOWN' for c in a.channels)+.02*a.route_rank
            return a.cost+50+25*self.channels[a.channel].localizations
        return min(range(len(actions)),key=lambda i:(score(actions[i]),i))
    def candidates(self):
        return [('/exit' if a.kind=='EXIT' else '/clear' if a.kind in ('CLEAR','PROBE_STEP','FULL_PROBE_FALLBACK') else '/measure',None if a.kind=='EXIT' else a.position,None if a.kind=='EXIT' else (a.channel or a.channels[0]),a.kind) for a in self.legal_actions()]
    def next_action(self):
        a=self.legal_actions()[self.teacher_index(self.legal_actions())]; return ('/exit' if a.kind=='EXIT' else '/clear' if a.kind in ('CLEAR','PROBE_STEP','FULL_PROBE_FALLBACK') else '/measure',None if a.kind=='EXIT' else a.position,None if a.kind=='EXIT' else (a.channel or a.channels[0]),a.kind)
    def execute(self,action,request):
        def measure(p,c,station=None,source='ACTIVE'):
            r=request('/measure',p,c); self.virtual_time=r['virtual_time_s']; self.observe(c,p,r['measure_result'],r.get('svd_deg'),station,source)
            if r['measure_result']=='near': r=request('/clear',p,c); self.virtual_time=r['virtual_time_s']; self.clear_result(c,r['clear_result']=='success',p,True)
        if action.kind=='COVER':
            self.diagnostics['station_revisits']+=int(action.station in self.physical_station_visited); self.diagnostics['station_visits']+=1; old=self.position
            chs=list(action.channels)
            if self.current_channel in chs: chs.remove(self.current_channel); chs.insert(0,self.current_channel)
            for c in chs:
                if self.channels[c].status not in ('CLEARED','ABSENT_CERTIFIED'): measure(action.position,c,self.station_names[action.station],'COVER')
            self.physical_station_visited.add(action.station); self.diagnostics['coverage_route_actual_m']+=math.dist(old,action.position)
        elif action.kind=='LOCALIZE':
            s=self.channels[action.channel]
            if exact_position(action.position) in s.observation_positions: self.diagnostics['duplicate_exact_measure_executed']+=1; raise RuntimeError('duplicate exact active localization')
            s.localizations+=1; measure(action.position,action.channel,source='LOCALIZE')
        elif action.kind=='CLEAR':
            cert=self.channels[action.channel].region.certificate(action.position)
            if not cert or not cert['safe']: raise RuntimeError('clear certificate invalidated')
            r=request('/clear',action.position,action.channel); self.virtual_time=r['virtual_time_s']; self.clear_result(action.channel,r['clear_result']=='success',action.position,True)
        elif action.kind in ('PROBE_STEP','FULL_PROBE_FALLBACK'):
            plan=action.plan
            if plan is None or plan.channel!=action.channel or action.position!=plan.first_point: self.diagnostics['probe_plan_first_point_match']=False; raise RuntimeError('probe candidate and plan disagree')
            self.diagnostics['probe_macros']+=1; old=self.position; calls=[]; limit=1 if action.kind=='PROBE_STEP' else len(plan.points)
            for p in plan.points[:limit]:
                r=request('/clear',p,action.channel); calls.append({'position':p}); self.virtual_time=r['virtual_time_s']; ok=r['clear_result']=='success'; self.diagnostics['probe_points']+=1; self.diagnostics['probe_failed_clear_count']+=int(not ok); self.clear_result(action.channel,ok,p)
                if ok: break
            self.diagnostics['probe_move_m']+=math.dist(old,self.position)
            if not plan_route_matches(plan,calls): self.diagnostics['probe_plan_route_match']=False; raise RuntimeError('probe execution route differs from plan')
            if action.kind=='FULL_PROBE_FALLBACK' and self.channels[action.channel].status!='CLEARED': raise RuntimeError('certified clear cover did not clear source')
        elif action.kind=='EXIT':
            if not self.exit_allowed(): raise RuntimeError('exit without certificates')
            request('/exit',None,None)
        else: raise ValueError(f'unknown action kind {action.kind}')
        self.steps+=1
