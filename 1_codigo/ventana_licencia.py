# CineCaptions · By Cinema Productions
# 1_codigo/ventana_licencia.py — la ventana «Activa tu licencia» (formato CineSlide: panel animado, clave, confeti).
"""
ventana_licencia.py  (v5.2.1)
-----------------------------
La ventana «Activa tu licencia», con el MISMO formato que la de CineSlide 9.22 (pedido del
04-10-2026: «actualiza la interfaz de licencia, hazla como la de CineSlide, el mismo formato»).

Tarjeta sin marco (se arrastra desde cualquier parte) con, a la izquierda, un panel animado
-aurora que se mueve, luces que suben y un EMBLEMA con la llave y un anillo de luz que gira (más
rápido mientras consulta la tienda, verde con una palomita que se dibuja al activarse, un pulso
rojo si falla)- y a la derecha la clave, el aviso de la tienda reconocida por el formato,
«Activar licencia», los botones de compra y el ID de la computadora. Clave correcta: EXPLOSIÓN
DE CONFETI (cañón desde el botón, estallido desde el emblema y dos cañones laterales) y se
cierra sola. Clave incorrecta: el campo se sacude. Todo se pinta a mano.

Lo propio de CineCaptions: los colores de la casa (siguen el tema elegido en Ajustes), la marca
«Cine» + «Captions» y, si la licencia YA está activa, la misma tarjeta muestra sus datos con
«Desactivar este equipo» (en CineSlide eso vive en Mantenimiento).

DialogoLicencia(padre, motivo, verificar).ejecutar() -> True si al cerrar hay licencia vigente.
"""
import math
import random
import re
import threading
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (QBrush, QConicalGradient, QDesktopServices, QFont, QFontMetricsF,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

import licencia
import qt_kit as ui
from i18n import tr
from qt_kit import QColor, QColorReal

# Colores de la casa ('#RRGGBB' -> el tema elegido; ver qt_kit.tc)
C = {'texto': '#E8F1FF', 'suave': '#B7C4DA', 'tenue': '#8D9BB5', 'acento': '#4589FF',
     'cian': '#00C8FF', 'ok': '#24D18F', 'rojo': '#FF6B6B', 'naranja': '#F5B84B', 'oro': '#FFD36E'}


def col(hexa, alfa=1.0):
    """Color de la casa (sigue el tema) con transparencia."""
    c = QColor(hexa)
    c.setAlphaF(max(0.0, min(1.0, float(alfa))))
    return c


def col_fijo(hexa, alfa=1.0):
    """Color que NO cambia con el tema (blancos, negros, confeti)."""
    c = QColorReal(hexa)
    c.setAlphaF(max(0.0, min(1.0, float(alfa))))
    return c


def fuente(px, peso=None, espacio=0.0):
    f = ui.fuente(px, peso=peso)
    if espacio:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(espacio))
    return f


_PIX = {}


def pix_icono(nombre, color, lado, dpr=None):
    """Un icono de Phosphor (QtAwesome) como QPixmap nítido; None si no hay QtAwesome."""
    dpr = dpr or (QApplication.primaryScreen().devicePixelRatio() if QApplication.primaryScreen() else 1.0)
    clave = (nombre, color, int(lado), round(dpr, 2))
    if clave not in _PIX:
        ic = ui.icono_linea(nombre, color)
        _PIX[clave] = ic.pixmap(QSize(int(lado), int(lado)), dpr) if ic is not None else None
    return _PIX[clave]


def _animaciones():
    try:
        import efectos_ui
        return not efectos_ui.reducir_animaciones()
    except Exception:
        return True


class _BotonActivar(QAbstractButton):
    """«Activar licencia» dibujado a mano: píldora con el degradado de la casa y un brillo que la
    cruza cada pocos segundos; un aro que gira mientras consulta la tienda; verde con una palomita
    al activarse. Lo anima el reloj de la ventana (avanzar)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText(tr('Activar licencia'))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(56)
        self.setMinimumWidth(220)
        self.modo = 'normal'                    # normal | ocupado | ok
        self._hover = self._hover_obj = 0.0
        self._t0 = time.monotonic()

    def sizeHint(self):
        return QSize(320, 56)

    def poner_modo(self, modo, texto=None):
        self.modo = modo
        if texto:
            self.setText(texto)
        self.update()

    def enterEvent(self, e):
        self._hover_obj = 1.0
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover_obj = 0.0
        super().leaveEvent(e)

    def avanzar(self, dt):
        self._hover += (self._hover_obj - self._hover) * min(1.0, dt * 12.0)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        t = time.monotonic() - self._t0
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        ruta = QPainterPath()
        ruta.addRoundedRect(r, 20.0, 20.0)
        ok = self.modo == 'ok'
        if not self.isEnabled() and self.modo == 'normal':
            p.setOpacity(0.45)
        g = QLinearGradient(r.topLeft(), r.topRight())
        if ok:
            g.setColorAt(0.0, col_fijo('#169E68'))
            g.setColorAt(1.0, col_fijo('#3DDBA0'))
        else:
            g.setColorAt(0.0, col('#0F62FE'))
            g.setColorAt(0.55, col('#4589FF'))
            g.setColorAt(1.0, col('#00C8FF'))
        p.fillPath(ruta, QBrush(g))
        if self.isDown():
            p.fillPath(ruta, col_fijo('#000000', 0.14))
        elif self._hover > 0.01:
            p.fillPath(ruta, col_fijo('#FFFFFF', 0.12 * self._hover))
        ciclo = (t % 3.6) / 3.6
        if self.modo == 'normal' and ciclo < 0.3:          # brillo que cruza el botón
            x = r.left() - 90.0 + (r.width() + 180.0) * (ciclo / 0.3)
            bg = QLinearGradient(QPointF(x - 60.0, 0.0), QPointF(x + 60.0, 0.0))
            bg.setColorAt(0.0, col_fijo('#FFFFFF', 0.0))
            bg.setColorAt(0.5, col_fijo('#FFFFFF', 0.32))
            bg.setColorAt(1.0, col_fijo('#FFFFFF', 0.0))
            p.save()
            p.setClipPath(ruta)
            p.fillRect(r, QBrush(bg))
            p.restore()
        p.setPen(QPen(col_fijo('#CFE6FF', 0.45 + 0.4 * self._hover), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(ruta)
        f = fuente(16, 'negrita')
        p.setFont(f)
        fm = QFontMetricsF(f)
        ic = 22.0
        ancho = ic + 12.0 + fm.horizontalAdvance(self.text())
        x0, cy = r.center().x() - ancho / 2.0, r.center().y()
        blanco = col_fijo('#FFFFFF')
        if self.modo == 'ocupado':
            p.setPen(QPen(col_fijo('#FFFFFF', 0.28), 2.6))
            p.drawEllipse(QPointF(x0 + ic / 2.0, cy), 9.0, 9.0)
            pen = QPen(blanco, 2.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(QRectF(x0 + ic / 2.0 - 9.0, cy - 9.0, 18.0, 18.0), int(-t * 540.0 * 16) % 5760, 110 * 16)
        elif ok:
            pen = QPen(blanco, 3.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            cx = x0 + ic / 2.0
            p.drawPolyline(QPolygonF([QPointF(cx - 8.0, cy), QPointF(cx - 2.5, cy + 6.0), QPointF(cx + 8.5, cy - 6.5)]))
        else:
            pm = pix_icono('ph.key-bold', '#FFFFFF', int(ic))
            if pm is not None:
                p.drawPixmap(QRectF(x0, cy - ic / 2.0, ic, ic), pm, QRectF(pm.rect()))
        p.setPen(blanco)
        p.drawText(QRectF(x0 + ic + 12.0, r.top(), ancho, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


class _CapaConfeti(QWidget):
    """Confeti, serpentinas, estrellitas y ondas de luz ENCIMA de toda la ventana (no recibe
    clics). lanzar() dispara un cañón; avanzar(dt) mueve las piezas con gravedad, resistencia del
    aire y vaivén (caen flotando como papel y giran en 3D)."""
    COLORES = ('#4589FF', '#00C8FF', '#F5B84B', '#FFFFFF', '#24D18F', '#B388FF', '#FF8FB1', '#FFD36E')

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.piezas, self.ondas, self.chispas = [], [], []
        self._colores = [col_fijo(c) for c in self.COLORES]

    def activa(self):
        return bool(self.piezas or self.ondas or self.chispas)

    @staticmethod
    def _estrella(radio):
        pts = []
        for i in range(8):
            a = math.radians(i * 45.0 - 90.0)
            rr = radio if i % 2 == 0 else radio * 0.38
            pts.append(QPointF(math.cos(a) * rr, math.sin(a) * rr))
        return QPolygonF(pts)

    def lanzar(self, x, y, n, ang0, ang1, v0=520.0, v1=1250.0, onda=True):
        for _i in range(int(n)):
            a = math.radians(random.uniform(ang0, ang1))
            v = random.uniform(v0, v1)
            forma = random.choice(('rect', 'rect', 'rect', 'circ', 'cinta', 'estrella'))
            self.piezas.append({'x': float(x), 'y': float(y), 'vx': math.cos(a) * v, 'vy': math.sin(a) * v,
                                'rot': random.uniform(0.0, 360.0), 'vr': random.uniform(-760.0, 760.0),
                                'fase': random.uniform(0.0, 6.283), 'vf': random.uniform(5.0, 13.0),
                                'c': random.choice(self._colores), 'w': random.uniform(6.0, 11.0),
                                'h': random.uniform(16.0, 26.0) if forma == 'cinta' else random.uniform(4.0, 7.5),
                                'forma': forma, 't': 0.0, 'vida': random.uniform(2.4, 3.8)})
        if onda:
            self.ondas.append({'x': float(x), 'y': float(y), 't': 0.0})
        for _i in range(10):
            self.chispas.append({'x': x + random.uniform(-90.0, 90.0), 'y': y + random.uniform(-70.0, 40.0),
                                 't': -random.uniform(0.0, 0.5), 's': random.uniform(5.0, 11.0),
                                 'c': random.choice(self._colores)})
        self.raise_()
        self.update()

    def avanzar(self, dt):
        arrastre = math.exp(-2.2 * dt)
        alto = self.height() + 60.0
        vivas = []
        for q in self.piezas:
            q['t'] += dt
            if q['t'] >= q['vida'] or q['y'] > alto:
                continue
            q['vx'] *= arrastre
            q['vy'] = q['vy'] * arrastre + 1500.0 * dt
            if q['vy'] > 240.0:                    # caída limitada: flotan como papel
                q['vy'] = 240.0 + (q['vy'] - 240.0) * 0.85
            q['fase'] += q['vf'] * dt
            q['x'] += (q['vx'] + math.sin(q['fase']) * 38.0) * dt
            q['y'] += q['vy'] * dt
            q['rot'] += q['vr'] * dt
            vivas.append(q)
        self.piezas = vivas
        for o in self.ondas:
            o['t'] += dt
        self.ondas = [o for o in self.ondas if o['t'] < 0.8]
        for s in self.chispas:
            s['t'] += dt
        self.chispas = [s for s in self.chispas if s['t'] < 0.9]
        self.update()

    def paintEvent(self, e):
        if not self.activa():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for o in self.ondas:                       # onda de luz que se abre desde cada cañón
            k = o['t'] / 0.8
            rad = 18.0 + 300.0 * (1.0 - (1.0 - k) ** 3)
            p.setPen(QPen(col_fijo('#FFFFFF', 0.5 * (1.0 - k)), 1.0 + 4.0 * (1.0 - k)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(o['x'], o['y']), rad, rad)
        p.setPen(Qt.PenStyle.NoPen)
        for q in self.piezas:
            resto = q['vida'] - q['t']
            p.setOpacity(1.0 if resto > 0.7 else max(0.0, resto / 0.7))
            p.save()
            p.translate(q['x'], q['y'])
            p.rotate(q['rot'])
            p.scale(1.0, max(0.12, abs(math.cos(q['fase']))))     # gira en 3D: de canto y de frente
            c = q['c']
            if q['forma'] == 'rect':
                p.fillRect(QRectF(-q['w'] / 2.0, -q['h'] / 2.0, q['w'], q['h']), c)
            elif q['forma'] == 'circ':
                p.setBrush(c)
                p.drawEllipse(QPointF(0.0, 0.0), q['w'] * 0.38, q['w'] * 0.38)
            elif q['forma'] == 'estrella':
                p.setBrush(c)
                p.drawPolygon(self._estrella(q['w'] * 0.75))
            else:                                  # serpentina
                pen = QPen(c, 2.4)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                h = q['h']
                ruta = QPainterPath(QPointF(0.0, -h / 2.0))
                ruta.cubicTo(QPointF(7.0, -h / 6.0), QPointF(-7.0, h / 6.0), QPointF(0.0, h / 2.0))
                p.drawPath(ruta)
                p.setPen(Qt.PenStyle.NoPen)
            p.restore()
        for s in self.chispas:                     # estrellitas que titilan
            if s['t'] < 0.0:
                continue
            esc = math.sin(math.pi * min(1.0, s['t'] / 0.9))
            p.setOpacity(esc)
            p.setBrush(s['c'])
            p.save()
            p.translate(s['x'], s['y'])
            p.rotate(s['t'] * 140.0)
            p.drawPolygon(self._estrella(s['s'] * (0.4 + 0.6 * esc)))
            p.restore()
        p.setOpacity(1.0)


class _CajaSacudible(QWidget):
    """Contenedor del campo de la clave: lo mueve en horizontal para la sacudida de «clave
    incorrecta»."""

    def __init__(self, hijo, parent=None):
        super().__init__(parent)
        self.hijo, self.dx = hijo, 0.0
        hijo.setParent(self)
        self.setFixedHeight(max(40, hijo.minimumHeight()))

    def poner_dx(self, dx):
        self.dx = float(dx)
        self._ubicar()

    def _ubicar(self):
        self.hijo.setGeometry(int(round(self.dx)), 0, self.width(), self.height())

    def resizeEvent(self, e):
        self._ubicar()
        super().resizeEvent(e)


class _BotonCerrar(QAbstractButton):
    """La X redonda de la esquina (rojo al pasar el ratón)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr('Cerrar'))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        encima = self.underMouse()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col_fijo('#FF5F57', 0.95) if encima else col_fijo('#FFFFFF', 0.06))
        p.drawEllipse(QRectF(self.rect()).adjusted(2, 2, -2, -2))
        pen = QPen(col_fijo('#FFFFFF') if encima else col('#8D9BB5'), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        c, d = QRectF(self.rect()).center(), 5.0
        p.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        p.drawLine(QPointF(c.x() + d, c.y() - d), QPointF(c.x() - d, c.y() + d))


class VentanaLicencia(QDialog):
    """La tarjeta (ver el docstring del módulo). La lógica vive en DialogoLicencia."""
    CARTA = (860.0, 560.0)
    QSS = (' QDialog { background: transparent; }'
           ' QWidget#panelLic { background: transparent; }'
           ' QLineEdit#campoClave { background: rgba(255,255,255,0.045); color:#E8F1FF; border:1px solid #2A3A5C;'
           ' border-radius:16px; padding:0 18px; selection-background-color:#0F62FE; }'
           ' QLineEdit#campoClave:focus { border:1px solid #4589FF; background: rgba(69,137,255,0.08); }'
           ' QLineEdit#campoClave[estado="error"] { border:1px solid #FF6B6B; background: rgba(255,107,107,0.08); }'
           ' QLineEdit#campoClave[estado="ok"] { border:1px solid #24D18F; background: rgba(36,209,143,0.08); }'
           ' QLineEdit#campoClave:disabled { color:#A9B6CC; }'
           ' QPushButton#btnTienda { background: rgba(255,255,255,0.05); color:#DCE6F5; border:1px solid #2A3A5C;'
           ' border-radius:17px; padding:0 16px; min-height:34px; font-size:13px; font-weight:600; }'
           ' QPushButton#btnTienda:hover { border-color:#4589FF; background: rgba(69,137,255,0.12); }'
           ' QPushButton#btnLink { background: transparent; color:#8D9BB5; border:0; padding:0 8px; min-height:34px;'
           ' font-size:13px; font-weight:600; }'
           ' QPushButton#btnLink:hover { color:#E8F1FF; }'
           ' QPushButton#btnPeligro { background: transparent; color:#FF8A80; border:0; padding:0 8px; min-height:34px;'
           ' font-size:13px; font-weight:600; }'
           ' QPushButton#btnPeligro:hover { color:#FFFFFF; }'
           ' QPushButton#btnIcono { background: rgba(255,255,255,0.05); border:1px solid #23314D; border-radius:13px;'
           ' min-width:28px; max-width:28px; min-height:28px; max-height:28px; padding:0; }'
           ' QPushButton#btnIcono:hover { border-color:#4589FF; background: rgba(69,137,255,0.12); }'
           ' QLabel#chipId { background: rgba(255,255,255,0.05); color:#8D9BB5; border:1px solid #23314D;'
           ' border-radius:13px; padding:5px 12px; font-size:12px; }'
           ' QFrame#sepLic { background: #1C2A44; border:0; }')

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setWindowTitle(tr('Licencia de CineCaptions'))
        if ui._ICONO.get('icono') is not None:
            self.setWindowIcon(ui._ICONO['icono'])
        self.animado = _animaciones()
        W, H, sc = 1120, 780, None
        try:
            pantalla = (padre.screen() if padre is not None else None) or QApplication.primaryScreen()
            sc = pantalla.availableGeometry()
            W, H = min(W, sc.width() - 16), min(H, sc.height() - 16)
        except Exception:
            pass
        self.resize(W, H)
        try:
            c = padre.frameGeometry().center() if (padre is not None and padre.isVisible()) else sc.center()
            self.move(int(c.x() - W / 2), int(c.y() - H / 2))
        except Exception:
            pass
        self.estado, self._t_estado = 'normal', time.monotonic()
        self._t0 = self._t_prev = time.monotonic()
        self._t_sacudida = None
        self.modo_activa = False
        rnd = random.Random(7)
        self._luces = [(rnd.random(), rnd.random(), 2.0 + 5.0 * rnd.random(), 0.035 + 0.05 * rnd.random(),
                        rnd.random() * 6.28, ('#00C8FF', '#FFD36E', '#B388FF', '#FFFFFF')[i % 4]) for i in range(26)]
        from version import APP_VERSION
        self.version = APP_VERSION
        self.beneficios = (tr('Subtítulos virales con un clic (GO)'), tr('IA local: voz, palabras clave y emojis'),
                           tr('Directo a tu timeline de Resolve'))
        self.setStyleSheet(ui.traducir_hoja(self.QSS))
        self._construir()
        self.b_x = _BotonCerrar(self)
        self.b_x.clicked.connect(self.reject)
        self.capa = _CapaConfeti(self)
        for b in self.findChildren(QPushButton):          # Enter en la clave = ACTIVAR (nunca «Comprar»)
            b.setAutoDefault(False)
            b.setDefault(False)
        self.reloj = QTimer(self)
        self.reloj.setInterval(16)
        self.reloj.timeout.connect(self._tic)

    # ---- armado
    def _construir(self):
        self.panel = QWidget(self)
        self.panel.setObjectName('panelLic')
        v = QVBoxLayout(self.panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        def etiqueta(texto, px, color, peso=None, esp=0.0, envolver=False):
            l = QLabel(texto)
            l.setFont(fuente(px, peso, esp))
            l.setStyleSheet('color:%s;background:transparent;' % ui.tc(color))
            l.setWordWrap(envolver)
            return l
        self._etiqueta = etiqueta
        self.lbl_tit = etiqueta(tr('Activa tu licencia'), 30, C['texto'], 'extra')
        self.lbl_sub = etiqueta(tr('Pega la clave que te llegó por correo al comprar. Se activa en esta computadora '
                                   'en segundos.'), 14, C['suave'], envolver=True)
        v.addWidget(self.lbl_tit)
        v.addSpacing(6)
        v.addWidget(self.lbl_sub)
        v.addSpacing(22)
        self.lbl_clave = etiqueta(tr('CLAVE DE LICENCIA'), 11, C['tenue'], 'negrita', 1.8)
        v.addWidget(self.lbl_clave)
        v.addSpacing(8)
        self.txt = QLineEdit()
        self.txt.setObjectName('campoClave')
        self.txt.setPlaceholderText('XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX')
        mono = QFont('Consolas')
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPixelSize(17)
        self.txt.setFont(mono)
        self.txt.setMinimumHeight(56)
        self.txt.textChanged.connect(self._al_escribir)
        self.caja = _CajaSacudible(self.txt)
        v.addWidget(self.caja)
        v.addSpacing(7)
        self.chip = etiqueta('', 12, C['suave'], 'medio')
        self.chip.setFixedHeight(20)
        v.addWidget(self.chip)
        v.addSpacing(9)
        self.boton = _BotonActivar()
        v.addWidget(self.boton)
        v.addSpacing(10)
        self.msg = etiqueta('', 13, C['suave'], 'medio', envolver=True)
        self.msg.setMinimumHeight(36)
        self.msg.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self.msg)
        # licencia ya activa: «Desactivar este equipo» va aquí (en el pie no cabe junto al ID)
        fila_des = QHBoxLayout()
        fila_des.setContentsMargins(0, 4, 0, 0)
        self.b_desactivar = QPushButton('  ' + tr('Desactivar este equipo'))
        self.b_desactivar.setObjectName('btnPeligro')
        ic = ui.icono_linea('ph.sign-out-bold', '#FF8A80', '#FFFFFF')
        if ic is not None:
            self.b_desactivar.setIcon(ic)
            self.b_desactivar.setIconSize(QSize(15, 15))
        self.b_desactivar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_desactivar.setToolTip(tr('Libera esta computadora para activar tu licencia en otra'))
        self.b_desactivar.hide()
        fila_des.addWidget(self.b_desactivar)
        fila_des.addStretch(1)
        v.addLayout(fila_des)
        v.addStretch(1)
        sep = QFrame()
        sep.setObjectName('sepLic')
        sep.setFixedHeight(1)
        v.addWidget(sep)
        v.addSpacing(12)
        tiendas = licencia.tiendas()
        self.botones_tienda = []
        self.fila_compra = QWidget()
        fila = QHBoxLayout(self.fila_compra)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(8)
        fila.addWidget(etiqueta(tr('¿Aún no tienes licencia?'), 13, C['texto'], 'medio'))
        fila.addStretch(1)
        for nombre, url in tiendas:
            texto = tr('Comprar en {tienda}', tienda=nombre) if len(tiendas) > 1 else tr('Comprar licencia')
            b = QPushButton('  ' + texto)
            b.setObjectName('btnTienda')
            ic = ui.icono_linea('ph.shopping-cart-simple-bold', '#DCE6F5')
            if ic is not None:
                b.setIcon(ic)
                b.setIconSize(QSize(16, 16))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(url)
            fila.addWidget(b)
            self.botones_tienda.append((b, url))
        self.fila_compra.setVisible(bool(tiendas))
        v.addWidget(self.fila_compra)
        v.addSpacing(6)
        self.nota_hotmart = etiqueta(tr('Tu clave de licencia te llega por correo al comprar en Gumroad.'
                                        ''), 12, C['tenue'], envolver=True)
        v.addWidget(self.nota_hotmart)
        v.addSpacing(12)
        pie = QHBoxLayout()
        pie.setSpacing(8)
        self.lbl_id = QLabel(tr('ID del equipo') + '  ·  ' + licencia.id_equipo())
        self.lbl_id.setObjectName('chipId')
        self.lbl_id.setToolTip(tr('ID de esta computadora (dáselo al vendedor si necesitas ayuda con tu licencia)'))
        self.lbl_id.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # el ancho justo de su texto a 12 px + relleno (12+12) y borde: nunca se corta ni se estira
        self.lbl_id.setFixedWidth(int(QFontMetricsF(fuente(12)).horizontalAdvance(self.lbl_id.text())) + 34)
        pie.addWidget(self.lbl_id)
        self.b_copiar = QPushButton()
        self.b_copiar.setObjectName('btnIcono')
        ic = ui.icono_linea('ph.copy-bold', '#B7C4DA', '#FFFFFF')
        if ic is not None:
            self.b_copiar.setIcon(ic)
            self.b_copiar.setIconSize(QSize(14, 14))
        else:
            self.b_copiar.setText('⧉')
        self.b_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_copiar.setToolTip(tr('Copiar el ID de esta computadora (para soporte)'))
        pie.addWidget(self.b_copiar)
        pie.addStretch(1)
        self.b_wa = None
        if licencia.LIC_WHATSAPP:
            self.b_wa = QPushButton('  ' + tr('Ayuda por WhatsApp'))
            self.b_wa.setObjectName('btnLink')
            ic = ui.icono_linea('ph.whatsapp-logo-bold', '#24D18F')
            if ic is not None:
                self.b_wa.setIcon(ic)
            self.b_wa.setCursor(Qt.CursorShape.PointingHandCursor)
            pie.addWidget(self.b_wa)
        self.b_salir = QPushButton(tr('Salir'))
        self.b_salir.setObjectName('btnLink')
        self.b_salir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_salir.clicked.connect(self.reject)
        pie.addWidget(self.b_salir)
        v.addLayout(pie)

    # ---- geometría y ciclo
    def _medidas(self):
        cw, ch = min(self.CARTA[0], self.width() - 40.0), min(self.CARTA[1], self.height() - 40.0)
        heroe = 320.0 if cw >= 820.0 else max(230.0, cw * 0.36)
        return cw, ch, heroe

    def _rect_carta(self):
        cw, ch, _h = self._medidas()
        k = min(1.0, (time.monotonic() - self._t0) / 0.52) if self.animado else 1.0
        dy = 30.0 * (1.0 - k) ** 3                 # entra subiendo
        return QRectF((self.width() - cw) / 2.0, (self.height() - ch) / 2.0 + dy, cw, ch)

    def _rect_heroe(self, r=None):
        r = r or self._rect_carta()
        return QRectF(r.left(), r.top(), self._medidas()[2], r.height())

    def _ubicar(self):
        if self.__dict__.get('capa') is None:
            return
        r = self._rect_carta()
        x = r.left() + self._medidas()[2] + 40.0
        self.panel.setGeometry(int(x), int(r.top() + 40.0), int(r.right() - 36.0 - x), int(r.height() - 40.0 - 24.0))
        self.b_x.move(int(r.right() - self.b_x.width() - 14), int(r.top() + 14))
        self.b_x.raise_()
        self.capa.setGeometry(self.rect())
        self.capa.raise_()

    def showEvent(self, e):
        super().showEvent(e)
        self._t0 = self._t_prev = time.monotonic()
        self._ubicar()
        self.reloj.start()

    def hideEvent(self, e):
        self.reloj.stop()
        super().hideEvent(e)

    def resizeEvent(self, e):
        self._ubicar()
        super().resizeEvent(e)

    def _tic(self):
        ahora = time.monotonic()
        dt = max(0.0, min(0.05, ahora - self._t_prev))
        self._t_prev = ahora
        if self.isMinimized():
            return
        t = ahora - self._t0
        if t < 0.7:
            self._ubicar()
        if self._t_sacudida is not None:
            k = ahora - self._t_sacudida
            if k > 0.55:
                self._t_sacudida = None
                self.caja.poner_dx(0.0)
            else:
                self.caja.poner_dx(12.0 * math.sin(k * 44.0) * math.exp(-k * 6.0))
        self.boton.avanzar(dt)
        if self.capa.activa():
            self.capa.avanzar(dt)
        rapido = (self.capa.activa() or t < 0.7 or self.estado == 'ocupado' or self._t_sacudida is not None
                  or ahora - self._t_estado < 1.3)
        self.reloj.setInterval(16 if rapido else 33)
        r = self._rect_carta()
        self.update((r.adjusted(-40.0, -40.0, 40.0, 50.0) if t < 0.7
                     else self._rect_heroe(r).adjusted(-2, -2, 2, 2)).toAlignedRect())

    # ---- dibujo
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        t = time.monotonic() - self._t0
        r = self._rect_carta()
        radio = 26.0
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(9):                         # sombra suave alrededor de la tarjeta
            m = 3.0 + i * 3.0
            p.setBrush(col_fijo('#000000', 0.05 * (1.0 - i / 9.0)))
            p.drawRoundedRect(r.adjusted(-m, -m + 6.0, m, m + 6.0), radio + m, radio + m)
        carta = QPainterPath()
        carta.addRoundedRect(r, radio, radio)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0.0, col('#0D1627'))
        g.setColorAt(1.0, col('#070B13'))
        p.fillPath(carta, QBrush(g))
        hr = self._rect_heroe(r)
        p.save()
        p.setClipPath(carta)
        p.setClipRect(hr, Qt.ClipOperation.IntersectClip)
        self._pintar_heroe(p, hr, t)
        p.restore()
        lg = QLinearGradient(QPointF(0.0, r.top()), QPointF(0.0, r.bottom()))
        lg.setColorAt(0.0, col('#4589FF', 0.0))
        lg.setColorAt(0.5, col('#4589FF', 0.40))
        lg.setColorAt(1.0, col('#4589FF', 0.0))
        p.setPen(QPen(QBrush(lg), 1.0))
        p.drawLine(QPointF(hr.right(), r.top() + 24.0), QPointF(hr.right(), r.bottom() - 24.0))
        borde = col('#22324F', 0.95)
        if self.estado == 'ok':
            borde = col(C['ok'], 0.55 + 0.35 * math.exp(-(time.monotonic() - self._t_estado) * 1.5))
        p.setPen(QPen(borde, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(carta)

    def _pintar_heroe(self, p, hr, t):
        g = QLinearGradient(hr.topLeft(), hr.bottomRight())
        g.setColorAt(0.0, col('#0B3A8C'))
        g.setColorAt(0.5, col('#0A1A3A'))
        g.setColorAt(1.0, col('#1C1442'))
        p.fillRect(hr, QBrush(g))
        mov = t if self.animado else 0.0
        for i, (fx, fy, rad, color, vel) in enumerate(((0.25, 0.22, 0.75, '#4589FF', 0.21),
                                                       (0.85, 0.78, 0.80, '#B388FF', 0.17),
                                                       (0.60, 0.45, 0.55, '#00C8FF', 0.13))):
            cx = hr.left() + hr.width() * (fx + 0.12 * math.sin(mov * vel * 2.0 + i))
            cy = hr.top() + hr.height() * (fy + 0.08 * math.cos(mov * vel * 1.6 + i * 2.0))
            rg = QRadialGradient(QPointF(cx, cy), hr.width() * rad)
            rg.setColorAt(0.0, col(color, 0.30))
            rg.setColorAt(1.0, col(color, 0.0))
            p.fillRect(hr, QBrush(rg))
        p.setPen(Qt.PenStyle.NoPen)
        for fx, fy, rad, vel, fase, color in self._luces:     # luces que suben
            k = (fy + mov * vel) % 1.0
            x = hr.left() + hr.width() * fx + 10.0 * math.sin(mov * 0.8 + fase)
            y = hr.bottom() + 20.0 - k * (hr.height() + 40.0)
            a = 0.55 * math.sin(math.pi * k) * (0.6 + 0.4 * math.sin(mov * 2.0 + fase))
            p.setBrush(col(color, max(0.0, a)))
            p.drawEllipse(QPointF(x, y), rad * 0.5, rad * 0.5)
        ex, ey = hr.center().x(), hr.top() + 158.0
        self._pintar_emblema(p, ex, ey, t)
        # la marca: «Cine» en blanco + «Captions» en azul (como el banner del instalador)
        f = fuente(30, 'extra')
        p.setFont(f)
        fm = QFontMetricsF(f)
        a1, a2 = fm.horizontalAdvance('Cine'), fm.horizontalAdvance('Captions')
        x0 = hr.center().x() - (a1 + a2) / 2.0
        caja = QRectF(x0, ey + 86.0, a1 + a2 + 4.0, 40.0)
        p.setPen(col(C['texto']))
        p.drawText(caja, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, 'Cine')
        p.setPen(col(C['acento']))
        p.drawText(caja.adjusted(a1, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, 'Captions')
        centro = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        p.setPen(col(C['cian'], 0.85))
        p.setFont(fuente(11, 'negrita', 3.0))
        p.drawText(QRectF(hr.left(), ey + 126.0, hr.width(), 20.0), centro, tr('LICENCIA') + '  ·  v%s' % self.version)
        y = hr.bottom() - 40.0 - 34.0 * (len(self.beneficios) - 1)
        for texto in self.beneficios:
            x = hr.left() + (38.0 if hr.width() >= 300 else 24.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col(C['cian'], 0.18))
            p.drawEllipse(QPointF(x + 10.0, y), 10.0, 10.0)
            pen = QPen(col(C['cian']), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPolyline(QPolygonF([QPointF(x + 5.5, y + 0.5), QPointF(x + 9.0, y + 4.0), QPointF(x + 15.0, y - 3.5)]))
            p.setPen(col(C['texto'], 0.86))
            ancho = hr.right() - (x + 30.0) - 14.0
            for px in (13, 12, 11):                     # textos largos (alemán...): un poco más chica antes de cortar
                fb = fuente(px, 'medio')
                if QFontMetricsF(fb).horizontalAdvance(texto) <= ancho:
                    break
            p.setFont(fb)
            p.drawText(QRectF(x + 30.0, y - 12.0, ancho, 24.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       QFontMetricsF(fb).elidedText(texto, Qt.TextElideMode.ElideRight, ancho))
            y += 34.0

    def _color_estado(self):
        if self.estado == 'ok':
            return col(C['ok'])
        if self.estado == 'error' and time.monotonic() - self._t_estado < 1.2:
            return col(C['rojo'])
        return col(C['acento'])

    @staticmethod
    def _trazo_parcial(p, pts, prog, color, ancho):
        """Dibuja la línea pts hasta la fracción prog de su largo (la palomita que se dibuja sola)."""
        largos = [math.hypot(b.x() - a.x(), b.y() - a.y()) for a, b in zip(pts, pts[1:])]
        resta = max(0.0, min(1.0, prog)) * sum(largos)
        dibujo = [pts[0]]
        for (a, b), L in zip(zip(pts, pts[1:]), largos):
            if resta <= 0.0:
                break
            f = min(1.0, resta / L) if L else 1.0
            dibujo.append(QPointF(a.x() + (b.x() - a.x()) * f, a.y() + (b.y() - a.y()) * f))
            resta -= L
        pen = QPen(color, ancho)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if len(dibujo) > 1:
            p.drawPolyline(QPolygonF(dibujo))

    def _pintar_llave(self, p, lado):
        pm = pix_icono('ph.key-fill', '#FFD36E', int(lado))
        if pm is not None:
            p.drawPixmap(QRectF(-lado / 2.0, -lado / 2.0, lado, lado), pm, QRectF(pm.rect()))
            return
        pen = QPen(col_fijo('#FFD36E'), 6.0)                 # sin QtAwesome: una llave dibujada
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(-12.0, -8.0), 11.0, 11.0)
        p.drawLine(QPointF(-4.0, 0.0), QPointF(20.0, 22.0))
        p.drawLine(QPointF(12.0, 15.0), QPointF(6.0, 21.0))

    def _pintar_emblema(self, p, x, y, t):
        R = 56.0
        c = self._color_estado()
        k_est = time.monotonic() - self._t_estado
        mov = t if self.animado else 0.0
        pulso = 0.75 + 0.25 * math.sin(mov * 2.2)
        if self.estado == 'ok':
            pulso = 1.0 + 0.7 * math.exp(-k_est * 2.5)
        elif self.estado == 'error' and k_est < 1.2:
            pulso = 1.0 + 0.5 * abs(math.sin(k_est * 9.0)) * math.exp(-k_est * 2.0)
        halo = QRadialGradient(QPointF(x, y), R * 2.3)
        h0, h1 = QColor(c), QColor(c)
        h0.setAlphaF(min(1.0, 0.34 * pulso))
        h1.setAlphaF(0.0)
        halo.setColorAt(0.0, h0)
        halo.setColorAt(1.0, h1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(x, y), R * 2.3, R * 2.3)
        p.setBrush(col('#060C18', 0.92))
        p.setPen(QPen(col_fijo('#FFFFFF', 0.10), 1.0))
        p.drawEllipse(QPointF(x, y), R, R)
        ang = (t * (420.0 if self.estado == 'ocupado' else 80.0)) % 360.0
        cg = QConicalGradient(QPointF(x, y), -ang)
        for pos, a in ((0.0, 1.0), (0.30, 0.0), (0.70, 0.0), (1.0, 0.9)):
            cc = QColor(c)
            cc.setAlphaF(a)
            cg.setColorAt(pos, cc)
        pen = QPen(QBrush(cg), 4.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(x, y), R + 9.0, R + 9.0)        # anillo de luz que gira
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(3):                                      # puntitos en órbita contraria
            a = math.radians(-ang * 0.55 + i * 120.0)
            cc = QColor(c)
            cc.setAlphaF(0.75)
            p.setBrush(cc)
            p.drawEllipse(QPointF(x + math.cos(a) * (R + 24.0), y + math.sin(a) * (R + 24.0)), 3.0, 3.0)
        if self.estado == 'ok':
            self._trazo_parcial(p, [QPointF(x - 24.0, y + 1.0), QPointF(x - 7.0, y + 18.0), QPointF(x + 25.0, y - 17.0)],
                                k_est / 0.45, col_fijo('#FFFFFF'), 7.0)
        else:
            p.save()
            p.translate(x, y + math.sin(mov * 1.7) * 3.0)
            if self.estado == 'ocupado':
                p.rotate(math.sin(t * 7.0) * 10.0)             # la llave «gira en la cerradura»
            self._pintar_llave(p, 62.0)
            p.restore()

    # ---- estados (los usa DialogoLicencia)
    def mensaje(self, texto, tipo='info'):
        color = {'error': C['rojo'], 'ok': C['ok'], 'aviso': C['naranja']}.get(tipo, C['suave'])
        self.msg.setStyleSheet('color:%s;background:transparent;' % ui.tc(color))
        self.msg.setText(texto)

    def _campo_estado(self, estado):
        self.txt.setProperty('estado', estado)
        st = self.txt.style()
        st.unpolish(self.txt)
        st.polish(self.txt)
        self.txt.update()

    def _chip(self, texto, color):
        self.chip.setStyleSheet('color:%s;background:transparent;' % ui.tc(color))
        self.chip.setText(texto)

    def _al_escribir(self, texto):
        if self.estado == 'ok' or self.modo_activa:
            return
        if self.txt.property('estado'):
            self._campo_estado('')
        if self.estado == 'error':
            self.estado = 'normal'
        k = re.sub(r'\s+', '', texto or '')
        tipo = licencia.tipo_de_clave(k)
        aviso, color = '', C['suave']
        if not k:
            pass
        elif tipo == 'ls':
            aviso, color = '✓  ' + tr('Clave de Lemon Squeezy'), C['ok']
        elif tipo == 'gumroad':
            aviso, color = (('✓  ' + tr('Clave de Gumroad'), C['ok']) if licencia.LIC_GUMROAD_PRODUCTO else
                            (tr('Clave de Gumroad: CineCaptions todavía no se vende ahí'), C['naranja']))
        elif tipo == 'hotmart':
            aviso, color = tr('Eso es tu número de compra de Hotmart: pide tu clave al vendedor'), C['naranja']
        elif len(k) >= 10:
            aviso, color = tr('Revisa la clave: cópiala tal cual del correo de tu compra'), C['tenue']
        self._chip(aviso, color)

    def ocupado(self, si, texto=None):
        self.txt.setEnabled(not si and not self.modo_activa)
        self.b_desactivar.setEnabled(not si)
        if si:
            self.estado, self._t_estado = 'ocupado', time.monotonic()
            self.boton.setEnabled(False)
            self.boton.poner_modo('ocupado', texto or tr('Activando…'))
        else:
            if self.estado == 'ocupado':
                self.estado = 'normal'
            self.boton.setEnabled(True)
            if self.modo_activa:
                self.estado = 'ok'
                self.boton.poner_modo('ok', tr('Listo'))
            else:
                self.boton.poner_modo('normal', tr('Activar licencia'))

    def fallar(self, texto, tipo='error'):
        self.ocupado(False)
        self.estado, self._t_estado = 'error', time.monotonic()
        self.mensaje(texto, tipo)
        if tipo == 'error':
            self._t_sacudida = time.monotonic()
            self._campo_estado('error')
        self.txt.setFocus()
        self.txt.selectAll()

    def celebrar(self, datos=None, confeti=True):
        self.estado, self._t_estado = 'ok', time.monotonic()
        self.txt.deselect()
        self.txt.setEnabled(False)
        self._campo_estado('ok')
        self.boton.setEnabled(True)
        self.boton.poner_modo('ok', tr('¡Listo! A crear subtítulos'))
        nombre = (str((datos or {}).get('cliente') or '').strip().split() or [''])[0]
        self.lbl_tit.setText(tr('¡Licencia activada!'))
        self.lbl_sub.setText((tr('¡Bienvenido(a), {nombre}!', nombre=nombre) + ' ' if nombre else '')
                             + tr('Ya puedes crear tus subtítulos.'))
        self.mensaje('✓  ' + tr('CineCaptions quedó activado en esta computadora.'), 'ok')
        self._chip('', C['suave'])
        if confeti and self.animado:
            self._explosion()

    def mostrar_activa(self, datos):
        """La licencia YA está activa: la misma tarjeta con sus datos y «Desactivar este equipo»."""
        self.modo_activa = True
        self.estado, self._t_estado = 'ok', time.monotonic() - 0.2
        self.lbl_tit.setText(tr('Tu licencia está activa'))
        quien = str(datos.get('cliente') or datos.get('correo') or '').strip()
        tienda = licencia.tienda_de(datos)
        self.lbl_sub.setText(tr('A nombre de {quien} · {tienda}', quien=quien, tienda=tienda) if quien
                             else tr('Licencia de {tienda}', tienda=tienda))
        self.txt.blockSignals(True)
        self.txt.setText(licencia.clave_enmascarada(datos.get('clave')))
        self.txt.blockSignals(False)
        self.txt.setEnabled(False)
        self._campo_estado('ok')
        self.boton.setEnabled(True)
        self.boton.poner_modo('ok', tr('Listo'))
        self._pintar_datos(datos)
        self.fila_compra.hide()
        self.nota_hotmart.hide()
        self.b_desactivar.show()
        self.b_salir.setText(tr('Cerrar'))

    def _pintar_datos(self, datos):
        partes = []
        if datos.get('ultima_ok'):
            partes.append(tr('Verificada el {cuando}', cuando=time.strftime('%d/%m/%Y %H:%M',
                                                                             time.localtime(float(datos['ultima_ok'])))))
        if datos.get('usados') is not None:
            partes.append(tr('{u} de {m} computadoras', u=datos.get('usados'), m=datos.get('limite') or '∞'))
        self._chip('✓  ' + '  ·  '.join(partes) if partes else '', C['ok'])
        lineas = []
        vence = licencia._fecha(datos.get('expira_ts')) or tr('nunca')
        if datos.get('correo'):
            lineas.append(tr('Correo: {correo}', correo=datos['correo']) + '  ·  ' + tr('Vence: {cuando}', cuando=vence))
        else:
            lineas.append(tr('Vence: {cuando}', cuando=vence))
        if datos.get('prueba'):
            lineas.append(tr('Clave de PRUEBA (modo de pruebas de la tienda).'))
        self.mensaje('\n'.join(lineas), 'info')

    def mostrar_activar(self, texto='', tipo='info'):
        """Vuelve al modo «Activa tu licencia» (después de desactivar este equipo)."""
        self.modo_activa = False
        self.estado, self._t_estado = 'normal', time.monotonic()
        self.lbl_tit.setText(tr('Activa tu licencia'))
        self.lbl_sub.setText(tr('Pega la clave que te llegó por correo al comprar. Se activa en esta computadora '
                                'en segundos.'))
        self.txt.setEnabled(True)
        self.txt.clear()
        self._campo_estado('')
        self.boton.setEnabled(True)
        self.boton.poner_modo('normal', tr('Activar licencia'))
        self._chip('', C['suave'])
        self.mensaje(texto, tipo)
        self.fila_compra.setVisible(bool(self.botones_tienda))
        self.nota_hotmart.show()
        self.b_desactivar.hide()
        self.b_salir.setText(tr('Salir'))
        self.txt.setFocus()

    def _explosion(self):
        """Clave correcta: cañón de confeti desde el botón, estallido desde el emblema y dos cañones
        desde los lados."""
        r = self._rect_carta()
        hr = self._rect_heroe(r)
        c = self.boton.mapTo(self, self.boton.rect().center())
        self.capa.setGeometry(self.rect())
        self.capa.lanzar(c.x(), c.y(), 120, -160.0, -20.0)
        ex, ey = hr.center().x(), hr.top() + 158.0
        QTimer.singleShot(170, self, lambda: self.capa.lanzar(ex, ey, 90, 0.0, 360.0, 300.0, 900.0))
        QTimer.singleShot(340, self, lambda: (
            self.capa.lanzar(r.left() + 6.0, r.top() + r.height() * 0.55, 60, -80.0, -25.0, 700.0, 1350.0, False),
            self.capa.lanzar(r.right() - 6.0, r.top() + r.height() * 0.55, 60, -155.0, -100.0, 700.0, 1350.0, False)))
        self.reloj.setInterval(16)

    # ---- teclado y ratón
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._rect_carta().contains(e.position()):
            h = self.windowHandle()
            if h is not None:
                h.startSystemMove()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.estado == 'ok':
                self.accept()
            return                                  # Enter en la clave ya activa (returnPressed)
        if e.key() == Qt.Key.Key_Escape:
            self.accept() if self.estado == 'ok' else self.reject()
            return
        super().keyPressEvent(e)


class DialogoLicencia:
    """
    Activar CineCaptions: la LÓGICA (tienda en un hilo aparte, mensajes, cerrar al activarse). La
    ventana es VentanaLicencia. Con verificar=True primero comprueba la licencia guardada en
    segundo plano y, si sigue valiendo, se cierra sola. Con la licencia ya vigente muestra sus
    datos (y la vuelve a verificar en segundo plano).
    ejecutar() -> True si al cerrar hay una licencia vigente.
    """

    def __init__(self, padre=None, motivo='', verificar=False):
        self.padre, self.ok, self.cambio, self._relojes = padre, False, False, []
        v = self.v = VentanaLicencia(padre)
        v.boton.clicked.connect(self._clic_boton)
        v.txt.returnPressed.connect(self._clic_boton)
        v.b_copiar.clicked.connect(self._copiar_id)
        v.b_desactivar.clicked.connect(self._desactivar)
        for b, url in v.botones_tienda:
            b.clicked.connect(lambda _c=False, u=url: self._abrir(u))
        if v.b_wa is not None:
            v.b_wa.clicked.connect(self._whatsapp)
        guardada = licencia.local()
        if guardada and licencia._vigente(guardada) and not motivo:
            self.ok = True
            v.mostrar_activa(guardada)
            QTimer.singleShot(400, v, lambda: self._trabajar(licencia.comprobar, self._fin_refrescar))
            return
        if guardada:
            v.txt.setText(str(guardada.get('clave') or ''))
        if motivo:
            v.mensaje(motivo, 'error')
        if verificar and guardada:
            v.ocupado(True, tr('Verificando tu licencia…'))
            v.mensaje(tr('Verificando tu licencia con la tienda…'), 'info')
            QTimer.singleShot(350, v, lambda: self._trabajar(licencia.comprobar, self._fin_verificar))
        else:
            QTimer.singleShot(0, v, v.txt.setFocus)

    def _clic_boton(self):
        if self.v.estado == 'ok':
            self.v.accept()
        elif self.v.estado != 'ocupado':
            self.activar()

    def _abrir(self, url):
        """La tienda se abre ENCIMA: esta ventana deja de estar por encima de todo."""
        try:
            if self.v.windowFlags() & Qt.WindowType.WindowStaysOnTopHint:
                geo = self.v.geometry()
                self.v.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
                self.v.setGeometry(geo)
                self.v.show()
            if self.padre is not None and hasattr(self.padre, 'poner_encima'):
                self.padre.poner_encima(False)
        except Exception:
            pass
        QDesktopServices.openUrl(QUrl(url))

    def _copiar_id(self):
        QApplication.clipboard().setText('CineCaptions · %s' % licencia.nombre_equipo())
        self.v.mensaje(tr('ID de esta computadora copiado.'), 'info')

    def _whatsapp(self):
        import urllib.parse
        texto = tr('Hola, necesito ayuda con mi licencia de CineCaptions.') + '\n' + \
            tr('ID de mi computadora: {id}', id=licencia.nombre_equipo())
        self._abrir('https://wa.me/%s?text=%s' % (re.sub(r'\D', '', licencia.LIC_WHATSAPP), urllib.parse.quote(texto)))

    def _trabajar(self, funcion, al_terminar, *args):
        """La tienda se consulta en un hilo aparte: la ventana nunca se congela (hasta 12 s sin
        internet)."""
        caja = {'r': None}

        def hilo():
            caja['r'] = licencia.seguro(funcion, *args)
        threading.Thread(target=hilo, daemon=True, name='licencia').start()
        reloj = QTimer(self.v)
        reloj.setInterval(100)

        def tic():
            if caja['r'] is not None:
                reloj.stop()
                if ui.vivo(self.v):
                    al_terminar(caja['r'])
        reloj.timeout.connect(tic)
        reloj.start()
        self._relojes.append(reloj)

    def activar(self):
        clave = self.v.txt.text().strip()
        if not clave:
            self.v.fallar(tr('Escribe (o pega) tu clave de licencia.'), 'error')
            return
        self.v.ocupado(True, tr('Activando…'))
        self.v.mensaje(tr('Activando con la tienda…'), 'info')
        self._trabajar(licencia.activar, self._fin_activar, clave)

    def _cerrar_ok(self):
        if ui.vivo(self.v) and self.v.isVisible():
            self.v.accept()

    def _fin_activar(self, r):
        if r.ok:
            self.ok = self.cambio = True
            self.v.celebrar(r.datos)
            QTimer.singleShot(4200 if self.v.animado else 1500, self.v, self._cerrar_ok)   # termina el confeti
        else:
            self.v.fallar(r.mensaje, 'aviso' if r.codigo == 'sin_conexion' else 'error')

    def _fin_verificar(self, r):
        if r.ok:
            self.ok = True
            self.v.celebrar(r.datos, confeti=False)
            QTimer.singleShot(900, self.v, self._cerrar_ok)
        else:
            self.v.fallar(r.mensaje, 'aviso' if r.codigo == 'sin_conexion' else 'error')

    def _fin_refrescar(self, r):
        """Licencia activa: se verificó otra vez en segundo plano (sin red, nada cambia)."""
        if r.ok and r.codigo == 'activa' and self.v.modo_activa:
            self.v._pintar_datos(r.datos)
        elif not r.ok and r.codigo in licencia.CODIGOS_DEFINITIVOS:
            self.ok, self.cambio = False, True
            self.v.mostrar_activar(r.mensaje, 'error')

    def _desactivar(self):
        if not ui.messagebox.askyesno(tr('Desactivar este equipo'),
                                      tr('CineCaptions dejará de funcionar en esta computadora hasta que vuelvas a '
                                         'activarla, y tu licencia quedará libre para usarla en otra.\n\n¿Desactivar?'),
                                      parent=self.v):
            return
        self.v.ocupado(True, tr('Desactivando…'))
        self.v.mensaje(tr('Liberando esta computadora en la tienda…'), 'info')
        self._trabajar(licencia.desactivar, self._fin_desactivar)

    def _fin_desactivar(self, r):
        if r.ok:
            self.ok, self.cambio = False, True
            self.v.mostrar_activar('✓  ' + r.mensaje, 'ok')
        else:
            self.v.ocupado(False)
            self.v.mensaje(r.mensaje, 'aviso' if r.codigo == 'sin_conexion' else 'error')

    def ejecutar(self):
        self.v.exec()
        for reloj in self._relojes:
            try:
                reloj.stop()
            except RuntimeError:
                pass
        self.v.deleteLater()
        return bool(licencia.vigente())
