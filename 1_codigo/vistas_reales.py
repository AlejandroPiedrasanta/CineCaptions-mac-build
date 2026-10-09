# CineCaptions · By Cinema Productions
# 1_codigo/vistas_reales.py — vistas previas renderizadas DE VERDAD por Resolve (packs y bloques de GO).
"""
vistas_reales.py  (v5.2)
------------------------
Vistas previas RENDERIZADAS por DaVinci Resolve, no dibujadas por el programa
(pedido: «la pestaña de estilos y composición debe renderizar la vista previa
real de los .drb ... las vistas previas renders reales»).

Por el MCP de Resolve se corre 2_recursos/resolve_scripts/«CineCaptions - Vista
Real.py», que coloca el pack en un timeline temporal y exporta fotogramas
reales (con la tipografia, el color, la posicion y la animacion de Fusion).
Aqui se pide, se reducen las imagenes (Pillow) y se guardan en cache:

    ~/DaVinciSubtitles/plantillas_cache/reales/<pack>/<formato>/<firma>/
        set02_00.jpg ... (cuadros de la animacion de cada set)
        indice.json

La firma cambia si cambia el .drb/.drt del pack o el texto de muestra, asi
que una vista vieja nunca se hace pasar por la actual.
"""
import hashlib
import json
import re
import shutil
import tempfile
import time
from pathlib import Path

import plantillas
import resolve_mcp

CARPETA = Path.home() / 'DaVinciSubtitles' / 'plantillas_cache' / 'reales'
PEDIDO = Path.home() / 'DaVinciSubtitles' / 'vista_real_pedido.json'
TEXTOS_MUESTRA = {'context': 'Así se', 'main': 'VE', 'complement': 'tu pack'}
CUADROS = (0.08, 0.2, 0.36, 0.6, 1.0)      # segundos desde que entra el bloque
ALTO_MINI = 540


def script():
    return plantillas_base() / 'resolve_scripts' / 'CineCaptions - Vista Real.py'


def plantillas_base():
    import sys
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def _slug(texto):
    t = re.sub(r'[^A-Za-z0-9]+', '_', str(texto)).strip('_')
    return t[:48] or 'pack'


def _pack(nombre):
    if nombre in (None, '', 'auto', 'dinamico'):
        return plantillas.pack_incorporado()
    return plantillas.buscar_pack(nombre)


def _firma(pack, formato, textos):
    h = hashlib.sha1()
    for ruta in (pack.ruta_drb(formato), pack.ruta_drt(formato)):
        if ruta:
            st = Path(ruta).stat()
            h.update(f'{ruta}|{st.st_size}|{int(st.st_mtime)}'.encode('utf-8'))
    h.update(json.dumps(textos, ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return h.hexdigest()[:12]


def carpeta_de(nombre_pack, formato, textos=None):
    pack = _pack(nombre_pack)
    if pack is None:
        return None
    textos = textos or TEXTOS_MUESTRA
    return CARPETA / _slug(pack.nombre) / formato / _firma(pack, formato, textos)


def _incluida(nombre_pack):
    """Los fotogramas que el PACK trae ya renderizados (el estilo «Kinetic»: sus clips son elementos, no sets, y no hay «vista del pack» que pedirle a Resolve;
    se hacen con hacer_vista_kinetic.py y viajan en pack/vista/). Devuelve (carpeta, indice) o (None, {})."""
    try:
        pack = _pack(nombre_pack)
        if pack is None or not getattr(pack, 'kinetic', False):
            return None, {}
        d = pack.carpeta / 'vista'
        return d, json.loads((d / 'indice.json').read_text(encoding='utf-8'))
    except Exception:
        return None, {}


def cacheadas(nombre_pack, formato, textos=None):
    """{numero_de_set: [rutas de los cuadros en orden]} ya renderizados, o {}."""
    d, indice = _incluida(nombre_pack)
    if d is not None:
        return {int(k): [str(d / r) for r in v if (d / r).is_file()] for k, v in (indice.get('sets') or {}).items() if any((d / r).is_file() for r in v)}
    try:
        d = carpeta_de(nombre_pack, formato, textos)
        indice = json.loads((d / 'indice.json').read_text(encoding='utf-8')) if d else {}
    except Exception:
        return {}
    salida = {}
    for numero, rutas in (indice.get('sets') or {}).items():
        vivas = [str(d / r) for r in rutas if (d / r).is_file()]
        if vivas:
            salida[int(numero)] = vivas
    return salida


def recortes(nombre_pack, formato, textos=None):
    """{numero_de_set: (x, y, w, h)} en fraccion del cuadro: la zona donde esta
    el texto (para que el mosaico lo muestre grande)."""
    d, indice = _incluida(nombre_pack)
    if d is not None:
        return {int(k): tuple(v) for k, v in (indice.get('recortes') or {}).items() if v and len(v) == 4}
    try:
        d = carpeta_de(nombre_pack, formato, textos)
        indice = json.loads((d / 'indice.json').read_text(encoding='utf-8')) if d else {}
    except Exception:
        return {}
    return {int(k): tuple(v) for k, v in (indice.get('recortes') or {}).items() if len(v) == 4}


def _caja_del_texto(rutas, aspecto=1.6, margen=0.45):
    """La caja (fraccion) que contiene lo que se dibujo en todos los cuadros,
    con aire alrededor y la proporcion del mosaico."""
    try:
        from PIL import Image
        caja = None
        ancho = alto = 0
        for r in rutas:
            with Image.open(r) as img:
                g = img.convert('L').point(lambda v: 255 if v > 26 else 0)
                ancho, alto = img.size
                b = g.getbbox()
            if b:
                caja = b if caja is None else (min(caja[0], b[0]), min(caja[1], b[1]), max(caja[2], b[2]), max(caja[3], b[3]))
        if caja is None or not ancho:
            return None
        x0, y0, x1, y1 = caja
        w, h = (x1 - x0) * (1 + margen), (y1 - y0) * (1 + margen * 1.6)
        if w / max(1, h) < aspecto:
            w = h * aspecto
        else:
            h = w / aspecto
        w, h = min(w, ancho), min(h, alto)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x = min(max(0, cx - w / 2), ancho - w)
        y = min(max(0, cy - h / 2), alto - h)
        return [round(x / ancho, 4), round(y / alto, 4), round(w / ancho, 4), round(h / alto, 4)]
    except Exception:
        return None


_LIMPIAR = r'''
import time
mp = project.GetMediaPool()
actual = project.GetCurrentTimeline()
sobras = []
for i in range(1, int(project.GetTimelineCount() or 0) + 1):
    t = project.GetTimelineByIndex(i)
    n = (t.GetName() or '') if t else ''
    if 'temporal' in n and ' vista ' in n and (actual is None or n != actual.GetName()):
        sobras.append(t)
result = bool(mp.DeleteTimelines(sobras)) if sobras else None
'''


# v5.8 (auditoria del flujo): si el programa o Resolve se cierran A MEDIAS de una vista real, el timeline temporal «· vista …» quedaba como el ACTUAL (y GO
# colocaba los subtitulos en el temporal). Antes de renderizar se anota en cual estabas; si algo se corta, el siguiente trabajo lo restaura y limpia.
PREVIO = Path.home() / 'DaVinciSubtitles' / 'vista_previo.json'
_ACTIVOS = [0]            # renders de vista real en curso EN ESTE PROGRAMA (con uno activo no se repara nada)

_ANOTAR = r'''
tl = project.GetCurrentTimeline() if project else None
result = {'proyecto': project.GetName() if project else None, 'timeline': tl.GetName() if tl else None}
'''

_RESTAURAR = r'''
previo = %r
actual = project.GetCurrentTimeline()
nombre = (actual.GetName() or '') if actual else ''
res = {'accion': None}
if project.GetName() == previo.get('proyecto') and 'temporal' in nombre and ' vista ' in nombre:
    for i in range(1, int(project.GetTimelineCount() or 0) + 1):
        t = project.GetTimelineByIndex(i)
        if t and t.GetName() == previo.get('timeline'):
            project.SetCurrentTimeline(t)
            res['accion'] = 'restaurado'
            break
result = res
'''


def _es_temporal_de_vista(nombre):
    return 'temporal' in str(nombre or '') and ' vista ' in str(nombre or '')


def anotar_previo():
    """Guarda en que proyecto/timeline estabas antes de que Resolve cree el timeline temporal de la vista."""
    try:
        import archivos_seguros
        ok, r, _err = resolve_mcp.script(_ANOTAR, timeout=20)
        if ok and isinstance(r, dict) and r.get('timeline') and not _es_temporal_de_vista(r['timeline']):
            archivos_seguros.escribir_json(PREVIO, r)
    except Exception:
        pass


def reparar_pendiente():
    """Si una vista real se cortó a medias y el timeline temporal quedó como el actual, vuelve al de antes y borra los temporales. True si reparó algo."""
    if _ACTIVOS[0] or not PREVIO.exists():
        return False
    try:
        previo = json.loads(PREVIO.read_text(encoding='utf-8'))
        ok, r, _err = resolve_mcp.script(_RESTAURAR % (previo,), timeout=20)
    except Exception:
        return False
    if ok and isinstance(r, dict) and r.get('accion') == 'restaurado':
        time.sleep(3.0)             # se borra DESPUES de des-seleccionarlo (borrarlo recien dejado llego a cerrar Resolve)
        try:
            resolve_mcp.script(_LIMPIAR, timeout=20)
            PREVIO.unlink()
        except Exception:
            pass
        return True
    return False


def limpiar_temporales_luego(segundos=3.0):
    """Borra el timeline temporal de la vista unos segundos despues (borrarlo
    en el acto, recien des-seleccionado, llego a cerrar Resolve)."""
    import threading

    def trabajo():
        time.sleep(segundos)
        try:
            resolve_mcp.script(_LIMPIAR, timeout=20)
            if not _ACTIVOS[0]:
                PREVIO.unlink()
        except Exception:
            pass
    threading.Thread(target=trabajo, daemon=True, name='limpiar-vista-real').start()


def _reducir(origen, destino, alto=ALTO_MINI):
    try:
        from PIL import Image
        with Image.open(origen) as img:
            img = img.convert('RGB')
            if img.height > alto:
                img = img.resize((max(1, round(img.width * alto / img.height)), alto), Image.Resampling.LANCZOS)
            img.save(destino, quality=88)
        return True
    except Exception:
        return False


def _pedir(pedido, timeout=240, al_estado=None):
    """Escribe el pedido, corre el script dentro de Resolve y lee el resultado."""
    PEDIDO.parent.mkdir(parents=True, exist_ok=True)
    PEDIDO.write_text(json.dumps(pedido, ensure_ascii=False, indent=1), encoding='utf-8')
    _ACTIVOS[0] += 1
    try:
        anotar_previo()
        ok, mensaje = resolve_mcp.ejecutar_py(script(), timeout=timeout)
    finally:
        _ACTIVOS[0] -= 1
    try:
        r = json.loads((Path(pedido['salida']) / 'vista_real_resultado.json').read_text(encoding='utf-8'))
    except Exception:
        r = {'ok': False, 'error': mensaje or 'Resolve no dejó resultado'}
    if not ok and not r.get('error'):
        r['error'] = mensaje
    return r


def renderizar_pack(nombre_pack, formato='v', textos=None, sets=None, al_estado=None, abrir_resolve=True):
    """Renderiza en Resolve los sets del pack (todos, o 'sets') y los deja en
    cache. Devuelve (ok, {set: [rutas]} | mensaje de error)."""
    from i18n import tr
    pack = _pack(nombre_pack)
    if pack is None:
        return False, tr('No encuentro el pack «{p}».', p=nombre_pack)
    if getattr(pack, 'kinetic', False):
        return True, cacheadas(nombre_pack, formato, textos)          # su vista viene incluida en el pack (hacer_vista_kinetic.py)
    if formato not in pack.formatos:
        formato = pack.formatos[0] if pack.formatos else 'v'
    textos = textos or TEXTOS_MUESTRA
    prep = resolve_mcp.preparar_resolve(abrir=abrir_resolve, al_estado=al_estado, pagina=None)
    if not prep.get('proyecto'):
        return False, prep.get('motivo') or tr('Resolve no está listo')
    destino = carpeta_de(nombre_pack, formato, textos)
    crudo = Path(tempfile.mkdtemp(prefix='cinecaptions_vista_real_'))
    if al_estado:
        al_estado(tr('Resolve está renderizando «{p}»…', p=pack.nombre))
    pedido = {'modo': 'pack', 'pack': pack.nombre, 'formato': formato,
              'drt': str(pack.ruta_drt(formato) or ''), 'drb': str(pack.ruta_drb(formato) or '') or None,
              'textos': textos, 'sets': sets, 'cuadros': list(CUADROS), 'duracion_s': 2.4, 'salida': str(crudo)}
    inicio = time.time()
    r = _pedir(pedido, al_estado=al_estado)
    limpiar_temporales_luego()
    if not r.get('ok'):
        shutil.rmtree(crudo, ignore_errors=True)
        return False, r.get('error') or tr('Resolve no devolvió imágenes')
    destino.mkdir(parents=True, exist_ok=True)
    por_set, originales = {}, {}
    for img in r.get('imagenes') or []:
        origen = Path(img.get('ruta') or '')
        if not origen.is_file():
            continue
        nombre = f"set{int(img['set']):02d}_{int(img['cuadro']):02d}.jpg"
        if _reducir(origen, destino / nombre):
            por_set.setdefault(str(int(img['set'])), []).append(nombre)
            originales.setdefault(str(int(img['set'])), []).append(str(origen))
    for v in por_set.values():
        v.sort()
    cajas = {k: _caja_del_texto(v) for k, v in originales.items()}
    viejo, viejas_cajas = {}, {}
    try:
        previo = json.loads((destino / 'indice.json').read_text(encoding='utf-8'))
        viejo, viejas_cajas = previo.get('sets') or {}, previo.get('recortes') or {}
    except Exception:
        pass
    viejo.update(por_set)
    viejas_cajas.update({k: v for k, v in cajas.items() if v})
    (destino / 'indice.json').write_text(json.dumps({
        'pack': pack.nombre, 'formato': formato, 'textos': textos, 'sets': viejo, 'recortes': viejas_cajas,
        'resolucion': [r.get('ancho'), r.get('alto')], 'segundos': round(time.time() - inicio, 1),
        'cuando': time.strftime('%Y-%m-%d %H:%M')}, ensure_ascii=False, indent=1), encoding='utf-8')
    shutil.rmtree(crudo, ignore_errors=True)
    return True, cacheadas(nombre_pack, formato, textos)


def renderizar_guion(nombre_pack, cue, posicion_emoji='abajo', al_estado=None, segundos_extra=None):
    """«Comprobar en Resolve» del editor Creativo (estilo «guion»): UN bloque colocado por Resolve con el mismo place_guion_track que usa Generar, sobre un
    timeline temporal vertical, y su fotograma. `cue` es el bloque tal como lo planea el editor (con sus tiempos reales: aquí se llevan a 0,2 s).
    Devuelve (ruta_png | None, mensaje). El timeline y el cabezal del usuario vuelven a quedar como estaban; el temporal lo limpia la siguiente corrida."""
    import copy
    from i18n import tr
    import guion_captions
    import plantillas
    pack = _pack(nombre_pack)
    if pack is None:
        return None, tr('No encuentro el pack «{p}».', p=nombre_pack)
    prep = resolve_mcp.preparar_resolve(abrir=True, al_estado=al_estado, pagina=None)
    if not prep.get('proyecto'):
        return None, prep.get('motivo') or tr('Resolve no está listo')
    c = copy.deepcopy(cue)
    d = 0.2 - float(c['start'])
    c['start'], c['end'] = round(float(c['start']) + d, 3), round(float(c['end']) + d, 3)
    for r in c.get('runs') or []:
        r['t'] = round(float(r.get('t') or c['start']) + d, 3)
        if r.get('fin') is not None:
            r['fin'] = round(float(r['fin']) + d, 3)
    for k in ('emoji_ini', 'emoji_fin'):
        if c.get(k) is not None:
            c[k] = round(float(c[k]) + d, 3)
    for k in ('sfx', 'sfx_archivo', 'sfx_nombre', 'sfx_manual', 'sfx_original', 'sfx_eventos', 'lines'):
        c.pop(k, None)                                             # solo la imagen: sin efectos de sonido
    carpeta = Path(tempfile.gettempdir()) / 'cinecaptions_vista_guion'
    shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True, exist_ok=True)
    datos = guion_captions.escribir([c], carpeta / 'vista.es.guion.json', 'es')
    pl = plantillas.para_manifiesto(pack.nombre, formato_forzado='v')
    track = {'language': 'es', 'style': 'guion', 'data_path': datos, 'srt_path': '', 'fonts': {}, 'adelanto_frames': 0, 'offset_frames': None,
             'plantilla': pl.get('plantilla') if isinstance(pl, dict) and 'plantilla' in pl else pl}
    if c.get('emoji'):
        try:
            import emojis
            track.update(emojis.para_manifiesto([{'emoji': c['emoji']}], posicion_emoji if posicion_emoji in ('abajo', 'arriba') else 'abajo'))
        except Exception:
            pass
    # el fotograma: cuando ya entró todo (la última palabra + 0,25 s), sin pasarse del fin del bloque
    ultima = max([float(r.get('t') or c['start']) for r in c.get('runs') or []] + [c['start']])
    seg = min(c['end'] - 0.1, ultima + 0.25)
    pedido = {'modo': 'guion', 'pack': pack.nombre, 'formato': 'v', 'drt': str(pack.ruta_drt('v') or ''), 'drb': str(pack.ruta_drb('v') or '') or None,
              'track': track, 'cuadros_s': [round(seg, 3)], 'salida': str(carpeta)}
    r = _pedir(pedido, al_estado=al_estado)
    limpiar_temporales_luego()
    for img in r.get('imagenes') or []:
        if img.get('ruta') and Path(img['ruta']).is_file():
            return img['ruta'], ''
    return None, r.get('error') or tr('Resolve no devolvió la imagen')


def renderizar_bloques(nombre_pack, formato, bloques, marca=None, al_estado=None):
    """GO: los bloques de muestra renderizados por Resolve sobre una COPIA
    temporal del timeline (tu video debajo). Devuelve [ruta | None] por bloque."""
    pack = _pack(nombre_pack)
    if pack is None or not bloques:
        return [None] * len(bloques or [])
    if formato not in pack.formatos:
        formato = pack.formatos[0] if pack.formatos else 'v'
    crudo = Path(tempfile.gettempdir()) / 'cinecaptions_vista_go'
    shutil.rmtree(crudo, ignore_errors=True)
    crudo.mkdir(parents=True, exist_ok=True)
    pedido = {'modo': 'bloques', 'pack': pack.nombre, 'formato': formato,
              'drt': str(pack.ruta_drt(formato) or ''), 'drb': str(pack.ruta_drb(formato) or '') or None,
              'bloques': [{'start': float(b['start']), 'end': float(b['end']),
                           'lines': [{'role': l.get('role') or 'main', 'text': l.get('text') or ''}
                                     for l in b.get('lines') or []]} for b in bloques],
              'marca': marca, 'salida': str(crudo)}
    r = _pedir(pedido, al_estado=al_estado)
    limpiar_temporales_luego()
    rutas = [None] * len(bloques)
    for img in r.get('imagenes') or []:
        try:
            k = int(img.get('bloque'))
        except (TypeError, ValueError):
            continue
        if 0 <= k < len(rutas) and img.get('ruta') and Path(img['ruta']).is_file():
            rutas[k] = img['ruta']
    return rutas
