# CineCaptions · By Cinema Productions
# 1_codigo/ritmo_ui.py — Regulador del ritmo de las animaciones: si la interfaz va justa (GO usando CPU/GPU, equipo modesto) baja los fotogramas del fondo y de la esfera para que los clics respondan; los sube al aliviarse.
"""
ritmo_ui.py  (v5.3)
-------------------
La interfaz pinta con QPainter (CPU). En Inicio el fondo y la esfera repintan casi toda la ventana ~30 veces por segundo; con
GO trabajando (voz, IA, Resolve) o en un equipo modesto eso se nota como una interfaz lenta.

El regulador mide el retraso real de un temporizador de 250 ms (si el bucle de eventos va saturado, llega tarde) y ajusta un
factor que multiplica el intervalo de los relojes registrados:
    nivel 0 -> x1.0 (todo fluido)    nivel 1 -> x1.5    nivel 2 -> x2.2
Sube de nivel rápido (retraso > 35 ms) y baja despacio (retraso < 12 ms durante ~2 s) para no oscilar. Nunca pausa nada:
solo alarga el intervalo, así que «las animaciones no se detienen» se cumple; en un equipo holgado queda siempre en el nivel 0.
"""
import sys
import threading
import time
import weakref

from PySide6.QtCore import QObject, Qt, QTimer, Signal

FACTORES = (1.0, 1.5, 2.2)
_PERIODO_MS = 250
_SUBE_MS = 35.0
_BAJA_MS = 12.0
_BAJA_TICS = 8


class _Ritmo:
    def __init__(self):
        self.nivel = 0
        self._relojes = []                 # [(weakref al QTimer, intervalo base en ms)]
        self._tic_t = None
        self._lag = 0.0
        self._calmo = 0
        self._espera = _BAJA_TICS           # tics calmos que hacen falta para bajar de nivel (se alarga si oscila)
        self._t_baja = 0.0
        self._timer = None

    @property
    def factor(self):
        return FACTORES[self.nivel]

    def iniciar(self):
        """Arranca la medición (una vez, con la QApplication creada)."""
        if self._timer is not None:
            return
        self._timer = QTimer()
        self._timer.setInterval(_PERIODO_MS)
        self._timer.timeout.connect(self._medir)
        self._tic_t = time.perf_counter()
        self._timer.start()

    def poner(self, reloj, base_ms):
        """Fija el intervalo base de un QTimer (el efectivo es base x factor) y lo registra si es nuevo."""
        base_ms = max(1, int(base_ms))
        for i, (ref, _b) in enumerate(self._relojes):
            if ref() is reloj:
                self._relojes[i] = (ref, base_ms)
                break
        else:
            self._relojes.append((weakref.ref(reloj), base_ms))
        reloj.setInterval(max(1, int(base_ms * self.factor)))

    def _medir(self):
        ahora = time.perf_counter()
        lag = max(0.0, (ahora - self._tic_t) * 1000.0 - _PERIODO_MS)
        self._tic_t = ahora
        self._lag = 0.5 * self._lag + 0.5 * lag
        if self._lag > _SUBE_MS and self.nivel < len(FACTORES) - 1:
            self.nivel += 1
            self._calmo = 0
            if time.perf_counter() - self._t_baja < 30.0:        # volvió a saturarse poco después de bajar: oscilaba
                self._espera = min(120, self._espera * 2)
            self._aplicar()
        elif self._lag < _BAJA_MS and self.nivel > 0:
            self._calmo += 1
            if self._calmo >= self._espera:
                self.nivel -= 1
                self._calmo = 0
                self._t_baja = time.perf_counter()
                self._aplicar()
        else:
            self._calmo = 0

    def _aplicar(self):
        vivos = []
        for ref, base in self._relojes:
            r = ref()
            if r is None:
                continue
            vivos.append((ref, base))
            try:
                r.setInterval(max(1, int(base * self.factor)))
            except RuntimeError:           # el QTimer ya se destruyó
                vivos.pop()
        self._relojes = vivos


ritmo = _Ritmo()


# ---------------------------------------------------------------------------------------------------------------------------------
# v5.49 (el usuario: «la animación de la página de inicio se traba demasiado y no se ve fluida»): un QTimer de 16 ms da 62,5 cuadros
# por segundo y el monitor refresca a 59,94-60 Hz: cada ~0,4 s dos cuadros caen en el mismo refresco y uno no llega a verse (un salto
# visible en todo lo que gira). RelojPantalla late con el refresco REAL del monitor: en Windows un hilo espera el vblank de la tarjeta
# (D3DKMTWaitForVerticalBlankEvent, lo mismo que usa Chromium) y avisa a la interfaz; a 30 fps late uno de cada dos, y en monitores de
# 120/144 Hz uno de cada dos o tres (nunca más de ~72 por segundo). Si no se puede (Mac, escritorio remoto, el vblank deja de llegar
# con la pantalla apagada…) es un QTimer normal. Se usa igual que un QTimer: timeout, start, stop, setInterval, isActive.

class _Vblank:
    """El vblank del monitor donde está la ventana `hwnd` (None o inválida = el principal). esperar() bloquea hasta el siguiente (sin
    el GIL: ctypes lo suelta)."""

    def __init__(self, hwnd):
        import ctypes
        from ctypes import wintypes

        class _Luid(ctypes.Structure):
            _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]

        class _Abrir(ctypes.Structure):
            _fields_ = [('hDc', wintypes.HDC), ('hAdapter', wintypes.UINT), ('AdapterLuid', _Luid), ('VidPnSourceId', wintypes.UINT)]

        class _Espera(ctypes.Structure):
            _fields_ = [('hAdapter', wintypes.UINT), ('hDevice', wintypes.UINT), ('VidPnSourceId', wintypes.UINT)]

        class _Monitor(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT), ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD),
                        ('szDevice', wintypes.WCHAR * 32)]

        self._ct = ctypes
        user32 = ctypes.WinDLL('user32')
        user32.MonitorFromWindow.restype = wintypes.HMONITOR
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromPoint.restype = wintypes.HMONITOR
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
        mon = user32.MonitorFromWindow(hwnd, 0) if hwnd else None                  # 0 = NULL si la ventana no vale
        mon = mon or user32.MonitorFromPoint(wintypes.POINT(0, 0), 1)             # 1 = el principal
        info = _Monitor()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            raise OSError('sin GetMonitorInfo')
        self._gdi = ctypes.WinDLL('gdi32')
        self._gdi.CreateDCW.restype = wintypes.HDC
        self._gdi.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
        self._gdi.DeleteDC.argtypes = [wintypes.HDC]
        a = _Abrir()
        a.hDc = self._gdi.CreateDCW(info.szDevice, None, None, None)              # «\\.\DISPLAY1»
        if not a.hDc:
            raise OSError('sin DC de la pantalla')
        try:
            st = self._gdi.D3DKMTOpenAdapterFromHdc(ctypes.byref(a))
        finally:
            self._gdi.DeleteDC(a.hDc)
        if st != 0:
            raise OSError(f'D3DKMTOpenAdapterFromHdc {st & 0xFFFFFFFF:#x}')
        self._adaptador = a.hAdapter
        self._espera = _Espera(a.hAdapter, 0, a.VidPnSourceId)

    def esperar(self):
        return self._gdi.D3DKMTWaitForVerticalBlankEvent(self._ct.byref(self._espera)) == 0

    def cerrar(self):
        try:
            self._gdi.D3DKMTCloseAdapter(self._ct.byref(self._ct.c_uint(self._adaptador)))
        except Exception:
            pass


class RelojPantalla(QObject):
    """Un QTimer que, a 60 y 30 fps, late con el refresco del monitor (ver arriba). `pantalla`: () -> el HWND de la ventana (su monitor);
    se mira al pasar a latir con el monitor."""
    timeout = Signal()
    _vblank = Signal()
    MAX_VSYNC_MS = 40                       # por encima (250 ms minimizada, 160 ms con «Reducir animaciones»): QTimer normal

    def __init__(self, padre=None):
        super().__init__(padre)
        self.pantalla = None
        self._ms = 16
        self._activo = False
        self._con_vsync = False
        self._sin_vsync_hasta = float('inf') if sys.platform != 'win32' else 0.0     # tras un fallo se reintenta a los 20 s
        self._fallo = False
        self._gen = 0
        self._pendiente = False
        self._periodo = 1.0 / 60.0                         # el del monitor, medido en el hilo
        self._ult = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tic_timer)
        self._guardia = QTimer(self)                       # si el vblank deja de llegar (pantalla apagada, driver), sigue a mano
        self._guardia.setInterval(100)
        self._guardia.timeout.connect(self._vigilar)
        self._vblank.connect(self._en_vblank, Qt.ConnectionType.QueuedConnection)

    # -- la API de QTimer que usa la escena
    def setTimerType(self, _tipo):
        pass

    def interval(self):
        return self._ms

    def isActive(self):
        return self._activo

    def setInterval(self, ms):
        self._ms = max(1, int(ms))
        if self._activo:
            self._arrancar()

    def start(self, ms=None):
        if ms is not None:
            self._ms = max(1, int(ms))
        self._activo = True
        self._arrancar()

    def stop(self):
        self._activo = False
        self._timer.stop()
        self._guardia.stop()
        self._gen += 1                                     # el hilo termina en el siguiente vblank
        self._con_vsync = False

    def con_vsync(self):
        """True si ahora mismo late con el monitor (para las pruebas)."""
        return self._activo and self._con_vsync

    # -- por dentro
    def _arrancar(self):
        if self._ms <= self.MAX_VSYNC_MS and time.perf_counter() >= self._sin_vsync_hasta:
            self._timer.stop()
            if not self._con_vsync:
                self._gen += 1
                gen = self._gen
                try:
                    hwnd = self.pantalla() if self.pantalla is not None else None
                except Exception:
                    hwnd = None
                self._con_vsync = True
                self._pendiente = False
                self._ult = time.perf_counter()
                threading.Thread(target=self._bucle, args=(gen, hwnd), name='reloj-vblank', daemon=True).start()
            self._guardia.start()
            return
        self._gen += 1
        self._con_vsync = False
        self._guardia.stop()
        self._timer.start(self._ms)

    def _bucle(self, gen, hwnd):
        try:
            vb = _Vblank(hwnd)
        except Exception:
            self._pedir_timer(gen)
            return
        try:
            n = 0
            t_prev = time.perf_counter()
            while gen == self._gen:
                if not vb.esperar():
                    self._pedir_timer(gen)
                    return
                ahora = time.perf_counter()
                d = ahora - t_prev
                t_prev = ahora
                if 0.003 < d < 0.05:
                    self._periodo += (d - self._periodo) * 0.05
                n += 1
                cada = max(1, round(self._ms / 1000.0 / self._periodo))
                if n % cada or self._pendiente:            # la interfaz aún no atendió el anterior: no se amontonan
                    continue
                self._pendiente = True
                try:
                    self._vblank.emit()
                except RuntimeError:                       # el reloj ya no existe
                    return
        finally:
            vb.cerrar()

    def _pedir_timer(self, gen):
        """(en el hilo) el vblank no funciona: la interfaz pasa al QTimer (_en_vblank ve _fallo)."""
        if gen != self._gen:
            return
        self._fallo = True
        self._pendiente = True
        try:
            self._vblank.emit()
        except RuntimeError:
            pass

    def _sin_vsync(self):
        self._fallo = False
        self._sin_vsync_hasta = time.perf_counter() + 20.0
        self._con_vsync = False
        self._arrancar()

    def _en_vblank(self):
        self._pendiente = False
        if not self._activo:
            return
        if self._fallo:
            if self._con_vsync:
                self._sin_vsync()
            return
        self._ult = time.perf_counter()
        self.timeout.emit()

    def _tic_timer(self):
        self.timeout.emit()
        if self._activo and self._ms <= self.MAX_VSYNC_MS and time.perf_counter() >= self._sin_vsync_hasta:
            self._arrancar()                               # pasaron los 20 s tras un fallo: se vuelve a probar con el monitor

    def _vigilar(self):
        if not (self._activo and self._con_vsync):
            return
        hueco = time.perf_counter() - self._ult
        if hueco > 1.5:                                    # el vblank no llega (pantalla apagada…): QTimer normal un rato
            self._sin_vsync()
        elif hueco > 0.1:
            self._ult = time.perf_counter()
            self.timeout.emit()
