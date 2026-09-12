import math

from solution.belief.q4_directional import Hypothesis, Q4DirectionalBelief, _visible
from solution.control.controller import Controller


def test_visibility_matches_cardinal_boundaries_and_invisible_overlap():
    source = Hypothesis((0.,0.),1000.,'directional',0.)
    assert _visible(source,(1000.,0.))
    assert _visible(source,(0.,1000.))
    assert not _visible(source,(-0.001,0.))
    assert not _visible(source,(0.,0.))
    assert not _visible(source,(1000.001,0.))


def test_weighted_summary_reports_ess_and_defined_proxy_entropy():
    belief=Q4DirectionalBelief([
        Hypothesis((0.,0.),1000.,'omni',None,3.),
        Hypothesis((1500.,0.),1000.,'directional',180.,1.)],age=4,requested_count=2)
    summary=belief.summary_at((500.,0.))
    assert math.isclose(summary.effective_sample_size,1/(.75**2+.25**2))
    assert summary.particle_count==2 and summary.age==4 and summary.degenerate
    assert summary.receive_entropy>=0


def test_same_public_history_reproduces_belief_and_actions():
    a,b=Controller(4),Controller(4)
    public=[(1,(0.,0.),'direction',12.5),(1,(100.,0.),'no_signal',None)]
    for channel,point,result,angle in public:
        a.observe(channel,point,result,angle)
        b.observe(channel,point,result,angle)
    assert a.legal_actions()==b.legal_actions()
    assert a.q4_beliefs[1].hypotheses==b.q4_beliefs[1].hypotheses


def test_belief_never_changes_q4_absence_certificate():
    controller=Controller(4)
    controller.observe(1,(0.,0.),'direction',0.)
    controller.observe(1,(-1800.,0.),'no_signal')
    assert controller.channels[1].status in ('LOCALIZING','CLEARABLE')
    assert not controller.exit_allowed()
