# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_detras_timeline.py — v5.29: prueba «Listo → al timeline» de «Captions detrás de ti» SIN Resolve: el matte de la
# persona con la IA (ProRes 4444 con alfa) y colocar_pro en modo «solo_encima» contra un Resolve SIMULADO. SOLO desarrollo.
"""
    python 1_codigo/herramientas_dev/probar_detras_timeline.py [video]

Por defecto Desktop/PARA PRUEBAS/PRUEBAS (1).mp4 (de pie en una cocina) con el Tema 1 y la PRO. Preferencias SOLO en memoria; posiciones_pro.json,
el plan de la PRO, el contexto de «detrás de ti», las copias de audio y el Registro en una carpeta temporal (lo de tu disco solo se LEE).
1) Las marcas y la copia con el audio compatible (audio_compatible): con tu posiciones_pro.json real (solo lectura), la copia de PRUEBA ESPAÑOL
   que GO llevó a Resolve encuentra las marcas del original; con origen.json, la copia y el original tienen la misma clave.
2) Un GO simulado del Tema 1: plan, placa (kit_neon_placa) y el contexto que guarda aplicar (_guardar_contexto_detras).
3) «Listo» (edicion_pro.aplicar_detras) con Resolve simulado: los tramos de las marcas, el matte de cada uno (ProRes 4444 con alfa, con la persona
   dentro), colocar_pro.main() en «solo_encima» sobre un timeline falso (V1 + placa en PRO-ZOOM + captions del Tema 1 en PRO-SUBS + un gráfico
   que NO se toca): PRO-ENCIMA arriba con un clip por tramo, los captions de esos tramos subidos con su marca, V1 y el gráfico intactos;
   repetir no apila; sin GO de ese video o con otro timeline abierto, no toca nada y lo dice.
Imprime OK/FALLO por comprobación; código de salida 1 si algo falló.
"""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
FALLOS, OKS = [], []


def comprobar(cond, texto):
    (OKS if cond else FALLOS).append(texto)
    print(('  OK    ' if cond else '  FALLO ') + texto, flush=True)
    return cond


# ------------------------------------------------------------------------------------------------------------- un Resolve de mentira
class Item:
    def __init__(self, tl, pista, start, end, mpi=None, nombre=''):
        self.tl, self.pista, self.start, self.end, self.mpi, self.nombre = tl, pista, int(start), int(end), mpi, nombre
        self.props = {'Tilt': 0.0, 'Pan': 0.0, 'ZoomX': 1.0, 'ZoomY': 1.0, 'CropBottom': 0.0}
        self.marcas, self.activo, self.color = {}, True, ''

    def GetStart(self):
        return self.start

    def GetEnd(self):
        return self.end

    def GetLeftOffset(self):
        return 0

    def GetName(self):
        return self.nombre

    def SetName(self, n):
        self.nombre = n
        return True

    def SetClipColor(self, c):
        self.color = c
        return True

    def GetProperty(self, k=None):
        return dict(self.props) if k is None else self.props.get(k)

    def SetProperty(self, k, v):
        self.props[k] = v
        return True

    def GetMarkers(self):
        return dict(self.marcas)

    def AddMarker(self, f, color, nombre, nota, dur, dato=''):
        self.marcas[len(self.marcas) + 1000] = {'color': color, 'name': nombre, 'customData': dato}
        return True

    def DeleteMarkerByCustomData(self, dato):
        self.marcas = {k: v for k, v in self.marcas.items() if v.get('customData') != dato}
        return True

    def SetClipEnabled(self, si):
        self.activo = bool(si)
        return True

    def GetMediaPoolItem(self):
        return self.mpi

    def GetFusionCompNameList(self):
        return []

    def SetFusionOutputCache(self, *_a):
        return True


class Clip:
    def __init__(self, ruta, frames=0):
        self.ruta, self.frames, self.props = str(ruta), int(frames), {'Alpha mode': 'None'}

    def GetClipProperty(self, k=None):
        if k == 'File Path':
            return self.ruta
        if k == 'Frames':
            return str(self.frames)
        return self.props.get(k)

    def SetClipProperty(self, k, v):
        self.props[k] = v
        return True


class Carpeta:
    def __init__(self, nombre):
        self.nombre, self.clips, self.subs = nombre, [], []

    def GetName(self):
        return self.nombre

    def GetClipList(self):
        return list(self.clips)

    def GetSubFolderList(self):
        return list(self.subs)


class Timeline:
    def __init__(self, nombre, fps, inicio):
        self.nombre, self.fps, self.inicio = nombre, fps, inicio
        self.pistas = []                                                   # [[nombre, [Item]]]

    def GetName(self):
        return self.nombre

    def GetSetting(self, k):
        return {'timelineFrameRate': str(self.fps), 'timelineResolutionWidth': '1080', 'timelineResolutionHeight': '1920'}.get(k)

    def GetStartFrame(self):
        return self.inicio

    def GetTrackCount(self, tipo):
        return len(self.pistas) if tipo == 'video' else 0

    def GetTrackName(self, tipo, i):
        return self.pistas[i - 1][0] if tipo == 'video' and 1 <= i <= len(self.pistas) else ''

    def SetTrackName(self, tipo, i, n):
        self.pistas[i - 1][0] = n
        return True

    def AddTrack(self, tipo, opciones=None):
        i = int((opciones or {}).get('index') or len(self.pistas) + 1)
        self.pistas.insert(i - 1, ['Video %d' % i, []])
        return True

    def DeleteTrack(self, tipo, i):
        del self.pistas[i - 1]
        return True

    def GetItemListInTrack(self, tipo, i):
        return list(self.pistas[i - 1][1]) if tipo == 'video' and 1 <= i <= len(self.pistas) else []

    def DeleteClips(self, items, ripple=False):
        for p in self.pistas:
            p[1] = [x for x in p[1] if x not in items]
        return True

    def GetIsTrackLocked(self, *_a):
        return False

    def SetCurrentTimecode(self, *_a):
        return True


class MediaPool:
    def __init__(self, tl):
        self.tl, self.raiz, self.actual = tl, Carpeta('Master'), None

    def GetRootFolder(self):
        return self.raiz

    def AddSubFolder(self, padre, nombre):
        c = Carpeta(nombre)
        padre.subs.append(c)
        return c

    def GetCurrentFolder(self):
        return self.actual or self.raiz

    def SetCurrentFolder(self, c):
        self.actual = c
        return True

    def ImportMedia(self, rutas):
        import av
        nuevos = []
        for r in rutas:
            try:
                with av.open(str(r)) as c:
                    vs = c.streams.video[0]
                    frames = vs.frames or int(float(vs.duration * vs.time_base) * float(vs.average_rate or 30))
            except Exception:
                frames = 0
            clip = Clip(r, frames)
            (self.actual or self.raiz).clips.append(clip)
            nuevos.append(clip)
        return nuevos

    def AppendToTimeline(self, lista):
        out = []
        for d in lista:
            i = int(d['trackIndex'])
            n = int(d.get('endFrame', 0)) - int(d.get('startFrame', 0)) + 1
            it = Item(self.tl, i, d['recordFrame'], int(d['recordFrame']) + max(1, n), d['mediaPoolItem'])
            self.tl.pistas[i - 1][1].append(it)
            out.append(it)
        return out


def main():
    video = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / 'Desktop' / 'PARA PRUEBAS' / 'PRUEBAS (1).mp4'
    if not video.is_file():
        print('No encuentro', video)
        return 1
    tmp = Path(tempfile.mkdtemp(prefix='ccdetras_tl_'))
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
    import audio_compatible as AC
    import edicion_pro as EP
    import posiciones_pro as POS

    # ------------------------------------------------------------------------------------------------------- 1) la copia de audio compatible
    print('== 1) Marcas y la copia con el audio compatible', flush=True)
    copia_real = next(iter(sorted(AC.CARPETA.glob('*/PRUEBA ESPAÑOL.mp4'))), None) if AC.CARPETA.is_dir() else None
    original_real = Path.home() / 'Desktop' / 'PRUEBA ESPAÑOL.mp4'
    if copia_real is not None and (POS.leer(original_real).get('detras') or {}).get('ts'):
        comprobar(POS.leer(copia_real).get('detras') == POS.leer(original_real).get('detras'),
                  f'tu caso real (solo lectura): la copia «{copia_real.parent.name}/{copia_real.name}» que GO llevó a Resolve ve las marcas del original '
                  f'{POS.leer(original_real).get("detras")}')
    else:
        print('     (sin la copia de PRUEBA ESPAÑOL o sin sus marcas: no pruebo tu caso real)')
    POS.ARCHIVO = tmp / 'posiciones_pro.json'
    POS.CACHE = tmp / 'cache_posiciones'
    import edicion_pro_persona as PE
    PE.MASCARAS = tmp / 'mascaras_persona'                            # (v5.31: las máscaras guardadas, aisladas)
    AC.CARPETA = tmp / 'audio_compatible'
    copia = AC.CARPETA / 'abc123' / video.name
    copia.parent.mkdir(parents=True)
    copia.write_bytes(b'x' * 2000)
    POS.guardar(str(video), 'detras', [3.0, 9.0], 'solo')
    comprobar((POS.leer(str(copia)).get('detras') or {}).get('ts') == [3.0, 9.0], 'una copia SIN origen.json encuentra las marcas por el nombre')
    AC._apuntar_origen(copia, video)
    comprobar(POS.clave_video(str(copia)) == POS.clave_video(str(video)), 'con origen.json la copia y el original tienen la misma clave')
    POS.guardar(str(copia), 'detras', [4.0], 'solo')
    comprobar((POS.leer(str(video)).get('detras') or {}).get('ts') == [4.0], 'y guardar desde la copia guarda en el original')
    POS.ARCHIVO.unlink()

    # ------------------------------------------------------------------------------------------------------- 2) un GO simulado (Tema 1 + PRO)
    print('== 2) GO simulado del Tema 1: plan, placa y contexto', flush=True)
    EP.PLAN_JSON = tmp / 'edicion_pro_plan.json'
    EP.DETRAS_CTX = tmp / 'detras_contexto.json'
    EP.CARPETA = tmp / 'edicion_pro'
    import efectos_visuales
    import kit_neon as KN
    import kit_neon_motions as KM
    import kit_neon_placa as PLA
    w = POS._voz_de(str(video))
    if not w:
        print('Ese video no está transcrito (pasa GO una vez).')
        return 1
    _w, _h, dur, fps = EP.medir(str(video))
    idioma = POS._idioma_de(w)
    cortes = efectos_visuales.detectar_cortes(str(video)) or []
    plan = EP.planificar(str(video), w, dur, cortes=cortes, idioma=idioma, opciones=EP.opciones_guardadas(), tema='neon')
    plan['kitneon'] = KM.ajustar_captions(KN.escena_captions(w, idioma, fin_video=dur), plan['kitneon_motions'])
    plan['_neon_ajustado'] = True
    plan['duracion'] = dur
    bl = KN.bloques_pro(plan['kitneon'])
    carpeta = EP.CARPETA / 'go'
    carpeta.mkdir(parents=True)
    t0 = time.time()
    placa = PLA.para_pro(str(video), plan, carpeta, 1080, 1920, fps)
    comprobar(placa is not None and Path(placa).is_file(), f'la placa del Tema 1 ({time.time() - t0:.0f} s)')
    inicio = int(round(3600 * fps))
    total = int(round(dur * fps))
    info = {'fps': fps, 'ancho': 1080, 'alto': 1920, 'inicio': inicio, 'base': inicio, 'producto': 'DaVinci Resolve Studio', 'via': 'mcp',
            'nombre': f'CineCaptions · {video.stem}', 'ocupado': [],
            'v1': [{'ruta': str(video), 'ini': inicio, 'fin': inicio + total, 'izq': 0, 'fps': fps, 'res': f'{_w}x{_h}', 'zx': 1.0, 'zy': 1.0,
                    'pan': 0.0, 'tilt': 0.0}]}
    ocup = [(m['ini'] - 0.1, m['fin'] + 0.1) for m in plan['kitneon_motions']]
    EP._guardar_contexto_detras(plan, info, str(video), str(video), fps, 1080, 1920, carpeta, True, placa,
                                {'ocupado': ocup, 'bloques': bl, 'preferidos': []}, EP.opciones_guardadas())
    ctx = EP.contexto_detras(str(video))
    comprobar(ctx is not None and ctx['placa'] and len(ctx['bloques']) == len(bl), f'GO deja el contexto de «detrás de ti» ({len(bl)} bloques, placa)')
    # las marcas: las sugeridas de la tira (lo que el usuario toca)
    an = POS.analizar_detras(str(video))
    cap = POS.captions_del_video(str(video))
    zonas, _m = POS.zonas_detras(an, POS.palabras(str(video)), POS.bloques_de(cap))
    sug = [t for t, _x in POS.sugerir(zonas, an, POS.bloques_de(cap), exigir_grande=True)]
    POS.guardar(str(video), 'detras', sug, 'solo')
    comprobar(len(sug) >= 1, f'marcas = las sugeridas de la tira: {sug}')
    # el plan que dejó «ese GO» (con un gráfico que el modo «solo_encima» NO debe tocar)
    datos_go = {'fps': fps, 'inicio': inicio, 'graficos': [], 'encima': [], 'mover': [], 'cache': True}
    EP.PLAN_JSON.write_text(json.dumps(datos_go), encoding='utf-8')

    # ------------------------------------------------------------------------------------------------------- 3) «Listo» → timeline (simulado)
    print('== 3) «Listo» → al timeline, con Resolve simulado', flush=True)
    tl = Timeline(info['nombre'], fps, inicio)
    mp = MediaPool(tl)
    tl.pistas.append(['Video 1', [Item(tl, 1, inicio, inicio + total, Clip(video, total), 'video')]])
    tl.pistas.append(['Video con cámara y zooms · PRO-ZOOM', [Item(tl, 2, inicio, inicio + total, Clip(placa, total), 'placa')]])
    tl.pistas.append(['Gráficos delante · PRO-DELANTE', [Item(tl, 3, inicio + 30, inicio + 90, Clip('grafico.mov', 60), 'gráfico')]])
    subs = []
    for b in bl:                                                       # (los clips neón empiezan en ini_clip, como los coloca GO)
        f0 = inicio + int(round(b['ini_clip'] * fps))
        subs.append(Item(tl, 4, f0, inicio + int(round(b['fin'] * fps)), Clip('neon.mov', 1), 'caption'))
    tl.pistas.append(['Captions · PRO-SUBS', subs])
    import importlib.util
    spec = importlib.util.spec_from_file_location('colocar_pro_prueba', str(EP.carpeta_recursos() / 'colocar_pro.py'))
    CP = importlib.util.module_from_spec(spec)
    CP.resolve = types.SimpleNamespace(OpenPage=lambda *_a: True, SCALE_FILL=3)
    CP.project = types.SimpleNamespace(GetCurrentTimeline=lambda: tl, GetMediaPool=lambda: mp, GetSetting=lambda *_a: 'user', SetSetting=lambda *_a: True)
    spec.loader.exec_module(CP)
    CP.RUTA_JSON = str(EP.PLAN_JSON)
    corridas = []

    def ejecutar_py(script, timeout=600, on_progreso=None, sincrono=False):
        corridas.append(json.loads(EP.PLAN_JSON.read_text(encoding='utf-8')))
        if on_progreso:                                                  # (v5.32: la barra de «Listo» sigue viva mientras Resolve trabaja)
            on_progreso(3.0)
        import contextlib
        import io
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            CP.main()
        return True, salida.getvalue()
    import resolve_mcp
    resolve_mcp.ejecutar_py = ejecutar_py
    EP._info_timeline = lambda: {k: v for k, v in info.items() if k != 'base'}
    t0 = time.time()
    avances = []
    ok, mensaje, n = EP.aplicar_detras(str(video), al_estado=lambda t: None, al_progreso=lambda f, t='': avances.append((f, t)))
    t_primero = time.time() - t0
    print(f'     aplicar_detras: {t_primero:.0f} s · {mensaje.strip()[-160:]}')
    fs = [f for f, _t in avances]
    comprobar(fs and all(b >= a - 1e-9 for a, b in zip(fs, fs[1:])) and abs(fs[-1] - 1.0) < 1e-9 and any('Recortando' in t for _f, t in avances),
              f'la barra avanza sin volver atrás hasta el 100 % ({len(fs)} avisos, con «Recortando a la persona…»)')
    guardadas = sorted(PE.MASCARAS.glob('*.mov')) if PE.MASCARAS.is_dir() else []
    comprobar(len(guardadas) == n, f'{len(guardadas)} máscaras guardadas para siempre en mascaras_persona (una por tramo)')
    comprobar(ok and n == len(sug), f'«Listo» pone {n} de {len(sug)} tramos (uno por marca)')
    plan_enviado = corridas[-1] if corridas else {}
    comprobar(plan_enviado.get('solo_encima') is True, 'colocar_pro recibe el modo «solo_encima» (solo «detrás de ti»)')
    enc = plan_enviado.get('encima') or []
    comprobar(enc and all(e.get('modo') == 'clip' and e.get('fuente') == 'placa' for e in enc),
              'cada tramo con la persona como clip (matte de la IA), sacada de la placa del Tema 1 — nada de Magic Mask')
    import av
    for e in enc:
        try:
            with av.open(e['archivo']) as c:
                vs = c.streams.video[0]
                fr = next(c.decode(vs))
                a = fr.to_ndarray(format='rgba')[..., 3]
                comprobar(vs.codec_context.name == 'prores' and 'a' in vs.codec_context.pix_fmt and (a > 128).mean() > 0.02,
                          f'{Path(e["archivo"]).name}: ProRes 4444 con alfa ({vs.codec_context.pix_fmt}), la persona ocupa {100 * (a > 128).mean():.0f} %')
        except Exception as ex:
            comprobar(False, f'{e.get("archivo")}: {ex!r}')
    nombres = [p[0] for p in tl.pistas]
    arriba = tl.pistas[-1]
    comprobar(CP._id(arriba[0]) == 'PRO-ENCIMA' and len(arriba[1]) == len(enc),
              f'PRO-ENCIMA es la pista de arriba del todo con {len(arriba[1])} clips ({nombres})')
    comprobar(all(it.mpi is not None and it.mpi.props.get('Alpha mode') == 'Straight' for it in arriba[1]), 'sus clips, con el alfa recto')
    subidos = [it for it in subs if any(str(m.get('customData')).startswith(CP.MARCA) for m in it.marcas.values())]
    comprobar(subidos and all(it.props['Tilt'] > 0 for it in subidos), f'{len(subidos)} captions del Tema 1 subidos (Tilt) con su marca para re-aplicar')
    comprobar(len(tl.pistas[0][1]) == 1 and tl.pistas[2][1][0].nombre == 'gráfico', 'V1 y el gráfico de la PRO, intactos')
    tilts = [it.props['Tilt'] for it in subs]
    t0 = time.time()
    ok2, _m2, n2 = EP.aplicar_detras(str(video), al_estado=lambda t: None)
    t_segundo = time.time() - t0
    comprobar(t_segundo < max(3.0, t_primero * 0.25), f'la segunda vez usa las máscaras guardadas: {t_segundo:.1f} s (antes {t_primero:.0f} s)')
    comprobar(ok2 and [it.props['Tilt'] for it in subs] == tilts and len(tl.pistas[-1][1]) == n2,
              'darle a «Listo» otra vez no apila (los captions vuelven a su sitio y suben lo mismo; PRO-ENCIMA se rehace)')
    comprobar(json.loads(EP.PLAN_JSON.read_text(encoding='utf-8')).get('solo_encima') is False, 'después, el plan guardado vuelve a ser el completo')
    ctx = EP.contexto_detras(str(video))
    puestos = sorted(round(((c['ini'] + c['fin']) / 2.0) / fps, 2) for e in enc for c in e['cues'])
    comprobar(ctx.get('aplicados') == puestos and EP.aplicados_para(str(video), ctx) == puestos,
              f'el contexto apunta lo que quedó en el timeline: {ctx.get("aplicados")}')
    # v5.30: pausas quitadas por GO: del timeline al archivo y vuelta
    c2 = dict(ctx, recorte={'segmentos': [[0.0, 5.0], [7.0, 30.0]]}, aplicados=[2.0, 6.0])
    comprobar(EP.aplicados_para(str(video), c2) == [2.0, 8.0] and EP._a_timeline_go(str(video), c2, [2.0, 8.0]) == [2.0, 6.0],
              'con pausas quitadas: 6 s del timeline = 8 s del archivo, y al revés')

    # ------------------------------------------------------------------------------------------------------- 4) la tira y «Listo» (interfaz)
    print('== 4) La tira enseña lo que hay en el timeline; «Listo» pone exactamente lo de la tira', flush=True)
    import qt_kit
    app = qt_kit.crear_app()
    import efectos_pro_ui as EPU
    import estilos_pro as EST
    import pro_lateral_ui as LAT
    POS.poner_proveedor(lambda: str(video))
    sec = EPU.SeccionEstilo(next(x for x in EST.SECCIONES if x['clave'] == 'detras'), LAT._POR_CLAVE['detras'])
    sec.resize(1400, 760)
    sec.show()

    def esperar(cond, tope=180):
        t0 = time.time()
        while not cond() and time.time() - t0 < tope:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        return cond()
    POS.guardar(str(video), 'detras', [1.0], 'solo')                  # (lo guardado es MÁS VIEJO que el último «Listo»: manda el timeline)
    datos_p = json.loads(POS.ARCHIVO.read_text(encoding='utf-8'))
    for v in datos_p.values():
        for m in (v.get('secciones') or {}).values():
            m['cuando'] = 1.0
    POS.ARCHIVO.write_text(json.dumps(datos_p), encoding='utf-8')
    sec.mostrar_posiciones(True)
    lin = sec._pos.linea
    esperar(lambda: lin.dur > 0 and lin.zonas is not None and lin.captions_listos)
    comprobar(lin.marcas == puestos and lin.modo == 'solo' and 'en tu timeline' in lin.nota and lin.igual_que_timeline(),
              f'la tira enseña lo que hay en el timeline ({lin.marcas}) y lo dice: «{lin.nota[:60]}…»')
    n_antes = len(corridas)
    sec._pos._listo()
    app.processEvents()
    comprobar(len(corridas) == n_antes and any('ya está así' in x for _n, x in REG), '«Listo» sin cambios: no toca Resolve («ya está así en tu timeline»)')
    sec.mostrar_posiciones(True)
    esperar(lambda: lin.dur > 0 and lin.zonas is not None and lin.captions_listos and lin.marcas == puestos)
    est = lin.estado_marcas()
    comprobar(est == (puestos, [], []), f'todo lo de la tira sale «en tu timeline» (relleno verde): {est}')
    quitada = lin.marcas[0]
    lin._quitar(0)
    est = lin.estado_marcas()
    comprobar(est[2] == [quitada] and not est[1], f'quitar una: sale en rojo «se quita» ({est[2]})')
    from PySide6.QtCore import QPointF
    pos_q = QPointF(lin._x(quitada), lin._tira().top() - 14)
    comprobar(lin._quitada_en(pos_q) == quitada, 'un clic en la ✕ roja la recupera tal cual')
    sec._pos.grab().save(str(tmp / 'tira_quitada.png'))
    sec._pos._listo()
    comprobar(sec._en_pos and sec._pos.isVisible() and lin.bloqueada and sec._pos._fila_prog.isVisible(),
              '«Listo» con cambios: la vista sigue abierta, la tira bloqueada y la barra a la vista')
    marcas_antes = list(lin.marcas)
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent, Qt as _Qt
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(lin._tira().center()), QPointF(lin._tira().center()),
                     _Qt.MouseButton.LeftButton, _Qt.MouseButton.LeftButton, _Qt.KeyboardModifier.NoModifier)
    lin.mousePressEvent(ev)
    comprobar(lin.marcas == marcas_antes, 'mientras aplica, un clic en la tira no cambia nada')
    vistos = []
    while getattr(sec, '_aplicando', False):
        app.processEvents()
        vistos.append(sec._pos._barra.get())
        if len(vistos) == 40:
            sec._pos.grab().save(str(tmp / 'tira_aplicando.png'))
        time.sleep(0.02)
    app.processEvents()
    comprobar(max(vistos or [0]) > 0.0 and len(corridas) > n_antes, f'la barra de la vista avanza (llegó al {100 * max(vistos or [0]):.0f} %)')
    comprobar(len(tl.pistas[-1][1]) == len(puestos) - 1 and CP._id(tl.pistas[-1][0]) == 'PRO-ENCIMA',
              f'quitar una y «Listo» → en el timeline queda una menos ({len(tl.pistas[-1][1])})')
    esperar(lambda: len(lin.marcas) == len(puestos) - 1 and lin._aplicados == lin.marcas, 30)
    comprobar(not lin.bloqueada and lin._aplicados == lin.marcas and 'Puesto en tu timeline' in lin.nota and 'ya está en tu timeline' in sec._pos._lbl_prog.text(),
              f'al acabar, la tira enseña lo de ahora en verde ({lin.marcas}) y lo dice: «{lin.nota[:50]}…»')
    sec._pos.grab().save(str(tmp / 'tira_aplicada.png'))
    sec.mostrar_posiciones(True)
    esperar(lambda: lin.dur > 0 and lin.zonas is not None and lin.captions_listos and len(lin.marcas) == len(puestos) - 1)
    comprobar(len(lin.marcas) == len(puestos) - 1, f'al volver a abrir, la tira enseña lo de ahora ({lin.marcas})')
    sec._pos._quitar_todas()
    n_antes = len(corridas)
    sec._pos._listo()
    esperar(lambda: not getattr(sec, '_aplicando', False) and len(corridas) > n_antes, 300)
    comprobar(not any(CP._id(p[0]) == 'PRO-ENCIMA' for p in tl.pistas) and all(abs(it.props['Tilt']) < 1e-6 for it in subs),
              '«Quitar todas» + «Listo» → fuera del timeline: sin PRO-ENCIMA y los captions en su sitio')
    comprobar(any('quitado de tu timeline' in x for _n, x in REG), 'y el Registro lo dice')
    esperar(lambda: lin._aplicados == [], 30)
    comprobar(lin._aplicados == [] and 'Quitado' in lin.nota, f'y la tira: «{lin.nota}»')
    # otro timeline abierto: no toca nada
    EP._info_timeline = lambda: dict({k: v for k, v in info.items() if k != 'base'}, v1=[dict(info['v1'][0], ruta='otro.mp4')])
    antes = [len(p[1]) for p in tl.pistas]
    ok3, m3, _n3 = EP.aplicar_detras(str(video))
    comprobar(not ok3 and 'otro timeline' in m3 and [len(p[1]) for p in tl.pistas] == antes, f'con otro timeline abierto no toca nada: «{m3}»')
    EP.DETRAS_CTX.unlink()
    ok4, m4, _n4 = EP.aplicar_detras(str(video))
    comprobar(not ok4 and 'GO' in m4, f'sin un GO de ese video lo dice: «{m4}»')
    print(f'\n{len(OKS)} OK · {len(FALLOS)} FALLO', flush=True)
    for f in FALLOS:
        print('  FALLO', f)
    return 1 if FALLOS else 0


if __name__ == '__main__':
    code = main()
    os._exit(code)
