import unittest
from dataclasses import replace
from decimal import Decimal
from bsim.reference import State, distance
from bsim.noise import FixtureNoise, OfficialError
from bsim.profiles import Blocked, require_profile
from bsim.scenarios import Scenario, Source, OfficialGenerator
from tests.simulator.support import make, call


class Physics(unittest.TestCase):
    def test_omni_thresholds(self):
        k = make().kernel
        for p, expected in [((3,4),'near'),((6,0),'direction'),((1000,0),'direction'),
                            ((1000.000001,0),'no_signal'),((5.000001,0),'direction'),((0,0),'near')]:
            with self.subTest(p=p):
                result = k.observe(State(), p, 7)
                self.assertEqual(result['measure_result'], expected)
                self.assertEqual('svd_deg' in result, expected == 'direction')
        self.assertEqual(k.observe(State(), (6,0),7)['svd_deg'],180)
        self.assertEqual(k.observe(State(), (6,0),8),{'measure_result':'no_signal'})

    def test_direction_and_clear(self):
        s = make([Source(7,0,0,1000,'directional',0)])
        k = s.kernel
        for p, r in [((-3,0),'no_signal'),((0,6),'direction'),((0,-6),'direction'),((3,0),'near'),((-1e-9,6),'no_signal')]:
            self.assertEqual(k.observe(State(),p,7)['measure_result'],r)
        with self.assertRaises(Blocked):
            k.observe(State(),(0,0),7)
        state, out = k.transition(State(),'/clear',(-20,0),7)
        self.assertEqual(out['clear_result'],'success')
        self.assertEqual(state.channel,1)
        self.assertEqual(state.virtual_us,9000000)
        self.assertEqual(k.transition(state,'/clear',(-20,0),7)[1]['clear_result'],'no_target_in_range')
        self.assertEqual(k.observe(state,(6,0),7)['measure_result'],'no_signal')
        self.assertEqual(k.transition(State(),'/clear',(20.000001,0),7)[1]['clear_result'],'no_target_in_range')

    def test_all_cardinal_halfplane_boundaries(self):
        for heading, p in [(0,(0,-6)),(90,(6,0)),(180,(0,6)),(270,(-6,0))]:
            k=make([Source(7,0,0,1500,'directional',heading)]).kernel
            self.assertEqual(k.observe(State(),p,7)['measure_result'],'direction')
            self.assertEqual(k.observe(State(),(p[0]*251,p[1]*251),7)['measure_result'],'no_signal')

    def test_error_endpoints_quantization_and_return(self):
        s=make(); call(s,'/enter','enter')
        for err in (-1,0,1):
            s.kernel.noise=FixtureNoise({'label':'TEST_INPUT','kind':'constant','value':err})
            a=call(s,'/measure',str(err)+'a',(6,0),7)[1]
            call(s,'/measure',str(err)+'b',(50,50),8)
            b=call(s,'/measure',str(err)+'c',(6,0),7)[1]
            self.assertEqual(a['svd_deg'],180+err)
            self.assertEqual(a['svd_deg'],b['svd_deg'])
        n=s.kernel.numerics
        self.assertEqual(n.angle(359.995),0)
        self.assertEqual(n.angle(-.005),0)
        self.assertEqual(n.angle(1.005),1.01)
        field=FixtureNoise({'label':'TEST_INPUT','kind':'table','entries':[{'channel':7,'x':6,'y':0,'error':1}]})
        self.assertEqual(field.error(7,6,0),1)
        with self.assertRaises(Blocked): field.error(7,6.000001,0)
        with self.assertRaises(ValueError): FixtureNoise({'label':'TEST_INPUT','kind':'constant','value':1.01})

    def test_atomic_failure_and_missing_profiles(self):
        s=make([Source(7,0,0,1000,'directional',0)])
        call(s,'/enter','enter'); before=s.state
        self.assertEqual(call(s,'/measure','blocked',(0,0),7)[0],500)
        self.assertEqual(s.state,before)
        self.assertIn('G06',s.last_error)
        self.assertNotIn('blocked',s.cache)
        for profile in ('strict_official','compatible_research'):
            with self.assertRaises(Blocked): require_profile(profile)
        with self.assertRaises(Blocked): OfficialGenerator().generate(1)
        with self.assertRaises(Blocked): OfficialError().error(7,0,0)

    def test_scenario_constraints(self):
        omni=[Source(c,c,0,1000,'omni') for c in range(1,11)]
        Scenario('LOCAL-3',3,'official_constraints',tuple(omni))
        with self.assertRaises(ValueError): Scenario('LOCAL-4',4,'official_constraints',tuple(omni))
        with self.assertRaises(ValueError): Scenario('LOCAL-short',3,'official_constraints',tuple(omni[:1]))
        with self.assertRaises(ValueError): Scenario('LOCAL-dup',3,'test_fixture',(omni[0],omni[0]))
        with self.assertRaises(ValueError): Source(7,1801,0,1000,'omni')
        with self.assertRaises(ValueError): Source(7,0,0,999,'omni')
        with self.assertRaises(ValueError): Source(True,0,0,1000,'omni')
        self.assertEqual(distance((0,0),(300,400)),Decimal(500))

    def test_fixture_rounding_variants_and_field_order(self):
        n=make().kernel.numerics
        self.assertEqual(replace(n,angle_rounding='half_even').angle(1.005),1.0)
        self.assertEqual(replace(n,angle_rounding='floor').angle(1.009),1.0)
        self.assertEqual(replace(n,time_rounding='half_even').movement_us(Decimal('.0000025')),0)
        self.assertEqual(replace(n,time_rounding='floor').movement_us(Decimal('.0000049')),0)
        spec={'label':'TEST_INPUT','kind':'table','entries':[
            {'channel':7,'x':6,'y':0,'error':1},{'channel':7,'x':0,'y':6,'error':-1}]}
        a=FixtureNoise(spec);b=FixtureNoise(spec)
        self.assertEqual(a.error(7,6,0),b.error(7,6,0))
        b.error(7,0,6)
        self.assertEqual(a.error(7,6,0),b.error(7,6,0))
        a.error(7,0,6)
        self.assertEqual(a.error(7,0,6),-1)
