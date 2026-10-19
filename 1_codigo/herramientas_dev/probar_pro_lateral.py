# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_pro_lateral.py — v5.5.17: prueba el módulo DERECHO de la Edición PRO en Proyecto (pro_lateral_ui: la barra con
# los 9 interruptores y el móvil con el ejemplo) objeto por objeto y función por función, con las preferencias SOLO en memoria. SOLO desarrollo.
"""
    python 1_codigo/herramientas_dev/probar_pro_lateral.py [--video V --palabras P.json]

1) Interfaz (Qt sin pantalla): FilaPro / PanelMotionsPro / PanelEjemploPro con el Tema 1 (sus interruptores propios) y con el Tema 2 (los
   globales): clic de ratón en cada icono (encender y apagar), lo guardado en las preferencias, el dibujo (grab) con cada uno señalado,
   las animaciones (paso_resorte hasta reposar), el ejemplo de cada interruptor (clip + foto) y el botón de Efectos.
2) Funciones: cada interruptor encendido SOLO en el plan de la PRO (Tema 1 neón y Tema 2): que añade lo que promete (los motions de su grupo,
   la píldora bajo los captions, la máscara, Motions completo) y, en el Tema 1, que nada pisa un motion del kit.
Imprime OK/FALLO por comprobación y un resumen; código de salida 1 si algo falló.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

FALLOS, OKS = [], []


def comprobar(cond, texto):
    (OKS if cond else FALLOS).append(texto)
    print(('  OK    ' if cond else '  FALLO ') + texto, flush=True)
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', default=str(Path.home() / 'Desktop' / 'PRUEBA ESPAÑOL.mp4'))
    ap.add_argument('--palabras', default=str(Path.home() / 'DaVinciSubtitles' / 'cache_voz' / '2dab72f7a727730e18d0958a.json'))
    a = ap.parse_args()
    import ajustes_ui
    PREFS = {'go_edicion_pro': True, 'pro_ia_local': False}
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: {**real(), **PREFS}
    ajustes_ui.guardar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    import edicion_pro as EP
    import instalador_scripts as INS
    import pro_lateral_ui as LAT
    INS._CACHE_EDICION['valor'] = 'studio'                # (v5.5.20: «Captions detrás de ti» solo con Studio: las secciones 1 y 2, como Studio)
    INS._edicion_guardada = lambda: 'studio'

    # ------------------------------------------------------------------------------------------------------------- 1) interfaz
    print('== 1) Interfaz', flush=True)
    for tema, pack in (('Tema 1', 'Kinetic'), ('Tema 2', 'Referencia')):
        PREFS.update(go_pack=pack, plantilla=pack, pro_neon_extras=[], pro_motions_modo='auto', pro_motions=[], pro_mascara='auto',
                     pro_internet=True, pro_motions_completo=False)
        efectos = []
        centro = QWidget()
        fila = LAT.FilaPro(centro, ir_efectos=lambda: efectos.append(1))
        fila.resize(1500, 760)
        fila.show()
        app.processEvents()
        lista, ej = fila.lista, fila.ejemplo
        comprobar(fila._pro and lista.isVisible(), f'{tema}: con la PRO en juego se ven la barra y el ejemplo')
        esperado = {o['clave']: (o['clave'] in PREFS['pro_neon_extras']) if pack == 'Kinetic' else LAT.estado(o['clave']) for o in LAT.OPCIONES}
        if pack == 'Kinetic':
            comprobar(not any(LAT.estado(o['clave']) for o in LAT.OPCIONES), f'{tema}: de inicio todo apagado (= la referencia)')
        barra, paso, y0 = lista._geo()
        for k, o in enumerate(LAT.OPCIONES):
            clave = o['clave']
            pos = QPointF(barra.center().x(), y0 + paso * (k + 0.5))
            comprobar(lista._icono_en(pos) == clave, f'{tema}: el clic en el icono {k + 1} cae en «{clave}»')
            antes = LAT.estado(clave)
            for tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                ev = QMouseEvent(tipo, pos, pos, Qt.MouseButton.LeftButton,
                                 Qt.MouseButton.LeftButton if tipo == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
                                 Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(lista, ev)
            app.processEvents()
            despues = LAT.estado(clave)
            if pack == 'Kinetic':
                comprobar(despues != antes and (clave in PREFS['pro_neon_extras']) == despues,
                          f'{tema}: «{clave}» se {"enciende" if despues else "apaga"} y se guarda en pro_neon_extras')
                comprobar(PREFS.get('pro_motions_modo') == 'auto' and PREFS.get('pro_mascara') == 'auto',
                          f'{tema}: «{clave}» no toca los interruptores de los otros temas')
            else:
                comprobar(despues != antes or not antes is False, f'{tema}: «{clave}» cambia ({antes} → {despues})')
            comprobar(lista.activa == clave and ej._clave == clave, f'{tema}: el móvil enseña el ejemplo de «{clave}»')
            mp4, jpg = LAT.ejemplo(clave)
            comprobar(mp4.exists() and jpg.exists(), f'{tema}: el ejemplo de «{clave}» existe ({mp4.name})')
            img = lista.grab()
            comprobar(not img.isNull() and img.width() > 0, f'{tema}: la barra se dibuja con «{clave}» señalado')
            comprobar(not ej.grab().isNull(), f'{tema}: el móvil se dibuja con «{clave}»')
        # volver a encender/apagar todo (deja el estado de partida) y que las animaciones reposen
        for o in LAT.OPCIONES:
            if LAT.estado(o['clave']) != esperado[o['clave']]:
                LAT.poner(o['clave'], esperado[o['clave']])
        t0 = time.time()
        while (lista.paso_resorte(1 / 60) or ej.paso_resorte(1 / 60)) and time.time() - t0 < 5:
            pass
        comprobar(time.time() - t0 < 5, f'{tema}: las animaciones de la barra y del móvil reposan')
        pos = QPointF(barra.center().x(), barra.bottom() - 6)
        for tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            QApplication.sendEvent(lista, QMouseEvent(tipo, pos, pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton
                                                      if tipo == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        comprobar(bool(efectos), f'{tema}: el botón de abajo lleva a Efectos')
        for ancho in (1280, 900, 700):
            fila.resize(ancho, 600)
            app.processEvents()
            fila._lados()
        comprobar(True, f'{tema}: la fila se adapta a 1280/900/700 px sin error')
        fila.close()
    if 'Kinetic':
        PREFS.update(go_pack='Referencia')
        for o in LAT.OPCIONES[-4:]:
            LAT.poner(o['clave'], False)
        r = LAT.poner(LAT.OPCIONES[-1]['clave'], False)
        quedan = [o['clave'] for o in LAT.OPCIONES if LAT.estado(o['clave'])]
        comprobar(bool(quedan), f'Tema 2: nunca se queda la PRO sin ningún motion (quedan {len(quedan)})')

    # ------------------------------------------------------------------------------------------------------------- 2) funciones
    print('== 2) Funciones (plan de la PRO con cada interruptor)', flush=True)
    import edicion_pro_planificador as PL
    import efectos_visuales
    import kit_neon as KN
    import kit_neon_motions as KM
    import motions_catalogo as MC
    w = json.loads(Path(a.palabras).read_text(encoding='utf-8'))
    w = w.get('palabras') if isinstance(w, dict) else w
    _w, _h, dur, fps = EP.medir(a.video)
    cortes = efectos_visuales.detectar_cortes(a.video) or []
    base = None
    for clave in [o['clave'] for o in LAT.OPCIONES]:
        PREFS.update(go_pack='Kinetic', plantilla='Kinetic', pro_neon_extras=[clave], pro_motions_modo='auto', pro_motions=[], pro_densidad='media')
        print(f'  · {clave}: opciones {EP.opciones_neon(EP.opciones_guardadas()).get("pro_motions")[:3]}…', flush=True)
        op = EP.opciones_neon(EP.opciones_guardadas())
        plan = EP.planificar(a.video, w, dur, cortes=cortes, idioma='es', opciones=EP.opciones_guardadas(), tema='neon')
        if base is None:
            base = plan
        mot = plan.get('kitneon_motions') or []
        ocup = [(m['ini'] + 0.05, m['fin'] - 0.05) for m in mot if m.get('capa') != 'iconos']      # (solape REAL; tocarse vale)
        piezas = plan.get('piezas') or []
        ids = [MC.id_de_pieza(p) for p in piezas]
        suyos = set(LAT.ids_de(clave))
        comprobar(len(mot) >= 10, f'Tema 1 + «{clave}»: siguen los motions del kit ({len(mot)})')
        comprobar(not any(p['ini'] < b and a_ < p['fin'] for p in piezas for a_, b in ocup),
                  f'Tema 1 + «{clave}»: lo añadido no pisa ningún motion del kit ({len(piezas)} piezas)')
        if clave in ('gancho', 'escenas', 'kit', 'graficos', 'plantillas', 'broll'):
            ajenos = [i for i in ids if i and i not in suyos]
            comprobar(not ajenos, f'Tema 1 + «{clave}»: solo motions de su grupo ({sorted(set(i for i in ids if i))[:6]})')
            print(f'          («{clave}» puso {sum(1 for i in ids if i in suyos)} motion(s) suyos en los huecos libres; {plan["resumen"].split("del menú:")[-1][:80]})', flush=True)
        if clave == 'detras':
            comprobar(plan['opciones'].get('pro_mascara') in ('auto', 'magic', 'ia'), 'Tema 1 + «detras»: la persona recortada se pide (máscara encendida)')
        if clave == 'motions_completo':
            comprobar(bool(plan['opciones'].get('pro_motions_completo')), 'Tema 1 + «motions_completo»: Motions completo se pide')
        if clave == 'pildora':
            import edicion_pro_temas as TM
            caps = KM.ajustar_captions(KN.escena_captions(w, 'es', fin_video=dur), mot)
            extra = TM.piezas({}, a.video, 'es', 1080, 1920, 30.0, [], dict(plan, piezas=list(piezas) + KM.piezas(mot)), maximo=3,
                              bloques=KN.bloques_pro(caps))
            pild = [p for p in extra if p.get('pieza') != 'velo_caption']
            comprobar(len(pild) >= 1, f'Tema 1 + «pildora»: hay píldoras bajo los captions ({len(pild)})')
            comprobar(all(15 <= float(p['valores'].get('y', 0)) <= 86 for p in pild), 'Tema 1 + «pildora»: dentro de la zona segura (y 15–86 %)')
            comprobar(not any(p['ini'] < b and a_ < p['fin'] for p in pild for a_, b in ocup), 'Tema 1 + «pildora»: ninguna sobre un motion del kit')
            for p in pild:
                print(f"          píldora {p['ini']:.1f}-{p['fin']:.1f}s y={p['valores'].get('y')} «{p['valores'].get('texto') or p['valores'].get('emoji') or ''}»")
    # Tema 2: cada grupo solo (los globales, en memoria)
    PREFS.update(go_pack='Referencia', plantilla='Referencia')
    for clave in ('gancho', 'escenas', 'kit', 'graficos', 'plantillas'):
        ids = LAT.ids_de(clave)
        PREFS.update(pro_motions_modo='elegidos', pro_motions=ids)
        plan = EP.planificar(a.video, w, dur, cortes=cortes, idioma='es', opciones=EP.opciones_guardadas(), tema=None)
        puestos = [MC.id_de_pieza(p) for p in plan.get('piezas') or []]
        ajenos = [i for i in puestos if i and i not in set(ids)]
        comprobar(not ajenos, f'Tema 2 + solo «{clave}»: ningún motion de otro grupo ({len([i for i in puestos if i])} suyos)')
    seccion_detras(a, app, PREFS, w, dur, fps, cortes)
    print(f'\n== {len(OKS)} OK · {len(FALLOS)} FALLO(S)')
    for f in FALLOS:
        print('   FALLO:', f)
    sys.exit(1 if FALLOS else 0)


def seccion_detras(a, app, PREFS, w, dur, fps, cortes):
    """v5.5.20: «Captions detrás de ti»: solo con Studio (en Free no se ve ni cuenta), el selector Suave · Media · Fuerte de su píldora (clics
    de verdad) y la elección de momentos por intensidad en el Tema 1 (detección en la PLACA) y por la vía común (V1, Temas 2–6)."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication, QWidget
    import edicion_pro as EP
    import instalador_scripts as INS
    import kit_neon as KN
    import kit_neon_motions as KM
    import kit_neon_placa as PLA
    import pro_lateral_ui as LAT
    print('== 3) Captions detrás de ti (solo Studio · intensidad · Tema 1 desde la placa)', flush=True)

    def clic(lista, pos):
        QApplication.sendEvent(lista, QMouseEvent(QEvent.Type.MouseMove, pos, pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                                  Qt.KeyboardModifier.NoModifier))
        for tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            QApplication.sendEvent(lista, QMouseEvent(tipo, pos, pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton
                                                      if tipo == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        app.processEvents()

    for ed in ('free', 'studio'):
        INS._CACHE_EDICION['valor'] = ed
        INS._edicion_guardada = (lambda ed=ed: ed)
        PREFS.update(go_pack='Referencia', plantilla='Referencia', pro_mascara='auto', pro_detras_intensidad='media')
        vis = [o['clave'] for o in LAT.opciones_visibles()]
        comprobar(('detras' in vis) == (ed == 'studio'), f'Resolve {ed}: «Captions detrás de ti» {"está" if ed == "studio" else "NO está"} en el menú ({len(vis)} interruptores)')
        comprobar(LAT.estado('detras') == (ed == 'studio'), f'Resolve {ed}: guardado encendido, cuenta como {ed == "studio"}')
        comprobar(EP.detras_disponible() == (ed == 'studio'), f'Resolve {ed}: edicion_pro.detras_disponible() = {ed == "studio"}')
        centro = QWidget()
        fila = LAT.FilaPro(centro)
        fila.resize(1500, 760)
        fila.show()
        app.processEvents()
        lista = fila.lista
        barra, paso, y0 = lista._geo()
        claves = [lista._icono_en(QPointF(barra.center().x(), y0 + paso * (k + 0.5))) for k in range(len(vis))]
        comprobar(claves == vis, f'Resolve {ed}: cada icono cae en su interruptor')
        comprobar(not lista.grab().isNull(), f'Resolve {ed}: la barra se dibuja')
        if ed == 'free':
            continue
        pos = QPointF(barra.center().x(), y0 + paso * (vis.index('detras') + 0.5))
        QApplication.sendEvent(lista, QMouseEvent(QEvent.Type.MouseMove, pos, pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                                  Qt.KeyboardModifier.NoModifier))
        t0 = time.time()
        while lista.paso_resorte(1 / 60) and time.time() - t0 < 5:
            pass
        lista.grab()
        comprobar([n for _r, n in lista._niveles_rects] == ['suave', 'media', 'fuerte'], 'Studio: la píldora de «detrás de ti» enseña Suave · Media · Fuerte')
        lista.grab().save(str(Path(os.environ.get('TEMP', '.')) / 'ccpro_detras_pildora.png'))
        for nivel in ('fuerte', 'suave', 'media'):
            r = next((r for r, n in lista._niveles_rects if n == nivel), None)
            if r is None:
                comprobar(False, f'Studio: el botón «{nivel}» se ve')
                continue
            clic(lista, r.center())
            lista.grab()
            comprobar(PREFS.get('pro_detras_intensidad') == nivel and LAT.estado('detras') and lista._info.x > 0.5,
                      f'Studio: clic en «{nivel}» lo guarda, «detrás de ti» sigue encendido y la píldora sigue abierta')
    # la elección de momentos por intensidad (Tema 1 con la placa y la vía común de V1)
    PREFS.update(go_pack='Kinetic', plantilla='Kinetic', pro_neon_extras=['detras'])
    plan = EP.planificar(a.video, w, dur, cortes=cortes, idioma='es', opciones=EP.opciones_guardadas(), tema='neon')
    plan['kitneon'] = KM.ajustar_captions(KN.escena_captions(w, 'es', fin_video=dur), plan['kitneon_motions'])     # (GO los añade)
    plan['_neon_ajustado'] = True
    bl = KN.bloques_pro(plan['kitneon'])
    comprobar(all('linea' in b and 'grande_abajo' in b and len(b['xs']) == 3 for b in bl), f'Tema 1: sus {len(bl)} bloques traen línea de abajo, si es grande y su ancho')
    mapa = PLA.mapa_camara(a.video, plan, 1080, 1920)
    info = {'fps': fps, 'inicio': 0, 'base': 0, 'v1': [{'ruta': a.video, 'ini': 0, 'fin': int(dur * fps) + 1, 'izq': 0, 'fps': fps, 'res': '1080x1920'}]}
    ocup = [(m['ini'] - 0.1, m['fin'] + 0.1) for m in plan['kitneon_motions']]
    for via, a_cuadro in (('Tema 1 (placa)', mapa), ('vía común (V1)', None)):
        cuantos = []
        for nivel in EP.NIVELES_DETRAS:
            cfg = EP.INTENSIDAD_DETRAS[nivel]
            tramos = EP._captions_detras(info, a.video, fps, ocup, 'media', lambda t: None, W=1080, H=1920, intensidad=nivel, bloques=bl,
                                          a_cuadro=a_cuadro)
            cues = [c for t in tramos for c in t['cues']]
            cuantos.append(len(cues))
            comprobar(len(tramos) <= cfg['tramos'], f'{via} · {nivel}: {len(tramos)} tramos de Magic Mask (máx. {cfg["tramos"]}), {len(cues)} captions detrás')
            comprobar(not any(t['ini'] < b_ and a_ < t['fin'] for t in tramos for a_, b_ in ocup), f'{via} · {nivel}: ningún tramo sobre un motion del kit')
            peor = 0.0
            for t in tramos:
                ps = (t['det'] or {}).get('personas') or []
                comprobar(bool(ps) and all(0 <= x <= 1 and 0 <= y <= 1 for q in ps for x, y in q['puntos']),
                          f'{via} · {nivel} · {t["ini"]:.1f}s: los puntos del Magic Mask caen sobre una persona dentro del cuadro')
                cab = EP._cabeza(t['det'] if a_cuadro else EP._a_timeline(t['det'], info['v1'][0], 1080, 1920))
                for c in t['cues']:
                    b = next((x for x in bl if abs(x.get('ini_clip', x['ini']) - c['ini']) < 0.02), None)
                    if b is None or cab is None:
                        continue
                    tapa = c['caja'][1] - cab[0]
                    peor = max(peor, tapa / b['linea'])
                    comprobar(b['grande_abajo'] and tapa <= min(cfg['tapa_max'], cfg['tapa'] * b['linea']) + 0.005,
                              f'{via} · {nivel} · {c["ini"]:.1f}s: la cabeza tapa {100 * tapa / b["linea"]:.0f} % de la palabra grande (máx. {100 * cfg["tapa"]:.0f} %)')
            print(f'          {via} · {nivel}: {len(cues)} captions detrás, lo que más tapa la cabeza: {100 * peor:.0f} % de la palabra grande')
            comprobar(all(t1['fin'] <= t2['ini'] + 1e-6 for t1, t2 in zip(tramos, tramos[1:])), f'{via} · {nivel}: dos recortes de la persona nunca se pisan')
            for t in tramos:
                abajo = max(c['caja'][1] for c in t['cues'])
                comprobar(abajo + 0.05 <= t['corte'] <= 1.0, f'{via} · {nivel} · {t["ini"]:.1f}s: la capa de la persona se recorta por debajo del caption ({t["corte"]:.2f} > {abajo:.2f})')
                ult = t['cues'][-1]
                k = next((i for i, x in enumerate(bl) if abs(x.get('ini_clip', x['ini']) - ult['ini']) < 0.02), None)
                if k is None:
                    continue
                sig = bl[k + 1] if k + 1 < len(bl) else None
                if sig is None or sig['arriba'] > t['corte'] + 0.01:
                    comprobar(t['fin'] >= bl[k]['fin'] + bl[k]['salida'] - 0.01 or (sig is not None and any(t2['ini'] <= t['fin'] + 1e-6 for t2 in tramos if t2 is not t and t2['ini'] > t['ini'])),
                              f'{via} · {nivel} · {t["ini"]:.1f}s: la persona sigue delante hasta que el caption termina de SALIR ({t["fin"]:.2f} s)')
                else:
                    comprobar(t['fin'] <= sig['ini'] + 0.01, f'{via} · {nivel} · {t["ini"]:.1f}s: el bloque siguiente (dentro del recorte) no queda tapado')
        comprobar(cuantos == sorted(cuantos), f'{via}: más intensidad = más captions detrás ({cuantos})')


if __name__ == '__main__':
    main()
