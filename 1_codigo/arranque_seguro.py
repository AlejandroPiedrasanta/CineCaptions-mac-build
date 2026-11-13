# CineCaptions · By Cinema Productions
# 1_codigo/arranque_seguro.py — que nada deje el programa sin abrir: hijos de librerías que no reabren la app y copias atascadas que se quitan.
"""
v5.85 (Mac «no abre», reproducido instalando la 5.84 en Macs de GitHub con macOS 15, 26 e Intel). Dos defensas:

1. `atender_hijo()` (lo PRIMERO del script principal, solo congelado): las librerías lanzan procesos hijos con ESTE ejecutable como si
   fuera Python («-B -S -I -c código» o «-m módulo»; p. ej. el resource_tracker de multiprocessing, que crea tqdm al bajar el modelo de
   voz). PyInstaller no sabe hacer de intérprete: el hijo arrancaba CineCaptions ENTERO. El de la tarea «modelo» del postinstall
   (offscreen) se quedaba invisible en la ventana de licencia con el candado de una sola ventana, y abrir el programa no hacía nada
   hasta reiniciar la Mac. Aquí el hijo corre su código como lo haría Python y sale, sin cargar nada del programa.

2. `copia_atascada(pid)` + `terminar(pid)` (los usa `_asegurar_instancia_unica`): si la copia que tiene el candado es un hijo de esos o
   lleva `TOPE_ABRIENDO_S` sin terminar de abrir (marca de sesión «abriendo…», que no sea la ventana de licencia), se cierra y abre
   esta en su lugar. Ante la duda, nunca: una copia que funciona solo se trae al frente.

Sin dependencias (ni psutil): `ps` en Mac/Linux y la API de Windows por ctypes.
"""
import os
import re
import sys
import time

TOPE_ABRIENDO_S = 300            # una copia que lleva tanto «abriendo» (sin ventana de licencia) está atascada (el vigía de 45 s ya lo anotó)

# banderas que pone multiprocessing (util._args_from_interpreter_flags) y otras librerías delante de «-c» / «-m»
_BANDERAS = {'-B', '-S', '-I', '-E', '-s', '-u', '-O', '-OO', '-q', '-b', '-bb', '-d', '-v', '-R', '-P'}
_CON_VALOR = {'-X', '-W'}
# lo mismo en una línea de órdenes de `ps` (Mac/Linux): el ejecutable seguido de banderas de intérprete y «-c» o «-m»
_HIJO_EN_LINEA = re.compile(r'CineCaptions(?:\.exe)?(?:\s+(?:-[BSIEsuOqbdvRP]{1,2}|-[XW]\s+\S+))*\s+-[cm]\s', re.I)


def como_interprete(argv):
    """('-c', código, resto) o ('-m', módulo, resto) si `argv` es una llamada de intérprete (banderas y luego -c/-m); None si es un
    arranque normal del programa (sin argumentos, un video, --tarea, --reinicio…)."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ('-c', '-m'):
            return (a, argv[i + 1], list(argv[i + 2:])) if i + 1 < len(argv) else None
        if a in _CON_VALOR:
            i += 2
            continue
        if a in _BANDERAS:
            i += 1
            continue
        return None
    return None


def atender_hijo(argv=None):
    """Si este proceso es un hijo lanzado por una librería, corre lo que pide y TERMINA el proceso (no vuelve); si no, no hace nada.
    Primero `multiprocessing.freeze_support()` (los hijos «--multiprocessing-fork» de Windows y, con PyInstaller, el resource_tracker)."""
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except Exception:
        pass
    llamada = como_interprete(sys.argv if argv is None else argv)
    if llamada is None:
        return
    modo, valor, resto = llamada
    try:
        if modo == '-c':
            import builtins
            sys.argv = ['-c'] + resto
            exec(compile(valor, '<string>', 'exec'), {'__name__': '__main__', '__builtins__': builtins})
        else:
            import runpy
            sys.argv = [valor] + resto
            runpy.run_module(valor, run_name='__main__', alter_sys=True)
    except SystemExit:
        raise
    except BaseException:
        import traceback
        try:
            traceback.print_exc()
        except Exception:
            pass
        sys.exit(1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# la copia que tiene el candado de una sola ventana
# ---------------------------------------------------------------------------
def _edad_ps(texto):
    """«[[dd-]hh:]mm:ss» de `ps -o etime=` → segundos."""
    dias, _, resto = texto.strip().rpartition('-')
    partes = [int(p) for p in resto.split(':')]
    while len(partes) < 3:
        partes.insert(0, 0)
    h, m, s = partes[-3:]
    return (int(dias) if dias else 0) * 86400 + h * 3600 + m * 60 + s


def info_proceso(pid):
    """{'exe', 'cmd', 'edad'} del proceso `pid` (cmd solo en Mac/Linux; edad en segundos), o None si no existe o no se puede leer."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if sys.platform.startswith('win'):
        return _info_windows(pid)
    try:
        import subprocess
        r = subprocess.run(['ps', '-o', 'etime=', '-o', 'args=', '-p', str(pid)], capture_output=True, text=True, timeout=3,
                           errors='replace')
        linea = (r.stdout or '').strip()
        if r.returncode != 0 or not linea:
            return None
        edad, _, cmd = linea.partition(' ')
        cmd = cmd.strip()
        return {'exe': cmd, 'cmd': cmd, 'edad': _edad_ps(edad)}
    except Exception:
        return None


def _info_windows(pid):
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)                      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = wintypes.DWORD(len(buf))
            exe = buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
            creado, salida, kernel, usuario = (wintypes.FILETIME() for _ in range(4))
            edad = None
            if k32.GetProcessTimes(h, ctypes.byref(creado), ctypes.byref(salida), ctypes.byref(kernel), ctypes.byref(usuario)):
                t100 = (creado.dwHighDateTime << 32) | creado.dwLowDateTime
                edad = max(0.0, time.time() - (t100 / 1e7 - 11644473600))
            return {'exe': exe, 'cmd': '', 'edad': edad}
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def es_cinecaptions(info, ejecutable=None):
    """¿El proceso es este mismo programa? Congelado: el mismo nombre de ejecutable; desde el código: «CineCaptions» en su línea."""
    if not info:
        return False
    exe = str(info.get('exe') or '')
    cmd = str(info.get('cmd') or '')
    ejecutable = ejecutable or (sys.executable if getattr(sys, 'frozen', False) else '')
    if ejecutable:
        nombre = os.path.basename(ejecutable).lower()
        return bool(nombre) and (os.path.basename(exe).lower() == nombre or nombre in cmd.lower())
    return 'cinecaptions' in (cmd or exe).lower()


def leer_marca(ruta=None):
    """(hora, estado) de la marca de sesión (registro.SESION: «hora|estado»), o None."""
    try:
        if ruta is None:
            import registro
            ruta = registro.SESION
        texto = open(ruta, encoding='utf-8').read()
        hora, _, estado = texto.partition('|')
        return float(hora), estado.strip()
    except Exception:
        return None


def copia_atascada(pid, info=None, marca=None, ahora=None, ejecutable=None):
    """El motivo (texto) si la copia `pid` que tiene el candado está atascada y se puede cerrar; None si no o ante la duda.
    `info`, `marca`, `ahora` y `ejecutable` son para las pruebas (por defecto: el proceso real, la marca de sesión y la hora)."""
    if not pid or int(pid) == os.getpid():
        return None
    info = info_proceso(pid) if info is None else info
    if not es_cinecaptions(info, ejecutable):
        return None
    if _HIJO_EN_LINEA.search(str(info.get('cmd') or '')):
        return 'un proceso auxiliar de una librería que se quedó abierto sin ventana'
    ahora = time.time() if ahora is None else ahora
    marca = leer_marca() if marca is None else marca
    if not marca:
        return None
    hora, estado = marca
    espera = ahora - hora
    edad = info.get('edad')
    # la marca es de ESA copia (empezó antes de escribirla) y dice que nunca terminó de abrir, fuera de la ventana de licencia
    if (estado.startswith('abriendo') and 'licencia' not in estado and espera >= TOPE_ABRIENDO_S
            and edad is not None and edad + 5 >= espera):
        return f'llevaba {int(espera // 60)} min sin terminar de abrir'
    return None


def terminar(pid, espera_s=3.0):
    """Cierra a la fuerza el proceso `pid`. True si ya no existe."""
    try:
        pid = int(pid)
        if sys.platform.startswith('win'):
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL('kernel32', use_last_error=True)
            k32.OpenProcess.restype = wintypes.HANDLE
            h = k32.OpenProcess(0x0001 | 0x00100000, False, pid)       # PROCESS_TERMINATE | SYNCHRONIZE
            if not h:
                return info_proceso(pid) is None
            try:
                k32.TerminateProcess(h, 1)
                # (terminado = la espera vuelve con WAIT_OBJECT_0; el proceso puede seguir «existiendo» mientras otro tenga un handle abierto)
                return k32.WaitForSingleObject(h, int(espera_s * 1000)) == 0
            finally:
                k32.CloseHandle(h)
        else:
            import signal
            os.kill(pid, signal.SIGKILL)
            limite = time.time() + espera_s
            while time.time() < limite:
                try:
                    os.waitpid(pid, os.WNOHANG)                       # (si fuera hijo nuestro, que no quede zombi)
                except (ChildProcessError, OSError):
                    pass
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return True
                except PermissionError:
                    return False
                time.sleep(0.1)
        return info_proceso(pid) is None
    except Exception:
        return False
