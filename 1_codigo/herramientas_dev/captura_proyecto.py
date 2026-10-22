"""v5.32: captura de la página Proyecto SIN pantalla (la franja del audio y el bloque del tema con el diseño de las maquetas del usuario), sin
tocar sus preferencias ni proyectos ni Resolve.

    python captura_proyecto.py <salida.png> [<video>] [--pagina estilos|efectos]
"""
import importlib.util
import os
import sys
import time

CODIGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('CINECAPTIONS_SIN_MCP', '1')


def main():
    salida = sys.argv[1]
    video = next((a for a in sys.argv[2:] if not a.startswith('--') and os.path.exists(a)), None)
    pagina = sys.argv[sys.argv.index('--pagina') + 1] if '--pagina' in sys.argv else 'estilos'
    sys.path.insert(0, CODIGO)
    spec = importlib.util.spec_from_file_location('cc_main', os.path.join(CODIGO, 'CineCaptions (script principal).py'))
    M = importlib.util.module_from_spec(spec)
    sys.modules['cc_main'] = M
    spec.loader.exec_module(M)
    import ajustes_ui
    import licencia
    import proyectos
    import resolve_mcp
    licencia.vigente = lambda: True
    M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    ajustes_ui.mostrar_novedades = lambda *a, **k: None
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    proyectos.guardar = lambda *a, **k: None
    resolve_mcp.ruta_exe = lambda: None
    app = M.ui.crear_app(['captura'], carpeta_fuentes=M.BASE_RECURSOS / 'fonts')
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.resize(1720, 1060)
    w.show()
    for _ in range(40):
        app.processEvents()
        time.sleep(0.05)
    if video:
        w.video_var.set(video)
    w.ir_a(pagina)
    t0 = time.time()
    while time.time() - t0 < 12:
        app.processEvents()
        time.sleep(0.05)
    w.grab().save(salida)
    print('captura', salida, flush=True)
    os._exit(0)


if __name__ == '__main__':
    main()
