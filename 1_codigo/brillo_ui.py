# CineCaptions · By Cinema Productions
# 1_codigo/brillo_ui.py — barridos de luz y ondas al pulsar para todos los botones.
"""
brillo_ui.py
------------
Micro-animaciones de toda la interfaz con una sola pieza:

  * Barrido de luz: al pasar el cursor por un botón (Boton, Chip, BotonNav, el del registro…) una banda de luz diagonal lo cruza.
  * Onda al pulsar: un círculo de luz crece desde el punto donde se hizo clic.
  * Los botones principales (azules) se «dan un destello» solos cada pocos segundos, uno cada vez, para invitar al clic.
  * barrido_periodico(widget): el mismo barrido, pero cada cierto tiempo, para barras y tarjetas grandes.

Cada botón tiene (cuando hace falta, la primera vez que se le pasa el cursor) una capa transparente encima que dibuja la luz;
no come clics y se recorta con las esquinas redondeadas del botón. Con «Reducir animaciones» (Ajustes) no se mueve nada.
Las clases del kit solo llaman a entrar() / presionar() / ajustar() / mostrado() desde sus eventos.
"""
import random
import time
import weakref

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QWidget

_PRIMARIOS = weakref.WeakSet()
_RELOJ = [None]
_QUIETO = [False, 0.0]


def quieto():
    """«Reducir animaciones» de Ajustes (se relee cada pocos segundos, no en cada pasada del cursor)."""
    ahora = time.time()
    if ahora - _QUIETO[1] > 4.0:
        _QUIETO[1] = ahora
        try:
            import efectos_ui
            _QUIETO[0] = bool(efectos_ui.reducir_animaciones())
        except Exception:
            _QUIETO[0] = False
    return _QUIETO[0]


class _Capa(QWidget):
    """La capa de luz que va encima de un botón."""
    def __init__(self, destino, radio=10.0, fuerte=False, color='#FFFFFF'):
        super().__init__(destino)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._radio = float(radio)
        self._fuerte = bool(fuerte)
        self._color = QColor(color)
        self._b = 1.0
        self._o = 1.0
        self._punto = QPointF(0, 0)
        self._a_b = QVariantAnimation(self)
        self._a_b.setDuration(620)
        self._a_b.setStartValue(0.0)
        self._a_b.setEndValue(1.0)
        self._a_b.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._a_b.valueChanged.connect(self._paso_b)
        self._a_o = QVariantAnimation(self)
        self._a_o.setDuration(520)
        self._a_o.setStartValue(0.0)
        self._a_o.setEndValue(1.0)
        self._a_o.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_o.valueChanged.connect(self._paso_o)
        self._a_b.finished.connect(self._fin)
        self._a_o.finished.connect(self._fin)
        self.hide()

    def _fin(self):
        if self._b >= 1.0 and self._o >= 1.0:
            self.hide()

    def _paso_b(self, v):
        self._b = float(v)
        self.update()

    def _paso_o(self, v):
        self._o = float(v)
        self.update()

    def barrer(self):
        if self._a_b.state() == QVariantAnimation.State.Running:
            return
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._a_b.start()

    def onda(self, punto):
        self._punto = QPointF(punto)
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._a_o.stop()
        self._a_o.start()

    def paintEvent(self, _e):
        W, H = float(self.width()), float(self.height())
        if W < 4 or H < 4:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ruta = QPainterPath()
        ruta.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), self._radio, self._radio)
        p.setClipPath(ruta)
        if self._b < 1.0:
            b = self._b
            fuerza = (96 if self._fuerte else 52) * (1.0 - abs(b - 0.5) * 2.0) ** 0.8
            centro = -0.25 * W + 1.5 * W * b
            ancho = max(34.0, W * 0.34)
            sesgo = H * 0.55
            haz = QPolygonF([QPointF(centro - ancho, H), QPointF(centro - ancho + sesgo, 0), QPointF(centro + ancho + sesgo, 0), QPointF(centro + ancho, H)])
            g = QLinearGradient(centro - ancho, 0, centro + ancho + sesgo, 0)
            c0 = QColor(self._color)
            c0.setAlpha(0)
            c1 = QColor(self._color)
            c1.setAlpha(int(fuerza))
            g.setColorAt(0.0, c0)
            g.setColorAt(0.5, c1)
            g.setColorAt(1.0, c0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawPolygon(haz)
        if self._o < 1.0:
            o = self._o
            r = max(W, H) * (0.15 + 0.95 * o)
            g = QRadialGradient(self._punto, r)
            c0 = QColor(self._color)
            c0.setAlpha(int((86 if self._fuerte else 56) * (1.0 - o)))
            c1 = QColor(self._color)
            c1.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(0.7, c0)
            g.setColorAt(1.0, c1)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(self._punto, r, r)
        p.end()


def _capa(w):
    c = getattr(w, '_capa_brillo', None)
    if c is None:
        tipo = w.property('tipo') if hasattr(w, 'property') else None
        nombre = type(w).__name__
        radio = w.height() / 2.0 if nombre == 'Chip' else 10.0
        c = _Capa(w, radio=radio, fuerte=(tipo == 'primario'))
        w._capa_brillo = c
    return c


def entrar(w):
    """El cursor entró en el botón: barrido de luz."""
    try:
        if not w.isEnabled() or quieto():
            return
        _capa(w).barrer()
    except RuntimeError:
        pass


def presionar(w, ev=None):
    """Clic en el botón: onda de luz desde el punto pulsado."""
    try:
        if not w.isEnabled() or quieto():
            return
        pos = ev.position() if ev is not None and hasattr(ev, 'position') else QPointF(w.width() / 2, w.height() / 2)
        _capa(w).onda(pos)
    except RuntimeError:
        pass


def ajustar(w):
    c = getattr(w, '_capa_brillo', None)
    if c is not None:
        try:
            c.setGeometry(w.rect())
        except RuntimeError:
            pass


def mostrado(w):
    """v5.5: ya NO hay destellos automaticos (los botones se «daban un destello» solos y saturaban la vista): el brillo solo
    responde al mouse."""
    return None


def _arrancar_reloj():
    if _RELOJ[0] is None:
        t = QTimer()
        t.setInterval(3200)
        t.timeout.connect(_destello)
        t.start()
        _RELOJ[0] = t


def _destello():
    if quieto():
        return
    try:
        candidatos = [w for w in list(_PRIMARIOS) if w.isVisible() and w.isEnabled() and not w.underMouse()]
        if candidatos:
            _capa(random.choice(candidatos)).barrer()
    except RuntimeError:
        pass


def barrido_periodico(widget, cada_ms=9000, radio=14.0, fuerte=False, color='#FFFFFF'):
    """v5.5: desactivado (barridos periodicos solos = ruido). Se conserva la firma para quien lo llame."""
    return None
    """Un barrido de luz cada cierto tiempo sobre una barra o tarjeta grande (solo si se ve)."""
    capa = _Capa(widget, radio=radio, fuerte=fuerte, color=color)
    widget._capa_periodica = capa
    t = QTimer(widget)
    t.setInterval(int(cada_ms))
    t.timeout.connect(lambda: capa.barrer() if (widget.isVisible() and not quieto()) else None)
    t.start()
    widget._reloj_periodico = t
    return capa
