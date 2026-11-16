# CineCaptions · By Cinema Productions
# 1_codigo/actualizar_fondo.py — actualizaciones con el programa CERRADO: avisa, descarga, comprueba e instala sola (Windows y Mac).
"""
v5.87 (pedido: «que de verdad notifiquen si sale una versión nueva aunque esté cerrado, que auto lo descargue y se instalen tanto en Mac
como en Windows»; en Mac, «sin contraseña»).

Quién lo corre (las dos con `CineCaptions --tarea actualizar_fondo`):
  Windows  la tarea programada del USUARIO «CineCaptions Actualizaciones» (cada CADA_H horas y, si el equipo estaba apagado, en cuanto se
           pueda). La crea el programa al abrirse (asegurar_programada, en un hilo) y la quita el desinstalador. CineCaptions se instala
           solo para el usuario (%LOCALAPPDATA%\\Programs), sin permisos de administrador: su instalador corre en silencio
           (/silencioso /noabrir /sinmodelo: los motores los pone al día el programa al abrirse, sin bajar GB a escondidas).
  Mac      el servicio del sistema ETIQUETA_MAC (/Library/LaunchDaemons, lo pone el .pkg), de root: al encender, cada CADA_H horas y al
           momento cuando el programa deja un pedido en PEDIDOS_MAC (QueueDirectories). Instala el .pkg sin pedir contraseña.

Qué hace: consulta el version.json FIRMADO (actualizaciones.comprobar: firma ed25519); si hay una versión más nueva y CineCaptions NO está
abierto (el candado ~/.cinecaptions.lock libre), avisa con una notificación del sistema, la descarga (SHA-256 del manifiesto firmado) y la
instala. Con el programa abierto no toca nada: el propio programa la descarga y la instala al cerrarlo. Un fallo no se reintenta solo
antes de REINTENTO_S (un pedido del programa, sí). Lo que pasa queda en carpeta_estado()/actualizar_fondo.log.

Seguridad del servicio de root (Mac): solo instala lo que dice el manifiesto firmado; de un pedido solo usa «reabrir», el PID que esperar
(nunca lo mata) y, como mucho, un .dmg ya descargado que COPIA a su carpeta y comprueba con el SHA-256 firmado antes de usarlo.

v5.90 (el usuario: «en Mac sigue sin recibir actualizaciones… que cuando salga una actualización de verdad notifique en la Mac, que tenga
más permiso y control»). MEDIDO en Macs de GitHub (macOS 15 y 26) con la 5.88 publicada: el servicio sí la instalaba (21-52 s), pero la
notificación de `osascript` NO salía en pantalla (va a nombre del «Editor de Scripts», sin permiso): nadie se enteraba de nada. Ahora, con
alguien frente a la Mac, el aviso es una tarjeta del propio CineCaptions (aviso_mac, abierta en su sesión): ya descargada la versión nueva
pregunta «Más tarde» / «Actualizar ahora» (sin respuesta en ESPERA_RESPUESTA_S se instala sola), enseña la instalación y el final.
«Más tarde» la aplaza POSPONER_S. El servicio mira cada CADA_H_MAC horas.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

NOMBRE_TAREA = 'CineCaptions Actualizaciones'                         # (en la raíz del Programador: crear carpetas pide administrador)
ETIQUETA_MAC = 'com.cinemaproductions.cinecaptions.actualizar'
PLIST_MAC = Path('/Library/LaunchDaemons') / (ETIQUETA_MAC + '.plist')
PEDIDOS_MAC = Path('/Users/Shared/CineCaptions/pedidos')
APP_MAC = '/Applications/CineCaptions.app'
CADA_H = 4
CADA_H_MAC = 1                             # v5.90 (StartInterval del plist que escribe el postinstall: vale tras reiniciar si ya estaba cargado)
REINTENTO_S = 6 * 3600
ESPERA_CIERRE_S = 90                       # lo que se espera a que se cierre el programa que hizo el pedido
ESPERA_RESPUESTA_S = 120                   # v5.90: lo que la tarjeta espera a que elijas antes de instalarse sola
MARGEN_RESPUESTA_S = 30                    # v5.90: lo que el servicio espera de más (la tarjeta tarda en abrirse)
POSPONER_S = 4 * 3600                      # v5.90: «Más tarde»
SIN_VENTANA = 0x08000000 if sys.platform.startswith('win') else 0


# ---------------------------------------------------------------------------------------------------------------------------------------
# dónde y quién
# ---------------------------------------------------------------------------------------------------------------------------------------
def version_instalada():
    from version import APP_VERSION
    return APP_VERSION


def es_root():
    return hasattr(os, 'geteuid') and os.geteuid() == 0


def carpeta_estado():
    if sys.platform == 'darwin' and es_root():
        return Path('/Library/Application Support/CineCaptions/actualizar')
    if sys.platform.startswith('win'):
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(base) / 'CineCaptions' / 'actualizar'
    return Path.home() / 'Library' / 'Application Support' / 'CineCaptions' / 'actualizar'


# v5.91 (el usuario: «omite que pida contraseña para poderse instalar»; eligió «arrastrar a Aplicaciones»): la app se arrastra a Aplicaciones
# (sin .pkg: no pide contraseña) y las versiones nuevas las instala un servicio DEL USUARIO (LaunchAgent, sin root): reemplaza la app que el
# usuario arrastró, que es suya. Las Mac que ya tenían la 5.87-5.90 conservan su servicio de root (la app de root en /Applications).
def plist_usuario():
    return Path.home() / 'Library' / 'LaunchAgents' / (ETIQUETA_MAC + '.plist')


def pedidos_usuario():
    return Path.home() / 'Library' / 'Application Support' / 'CineCaptions' / 'pedidos'


def app_instalada():
    """La CineCaptions.app de este programa (donde la arrastró el usuario); sin compilar, /Applications/CineCaptions.app."""
    if getattr(sys, 'frozen', False):
        try:
            p = Path(sys.executable).resolve().parents[2]
            if p.suffix == '.app':
                return p
        except (OSError, IndexError):
            pass
    return Path(APP_MAC)


def app_de_paso(app=None):
    """¿La app corre desde el disco montado o «trasladada» por macOS (abierta sin arrastrarla)? Ahí no se puede actualizar."""
    s = str(app or app_instalada()).replace('\\', '/')
    return s.startswith('/Volumes/') or '/AppTranslocation/' in s


def servicio_root_mac():
    return sys.platform == 'darwin' and PLIST_MAC.is_file() and PEDIDOS_MAC.is_dir() and os.access(PEDIDOS_MAC, os.W_OK)


def servicio_mac():
    """'root' (5.87-5.90: /Library/LaunchDaemons) | 'usuario' (5.91: ~/Library/LaunchAgents) | None."""
    if sys.platform != 'darwin':
        return None
    if servicio_root_mac():
        return 'root'
    if plist_usuario().is_file():
        return 'usuario'
    return None


def carpeta_pedidos():
    """Donde se dejan (y leen) los pedidos: la compartida del servicio de root o la del usuario."""
    if es_root() or servicio_root_mac():
        return PEDIDOS_MAC
    return pedidos_usuario()


def usuario_de_la_mac():
    """(nombre, uid, casa) de quien está frente a la Mac, o None (pantalla de inicio de sesión, nadie)."""
    try:
        import pwd
        nombre = subprocess.run(['stat', '-f%Su', '/dev/console'], capture_output=True, text=True, timeout=10).stdout.strip()
        if not nombre or nombre in ('root', 'loginwindow', '_mbsetupuser'):
            return None
        p = pwd.getpwnam(nombre)
        return nombre, p.pw_uid, Path(p.pw_dir)
    except Exception:
        return None


def _casa():
    if sys.platform == 'darwin' and es_root():
        u = usuario_de_la_mac()
        return u[2] if u else None
    return Path.home()


def _log(texto):
    try:
        c = carpeta_estado()
        c.mkdir(parents=True, exist_ok=True)
        with open(c / 'actualizar_fondo.log', 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S  ') + str(texto) + '\n')
    except Exception:
        pass


def _leer_estado():
    try:
        import archivos_seguros
        return archivos_seguros.leer_json(carpeta_estado() / 'estado.json', {}) or {}
    except Exception:
        return {}


def _guardar_estado(datos):
    try:
        import archivos_seguros
        ruta = archivos_seguros.escribir_json(carpeta_estado() / 'estado.json', datos)
        if sys.platform == 'darwin' and es_root():
            os.chmod(ruta, 0o644)                       # v5.90: la tarjeta (del usuario) lo lee para saber cuándo terminó la instalación
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------------------------------------------------
# ¿está abierto el programa? (el mismo candado que _asegurar_instancia_unica: lo suelta el sistema si el programa muere)
# ---------------------------------------------------------------------------------------------------------------------------------------
def programa_abierto(casa=None):
    casa = casa if casa is not None else _casa()
    if casa is None:
        return False
    ruta = Path(casa) / '.cinecaptions.lock'
    if not ruta.exists():
        return False
    try:
        f = open(ruta, 'r+', encoding='utf-8')
    except OSError:
        return False
    try:
        if os.name == 'nt':                       # (por lo que HAY, no por sys.platform)
            import msvcrt
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            return False
        import fcntl
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return False
    finally:
        f.close()


# ---------------------------------------------------------------------------------------------------------------------------------------
# notificaciones del sistema
# ---------------------------------------------------------------------------------------------------------------------------------------
def _textos():
    """Los textos en el idioma del usuario (el servicio de la Mac es root: su idioma es el de quien está frente a la Mac)."""
    try:
        import i18n
        casa = _casa()
        if casa is not None and sys.platform == 'darwin' and es_root():
            codigo = i18n.leer_ini(Path(casa) / 'DaVinciSubtitles' / 'idioma.ini')
            if codigo:
                i18n.cambiar_idioma_en_caliente(codigo)
        return i18n.tr
    except Exception:
        return lambda t, **k: t.format(**k)


def notificar(texto, titulo='CineCaptions'):
    """Una notificación del sistema. Windows: la del icono de la bandeja (Qt) unos segundos; Mac: la de macOS (osascript), como el usuario
    que está frente a la Mac si esto corre de root. No lanza."""
    try:
        if sys.platform == 'darwin':
            orden = ['/usr/bin/osascript', '-e', 'on run argv', '-e', 'display notification (item 1 of argv) with title (item 2 of argv)',
                     '-e', 'end run', texto, titulo]
            if es_root():
                u = usuario_de_la_mac()
                if not u:
                    return
                orden = ['/bin/launchctl', 'asuser', str(u[1]), '/usr/bin/sudo', '-u', u[0]] + orden
            subprocess.run(orden, capture_output=True, timeout=30)
        elif sys.platform.startswith('win'):
            _notificar_windows(texto, titulo)
    except Exception as e:
        _log(f'notificación: {type(e).__name__}: {e}')


def _notificar_windows(texto, titulo, segundos=8):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('CineCaptions.App')
    except Exception:
        pass
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    app = QApplication.instance() or QApplication([sys.argv[0]])
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return
    icono = QIcon()
    try:
        from sfx_rules import base_recursos
        icono = QIcon(str(Path(base_recursos()) / 'logo_cinecaptions.png'))
    except Exception:
        pass
    bandeja = QSystemTrayIcon(icono)
    bandeja.setToolTip(titulo)
    bandeja.show()
    bandeja.showMessage(titulo, texto, icono, segundos * 1000)
    bucle = QEventLoop()
    QTimer.singleShot(segundos * 1000, bucle.quit)
    bucle.exec()
    bandeja.hide()
    del app


# ---------------------------------------------------------------------------------------------------------------------------------------
# pedidos del programa (Mac): «instálala ya» desde «Actualizar» o al cerrar, sin contraseña
# ---------------------------------------------------------------------------------------------------------------------------------------
def servicio_mac_instalado():
    return servicio_mac() is not None


def pedir_al_servicio(reabrir=True, dmg=None):
    """Deja el pedido al servicio de la Mac (lo despierta al momento: QueueDirectories). True si quedó. El servicio espera a que este
    programa se cierre, instala sin contraseña y, con `reabrir`, lo vuelve a abrir. v5.91: el de root (5.87-5.90) o el del usuario."""
    tipo = servicio_mac()
    if not tipo:
        return False
    carpeta = PEDIDOS_MAC if tipo == 'root' else pedidos_usuario()
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        datos = {'reabrir': bool(reabrir), 'pid': os.getpid(), 'dmg': str(dmg) if dmg else '', 'ts': time.time()}
        tmp = carpeta / f'.pedido_{os.getpid()}.tmp'
        tmp.write_text(json.dumps(datos), encoding='utf-8')
        tmp.rename(carpeta / f'pedido_{os.getpid()}.json')
    except OSError:
        return False
    if tipo == 'usuario':
        _despertar_servicio_usuario()
    return True


def _despertar_servicio_usuario():
    """El servicio del usuario se despierta solo con el pedido (QueueDirectories) si está cargado; si no (recién creado, sesión rara), se
    carga, y como último recurso se corre aparte la pasada de este mismo programa."""
    uid = os.getuid()
    objetivo = f'gui/{uid}/{ETIQUETA_MAC}'
    try:
        if subprocess.run(['/bin/launchctl', 'print', objetivo], capture_output=True, timeout=20).returncode == 0:
            return
        if subprocess.run(['/bin/launchctl', 'bootstrap', f'gui/{uid}', str(plist_usuario())], capture_output=True, timeout=30).returncode == 0:
            return
    except (OSError, subprocess.SubprocessError):
        pass
    correr_aparte()


def pedir_y_correr_aparte(reabrir=True, dmg=None):
    """v5.91, Mac SIN servicio (no se pudo crear el del usuario): el pedido en la carpeta del usuario y la pasada en un proceso aparte, que
    espera a que este programa se cierre, reemplaza la app y (con `reabrir`) la vuelve a abrir. True si quedó en marcha."""
    if sys.platform != 'darwin' or es_root() or servicio_root_mac() or app_de_paso():
        return False
    try:
        carpeta = pedidos_usuario()
        carpeta.mkdir(parents=True, exist_ok=True)
        datos = {'reabrir': bool(reabrir), 'pid': os.getpid(), 'dmg': str(dmg) if dmg else '', 'ts': time.time()}
        tmp = carpeta / f'.pedido_{os.getpid()}.tmp'
        tmp.write_text(json.dumps(datos), encoding='utf-8')
        tmp.rename(carpeta / f'pedido_{os.getpid()}.json')
    except OSError:
        return False
    return correr_aparte()


def correr_aparte():
    """La pasada de actualizar_fondo en un proceso aparte (sobrevive al cierre del programa): lo usa la Mac sin servicio."""
    if not getattr(sys, 'frozen', False):
        return False
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'PYTHON', '_PYI', 'QT_'))}
    entorno['QT_QPA_PLATFORM'] = 'offscreen'
    try:
        subprocess.Popen([sys.executable, '--tarea', 'actualizar_fondo'], close_fds=True, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=entorno, cwd=str(Path.home()))
        return True
    except OSError:
        return False


def _carpeta_de_root(ruta):
    """¿Es una carpeta DE VERDAD (no un enlace) y de root? (si un usuario pudiera cambiarla por un enlace, el servicio de root borraría
    archivos de otra parte al vaciar los pedidos)"""
    import stat as st
    try:
        s = os.lstat(ruta)
        return st.S_ISDIR(s.st_mode) and s.st_uid == 0
    except OSError:
        return False


def _tomar_pedidos(carpeta=None):
    """Lee y BORRA los pedidos (QueueDirectories relanza el servicio mientras la carpeta no esté vacía). Solo archivos normales, en
    carpetas de root (el servicio de root); un enlace se quita sin seguirlo."""
    import stat as st
    pedidos = []
    carpeta = Path(carpeta) if carpeta is not None else carpeta_pedidos()
    if sys.platform != 'darwin' or not carpeta.is_dir():
        return pedidos
    if es_root() and not (_carpeta_de_root(carpeta.parent) and _carpeta_de_root(carpeta)):
        _log('pedidos: la carpeta no es de root; no la toco')
        return pedidos
    for p in sorted(carpeta.iterdir()):
        try:
            s = os.lstat(p)
            if p.name.startswith('.') and st.S_ISREG(s.st_mode) and time.time() - s.st_mtime < 30:
                continue                                    # v5.90: a medio escribir (se renombra al momento): no se borra debajo de quien escribe
            if st.S_ISREG(s.st_mode) and p.suffix == '.json' and s.st_size <= 4096:
                d = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(d, dict):
                    pedidos.append(d)
        except Exception:
            pass
        try:
            if not p.is_dir() or p.is_symlink():
                p.unlink()
        except OSError:
            pass
    return pedidos


def _esperar_cierre(pid, tope_s=ESPERA_CIERRE_S):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return
    if pid <= 1:
        return
    limite = time.time() + tope_s
    while time.time() < limite:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.5)


def _dmg_del_pedido(pedidos, archivo):
    """Un .dmg ya descargado por el programa, COPIADO a la carpeta del servicio y comprobado con el SHA-256 firmado; si no vale, None."""
    import actualizaciones
    esperado = str((archivo or {}).get('sha256') or '').lower()
    tam = int((archivo or {}).get('tam') or 0)
    for d in pedidos:
        origen = Path(str(d.get('dmg') or ''))
        try:
            if not esperado or not origen.name.endswith('.dmg') or not origen.is_file() or (tam and origen.stat().st_size != tam):
                continue
        except OSError:
            continue
        destino = actualizaciones.carpeta_descargas() / origen.name             # (de root y solo suya)
        try:
            if origen.resolve() != destino.resolve():                         # (el servicio del usuario: es la misma carpeta)
                shutil.copyfile(origen, destino)
            if actualizaciones.sha256_de(destino) == esperado:
                return destino
            destino.unlink()
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------------------------------------------------------------------
# instalar
# ---------------------------------------------------------------------------------------------------------------------------------------
def _instalar_windows(ruta):
    """El instalador por usuario, en silencio, APARTE (sobrevive a este proceso: el instalador cierra los CineCaptions de su carpeta)."""
    subprocess.Popen([str(ruta), '/silencioso', '/noabrir', '/sinmodelo'], close_fds=True, creationflags=0x00000008 | SIN_VENTANA,
                     cwd=os.path.dirname(str(ruta)) or None)
    return True


def _instalar_mac(dmg):
    """Instala la versión del .dmg descargado y comprobado. True si quedó instalada.
    v5.91: si el disco trae CineCaptions.app (arrastrar a Aplicaciones) se REEMPLAZA la app instalada: el servicio de root la de
    /Applications (de root), el del usuario la que él arrastró (es suya: sin contraseña). Un disco de antes (solo .pkg) lo instala el de
    root con `installer`; el del usuario no puede sin contraseña."""
    import actualizaciones
    montajes = actualizaciones.montar_dmg(dmg)
    try:
        nueva = actualizaciones.app_en_montajes(montajes)
        if nueva is not None:
            _reemplazar_app(nueva)
            _log(f'app reemplazada: {nueva.name} → {_destino_app()}')
            return True
    finally:
        actualizaciones.desmontar(montajes)
    if not es_root():
        raise RuntimeError('esta versión trae un .pkg y el servicio del usuario no puede instalarlo sin contraseña')
    pkg = actualizaciones._pkg_de_dmg(dmg)
    r = subprocess.run(['/usr/sbin/installer', '-pkg', str(pkg), '-target', '/'], capture_output=True, text=True, timeout=3600)
    _log('installer: ' + ' '.join((r.stdout or r.stderr or '').split())[-300:])
    try:
        Path(pkg).unlink()
    except OSError:
        pass
    return r.returncode == 0


def _destino_app():
    return Path(APP_MAC) if es_root() else app_instalada()


def _reemplazar_app(origen, borrar_viejo=True):
    """Copia la app nueva junto a la instalada («….app.nuevo», con ditto: conserva firmas y permisos) y las cambia de nombre: cambiar de nombre
    es al momento, así nunca queda una app a medias; la vieja se borra después. De root: root:wheel y sin escribible por otros (el servicio
    de root la ejecuta). Lanza si algo falla (la instalada se queda como estaba)."""
    destino = _destino_app()
    if app_de_paso(destino):
        raise RuntimeError(f'CineCaptions corre desde {destino}: arrástralo a Aplicaciones para poder actualizarlo')
    nuevo = destino.with_name(destino.name + '.nuevo')
    viejo = destino.with_name(destino.name + '.viejo')
    for p in (nuevo, viejo):
        shutil.rmtree(p, ignore_errors=True)
    try:
        r = subprocess.run(['/usr/bin/ditto', str(origen), str(nuevo)], capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise RuntimeError('ditto: ' + (r.stderr or '').strip()[-200:])
        if es_root():
            subprocess.run(['/usr/sbin/chown', '-R', 'root:wheel', str(nuevo)], capture_output=True, timeout=300)
            subprocess.run(['/bin/chmod', '-R', 'go-w', str(nuevo)], capture_output=True, timeout=300)
        subprocess.run(['/usr/bin/xattr', '-dr', 'com.apple.quarantine', str(nuevo)], capture_output=True, timeout=300)
        subprocess.run(['/usr/bin/xattr', '-d', 'com.apple.FinderInfo', str(nuevo)], capture_output=True, timeout=60)   # (rompe la firma estricta)
        if not (nuevo / 'Contents' / 'MacOS' / 'CineCaptions').is_file():
            raise RuntimeError('la copia de la app quedó incompleta')
        if destino.exists():
            os.rename(destino, viejo)
        os.rename(nuevo, destino)
    except BaseException:
        shutil.rmtree(nuevo, ignore_errors=True)
        if viejo.exists() and not destino.exists():
            os.rename(viejo, destino)
        raise
    if not borrar_viejo:
        return viejo                                                # (el programa abierto sigue corriendo desde ahí: se borra al cerrarse)
    shutil.rmtree(viejo, ignore_errors=True)
    return None


def entorno_para_abrir():
    """v5.91 (medido en Macs de GitHub): `open` le pasa a la app que abre el entorno de quien la abre; el servicio corre con
    QT_QPA_PLATFORM=offscreen (sin pantalla) y la tarjeta (o CineCaptions al volver a abrirse) salía sin ventana. Sin eso ni lo de PyInstaller."""
    return {k: v for k, v in os.environ.items() if not k.startswith(('QT_', 'DYLD_', '_PYI', 'PYTHON'))}


def _abrir_como_usuario():
    if not es_root():
        subprocess.run(['/usr/bin/open', str(app_instalada())], capture_output=True, timeout=60, env=entorno_para_abrir())
        return
    u = usuario_de_la_mac()
    if not u:
        return
    subprocess.run(['/bin/launchctl', 'asuser', str(u[1]), '/usr/bin/sudo', '-u', u[0], '/usr/bin/open', APP_MAC], capture_output=True, timeout=60)


def _hay_quien_mire():
    """¿Hay alguien frente a la Mac que pueda ver la tarjeta? (de root: quien sea; del usuario: él mismo)"""
    u = usuario_de_la_mac()
    if not u:
        return False
    if es_root():
        return True
    try:
        import getpass
        return u[0] == getpass.getuser()
    except Exception:
        return False


# ---------------------------------------------------------------------------------------------------------------------------------------
# v5.90 · Mac: la tarjeta de CineCaptions (aviso_mac) en la sesión de quien está frente a la Mac, en vez de la notificación invisible
# ---------------------------------------------------------------------------------------------------------------------------------------
def archivo_aviso():
    return carpeta_estado() / 'aviso.json'


def tarjeta_mac(modo, r, vieja='', **extra):
    """Abre la tarjeta (`open -n … --args --tarea aviso_mac /dev/null <aviso.json>`, como el usuario). Devuelve su id o None (nadie frente a
    la Mac, no es la Mac o no se pudo abrir). Una tarjeta anterior se cierra sola al ver otro id en aviso.json."""
    if sys.platform != 'darwin' or not _hay_quien_mire():
        return None
    app = Path(APP_MAC) if es_root() else app_instalada()
    if not app.is_dir():
        return None
    u = usuario_de_la_mac()
    ident = f'{int(time.time() * 1000)}-{os.getpid()}'
    datos = {'id': ident, 'modo': modo, 'version': str(r.get('version') or ''), 'vieja': str(vieja or ''), 'notas': str(r.get('notas') or ''),
             'url': str(r.get('url') or ''), 'espera_s': ESPERA_RESPUESTA_S, 'estado': str(carpeta_estado() / 'estado.json'),
             'pedidos': str(carpeta_pedidos())}
    datos.update(extra)
    try:
        import archivos_seguros
        ruta = archivos_seguros.escribir_json(archivo_aviso(), datos)
        os.chmod(ruta, 0o644)                                       # (la lee el usuario)
        orden = ['/usr/bin/open', '-n', '-a', str(app), '--args', '--tarea', 'aviso_mac', '/dev/null', str(ruta)]
        if es_root():
            orden = ['/bin/launchctl', 'asuser', str(u[1]), '/usr/bin/sudo', '-u', u[0], '-H'] + orden
        res = subprocess.run(orden, capture_output=True, text=True, timeout=60, env=entorno_para_abrir())
        if res.returncode != 0:
            _log(f'tarjeta {modo}: open falló ({(res.stderr or res.stdout).strip()[:200]})')
            return None
        _log(f'tarjeta {modo} ({datos["version"]}) para {u[0]}')
        return ident
    except Exception as e:
        _log(f'tarjeta {modo}: {type(e).__name__}: {e}')
        return None


def cerrar_tarjeta_mac():
    """Cualquier tarjeta abierta se cierra sola al ver que cambió el id de aviso.json."""
    try:
        import archivos_seguros
        ruta = archivos_seguros.escribir_json(archivo_aviso(), {'id': f'cerrada-{int(time.time() * 1000)}', 'modo': 'cerrada'})
        os.chmod(ruta, 0o644)
    except Exception:
        pass


def _esperar_respuesta(ident, tope_s=None):
    """'instalar' | 'luego' | 'abierto' (alguien abrió CineCaptions mientras: decide el programa). Sin respuesta en el plazo: 'instalar'
    (la tarjeta también se instala sola al acabar su cuenta atrás)."""
    limite = time.time() + (tope_s if tope_s is not None else ESPERA_RESPUESTA_S + MARGEN_RESPUESTA_S)
    while time.time() < limite:
        if programa_abierto():
            return 'abierto'
        for d in _tomar_pedidos():
            if d.get('accion') in ('instalar', 'luego') and str(d.get('id')) == str(ident):
                return d['accion']
            if not d.get('accion'):                                 # un pedido del programa («Actualizar» o al cerrarlo): instalar ya
                return 'instalar'
        time.sleep(1)
    return 'instalar'


# ---------------------------------------------------------------------------------------------------------------------------------------
# la tarea
# ---------------------------------------------------------------------------------------------------------------------------------------
class _Candado:
    """Una sola actualización de fondo a la vez (la tarea de cada 4 h y un pedido pueden coincidir)."""

    def __enter__(self):
        self.f = None
        try:
            c = carpeta_estado()
            c.mkdir(parents=True, exist_ok=True)
            self.f = open(c / 'actualizar.lock', 'a+')
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def __exit__(self, *_a):
        try:
            if self.f:
                self.f.close()
        except Exception:
            pass
        return False


def correr(info=None):
    """Una pasada. Devuelve qué pasó: 'ocupado' | 'espera' | 'al_dia' | 'sin_red' | 'abierto' | 'instalando' (Windows: el instalador ya
    corre aparte) | 'instalada' (Mac) | 'fallo'."""
    info = info or (lambda t: None)
    with _Candado() as tomado:
        if not tomado:
            return 'ocupado'
        import actualizaciones
        pedidos = _tomar_pedidos()
        # v5.90: las respuestas de la tarjeta que llegan tarde (el servicio ya no esperaba): «Actualizar ahora» cuenta como pedido; «Más tarde»
        # no pide nada (y nunca se espera a su PID: es el de la tarjeta)
        pedidos = [{k: v for k, v in d.items() if k != 'pid'} if d.get('accion') else d for d in pedidos if d.get('accion') in (None, 'instalar')]
        estado = _leer_estado()
        if not pedidos and time.time() - float(estado.get('fallo_ts') or 0) < REINTENTO_S:
            return 'espera'
        r = actualizaciones.comprobar(version_instalada(), canal_beta=False)
        if r.get('estado') != 'nueva' or not r.get('archivo'):
            if r.get('estado') == 'al_dia' and estado.get('fallo_ts'):
                _guardar_estado({k: v for k, v in estado.items() if k not in ('fallo_ts', 'motivo')})
            info(f"sin versión nueva ({r.get('estado')})")
            return 'al_dia' if r.get('estado') == 'al_dia' else 'sin_red'
        version = r['version']
        pospuesta = estado.get('pospuesta') if isinstance(estado.get('pospuesta'), dict) else {}
        if not pedidos and pospuesta.get('version') == version and time.time() < float(pospuesta.get('hasta') or 0):
            info(f'{version}: aplazada con «Más tarde»')
            return 'pospuesta'
        for d in pedidos:
            _esperar_cierre(d.get('pid'))
        if programa_abierto():
            info(f'{version}: CineCaptions está abierto; se instala al cerrarlo')
            return 'abierto'
        tr = _textos()
        reabrir = any(d.get('reabrir') for d in pedidos)
        vieja = version_instalada()
        con_tarjeta = sys.platform == 'darwin' and _hay_quien_mire()
        if not pedidos and not con_tarjeta:
            notificar(tr('Hay una versión nueva de CineCaptions ({v}): se está instalando sola.', v=version))
        tarjeta = None
        if con_tarjeta and pedidos:
            tarjeta = tarjeta_mac('instalando', r, vieja)                  # «Actualizar ahora» o al cerrar el programa: que se vea, desde ya
        try:
            ruta = _dmg_del_pedido(pedidos, r['archivo']) if sys.platform == 'darwin' else None
            if ruta is None:
                ruta = actualizaciones.descargar(r['archivo'], vieja)
            _log(f'{version}: descargada y comprobada ({ruta})')
            if sys.platform.startswith('win'):
                _instalar_windows(ruta)
                _guardar_estado({'instalando': version, 'ts': time.time()})
                info(f'{version}: instalador en marcha')
                return 'instalando'
            if con_tarjeta and not pedidos:
                # v5.90: ya descargada, se PREGUNTA (antes se instalaba a escondidas con una notificación que no se veía)
                tarjeta = tarjeta_mac('preguntar', r, vieja)
                if tarjeta:
                    respuesta = _esperar_respuesta(tarjeta)
                    _log(f'{version}: respuesta de la tarjeta: {respuesta}')
                    if respuesta == 'abierto':
                        cerrar_tarjeta_mac()
                        info(f'{version}: CineCaptions se abrió mientras preguntaba; se instala al cerrarlo')
                        return 'abierto'
                    if respuesta == 'luego':
                        cerrar_tarjeta_mac()                                # (si la respuesta no vino de ella, que no siga contando)
                        _guardar_estado({'pospuesta': {'version': version, 'hasta': time.time() + POSPONER_S}})
                        info(f'{version}: «Más tarde» (se vuelve a ofrecer en {POSPONER_S // 3600} h)')
                        return 'pospuesta'
                else:
                    notificar(tr('Hay una versión nueva de CineCaptions ({v}): se está instalando sola.', v=version))
            _guardar_estado({'instalando': version, 'ts': time.time()})
            if not _instalar_mac(ruta):
                raise RuntimeError('installer no terminó bien')
            _guardar_estado({'instalada': version, 'ts': time.time()})
            _log(f'{version}: instalada')
            if reabrir:
                _abrir_como_usuario()                                       # (al abrirse enseña sus novedades: eso es el aviso)
            elif not (con_tarjeta and tarjeta_mac('hecha', r, vieja)):
                notificar(tr('CineCaptions se actualizó a la {v}.', v=version))
            return 'instalada'
        except Exception as e:
            motivo = f'{type(e).__name__}: {e}'[:300]
            _guardar_estado({'fallo_ts': time.time(), 'motivo': motivo, 'version': version})
            _log(f'{version}: fallo {motivo}')
            if reabrir:
                _abrir_como_usuario()
            if con_tarjeta:
                time.sleep(1.5)                                             # (la tarjeta de «instalando» ve el fallo y se cierra)
                tarjeta_mac('fallo', r, vieja, motivo=tr(_motivo_claro(motivo)))
            return 'fallo'


def _motivo_claro(motivo):
    """El fallo en palabras del usuario (el técnico queda en el registro)."""
    bajo = str(motivo).lower()
    if 'huella' in bajo or 'sha' in bajo:
        return 'La descarga llegó dañada.'
    if any(t in bajo for t in ('a medias', 'timed out', 'urlopen', 'connection', 'conexi', 'network', 'nodename', 'resolve host')):
        return 'Se cortó la descarga (revisa internet).'
    if 'no space' in bajo or 'espacio' in bajo:
        return 'No hay espacio libre suficiente en el disco.'
    if 'installer' in bajo or 'hdiutil' in bajo or '.pkg' in bajo:
        return 'El instalador de macOS no pudo terminar.'
    return 'Algo falló al instalarla.'


# ---------------------------------------------------------------------------------------------------------------------------------------
# Windows: la tarea programada (la pone el programa al abrirse; el desinstalador la quita)
# ---------------------------------------------------------------------------------------------------------------------------------------
def xml_tarea(exe, usuario):
    """El XML de la tarea: cada CADA_H horas, en cuanto se pueda si el equipo estaba apagado, solo con red, sin límite de batería, con el
    usuario conectado (las notificaciones se ven) y sin permisos de administrador."""
    from xml.sax.saxutils import escape
    carpeta = os.path.dirname(exe)
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Cinema Productions</Author>
    <Description>Busca las versiones nuevas de CineCaptions y las instala con el programa cerrado.</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition><Interval>PT{CADA_H}H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>2026-01-01T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(usuario)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>"{escape(exe)}"</Command>
      <Arguments>--tarea actualizar_fondo</Arguments>
      <WorkingDirectory>{escape(carpeta)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'''


def plist_agente(binario, plist, pedidos, registro):
    """v5.91: el servicio DEL USUARIO de la Mac (LaunchAgent): al iniciar sesión, cada CADA_H_MAC horas y al momento con un pedido. Si la app
    ya no está (se tiró a la Papelera), se quita solo: borra su plist y se descarga."""
    from xml.sax.saxutils import escape
    guion = ('if [ -x "$0" ]; then exec "$0" --tarea actualizar_fondo; fi; '
             f'rm -f "$1"; /bin/launchctl bootout gui/$(id -u)/{ETIQUETA_MAC}')
    args = ''.join(f'<string>{escape(str(a))}</string>' for a in ('/bin/sh', '-c', guion, binario, plist))
    partes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
              '<plist version="1.0">', '<dict>',
              f'    <key>Label</key><string>{ETIQUETA_MAC}</string>',
              f'    <key>ProgramArguments</key><array>{args}</array>',
              '    <key>RunAtLoad</key><true/>',
              f'    <key>StartInterval</key><integer>{CADA_H_MAC * 3600}</integer>',
              f'    <key>QueueDirectories</key><array><string>{escape(str(pedidos))}</string></array>',
              '    <key>EnvironmentVariables</key><dict><key>QT_QPA_PLATFORM</key><string>offscreen</string></dict>',
              f'    <key>StandardOutPath</key><string>{escape(str(registro))}</string>',
              f'    <key>StandardErrorPath</key><string>{escape(str(registro))}</string>',
              '    <key>ProcessType</key><string>Background</string>',
              '    <key>Nice</key><integer>5</integer>', '    <key>LowPriorityIO</key><true/>',
              '</dict>', '</plist>', '']
    return '\n'.join(partes)



def _asegurar_agente_mac(exe=None):
    if servicio_root_mac():
        return 'al_dia'                                             # (5.87-5.90: su servicio de root sigue instalando)
    app = app_instalada()
    if app_de_paso(app):
        return 'no_aplica'                                          # (abierta desde el disco o sin arrastrar: no se puede actualizar ahí)
    binario = str(exe or (app / 'Contents' / 'MacOS' / 'CineCaptions'))
    plist = plist_usuario()
    registro = Path.home() / 'Library' / 'Logs' / 'CineCaptions_actualizar.log'
    texto = plist_agente(binario, plist, pedidos_usuario(), registro)
    objetivo = f'gui/{os.getuid()}/{ETIQUETA_MAC}'
    try:
        pedidos_usuario().mkdir(parents=True, exist_ok=True)
        registro.parent.mkdir(parents=True, exist_ok=True)
        cargado = subprocess.run(['/bin/launchctl', 'print', objetivo], capture_output=True, timeout=20).returncode == 0
        if plist.is_file() and plist.read_text(encoding='utf-8') == texto and cargado:
            return 'al_dia'
        import archivos_seguros
        archivos_seguros.escribir_texto(plist, texto)
        if cargado:
            subprocess.run(['/bin/launchctl', 'bootout', objetivo], capture_output=True, timeout=30)
        r = subprocess.run(['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', str(plist)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return f'fallo: {type(e).__name__}: {e}'
    if r.returncode == 0:
        return 'creada'
    return 'fallo: ' + ' '.join((r.stderr or r.stdout or '').split())[:200]


def asegurar_programada(exe=None):
    """Windows, programa instalado: crea (o corrige) la tarea programada si falta o apunta a otro .exe. Corre en un hilo (schtasks tarda).
    v5.91 Mac: el servicio del usuario (LaunchAgent) si la Mac no tiene el de root de antes.
    Devuelve 'creada' | 'al_dia' | 'no_aplica' | 'fallo: …'."""
    if sys.platform == 'darwin' and (exe or getattr(sys, 'frozen', False)):
        return _asegurar_agente_mac(exe)
    if not sys.platform.startswith('win') or not (exe or getattr(sys, 'frozen', False)):
        return 'no_aplica'
    exe = str(exe or sys.executable)
    r = subprocess.run(['schtasks', '/Query', '/TN', NOMBRE_TAREA, '/XML'], capture_output=True, text=True, errors='replace',
                       timeout=30, creationflags=SIN_VENTANA)
    if r.returncode == 0 and exe.lower() in (r.stdout or '').lower() and 'actualizar_fondo' in (r.stdout or ''):
        return 'al_dia'
    usuario = '\\'.join(p for p in (os.environ.get('USERDOMAIN'), os.environ.get('USERNAME')) if p)
    xml = carpeta_estado() / 'tarea.xml'
    try:
        xml.parent.mkdir(parents=True, exist_ok=True)
        xml.write_text(xml_tarea(exe, usuario), encoding='utf-16')
        r = subprocess.run(['schtasks', '/Create', '/TN', NOMBRE_TAREA, '/XML', str(xml), '/F'], capture_output=True, text=True,
                           errors='replace', timeout=30, creationflags=SIN_VENTANA)
    finally:
        try:
            xml.unlink()
        except OSError:
            pass
    if r.returncode == 0:
        return 'creada'
    return 'fallo: ' + ' '.join((r.stderr or r.stdout or '').split())[:200]


def quitar_programada():
    if sys.platform == 'darwin':
        subprocess.run(['/bin/launchctl', 'bootout', f'gui/{os.getuid()}/{ETIQUETA_MAC}'], capture_output=True, timeout=30)
        try:
            plist_usuario().unlink()
            return True
        except OSError:
            return False
    if not sys.platform.startswith('win'):
        return False
    r = subprocess.run(['schtasks', '/Delete', '/TN', NOMBRE_TAREA, '/F'], capture_output=True, timeout=30, creationflags=SIN_VENTANA)
    return r.returncode == 0
