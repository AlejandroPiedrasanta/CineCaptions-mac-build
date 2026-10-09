# CineCaptions · By Cinema Productions
# 1_codigo/probar_efectos.py — prueba de punta a punta de la página «Efectos»: suelta un video en la app sin pantalla (GO real con los efectos visuales ENCENDIDOS), Resolve renderiza y se saca una hoja de cuadros.
"""
    python probar_efectos.py <video> [pack=Referencia]

Igual que hacer_vista_slider.py (proyecto nuevo, GO, render, limpieza y vuelta al proyecto de antes), pero con CINECAPTIONS_FX=1 (probar_go.py enciende «go_efectos_visuales» solo en
memoria). Al final saca los cuadros de la intro, de cada corte con transición y de cada icono flotante (los instantes salen de ~/DaVinciSubtitles/efectos_plan.json) en
~/DaVinciSubtitles/banco/hoja_efectos.png. El render queda en ~/DaVinciSubtitles/banco/efectos_prueba.mov.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
AUDIO_CODIGO = ("tl = project.GetCurrentTimeline()\n"
                "result = [(i, tl.GetTrackName('audio', i), len(tl.GetItemListInTrack('audio', i) or [])) for i in range(1, tl.GetTrackCount('audio') + 1)]")
PISTAS_CODIGO = ("tl = project.GetCurrentTimeline()\n"
                 "result = [(i, tl.GetTrackName('video', i), len(tl.GetItemListInTrack('video', i) or [])) for i in range(1, tl.GetTrackCount('video') + 1)]")


def main(media, pack='Referencia', timeout=900):
    import banco_pruebas as b
    import mcp_cinecaptions as m
    import resolve_mcp
    media = str(media)
    previo = {}
    if resolve_mcp.resolve_abierto():
        ok, previo, _err = resolve_mcp.script(m._ESTADO_PREVIO % {'nombre': 'CineCaptions'}, timeout=40)
        previo = previo if ok and isinstance(previo, dict) else {}
    print('Resolve antes:', previo or 'cerrado', flush=True)
    stem = Path(media).stem[:40]
    entorno = {**os.environ, 'DUMP_S': str(timeout)}
    if not os.environ.get('FX_OFF'):                      # FX_OFF=1: GO normal, sin efectos (comprueba que apagado no cambia nada)
        entorno['CINECAPTIONS_FX'] = '1'
    render = None
    try:
        r = subprocess.run([sys.executable, str(AQUI / 'probar_go.py'), media, pack, '--soltar'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=timeout + 60, env=entorno)
        print('\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'site-packages' not in l)[-2200:], flush=True)
        if r.returncode != 0:
            raise RuntimeError(f'GO no terminó (código {r.returncode})')
        ok_v, info, _e = resolve_mcp.script(m._VERIFICAR_TL, timeout=30)
        print('timeline:', json.dumps(info, ensure_ascii=False)[:500], flush=True)
        ok_f, pistas, _e = resolve_mcp.script("tl = project.GetCurrentTimeline()\nresult = [(i, tl.GetTrackName('video', i), len(tl.GetItemListInTrack('video', i) or [])) for i in range(1, tl.GetTrackCount('video') + 1)]", timeout=30)
        print('pistas de video:', pistas, flush=True)
        if os.environ.get('FX_DOBLE'):                                     # re-aplicar no debe apilar nada: se vuelve a poner el mismo plan
            import efectos_visuales as F
            plan0 = json.loads((Path.home() / 'DaVinciSubtitles' / 'efectos_plan.json').read_text(encoding='utf-8'))
            print('segunda aplicación:', F.aplicar({'eventos': plan0['eventos']}, offset_frames=0), flush=True)
            ok_f, pistas, _e = resolve_mcp.script(PISTAS_CODIGO, timeout=30)
            print('pistas tras la segunda:', pistas, flush=True)
        if os.environ.get('FX_OFF'):
            print('sin efectos: ¿pistas FX?', [p for p in (pistas or []) if str(p[1]).startswith('FX-')], flush=True)
            return
        render = b.renderizar('efectos_prueba', tope_s=timeout)
        print('render:', render, flush=True)
        try:
            import av as _av
            _c = _av.open(render)
            print('duración del render: %.2f s' % (float(_c.duration) / 1e6), flush=True)
            _c.close()
        except Exception:
            pass
        ok_a, audio, _e = resolve_mcp.script(AUDIO_CODIGO, timeout=30)
        print('pistas de audio:', audio, flush=True)
        import subprocess as _sp, re as _re
        def _vol(ruta, ss, t):
            r = _sp.run(['ffmpeg', '-hide_banner', '-nostats', '-ss', str(ss), '-t', str(t), '-i', str(ruta), '-vn', '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
            m = _re.search(r'mean_volume:\s*(-?[\d.]+) dB', r.stderr)
            return float(m.group(1)) if m else None
        for ss, t in ((0, 1.6), (4, 3)):
            print(f'volumen {ss}-{ss + t}s · fuente {_vol(media, ss, t)} dB · render {_vol(render, ss, t)} dB', flush=True)
        plan = json.loads((Path.home() / 'DaVinciSubtitles' / 'efectos_plan.json').read_text(encoding='utf-8'))
        instantes = []
        vistos = {}
        for e in plan['eventos']:
            vistos[e['tipo']] = vistos.get(e['tipo'], 0) + 1
            if vistos[e['tipo']] > 3:                                  # unos pocos de cada tipo (un overlay continuo tiene decenas)
                continue
            if e['tipo'] == 'intro':
                instantes += [0.1, 0.3]
            elif e['tipo'] == 'corte':
                instantes += [e['ini'] - 0.2, e['ini'], e['ini'] + 0.2]
            else:
                instantes += [e['ini'] + 0.35, e['ini'] + 1.6]
        mov = plan.get('movimiento') or {}
        for t in (mov.get('golpes') or [])[:3]:
            instantes += [t - 0.1, t + 0.04, t + 0.15]
        for t in (mov.get('cortes') or [])[:3]:
            instantes += [t - 0.1, t, t + 0.1]
        for t in (mov.get('saltos') or [])[:4]:
            instantes += [t - 0.1, t + 0.1]
        hoja = b.hoja(render, instantes[:36], Path.home() / 'DaVinciSubtitles' / 'banco' / 'hoja_efectos.png', columnas=6, recorte=(0.0, 1.0))
        print('hoja:', hoja, flush=True)
    finally:
        ok, limpieza, err = resolve_mcp.script(m._LIMPIAR_ARRASTRE % {'stem': stem, 'previo_p': previo.get('proyecto'), 'previo_tl': previo.get('timeline'),
                                                                      'borrar': bool(previo.get('proyecto'))}, timeout=60)
        print('limpieza:', json.dumps(limpieza, ensure_ascii=False) if ok else f'no pude limpiar: {err}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'Referencia')
