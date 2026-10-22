# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_detras_posiciones.py — v5.27: prueba «Captions detrás de ti» con Efectos › «Posición» sobre videos REALES de
# personas: solo humanos, dónde queda bien, los topes de las marcas, «Listo» y lo que hace GO con ellas. SOLO desarrollo.
"""
    python 1_codigo/herramientas_dev/probar_detras_posiciones.py [video …]

Por defecto los tres videos de personas de Desktop/PARA PRUEBAS (TEMA6USAR: podcast con micrófono; CLIENTE: inmobiliaria con tomas de casas;
PRUEBAS (1): de pie en una cocina). Preferencias SOLO en memoria; posiciones_pro.json, su caché y el Registro, en una carpeta temporal.
1) Solo humanos: en las tomas sin nadie no hay persona; en las de personas, los puntos del Magic Mask caen DENTRO de la silueta y arriba
   (cara y hombros: nunca el micrófono, la mesa ni las manos).
2) Zonas (lo que pinta la tira) y GO: con una marca en medio de cada zona («solo mis marcas», Tema 1 con la placa y la vía común de V1), GO
   pone detrás un caption a ±RADIO_MARCA_DETRAS_S de la marca; las marcas reales del usuario en CLIENTE (0,1 y 2,1 s) también.
3) El audio de un timeline (GO pulsado sin volver a soltar el video): las marcas hechas sobre el video valen, pasadas a su tiempo.
4) Interfaz (Qt sin pantalla): clic fuera del verde → al verde, dos en el mismo caption, arrastrar con tope, el máximo de marcas, un video sin
   ningún sitio bueno, «Listo» (guardado + encendido en GO + video en Inicio) y la píldora de Proyecto («N posiciones tuyas»).
Imprime OK/FALLO por comprobación; código de salida 1 si algo falló. Deja capturas de la tira en la carpeta temporal.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

FALLOS, OKS = [], []
PRUEBAS = Path.home() / 'Desktop' / 'PARA PRUEBAS'
# lo que se ve en cada video (comprobado a ojo en sus hojas de fotogramas): segundos con alguien y sin nadie
CON_PERSONA = {'CLIENTE.mp4': [0.2, 1.2, 2.2, 6.2, 7.2, 8.2, 14.2, 16.2, 23.2, 27.2], 'PRUEBAS (1).mp4': [2.2, 7.7, 12.2, 20.2],
               'TEMA6USAR.mp4': [3.2, 21.2, 40.2, 61.7]}
SIN_PERSONA = {'CLIENTE.mp4': [3.2, 4.2, 5.2, 9.2, 11.2, 12.2, 13.2, 19.2, 24.2, 25.2, 28.2, 29.2]}


def comprobar(cond, texto):
    (OKS if cond else FALLOS).append(texto)
    print(('  OK    ' if cond else '  FALLO ') + texto, flush=True)
    return cond


def palabras_de(video):
    """Las palabras de ese video de la caché de la voz (las de su último GO), o None."""
    import cache_voz
    for f in sorted(cache_voz.CARPETA.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if d.get('video') == Path(video).name and d.get('palabras'):
            return d['palabras']
    return None


def main():
    videos = [Path(v) for v in sys.argv[1:]] or [PRUEBAS / n for n in ('CLIENTE.mp4', 'PRUEBAS (1).mp4', 'TEMA6USAR.mp4', 'PRUEBAS (8).mp4')]
    videos = [v for v in videos if v.is_file()]
    if not videos:
        print('No encuentro los videos de prueba.')
        return 1
    tmp = Path(tempfile.mkdtemp(prefix='ccdetras_'))
    print('Carpeta temporal:', tmp, flush=True)
    import ajustes_ui
    PREFS = {'go_edicion_pro': True, 'pro_ia_local': False, 'go_pack': 'Kinetic', 'plantilla': 'Kinetic', 'pro_neon_extras': ['detras'],
             'pro_mascara': 'auto', 'pro_detras_intensidad': 'media'}
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: {**real(), **PREFS}
    ajustes_ui.guardar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    import registro
    REG = []
    for n in ('info', 'aviso', 'ok'):
        if hasattr(registro, n):
            setattr(registro, n, lambda texto, *a, _n=n, **k: REG.append((_n, str(texto))))
    registro.excepcion = lambda *a, **k: REG.append(('excepcion', repr(k)))
    import instalador_scripts as INS
    INS._CACHE_EDICION['valor'] = 'studio'
    INS._edicion_guardada = lambda: 'studio'
    import edicion_pro as EP
    import edicion_pro_persona as PE
    import efectos_visuales
    import kit_neon as KN
    import kit_neon_motions as KM
    import kit_neon_placa as PLA
    import posiciones_pro as POS
    POS.ARCHIVO = tmp / 'posiciones_pro.json'
    POS.CACHE = tmp / 'cache_posiciones'
    EP.PLAN_JSON = tmp / 'edicion_pro_plan.json'                      # (v5.29: «Listo» de «detrás de ti» va al timeline: nunca el contexto ni el
    EP.DETRAS_CTX = tmp / 'detras_contexto.json'                      # plan reales, y sin un GO de mentira no llega a hablar con Resolve)

    # ------------------------------------------------------------------------------------------------------- 1) solo humanos
    print('== 1) Solo humanos (IA local + puntos del Magic Mask)', flush=True)
    for v in videos:
        for t in SIN_PERSONA.get(v.name, []):
            det = PE.personas(v, t)
            comprobar(det is not None and not det['personas'], f'{v.name} {t:.1f} s (sin nadie): ninguna persona')
        for t in CON_PERSONA.get(v.name, []):
            img = PE.fotograma(v, t)
            det = PE.personas_de_imagen(img)
            ps = det['personas']
            if not comprobar(len(ps) >= 1, f'{v.name} {t:.1f} s: la persona se ve'):
                continue
            a = PE.mate(img)
            h, w = a.shape
            for q in ps:
                x0, y0, x1, y1 = q['bbox']
                dentro = all(a[min(h - 1, int(y * h)), min(w - 1, int(x * w))] > 0.5 for x, y in q['puntos'])
                arriba = all(y <= y0 + 0.45 * (y1 - y0) for _x, y in q['puntos'])
                lejos_borde = all(0.03 <= x <= 0.97 for x, _y in q['puntos'])
                comprobar(len(q['puntos']) >= 2 and dentro and arriba and lejos_borde,
                          f'{v.name} {t:.1f} s: {len(q["puntos"])} puntos en la silueta, en cara/hombros, lejos del borde')

    # ------------------------------------------------------------------------------------------------------- 2) zonas y GO
    print('== 2) Dónde queda bien (la tira) y lo que hace GO con esas marcas', flush=True)
    analisis = {}
    for v in videos:
        t0 = time.time()
        an = POS.analizar_detras(str(v))
        pals = POS.palabras(str(v))
        zonas, motivo = POS.zonas_detras(an, pals)
        analisis[v.name] = (an, pals, zonas, motivo)
        total = sum(b - a for a, b in zonas)
        print(f'     {v.name}: {time.time() - t0:.1f} s · {len(an["muestras"])} miradas · zonas {zonas}', flush=True)
        if v.name == 'CLIENTE.mp4':
            comprobar(any(a <= 0.1 <= b for a, b in zonas) and any(a <= 2.1 <= b for a, b in zonas),
                      'CLIENTE: sus marcas 0,1 y 2,1 s caen en verde (ella habla a cámara)')
            comprobar(not any(a < 3.9 < b for a, b in zonas) and motivo(4.5) == 'sin_persona', 'CLIENTE: la casa de 3,9–5,4 s no es verde (no hay nadie)')
            comprobar(motivo(20.0) in ('sin_persona', 'sin_captions'), f'CLIENTE 20 s: no es verde ({motivo(20.0)})')
        if v.name == 'PRUEBAS (1).mp4':
            comprobar(total >= 18.0, f'PRUEBAS (1): de pie y quieto casi todo el video: {total:.1f} s en verde')
        if v.name == 'TEMA6USAR.mp4':
            comprobar(bool(zonas), 'TEMA6USAR: con la cabeza al 16 % del alto hay verde (v5.31: GO pone ahí los captions bajos; cada '
                      'sugerencia y cada marca la comprueba la regla de GO)')
        t1 = time.time()
        POS.analizar_detras(str(v))
        comprobar(time.time() - t1 < 0.5, f'{v.name}: la segunda vez sale de la caché ({time.time() - t1:.2f} s)')
        # GO con el Tema 1 (la placa) y con la vía común de V1
        w = palabras_de(v)
        if not w:
            print(f'     {v.name}: sin transcribir (pasa GO una vez): no pruebo GO con él')
            continue
        _w, _h, dur, fps = EP.medir(str(v))
        cortes = efectos_visuales.detectar_cortes(str(v)) or []
        idioma = POS._idioma_de(w)
        plan = EP.planificar(str(v), w, dur, cortes=cortes, idioma=idioma, opciones=EP.opciones_guardadas(), tema='neon')
        plan['kitneon'] = KM.ajustar_captions(KN.escena_captions(w, idioma, fin_video=dur), plan['kitneon_motions'])
        bl = KN.bloques_pro(plan['kitneon'])
        orig_assets = EP._assets_emoji                                # (sin bajar nada de internet: solo que lea las palabras sin fallar)
        EP._assets_emoji = lambda c, var: None
        try:
            EP._emojis_pro(bl, [], {}, {}, 1080, 1920, EP.opciones_guardadas(), None)
            comprobar(True, f'{v.name}: «Emojis animados» lee los captions del Tema 1 (3 datos por palabra) sin «too many values to unpack»')
        except Exception as e:
            comprobar(False, f'{v.name}: «Emojis animados» con los captions del Tema 1: {e!r}')
        finally:
            EP._assets_emoji = orig_assets
        mapa = PLA.mapa_camara(str(v), plan, 1080, 1920)
        info = {'fps': fps, 'inicio': 0, 'base': 0, 'v1': [{'ruta': str(v), 'ini': 0, 'fin': int(dur * fps) + 1, 'izq': 0, 'fps': fps,
                                                            'res': f'{_w}x{_h}'}]}
        ocup = [(m['ini'] - 0.1, m['fin'] + 0.1) for m in plan['kitneon_motions'] if m.get('capa') != 'iconos']
        zonas_c, _mc = POS.zonas_detras(an, pals, [{'start': x['ini'], 'end': x['fin']} for x in bl])     # (el verde de la tira con los captions del Tema 1: solo donde HAY caption)
        marcas = []
        for a, b in zonas_c:
            t = a + 0.5
            while t < b and len(marcas) < POS.TOPE_MARCAS['detras']:
                if all(abs(t - x) >= 3.0 for x in marcas):
                    marcas.append(round(t, 1))
                t += 3.0
        # (v5.28) lo que la tira SUGIERE con los captions del tema (los mismos que ve el usuario): GO pone detrás TODAS
        cap = POS.captions_del_video(str(v))
        sugeridas = []
        if cap:
            zonas_ui, _m2 = POS.zonas_detras(an, pals, POS.bloques_de(cap))
            sugeridas = [t for t, _x in POS.sugerir(zonas_ui, an, POS.bloques_de(cap), exigir_grande=cap['pack'] == 'Kinetic')]
        for nombre, lista, minimo in (('marcas en verde (cada 3 s)', marcas, 0.5), ('sugeridas', sugeridas, 1.0)):
            for via, ac in (('Tema 1 (placa)', mapa), ('vía común (V1)', None)):
                if not lista:
                    break
                REG.clear()
                tramos = EP._captions_detras(info, str(v), fps, ocup, 'media', lambda t: None, W=1080, H=1920, intensidad='media', bloques=bl,
                                              a_cuadro=ac, marcas={'modo': 'solo', 'ts': lista}, cortes=cortes)
                cues = [c for tr_ in tramos for c in tr_['cues']]
                puestas = [t for t in lista if any(c['ini'] - EP.RADIO_MARCA_DETRAS_S <= t <= c['fin'] + EP.RADIO_MARCA_DETRAS_S for c in cues)]
                avisos = [x for _n, x in REG if 'Posiciones de Efectos' in x]
                comprobar(len(puestas) >= minimo * len(lista),
                          f'{v.name} · {via}: {len(puestas)} de {len(lista)} {nombre} salen detrás' + (f' · Registro: {avisos[0][:160]}' if avisos else ''))
                comprobar(all(tr_.get('forzado') for tr_ in tramos), f'{v.name} · {via}: con «solo mis marcas» no hay más que las marcadas')
        if v.name == 'CLIENTE.mp4':
            for via, ac in (('Tema 1 (placa)', mapa), ('vía común (V1)', None)):
                tramos = EP._captions_detras(info, str(v), fps, ocup, 'media', lambda t: None, W=1080, H=1920, intensidad='media', bloques=bl,
                                              a_cuadro=ac, marcas={'modo': 'suma', 'ts': [0.1, 2.1]}, cortes=cortes)
                comprobar(any(tr_['ini'] <= 0.6 and tr_.get('forzado') for tr_ in tramos),
                          f'CLIENTE · {via}: las marcas del usuario (0,1 y 2,1 s, «+ automático») ya salen detrás ({[(round(x["ini"], 1), round(x["fin"], 1)) for x in tramos]})')

    # ------------------------------------------------------------------------------------------------------- 3) el audio de un timeline
    print('== 3) GO con el audio del timeline: valen las marcas del video', flush=True)
    import resolve_bridge
    cliente = next((v for v in videos if v.name == 'CLIENTE.mp4'), videos[0])
    wav = tmp / 'Timeline 1_audio.wav'
    resolve_bridge.video_detectado = lambda: {'video_path': str(wav), 'clip_principal': str(cliente), 'clip_principal_desde': 1.5}
    POS.guardar(str(cliente), 'detras', [0.1, 2.1, 20.0], 'suma')
    m = POS.leer_linea(str(wav)).get('detras') or {}
    comprobar(m.get('ts') == [0.6, 18.5] and m.get('modo') == 'suma', f'leer_linea(.wav): las del video pasadas al audio (−1,5 s): {m}')
    plan_m = POS.para_plan(str(wav))
    comprobar((plan_m.get('detras') or {}).get('ts') == [0.6, 18.5], f'para_plan(.wav) (lo que usa GO) las trae: {plan_m.get("detras")}')
    POS.guardar_linea(str(wav), 'detras', [1.0], 'solo', imagen=(str(cliente), 1.5, 10.0))
    comprobar(POS.leer(str(cliente))['detras']['ts'] == [0.1, 2.5, 20.0], f'guardar_linea(.wav): va al video (+1,5 s) sin tocar lo de fuera: '
                                                                             f'{POS.leer(str(cliente))["detras"]["ts"]}')
    POS.guardar(str(wav), 'pildora', [3.0], 'solo')
    comprobar((POS.leer_linea(str(wav)).get('pildora') or {}).get('ts') == [3.0], 'las de antes, guardadas con la ruta del .wav, también valen')
    POS.ARCHIVO.unlink()

    # ------------------------------------------------------------------------------------------------------- 4) interfaz
    print('== 4) Interfaz (sin pantalla)', flush=True)
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication, QWidget
    import qt_kit
    app = qt_kit.crear_app()                                          # (con su despachador: los hilos de la tira devuelven su resultado)
    import estilos_pro as EST
    import efectos_pro_ui as EPU
    import pro_lateral_ui as LAT
    resolve_bridge.video_detectado = lambda: {}
    INICIO = [str(cliente)]
    POS.poner_proveedor(lambda: INICIO[0], poner=lambda r: INICIO.__setitem__(0, r))
    PREFS['pro_neon_extras'] = []                                     # («detrás de ti» apagado: «Listo» lo enciende)
    s = next(x for x in EST.SECCIONES if x['clave'] == 'detras')
    sec = EPU.SeccionEstilo(s, LAT._POR_CLAVE['detras'])
    sec.resize(1400, 760)
    sec.show()
    app.processEvents()

    def esperar(cond, tope=180):
        t0 = time.time()
        while not cond() and time.time() - t0 < tope:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        return cond()

    def boton(lin, t, tipo, boton_=Qt.MouseButton.LeftButton, x=None):
        r = lin._tira()
        pos = QPointF(lin._x(t) if x is None else x, r.center().y())
        botones = boton_ if tipo != QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
        QApplication.sendEvent(lin, QMouseEvent(tipo, pos, pos, boton_, botones, Qt.KeyboardModifier.NoModifier))
        app.processEvents()

    def clic(lin, t):
        boton(lin, t, QEvent.Type.MouseButtonPress)
        boton(lin, t, QEvent.Type.MouseButtonRelease)

    sec.mostrar_posiciones(True)
    vista = sec._pos
    lin = vista.linea
    listo = esperar(lambda: lin.dur > 0 and lin.zonas is not None and lin.captions_listos)
    comprobar(listo, f'CLIENTE: la tira carga y sabe dónde queda bien (zonas {lin.zonas})')
    if listo:
        lin.grab().save(str(tmp / 'tira_CLIENTE.png'))
        clic(lin, 20.0)
        comprobar(len(lin.marcas) == 1 and any(a <= lin.marcas[0] <= b for a, b in lin.zonas) and lin.nota,
                  f'clic en 20 s (casa, sin voz) → la marca va al verde: {lin.marcas} · «{lin.nota}»')
        comprobar(LAT.estado('detras'), 'la primera marca ya enciende «detrás de ti» en GO (sin tener que darle a «Activado en GO»)')
        clic(lin, 0.5)
        comprobar(len(lin.marcas) == 2, f'clic en 0,5 s (verde) → se queda ahí: {lin.marcas}')
        clic(lin, 1.0)
        comprobar(len(lin.marcas) == 2 and 'Ya hay una marca' in lin.nota, f'clic a 0,5 s de otra → no se duplica: «{lin.nota}»')
        t_ini = min(lin.marcas)
        boton(lin, t_ini, QEvent.Type.MouseButtonPress)
        r = lin._tira()
        pos = QPointF(lin._x(15.0), r.center().y())
        QApplication.sendEvent(lin, QMouseEvent(QEvent.Type.MouseMove, pos, pos, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                                Qt.KeyboardModifier.NoModifier))
        app.processEvents()
        comprobar(any(a <= lin.marcas[lin._arr] <= b for a, b in lin.zonas), f'arrastrarla a 15 s → se para en el borde del verde ({lin.marcas[lin._arr]:.1f} s)')
        boton(lin, 15.0, QEvent.Type.MouseButtonRelease)
        guardadas = (POS.leer(str(cliente)).get('detras') or {}).get('ts')
        comprobar(guardadas == sorted(lin.marcas) or len(guardadas or []) == len(lin.marcas), f'cada cambio se guarda: {guardadas}')
        lin.grab().save(str(tmp / 'tira_CLIENTE_marcas.png'))
        REG.clear()
        vista._listo()
        comprobar(LAT.estado('detras'), '«Listo» con marcas → «detrás de ti» sigue ENCENDIDO en GO')
        comprobar(not getattr(sec, '_en_pos', False), '«Listo» cierra la tira')
        comprobar(any(('posición guardada' in x or 'posiciones guardadas' in x) and ('GO la' in x or 'ya en tu timeline' in x) for _n, x in REG),
                  f'«Listo» lo dice en el Registro: {REG[-1:]}')
        plan_m = POS.para_plan(str(cliente))
        comprobar(len((plan_m.get('detras') or {}).get('ts') or []) == len(lin.marcas), f'GO (para_plan) las tiene: {plan_m}')
        n, _m = POS.resumen(str(cliente), 'detras')
        comprobar(n == len(lin.marcas), f'el resumen de la sección (su cabecera) cuenta {n}')
    # v5.27: sugerencias a un clic y la vista con los captions del tema de Inicio (el video de Inicio)
    import plantillas
    sug_v = next((v for v in videos if v.name == 'PRUEBAS (8).mp4'), None) or next((v for v in videos if v.name == 'PRUEBAS (1).mp4'), None)
    if sug_v is not None:
        INICIO[0] = str(sug_v)
        vista._a_mano = False
        PREFS['pro_neon_extras'] = []                                 # (apagado: la sugerencia lo enciende)
        sec.mostrar_posiciones(True)
        vista.abrir(str(sug_v))
        listo = esperar(lambda: lin.ruta == str(sug_v) and lin.zonas is not None and lin.captions_listos and lin.captions is not None and lin.sugeridas)
        comprobar(listo and 1 <= len(lin.sugeridas) <= POS.N_SUGERIDAS, f'{sug_v.name}: {len(lin.sugeridas)} sitios sugeridos {lin.sugeridas}')
        if listo:
            botones = sum(1 for i in range(vista._capa_sug.count()) if vista._capa_sug.itemAt(i).widget() is not None) - 1
            comprobar(not vista._fila_sug.isHidden() and botones == len(lin.sugeridas) + (1 if len(lin.sugeridas) > 1 else 0),
                      f'la fila «Sugeridas:» enseña un botón por sitio (+ «Poner las {len(lin.sugeridas)}»)')
            comprobar(lin.captions['nombre'] == plantillas.nombre_visible(POS.tema_de_inicio()),
                      f'la vista usa el tema de Inicio: {lin.captions["nombre"]} ({"los captions que GO puso" if lin.captions["de_go"] else "planificados"})')
            claves = [round(t, 1) for t, _x in lin.sugeridas]
            esperar(lambda: all(k in lin._vistas for k in claves), 120)
            infos = [lin._vistas.get(k, (None, {}))[1] for k in claves]
            comprobar(all(i.get('detras') for i in infos), f'en la vista, cada sugerida queda DETRÁS de la persona: {[i.get("motivo") for i in infos]}')
            lin._t_sobre = lin.sugeridas[0][0]
            lin.grab().save(str(tmp / f'vista_{sug_v.stem}_sugerida.png'))
            lin._t_sobre = None
            t0 = lin.sugeridas[0][0]
            vista._poner(t0)
            comprobar(t0 in lin.marcas and LAT.estado('detras'), f'clic en «+ {POS.texto_t(t0)}» → queda puesta y «detrás de ti» se enciende en GO')
            comprobar(all(abs(t - t0) >= POS.SEPARACION_MIN for t, _x in lin.sugeridas), 'y deja de sugerirse')
            if lin.sugeridas:
                t1 = lin.sugeridas[0][0]
                clic(lin, t1)
                comprobar(t1 in lin.marcas, f'clic en su anillo «+» de la tira → puesta en {POS.texto_t(t1)}')
            antes = len(lin.marcas)
            vista._poner_todas()
            comprobar(len(lin.marcas) >= antes and not lin.sugeridas and vista._fila_sug.isHidden(),
                      f'«Poner las N» → {len(lin.marcas)} marcas y ya no queda nada que sugerir (la fila se esconde)')
            z = next((zz for zz in lin.zonas if zz[1] - zz[0] > 2.0), None)
            if z is not None:
                lin.quitar_todas()
                borde = next((round(t, 1) for t in (z[1] - 0.1, z[0] + 0.1) if all(abs(t - s) > 0.8 for s, _x in lin.sugeridas)), None)
                if borde is not None:                                  # (lejos de un anillo «+»: ese pondría la sugerencia)
                    clic(lin, borde)
                    comprobar(lin.marcas and abs(lin.marcas[0] - borde) < 0.06 and (not lin.nota or 'GO no lo pone' in lin.nota),
                              f'clic dentro del verde, junto a su borde ({POS.texto_t(borde)}) → se queda ahí y sin aviso vacío ({lin.marcas}, «{lin.nota}»)')
            lin._t_sobre = lin.marcas[0] if lin.marcas else None
            lin.grab().save(str(tmp / f'vista_{sug_v.stem}_marca.png'))
            lin._t_sobre = None
            # otro tema en Inicio → la vista con SUS captions
            PREFS['go_pack'] = PREFS['plantilla'] = 'Referencia'
            vista.al_volver()
            esperar(lambda: lin.captions is not None and lin.captions.get('pack') == 'Referencia' and lin.sugeridas, 60)
            comprobar(lin.captions is not None and lin.captions.get('nombre') == 'Tema 2', f'cambio a Tema 2 en Inicio → la vista lo detecta ({(lin.captions or {}).get("nombre")})')
            if lin.sugeridas:
                k = round(lin.sugeridas[0][0], 1)
                esperar(lambda: k in lin._vistas, 60)
                lin._t_sobre = lin.sugeridas[0][0]
                lin.grab().save(str(tmp / f'vista_{sug_v.stem}_tema2.png'))
                lin._t_sobre = None
            PREFS['go_pack'] = PREFS['plantilla'] = 'Kinetic'
    # un video elegido a mano: el tope de marcas y «Listo» lo pone en Inicio
    pruebas_v = next((v for v in videos if v.name == 'PRUEBAS (1).mp4'), None)
    if pruebas_v is not None:
        vista._a_mano = True
        sec.mostrar_posiciones(True)
        vista.abrir(str(pruebas_v))
        listo = esperar(lambda: lin.ruta == str(pruebas_v) and lin.dur > 0 and lin.zonas is not None and lin.captions_listos)
        comprobar(listo, f'PRUEBAS (1) elegido a mano: carga ({lin.zonas})')
        if listo:
            tope = POS.TOPE_MARCAS['detras']
            for k in range(tope + 1):
                clic(lin, 1.0 + 2.5 * k)
            comprobar(len(lin.marcas) == tope and 'Máximo' in lin.nota, f'tope: {tope} marcas y la {tope + 1}.ª no entra: «{lin.nota[:70]}»')
            lin.grab().save(str(tmp / 'tira_PRUEBAS.png'))
            vista._listo()
            comprobar(INICIO[0] == str(pruebas_v), '«Listo» con un video elegido a mano → pasa a ser el de Inicio (GO lo usará)')
            fila = LAT.FilaPro(QWidget())
            fila.resize(1500, 760)
            fila.show()
            app.processEvents()
            lista = fila.lista
            vis = [o['clave'] for o in LAT.opciones_visibles()]
            barra, paso, y0 = lista._geo()
            pos = QPointF(barra.center().x(), y0 + paso * (vis.index('detras') + 0.5))
            QApplication.sendEvent(lista, QMouseEvent(QEvent.Type.MouseMove, pos, pos, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                                      Qt.KeyboardModifier.NoModifier))
            t0 = time.time()
            while lista.paso_resorte(1 / 60) and time.time() - t0 < 5:
                pass
            sub = lista._et_txt[1] if lista._et_txt else ''
            comprobar(f'Encendido · {tope} posiciones' in sub, f'la píldora de Proyecto (Inicio) lo dice: «{sub}»')
            lista.grab().save(str(tmp / 'pildora_detras.png'))               # (los botones de la intensidad se colocan al pintar)
            comprobar([n for _r, n in lista._niveles_rects] == ['suave', 'media', 'fuerte'], 'y sigue con Suave · Media · Fuerte debajo')
    tema6 = next((v for v in videos if v.name == 'TEMA6USAR.mp4'), None)
    if tema6 is not None:
        sec.mostrar_posiciones(True)
        vista.abrir(str(tema6))
        listo = esperar(lambda: lin.ruta == str(tema6) and lin.dur > 0 and lin.zonas is not None and lin.captions_listos)
        listo = listo and esperar(lambda: isinstance(lin._reglas, dict) and not lin._go_ocupado and lin.sugeridas, 120)
        if comprobar(listo, f'TEMA6USAR: sugerencias comprobadas con la regla de GO ({lin.sugeridas})'):
            comprobar(all(lin.estado_go(t) for t, _x in lin.sugeridas), 'y GO pone todas')
            lin._t_sobre = lin.sugeridas[0][0]
            lin.grab().save(str(tmp / 'tira_TEMA6USAR.png'))
    print(f'\n{len(OKS)} OK · {len(FALLOS)} FALLO', flush=True)
    for f in FALLOS:
        print('  FALLO', f)
    print('Capturas en', tmp)
    return 1 if FALLOS else 0


if __name__ == '__main__':
    code = main()
    os._exit(code)
