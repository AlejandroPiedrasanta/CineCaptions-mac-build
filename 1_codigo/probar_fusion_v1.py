# CineCaptions · By Cinema Productions
# 1_codigo/probar_fusion_v1.py — prueba en Resolve del movimiento sobre el video (fusion_v1.py): zoom lento, temblor, transiciones y fondo desenfocado.
"""
    python probar_fusion_v1.py <video> [zoom=normal] [transicion=zoom_blur] [golpes=1,3,5] [cortes=2,4] [fondo=0|1]

Crea una carpeta y un timeline temporales «zz_FUSION» en el proyecto abierto (solo si su título es de pruebas), importa la comp al clip de V1, renderiza y deja
`~/DaVinciSubtitles/banco/hoja_fusion.png` (cuadros alrededor de cada golpe y de cada corte) y las dos primeras comps en la carpeta del banco. Al final limpia.
Los instantes de golpes y cortes se dan en SEGUNDOS.
"""
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

CREAR = r'''
mp = project.GetMediaPool()
raiz = mp.GetRootFolder()
for f in (raiz.GetSubFolderList() or []):
    if f.GetName() == 'zz_FUSION':
        mp.DeleteFolders([f])
carpeta = mp.AddSubFolder(raiz, 'zz_FUSION')
mp.SetCurrentFolder(carpeta)
clips = mp.ImportMedia([%(video)r])
tl = mp.CreateEmptyTimeline('zz_FUSION_tl')
project.SetCurrentTimeline(tl)
tl.SetSetting('useCustomSettings', '1')
tl.SetSetting('timelineResolutionWidth', '1080')
tl.SetSetting('timelineResolutionHeight', '1920')
tl.SetSetting('timelineFrameRate', '30')
mp.AppendToTimeline(clips)
it = tl.GetItemListInTrack('video', 1)[0]
result = {'tl': tl.GetName(), 'fps': tl.GetSetting('timelineFrameRate'), 'ancho': tl.GetSetting('timelineResolutionWidth'), 'alto': tl.GetSetting('timelineResolutionHeight'),
          'dur': it.GetDuration(), 'ini': it.GetStart(), 'proyecto': project.GetName()}
'''
APLICAR = r'''
tl = project.GetCurrentTimeline()
it = tl.GetItemListInTrack('video', 1)[0]
antes = it.GetFusionCompNameList() or []
comp = it.ImportFusionComp(%(ruta)r)
despues = it.GetFusionCompNameList() or []
result = {'antes': antes, 'despues': despues, 'comp': bool(comp)}
'''
LIMPIAR = r'''
mp = project.GetMediaPool()
tl = None
for i in range(1, project.GetTimelineCount() + 1):
    t = project.GetTimelineByIndex(i)
    if t.GetName() == 'zz_FUSION_tl':
        tl = t
otro = None
for i in range(1, project.GetTimelineCount() + 1):
    t = project.GetTimelineByIndex(i)
    if t.GetName() != 'zz_FUSION_tl':
        otro = t
        break
if otro:
    project.SetCurrentTimeline(otro)
if tl:
    mp.DeleteTimelines([tl])
for f in (mp.GetRootFolder().GetSubFolderList() or []):
    if f.GetName() == 'zz_FUSION':
        mp.DeleteFolders([f])
result = {'timelines': project.GetTimelineCount()}
'''


def main():
    video = sys.argv[1]
    zoom = sys.argv[2] if len(sys.argv) > 2 else 'normal'
    zoom = None if zoom in ('0', 'no', 'none') else zoom
    trans = sys.argv[3] if len(sys.argv) > 3 else 'zoom_blur'
    golpes = [float(x) for x in (sys.argv[4] if len(sys.argv) > 4 else '1,3').split(',') if x]
    cortes = [float(x) for x in (sys.argv[5] if len(sys.argv) > 5 else '2,4').split(',') if x]
    fondo = (sys.argv[6] if len(sys.argv) > 6 else '0') == '1'
    import banco_pruebas as b
    import fusion_v1
    import resolve_mcp
    ok, info, err = resolve_mcp.script(CREAR % {'video': video}, timeout=90)
    print('timeline:', ok, info, err or '', flush=True)
    if not ok:
        return
    try:
        fps = float(info['fps'])
        dur = int(info['dur'])
        comp = Path.home() / 'DaVinciSubtitles' / 'banco' / 'fusion_prueba.comp'
        cfg = {'fps': fps, 'zoom': zoom, 'golpes': [int(round(t * fps)) for t in golpes], 'cortes': [int(round(t * fps)) for t in cortes], 'transicion': trans}
        if fondo:
            cfg['fondo'] = {'lienzo': (int(info['ancho']), int(info['alto'])), 'clip': (1280, 720), 'desenfoque': float(sys.argv[7]) if len(sys.argv) > 7 else 40}
        texto = fusion_v1.texto_comp(dur, fps, zoom=zoom, golpes=cfg['golpes'], cortes=cfg['cortes'], transicion=trans, fondo=cfg.get('fondo'))
        import os
        if os.environ.get('FUSION_COMP'):                       # una comp a mano (para explorar cómo se comporta Fusion)
            texto = Path(os.environ['FUSION_COMP']).read_text(encoding='utf-8').replace('@DUR@', str(dur))
        comp.parent.mkdir(parents=True, exist_ok=True)
        comp.write_text(texto, encoding='utf-8')
        print('comp escrita:', comp, len(texto), 'bytes', flush=True)
        ok, r, err = resolve_mcp.script(APLICAR % {'ruta': str(comp)}, timeout=60)
        print('aplicar:', ok, r, err or '', flush=True)
        t0 = time.time()
        render = b.renderizar('fusion_prueba', tope_s=400)
        print('render:', render, f'{time.time() - t0:.0f} s', flush=True)
        if render:
            instantes = []
            for t in golpes:
                instantes += [t - 0.1, t + 0.05, t + 0.2]
            for t in cortes:
                instantes += [t - 0.12, t - 0.05, t, t + 0.05, t + 0.12]
            instantes = instantes or [0.5, 2.0, 4.0]
            hoja = b.hoja(render, instantes[:24], Path.home() / 'DaVinciSubtitles' / 'banco' / 'hoja_fusion.png', columnas=6, recorte=(0.0, 1.0), fps=fps)
            print('hoja:', hoja, flush=True)
    finally:
        ok, r, err = resolve_mcp.script(LIMPIAR, timeout=60)
        print('limpieza:', ok, r, err or '', flush=True)


if __name__ == '__main__':
    main()
