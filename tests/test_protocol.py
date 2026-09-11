import unittest
import json
import threading
from bsim.protocol import encode, validate, Invalid
from tests.support import make, call, payload, HEADERS


class Protocol(unittest.TestCase):
    def setUp(self):
        self.s=make(); call(self.s,'/enter','enter')

    def raw(self, body, path='/measure', method='POST', headers=None):
        return self.s.request(method,path,headers or HEADERS,body)

    def test_official_timing_example(self):
        from bsim.evaluation import replay
        from tests.support import ROOT
        report=replay(ROOT/'fixtures/timing.json',ROOT/'fixtures/timing.trace.json')
        self.assertEqual([r['response']['virtual_time_s'] for r in report['records']],[0,105,111,194,199,199])
        self.assertEqual(report['status'],'PASS')

    def test_idempotence_and_rejections(self):
        raw=encode(payload('m',(300,400),1))
        a=self.raw(raw); self.s.clock.advance(1)
        self.assertEqual(a,self.raw(raw)); self.assertEqual(self.s.state.virtual_us,105000000)
        self.assertEqual(self.raw(encode(payload('m',(300,400),2)))[0],409)
        self.assertEqual(self.raw(raw,path='/clear')[0],409)
        before=self.s.state
        bad=payload('reuse',(100,100),1); bad['extra']=1
        self.assertEqual(self.raw(encode(bad))[0:1],(200,))
        self.assertFalse(self.raw(encode(bad))[1]['accepted'])
        self.assertEqual(self.s.state,before)
        self.assertTrue(self.raw(encode(payload('reuse',(100,100),1)))[1]['accepted'])
        for key,value in [('arena_id','other'),('robot_id','OTHER')]:
            d=payload('again'+key,(100,100),1); d[key]=value
            self.assertFalse(self.raw(encode(d))[1]['accepted'])
            self.assertNotIn('again'+key,self.s.cache)

    def test_json_invalids(self):
        good=encode(payload('valid',(0,0),1))
        bodies=[b'[]',b'null',b'{}',b'\xef\xbb\xbf'+good,b'\xff',good[:-1],
                good[:-1]+b',"channel":1}',good.replace(b'"channel":1',b'"channel":NaN'),
                good.replace(b'"channel":1',b'"channel":Infinity')]
        for raw in bodies:
            with self.subTest(raw=raw): self.assertEqual(self.raw(raw)[0],400)
        for val in (True,False,1.5,0,21,'1',None):
            self.assertEqual(self.raw(encode(payload('c',(0,0),val)))[0],400)
        self.assertTrue(self.raw(encode(payload('float',(0,0),1.0)))[1]['accepted'])
        for p in ((True,0),(2000000.001,0),(0,-2000000.001),('1',0)):
            self.assertEqual(self.raw(encode(payload('p',p,1)))[0],400)
        self.assertTrue(self.raw(encode(payload('limit',(2000000,0),1)))[1]['accepted'])

    def test_headers_paths_identifiers_size_depth(self):
        raw=encode(payload('h',(0,0),1))
        for path in ('/measure/','/measure?x=1','/reset','/MEASURE'):
            self.assertEqual(self.raw(raw,path=path)[0],404)
        for method in ('GET','PUT','DELETE','PATCH','OPTIONS'):
            self.assertEqual(self.raw(raw,method=method)[0],405)
        for content in ('text/plain','application/json; foo=bar','application/json; charset=gbk','application/json; charset=utf-8; charset=utf-8'):
            self.assertEqual(self.raw(raw,headers={'Content-Type':content})[0],415)
        self.assertEqual(self.raw(raw,headers={'Content-Type':'application/json','Content-Encoding':'gzip'})[0],415)
        self.assertTrue(self.raw(raw,headers={'Content-Type':'application/json; charset=utf-8'})[1]['accepted'])
        for val in ('','x'*129,'a\n','x\u200b','汉'*43,'\ud800'):
            d=payload(val,(0,0),1)
            self.assertEqual(self.raw(json.dumps(d).encode())[0],400)
        self.assertTrue(self.raw(encode(payload('汉'*42,(0,0),1)))[1]['accepted'])
        d=payload('nested',(0,0),1); d['position']['z']=0
        self.assertEqual(self.raw(encode(d))[1],self.s.rejection(200)[1])
        d=payload('size',(0,0),1); raw=encode(d)
        self.assertTrue(self.raw(raw+b' '*(65536-len(raw)))[1]['accepted'])
        self.assertEqual(self.raw(raw+b' '*(65537-len(raw)))[0],413)
        d=payload('deep',(0,0),1); value=0
        for _ in range(16): value={'a':value}
        d['extra']=value
        self.assertEqual(self.raw(encode(d))[0],400)
        # Root plus 15 nested objects is depth 16: structurally valid, unknown field.
        d['extra']=value['a']
        self.assertEqual(self.raw(encode(d))[0],200)

    def test_state_and_capacity(self):
        s=make(capacity=1)
        self.assertFalse(call(s,'/measure','pre',(0,0),1)[1]['accepted'])
        call(s,'/enter','enter')
        self.assertFalse(call(s,'/enter','twice')[1]['accepted'])
        self.assertEqual(call(s,'/measure','m',(0,0),1)[0],429)
        self.assertTrue(call(s,'/enter','enter')[1]['accepted'])

    def test_concurrent_actions(self):
        started=threading.Event(); finish=threading.Event()
        original=self.s.kernel.transition
        def slow(*args):
            started.set(); self.assertTrue(finish.wait(2)); return original(*args)
        self.s.kernel.transition=slow
        out=[]
        t=threading.Thread(target=lambda:out.append(call(self.s,'/measure','a',(6,0),7)))
        t.start(); self.assertTrue(started.wait(1))
        self.assertEqual(call(self.s,'/measure','b',(10,0),7)[0],409)
        same=threading.Thread(target=lambda:out.append(call(self.s,'/measure','a',(6,0),7)))
        same.start(); finish.set(); t.join(2); same.join(2)
        self.assertEqual(len(out),2); self.assertEqual(out[0],out[1])
        self.assertEqual(len(self.s.events),2)
