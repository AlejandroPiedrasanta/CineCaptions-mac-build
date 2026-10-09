# CineCaptions · By Cinema Productions
# 1_codigo/mograf_ui.py — Motion Graphics de la interfaz: entrada de tarjetas con marcas, título cinético, traza de luz, formas ambiente y HUD de Inicio.
"""
mograf_ui.py  (v5.3)
--------------------
Motion Graphics nativos (QPainter, vectoriales, sin web ni OpenGL) para TODAS las pantallas y para Inicio.
Pedido: «mejora las animaciones de todas las páginas y la página de inicio con Motion Graphics».

  * entrada_escalonada(...)  las tarjetas suben y aparecen una tras otra; en cada una se dibujan las cuatro marcas de
                             esquina («encuadre») y se apagan: el gesto clásico de un lower third.
  * EtiquetaCinetica         el título de cada pantalla entra letra a letra (subida + fundido) con un subrayado que se
                             dibuja de izquierda a derecha.
  * traza(tarjeta, si)       al pasar el cursor por una tarjeta, un punto de luz con cola recorre su borde.
  * sembrar_formas / dibujar_formas
                             formas geométricas finas (anillos, cruces, triángulos, hexágonos, arcos) que derivan y
                             giran muy despacio detrás de todo; y ráfagas de datos que cruzan de vez en cuando.
  * dibujar_hud(...)         lo de Inicio: dial de marcas girando alrededor de la esfera, órbitas con satélites, marcos
                             de visor en las esquinas con REC y timecode, y un radar que barre mientras GO trabaja.

Criterio (las skills de movimiento): curvas de salida, nada repetitivo en lo que se usa cien veces por minuto, el
espectáculo en los momentos raros. Todo respeta «Reducir animaciones» y no cuesta CPU cuando no se ve (los
temporizadores solo corren mientras hay algo que mover).
"""
import math
import random
import time

from PySide6.QtCore import QEasingCurve, QEvent, QLineF, QObject, QPointF, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import (QConicalGradient, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF)
from PySide6.QtWidgets import QFrame, QGraphicsEffect, QWidget

import qt_kit as ui
from qt_kit import QColor, QColorReal

TAU = math.tau


def quieto():
    """«Reducir animaciones» (Ajustes > Interfaz) o la bandera global de brillo_ui."""
    try:
        import brillo_ui
        if brillo_ui.quieto():
            return True
    except Exception:
        pass
    try:
        import efectos_ui
        return bool(efectos_ui.reducir_animaciones())
    except Exception:
        return False


def _rgba(color, alfa):
    c = QColor(color)
    return QColorReal(c.red(), c.green(), c.blue(), max(0, min(255, int(alfa))))


def _clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def _salida(t):
    t = _clamp(t)
    return 1.0 - (1.0 - t) ** 3


def _suave(t):
    t = _clamp(t)
    return t * t * (3.0 - 2.0 * t)


# =====================================================================================================================
# 1. La entrada de las tarjetas (subida + fundido + marcas de esquina)
# =====================================================================================================================
class _EfectoEntrada(QGraphicsEffect):
    """Dibuja el widget desplazado hacia abajo 'dy' px, con opacidad 'op' y, encima, sus cuatro marcas de esquina
    (se dibujan hacia fuera y se apagan; 'k' es el avance 0..1). Se quita al terminar.

    v5.4: las marcas eran un widget hijo que se repintaba en cada cuadro; un hijo que se repinta invalida la imagen
    de la tarjeta y obliga a rasterizar TODA la tarjeta (y la pagina) otra vez en cada cuadro -> tirones al cambiar
    de pestaña. Pintadas aqui, la imagen de la tarjeta se queda en cache y cada cuadro solo la coloca."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self._op = 0.0
        self._dy = 0.0
        self._k = 0.0

    def poner(self, op, dy, k=0.0):
        self._op, self._dy, self._k = float(op), float(dy), float(k)
        self.update()

    def boundingRectFor(self, rect):
        return rect.adjusted(0, 0, 0, abs(self._dy) + 1.0)

    def draw(self, painter):
        pix = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates)
        if pix.isNull():
            return
        painter.save()
        painter.setOpacity(self._op)
        painter.drawPixmap(QPointF(0.0, self._dy), pix)
        # v5.5: sin las marcas de esquina (era ruido visual: la entrada es solo subir y aparecer con un resorte)
        painter.restore()

    def _dibujar_marcas(self, p):
        k = self._k
        if k <= 0.02 or k >= 0.995:
            return
        largo = 24.0 * _salida(k / 0.55)
        alfa = 235.0 * (1.0 - _clamp((k - 0.50) / 0.50))
        if alfa <= 2:
            return
        r = self.sourceBoundingRect(Qt.CoordinateSystem.LogicalCoordinates)
        x0, y0 = r.left(), r.top() + self._dy
        W, H = r.width(), r.height()
        m = 5.0
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(_rgba(ui.ACCENT_CLARO, alfa), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for x, y, sx, sy in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
            p.drawLine(QPointF(x0 + x, y0 + y), QPointF(x0 + x + sx * largo, y0 + y))
            p.drawLine(QPointF(x0 + x, y0 + y), QPointF(x0 + x, y0 + y + sy * largo))


def entrada_escalonada(widgets, retardo=70, duracion=620, subida=26):
    """Las tarjetas suben y aparecen una tras otra; en cada una se dibujan sus marcas de esquina."""
    if quieto():
        return
    for k, w in enumerate(widgets):
        if w is None or not w.isVisible():
            continue
        efecto = _EfectoEntrada(w)
        efecto.poner(0.0, subida)
        w.setGraphicsEffect(efecto)
        anim = QVariantAnimation(w)
        anim.setDuration(duracion)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        curva = QEasingCurve(QEasingCurve.Type.OutBack)       # un resorte con ~7 % de rebote (la curva a medida de Python tumbaba Qt)
        curva.setOvershoot(1.05)
        anim.setEasingCurve(curva)

        def paso(v, efecto=efecto):
            v = float(v)
            if ui.vivo(efecto):
                efecto.poner(min(1.0, v), (1.0 - v) * subida, min(1.0, v))

        def fin(w=w):
            if ui.vivo(w):
                w.setGraphicsEffect(None)

        anim.valueChanged.connect(paso)
        anim.finished.connect(fin)
        QTimer.singleShot(k * retardo, anim.start)
        w._anim_entrada = anim


# =====================================================================================================================
# 2. El título cinético
# =====================================================================================================================
class EtiquetaCinetica(ui.Etiqueta):
    """El título de una pantalla: al llamar a revelar() entra letra a letra (subida + fundido) y dibuja su subrayado."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._k = 1.0
        self._anim = None

    def revelar(self):
        if quieto() or not self.isVisible():
            return
        if self._anim is None:
            self._anim = QVariantAnimation(self)
            self._anim.setDuration(780)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.Type.Linear)
            self._anim.valueChanged.connect(self._paso)
            self._anim.finished.connect(self._fin)
        self._anim.stop()
        self._k = 0.0
        self._anim.start()

    def _paso(self, v):
        self._k = float(v)
        self.update()

    def _fin(self):
        self._k = 1.0
        self.update()

    def paintEvent(self, e):
        k = self._k
        if k >= 1.0:
            return super().paintEvent(e)
        texto = self.text()
        n = max(1, len(texto))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        f = self.font()
        p.setFont(f)
        fm = QFontMetricsF(f)
        x = float(self.contentsMargins().left())
        base = (self.height() + fm.ascent() - fm.descent()) / 2.0
        color = QColor(self._color or '#FFFFFF')
        ancho_total = fm.horizontalAdvance(texto)
        for i, ch in enumerate(texto):
            t = _salida((k * (n + 7) - i) / 7.0)
            if t > 0.0:
                c = QColorReal(color.red(), color.green(), color.blue(), int(255 * t))
                p.setPen(c)
                p.drawText(QPointF(x, base + (1.0 - t) * 13.0), ch)
            x += fm.horizontalAdvance(ch)
        # el subrayado se dibuja y se apaga
        u = _suave(_clamp(k / 0.7))
        alfa = 230.0 * (1.0 - _clamp((k - 0.62) / 0.38))
        if alfa > 2:
            y = base + fm.descent() + 4.0
            x0 = float(self.contentsMargins().left())
            g = QLinearGradient(x0, y, x0 + ancho_total, y)
            g.setColorAt(0.0, _rgba(ui.ACCENT_CLARO, alfa))
            g.setColorAt(1.0, _rgba(ui.ACCENT_CLARO, 0))
            p.setPen(QPen(g, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x0, y), QPointF(x0 + ancho_total * u, y))
        p.end()


# =====================================================================================================================
# 3. La traza de luz en el borde de las tarjetas (al pasar el cursor)
# =====================================================================================================================
class _Traza(QWidget):
    """Un punto de luz con cola que recorre el borde de la tarjeta mientras el cursor está encima."""
    COLA = 14
    VUELTA_S = 3.4

    def __init__(self, tarjeta):
        super().__init__(tarjeta)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._u = random.random()
        self._a = 0.0                  # opacidad 0..1
        self._meta = 0.0
        self._camino = None
        self._ultima = QRect()
        self._t = QTimer(self)
        self._t.timeout.connect(self._tic)
        self._ult = time.perf_counter()
        tarjeta.installEventFilter(self)
        self._geometria()
        self.show()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize:
            self._geometria()
        return False

    def _geometria(self):
        t = self.parentWidget()
        self.setGeometry(t.rect())
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        c = QPainterPath()
        c.addRoundedRect(r, 14, 14)
        self._camino = c

    def activar(self, si):
        self._meta = 1.0 if si else 0.0
        if not self._t.isActive():
            self._ult = time.perf_counter()
            self._t.start(33)
        self.raise_()

    def _tic(self):
        ahora = time.perf_counter()
        dt = min(0.1, ahora - self._ult)
        self._ult = ahora
        self._u = (self._u + dt / self.VUELTA_S) % 1.0
        self._a += (self._meta - self._a) * min(1.0, dt * 8.0)
        if self._meta == 0.0 and self._a < 0.02:
            self._t.stop()
            self._a = 0.0
            self.update(self._ultima.adjusted(-6, -6, 6, 6))
            return
        nueva = self._caja()
        self.update(self._ultima.united(nueva).adjusted(-6, -6, 6, 6) if not self._ultima.isNull() else nueva)
        self._ultima = nueva

    def _puntos(self):
        pts = []
        for i in range(self.COLA):
            u = (self._u - i * 0.012) % 1.0
            pts.append(self._camino.pointAtPercent(u))
        return pts

    def _caja(self):
        pts = self._puntos()
        xs = [q.x() for q in pts]
        ys = [q.y() for q in pts]
        return QRect(int(min(xs)) - 3, int(min(ys)) - 3, int(max(xs) - min(xs)) + 7, int(max(ys) - min(ys)) + 7)

    def paintEvent(self, _e):
        if self._a < 0.02 or self._camino is None:
            return
        pts = self._puntos()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(len(pts) - 1):
            f = 1.0 - i / float(len(pts))
            p.setPen(QPen(_rgba(ui.ACCENT_CLARO, 235 * f * f * self._a), 1.0 + 1.8 * f, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(pts[i], pts[i + 1])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_rgba('#FFFFFF', 255 * self._a))
        p.drawEllipse(pts[0], 2.1, 2.1)
        p.end()


def traza(tarjeta, si):
    """Enciende o apaga la traza de luz del borde de una tarjeta (enterEvent / leaveEvent de Tarjeta)."""
    if quieto() or tarjeta is None or tarjeta.property('sin_traza'):
        return
    if tarjeta.height() > 700 or tarjeta.width() < 120 or tarjeta.graphicsEffect() is not None:
        return
    t = getattr(tarjeta, '_traza_mg', None)
    if t is None or not ui.vivo(t):
        if not si:
            return
        t = _Traza(tarjeta)
        tarjeta._traza_mg = t
    t.activar(si)


# =====================================================================================================================
# 4. Formas ambiente (detrás de todas las pantallas)
# =====================================================================================================================
class _Forma:
    __slots__ = ('tipo', 'x', 'y', 'tam', 'rot', 'vrot', 'vx', 'vy', 'alfa', 'color', 'fase')

    def __init__(self, tipo, x, y, tam, rot, vrot, vx, vy, alfa, color, fase):
        self.tipo, self.x, self.y, self.tam, self.rot, self.vrot = tipo, x, y, tam, rot, vrot
        self.vx, self.vy, self.alfa, self.color, self.fase = vx, vy, alfa, color, fase


def sembrar_formas(n=9):
    r = random.Random(11)
    tipos = ['anillo', 'cruz', 'triangulo', 'hex', 'arco', 'puntos', 'anillo', 'hex', 'cruz']
    colores = [ui.ACCENT_CLARO, '#22D3EE', '#8B5CF6', '#FFFFFF', ui.ROL_PRINCIPAL]
    formas = []
    for i in range(n):
        formas.append(_Forma(tipos[i % len(tipos)], r.random(), r.random(), r.uniform(18, 64), r.uniform(0, 360),
                             r.uniform(-9, 9), r.uniform(-0.006, 0.006), r.uniform(-0.004, 0.004), r.uniform(26, 52),
                             r.choice(colores), r.uniform(0, TAU)))
    return formas


def _poligono(cx, cy, r, lados, rot):
    return QPolygonF([QPointF(cx + r * math.cos(math.radians(rot) + j * TAU / lados),
                              cy + r * math.sin(math.radians(rot) + j * TAU / lados)) for j in range(lados)])


def dibujar_formas(p, w, h, t, k, formas):
    """Dibuja las formas (k = intensidad 0..1 del fondo). Líneas finas, alfa bajo: no compiten con lo que se lee."""
    if k <= 0.02 or not formas:
        return
    p.save()
    p.setBrush(Qt.BrushStyle.NoBrush)
    for f in formas:
        x = ((f.x + f.vx * t) % 1.2 - 0.1) * w
        y = ((f.y + f.vy * t) % 1.2 - 0.1) * h
        rot = f.rot + f.vrot * t
        alfa = (f.alfa * (0.7 + 0.3 * math.sin(t * 0.5 + f.fase))) * (0.35 + 0.65 * k)
        p.setPen(QPen(_rgba(f.color, alfa), 1.2))
        r = f.tam
        if f.tipo == 'anillo':
            p.drawEllipse(QPointF(x, y), r, r)
            p.setPen(QPen(_rgba(f.color, alfa * 1.5), 1.6))
            p.drawArc(QRectF(x - r * 0.62, y - r * 0.62, r * 1.24, r * 1.24), int(rot * 16), 70 * 16)
        elif f.tipo == 'cruz':
            p.save()
            p.translate(x, y)
            p.rotate(rot)
            p.drawLine(QPointF(-r * 0.5, 0), QPointF(r * 0.5, 0))
            p.drawLine(QPointF(0, -r * 0.5), QPointF(0, r * 0.5))
            p.restore()
        elif f.tipo == 'triangulo':
            p.drawPolygon(_poligono(x, y, r * 0.8, 3, rot))
        elif f.tipo == 'hex':
            p.drawPolygon(_poligono(x, y, r * 0.8, 6, rot))
            p.drawPolygon(_poligono(x, y, r * 0.42, 6, -rot))
        elif f.tipo == 'arco':
            p.setPen(QPen(_rgba(f.color, alfa * 1.3), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(x - r, y - r, 2 * r, 2 * r), int(rot * 16), 210 * 16)
        else:                                  # 'puntos': una mini rejilla de 3 x 3
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_rgba(f.color, alfa * 1.4))
            for i in range(3):
                for j in range(3):
                    p.drawEllipse(QPointF(x + (i - 1) * 10, y + (j - 1) * 10), 1.3, 1.3)
            p.setBrush(Qt.BrushStyle.NoBrush)
    p.restore()


# =====================================================================================================================
# 5. El HUD de Inicio (encuadre de cámara, dial, órbitas, radar)
# =====================================================================================================================
def _letras(f, espacio=1.8):
    f = QFont(f)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espacio)
    return f


def dibujar_hud(p, W, H, c, Rs, t, energia=0.0, estado='reposo', calidad=1.0, carga=0.0):
    """La capa de Motion Graphics de Inicio, dibujada sobre la esfera. 't' = segundos de la escena; 'energia' 0..1."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    entra = _salida(t / 1.6)
    trabaja = estado in ('trabajando', 'explotando')
    azul, claro, cian = '#4589FF', '#8FB4FF', '#22D3EE'
    detalle = calidad >= 0.55

    # --- 1. el dial: marcas que giran alrededor de la esfera (se aceleran y se encienden con la energía)
    n = 96 if detalle else 48
    giro = t * (0.10 + 0.9 * energia)
    r0, r1, r2 = Rs * 1.10, Rs * 1.135, Rs * 1.175
    largas, cortas = [], []                                         # dos grupos de marcas = dos llamadas de dibujo (no 96)
    for i in range(n):
        a = giro + i * TAU / n
        ca, sa = math.cos(a), math.sin(a)
        larga = i % 6 == 0
        rr = r2 if larga else r1
        (largas if larga else cortas).append(QLineF(c.x() + r0 * ca, c.y() + r0 * sa, c.x() + rr * ca, c.y() + rr * sa))
    p.setPen(QPen(_rgba(claro, (26 + 80 * energia) * entra), 1.2))
    p.drawLines(cortas)
    p.setPen(QPen(_rgba(claro, (72 + 80 * energia) * entra), 1.8))
    p.drawLines(largas)
    # un arco brillante que gira por fuera del dial
    p.setPen(QPen(_rgba(cian, (70 + 120 * energia) * entra), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    ra = Rs * 1.23
    p.drawArc(QRectF(c.x() - ra, c.y() - ra, 2 * ra, 2 * ra), int(-giro * 1.3 * 57.2958 * 16), 52 * 16)
    p.drawArc(QRectF(c.x() - ra, c.y() - ra, 2 * ra, 2 * ra), int((-giro * 1.3 * 57.2958 + 180) * 16), 26 * 16)

    # --- 2. órbitas con satélites
    for rx, incl, vel, nsat, col in ((Rs * 1.50, -18.0, 0.34, 2, claro), (Rs * 1.92, 23.0, -0.21, 3, cian)):
        p.save()
        p.translate(c)
        p.rotate(incl)
        p.setPen(QPen(_rgba(col, 46 * entra), 1.0))
        p.drawEllipse(QPointF(0, 0), rx, rx * 0.30)
        for s in range(nsat):
            ang = t * vel * (1.0 + 2.2 * energia) + s * TAU / nsat
            sx, sy = rx * math.cos(ang), rx * 0.30 * math.sin(ang)
            prof = 0.5 + 0.5 * math.sin(ang)                  # 0 = detrás, 1 = delante
            r = 1.6 + 2.2 * prof
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_rgba(col, (40 + 90 * prof) * entra))
            p.drawEllipse(QPointF(sx, sy), r * 2.6, r * 2.6)
            p.setBrush(_rgba('#FFFFFF', (90 + 160 * prof) * entra))
            p.drawEllipse(QPointF(sx, sy), r, r)
        p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)

    # --- 3. radar mientras GO trabaja
    if trabaja and detalle:
        ang = -(t * 160.0) % 360.0
        g = QConicalGradient(c, ang)
        g.setColorAt(0.0, _rgba(cian, 90))
        g.setColorAt(0.16, _rgba(azul, 0))
        g.setColorAt(1.0, _rgba(azul, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        rr = Rs * 1.16
        p.drawEllipse(c, rr, rr)
        p.setBrush(Qt.BrushStyle.NoBrush)

    # --- 4. (v5.4) sin encuadre de visor, REC ni timecode: solo la barra de carga mientras GO trabaja
    m = 26.0
    if detalle and W > 520:
        # barra de carga fina bajo el pie mientras trabaja
        if trabaja and carga > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_rgba(claro, 40))
            p.drawRect(QRectF(m + 4, H - m - 3, W - 2 * m - 8, 2))
            g = QLinearGradient(m + 4, 0, W - m - 4, 0)
            g.setColorAt(0.0, _rgba(azul, 230))
            g.setColorAt(1.0, _rgba(cian, 230))
            p.setBrush(g)
            p.drawRect(QRectF(m + 4, H - m - 3, (W - 2 * m - 8) * _clamp(carga), 2))
    p.restore()
