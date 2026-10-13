# CineCaptions · By Cinema Productions
# 1_codigo/probar_go.py — pulsa GO de la app SIN pantalla sobre un archivo y un pack, y deja los bloques en el timeline actual de Resolve (el banco zz_BANCO).
"""
probar_go.py  (v5.9)
--------------------
El mismo botón GO de la ventana (SubtitleApp._go), pero sin que nadie lo vea: transcribe, planifica, escribe el .json y coloca en Resolve.
Lo usa la herramienta `go_real` del MCP (mcp_cinecaptions.py) para probar el flujo REAL de la app, no solo el planificador.

    python probar_go.py <audio o video> [pack]          (por defecto, el pack «Referencia»)

La ventana se «muestra» (fuera de pantalla) porque la animación final de GO es la que dispara la colocación en el timeline; si no se muestra
nunca avanza y GO se queda esperando. No toca las preferencias del usuario: el pack se parcha en memoria.
"""
import faulthandler
import importlib.util
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    # todo esto SOLO al ejecutarlo como script: el .exe lista cada .py como módulo propio y no debe heredar estos efectos al importarlo
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ.pop('CINECAPTIONS_SIN_MCP', None)
    sys.path.insert(0, AQUI)
    os.chdir(AQUI)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    soltar = '--soltar' in sys.argv                   # simula ARRASTRAR el archivo a Inicio (arranca GO solo y arma el timeline con el video)
    media = args[0]
    pack = args[1] if len(args) > 1 else 'Referencia'  # «-» = no tocar nada: las preferencias reales del usuario (lo que haría su GO)
    spec = importlib.util.spec_from_file_location('cc_main', os.path.join(AQUI, 'CineCaptions (script principal).py'))
    M = importlib.util.module_from_spec(spec)
    sys.modules['cc_main'] = M
    spec.loader.exec_module(M)
    import ajustes_ui
    import licencia
    licencia.vigente = lambda: True
    M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
    if os.environ.get('CINECAPTIONS_PACKS'):                                               # una carpeta de packs de PRUEBA (p. ej. un estilo mezclado): no toca los packs del usuario
        import plantillas
        from pathlib import Path
        plantillas.CARPETA_PACKS = Path(os.environ['CINECAPTIONS_PACKS'])
        plantillas.invalidar_packs()
    real = ajustes_ui.leer_prefs
    if pack != '-':
        ajustes_ui.leer_prefs = lambda: {**real(), 'plantilla': pack, 'go_pack': pack}        # (el chip «Estilo» del usuario, 'go_pack', mandaría sobre 'plantilla')
    if os.environ.get('CINECAPTIONS_FX'):                                                  # prueba de los efectos visuales (página Efectos): se enciende solo en memoria
        _leer_antes = ajustes_ui.leer_prefs
        _extra = json.loads(os.environ.get('CINECAPTIONS_FX_OPC') or '{}')                  # p. ej. {"fx_zoom": "normal", "fx_cortes": "glitch"}: opciones sueltas solo en memoria
        ajustes_ui.leer_prefs = lambda: {**_leer_antes(), 'go_efectos_visuales': True, **_extra}
    ajustes_ui.guardar_prefs = lambda *a, **k: None                                       # NUNCA escribe las preferencias del usuario
    if os.environ.get('CINECAPTIONS_PRO') in ('0', '1'):                                   # la Edición PRO apagada/encendida solo en memoria (p. ej. el pase ligero de los Temas 1–4)
        import edicion_pro
        edicion_pro.activado = (lambda: True) if os.environ['CINECAPTIONS_PRO'] == '1' else (lambda: False)
    import qt_kit
    dialogos = []
    def _dialogo(tipo, titulo, texto, parent=None, botones=None):          # un diálogo modal colgaría la prueba sin ventana: se anota y se sigue
        dialogos.append((tipo, titulo, str(texto)[:300]))
        print(f'DIALOGO[{tipo}] {titulo}: {str(texto)[:300]!r}', flush=True)
        return True
    qt_kit.mostrar_mensaje = _dialogo
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    if pack != '-':
        w.plantilla_sel = pack
    w.show()
    faulthandler.dump_traceback_later(int(os.environ.get('DUMP_S', '400')), exit=True)       # si algo se cuelga, las pilas de todos los hilos
    if soltar:
        print(f'plantilla_sel de la app: {w.plantilla_sel!r} · página: {w._pagina_actual}', flush=True)
        w._soltar_archivo(media)                      # lo mismo que arrastrar el video a la ventana
        t_ini = time.time()
        while not getattr(w, '_go_corriendo', False) and time.time() - t_ini < 10:
            app.processEvents()
            time.sleep(0.05)
        print(f'pack GO: {w.plantilla_sel!r} · estilo guion: {bool(w._pack_guion())}', flush=True)
    else:
        print(f'pack GO: {w._plantilla_un_clic()} · estilo guion: {bool(w._pack_guion())}', flush=True)
        w._go_archivo = media
        w._go()
    t0 = time.time()
    while getattr(w, '_go_corriendo', False) and time.time() - t0 < float(os.environ.get('GO_MAX_S', '420')):     # el Tema 5 (IA + Remotion + Magic Mask) tarda más
        app.processEvents()
        time.sleep(0.05)
    for _ in range(40):
        app.processEvents()
        time.sleep(0.05)
    print('GO terminado en %.0f s · corriendo=%s' % (time.time() - t0, getattr(w, '_go_corriendo', None)), flush=True)
    try:                                              # lo que vería el usuario en Inicio
        gp = w.go_panel
        print('PANEL titulo=%r · linea=%r · aviso_inicio=%r · estado=%s · paso_fallido=%r · eta=%r' % (getattr(gp.titulo, '_texto', ''), getattr(gp.linea, 'text', lambda: '')(), getattr(w.aviso_inicio, 'text', lambda: '')(), gp.boton.estado, gp.paso_fallido, gp.boton._eta_texto()), flush=True)
        import registro
        for e in [e for e in registro.registro().lista() if e.nivel in ('error', 'aviso', 'advertencia', 'warning')][-5:]:
            print('REGISTRO %s · %s · %s' % (e.nivel, e.origen, str(e.mensaje)[:200]), flush=True)
            if getattr(e, 'detalle', ''):
                print('REGISTRO detalle · %s' % str(e.detalle).replace('\n', ' | ')[-400:], flush=True)
    except Exception as exc:
        print('(no pude leer el panel)', exc, flush=True)
    faulthandler.cancel_dump_traceback_later()
    os._exit(0 if not getattr(w, '_go_corriendo', False) else 2)


if __name__ == '__main__':
    main()
