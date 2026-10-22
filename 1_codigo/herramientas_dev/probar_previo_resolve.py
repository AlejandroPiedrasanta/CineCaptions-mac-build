# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_previo_resolve.py — suspende Resolve ANTES de pulsar GO: la revisión previa (colocacion.preparar_resolve_para_go) debe reiniciarlo y terminar bien. SOLO desarrollo (no entra en el .exe; necesita Resolve abierto y es seguro con el del usuario solo si él lo autoriza: ver memoria «resolve-uso-paralelo»).
"""Resolve SUSPENDIDO antes de pulsar GO (como un Resolve colgado tras suspender el PC): el GO debe notarlo al empezar, reiniciar Resolve y terminar bien.
python probar_previo_resolve.py <video> <pack>"""
import ctypes, os, subprocess, sys, time
from pathlib import Path

AQUI = str(Path(__file__).resolve().parent.parent)                      # 1_codigo
PY = str(Path(AQUI).parent / '6_compilacion' / 'venv315' / 'Scripts' / 'python.exe')
video, pack = sys.argv[1], sys.argv[2]
registro = Path.home() / 'DaVinciSubtitles' / 'cinecaptions.log'
n0 = len(registro.read_text(encoding='utf-8', errors='replace').splitlines())
k32, ntdll = ctypes.windll.kernel32, ctypes.windll.ntdll
r = subprocess.run(['powershell', '-NoProfile', '-Command', "(Get-Process Resolve -ErrorAction SilentlyContinue).Id -join ','"], capture_output=True, text=True)
for pid in [int(x) for x in (r.stdout or '').strip().split(',') if x.strip().isdigit()]:
    h = k32.OpenProcess(0x1F0FFF, False, pid)
    ntdll.NtSuspendProcess(h)
    k32.CloseHandle(h)
    print('Resolve SUSPENDIDO antes del GO (pid %d)' % pid, flush=True)
time.sleep(8)                                    # (para que la ventana ya figure «No responde»)
env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONIOENCODING': 'utf-8'}
t0 = time.time()
p = subprocess.run([PY, '-u', os.path.join(AQUI, 'probar_go_variantes.py'), video, pack, '--sfx', '--emojis', '--efectos'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=420)
print('GO terminó en %.0f s, código %s' % (time.time() - t0, p.returncode), flush=True)
print((p.stdout or '')[-300:], flush=True)
lineas = registro.read_text(encoding='utf-8', errors='replace').splitlines()[n0:]
for l in lineas:
    if any(x in l for x in ('Resolve', 'Puente', 'GO:')) and l[:4] == '2026':
        print(l[:190])
