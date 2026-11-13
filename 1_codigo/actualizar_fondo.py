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
REINTENTO_S = 6 * 3600
ESPERA_CIERRE_S = 90                       # lo que se espera a que se cierre el programa que hizo el pedido
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
        archivos_seguros.escribir_json(carpeta_estado() / 'estado.json', datos)
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
    return sys.platform == 'darwin' and PLIST_MAC.is_file() and PEDIDOS_MAC.is_dir() and os.access(PEDIDOS_MAC, os.W_OK)


def pedir_al_servicio(reabrir=True, dmg=None):
    """Deja el pedido al servicio de la Mac (lo despierta al momento: QueueDirectories). True si quedó. El servicio espera a que este
    programa se cierre, instala sin contraseña y, con `reabrir`, lo vuelve a abrir."""
    if not servicio_mac_instalado():
        return False
    try:
        datos = {'reabrir': bool(reabrir), 'pid': os.getpid(), 'dmg': str(dmg) if dmg else '', 'ts': time.time()}
        tmp = PEDIDOS_MAC / f'.pedido_{os.getpid()}.tmp'
        tmp.write_text(json.dumps(datos), encoding='utf-8')
        tmp.rename(PEDIDOS_MAC / f'pedido_{os.getpid()}.json')
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


def _tomar_pedidos():
    """Lee y BORRA los pedidos (QueueDirectories relanza el servicio mientras la carpeta no esté vacía). Solo archivos normales, en
    carpetas de root; un enlace se quita sin seguirlo."""
    import stat as st
    pedidos = []
    if sys.platform != 'darwin' or not PEDIDOS_MAC.is_dir():
        return pedidos
    if es_root() and not (_carpeta_de_root(PEDIDOS_MAC.parent) and _carpeta_de_root(PEDIDOS_MAC)):
        _log('pedidos: la carpeta no es de root; no la toco')
        return pedidos
    for p in sorted(PEDIDOS_MAC.iterdir()):
        try:
            s = os.lstat(p)
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
    """De root: saca el .pkg del .dmg y lo instala (installer, sin contraseña). True si quedó instalado."""
    import actualizaciones
    pkg = actualizaciones._pkg_de_dmg(dmg)
    r = subprocess.run(['/usr/sbin/installer', '-pkg', str(pkg), '-target', '/'], capture_output=True, text=True, timeout=3600)
    _log('installer: ' + ' '.join((r.stdout or r.stderr or '').split())[-300:])
    try:
        Path(pkg).unlink()
    except OSError:
        pass
    return r.returncode == 0


def _abrir_como_usuario():
    u = usuario_de_la_mac()
    if not u:
        return
    subprocess.run(['/bin/launchctl', 'asuser', str(u[1]), '/usr/bin/sudo', '-u', u[0], '/usr/bin/open', APP_MAC], capture_output=True, timeout=60)


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
        for d in pedidos:
            _esperar_cierre(d.get('pid'))
        if programa_abierto():
            info(f'{version}: CineCaptions está abierto; se instala al cerrarlo')
            return 'abierto'
        tr = _textos()
        reabrir = any(d.get('reabrir') for d in pedidos)
        if not pedidos:
            notificar(tr('Hay una versión nueva de CineCaptions ({v}): se está instalando sola.', v=version))
        try:
            ruta = _dmg_del_pedido(pedidos, r['archivo']) if sys.platform == 'darwin' else None
            if ruta is None:
                ruta = actualizaciones.descargar(r['archivo'], version_instalada())
            _log(f'{version}: descargada y comprobada ({ruta})')
            if sys.platform.startswith('win'):
                _instalar_windows(ruta)
                _guardar_estado({'instalando': version, 'ts': time.time()})
                info(f'{version}: instalador en marcha')
                return 'instalando'
            if not _instalar_mac(ruta):
                raise RuntimeError('installer no terminó bien')
            _guardar_estado({'instalada': version, 'ts': time.time()})
            _log(f'{version}: instalada')
            notificar(tr('CineCaptions se actualizó a la {v}.', v=version))
            if reabrir:
                _abrir_como_usuario()
            return 'instalada'
        except Exception as e:
            _guardar_estado({'fallo_ts': time.time(), 'motivo': f'{type(e).__name__}: {e}'[:300], 'version': version})
            _log(f'{version}: fallo {type(e).__name__}: {e}')
            if reabrir:
                _abrir_como_usuario()
            return 'fallo'


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


def asegurar_programada(exe=None):
    """Windows, programa instalado: crea (o corrige) la tarea programada si falta o apunta a otro .exe. Corre en un hilo (schtasks tarda).
    Devuelve 'creada' | 'al_dia' | 'no_aplica' | 'fallo: …'."""
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
    if not sys.platform.startswith('win'):
        return False
    r = subprocess.run(['schtasks', '/Delete', '/TN', NOMBRE_TAREA, '/F'], capture_output=True, timeout=30, creationflags=SIN_VENTANA)
    return r.returncode == 0
