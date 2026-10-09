# CineCaptions · By Cinema Productions
# 1_codigo/hacer_vistas_guia_video.py — genera los CLIPS de 4 s (entrada, texto sostenido y SALIDA) de los 48 ejemplos de «Crea tu estilo», renderizados por Resolve.
"""
hacer_vistas_guia_video.py  (v5.4.5)
------------------------------------
Las tarjetas de «Crea tu estilo» enseñan la animación COMPLETA de cada ejemplo (antes eran 7 fotogramas de la entrada, y la salida nunca se veía). Aquí se
arma en Resolve —con el mismo construir_guia.py de siempre, modo 'vistas'— un timeline temporal con los 48 ejemplos de 4 s cada uno (macros reales Luxe Shine /
Luxe Slide y presets de Amro.Films Captions), Resolve lo RENDERIZA (cola de render: nada de ExportCurrentFrameAsStill, que ya tumbó Resolve) y ffmpeg lo corta en
un mp4 corto por ejemplo sobre FONDO NEGRO (en la galería se mezcla en «Screen» sobre una foto de muestra):

    python hacer_vistas_guia_video.py [salida=2_recursos/guia_estilo/vistas] [--ids 1,2,3] [--ancho 216] [--crf 30]

Salida: ej_NN.mp4 (sin audio, 4 s, 30 fps). Limpia el timeline temporal y los bins que creó. Se repite si cambian los ejemplos (ejemplos_estilo.py) o los macros.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

MARCA = 'RCS · temporal (se limpia solo)'
BINS = ('RCS · Crea tu estilo (bloques)', 'RCS · Crea tu estilo (Amro)')

_PONER = r"""
nombre = %(nombre)r
tl = None
for i in range(1, int(project.GetTimelineCount() or 0) + 1):
    t = project.GetTimelineByIndex(i)
    if t and t.GetName() == nombre:
        tl = t
        break
res = {'proyecto': project.GetName(), 'encontrado': bool(tl)}
if tl:
    res['actual'] = bool(project.SetCurrentTimeline(tl))
    res['fps'] = tl.GetSetting('timelineFrameRate')
    res['ancho'] = tl.GetSetting('timelineResolutionWidth')
    res['alto'] = tl.GetSetting('timelineResolutionHeight')
    res['fin'] = tl.GetEndFrame() - tl.GetStartFrame()
result = res
"""

_LIMPIAR = r"""
nombre, bins, previo = %(nombre)r, %(bins)r, %(previo)r
mp = project.GetMediaPool()
res = {'proyecto': project.GetName()}
tls = [project.GetTimelineByIndex(i) for i in range(1, int(project.GetTimelineCount() or 0) + 1)]
mio = [t for t in tls if t and t.GetName() == nombre]
anterior = next((t for t in tls if t and t.GetName() == previo), None) if previo else None
if anterior:
    project.SetCurrentTimeline(anterior)
res['timeline_borrado'] = bool(mp.DeleteTimelines(mio)) if mio else None
for j in (project.GetRenderJobList() or []):
    project.DeleteRenderJob(j['JobId'])
raiz = mp.GetRootFolder()
cajas = [c for c in (raiz.GetSubFolderList() or []) if c.GetName() in bins]
mp.SetCurrentFolder(raiz)
res['bins_borrados'] = bool(mp.DeleteFolders(cajas)) if cajas else None
tl = project.GetCurrentTimeline()
res['timeline_ahora'] = tl.GetName() if tl else None
result = res
"""


def generar(salida, ids=None, ancho=216, crf=30, tope_render_s=1200):
    import banco_pruebas as b
    import ejemplos_estilo as E
    import resolve_mcp
    salida = Path(salida)
    guia = E.carpeta_recursos()
    ok, estado, _e = resolve_mcp.script("tl = project.GetCurrentTimeline()\nresult = {'proyecto': project.GetName(), 'timeline': tl.GetName() if tl else None}", timeout=40)
    previo = (estado or {}).get('timeline') if ok else None
    print('Resolve antes:', estado if ok else 'sin respuesta', flush=True)
    datos = E.datos_guia(guia / 'Crea tu estilo.drb', amro=guia / 'Amro principales.drb', fotos=None, solo=None if ids is None else set(ids))
    datos['modo'] = 'vistas'
    segundos = float(datos['segundos'])
    nombre = f"{MARCA} · vista guia video {time.strftime('%H%M%S')}"
    render = None
    try:
        ok, mensaje = resolve_mcp.abrir_guia(guia / 'construir_guia.py', nombre, datos)
        print('guía armada:', ok, str(mensaje)[-300:], flush=True)
        if not ok:
            raise RuntimeError(f'Resolve no armó la guía: {mensaje}')
        ok, info, err = resolve_mcp.script(_PONER % {'nombre': nombre}, timeout=60)
        print('timeline temporal:', info, flush=True)
        if not ok or not (info or {}).get('actual'):
            raise RuntimeError(f'no pude poner el timeline de la guía como actual: {err or info}')
        fps = float(info.get('fps') or 30)
        for exacto in (30000 / 1001, 24000 / 1001, 60000 / 1001):
            if abs(fps - exacto) < 0.01:
                fps = exacto
        segundos = round(fps * segundos) / fps                      # lo que dura de verdad cada ejemplo en el timeline (p. ej. 120 fotogramas a 29,97 = 4,004 s)
        render = b.renderizar('guia_ejemplos', tope_s=tope_render_s)
        if not render:
            raise RuntimeError('el render no terminó')
        print('render:', render, flush=True)
        salida.mkdir(parents=True, exist_ok=True)
        alto = int(round(ancho * 16 / 9 / 2.0)) * 2
        hechos = 0
        for k, ej in enumerate(datos['ejemplos']):
            destino = salida / f"ej_{int(ej['id']):02d}.mp4"
            cmd = [shutil.which('ffmpeg') or 'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{k * segundos:.3f}', '-t', f'{segundos:.3f}', '-i', render,
                   '-an', '-vf', f'scale={ancho}:{alto}:flags=lanczos,fps=30', '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-pix_fmt', 'yuv420p',
                   '-g', '60', '-movflags', '+faststart', str(destino)]
            subprocess.run(cmd, check=True)
            hechos += 1
        print(f'LISTO {hechos} clips en {salida}', flush=True)
    finally:
        ok, limpieza, err = resolve_mcp.script(_LIMPIAR % {'nombre': nombre, 'bins': list(BINS), 'previo': previo}, timeout=90)
        print('limpieza:', json.dumps(limpieza, ensure_ascii=False) if ok else f'no pude limpiar: {err}', flush=True)
        if render:
            try:
                os.remove(render)
            except OSError:
                pass


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opc = dict(zip(sys.argv[1:], sys.argv[2:]))
    destino = args[0] if args else str(AQUI.parent / '2_recursos' / 'guia_estilo' / 'vistas')
    ids = [int(x) for x in opc['--ids'].split(',')] if '--ids' in opc else None
    generar(destino, ids=ids, ancho=int(opc.get('--ancho', 216)), crf=int(opc.get('--crf', 30)))
