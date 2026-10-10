# CineCaptions · By Cinema Productions
# 1_codigo/probar_viral_app.py — prueba del estilo «VIRAL» DENTRO de la app (sin pantalla y SIN Resolve): GO, Creativo (palabras marcadas), sonidos y emojis.
"""
Uso:   python probar_viral_app.py <palabras.json> [--idioma en] [--marcar n1,n2,...] [--sin-sfx]

Crea SubtitleApp sin pantalla (QT offscreen, Resolve apagado), con el pack VIRAL elegido, y llama a la MISMA función que usan GO y «Generar» del editor Creativo
(_generar_con_kinetic → viral_planificador). Imprime el plan, los sonidos que asignó (un evento por palabra) y los emojis, y deja el .json en ~/DaVinciSubtitles.
--marcar  índices de palabras pintadas como «Principal» en Creativo (el pincel del editor): llevan efecto aunque les toque pila.
NO toca las preferencias del usuario (se parchean en memoria) ni Resolve (CINECAPTIONS_SIN_MCP).
"""
import faulthandler
import importlib.util
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['CINECAPTIONS_SIN_MCP'] = '1'
    sys.path.insert(0, AQUI)
    os.chdir(AQUI)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    idioma = sys.argv[sys.argv.index('--idioma') + 1] if '--idioma' in sys.argv else 'en'
    marcar = [int(x) for x in sys.argv[sys.argv.index('--marcar') + 1].split(',')] if '--marcar' in sys.argv else []
    con_sfx = '--sin-sfx' not in sys.argv
    palabras = json.loads(open(args[0], encoding='utf-8').read())
    palabras = palabras.get('palabras') if isinstance(palabras, dict) else palabras
    spec = importlib.util.spec_from_file_location('cc_main', os.path.join(AQUI, 'CineCaptions (script principal).py'))
    M = importlib.util.module_from_spec(spec)
    sys.modules['cc_main'] = M
    spec.loader.exec_module(M)
    import ajustes_ui
    import licencia
    licencia.vigente = lambda: True
    M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: {**real(), 'plantilla': 'VIRAL', 'go_pack': 'VIRAL', 'go_emojis': True}
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    import sfx_rules
    sfx_rules.guardar_modo = lambda *a, **k: None                   # (las recomendaciones del estilo escribirían el sfx_modo.json REAL del usuario)
    import resolve_mcp
    resolve_mcp.ruta_exe = lambda: None
    resolve_mcp.estado_cacheado = lambda *a, **k: {}
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.plantilla_sel = 'VIRAL'
    faulthandler.dump_traceback_later(240, exit=True)
    import plantillas
    pack = plantillas.buscar_pack('VIRAL')
    print('pack:', pack.nombre, '· kinetic:', pack.kinetic, '· viral:', pack.viral, '· _pack_kinetic:', bool(w._pack_kinetic()), '· _pack_guion:', bool(w._pack_guion()))
    roles = [None] * len(palabras)
    for i in marcar:
        roles[i] = 'main'
    w._un_clic = not marcar                                   # sin marcas = GO (decide solo); con marcas = el editor Creativo (mandan las marcas)
    mensajes = []
    res = w._generar_con_kinetic(pack, palabras, roles, {}, 'viral_app', idioma, mensajes.append, con_sfx)
    for m in mensajes:
        print('AVISO:', m)
    if res is None:
        print('FALLO: _generar_con_kinetic devolvió None', flush=True)
        os._exit(1)
    bloques, track, pista_sfx = res
    datos = json.loads(open(track['data_path'], encoding='utf-8').read())
    print(f"\nestilo del manifiesto: {track['style']!r} · clip_prueba: {track.get('clip_prueba')!r} · json: {track['data_path']}")
    print(f"sonidos: {'sfx_archivos' in track and sum(len(a) for a in track['sfx_archivos'].values())} archivos de {len(track.get('sfx_archivos') or {})} categorías · resumen {track.get('sfx_resumen')}")
    for k, c in enumerate(datos['cues']):
        ev = c.get('sfx_eventos') or []
        print(f"{k:3d} {c['plantilla']:<10s} {c['start']:6.2f}→{c['end']:6.2f}  sfx={'sí' if c.get('sfx') else 'no'}({len(ev)} ev)  emoji={c.get('emoji')}  "
              + ' '.join(f"[{r['k'][2:]}:{r['texto']}]" for r in c['runs']))
    n_ef = sum(1 for c in datos['cues'] if c['plantilla'] in ('v shatter', 'v select', 'v drag'))
    n_em = sum(1 for c in datos['cues'] if c.get('emoji'))
    print(f"\n{len(datos['cues'])} bloques · {n_ef} con efecto · {n_em} con emoji · {sum(len(c.get('sfx_eventos') or []) for c in datos['cues'])} eventos de sonido")
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
