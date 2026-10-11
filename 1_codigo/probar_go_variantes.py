# CineCaptions · By Cinema Productions
# 1_codigo/probar_go_variantes.py — GO de la app sin pantalla sobre un video REAL con un pack y con los sonidos / emojis / efectos visuales encendidos o apagados a mano (para encontrar qué tumba a Resolve).
"""
    python probar_go_variantes.py <video> <pack> [--sfx] [--emojis] [--efectos]
    python probar_go_variantes.py <video> <pack> --secuencia nada,sfx,emojis,efectos,sfx+emojis+efectos     una vuelta por variante, cada una con un Resolve RECIÉN ARRANCADO

Sin banderas todo va apagado (solo los captions). Con cada bandera se enciende esa parte del GO real (go_sfx, go_emojis, go_efectos_visuales). Usa las preferencias del usuario para el resto, sin
guardar nada; la transcripción y la IA de texto son las reales (con caché). Con --secuencia cada vuelta es un proceso nuevo y, entre vueltas, se cierra el Resolve de pruebas (solo si su proyecto es
«CineCaptions N»: acción «cerrar» de CineCaptions_Vista.lua) para que la siguiente arranque en frío; si Resolve se cierra solo (se cae), eso ES el resultado de esa variante. Un Resolve colgado
hay que cerrarlo a mano.
"""
import subprocess
import sys
import time
from pathlib import Path

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding='utf-8', errors='replace')            # redirigido a un archivo, Windows usaría cp1252 y reventaría con «ó»
    except Exception:
        pass
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import hacer_vistas_mezcla as H


def una(video, pack, prefs):
    """Una vuelta de GO en ESTE proceso. Devuelve el código de salida: 0 GO bien · 2 GO falló."""
    ok = H._go(video, None, None, pack=pack, prefs_extra=prefs, tope_s=300)
    print('RESULTADO:', 'GO terminó bien' if ok else 'GO FALLÓ', flush=True)
    return 0 if ok else 2


def secuencia(video, pack, variantes):
    resumen = []
    for v in variantes:
        flags = [f'--{x}' for x in v.split('+') if x != 'nada']          # (sfx, emojis, efectos, sinsfxemoji)
        if H.resolve_abierto() and not H.cerrar_resolve():
            print('No pude dejar Resolve cerrado para una vuelta en frío: paro aquí.', flush=True)
            break
        print(f'=== variante «{v}»', flush=True)
        t0 = time.time()
        r = subprocess.run([sys.executable, '-u', str(Path(__file__)), str(video), pack, *flags], capture_output=True, text=True, encoding='utf-8', errors='replace')
        time.sleep(3)
        vivo = H.resolve_abierto()
        ultimo = next((l for l in reversed((r.stdout or '').splitlines()) if l.startswith('RESULTADO')), 'sin RESULTADO')
        res = ('ok' if r.returncode == 0 and vivo else 'fallo (GO terminó con error)' if vivo else 'RESOLVE SE CAYÓ')
        print(f'=== resultado «{v}»: {res} · {ultimo} ({time.time() - t0:.0f} s)', flush=True)
        resumen.append((v, res))
        if vivo and H.resolve_colgado():
            print('Resolve se quedó colgado: paro aquí (ciérralo a mano).', flush=True)
            break
    print('RESUMEN:', resumen, flush=True)
    return 0


def main():
    argv = sys.argv[1:]
    valores = {argv[i + 1] for i, a in enumerate(argv) if a == '--secuencia' and i + 1 < len(argv)}
    pos = [a for a in argv if not a.startswith('--') and a not in valores]
    video, pack = Path(pos[0]), pos[1]
    if '--secuencia' in argv:
        return secuencia(video, pack, argv[argv.index('--secuencia') + 1].split(','))
    prefs = {'go_sfx': '--sfx' in argv, 'go_emojis': '--emojis' in argv, 'go_efectos_visuales': '--efectos' in argv}
    if '--sinsfxemoji' in argv:
        prefs['sfx_emojis'] = False                                   # los emojis sin su sonido propio
    print('variante:', prefs, flush=True)
    return una(video, pack, prefs)


if __name__ == '__main__':
    sys.exit(main())
