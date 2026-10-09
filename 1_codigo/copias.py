# CineCaptions · By Cinema Productions
# 1_codigo/copias.py — copias de seguridad de ~/DaVinciSubtitles (crear y restaurar un .zip).
"""
copias.py
---------
«Crear copia de seguridad» (esquina del menu lateral) y «Restaurar copia»
(Ajustes > General): un .zip con TODO lo tuyo de ~/DaVinciSubtitles
-proyectos, marcas del editor, recetas, preferencias, reglas de SFX, tus
packs de estilos, la licencia- sin las caches que se rehacen solas.

Las copias van a Documentos\\CineCaptions\\Copias de seguridad, fuera de la
carpeta de datos: si esa carpeta se borra o se estropea, la copia sigue ahi.
"""
import datetime
import json
import os
import shutil
import zipfile
from pathlib import Path

DATOS = Path.home() / 'DaVinciSubtitles'
MARCA = 'cinecaptions_copia.json'
# lo que se rehace solo o es pasajero: no hace falta copiarlo
SIN_COPIA_DIRS = {'emojis_cache', 'sugerencias_cache', 'jobs', 'instalador', '__pycache__'}
SIN_COPIA_ARCH = {'puente.heartbeat', 'puente.arranque.txt', 'puente.relevo', 'bridge_error.txt',
                  'mcp_ultimo_script.txt'}
MAXIMO_ARCHIVO = 400 * 1024 * 1024


def carpeta_copias():
    base = Path.home() / 'Documents'
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 (Documentos, aunque este movido a otra unidad)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                base = Path(buf.value)
        except Exception:
            pass
    return base / 'CineCaptions' / 'Copias de seguridad'


def _archivos():
    if not DATOS.is_dir():
        return []
    salida = []
    for raiz, dirs, archivos in os.walk(DATOS):
        dirs[:] = [d for d in dirs if d not in SIN_COPIA_DIRS]
        for a in archivos:
            if a in SIN_COPIA_ARCH or a.endswith(('.tmp', '.lock', '.done.json')):
                continue
            ruta = Path(raiz) / a
            try:
                if ruta.stat().st_size <= MAXIMO_ARCHIVO:
                    salida.append(ruta)
            except OSError:
                pass
    return salida


def crear(progreso=None):
    """Hace la copia. Devuelve (ruta_zip, n_archivos). progreso(fraccion)."""
    destino_dir = carpeta_copias()
    destino_dir.mkdir(parents=True, exist_ok=True)
    sello = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    destino = destino_dir / f'CineCaptions_copia_{sello}.zip'
    archivos = _archivos()
    tmp = destino.with_suffix('.zip.tmp')
    try:
        from version import APP_VERSION
    except Exception:
        APP_VERSION = ''
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr(MARCA, json.dumps({'programa': 'CineCaptions', 'version': APP_VERSION,
                                      'creada': datetime.datetime.now().isoformat(timespec='seconds'),
                                      'archivos': len(archivos)}, ensure_ascii=False, indent=1))
        for i, ruta in enumerate(archivos):
            try:
                z.write(ruta, ruta.relative_to(DATOS).as_posix())
            except OSError:
                pass
            if progreso and (i % 20 == 0 or i == len(archivos) - 1):
                progreso((i + 1) / max(1, len(archivos)))
    os.replace(tmp, destino)
    return destino, len(archivos)


def listar():
    d = carpeta_copias()
    if not d.is_dir():
        return []
    return sorted(d.glob('CineCaptions_copia_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)


def ultima():
    """datetime de la copia mas reciente, o None."""
    copias = listar()
    if not copias:
        return None
    return datetime.datetime.fromtimestamp(copias[0].stat().st_mtime)


def es_copia(ruta):
    try:
        with zipfile.ZipFile(ruta) as z:
            return MARCA in z.namelist()
    except Exception:
        return False


def restaurar(ruta):
    """Vuelve a poner una copia. ANTES hace una copia de lo que hay ahora
    (por si te equivocaste de archivo). Devuelve la ruta de esa copia previa."""
    if not es_copia(ruta):
        raise ValueError('ese archivo no es una copia de CineCaptions')
    previa, _ = crear()
    with zipfile.ZipFile(ruta) as z:
        for info in z.infolist():
            nombre = info.filename
            if nombre == MARCA or nombre.endswith('/'):
                continue
            destino = (DATOS / nombre).resolve()
            if DATOS.resolve() not in destino.parents:
                continue  # una ruta que intenta salir de la carpeta: fuera
            destino.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as origen, open(destino, 'wb') as f:
                shutil.copyfileobj(origen, f)
    return previa
