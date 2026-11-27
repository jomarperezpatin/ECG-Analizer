"""Physical ADC acquisition. Experimental mode requires externally validated equipment; LO is not a safety test."""
import threading
import time
import uuid
import numpy as np
from proyecto import convolution
from verificar_arduino import parse_data
import re

def parse_legacy(line):
    """Exact numeric ADC or original plotter bounds; never interpret DATA/LO as ADC."""
    fields=line.split(",")
    value=fields[0] if len(fields)==1 else fields[2] if len(fields)==3 and fields[:2]==["0","1023"] else None
    if value is None or not re.fullmatch(r"[0-9]{1,4}",value) or not 0<=int(value)<=1023:
        raise ValueError("Formato serial numérico incompatible (se esperaba ADC de 0 a 1023)")
    return int(value)


def open_serial(port):
    import serial
    return serial.Serial(port, 115200, timeout=.2, write_timeout=1)


def expect(ser, cmd, answer, cancel):
    ser.write((cmd+'\n').encode('ascii'))
    end = time.monotonic()+3
    while time.monotonic()<end and not cancel.is_set():
        if ser.readline().decode('ascii').strip()==answer:
            return
    raise RuntimeError('Sin respuesta esperada a '+cmd+' ('+answer+'). Verifica el firmware y la frecuencia seleccionada.')


class Bench:
    def __init__(self):
        self.lock=threading.Lock()
        self.job=None

    def start(self, port, samples, mode="bench", fs=250, protocol="ecg1"):
        if fs not in (100,250) or protocol not in ("ecg1","numeric") or (protocol=="numeric" and (mode!="bench" or fs!=100)):
            raise ValueError("El firmware numérico solo admite pruebas de banco a 100 Hz nominales")
        with self.lock:
            if self.job and self.job['state'] in ('connecting','running'):
                raise RuntimeError('Ya existe una adquisición activa')
            j=dict(id=uuid.uuid4().hex, port=port, samples=samples, mode=mode, fs=fs, protocol=protocol, state='connecting', rows=[], error='', cancel=threading.Event(), heartbeat=time.monotonic())
            self.job=j
        threading.Thread(target=self.run,args=(j,),daemon=True).start()
        return j['id']

    def run(self,j):
        end_state='error'; error=''; cancel=j['cancel']
        try:
            with open_serial(j['port']) as ser:
                if j.get('protocol','ecg1')=='numeric':
                    self.run_legacy(ser,j)
                    end_state='complete'
                    return
                try:
                    if cancel.wait(2.5): raise RuntimeError('Prueba cancelada')
                    ser.reset_input_buffer()
                    expect(ser,'HELLO',f"ECG,1,{j.get('fs',250)}",cancel)
                    expect(ser,'START','OK,START',cancel)
                    with self.lock: j['state']='running'
                    deadline=time.monotonic()+j['samples']/j.get('fs',250)+5
                    last_data=time.monotonic() 
                    while len(j['rows'])<j['samples']:
                        if cancel.is_set(): raise RuntimeError('Prueba cancelada')
                        if time.monotonic()-j['heartbeat']>5: raise RuntimeError('Interfaz desconectada')
                        if time.monotonic()>deadline: raise RuntimeError('Tiempo límite de captura')
                        if time.monotonic()-last_data>2: raise RuntimeError('Arduino dejó de enviar muestras')
                        line=ser.readline().decode('ascii').strip()
                        if not line: continue
                        row=parse_data(line)
                        last_data=time.monotonic()
                        if row[3]==-1: raise RuntimeError('Firmware con detección LO deshabilitada')
                        with self.lock:
                            if row[0]!=len(j['rows']) or (j['rows'] and row[1]<=j['rows'][-1][1]):
                                raise RuntimeError('Pérdida de muestra o marca temporal inválida')
                            j['rows'].append(row)
                        if j.get('mode')=='experimental' and row[3]!=0:
                            raise RuntimeError('Electrodos desconectados (LO alto). Captura experimental interrumpida.')
                    if cancel.is_set(): raise RuntimeError('Prueba cancelada')
                    end_state='complete'
                finally:
                    # Do not hide the original acquisition failure if STOP also fails.
                    import sys
                    original_error = sys.exc_info()[0] is not None
                    try:
                        expect(ser,'STOP','OK,STOP',threading.Event())
                    except Exception:
                        if not original_error: raise
        except Exception as exc:
            end_state='stopped' if cancel.is_set() else 'error'
            error=str(exc)
            if isinstance(exc,PermissionError) or any(x in error.lower() for x in ('permissionerror','acceso denegado','access is denied','access denied')):
                error=f"Puerto {j['port']} ocupado o sin permiso. Cierra Serial Monitor/Plotter y otros programas que usen el puerto; vuelve a intentar. ({error})"
        finally:
            with self.lock:
                if cancel.is_set(): end_state='stopped'
                j.update(state=end_state,error=error)

    def run_legacy(self,ser,j):
        # The original sketch streams immediately after USB reset. No HELLO/START.
        cancel=j['cancel']
        if cancel.wait(2): raise RuntimeError('Prueba cancelada')
        ser.reset_input_buffer()
        # The first line after buffer reset might be partial; discard it.
        ser.readline()
        with self.lock: j['state']='running'
        deadline=time.monotonic()+j['samples']/100*1.5+5
        last=time.monotonic()
        while len(j['rows'])<j['samples']:
            if cancel.is_set(): raise RuntimeError('Prueba cancelada')
            now=time.monotonic()
            if now-j['heartbeat']>5: raise RuntimeError('Interfaz desconectada')
            if now>deadline or now-last>2: raise RuntimeError('Arduino dejó de enviar muestras numéricas')
            line=ser.readline().decode('ascii').strip()
            if not line: continue
            value=parse_legacy(line)
            last=time.monotonic()
            with self.lock:
                n=len(j['rows'])
                j['rows'].append((n,n*10000,value,-1))
        if cancel.is_set(): raise RuntimeError('Prueba cancelada')

    def status(self, ident):
        with self.lock:
            j=self.job
            if not j or j['id']!=ident: raise KeyError('Prueba no encontrada')
            j['heartbeat']=time.monotonic()
            rows=list(j['rows']); state=j['state']; error=j['error']; samples=j['samples']; port=j['port']
        fs=j.get('fs',250); legacy=j.get('protocol','ecg1')=='numeric'
        raw=[r[2] for r in rows]
        filtered=convolution(raw,np.ones(10)/10)[:len(raw)].tolist()
        filtered=[None if i<9 else v for i,v in enumerate(filtered)]
        t=[(r[1]-rows[0][1])/1e6 for r in rows]
        return dict(id=ident,port=port, samples=samples,fs=fs,duration=samples/fs,mode=j.get('mode','bench'),source='arduino',state=state,error=error,raw=raw,filtered=filtered,time=t,lead=[r[3] for r in rows], observed_fs=(len(t)-1)/t[-1] if not legacy and len(t)>1 and t[-1]>0 else None, timing='nominal' if legacy else 'device', filter_kind='moving', window=10, delay_samples=4.5)

    def stop(self,ident):
        with self.lock:
            if not self.job or self.job['id']!=ident: raise KeyError('Prueba no encontrada')
            if self.job['state'] in ('connecting','running'): self.job['cancel'].set()

bench=Bench()
