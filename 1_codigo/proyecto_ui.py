# CineCaptions · By Cinema Productions
# 1_codigo/proyecto_ui.py — v5.32: el aspecto nuevo de la página Proyecto (las maquetas del usuario): la franja del audio y el bloque del tema.
"""
v5.32 (el usuario, con sus maquetas: «en la página de proyecto aplica ese estilo tal cual», «los botones… hazlo así exactamente» y «hazlo
exactamente igual a las referencias… tiene una animación, púlelo más»):
  · franja del audio: «Obtener» y «Crea tu estilo» como botones luminosos (BotonLuz: degradado del acento al turquesa con halo), el chip del
    formato con borde de acento, separadores finos (Separador) y el motor de voz como dos píldoras (PildoraMotor: la elegida con borde y halo);
  · bloque del tema (FondoTema): detrás, un halo lila y, a cada lado y en espejo, dos arcos finos que suben de los botones al nombre con un
    punto que se desliza; el nombre (un_clic_ui.TituloGo estilo 'tema': de blanco a celeste y lila, con su raya de luz que recorre) y los
    dos botones grandes (BotonEstado, emparejados al mismo ancho): «En uso» verde con su ✓ y «Edición PRO activada» dorado con su corona;
    respiran a la vez y un destello los cruza seguidos. Sin la píldora «TEMA ACTIVO» (el usuario: «elimina esto para que el slider esté más
    grande… todo proporcional y simétrico»).
Todo pintado (sin efectos de Qt: regla de rendimiento). Lo que late usa UN reloj (RELOJ, 30 cuadros/s) que solo corre mientras algo se ve y
nunca con «Reducir animaciones» (mograf_ui.quieto); cada pieza repinta solo su rectángulo. Los verdes salen del color de acento del tema.
"""
import math
import random
import time
import weakref

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QRegion
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QWidget

import qt_kit as ui
from qt_kit import Boton, QColor, QColorReal, fuente

ORO, ORO_CLARO = '#FFC93C', '#FFE08A'
CIAN = '#38BDF8'
_ICONOS = {}


def _icono(nombre, color):
    k = (nombre, color)
    if k not in _ICONOS:
        _ICONOS[k] = ui.icono_linea('ph.' + nombre, color)
    return _ICONOS[k]


def _real(color):
    """Un QColorReal de un texto o de otro color (el QColor del tema pasa los azules al acento: aquí no se quiere)."""
    if isinstance(color, str):
        return QColorReal(color)
    return QColorReal(color.red(), color.green(), color.blue(), color.alpha())


def _rgba(color, a):
    q = _real(color)
    return QColorReal(q.red(), q.green(), q.blue(), max(0, min(255, int(a))))


def _mezcla(a, b, k):
    a, b = _real(QColor(a) if isinstance(a, str) else a), _real(b)
    return QColorReal(int(a.red() + (b.red() - a.red()) * k), int(a.green() + (b.green() - a.green()) * k),
                      int(a.blue() + (b.blue() - a.blue()) * k))


def _oscuro(color, k):
    """El color mezclado con el azul noche del fondo (k = cuánto queda del color)."""
    q = _real(color)
    return QColorReal(int(8 + (q.red() - 8) * k), int(14 + (q.green() - 14) * k), int(26 + (q.blue() - 26) * k))


def _halo(p, r, radio, color, capas=((10, 10), (6, 20), (3, 34)), k=1.0):
    """Un halo suave alrededor de `r`: bordes cada vez más finos y opacos (sin QGraphicsEffect). `k` lo atenúa (el latido)."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    for grosor, alfa in capas:
        p.setPen(QPen(_rgba(color, alfa * k), grosor))
        p.drawRoundedRect(r, radio, radio)


def _quieto():
    try:
        import mograf_ui
        return mograf_ui.quieto()
    except Exception:
        return False


class _Reloj:
    """Un solo reloj para todo lo que late en Proyecto (30 cuadros/s): llama a `latir()` de las piezas a la vista y se para solo cuando ninguna
    se ve. Con «Reducir animaciones» no arranca: las piezas se pintan quietas."""
    def __init__(self):
        self._piezas = weakref.WeakSet()
        self._t = None

    def alta(self, pieza):
        if _quieto():
            return
        self._piezas.add(pieza)
        if self._t is None:
            self._t = QTimer()
            self._t.setInterval(33)
            self._t.timeout.connect(self._tic)
        if not self._t.isActive():
            self._t.start()

    def baja(self, pieza):
        self._piezas.discard(pieza)

    def _tic(self):
        vivas = [w for w in list(self._piezas) if w.isVisible()]
        if not vivas:
            self._t.stop()
            return
        for w in vivas:
            try:
                w.latir()
            except RuntimeError:                                         # (ya no existe)
                self._piezas.discard(w)


RELOJ = _Reloj()


def _latido(periodo, fase=0.0):
    """0..1..0 suave con ese periodo (s); 1 quieto con «Reducir animaciones»."""
    if _quieto():
        return 1.0
    return 0.5 - 0.5 * math.cos(2 * math.pi * ((time.monotonic() / periodo + fase) % 1.0))


class _Latente:
    """Lo que late: se da de alta en el reloj al mostrarse y de baja al esconderse."""
    def showEvent(self, e):
        super().showEvent(e)
        RELOJ.alta(self)

    def hideEvent(self, e):
        RELOJ.baja(self)
        super().hideEvent(e)

    def latir(self):
        self.update()


# ======================================================================================================================== la franja del audio
class BotonLuz(Boton):
    """«Obtener» / «Crea tu estilo»: píldora con degradado del acento al turquesa, halo, brillo arriba, icono y texto en negrita."""
    def __init__(self, texto, comando, icono, alto=50, ancho=None, tam=16, padre=None):
        super().__init__(texto, comando, tipo='primario', alto=alto, ancho=ancho, tam=tam, negrita=True, padre=padre)
        self._nombre_icono = icono
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def sizeHint(self):
        return QSize(max(self.minimumWidth(), int(QFontMetricsF(self.font()).horizontalAdvance(self.text())) + 88), self.height() or 50)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        acento = _real(QColor(ui.ACCENT))
        activo = self.isEnabled()
        c1 = acento if activo else QColorReal(70, 84, 104)
        c2 = _mezcla(acento, QColorReal('#22D3EE'), 0.6) if activo else QColorReal(60, 72, 92)
        radio = r.height() / 2.4
        if activo:
            _halo(p, r, radio, acento, ((10, 14 if self.underMouse() else 8), (6, 22), (3, 40)))
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0.0, c1)
        g.setColorAt(1.0, c2)
        p.setPen(QPen(QColorReal(255, 255, 255, 70 if activo else 30), 1))
        p.setBrush(g)
        p.drawRoundedRect(r, radio, radio)
        brillo = QLinearGradient(r.topLeft(), QPointF(r.left(), r.center().y()))
        brillo.setColorAt(0.0, QColorReal(255, 255, 255, 60 if not self.isDown() else 20))
        brillo.setColorAt(1.0, QColorReal(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brillo)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -r.height() / 2), radio, radio)
        p.setFont(self.font())
        fm = QFontMetricsF(p.font())
        w_txt = fm.horizontalAdvance(self.text())
        lado = 20
        x = r.center().x() - (w_txt + lado + 12) / 2
        ic = _icono(self._nombre_icono, '#FFFFFF')
        if ic is not None:
            ic.paint(p, QRectF(x, r.center().y() - lado / 2, lado, lado).toRect())
        p.setPen(QColorReal(255, 255, 255, 255 if activo else 150))
        p.drawText(QRectF(x + lado + 12, r.top(), w_txt + 4, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.text())
        p.end()


class PildoraMotor(QAbstractButton):
    """Una opción de «Transcribir con»: icono, nombre y ⌄; la elegida con borde de acento, fondo teñido y halo."""
    def __init__(self, texto, icono, padre=None):
        super().__init__(padre)
        self.setText(texto)
        self._ic = icono
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(50)

    def sizeHint(self):
        return QSize(int(QFontMetricsF(fuente(14, peso='medio')).horizontalAdvance(self.text())) + 92, 50)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        acento = _real(QColor(ui.ACCENT))
        sel = self.isChecked()
        radio = 14
        if sel:
            _halo(p, r, radio, acento, ((8, 10), (4, 22)))
        p.setPen(QPen(acento if sel else QColorReal(255, 255, 255, 40 if self.underMouse() else 26), 1.6 if sel else 1.0))
        p.setBrush(_rgba(acento, 30) if sel else QColorReal(255, 255, 255, 8))
        p.drawRoundedRect(r, radio, radio)
        ic = _icono(self._ic, acento.name() if sel else '#C9D6EC')
        x = r.left() + 16
        if ic is not None:
            ic.paint(p, QRectF(x, r.center().y() - 10, 20, 20).toRect())
        p.setFont(fuente(14, peso='medio' if sel else None))
        p.setPen(QColorReal('#FFFFFF') if sel else QColorReal('#C9D6EC'))
        p.drawText(QRectF(x + 30, r.top(), r.width() - 76, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.text())
        flecha = _icono('caret-down', '#C9D6EC')
        if flecha is not None:
            flecha.paint(p, QRectF(r.right() - 28, r.center().y() - 7, 14, 14).toRect())
        p.end()


class Separador(QWidget):
    """Una raya vertical fina entre grupos de la franja."""
    def __init__(self, alto=44, padre=None):
        super().__init__(padre)
        self.setFixedSize(QSize(9, alto))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setPen(QPen(QColorReal(255, 255, 255, 26), 1))
        x = self.width() / 2.0
        p.drawLine(QPointF(x, 2), QPointF(x, self.height() - 2))
        p.end()


# ======================================================================================================================== el bloque del tema
class FondoTema(_Latente, QWidget):
    """El panel del tema de la referencia: detrás del nombre (`ancla`) un halo lila y, a cada lado, dos arcos finos EN ESPEJO que salen de
    encima de los botones (BotonEstado hijos) y suben hasta el nombre, con un punto lila que se desliza por el de dentro (los dos puntos a la
    vez y en espejo). Todo se mide en cada pintada: encaja con cualquier ancho de ventana y de botones."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self.ancla = None
        self._puntos = []

    # -- geometría
    def _titulo(self):
        """El rectángulo del TEXTO del nombre (el widget del título ocupa toda la fila: con su ancho, el halo se hacía una franja)."""
        if self.ancla is not None and self.ancla.isVisible():
            g = QRectF(self.ancla.geometry())
            ancho = float(getattr(self.ancla, '_ancho', 0.0) or g.width() * 0.3)
            return QRectF(g.center().x() - ancho / 2, g.top(), ancho, g.height())
        return QRectF(self.width() * 0.4, 0, self.width() * 0.2, 100)

    def _botones(self):
        """El rectángulo que ocupan los botones grandes a la vista (en coordenadas de este panel), o None."""
        r = None
        for b in self.findChildren(BotonEstado):
            if not b.isVisible():
                continue
            g = QRectF(b.mapTo(self, QPoint(0, 0)), QSizeF(b.size())).adjusted(BotonEstado.MARGEN, BotonEstado.MARGEN,
                                                                               -BotonEstado.MARGEN, -BotonEstado.MARGEN)
            r = g if r is None else r.united(g)
        return r

    def _arcos(self):
        """[(caja de la elipse, ángulo de abajo, ángulo de arriba)] del lado izquierdo (grados de pantalla: 0 = derecha, + hacia abajo); el
        derecho es su espejo. Centro común: el del nombre en x; en y, un poco por debajo del borde de arriba de los botones."""
        t = self._titulo()
        b = self._botones() or QRectF(t.center().x() - t.width(), t.bottom() + 20, 2 * t.width(), 70)
        cx = t.center().x()
        cy = b.top() + b.height() * 0.55
        mitad = max(60.0, b.width() / 2.0)
        out = []
        for k in (0.62, 0.84):                                           # el de dentro y el de fuera, en fracción de la media fila de botones
            r = mitad * k
            ry = r * 0.8
            baja = -math.degrees(math.asin(max(-1.0, min(1.0, (b.top() - 10 - cy) / ry))))    # justo encima de los botones
            sube = -math.degrees(math.asin(max(-1.0, min(1.0, (t.top() + t.height() * 0.15 - cy) / ry))))  # hasta la altura del nombre
            out.append((QRectF(cx - r, cy - ry, 2 * r, 2 * ry), 180.0 + baja, 180.0 + sube))
        return out, cx

    def _punto(self, caja, a0, a1, u):
        a = math.radians(a0 + (a1 - a0) * u)
        c = caja.center()
        return QPointF(c.x() + caja.width() / 2 * math.cos(a), c.y() + caja.height() / 2 * math.sin(a))

    def _calcular_puntos(self):
        arcos, cx = self._arcos()
        caja, a0, a1 = arcos[0]
        u = 0.32 + 0.12 * math.sin(time.monotonic() * 0.45) if not _quieto() else 0.32
        q = self._punto(caja, a0, a1, u)
        return [q, QPointF(2 * cx - q.x(), q.y())]                       # el derecho, el espejo del izquierdo

    def latir(self):                                                     # (solo los puntos: el resto es quieto)
        viejos = list(self._puntos)
        self._puntos = self._calcular_puntos()
        for q in viejos + self._puntos:
            self.update(QRect(int(q.x()) - 14, int(q.y()) - 14, 28, 28))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._titulo()
        ct = t.center()
        rx = max(120.0, t.width() * 0.75)
        ry = max(20.0, min(t.height() * 0.95, ct.y() - 2.0))              # el halo lila detrás del nombre (sin tocar el borde de arriba)
        halo = QRadialGradient(QPointF(0, 0), ry)
        halo.setColorAt(0.0, QColorReal(100, 90, 255, 56))
        halo.setColorAt(0.5, QColorReal(70, 90, 230, 22))
        halo.setColorAt(1.0, QColorReal(40, 60, 160, 0))
        p.save()
        p.translate(ct)
        p.scale(rx / ry, 1.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(0, 0), ry, ry)
        p.restore()
        arcos, cx = self._arcos()
        for (caja, a0, a1), alfa in zip(arcos, (120, 70)):              # cada arco en tramos: se apaga en sus dos puntas
            n = 28
            for i in range(n):
                u0, u1 = i / n, (i + 1) / n
                fuerza = math.sin(math.pi * (u0 + u1) / 2)
                p.setPen(QPen(QColorReal(120, 104, 255, int(alfa * fuerza)), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                for espejo in (False, True):
                    q0, q1 = self._punto(caja, a0, a1, u0), self._punto(caja, a0, a1, u1)
                    if espejo:
                        q0, q1 = QPointF(2 * cx - q0.x(), q0.y()), QPointF(2 * cx - q1.x(), q1.y())
                    p.drawLine(q0, q1)
        self._puntos = self._calcular_puntos()
        for q in self._puntos:                                           # los puntos lila, con su brillo
            rg = QRadialGradient(q, 11)
            rg.setColorAt(0.0, QColorReal(150, 120, 255, 120))
            rg.setColorAt(1.0, QColorReal(150, 120, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(rg)
            p.drawEllipse(q, 11, 11)
            p.setBrush(QColorReal(150, 120, 255))
            p.drawEllipse(q, 3.6, 3.6)
        p.end()


class BotonEstado(_Latente, QAbstractButton):
    """Los botones grandes del tema (la referencia): 'uso' verde con su ✓ y 'pro' dorado con su corona. `activo` = encendido: relleno
    degradado oscuro del color, borde brillante, halo que respira y un destello; si no, la misma tarjeta apagada. Deshabilitado y activo
    («En uso») se ve igual que activo: es una confirmación. v5.32 (el usuario: «un poco más pequeños, todo proporcional y simétrico»):
    `emparejar(a, b)` los deja del MISMO ancho, respiran a la vez y el destello cruza los dos seguidos, de izquierda a derecha."""
    MARGEN = 10                                                          # (alrededor, para el halo)
    TAM_TEXTO = 19                                                       # (el usuario: «un poco más pequeño» → ~15 % menos)
    HUECO = 18                                                           # (entre el círculo y el texto)

    def __init__(self, tipo, texto, comando=None, activo=False, alto=68, ancho=290, padre=None):
        super().__init__(padre)
        self.tipo = tipo
        self._activo = bool(activo)
        self._ancho_min = ancho
        self._pareja = None
        self.setText(texto)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(alto)
        if comando is not None:
            self.clicked.connect(lambda _c=False: comando())

    @staticmethod
    def emparejar(a, b):
        """Los dos botones del tema, del mismo ancho (el que necesite el más largo); b None = `a` solo."""
        a._pareja = weakref.ref(b) if b is not None else None
        if b is not None:
            b._pareja = weakref.ref(a)
        a._medir()

    def _otro(self):
        try:
            o = self._pareja() if self._pareja is not None else None
            if o is not None:
                o.isVisible()                                            # (RuntimeError si ya se borró)
            return o
        except RuntimeError:
            return None

    def poner(self, activo, texto=None):
        self._activo = bool(activo)
        if texto is not None:
            self.setText(texto)
        self.update()

    def setText(self, texto):
        super().setText(texto)
        self._medir()

    def _necesario(self):
        alto = self.height() - 2 * self.MARGEN if self.height() > 2 * self.MARGEN else 60
        d = self._diametro(alto)
        return QFontMetricsF(fuente(self.TAM_TEXTO, peso='negrita')).horizontalAdvance(self.text()) + d + self.HUECO + 2 * 29 + 2 * self.MARGEN

    def _medir(self):
        """Ancho para que quepa el texto con su círculo y aire a los lados; emparejados, los dos el del más largo."""
        otro = self._otro() if hasattr(self, '_pareja') else None
        w = int(max(self._ancho_min, self._necesario(), otro._necesario() if otro is not None else 0))
        for b in ([self, otro] if otro is not None else [self]):
            b.setFixedWidth(w)
            b.updateGeometry()

    def sizeHint(self):
        return QSize(self.width(), self.height())

    @staticmethod
    def _diametro(alto_dentro):
        return min(alto_dentro * 0.66, 39.0)

    def latir(self):
        if self._activo:
            self.update()

    def _tramo(self):
        """(izquierda, derecha) de la pareja en coordenadas de la ventana: el destello la cruza entera."""
        izq = self.mapTo(self.window(), QPoint(0, 0)).x()
        der = izq + self.width()
        otro = self._otro()
        if otro is not None and otro.isVisible():
            oi = otro.mapTo(self.window(), QPoint(0, 0)).x()
            izq, der = min(izq, oi), max(der, oi + otro.width())
        return izq, der

    def _colores(self):
        if self.tipo == 'pro':
            return {'borde': QColorReal(255, 201, 60), 'halo': QColorReal(255, 186, 40), 'izq': QColorReal(34, 25, 8),
                    'medio': QColorReal(44, 32, 10), 'der': QColorReal(112, 80, 18), 'aro': QColorReal(214, 160, 48),
                    'circulo': QColorReal(58, 41, 11), 'icono': '#FFCB45', 'texto': QColorReal(253, 236, 190)}
        a = _real(QColor(ui.ACCENT))
        borde = _mezcla(a, QColorReal(120, 255, 200), 0.5)
        return {'borde': borde, 'halo': a, 'izq': _oscuro(a, 0.42), 'medio': _oscuro(a, 0.26), 'der': _oscuro(a, 0.4),
                'aro': _mezcla(a, QColorReal(255, 255, 255), 0.3), 'circulo': a, 'icono': '#FFFFFF', 'texto': QColorReal(255, 255, 255)}

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self.MARGEN
        r = QRectF(self.rect()).adjusted(m, m, -m, -m)
        col = self._colores()
        on = self._activo
        radio = r.height() * 0.3
        caja = QPainterPath()
        caja.addRoundedRect(r, radio, radio)
        if on:
            k = 0.7 + 0.3 * _latido(3.6) + (0.25 if self.underMouse() else 0.0)       # (los dos respiran a la vez)
            _halo(p, r, radio, col['halo'], ((18, 9), (11, 18), (6, 34), (3, 70)), k)
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0.0, col['izq'])
            g.setColorAt(0.55, col['medio'])
            g.setColorAt(1.0, col['der'])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawPath(caja)
            p.save()
            p.setClipPath(caja)
            ola = QPainterPath()                                         # la curva de luz de la referencia (abajo a la derecha)
            ola.moveTo(r.left() + r.width() * 0.35, r.bottom())
            ola.cubicTo(r.left() + r.width() * 0.6, r.bottom() - r.height() * 0.15, r.left() + r.width() * 0.8, r.top() + r.height() * 0.55,
                        r.right(), r.top() + r.height() * 0.25)
            ola.lineTo(r.right(), r.bottom())
            ola.closeSubpath()
            p.setBrush(QColorReal(255, 255, 255, 12))
            p.drawPath(ola)
            arriba = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + r.height() * 0.5))
            arriba.setColorAt(0.0, QColorReal(255, 255, 255, 26))
            arriba.setColorAt(1.0, QColorReal(255, 255, 255, 0))
            p.setBrush(arriba)
            p.drawRect(r)
            if not _quieto():                                            # el destello: cruza la PAREJA seguida cada ~5 s
                u = (time.monotonic() / 5.2) % 1.0 / 0.32
                if u < 1.0:
                    izq, der = self._tramo()
                    yo = self.mapTo(self.window(), QPoint(0, 0)).x()
                    x = (izq - 120 + (der - izq + 240) * u) - yo
                    d = QLinearGradient(QPointF(x - 50, r.top()), QPointF(x + 50, r.bottom()))
                    d.setColorAt(0.0, QColorReal(255, 255, 255, 0))
                    d.setColorAt(0.5, QColorReal(255, 255, 255, 34))
                    d.setColorAt(1.0, QColorReal(255, 255, 255, 0))
                    p.setBrush(d)
                    p.drawRect(r)
            p.restore()
            p.setPen(QPen(col['borde'], 2.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(caja)
        else:
            p.setPen(QPen(_rgba(col['borde'], 130 if self.underMouse() else 85), 1.4))
            p.setBrush(QColorReal(255, 255, 255, 12 if self.underMouse() else 7))
            p.drawPath(caja)
        p.setFont(fuente(self.TAM_TEXTO, peso='negrita'))
        fm = QFontMetricsF(p.font())
        w_txt = fm.horizontalAdvance(self.text())
        d = self._diametro(r.height())                                   # el círculo del icono
        x = r.center().x() - (d + self.HUECO + w_txt) / 2
        c = QPointF(x + d / 2, r.center().y())
        if on:
            rg = QRadialGradient(QPointF(c.x() - d * 0.15, c.y() - d * 0.2), d * 0.7)
            rg.setColorAt(0.0, _mezcla(col['circulo'], QColorReal(255, 255, 255), 0.18))
            rg.setColorAt(1.0, _oscuro(col['circulo'], 0.82) if self.tipo == 'uso' else col['circulo'])
            p.setPen(QPen(col['aro'], 2.4))
            p.setBrush(rg)
        else:
            p.setPen(QPen(_rgba(col['borde'], 110), 1.8))
            p.setBrush(_rgba(col['borde'], 22))
        p.drawEllipse(c, d / 2, d / 2)
        ic = _icono('crown-simple-fill' if self.tipo == 'pro' else 'check-bold', col['icono'] if on else _rgba(col['borde'], 200).name())
        if ic is not None:
            lado = d * 0.5
            ic.paint(p, QRectF(c.x() - lado / 2, c.y() - lado / 2, lado, lado).toRect())
        if on and self.tipo == 'pro':
            t = QLinearGradient(QPointF(0, r.top() + 14), QPointF(0, r.bottom() - 14))
            t.setColorAt(0.0, QColorReal(255, 246, 214))
            t.setColorAt(1.0, QColorReal(246, 214, 140))
            p.setPen(QPen(t, 1))
        else:
            p.setPen(col['texto'] if on else QColorReal(214, 224, 240))
        p.drawText(QRectF(x + d + self.HUECO, r.top(), w_txt + 8, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.text())
        p.end()


# ======================================================================================================================== v5.62: el tema en una barra
# El usuario eligió la propuesta C («Tarjeta más grande»): el nombre grande, los dos botones grandes y su halo con arcos (TituloGo, BotonEstado,
# FondoTema) ocupaban ~170 px debajo del slider. Ahora van en UNA barra de cristal compacta, con unos puntos que dicen en qué tarjeta va. El
# slider gana ese alto (la tarjeta crece donde manda el alto, como en su monitor de 2293×960).
class BarraTema(QWidget):
    """La barra de cristal: [nombre del tema] [En uso / Usar este tema] | [Edición PRO y las acciones de la tarjeta]. `poner(usar, acciones)`
    mete los botones que maneja la página; `nombre(texto)` cambia el nombre; la raya del medio solo se ve si hay algo a la derecha."""
    ALTO = 56

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFixedHeight(self.ALTO)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._capa = QHBoxLayout(self)
        self._capa.setContentsMargins(22, 8, 8, 8)
        self._capa.setSpacing(16)
        self._nombre = NombreTema()
        self._capa.addWidget(self._nombre)
        self._sep = Separador(alto=26)
        self._derecha = None

    def poner(self, usar, acciones):
        self._capa.addWidget(usar)
        self._capa.addWidget(self._sep)
        self._capa.addWidget(acciones)
        self._derecha = acciones

    def nombre(self, texto):
        self._nombre.poner(texto)

    def ajustar(self):
        """Tras cambiar los botones: la raya solo con algo a la derecha, y el ancho justo."""
        capa = self._derecha.layout() if self._derecha is not None else None
        hay = bool(capa is not None and capa.count() > 0)
        self._sep.setVisible(hay)
        if self._derecha is not None:
            self._derecha.setVisible(hay)                                     # (vacío seguía ocupando su hueco en la capa)
        self.adjustSize()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2.0
        g = QLinearGradient(0, 0, 0, self.height())
        for pos, hexa in ((0.0, '#142236'), (1.0, '#09111F')):            # (QColor del tema: neutros con Negro profundo)
            c = QColor(hexa)
            c.setAlpha(235)
            g.setColorAt(pos, c)
        p.setPen(QPen(QColorReal(255, 255, 255, 23), 1.0))
        p.setBrush(g)
        p.drawRoundedRect(r, rad, rad)
        p.setPen(QPen(QColorReal(255, 255, 255, 18), 1.0))                    # el filo de arriba del cristal
        p.drawLine(QPointF(rad, 1.5), QPointF(self.width() - rad, 1.5))
        p.end()


class NombreTema(QWidget):
    """El nombre del tema en la barra: ExtraBold 24 con el degradado del título de antes (blanco → celeste → lila)."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self._texto = ''
        self._f = fuente(24, peso='extra')
        self.setFixedHeight(40)

    def poner(self, texto):
        self._texto = str(texto or '')
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(int(math.ceil(QFontMetricsF(self._f).horizontalAdvance(self._texto))) + 2, 40)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._f)
        g = QLinearGradient(0, 0, max(1, self.width()), 0)
        g.setColorAt(0.0, QColorReal(255, 255, 255))
        g.setColorAt(0.55, QColorReal(191, 227, 255))
        g.setColorAt(1.0, QColorReal(201, 181, 255))
        p.setPen(QPen(g, 1))
        p.drawText(QRectF(self.rect()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._texto)
        p.end()


class BotonCompacto(QAbstractButton):
    """Los botones de la barra. tipo 'uso': activo = «✓ En uso» (texto verde, sin relleno: es una confirmación), si no, la píldora verde
    rellena («Usar este tema», «Crear mi estilo»); tipo 'pro': la píldora dorada («Edición PRO activada»; apagada, «Activar edición PRO» con
    el borde tenue). Misma API que BotonEstado: poner(activo, texto, icono)."""

    def __init__(self, tipo, texto, comando=None, activo=False, padre=None):
        super().__init__(padre)
        self.tipo = tipo
        self._activo = bool(activo)
        self._icono_n = 'crown' if tipo == 'pro' else 'check'
        self._h = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setText(texto)
        if comando is not None:
            self.clicked.connect(lambda _c=False: comando())
        self._cursor()

    def poner(self, activo, texto=None, icono=None):
        self._activo = bool(activo)
        if texto is not None:
            self.setText(texto)
        if icono is not None:
            self._icono_n = icono
        self._cursor()
        self.updateGeometry()
        self.update()

    def setEnabled(self, si):
        super().setEnabled(si)
        self._cursor()

    def _cursor(self):
        quieto = self.tipo == 'uso' and self._activo
        self.setCursor(Qt.CursorShape.ArrowCursor if quieto or not self.isEnabled() else Qt.CursorShape.PointingHandCursor)

    def _fuente(self):
        return fuente(13, peso='medio') if (self.tipo == 'uso' and self._activo) else fuente(13, peso='negrita')

    def sizeHint(self):
        w = QFontMetricsF(self._fuente()).horizontalAdvance(self.text())
        if self.tipo == 'uso' and self._activo:
            return QSize(int(math.ceil(20 + 7 + w + 4)), 36)
        return QSize(int(math.ceil((12 if self.tipo == 'pro' else 14) + 16 + 8 + w + 16)), 40 if self.tipo == 'pro' else 36)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, e):
        self._h = 1.0
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._h = 0.0
        self.update()
        super().leaveEvent(e)

    def _glifo(self, color, lado):
        ic = _icono(self._icono_n, color)
        return ic.pixmap(QSize(lado, lado), self.devicePixelRatioF()) if ic is not None else None

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        alin = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.setFont(self._fuente())
        w_txt = QFontMetricsF(self._fuente()).horizontalAdvance(self.text())
        verde = _real(ui.ACCENT_CLARO)
        if self.tipo == 'uso' and self._activo:                              # «✓ En uso»
            c = QColorReal(verde)
            c.setAlpha(41)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(10.0, r.center().y()), 10.0, 10.0)
            pm = self._glifo(verde.name(), 12)
            if pm is not None:
                p.drawPixmap(QPointF(4.0, r.center().y() - 6.0), pm)
            p.setPen(verde)
            p.drawText(QRectF(27.0, 0, w_txt + 4, self.height()), alin, self.text())
            p.end()
            return
        rad = r.height() / 2.0
        if self.tipo == 'pro':
            oro = _real(ui.AMBAR)
            fondo = QColorReal(oro)
            fondo.setAlpha(int((26 if self._activo else 0) + 20 * self._h))
            borde = QColorReal(oro)
            borde.setAlpha(140 if self._activo else 77 + int(50 * self._h))
            p.setPen(QPen(borde, 1.0))
            p.setBrush(fondo)
            p.drawRoundedRect(r, rad, rad)
            tinta = QColorReal(oro)
            if not self._activo:
                tinta.setAlpha(215)
            pm = self._glifo(oro.name(), 16)
            if pm is not None:
                p.drawPixmap(QPointF(12.0, r.center().y() - 8.0), pm)
            p.setPen(tinta)
            p.drawText(QRectF(36.0, 0, w_txt + 4, self.height()), alin, self.text())
            p.end()
            return
        g = QLinearGradient(r.topLeft(), r.topRight())                       # «Usar este tema» / «Crear mi estilo»
        g.setColorAt(0.0, _mezcla(verde, QColorReal(255, 255, 255), 0.12 * self._h))
        g.setColorAt(1.0, _mezcla(_real(ui.ACCENT), QColorReal(255, 255, 255), 0.12 * self._h))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, rad, rad)
        oscuro = QColorReal(11, 20, 36)
        pm = self._glifo(oscuro.name(), 14)
        if pm is not None:
            p.drawPixmap(QPointF(14.0, r.center().y() - 7.0), pm)
        p.setPen(oscuro)
        p.drawText(QRectF(36.0, 0, w_txt + 4, self.height()), alin, self.text())
        p.end()


class PuntosSlider(QWidget):
    """Los puntos de debajo de la barra: uno por tarjeta del slider; el de la que está al centro se alarga en verde y lo sigue mientras se
    desliza (lee CarruselPacks._pos al repintarse el slider). El de «Crea tu estilo», verde tenue. Un clic en un punto lleva a esa tarjeta."""
    LADO, HUECO, LARGO = 6.0, 7.0, 12.0

    def __init__(self, carrusel, padre=None):
        super().__init__(padre)
        self._car = carrusel
        self._visto = None
        self._xs = []
        self.setFixedHeight(14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        carrusel.installEventFilter(self)

    def _n(self):
        return len(getattr(self._car, '_cartas', None) or [])

    def sizeHint(self):
        n = self._n()
        return QSize(int(n * self.LADO + self.LARGO + max(0, n - 1) * self.HUECO) + 2, 14)

    def eventFilter(self, obj, e):
        if obj is self._car and e.type() == QEvent.Type.Paint:
            ahora = (round(float(getattr(self._car, '_pos', 0.0)), 3), self._n())
            if ahora != self._visto:
                if self._visto is None or ahora[1] != self._visto[1]:
                    self.updateGeometry()
                self._visto = ahora
                self.update()
        return False

    def mousePressEvent(self, e):
        x = e.position().x()
        if self._xs:
            k = min(range(len(self._xs)), key=lambda i: abs(self._xs[i] - x))
            self._car._ir_a(k)

    def paintEvent(self, _e):
        n = self._n()
        if not n:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pos = float(getattr(self._car, '_pos', 0.0))
        anchos = [self.LADO + self.LARGO * max(0.0, 1.0 - abs(pos - i)) for i in range(n)]
        x = (self.width() - (sum(anchos) + self.HUECO * (n - 1))) / 2.0
        y = (self.height() - self.LADO) / 2.0
        verde = _real(ui.ACCENT_CLARO)
        self._xs = []
        p.setPen(Qt.PenStyle.NoPen)
        for i, w in enumerate(anchos):
            q = max(0.0, 1.0 - abs(pos - i))
            carta = self._car._cartas[i]
            base = _mezcla(verde, QColorReal(9, 17, 31), 0.55) if getattr(carta, 'tipo', '') == 'anadir' else QColorReal(57, 64, 82)
            p.setBrush(_mezcla(base, verde, q))
            p.drawRoundedRect(QRectF(x, y, w, self.LADO), self.LADO / 2.0, self.LADO / 2.0)
            self._xs.append(x + w / 2.0)
            x += w + self.HUECO
        p.end()


# ======================================================================================================================== v5.63: el cielo de Proyecto
# (estrellas de cada capa: cuántas, px/s de deriva, radio, brillo) y constelaciones (puntos en fracción del ancho y del alto), como en Inicio
_CAPAS_CIELO = ((300, 2.0, 0.7, 0.55), (150, 4.0, 1.1, 0.8), (60, 7.0, 1.7, 1.0))
_CONSTELACIONES = (((0.08, 0.18), (0.13, 0.12), (0.19, 0.16), (0.24, 0.10), (0.27, 0.19)), ((0.70, 0.14), (0.75, 0.22), (0.81, 0.18), (0.86, 0.25)),
                   ((0.06, 0.74), (0.11, 0.82), (0.17, 0.78), (0.15, 0.90)), ((0.88, 0.64), (0.92, 0.72), (0.96, 0.66)))
# los colores del cielo por tema: «noche» (el azul de siempre) y «negro» (v5.63, el usuario eligió el tono A, negro puro, y negro + blanco
# para todo CineCaptions): fondo (centro, medio, borde), nebulosas (r, g, b, alfa), viñeta, estrellas, rayas y nodos
_PALETAS_CIELO = {
    'noche': {'fondo': ('#121B31', '#0B1222', '#060A14'), 'nebulosas': ((139, 92, 246, 20), (34, 181, 115, 18)), 'vineta': (3, 6, 12),
              'estrella': (215, 228, 255), 'raya': (170, 195, 255, 51), 'nodo': (210, 225, 255)},
    'negro': {'fondo': ('#131313', '#0A0A0A', '#040404'), 'nebulosas': ((255, 255, 255, 7), (255, 255, 255, 5)), 'vineta': (0, 0, 0),
              'estrella': (255, 255, 255), 'raya': (255, 255, 255, 38), 'nodo': (255, 255, 255)},
}


def _paleta_cielo():
    try:
        import tema
        return _PALETAS_CIELO['negro' if tema.leer()['tema'] in ('negro', 'grafito') else 'noche']
    except Exception:
        return _PALETAS_CIELO['noche']


class TarjetaCielo(ui.Tarjeta):
    """v5.63 (el usuario eligió el fondo C, «Constelaciones», entre tres maquetas animadas): la tarjeta de Proyecto con un cielo como el de
    Inicio: degradado de espacio con dos nebulosas tenues (lila y verde), tres capas de estrellas que derivan a distinta velocidad
    (paralaje) y titilan, cuatro constelaciones con su raya fina y, cada 11 s, una estrella fugaz.
    Rendimiento (medido sin pantalla a 2293×960 al 1,5: repintar la tarjeta ENTERA, con el slider, el móvil y las barras encima, cuesta
    ~32 ms; antes la tarjeta de vidrio se repintaba así 2 veces por segundo para refrescar la aurora, ~64 ms/s): lo fijo (degradado,
    nebulosas, viñeta, esquinas) es UNA imagen por tamaño; las estrellas se componen en un cuadro (QPixmap) FPS veces por segundo (~5 ms),
    por lotes (drawPoints por capa, grosor y brillo; el halo de las constelaciones es un sprite), y en cada tic se repinta solo lo que NO se
    repinta ya solo (`zonas_vivas`: el slider y el móvil van a 30/s y, al repintarse, copian su trozo del cuadro): ~10 ms → ~74 ms/s. La
    fugaz NO va en el cuadro: paintEvent la pinta encima y, mientras cruza, solo su rectángulo se repinta a FPS_FUGAZ. Fuera de
    Tarjeta._vivas (sin el refresco de la aurora). Quieto con «Reducir animaciones»; parado si no se ve o la ventana está minimizada."""
    FPS, FPS_FUGAZ = 5, 24
    RADIO = 18.0
    PERIODO_FUGAZ, DURA_FUGAZ = 11.0, 1.4
    BRILLOS = 8                                            # (niveles de brillo para los lotes: el titilar va por niveles)

    def __init__(self, sin_marco=False, **kw):
        super().__init__(**kw)
        ui.Tarjeta._vivas.discard(self)
        # v5.64 (el usuario: «que el fondo tipo astral abarque toda la página, así como la página de Inicio»): sin_marco = el cielo de borde a
        # borde de la ventana (sin esquinas redondeadas, borde ni filo de luz); la página le quita sus márgenes y la tarjeta los lleva dentro
        self._sin_marco = sin_marco
        self._radio = 0.0 if sin_marco else self.RADIO
        self._pal = _paleta_cielo()                         # (v5.63: negro puro con el tema Negro profundo; el tema cambia al reiniciar)
        azar = random.Random(7)
        # por capa: [(x, y, fase, grueso)] en dos grosores (para dibujarlas por lotes)
        self._estrellas = [[(azar.random(), azar.random(), azar.random() * 6.283, 0 if azar.random() < 0.5 else 1) for _ in range(n)]
                           for n, _v, _tam, _a in _CAPAS_CIELO]
        self._fijo = None                                  # ((ancho, alto, dpr), QPixmap)
        self._cuadro = None
        self._nodo = None                                  # (dpr, QPixmap) el halo de un punto de constelación
        self.zonas_vivas = None                            # la página: [QRect] de lo que ya se repinta solo (coordenadas de esta tarjeta)
        self._t_cuadro = -1.0                              # cuándo se compuso el cuadro (s del reloj del cielo)
        self._caja_fugaz = None                            # el rectángulo de la fugaz en el tic anterior (para borrarla)
        self._t0 = time.perf_counter()
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)

    # -- reloj ------------------------------------------------------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self._cuadro = None
        if not self._quieto():
            self._reloj.start(int(1000 / self.FPS))

    def hideEvent(self, e):
        super().hideEvent(e)
        self._reloj.stop()

    @staticmethod
    def _quieto():
        try:
            import mograf_ui
            return bool(mograf_ui.quieto())
        except Exception:
            return False

    def _t(self):
        return 0.0 if self._quieto() else time.perf_counter() - self._t0

    def _tic(self):
        v = self.window()
        if not self.isVisible() or (v is not None and v.isMinimized()):
            return
        if self._quieto():
            self._reloj.stop()
            return
        t = self._t()
        if t - self._t_cuadro >= 1.0 / self.FPS - 0.02:
            self._t_cuadro = t
            self._componer(t)
            zona = QRegion(self.rect())
            try:
                for r in (self.zonas_vivas() if self.zonas_vivas is not None else []):
                    zona = zona.subtracted(QRegion(r))
            except Exception:
                zona = QRegion(self.rect())
            self.update(zona)
        f = self._fugaz(t)                                                 # la fugaz: solo su rectángulo (y el de antes, para borrarla)
        caja = self._caja(f) if f is not None else None
        for c in (self._caja_fugaz, caja):
            if c is not None:
                self.update(c)
        self._caja_fugaz = caja
        ms = int(1000 / (self.FPS_FUGAZ if f is not None or self._fugaz(t + 0.25) is not None else self.FPS))
        if self._reloj.interval() != ms:
            self._reloj.setInterval(ms)

    def _fugaz(self, t):
        """(q 0..1, semilla) de la estrella fugaz que cruza ahora, o None."""
        n = int(t // self.PERIODO_FUGAZ)
        q = (t - n * self.PERIODO_FUGAZ - 2.0) / self.DURA_FUGAZ
        return (q, n) if 0.0 < q < 1.0 else None

    def _puntas(self, f):
        """(cola, cabeza) de la fugaz f = (q, semilla)."""
        q, semilla = f
        azar = random.Random(semilla)
        w, h = self.width(), self.height()
        x0, y0 = w * (0.15 + 0.5 * azar.random()) + q * 520.0, h * (0.05 + 0.2 * azar.random()) + q * 190.0
        return QPointF(x0 - 180.0, y0 - 66.0), QPointF(x0, y0)

    def _caja(self, f):
        a, b = self._puntas(f)
        return QRectF(a, b).normalized().adjusted(-4, -4, 4, 4).toAlignedRect()

    def _pintar_fugaz(self, p, t):
        f = self._fugaz(t)
        if f is None:
            return
        a, b = self._puntas(f)
        lg = QLinearGradient(a, b)
        lg.setColorAt(0.0, QColorReal(255, 255, 255, 0))
        lg.setColorAt(1.0, QColorReal(255, 255, 255, int(204 * math.sin(f[0] * math.pi))))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipPath(self._camino(self.width(), self.height()))
        p.setPen(QPen(lg, 1.6))
        p.drawLine(a, b)

    # -- dibujo -----------------------------------------------------------------------------------------------------------------------------
    def _camino(self, w, h):
        c = QPainterPath()
        if self._sin_marco:
            c.addRect(QRectF(0.0, 0.0, w, h))
        else:
            c.addRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), self._radio, self._radio)
        return c

    def _fijo_pm(self, w, h, dpr):
        clave = (w, h, round(dpr, 2))
        if self._fijo is not None and self._fijo[0] == clave:
            return self._fijo[1]
        pm = QPixmap(int(math.ceil(w * dpr)), int(math.ceil(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipPath(self._camino(w, h))
        pal = self._pal
        g = QRadialGradient(QPointF(w * 0.5, h * 0.42), max(w, h) * 0.8)
        for pos, hexa in zip((0.0, 0.6, 1.0), pal['fondo']):
            g.setColorAt(pos, QColorReal(hexa))
        p.fillRect(QRectF(0, 0, w, h), g)
        for (fx, fy, radio), (r_, g_, b_, a) in zip(((0.18, 0.25, 620.0), (0.82, 0.70, 640.0)), pal['nebulosas']):
            n = QRadialGradient(QPointF(w * fx, h * fy), radio)
            n.setColorAt(0.0, QColorReal(r_, g_, b_, a))
            n.setColorAt(0.45, QColorReal(r_, g_, b_, int(a * 0.55)))
            n.setColorAt(1.0, QColorReal(r_, g_, b_, 0))
            p.fillRect(QRectF(0, 0, w, h), n)
        v = QRadialGradient(QPointF(w * 0.5, h * 0.45), max(w, h) * 0.75)
        v.setColorAt(min(w, h) * 0.35 / (max(w, h) * 0.75), QColorReal(*pal['vineta'], 0))
        v.setColorAt(1.0, QColorReal(*pal['vineta'], 115))
        p.fillRect(QRectF(0, 0, w, h), v)
        p.end()
        self._fijo = (clave, pm)
        return pm

    def _nodo_pm(self, dpr):
        """El halo de un punto de constelación (14×14), pintado una vez por dpr."""
        if self._nodo is None or abs(self._nodo[0] - dpr) > 0.01:
            pm = QPixmap(int(math.ceil(14 * dpr)), int(math.ceil(14 * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            halo = QRadialGradient(QPointF(7.0, 7.0), 7.0)
            nodo = self._pal['nodo']
            halo.setColorAt(0.0, QColorReal(*nodo, 230))
            halo.setColorAt(0.45, QColorReal(*nodo, 126))
            halo.setColorAt(1.0, QColorReal(*nodo, 0))
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(halo)
            q.drawEllipse(QPointF(7.0, 7.0), 7.0, 7.0)
            q.end()
            self._nodo = (dpr, pm)
        return self._nodo[1]

    def _componer(self, t):
        w, h, dpr = self.width(), self.height(), self.devicePixelRatioF()
        if w < 4 or h < 4:
            return
        fijo = self._fijo_pm(w, h, dpr)
        if self._cuadro is None or self._cuadro.size() != fijo.size() or abs(self._cuadro.devicePixelRatio() - dpr) > 0.01:
            self._cuadro = QPixmap(fijo.size())
            self._cuadro.setDevicePixelRatio(dpr)
            self._cuadro.fill(Qt.GlobalColor.transparent)                  # (sin esto el QPixmap no tiene alfa: esquinas negras)
        p = QPainter(self._cuadro)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)      # (pisa el cuadro entero: sin borrarlo antes)
        p.drawPixmap(0, 0, fijo)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipPath(self._camino(w, h))
        n = self.BRILLOS
        for k, ((_n, vel, tam, alfa), capa) in enumerate(zip(_CAPAS_CIELO, self._estrellas)):
            lotes = {}
            for fx, fy, fase, grueso in capa:
                nivel = int((0.5 + 0.5 * math.sin(t * (1.5 + k) + fase)) * (n - 1) + 0.5)
                lotes.setdefault((grueso, nivel), []).append(QPointF((fx * w - t * vel) % w, fy * h))
            for (grueso, nivel), puntos in lotes.items():
                a = alfa * (0.55 + 0.45 * (nivel / (n - 1) * 2.0 - 1.0))
                lapiz = QPen(QColorReal(*self._pal['estrella'], int(255 * a)), 2.0 * tam * (0.8 if grueso == 0 else 1.2))
                lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(lapiz)
                p.drawPoints(puntos)
        desplaza = (t * _CAPAS_CIELO[0][1]) % w                       # las constelaciones van con la capa lenta (y dan la vuelta)
        p.setPen(QPen(QColorReal(*self._pal['raya']), 1.0))
        nodo = self._nodo_pm(dpr)
        for copia in (0.0, w):
            for puntos in _CONSTELACIONES:
                ps = [QPointF(fx * w - desplaza + copia, fy * h) for fx, fy in puntos]
                for a_, b_ in zip(ps, ps[1:]):
                    p.drawLine(a_, b_)
                for c in ps:
                    p.drawPixmap(QPointF(c.x() - 7.0, c.y() - 7.0), nodo)
        p.setClipping(False)
        if not self._sin_marco:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColorReal(255, 255, 255, 18), 1.0))          # el borde de la tarjeta y su filo de luz arriba
            p.drawPath(self._camino(w, h))
            p.setPen(QPen(QColorReal(255, 255, 255, 26), 1.0))
            p.drawLine(QPointF(self._radio, 1.5), QPointF(w - self._radio, 1.5))
        p.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._cuadro = None

    def paintEvent(self, _e):
        if self._cuadro is None or self._fijo is None or self._fijo[0][:2] != (self.width(), self.height()):
            self._componer(self._t())
        if self._cuadro is None:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cuadro)                                  # (Qt recorta a lo que pidió repintar: barato)
        self._pintar_fugaz(p, self._t())
        p.end()


class CieloDePagina(TarjetaCielo):
    """v5.66 (el usuario, del Corrector: «un poco de fondo de interfaz siguiendo el patrón de la página de Inicio y Tema»): el mismo cielo de
    constelaciones como FONDO de una página entera, sin entrar en su layout: hijo de la página, detrás de todo y con su tamaño (lo sigue al
    redimensionar). `zonas_vivas` (la página): lo que ya se repinta solo encima, para no repintarlo en cada tic del cielo."""

    def __init__(self, pagina):
        super().__init__(sin_marco=True, margenes=(0, 0, 0, 0))
        self.setParent(pagina)
        self.setGeometry(pagina.rect())
        self.lower()
        pagina.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
            self.lower()
        return False
