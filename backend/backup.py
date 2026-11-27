"""Bounded, app-specific BSON backups; never restore over an existing database."""
import json
import os
import re
import struct
import uuid
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import database as storage

router=APIRouter(prefix='/api/backup')
COLLECTIONS=('pacientes','estudios')
FORMAT_V1='ecg-analyzer-bson-v1'
FORMAT='ecg-analyzer-bson-v2'
MAX_BYTES=512*1024*1024
MAX_DOC=16*1024*1024
restored=set()

class FileRequest(BaseModel):
    path: str = Field(min_length=1,max_length=32767)

class SelectRequest(BaseModel):
    database: str | None = None

def checked_path(value):
    p=Path(value)
    if not p.is_absolute() or p.suffix.lower()!='.ecgbackup':
        raise ValueError('Selecciona un archivo .ecgbackup válido.')
    return p

def require_managed():
    if not os.environ.get('ECG_API_TOKEN'):
        raise HTTPException(403,'Usa Electron para las operaciones de respaldo.')

def docs(stream):
    from bson import BSON
    while True:
        head=stream.read(4)
        if not head:return
        if len(head)!=4:raise ValueError('Respaldo truncado.')
        size=struct.unpack('<i',head)[0]
        if not 5<=size<=MAX_DOC:raise ValueError('Longitud BSON inválida.')
        tail=stream.read(size-4)
        if len(tail)!=size-4:raise ValueError('Respaldo truncado.')
        yield BSON(head+tail).decode()

def validate_document(name,doc):
    # Restore only records readable by the v0.6+ archive. Reject other schemas.
    import re
    def uid(v):return isinstance(v,str) and bool(re.fullmatch(storage.ID_PATTERN,v))
    if not uid(doc.get('_id')):raise ValueError('Esquema de identificadores incompatible.')
    if name=='pacientes':
        storage.Patient.model_validate(doc)
    else:
        if doc.get('id')!=doc['_id'] or not uid(doc.get('patient_id')):
            raise ValueError('Esquema de estudios incompatible.')
        s=storage.Study.model_validate(doc)
        if len(s.raw)!=s.samples or len(s.time)!=s.samples or len(doc.get('filtered',[]))!=s.samples:
            raise ValueError('Longitudes de estudio incompatibles.')
        if not isinstance(doc.get('image_png'),bytes) or not doc['image_png'].startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Imagen PNG no válida.')

def collection_names(d):
    # Keep the two application collections plus any complete GridFS buckets.
    existing=set(d.list_collection_names()) if hasattr(d,'list_collection_names') else set(COLLECTIONS)
    extras=existing-set(COLLECTIONS)
    names=list(COLLECTIONS)
    for name in sorted(extras):
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(files|chunks)',name):
            raise ValueError('Hay colecciones no reconocidas. Usa mongodump para una copia íntegra de la base.')
        base=name.rsplit('.',1)[0]
        if not {base+'.files',base+'.chunks'} <= extras:
            raise ValueError('Bucket GridFS incompleto. Usa mongodump para conservar la base sin cambios.')
        names.append(name)
    return names

def native_document(name,doc,patients):
    if name not in COLLECTIONS:return False
    try:
        validate_document(name,doc)
        if name=='pacientes':patients.add(doc['_id'])
        elif doc['patient_id'] not in patients:return False
        return True
    except (ValueError,TypeError,KeyError):return False

def write_backup(path,d):
    from bson import BSON
    counts={}; total=0; created=False; patients=set(); compatible=True
    names=collection_names(d)
    try:
        with path.open('xb') as f:
            created=True
            with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for name in names:
                    count=0
                    with z.open(name+'.bson','w') as out:
                        for doc in d[name].find({}):
                            if '_id' not in doc:raise ValueError('Documento sin identificador.')
                            if not native_document(name,doc,patients):compatible=False
                            encoded=BSON.encode(doc);total+=len(encoded)
                            if total>MAX_BYTES:raise ValueError('Respaldo supera 512 MiB sin comprimir.')
                            out.write(encoded);count+=1
                    counts[name]=count
                z.writestr('manifest.json',json.dumps({'format':FORMAT,'database':d.name,'counts':counts,'date':storage.utc_now(),'compatible':compatible}))
        return counts
    except Exception:
        if created:path.unlink(missing_ok=True)
        raise

def archive_compatible(path):
    with zipfile.ZipFile(path) as z:
        return bool(json.loads(z.read('manifest.json')).get('compatible',True))

def restore_backup(path,client):
    name='ecg_restore_'+uuid.uuid4().hex
    target=client[name]
    started=False
    try:
        with zipfile.ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)>100 or len(set(z.namelist()))!=len(infos) or sum(i.file_size for i in infos)>MAX_BYTES+65536 or z.getinfo('manifest.json').file_size>65536:
                raise ValueError('Formato de respaldo inválido o demasiado grande.')
            manifest=json.loads(z.read('manifest.json'))
            version=manifest.get('format')
            if version not in (FORMAT_V1,FORMAT):raise ValueError('Formato de respaldo incompatible.')
            counts_expected=manifest.get('counts')
            if not isinstance(counts_expected,dict) or not set(COLLECTIONS)<=set(counts_expected):raise ValueError('Colecciones inválidas.')
            extra=set(counts_expected)-set(COLLECTIONS)
            if version==FORMAT_V1 and extra:raise ValueError('Colecciones inválidas.')
            for c in extra:
                if not re.fullmatch(r'[A-Za-z0-9_-]+\.(files|chunks)',c) or not {c.rsplit('.',1)[0]+'.files',c.rsplit('.',1)[0]+'.chunks'}<=extra:
                    raise ValueError('Colecciones inválidas.')
            names=[*COLLECTIONS,*sorted(extra)]
            if set(z.namelist())!={'manifest.json',*(c+'.bson' for c in names)}:raise ValueError('Archivos inválidos.')
            patient_ids=set(); counts={}; compatible=True
            for c in names:
                count=0
                with z.open(c+'.bson') as f:
                    for doc in docs(f):
                        if '_id' not in doc:raise ValueError('Documento sin identificador.')
                        if not native_document(c,doc,patient_ids):compatible=False
                        count+=1
                counts[c]=count
            if counts!=counts_expected:raise ValueError('Conteos del respaldo no coinciden.')
            if version==FORMAT_V1 and not compatible:raise ValueError('Esquema de respaldo anterior incompatible.')
            if name in client.list_database_names():raise ValueError('Conflicto de nombre de restauración.')
            started=True
            for c in names:
                target.create_collection(c)
                with z.open(c+'.bson') as f:
                    for doc in docs(f):target[c].insert_one(doc)
        # Trust validation of contents, not the manifest compatibility claim.
        if compatible:restored.add(name)
        return name,counts
    except Exception:
        if started:
            try:client.drop_database(name)
            except Exception:pass
        raise

@router.post('/create')
@storage.locked
def create(req: FileRequest):
    require_managed()
    try:
        p=checked_path(req.path); counts=write_backup(p,storage.db())
        return {'file':p.name,'counts':counts,'database':storage.db_name(),'compatible':archive_compatible(p)}
    except FileExistsError:raise HTTPException(409,'Ya existe ese archivo. Elige otro nombre.')
    except ValueError as e:raise HTTPException(422,str(e))
    except Exception:raise HTTPException(503,'No se pudo crear el respaldo. Revisa MongoDB, permisos y espacio disponible.')

@router.post('/restore')
@storage.locked
def restore(req: FileRequest):
    require_managed()
    try:
        p=checked_path(req.path);name,counts=restore_backup(p,storage.client())
        return {'database':name,'counts':counts,'compatible':name in restored}
    except (ValueError,zipfile.BadZipFile,KeyError,TypeError) as e:raise HTTPException(422,'Respaldo inválido o incompatible. No se modificó la base original.')
    except Exception:raise HTTPException(503,'No se pudo restaurar. No se modificó la base original.')

@router.post('/select')
@storage.locked
def select(req: SelectRequest):
    require_managed()
    if req.database is not None and req.database not in restored:raise HTTPException(422,'Solo se puede abrir una restauración de esta sesión.')
    storage.selected_database=req.database
    return {'database':storage.db_name()}
