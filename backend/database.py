"""Local study archive. Development data only; never bind the API to a public address."""
import os
import io
import math
import re
import base64
import threading
from datetime import datetime, timezone
from functools import lru_cache, wraps
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt, field_validator
from proyecto import convolution
from analysis import analyze
import numpy as np

router = APIRouter(prefix='/api/storage')
plot_lock = threading.Lock()
archive_lock = threading.RLock()
selected_database = None

def db_name():
    return selected_database or os.environ.get('ECG_MONGO_DB','ecg_database')

def locked(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with archive_lock:
            return fn(*args, **kwargs)
    return wrapped

ID_PATTERN = r'^[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}$'

class Patient(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    age: int = Field(ge=0, le=130)
    weight: float = Field(ge=0.1, le=500, allow_inf_nan=False)
    height: float = Field(ge=1, le=270, allow_inf_nan=False)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if not value.strip() or re.search(r'[\x00-\x1f\x7f]', value):
            raise ValueError('Nombre o código inválido')
        return value.strip()

class Study(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    patient_id: str | None = Field(default=None, pattern=ID_PATTERN)
    patient: Patient
    date: datetime
    mode: Literal['simulation','bench','experimental']
    state: str | None = None
    fs: StrictInt
    samples: StrictInt
    raw: list[float] = Field(min_length=200, max_length=30000)
    time: list[float] = Field(min_length=200, max_length=30000)
    lead: list[StrictInt] = Field(default_factory=list, max_length=30000)
    port: str | None = Field(default=None, max_length=100)
    filter_kind: Literal['none','moving','notch','bandpass','combined'] | None = None
    window: StrictInt = 10

class StudyId(BaseModel):
    id: str = Field(pattern=ID_PATTERN)

@lru_cache(maxsize=1)
def client():
    from pymongo import MongoClient
    return MongoClient(os.environ.get('ECG_MONGO_URI') or os.environ.get('MONGODB_URI') or 'mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, socketTimeoutMS=5000)

def db():
    return client()[db_name()]

def storage_error():
    return HTTPException(503,'MongoDB local no disponible. Verifica el servicio y la configuración ECG_MONGO_URI.')

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def prepare(s):
    if s.fs not in (100,250,500) or not 2*s.fs<=s.samples<=60*s.fs or len(s.raw)!=s.samples or len(s.time)!=s.samples:
        raise ValueError('Cantidad de muestras o frecuencia no válida')
    x=np.asarray(s.raw); t=np.asarray(s.time)
    if not np.all(np.isfinite(x)) or np.max(np.abs(x))>1e6 or not np.all(np.isfinite(t)) or abs(t[0])>1e-6 or np.any(np.diff(t)<=0):
        raise ValueError('Datos o marcas de tiempo inválidos')
    if s.mode in ('bench','experimental'):
        legacy=s.mode=='bench' and s.fs==100 and set(s.lead)=={-1}
        if (s.state!='complete' or (s.fs not in (100,250)) or len(s.lead)!=s.samples
            or not set(s.lead)<=({-1} if legacy else {0,1}) or np.any(x<0) or np.any(x>1023) or np.any(x!=np.floor(x))):
            raise ValueError('La captura física debe estar completa y contener datos ADC/LO válidos')
        if legacy and not np.allclose(t,np.arange(s.samples)/100,rtol=0,atol=1e-6):
            raise ValueError('Tiempo nominal incompatible con firmware numérico')
    if s.mode=='experimental' and any(s.lead):
        raise ValueError('Captura experimental: LO debe estar bajo en todas las muestras')
    if s.mode=='simulation' and s.lead:
        raise ValueError('Una simulación no tiene electrodos físicos')
    if s.date.tzinfo is None: raise ValueError('Fecha sin zona horaria')
    patient=s.patient.model_dump(); patient['name']=patient['name'].strip()
    if not patient['name']: raise ValueError('Nombre vacío')
    patient['bmi']=patient['weight']/(patient['height']/100)**2
    result=dict(id=s.id,patient=patient,date=s.date.astimezone(timezone.utc).isoformat(),mode=s.mode,state='complete',fs=s.fs,samples=s.samples,duration=s.samples/s.fs,raw=s.raw,time=s.time,lead=s.lead,port=s.port,source='arduino' if s.mode!='simulation' else 'python')
    if s.mode!='simulation':
        result['timing']='nominal' if legacy else 'device'
        result['observed_fs']=None if legacy else (len(t)-1)/(t[-1]-t[0])
    if s.filter_kind is not None:
        result.update(analyze(s.raw,s.fs,s.filter_kind,s.window,s.time))
    else:
        y=convolution(x,np.ones(10)/10)[:len(x)]
        result.update(filtered=[None]*9+y[9:].tolist(),filter_kind='moving',window=10,delay_samples=4.5)
    return result

def render_report(study, fmt="png"):
    # Use independent Figure, not pyplot or GUI. All drawing serialized.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    with plot_lock:
        figure=Figure(figsize=(12,6),dpi=130,layout='constrained')
        FigureCanvasAgg(figure)
        axes=figure.subplots(2,1,sharex=True)
        title={'bench':'ADC DE BANCO · NO ECG CLÍNICO','experimental':'ECG EXPERIMENTAL · NO DIAGNÓSTICO','simulation':'ECG SIMULADO · NO CLÍNICO'}[study['mode']]
        p=study['patient']; figure.suptitle('ECG Analyzer | '+title+'\n'+p['name']+' | '+str(p['age'])+' años | '+str(p['weight'])+' kg | '+str(p['height'])+' cm | IMC '+format(p['bmi'],'.2f')+'\nID '+study['id']+' | '+study['date']+' | '+str(study['fs'])+(' Hz nominales | LO no disponible | ' if study.get('timing')=='nominal' else ' Hz | ')+str(study['samples'])+' muestras', fontsize=10)
        unit='ADC (cuentas)' if study['mode']!='simulation' else 'Amplitud relativa'
        for ax,key,label,color in [(axes[0],'raw','Original','#356b9b'),(axes[1],'filtered','Procesada · '+str(study.get('filter_kind') or 'Media móvil'),'#148a73')]:
            ax.plot(study['time'], np.asarray(study[key],dtype=float),linewidth=.8,color=color)
            ax.set_title(label); ax.set_ylabel(unit); ax.grid(alpha=.3)
        axes[1].set_xlabel('Tiempo (s)')
        buffer=io.BytesIO(); figure.savefig(buffer,format=fmt); return buffer.getvalue()

def png(study):
    return render_report(study, 'png')

@router.get('/health')
@locked
def health():
    try:
        client().admin.command('ping')
        return {'status':'ok','database':db_name()}
    except Exception:
        raise storage_error()

@router.post('/save')
@locked
def save(s: Study):
    try: record=prepare(s); image=png(record)
    except ValueError as exc: raise HTTPException(422,str(exc))
    # Small bounded PNG + arrays stored atomically in one study document.
    try:
        from bson import BSON, Binary
        d=db(); previous=d.estudios.find_one({'_id':s.id},{'patient_id':1})
        patient_id=previous['patient_id'] if previous else (s.patient_id or s.id)
        if s.patient_id and s.patient_id!=patient_id: raise HTTPException(409,'El estudio ya pertenece a otro paciente')
        if s.patient_id and not d.pacientes.find_one({'_id':patient_id}): raise HTTPException(404,'Paciente no encontrado')
        record.update(patient_id=patient_id, saved_at=utc_now())
        doc={'_id':s.id,**record,'image_png':Binary(image)}
        if len(BSON.encode(doc))>15*1024*1024: raise HTTPException(413,'Estudio demasiado grande')
        d.pacientes.update_one({'_id':patient_id},{'$setOnInsert':{'created_at':utc_now()},'$set':{**record['patient'],'updated_at':utc_now()}},upsert=True)
        d.estudios.replace_one({'_id':s.id},doc,upsert=True)
        return {'id':s.id,'patient_id':patient_id,'saved_at':record['saved_at']}
    except HTTPException: raise
    except Exception: raise storage_error()

@router.get('/list')
@locked
def list_studies(q: str=Query(default='',max_length=160)):
    try:
        query={'patient.name':{'$regex':re.escape(q.strip()),'$options':'i'}} if q.strip() else {}
        fields={'_id':0,'id':1,'patient_id':1,'patient':1,'date':1,'mode':1,'fs':1,'samples':1,'filter_kind':1,'saved_at':1}
        rows=list(db().estudios.find(query,fields).sort('date',-1).limit(201))
        if any(not r.get('id') for r in rows):
            raise HTTPException(409,'Esquema de estudios diferente. Usa una base de prueba y revisa la migración antes de continuar.')
        return {'records':rows[:200],'more':len(rows)>200}
    except HTTPException: raise
    except Exception: raise storage_error()

@router.post('/get')
@locked
def get_study(s: StudyId):
    try: row=db().estudios.find_one({'_id':s.id},{'_id':0,'image_png':0})
    except Exception: raise storage_error()
    if row is None: raise HTTPException(404,'Estudio no encontrado')
    return row

@router.post('/image')
@locked
def get_image(s: StudyId):
    try: row=db().estudios.find_one({'_id':s.id},{'image_png':1})
    except Exception: raise storage_error()
    if row is None: raise HTTPException(404,'Imagen no encontrada')
    return {'png':base64.b64encode(row['image_png']).decode('ascii')}

@router.post('/delete')
@locked
def delete(s: StudyId):
    try: result=db().estudios.delete_one({'_id':s.id})
    except Exception: raise storage_error()
    if not result.deleted_count: raise HTTPException(404,'Estudio no encontrado')
    return {'ok':True}


@router.post('/export')
@locked
def export_study(s: StudyId, fmt: Literal['pdf','csv'] = 'pdf'):
    record = get_study(s)
    if fmt == 'pdf':
        content = render_report(record, 'pdf')
    else:
        import csv
        output = io.StringIO(newline='')
        w = csv.writer(output)
        w.writerow(['tiempo_s','original_adc' if record['mode']!='simulation' else 'original_relativa','procesada','LO'])
        for i,(t,x,y) in enumerate(zip(record['time'],record['raw'],record['filtered'])):
            w.writerow([t,x,y,record['lead'][i] if record.get('lead') else ''])
        content=output.getvalue().encode('utf-8-sig')
    return {'content':base64.b64encode(content).decode('ascii'),'format':fmt}
