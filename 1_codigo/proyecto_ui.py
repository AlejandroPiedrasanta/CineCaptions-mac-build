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
import time
import weakref

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QWidget

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
