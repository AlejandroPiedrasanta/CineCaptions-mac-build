# CineCaptions · By Cinema Productions
# 1_codigo/probar_viral.py — prueba del estilo «VIRAL»: laboratorio de comps, planificador sobre un video real y render con hoja de cuadros.
"""
Uso:
  python probar_viral.py lab [--sin-pack]                       coloca los clips de laboratorio «v lab …» (pack_viral.py --lab) y renderiza
  python probar_viral.py cues archivo.json [--nombre x] [--fondo (r,g,b)]   coloca unos cues ya hechos (kinetic_captions.escribir) y renderiza
  python probar_viral.py video <media> [--nombre x] [--fondo-video]         palabras del video (transcribir) → viral_planificador → Resolve → render
Siempre sobre el timeline temporal zz_BANCO (banco_pruebas): comprobar el proyecto abierto y acabar con `limpiar` (o el MCP limpiar_banco).
  python probar_viral.py limpiar
CUIDADO: toca el Resolve del usuario; los arneses parchean ajustes_ui.guardar_prefs.
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / '2_recursos' / 'generador_packs'))
import ajustes_ui

ajustes_ui.guardar_prefs = lambda *a, **k: None          # los arneses ensucian las prefs reales (memoria del proyecto)

import banco_pruebas

CARPETA = banco_pruebas.CARPETA


def _arg(argv, nombre, defecto=None):
    return argv[argv.index(nombre) + 1] if nombre in argv else defecto


ELEMENTOS = [('v fina', 'did you hear', 0.09), ('v negrita', 'Bakery', 0.16), ('v shatter', 'Shatter', 0.26), ('v select', 'Select', 0.26), ('v drag', 'Drag', 0.26)]


def cues_lab(nombres, dur=2.0):
    """Un cue por clip de laboratorio, uno detrás de otro."""
    runs = lambda k, t, texto, size, x=0.5, y=0.5: {'k': k, 't': t, 'texto': texto, 'size': size, 'x': x, 'y': y}
    return [{'start': dur * i, 'end': dur * i + dur, 'plantilla': 'lab', 'caja': [0.2, 0.8], 'runs': [runs(k, dur * i, 'Test', 0.25)]} for i, k in enumerate(nombres)]


def colocar_y_render(cues, nombre, fondo_color=(24, 24, 28), media=None, audio=None, fps=30, fin=None, hoja_tiempos=None, columnas=4, ancho_hoja=270, recorte=(0.12, 0.88), res=(1080, 1920)):
    """Coloca los cues en el banco (timeline temporal zz_BANCO), renderiza y SIEMPRE limpia al acabar: vuelve al timeline que tenía el usuario."""
    fin = fin or (max(c['end'] for c in cues) + 1.0)
    try:
        r = banco_pruebas.preparar(audio=audio, fondo=media, color=fondo_color, frames=int(fin * fps) + 30, fps=fps, renovar=('VIRAL',), ancho=res[0], alto=res[1])
        print('banco:', r, flush=True)
        ok, msg = banco_pruebas.colocar_viral(cues, formato='h' if res[0] > res[1] else 'v')
        print('colocar:', 'OK' if ok else 'FALLO', str(msg)[-1500:], flush=True)
        if not ok:
            return None
        ruta = banco_pruebas.renderizar(nombre, tope_s=420)
        print('render:', ruta, flush=True)
    finally:
        print('limpiar:', banco_pruebas.limpiar(), flush=True)
    if ruta and hoja_tiempos:
        print('hoja:', banco_pruebas.hoja(ruta, hoja_tiempos, str(CARPETA / f'hoja_{nombre}.png'), ancho=ancho_hoja, recorte=recorte, columnas=columnas, fps=fps, aspecto=res[1] / res[0]), flush=True)
    return ruta


def main(argv):
    cmd = argv[0] if argv else 'lab'
    if cmd == 'limpiar':
        print(banco_pruebas.limpiar())
        return
    if cmd == 'lab':
        import viral_lab
        if '--sin-pack' not in argv:
            import pack_viral
            print(pack_viral.construir(lab=True)[0])
        nombres = [k for k in viral_lab.todos() if not argv[1:2] or any(k.endswith(x) for x in argv[1].split(','))]
        dur = 2.0
        cues = cues_lab(nombres, dur)
        tiempos = [round(dur * i + d, 2) for i in range(len(nombres)) for d in (0.15, 0.5, 1.2)]
        print(list(zip(nombres, tiempos)))
        colocar_y_render(cues, 'viral_lab', hoja_tiempos=tiempos, columnas=4)
        return
    if cmd == 'elementos':
        import pack_viral
        if '--sin-pack' not in argv:
            print(pack_viral.construir()[0])
        quiero = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else None
        spec = [e for e in ELEMENTOS if not quiero or any(e[0].endswith(q) for q in quiero)]
        dur = 2.4
        cues = [{'start': dur * i, 'end': dur * i + 2.0, 'plantilla': 'elementos', 'caja': [0.4, 0.6],
                 'runs': [{'k': k, 't': dur * i, 'fin': dur * i + 2.0, 'texto': t, 'size': sz, 'x': 0.5, 'y': 0.5}]} for i, (k, t, sz) in enumerate(spec)]
        offs = (0.05, 0.15, 0.3, 0.45, 0.6, 0.8, 1.1, 1.8)
        tiempos = [round(dur * i + d, 2) for i in range(len(spec)) for d in offs]
        colocar_y_render(cues, 'viral_elementos', hoja_tiempos=tiempos, columnas=len(offs), ancho_hoja=270, recorte=(0.38, 0.62))
        return
    if cmd == 'calibrar':
        import pack_viral
        if '--sin-pack' not in argv:
            print(pack_viral.construir()[0])
        res = tuple(int(v) for v in _arg(argv, '--res', '1080x1920').lower().split('x'))
        spec = [('v fina', 'HHHH', 0.20), ('v negrita', 'HHHH', 0.20), ('v drag', 'HHHH', 0.20)]
        dur = 2.4
        cues = [{'start': dur * i, 'end': dur * i + 2.0, 'plantilla': 'calibrar', 'caja': [0.4, 0.6],
                 'runs': [{'k': k, 't': dur * i, 'fin': dur * i + 2.0, 'texto': t, 'size': sz, 'x': 0.5, 'y': 0.5}]} for i, (k, t, sz) in enumerate(spec)]
        ruta = colocar_y_render(cues, 'viral_calibrar', hoja_tiempos=[1.5, 3.9, 6.3], columnas=3, ancho_hoja=270, recorte=(0.40, 0.60), res=res)
        if ruta:
            import banco_pruebas as B
            import viral_captions as VC
            for k, (clave, texto, size) in enumerate(spec):
                fr = int((dur * k + 1.6) * 30)
                for um in (60, 150):
                    m = B.medir_texto(ruta, [fr], fondo=(24, 24, 28), umbral=um, ancho=min(res[0], 960), aspecto=res[1] / res[0])
                    for y0, y1, x0, x1 in m[0]['cajas']:
                        ancho, alto = (x1 - x0) * res[0], (y1 - y0) * res[1]
                        print(f'{clave} umbral {um}: ancho {ancho:.0f}px alto {alto:.0f}px  centro y={(y0 + y1) / 2:.4f} x={(x0 + x1) / 2:.4f}  | predicho (K_PX={VC.K_PX}, ancho_tl={res[0]}) ancho {VC.ancho_px(clave, texto, size, res[0]):.0f} cap {VC.cap_de_size(clave, size, res[0]):.1f}', flush=True)
        return
    if cmd == 'video':
        import viral_planificador
        media = Path(argv[1])
        solo_palabras = media.suffix.lower() == '.json'          # un .json de palabras (sin video): fondo gris y la duración sale de la última palabra
        ruta_p = media if solo_palabras else Path.home() / 'DaVinciSubtitles' / 'mcp' / f'palabras_{media.stem}.json'
        pal = json.loads(ruta_p.read_text(encoding='utf-8'))
        pal = pal.get('palabras') or pal.get('words') if isinstance(pal, dict) else pal
        ancla = _arg(argv, '--ancla', 'bajo')
        mains = [m for m in _arg(argv, '--mains', '').split(',') if m] or None
        if solo_palabras:
            dur = float(pal[-1].get('end', pal[-1].get('start', 0))) + 1.0
        else:
            import subprocess
            dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(media)]).decode().strip())
        dims = tuple(int(v) for v in _arg(argv, '--res', '1080x1920').lower().split('x'))
        res = viral_planificador.planificar(pal, idioma=_arg(argv, '--idioma', 'en'), ancla=ancla, mains=mains, fin_video=dur, ancho_tl=dims[0], alto_tl=dims[1])
        print(viral_planificador.resumen(res), flush=True)
        cues = res['cues']
        nombre = _arg(argv, '--nombre', 'viral_' + media.stem.replace(' ', '').replace('(', '').replace(')', ''))
        (CARPETA / f'cues_{nombre}.json').write_text(json.dumps({'language': 'en', 'cues': cues}, ensure_ascii=False, indent=1), encoding='utf-8')
        if '--solo-plan' in argv:
            return
        tiempos = [float(t) for t in _arg(argv, '--tiempos', '').split(',') if t]
        if not tiempos:
            for c in cues:
                if c['plantilla'] in ('v shatter', 'v select', 'v drag'):
                    h = next(r['t'] for r in c['runs'] if r['k'] == c['plantilla'])
                    tiempos += [round(h + 0.25, 2), round(h + 1.0, 2)]
                else:
                    tiempos.append(round(c['end'] - 0.25, 2))
        horizontal = dims[0] > dims[1]
        colocar_y_render(cues, nombre, media=None if (horizontal or solo_palabras or '--gris' in argv) else str(media), fin=dur, hoja_tiempos=tiempos[:24], columnas=int(_arg(argv, '--columnas', '6')),
                         ancho_hoja=(400 if horizontal else 240), recorte=((0.35, 1.0) if horizontal else (0.40, 0.80)), res=dims)
        return
    if cmd == 'cues':
        cues = json.loads(Path(argv[1]).read_text(encoding='utf-8'))['cues']
        tiempos = [float(t) for t in _arg(argv, '--tiempos', '').split(',') if t] or [round(c['start'] + 0.7, 2) for c in cues][:16]
        colocar_y_render(cues, _arg(argv, '--nombre', 'viral_cues'), hoja_tiempos=tiempos)
        return
    raise SystemExit(__doc__)


if __name__ == '__main__':
    argv = [a for a in sys.argv[1:] if a != '--temporal']
    if '--temporal' in sys.argv:                  # en un proyecto TEMPORAL y vacío de Resolve (no ensucia el del usuario); ver proyecto_pruebas.py
        import proyecto_pruebas
        print('proyecto temporal:', proyecto_pruebas.entrar(), flush=True)
        try:
            main(argv)
        finally:
            print('de vuelta:', proyecto_pruebas.salir(), flush=True)
    else:
        main(argv)
