# CineCaptions · By Cinema Productions
# 1_codigo/isla_ui.py — la «isla dinámica»: el menú de navegación flotante de arriba, los controles de la ventana y el borde.
"""
La isla reemplaza al menú lateral. Es UNA pieza que se pinta sola (sin un botón por cada icono):
  [ marca ]  Inicio · Proyecto · Creativo · Sonido   |  ● Resolve · ⚙ Ajustes · 📌   — y a la derecha, aparte, − ▢ ✕.
Movimiento (todo con resortes de qt_kit, sin curvas fijas):
  * la pastilla de la pagina elegida DESLIZA de un icono al otro (k=340, c=26) y su etiqueta se abre/cierra con ella,
  * el icono bajo el mouse crece un 12 % y el pulsado se encoge a 0,9 (k=620, c=19),
  * el engranaje gira al pasar el mouse, la chincheta se inclina al fijarse, el punto de Resolve respira,
  * la isla ENTRA desde arriba al arrancar (resorte lento) y se vuelve a centrar sola cuando cambia de ancho.
Los controles de la ventana (minimizar, maximizar, cerrar) van DENTRO de la interfaz: la ventana no tiene barra de titulo del sistema;
arrastrar la isla o la franja de arriba mueve la ventana y los bordes la redimensionan (BordesVentana).
"""
import math
import time

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QCursor, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QComboBox,
                               QFrame, QLabel, QLineEdit, QScrollArea, QStackedWidget, QTextEdit, QApplication, QWidget)

import qt_kit as ui
from qt_kit import QColor, Resorte, fuente, motor_resortes
from i18n import tr

ALTO = 50                  # alto de la capsula
MARGEN = 16                # aire alrededor para la sombra
H_ITEM = 38
W_ICONO = 40

ICONOS = {
    'marca': 'ph.sparkle-bold',
    'inicio': 'ph.house-bold',
    'nuevo': 'ph.folder-open-bold',
    'editor': 'ph.text-aa-bold',
    'sfx': 'ph.speaker-high-bold',
    'efectos': 'ph.magic-wand-bold',
    'estado': 'ph.plugs-connected-bold',
    'ajustes': 'ph.gear-six-bold',
    'pin': 'ph.push-pin-bold',
    'min': 'ph.minus-bold',
    'max': 'ph.square-bold',
    'restaurar': 'ph.copy-simple-bold',
    'cerrar': 'ph.x-bold',
}
_CACHE_ICONOS = {}


def _pixmap(clave, color, lado):
    k = (clave, color, lado)
    pm = _CACHE_ICONOS.get(k)
    if pm is None:
        ic = ui.icono_linea(ICONOS.get(clave, clave), color)
        pm = ic.pixmap(QSize(lado, lado)) if ic is not None else QPixmap()
        _CACHE_ICONOS[k] = pm
    return pm


class _Item:
    __slots__ = ('clave', 'tipo', 'texto', 'hover', 'press', 'sel', 'rect', 'ancho_texto', 'extra')

    def __init__(self, clave, tipo, texto=''):
        self.clave = clave
        self.tipo = tipo                         # 'nav' | 'accion' | 'sep'
        self.texto = texto
        self.hover = Resorte(0.0, 420.0, 26.0)
        self.press = Resorte(0.0, 620.0, 19.0)
        self.sel = Resorte(0.0, 300.0, 24.0)      # 1 = pagina elegida (etiqueta abierta)
        self.rect = QRectF()
        self.ancho_texto = 0.0
        self.extra = Resorte(0.0, 160.0, 14.0)    # giro del engranaje / inclinacion de la chincheta


class IslaNav(QWidget):
    """La capsula de navegacion. Emite pagina(clave) y accion(clave, rect_global)."""
    pagina = Signal(str)
    accion = Signal(str, object)

    def __init__(self, padre, paginas):
        super().__init__(padre)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._fm = QFontMetricsF(fuente(13, peso='medio'))
        self._items = []
        for clave, nombre in paginas:
            it = _Item(clave, 'nav', tr(nombre))
            it.ancho_texto = self._fm.horizontalAdvance(it.texto)
            self._items.append(it)
        self._items.append(_Item('s1', 'sep'))
        self._items.append(_Item('estado', 'accion', tr('Resolve')))
        self._items.append(_Item('ajustes', 'accion', tr('Ajustes')))
        self._items.append(_Item('pin', 'accion', tr('Mantener encima de Resolve')))
        self._actual = None
        self._pin = False
        self._color_estado = QColor('#6B7C99')
        self._pulso = 0.0
        self._pastilla = [Resorte(0.0, 340.0, 26.0), Resorte(40.0, 340.0, 26.0)]       # x y ancho de la pastilla
        self._entrada = Resorte(0.0, 90.0, 13.0)          # la isla baja desde arriba al arrancar
        self._entrada.objetivo = 1.0
        self._t0 = time.perf_counter()
        self._hover = None
        self._presionado = None
        self._arrastre = None
        self._reloj = QTimer(self)
        self._reloj.setInterval(33)
        self._reloj.timeout.connect(self._respirar)
        self._reloj.start()
        self._medir()
        motor_resortes.pedir(self)

    # -- API ------------------------------------------------------------------------------------------------------------------
    def marcar(self, clave):
        """La pagina elegida: su pastilla se desliza y su etiqueta se abre; las demas se cierran."""
        self._actual = clave
        for it in self._items:
            if it.tipo == 'nav':
                it.sel.objetivo = 1.0 if it.clave == clave else 0.0
        motor_resortes.pedir(self)

    def poner_pin(self, si):
        self._pin = bool(si)
        for it in self._items:
            if it.clave == 'pin':
                it.extra.objetivo = 1.0 if si else 0.0
        motor_resortes.pedir(self)
        self.update()

    def poner_estado(self, color):
        self._color_estado = QColor(color)
        self.update()

    def rect_de(self, clave):
        """El rectangulo (coordenadas de la ventana) de un boton de la isla."""
        for it in self._items:
            if it.clave == clave:
                return QRectF(it.rect.translated(self.pos().x(), self.pos().y()))
        return QRectF()

    # -- geometria --------------------------------------------------------------------------------------------------------------
    def _medir(self):
        """Coloca cada item segun sus resortes y ajusta el ancho de la isla (que se recentra sola)."""
        x = 10.0
        y = MARGEN + (ALTO - H_ITEM) / 2.0
        for it in self._items:
            if it.tipo == 'sep':
                it.rect = QRectF(x + 4, MARGEN + 12, 1, ALTO - 24)
                x += 10
            elif it.tipo == 'marca':
                it.rect = QRectF(x, y, W_ICONO, H_ITEM)
                x += W_ICONO + 2
            else:
                abre = max(0.0, min(1.0, it.sel.x))
                ancho = W_ICONO + abre * (it.ancho_texto + 10)
                it.rect = QRectF(x, y, ancho, H_ITEM)
                x += ancho + 2
        total = int(x + 8)
        if total != self.width() or self.height() != ALTO + 2 * MARGEN:
            self.setFixedSize(total, ALTO + 2 * MARGEN)
        self.reposicionar()
        # la pastilla sigue a la pagina elegida
        for it in self._items:
            if it.tipo == 'nav' and it.clave == self._actual:
                self._pastilla[0].objetivo = it.rect.x()
                self._pastilla[1].objetivo = it.rect.width()
                if self._pastilla[1].x < 4:
                    self._pastilla[0].poner(it.rect.x())
                    self._pastilla[1].poner(it.rect.width())

    def reposicionar(self):
        p = self.parentWidget()
        if p is None:
            return
        e = max(0.0, self._entrada.x)
        x = int((p.width() - self.width()) / 2)
        y = int(-ALTO - MARGEN + (ALTO + MARGEN + 6) * e)       # entra desde arriba y se asienta con 6 px de margen
        if self.pos().x() != x or self.pos().y() != y:
            self.move(x, y)

    def paso_resorte(self, dt):
        sigue = self._entrada.paso(dt)
        for r in self._pastilla:
            sigue = r.paso(dt) or sigue
        for it in self._items:
            for r in (it.hover, it.press, it.sel, it.extra):
                sigue = r.paso(dt) or sigue
        self._medir()
        self.update()
        return sigue

    def _respirar(self):
        # el punto de Resolve respira (muy sutil); solo repinta si la isla se ve
        self._pulso = 0.5 + 0.5 * math.sin((time.perf_counter() - self._t0) * 2.2)
        if self.isVisible():
            self.update(QRectF(self._rect_item('estado')).adjusted(-6, -6, 6, 6).toRect())

    def _rect_item(self, clave):
        for it in self._items:
            if it.clave == clave:
                return it.rect
        return QRectF()

    def _item_en(self, pos):
        for it in self._items:
            if it.tipo in ('nav', 'accion') and it.rect.contains(pos):
                return it
        return None

    # -- pintura ----------------------------------------------------------------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        caps = QRectF(0.5 + 2, MARGEN + 0.5, self.width() - 5, ALTO - 1)
        radio = caps.height() / 2.0
        acento = QColor(ui.ACCENT_CLARO)
        # sombra en capas (de afuera hacia adentro)
        p.setPen(Qt.PenStyle.NoPen)
        for grosor, alfa in ((16, 10), (10, 18), (5, 28)):
            p.setBrush(QColor(0, 0, 0, alfa))
            p.drawRoundedRect(caps.adjusted(-grosor / 2, -grosor / 2 + 5, grosor / 2, grosor / 2 + 5), radio + grosor / 2, radio + grosor / 2)
        # el cristal
        g = QLinearGradient(caps.topLeft(), caps.bottomLeft())
        g.setColorAt(0.0, QColor('#141F36'))
        g.setColorAt(1.0, QColor('#0B1220'))
        camino = QPainterPath()
        camino.addRoundedRect(caps, radio, radio)
        p.fillPath(camino, g)
        p.save()
        p.setClipPath(camino)
        ng = QLinearGradient(caps.bottomLeft(), QPointF(caps.left(), caps.bottom() - caps.height() * 0.7))
        ng.setColorAt(0.0, QColor(acento.red(), acento.green(), acento.blue(), 70))
        ng.setColorAt(1.0, QColor(acento.red(), acento.green(), acento.blue(), 0))
        p.fillRect(caps, ng)
        lg = QLinearGradient(caps.topLeft(), caps.topRight())
        lg.setColorAt(0.0, QColor(255, 255, 255, 0))
        lg.setColorAt(0.5, QColor(255, 255, 255, 70))
        lg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(caps.left() + radio, caps.top(), caps.width() - 2 * radio, 1.2), lg)
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(camino)
        # la pastilla elegida (desliza entre iconos)
        if self._actual is not None and self._pastilla[1].x > 4:
            pa = QRectF(self._pastilla[0].x, MARGEN + (ALTO - H_ITEM) / 2.0, self._pastilla[1].x, H_ITEM)
            for grosor, alfa in ((10, 26), (5, 56)):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(acento.red(), acento.green(), acento.blue(), alfa))
                p.drawRoundedRect(pa.adjusted(-grosor / 2, -grosor / 2, grosor / 2, grosor / 2), H_ITEM / 2 + grosor / 2, H_ITEM / 2 + grosor / 2)
            pg = QLinearGradient(pa.topLeft(), pa.bottomLeft())
            pg.setColorAt(0.0, acento.lighter(125))
            pg.setColorAt(1.0, acento)
            p.setBrush(QBrush(pg))
            p.drawRoundedRect(pa, H_ITEM / 2, H_ITEM / 2)
        # los items
        for it in self._items:
            if it.tipo == 'sep':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 34))
                p.drawRect(it.rect)
                continue
            r = it.rect
            h = max(0.0, min(1.0, it.hover.x))
            esc = 1.0 + 0.12 * h - 0.10 * max(0.0, it.press.x)
            elegida = it.tipo == 'nav' and it.sel.x > 0.5
            if h > 0.02 and not elegida:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, int(26 * h)))
                p.drawRoundedRect(r, H_ITEM / 2, H_ITEM / 2)
            color = '#FFFFFF' if elegida else ('#E8EEF8' if h > 0.3 else '#9FB0CC')
            if it.clave == 'marca':
                color = ui.ACCENT_CLARO
            lado = 20
            cx, cy = r.left() + W_ICONO / 2.0, r.center().y()
            p.save()
            p.translate(cx, cy)
            if it.clave == 'ajustes':
                p.rotate(70.0 * max(0.0, min(1.0, it.hover.x)))           # el engranaje gira al pasar el mouse
            elif it.clave == 'pin':
                p.rotate(-30.0 * (1.0 - max(0.0, min(1.0, it.extra.x))))  # la chincheta se endereza al fijarse
            p.scale(esc, esc)
            if it.clave == 'estado':
                # el punto de Resolve: un halo que respira + el punto
                p.setPen(Qt.PenStyle.NoPen)
                c = QColor(self._color_estado)
                c.setAlpha(int(40 + 50 * self._pulso))
                p.setBrush(c)
                p.drawEllipse(QPointF(0, 0), 8 + 3 * self._pulso, 8 + 3 * self._pulso)
                p.setBrush(QColor(self._color_estado))
                p.drawEllipse(QPointF(0, 0), 4.6, 4.6)
            else:
                pm = _pixmap(it.clave, color if isinstance(color, str) else color, lado * 2)
                if not pm.isNull():
                    p.drawPixmap(QRectF(-lado / 2, -lado / 2, lado, lado), pm, QRectF(pm.rect()))
            p.restore()
            if it.tipo == 'nav' and it.sel.x > 0.02:
                a = max(0.0, min(1.0, (it.sel.x - 0.15) / 0.85))
                p.setPen(QColor(255, 255, 255, int(255 * a)))
                p.setFont(fuente(13, peso='medio'))
                caja = QRectF(r.left() + W_ICONO - 4, r.top(), r.width() - W_ICONO + 2, r.height())
                p.setClipRect(caja.adjusted(-2, 0, 0, 0))
                p.drawText(caja, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), it.texto)
                p.setClipping(False)
        p.end()

    # -- raton ------------------------------------------------------------------------------------------------------------------
    def mouseMoveEvent(self, e):
        it = self._item_en(e.position())
        if it is not self._hover:
            if self._hover is not None:
                self._hover.hover.objetivo = 0.0
            self._hover = it
            if it is not None:
                it.hover.objetivo = 1.0
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setToolTip(it.texto if it.tipo == 'accion' or it.sel.x < 0.5 else '')
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip('')
            motor_resortes.pedir(self)

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover.hover.objetivo = 0.0
            self._hover = None
            motor_resortes.pedir(self)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        it = self._item_en(e.position())
        if it is None:
            # el cristal vacio de la isla arrastra la ventana
            h = self.window().windowHandle() if self.window() is not None else None
            if h is not None:
                h.startSystemMove()
            return
        self._presionado = it
        it.press.objetivo = 1.0
        motor_resortes.pedir(self)

    def mouseReleaseEvent(self, e):
        it, self._presionado = self._presionado, None
        if it is None:
            return
        it.press.objetivo = 0.0
        motor_resortes.pedir(self)
        if e.button() == Qt.MouseButton.LeftButton and self._item_en(e.position()) is it:
            if it.tipo == 'nav':
                self.pagina.emit(it.clave)
            elif it.tipo == 'accion':
                self.accion.emit(it.clave, self.rect_de(it.clave))

    def mouseDoubleClickEvent(self, e):
        if self._item_en(e.position()) is None:
            self.accion.emit('maximizar', QRectF())


class ControlesVentana(QWidget):
    """Minimizar · maximizar/restaurar · cerrar, dentro de la interfaz, en una capsula pequeña de la esquina de arriba a la derecha."""
    accion = Signal(str)

    def __init__(self, padre):
        super().__init__(padre)
        self.setMouseTracking(True)
        self._claves = ['min', 'max', 'cerrar']
        self._hover = [Resorte(0.0, 420.0, 26.0) for _ in self._claves]
        self._press = [Resorte(0.0, 620.0, 19.0) for _ in self._claves]
        self._maximizada = False
        self._i_hover = -1
        self._i_press = -1
        self.setFixedSize(3 * 36 + 16 + 2 * MARGEN, 40 + 2 * MARGEN)
        self.reposicionar()

    def poner_maximizada(self, si):
        self._maximizada = bool(si)
        self.update()

    def reposicionar(self):
        p = self.parentWidget()
        if p is not None:
            self.move(p.width() - self.width() - 4, 0)

    def _rect(self, i):
        return QRectF(MARGEN + 8 + i * 36, MARGEN + 2, 36, 36)

    def _en(self, pos):
        for i in range(3):
            if self._rect(i).contains(pos):
                return i
        return -1

    def paso_resorte(self, dt):
        sigue = False
        for r in self._hover + self._press:
            sigue = r.paso(dt) or sigue
        self.update()
        return sigue

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        caps = QRectF(MARGEN + 0.5, MARGEN + 0.5, self.width() - 2 * MARGEN - 1, 39)
        radio = caps.height() / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        for grosor, alfa in ((12, 10), (6, 22)):
            p.setBrush(QColor(0, 0, 0, alfa))
            p.drawRoundedRect(caps.adjusted(-grosor / 2, -grosor / 2 + 4, grosor / 2, grosor / 2 + 4), radio + grosor / 2, radio + grosor / 2)
        g = QLinearGradient(caps.topLeft(), caps.bottomLeft())
        g.setColorAt(0.0, QColor('#141F36'))
        g.setColorAt(1.0, QColor('#0B1220'))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        p.drawRoundedRect(caps, radio, radio)
        for i, clave in enumerate(self._claves):
            r = self._rect(i)
            h = max(0.0, min(1.0, self._hover[i].x))
            esc = 1.0 + 0.10 * h - 0.10 * max(0.0, self._press[i].x)
            peligro = clave == 'cerrar'
            if h > 0.02:
                p.setPen(Qt.PenStyle.NoPen)
                if peligro:
                    for grosor, alfa in ((8, 30), (3, 70)):
                        p.setBrush(QColor(239, 68, 68, int(alfa * h)))
                        p.drawEllipse(r.adjusted(2 - grosor / 2, 2 - grosor / 2, -2 + grosor / 2, -2 + grosor / 2))
                    p.setBrush(QColor(239, 68, 68, int(230 * h)))
                else:
                    p.setBrush(QColor(255, 255, 255, int(30 * h)))
                p.drawEllipse(r.adjusted(2, 2, -2, -2))
            nombre = 'restaurar' if (clave == 'max' and self._maximizada) else clave
            color = '#FFFFFF' if (h > 0.3) else '#9FB0CC'
            pm = _pixmap(nombre, color, 32)
            if not pm.isNull():
                p.save()
                p.translate(r.center())
                p.scale(esc, esc)
                lado = 15
                p.drawPixmap(QRectF(-lado / 2, -lado / 2, lado, lado), pm, QRectF(pm.rect()))
                p.restore()
        p.end()

    def mouseMoveEvent(self, e):
        i = self._en(e.position())
        if i != self._i_hover:
            if self._i_hover >= 0:
                self._hover[self._i_hover].objetivo = 0.0
            self._i_hover = i
            if i >= 0:
                self._hover[i].objetivo = 1.0
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setToolTip({'min': tr('Minimizar'), 'max': tr('Restaurar') if self._maximizada else tr('Maximizar'), 'cerrar': tr('Cerrar')}[self._claves[i]])
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            motor_resortes.pedir(self)

    def leaveEvent(self, e):
        if self._i_hover >= 0:
            self._hover[self._i_hover].objetivo = 0.0
            self._i_hover = -1
            motor_resortes.pedir(self)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        i = self._en(e.position())
        if i < 0:
            h = self.window().windowHandle() if self.window() is not None else None
            if h is not None:
                h.startSystemMove()
            return
        self._i_press = i
        self._press[i].objetivo = 1.0
        motor_resortes.pedir(self)

    def mouseReleaseEvent(self, e):
        i, self._i_press = self._i_press, -1
        if i < 0:
            return
        self._press[i].objetivo = 0.0
        motor_resortes.pedir(self)
        if self._en(e.position()) == i:
            self.accion.emit(self._claves[i])


class MarcaCinema(QWidget):
    """La marca «CINEMA PRODUCTIONS» (blanca, fondo transparente) en la esquina de arriba a la izquierda de Inicio, a la altura de la isla.
    No recibe el ratón (arrastrar la franja de arriba sigue moviendo la ventana) y se oculta si la ventana es tan estrecha que chocaría con la isla."""
    ALTO_LOGO = 26
    MARGEN_X = 28

    def __init__(self, padre, ruta):
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._origen = QPixmap(str(ruta)) if ruta else QPixmap()
        self._pm = None
        self._dpr = 0.0
        self._en_inicio = False
        self.hide()

    def _preparar(self):
        dpr = max(1.0, float(self.devicePixelRatioF()))
        if self._pm is None or abs(dpr - self._dpr) > 0.01:
            self._dpr = dpr
            if self._origen.isNull():
                self._pm = QPixmap()
            else:
                self._pm = self._origen.scaledToHeight(int(round(self.ALTO_LOGO * dpr)), Qt.TransformationMode.SmoothTransformation)
                self._pm.setDevicePixelRatio(dpr)
            self.setFixedSize(int(round(self._pm.width() / dpr)), int(round(self._pm.height() / dpr))) if not self._pm.isNull() else self.setFixedSize(1, 1)

    def poner_en_inicio(self, si):
        self._en_inicio = bool(si)
        self.reposicionar()

    def reposicionar(self, isla=None):
        p = self.parentWidget()
        if p is None:
            return
        self._preparar()
        isla = isla if isla is not None else getattr(p, 'isla', None)
        if self._pm is None or self._pm.isNull() or not self._en_inicio:
            self.hide()
            return
        # la isla ENTRA animada y se recentra con resorte: se usa su sitio de REPOSO (centrada, asentada a 6 px), no su posición de este instante
        y = int(6 + isla.height() / 2 - self.height() / 2) if isla is not None else 22
        x = self.MARGEN_X
        if isla is not None and x + self.width() + 24 > (p.width() - isla.width()) / 2 + MARGEN:         # no cabe junto a la isla: se oculta
            self.hide()
            return
        self.move(x, max(8, y))
        self.show()
        self.raise_()

    def paintEvent(self, _e):
        if self._pm is None or self._pm.isNull():
            return
        p = QPainter(self)
        p.setOpacity(0.92)
        p.drawPixmap(0, 0, self._pm)


class MarcoVentana(QWidget):
    """El borde de 1 px de la ventana sin barra de titulo (no recibe el raton)."""
    def __init__(self, padre):
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def paintEvent(self, _e):
        w = self.window()
        if w is not None and (w.isMaximized() or w.isFullScreen()):
            return
        p = QPainter(self)
        p.setPen(QPen(QColor(255, 255, 255, 36), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        p.end()


class BordesVentana(QObject):
    """Arrastrar la franja de arriba mueve la ventana; los bordes (6 px) la redimensionan. Un filtro global de eventos del raton
    (sin widgets extra encima del contenido)."""
    FRANJA = 8          # alto de la franja de arrastre arriba
    GROSOR = 6

    def __init__(self, ventana, al_cerrar_paneles=None):
        super().__init__(ventana)
        self._v = ventana
        self._al_clic_fuera = al_cerrar_paneles
        self._ini = None
        QApplication.instance().installEventFilter(self)

    def _bordes(self, pos_global):
        v = self._v
        if v.isMaximized() or v.isFullScreen():
            return Qt.Edge(0)
        p = v.mapFromGlobal(pos_global.toPoint())
        b = Qt.Edge(0)
        if p.x() <= self.GROSOR:
            b |= Qt.Edge.LeftEdge
        if p.x() >= v.width() - self.GROSOR:
            b |= Qt.Edge.RightEdge
        if p.y() <= self.GROSOR:
            b |= Qt.Edge.TopEdge
        if p.y() >= v.height() - self.GROSOR:
            b |= Qt.Edge.BottomEdge
        return b

    # -- mantener pulsado en cualquier zona «vacía» y arrastrar mueve la ventana ---------------------------------------------
    _INTERACTIVOS = (QAbstractButton, QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit)
    _NEUTROS = (QWidget, QFrame, QLabel, QScrollArea, QStackedWidget)

    @classmethod
    def _arrastrable(cls, w):
        """True si pulsar en `w` no hace nada propio: ni el ni sus madres son botones, campos, listas o widgets con su propio
        mousePressEvent (lienzos, ondas, tarjetas clicables…). Un widget puede vetarse con la propiedad `no_arrastrar`."""
        n = 0
        while w is not None and n < 40:
            if w.property('no_arrastrar') or isinstance(w, cls._INTERACTIVOS):
                return False
            if isinstance(w, QAbstractScrollArea) and not isinstance(w, QScrollArea):
                return False
            if w.cursor().shape() != Qt.CursorShape.ArrowCursor and not isinstance(w, (QFrame, QLabel)):
                return False
            if getattr(w, '_clicable', False):
                return False
            for k in type(w).__mro__:
                if k.__module__.startswith('PySide6') or k.__name__ == 'Tarjeta':
                    break
                if any(m in k.__dict__ for m in ('mousePressEvent', 'mouseMoveEvent', 'mouseReleaseEvent')):
                    return False
            if w.cursor().shape() in (Qt.CursorShape.PointingHandCursor, Qt.CursorShape.IBeamCursor):
                return False
            if w.isWindow():
                break
            w = w.parentWidget()
            n += 1
        return True

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Type.MouseButtonRelease:
            self._ini = None
            return False
        if t not in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            return False
        try:
            if not isinstance(obj, QWidget) or obj.window() is not self._v:
                return False
            g = ev.globalPosition()
            if t == QEvent.Type.MouseMove and getattr(self, '_ini', None) is not None:
                if ev.buttons() & Qt.MouseButton.LeftButton:
                    if (g - self._ini).manhattanLength() >= 8:
                        self._ini = None
                        h = self._v.windowHandle()
                        if h is not None and not self._v.isMaximized():
                            h.startSystemMove()
                            return True
                else:
                    self._ini = None
            if t == QEvent.Type.MouseButtonPress and self._al_clic_fuera is not None:
                self._al_clic_fuera(obj)
            b = self._bordes(g)
            if t == QEvent.Type.MouseMove:
                if ev.buttons() == Qt.MouseButton.NoButton:
                    cur = {Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor, Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
                           Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor, Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
                           Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeFDiagCursor,
                           Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeFDiagCursor,
                           Qt.Edge.RightEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeBDiagCursor,
                           Qt.Edge.LeftEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeBDiagCursor}.get(b)
                    if cur is not None:
                        if not getattr(self, '_cursor_puesto', False):
                            QApplication.setOverrideCursor(cur)
                            self._cursor_puesto = True
                        else:
                            QApplication.changeOverrideCursor(cur)
                    elif getattr(self, '_cursor_puesto', False):
                        QApplication.restoreOverrideCursor()
                        self._cursor_puesto = False
                return False
            # clic
            if ev.button() != Qt.MouseButton.LeftButton:
                return False
            h = self._v.windowHandle()
            if h is None:
                return False
            if int(b.value if hasattr(b, 'value') else b):
                h.startSystemResize(b)
                return True
            p = self._v.mapFromGlobal(g.toPoint())
            if p.y() <= self.FRANJA and not self._v.isMaximized():
                h.startSystemMove()
                return True
            self._ini = g if (not self._v.isMaximized() and self._arrastrable(obj)) else None
        except Exception:
            return False
        return False
