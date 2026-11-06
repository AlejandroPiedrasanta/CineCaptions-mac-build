# CineCaptions · By Cinema Productions
# 1_codigo/idioma_ui.py — el idioma de la interfaz en Ajustes: panel de tarjetas con banderas dibujadas que ondean (13 idiomas).
"""v5.71 (el usuario eligió la propuesta B: «mejor con las banderas a la par, animadas al seleccionar, y agrega otros idiomas»):
el idioma de la interfaz se elige en un panel de tarjetas (bandera grande, saludo, nombre propio y nombre en el idioma de la interfaz);
la elegida ondea. Las banderas se DIBUJAN (QPainter, sin imágenes): 13 formas en un lienzo 30×20 (3:2).
En Ajustes › Interfaz la fila «Idioma de la interfaz» es un `BotonIdioma` (bandera + nombre) que abre `HojaIdioma` en una CapaModal."""
import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QAbstractButton, QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

import qt_kit as ui
from qt_kit import Boton, Etiqueta, QColor, QColorReal, fuente
from i18n import tr

# (código de la interfaz, bandera, saludo, nombre en español: el de la tercera línea, traducido con i18n.nombre_idioma)
IDIOMAS = (
    ('es', 'es', 'Hola', 'Español'),
    ('en', 'us', 'Hello', 'Inglés'),
    ('pt', 'br', 'Olá', 'Portugués'),
    ('fr', 'fr', 'Bonjour', 'Francés'),
    ('de', 'de', 'Hallo', 'Alemán'),
    ('it', 'it', 'Ciao', 'Italiano'),
    ('ja', 'jp', 'こんにちは', 'Japonés'),
    ('ko', 'kr', '안녕하세요', 'Coreano'),
    ('zh', 'cn', '你好', 'Chino'),
    ('ru', 'ru', 'Привет', 'Ruso'),
    ('nl', 'nl', 'Hallo', 'Neerlandés'),
    ('tr', 'tr', 'Merhaba', 'Turco'),
    ('pl', 'pl', 'Cześć', 'Polaco'),
)
NUEVOS = {'ja', 'ko', 'zh', 'ru', 'nl', 'tr', 'pl'}
NUEVOS_HASTA = (5, 73)            # la etiqueta «NUEVO» se ve hasta la 5.73
BANDERA = {c: b for c, b, _s, _n in IDIOMAS}


# ---------------------------------------------------------------------------
# Banderas (lienzo 30×20)
# ---------------------------------------------------------------------------
def _franjas_h(p, *colores):
    h = 20 / len(colores)
    for i, c in enumerate(colores):
        p.fillRect(QRectF(0, i * h, 30, h + 0.05), QColorReal(c))


def _franjas_v(p, *colores):
    w = 30 / len(colores)
    for i, c in enumerate(colores):
        p.fillRect(QRectF(i * w, 0, w + 0.05, 20), QColorReal(c))


def _estrella(p, cx, cy, r, color, giro=0.0):
    puntos = []
    for i in range(10):
        a = math.radians(-90 + giro + i * 36)
        rr = r if i % 2 == 0 else r * 0.382
        puntos.append(QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a)))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColorReal(color))
    p.drawPolygon(QPolygonF(puntos))


def _circulo(p, cx, cy, r, color):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColorReal(color))
    p.drawEllipse(QPointF(cx, cy), r, r)


def _us(p):
    for i in range(13):
        p.fillRect(QRectF(0, i * 20 / 13, 30, 20 / 13 + 0.03), QColorReal('#B22234' if i % 2 == 0 else '#FFFFFF'))
    p.fillRect(QRectF(0, 0, 12, 20 * 7 / 13), QColorReal('#3C3B6E'))
    for f in range(5):
        for c in range(6 if f % 2 == 0 else 5):
            _circulo(p, 1.0 + c * 2.0 + (1.0 if f % 2 else 0), 1.2 + f * 1.95, 0.42, '#FFFFFF')


def _br(p):
    p.fillRect(QRectF(0, 0, 30, 20), QColorReal('#009C3B'))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColorReal('#FFDF00'))
    p.drawPolygon(QPolygonF([QPointF(15, 2.2), QPointF(27.6, 10), QPointF(15, 17.8), QPointF(2.4, 10)]))
    _circulo(p, 15, 10, 4.7, '#002776')
    arco = QPainterPath(QPointF(10.4, 9.2))
    arco.quadTo(QPointF(15, 7.6), QPointF(19.6, 10.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColorReal('#FFFFFF'), 0.9))
    p.drawPath(arco)


def _kr(p):
    p.fillRect(QRectF(0, 0, 30, 20), QColorReal('#FFFFFF'))
    p.save()
    p.translate(15, 10)
    p.rotate(33.7)
    p.translate(-15, -10)
    _circulo(p, 15, 10, 5, '#0047A0')
    rojo = QPainterPath(QPointF(10, 10))
    rojo.arcTo(QRectF(10, 5, 10, 10), 180, -180)          # media luna de arriba
    rojo.arcTo(QRectF(15, 7.5, 5, 5), 0, -180)            # la gota de la derecha, hacia abajo
    rojo.arcTo(QRectF(10, 7.5, 5, 5), 0, 180)             # la de la izquierda, hacia arriba
    rojo.closeSubpath()
    p.setBrush(QColorReal('#CD2E3A'))
    p.drawPath(rojo)
    p.restore()
    for (x, y, giro) in ((6.2, 4.6, -56.3), (23.8, 15.4, -56.3), (23.8, 4.6, 56.3), (6.2, 15.4, 56.3)):
        p.save()
        p.translate(x, y)
        p.rotate(giro)
        for k in range(3):
            p.fillRect(QRectF(-2.6, -2 + k * 1.45, 5.2, 0.9), QColorReal('#000000'))
        p.restore()


def _cn(p):
    p.fillRect(QRectF(0, 0, 30, 20), QColorReal('#EE1C25'))
    _estrella(p, 5, 5, 3, '#FFFF00')
    for (x, y, g) in ((10, 2, 23), (12, 4, 45), (12, 7, 70), (10, 9, 20)):
        _estrella(p, x, y, 1, '#FFFF00', g)


def _tr(p):
    p.fillRect(QRectF(0, 0, 30, 20), QColorReal('#E30A17'))
    _circulo(p, 11.2, 10, 5, '#FFFFFF')
    _circulo(p, 12.45, 10, 4, '#E30A17')
    _estrella(p, 17.1, 10, 2.2, '#FFFFFF', -90)


def _jp(p):
    p.fillRect(QRectF(0, 0, 30, 20), QColorReal('#FFFFFF'))
    _circulo(p, 15, 10, 6, '#BC002D')


FORMAS = {
    'es': lambda p: _franjas_h(p, '#AA151B', '#F1BF00', '#F1BF00', '#AA151B'),
    'us': _us,
    'br': _br,
    'fr': lambda p: _franjas_v(p, '#002654', '#FFFFFF', '#CE1126'),
    'de': lambda p: _franjas_h(p, '#000000', '#DD0000', '#FFCE00'),
    'it': lambda p: _franjas_v(p, '#009246', '#FFFFFF', '#CE2B37'),
    'jp': _jp,
    'kr': _kr,
    'cn': _cn,
    'ru': lambda p: _franjas_h(p, '#FFFFFF', '#0039A6', '#D52B1E'),
    'nl': lambda p: _franjas_h(p, '#AE1C28', '#FFFFFF', '#21468B'),
    'tr': _tr,
    'pl': lambda p: _franjas_h(p, '#FFFFFF', '#DC143C'),
}
_CACHE = {}


def _lienzo(bandera, w, h, dpr):
    """La bandera quieta en un QPixmap de w×h (lógicos) a la resolución de la pantalla (en píxeles reales, sin devicePixelRatio)."""
    clave = (bandera, round(w, 1), round(h, 1), round(dpr, 2))
    pm = _CACHE.get(clave)
    if pm is None:
        pm = QPixmap(max(1, math.ceil(w * dpr)), max(1, math.ceil(h * dpr)))
        pm.fill(QColorReal(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(pm.width() / 30.0, pm.height() / 20.0)
        FORMAS.get(bandera, FORMAS['es'])(p)
        p.end()
        _CACHE[clave] = pm
    return pm


def pintar_bandera(p, bandera, r, radio=4.0, onda=0.0, fase=0.0, dpr=1.0, sombra=True, tiras=24):
    """La bandera en el rectángulo r (3:2). Con `onda` (px) ondea: tiras verticales desplazadas con un seno que crece hacia la punta,
    con la luz y la sombra de los pliegues; quieta, recortada con esquinas redondeadas y un filo claro."""
    pm = _lienzo(bandera, r.width(), r.height(), dpr)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if sombra:
        p.setPen(Qt.PenStyle.NoPen)
        for k, a in ((3.0, 34), (1.6, 46)):
            p.setBrush(QColorReal(0, 0, 0, a))
            p.drawRoundedRect(r.adjusted(-k * 0.4, k, k * 0.4, k + 0.6), radio + 1, radio + 1)
    if onda <= 0.05:
        camino = QPainterPath()
        camino.addRoundedRect(r, radio, radio)
        p.setClipPath(camino)
        p.drawPixmap(r, pm, QRectF(0, 0, pm.width(), pm.height()))
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColorReal(255, 255, 255, 46), 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radio, radio)
        p.restore()
        return
    ancho = r.width() / tiras
    escala = pm.width() / r.width()
    for i in range(tiras):
        a = i / (tiras - 1)
        ang = fase + a * 2.6 * math.pi
        dy = onda * math.sin(ang) * (0.35 + 0.65 * a)
        x = i * ancho
        w = min(ancho + 0.6, r.width() - x)
        destino = QRectF(r.left() + x, r.top() + dy, w, r.height())
        p.drawPixmap(destino, pm, QRectF(x * escala, 0, w * escala, pm.height()))
        luz = 0.10 * math.cos(ang)
        tono = QColorReal(255, 255, 255, int(255 * luz)) if luz > 0 else QColorReal(0, 0, 0, int(255 * min(1.0, -luz * 1.6)))
        p.fillRect(QRectF(destino.left(), destino.top(), ancho, destino.height()), tono)
    p.restore()


def _dpr(widget):
    try:
        return max(1.0, float(widget.devicePixelRatioF()))
    except Exception:
        return 1.0


def _nuevo_visible():
    try:
        import version
        partes = tuple(int(x) for x in str(version.APP_VERSION).split('.')[:2])
        return partes <= NUEVOS_HASTA
    except Exception:
        return False


def _nombre_nativo(codigo):
    import i18n
    return i18n.IDIOMAS_UI.get(codigo, codigo)


# ---------------------------------------------------------------------------
# La fila de Ajustes: bandera + nombre (abre el panel)
# ---------------------------------------------------------------------------
class BotonIdioma(QAbstractButton):
    def __init__(self, codigo, alto=52, padre=None):
        super().__init__(padre)
        self._codigo = codigo
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(int(alto))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(tr('Idioma de la interfaz'))

    def poner(self, codigo):
        self._codigo = codigo
        self.update()

    def codigo(self):
        return self._codigo

    def sizeHint(self):
        return QSize(380, self.height())

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor('#14223C' if self._hover else '#111D33'))
        p.setPen(QPen(QColor('#2E4A7A' if self._hover else '#1E2A42'), 1))
        p.drawRoundedRect(r, 10, 10)
        alto_b = 20.0
        caja = QRectF(r.left() + 16, r.center().y() - alto_b / 2, alto_b * 1.5, alto_b)
        pintar_bandera(p, BANDERA.get(self._codigo, 'es'), caja, radio=3, dpr=_dpr(self), sombra=False)
        p.setPen(QColor('#E8F1FF'))
        p.setFont(fuente(16, peso='medio'))
        texto = QRectF(caja.right() + 14, r.top(), r.width() - caja.right() - 60, r.height())
        p.drawText(texto, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), _nombre_nativo(self._codigo))
        ic = ui.icono_linea('ph.caret-right-bold', '#8D9BB5')
        if ic is not None:
            lado = 14
            ic.paint(p, int(r.right() - 16 - lado), int(r.center().y() - lado / 2), lado, lado)
        p.end()


# ---------------------------------------------------------------------------
# El panel de tarjetas
# ---------------------------------------------------------------------------
class _TarjetaIdioma(QAbstractButton):
    def __init__(self, codigo, bandera, saludo, nombre_es, actual, nuevo, padre=None):
        super().__init__(padre)
        import i18n
        self.codigo = codigo
        self._bandera = bandera
        self._saludo = saludo
        self._nativo = _nombre_nativo(codigo)
        self._tercera = tr('Idioma actual') if codigo == actual else i18n.nombre_idioma(codigo, nombre_es)
        self._nuevo = nuevo
        self._hover = False
        self.onda = 0.0
        self.fase = 0.0
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(150, 124)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(self._nativo)

    def sizeHint(self):
        return QSize(168, 142)

    def rect_bandera(self):
        return QRectF(15, 15, 54, 36)

    def mouseDoubleClickEvent(self, e):
        fn = getattr(self, 'al_doble_clic', None)
        if fn is not None and e.button() == Qt.MouseButton.LeftButton:
            fn()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        sel = self.isChecked()
        acento = QColor(ui.ACCENT)
        if sel:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#0D1627'))
            p.drawRoundedRect(r, 14, 14)
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0.0, QColorReal(acento.red(), acento.green(), acento.blue(), 58))
            g.setColorAt(1.0, QColorReal(acento.red(), acento.green(), acento.blue(), 10))
            p.setBrush(g)
            p.setPen(QPen(acento, 1.6))
        else:
            p.setBrush(QColor('#111D33' if self._hover else '#0D1627'))
            p.setPen(QPen(QColor('#2E4A7A' if self._hover else '#1E2A42'), 1))
        p.drawRoundedRect(r, 14, 14)
        dpr = _dpr(self)
        fb = self.rect_bandera().translated(r.left() - 1, r.top() - 1)
        pintar_bandera(p, self._bandera, fb, radio=4, onda=self.onda if sel else 0.0, fase=self.fase, dpr=dpr)
        if sel:
            ic = ui.icono_linea('ph.check-bold', ui.ACCENT_CLARO)
            if ic is not None:
                ic.paint(p, int(r.right() - 34), int(r.top() + 16), 20, 20)
        elif self._nuevo:
            p.setFont(fuente(9, peso='extra'))
            texto = tr('NUEVO')
            ancho = p.fontMetrics().horizontalAdvance(texto) + 14
            chip = QRectF(r.right() - 14 - ancho, r.top() + 16, ancho, 18)
            p.setBrush(QColorReal(acento.red(), acento.green(), acento.blue(), 38))
            p.setPen(QPen(QColorReal(acento.red(), acento.green(), acento.blue(), 130), 1))
            p.drawRoundedRect(chip, 9, 9)
            p.setPen(QColor(ui.ACCENT_CLARO))
            p.drawText(chip, int(Qt.AlignmentFlag.AlignCenter), texto)
        x = r.left() + 14
        w = r.width() - 28
        tercera = QRectF(x, r.bottom() - 14 - 16, w, 16)
        nativo = QRectF(x, tercera.top() - 19, w, 18)
        saludo = QRectF(x, nativo.top() - 32, w, 30)
        p.setPen(QColor('#FFFFFF'))
        f = fuente(20, peso='extra')
        p.setFont(f)
        p.drawText(saludo, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                   p.fontMetrics().elidedText(self._saludo, Qt.TextElideMode.ElideRight, int(w)))
        p.setPen(QColor('#E8F1FF'))
        p.setFont(fuente(12.5, peso='negrita'))
        p.drawText(nativo, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._nativo)
        p.setPen(QColor('#8D9BB5'))
        p.setFont(fuente(11.5))
        p.drawText(tercera, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   p.fontMetrics().elidedText(self._tercera, Qt.TextElideMode.ElideRight, int(w)))
        p.end()


class HojaIdioma(QFrame):
    """El panel: cabecera, 13 tarjetas en 4 columnas y el pie (qué pasa al reiniciar, Cancelar, «Usar …»).
    al_usar(codigo) recibe el elegido; al_cancelar() cierra."""

    def __init__(self, elegido, actual, al_usar, al_cancelar, padre=None):
        super().__init__(padre)
        self._actual = actual
        self._al_usar = al_usar
        self.setObjectName('hojaIdioma')
        self.setStyleSheet(ui.traducir_hoja('QFrame#hojaIdioma { background-color: #0B111D; border: 1px solid #22324F; border-radius: 18px; }'))
        c = QVBoxLayout(self)
        c.setContentsMargins(26, 22, 26, 22)
        c.setSpacing(16)
        cab = QHBoxLayout()
        cab.setSpacing(12)
        cab.addWidget(Etiqueta(tr('Idioma de la interfaz'), 21, peso='extra', color='#FFFFFF'), 0, Qt.AlignmentFlag.AlignBottom)
        cab.addWidget(Etiqueta(tr('{n} idiomas · se aplica al reiniciar', n=len(IDIOMAS)), 13, color=ui.TEXT_MUTED), 0,
                      Qt.AlignmentFlag.AlignBottom)
        cab.addStretch(1)
        c.addLayout(cab)
        rejilla = QGridLayout()
        rejilla.setSpacing(10)
        nuevo = _nuevo_visible()
        self.tarjetas = []
        for i, (codigo, bandera, saludo, nombre_es) in enumerate(IDIOMAS):
            t = _TarjetaIdioma(codigo, bandera, saludo, nombre_es, actual, nuevo and codigo in NUEVOS)
            t.clicked.connect(lambda _=False, k=codigo: self.elegir(k))
            t.al_doble_clic = lambda k=codigo: (self.elegir(k), self._usar())
            rejilla.addWidget(t, i // 4, i % 4)
            self.tarjetas.append(t)
        for col in range(4):
            rejilla.setColumnStretch(col, 1)
        c.addLayout(rejilla, 1)
        pie = QHBoxLayout()
        pie.setSpacing(10)
        icono = QLabel()
        ic = ui.icono_linea('ph.arrow-clockwise-bold', '#8D9BB5')
        if ic is not None:
            icono.setPixmap(ic.pixmap(QSize(16, 16), max(1.0, float(QApplication.instance().devicePixelRatio()))))
            icono.setFixedSize(16, 16)
            icono.setScaledContents(True)
        pie.addWidget(icono, 0, Qt.AlignmentFlag.AlignVCenter)
        self.aviso = Etiqueta('', 13.5, color=ui.TEXT_MUTED)
        pie.addWidget(self.aviso, 1, Qt.AlignmentFlag.AlignVCenter)
        pie.addWidget(Boton(tr('Cancelar'), al_cancelar, tipo='neutro', alto=46, ancho=120, tam=15, negrita=True))
        self.usar_btn = Boton('', self._usar, tipo='primario', alto=46, ancho=160, tam=15, negrita=True)
        pie.addWidget(self.usar_btn)
        c.addLayout(pie)
        self._t_eleccion = time.monotonic()
        self._reloj = QTimer(self)
        self._reloj.setInterval(33)
        self._reloj.timeout.connect(self._tic)
        self._elegido = None
        self.elegir(elegido if elegido in dict((k, 1) for k, *_r in IDIOMAS) else actual, animar=False)

    def elegido(self):
        return self._elegido

    def elegir(self, codigo, animar=True):
        self._elegido = codigo
        for t in self.tarjetas:
            t.setChecked(t.codigo == codigo)
        if animar:
            self._t_eleccion = time.monotonic()
        nombre = _nombre_nativo(codigo)
        self.usar_btn.configure(text=tr('Usar {idioma}', idioma=nombre))
        if codigo == self._actual:
            self.aviso.configure(text=tr('Se aplica al reiniciar CineCaptions.'))
        else:
            self.aviso.configure(text=tr('{idioma} seguirá hasta que reinicies', idioma=_nombre_nativo(self._actual)))

    def _usar(self):
        if self._elegido:
            self._al_usar(self._elegido)

    def _tic(self):
        """La bandera elegida ondea siempre (suave) y con más fuerza justo al elegirla."""
        t = time.monotonic()
        golpe = math.exp(-(t - self._t_eleccion) / 0.55)
        for tarjeta in self.tarjetas:
            if tarjeta.isChecked():
                tarjeta.fase = (t * 5.2) % (2 * math.pi)
                tarjeta.onda = 1.7 + 3.2 * golpe
                tarjeta.update(tarjeta.rect_bandera().adjusted(-4, -9, 4, 10).toAlignedRect())

    def showEvent(self, e):
        super().showEvent(e)
        self._reloj.start()

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)
