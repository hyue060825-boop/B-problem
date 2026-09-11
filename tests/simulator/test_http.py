import unittest
import threading
import http.client
import socket
from bsim.http_server import LocalServer, serve_session
from bsim.client import RobotClient
from bsim.protocol import encode
from tests.simulator.support import make,payload,HEADERS,call


class Http(unittest.TestCase):
    def setUp(self):
        self.s=make();self.server=LocalServer(('127.0.0.1',0),self.s)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01})
        self.thread.start();self.port=self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)

    def request(self,method,path,body,headers=HEADERS):
        import json
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=2)
        try:
            c.request(method,path,body,headers);r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()

    def test_http_reference_exact_and_closed(self):
        ref=make()
        for path,rid,p,ch in [('/enter','e',None,None),('/measure','m',(300,400),1),('/clear','c',(300,0),3),('/exit','x',None,None)]:
            raw=encode(payload(rid,p,ch))
            self.assertEqual(self.request('POST',path,raw),ref.request('POST',path,HEADERS,raw))
            self.assertEqual(self.s.state,ref.state)
        with self.assertRaises(http.client.RemoteDisconnected):self.request('POST','/exit',encode(payload('x')))

    def test_wire_errors_and_retries(self):
        raw=encode(payload('e'))
        for method,path,headers,status in [('GET','/enter',HEADERS,405),('BREW','/enter',HEADERS,405),('POST','/enter/',HEADERS,404),('POST','/enter',{'Content-Type':'text/plain'},415)]:
            self.assertEqual(self.request(method,path,raw,headers)[0],status)
        self.assertEqual(self.request('POST','/enter',b'{}')[0],400)
        self.assertEqual(self.request('POST','/enter',raw)[0],200)
        self.assertEqual(self.request('POST','/enter',raw)[1]['virtual_time_s'],0)
        self.assertEqual(self.request('POST','/measure',b' ' * 65537)[0],413)
        c=RobotClient('http://127.0.0.1:%d'%self.port,'LOCAL-TEAM')
        self.assertTrue(c.act('/measure',(6,0),7)[1]['accepted'])

    def test_incomplete_body_past_deadline_does_not_execute(self):
        call(self.s,'/enter','entered')
        raw=encode(payload('late',(6,0),7))
        sock=socket.create_connection(('127.0.0.1',self.port),timeout=2)
        sock.sendall(('POST /measure HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n'%len(raw)).encode()+raw[:-1])
        self.s.clock.advance(1200)
        sock.sendall(raw[-1:])
        self.assertEqual(sock.recv(1024),b'');sock.close()
        self.assertNotIn('late',self.s.cache)
        self.assertEqual(self.s.state.virtual_us,0)

    def test_deep_json_returns_public_400_over_http(self):
        value = 0
        for _ in range(600):
            value = {'x': value}
        data = payload('deep')
        data['extra'] = value
        status, body = self.request('POST', '/enter', encode(data))
        self.assertEqual(status, 400)
        self.assertFalse(body['accepted'])
        self.assertEqual(body['virtual_time_s'], 0)
        self.assertNotIn('deep', self.s.cache)
