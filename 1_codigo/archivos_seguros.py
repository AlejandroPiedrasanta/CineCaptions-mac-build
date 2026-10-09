# CineCaptions · By Cinema Productions
# 1_codigo/archivos_seguros.py — escritura atómica de JSON/texto (preferencias, marcas, proyectos): un corte o dos hilos ya no dejan archivos a medias.
"""
Antes cada módulo hacía `ruta.write_text(...)`: el archivo se VACÍA primero y se llena después. Un corte de luz, un cierre forzado o
un segundo hilo que leyera en ese instante veía un JSON a medias, lo daba por «no hay nada» y, al guardar encima, borraba todas las
preferencias o las marcas del usuario. Aquí:

  * escribir_texto / escribir_json : escribe en un archivo temporal del MISMO directorio, lo fuerza a disco y lo cambia por el
                                     definitivo de un solo paso (os.replace, atómico). Quien lee ve siempre el archivo viejo
                                     completo o el nuevo completo. Con respaldo=True deja antes una copia «.bak» del anterior.
  * leer_json                      : lee un JSON; si el principal está roto prueba con el «.bak»; si no, devuelve el valor por defecto.
  * mezclar_json                   : lee-modifica-escribe bajo un cerrojo (dos hilos que guardan claves distintas no se pisan) y,
                                     si el archivo existía pero estaba roto, lo aparta como «.roto» en vez de borrarlo en silencio.
"""
import json
import os
import shutil
import threading
import time
from pathlib import Path

_CERROJO = threading.RLock()


def _reemplazar(origen, destino):
    """os.replace con reintentos: en Windows un antivirus, el indexador o un lector pueden tener el archivo abierto un instante."""
    for intento in range(20):
        try:
            os.replace(origen, destino)
            return
        except PermissionError:
            if intento == 19:
                raise
            time.sleep(min(0.08, 0.01 * (intento + 1)))


def escribir_texto(ruta, texto, encoding='utf-8', respaldo=False):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(f'{ruta.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        with open(tmp, 'w', encoding=encoding) as f:
            f.write(texto)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        if respaldo and ruta.exists():
            try:
                shutil.copy2(ruta, ruta.with_name(ruta.name + '.bak'))
            except OSError:
                pass
        _reemplazar(tmp, ruta)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return ruta


def escribir_json(ruta, datos, respaldo=False, **opciones):
    opciones.setdefault('ensure_ascii', False)
    return escribir_texto(ruta, json.dumps(datos, **opciones), respaldo=respaldo)


def _leer(ruta):
    """Lee el JSON; si Windows lo tiene bloqueado justo ahora (otro hilo lo está cambiando) reintenta unos milisegundos."""
    for intento in range(8):
        try:
            return json.loads(Path(ruta).read_text(encoding='utf-8'))
        except PermissionError:
            if intento == 7:
                raise
            time.sleep(0.01 * (intento + 1))


def leer_json(ruta, defecto=None, con_respaldo=False):
    ruta = Path(ruta)
    try:
        return _leer(ruta)
    except Exception:
        if con_respaldo:
            try:
                return _leer(ruta.with_name(ruta.name + '.bak'))
            except Exception:
                pass
        return defecto


def mezclar_json(ruta, cambios, **opciones):
    """Mezcla `cambios` en el diccionario guardado (sin tocar el resto de claves) y lo escribe de forma atómica. True si se guardó."""
    ruta = Path(ruta)
    with _CERROJO:
        actual = None
        try:
            actual = _leer(ruta)
        except FileNotFoundError:
            actual = {}
        except Exception:
            # existía pero no se pudo leer: se aparta (para poder recuperarlo) en vez de pisarlo con un diccionario casi vacío
            try:
                shutil.copy2(ruta, ruta.with_name(ruta.name + '.roto'))
            except OSError:
                pass
            actual = {}
        if not isinstance(actual, dict):
            actual = {}
        actual.update(cambios)
        try:
            escribir_json(ruta, actual, **opciones)
            return True
        except OSError:
            return False
