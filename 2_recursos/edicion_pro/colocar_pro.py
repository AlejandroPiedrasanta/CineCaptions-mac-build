# CineCaptions · By Cinema Productions
# 2_recursos/edicion_pro/colocar_pro.py — corre DENTRO de Resolve: pone la Edición PRO en el timeline (gráficos OGraf, la persona con Magic Mask, sonidos).
"""
Lo lanza edicion_pro.aplicar() (resolve_mcp.ejecutar_py) y lee ~/DaVinciSubtitles/edicion_pro_plan.json:

    {'fps', 'inicio', 'graficos': [{'capa': 'fondo'|'velo'|'detras'|'delante', 'ini': fotograma (desde 'inicio'), 'archivo': .ograf (ruta larga), 'nombre'}],
     'persona': [{'ini', 'fin', 'modo': 'magic'|'clip', 'comp': .comp | 'archivo': .mov, 'ref': fotograma del clip}],
     'broll': [{'ini', 'dur': segundos, 'archivo': .mp4, 'palabra'}],
     'encima': [{'ini', 'fin', 'modo', 'comp'|'archivo', 'ref', 'velo': .ograf, 'cues': [{'ini', 'fin', 'subir': píxeles hacia arriba}]}],
     'sonidos': [{'ini': fotograma, 'archivo': .wav, 'dur': segundos}], 'cache': True}

Pistas (de abajo arriba, justo encima de V1 / FX-BROLL y DEBAJO de los captions, que siguen mandando):
PRO-BROLL · PRO-FONDO · PRO-VELO · PRO-DETRAS · PRO-PERSONA · PRO-DELANTE; el audio en «PRO-SONIDO». Cada corrida vacía y rellena sus pistas
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
ORDEN = ['PRO-BROLL', 'PRO-FONDO', 'PRO-VELO', 'PRO-DETRAS', 'PRO-PERSONA', 'PRO-DELANTE']
CAPA = {'fondo': 'PRO-FONDO', 'velo': 'PRO-VELO', 'detras': 'PRO-DETRAS', 'delante': 'PRO-DELANTE'}
PISTA_ENCIMA = 'PRO-ENCIMA'
MARCA = 'ccpro-subir'                    # marca en cada clip de captions que se subió: 'ccpro-subir:<Tilt antes>:<Tilt después>'
PISTA_SONIDO = 'PRO-SONIDO'
BIN = 'RCS · Edición PRO'
NOMBRE_COMP = 'CineCaptions PRO · persona'
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
    for n in ORDEN + [PISTA_ENCIMA]:
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


def _poner_persona(tl, mp, caja, p, f0, f1, pista):
    """El recorte de la persona de f0 a f1 en `pista`: el ProRes con alfa de la IA local ('clip') o el mismo clip de V1 con la composición del Magic Mask."""
    if p.get('modo') == 'clip':
        clip = _importar(mp, caja, p['archivo'])
        if clip is None:
            return None
        try:
            clip.SetClipProperty('Alpha mode', 'Straight')
        except Exception:
            pass
        r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': f1 - f0 - 1, 'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
        return r[0] if r else None
    v1 = _clip_v1(tl, f0, f1)
    if v1 is None:
        print('  la persona de %d a %d cruza un corte de V1: no se recorta' % (f0, f1))
        return None
    src0 = int(v1.GetLeftOffset()) + (f0 - v1.GetStart())
    r = mp.AppendToTimeline([{'mediaPoolItem': v1.GetMediaPoolItem(), 'startFrame': src0, 'endFrame': src0 + (f1 - f0) - 1,
                              'recordFrame': f0, 'trackIndex': pista, 'mediaType': 1}]) or []
    if not r:
        return None
    it = r[0]
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
    """Re-aplicar no apila: los captions que subió una corrida anterior (llevan la marca) vuelven a su sitio si siguen donde se dejaron."""
    vueltos = 0
    for i in _pistas_captions(tl):
        for it in tl.GetItemListInTrack('video', i) or []:
            try:
                marcas = it.GetMarkers() or {}
            except Exception:
                continue
            for m in marcas.values():
                dato = str(m.get('customData') or '')
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


def _subir_captions(tl, cues, base):
    """Sube (Tilt) los clips de los captions que EMPIEZAN dentro de cada bloque y les deja la marca. Devuelve cuántos movió."""
    clips = [(it.GetStart(), it) for i in _pistas_captions(tl) for it in tl.GetItemListInTrack('video', i) or []]
    movidos = 0
    for c in cues:
        f0, f1, d = base + int(c['ini']), base + int(c['fin']), float(c['subir'])
        for s, it in clips:
            if f0 - 1 <= s < f1:
                try:
                    antes = float(it.GetProperty('Tilt') or 0.0)
                    if it.SetProperty('Tilt', antes + d):
                        movidos += 1
                        it.AddMarker(0, 'Sand', 'PRO · detrás de la persona', '', 1, '%s:%.3f:%.3f' % (MARCA, antes, antes + d))
                except Exception:
                    pass
    return movidos


def _encima(tl, mp, caja, tramos, base, decir, cache):
    """Los captions DETRÁS de la persona: la persona recortada en PRO-ENCIMA (la pista de más arriba) en cada tramo, su velo suave en
    PRO-VELO y la pila de los captions subida hasta la coronilla. Un tramo cuyo Magic Mask no termina de rastrear se quita entero.
    Devuelve (tramos puestos, clips de captions movidos)."""
    _deshacer_subidas(tl)
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


def _sonidos(tl, mp, caja, eventos, base):
    if not eventos:
        i = _indice(tl, PISTA_SONIDO, 'audio')
        if i:
            _vaciar(tl, i, 'audio')
            try:
                tl.DeleteTrack('audio', i)
            except Exception:
                pass
        return 0
    i = _indice(tl, PISTA_SONIDO, 'audio')
    if i:
        _vaciar(tl, i, 'audio')
    else:
        try:
            tl.AddTrack('audio', 'stereo')
        except Exception:
            tl.AddTrack('audio')
        i = int(tl.GetTrackCount('audio'))
        tl.SetTrackName('audio', i, PISTA_SONIDO)
    fps = float(tl.GetSetting('timelineFrameRate') or 30)
    puestos, fin = 0, -1
    for ev in sorted(eventos, key=lambda e: int(e['ini'])):
        clip = _importar(mp, caja, ev['archivo'])
        ini = base + int(ev['ini'])
        frames = max(2, int(round(float(ev.get('dur') or 1.0) * fps)))
        if clip is None or ini < fin:
            continue
        r = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': frames - 1, 'recordFrame': ini, 'trackIndex': i, 'mediaType': 2}]) or []
        if r:
            fin = ini + frames
            puestos += 1
            try:
                r[0].SetProperty('Volume', float(ev.get('db', -9.0)))      # Resolve 21.1: propiedades de audio del clip
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
    idx = _pistas(tl)
    puestos = {'fondo': 0, 'velo': 0, 'detras': 0, 'delante': 0, 'persona': 0}
    sin_poner = 0
    fin_pista = {n: -1 for n in ORDEN}
    # 1) los gráficos OGraf
    for g in sorted(datos.get('graficos') or [], key=lambda g: int(g['ini'])):
        pista = CAPA.get(g.get('capa'), 'PRO-DELANTE')
        clip = _importar(mp, caja, g['archivo'])
        ini = base + int(g['ini'])
        if clip is None:
            print('  no pude importar %s' % os.path.basename(g['archivo']))
            sin_poner += 1
            continue
        if ini < fin_pista[pista]:
            sin_poner += 1
            continue
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
    # 2) el B-roll de stock, debajo de todo
    tomas = _broll(tl, mp, caja, datos.get('broll') or [], base, idx['PRO-BROLL'])
    # 3) la persona (el mismo clip de V1 recortado), encima de lo que va DETRÁS
    magic = []
    for p in sorted(datos.get('persona') or [], key=lambda p: int(p['ini'])):
        f0, f1 = base + int(p['ini']), base + int(p['fin'])
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
            tl.DeleteClips([it], False)
            puestos['persona'] -= 1
    rastreados = sum(oks)
    # 4) los captions DETRÁS de la persona (la persona en la pista de más arriba)
    detras, movidos = _encima(tl, mp, caja, datos.get('encima') or [], base, decir, datos.get('cache', True))
    # 5) los sonidos de los gráficos
    sonidos = _sonidos(tl, mp, caja, datos.get('sonidos') or [], base)
    _quitar_vacias(tl)
    try:
        tl.SetCurrentTimecode(_tc(tl, tl.GetStartFrame()))
    except Exception:
        pass
    total = puestos['fondo'] + puestos['velo'] + puestos['detras'] + puestos['delante']
    print('Edición PRO: %d gráficos (%d detrás, %d delante, %d escenas, %d velos), %d recortes de persona%s, captions detrás de la persona en %d tramos '
          '(%d clips subidos), %d tomas de B-roll, %d sonidos%s.' % (
              total, puestos['detras'], puestos['delante'], puestos['fondo'], puestos['velo'], puestos['persona'],
              (' (%d con Magic Mask)' % rastreados) if magic else '', detras, movidos, tomas, sonidos, (', %d sin poner' % sin_poner) if sin_poner else ''))
    if len(tl.GetItemListInTrack('video', 1) or []) < v1_antes:
        raise SystemExit('ATENCION: V1 perdió clips al colocar la Edición PRO')
    if total == 0 and datos.get('graficos'):
        raise SystemExit('Resolve no colocó ningún gráfico de la Edición PRO')
