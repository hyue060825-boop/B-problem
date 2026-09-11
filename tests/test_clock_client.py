import unittest
from dataclasses import replace
from decimal import Decimal
from bsim.session import InterfaceClosed, Session
from bsim.client import RobotClient, public_response
from bsim.clocks import ManualClock
from bsim.protocol import encode
from tests.support import make,call,payload,HEADERS


class ClockClient(unittest.TestCase):
    def test_lifecycle_and_late_enter(self):
        for elapsed,remaining in [(60,1200),(300,1200),(600,900),(1499.5,0)]:
            s=make(); s.clock.advance(elapsed)
            self.assertEqual(call(s,'/enter','enter')[1]['remaining_real_duration_s'],remaining)
        s=make(); s.clock.advance(1500)
        with self.assertRaises(InterfaceClosed):call(s,'/enter','enter')
        s=make(); s.phase='idle'; s.window_open=None; s.prepare(); s.data_ready()
        with self.assertRaises(InterfaceClosed):call(s,'/enter','enter')
        s.clock.advance(5); self.assertTrue(call(s,'/enter','enter')[1]['accepted'])
        s.clock.advance(1200)
        with self.assertRaises(InterfaceClosed):call(s,'/exit','exit')
        s=make();call(s,'/enter','enter');s.abort()
        with self.assertRaises(InterfaceClosed):call(s,'/exit','exit')

    def test_registered_action_finishes_and_virtual_crossing(self):
        s=make();call(s,'/enter','enter');s.clock.advance(1199)
        original=s.kernel.transition
        def transition(*args):
            s.clock.advance(5)
            return original(*args)
        s.kernel.transition=transition
        self.assertTrue(call(s,'/measure','late',(6,0),7)[1]['accepted'])
        self.assertEqual(s.phase,'ended')
        s=make();call(s,'/enter','enter')
        s.state=replace(s.state,virtual_us=359999000000)
        self.assertEqual(call(s,'/measure','cross',(0,0),1)[1]['virtual_time_s'],360004)
        self.assertEqual(s.reason,'virtual_timeout')
        with self.assertRaises(InterfaceClosed):call(s,'/exit','exit')

    def test_noninteger_movement_microseconds(self):
        s=make();call(s,'/enter','enter')
        # Independent decimal expected sqrt(2)/5 rounded to integer us = 282843.
        for i in range(100):
            call(s,'/measure','step%d'%i,(1,1) if i%2==0 else (0,0),1)
        self.assertEqual(s.state.virtual_us,100*(5000000+282843))
        self.assertEqual(s.kernel.numerics.movement_us(Decimal('.0000025')),1)

    def test_client_lost_response_and_pending(self):
        s=make(); seen=[]
        def transport(path, raw):
            seen.append(raw)
            out=s.request('POST',path,HEADERS,raw)
            if len(seen)==1: raise OSError('lost response')
            return out
        c=RobotClient('http://127.0.0.1:1','LOCAL-TEAM',transport=transport)
        self.assertTrue(c.act('/enter')[1]['accepted'])
        self.assertEqual(seen[0],seen[1]);self.assertEqual(len(s.events),1)
        c.act('/measure',(300,400),1); t=c.virtual_time_s
        c.act('/enter');self.assertEqual(c.virtual_time_s,t)
        def failing(path, raw): raise OSError('closed')
        c=RobotClient('http://127.0.0.1:1','LOCAL-TEAM',retries=0,transport=failing)
        with self.assertRaises(OSError):c.act('/enter')
        with self.assertRaises(RuntimeError):c.act('/exit')
        with self.assertRaises(OSError):c.retry_pending()

    def test_response_leakage_and_history(self):
        base={'accepted':True,'real_timestamp_ms':0,'virtual_time_s':0,'measure_result':'near'}
        for key in ('N','radius','source_id','reward','sources','seed','remaining_count'):
            with self.assertRaises(ValueError):public_response('/measure',{**base,key:1})
        from bsim.scenarios import Source
        sessions=[make([]),make([Source(7,1700,0,1000,'omni')])]
        histories=[]
        for s in sessions:
            # Identical explicit request histories, different truth on unobserved channel.
            call(s,'/enter','enter'); response=call(s,'/measure','m',(0,0),1)[1]
            histories.append(public_response('/measure',response))
        self.assertEqual(*histories)
