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
v5.52: el manifiesto lleva además "firma": {"alg": "ed25519", "clave": "<id>", "valor": "<base64>"} (3_compilar/firmar_manifiesto.py, desde
Publicar_Version.ps1) y el programa NO ofrece nada sin una firma válida de CLAVES_FIRMA: aunque alguien entrara en la cuenta de GitHub o
cambiara la dirección del manifiesto, no podría repartir un instalador suyo (la huella SHA-256 de cada instalador va dentro de lo firmado).

Qué hace cada pieza:
  comprobar()   consulta el manifiesto y dice si hay una versión más nueva que la instalada (con el archivo que le toca a ESTE equipo);
  descargar()   baja el instalador a una carpeta temporal con avance, y SOLO lo da por bueno si su SHA-256 coincide con el del manifiesto;
  instalar()    lo lanza: en Windows el instalador de siempre (cierra el programa, reemplaza la versión y lo vuelve a abrir); en Mac abre el .dmg.
La dirección del manifiesto sale de (en este orden) la variable CINECAPTIONS_URL_ACTUALIZACIONES, la preferencia «url_actualizaciones» y URL_MANIFIESTO.
Nada de esto corre en el hilo de la interfaz (lo llaman correr_en_hilo y un hilo propio).
"""
import base64
import hashlib
import json
import os
import platform
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import firma_ed25519

# Donde se publican las versiones: el «latest/download» de GitHub siempre apunta al version.json de la última publicación del repositorio
# de instaladores (público, solo trae los instaladores; el código sigue en el repositorio privado). Se puede cambiar sin recompilar con la
# variable CINECAPTIONS_URL_ACTUALIZACIONES o la preferencia «url_actualizaciones».
URL_MANIFIESTO = 'https://github.com/AlejandroPiedrasanta/CineCaptions-releases/releases/latest/download/version.json'
# v5.52: claves PÚBLICAS que pueden firmar el manifiesto (id → hex). Las privadas NUNCA van al repositorio: ~/CineCaptions_claves
# (la de reserva, copiada aparte por si se pierde la principal). Perder las dos = los programas instalados ya no aceptan actualizaciones.
CLAVES_FIRMA = {
    '7a4e413e': '64d8646c1df645cb148402eb08066d45cb6c510508d54588779b294451a9225a',   # principal
    'de5653c3': 'cb292941636c7b8c59cad39ca499a7795d0a27082d1f614328e9e87b61b66252',   # reserva
}
INTERVALO_AUTO_S = 10                 # el programa mira cada 10 s si hay una versión nueva (con ETag: casi siempre un «304 sin cambios», casi sin tráfico)
INTERVALO_SIN_RED_S = 60              # tras varios fallos seguidos (sin internet) mira cada minuto, sin llenar el Registro


def _partes(v):
    """'5.2.0-beta.3' -> (5, 2, 0, 0, 3): una beta va antes que su estable. v5.20: también de DOS números ('5.20' = 5.20.0; desde la 5.20 las
    versiones son 5.20, 5.21… en vez de 5.5.x)."""
    m = re.match(r'(\d+)\.(\d+)(?:\.(\d+))?(?:-beta\.?(\d+))?', str(v or '').strip())
    if not m:
        return (0, 0, 0, 1, 0)
    a, b, c, beta = m.groups()
    return (int(a), int(b), int(c or 0), 0 if beta is not None else 1, int(beta or 0))


def corta(v):
    """v5.20: como se ENSEÑA una versión: el manifiesto publica «5.20.0» (los 5.5.x instalados solo entienden x.y.z) y aquí se ve «5.20»."""
    m = re.fullmatch(r'(\d+)\.(\d+)\.0((?:-beta\.?\d+)?)', str(v or '').strip())
    if m and int(m.group(2)) >= 20:
        return f'{m.group(1)}.{m.group(2)}{m.group(3)}'
    return str(v or '')


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
        return 'mac_arm64' if platform.machine().lower() in ('arm64', 'aarch64') or mac_con_rosetta() else 'mac_x86_64'
    return 'linux'


def mac_con_rosetta():
    """v5.88 (pedido «prueba diferentes modelos de Mac»): la versión Intel abierta en una Mac con chip de Apple (Rosetta) ve
    platform.machine() = «x86_64» y se actualizaba SIEMPRE a la Intel (más lenta y sin el motor de IA de Apple Silicon). Con Rosetta
    `sysctl.proc_translated` vale 1: la actualización le trae la de Apple Silicon."""
    if sys.platform != 'darwin':
        return False
    if 'v' not in _ROSETTA:                     # (una vez por sesión; se llama al leer el manifiesto, en el hilo de la búsqueda)
        try:
            import subprocess
            r = subprocess.run(['/usr/sbin/sysctl', '-n', 'sysctl.proc_translated'], capture_output=True, text=True, timeout=5)
            _ROSETTA['v'] = r.stdout.strip() == '1'
        except Exception:
            _ROSETTA['v'] = False
    return _ROSETTA['v']


_ROSETTA = {}


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
    ultimo = ''
    for intento in (1, 2):                                # un fallo suelto de red (recién instalado, VPN, DNS) se reintenta una vez antes de rendirse
        try:
            with _abrir(url, version_local, timeout) as r:
                datos = json.loads(r.read().decode('utf-8'))
                _CACHE.update(url=url, etag=r.headers.get('ETag'), datos=datos)
            return _interpretar(datos, version_local, canal_beta)
        except Exception as e:
            ultimo = str(e)
            if intento == 1:
                time.sleep(1.5)
    return {'estado': 'error', 'mensaje': ultimo}


def explicar_fallo(mensaje):
    """Una frase CLARA para el usuario a partir del texto crudo de un fallo de red al buscar actualizaciones (el crudo va al Registro)."""
    m = str(mensaje or '')
    bajo = m.lower()
    if 'sin firma' in bajo:
        return 'No se ofrece: la versión publicada no trae la firma de Cinema Productions y, por seguridad, no se instala nada sin ella.'
    if 'timed out' in bajo or 'timeout' in bajo:
        return 'No pude comprobarlo: el servidor tardó demasiado en responder. Prueba otra vez en unos minutos.'
    if 'certificate' in bajo or 'ssl' in bajo:
        return 'No pude comprobarlo: no se pudo verificar la conexión segura. Revisa la fecha y la hora del equipo, o un antivirus o VPN que intercepte HTTPS.'
    import re
    codigo = re.search(r'HTTP(?: Error)? (\d{3})', m)
    if codigo:
        return f'No pude comprobarlo: el servidor de actualizaciones respondió con el error {codigo.group(1)}. Prueba otra vez más tarde.'
    if 'getaddrinfo' in bajo or 'name or service' in bajo or 'unreachable' in bajo or 'urlopen error' in bajo or 'connection' in bajo:
        return 'No pude comprobarlo: no hay conexión a internet (o un cortafuegos bloquea a CineCaptions).'
    return 'No pude comprobarlo: ' + (m[:90] or 'el servidor no respondió.')


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


def bytes_firmados(datos):
    """Lo que se firma: el manifiesto sin «firma», en JSON canónico (claves ordenadas, sin espacios, solo ASCII)."""
    resto = {k: v for k, v in datos.items() if k != 'firma'}
    return json.dumps(resto, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


_FIRMAS_VISTAS = {}                   # el aviso automático relee el mismo manifiesto cada 10 s: se verifica una vez


def firma_valida(datos):
    try:
        f = datos.get('firma') or {}
        publica = CLAVES_FIRMA.get(str(f.get('clave') or ''))
        if not publica or f.get('alg') != 'ed25519':
            return False
        mensaje = bytes_firmados(datos)
        memo = hashlib.sha256(mensaje + str(f.get('valor')).encode('utf-8')).hexdigest()
        if memo not in _FIRMAS_VISTAS:
            _FIRMAS_VISTAS[memo] = firma_ed25519.verificar(bytes.fromhex(publica), mensaje, base64.b64decode(str(f.get('valor') or ''), validate=True))
        return _FIRMAS_VISTAS[memo]
    except Exception:
        return False


def _interpretar(datos, version_local, canal_beta=False):
    if not firma_valida(datos):
        return {'estado': 'error', 'mensaje': 'manifiesto sin firma válida de Cinema Productions'}
    candidatos = [datos.get('estable') or {}]
    if canal_beta:
        candidatos.append(datos.get('beta') or {})
    mejor = max((c for c in candidatos if c.get('version')), key=lambda c: _partes(c['version']), default=None)
    if mejor and es_mas_nueva(mejor['version'], version_local):
        archivo = (mejor.get('archivos') or {}).get(clave_plataforma())
        archivo = archivo if isinstance(archivo, dict) and archivo.get('url') else None
        r = {'estado': 'nueva', 'version': corta(mejor['version']), 'url': (archivo or {}).get('url') or mejor.get('url') or '',
             'notas': mejor.get('notas') or '', 'fecha': mejor.get('fecha') or '', 'archivo': archivo}
        r.update(_obligatoria(datos, version_local, archivo))
        return r
    return {'estado': 'al_dia', 'version': version_local}


def _obligatoria(datos, version_local, archivo):
    """v5.72 (pedido del usuario: «force_update» + versión mínima): `"force_update": true` y `"version_minima": "5.71"` en la RAÍZ del
    version.json (dentro de lo firmado: nadie los cambia sin la clave). Obligatoria solo si la instalada es MENOR que la mínima y hay
    instalador de ESTA plataforma (sin él, el programa no podría actualizarse y quedaría bloqueado para nada)."""
    minima = str(datos.get('version_minima') or '').strip()
    if datos.get('force_update') is True and minima and archivo and es_mas_nueva(minima, version_local):
        return {'obligatoria': True, 'minima': corta(minima)}
    return {}


def carpeta_descargas():
    if sys.platform == 'darwin' and hasattr(os, 'geteuid') and os.geteuid() == 0:
        # v5.87: el servicio de root de la Mac (actualizar_fondo) descarga en una carpeta SOLO suya: en /tmp, otro usuario podría crearla
        # antes y cambiar el .dmg entre la comprobación del SHA-256 y la instalación (que es de root)
        c = Path('/Library/Application Support/CineCaptions/actualizar/descarga')
        c.mkdir(parents=True, exist_ok=True)
        os.chown(c, 0, 0)
        os.chmod(c, 0o700)
        return c
    c = Path(tempfile.gettempdir()) / 'cinecaptions_actualizacion'
    c.mkdir(parents=True, exist_ok=True)
    return c


def limpiar_descargas_viejas(edad_s=3600):
    """v5.87: lo que dejó la última actualización (el .exe, o el .dmg y el .pkg de la Mac: hasta 1,2 GB) se quedaba en la carpeta temporal
    hasta la SIGUIENTE actualización. Al abrir el programa se quita lo que tenga más de `edad_s` (ya instalado; lo reciente puede ser de una
    actualización en marcha: no se toca). Devuelve los bytes quitados. No lanza."""
    quitados = 0
    try:
        c = Path(tempfile.gettempdir()) / 'cinecaptions_actualizacion'
        if not c.is_dir():
            return 0
        ahora = time.time()
        for p in c.iterdir():
            try:
                st = p.stat()
                if ahora - st.st_mtime < edad_s:
                    continue
                if p.is_dir():
                    import shutil
                    tam = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
                    shutil.rmtree(p)
                else:
                    tam = st.st_size
                    p.unlink()
                quitados += tam
            except OSError:
                pass
    except Exception:
        pass
    return quitados


def sha256_de(ruta, bloque=1 << 20):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        while True:
            b = f.read(bloque)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


_LOCK_DESCARGA = threading.Lock()


def descargar(archivo, version_local='', progreso=None, cancelado=None, timeout=30):
    """Baja el instalador a una carpeta temporal y devuelve su ruta. `archivo` = {'url', 'sha256', 'tam'}; progreso(bytes, total) en cada trozo;
    cancelado() -> True corta. Lanza RuntimeError si la descarga se corta o si la huella NO coincide (el archivo se borra: nunca se ejecuta).

    v5.4.41: UNA descarga a la vez (dos a la vez escribían en el mismo «.parte», salía un archivo mezclado y la huella no cuadraba: «No se pudo actualizar» al primer intento y bien al segundo)
    y, si aun así la huella no cuadra o la descarga queda a medias (red), se repite UNA vez antes de rendirse."""
    with _LOCK_DESCARGA:
        for intento in (1, 2):
            try:
                return _descargar_una_vez(archivo, version_local, progreso, cancelado, timeout)
            except RuntimeError as e:
                texto = str(e)
                if intento == 2 or not ('huella' in texto or 'a medias' in texto):
                    raise


def _descargar_una_vez(archivo, version_local='', progreso=None, cancelado=None, timeout=30):
    url = archivo['url']
    nombre = os.path.basename(url.split('?')[0]) or 'CineCaptions_actualizacion.bin'
    destino = carpeta_descargas() / nombre
    parcial = destino.with_name(destino.name + '.%d.%d.parte' % (os.getpid(), int(time.time() * 1000)))          # (propio de ESTE intento: nunca se comparte)
    esperado = str(archivo.get('sha256') or '').lower()
    total = int(archivo.get('tam') or 0)
    # v5.90: la misma versión ya bajada y comprobada se reutiliza (el servicio de la Mac la volvía a bajar en cada pasada: 711 MB cada hora
    # tras un «Más tarde», y macOS dejaba un informe por escribir más de 1 GB en minutos). Se vuelve a comprobar su SHA-256 firmado.
    try:
        if esperado and destino.is_file() and (not total or destino.stat().st_size == total) and sha256_de(destino) == esperado:
            if progreso:
                progreso(destino.stat().st_size, destino.stat().st_size)
            return destino
    except OSError:
        pass
    for p in carpeta_descargas().glob('*'):                 # lo descargado de otras veces se limpia (un instalador igual que no cuadra, también)
        try:
            p.unlink()
        except OSError:
            pass
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


def instalar(ruta, aviso_mac='', silencioso=False):
    """Lanza lo descargado y devuelve True si arrancó. Windows: el instalador (se instala solo, cierra y reemplaza esta versión y vuelve a abrir
    CineCaptions). Mac (v5.87): igual, con _instalar_mac. `aviso_mac`: el texto de la ventana de la contraseña de macOS.
    v5.87 `silencioso` (al CERRAR el programa con la versión nueva ya descargada): sin ventanas y sin volver a abrirlo; Windows con
    /silencioso /noabrir /sinmodelo (los motores los pone al día el programa al abrirse), Mac solo por el servicio del sistema (sin contraseña:
    sin él, False, nada de pedir la contraseña a quien solo cerraba)."""
    ruta = str(ruta)
    try:
        if sys.platform.startswith('win'):
            # DETACHED_PROCESS: sobrevive al cierre del programa. cwd = la carpeta del propio instalador: si heredara la del programa (los accesos
            # directos la fijan a la carpeta de instalación) Windows no dejaría renombrarla ni reemplazar la versión instalada.
            args = ['/silencioso', '/noabrir', '/sinmodelo'] if silencioso else ['/empezar']
            subprocess.Popen([ruta] + args, close_fds=True, creationflags=0x00000008, cwd=os.path.dirname(ruta) or tempfile.gettempdir())
        elif sys.platform == 'darwin':
            if silencioso:
                import actualizar_fondo
                return actualizar_fondo.pedir_al_servicio(reabrir=False, dmg=ruta)
            return _instalar_mac(ruta, aviso_mac)
        else:
            return False
        return True
    except OSError:
        return False


# v5.87 (el usuario: «en Mac al actualizar no se actualiza bien, no se abre solo, tengo que cerrarlo y volverlo a abrir»): hasta la 5.86 la Mac
# solo abría el .dmg y pedía abrir el .pkg a mano CON EL PROGRAMA ABIERTO: el .pkg reemplazaba la app mientras corría la vieja, nada la cerraba
# ni la volvía a abrir. Ahora, como en Windows: se saca el .pkg del .dmg, este script espera a que CineCaptions se cierre, lo instala (con la
# contraseña de la Mac: la ventana de macOS) y vuelve a abrir CineCaptions. Sin contraseña (cancelada), el instalador de macOS de siempre; al
# terminar, se abre igual. Lo que pasa queda en ~/DaVinciSubtitles/actualizacion_mac.log.
APP_MAC = '/Applications/CineCaptions.app'            # (donde instala el .pkg)
SCRIPT_MAC = r'''#!/bin/bash
# CineCaptions · actualización en la Mac (actualizaciones._instalar_mac): espera a que el programa se cierre, instala el .pkg y lo vuelve a abrir.
# $1 PID del programa · $2 el .pkg · $3 la app que abrir al terminar · $4 el registro · $5 el texto de la ventana de la contraseña
PID="$1"; PKG="$2"; APP="$3"; LOG="$4"; AVISO="$5"
{
echo "== $(date '+%Y-%m-%d %H:%M:%S')  actualización: $PKG"
for i in $(seq 1 120); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
if kill -0 "$PID" 2>/dev/null; then
    echo "el programa no se cerró en 60 s: lo cierro"
    kill -TERM "$PID" 2>/dev/null; sleep 5; kill -9 "$PID" 2>/dev/null; sleep 1
fi
if /usr/bin/sudo -n /usr/sbin/installer -pkg "$PKG" -target / 2>/dev/null; then
    echo "instalado"
elif /usr/bin/osascript -e 'on run argv' \
        -e 'do shell script "/usr/sbin/installer -pkg " & quoted form of (item 1 of argv) & " -target /" with prompt (item 2 of argv) with administrator privileges' \
        -e 'end run' "$PKG" "$AVISO"; then
    echo "instalado (con la contraseña)"
else
    echo "sin contraseña o no se pudo: abro el instalador de macOS"
    /usr/bin/open -W "$PKG"
fi
sleep 1
/usr/bin/open "$APP" && echo "abierto: $APP"
} >> "$LOG" 2>&1
'''


def _pkg_de_dmg(dmg):
    """El .pkg que trae el .dmg descargado, copiado junto a él (se monta sin ventanas ni Finder y se desmonta al acabar)."""
    import plistlib
    import shutil
    r = subprocess.run(['hdiutil', 'attach', '-nobrowse', '-readonly', '-noautoopen', '-plist', str(dmg)], capture_output=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError('hdiutil attach: ' + (r.stderr or b'').decode('utf-8', 'replace').strip()[-300:])
    montajes = [e['mount-point'] for e in plistlib.loads(r.stdout).get('system-entities', []) if e.get('mount-point')]
    try:
        pkgs = sorted(p for m in montajes for p in Path(m).glob('*.pkg'))
        if not pkgs:
            raise RuntimeError('el .dmg no trae ningún .pkg')
        destino = Path(dmg).resolve().with_suffix('.pkg')         # (absoluta: el script corre en otra carpeta; relativa, installer no la encontraba)
        if destino.is_dir():
            shutil.rmtree(destino, ignore_errors=True)
        if pkgs[0].is_dir():
            shutil.copytree(pkgs[0], destino, dirs_exist_ok=True)
        else:
            shutil.copy(pkgs[0], destino)                          # (sin copy2: con la fecha de AHORA, limpiar_descargas_viejas no lo toca enseguida)
        return destino
    finally:
        for m in montajes:
            if subprocess.run(['hdiutil', 'detach', m, '-quiet'], capture_output=True, timeout=120).returncode != 0:
                subprocess.run(['hdiutil', 'detach', m, '-force', '-quiet'], capture_output=True, timeout=120)


def _instalar_mac(dmg, aviso='', reabrir=True):
    """v5.87: prepara el .pkg y deja en marcha SCRIPT_MAC (aparte: sobrevive al cierre del programa). True si quedó en marcha; quien llama
    cierra el programa (el script espera a que se cierre). Corre en un hilo (hdiutil tarda segundos).
    Con el servicio del sistema (actualizar_fondo, lo pone el .pkg desde la 5.87) se le deja el pedido y él instala SIN contraseña (pedido
    del usuario: «sin contraseña»); el script con la ventana de la contraseña queda para una Mac que aún no lo tiene."""
    try:
        import actualizar_fondo
        if actualizar_fondo.pedir_al_servicio(reabrir=reabrir, dmg=dmg):
            return True
    except Exception:
        pass
    try:
        pkg = _pkg_de_dmg(dmg)
    except Exception:
        return False
    app = APP_MAC
    if not Path(app).is_dir() and getattr(sys, 'frozen', False):
        propia = Path(sys.executable).resolve().parents[2]
        if propia.suffix == '.app':
            app = str(propia)
    script = carpeta_descargas() / 'actualizar_mac.sh'
    script.write_text(SCRIPT_MAC, encoding='utf-8')
    os.chmod(script, 0o755)
    registro = Path.home() / 'DaVinciSubtitles' / 'actualizacion_mac.log'
    registro.parent.mkdir(parents=True, exist_ok=True)
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'PYTHON', '_PYI', 'QT_'))}
    subprocess.Popen(['/bin/bash', str(script), str(os.getpid()), str(Path(pkg).resolve()), app, str(registro),
                      aviso or 'CineCaptions se actualiza: escribe la contraseña de tu Mac para instalar la versión nueva.'],
                     close_fds=True, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=entorno, cwd=str(carpeta_descargas()))
    return True
