import threading, time, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from bench import Bench

class FakeSerial:
    def __init__(self, lead=1, gap=False): self.buf=[]; self.seq=0; self.lead=lead; self.gap=gap; self.commands=[]
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def reset_input_buffer(self): pass
    def write(self,cmd):
        cmd=cmd.decode().strip();self.commands.append(cmd)
        self.buf.append({'HELLO':'ECG,1,250','START':'OK,START','STOP':'OK,STOP'}[cmd])
    def readline(self):
        if self.buf: return self.buf.pop(0).encode()
        n=self.seq+(1 if self.gap and self.seq>0 else 0);self.seq+=1
        return f'DATA,{n},{n*4000+12},720,{self.lead}'.encode()

class Tests(unittest.TestCase):
    def capture(self,serial,mode='bench'):
        b=Bench();e=threading.Event();j=dict(id='test',port='COM8',samples=500,mode=mode,state='connecting',rows=[],error='',cancel=e,heartbeat=time.monotonic());b.job=j
        with patch('bench.open_serial',return_value=serial),patch.object(e,'wait',return_value=False): b.run(j)
        return b.status('test')
    def test_capture(self):
        s=FakeSerial();r=self.capture(s);self.assertEqual(r['state'],'complete');self.assertEqual(len(r['raw']),500);self.assertEqual(r['observed_fs'],250);self.assertEqual(r['lead'][-1],1);self.assertEqual(r['filtered'][:9],[None]*9);self.assertEqual(s.commands,['HELLO','START','STOP'])
    def test_gap(self):
        s=FakeSerial(gap=True);r=self.capture(s);self.assertEqual(r['state'],'error');self.assertIn('Pérdida',r['error']);self.assertEqual(s.commands[-1],'STOP')
    def test_leads_disabled(self):
        s=FakeSerial(lead=-1);r=self.capture(s);self.assertEqual(r['state'],'error');self.assertEqual(s.commands[-1],'STOP')
    def test_api_reject(self):
        c=TestClient(app);self.assertEqual(c.post('/api/bench/start',json={'port':'COM8','samples':600,'confirmed_bench':False}).status_code,422)
        with patch('main.list_ports',return_value=[]): self.assertEqual(c.post('/api/bench/start',json={'port':'COM8','samples':600,'confirmed_bench':True}).status_code,422)
    def test_experimental_lo(self):
        r=self.capture(FakeSerial(lead=0),'experimental'); self.assertEqual(r['state'],'complete'); self.assertEqual(r['mode'],'experimental')
        s=FakeSerial(lead=1); r=self.capture(s,'experimental'); self.assertEqual(r['state'],'error'); self.assertIn('desconectados',r['error']); self.assertEqual(s.commands[-1],'STOP')
    def test_experimental_confirmation(self):
        c=TestClient(app)
        p={'port':'COM8','samples':600,'mode':'experimental','confirmed_bench':True}
        self.assertEqual(c.post('/api/bench/start',json=p).status_code,422)
        with patch('main.list_ports',return_value=[{'device':'COM8'}]),patch('main.bench.start',return_value='id') as start:
            self.assertEqual(c.post('/api/bench/start',json={**p,'confirmed_experimental':True}).status_code,200); start.assert_called_once_with('COM8',600,'experimental',250,'ecg1')
    def test_permission_error(self):
        b=Bench();e=threading.Event();j=dict(id='test',port='COM8',samples=500,mode='bench',state='connecting',rows=[],error='',cancel=e,heartbeat=time.monotonic());b.job=j
        with patch('bench.open_serial',side_effect=PermissionError('Acceso denegado')): b.run(j)
        r=b.status('test');self.assertEqual(r['state'],'error');self.assertEqual(r['raw'],[]);self.assertIn('Puerto COM8 ocupado',r['error'])
    def test_stop_failure_preserves_capture_error(self):
        class BrokenStop(FakeSerial):
            def write(self,cmd):
                if cmd==b'STOP\n':raise IOError('STOP fallo')
                return super().write(cmd)
        r=self.capture(BrokenStop(gap=True));self.assertEqual(r['state'],'error');self.assertIn('Pérdida',r['error'])
    def test_cancel(self):
        b=Bench();e=threading.Event();b.job=dict(id='test',state='running',cancel=e);b.stop('test');self.assertTrue(e.is_set())

class LegacySerial:
    def __init__(self,lines): self.lines=iter(lines); self.writes=[]; self.closed=False
    def __enter__(self): return self
    def __exit__(self,*args): self.closed=True
    def reset_input_buffer(self): pass
    def readline(self): return next(self.lines).encode()
    def write(self,b): self.writes.append(b)

class LegacyTests(unittest.TestCase):
    def test_numeric_format(self):
        from bench import parse_legacy
        self.assertEqual(parse_legacy('512'),512)
        self.assertEqual(parse_legacy('0,1023,600'),600)
        for value in ['DATA,0,10000,512,0','nan','1024','-1','2,3,4','ECG:512','1.2']:
            with self.assertRaises(ValueError): parse_legacy(value)
    def capture(self,lines):
        s=LegacySerial(lines); b=Bench(); e=threading.Event(); j=dict(id='legacy',port='COM8',samples=200,fs=100,protocol='numeric',mode='bench',state='connecting',rows=[],error='',cancel=e,heartbeat=time.monotonic()); b.job=j
        with patch('bench.open_serial',return_value=s),patch.object(e,'wait',return_value=False): b.run(j)
        self.assertTrue(s.closed);self.assertEqual(s.writes,[])
        return b.status('legacy')
    def test_legacy_reads_raw(self):
        r=self.capture(['partial']+[str(i) for i in range(200)])
        self.assertEqual(r['state'],'complete');self.assertEqual(r['raw'],list(range(200)));self.assertEqual(r['lead'],[-1]*200);self.assertEqual(r['timing'],'nominal');self.assertIsNone(r['observed_fs']);self.assertAlmostEqual(r['filtered'][9],4.5)
    def test_no_confusion_with_protocol(self):
        r=self.capture(['partial','DATA,0,10000,512,0'])
        self.assertEqual(r['state'],'error');self.assertEqual(r['raw'],[])
    def test_legacy_requires_bench(self):
        with self.assertRaises(ValueError): Bench().start('COM8',200,'experimental',100,'numeric')
    def test_legacy_api(self):
        c=TestClient(app)
        with patch('main.list_ports',return_value=[{'device':'COM8'}]),patch('main.bench.start',return_value='id') as start:
            self.assertEqual(c.post('/api/bench/start',json={'port':'COM8','samples':600,'fs':100,'confirmed_bench':True,'protocol':'numeric'}).status_code,200)
            start.assert_called_once_with('COM8',600,'bench',100,'numeric')

    def test_structured_100(self):
        class Serial100(FakeSerial):
            def write(self,cmd):
                super().write(cmd)
                if cmd==b'HELLO\n': self.buf[-1]='ECG,1,100'
            def readline(self):
                if self.buf: return self.buf.pop(0).encode()
                n=self.seq; self.seq+=1
                return f'DATA,{n},{n*10000+12},512,0'.encode()
        b=Bench();e=threading.Event();s=Serial100();j=dict(id='100',port='COM8',samples=200,fs=100,protocol='ecg1',mode='experimental',state='connecting',rows=[],error='',cancel=e,heartbeat=time.monotonic());b.job=j
        with patch('bench.open_serial',return_value=s),patch.object(e,'wait',return_value=False):b.run(j)
        r=b.status('100');self.assertEqual(r['state'],'complete');self.assertEqual(r['observed_fs'],100);self.assertEqual(r['timing'],'device');self.assertEqual(r['raw'],[512]*200)
