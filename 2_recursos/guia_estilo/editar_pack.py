# CineCaptions · By Cinema Productions
# 2_recursos/guia_estilo/editar_pack.py — corre DENTRO de Resolve: abre un pack de «Pack de estilos» como timeline para editarlo (y exportarlo de nuevo).
"""
Lo lanza la app por el MCP (edicion_pack.abrir_en_resolve) justo después de escribir ~/DaVinciSubtitles/editar_pack.json.

  * Si el pack trae su timeline (.drt) se importa tal cual: es el archivo que el usuario ya conoce, con todos sus clips apilados y nombrados.
  * Si solo trae el bin (.drb), se importa en el bin «RCS · Editar · <pack>» y se arma el timeline como en un pack: por cada variante
    V1 principal · V2 arriba · V3 abajo · V4 imagen (una variante tras otra) y al final «simple»; cada clip ya lleva el NOMBRE EXACTO que lee CineCaptions
    (principal, arriba 2, abajo 3…) y su posición, para exportarlo sin tocar los nombres.

Después se edita en Resolve (fuente, color, tamaño, posición) y se exporta: Archivo > Exportar > Timeline (.drt) → «Añadir plantilla (.drb)» en la app.
Nada se borra ni se sobrescribe: si el timeline de edición ya existe, solo se abre.
"""
import json
import os
import re

RUTA_JSON = os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'editar_pack.json')
TEXTOS = {'context': 'así se ve', 'main': 'TU ESTILO', 'complement': 'en tu video', 'image': '●', 'base': 'palabras sueltas'}
NOMBRE = {'context': 'arriba', 'main': 'principal', 'complement': 'abajo', 'image': 'imagen', 'base': 'simple'}
ALIAS = {'arriba': 'context', 'contexto': 'context', 'principal': 'main', 'abajo': 'complement', 'complemento': 'complement', 'imagen': 'image',
         'simple': 'base', 'base': 'base'}
PISTAS = {'main': 1, 'context': 2, 'complement': 3, 'image': 4, 'base': 1}


def parsear(nombre):
    """'Arriba 2' -> ('context', 2); 'simple' -> ('base', 0); gemela de packs_drt.parsear_nombre()."""
    n = re.sub(r'\.[a-z]+$', '', (nombre or '').strip().lower())
    if n in ('simple', 'base'):
        return 'base', 0
    for palabra, rol in ALIAS.items():
        if n == palabra:
            return rol, 1
        m = re.match('^' + re.escape(palabra) + r'[\s\-_.]*0*(\d+)$', n)
        if m:
            return rol, int(m.group(1))
    return None, 0


def _clips(carpeta):
    """{(rol, n): clip} del bin y sus sub-bins."""
    hallados = {}
    for c in (carpeta.GetClipList() or []):
        rol, n = parsear(c.GetName())
        if rol:
            hallados.setdefault((rol, n), c)
    for s in carpeta.GetSubFolderList() or []:
        for k, v in _clips(s).items():
            hallados.setdefault(k, v)
    return hallados


def _poner_texto(item, texto):
    comp = item.GetFusionCompByIndex(1)
    t = comp.FindTool('Template') or comp.FindTool('Text1')
    if t is None:
        for _, x in comp.GetToolList().items():
            if x.ID == 'TextPlus':
                t = x
                break
    if t is not None:
        t.SetInput('StyledText', texto)


def _nombre_de(rol, n):
    return NOMBRE[rol] + ('' if n in (0, 1) else ' %d' % n)


def main():
    with open(RUTA_JSON, encoding='utf-8') as f:
        datos = json.load(f)
    nombre = datos['timeline']
    pm = resolve.GetProjectManager()
    proy = pm.GetCurrentProject() if pm else None
    if proy is None:
        raise SystemExit('no hay un proyecto abierto en Resolve')
    for i in range(1, (proy.GetTimelineCount() or 0) + 1):
        t = proy.GetTimelineByIndex(i)
        if t and (t.GetName() or '') == nombre:
            proy.SetCurrentTimeline(t)
            resolve.OpenPage('edit')
            print('Se abrió el timeline «%s» que ya estaba en el proyecto.' % nombre)
            return
    mp = proy.GetMediaPool()
    previo = proy.GetCurrentTimeline()
    raiz = mp.GetRootFolder()
    drt = datos.get('drt') or ''
    if drt and os.path.isfile(drt):
        try:
            tl = mp.ImportTimelineFromFile(drt, {'timelineName': nombre, 'importSourceClips': True})
        except Exception:
            tl = None
        if tl:
            try:
                tl.SetName(nombre)             # Resolve conserva el nombre que trae el .drt: así la próxima vez se reconoce y solo se abre
            except Exception:
                pass
            proy.SetCurrentTimeline(tl)
            resolve.OpenPage('edit')
            print('Importé el timeline (.drt) del pack: «%s».' % nombre)
            return
        print('  (Resolve no importó el .drt; sigo con el bin del pack)')
    drb = datos.get('drb') or ''
    if not drb or not os.path.isfile(drb):
        raise SystemExit('este pack no trae ni timeline (.drt) ni bin (.drb) que pueda abrir')
    bin_ = 'RCS · Editar · ' + datos['nombre']
    caja = next((f for f in (raiz.GetSubFolderList() or []) if f.GetName() == bin_), None)
    clips = _clips(caja) if caja is not None else {}
    if not clips:
        if caja is None:
            caja = mp.AddSubFolder(raiz, bin_)
        if caja is None:
            raise SystemExit('Resolve no pudo crear el bin del pack')
        mp.SetCurrentFolder(caja)
        try:
            mp.ImportFolderFromFile(drb)
        finally:
            mp.SetCurrentFolder(raiz)
        clips = _clips(caja)
    if not clips:
        raise SystemExit('Resolve no pudo importar los bloques del pack')
    tl = mp.CreateEmptyTimeline(nombre)
    if tl is None:
        raise SystemExit('Resolve no pudo crear el timeline de edición')
    try:
        proy.SetCurrentTimeline(tl)
        resolve.OpenPage('edit')
        for k, v in (('useCustomSettings', '1'), ('timelineResolutionWidth', str(datos['ancho'])), ('timelineResolutionHeight', str(datos['alto']))):
            try:
                tl.SetSetting(k, v)
            except Exception:
                pass
        for _ in range(3):
            tl.AddTrack('video')
        try:
            fps = float(tl.GetSetting('timelineFrameRate') or 30)
        except Exception:
            fps = 30.0
        largo = int(round(fps * 3))
        inicio = tl.GetStartFrame()
        variantes = sorted({n for (rol, n) in clips if rol != 'base'})
        orden = [(n, [(r, n) for r in ('main', 'context', 'complement', 'image') if (r, n) in clips]) for n in variantes]
        if ('base', 0) in clips:
            orden.append((0, [('base', 0)]))
        hechos = 0
        for k, (n, piezas) in enumerate(orden):
            for rol, nn in piezas:
                nuevos = mp.AppendToTimeline([{'mediaPoolItem': clips[(rol, nn)], 'startFrame': 0, 'endFrame': largo - 1, 'recordFrame': inicio + k * largo,
                                               'trackIndex': PISTAS[rol], 'mediaType': 1}])
                item = nuevos[0] if nuevos else None
                if not item:
                    continue
                try:
                    _poner_texto(item, TEXTOS[rol])
                except Exception as e:
                    print('  %s: %s' % (_nombre_de(rol, nn), e))
                pos = (datos.get('posiciones') or {}).get('%s|%d' % (rol, nn))
                if pos:
                    try:
                        item.SetProperty('Tilt', float(pos['y']))
                        item.SetProperty('Pan', float(pos['x']))
                        item.SetProperty('ZoomX', float(pos['zx']))
                        item.SetProperty('ZoomY', float(pos['zy']))
                    except Exception:
                        pass
                try:
                    item.SetName(_nombre_de(rol, nn))              # el nombre EXACTO que lee CineCaptions
                except Exception:
                    pass
                hechos += 1
            try:
                tl.AddMarker(k * largo, 'Yellow', 'simple' if n == 0 else 'variante %d' % n, '', largo)
            except Exception:
                pass
        if hechos == 0:
            raise RuntimeError('Resolve no colocó ningún clip')
        print('Abrí «%s» para editar: %d clips.' % (nombre, hechos))
    except BaseException as e:
        try:
            if previo:
                proy.SetCurrentTimeline(previo)
            mp.DeleteTimelines([tl])
        except Exception:
            pass
        if isinstance(e, SystemExit):
            raise
        raise SystemExit('No pude abrir el pack: %s' % e)
    resolve.OpenPage('edit')
