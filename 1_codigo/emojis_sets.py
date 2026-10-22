# CineCaptions · By Cinema Productions
# 1_codigo/emojis_sets.py — SETS de emojis (estilos de imagen) que se bajan al pedirlos: Fluent 3D completo (Microsoft, MIT) y Noto de Google (Apache 2.0).
"""
emojis_sets.py  (v5.5)
----------------------
El programa trae 271 emojis Fluent 3D y, para el resto, dibuja los del sistema (planos). Aquí está lo que falta para que TODOS los emojis puedan verse en 3D (u otro estilo):

    fluent3d   Fluent Emoji 3D de Microsoft (licencia MIT), ~1 280 de los 1 390 del catálogo. Se bajan de jsDelivr (el repositorio microsoft/fluentui-emoji), uno por uno, la primera
               vez que se usan, y quedan en ~/DaVinciSubtitles/emojis_sets/fluent3d/<id>.png (256 px). `2_recursos/emojis/fluent_mapa.json` dice dónde está cada uno (id → ruta).
    noto       Noto Emoji de Google (CC BY 4.0; PNG de 512 px reducidos a 256, de fonts.gstatic.com), todos por su código Unicode.

Sin internet (o sin el emoji en ese set) el programa sigue con lo de siempre: el Fluent que trae, o el del sistema. Los emojis ANIMADOS (Noto Animated, CC BY 4.0) siguen en emojis_animados.py.
Por qué no LottieFiles: bajar de allí exige una cuenta y su licencia no permite redistribuir las animaciones dentro de otra aplicación; Fluent y Noto sí se pueden usar y repartir.

    ruta(set, id)                     el PNG ya bajado (o None)
    asegurar(set, emoji)              lo baja ahora si falta (hasta ~20 s) y devuelve la ruta, o None
    pedir(set, emoji)                 lo pide en segundo plano
    bajar_todo(set, emojis, ...)      baja todos los que faltan (con progreso y cancelación)
"""
import json
import os
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures.thread import ThreadPoolExecutor      # v5.41: 3.15 la expone «lazy» en el paquete y el .exe no la despertaba
from pathlib import Path

CARPETA = Path.home() / 'DaVinciSubtitles' / 'emojis_sets'
LADO = 256
SETS = {
    'fluent3d': {'nombre': '3D (Microsoft Fluent)', 'licencia': 'MIT © Microsoft Corporation'},
    'noto': {'nombre': 'Google (Noto)', 'licencia': 'CC BY 4.0 © Google LLC (Noto Emoji)'},
}
_URL_FLUENT = ('https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/%s', 'https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/%s')
_URL_NOTO = ('https://fonts.gstatic.com/s/e/notoemoji/latest/%s/512.png',)          # el mismo servidor de los Noto animados (emojis_animados.py)
_MAPA = {}
_LOCK = threading.Lock()
_COLA = queue.Queue()
_HILO = []
_SIN_RED = {'hasta': 0.0}            # tras un fallo de red no se insiste durante un rato (cada intento tarda hasta 20 s)


def nombre(estilo):
    return SETS.get(estilo, {}).get('nombre', estilo)


def _mapa_fluent():
    if 'fluent' not in _MAPA:
        datos = {}
        try:
            import emojis
            datos = json.loads((emojis.carpeta() / 'fluent_mapa.json').read_text(encoding='utf-8'))
        except Exception:
            datos = {}
        _MAPA['fluent'] = datos if isinstance(datos, dict) else {}
    return _MAPA['fluent']


def hex_de(glifo, sin_fe0f=False):
    return '_'.join(f'{ord(c):x}' for c in str(glifo or '') if not (sin_fe0f and ord(c) == 0xFE0F))


def carpeta_de(estilo):
    return CARPETA / estilo


def ruta(estilo, eid):
    """El PNG del emoji `eid` en ese set si ya está bajado, o None."""
    r = carpeta_de(estilo) / f'{eid}.png'
    try:
        return r if r.is_file() and r.stat().st_size > 200 else None
    except OSError:
        return None


def hay(estilo, emoji):
    """¿Ese set tiene imagen para ese emoji (se pueda bajar o ya esté)? emoji = {'id', 'glifo', …}."""
    if estilo == 'fluent3d':
        return str(emoji.get('id')) in _mapa_fluent()
    if estilo == 'noto':
        return bool(emoji.get('glifo'))
    return False


def _urls(estilo, emoji):
    if estilo == 'fluent3d':
        rel = _mapa_fluent().get(str(emoji.get('id')))
        if not rel:
            return []
        rel = urllib.parse.quote(rel, safe='/')
        return [u % rel for u in _URL_FLUENT]
    if estilo == 'noto':
        glifo = emoji.get('glifo') or ''
        salida = []
        for h in dict.fromkeys((hex_de(glifo, True), hex_de(glifo))):
            salida += [u % h for u in _URL_NOTO]
        return salida
    return []


def _descargar(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'CineCaptions'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def bajar(estilo, emoji):
    """Baja y guarda el PNG (256 px) de ese emoji. True si queda en caché. Sin internet devuelve False y no insiste durante 60 s."""
    if ruta(estilo, emoji['id']) is not None:
        return True
    if time.time() < _SIN_RED['hasta']:
        return False
    import io
    from PIL import Image
    crudo = None
    todo_404 = True
    for url in _urls(estilo, emoji):
        try:
            crudo = _descargar(url)
            break
        except urllib.error.HTTPError as e:
            if e.code != 404:
                todo_404 = False
        except Exception:
            todo_404 = False
    if crudo is None:
        if not todo_404:
            _SIN_RED['hasta'] = time.time() + 60.0
        return False
    try:
        with Image.open(io.BytesIO(crudo)) as img:
            img = img.convert('RGBA')
            if max(img.size) > LADO:
                img.thumbnail((LADO, LADO), Image.LANCZOS)
            destino = carpeta_de(estilo) / f"{emoji['id']}.png"
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + f'.{os.getpid()}.{threading.get_ident()}.tmp')
            img.save(temporal, format='PNG')
            os.replace(temporal, destino)
        return True
    except Exception:
        return False


def asegurar(estilo, emoji):
    """La ruta del PNG, bajándolo ahora si falta. None si no se pudo (sin internet, o ese set no tiene ese emoji)."""
    if estilo not in SETS or not hay(estilo, emoji):
        return None
    if ruta(estilo, emoji['id']) is None:
        bajar(estilo, emoji)
    return ruta(estilo, emoji['id'])


def _trabajo():
    while True:
        estilo, emoji, al_listo = _COLA.get()
        try:
            if bajar(estilo, emoji) and al_listo:
                al_listo(emoji['id'])
        except Exception:
            pass


def pedir(estilo, emoji, al_listo=None):
    """Lo pide en segundo plano (una cola con 2 hilos); `al_listo(id)` se llama desde el hilo de trabajo cuando llega."""
    if estilo not in SETS or not hay(estilo, emoji) or ruta(estilo, emoji['id']) is not None:
        return
    with _LOCK:
        while len(_HILO) < 2:
            h = threading.Thread(target=_trabajo, daemon=True)
            h.start()
            _HILO.append(h)
    _COLA.put((estilo, emoji, al_listo))


def pendientes():
    """Cuántos emojis hay en la cola de descargas en segundo plano."""
    return _COLA.qsize()


def faltan(estilo, emojis):
    return [e for e in emojis if hay(estilo, e) and ruta(estilo, e['id']) is None]


def bajar_todo(estilo, emojis, al_progreso=None, cancelar=None, hilos=6):
    """Baja todos los que faltan. al_progreso(hechos, total, fallos) tras cada uno; cancelar() -> True para parar. Devuelve (hechos, fallos)."""
    pendientes = faltan(estilo, emojis)
    total = len(pendientes)
    estado = {'hechos': 0, 'fallos': 0}
    _SIN_RED['hasta'] = 0.0

    def uno(e):
        if cancelar and cancelar():
            return
        ok = bajar(estilo, e)
        with _LOCK:
            estado['hechos' if ok else 'fallos'] += 1
            h, f = estado['hechos'], estado['fallos']
        if al_progreso:
            al_progreso(h, total, f)
    with ThreadPoolExecutor(max_workers=max(1, int(hilos))) as pool:
        list(pool.map(uno, pendientes))
    return estado['hechos'], estado['fallos']
