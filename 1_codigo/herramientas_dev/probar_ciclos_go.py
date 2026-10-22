# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_ciclos_go.py — repite el GO N veces seguidas con un pack y cuenta fallos/tiempos (cuelgues intermitentes de Resolve). SOLO desarrollo (no entra en el .exe; necesita Resolve abierto y es seguro con el del usuario solo si él lo autoriza: ver memoria «resolve-uso-paralelo»).
"""K GOs seguidos (cada uno en su proceso, SIN cerrar Resolve entre medias) y, tras cada uno, memoria / respuesta de Resolve.
python probar_ciclos_go.py <video> <pack> <K> [--reproducir] [--espera 20]"""
import os, subprocess, sys, time
from pathlib import Path

AQUI = str(Path(__file__).resolve().parent.parent)                      # 1_codigo
PY = str(Path(AQUI).parent / '6_compilacion' / 'venv315' / 'Scripts' / 'python.exe')
def estado():
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
                        "$p=Get-Process Resolve -ErrorAction SilentlyContinue|Select-Object -First 1; if($p){ '{0}|{1}|{2:N2}|{3}' -f $p.Id,$p.Responding,($p.WorkingSet64/1GB),$p.MainWindowTitle } else { 'SIN_RESOLVE' }"],
                       capture_output=True, text=True)
    return (r.stdout or '').strip()


def main():
    video, pack, k = sys.argv[1], sys.argv[2], int(sys.argv[3])
    reproducir = '--reproducir' in sys.argv
    espera = float(sys.argv[sys.argv.index('--espera') + 1]) if '--espera' in sys.argv else 20.0
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONIOENCODING': 'utf-8'}
    if reproducir:
        env['CC_REPRODUCIR'] = '1'
    print(f'### ciclos={k} reproducir={reproducir} pack={pack}', flush=True)
    print('inicio:', estado(), flush=True)
    for i in range(1, k + 1):
        t0 = time.time()
        r = subprocess.run([PY, '-u', os.path.join(AQUI, 'probar_go_variantes.py'), video, pack, '--sfx', '--emojis', '--efectos'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        ultimo = next((l for l in reversed((r.stdout or '').splitlines()) if l.startswith('RESULTADO')), 'sin RESULTADO')
        print(f'[{i}] {ultimo} ({time.time() - t0:.0f} s) · {estado()}', flush=True)
        time.sleep(espera)
        est = estado()
        print(f'[{i}] +{espera:.0f} s: {est}', flush=True)
        if 'SIN_RESOLVE' in est or '|False|' in est or r.returncode != 0:
            print('PARO: Resolve caído/colgado o GO fallido', flush=True)
            break
    print('fin:', estado(), flush=True)


if __name__ == '__main__':
    main()
