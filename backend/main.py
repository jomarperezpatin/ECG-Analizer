from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictInt
from proyecto import simulate, list_ports

app = FastAPI(title='ECG Analyzer local', version='1.0.0')

# Managed Electron sessions authenticate each loopback request with an ephemeral token.
import os
import secrets
from starlette.responses import JSONResponse

@app.middleware('http')
async def local_access(request, call_next):
    token = os.environ.get('ECG_API_TOKEN')
    if token and not secrets.compare_digest(request.headers.get('X-ECG-Token',''), token):
        return JSONResponse({'detail':'Acceso local no autorizado'}, status_code=401)
    if request.headers.get('origin'):
        return JSONResponse({'detail':'Abre la aplicación en Electron'}, status_code=403)
    return await call_next(request)

class SimulationRequest(BaseModel):
    samples: StrictInt
    fs: StrictInt

@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '1.0.0', 'real_acquisition': True, 'clinical_acquisition': False, 'bench_acquisition': True}

@app.get('/api/ports')
def ports():
    try:
        return {'ports': list_ports(), 'verified': False}
    except ImportError:
        raise HTTPException(503, 'PySerial no instalado correctamente')
    except Exception:
        raise HTTPException(503, 'No fue posible enumerar los puertos')

@app.post('/api/ecg/simulate')
def simulation(request: SimulationRequest):
    try:
        return simulate(request.samples, request.fs)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

from bench import bench
from pydantic import StrictStr, StrictBool
from typing import Literal

class BenchRequest(BaseModel):
    fs: StrictInt = 250
    port: StrictStr
    samples: StrictInt
    confirmed_bench: StrictBool = False
    mode: Literal['bench','experimental'] = 'bench'
    confirmed_experimental: StrictBool = False
    protocol: Literal['ecg1','numeric'] = 'ecg1'

class BenchId(BaseModel):
    id: StrictStr

@app.post('/api/bench/start')
def start_bench(request: BenchRequest):
    if request.fs not in (100,250) or not 2*request.fs <= request.samples <= 60*request.fs or (request.protocol=='numeric' and (request.mode!='bench' or request.fs!=100)):
        raise HTTPException(422, 'Adquisición física: 100/250 Hz con ECG/1 o 100 Hz nominales con firmware original (solo banco).')
    if request.mode=='bench' and not request.confirmed_bench:
        raise HTTPException(422, 'Confirma prueba de banco sin personas')
    if request.mode=='experimental' and not request.confirmed_experimental:
        raise HTTPException(422, 'Se requiere confirmación de validación externa de seguridad eléctrica y autorización del participante')
    try:
        if request.port not in [p['device'] for p in list_ports()]:
            raise HTTPException(422,'Arduino no detectado en el puerto elegido')
        return {'id':bench.start(request.port,request.samples,request.mode,request.fs,request.protocol)}
    except RuntimeError as exc: raise HTTPException(409,str(exc))
    except ImportError: raise HTTPException(503,'PySerial no disponible')

@app.post('/api/bench/status')
def status_bench(request: BenchId):
    try: return bench.status(request.id)
    except KeyError: raise HTTPException(404,'Prueba no encontrada')

@app.post('/api/bench/stop')
def stop_bench(request: BenchId):
    try: bench.stop(request.id); return {'ok':True}
    except KeyError: raise HTTPException(404,'Prueba no encontrada')

from analysis import analyze

class AnalysisRequest(BaseModel):
    raw: list[float]
    fs: StrictInt
    kind: StrictStr = 'moving'
    window: StrictInt = 10
    timestamps: list[float] | None = None

@app.post('/api/ecg/analyze')
def analysis(request: AnalysisRequest):
    try:
        return analyze(request.raw, request.fs, request.kind, request.window, request.timestamps)
    except ValueError as exc:
        raise HTTPException(422,str(exc))

from database import router as storage_router
app.include_router(storage_router)

from backup import router as backup_router
app.include_router(backup_router)
