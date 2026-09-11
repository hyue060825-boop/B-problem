import unittest
from bsim.fast import FastKernel
from bsim.env import BatchEnv
from bsim.validation import compare_kernels
from bsim.evaluation import replay,compare_records,audit_public_trace,score
from tests.support import make,call,payload,ROOT


class Equivalence(unittest.TestCase):
    def test_generated_properties_and_boundaries(self):
        report=compare_kernels(ROOT/'fixtures/timing.json',5000)
        self.assertEqual(report['mismatches'],[])

    def test_batch_reference_and_fast_session(self):
        ref=make();fast=make(kernel_cls=FastKernel);batch=BatchEnv([fast])
        for path,rid,p,c in [('/enter','e',None,None),('/measure','m',(3,4),7),('/clear','c',(3,4),7),('/measure','n',(3,4),7),('/exit','x',None,None)]:
            code,body=call(ref,path,rid,p,c)
            out=batch.step([(path,payload(rid,p,c))])[0]
            self.assertEqual((out['status'],out['response']),(code,body));self.assertEqual(ref.state,fast.state)
        self.assertTrue(batch.step([('/exit',payload('x'))])[0]['connection_closed'])
        self.assertTrue(score(ref)['all_cleared'])

    def test_replay_and_observable_audit(self):
        a=replay(ROOT/'fixtures/timing.json',ROOT/'fixtures/timing.trace.json')
        b=replay(ROOT/'fixtures/timing.json',ROOT/'fixtures/timing.trace.json',FastKernel)
        self.assertEqual(compare_records(a['records'],b['records'],True),[])
        self.assertEqual(audit_public_trace(a['records'])['status'],'PASS')
        a['records'][1]['response']['virtual_time_s']=106
        self.assertEqual(audit_public_trace(a['records'])['status'],'FAIL')
        self.assertTrue(compare_records(a['records'],b['records']))
        self.assertIsNone(score(make())['time_per_clear_s'])
