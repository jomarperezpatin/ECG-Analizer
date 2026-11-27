import unittest
import numpy as np
from fastapi.testclient import TestClient
from main import app
from analysis import analyze
from proyecto import convolution

class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.t=np.arange(2500)/250
        self.x=np.sin(2*np.pi*10*self.t)+2*np.sin(2*np.pi*60*self.t)
    def test_moving(self):
        r=analyze(self.x,250,'moving',5)
        self.assertEqual(r['filtered'][:4],[None]*4)
        self.assertEqual(r['delay_samples'],2)
        np.testing.assert_allclose(r['filtered'][4:],convolution(self.x,np.ones(5)/5)[4:len(self.x)])
    def test_constant(self):
        r=analyze([300]*500,250); self.assertIsNone(r['original_peak'])
    def test_removed_filters(self):
        for name in ('none','notch','bandpass','combined'):
            with self.assertRaises(ValueError): analyze(self.x,250,name)
    def test_irregular(self):
        t=self.t.copy();t[50]+=.002
        with self.assertRaises(ValueError): analyze(self.x,250,'moving',timestamps=t)
    def test_api(self):
        c=TestClient(app);r=c.post('/api/ecg/analyze',json={'raw':self.x.tolist(),'fs':250,'kind':'moving','timestamps':self.t.tolist()});self.assertEqual(r.status_code,200);self.assertAlmostEqual(r.json()['original_peak'],60,delta=.11)
        self.assertEqual(c.post('/api/ecg/analyze',json={'raw':[0]*200,'fs':100,'kind':'notch'}).status_code,422)
    def test_legacy_experimental_denied(self):
        c=TestClient(app); self.assertEqual(c.post('/api/bench/start',json={'port':'COM8','samples':600,'fs':100,'protocol':'numeric','mode':'experimental','confirmed_experimental':True}).status_code,422)
