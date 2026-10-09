# CineCaptions · By Cinema Productions
# 1_codigo/actualizaciones.py — actualizaciones automáticas: lee un version.json publicado, descarga el instalador, comprueba su huella SHA-256 y lo lanza.
"""
actualizaciones.py  (v5.3.5)
----------------------------
«Buscar actualizaciones», el aviso automático de Inicio (Ajustes > Acerca de). El canal beta ya no se ofrece en la interfaz.

El programa lee un archivo version.json publicado en internet (ver Publicar_Version.ps1, que lo genera y lo sube junto con los instaladores):

    {
      "estable": {"version": "5.3.5", "notas": "Lo nuevo en una o dos líneas", "fecha": "2026-10-08",
                  "archivos": {"windows":    {"url": "https://.../Instalar_CineCaptions_5.3.5.exe",             "sha256": "…", "tam": 202233064},
                               "mac_arm64":  {"url": "https://.../CineCaptions_Mac_AppleSilicon_5.3.5.dmg",     "sha256": "…", "tam": 171370069},
                               "mac_x86_64": {"url": "https://.../CineCaptions_Mac_Intel_5.3.5.dmg",            "sha256": "…", "tam": 188084169}}},
      "beta":    {"version": "5.4.0-beta.1", "archivos": {…}, "notas": "…"}
    }

(El formato viejo, «url» suelta en la versión, sigue valiendo: se abre en el navegador.)

Qué hace cada pieza:
  comprobar()   consulta el manifiesto y dice si hay una versión más nueva que la instalada (con el archivo que le toca a ESTE equipo);
  descargar()   baja el instalador a una carpeta temporal con avance, y SOLO lo da por bueno si su SHA-256 coincide con el del manifiesto;
  instalar()    lo lanza: en Windows el instalador de siempre (cierra el programa, reemplaza la versión y lo vuelve a abrir); en Mac abre el .dmg.
La dirección del manifiesto sale de (en este orden) la variable CINECAPTIONS_URL_ACTUALIZACIONES, la preferencia «url_actualizaciones» y URL_MANIFIESTO.
Nada de esto corre en el hilo de la interfaz (lo llaman correr_en_hilo y un hilo propio).
"""
import hashlib
import json
import os
import platform
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# Donde se publican las versiones: el «latest/download» de GitHub siempre apunta al version.json de la última publicación del repositorio
# de instaladores (público, solo trae los instaladores; el código sigue en el repositorio privado). Se puede cambiar sin recompilar con la
# variable CINECAPTIONS_URL_ACTUALIZACIONES o la preferencia «url_actualizaciones».
URL_MANIFIESTO = 'https://github.com/AlejandroPiedrasanta/CineCaptions-releases/releases/latest/download/version.json'
INTERVALO_AUTO_S = 10                 # el programa mira cada 10 s si hay una versión nueva (con ETag: casi siempre un «304 sin cambios», casi sin tráfico)
INTERVALO_SIN_RED_S = 60              # tras varios fallos seguidos (sin internet) mira cada minuto, sin llenar el Registro


def _partes(v):
    """'5.2.0-beta.3' -> (5, 2, 0, 0, 3): una beta va antes que su estable."""
    m = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-beta\.?(\d+))?', str(v or '').strip())
    if not m:
        return (0, 0, 0, 1, 0)
    a, b, c, beta = m.groups()
    return (int(a), int(b), int(c), 0 if beta is not None else 1, int(beta or 0))


def es_mas_nueva(remota, local):
    return _partes(remota) > _partes(local)


def url_manifiesto():
    v = os.environ.get('CINECAPTIONS_URL_ACTUALIZACIONES')
    if not v:
        try:
            import ajustes_ui
            v = str(ajustes_ui.leer_prefs().get('url_actualizaciones') or '')
        except Exception:
            v = ''
    return (v or URL_MANIFIESTO).strip()


def configurado():
    return bool(url_manifiesto())


def clave_plataforma():
    """La clave de «archivos» que le toca a este equipo."""
    if sys.platform.startswith('win'):
        return 'windows'
    if sys.platform == 'darwin':
        return 'mac_arm64' if platform.machine().lower() in ('arm64', 'aarch64') else 'mac_x86_64'
    return 'linux'


def _contexto_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _abrir(url, version_local, timeout):
    pedido = urllib.request.Request(url, headers={'User-Agent': f'CineCaptions/{version_local}'})
    return urllib.request.urlopen(pedido, timeout=timeout, context=_contexto_ssl())


def comprobar(version_local, canal_beta=False, timeout=12):
    """{'estado': 'al_dia'|'nueva'|'sin_canal'|'error', 'version', 'url', 'notas', 'archivo': {url, sha256, tam}|None, 'mensaje'}"""
    url = url_manifiesto()
    if not url:
        return {'estado': 'sin_canal'}
    try:
        with _abrir(url, version_local, timeout) as r:
            datos = json.loads(r.read().decode('utf-8'))
            _CACHE.update(url=url, etag=r.headers.get('ETag'), datos=datos)
    except Exception as e:
        return {'estado': 'error', 'mensaje': str(e)}
    return _interpretar(datos, version_local, canal_beta)


_CACHE = {'url': None, 'etag': None, 'datos': None}


def comprobar_ligero(version_local, canal_beta=False, timeout=8):
    """Como comprobar(), pensado para repetirse cada pocos segundos: manda el ETag de la última respuesta y, si el manifiesto no cambió, el servidor
    contesta 304 sin cuerpo (y se reutiliza lo ya leído)."""
    url = url_manifiesto()
    if not url:
        return {'estado': 'sin_canal'}
    cabeceras = {'User-Agent': f'CineCaptions/{version_local}'}
    if _CACHE.get('etag') and _CACHE.get('url') == url and _CACHE.get('datos') is not None:
        cabeceras['If-None-Match'] = _CACHE['etag']
    try:
        pedido = urllib.request.Request(url, headers=cabeceras)
        with urllib.request.urlopen(pedido, timeout=timeout, context=_contexto_ssl()) as r:
            datos = json.loads(r.read().decode('utf-8'))
            _CACHE.update(url=url, etag=r.headers.get('ETag'), datos=datos)
    except urllib.error.HTTPError as e:
        if e.code == 304 and _CACHE.get('datos') is not None:
            datos = _CACHE['datos']
        else:
            return {'estado': 'error', 'mensaje': f'HTTP {e.code}'}
    except Exception as e:
        return {'estado': 'error', 'mensaje': str(e)}
    return _interpretar(datos, version_local, canal_beta)


def _interpretar(datos, version_local, canal_beta=False):
    candidatos = [datos.get('estable') or {}]
    if canal_beta:
        candidatos.append(datos.get('beta') or {})
    mejor = max((c for c in candidatos if c.get('version')), key=lambda c: _partes(c['version']), default=None)
    if mejor and es_mas_nueva(mejor['version'], version_local):
        archivo = (mejor.get('archivos') or {}).get(clave_plataforma())
        return {'estado': 'nueva', 'version': mejor['version'], 'url': (archivo or {}).get('url') or mejor.get('url') or '',
                'notas': mejor.get('notas') or '', 'fecha': mejor.get('fecha') or '', 'archivo': archivo if isinstance(archivo, dict) and archivo.get('url') else None}
    return {'estado': 'al_dia', 'version': version_local}


def carpeta_descargas():
    c = Path(tempfile.gettempdir()) / 'cinecaptions_actualizacion'
    c.mkdir(parents=True, exist_ok=True)
    return c


def sha256_de(ruta, bloque=1 << 20):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        while True:
            b = f.read(bloque)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def descargar(archivo, version_local='', progreso=None, cancelado=None, timeout=30):
    """Baja el instalador a una carpeta temporal y devuelve su ruta. `archivo` = {'url', 'sha256', 'tam'}; progreso(bytes, total) en cada trozo;
    cancelado() -> True corta. Lanza RuntimeError si la descarga se corta o si la huella NO coincide (el archivo se borra: nunca se ejecuta)."""
    url = archivo['url']
    nombre = os.path.basename(url.split('?')[0]) or 'CineCaptions_actualizacion.bin'
    destino = carpeta_descargas() / nombre
    parcial = destino.with_name(destino.name + '.parte')
    for p in carpeta_descargas().glob('*'):                 # lo descargado de otras veces se limpia (también un instalador igual: se vuelve a comprobar)
        try:
            p.unlink()
        except OSError:
            pass
    esperado = str(archivo.get('sha256') or '').lower()
    total = int(archivo.get('tam') or 0)
    hecho = 0
    try:
        with _abrir(url, version_local, timeout) as r, open(parcial, 'wb') as f:
            total = int(r.headers.get('Content-Length') or total or 0)
            ultimo = 0.0
            while True:
                if cancelado and cancelado():
                    raise RuntimeError('descarga cancelada')
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                hecho += len(b)
                if progreso and time.time() - ultimo > 0.15:
                    ultimo = time.time()
                    progreso(hecho, total)
        if progreso:
            progreso(hecho, total or hecho)
        if total and hecho != total:
            raise RuntimeError(f'la descarga quedó a medias ({hecho} de {total} bytes)')
        if esperado:
            real = sha256_de(parcial)
            if real != esperado:
                raise RuntimeError('la huella (SHA-256) del archivo descargado NO coincide con la publicada: no se instala')
        else:
            raise RuntimeError('la actualización no trae huella SHA-256: no se instala sin poder comprobarla')
        if destino.exists():
            destino.unlink()
        parcial.rename(destino)
        return destino
    except BaseException:
        try:
            parcial.unlink()
        except OSError:
            pass
        raise


def instalar(ruta):
    """Lanza lo descargado y devuelve True si arrancó. Windows: el instalador (se instala solo, cierra y reemplaza esta versión y vuelve a abrir
    CineCaptions). Mac: abre el .dmg (el usuario abre el .pkg que trae)."""
    ruta = str(ruta)
    try:
        if sys.platform.startswith('win'):
            # DETACHED_PROCESS: sobrevive al cierre del programa. cwd = la carpeta del propio instalador: si heredara la del programa (los accesos
            # directos la fijan a la carpeta de instalación) Windows no dejaría renombrarla ni reemplazar la versión instalada.
            subprocess.Popen([ruta, '/empezar'], close_fds=True, creationflags=0x00000008, cwd=os.path.dirname(ruta) or tempfile.gettempdir())
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', ruta], close_fds=True)
        else:
            return False
        return True
    except OSError:
        return False
