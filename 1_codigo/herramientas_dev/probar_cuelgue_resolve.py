# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_cuelgue_resolve.py — suspende Resolve a mitad de un GO real (armar / captions / efectos) y comprueba que el programa lo nota, lo reinicia y termina. SOLO desarrollo (no entra en el .exe; necesita Resolve abierto y es seguro con el del usuario solo si él lo autoriza: ver memoria «resolve-uso-paralelo»).
"""GO real + cuelgue SIMULADO de Resolve (se le suspende el proceso) en el paso indicado, para comprobar que el GO lo detecta, lo cierra, lo reabre, rearma y termina.
python probar_cuelgue_resolve.py <video> <pack> <momento: armar|colocar|efectos>"""
import ctypes, os, subprocess, sys, threading, time
from pathlib import Path

AQUI = str(Path(__file__).resolve().parent.parent)                      # 1_codigo
PY = str(Path(AQUI).parent / '6_compilacion' / 'venv315' / 'Scripts' / 'python.exe')
video, pack, momento = sys.argv[1], sys.argv[2], sys.argv[3]
registro = Path.home() / 'DaVinciSubtitles' / 'cinecaptions.log'
claves = {'armar': 'Armando en Resolve un timeline', 'colocar': 'armado con tu video', 'efectos': 'Colocado en Resolve'}
n0 = len(registro.read_text(encoding='utf-8', errors='replace').splitlines())
env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONIOENCODING': 'utf-8', 'CC_UMBRAL_COLGADO_S': '20', 'CC_REPRODUCIR': '1'}
t0 = time.time()
proc = subprocess.Popen([PY, '-u', os.path.join(AQUI, 'probar_go_variantes.py'), video, pack, '--sfx', '--emojis', '--efectos'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding='utf-8', errors='replace', env=env)
salida = []
threading.Thread(target=lambda: [salida.append(l) for l in proc.stdout], daemon=True).start()


def pids():
    r = subprocess.run(['powershell', '-NoProfile', '-Command', "(Get-Process Resolve -ErrorAction SilentlyContinue).Id -join ','"], capture_output=True, text=True)
    return [int(x) for x in (r.stdout or '').strip().split(',') if x.strip().isdigit()]


k32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
suspendido = False
while proc.poll() is None and time.time() - t0 < 600:
    time.sleep(1.0)
    if not suspendido:
        try:
            lineas = registro.read_text(encoding='utf-8', errors='replace').splitlines()[n0:]
        except OSError:
            lineas = []
        if any(claves[momento] in l for l in lineas):
            time.sleep(2.5 if momento != 'efectos' else 0.5)
            for pid in pids():
                h = k32.OpenProcess(0x1F0FFF, False, pid)
                ntdll.NtSuspendProcess(h)
                k32.CloseHandle(h)
                print('Resolve SUSPENDIDO (pid %d) en t=%.0f s, momento «%s»' % (pid, time.time() - t0, momento), flush=True)
            suspendido = True
print('GO terminó en %.0f s, código %s' % (time.time() - t0, proc.poll()), flush=True)
print(''.join(salida[-4:])[-600:], flush=True)
try:
    lineas = registro.read_text(encoding='utf-8', errors='replace').splitlines()[n0:]
    for l in lineas:
        if any(x in l for x in ('Resolve dejó de responder', 'Cerrando Resolve', 'Reabriendo', 'reabierto', 'colgado', 'Colocado en Resolve', 'armado con tu video', 'GO · reproducir', 'GO:')):
            print(l[:200])
except Exception:
    pass
