# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_go_sin_resolve.py — GO de punta a punta SIN Resolve (CINECAPTIONS_SIN_RESOLVE=1), sin pantalla, sobre una copia del video.
"""
    6_compilacion/venv315/Scripts/python.exe 1_codigo/herramientas_dev/probar_go_sin_resolve.py <video> [--por-ajuste] [--tema Kinetic|Referencia|VIRAL|Tema4|Tema5|Tema6 (en memoria)]

--por-ajuste: en vez de CINECAPTIONS_SIN_RESOLVE=1, enciende en memoria el interruptor de Ajustes «Video MP4 en lugar de Resolve».

Usa una COPIA del video (el MP4 sale junto a él: «<video> (CineCaptions).mp4»). No escribe las preferencias ni los proyectos recientes del
usuario y no abre el Explorador; sí deja en ~/DaVinciSubtitles lo de cualquier GO (<video>.<idioma>.guion.json, .srt, .marcas.json): bórralo
si el video era de prueba. Imprime el avance, los pasos y las últimas líneas del Registro.
"""
import faulthandler
import importlib.util
import os
import sys
import time

CODIGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    media = os.path.abspath([a for a in sys.argv[1:] if not a.startswith('--')][0])
    por_ajuste = '--por-ajuste' in sys.argv            # en vez de forzar el entorno, el interruptor de Ajustes (go_salida_mp4) solo en memoria
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    if not por_ajuste:
        os.environ['CINECAPTIONS_SIN_RESOLVE'] = '1'
    sys.path.insert(0, CODIGO)
    os.chdir(CODIGO)
    spec = importlib.util.spec_from_file_location('cc_main', os.path.join(CODIGO, 'CineCaptions (script principal).py'))
    M = importlib.util.module_from_spec(spec)
    sys.modules['cc_main'] = M
    spec.loader.exec_module(M)
    import ajustes_ui
    import licencia
    import proyectos
    import qt_kit
    import registro
    import render_sin_resolve
    import resolve_mcp
    licencia.vigente = lambda: True
    M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    ajustes_ui.mostrar_novedades = lambda *a, **k: None
    if por_ajuste:
        _leer = ajustes_ui.leer_prefs
        ajustes_ui.leer_prefs = lambda: {**_leer(), 'go_salida_mp4': True}
    tema = sys.argv[sys.argv.index('--tema') + 1] if '--tema' in sys.argv else None     # v5.5.8: el tema de GO (nombre interno: Kinetic, Referencia, VIRAL, Tema4…), en memoria
    if tema:
        _leer_t = ajustes_ui.leer_prefs
        ajustes_ui.leer_prefs = lambda: {**_leer_t(), 'go_pack': tema}
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    proyectos.guardar = lambda *a, **k: None
    render_sin_resolve.mostrar_en_carpeta = lambda r: print('MOSTRARIA', r, flush=True)
    resolve_mcp.ruta_exe = lambda: None
    qt_kit.mostrar_mensaje = lambda tipo, titulo, texto, parent=None, botones=None: print(f'DIALOGO[{tipo}] {titulo}: {str(texto)[:300]!r}', flush=True) or True
    M.ui.error_con_acciones = lambda *a, **k: print('ERROR_CON_ACCIONES', str(a)[:400], flush=True)

    app = M.ui.crear_app(['go'], carpeta_fuentes=M.BASE_RECURSOS / 'fonts')
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    if tema:
        w.plantilla_sel = tema
    w.move(-5000, -5000)
    w.show()
    faulthandler.dump_traceback_later(600, exit=True)
    for _ in range(40):
        app.processEvents()
        time.sleep(0.05)
    w._go_archivo = media
    w._go()
    print('sin_resolve:', w._go_sin_resolve, '· pack GO:', w._plantilla_un_clic(), flush=True)
    t0 = time.time()
    ultimo = ''
    while getattr(w, '_go_corriendo', False) and time.time() - t0 < 560:
        app.processEvents()
        time.sleep(0.05)
        linea = w.go_panel.linea.text() if callable(getattr(w.go_panel.linea, 'text', None)) else ''
        if linea != ultimo and ('Grabando' not in linea or linea.endswith('0 %')):
            ultimo = linea
            print(f'  [{time.time() - t0:5.1f}s] {linea[:120]}', flush=True)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
    print('GO terminado en %.0f s · corriendo=%s · termino=%s' % (time.time() - t0, w._go_corriendo, getattr(w, '_go_termino', None)), flush=True)
    print('pasos:', [t for _c, t in w.go_panel.PASOS], flush=True)
    for e in registro.registro().lista()[-6:]:
        print('REGISTRO %s · %s · %s' % (e.nivel, e.origen, str(e.mensaje)[:220]), flush=True)
    faulthandler.cancel_dump_traceback_later()
    os._exit(0 if getattr(w, '_go_termino', False) else 1)


if __name__ == '__main__':
    main()
