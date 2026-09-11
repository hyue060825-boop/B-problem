import json, math
import numpy as np
import torch
from solution.coverage.certificates import check_omni_parameters, triangular_grid, verify_directional_certificate
from solution.control.controller import Controller
from solution.rl.features import public_state
from solution.rl.model import CandidatePolicy, masked_distribution

def test_omni_continuous_endpoint_certificate():
    rows=check_omni_parameters()
    assert all(r['certified'] for r in rows)
    assert rows[1]['max_distance_m'] < 1000
    assert abs((1200-1135)*6-390)<1e-9

def test_directional_grid_certificate_and_boundaries():
    g=triangular_grid(995)
    assert g['triangle_count'] >= 40 and g['vertex_count'] >= 30
    assert verify_directional_certificate(g)
    for tri in g['triangles'][:10]:
        assert max(math.dist(a,b) for a in tri for b in tri) <= 995+1e-5

def test_controller_observable_state_and_exit():
    c=Controller(3)
    assert c.channels[1].status=='UNKNOWN'
    c.observe(1,(0,0),'no_signal',station='origin')
    assert c.channels[1].status=='UNKNOWN'
    c.observe(1,(0,0),'near',station='origin')
    assert c.channels[1].status=='CLEARABLE'
    assert c.next_action()[0]=='/clear'
    c.clear_result(1,True)
    assert c.channels[1].status=='CLEARED' and not c.exit_allowed()
    c.mark_all_remaining_absent_after_16()
    assert not c.exit_allowed()

def test_q4_no_signal_does_not_certify_absent():
    c=Controller(4); c.observe(1,(0,0),'no_signal',station=(0,0))
    assert c.channels[1].status=='UNKNOWN'
    try: c.certify_absent(1)
    except ValueError: pass
    else: assert False

def test_public_features_model_and_mask():
    states=[{'status':'UNKNOWN','observations':[],'area_m2':0} for _ in range(20)]
    acts=[{'type':'COVER','position':(0,0),'channel':1,'move_cost_s':0}, {'type':'EXIT','position':(0,0),'channel':0}]
    s=public_state({'problem':3,'position':(0,0),'current_channel':1},states,acts)
    assert s['global'].shape==(10,) and s['channels'].shape==(20,9) and s['candidates'].shape==(2,11)
    m=CandidatePolicy(); logits,value=m({k:torch.tensor(v,dtype=torch.float32)[None] for k,v in s.items()},torch.tensor([[True,False]]))
    assert logits.shape==(1,2) and value.shape==(1,)
    dist=masked_distribution(logits,torch.tensor([[True,False]])); assert int(dist.sample())==0
