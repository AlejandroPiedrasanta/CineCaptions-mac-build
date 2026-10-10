# CineCaptions · By Cinema Productions
# 1_codigo/probar_estilos_app.py — prueba de los 3 estilos (VIRAL, Kinetic, Referencia) DENTRO de la app, sin pantalla y SIN Resolve: sonidos, emojis y colores que salen en cada uno.
"""
Uso:   python probar_estilos_app.py <palabras.json> [--pack VIRAL|Kinetic|Referencia] [--idioma en] [--marcar n1,n2,...] [--donde todas|principal|ninguna] [--sin-sfx] [--detalle]

Igual que probar_viral_app.py pero para cualquiera de los tres estilos: crea SubtitleApp sin pantalla (QT offscreen, Resolve apagado), llama a la MISMA función que usan GO y «Generar»
del editor Creativo (_generar_con_kinetic o _generar_con_guion) y resume lo que decide: cuántos bloques, qué sonido suena y cuándo (por palabra / solo la principal), los emojis y sus
sonidos, y los colores / estilos que rotan. NO toca las preferencias del usuario (se parchean en memoria) ni Resolve (CINECAPTIONS_SIN_MCP).
--donde  fuerza «Sonido por palabra» (todas | principal | ninguna) sin guardarlo.   --detalle  imprime cada sonido con su instante.
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
    args = [a for a in sys.argv[1:] if not a.startswith('--') and (sys.argv[sys.argv.index(a) - 1] not in ('--pack', '--idioma', '--marcar', '--donde') if a in sys.argv else True)]
    nombre_pack = sys.argv[sys.argv.index('--pack') + 1] if '--pack' in sys.argv else 'VIRAL'
    idioma = sys.argv[sys.argv.index('--idioma') + 1] if '--idioma' in sys.argv else 'en'
    marcar = [int(x) for x in sys.argv[sys.argv.index('--marcar') + 1].split(',')] if '--marcar' in sys.argv else []
    donde = sys.argv[sys.argv.index('--donde') + 1] if '--donde' in sys.argv else None
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
    ajustes_ui.leer_prefs = lambda: {**real(), 'plantilla': nombre_pack, 'go_pack': nombre_pack, 'go_emojis': True}
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    import sfx_rules
    sfx_rules.guardar_modo = lambda *a, **k: None                   # (las recomendaciones del estilo escribirían el sfx_modo.json REAL del usuario)
    if donde:
        original = sfx_rules.cargar_modo
        sfx_rules.cargar_modo = lambda: {**original(), 'modo': 'simple', 'donde': donde}
    import resolve_mcp
    resolve_mcp.ruta_exe = lambda: None
    resolve_mcp.estado_cacheado = lambda *a, **k: {}
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.plantilla_sel = nombre_pack
    faulthandler.dump_traceback_later(300, exit=True)
    import plantillas
    pack = plantillas.buscar_pack(nombre_pack)
    roles = [None] * len(palabras)
    for i in marcar:
        roles[i] = 'main'
    w._un_clic = not marcar
    mensajes = []
    if getattr(pack, 'guion', None) and not pack.kinetic:
        res = w._generar_con_guion(pack, palabras, roles, {}, 'estilos_app', idioma, mensajes.append, con_sfx)
        forma = 'guion'
    else:
        res = w._generar_con_kinetic(pack, palabras, roles, {}, 'estilos_app', idioma, mensajes.append, con_sfx)
        forma = 'kinetic'
    for m in mensajes:
        print('AVISO:', m)
    if res is None:
        print('FALLO: el generador devolvió None', flush=True)
        os._exit(1)
    bloques, track, pista_sfx = res
    datos = json.loads(open(track['data_path'], encoding='utf-8').read())
    cues = datos['cues']
    eventos = [(e['t'], e.get('sfx'), e.get('sfx_nombre')) for c in cues for e in (c.get('sfx_eventos') or [])]
    por_cat = {}
    for _t, cat, _n in eventos:
        por_cat[cat] = por_cat.get(cat, 0) + 1
    dur = max((c['end'] for c in cues), default=0.0)
    n_pal = len([p for p in palabras if str(p.get('word', '')).strip()])
    print(f'\n== {nombre_pack} ({forma}) · {len(cues)} bloques · {n_pal} palabras · {dur:.1f} s')
    print(f'sonidos: {len(eventos)} ({len(eventos) / max(dur, 1) * 60:.0f}/min · {len(eventos) / max(n_pal, 1) * 100:.0f} % de las palabras) · por categoría: {por_cat}')
    nombres = {}
    for _t, _c, n in eventos:
        nombres[n] = nombres.get(n, 0) + 1
    print('  archivos:', nombres)
    emojis = [(c['start'], c.get('emoji'), ' '.join(r['texto'] for r in c['runs'])[:40]) for c in cues if c.get('emoji')]
    print(f'emojis: {len(emojis)} de {len(cues)} bloques ({len(emojis) / max(len(cues), 1) * 100:.0f} %)')
    if forma == 'guion':
        est = [r.get('estilo') or c.get('estilo') for c in cues for r in c['runs'] if r['rol'] == 'main']
    else:
        est = [r['k'] for c in cues for r in c['runs']]
    cuenta = {}
    for e in est:
        cuenta[e] = cuenta.get(e, 0) + 1
    print('estilos / clips usados:', dict(sorted(cuenta.items(), key=lambda kv: str(kv[0]))))
    seguidos = sum(1 for a, b in zip(est, est[1:]) if a == b)
    print(f'repeticiones seguidas del mismo estilo/clip: {seguidos} de {max(len(est) - 1, 1)}')
    if '--detalle' in sys.argv:
        for t, cat, n in sorted(eventos):
            print(f'   {t:7.2f}  {cat}  {n}')
        for t, eid, texto in emojis:
            print(f'   {t:7.2f}  emoji {eid}  «{texto}»')
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
