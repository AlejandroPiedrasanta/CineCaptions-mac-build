"""v5.32 (el usuario: «aplica ese diseño»): la vista «Posición» de «Captions detrás de ti» con el diseño nuevo, SIN pantalla y sin tocar lo del
usuario (preferencias y marcas se parchean en memoria): cabecera, visor, panel (Ajustes · Marcas · Sugerencias) y tira; reproducir unos
segundos; la posición del caption (vertical = solo «Arriba»; horizontal = Arriba / Izquierda / Derecha). Deja capturas para mirarlas.

    python probar_detras_vista.py <carpeta_salida> <video> [<video> …]
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('CINECAPTIONS_SIN_MCP', '1')
OKS, FALLOS = [], []


def comprobar(cond, texto):
    (OKS if cond else FALLOS).append(texto)
    print(('  OK    ' if cond else '  FALLO ') + texto, flush=True)
    return cond


def esperar(app, cond, max_s):
    t0 = time.time()
    while time.time() - t0 < max_s:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.03)
    return cond()


def main():
    salida = Path(sys.argv[1])
    salida.mkdir(parents=True, exist_ok=True)
    videos = [Path(v) for v in sys.argv[2:]]
    import ajustes_ui
    PREFS = {'go_edicion_pro': True}
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: {**real(), **PREFS}
    ajustes_ui.guardar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    import qt_kit as ui
    app = ui.crear_app(['vista'], carpeta_fuentes=Path(__file__).resolve().parents[2] / '2_recursos' / 'fonts')
    import instalador_scripts as INS
    INS._CACHE_EDICION['valor'] = 'studio'
    INS._edicion_guardada = lambda: 'studio'
    import posiciones_pro as POS
    POS.guardar_linea = lambda *a, **k: None                          # (las marcas del usuario no se tocan)
    prestado = os.environ.get('CC_CAPTIONS_DE')                        # (un video de prueba sin transcribir: las palabras y captions de otro)
    if prestado:
        pal_real, cap_real = POS.palabras, POS.captions_del_video

        def palabras(ruta):
            return pal_real(ruta) or pal_real(prestado)

        def captions(ruta, imagen=None):
            c = cap_real(ruta, imagen)
            if c:
                return c
            c = dict(cap_real(prestado) or {})
            c.update(bloques=None, plan_placa=None)                     # (los cues del tema, sin la placa del Tema 1 del otro video)
            return c
        POS.palabras, POS.captions_del_video = palabras, captions
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    for video in videos:
        print(f'== {video.name}', flush=True)
        PREFS['pro_detras_posicion'] = 'arriba'
        marco = QWidget()
        marco.setObjectName('marco')
        marco.setStyleSheet(f'QWidget#marco {{ background: {ui.BG_COLOR}; }}')
        marco.resize(1560, 1000)
        capa = QVBoxLayout(marco)
        capa.setContentsMargins(24, 20, 24, 20)
        vista = POS.VistaPosiciones('detras')
        capa.addWidget(vista)
        marco.show()
        vista.abrir(str(video))
        vista.poner_resumen('Sin efecto · 5 posiciones')                # (lo pone la sección de Efectos)
        ln = vista.linea
        comprobar(ln.compacta and getattr(vista, '_nuevo', None) is not None, 'la vista de «detrás de ti» usa el diseño nuevo')
        listo = esperar(app, lambda: ln.dur > 0 and ln.fotos and ln.zonas is not None and ln.captions_listos and not ln.analizando(), 300)
        comprobar(listo, f'carga el video, la detección y los captions ({ln.dur:.1f} s, {len(ln.fotos)} fotogramas)')
        if not ln.marcas and ln.sugeridas:
            vista._poner_todas()
        esperar(app, lambda: isinstance(ln._reglas, dict) and all(ln.estado_go(t) is not None for t in ln.marcas), 240)
        t = ln.marcas[-1] if ln.marcas else (ln.sugeridas[0][0] if ln.sugeridas else ln.dur / 2)
        ln.poner_cabezal(t)
        esperar(app, lambda: ln._vista_de(t) is not None, 120)
        app.processEvents()
        nombre = video.stem.replace(' ', '_')
        marco.grab().save(str(salida / f'{nombre}_ajustes.png'))
        nuevo = vista._nuevo
        horizontal = ln.horizontal()
        visibles = [k for k, m in nuevo.panel.mosaicos.items() if not m.isHidden()]
        comprobar(visibles == (['arriba', 'izquierda', 'derecha'] if horizontal else ['arriba']),
                  f'posición del caption: {"horizontal" if horizontal else "vertical"} → {", ".join(visibles)}')
        comprobar(nuevo.cab.pildora._t != '', f'cabecera: «{nuevo.cab.pildora._t}»')
        d = ln.deteccion()
        comprobar(d is not None and nuevo.panel.estado._d[0] in ('bien', 'regular', 'mal'),
                  f'estado del tracking: {nuevo.panel.estado._d[1]} ({int(round(100 * d[0])) if d else "?"} %)')
        nuevo.panel.p_marcas.click()
        app.processEvents()
        nuevo._hacer()
        app.processEvents()
        filas = nuevo.panel.capa_marcas.count()
        comprobar(filas >= len(ln.marcas) + 1, f'pestaña Marcas: {len(ln.marcas)} marcas en la lista')
        marco.grab().save(str(salida / f'{nombre}_marcas.png'))
        nuevo.panel.p_sug.click()
        app.processEvents()
        marco.grab().save(str(salida / f'{nombre}_sugerencias.png'))
        nuevo.panel.p_ajustes.click()
        # ---- reproducir 2 s
        ln.poner_cabezal(max(0.0, min(ln.dur - 3.0, 5.0)))
        nuevo.visor._mudo = True                                          # (sin sonido en la prueba)
        nuevo.visor.reproducir()
        t0 = ln.cabezal
        esperar(app, lambda: nuevo.visor.rep.img is not None and ln.cabezal > t0 + 1.5, 20)
        comprobar(nuevo.visor.rep.img is not None and ln.cabezal > t0 + 1.0, f'reproduce: el cabezal pasó de {t0:.1f} a {ln.cabezal:.1f} s')
        marco.grab().save(str(salida / f'{nombre}_reproduciendo.png'))
        nuevo.visor.parar()
        comprobar(not nuevo.visor.reproduciendo(), 'pausa')
        if horizontal:                                                    # ---- otra posición: la regla y la vista se rehacen
            for lado in ('izquierda', 'derecha'):
                nuevo.panel._elegir_posicion(lado)
                comprobar(ln.posicion() == lado and PREFS.get('pro_detras_posicion') == lado, f'posición «{lado}» guardada')
                esperar(app, lambda: isinstance(ln._reglas, dict) and ln._reglas.get('posicion') == lado, 120)
                comprobar(isinstance(ln._reglas, dict) and ln._reglas.get('posicion') == lado, f'la regla de GO usa «{lado}»')
                tt = ln.marcas[0] if ln.marcas else (ln.sugeridas[0][0] if ln.sugeridas else ln.dur / 2)
                ln.poner_cabezal(tt)
                esperar(app, lambda: ln._vista_de(tt) is not None, 120)
                info = (ln._vista_de(tt) or (None, {}))[1] or {}
                print(f'     vista en {tt:.1f} s: detrás={info.get("detras")} motivo={info.get("motivo")} posición={info.get("posicion")}')
                app.processEvents()
                marco.grab().save(str(salida / f'{nombre}_{lado}.png'))
        marco.close()
        marco.deleteLater()
        app.processEvents()
    print(f'\n{len(OKS)} OK · {len(FALLOS)} FALLO')
    return 1 if FALLOS else 0


if __name__ == '__main__':
    sys.exit(main())
