# CineCaptions · By Cinema Productions
# 1_codigo/hacer_vista_slider.py — genera el VIDEO que se reproduce en la tarjeta de un pack del slider «Pack de estilos» (captions reales de Resolve).
"""
hacer_vista_slider.py  (v5.4.5)
-------------------------------
Las tarjetas del slider de Proyecto enseñan un video con los captions del pack TAL CUAL quedan en la línea de tiempo (no una imagen fija). Este script lo
fabrica de punta a punta con el flujo REAL de la app:

    python hacer_vista_slider.py <video.mp4> <pack> <salida.mp4> [--ancho 486] [--crf 27]

  1. suelta el video en la app sin pantalla (probar_go.py --soltar, con el pack forzado en memoria): proyecto nuevo «CineCaptions», timeline con el video,
     transcribe, planifica y coloca los captions con el pack;
  2. Resolve renderiza ese timeline (H.264 Master, resolución del timeline);
  3. ffmpeg lo reduce a un mp4 pequeño y SIN audio (el slider es mudo) con +faststart;
  4. limpia lo creado y vuelve al proyecto y timeline que había (igual que el MCP `arrastrar_video`).

Los resultados viven en 2_recursos/vistas_slider/<pack>.mp4 (vistas_slider.py los busca por el nombre del pack). Cambiar un pack o su planificador obliga a
repetirlo para que el video siga siendo fiel.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))


def _ffmpeg():
    return shutil.which('ffmpeg') or 'ffmpeg'


def _fin_sin_negro(render):
    """v5.5.8: el segundo donde empieza el negro del FINAL del render (el timeline sigue unos segundos tras el video por los sonidos del cierre:
    los ejemplos acababan con 2,5–4 s en negro y el slider los repite en bucle). None si no acaba en negro."""
    try:
        r = subprocess.run([_ffmpeg(), '-hide_banner', '-i', str(render), '-an', '-vf', 'blackdetect=d=0.3:pix_th=0.08', '-f', 'null', '-'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
        import re
        tramos = re.findall(r'black_start:([0-9.]+) black_end:([0-9.]+)', r.stderr)
        dur = re.search(r'Duration: (\d+):(\d+):([0-9.]+)', r.stderr)
        if not tramos or not dur:
            return None
        total = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))
        ini, fin = (float(x) for x in tramos[-1])
        return ini if ini > 1.0 and fin >= total - 0.15 else None
    except Exception:
        return None


def generar(media, pack, salida, ancho=486, crf=27, timeout=900, conservar=False, verificar=None):
    import banco_pruebas as b
    import mcp_cinecaptions as m
    import resolve_mcp
    media = str(media)
    salida = Path(salida)
    previo = {}
    if resolve_mcp.resolve_abierto():
        ok, previo, _err = resolve_mcp.script(m._ESTADO_PREVIO % {'nombre': 'CineCaptions'}, timeout=40)
        previo = previo if ok and isinstance(previo, dict) else {}
    print(f'Resolve antes: {previo or "cerrado"}', flush=True)
    stem = Path(media).stem[:40]
    entorno = {**os.environ, 'DUMP_S': str(timeout)}
    render = None
    try:
        r = subprocess.run([sys.executable, str(AQUI / 'probar_go.py'), media, pack, '--soltar'], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout + 60, env=entorno)
        salida_go = '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'site-packages' not in l)
        print(salida_go[-1800:], flush=True)
        if r.returncode != 0:
            raise RuntimeError(f'GO no terminó (código {r.returncode})')
        ok_v, estado_tl, _e = resolve_mcp.script(m._VERIFICAR_TL, timeout=30)
        print('timeline:', json.dumps(estado_tl, ensure_ascii=False)[:600], flush=True)
        if verificar is not None:                     # v5.5.8: p. ej. que los captions se puedan editar en el Inspector
            try:
                print('verificación:', json.dumps(verificar(), ensure_ascii=False)[:900], flush=True)
            except Exception as e:
                print('verificación falló:', e, flush=True)
        render = b.renderizar('slider_' + pack.replace(' ', '_'), tope_s=timeout)
        if not render:
            raise RuntimeError('el render no terminó')
        print('render:', render, flush=True)
        alto = int(round(ancho * 16 / 9 / 2.0)) * 2
        salida.parent.mkdir(parents=True, exist_ok=True)
        fin = _fin_sin_negro(render)
        cmd = [_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-i', render] + (['-t', '%.3f' % fin] if fin else []) + ['-an', '-vf', f'scale={ancho}:{alto}:flags=lanczos,fps=30',
               '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-maxrate', '1800k', '-bufsize', '3600k', '-pix_fmt', 'yuv420p', '-g', '60',
               '-movflags', '+faststart', str(salida)]
        subprocess.run(cmd, check=True)
        print(f'LISTO {salida} ({salida.stat().st_size / 1e6:.1f} MB)', flush=True)
    finally:
        if conservar:                                 # v5.5.8: el proyecto se queda (para revisar el timeline a mano)
            print('proyecto conservado para revisarlo', flush=True)
        else:
            ok, limpieza, err = resolve_mcp.script(m._LIMPIAR_ARRASTRE % {'stem': stem, 'previo_p': previo.get('proyecto'), 'previo_tl': previo.get('timeline'),
                                                                          'borrar': bool(previo.get('proyecto'))}, timeout=60)
            print('limpieza:', json.dumps(limpieza, ensure_ascii=False) if ok else f'no pude limpiar: {err}', flush=True)
    return render


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opc = dict(zip(sys.argv[1:], sys.argv[2:]))
    generar(args[0], args[1], args[2], ancho=int(opc.get('--ancho', 486)), crf=int(opc.get('--crf', 27)))
