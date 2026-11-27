import os, sys, subprocess, time, unittest, urllib.request, urllib.error
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from database import render_report, prepare, Study
from proyecto import simulate
from datetime import datetime, timezone

class NewTests(unittest.TestCase):
    def test_token(self):
        with patch.dict(os.environ,{'ECG_API_TOKEN':'test-secret'}):
            c=TestClient(app)
            self.assertEqual(c.get('/api/health').status_code,401)
            self.assertEqual(c.get('/api/health',headers={'X-ECG-Token':'test-secret'}).status_code,200)
            self.assertEqual(c.get('/api/health',headers={'X-ECG-Token':'test-secret','Origin':'http://evil.invalid'}).status_code,403)
    def test_report_exports(self):
        r=prepare(Study(**simulate(500,250),id='a'*32,date=datetime.now(timezone.utc),patient={'name':'Ficticio','age':24,'weight':62,'height':171}))
        self.assertTrue(render_report(r,'pdf').startswith(b'%PDF'))
        with patch('database.get_study',return_value=r):
            from database import export_study, StudyId
            import base64
            data=export_study(StudyId(id='a'*32),'csv');self.assertIn('tiempo_s',base64.b64decode(data['content']).decode('utf-8-sig'))
    def test_process(self):
        p=subprocess.Popen([sys.executable,'launch.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,'ECG_API_TOKEN':'test-token'})
        try:
            line=p.stdout.readline().decode().strip(); self.assertTrue(line.startswith('ECG_PORT='),line)
            url='http://127.0.0.1:'+line.split('=')[1]+'/api/health'
            for _ in range(50):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url,headers={'X-ECG-Token':'test-token'}),timeout=.5) as r: self.assertEqual(r.status,200)
                    break
                except OSError: time.sleep(.1)
            else: self.fail('Servidor no disponible')
            p.stdin.close();self.assertEqual(p.wait(timeout=8),0)
        finally:
            if p.poll() is None:p.kill();p.wait()
            p.stdout.close();p.stderr.close()
if __name__=='__main__': unittest.main()
