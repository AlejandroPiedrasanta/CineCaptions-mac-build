# CineCaptions · By Cinema Productions
# 2_recursos/guia_estilo/construir_guia.py — corre DENTRO de Resolve: arma el timeline «Crea tu estilo» con los 48 ejemplos (Luxe Shine o Amro de principal; Luxe Slide arriba y abajo) y saca sus vistas reales.
"""
Lo lanza la app por el MCP (resolve_mcp.ejecutar_py) justo después de escribir ~/DaVinciSubtitles/guia_estilo_ejemplos.json (ejemplos_estilo.datos_guia).

Para cada ejemplo pone tres clips apilados, como en un pack:  V1 principal (Luxe Shine, o un preset de Amro.Films Captions en los ejemplos de Amro)
· V2 arriba (Luxe Slide) · V3 abajo (Luxe Slide), con la tipografía, el tamaño, el color y la posición del ejemplo, y un marcador con su número y su nombre.
Dos modos (campo 'modo' del JSON):
  * 'guia'   (por defecto) el timeline «Crea tu estilo», que se queda en el proyecto para retocar los ejemplos.
  * 'vistas' un timeline TEMPORAL (con la marca de los temporales de CineCaptions, que se limpia solo en la siguiente corrida) del que solo se sacan
             los fotogramas reales de cada ejemplo ('fotos' = carpeta de salida): son las vistas de la galería «Crea tu estilo». Como «Vista real · Resolve»,
             no borra nada en caliente y deja el timeline, el cabezal y la página de Resolve como estaban. Los clips NO llevan los nombres que
lee CineCaptions a propósito (se llaman «07 · principal»…): quien se queda con un ejemplo tiene que ponerle el nombre exacto —principal, arriba,
abajo, y «2» o «3» para las variantes—; esa es justo la estructura que explica el «!» de la app.

Los clips salen de «Crea tu estilo.drb» (2_recursos/guia_estilo/), que lleva los macros ORIGINALES del Luxe Title Pack (los mismos de los packs del
programa: ni Text+ sueltos ni imitaciones). No se insertan efectos por la API: eso cuelga o tumba a Resolve con nombres que no reconoce.
"""
import json
import os
import time

RUTA_JSON = os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'guia_estilo_ejemplos.json')
BIN_AMRO = 'RCS · Crea tu estilo (Amro)'
BIN = 'RCS · Crea tu estilo (bloques)'      # «RCS · »: los scripts de subtítulos no cuentan los bins con ese prefijo como plantillas del usuario
ALIAS = {'arriba': 'arriba', 'contexto': 'arriba', 'principal': 'principal', 'abajo': 'abajo', 'complemento': 'abajo'}


def _clips_de_guia(carpeta):
    """{arriba, principal, abajo} de ese bin (y sus sub-bins), o {} si no están. Resolve nombra los clips del .drb como lo hace el archivo
    (contexto / principal / complemento): el nombre viejo y el nuevo valen igual."""
    hallados = {}
    for c in (carpeta.GetClipList() or []):
        rol = ALIAS.get((c.GetName() or '').strip().lower())
        if rol:
            hallados.setdefault(rol, c)
    if len(hallados) == 3:
        return hallados
    for s in carpeta.GetSubFolderList() or []:
        r = _clips_de_guia(s)
        if r:
            return r
    return {}


def _principales_amro(carpeta):
    """{N: clip} de los textos principales de Amro (principal = 1, principal 2 = 2…) del bin y sus sub-bins."""
    hallados = {}
    for c in (carpeta.GetClipList() or []):
        nombre = (c.GetName() or '').strip().lower()
        if nombre == 'principal':
            hallados[1] = c
        elif nombre.startswith('principal '):
            try:
                hallados[int(nombre.split()[-1])] = c
            except ValueError:
                pass
    for s in carpeta.GetSubFolderList() or []:
        for k, v in _principales_amro(s).items():
            hallados.setdefault(k, v)
    return hallados


def _importar(mp, raiz, nombre_bin, drb):
    caja = next((f for f in (raiz.GetSubFolderList() or []) if f.GetName() == nombre_bin), None)
    if caja is None:
        caja = mp.AddSubFolder(raiz, nombre_bin)
    if caja is None:
        raise SystemExit('Resolve no pudo crear el bin %s' % nombre_bin)
    mp.SetCurrentFolder(caja)
    try:
        mp.ImportFolderFromFile(drb)
    finally:
        mp.SetCurrentFolder(raiz)
    return caja


def poner_texto(item, texto):
    """El preset de Amro trae su tipografía, color y tamaño: solo se le cambia el texto (al primer Text+, como hace el programa)."""
    comp = item.GetFusionCompByIndex(1)
    t1 = comp.FindTool('Text1')
    if t1 is None:
        for _, t in comp.GetToolList().items():
            if t.ID == 'TextPlus':
                t1 = t
                break
    if t1 is None:
        raise RuntimeError('el clip no trae un Text+')
    t1.SetInput('StyledText', texto)


def _tc(tl, frame):
    """Timecode de un fotograma absoluto (con drop frame si el timeline lo usa)."""
    fps = float(tl.GetSetting('timelineFrameRate') or 24)
    entero = int(round(fps))
    df = ';' in str(tl.GetStartTimecode() or '')
    frame = int(frame)
    if df and entero in (30, 60):
        drop = 2 if entero == 30 else 4
        diez = entero * 600 - drop * 9
        minuto = entero * 60 - drop
        d, m = divmod(frame, diez)
        frame += drop * 9 * d + (drop * ((m - drop) // minuto) if m > drop else 0)
    f = frame % entero
    s = frame // entero
    return '%02d:%02d:%02d%s%02d' % (s // 3600, s // 60 % 60, s % 60, ';' if df else ':', f)


def _fotos(proy, tl, base, cuadros, rutas):
    """Varios fotogramas REALES de un mismo ejemplo (su animación de entrada). Como «Vista real · Resolve»: se va a cada uno, se espera a que Fusion lo dibuje
    y se exporta. Antes de empezar se salta a otro cuadro para que el visor no reutilice el último que enseñó. Devuelve cuántos salieron."""
    try:
        tl.SetCurrentTimecode(_tc(tl, base + 24))
        time.sleep(0.12)
    except Exception:
        return 0
    hechos = 0
    for f, ruta in zip(cuadros, rutas):
        try:
            if not tl.SetCurrentTimecode(_tc(tl, base + f)):
                continue
        except Exception:
            continue
        time.sleep(0.34)
        for _ in range(3):
            try:
                if proy.ExportCurrentFrameAsStill(str(ruta)) and os.path.exists(str(ruta)):
                    hechos += 1
                    break
            except Exception:
                pass
            time.sleep(0.2)
    return hechos


def configurar(item, cfg):
    """Texto, tipografía, tamaño en reposo (sizeCtrl.RestingSize), color y espaciado de un clip Luxe de la guía."""
    comp = item.GetFusionCompByIndex(1)
    t1 = comp.FindTool('Text1')
    if t1 is None:
        raise RuntimeError('el clip no trae un Text1')
    entrada = comp.FindTool('Template') or t1          # el Text1 del macro lee el texto del Template
    entrada.SetInput('StyledText', cfg['texto'])
    t1.SetInput('Font', cfg['font'])
    t1.SetInput('Style', cfg['style'])
    sc = comp.FindTool('sizeCtrl')
    if sc is not None:
        sc.SetInput('RestingSize', float(cfg['size']))
    else:
        t1.SetInput('Size', float(cfg['size']))
    r, g, b = cfg['color']
    t1.SetInput('Red1', float(r))
    t1.SetInput('Green1', float(g))
    t1.SetInput('Blue1', float(b))
    t1.SetInput('CharacterSpacing', float(cfg['tracking']))


def _gemelo():
    """El módulo de CineCaptions.py (para limpiar los temporales de siempre)."""
    import importlib.util
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resolve_scripts', 'CineCaptions.py')
    spec = importlib.util.spec_from_file_location('_cinecaptions_gemelo_guia', ruta)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__['resolve'] = resolve        # noqa: F821 (lo pone el MCP)
    mod.__dict__['project'] = project        # noqa: F821
    spec.loader.exec_module(mod)
    return mod


def main():
    with open(RUTA_JSON, encoding='utf-8') as f:
        datos = json.load(f)
    nombre = datos['nombre']
    vistas = datos.get('modo') == 'vistas'
    pm = resolve.GetProjectManager()
    proy = pm.GetCurrentProject() if pm else None
    if proy is None:
        raise SystemExit('no hay un proyecto abierto en Resolve')
    # si la guía nueva ya está en el proyecto, solo se abre; una guía vieja (5 variantes) se aparta, no se borra
    for i in range(1, 0 if vistas else (proy.GetTimelineCount() or 0) + 1):
        t = proy.GetTimelineByIndex(i)
        if t and (t.GetName() or '').lower() == nombre.lower():
            try:
                nuevos = len(t.GetMarkers() or {})
            except Exception:
                nuevos = 0
            if nuevos >= len(datos['ejemplos']) and not datos.get('fotos'):
                proy.SetCurrentTimeline(t)
                resolve.OpenPage('edit')
                return
            t.SetName(nombre + ' (anterior)')
            break
    mp = proy.GetMediaPool()
    previo = proy.GetCurrentTimeline()
    try:
        tc_previo = previo.GetCurrentTimecode() if previo else None
    except Exception:
        tc_previo = None
    try:
        pagina_previa = resolve.GetCurrentPage()
    except Exception:
        pagina_previa = None
    if vistas:
        try:
            _gemelo()._limpiar_temporales(proy, mp)
        except Exception as e:
            print('  (no pude limpiar los temporales de antes: %s)' % e)
    raiz = mp.GetRootFolder()
    caja = next((f for f in (raiz.GetSubFolderList() or []) if f.GetName() == BIN), None)
    clips = _clips_de_guia(caja) if caja is not None else {}
    if not clips:
        drb = datos.get('drb')
        if not drb or not os.path.isfile(drb):
            raise SystemExit('no encuentro «Crea tu estilo.drb» en el programa (reinstálalo)')
        if caja is None:
            caja = mp.AddSubFolder(raiz, BIN)
        if caja is None:
            raise SystemExit('Resolve no pudo crear el bin de la guía')
        mp.SetCurrentFolder(caja)
        try:
            mp.ImportFolderFromFile(drb)
        finally:
            mp.SetCurrentFolder(raiz)
        clips = _clips_de_guia(caja)
        if not clips:
            raise SystemExit('Resolve no pudo importar los bloques de la guía')
    amro = {}
    if datos.get('amro') and any(c.get('clip_amro') for e in datos['ejemplos'] for c in e['bloques']):
        caja_amro = next((f for f in (raiz.GetSubFolderList() or []) if f.GetName() == BIN_AMRO), None)
        amro = _principales_amro(caja_amro) if caja_amro is not None else {}
        if len(amro) < 6:
            if not os.path.isfile(datos['amro']):
                raise SystemExit('no encuentro «Amro principales.drb» en el programa (reinstálalo)')
            amro = _principales_amro(_importar(mp, raiz, BIN_AMRO, datos['amro']))
        if len(amro) < 6:
            raise SystemExit('Resolve no pudo importar los textos principales de Amro')
    tl = mp.CreateEmptyTimeline(nombre)
    if tl is None:
        raise SystemExit('Resolve no pudo crear el timeline de la guía')
    try:
        proy.SetCurrentTimeline(tl)
        if not vistas or pagina_previa != 'edit':
            resolve.OpenPage('edit')
        for k, v in (('useCustomSettings', '1'), ('timelineResolutionWidth', '1080'), ('timelineResolutionHeight', '1920')):
            try:
                tl.SetSetting(k, v)
            except Exception:
                pass
        for _ in range(2):
            tl.AddTrack('video')
        try:
            fps = float(tl.GetSetting('timelineFrameRate') or 30)
        except Exception:
            fps = 30.0
        largo = int(round(fps * float(datos.get('segundos', 4))))
        inicio = tl.GetStartFrame()
        pistas = {'principal': 1, 'arriba': 2, 'abajo': 3}
        hechos = 0
        for k, ej in enumerate(datos['ejemplos']):
            for cfg in ej['bloques']:
                if cfg.get('clip_amro'):
                    numero = 1 if cfg['clip_amro'] == 'principal' else int(cfg['clip_amro'].split()[-1])
                    base = amro[numero]
                else:
                    base = clips[cfg['rol']]
                nuevos = mp.AppendToTimeline([{'mediaPoolItem': base, 'startFrame': 0, 'endFrame': largo - 1,
                                               'recordFrame': inicio + k * largo, 'trackIndex': pistas[cfg['rol']], 'mediaType': 1}])
                item = nuevos[0] if nuevos else None
                if not item:
                    continue
                try:
                    if cfg.get('clip_amro'):
                        poner_texto(item, cfg['texto'])
                    else:
                        configurar(item, cfg)
                except Exception as e:
                    print('  ejemplo %s (%s): %s' % (ej['id'], cfg['rol'], e))
                try:
                    item.SetProperty('Tilt', float(cfg['tilt']))
                except Exception:
                    pass
                try:
                    item.SetName('%02d · %s' % (ej['id'], cfg['rol']))
                except Exception:
                    pass
                hechos += 1
            try:
                tl.AddMarker(k * largo, 'Yellow', '%02d · %s' % (ej['id'], ej['nombre']), ej['nota'], largo)
            except Exception:
                pass
        if hechos == 0:
            raise RuntimeError('Resolve no colocó ningún clip')
        if datos.get('fotos'):
            os.makedirs(datos['fotos'], exist_ok=True)
            cuadros = [max(1, int(round(float(s) * fps))) for s in (datos.get('cuadros_s') or [2.0])]
            sacadas = 0
            for k, ej in enumerate(datos['ejemplos']):
                rutas = [os.path.join(datos['fotos'], 'ej_%02d_%d.png' % (ej['id'], n)) for n in range(len(cuadros))]
                if _fotos(proy, tl, inicio + k * largo, cuadros, rutas):
                    sacadas += 1
            print('Vistas reales sacadas: %d de %d ejemplos.' % (sacadas, len(datos['ejemplos'])))
        print('Guía «%s»: %d ejemplos, %d clips.' % (nombre, len(datos['ejemplos']), hechos))
    except BaseException as e:
        # a medias no sirve: se deja a Resolve como estaba (la guía a medias se quita; el temporal de las vistas lo limpia la siguiente corrida)
        try:
            if previo:
                proy.SetCurrentTimeline(previo)
            if not vistas:
                mp.DeleteTimelines([tl])
        except Exception:
            pass
        if isinstance(e, SystemExit):
            raise
        raise SystemExit('No pude armar la guía: %s' % e)
    if vistas:
        try:
            if previo is not None:
                proy.SetCurrentTimeline(previo)
                if tc_previo:
                    previo.SetCurrentTimecode(tc_previo)
            if pagina_previa and pagina_previa != 'edit':
                resolve.OpenPage(pagina_previa)
        except Exception:
            pass
        return
    resolve.OpenPage('edit')
