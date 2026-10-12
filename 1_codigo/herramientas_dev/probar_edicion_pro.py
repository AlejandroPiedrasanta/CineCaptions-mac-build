# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_edicion_pro.py — prueba de punta a punta de la Edición PRO en Resolve REAL (proyecto temporal zz_PRUEBAS_CC).
"""
    python 1_codigo/herramientas_dev/probar_edicion_pro.py <video> [--palabras palabras.json] [--idioma es] [--genero auto] [--mascara auto]
                                                           [--variacion 0] [--render 0-30] [--sin-salir]

1. abre el proyecto temporal (proyecto_pruebas.entrar: guarda y cierra el del usuario) y arma un timeline con el video en V1;
2. transcribe (o lee --palabras: [{'word','start','end'}]) y planifica (edicion_pro.planificar) e imprime el plan;
3. lo coloca (edicion_pro.aplicar: Magic Mask en Studio) y, con --render a-b, renderiza ese tramo a ~/DaVinciSubtitles/edicion_pro/pruebas/render_pro.mp4
   y hace una hoja de contactos (cada 1,5 s);
4. sale del temporal (vuelve a abrir el proyecto del usuario y borra el temporal) salvo --sin-salir.
OJO: tras renderizar NO se cambia de página a mano (Resolve 21.1.1 se cayó pasando de Entrega a Edición justo después de un render por API).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edicion_pro  # noqa: E402
import proyecto_pruebas as PP  # noqa: E402
import resolve_mcp  # noqa: E402

_RENDER = r'''
import os, time
tl = project.GetCurrentTimeline()
base = tl.GetStartFrame()
fps = float(tl.GetSetting('timelineFrameRate') or 30)
project.DeleteAllRenderJobs()
project.SetRenderSettings({'SelectAllFrames': False, 'MarkIn': base + int(%(a)f * fps), 'MarkOut': base + int(%(b)f * fps) - 1,
                           'TargetDir': %(dir)r, 'CustomName': 'render_pro', 'ExportVideo': True, 'ExportAudio': True})
project.SetCurrentRenderFormatAndCodec('mp4', 'H264')
job = project.AddRenderJob()
project.StartRendering(job)
t0 = time.time()
while project.IsRenderingInProgress() and time.time() - t0 < 55:
    time.sleep(1)
result = {'job': job, 'estado': project.GetRenderJobStatus(job), 's': round(time.time() - t0, 1)}
'''
_ESPERAR = r'''
import time
t0 = time.time()
while project.IsRenderingInProgress() and time.time() - t0 < 55:
    time.sleep(1)
j = (project.GetRenderJobList() or [{}])[-1]
result = project.GetRenderJobStatus(j.get('JobId')) if j else None
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--palabras')
    ap.add_argument('--idioma', default='es')
    ap.add_argument('--genero', default='auto')
    ap.add_argument('--mascara', default='auto')
    ap.add_argument('--variacion', type=int, default=0)
    ap.add_argument('--render', default='')
    ap.add_argument('--sin-salir', action='store_true')
    a = ap.parse_args()
    video = str(Path(a.video).resolve())
    if a.palabras:
        palabras = json.loads(Path(a.palabras).read_text(encoding='utf-8'))
    else:
        import subtitle_transcriber as st
        palabras = st.transcribe(video, a.idioma, 'small')
    w, h, dur, fps = edicion_pro.medir(video)
    try:
        import efectos_visuales
        cortes = efectos_visuales.detectar_cortes(video) or []
    except Exception:
        cortes = []
    op = dict(edicion_pro.OPCIONES_POR_DEFECTO, pro_genero=a.genero, pro_mascara=a.mascara, pro_variacion=a.variacion, pro_ia_local=False)
    t0 = time.time()
    plan = edicion_pro.planificar(video, palabras, dur, cortes=cortes, idioma=a.idioma, opciones=op)
    print(f'plan ({time.time() - t0:.1f} s): {plan["resumen"]} · acento {plan["direccion"]["acento"]} · {plan["direccion"]["fuenteTitular"]}/{plan["direccion"]["fuenteTexto"]}')
    for p in plan['piezas']:
        v = p['valores']
        txt = ' / '.join(str(v.get(k)) for k in ('linea1', 'linea2', 'numero', 'unidad', 'texto', 'titulo', 'item1', 'nombre1') if v.get(k))
        print(f"  {p['ini']:6.2f}-{p['fin']:6.2f} {p['pieza']:9s} {p['capa']:7s} {txt[:70]}")
    PP.entrar()
    try:
        tw, th = (1080, 1920) if (h or 0) > (w or 0) else (1920, 1080)          # como GO: timeline HD aunque el video sea 4K
        r = resolve_mcp.crear_timeline_con_video(video, nombre='PRO prueba', ancho=tw, alto=th, fps=round(fps, 3) if fps else 30)
        print('timeline:', {k: r.get(k) for k in ('timeline', 'ancho', 'alto', 'fps', 'error')})
        t0 = time.time()
        ok, msg = edicion_pro.aplicar(plan, al_estado=print)
        print(f'aplicar ({time.time() - t0:.1f} s): ok={ok} {msg}')
        if a.render:
            ini, fin = (float(x) for x in a.render.split('-'))
            carpeta = Path.home() / 'DaVinciSubtitles' / 'edicion_pro' / 'pruebas'
            ok_r, rr, err = resolve_mcp.script(_RENDER % {'a': ini, 'b': fin, 'dir': str(carpeta)}, timeout=58)
            print('render:', rr or err)
            for _ in range(20):
                if isinstance(rr, dict) and (rr.get('estado') or {}).get('JobStatus') == 'Complete':
                    break
                ok_r, est, err = resolve_mcp.script(_ESPERAR, timeout=58)
                print('  ', est)
                if isinstance(est, dict) and est.get('JobStatus') in ('Complete', 'Failed', 'Cancelled'):
                    break
            mp4 = carpeta / 'render_pro.mp4'
            if mp4.exists():
                import subprocess
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp4), '-vf', 'fps=1/1.5,scale=216:-1,tile=10x2', '-frames:v', '1', str(carpeta / 'hoja_pro.png')])
                print('hoja:', carpeta / 'hoja_pro.png')
    finally:
        if not a.sin_salir:
            print('salir:', PP.salir())
        resolve_mcp.cerrar()


if __name__ == '__main__':
    main()
