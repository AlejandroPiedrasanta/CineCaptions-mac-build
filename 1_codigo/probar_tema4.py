# CineCaptions · By Cinema Productions
# 1_codigo/probar_tema4.py — pone el Tema 4 en Resolve sobre un video NEGRO con las palabras de una transcripción y lo renderiza por tramos, para compararlo con la referencia.
"""
probar_tema4.py  (v5.4.33)
--------------------------
    python probar_tema4.py <palabras.json> [--salida <carpeta>] [--tramo 8] [--pack Tema4] [--solo-render]
    python probar_tema4.py --video <video.mp4> --slider [--solo-render] [--tramo 8]     el VIDEO DE MUESTRA de la tarjeta del tema en el slider (2_recursos/vistas_slider/<pack>.mp4 + .jpg)

Hace lo mismo que hacer_vistas_mezcla.py pero con UN pack (por defecto «Tema4») y las palabras de un archivo (p. ej. las de TEMA 4.mp4 en ~/DaVinciSubtitles/mcp/palabras_TEMA 4.json):
  1. video negro de la duración de las palabras; 2. GO de la app sin pantalla (sin sonidos, emojis ni efectos visuales: solo los captions); 3. Resolve renderiza el timeline por TRAMOS
  de `--tramo` segundos (Resolve Free se atasca con renders largos y muchas comps); 4. deja los .mov en la carpeta de salida (por defecto ~/DaVinciSubtitles/vistas_mezcla/tema4).
Con --solo-render, Resolve ya tiene el timeline de la corrida anterior (solo se vuelve a renderizar).
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import hacer_vistas_mezcla as H


def main():
    argv = sys.argv[1:]
    valores = {argv[i + 1] for i, a in enumerate(argv) if a in ('--salida', '--tramo', '--pack', '--video') and i + 1 < len(argv)}
    pos = [a for a in argv if not a.startswith('--') and a not in valores]
    if '--video' in argv:
        return slider(Path(argv[argv.index('--video') + 1]), argv)
    ruta = Path(pos[0])
    pack = argv[argv.index('--pack') + 1] if '--pack' in argv else 'Tema4'
    tramo = float(argv[argv.index('--tramo') + 1]) if '--tramo' in argv else 8.0
    salida = Path(argv[argv.index('--salida') + 1]) if '--salida' in argv else Path.home() / 'DaVinciSubtitles' / 'vistas_mezcla' / 'tema4'
    palabras = json.loads(ruta.read_text(encoding='utf-8'))
    palabras = palabras.get('palabras') if isinstance(palabras, dict) else palabras
    dur = max(float(p.get('end', 0)) for p in palabras) + 1.5
    trabajo = Path.home() / 'DaVinciSubtitles' / 'vistas_mezcla'
    trabajo.mkdir(parents=True, exist_ok=True)
    salida.mkdir(parents=True, exist_ok=True)
    if '--solo-render' not in argv:
        video = H.escribir_video_negro(trabajo / 'negro_tema4.mp4', dur)
        if not H._go(video, palabras, None, pack=pack):
            print('GO no terminó bien: no se renderiza.', flush=True)
            return 2
        H.time.sleep(10)
    import instalador_scripts
    instalador_scripts.instalar_scripts_en_resolve(forzar=True)
    ok_p, r_p = H._orden_vista({'accion': 'render_parar', 'destino': str(trabajo / 'render')}, timeout=60)
    print('render anterior parado:', ok_p, r_p, flush=True)
    t0, k = 0.0, 0
    hechos = []
    while t0 < dur:
        t1 = min(dur, t0 + tramo)
        try:
            r = H._renderizar(trabajo / 'render', nombre=f'tema4_{k:02d}', desde_s=t0, hasta_s=t1)
        except Exception as exc:
            print(f'   tramo {k} ({t0:.0f}-{t1:.0f} s) falló: {exc}', flush=True)
            t0, k = t1, k + 1
            continue
        destino = salida / f'tema4_{k:02d}_{int(t0)}s.mov'
        destino.write_bytes(r.read_bytes())
        print(f'   tramo {k}: {destino.name} ({H._duracion(destino):.1f} s)', flush=True)
        hechos.append(str(destino))
        t0, k = t1, k + 1
    print(f'{len(hechos)} tramos en {salida}', flush=True)
    return 0


def _concatenar(archivos, destino_mp4, ancho=486, crf=27):
    """Une los .mov renderizados por tramos en un mp4 pequeño y SIN audio (+faststart), como los videos del slider."""
    import subprocess
    lista = destino_mp4.with_suffix('.txt')
    lista.write_text(''.join(f"file '{Path(a).as_posix()}'" + chr(10) for a in archivos), encoding='utf-8')
    cmd = [H.shutil.which('ffmpeg') or 'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(lista), '-an', '-vf', f'scale={ancho}:-2:flags=lanczos', '-c:v', 'libx264', '-preset', 'slow',
           '-crf', str(crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destino_mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        lista.unlink()
    except OSError:
        pass
    if r.returncode != 0 or not destino_mp4.is_file():
        raise RuntimeError('ffmpeg no pudo unir los tramos: ' + (r.stderr or '')[-300:])
    return destino_mp4


def slider(video, argv):
    """GO REAL de la app sobre `video` con el pack (prefs del usuario: sonidos, emojis y efectos como los verías), render por tramos y mp4 + póster para la tarjeta del slider."""
    pack = argv[argv.index('--pack') + 1] if '--pack' in argv else 'Tema4'
    tramo = float(argv[argv.index('--tramo') + 1]) if '--tramo' in argv else 8.0
    dur = H._duracion(video)
    trabajo = Path.home() / 'DaVinciSubtitles' / 'vistas_mezcla'
    trabajo.mkdir(parents=True, exist_ok=True)
    if '--solo-render' not in argv:
        completo = {'go_sfx': True, 'go_emojis': True, 'go_efectos_visuales': True}
        if not H._go(video, None, None, pack=pack, prefs_extra=completo):
            print('GO no terminó bien: no se renderiza.', flush=True)
            return 2
        H.time.sleep(10)
    import instalador_scripts
    instalador_scripts.instalar_scripts_en_resolve(forzar=True)
    H._orden_vista({'accion': 'render_parar', 'destino': str(trabajo / 'render')}, timeout=60)
    t0, k, trozos = 0.0, 0, []
    while t0 < dur - 0.05:
        t1 = min(dur, t0 + tramo)
        r = H._renderizar(trabajo / 'render', nombre=f'slider_{k:02d}', ancho=540, alto=960, desde_s=t0, hasta_s=t1)
        copia = trabajo / f'slider_{pack}_{k:02d}.mov'
        copia.write_bytes(r.read_bytes())
        trozos.append(copia)
        print(f'   tramo {k}: {t0:.0f}-{t1:.0f} s ({H._duracion(copia):.1f} s)', flush=True)
        t0, k = t1, k + 1
    destino = AQUI.parent / '2_recursos' / 'vistas_slider'
    destino.mkdir(parents=True, exist_ok=True)
    mp4 = _concatenar(trozos, destino / f'{pack}.mp4')
    print(f'{mp4.name}: {H._duracion(mp4):.1f} s, {mp4.stat().st_size / 1024:.0f} KB', flush=True)
    import subprocess
    t_poster = float(argv[argv.index('--poster') + 1]) if '--poster' in argv else 3.4                   # el fotograma de la tarjeta cuando no está al centro
    jpg = destino / f'{pack}.jpg'
    subprocess.run([H.shutil.which('ffmpeg') or 'ffmpeg', '-y', '-ss', str(t_poster), '-i', str(mp4), '-frames:v', '1', '-q:v', '3', str(jpg)], capture_output=True)
    print(f'{jpg.name}: {jpg.stat().st_size / 1024:.0f} KB' if jpg.is_file() else 'no pude sacar el póster', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
