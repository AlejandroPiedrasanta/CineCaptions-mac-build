# CineCaptions · By Cinema Productions
# 1_codigo/emojis_animados.py — emojis ANIMADOS del selector: Noto Animated Emoji (Google, CC BY 4.0), bajados al pedirlos y cacheados.
"""
emojis_animados.py  (v5.4)
--------------------------
El selector de emojis los muestra moviéndose. Fuente: «Noto Emoji Animation» (Google, licencia CC BY 4.0), unos 3 700
emojis; cada uno se baja la primera vez que se ve (webp de 512 px, ~600 KB), se reduce a 72 px con Pillow (~40 KB, la
mitad de los cuadros) y queda en ~/DaVinciSubtitles/emojis_animados. Sin internet o sin versión animada de ese emoji,
el selector sigue mostrando la imagen fija de siempre.

  frame(glifo, t, al_listo) -> QPixmap | None   el cuadro que toca en el instante t (segundos); None = aún no hay
  y, si falta, lo pide en segundo plano (al_listo(glifo) se llama en el hilo de la interfaz cuando llega).
"""
import io
import queue
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap

CARPETA = Path.home() / 'DaVinciSubtitles' / 'emojis_animados'
LADO = 72
_URL = 'https://fonts.gstatic.com/s/e/notoemoji/latest/%s/512.webp'
_MAX_RAM = 160

_RAM = OrderedDict()          # glifo -> (lista de QImage, ms por cuadro) o None (no hay versión animada)
_PIXMAPS = {}                 # (glifo, k) -> QPixmap (se hacen en el hilo de la interfaz)
_PEDIDOS = {}                 # glifo -> [callbacks]
_COLA = queue.LifoQueue()     # lo último que se ve se baja primero
_LOCK = threading.Lock()
_HILOS = []
_DESCARGA = {'total': 0, 'hechos': 0, 'fallos': 0, 'activo': False, 'sin_red': False}


def hex_de(glifo, sin_fe0f=False):
    return '_'.join(f'{ord(c):x}' for c in glifo if not (sin_fe0f and ord(c) == 0xFE0F))


def ruta_de(glifo):
    return CARPETA / (hex_de(glifo) + '.webp')


def _marca_sin_version(glifo):
    return CARPETA / (hex_de(glifo) + '.no')


def _bajar(glifo):
    """Baja y reduce. Devuelve True si quedó el archivo en caché."""
    from PIL import Image
    crudo = None
    todo_404 = True
    for h in dict.fromkeys((hex_de(glifo), hex_de(glifo, True))):
        try:
            req = urllib.request.Request(_URL % h, headers={'User-Agent': 'CineCaptions'})
            with urllib.request.urlopen(req, timeout=20) as r:
                crudo = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code != 404:
                todo_404 = False
        except Exception:
            todo_404 = False            # sin red: no es que ese emoji no exista, se reintenta otro dia
    CARPETA.mkdir(parents=True, exist_ok=True)
    if not crudo:
        if todo_404:
            _marca_sin_version(glifo).write_bytes(b'')       # Google no tiene version animada de ese emoji
        else:
            _DESCARGA['sin_red'] = True
        return False
    im = Image.open(io.BytesIO(crudo))
    n = getattr(im, 'n_frames', 1)
    cuadros, duraciones = [], []
    for i in range(0, n, 2):
        im.seek(i)
        d = int(im.info.get('duration') or 33)
        if i + 1 < n:
            im.seek(i + 1)
            d += int(im.info.get('duration') or 33)
            im.seek(i)
        cuadros.append(im.convert('RGBA').resize((LADO, LADO), Image.LANCZOS))
        duraciones.append(max(20, d))
    destino = ruta_de(glifo)
    temporal = destino.with_suffix('.tmp')
    cuadros[0].save(temporal, format='WEBP', save_all=True, append_images=cuadros[1:], duration=duraciones, loop=0,
                    quality=72, method=4)
    temporal.replace(destino)
    return True


def _leer(glifo):
    """(lista de QImage, ms por cuadro) desde la caché de disco, o None."""
    from PIL import Image
    ruta = ruta_de(glifo)
    if not ruta.is_file():
        return None
    im = Image.open(ruta)
    cuadros, total = [], 0
    for i in range(getattr(im, 'n_frames', 1)):
        im.seek(i)
        total += int(im.info.get('duration') or 40)
        rgba = im.convert('RGBA')
        qi = QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
        cuadros.append(qi)
    if not cuadros:
        return None
    return (cuadros, max(20, total // len(cuadros)))


def _trabajo():
    while True:
        glifo = _COLA.get()
        resultado = None
        try:
            if not ruta_de(glifo).is_file() and not _marca_sin_version(glifo).is_file():
                _bajar(glifo)
            resultado = _leer(glifo)
        except Exception:
            resultado = None
            try:
                import registro
                if _DESCARGA.setdefault('errores_anotados', 0) < 5:
                    _DESCARGA['errores_anotados'] += 1
                    registro.excepcion(origen=f'emoji animado {hex_de(glifo)}')
            except Exception:
                pass
        with _LOCK:
            _RAM[glifo] = resultado
            while len(_RAM) > _MAX_RAM:
                viejo, _ = _RAM.popitem(last=False)
                for k in [k for k in _PIXMAPS if k[0] == viejo]:
                    _PIXMAPS.pop(k, None)
            avisos = _PEDIDOS.pop(glifo, [])
        try:
            import qt_kit as ui
            for cb in avisos:
                ui.ejecutar_en_ui(lambda cb=cb, g=glifo: cb(g))
        except Exception:
            pass


def _asegurar_hilos():
    while len(_HILOS) < 3:
        t = threading.Thread(target=_trabajo, daemon=True, name='emojis-animados')
        t.start()
        _HILOS.append(t)


def pedir(glifo, al_listo=None):
    with _LOCK:
        if glifo in _RAM:
            return
        if glifo in _PEDIDOS:
            if al_listo and al_listo not in _PEDIDOS[glifo]:
                _PEDIDOS[glifo].append(al_listo)
            return
        _PEDIDOS[glifo] = [al_listo] if al_listo else []
    _asegurar_hilos()
    _COLA.put(glifo)


def frame(glifo, t, al_listo=None):
    """El cuadro de ese emoji en el instante t (s), o None si todavía no hay animación (la pide en segundo plano)."""
    with _LOCK:
        datos = _RAM.get(glifo, False)
        if datos:
            _RAM.move_to_end(glifo)
    if datos is False:
        pedir(glifo, al_listo)
        return None
    if not datos:
        return None
    cuadros, ms = datos
    k = int(t * 1000 / ms) % len(cuadros)
    pm = _PIXMAPS.get((glifo, k))
    if pm is None:
        pm = QPixmap.fromImage(cuadros[k])
        _PIXMAPS[(glifo, k)] = pm
    return pm


# ---------------------------------------------------------------------------------------------------------------------
# Descarga de TODOS los animados del catalogo en segundo plano (al abrir el programa), con progreso para la pantalla de estado.


def estado():
    """(hechos, total, activo, fallos)"""
    return (_DESCARGA['hechos'], _DESCARGA['total'], _DESCARGA['activo'], _DESCARGA['fallos'])


def precargar_todo(glifos):
    """Baja y reduce los animados que falten (2 hilos). Los que ya estan en disco cuentan como hechos sin red."""
    if _DESCARGA['activo']:
        return
    glifos = [g for g in dict.fromkeys(glifos) if g]
    _DESCARGA.update(total=len(glifos), hechos=0, fallos=0, activo=True, sin_red=False)
    pendientes = queue.Queue()
    for g in glifos:
        pendientes.put(g)

    def hilo():
        while True:
            try:
                g = pendientes.get_nowait()
            except queue.Empty:
                return
            try:
                if ruta_de(g).is_file():
                    pass
                elif _marca_sin_version(g).is_file():
                    _DESCARGA['fallos'] += 1
                elif _DESCARGA['sin_red']:
                    _DESCARGA['fallos'] += 1
                else:
                    if not _bajar(g):
                        _DESCARGA['fallos'] += 1
            except Exception:
                _DESCARGA['fallos'] += 1
            _DESCARGA['hechos'] += 1

    hilos = [threading.Thread(target=hilo, daemon=True, name='emojis-descarga') for _ in range(2)]
    for h in hilos:
        h.start()

    def vigilar():
        for h in hilos:
            h.join()
        _DESCARGA['activo'] = False
    threading.Thread(target=vigilar, daemon=True).start()


# ---------------------------------------------------------------------------------------------------------------------
# v5.5: la secuencia PARA RESOLVE. El emoji animado viaja como secuencia de PNG (256 px, con transparencia, a 30 cuadros/s)
# y el script la importa como UN clip que se mueve: antes llegaba un PNG fijo.
CARPETA_SEQ = Path.home() / 'DaVinciSubtitles' / 'emojis_secuencia'
LADO_SEQ = 256
FPS_SEQ = 30
MAX_SEGUNDOS_SEQ = 3.0


def _descargar_crudo(glifo):
    """Los bytes del webp de 512 px (o None: sin red / sin versión animada)."""
    todo_404 = True
    for h in dict.fromkeys((hex_de(glifo), hex_de(glifo, True))):
        try:
            req = urllib.request.Request(_URL % h, headers={'User-Agent': 'CineCaptions'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 404:
                todo_404 = False
        except Exception:
            todo_404 = False
    if todo_404:
        try:
            CARPETA.mkdir(parents=True, exist_ok=True)
            _marca_sin_version(glifo).write_bytes(b'')
        except OSError:
            pass
    return None


def secuencia_resolve(glifo):
    """{'patron': ruta con %04d, 'n': cuadros, 'fps': 30} de la secuencia PNG de ese emoji, o None si no tiene versión animada
    (se queda el PNG fijo). Se baja y se hace UNA vez; corre en el hilo de trabajo (puede tardar un par de segundos)."""
    import json
    carpeta = CARPETA_SEQ / hex_de(glifo)
    meta = carpeta / 'meta.json'
    try:
        if meta.is_file():
            datos = json.loads(meta.read_text(encoding='utf-8'))
            if Path(datos['patron'] % 1).is_file():
                return datos
        if _marca_sin_version(glifo).is_file():
            return None
        crudo = _descargar_crudo(glifo)
        if not crudo:
            return None
        from PIL import Image
        im = Image.open(io.BytesIO(crudo))
        n = getattr(im, 'n_frames', 1)
        if n < 2:
            return None
        tiempos, total = [], 0
        for i in range(n):
            im.seek(i)
            tiempos.append(total)
            total += max(10, int(im.info.get('duration') or 33))
        largo_s = min(MAX_SEGUNDOS_SEQ, total / 1000.0)
        cuantos = max(2, int(round(largo_s * FPS_SEQ)))
        carpeta.mkdir(parents=True, exist_ok=True)
        for k in range(cuantos):
            ms = (k * 1000.0 / FPS_SEQ)
            j = max(i for i, t in enumerate(tiempos) if t <= ms)
            im.seek(j)
            im.convert('RGBA').resize((LADO_SEQ, LADO_SEQ), Image.LANCZOS).save(carpeta / f'e_{k + 1:04d}.png')
        datos = {'patron': str(carpeta / 'e_%04d.png'), 'n': cuantos, 'fps': FPS_SEQ}
        meta.write_text(json.dumps(datos), encoding='utf-8')
        return datos
    except Exception:
        return None
