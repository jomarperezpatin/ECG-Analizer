import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from proyecto import convolution

class TestBackend(unittest.TestCase):
    def setUp(self): self.client = TestClient(app)
    def test_health(self): self.assertTrue(self.client.get('/api/health').json()['real_acquisition']); self.assertFalse(self.client.get('/api/health').json()['clinical_acquisition'])
    def test_convolution(self): self.assertEqual(convolution([1,2,3],[1,1]).tolist(),[1,3,5,3])
    def test_simulation(self):
        for fs in (100,250,500):
            d=self.client.post('/api/ecg/simulate',json={'samples':fs*2,'fs':fs}).json()
            self.assertEqual(len(d['raw']),fs*2); self.assertEqual(d['filtered'][:9],[None]*9)
            self.assertEqual(d['time'][1],1/fs); self.assertEqual(d['source'],'python')
    def test_validation(self):
        for payload in ({'samples':1,'fs':100},{'samples':200,'fs':60},{'samples':200.5,'fs':100}):
            self.assertEqual(self.client.post('/api/ecg/simulate',json=payload).status_code,422)
    def test_ports_mocked(self):
        with patch('main.list_ports',return_value=[{'device':'COM8','candidate':True}]):
            d=self.client.get('/api/ports').json(); self.assertFalse(d['verified']); self.assertEqual(d['ports'][0]['device'],'COM8')
    def test_port_error(self):
        with patch('main.list_ports',side_effect=ImportError):
            self.assertEqual(self.client.get('/api/ports').status_code,503)

if __name__ == '__main__': unittest.main()
