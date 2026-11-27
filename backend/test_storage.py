import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import sys
import base64
from fastapi.testclient import TestClient
from main import app
from database import prepare, png, Study
from proyecto import simulate

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.http=TestClient(app)
        self.payload={**simulate(500,250),'id':'a'*32,'date':'2026-11-26T14:00:00Z','patient':{'name':'Ana María Pérez','age':25,'weight':75,'height':175},'filter_kind':'moving'}
    def test_prepare_and_png(self):
        r=prepare(Study(**self.payload))
        self.assertEqual(r['raw'],self.payload['raw']); self.assertEqual(len(r['filtered']),500)
        self.assertAlmostEqual(r['patient']['bmi'],24.4898,places=3)
        self.assertEqual(r['resolution'],250/491); self.assertTrue(png(r).startswith(b'\x89PNG\r\n\x1a\n'))
    def test_invalid_samples(self):
        r={**self.payload,'samples':501}; self.assertEqual(self.http.post('/api/storage/save',json=r).status_code,422)
    def test_invalid_bench(self):
        r={**self.payload,'mode':'bench','state':'stopped'}; self.assertEqual(self.http.post('/api/storage/save',json=r).status_code,422)
    def test_experimental_storage(self):
        p={**self.payload,'mode':'experimental','state':'complete','raw':[512]*500,'lead':[0]*500,'patient':{**self.payload['patient'],'name':'EXP-001'}}
        r=prepare(Study(**p)); self.assertEqual(r['source'],'arduino'); self.assertEqual(r['mode'],'experimental'); self.assertTrue(png(r).startswith(b'\x89PNG'))
        invalid={**p,'lead':[1]+[0]*499}
        self.assertEqual(self.http.post('/api/storage/save',json=invalid).status_code,422)
        named=prepare(Study(**{**p,'patient':{**p['patient'],'name':'  Ana María Pérez  '}}))
        self.assertEqual(named['patient']['name'],'Ana María Pérez')
        self.assertTrue(png(named).startswith(b'\x89PNG'))
    def test_invalid_patient_name(self):
        for name in ('   ','Ana\nPérez','x'*161):
            p={**self.payload,'patient':{**self.payload['patient'],'name':name}}
            self.assertEqual(self.http.post('/api/storage/save',json=p).status_code,422)
    def test_unavailable(self):
        with patch('database.client',side_effect=RuntimeError):
            self.assertEqual(self.http.get('/api/storage/health').status_code,503)
    def test_archive_mock(self):
        # Fake driver and collections: verify route flow, not real BSON or MongoDB.
        docs={}; patients={}
        d=MagicMock()
        def find(q,projection=None):
            r=docs.get(q['_id']); return None if r is None else {k:v for k,v in r.items() if not projection or projection.get(k,1)!=0}
        d.estudios.find_one.side_effect=find
        d.estudios.replace_one.side_effect=lambda q,doc,upsert:docs.update({q['_id']:doc})
        d.pacientes.update_one.side_effect=lambda q,update,upsert:patients.update({q['_id']:update['$set']})
        d.pacientes.find_one.side_effect=lambda q:patients.get(q['_id'])
        d.estudios.delete_one.side_effect=lambda q:SimpleNamespace(deleted_count=int(docs.pop(q['_id'],None) is not None))
        fake_bson=SimpleNamespace(BSON=SimpleNamespace(encode=lambda x:b'fake'),Binary=lambda b:b)
        with patch('database.db',return_value=d),patch.dict(sys.modules,{'bson':fake_bson}):
            p=self.payload; ident=p['id']
            response=self.http.post('/api/storage/save',json=p)
            self.assertEqual(response.status_code,200,response.text); self.assertEqual(response.json()['patient_id'],ident)
            self.assertEqual(len(docs),1); self.assertEqual(len(patients),1); self.assertEqual(patients[ident]['name'],'Ana María Pérez')
            response=self.http.post('/api/storage/save',json={**p,'filter_kind':'moving','window':5})
            self.assertEqual(response.status_code,200,response.text); self.assertEqual(len(docs),1)
            r=self.http.post('/api/storage/get',json={'id':ident}).json(); self.assertEqual(r['window'],5); self.assertNotIn('image_png',r)
            im=self.http.post('/api/storage/image',json={'id':ident}).json();self.assertTrue(base64.b64decode(im['png']).startswith(b'\x89PNG'))
            response=self.http.post('/api/storage/save',json={**p,'id':'b'*32,'patient_id':ident});self.assertEqual(response.status_code,200,response.text); self.assertEqual(len(patients),1)
            self.assertEqual(self.http.post('/api/storage/delete',json={'id':ident}).status_code,200);self.assertEqual(self.http.post('/api/storage/get',json={'id':ident}).status_code,404)
    def test_list_search(self):
        d=MagicMock(); d.estudios.find.return_value.sort.return_value.limit.return_value=[{'id':'a'*32}]
        with patch('database.db',return_value=d):
            r=self.http.get('/api/storage/list',params={'q':'a.*'}); self.assertEqual(r.json()['records'],[{'id':'a'*32}]); self.assertEqual(d.estudios.find.call_args.args[0]['patient.name']['$regex'],r'a\.\*')
if __name__=='__main__':unittest.main()

class LegacyStorageTests(unittest.TestCase):
    def test_legacy_metadata(self):
        p={**simulate(200,100),'id':'a'*32,'date':'2026-11-26T14:00:00Z','patient':{'name':'Prueba','age':25,'weight':75,'height':175},'mode':'bench','state':'complete','raw':[512]*200,'lead':[-1]*200}
        r=prepare(Study(**p));self.assertEqual(r['timing'],'nominal');self.assertIsNone(r['observed_fs']);self.assertEqual(r['filter_kind'],'moving');self.assertTrue(png(r).startswith(b'\x89PNG'))
        with self.assertRaises(ValueError): prepare(Study(**{**p,'mode':'experimental'}))
