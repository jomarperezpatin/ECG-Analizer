import io
import json
import os
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
import backup
import database as storage
from proyecto import simulate

# Fake BSON codec ONLY for exercising archive control flow without installed PyMongo.
# Real BSON/PyMongo integration is tested separately on the user's Windows system.
class FakeBSON:
    def __init__(self,data):self.data=data
    @staticmethod
    def encode(doc):
        data=json.dumps(doc,default=lambda b:{'__test_bytes__':list(b)}).encode()+b'\0'
        return struct.pack('<i',len(data)+4)+data
    def decode(self):
        return json.loads(self.data[4:-1],object_hook=lambda v:bytes(v['__test_bytes__']) if '__test_bytes__' in v else v)
class Collection:
    def __init__(self,rows=()):self.rows=list(rows)
    def find(self,_):return iter(self.rows)
    def insert_one(self,doc):self.rows.append(doc)
class DB:
    def __init__(self,name):self.name=name;self.collections={}
    def __getitem__(self,name):return self.collections.setdefault(name,Collection())
    def create_collection(self,name):self.collections[name]=Collection()
class Client:
    def __init__(self):self.dbs={}
    def __getitem__(self,name):return self.dbs.setdefault(name,DB(name))
    def list_database_names(self):return [k for k,v in self.dbs.items() if v.collections]
    def drop_database(self,name):self.dbs.pop(name,None)

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.client=Client(); self.source=self.client['ecg_database']; self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'test.ecgbackup'; ident='a'*32
        self.patient={'_id':ident,'name':'Ficticio','age':25,'weight':75,'height':175,'bmi':24.49}
        study=storage.prepare(storage.Study(**simulate(500,250),id=ident,date='2026-11-26T14:00:00Z',patient=self.patient))
        self.study={'_id':ident,**study,'patient_id':ident,'image_png':b'\x89PNG\r\n\x1a\nexample'}
        self.source['pacientes'].insert_one(self.patient);self.source['estudios'].insert_one(self.study)
        self.codec=patch.dict(sys.modules,{'bson':SimpleNamespace(BSON=FakeBSON)});self.codec.start();self.addCleanup(self.codec.stop)
    def test_roundtrip(self):
        self.assertEqual(backup.write_backup(self.p,self.source),{'pacientes':1,'estudios':1})
        name,counts=backup.restore_backup(self.p,self.client)
        self.assertNotEqual(name,self.source.name);self.assertEqual(counts['estudios'],1)
        self.assertEqual(self.client[name]['estudios'].rows,[self.study]);self.assertEqual(self.source['estudios'].rows,[self.study])
    def test_no_overwrite(self):
        self.p.write_bytes(b'previous')
        with self.assertRaises(FileExistsError):backup.write_backup(self.p,self.source)
        self.assertEqual(self.p.read_bytes(),b'previous')
    def test_corrupt_archive(self):
        with zipfile.ZipFile(self.p,'w') as z:z.writestr('manifest.json','{}')
        with self.assertRaises(ValueError):backup.restore_backup(self.p,self.client)
        self.assertEqual(self.client.list_database_names(),[self.source.name])
    def test_wrong_schema(self):
        self.study['id']='wrong'
        self.study['_id']=123
        backup.write_backup(self.p,self.source)
        self.assertFalse(backup.archive_compatible(self.p))
        name,counts=backup.restore_backup(self.p,self.client)
        self.assertNotIn(name,backup.restored)
        self.assertEqual(self.client[name]['estudios'].rows,[self.study])
        self.assertEqual(self.source['estudios'].rows,[self.study])
    def test_legacy_patient_ids_and_gridfs(self):
        self.patient['_id']=123; self.patient['patient_id']='legacy'
        self.study['_id']=456; self.study['patient_id']='legacy'
        self.source['fs.files'].insert_one({'_id':1,'length':4})
        self.source['fs.chunks'].insert_one({'_id':2,'files_id':1,'n':0,'data':b'abcd'})
        with patch.object(self.source,'list_collection_names',lambda:list(self.source.collections),create=True):
            backup.write_backup(self.p,self.source)
        name,counts=backup.restore_backup(self.p,self.client)
        self.assertEqual(counts['fs.chunks'],1)
        self.assertNotIn(name,backup.restored)
        for c in self.source.collections:
            self.assertEqual(self.source[c].rows,self.client[name][c].rows)
    def test_selection(self):
        with patch.dict(os.environ,{'ECG_API_TOKEN':'test','ECG_MONGO_DB':'original'}),patch.object(backup,'restored',{'ecg_restore_test'}),patch.object(storage,'selected_database',None):
            self.assertEqual(backup.select(backup.SelectRequest(database='ecg_restore_test'))['database'],'ecg_restore_test')
            self.assertEqual(backup.select(backup.SelectRequest())['database'],'original')
            with self.assertRaises(Exception):backup.select(backup.SelectRequest(database='arbitrary'))
    def test_managed_only(self):
        with patch.dict(os.environ,{'ECG_API_TOKEN':''}):
            r=TestClient(app).post('/api/backup/create',json={'path':str(self.p)})
            self.assertEqual(r.status_code,403)
    def test_invalid_path(self):
        for p in ['relative.ecgbackup',str(self.p.with_suffix('.zip'))]:
            with self.assertRaises(ValueError):backup.checked_path(p)
    def test_truncated(self):
        with self.assertRaises(ValueError):list(backup.docs(io.BytesIO(struct.pack('<i',9)+b'x')))

if __name__=='__main__':unittest.main()
