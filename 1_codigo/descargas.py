# CineCaptions · By Cinema Productions
# 1_codigo/descargas.py — descargas grandes que se reanudan y se verifican (SHA-256).
"""
descargas.py  (v5.4.8)
----------------------
Una descarga de cientos de MB que se corta a la mitad no debe empezar de cero ni dejar un archivo roto:

    descargar(url, destino, sha256=None, tam=None, progreso=None)
        baja a `destino + '.parcial'`, la REANUDA con `Range:` si ya había una parte (o si se cortó la conexión), reintenta con espera creciente (2, 4, 8, 16 s),
        comprueba el tamaño y el SHA-256 al terminar y solo entonces la renombra. Si no coincide, borra lo bajado y lanza ValueError (nunca deja un archivo malo).
    sha256_de(ruta)                         el hash de un archivo
    rueda_de_pypi(paquete)                  (url, sha256, nombre, tam) de la rueda de Windows de un paquete de PyPI (para librerías binarias, p. ej. cuBLAS)

Usa certifi si está (los equipos sin los certificados al día fallaban con SSL). Nunca guarda nada fuera de la carpeta de `destino`.
"""
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

AGENTE = 'CineCaptions'


def _contexto_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def sha256_de(ruta, trozo=1 << 20):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        while True:
            b = f.read(trozo)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def descargar(url, destino, sha256=None, tam=None, progreso=None, reintentos=4, timeout=60, cancelar=None):
    """Descarga `url` en `destino` (reanudable y verificada). `cancelar`: función que devuelve True para parar (se lanza InterruptedError y el .parcial se conserva)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.is_file() and (not tam or destino.stat().st_size == tam) and (not sha256 or sha256_de(destino).lower() == sha256.lower()):
        if progreso:
            progreso(1.0)
        return destino
    parcial = destino.with_name(destino.name + '.parcial')
    contexto = _contexto_ssl()
    ultimo_error = None
    for intento in range(reintentos + 1):
        if cancelar and cancelar():
            raise InterruptedError('descarga cancelada')
        hecho = parcial.stat().st_size if parcial.is_file() else 0
        cabeceras = {'User-Agent': AGENTE}
        if hecho:
            cabeceras['Range'] = f'bytes={hecho}-'
        try:
            pedido = urllib.request.Request(url, headers=cabeceras)
            with urllib.request.urlopen(pedido, timeout=timeout, context=contexto) as r:
                codigo = getattr(r, 'status', 200)
                if hecho and codigo != 206:             # el servidor no sabe reanudar: se empieza de cero
                    hecho = 0
                total = tam or ((int(r.headers.get('Content-Length') or 0) + hecho) if r.headers.get('Content-Length') else 0)
                with open(parcial, 'ab' if hecho else 'wb') as f:
                    while True:
                        if cancelar and cancelar():
                            raise InterruptedError('descarga cancelada')
                        bloque = r.read(1 << 20)
                        if not bloque:
                            break
                        f.write(bloque)
                        hecho += len(bloque)
                        if progreso and total:
                            progreso(min(1.0, hecho / total))
                if total and hecho < total:               # el servidor cerró antes de tiempo (sin error): se reanuda desde lo ya bajado
                    raise ConnectionError(f'la conexión se cortó a los {hecho} de {total} bytes')
            ultimo_error = None
            break
        except InterruptedError:
            raise
        except urllib.error.HTTPError as e:
            if e.code == 416 and parcial.is_file():      # «rango no satisfecho»: el .parcial ya era el archivo entero
                ultimo_error = None
                break
            ultimo_error = e
        except Exception as e:                           # red caída, tiempo agotado…: se reintenta reanudando
            ultimo_error = e
        time.sleep(min(16, 2 ** (intento + 1)))
    if ultimo_error is not None:
        raise ConnectionError(f'No se pudo descargar tras {reintentos + 1} intentos: {ultimo_error}')
    if tam and parcial.stat().st_size != tam:
        tamano = parcial.stat().st_size
        parcial.unlink(missing_ok=True)
        raise ValueError(f'Tamaño incorrecto ({tamano} de {tam} bytes): se descartó la descarga')
    if sha256 and sha256_de(parcial).lower() != sha256.lower():
        parcial.unlink(missing_ok=True)
        raise ValueError('La firma SHA-256 no coincide: se descartó la descarga')
    parcial.replace(destino)
    return destino


def rueda_de_pypi(paquete, plataforma='win_amd64'):
    """(url, sha256, nombre_archivo, tamaño) de la rueda (.whl) de esa plataforma en la última versión del paquete de PyPI."""
    pedido = urllib.request.Request(f'https://pypi.org/pypi/{paquete}/json', headers={'User-Agent': AGENTE})
    with urllib.request.urlopen(pedido, timeout=30, context=_contexto_ssl()) as r:
        datos = json.loads(r.read().decode('utf-8'))
    for f in datos.get('urls', []):
        if f.get('packagetype') == 'bdist_wheel' and str(f.get('filename', '')).endswith(f'{plataforma}.whl'):
            return f['url'], (f.get('digests') or {}).get('sha256'), f['filename'], int(f.get('size') or 0)
    raise LookupError(f'{paquete}: no hay rueda para {plataforma}')
