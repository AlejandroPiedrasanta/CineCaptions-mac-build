# CineCaptions · By Cinema Productions
# 1_codigo/registro.py — el registro de avisos y errores: archivo de log, historial y señal para la interfaz.
"""
registro.py
-----------
Todo lo que el programa quiere decir sobre sí mismo (una nota, un aviso, un error) pasa por aquí:

  * Se escribe en ~/DaVinciSubtitles/cinecaptions.log (con rotación a 1 MB: cinecaptions.log.1).
  * Se guarda en memoria el historial reciente (ventana «Registro»).
  * Se emite una señal para que la interfaz lo muestre en la barra de título de la pantalla (registro_ui.py).

Los errores que antes quedaban SOLO en error_ventana.txt, las excepciones de los hilos, las de la interfaz y los avisos de
Qt (warnings) llegan aquí solos con instalar_ganchos(); no hace falta tocar el resto del código para que se vean.

Se puede usar desde cualquier hilo: la escritura va con candado y la señal viaja sola al hilo de la interfaz.
"""
import collections
import datetime
import os
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal

CARPETA = Path.home() / 'DaVinciSubtitles'
ARCHIVO = CARPETA / 'cinecaptions.log'
MAXIMO_BYTES = 1_000_000
ARCHIVO_ERRORES = CARPETA / 'errores.log'
MAXIMO_ERRORES = 2_000_000
NIVELES = ('info', 'ok', 'aviso', 'error')
# los avisos de Qt que no sirven de nada al usuario (se quedan solo en el archivo, no se muestran)
RUIDO_QT = ('QFont::', 'QWindowsContext', 'QPainter::', 'propagateSizeHints', 'QSslSocket', 'qt.qpa', 'QSocketNotifier',
            'setGeometry', 'This plugin does not support', 'QPixmap::', 'QBasicTimer', 'QObject::startTimer', 'QWidget::')


class Entrada:
    __slots__ = ('tiempo', 'nivel', 'mensaje', 'origen', 'detalle', 'veces', 'leida')

    def __init__(self, nivel, mensaje, origen='', detalle=''):
        self.tiempo = time.time()
        self.nivel = nivel if nivel in NIVELES else 'info'
        self.mensaje = str(mensaje).strip()
        self.origen = str(origen or '')
        self.detalle = str(detalle or '')
        self.veces = 1
        self.leida = False

    def hora(self):
        return datetime.datetime.fromtimestamp(self.tiempo).strftime('%H:%M:%S')

    def linea(self):
        o = f' · {self.origen}' if self.origen else ''
        v = f' (x{self.veces})' if self.veces > 1 else ''
        return f'{self.hora()}  [{self.nivel.upper():5}]{o}: {self.mensaje}{v}'


class _Registro(QObject):
    nueva = Signal(object)          # una Entrada (nueva o repetida)
    cambio = Signal()               # se leyó / se limpió: los contadores cambian

    def __init__(self):
        super().__init__()
        self._lista = collections.deque(maxlen=400)
        self._candado = threading.Lock()
        self._ultimo_disco = None
        self._emitiendo = False

    # -- escritura
    def anotar(self, nivel, mensaje, origen='', detalle=''):
        mensaje = str(mensaje or '').strip()
        if not mensaje:
            return None
        with self._candado:
            previa = self._lista[-1] if self._lista else None
            if previa is not None and previa.mensaje == mensaje and previa.nivel == nivel and time.time() - previa.tiempo < 4.0:
                previa.veces += 1
                previa.tiempo = time.time()
                e = previa
            else:
                e = Entrada(nivel, mensaje, origen, detalle)
                self._lista.append(e)
            self._a_disco(e)
        self._emitiendo = True
        try:
            self.nueva.emit(e)
        except RuntimeError:
            pass
        finally:
            self._emitiendo = False
        return e

    def _a_disco(self, e):
        try:
            CARPETA.mkdir(parents=True, exist_ok=True)
            if ARCHIVO.is_file() and ARCHIVO.stat().st_size > MAXIMO_BYTES:
                viejo = ARCHIVO.with_name(ARCHIVO.name + '.1')
                try:
                    if viejo.exists():
                        viejo.unlink()
                    ARCHIVO.replace(viejo)
                except OSError:
                    pass
            fecha = datetime.datetime.fromtimestamp(e.tiempo).strftime('%Y-%m-%d')
            texto = f'{fecha} {e.linea()}\n'
            if e.detalle:
                texto += ''.join(f'    {l}\n' for l in e.detalle.rstrip().splitlines())
            with open(ARCHIVO, 'a', encoding='utf-8') as f:
                f.write(texto)
            if e.nivel in ('aviso', 'error'):
                self._a_disco_errores(fecha, texto)
        except Exception:
            pass

    def _a_disco_errores(self, fecha, texto):
        """errores.log: SOLO avisos y errores, con 3 copias de 2 MB. El log general rota a 1 MB y en una sesión larga empuja fuera los errores
        de hace horas; este archivo es el que se manda para reportar algo que falló."""
        try:
            if ARCHIVO_ERRORES.is_file() and ARCHIVO_ERRORES.stat().st_size > MAXIMO_ERRORES:
                for k in (3, 2, 1):
                    origen = ARCHIVO_ERRORES.with_name(f'{ARCHIVO_ERRORES.name}.{k}')
                    if origen.exists():
                        if k == 3:
                            origen.unlink()
                        else:
                            origen.replace(ARCHIVO_ERRORES.with_name(f'{ARCHIVO_ERRORES.name}.{k + 1}'))
                ARCHIVO_ERRORES.replace(ARCHIVO_ERRORES.with_name(ARCHIVO_ERRORES.name + '.1'))
            with open(ARCHIVO_ERRORES, 'a', encoding='utf-8') as f:
                f.write(texto if texto.startswith(fecha) else f'{fecha} {texto}')
        except Exception:
            pass

    # -- lectura
    def lista(self, nivel_minimo=None):
        with self._candado:
            datos = list(self._lista)
        if nivel_minimo:
            datos = [e for e in datos if NIVELES.index(e.nivel) >= NIVELES.index(nivel_minimo) or (nivel_minimo == 'aviso' and e.nivel == 'error')]
        return datos

    def sin_leer(self):
        """(avisos, errores) que el usuario aún no ha visto en la ventana Registro."""
        with self._candado:
            datos = [e for e in self._lista if not e.leida]
        return (sum(1 for e in datos if e.nivel == 'aviso'), sum(1 for e in datos if e.nivel == 'error'))

    def marcar_leidas(self):
        with self._candado:
            for e in self._lista:
                e.leida = True
        self.cambio.emit()

    def limpiar(self):
        with self._candado:
            self._lista.clear()
        self.cambio.emit()


_REGISTRO = None


def registro():
    global _REGISTRO
    if _REGISTRO is None:
        _REGISTRO = _Registro()
    return _REGISTRO


def anotar(nivel, mensaje, origen='', detalle=''):
    return registro().anotar(nivel, mensaje, origen, detalle)


def info(mensaje, origen=''):
    return anotar('info', mensaje, origen)


def ok(mensaje, origen=''):
    return anotar('ok', mensaje, origen)


def aviso(mensaje, origen='', detalle=''):
    return anotar('aviso', mensaje, origen, detalle)


def error(mensaje, origen='', detalle=''):
    return anotar('error', mensaje, origen, detalle)


def resumen_de_traza(texto):
    """(mensaje corto, origen) de un traceback: «KeyError: 'x'» y «archivo.py:123 en funcion»."""
    lineas = [l for l in str(texto).strip().splitlines() if l.strip()]
    if not lineas:
        return str(texto)[:160], ''
    ultima = lineas[-1].strip()
    origen = ''
    for l in reversed(lineas):
        l = l.strip()
        if l.startswith('File "'):
            try:
                ruta = l.split('"')[1]
                num = l.split('line ')[1].split(',')[0]
                fn = l.split(' in ')[-1]
                origen = f'{Path(ruta).name}:{num} en {fn}'
            except Exception:
                pass
            break
    return ultima[:200], origen


def excepcion(texto=None, origen=''):
    """Anota la excepción en curso (o el traceback que se le pase) como error."""
    texto = texto if texto is not None else traceback.format_exc()
    mensaje, donde = resumen_de_traza(texto)
    return error(mensaje, origen or donde, detalle=texto)


def ruta_archivo():
    return ARCHIVO


# ---- ganchos: lo que ya falla en cualquier parte llega solo al registro
def _gancho_excepcion(tipo, valor, tb):
    try:
        if registro()._emitiendo:        # un aviso fallando al repartirse a sus oyentes: no se anota otra vez (era un bucle sin fin)
            raise RuntimeError('reentrada')
        excepcion(''.join(traceback.format_exception(tipo, valor, tb)), 'excepción sin atrapar')
    except Exception:
        pass
    try:
        if sys.__stderr__ is not None:
            sys.__stderr__.write(''.join(traceback.format_exception(tipo, valor, tb)))
    except Exception:
        pass


def _gancho_hilo(args):
    if args.exc_type is SystemExit:
        return
    _gancho_excepcion(args.exc_type, args.exc_value, args.exc_traceback)


def _gancho_qt(modo, contexto, mensaje):
    try:
        from PySide6.QtCore import QtMsgType
        if modo in (QtMsgType.QtDebugMsg, QtMsgType.QtInfoMsg):
            return
        texto = str(mensaje or '')
        if any(texto.startswith(r) or r in texto[:60] for r in RUIDO_QT):
            return
        nivel = 'aviso' if modo == QtMsgType.QtWarningMsg else 'error'
        origen = 'Qt'
        try:
            if contexto and contexto.file:
                origen = f'Qt · {Path(contexto.file).name}:{contexto.line}'
        except Exception:
            pass
        anotar(nivel, texto, origen)
    except Exception:
        pass


def instalar_ganchos():
    """Excepciones sin atrapar, excepciones de hilos y avisos de Qt → al registro (y al archivo)."""
    try:
        sys.excepthook = _gancho_excepcion
        threading.excepthook = _gancho_hilo
    except Exception:
        pass
    try:
        from PySide6.QtCore import qInstallMessageHandler
        qInstallMessageHandler(_gancho_qt)
    except Exception:
        pass
    info('CineCaptions iniciado', 'registro')
    for paso in (_cabecera_de_sesion, _revisar_cierre_anterior, _fallos_nativos, _gancho_unraisable, _entorno_en_hilo):
        try:
            paso()
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------------------------------
# v5.4: mas pistas para cuando algo falla
SESION = CARPETA / 'sesion_abierta.flag'
FALLOS_NATIVOS = CARPETA / 'fallo_nativo.log'


def _cabecera_de_sesion():
    """Una linea con el entorno: version, sistema, Python, Qt, GPU y disco libre (lo primero que se pide al reportar un bug)."""
    import platform
    import shutil
    partes = []
    try:
        import version
        partes.append(f'v{version.APP_VERSION}')
    except Exception:
        pass
    partes.append(platform.platform())
    partes.append(f'Python {platform.python_version()}')
    try:
        import PySide6
        partes.append(f'PySide6 {PySide6.__version__}')
    except Exception:
        pass
    try:
        import motor_voz
        inf = motor_voz.info_instalado() or {}
        if inf:
            partes.append(f"IA: voz {inf.get('modelo')} / texto {inf.get('modelo_texto')} / {inf.get('gpu') or 'sin GPU'}")
    except Exception:
        pass
    try:
        libre = shutil.disk_usage(str(Path.home())).free / 1024 ** 3
        partes.append(f'disco libre {libre:.0f} GB')
    except Exception:
        pass
    info(' · '.join(partes), 'entorno')


def _revisar_cierre_anterior():
    """Si la sesion anterior no se cerro bien (se colgo o se cayo), lo deja anotado con la pista de donde mirar."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    if SESION.is_file():
        extra = ''
        try:
            if FALLOS_NATIVOS.is_file() and FALLOS_NATIVOS.stat().st_size > 0:
                extra = f' Hay un volcado del fallo en {FALLOS_NATIVOS.name}.'
        except OSError:
            pass
        estado = ''
        try:
            estado = SESION.read_text(encoding='utf-8').partition('|')[2].strip()
        except OSError:
            pass
        corte = None
        try:
            import vigilancia
            corte = vigilancia.tarea_cortada_anterior()
        except Exception:
            pass
        if estado == 'abriendo':
            error('La sesión anterior NO llegó a terminar de abrir: el programa se quedó atascado (o se cerró) durante el arranque.' + extra, 'sesión',
                  detalle='Mira errores.log y fallo_nativo.log (carpeta DaVinciSubtitles): ahí queda dónde se quedó. Si se repite, usa «Copiar informe» en el Registro y mándalo.')
        elif corte and corte[0]:
            error(f'La sesión anterior se cortó en mitad de «{corte[0]}», en el paso «{corte[1] or "?"}» (hace {int(corte[2] // 60)} min).' + extra, 'sesión')
        else:
            aviso('La sesión anterior de CineCaptions no se cerró bien (se colgó o se cayó).' + extra, 'sesión')
        _mac_informes_de_cierre()
    SESION.write_text(f'{time.time()}|abriendo', encoding='utf-8')
    import atexit
    atexit.register(lambda: SESION.unlink(missing_ok=True))


def _mac_informes_de_cierre():
    """En Mac, el sistema deja un informe de cada caída en ~/Library/Logs/DiagnosticReports: si hay uno reciente de CineCaptions se anota cuál es."""
    if sys.platform != 'darwin':
        return
    try:
        carpeta = Path.home() / 'Library' / 'Logs' / 'DiagnosticReports'
        limite = time.time() - 3 * 86400
        recientes = sorted((p for p in carpeta.glob('*') if 'cinecaptions' in p.name.lower() and p.stat().st_mtime > limite),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        if recientes:
            aviso(f'macOS guardó {len(recientes)} informe(s) de caída reciente(s) de CineCaptions: {recientes[0].name}', 'sesión',
                  detalle='Carpeta: ' + str(carpeta) + '\n' + '\n'.join(p.name for p in recientes[:5]))
    except Exception:
        pass


def entorno_detallado():
    """Líneas con el entorno real (Windows o Mac): sistema, arquitectura, Rosetta, memoria, GPU, si es el .exe/.app. Puede tardar unos segundos (subprocess):
    llamar en un hilo."""
    import locale
    import platform
    import subprocess
    lineas = []
    if sys.platform == 'darwin':
        lineas.append(f'macOS {platform.mac_ver()[0]} · {platform.machine()}')
        try:
            r = subprocess.run(['sysctl', '-n', 'sysctl.proc_translated'], capture_output=True, text=True, timeout=3).stdout.strip()
            if r == '1':
                lineas.append('ATENCIÓN: corre bajo Rosetta (la versión Intel en un Mac Apple Silicon): los modelos irán mucho más lentos.')
        except Exception:
            pass
        if platform.machine() == 'arm64':
            lineas.append('GPU: Apple Silicon (Metal / MPS)')
    elif sys.platform.startswith('win'):
        lineas.append(f'Windows {platform.version()} · {platform.machine()}')
    else:
        lineas.append(platform.platform())
    try:
        import vigilancia
        libre = vigilancia.memoria_libre_mb()
        lineas.append(f'CPU {os.cpu_count()} núcleos · memoria libre {libre} MB' if libre is not None else f'CPU {os.cpu_count()} núcleos')
    except Exception:
        pass
    if sys.platform.startswith('win') or sys.platform.startswith('linux'):
        try:
            r = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'], capture_output=True, text=True,
                               timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()
            lineas.append('GPU NVIDIA: ' + r if r else 'GPU NVIDIA: no detectada (voz e IA irán en CPU)')
        except Exception:
            lineas.append('GPU NVIDIA: no detectada (voz e IA irán en CPU)')
    lineas.append(('programa empaquetado' if getattr(sys, 'frozen', False) else 'desde código') + f' · {sys.executable}')
    try:
        lineas.append(f'idioma del sistema {locale.getlocale()[0]} · datos en {CARPETA}')
    except Exception:
        pass
    return lineas


def _entorno_en_hilo():
    def trabajo():
        try:
            info(' | '.join(entorno_detallado()), 'entorno')
        except Exception:
            pass
    threading.Thread(target=trabajo, daemon=True, name='entorno').start()


def _cola(ruta, n):
    try:
        return ''.join(Path(ruta).read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)[-n:])
    except Exception:
        return '(no hay)\n'


def reporte_soporte(lineas_log=150):
    """El informe que se manda para reportar un fallo (Windows o Mac): entorno, estado de librerías y motores, tareas en curso, los últimos errores y avisos
    (errores.log, que no se pierde con la rotación), el final del log y, si lo hay, el volcado del fallo nativo / los informes de caída de macOS."""
    partes = [f'CineCaptions · informe de soporte · {datetime.datetime.now():%Y-%m-%d %H:%M:%S}']
    try:
        import version
        partes.append(f'versión {version.APP_VERSION}')
    except Exception:
        pass
    try:
        partes.extend(entorno_detallado())
    except Exception:
        pass
    try:
        import salud
        filas = salud.ultimo()          # (el chequeo de arranque ya lo dejó hecho; no se vuelve a correr aquí: puede estar en el hilo de la interfaz)
        if filas:
            partes.append('\n== Librerías y motores ==\n' + salud.informe(filas))
    except Exception:
        pass
    try:
        import vigilancia
        partes.append('\n== Tareas en curso ==\n' + (', '.join(vigilancia.en_curso()) or 'ninguna'))
    except Exception:
        pass
    partes.append('\n== Avisos y errores (errores.log) ==\n' + _cola(ARCHIVO_ERRORES, lineas_log))
    partes.append('\n== Final del registro ==\n' + _cola(ARCHIVO, lineas_log))
    try:
        if FALLOS_NATIVOS.is_file() and FALLOS_NATIVOS.stat().st_size > 60:
            partes.append('\n== Volcado de fallo nativo ==\n' + _cola(FALLOS_NATIVOS, 80))
    except Exception:
        pass
    if sys.platform == 'darwin':
        try:
            carpeta = Path.home() / 'Library' / 'Logs' / 'DiagnosticReports'
            hay = sorted((p for p in carpeta.glob('*') if 'cinecaptions' in p.name.lower()), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
            if hay:
                partes.append('\n== Informes de caída de macOS ==\n' + '\n'.join(p.name for p in hay) + '\n' + _cola(hay[0], 60))
        except Exception:
            pass
    return '\n'.join(partes)


def guardar_reporte():
    """Escribe reporte_soporte.txt en la carpeta de datos y devuelve su ruta (o None)."""
    try:
        ruta = CARPETA / 'reporte_soporte.txt'
        CARPETA.mkdir(parents=True, exist_ok=True)
        ruta.write_text(reporte_soporte(), encoding='utf-8')
        return ruta
    except Exception:
        return None


def _fallos_nativos():
    """faulthandler: si Python o Qt se caen del todo (segfault), la traza de todos los hilos queda en fallo_nativo.log."""
    import faulthandler
    global _ARCHIVO_FALLOS
    _ARCHIVO_FALLOS = open(FALLOS_NATIVOS, 'a', encoding='utf-8')
    _ARCHIVO_FALLOS.write(f'--- sesion {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---' + chr(10))
    _ARCHIVO_FALLOS.flush()
    faulthandler.enable(_ARCHIVO_FALLOS, all_threads=True)


_ARCHIVO_FALLOS = None


def _gancho_unraisable():
    """Excepciones que Python no puede lanzar (destructores, callbacks): antes se perdian en silencio."""
    def gancho(args):
        try:
            texto = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
            aviso(f'{args.exc_type.__name__}: {args.exc_value}', 'excepción ignorada · ' + str(getattr(args.object, '__qualname__', args.object))[:60], detalle=texto)
        except Exception:
            pass
    sys.unraisablehook = gancho


def vigilar_congelaciones(umbral_s=2.5):
    """Detector de interfaz congelada: un hilo comprueba que el bucle de eventos siga latiendo; si pasa de 'umbral_s' sin
    responder anota CUANTO duro y la linea de codigo donde estaba atascado (lo que antes costaba horas de adivinar)."""
    from PySide6.QtCore import QTimer
    pulso = {'t': time.time(), 'aviso': 0.0}
    hilo_ui = threading.get_ident()
    reloj = QTimer()
    reloj.setInterval(250)
    reloj.timeout.connect(lambda: pulso.__setitem__('t', time.time()))
    reloj.start()

    def vigia():
        while True:
            time.sleep(0.5)
            parado = time.time() - pulso['t']
            if parado >= umbral_s and time.time() - pulso['aviso'] > 30:
                pulso['aviso'] = time.time()
                marco = sys._current_frames().get(hilo_ui)
                pila = ''.join(traceback.format_stack(marco)[-6:]) if marco is not None else ''
                try:
                    aviso(f'La interfaz estuvo sin responder {parado:.1f} s', 'congelación', detalle=pila)
                except Exception:
                    pass
    threading.Thread(target=vigia, daemon=True, name='vigia-ui').start()
    return reloj
