"""Verificación del protocolo ECG/1. No es una adquisición clínica."""
import argparse
import statistics
import sys
import time


def parse_data(line):
    tag, seq, stamp, adc, lead = line.split(',')
    if tag != 'DATA':
        raise ValueError('Trama no reconocida')
    seq, stamp, adc, lead = map(int, (seq, stamp, adc, lead))
    if not (0 <= seq <= 0xffffffff and 0 <= stamp <= 0xffffffff and 0 <= adc <= 1023 and lead in (-1, 0, 1)):
        raise ValueError('Trama fuera de rango')
    return seq, stamp, adc, lead


def summarize(rows, fs=250):
    if len(rows) < 2:
        raise ValueError('Muestras insuficientes')
    gaps = sum(max(0, b[0]-a[0]-1) for a,b in zip(rows, rows[1:])) + rows[0][0]
    if any(b[0] <= a[0] or b[1] <= a[1] for a,b in zip(rows,rows[1:])):
        raise ValueError('Secuencia o tiempo no creciente')
    seconds = (rows[-1][1]-rows[0][1])/1e6
    actual_rate = (len(rows)-1)/seconds
    jitter_ms = [abs((b[1]-a[1])/1000-(1000/fs)*(b[0]-a[0])) for a,b in zip(rows,rows[1:])]
    return gaps, actual_rate, statistics.mean(jitter_ms), min(r[2] for r in rows), max(r[2] for r in rows)


def main():
    import serial
    from serial.tools import list_ports
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Ej. COM8. Sin este argumento enumera puertos.')
    parser.add_argument('--fs',type=int,choices=(100,250),default=100,help='Frecuencia del firmware ECG/1')
    args = parser.parse_args()
    if not args.port:
        for p in list_ports.comports():
            print(p.device, p.description)
        print('Ejecuta de nuevo con --port COMx')
        return 0
    print('Prueba de banco: no conectar electrodos a una persona.')
    with serial.Serial(args.port, 115200, timeout=.3, write_timeout=1) as ser:
        time.sleep(2.5)
        ser.reset_input_buffer()
        def expect(command, expected):
            ser.write((command+'\n').encode('ascii'))
            deadline = time.monotonic()+3
            while time.monotonic()<deadline:
                line=ser.readline().decode('ascii',errors='replace').strip()
                if line==expected: return
            raise RuntimeError('Sin respuesta esperada a '+command+': '+expected)
        expect('HELLO',f'ECG,1,{args.fs}')
        print(f'Firmware ECG/1 identificado; frecuencia nominal {args.fs} Hz.')
        rows=[]
        try:
            expect('START','OK,START')
            deadline=time.monotonic()+10
            while len(rows)<500 and time.monotonic()<deadline:
                line=ser.readline().decode('ascii',errors='strict').strip()
                if not line: continue
                rows.append(parse_data(line))
            if len(rows)!=500: raise RuntimeError(f'Captura incompleta: {len(rows)}/500')
        finally:
            expect('STOP','OK,STOP')
        gaps,rate,jitter,low,high=summarize(rows,args.fs)
        print(f'Muestras: {len(rows)} | Perdidas: {gaps} | Frecuencia observada: {rate:.2f} Hz')
        print(f'Desviacion media del periodo: {jitter:.3f} ms | ADC: {low} a {high}')
        print('Deteccion LO: '+('no habilitada' if any(r[3]==-1 for r in rows) else 'habilitada'))
        print(f'LO alto: {sum(r[3]==1 for r in rows)} | LO bajo: {sum(r[3]==0 for r in rows)} | LO desconocido: {sum(r[3]==-1 for r in rows)}')
        if gaps or not args.fs*.98 <= rate <= args.fs*1.02:
            print('ADVERTENCIA: revisar regularidad de muestreo.'); return 1
        print('Prueba de comunicacion satisfactoria (no valida seguridad ni calidad ECG).')
        return 0

if __name__=='__main__':
    try: sys.exit(main())
    except Exception as e:
        print('Error:',e,file=sys.stderr); sys.exit(1)
