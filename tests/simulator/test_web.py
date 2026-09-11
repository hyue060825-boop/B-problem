import json
import socket
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from bsim.web_dashboard import Dashboard, DashboardServer
from bsim.client import RobotClient


class WebDashboard(unittest.TestCase):
    def setUp(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); robot_port=sock.getsockname()[1]
        self.manager=Dashboard(robot_port)
        self.server=DashboardServer(('127.0.0.1',0),self.manager,'TEST-TOKEN')
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01})
        self.thread.start()
        self.url='http://127.0.0.1:%d'%self.server.server_address[1]

    def tearDown(self):
        self.manager.close();self.server.shutdown();self.server.server_close();self.thread.join(2)

    def request(self,path,data=None,token='TEST-TOKEN',origin=None):
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token}
        if origin:headers['Origin']=origin
        req=Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            with urlopen(req,timeout=3) as res:return res.status,json.loads(res.read())
        except HTTPError as res:return res.code,json.loads(res.read())

    def start(self,fixture='mixed'):
        code,state=self.request('/api/start',{'fixture':fixture});self.assertEqual(code,200)
        self.assertEqual(state['phase'],'countdown')
        # Explicit TEST-only time shortcut; HTTP has no skip-countdown endpoint.
        self.manager.session.countdown_end=self.manager.session.clock.monotonic()
        limit=time.monotonic()+2
        while time.monotonic()<limit:
            try:
                with socket.create_connection(('127.0.0.1',self.manager.robot_port),timeout=.1):break
            except OSError:time.sleep(.02)
        else:self.fail('robot server failed to listen')
        return state['session_id']

    def test_auth_and_separate_truth(self):
        for path in ('/api/state','/api/debug/truth','/api/export'):
            self.assertEqual(self.request(path,token='wrong')[0],401)
        self.assertEqual(self.request('/api/start',{'fixture':'timing'},origin='https://external.invalid')[0],403)
        self.assertEqual(self.manager.snapshot()['phase'],'idle')
        sid=self.start()
        state=self.request('/api/state')[1]
        for key in ('sources','radius','heading','N','noise'):
            self.assertNotIn(key,state)
        truth=self.request('/api/debug/truth')[1]
        self.assertEqual(len(truth['sources']),10)
        self.assertEqual(truth['session_id'],sid)
        with urlopen(self.url+'/') as res:
            html=res.read().decode();self.assertNotIn('TEST-TOKEN',html)
        # Robot port still exposes only four official actions, never admin truth.
        req=Request('http://127.0.0.1:%d/api/debug/truth'%self.manager.robot_port,data=b'{}',headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as err:urlopen(req)
        self.assertEqual(err.exception.code,404)

    def test_manual_actions_external_client_export_and_abort(self):
        sid=self.start('timing')
        def act(name,p=None,ch=None):
            d={'session_id':sid,'action':name}
            if p is not None:d['position']=p;d['channel']=ch
            return self.request('/api/action',d)
        self.assertTrue(act('enter')[1]['response']['accepted'])
        self.assertEqual(act('measure',[300,400],1)[1]['response']['virtual_time_s'],105)
        # An independent policy client is reflected in the dashboard too.
        external=RobotClient('http://127.0.0.1:%d'%self.manager.robot_port,'LOCAL-TEAM')
        self.assertTrue(external.act('/measure',(3,4),7)[1]['accepted'])
        self.assertEqual(act('clear',[3,4],7)[1]['response']['clear_result'],'success')
        state=self.request('/api/state')[1]
        self.assertEqual(state['cleared_count'],1);self.assertEqual(len(state['events']),4)
        log=self.request('/api/export')[1]
        self.assertTrue(log['label'].startswith('LOCAL-'))
        self.assertEqual(len(log['records']),4)
        self.assertNotIn('sources',json.dumps(log))
        self.assertEqual(self.request('/api/abort',{'session_id':'stale'})[0],400)
        self.assertEqual(self.request('/api/abort',{'session_id':sid})[1]['phase'],'ended')
        self.manager.worker.join(2)
        self.assertFalse(self.manager.worker.is_alive())
        with self.assertRaises(OSError):socket.create_connection(('127.0.0.1',self.manager.robot_port),timeout=.1)
        new_sid=self.start('timing');self.assertNotEqual(sid,new_sid)
        self.assertEqual(self.request('/api/action',{'session_id':sid,'action':'enter'})[0],400)

    def test_conflicts_unknown_fixture_and_port_busy(self):
        self.assertEqual(self.request('/api/start',{'fixture':'../../outside'})[0],400)
        self.assertEqual(self.request('/api/start',{'fixture':'strict_official'})[0],400)
        with socket.socket() as blocker:
            blocker.bind(('127.0.0.1',self.manager.robot_port));blocker.listen()
            self.assertEqual(self.request('/api/start',{'fixture':'timing'})[0],400)
        sid=self.start()
        self.assertEqual(self.request('/api/start',{'fixture':'timing'})[0],400)
        self.assertEqual(self.request('/api/action',{'session_id':sid,'action':'reset'})[0],400)
