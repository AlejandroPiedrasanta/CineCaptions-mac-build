# CineCaptions · By Cinema Productions
# 2_recursos/efectos/colocar_efectos.py — corre DENTRO de Resolve: pone la intro, las transiciones de los cortes y los iconos flotantes en pistas propias «FX-…».
"""
Lo lanza efectos_visuales.aplicar() (resolve_mcp.ejecutar_py) y lee ~/DaVinciSubtitles/efectos_plan.json:

    {'fps': 30.0, 'inicio': <primer fotograma del timeline>, 'offset_frames': 0,
     'eventos': [{'tipo': 'intro'|'corte'|'icono'|'sonido', 'ini': segundos, 'modo': 'screen'|'normal'|'audio', 'archivo': mp4/wav | 'secuencia': {'patron', 'n'}}]}

Reglas: nunca toca V1/A1 ni las pistas de los captions; las pistas FX-INTRO / FX-CORTES / FX-ICONOS (video) y FX-SONIDO (audio, el sonido de la intro) se vacían y se vuelven a llenar en cada corrida (re-aplicar no apila
nada); los clips de una misma pista nunca se pisan; los archivos se importan una sola vez al bin «RCS · Efectos» (el prefijo «RCS · » hace que CineCaptions no lo
cuente como plantillas del usuario). Nada de InsertFusionTitleIntoTimeline ni de stills: solo importar medios y AppendToTimeline.
"""
import json
import os

RUTA_JSON = os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'efectos_plan.json')
PISTAS = {'intro': 'FX-INTRO', 'corte': 'FX-CORTES', 'icono': 'FX-ICONOS', 'numero': 'FX-NUMEROS', 'pegatina': 'FX-PEGATINAS', 'enfasis': 'FX-ENFASIS',
          'overlay': 'FX-OVERLAY', 'propio': 'FX-PROPIOS', 'outro': 'FX-OUTRO', 'broll': 'FX-BROLL'}
PISTA_SONIDO = 'FX-SONIDO'
PISTA_MUSICA = 'FX-MUSICA'
MAX_CARRILES = 8
BIN = 'RCS · Efectos'


def _norm(r):
    return os.path.normcase(os.path.normpath(str(r)))


def _buscar_clip(carpeta, buscada):
    for clip in carpeta.GetClipList() or []:
        try:
            r = clip.GetClipProperty('File Path') or ''
        except Exception:
            continue
        if r and _norm(r) == buscada:
            return clip
    for sub in carpeta.GetSubFolderList() or []:
        x = _buscar_clip(sub, buscada)
        if x is not None:
            return x
    return None


def _carpeta_efectos(mp):
    raiz = mp.GetRootFolder()
    for f in raiz.GetSubFolderList() or []:
        if f.GetName() == BIN:
            return f
    return mp.AddSubFolder(raiz, BIN) or raiz


def _importar(mp, caja, ev):
    """El clip del Media Pool de ese archivo / secuencia (se reusa si ya está)."""
    if ev.get('secuencia'):
        patron, n = str(ev['secuencia']['patron']), int(ev['secuencia']['n'])
        buscada = _norm(patron.replace('%04d', '[0001-%04d]' % n))
        pedido = [{'FilePath': patron, 'StartIndex': 1, 'EndIndex': n}]
    else:
        buscada = _norm(ev['archivo'])
        pedido = [str(ev['archivo'])]
    ya = _buscar_clip(mp.GetRootFolder(), buscada)
    if ya is not None:
        return ya
    previa = mp.GetCurrentFolder()
    try:
        mp.SetCurrentFolder(caja)
        nuevos = mp.ImportMedia(pedido)
    finally:
        try:
            mp.SetCurrentFolder(previa)
        except Exception:
            pass
    return nuevos[0] if nuevos else None


def _pista(tl, nombre, tipo='video'):
    """El índice de la pista (de video o de audio) con ese nombre (se crea si no está) y sus clips de antes ya borrados."""
    for i in range(1, int(tl.GetTrackCount(tipo) or 0) + 1):
        if tl.GetTrackName(tipo, i) == nombre:
            try:
                if tl.GetIsTrackLocked(tipo, i):
                    tl.SetTrackLock(tipo, i, False)
            except Exception:
                pass
            viejos = tl.GetItemListInTrack(tipo, i) or []
            if viejos:
                tl.DeleteClips(viejos, False)
            return i
    creada = False
    if tipo == 'audio':
        try:
            creada = bool(tl.AddTrack('audio', 'stereo'))
        except Exception:
            creada = False
    if not creada and not tl.AddTrack(tipo):
        return None
    i = int(tl.GetTrackCount(tipo))
    tl.SetTrackName(tipo, i, nombre)
    return i


def _vaciar_y_quitar(tl, nombre, tipo='video'):
    """Una pista FX de una vez anterior que ahora no lleva nada: se vacía y se quita (sin crear pistas nuevas que luego sobrarían)."""
    for i in range(int(tl.GetTrackCount(tipo) or 0), 0, -1):
        if tl.GetTrackName(tipo, i) == nombre:
            viejos = tl.GetItemListInTrack(tipo, i) or []
            if viejos:
                tl.DeleteClips(viejos, False)
            try:
                tl.DeleteTrack(tipo, i)
            except Exception:
                pass


def _quitar_si_vacia(tl, nombre, tipo='video'):
    for i in range(int(tl.GetTrackCount(tipo) or 0), 0, -1):
        if tl.GetTrackName(tipo, i) == nombre and not (tl.GetItemListInTrack(tipo, i) or []):
            try:
                tl.DeleteTrack(tipo, i)
            except Exception:
                pass


NOMBRE_COMP = 'CineCaptions FX'


def _poner_movimiento(tl, entradas):
    """La composición de Fusion de cada clip de V1 (zoom, temblor, transiciones, fondo desenfocado): se quita la de la vez anterior y se importa la nueva.
    `entradas`: [{'inicio': fotograma del clip en el timeline, 'ruta': .comp | None}]. Devuelve cuántas se pusieron."""
    puestas = 0
    por_inicio = {int(e['inicio']): e for e in entradas}
    for it in tl.GetItemListInTrack('video', 1) or []:
        e = por_inicio.get(int(it.GetStart()))
        if e is None:
            continue
        try:
            for n in list(it.GetFusionCompNameList() or []):
                if n == NOMBRE_COMP:
                    it.DeleteFusionCompByName(n)
            if not e.get('ruta'):
                continue
            antes = set(it.GetFusionCompNameList() or [])
            comp = it.ImportFusionComp(e['ruta'])
            if not comp:
                print('  Resolve no aceptó la composición de movimiento')
                continue
            nuevos = [n for n in (it.GetFusionCompNameList() or []) if n not in antes]
            if nuevos:
                try:
                    it.RenameFusionCompByName(nuevos[0], NOMBRE_COMP)
                    it.LoadFusionCompByName(NOMBRE_COMP)
                except Exception:
                    pass
            try:
                it.SetFusionOutputCache('enabled')                     # v5.5.4: se pre-renderiza en segundo plano (la reproducción, fluida)
            except Exception:
                pass
            puestas += 1
        except Exception as ex:
            print('  (movimiento sobre V1: %s)' % ex)
    return puestas


def _poner_audio(tl, mp, caja, fps, base, eventos, nombre_base):
    """Los eventos de audio (sonidos de la intro, de los cortes, del gancho…) en pistas «nombre_base», «nombre_base 2»… (A1 no se toca): cada evento va a la primera pista donde no pisa a otro.
    Devuelve (puestos, saltados)."""
    carriles = []                                                     # [{'idx', 'fin'}]
    puestos = saltados = 0
    for ev in sorted(eventos, key=lambda e: float(e['ini'])):
        clip = _importar(mp, caja, ev)
        if clip is None:
            print('  no pude importar el sonido %s' % ev.get('asset'))
            saltados += 1
            continue
        frames = max(2, int(round(float(ev.get('dur') or 1.0) * fps)))
        ini = base + int(round(float(ev['ini']) * fps))
        k = next((i for i, c in enumerate(carriles) if c['fin'] <= ini), None)
        if k is None:
            if len(carriles) >= MAX_CARRILES:
                saltados += 1
                continue
            nombre = nombre_base if not carriles else '%s %d' % (nombre_base, len(carriles) + 1)
            idx = _pista(tl, nombre, 'audio')
            if idx is None:
                print('  no pude crear la pista de audio %s' % nombre)
                saltados += 1
                continue
            carriles.append({'idx': idx, 'fin': -1})
            k = len(carriles) - 1
        nuevos = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': frames - 1, 'recordFrame': ini, 'trackIndex': carriles[k]['idx'], 'mediaType': 2}])
        if not nuevos:
            saltados += 1
            continue
        carriles[k]['fin'] = ini + frames
        try:
            nuevos[0].SetName('%s · %s' % (nombre_base, ev.get('asset', '')))
        except Exception:
            pass
        puestos += 1
    # las pistas de una vez anterior que ya no hacen falta
    for i in range(len(carriles) + 1, MAX_CARRILES + 1):
        _vaciar_y_quitar(tl, '%s %d' % (nombre_base, i), 'audio')
    if not carriles:
        _vaciar_y_quitar(tl, nombre_base, 'audio')
    return puestos, saltados


def main():
    with open(RUTA_JSON, encoding='utf-8') as f:
        datos = json.load(f)
    tl = project.GetCurrentTimeline()
    if tl is None:
        raise SystemExit('no hay un timeline activo en Resolve')
    mp = project.GetMediaPool()
    fps = float(datos.get('fps') or tl.GetSetting('timelineFrameRate') or 30)
    base = int(datos.get('inicio') or tl.GetStartFrame()) + int(datos.get('offset_frames') or 0)
    modos = {'screen': getattr(resolve, 'COMPOSITE_SCREEN', None), 'multiply': getattr(resolve, 'COMPOSITE_MULTIPLY', None)}
    caja = _carpeta_efectos(mp)
    v1_antes = len(tl.GetItemListInTrack('video', 1) or [])
    puestos = {k: 0 for k in PISTAS}
    solo_audio = bool(datos.get('solo_audio'))                          # sin efectos visuales: solo el audio extra (música, sonidos); las pistas visuales no se tocan
    puestos['movimiento'] = 0 if solo_audio else _poner_movimiento(tl, datos.get('v1') or [])
    saltados = 0
    por_pista = {}
    pistas_visuales = {} if solo_audio else PISTAS
    for tipo, nombre in pistas_visuales.items():
        eventos = sorted((e for e in datos.get('eventos', []) if e.get('tipo') == tipo), key=lambda e: float(e['ini']))
        if not eventos:
            if tipo != 'broll':                                         # la pista reservada de B-roll se queda (bloqueada) para la próxima vez
                _vaciar_y_quitar(tl, nombre)
            continue
        if tipo == 'broll' and not any(tl.GetTrackName('video', i) == nombre for i in range(1, int(tl.GetTrackCount('video') or 0) + 1)):
            print('  B-roll: falta la pista reservada FX-BROLL (debajo de los captions): no se pone para no tapar los subtítulos')
            saltados += len(eventos)
            continue
        idx = _pista(tl, nombre)
        if idx is None:
            print('  no pude crear la pista %s' % nombre)
            saltados += len(eventos)
            continue
        por_pista[tipo] = idx
        fin_anterior = -1
        for ev in eventos:
            clip = _importar(mp, caja, ev)
            if clip is None:
                print('  no pude importar el efecto %s (%s)' % (tipo, ev.get('asset')))
                saltados += 1
                continue
            try:
                frames = int(float(clip.GetClipProperty('Frames') or 0))
                fps_clip = float(clip.GetClipProperty('FPS') or fps)
            except Exception:
                frames, fps_clip = 0, fps
            if frames <= 1:
                saltados += 1
                continue
            if ev.get('dur'):                                           # un tramo del clip (el último bucle de un overlay, p. ej.)
                frames = max(2, min(frames, int(round(float(ev['dur']) * fps_clip))))
            dur_tl = int(round(frames * fps / fps_clip))                # lo que dura en el timeline (fotogramas)
            ini = base + int(round(float(ev['ini']) * fps))
            if tipo == 'corte':                                         # el corte cae en medio del efecto
                ini -= dur_tl // 2
            ini = max(base, ini)
            if fin_anterior - 2 <= ini < fin_anterior:                  # redondeos de fotogramas entre bucles seguidos: se pegan, no se saltan
                ini = fin_anterior
            if ini < fin_anterior:                                      # nunca se pisan dos clips de la misma pista
                saltados += 1
                continue
            nuevos = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': frames - 1, 'recordFrame': ini, 'trackIndex': idx, 'mediaType': 1}])
            item = nuevos[0] if nuevos else None
            if not item:
                saltados += 1
                continue
            fin_anterior = ini + dur_tl
            if tipo == 'broll':
                try:
                    item.SetProperty('Scaling', getattr(resolve, 'SCALE_FILL', 3))                  # la toma llena el cuadro (recorta lo que sobre)
                except Exception:
                    pass
            if modos.get(ev.get('modo')) is not None:
                try:
                    item.SetProperty('CompositeMode', modos[ev['modo']])
                except Exception as e:
                    print('  (no pude poner el modo %s: %s)' % (ev.get('modo'), e))
            if ev.get('opacidad') is not None and float(ev['opacidad']) < 99.5:
                try:
                    item.SetProperty('Opacity', float(ev['opacidad']))
                except Exception as e:
                    print('  (no pude poner la opacidad: %s)' % e)
            try:
                item.SetName('%s · %s' % (nombre, ev.get('asset', '')))
            except Exception:
                pass
            puestos[tipo] += 1
    # los sonidos (intro, cortes, gancho…) en pistas «FX-SONIDO», «FX-SONIDO 2»… y la música de fondo en «FX-MUSICA» (el audio del video, en A1, no se toca)
    sonidos = [e for e in datos.get('eventos', []) if e.get('tipo') == 'sonido']
    puestos['sonido'], s1 = _poner_audio(tl, mp, caja, fps, base, sonidos, PISTA_SONIDO)
    musica = [e for e in datos.get('eventos', []) if e.get('tipo') == 'musica']
    puestos['musica'], s2 = _poner_audio(tl, mp, caja, fps, base, musica, PISTA_MUSICA)
    saltados += s1 + s2
    for tipo, nombre in pistas_visuales.items():
        if tipo in por_pista and puestos[tipo] == 0 and tipo != 'broll':
            _quitar_si_vacia(tl, nombre)
    print('Efectos: %s (%d sin poner).' % (', '.join('%d %s' % (v, k) for k, v in puestos.items() if v), saltados))
    v1_ahora = len(tl.GetItemListInTrack('video', 1) or [])
    if v1_ahora < v1_antes:                                         # nunca debería pasar: se avisa en voz alta en vez de callar
        raise SystemExit('ATENCION: V1 tenía %d clip(s) y ahora tiene %d tras colocar los efectos' % (v1_antes, v1_ahora))
    if sum(puestos.values()) == 0 and datos.get('eventos'):
        raise SystemExit('Resolve no colocó ningún efecto')
