# CineCaptions · By Cinema Productions
# 2_recursos/efectos/colocar_efectos.py — corre DENTRO de Resolve: pone la intro, las transiciones de los cortes y los iconos flotantes en pistas propias «FX-…».
"""
Lo lanza efectos_visuales.aplicar() (resolve_mcp.ejecutar_py) y lee ~/DaVinciSubtitles/efectos_plan.json:

    {'fps': 30.0, 'inicio': <primer fotograma del timeline>, 'offset_frames': 0,
     'eventos': [{'tipo': 'intro'|'corte'|'icono'|'sonido', 'ini': segundos, 'modo': 'screen'|'normal'|'audio', 'archivo': mp4/wav | 'secuencia': {'patron', 'n'}}]}

v5.34, AI Sound Director: eventos 'voz_ai' (la voz restaurada, una COPIA, en la pista «AI VOICE»: A1 se apaga SOLO después de comprobar que la
copia quedó puesta; si algo falla, A1 queda encendida) y sonidos con 'pista' en AI MUSIC / AI AMBIENCE / AI SFX … (por NOMBRE). Sin esos eventos,
sus pistas se quitan y A1 vuelve a sonar; 'solo_ai' = solo eso (la limpieza cuando el director se apaga).

Reglas: nunca toca V1/A1 ni las pistas de los captions (salvo apagar A1 con AI VOICE ya puesta); las pistas FX-INTRO / FX-CORTES / FX-ICONOS (video) y FX-SONIDO (audio, el sonido de la intro) se vacían y se vuelven a llenar en cada corrida (re-aplicar no apila
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
PISTA_VOZ_AI = 'AI VOICE'                    # v5.34, AI Sound Director: la voz restaurada (una COPIA; A1 se apaga solo con ella ya puesta)
PISTAS_AI = ('AI MUSIC', 'AI AMBIENCE', 'AI SFX MOTION', 'AI SFX UI', 'AI SFX IMPACTS', 'AI SFX TONAL', 'AI SFX TEXTURE')
PROPIAS = ('FX-', 'PRO-', 'AI ', 'SFX')       # las pistas de audio que pone CineCaptions (las demás son del usuario)
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


def _pista(tl, nombre, tipo='video', sub='stereo'):
    """El índice de la pista (de video o de audio, `sub` mono/stereo) con ese nombre (se crea si no está) y sus clips de antes ya borrados."""
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
            creada = bool(tl.AddTrack('audio', sub))
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
NOMBRE_INTRO = 'CineCaptions Intro'          # v5.33: solo el zoom de la intro del gancho (con la PRO: colocar_pro sí recorta a la persona encima)


def _poner_movimiento(tl, entradas):
    """La composición de Fusion de cada clip de V1 (zoom, temblor, transiciones, fondo desenfocado): se quita la de la vez anterior y se importa la nueva.
    `entradas`: [{'inicio': fotograma del clip en el timeline, 'ruta': .comp | None, 'nombre': nombre de la comp (por defecto NOMBRE_COMP)}].
    Devuelve cuántas se pusieron."""
    puestas = 0
    por_inicio = {int(e['inicio']): e for e in entradas}
    for it in tl.GetItemListInTrack('video', 1) or []:
        e = por_inicio.get(int(it.GetStart()))
        if e is None:
            continue
        try:
            for n in list(it.GetFusionCompNameList() or []):
                if n in (NOMBRE_COMP, NOMBRE_INTRO):
                    it.DeleteFusionCompByName(n)
            if not e.get('ruta'):
                continue
            nombre = e.get('nombre') or NOMBRE_COMP
            antes = set(it.GetFusionCompNameList() or [])
            comp = it.ImportFusionComp(e['ruta'])
            if not comp:
                print('  Resolve no aceptó la composición de movimiento')
                continue
            nuevos = [n for n in (it.GetFusionCompNameList() or []) if n not in antes]
            if nuevos:
                try:
                    it.RenameFusionCompByName(nuevos[0], nombre)
                    it.LoadFusionCompByName(nombre)
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


def _apagar_sfx(tl, nombres):
    """v5.34, AI Sound Director (único dueño del sonido): los clips de los sonidos de Simple (pistas cuyo nombre empieza por uno de `nombres`: «SFX»,
    «SFX 2»…) se APAGAN —siguen ahí, y un GO con el director apagado los vuelve a poner—. Las pistas «AI SFX …» no se tocan. Devuelve cuántos."""
    prefijos = [str(n).upper() for n in nombres or [] if n]
    apagados = 0
    for i in range(1, int(tl.GetTrackCount('audio') or 0) + 1):
        nombre = str(tl.GetTrackName('audio', i) or '').upper()
        if not any(nombre.startswith(p) for p in prefijos):
            continue
        for it in tl.GetItemListInTrack('audio', i) or []:
            try:
                if it.GetClipEnabled() and it.SetClipEnabled(False):
                    apagados += 1
            except Exception:
                pass
    return apagados


def _indice(tl, nombre, tipo='audio'):
    for i in range(1, int(tl.GetTrackCount(tipo) or 0) + 1):
        if tl.GetTrackName(tipo, i) == nombre:
            return i
    return None


def _a1_encendida(tl):
    try:
        tl.SetTrackEnable('audio', 1, True)
    except Exception:
        pass


def _poner_voz_ai(tl, mp, caja, fps, base, eventos):
    """v5.34, AI Sound Director: la voz restaurada (una COPIA: el audio original sigue en A1) en la pista «AI VOICE». A1 se apaga SOLO después de
    comprobar que la copia quedó puesta entera y en su sitio; si algo falla, la copia se quita y A1 queda encendida. Sin evento (director apagado o
    voz que no hacía falta tocar): AI VOICE fuera y A1 vuelve a sonar. Con otras pistas de audio del usuario la voz original no se sustituye.
    Devuelve (puestas, nota)."""
    ev = next((e for e in eventos if e.get('tipo') == 'voz_ai' and e.get('archivo')), None)
    if ev is None:
        if _indice(tl, PISTA_VOZ_AI) is None:
            return 0, ''
        _vaciar_y_quitar(tl, PISTA_VOZ_AI, 'audio')
        _a1_encendida(tl)
        return 0, 'AI VOICE quitada: la voz original (A1) vuelve a sonar'

    def deshacer(motivo):
        _vaciar_y_quitar(tl, PISTA_VOZ_AI, 'audio')
        _a1_encendida(tl)
        return 0, motivo + ': la voz original sigue en A1'
    propias = PROPIAS + tuple(str(p) for p in (ev.get('propias') or []) if p)
    ajenas = []
    for i in range(2, int(tl.GetTrackCount('audio') or 0) + 1):
        nombre = str(tl.GetTrackName('audio', i) or '')
        if nombre.startswith(propias):
            continue
        try:
            if not tl.GetIsTrackEnabled('audio', i):
                continue
        except Exception:
            pass
        if tl.GetItemListInTrack('audio', i):
            ajenas.append(nombre or 'A%d' % i)
    if ajenas:
        return deshacer('hay otras pistas de audio con clips (%s)' % ', '.join(ajenas[:3]))
    a1 = sorted(tl.GetItemListInTrack('audio', 1) or [], key=lambda it: it.GetStart())
    frames = max(2, int(round(float(ev.get('dur') or 0.0) * fps)))
    ini = base + int(round(float(ev.get('ini') or 0.0) * fps))
    if not a1:
        return deshacer('A1 está vacía')
    tolerancia = max(3, int(round(0.5 * fps)))                        # (el audio de un video puede acabar unos fotogramas antes que su imagen)
    if abs(a1[0].GetStart() - ini) > 1 or abs(a1[-1].GetEnd() - (ini + frames)) > tolerancia:
        return deshacer('la copia no cuadra con A1 (A1 %d-%d, copia %d-%d)' % (a1[0].GetStart(), a1[-1].GetEnd(), ini, ini + frames))
    clip = _importar(mp, caja, ev)
    if clip is None:
        return deshacer('no pude importar la voz restaurada')
    _vaciar_y_quitar(tl, PISTA_VOZ_AI, 'audio')                          # re-aplicar no apila: una pista nueva con un solo clip
    idx = _pista(tl, PISTA_VOZ_AI, 'audio', 'mono' if int(ev.get('canales') or 2) == 1 else 'stereo')
    if idx is None:
        return deshacer('no pude crear la pista AI VOICE')
    nuevos = mp.AppendToTimeline([{'mediaPoolItem': clip, 'startFrame': 0, 'endFrame': frames - 1, 'recordFrame': ini, 'trackIndex': idx, 'mediaType': 2}])
    puestos = tl.GetItemListInTrack('audio', idx) or []
    if not nuevos or len(puestos) != 1 or abs(puestos[0].GetStart() - ini) > 1 or abs(puestos[0].GetDuration() - frames) > 2:
        return deshacer('AI VOICE no quedó bien puesta')
    try:
        puestos[0].SetName('AI VOICE · %s' % (ev.get('backend') or 'voz restaurada'))
    except Exception:
        pass
    try:
        tl.SetTrackEnable('audio', 1, False)
        apagada = tl.GetIsTrackEnabled('audio', 1) is False
    except Exception:
        apagada = False
    if not apagada:
        return deshacer('no pude apagar A1 (sonarían las dos voces)')
    return 1, 'AI VOICE puesta y A1 apagada (reversible: al apagar el director, A1 vuelve)'


def _validar_destino_ai(proyecto, tl, destino):
    """La pagina Sonido solo puede reponer audio en el proyecto/timeline de su ultimo GO."""
    if destino is None:
        return
    if not isinstance(destino, dict) or not all(isinstance(destino.get(k), str) and destino[k].strip() for k in ('proyecto', 'timeline')):
        raise SystemExit('Sonido no se aplico: falta el destino del ultimo GO. Haz GO con AI Sound Director encendido.')
    mensaje = "Sonido no se aplico: abre el proyecto '%s' y el timeline '%s' del ultimo GO." % (destino['proyecto'], destino['timeline'])
    if proyecto.GetName() != destino['proyecto'] or tl.GetName() != destino['timeline']:
        raise SystemExit(mensaje)
    if destino.get('timeline_id') is not None and str(destino['timeline_id']) != '':
        try:
            identificador = tl.GetUniqueId()
        except Exception:
            identificador = None
        if not identificador or str(identificador) != str(destino['timeline_id']):
            raise SystemExit(mensaje)


def main():
    with open(RUTA_JSON, encoding='utf-8') as f:
        datos = json.load(f)
    proyecto = project
    if datos.get('destino_ai') is not None:
        proyecto = resolve.GetProjectManager().GetCurrentProject()
        if proyecto is None:
            raise SystemExit('Sonido no se aplico: no hay un proyecto abierto en Resolve.')
    tl = proyecto.GetCurrentTimeline()
    if tl is None:
        raise SystemExit('no hay un timeline activo en Resolve')
    _validar_destino_ai(proyecto, tl, datos.get('destino_ai'))
    mp = proyecto.GetMediaPool()
    fps = float(datos.get('fps') or tl.GetSetting('timelineFrameRate') or 30)
    base = int(datos.get('inicio') or tl.GetStartFrame()) + int(datos.get('offset_frames') or 0)
    modos = {'screen': getattr(resolve, 'COMPOSITE_SCREEN', None), 'multiply': getattr(resolve, 'COMPOSITE_MULTIPLY', None)}
    caja = _carpeta_efectos(mp)
    v1_antes = len(tl.GetItemListInTrack('video', 1) or [])
    puestos = {k: 0 for k in PISTAS}
    solo_ai = bool(datos.get('solo_ai'))                                # v5.34: solo las pistas del AI Sound Director (la limpieza al apagarlo)
    solo_audio = bool(datos.get('solo_audio')) or solo_ai               # sin efectos visuales: solo el audio extra (música, sonidos); las pistas visuales no se tocan
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
    eventos = datos.get('eventos', [])
    if not solo_ai:
        sonidos = [e for e in eventos if e.get('tipo') == 'sonido' and not e.get('pista')]
        puestos['sonido'], s1 = _poner_audio(tl, mp, caja, fps, base, sonidos, PISTA_SONIDO)
        musica = [e for e in eventos if e.get('tipo') == 'musica' and not e.get('pista')]
        puestos['musica'], s2 = _poner_audio(tl, mp, caja, fps, base, musica, PISTA_MUSICA)
        saltados += s1 + s2
    # v5.34, AI Sound Director: sus pistas (por NOMBRE, nunca por índice) y la voz restaurada; sin sus eventos, sus pistas se quitan y A1 vuelve
    puestos['ai'] = 0
    existentes = {str(tl.GetTrackName('audio', i)) for i in range(1, int(tl.GetTrackCount('audio') or 0) + 1)}
    pedidos_ai = 0
    for nombre in PISTAS_AI:
        evs = [e for e in eventos if e.get('pista') == nombre]
        pedidos_ai += len(evs)
        if evs or nombre in existentes:
            n_ai, s_ai = _poner_audio(tl, mp, caja, fps, base, evs, nombre)
            puestos['ai'] += n_ai
            saltados += s_ai
    if datos.get('apagar_sfx') and (puestos['ai'] > 0 or pedidos_ai == 0):    # solo con los sonidos del director ya puestos (o su silencio a propósito)
        apagados = _apagar_sfx(tl, datos['apagar_sfx'])
        if apagados:
            print('  %d sonidos de Simple apagados (los decide el AI Sound Director)' % apagados)
    puestos['voz'], nota_voz = _poner_voz_ai(tl, mp, caja, fps, base, eventos)
    if nota_voz:
        print('  ' + nota_voz)
    for tipo, nombre in pistas_visuales.items():
        if tipo in por_pista and puestos[tipo] == 0 and tipo != 'broll':
            _quitar_si_vacia(tl, nombre)
    print('Efectos: %s (%d sin poner).' % (', '.join('%d %s' % (v, k) for k, v in puestos.items() if v), saltados))
    v1_ahora = len(tl.GetItemListInTrack('video', 1) or [])
    if v1_ahora < v1_antes:                                         # nunca debería pasar: se avisa en voz alta en vez de callar
        raise SystemExit('ATENCION: V1 tenía %d clip(s) y ahora tiene %d tras colocar los efectos' % (v1_antes, v1_ahora))
    if sum(puestos.values()) == 0 and [e for e in datos.get('eventos', []) if e.get('tipo') != 'voz_ai']:      # (la voz que no se sustituye no es un fallo)
        raise SystemExit('Resolve no colocó ningún efecto')
