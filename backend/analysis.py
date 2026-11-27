"""Offline experimental filtering and FFT; never a clinical interpretation."""
import numpy as np
from proyecto import convolution, RATES

FILTERS = ('moving',)

def spectrum(x, fs):
    x = np.asarray(x, dtype=float)
    w = np.hanning(len(x))
    a = np.abs(np.fft.rfft((x-x.mean())*w))*2/w.sum()
    a[0] /= 2
    if len(x)%2 == 0: a[-1] /= 2
    f = np.fft.rfftfreq(len(x), 1/fs)
    i = int(np.argmax(a[1:])+1)
    peak = float(f[i]) if a[i] > 1e-10 else None
    return f.tolist(), a.tolist(), peak

def analyze(raw, fs, kind='moving', window=10, timestamps=None):
    if fs not in RATES or not 2*fs <= len(raw) <= 60*fs or kind not in FILTERS or not 2<=window<=50:
        raise ValueError('Configuración de análisis no válida')
    x=np.asarray(raw,dtype=float)
    if not np.all(np.isfinite(x)) or np.max(np.abs(x))>1e6:
        raise ValueError('Muestras inválidas')
    actual=float(fs)
    if timestamps is not None:
        t=np.asarray(timestamps,dtype=float)
        if t.shape!=x.shape or not np.all(np.isfinite(t)) or np.any(np.diff(t)<=0):
            raise ValueError('Marcas temporales inválidas')
        actual=(len(t)-1)/(t[-1]-t[0])
        if abs(actual-fs)>fs*.02 or np.max(np.abs(np.diff(t)*actual-1))>.2:
            raise ValueError('Muestreo irregular: FFT y filtros requieren muestras aproximadamente equiespaciadas')
    y=convolution(x,np.ones(window)/window)[:len(x)]
    invalid=window-1; delay=(window-1)/2
    f,original,p1=spectrum(x[invalid:],actual)
    _,processed,p2=spectrum(y[invalid:],actual)
    return dict(filtered=[None]*invalid+y[invalid:].tolist(),filter_kind=kind,window=window,delay_samples=delay,analysis_fs=actual,frequency=f,original_spectrum=original,filtered_spectrum=processed,original_peak=p1,filtered_peak=p2,resolution=actual/(len(x)-invalid))
