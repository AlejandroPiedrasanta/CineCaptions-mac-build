# CineCaptions · By Cinema Productions
# 2_recursos/edicion_pro/colocar_pro.py — corre DENTRO de Resolve: pone la Edición PRO en el timeline (gráficos OGraf, la persona con Magic Mask, sonidos).
"""
Lo lanza edicion_pro.aplicar() (resolve_mcp.ejecutar_py) y lee ~/DaVinciSubtitles/edicion_pro_plan.json:

    {'fps', 'inicio', 'graficos': [{'capa': 'fondo'|'velo'|'detras'|'delante', 'ini': fotograma (desde 'inicio'), 'archivo': .ograf (ruta larga), 'nombre'}],
     'persona': [{'ini', 'fin', 'modo': 'magic'|'clip', 'comp': .comp | 'archivo': .mov, 'ref': fotograma del clip}],
     'broll': [{'ini', 'dur': segundos, 'archivo': .mp4, 'palabra'}],
     'encima': [{'ini', 'fin', 'modo', 'comp'|'archivo', 'ref', 'velo': .ograf, 'cues': [{'ini', 'fin', 'subir': píxeles hacia arriba, 'caras'}]}],
     'mover': [{'ini', 'fin', 'subir', 'caras': [[x0, y0, x1, y1] fracciones]}]   (los demás bloques: ninguno tapa una cara; sus emojis tampoco),
     'sonidos': [{'ini': fotograma, 'archivo': .wav, 'dur': segundos}], 'punch': [[inicio absoluto del clip de V1, zoom]], 'cache': True,
     'captions_propios': True (Tema 5: los captions son animaciones Remotion en PRO-SUBS; los Text+ de respaldo que puso GO se apagan),
     'gris_foco': [[ini, fin]] (Tema 5: el fondo en blanco y negro bajo la persona a color), 'zoom': [[corte, n antes, n después]] (Tema 5:
     la transición con zoom de Fusion en los cortes)}

Pistas (de abajo arriba, justo encima de V1 / FX-BROLL y DEBAJO de los captions, que siguen mandando):
PRO-BROLL · PRO-ZOOM · PRO-GRIS · PRO-FONDO · PRO-VELO · PRO-DETRAS · PRO-PERSONA · PRO-DELANTE · PRO-SUBS; el audio en «PRO-SONIDO». Cada corrida vacía y rellena sus pistas
(re-aplicar no apila). Y ENCIMA de los captions, «PRO-ENCIMA»: la persona recortada solo en los tramos en que los captions van DETRÁS de ella;
en esos tramos la pila de los captions sube (Tilt) hasta la coronilla. Si el recorte no sale (rastreo incompleto), ese tramo se deshace entero.

Magic Mask (Studio): la persona es el mismo clip de V1 en PRO-PERSONA con una composición de Fusion (MediaIn → MagicMask → MediaOut) que trae
los puntos sobre cada persona en el fotograma de referencia. El rastreo SOLO avanza con esa composición abierta en la página Fusion, y la
página Fusion abre el clip de MÁS ARRIBA bajo el cabezal: por eso se apagan un momento las pistas de encima (captions y gráficos) y se
vuelven a encender. NUNCA se llama a StopTracking: abre un diálogo modal («¿cancelar el render?») que bloquea Resolve.
Nada de InsertFusionTitleIntoTimeline (con nombres dudosos tumbó Resolve): todo es ImportMedia + AppendToTimeline.
"""
import json
import os
import re
import tempfile
import time

RUTA_JSON = os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'edicion_pro_plan.json')
ORDEN = ['PRO-BROLL', 'PRO-ZOOM', 'PRO-GRIS', 'PRO-FONDO', 'PRO-VELO', 'PRO-DETRAS', 'PRO-PERSONA', 'PRO-DELANTE', 'PRO-SUBS']
CAPA = {'fondo': 'PRO-FONDO', 'velo': 'PRO-VELO', 'detras': 'PRO-DETRAS', 'delante': 'PRO-DELANTE', 'iconos': 'PRO-ICONOS', 'subs': 'PRO-SUBS'}
PISTA_ENCIMA = 'PRO-ENCIMA'
PISTA_ICONOS = 'PRO-ICONOS'              # los iconos 3D junto a los captions: encima de ellos (y debajo de PRO-ENCIMA)
MARCA_EMOJI = 'ccpro-emoji-off'          # el emoji del tema que se apagó porque en ese bloque va un icono 3D
TRANSFORMACION = ('Scaling', 'ZoomX', 'ZoomY', 'Pan', 'Tilt', 'RotationAngle', 'AnchorPointX', 'AnchorPointY', 'Pitch', 'Yaw', 'FlipX', 'FlipY',
                  'CropLeft', 'CropRight', 'CropTop', 'CropBottom', 'CropSoftness')
MARCA = 'ccpro-subir'                    # marca en cada clip de captions que se subió: 'ccpro-subir:<Tilt antes>:<Tilt después>'
PISTA_SONIDO = 'PRO-SONIDO'              # (versiones anteriores: todo en una pista)
PISTAS_AUDIO = ['PRO-WHOOSH', 'PRO-TEXTURA', 'PRO-RISER', 'PRO-HIT']   # una familia de sonido por pista (guía de sonido)
BIN = 'RCS · Edición PRO'
NOMBRE_COMP = 'CineCaptions PRO · persona'
NOMBRE_ZOOM = 'CineCaptions PRO · zoom'
NOMBRE_FOCO = 'PRO · fondo en blanco y negro'
RASTREO_MAX_S = 150


def _norm(r):
    return os.path.normcase(os.path.normpath(str(r)))


def _buscar(carpeta, buscada):
    for c in carpeta.GetClipList() or []:
        try:
            if _norm(c.GetClipProperty('File Path') or '') == buscada:
                return c
        except Exception:
            pass
    for sub in carpeta.GetSubFolderList() or []:
        x = _buscar(sub, buscada)
        if x is not None:
            return x
    return None


def _caja(mp):
    raiz = mp.GetRootFolder()
    for f in raiz.GetSubFolderList() or []:
        if f.GetName() == BIN:
            return f
    return mp.AddSubFolder(raiz, BIN) or raiz


def _importar(mp, caja, ruta):
    ya = _buscar(mp.GetRootFolder(), _norm(ruta))
    if ya is not None:
        return ya
    previa = mp.GetCurrentFolder()
    try:
        mp.SetCurrentFolder(caja)
        nuevos = mp.ImportMedia([str(ruta)]) or []
    finally:
        try:
            mp.SetCurrentFolder(previa)
        except Exception:
            pass
    return nuevos[0] if nuevos else None


def _indice(tl, nombre, tipo='video'):
    for i in range(1, int(tl.GetTrackCount(tipo) or 0) + 1):
        if tl.GetTrackName(tipo, i) == nombre:
            return i
    return None


def _vaciar(tl, idx, tipo='video'):
    try:
        if tl.GetIsTrackLocked(tipo, idx):
            tl.SetTrackLock(tipo, idx, False)
    except Exception:
        pass
    viejos = tl.GetItemListInTrack(tipo, idx) or []
    if viejos:
        tl.DeleteClips(viejos, False)


def _pistas(tl):
    """Las pistas PRO, vacías y en su orden, justo encima de V1 (o de FX-BROLL). Devuelve {nombre: índice}."""
    for n in ORDEN:
        i = _indice(tl, n)
        if i is not None:
            _vaciar(tl, i)
    if all(_indice(tl, n) is not None for n in ORDEN):
        return {n: _indice(tl, n) for n in ORDEN}
    debajo = _indice(tl, 'FX-BROLL') or 1
    for n in ORDEN:
        if _indice(tl, n) is not None:
            debajo = _indice(tl, n)
            continue
        ok = False
        try:
            ok = bool(tl.AddTrack('video', {'index': debajo + 1}))           # Resolve 21: se inserta en esa posición (los captions suben)
        except Exception:
            ok = False
        if ok:
            tl.SetTrackName('video', debajo + 1, n)
        else:                                                              # sin inserción: al final (encima de todo); mejor eso que nada
            tl.AddTrack('video')
            tl.SetTrackName('video', int(tl.GetTrackCount('video')), n)
        debajo = _indice(tl, n)
    return {n: _indice(tl, n) for n in ORDEN}


def _quitar_vacias(tl):
    for n in ORDEN + [PISTA_ENCIMA, PISTA_ICONOS]:
        i = _indice(tl, n)
        if i is not None and not (tl.GetItemListInTrack('video', i) or []):
            try:
                tl.DeleteTrack('video', i)
            except Exception:
                pass


def _tc(tl, f):
    fps = float(tl.GetSetting('timelineFrameRate') or 30)
    e = int(round(fps))
    f = int(f)
    s = f // e
    return '%02d:%02d:%02d:%02d' % (s // 3600, s // 60 % 60, s % 60, f % e)


def _cache(item):
    try:
        item.SetFusionOutputCache('enabled')                               # «Render Cache Fusion Output»: Resolve lo pre-renderiza en segundo plano
    except Exception:
        pass


def _cache_color(item):
    try:
        item.SetColorOutputCache(True)                                     # «Render Cache Color Output» (las copias en gris del foco / modo error)
    except Exception:
        pass


def _modo_cache():
    """v5.4.52 (pedido del usuario: «la línea de tiempo no debe tener lags»): con la caché de render en «none» Resolve no guarda NADA aunque los
    clips lo pidan. Si está en «none» se pasa a «user»: solo se cachean los clips marcados (los de la Edición PRO: la Magic Mask, los gráficos,
    las transiciones), en segundo plano, y la reproducción va fluida. Si el usuario eligió «smart» o «user», se respeta."""
    try:
        if str(project.GetSetting('perfRenderCacheMode') or '').lower() == 'none':
            if project.SetSetting('perfRenderCacheMode', 'user'):
                print('Caché de render: «user» (la Edición PRO se pre-renderiza en segundo plano).')
    except Exception:
        pass


def _clip_v1(tl, f0, f1):
    """El clip de V1 que contiene [f0, f1) (None si no hay uno solo)."""
    for it in tl.GetItemListInTrack('video', 1) or []:
        if it.GetStart() <= f0 and f1 <= it.GetEnd():
            return it
    return None


def _rastreo_completo(it):
    """¿El Magic Mask del clip está rastreado de punta a punta? Se lee en su composición EXPORTADA (ProcessedFramesLow/High): la API no deja
    leerla sin abrir la página Fusion. Un clip sin rastrear sale entero (opaco) y TAPARÍA los captions y los titulares: no se deja."""
    ruta = os.path.join(tempfile.gettempdir(), 'ccpro_mm_%d.comp' % int(it.GetStart()))
    try:
        if not it.ExportFusionComp(ruta, 1):
            return False
        with open(ruta, encoding='utf-8', errors='replace') as f:
            txt = f.read()
    except Exception:
        return False
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass

    def valor(nombre):
        m = re.search(nombre + r'\s*=\s*Input\s*\{([^}]*)\}', txt)
        if not m:
            return None
        v = re.search(r'Value\s*=\s*(-?[\d.]+)', m.group(1))
        return float(v.group(1)) if v else 0.0
    lo, hi = valor('ProcessedFramesLow'), valor('ProcessedFramesHigh')
    return lo is not None and hi is not None and lo <= 0 and hi >= int(it.GetDuration()) - 1


def _rastrear(tl, items, idx_persona, decir):
    """Lanza el rastreo del Magic Mask de cada clip de la persona: items [(clip, fotograma de referencia, nombre del MagicMask)].
    Devuelve [True/False] por clip: True solo si su composición quedó rastreada entera (`_rastreo_completo`)."""
    if not items:
        return []
    apagadas = []
    for i in range(idx_persona + 1, int(tl.GetTrackCount('video') or 0) + 1):
        try:
            if tl.GetIsTrackEnabled('video', i):
                tl.SetTrackEnable('video', i, False)
                apagadas.append(i)
        except Exception:
            pass
    hechos = [False] * len(items)
    try:
        for k, (it, ref, herramienta) in enumerate(items):
            dur = int(it.GetDuration())
            mm = None
            for intento in range(3):                                       # la página Fusion tarda en cambiar de clip: si sigue en el anterior, otra vez
                resolve.OpenPage('edit')
                time.sleep(0.3 + 0.4 * intento)
                tl.SetCurrentTimecode(_tc(tl, it.GetStart() + ref))
                resolve.OpenPage('fusion')
                time.sleep(1.2 + 1.0 * intento)
                comp = resolve.Fusion().CurrentComp
                mm = comp.FindTool(herramienta) if comp else None
                if mm is not None:
                    break
            if mm is None:
                print('  Magic Mask: la página Fusion no abrió el clip de la persona (%d)' % (k + 1))
                continue
            decir('Magic Mask: rastreando a la persona (%d de %d)…' % (k + 1, len(items)))
            mm.SetInput('TrackBidirectional', 1)
            t0, ultimo, quieto = time.time(), None, time.time()
            while time.time() - t0 < RASTREO_MAX_S:
                time.sleep(1.0)
                lo, hi = mm.GetInput('ProcessedFramesLow'), mm.GetInput('ProcessedFramesHigh')
                if lo is not None and hi is not None and lo <= 0 and hi >= dur - 1:
                    break
                if (lo, hi) != ultimo:
                    ultimo, quieto = (lo, hi), time.time()
                elif time.time() - quieto > 12:                            # sin avanzar 12 s: se deja como está (no se cancela: modal)
                    print('  Magic Mask: el rastreo se paró en %s-%s de %d fotogramas' % (lo, hi, dur))
                    break
    finally:
        resolve.OpenPage('edit')
        time.sleep(0.4)
        for i in apagadas:
            try:
                tl.SetTrackEnable('video', i, True)
            except Exception:
                pass
    for k, (it, _ref, _h) in enumerate(items):
        hechos[k] = _rastreo_completo(it)
    return hechos


def _copiar_transformacion(de, a):
    """El recorte de la persona tiene que caer EXACTAMENTE sobre la persona de V1: misma escala (ajustado), zoom (punch-in), Pan, Tilt, recorte…"""
    try:
        props = de.GetProperty() or {}
    except Exception:
        props = {}
    for k in TRANSFORMACION:
        if k in props:
            try:
                a.SetProperty(k, props[k])
            except Exception:
                pass


def _punch_ins(tl, punch):
    """El punch-in que alterna en los saltos de V1 (pausas quitadas), como en la skill: zoom fijo en uno de cada dos clips. Absoluto (re-aplicar no apila)."""
    zooms = {int(f): float(z) for f, z in punch or []}
    puestos = 0
    for it in tl.GetItemListInTrack('video', 1) or []:
        z = zooms.get(int(it.GetStart()))
        if z:
            try:
                if it.SetProperty('ZoomX', z) and it.SetProperty('ZoomY', z):
                    puestos += 1
            except Exception:
                pass
    return puestos


def _fin_detras(tl, idx, f0):
    """Dónde acaba de verdad lo que va DETRÁS de la persona que empieza en f0 (los OGraf duran más que su tramo: llevan su salida)."""
    fin = 0
    for n in ('PRO-DETRAS', 'PRO-VELO', 'PRO-FONDO'):
        if idx.get(n):
            for x in tl.GetItemListInTrack('video', idx[n]) or []:
                if abs(int(x.GetStart()) - f0) <= 2:
                    fin = max(fin, int(x.GetEnd()))
    return fin


def _poner_persona(tl, mp, caja, p, f0, f1, pista):
    """El recorte de la persona de f0 a f1 en `pista`: el ProRes con alfa de la IA local ('clip') o el mismo clip de V1 con la composición del
    Magic Mask; con la transformación del clip de V1 que tiene debajo. Nunca sobre un clip de V1 con el movimiento de Efectos (no casaría)."""
    v1 = _clip_v1(tl, f0, f1)
    if v1 is not None and 'CineCaptions FX' in (v1.GetFusionCompNameList() or []):
        print('  la persona de %d a %d va sobre un clip con el movimiento de Efectos: no se recorta' % (f0, f1))
        return None
    if p.get('modo') == 'clip':
        clip = _importar(mp, caja, p['archivo'])
        if clip is None:
            return None
        try:
            clip.SetClipProperty('Alpha mode', 'Straight')
            f1 = min(f1, f0 + int(float(clip.GetClipProperty('Frames') or (f1 - f0))))
        except Exception:
            pass
        r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': f1 - f0 - 1, 'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
        if r and v1 is not None:
            _copiar_transformacion(v1, r[0])
        return r[0] if r else None
    if v1 is None:
        print('  la persona de %d a %d cruza un corte de V1: no se recorta' % (f0, f1))
        return None
    src0 = int(v1.GetLeftOffset()) + (f0 - v1.GetStart())
    r = mp.AppendToTimeline([{'mediaPoolItem': v1.GetMediaPoolItem(), 'startFrame': src0, 'endFrame': src0 + (f1 - f0) - 1,
                              'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
    if not r:
        return None
    it = r[0]
    _copiar_transformacion(v1, it)
    for n in list(it.GetFusionCompNameList() or []):
        try:
            it.DeleteFusionCompByName(n)
        except Exception:
            pass
    if not it.ImportFusionComp(p['comp']):
        print('  Resolve no aceptó la composición del Magic Mask')
        tl.DeleteClips([it], False)
        return None
    nombres = it.GetFusionCompNameList() or []
    if nombres:
        try:
            it.RenameFusionCompByName(nombres[-1], NOMBRE_COMP)
            it.LoadFusionCompByName(NOMBRE_COMP)
        except Exception:
            pass
    return it


def _broll(tl, mp, caja, tomas, base, pista):
    """Las tomas de stock en PRO-BROLL (debajo de todo lo PRO y de los captions), llenando el cuadro."""
    fps = float(tl.GetSetting('timelineFrameRate') or 30)
    puestas, fin = 0, -1
    for ev in sorted(tomas or [], key=lambda e: int(e['ini'])):
        clip = _importar(mp, caja, ev['archivo'])
        if clip is None:
            continue
        try:
            frames = int(float(clip.GetClipProperty('Frames') or 0))
            fps_clip = float(clip.GetClipProperty('FPS') or fps)
        except Exception:
            frames, fps_clip = 0, fps
        frames = min(frames, int(round(float(ev.get('dur') or 2.0) * fps_clip)))
        ini = base + int(ev['ini'])
        if frames <= 1 or ini < fin:
            continue
        r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': frames - 1, 'recordFrame': ini, 'trackIndex': pista, 'mediaType': 1}]) or []
        if not r:
            continue
        fin = r[0].GetEnd()
        try:
            r[0].SetProperty('Scaling', getattr(resolve, 'SCALE_FILL', 3))        # la toma llena el cuadro (recorta lo que sobre)
            r[0].SetName('PRO · B-roll ' + str(ev.get('palabra') or ''))
        except Exception:
            pass
        puestas += 1
    return puestas


def _pistas_captions(tl):
    """Las pistas de los captions (y sus emojis): las que hay encima de las PRO que no son de PRO ni de los Efectos."""
    n = int(tl.GetTrackCount('video') or 0)
    tope = max([i for i in range(1, n + 1) if str(tl.GetTrackName('video', i) or '') in ORDEN] or [1])
    return [i for i in range(tope + 1, n + 1) if not str(tl.GetTrackName('video', i) or '').startswith(('PRO-', 'FX-'))]


def _deshacer_subidas(tl):
    """Re-aplicar no apila: los captions que subió una corrida anterior (llevan la marca) vuelven a su sitio si siguen donde se dejaron, y los
    emojis que se apagaron por un icono 3D se vuelven a encender."""
    vueltos = 0
    for i in _pistas_captions(tl):
        for it in tl.GetItemListInTrack('video', i) or []:
            try:
                marcas = it.GetMarkers() or {}
            except Exception:
                continue
            for m in marcas.values():
                dato = str(m.get('customData') or '')
                if dato == MARCA_EMOJI:
                    try:
                        it.SetClipEnabled(True)
                        it.DeleteMarkerByCustomData(dato)
                    except Exception:
                        pass
                    continue
                if not dato.startswith(MARCA + ':'):
                    continue
                try:
                    antes, despues = (float(x) for x in dato.split(':')[1:3])
                    if abs(float(it.GetProperty('Tilt') or 0.0) - despues) < 0.5 and it.SetProperty('Tilt', antes):
                        vueltos += 1
                    it.DeleteMarkerByCustomData(dato)
                except Exception:
                    pass
    return vueltos


def _poner_tilt(it, nuevo):
    """Pone el Tilt de un clip de captions y deja (o actualiza) la marca con su Tilt ORIGINAL, para que re-aplicar lo devuelva a su sitio."""
    try:
        original = float(it.GetProperty('Tilt') or 0.0)
        for m in list((it.GetMarkers() or {}).values()):
            dato = str(m.get('customData') or '')
            if dato.startswith(MARCA + ':'):
                original = float(dato.split(':')[1])
                it.DeleteMarkerByCustomData(dato)
        if it.SetProperty('Tilt', float(nuevo)):
            it.AddMarker(0, 'Sand', 'PRO · captions movidos', '', 1, '%s:%.3f:%.3f' % (MARCA, original, float(nuevo)))
            return True
    except Exception:
        pass
    return False


def _subir_captions(tl, cues, base):
    """Sube (Tilt) los clips de los captions que EMPIEZAN dentro de cada bloque y les deja la marca. Devuelve cuántos movió."""
    clips = [(it.GetStart(), it) for i in _pistas_captions(tl) for it in tl.GetItemListInTrack('video', i) or []]
    movidos = 0
    for c in cues:
        f0, f1, d = base + int(c['ini']), base + int(c['fin']), float(c['subir'])
        if abs(d) < 0.5:
            continue
        for s, it in clips:
            if f0 - 1 <= s < f1 and _poner_tilt(it, float(it.GetProperty('Tilt') or 0.0) + d):
                movidos += 1
    return movidos


def _emojis_sin_cara(tl, cues, base):
    """REGLA DEL USUARIO: ningún emoji tapa una cara. Los emojis de cada bloque (ya movido) que caen sobre una de sus 'caras' bajan debajo de
    la barbilla o suben encima de la cabeza (lo que quede más cerca dentro del cuadro). Devuelve cuántos apartó."""
    W = float(tl.GetSetting('timelineResolutionWidth') or 1080)
    H = float(tl.GetSetting('timelineResolutionHeight') or 1920)
    emojis = [(it.GetStart(), it) for i in _pistas_captions(tl) if 'EMOJI' in str(tl.GetTrackName('video', i) or '').upper()
              for it in tl.GetItemListInTrack('video', i) or []]
    r, aire, apartados = 0.045, 0.015, 0
    for c in cues:
        caras = c.get('caras') or []
        if not caras:
            continue
        f0, f1 = base + int(c['ini']), base + int(c['fin'])
        for s, it in emojis:
            if not (f0 - 1 <= s < f1):
                continue
            try:
                x = 0.5 + float(it.GetProperty('Pan') or 0.0) / W
                y = 0.5 - float(it.GetProperty('Tilt') or 0.0) / H
            except Exception:
                continue
            malas = [k for k in caras if k[0] - r < x < k[2] + r and k[1] - r < y < k[3] + r]
            if not malas:
                continue
            opciones = [max(k[3] for k in malas) + r + aire, min(k[1] for k in malas) - r - aire]
            opciones = [o for o in opciones if 0.04 + r <= o <= 0.96 - r]
            if opciones and _poner_tilt(it, (0.5 - min(opciones, key=lambda o: abs(o - y))) * H):
                apartados += 1
    return apartados


def _encima(tl, mp, caja, tramos, base, decir, cache):
    """Los captions DETRÁS de la persona: la persona recortada en PRO-ENCIMA (la pista de más arriba) en cada tramo, su velo suave en
    PRO-VELO y la pila de los captions subida hasta la coronilla. Un tramo cuyo Magic Mask no termina de rastrear se quita entero.
    Devuelve (tramos puestos, clips de captions movidos)."""
    i = _indice(tl, PISTA_ENCIMA)
    if i is not None:
        _vaciar(tl, i)
        if i != int(tl.GetTrackCount('video')) or not tramos:      # siempre la de MÁS ARRIBA (encima de los captions)
            tl.DeleteTrack('video', i)
            i = None
    if not tramos:
        return 0, 0
    if i is None:
        tl.AddTrack('video')
        i = int(tl.GetTrackCount('video'))
        tl.SetTrackName('video', i, PISTA_ENCIMA)
    puestos, fin = [], -1
    for t in sorted(tramos, key=lambda t: int(t['ini'])):
        f0, f1 = base + int(t['ini']), base + int(t['fin'])
        if f1 - f0 < 6 or f0 < fin:
            continue
        it = _poner_persona(tl, mp, caja, t, f0, f1, i)
        if it is None:
            continue
        fin = it.GetEnd()
        try:
            it.SetName('PRO · persona encima')
            it.SetClipColor('Orange')
        except Exception:
            pass
        if cache:
            _cache(it)
        puestos.append((t, it))
    magic = [(k, it, int(t.get('ref') or 0), t.get('herramienta') or 'CCProMagic') for k, (t, it) in enumerate(puestos) if t.get('modo') != 'clip']
    oks = _rastrear(tl, [(it, ref, h) for _k, it, ref, h in magic], i, decir) if magic else []
    fallidos = {k for (k, _it, _ref, _h), ok in zip(magic, oks) if not ok}
    idx_velo = _indice(tl, 'PRO-VELO')
    velos = [(x.GetStart(), x.GetEnd()) for x in (tl.GetItemListInTrack('video', idx_velo) or [])] if idx_velo else []
    hechos, movidos = 0, 0
    for k, (t, it) in enumerate(puestos):
        if k in fallidos:
            tl.DeleteClips([it], False)                                 # sin la persona bien recortada, los captions se quedan donde estaban
            continue
        movidos += _subir_captions(tl, t.get('cues') or [], base)
        hechos += 1
        f0, f1 = it.GetStart(), it.GetEnd()
        if t.get('velo') and idx_velo and not any(a < f1 and f0 < b for a, b in velos):
            clip = _importar(mp, caja, t['velo'])
            r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'trackIndex': idx_velo, 'recordFrame': f0}]) or [] if clip else []
            if r:
                velos.append((r[0].GetStart(), r[0].GetEnd()))
                try:
                    r[0].SetName('PRO · velo de los captions')
                except Exception:
                    pass
    return hechos, movidos


def _pista_iconos(tl, hace_falta):
    """PRO-ICONOS, vacía, encima de los captions (se crea al final; PRO-ENCIMA, si hace falta, va después y queda por encima)."""
    i = _indice(tl, PISTA_ICONOS)
    if i is not None:
        _vaciar(tl, i)
        return i
    if not hace_falta:
        return None
    tl.AddTrack('video')
    i = int(tl.GetTrackCount('video'))
    tl.SetTrackName('video', i, PISTA_ICONOS)
    return i


def _apagar_emojis(tl, ventanas, base):
    """Apaga (con marca, para re-aplicar) el emoji del tema en los bloques donde va un icono 3D: uno solo, el 3D."""
    apagados = 0
    for i in _pistas_captions(tl):
        if 'EMOJI' not in str(tl.GetTrackName('video', i) or '').upper():
            continue
        for it in tl.GetItemListInTrack('video', i) or []:
            s = int(it.GetStart())
            if any(base + int(a) <= s < base + int(b) for a, b in ventanas):
                try:
                    if it.SetClipEnabled(False):
                        it.AddMarker(0, 'Sand', 'PRO · emoji cambiado por un icono 3D', '', 1, MARCA_EMOJI)
                        apagados += 1
                except Exception:
                    pass
    return apagados


def _color_claves(tl, cc):
    """Temas 1–4 (pase ligero): la palabra DESTACADA de los captions «guion» en el color de acento del video. Solo los Text+ que entran en el
    momento de una palabra principal (cc['momentos'], fotogramas absolutos, ±3), relleno 1 (Red1/Green1/Blue1); el resto del diseño, intacto."""
    if not cc or not cc.get('momentos'):
        return 0
    r, g, b = (float(x) for x in cc['rgb'])
    momentos = sorted(int(m) for m in cc['momentos'])
    hechos = 0
    for i in _pistas_captions(tl):
        if 'EMOJI' in str(tl.GetTrackName('video', i) or '').upper():
            continue
        for it in tl.GetItemListInTrack('video', i) or []:
            s = int(it.GetStart())
            if not any(abs(s - m) <= 3 for m in momentos):
                continue
            try:
                comp = it.GetFusionCompByIndex(1)
                herramientas = list((comp.GetToolList(False, 'TextPlus') or {}).values()) if comp else []
                for h in herramientas:
                    h.SetInput('Red1', r)
                    h.SetInput('Green1', g)
                    h.SetInput('Blue1', b)
                hechos += 1 if herramientas else 0
            except Exception:
                pass
    return hechos


def _apagar_captions(tl):
    """Tema 5: los captions de verdad son las animaciones de PRO-SUBS; los Text+ (y emojis) que GO dejó de respaldo se apagan (siguen ahí, para
    encenderlos a mano si se prefieren), y también SUS sonidos (pistas de audio «SFX…»: un toque por palabra y el de cada emoji, que ya no se ven).
    Un GO nuevo los vuelve a poner."""
    apagados = 0
    for i in _pistas_captions(tl):
        for it in tl.GetItemListInTrack('video', i) or []:
            try:
                if it.GetClipEnabled() and it.SetClipEnabled(False):
                    apagados += 1
            except Exception:
                pass
    for i in range(1, int(tl.GetTrackCount('audio') or 0) + 1):
        if not str(tl.GetTrackName('audio', i) or '').upper().startswith('SFX'):
            continue
        for it in tl.GetItemListInTrack('audio', i) or []:
            try:
                if it.GetClipEnabled() and it.SetClipEnabled(False):
                    apagados += 1
            except Exception:
                pass
    return apagados


def _detras_delante(tl, idx, f0, f1):
    """El rastreo del Magic Mask falló en [f0, f1): los captions del Tema 5 que iban DETRÁS de la persona pasan a la pista de delante (si nadie la
    ocupa ahí): sin la persona encima, una palabra enorme a la altura de la cabeza se quedaría tapando la cara."""
    i_det, i_del = idx.get('PRO-DETRAS'), idx.get('PRO-DELANTE')
    if not i_det or not i_del:
        return 0
    ocupado = [(int(x.GetStart()), int(x.GetEnd())) for x in tl.GetItemListInTrack('video', i_del) or []]
    movidos = 0
    for it in list(tl.GetItemListInTrack('video', i_det) or []):
        s, e = int(it.GetStart()), int(it.GetEnd())
        if not (s < f1 and f0 < e) or not str(it.GetName() or '').startswith('PRO · Caption'):
            continue
        mpi = it.GetMediaPoolItem()
        try:                                                           # la clave llevaba la sombra de la persona: sin persona, la limpia
            ruta = str(mpi.GetClipProperty('File Path') or '') if mpi is not None else ''
            if ruta.endswith('_sombra.mov') and os.path.exists(ruta[:-len('_sombra.mov')] + '.mov'):
                mp0 = project.GetMediaPool()
                mpi = _importar(mp0, _caja(mp0), ruta[:-len('_sombra.mov')] + '.mov') or mpi
        except Exception:
            pass
        if mpi is not None and not any(s < b and a < e for a, b in ocupado):
            r = project.GetMediaPool().AppendToTimeline([{'mediaPoolItem': mpi, 'trackIndex': i_del, 'recordFrame': s, 'mediaType': 1}]) or []
            if r:
                try:
                    r[0].SetName('PRO · Caption (delante: el rastreo falló)')
                except Exception:
                    pass
        tl.DeleteClips([it], False)
        movidos += 1
    if movidos:
        print('  rastreo incompleto en %d-%d: %d caption(s) «detrás» pasan delante' % (f0, f1, movidos))
    quitadas = 0                                                       # la órbita sin la persona encima pasaría por la cara: fuera (las dos mitades)
    for n in ('PRO-DETRAS', 'PRO-DELANTE'):
        i = idx.get(n)
        for it in list(tl.GetItemListInTrack('video', i) or []) if i else []:
            if str(it.GetName() or '').startswith('PRO · Órbita') and int(it.GetStart()) < f1 and f0 < int(it.GetEnd()):
                tl.DeleteClips([it], False)
                quitadas += 1
    if quitadas:
        print('  sin la persona recortada en %d-%d: la órbita no va' % (f0, f1))
    return movidos


def _revisar_persona(tl, idx):
    """Tras poner a la persona: lo que la NECESITA encima (la clave detrás, la órbita, el fondo gris del foco) y se quedó sin ella (el recorte
    no se pudo poner o no rastreó) se arregla: la clave pasa delante, la órbita y el gris del foco se quitan."""
    ip, ig = idx.get('PRO-PERSONA'), idx.get('PRO-GRIS')
    hay = [(int(x.GetStart()), int(x.GetEnd())) for x in (tl.GetItemListInTrack('video', ip) or [])] if ip else []

    def cubierto(s, e):
        return any(a <= s + 2 and e - 2 <= b for a, b in hay)
    arreglos, tramos = 0, []
    for it in list(tl.GetItemListInTrack('video', idx.get('PRO-DETRAS')) or []) if idx.get('PRO-DETRAS') else []:
        nombre = str(it.GetName() or '')
        s, e = int(it.GetStart()), int(it.GetEnd())
        if (nombre.startswith('PRO · Caption') or nombre.startswith('PRO · Órbita')) and not cubierto(s, e):
            tramos.append((s, e))
    for s, e in tramos:
        arreglos += 1
        _detras_delante(tl, idx, s, e)
    for it in list(tl.GetItemListInTrack('video', ig) or []) if ig else []:
        if str(it.GetName() or '') == NOMBRE_FOCO and not cubierto(int(it.GetStart()), int(it.GetEnd())):
            tl.DeleteClips([it], False)
            arreglos += 1
    return arreglos


def _comp_zoom(ruta, n, sale):
    """La media transición con zoom (Fusion): MediaIn → Transform con desenfoque de movimiento → MediaOut, `n` fotogramas. Hacia el corte
    (sale=False) acerca cada vez más rápido; tras el corte (sale=True) llega acercado y vuelve a su sitio frenando. El desenfoque lo da el
    propio movimiento (MotionBlur del Transform)."""
    n = max(2, int(n))
    if sale:
        claves = '[0] = { 1.28, RH = { %.3f, 1.12 } }, [%d] = { 1.0, LH = { %.3f, 1.0 } }' % (n * 0.25, n - 1, (n - 1) * 0.55)
    else:
        claves = '[0] = { 1.0, RH = { %.3f, 1.0 } }, [%d] = { 1.28, LH = { %.3f, 1.12 } }' % (n * 0.45, n - 1, (n - 1) * 0.75)
    texto = '''Composition {
	CurrentTime = 0,
	Tools = ordered() {
		MediaIn1 = MediaIn { ViewInfo = OperatorInfo { Pos = { 0, 50 } }, },
		CCZoom = Transform {
			Inputs = {
				Size = Input { SourceOp = "CCZoomSize", Source = "Value", },
				MotionBlur = Input { Value = 1, },
				Quality = Input { Value = 9, },
				ShutterAngle = Input { Value = 300, },
				Input = Input { SourceOp = "MediaIn1", Source = "Output", },
			},
			ViewInfo = OperatorInfo { Pos = { 110, 50 } },
		},
		CCZoomSize = BezierSpline {
			SplineColor = { Red = 225, Green = 0, Blue = 225 },
			NameSet = true,
			KeyFrames = { %s }
		},
		MediaOut1 = MediaOut {
			Inputs = {
				Index = Input { Value = "0", },
				Input = Input { SourceOp = "CCZoom", Source = "Output", },
			},
			ViewInfo = OperatorInfo { Pos = { 220, 50 } },
		},
	},
}
''' % claves
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(texto)
    return ruta


def _zoom(tl, mp, cortes, base, pista):
    """Tema 5: la transición con zoom en cada corte [fotograma, n antes, n después]: dos copias de V1 (lo de antes del corte y lo de después) en
    PRO-ZOOM, cada una con su media transición de Fusion y la transformación de V1. Nunca sobre un clip con el movimiento de Efectos."""
    puestas = 0
    for c in cortes or []:
        f, antes, despues = base + int(c[0]), int(c[1]), int(c[2])
        for f0, f1, sale in ((f - antes, f, False), (f, f + despues, True)):
            v1 = _clip_v1(tl, f0, f1)
            if v1 is None or 'CineCaptions FX' in (v1.GetFusionCompNameList() or []):
                continue
            src0 = int(v1.GetLeftOffset()) + (f0 - v1.GetStart())
            r = mp.AppendToTimeline([{'mediaPoolItem': v1.GetMediaPoolItem(), 'startFrame': src0, 'endFrame': src0 + (f1 - f0) - 1,
                                      'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
            if not r:
                continue
            it = r[0]
            _copiar_transformacion(v1, it)
            for nombre in list(it.GetFusionCompNameList() or []):
                try:
                    it.DeleteFusionCompByName(nombre)
                except Exception:
                    pass
            comp = _comp_zoom(os.path.join(tempfile.gettempdir(), 'ccpro_zoom_%d_%d.comp' % (f0, int(sale))), f1 - f0, sale)
            if not it.ImportFusionComp(comp):
                tl.DeleteClips([it], False)
                continue
            try:
                nombres = it.GetFusionCompNameList() or []
                if nombres:
                    it.RenameFusionCompByName(nombres[-1], NOMBRE_ZOOM)
                    it.LoadFusionCompByName(NOMBRE_ZOOM)
                it.SetName('PRO · transición con zoom')
                it.SetClipColor('Purple')
            except Exception:
                pass
            _cache(it)
            puestas += 1
    return puestas


def _dividida(tl, mp, tramos, base, pista):
    """Tema 5, pantalla dividida: una copia del clip de V1 de ese tramo, encima de él y BAJADA (Tilt) para que la persona quede en la mitad de
    abajo; la mitad de arriba la tapa la escena de papel (PRO-FONDO, encima). [[f0, f1, píxeles que baja]]."""
    puestas = 0
    for g in tramos or []:
        f0, f1 = base + int(g[0]), base + int(g[1])
        v1 = _clip_v1(tl, f0, f1)
        if v1 is None or 'CineCaptions FX' in (v1.GetFusionCompNameList() or []):
            continue
        src0 = int(v1.GetLeftOffset()) + (f0 - v1.GetStart())
        r = mp.AppendToTimeline([{'mediaPoolItem': v1.GetMediaPoolItem(), 'startFrame': src0, 'endFrame': src0 + (f1 - f0) - 1,
                                  'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
        if not r:
            continue
        it = r[0]
        _copiar_transformacion(v1, it)
        try:
            it.SetProperty('Tilt', float(it.GetProperty('Tilt') or 0.0) - float(g[2]))
            it.SetName('PRO · pantalla dividida')
            it.SetClipColor('Navy')
        except Exception:
            pass
        puestas += 1
    return puestas


def _gris(tl, mp, tramos, base, pista, nombre='PRO · gris', luz='1.0'):
    """«Modo error»: el plano en gris un momento (cuando dice algo malo o se equivoca). Una copia del clip de V1 de ese tramo, encima, sin
    saturación (SetCDL) y con la misma transformación. No va sobre un clip con el movimiento de Efectos. Tema 5 («foco»): lo mismo, algo más
    oscuro (`luz`), con la persona A COLOR encima (PRO-PERSONA); si la persona no queda, `_revisar_persona` lo quita."""
    puestos = 0
    for g in tramos or []:
        f0, f1 = base + int(g[0]), base + int(g[1])
        v1 = _clip_v1(tl, f0, f1)
        if v1 is None or 'CineCaptions FX' in (v1.GetFusionCompNameList() or []):
            continue
        src0 = int(v1.GetLeftOffset()) + (f0 - v1.GetStart())
        r = mp.AppendToTimeline([{'mediaPoolItem': v1.GetMediaPoolItem(), 'startFrame': src0, 'endFrame': src0 + (f1 - f0) - 1,
                                  'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
        if not r:
            continue
        it = r[0]
        _copiar_transformacion(v1, it)
        try:
            ok = it.SetCDL({'NodeIndex': '1', 'Slope': '%s %s %s' % (luz, luz, luz), 'Offset': '0.0 0.0 0.0', 'Power': '1.0 1.0 1.0', 'Saturation': '0.0'})
            it.SetName(nombre)
            it.SetClipColor('Chocolate')
            _cache_color(it)
        except Exception:
            ok = False
        if not ok:
            tl.DeleteClips([it], False)
            continue
        puestos += 1
    return puestos


def _sonidos(tl, mp, caja, eventos, base):
    """El diseño de sonido: cada familia en su pista de audio (PRO-WHOOSH · PRO-TEXTURA · PRO-RISER · PRO-HIT), clips enteros, cada uno con su
    nivel (Volume). En una misma pista no se pisan (el que llega después se salta). Las pistas PRO de audio de antes se vacían o se quitan."""
    fps = float(tl.GetSetting('timelineFrameRate') or 30)
    por_pista = {}
    for ev in eventos or []:
        por_pista.setdefault(ev.get('pista') or PISTA_SONIDO, []).append(ev)
    for n in [PISTA_SONIDO] + PISTAS_AUDIO:                               # las de la corrida anterior que ya no hacen falta, fuera
        i = _indice(tl, n, 'audio')
        if i:
            _vaciar(tl, i, 'audio')
            if n not in por_pista:
                try:
                    tl.DeleteTrack('audio', i)
                except Exception:
                    pass
    puestos = 0
    for nombre in [n for n in PISTAS_AUDIO + [PISTA_SONIDO] if n in por_pista]:
        i = _indice(tl, nombre, 'audio')
        if not i:
            try:
                tl.AddTrack('audio', 'stereo')
            except Exception:
                tl.AddTrack('audio')
            i = int(tl.GetTrackCount('audio'))
            tl.SetTrackName('audio', i, nombre)
        fin = -1
        for ev in sorted(por_pista[nombre], key=lambda e: int(e['ini'])):
            clip = _importar(mp, caja, ev['archivo'])
            ini = base + int(ev['ini'])
            frames = max(2, int(round(float(ev.get('dur') or 1.0) * fps)))
            if clip is None or ini < fin:
                continue
            r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': frames - 1, 'recordFrame': ini, 'trackIndex': i, 'mediaType': 2}]) or []
            if r:
                fin = ini + frames
                puestos += 1
                db = float(ev.get('db', 0.0))                       # v5.4.52: el volumen ya va DENTRO del archivo (edicion_pro._con_ganancia): 0 dB
                if abs(db) > 0.05:                                  # (un plan viejo con nivel de clip: 'AudioVolume' en Resolve 21)
                    try:
                        r[0].SetProperty('AudioVolume', db) or r[0].SetProperty('Volume', db)
                    except Exception:
                        pass
    return puestos


def main():
    with open(RUTA_JSON, encoding='utf-8') as f:
        datos = json.load(f)
    tl = project.GetCurrentTimeline()
    if tl is None:
        raise SystemExit('no hay un timeline activo en Resolve')
    mp = project.GetMediaPool()
    caja = _caja(mp)
    base = int(datos.get('inicio') if datos.get('inicio') is not None else tl.GetStartFrame())
    v1_antes = len(tl.GetItemListInTrack('video', 1) or [])
    decir = lambda t: print(t)
    resolve.OpenPage('edit')
    if datos.get('cache', True):
        _modo_cache()
    idx = _pistas(tl)
    idx[PISTA_ICONOS] = _pista_iconos(tl, any(g.get('capa') == 'iconos' for g in datos.get('graficos') or []))
    puestos = {'fondo': 0, 'velo': 0, 'detras': 0, 'delante': 0, 'persona': 0, 'iconos': 0, 'subs': 0}
    sin_poner = 0
    fin_pista = {n: -1 for n in ORDEN + [PISTA_ICONOS]}
    # 1) los gráficos OGraf
    for g in sorted(datos.get('graficos') or [], key=lambda g: int(g['ini'])):
        pista = CAPA.get(g.get('capa'), 'PRO-DELANTE')
        if idx.get(pista) is None:
            sin_poner += 1
            continue
        clip = _importar(mp, caja, g['archivo'])
        ini = base + int(g['ini'])
        if clip is None:
            print('  no pude importar %s' % os.path.basename(g['archivo']))
            sin_poner += 1
            continue
        if ini < fin_pista[pista]:
            sin_poner += 1
            continue
        if g.get('alfa'):                                                  # animación de Remotion: ProRes 4444 con alfa recto, solo video
            try:
                clip.SetClipProperty('Alpha mode', 'Straight')
            except Exception:
                pass
            r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'trackIndex': idx[pista], 'recordFrame': ini, 'mediaType': 1}]) or []
        else:
            r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'trackIndex': idx[pista], 'recordFrame': ini}]) or []
        if not r:
            sin_poner += 1
            continue
        fin_pista[pista] = r[0].GetEnd()
        try:
            r[0].SetName(g.get('nombre') or os.path.basename(g['archivo']))
        except Exception:
            pass
        if datos.get('cache', True):
            _cache(r[0])
        puestos[g.get('capa', 'delante')] = puestos.get(g.get('capa', 'delante'), 0) + 1
    # 2) el B-roll de stock, debajo de todo; y el «modo error» en gris
    tomas = _broll(tl, mp, caja, datos.get('broll') or [], base, idx['PRO-BROLL'])
    grises = _gris(tl, mp, datos.get('gris') or [], base, idx['PRO-GRIS'])
    focos = _gris(tl, mp, datos.get('gris_foco') or [], base, idx['PRO-GRIS'], NOMBRE_FOCO, '0.8')
    divididas = _dividida(tl, mp, datos.get('dividida') or [], base, idx['PRO-GRIS'])
    if divididas:
        print('Tema 5: %d tramos en pantalla dividida.' % divididas)
    # 3) la persona (el mismo clip de V1 recortado), encima de lo que va DETRÁS; antes, los punch-ins de V1 (el recorte copia su zoom) y las
    #    transiciones con zoom (copias de V1 con su zoom)
    punch = _punch_ins(tl, datos.get('punch') or [])
    zooms = _zoom(tl, mp, datos.get('zoom') or [], base, idx['PRO-ZOOM'])
    if zooms:
        print('Tema 5: %d medias transiciones con zoom.' % zooms)
    magic = []
    for p in sorted(datos.get('persona') or [], key=lambda p: int(p['ini'])):
        f0, f1 = base + int(p['ini']), base + int(p['fin'])
        v1 = _clip_v1(tl, f0, f1)
        f1 = max(f1, min(_fin_detras(tl, idx, f0), int(v1.GetEnd()) if v1 is not None else f1))
        if f1 - f0 < 6 or f0 < fin_pista['PRO-PERSONA']:
            continue
        it = _poner_persona(tl, mp, caja, p, f0, f1, idx['PRO-PERSONA'])
        if it is None:
            continue
        if p.get('modo') != 'clip':
            magic.append((it, int(p.get('ref') or 0), p.get('herramienta') or 'CCProMagic'))
        fin_pista['PRO-PERSONA'] = it.GetEnd()
        try:
            it.SetName('PRO · persona')
            it.SetClipColor('Orange')
        except Exception:
            pass
        if datos.get('cache', True):
            _cache(it)
        puestos['persona'] += 1
    oks = _rastrear(tl, magic, idx['PRO-PERSONA'], decir) if magic else []
    for (it, _ref, _h), ok in zip(magic, oks):
        if not ok:                                                         # sin recortar taparía el titular: fuera (el titular queda delante)
            f0, f1 = int(it.GetStart()), int(it.GetEnd())
            tl.DeleteClips([it], False)
            puestos['persona'] -= 1
            _detras_delante(tl, idx, f0, f1)
    rastreados = sum(oks)
    arreglos = _revisar_persona(tl, idx)                                   # lo que necesitaba a la persona encima y se quedó sin ella
    if focos or arreglos:
        print('Tema 5: %d tramos con el fondo en blanco y negro; %d piezas sin la persona encima, arregladas.' % (focos, arreglos))
    # 4) los captions DETRÁS de la persona (la persona en la pista de más arriba)
    _deshacer_subidas(tl)                                                  # re-aplicar no apila: primero, todo a su sitio
    detras, movidos = _encima(tl, mp, caja, datos.get('encima') or [], base, decir, datos.get('cache', True))
    # 4b) el resto de los captions, fuera de las caras; y ningún emoji encima de una cara
    movidos += _subir_captions(tl, datos.get('mover') or [], base)
    emojis = _emojis_sin_cara(tl, [c for e in datos.get('encima') or [] for c in e.get('cues') or []] + list(datos.get('mover') or []), base)
    cambiados = _apagar_emojis(tl, datos.get('sin_emoji') or [], base) if puestos.get('iconos') else 0
    respaldo = _apagar_captions(tl) if datos.get('captions_propios') and puestos.get('subs') else 0
    coloreados = _color_claves(tl, datos.get('color_claves'))
    if coloreados:
        print('Temas 1–4: %d palabras destacadas en el color del video.' % coloreados)
    # 5) los sonidos de los gráficos
    sonidos = _sonidos(tl, mp, caja, datos.get('sonidos') or [], base)
    _quitar_vacias(tl)
    try:
        tl.SetCurrentTimecode(_tc(tl, tl.GetStartFrame()))
    except Exception:
        pass
    total = puestos['fondo'] + puestos['velo'] + puestos['detras'] + puestos['delante'] + puestos['iconos'] + puestos['subs']
    if puestos['subs']:
        print('Tema 5: %d captions animados (%d Text+ de respaldo apagados).' % (puestos['subs'], respaldo))
    print('Edición PRO: %d gráficos (%d detrás, %d delante, %d escenas, %d velos), %d recortes de persona%s, captions detrás de la persona en %d tramos '
          '(%d clips movidos, %d emojis apartados de la cara), %d iconos 3D (%d emojis cambiados), %d tramos en gris, %d tomas de B-roll, '
          '%d punch-ins, %d sonidos%s.' % (
              total, puestos['detras'], puestos['delante'], puestos['fondo'], puestos['velo'], puestos['persona'],
              (' (%d con Magic Mask)' % rastreados) if magic else '', detras, movidos, emojis, puestos['iconos'], cambiados, grises, tomas, punch, sonidos, (', %d sin poner' % sin_poner) if sin_poner else ''))
    if len(tl.GetItemListInTrack('video', 1) or []) < v1_antes:
        raise SystemExit('ATENCION: V1 perdió clips al colocar la Edición PRO')
    if total == 0 and datos.get('graficos'):
        raise SystemExit('Resolve no colocó ningún gráfico de la Edición PRO')
