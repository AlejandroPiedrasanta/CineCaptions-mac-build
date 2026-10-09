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
import time
import weakref

from PySide6.QtCore import QTimer

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
