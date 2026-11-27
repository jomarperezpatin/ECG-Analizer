import time
import sys
import subprocess

# -------------------------------------------------------------
# 0. Auto-instalación y verificación de dependencias
# -------------------------------------------------------------
def asegurar_paquete(modulo_nombre, paquete_pip):
    try:
        __import__(modulo_nombre)
    except ImportError:
        print(f"\n[Aviso] Falta '{paquete_pip}'. Instalándolo automáticamente en este entorno...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", paquete_pip])
            __import__(modulo_nombre)
            print(f"[Éxito] '{paquete_pip}' instalado correctamente.")
        except Exception as err:
            print(f"\n[Error] No se pudo instalar automáticamente '{paquete_pip}': {err}")
            print(f"Por favor ejecuta en tu terminal: {sys.executable} -m pip install {paquete_pip}")
            sys.exit(1)

# Asegurar numpy y matplotlib
asegurar_paquete("numpy", "numpy")
asegurar_paquete("matplotlib", "matplotlib")

# Para pyserial, suele haber un conflicto común si se instaló 'serial' en lugar de 'pyserial'
try:
    import serial
    import serial.tools.list_ports
    if not hasattr(serial, 'Serial'):
        raise ImportError("Módulo 'serial' incorrecto instalado.")
except (ImportError, AttributeError):
    print("\n[Aviso] Instalando 'pyserial'...")
    try:
        # Desinstalar posible paquete obsoleto 'serial' que causa conflictos
        subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", "serial"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial"])
        import serial
        import serial.tools.list_ports
        print("[Éxito] 'pyserial' se instaló y configuró correctamente.")
    except Exception as err:
        print(f"[Error] Ejecuta manualmente: {sys.executable} -m pip install pyserial")
        sys.exit(1)

import numpy as np
import matplotlib.pyplot as plt


# -------------------------------------------------------------
# 1. Función de Convolución
# -------------------------------------------------------------
def convolution(x, h):
    lx = len(x)
    lh = len(h)
    lsalida = lx + lh - 1
    y = np.zeros(lsalida)
    
    for n in range(lsalida):
        suma = 0.0
        for k in range(lx):
            if 0 <= n - k < lh:
                suma += x[k] * h[n - k]
        y[n] = suma
        
    return y


def es_numero(cadena):
    """Verifica si la cadena es un número entero o decimal válido."""
    try:
        float(cadena)
        return True
    except ValueError:
        return False


def listar_puertos():
    """Muestra los puertos COM disponibles."""
    puertos = list(serial.tools.list_ports.comports())
    if not puertos:
        print("  -> No se detectó ningún puerto COM conectado.")
    else:
        for p in puertos:
            print(f"  -> {p.device}: {p.description}")
    return [p.device for p in puertos]


# -------------------------------------------------------------
# 2. Configuración y Captura desde Arduino (COM8)
# -------------------------------------------------------------
puerto = 'COM8' 
baudios = 115200
muestras_totales = 600 # Aprox 5 segundos a 10ms por muestra

print("=" * 65)
print("       SISTEMA DE ADQUISICIÓN Y FILTRADO DE ECG (ARDUINO)")
print("=" * 65)

print("\nBuscando puertos disponibles en tu equipo:")
puertos_detectados = listar_puertos()

if puerto not in puertos_detectados:
    print(f"\n[Aviso] COM8 no aparece en la lista de puertos detectados.")
    print("Asegúrate de que el cable USB del Arduino esté bien conectado.")
    if len(puertos_detectados) == 1:
        print(f"Se detectó únicamente '{puertos_detectados[0]}'. ¿Deseas usar ese en vez de COM8?")
        try:
            resp = input(f"¿Cambiar a {puertos_detectados[0]}? (S/n): ").strip().lower()
            if resp in ["", "s", "si", "y"]:
                puerto = puertos_detectados[0]
        except (EOFError, KeyboardInterrupt):
            pass

print(f"\n>>> Conectando a {puerto} a {baudios} baudios...")

x_ecg = []
conexion_exitosa = False

try:
    with serial.Serial(puerto, baudios, timeout=2) as ser:
        # El Arduino se reinicia al conectar (DTR reset). Esperar a que arranque:
        print("Sincronizando con Arduino (esperando reinicio de puerto)...")
        time.sleep(2)
        ser.reset_input_buffer()
        print("¡Conectado! Capturando datos del ECG, por favor quédate quieto...")
        
        tiempo_inicio = time.time()
        timeout_maximo = 20 # Tiempo máximo de captura
        lecturas_vacias = 0

        while len(x_ecg) < muestras_totales:
            linea_bytes = ser.readline()
            
            if not linea_bytes:
                lecturas_vacias += 1
                if lecturas_vacias >= 6:
                    print("\n[Aviso] El puerto está abierto pero no llegan datos del Arduino.")
                    print("Verifica que tu código de Arduino esté usando 'Serial.println(...)' a 115200 baudios.")
                    break
                continue
            
            lecturas_vacias = 0
            linea = linea_bytes.decode('utf-8', errors='ignore').strip()
            
            # Admite datos simples ("512") o con límites de Plotter ("0,1023,512")
            partes = linea.split(',')
            valor_candidato = partes[-1].strip()
            if valor_candidato and es_numero(valor_candidato):
                x_ecg.append(float(valor_candidato))
                if len(x_ecg) % 50 == 0:
                    print(f"  Muestras capturadas: {len(x_ecg)} / {muestras_totales}  (Último valor: {valor_candidato})")

            if time.time() - tiempo_inicio > timeout_maximo:
                print("\n[Aviso] Tiempo límite de espera alcanzado.")
                break

        if len(x_ecg) > 0:
            conexion_exitosa = True
            print(f"\n¡Captura completada con éxito! ({len(x_ecg)} muestras recibidas)")

except serial.SerialException as e:
    err_str = str(e)
    print(f"\n[Error Serial en {puerto}]: {err_str}")
    if "PermissionError" in err_str or "Access is denied" in err_str:
        print("\n>>> IMPORTANTE: El puerto COM8 está ocupado por otro programa.")
        print(">>> CIERRA el 'Monitor Serie' del Arduino IDE o cualquier otra ventana que lo esté usando.")
except Exception as e:
    print(f"\n[Error inesperado]: {e}")


# -------------------------------------------------------------
# 3. Respaldo / Modo Simulación si no se pudo conectar
# -------------------------------------------------------------
if not conexion_exitosa or len(x_ecg) == 0:
    print("\n" + "-" * 65)
    print("No se pudieron obtener muestras reales del Arduino.")
    print("¿Deseas generar una señal de ECG simulada para ver la gráfica y el filtro?")
    print("-" * 65)
    try:
        opc = input("Generar prueba simulada? (S/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        opc = "s"

    if opc in ["", "s", "si", "y", "yes"]:
        t = np.linspace(0, 5, muestras_totales)
        f_cardiaca = 1.25
        ecg_base = np.zeros(muestras_totales)
        for i in range(int(5 * f_cardiaca)):
            centro = int((i + 0.5) * (muestras_totales / (5 * f_cardiaca)))
            if 0 <= centro < muestras_totales:
                ancho = 6
                r_range = np.arange(max(0, centro - ancho), min(muestras_totales, centro + ancho))
                ecg_base[r_range] += 3.0 * np.exp(-((r_range - centro) ** 2) / (2 * (2 ** 2)))
        ruido = 0.25 * np.random.normal(0, 1, muestras_totales) + 0.15 * np.sin(2 * np.pi * 60 * t)
        x_ecg = (ecg_base + ruido + 1.5).tolist()
    else:
        print("Saliendo...")
        sys.exit(0)


# -------------------------------------------------------------
# 4. Procesamiento de la Señal (Convolución)
# -------------------------------------------------------------
x = np.array(x_ecg)

# Kernel de media móvil (filtro paso bajo de 10 muestras)
h = np.ones(10) / 10.0 

print("\nAplicando convolución...")
y = convolution(x, h)


# -------------------------------------------------------------
# 5. Graficación de Resultados
# -------------------------------------------------------------
print("Generando gráficos...")
plt.figure(figsize=(11, 7))

# Gráfica Superior: Señal Cruda de Arduino
plt.subplot(2, 1, 1)
plt.plot(x, color='gray', linewidth=1.2, label='ECG Crudo')
plt.title(f'Señal de ECG Original (Capturada de Arduino en {puerto})')
plt.ylabel('Amplitud')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(loc='upper right')

# Gráfica Inferior: Señal Convolucionada
plt.subplot(2, 1, 2)
plt.plot(y, color='teal', linewidth=1.8, label='ECG Filtrado (Media Móvil)')
plt.title('Señal de ECG Procesada (Convolución con Media Móvil - Filtro Paso Bajo)')
plt.xlabel('n (Muestras)')
plt.ylabel('Amplitud')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(loc='upper right')

plt.tight_layout()

# Guardar imagen como respaldo
plt.savefig("ecg_procesado.png", dpi=300)
print("Gráfica guardada como 'ecg_procesado.png'.")

# Mostrar ventana interactiva
plt.show()
ar