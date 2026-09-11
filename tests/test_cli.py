import unittest
import subprocess
import sys
import socket
import time
import json
from pathlib import Path
from bsim.client import RobotClient
from tests.support import ROOT


class CLI(unittest.TestCase):
    def runcli(self,*args):
        return subprocess.run([sys.executable,'-m','bsim',*args],cwd=ROOT,capture_output=True,text=True,timeout=10)

    def test_profile_block_and_replay_cli(self):
        result=self.runcli('serve','--profile','strict_official')
        self.assertEqual(result.returncode,2);self.assertIn('G02',result.stderr)
        result=self.runcli('serve','--profile','compatible_research')
        self.assertEqual(result.returncode,2)
        result=self.runcli('replay','--fixture','fixtures/timing.json','--trace','fixtures/timing.trace.json')
        self.assertEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout)['status'],'PASS')
        result=self.runcli('benchmark','--device','cuda','--num-envs','256')
        self.assertEqual(result.returncode,2);self.assertIn('NOT_IMPLEMENTED',result.stderr)

    def test_separate_server_and_socket_lifecycle(self):
        # Bind ephemeral port locally; never contacts default official port 2026.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        process=subprocess.Popen([sys.executable,'-m','bsim','serve','--profile','fixture_conformance',
                                  '--fixture','fixtures/timing.json','--port',str(port)],cwd=ROOT,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            line=process.stdout.readline();self.assertIn('LOCAL',line)
            with self.assertRaises(OSError):socket.create_connection(('127.0.0.1',port),timeout=.1)
            deadline=time.monotonic()+7
            while time.monotonic()<deadline:
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.05)
            else:self.fail('server did not open after countdown')
            client=RobotClient('http://127.0.0.1:%d'%port,'LOCAL-TEAM',retries=0)
            times=[]
            for path,p,ch in [('/enter',None,None),('/measure',(300,400),1),('/measure',(300,400),2),('/clear',(300,0),3),('/measure',(300,0),2),('/exit',None,None)]:
                times.append(client.act(path,p,ch)[1]['virtual_time_s'])
            self.assertEqual(times,[0,105,111,194,199,199])
            self.assertEqual(process.wait(3),0)
            with self.assertRaises(OSError):socket.create_connection(('127.0.0.1',port),timeout=.1)
        finally:
            if process.poll() is None:process.terminate();process.wait(3)
            process.stdout.close();process.stderr.close()
