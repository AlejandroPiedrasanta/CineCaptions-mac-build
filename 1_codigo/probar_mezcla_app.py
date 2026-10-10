# CineCaptions · By Cinema Productions
# 1_codigo/probar_mezcla_app.py — prueba del estilo MEZCLADO de «Crea tu estilo» (looks de los tres temas) DENTRO de la app, sin pantalla y SIN Resolve.
"""
Uso:   python probar_mezcla_app.py <palabras.json> [--looks t1:lima,t3:shatter,t2:3] [--idioma es] [--sin-sfx] [--manifiesto ruta.json]

Crea SubtitleApp sin pantalla (QT offscreen, Resolve apagado), arma un pack de mezcla en una carpeta TEMPORAL (no toca los packs del usuario), llama a la MISMA función que usan GO y «Generar»
(_generar_con_motor → _generar_con_mezcla) y resume lo que sale: tramos, bloques de cada tema, pistas del manifiesto, sonidos y emojis, y si algún bloque se pisa con otro.
--manifiesto escribe el manifiesto resultante (con sus sidecar .lua) para probarlo luego en Resolve. NO toca las preferencias del usuario (se parchean en memoria).
"""
import faulthandler
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

AQUI = os.path.dirname(os.path.abspath(__file__))


def _arg(nombre, defecto=None):
    return sys.argv[sys.argv.index(nombre) + 1] if nombre in sys.argv else defecto


def main():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['CINECAPTIONS_SIN_MCP'] = '1'
    sys.path.insert(0, AQUI)
    os.chdir(AQUI)
    valores = {_arg('--looks'), _arg('--idioma'), _arg('--manifiesto')}
    args = [a for a in sys.argv[1:] if not a.startswith('--') and a not in valores]
    looks = (_arg('--looks') or 't1:lima,t3:shatter,t2:3,t3:pila,t1:serif,t2:1').split(',')
    idioma = _arg('--idioma', 'es')
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
    tmp = Path(tempfile.mkdtemp(prefix='cc_mezcla_packs_'))
    import plantillas
    plantillas.CARPETA_PACKS = tmp                                     # los packs de prueba NO van a los del usuario
    real = ajustes_ui.leer_prefs
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    import sfx_rules
    sfx_rules.guardar_modo = lambda *a, **k: None                      # (las recomendaciones del estilo escribirían el sfx_modo.json REAL del usuario)
    import mezcla_planificador as mp
    nombre, carpeta = mp.crear_pack('Mezcla de prueba', looks)
    plantillas.invalidar_packs()
    ajustes_ui.leer_prefs = lambda: {**real(), 'plantilla': nombre, 'go_pack': nombre, 'go_emojis': True}
    import resolve_mcp
    resolve_mcp.ruta_exe = lambda: None
    resolve_mcp.estado_cacheado = lambda *a, **k: {}
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.plantilla_sel = nombre
    faulthandler.dump_traceback_later(300, exit=True)
    pack = plantillas.buscar_pack(nombre)
    print('pack:', pack.nombre, '· mezcla:', pack.mezcla, '· looks:', pack.looks, '· formatos:', pack.formatos, '· problemas:', pack.problemas)
    print('sirve_en_go v:', plantillas.sirve_en_go(pack, 'v'), '· h:', plantillas.sirve_en_go(pack, 'h'), '· estructura:', plantillas.estructura_de(pack))
    print('pack_permitido:', plantillas.pack_permitido(nombre), '· _pack_mezcla:', bool(w._pack_mezcla()), '· _pack_guion:', bool(w._pack_guion()), '· _pack_kinetic:', bool(w._pack_kinetic()))
    print('poster:', (carpeta / 'vista_mezcla.jpg').is_file(), '· para_manifiesto:', plantillas.para_manifiesto(nombre))
    w._un_clic = True
    mensajes = []
    import dynamic_subtitles as dyn
    pista_plantilla = w._pista_plantilla()
    roles = [None] * len(palabras)
    res = w._generar_con_motor(dyn, palabras, roles, pista_plantilla, 'prueba_mezcla', idioma, con_sfx, mensajes.append)
    for m in mensajes:
        print('AVISO:', m)
    if res is None:
        print('FALLO: el generador devolvió None', flush=True)
        os._exit(1)
    bloques, track, pista_sfx = res
    manifest = {'tracks': []}
    w._poner_pistas_motor(manifest, track, 0)
    print('\nmanifiesto: mezcla =', manifest.get('mezcla'), '· pistas:', len(manifest['tracks']))
    todos = []
    for t in manifest['tracks']:
        datos = json.loads(open(t['data_path'], encoding='utf-8').read())
        cues = datos['cues']
        todos += [(float(c['start']), float(c['end']), t['style']) for c in cues]
        extra = [(e['plantilla'].get('pack'), e.get('clip_prueba')) for e in (t.get('plantillas_extra') or [])]
        print(f"  · {t['style']:7s} {len(cues):3d} bloques · pack «{(t.get('plantilla') or {}).get('pack')}» · clip_prueba {t.get('clip_prueba')} · extra {extra} · sfx {bool(t.get('sfx_archivos'))} · emojis {len(t.get('emojis') or {})} · mezcla_pistas {'mezcla_pistas' in t}")
        eventos = [(e['t'], e.get('sfx')) for c in cues for e in (c.get('sfx_eventos') or [])]
        emojis = [c.get('emoji') for c in cues if c.get('emoji')]
        print(f'      sonidos por palabra: {len(eventos)} · bloques con emoji: {len(emojis)}')
    todos.sort()
    pisados = [(a, b) for a, b in zip(todos, todos[1:]) if a[1] > b[0] + 1e-6]
    dur = max(e for _s, e, _t in todos)
    print(f'bloques: {len(todos)} en {dur:.1f} s · que se pisan: {len(pisados)}')
    if '--manifiesto' in sys.argv:
        import archivos_seguros
        import sidecar_lua
        ruta = Path(_arg('--manifiesto'))
        archivos_seguros.escribir_json(ruta, manifest, indent=2)
        sidecar_lua.escribir_sidecar(ruta, manifest)
        print('manifiesto escrito:', ruta)
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
