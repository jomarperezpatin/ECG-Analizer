"""ECG experimental: procesamiento importable, sin I/O al importar."""
import math
import numpy as np

RATES = (100, 250, 500)


def convolution(x, h):
    """Convolución discreta completa del código original; límites optimizados."""
    lx, lh = len(x), len(h)
    if not lx or not lh:
        return np.zeros(0)
    y = np.zeros(lx + lh - 1)
    for n in range(len(y)):
        suma = 0.0
        for k in range(max(0, n - lh + 1), min(lx - 1, n) + 1):
            suma += x[k] * h[n - k]
        y[n] = suma
    return y


def simulate(samples, fs):
    if fs not in RATES or not 2 * fs <= samples <= 60 * fs:
        raise ValueError('Configuración de muestreo no válida')
    time = np.arange(samples, dtype=float) / fs
    p = time % 0.8
    def g(c, w):
        return np.exp(-0.5 * ((p - c) / w) ** 2)
    raw = (0.12*g(.16,.035)-.13*g(.295,.012)+1.1*g(.33,.014)
           -.25*g(.37,.014)+.27*g(.55,.06)+.045*np.sin(2*math.pi*.35*time)
           +.045*np.sin(2*math.pi*27*time)+.025*np.cos(2*math.pi*43*time)
           +(.12*np.sin(2*math.pi*60*time) if fs>120 else 0))
    y = convolution(raw, np.ones(10)/10)[:samples]
    return dict(time=time.tolist(), raw=raw.tolist(), filtered=[None]*9+y[9:].tolist(),
                fs=fs, samples=samples, duration=samples/fs, mode='simulation', source='python', filter_kind='moving', window=10, delay_samples=4.5)


def list_ports():
    """Solo enumera dispositivos. No abre puertos ni confirma el firmware."""
    from serial.tools import list_ports as serial_ports
    result = []
    for p in serial_ports.comports():
        description = p.description or ''
        manufacturer = p.manufacturer or ''
        candidate = p.vid in (0x2341, 0x2A03) or 'arduino' in (description+' '+manufacturer).lower()
        result.append(dict(device=p.device, description=description, manufacturer=manufacturer,
                           vid=p.vid, pid=p.pid, candidate=candidate))
    return result
