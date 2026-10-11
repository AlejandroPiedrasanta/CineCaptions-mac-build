# CineCaptions · By Cinema Productions
# 1_codigo/recortar_bucle_vistas.py — recorta los clips de muestra de «Crea tu estilo» (texto sobre NEGRO) para que den la vuelta sin tiempo muerto.
"""
    python recortar_bucle_vistas.py <carpeta_o_mp4> [--antes 0.15] [--despues 0.55] [--solo-ver]

Cada clip lleva el texto sobre negro con un tramo vacío antes de entrar y, sobre todo, después de salir: al repetirse en bucle la tarjeta se quedaba vacía varios segundos
antes de volver a empezar. Esto mide en qué cuadros hay texto (luminancia) y deja el clip desde `--antes` s antes de la entrada hasta `--despues` s después de la salida
(para que la salida acabe entera). Con --solo-ver solo cuenta lo que haría. Reescribe el mp4 en su sitio (h264, sin audio, +faststart).
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

UMBRAL_LUM = 40                    # el texto es claro sobre negro puro: un cuadro "tiene texto" si su píxel más claro pasa de esto
MIN_S = 2.0


def _ffmpeg():
    import shutil
    return shutil.which('ffmpeg') or 'ffmpeg'


def _ffprobe():
    import shutil
    return shutil.which('ffprobe') or 'ffprobe'


def medir(ruta):
    """(fps, n_cuadros, primero, ultimo) de los cuadros con texto; primero/ultimo None si no hay."""
    sal = subprocess.run([_ffprobe(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'csv=p=0', str(ruta)], capture_output=True, text=True).stdout.strip().splitlines()[0].split(',')
    ancho, alto, fr = int(sal[0]), int(sal[1]), sal[2]
    num, den = fr.split('/')
    fps = float(num) / float(den or 1)
    w = 96
    h = max(2, int(round(alto * w / ancho / 2)) * 2)
    raw = subprocess.run([_ffmpeg(), '-v', 'error', '-i', str(ruta), '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    n = len(raw) // (w * h)
    a = np.frombuffer(raw, np.uint8)[:n * w * h].reshape(n, h, w)
    activos = np.where(a.max(axis=(1, 2)) > UMBRAL_LUM)[0]
    if not len(activos):
        return fps, n, None, None
    return fps, n, int(activos[0]), int(activos[-1])


def recortar(ruta, antes=0.15, despues=0.55, solo_ver=False):
    fps, n, i0, i1 = medir(ruta)
    dur = n / fps
    if i0 is None:
        return f'{ruta.name}: sin texto (no se toca)'
    t0 = max(0.0, i0 / fps - antes)
    t1 = min(dur, (i1 + 1) / fps + despues)
    if t1 - t0 < MIN_S:                                   # no dejar clips cortísimos
        extra = (MIN_S - (t1 - t0)) / 2.0
        t0, t1 = max(0.0, t0 - extra), min(dur, t1 + extra)
    texto = f'{ruta.name}: {dur:.2f} s -> {t1 - t0:.2f} s (texto {i0 / fps:.2f}-{(i1 + 1) / fps:.2f} s)'
    if solo_ver or dur - (t1 - t0) < 0.2:
        return texto + ('' if solo_ver else ' [ya estaba ajustado]')
    tmp = ruta.with_name(ruta.stem + '__bucle.mp4')
    r = subprocess.run([_ffmpeg(), '-y', '-ss', f'{t0:.3f}', '-i', str(ruta), '-t', f'{t1 - t0:.3f}', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '27', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', str(tmp)], capture_output=True, text=True)
    if r.returncode != 0 or not tmp.is_file():
        raise RuntimeError(f'ffmpeg falló con {ruta.name}: ' + (r.stderr or '')[-200:])
    tmp.replace(ruta)
    return texto


def main():
    argv = sys.argv[1:]
    valores = {argv[i + 1] for i, a in enumerate(argv) if a in ('--antes', '--despues') and i + 1 < len(argv)}
    pos = [a for a in argv if not a.startswith('--') and a not in valores]
    antes = float(argv[argv.index('--antes') + 1]) if '--antes' in argv else 0.15
    despues = float(argv[argv.index('--despues') + 1]) if '--despues' in argv else 0.55
    destino = Path(pos[0])
    archivos = [destino] if destino.is_file() else sorted(destino.glob('*.mp4'))
    for f in archivos:
        print(recortar(f, antes, despues, '--solo-ver' in argv), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
