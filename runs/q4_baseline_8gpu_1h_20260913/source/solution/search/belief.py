"""Serializable public history and bounded, history-checked Q3 hypotheses.

Research approximation: uniform feasible position proposals, conditional uniform
count/channel/radius, bounded fixed error field conditioned at observed points.
This is not the official generator or an exact Bayesian posterior.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import time

import numpy as np
from shapely.geometry import Point
from shapely.ops import triangulate

from bsim.noise import Numerics
from bsim.client import public_response
from bsim.reference import ReferenceKernel, State
from bsim.research import FixedField
from bsim.scenarios import Scenario, Source
from solution.control.controller import Action, Controller
from solution.geometry.core import FeasibleRegion, wrap_to_180, circle_polygon

BELIEF_VERSION='q3-public-conditional-v1'
CANDIDATE_VERSION='controller-actions-v1'
NUMERICS=Numerics('TEST_INPUT','half_up','half_up','invisible',0.)


def action_dict(action):
    return json.loads(json.dumps(asdict(action)))


def action_id(action):
    data=action_dict(action) if isinstance(action,Action) else action
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def decode_action(data):
    return Action(**{**data,'position':tuple(data['position']),'channels':tuple(data['channels'])})


def public_snapshot(macros,remaining_real_s=1200.):
    return dict(version=BELIEF_VERSION,problem=3,macros=deepcopy(macros),remaining_real_s=float(remaining_real_s))


def restore_controller(public):
    if set(public)!={'version','problem','macros','remaining_real_s'} or public['version']!=BELIEF_VERSION or public['problem']!=3:
        raise ValueError('public-history schema/version mismatch')
    c=Controller(3)
    for macro in public['macros']:
        action=decode_action(macro['action'])
        if action_id(action) not in {action_id(a) for a in c.legal_actions()}:
            raise ValueError('candidate semantics changed or invalid history')
        calls=iter(macro['calls'])
        def request(path,position,channel):
            row=next(calls)
            if set(row)!={'path','position','channel','response'}:raise ValueError('non-public call schema')
            if path!=row['path'] or (list(position) if position is not None else None)!=row['position'] or channel!=row['channel']:
                raise ValueError('public replay action mismatch')
            if row['response']['accepted'] is not True:raise ValueError('only accepted history allowed')
            return public_response(path,row['response'])
        c.execute(action,request)
        if next(calls,None) is not None:raise ValueError('unused history responses')
    c.remaining_real_s=public['remaining_real_s']
    return c


def calls_from(public):
    return [call for macro in public['macros'] for call in macro['calls']]


class ConditionalFixedField:
    def __init__(self,seed,observed):
        self.fallback=FixedField(seed,'smooth')
        self.observed=dict(observed)

    def error(self,channel,x,y):
        return self.observed.get((channel,float(x),float(y)),self.fallback.error(channel,x,y))


class PositionProposal:
    def __init__(self,channel,calls):
        self.channel=channel;self.calls=calls;self.known=False
        region=FeasibleRegion();cleared=False
        for row in calls:
            if cleared:continue
            p=row['position'];r=row['response']
            if row['path']=='/measure':
                result=r['measure_result']
                if result=='direction':region.direction(p,r['svd_deg']);self.known=True
                elif result=='near':region.near(p);self.known=True
                else:region.exclude(p,1000)
            elif row['path']=='/clear':
                if r['clear_result']=='success':
                    region.geom=region.geom.intersection(circle_polygon(p,20));self.known=True;cleared=True
                else:region.exclude(p,20)
        self.region=region.geom
        self.triangles=[np.array(t.exterior.coords[:3]) for t in triangulate(self.region)]
        area=np.array([abs((t[1,0]-t[0,0])*(t[2,1]-t[0,1])-(t[1,1]-t[0,1])*(t[2,0]-t[0,0]))/2 for t in self.triangles])
        self.prob=area/area.sum() if len(area) and area.sum()>0 else []

    def sample(self,rng,attempts,reasons):
        if not len(self.prob):reasons['empty_region']+=1;return None
        for _ in range(attempts):
            t=self.triangles[int(rng.choice(len(self.triangles),p=self.prob))]
            u,v=rng.random(2)
            if u+v>1:u,v=1-u,1-v
            p=t[0]+u*(t[1]-t[0])+v*(t[2]-t[0])
            if np.linalg.norm(p)>1800 or not self.region.covers(Point(p)):
                reasons['position_outside']+=1;continue
            lower,upper=1000.,1500.;observed={};cleared=False;valid=True
            for row in self.calls:
                q=row['position'];r=row['response'];d=math.dist(p,q)
                if row['path']=='/clear':
                    expected='success' if not cleared and d<=20 else 'no_target_in_range'
                    if expected!=r['clear_result']:valid=False;break
                    cleared|=expected=='success'
                elif row['path']=='/measure':
                    result=r['measure_result']
                    if cleared:
                        if result!='no_signal':valid=False;break
                    elif result=='no_signal':upper=min(upper,np.nextafter(d,-math.inf))
                    elif result=='near':
                        if d>5:valid=False;break
                        lower=max(lower,d)
                    else:
                        if d<=5:valid=False;break
                        lower=max(lower,d)
                        bearing=math.degrees(math.atan2(p[1]-q[1],p[0]-q[0]))
                        error=float(np.clip(wrap_to_180(r['svd_deg']-bearing),-1,1))
                        key=(self.channel,float(q[0]),float(q[1]))
                        if NUMERICS.angle(bearing+error)!=r['svd_deg'] or (key in observed and observed[key]!=error):
                            valid=False;break
                        observed[key]=error
            if not valid:reasons['history_constraint']+=1;continue
            if lower>upper:reasons['radius_interval']+=1;continue
            radius=float(rng.uniform(lower,upper)) if lower<upper else lower
            return Source(self.channel,float(p[0]),float(p[1]),radius,'omni',None),observed
        reasons['proposal_exhausted']+=1;return None


def validate_world(kernel,calls):
    state=State()
    for row in calls:
        if row['path'] not in ('/measure','/clear'):continue
        state,result=kernel.transition(state,row['path'],tuple(row['position']),row['channel'])
        if any(row['response'].get(k)!=v for k,v in result.items()):return False
        if state.virtual_us!=round(row['response']['virtual_time_s']*1e6):return False
    return True


class BeliefScenarioSampler:
    def sample(self,public,seed,count=8,max_seconds=10.,position_attempts=128):
        restore_controller(public)  # Validate public schema and action semantics.
        started=time.perf_counter();rng=np.random.default_rng(seed);calls=calls_from(public)
        by_channel={c:[r for r in calls if r['channel']==c] for c in range(1,21)}
        proposals={c:PositionProposal(c,rows) for c,rows in by_channel.items()}
        known=[c for c,p in proposals.items() if p.known]
        possible=[c for c,p in proposals.items() if not p.known and len(p.prob)]
        reasons=Counter();worlds=[];trials=0
        minimum=max(10,len(known));maximum=min(16,len(known)+len(possible))
        while len(worlds)<count and trials<count*4 and time.perf_counter()-started<max_seconds:
            trials+=1
            if minimum>maximum:reasons['count_incompatible']+=1;break
            n=int(rng.integers(minimum,maximum+1))
            channels=known+list(rng.choice(possible,n-len(known),replace=False))
            sources=[];observed={}
            for c in channels:
                result=proposals[int(c)].sample(rng,position_attempts,reasons)
                if result is None:break
                source,errors=result;sources.append(source);observed.update(errors)
            if len(sources)!=n:continue
            kernel=ReferenceKernel(Scenario('LOCAL-BELIEF',3,'official_constraints',tuple(sources)),
                                   ConditionalFixedField(int(rng.integers(0,2**31)),observed),NUMERICS)
            if not validate_world(kernel,calls):reasons['full_replay_mismatch']+=1;continue
            worlds.append(kernel)
        return worlds,dict(version=BELIEF_VERSION,requested=count,effective=len(worlds),attempts=trials,
                           acceptance=len(worlds)/max(1,trials),rejections=dict(reasons),
                           seconds=time.perf_counter()-started,uncertain=len(worlds)<count,
                           prior='uniform feasible proposals; conditional count/channel/radius; conditioned bounded fixed error')
