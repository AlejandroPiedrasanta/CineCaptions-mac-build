# CineCaptions · By Cinema Productions
# 1_codigo/registro_ui.py — el aviso en la barra de título, el botón del registro con contador y la ventana Registro.
"""
registro_ui.py
--------------
  * SubtituloVivo   — ocupa el sitio del subtítulo de la barra de título de cada pantalla. Normalmente muestra la línea de apoyo;
                      cuando llega una nota, un aviso o un error (registro.py) el texto sube y entra el aviso con su icono,
                      un barrido de luz del color del nivel, y vuelve solo a la línea de apoyo. Un clic abre el Registro.
  * BotonRegistro   — el botón junto al «?»: un contador (rojo = errores, ámbar = avisos) que da un saltito al llegar uno nuevo.
  * DialogoRegistro — el historial completo: filtros, copiar, abrir el archivo (cinecaptions.log) y limpiar.
"""
import html
import math
import os
import sys

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QFontMetricsF, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QPlainTextEdit, QScrollArea, QSizePolicy, QTextEdit,
                               QVBoxLayout, QWidget)

import qt_kit as ui
from qt_kit import Boton, Dialogo, Etiqueta, QColor, Segmentado, StringVar, Tooltip, caja_h, caja_v
import registro
from i18n import tr

COLOR_NIVEL = {'info': '#4589FF', 'ok': '#24D18F', 'aviso': '#F5B84B', 'error': '#FF6B6B'}
DURACION_MS = {'info': 5200, 'ok': 5200, 'aviso': 10000, 'error': 15000}


def _quieto():
    try:
        import efectos_ui
        return bool(efectos_ui.reducir_animaciones())
    except Exception:
        return False


def _icono_nivel(p, nivel, cx, cy, r, color, alfa=1.0):
    """El circulito con ✓ / i / ! / ✕ de cada nivel."""
    c = QColor(color)
    fondo = QColor(c)
    fondo.setAlpha(int(56 * alfa))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fondo)
    p.drawEllipse(QPointF(cx, cy), r, r)
    c.setAlpha(int(255 * alfa))
    p.setPen(QPen(c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    k = r / 9.0
    if nivel == 'ok':
        p.drawPolyline([QPointF(cx - 3.6 * k, cy + 0.2 * k), QPointF(cx - 1.0 * k, cy + 2.8 * k), QPointF(cx + 3.8 * k, cy - 2.6 * k)])
    elif nivel == 'error':
        p.drawLine(QPointF(cx - 3 * k, cy - 3 * k), QPointF(cx + 3 * k, cy + 3 * k))
        p.drawLine(QPointF(cx + 3 * k, cy - 3 * k), QPointF(cx - 3 * k, cy + 3 * k))
    elif nivel == 'aviso':
        p.drawLine(QPointF(cx, cy - 4.2 * k), QPointF(cx, cy + 1.2 * k))
        p.drawPoint(QPointF(cx, cy + 4.0 * k))
    else:
        p.drawPoint(QPointF(cx, cy - 3.8 * k))
        p.drawLine(QPointF(cx, cy - 1.0 * k), QPointF(cx, cy + 4.0 * k))
    p.setPen(Qt.PenStyle.NoPen)


class SubtituloVivo(QWidget):
    """La línea de apoyo de la barra de título, que además avisa. Compatible con la etiqueta que reemplaza
    (configure(text=...), setText, text)."""
    clic = Signal()

    def __init__(self, texto='', tam=13, color='#8D9BB5', padre=None):
        super().__init__(padre)
        self._texto = str(texto)
        self._color = QColor(color)
        self.setFont(ui.fuente(tam))
        self.setMinimumHeight(30)
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._compacto = False          # ventana angosta: solo se ven los avisos
        self._entrada = None
        self._k = 0.0                   # 0 = línea de apoyo, 1 = aviso
        self._barrido = 1.0             # 0..1 del barrido de luz (1 = sin barrido)
        self._a_k = QVariantAnimation(self)
        self._a_k.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_k.valueChanged.connect(self._paso_k)
        self._a_b = QVariantAnimation(self)
        self._a_b.setDuration(900)
        self._a_b.setStartValue(0.0)
        self._a_b.setEndValue(1.0)
        self._a_b.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._a_b.valueChanged.connect(self._paso_b)
        self._t_fin = QTimer(self)
        self._t_fin.setSingleShot(True)
        self._t_fin.timeout.connect(self._ocultar)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        registro.registro().nueva.connect(self._nuevo)

    # -- compatibilidad con Etiqueta
    def configure(self, text=None, text_color=None, **_):
        if text is not None:
            self.setText(text)
        if text_color is not None:
            self._color = QColor(text_color)
            self.update()

    def setText(self, texto):
        self._texto = str(texto)
        self.update()

    def text(self):
        return self._texto

    def poner_color(self, color):
        self._color = QColor(color)
        self.update()
    def poner_compacto(self, si):
        self._compacto = bool(si)
        self.update()

    # -- avisos
    def _nuevo(self, e):
        self._entrada = e
        self.setToolTip((e.mensaje + (f'\n{e.origen}' if e.origen else '') + '\n' + tr('Clic: abrir el registro')))
        self._animar_k(1.0, 280)
        if not _quieto():
            self._a_b.stop()
            self._a_b.start()
        self._t_fin.start(DURACION_MS.get(e.nivel, 5000))
        self.update()

    def _ocultar(self):
        self._animar_k(0.0, 420)

    def _animar_k(self, meta, ms):
        if _quieto():
            self._k = float(meta)
            self.update()
            return
        self._a_k.stop()
        self._a_k.setDuration(ms)
        self._a_k.setStartValue(self._k)
        self._a_k.setEndValue(float(meta))
        self._a_k.start()

    def _paso_k(self, v):
        self._k = float(v)
        self.update()

    def _paso_b(self, v):
        self._barrido = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        # al llegar a una pantalla: si hay un aviso reciente, se ve
        import time
        datos = registro.registro().lista()
        if datos and time.time() - datos[-1].tiempo < 9.0 and self._k < 0.01:
            self._nuevo(datos[-1])

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit()
            abrir_registro(self.window())
            e.accept()
            return
        super().mousePressEvent(e)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(int(QFontMetricsF(self.font()).horizontalAdvance(self._texto)) + 8, 30)

    def paintEvent(self, _e):
        W, H = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = QFontMetricsF(self.font())
        k = self._k
        e = self._entrada
        nivel = e.nivel if e else 'info'
        col = QColor(COLOR_NIVEL.get(nivel, '#4589FF'))
        # fondo del aviso
        if k > 0.01 and e is not None:
            fondo = QColor(col)
            fondo.setAlpha(int((34 if nivel == 'error' else 22) * k))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fondo)
            p.drawRoundedRect(QRectF(0, 3, W, H - 6), 9, 9)
            borde = QColor(col)
            borde.setAlpha(int((120 if nivel == 'error' else 70) * k))
            p.setPen(QPen(borde, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.5, 3.5, W - 1, H - 7), 9, 9)
            p.setPen(Qt.PenStyle.NoPen)
        # línea de apoyo: sube y se desvanece
        if k < 0.99 and not self._compacto:
            c = QColor(self._color)
            c.setAlpha(int(255 * (1.0 - k)))
            p.setPen(c)
            p.setFont(self.font())
            txt = fm.elidedText(self._texto, Qt.TextElideMode.ElideRight, W - 4)
            p.drawText(QRectF(2, -k * 12, W - 4, H), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), txt)
        # el aviso: entra desde abajo
        if k > 0.01 and e is not None:
            dy = (1.0 - k) * 12.0
            _icono_nivel(p, nivel, 20.0, H / 2 + dy, 8.5, col, k)
            hora = e.hora()
            ancho_hora = fm.horizontalAdvance(hora) + 14
            p.setFont(self.font())
            mt = QColor('#8D9BB5')
            mt.setAlpha(int(200 * k))
            p.setPen(mt)
            p.drawText(QRectF(W - ancho_hora - 8, dy, ancho_hora, H), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), hora)
            tx = QColor('#FFFFFF' if nivel in ('error', 'aviso') else '#E0EBFB')
            tx.setAlpha(int(255 * k))
            p.setPen(tx)
            mensaje = e.mensaje.replace('\n', ' ')
            if e.veces > 1:
                mensaje += f'  (×{e.veces})'
            txt = fm.elidedText(mensaje, Qt.TextElideMode.ElideRight, W - 44 - ancho_hora - 10)
            p.drawText(QRectF(38, dy, W - 44 - ancho_hora, H), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), txt)
            # barrido de luz del color del nivel
            b = self._barrido
            if b < 1.0:
                x = -80 + (W + 160) * b
                haz = QLinearGradient(x - 70, 0, x + 70, 0)
                c0 = QColor(col)
                c0.setAlpha(0)
                c1 = QColor('#FFFFFF')
                c1.setAlpha(int(90 * math.sin(b * math.pi)))
                haz.setColorAt(0.0, c0)
                haz.setColorAt(0.5, c1)
                haz.setColorAt(1.0, c0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(haz)
                p.drawRoundedRect(QRectF(0, 3, W, H - 6), 9, 9)
        p.end()


class BotonRegistro(QAbstractButton):
    """El botón del registro (junto al «?»): lista con contador; da un saltito cuando llega un aviso o un error."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr('Registro de avisos y errores'))
        self._hover = 0.0
        self._salto = 0.0
        self._a_h = QVariantAnimation(self)
        self._a_h.setDuration(160)
        self._a_h.valueChanged.connect(self._paso_h)
        self._a_s = QVariantAnimation(self)
        self._a_s.setDuration(700)
        self._a_s.setStartValue(0.0)
        self._a_s.setEndValue(1.0)
        self._a_s.valueChanged.connect(self._paso_s)
        reg = registro.registro()
        reg.nueva.connect(self._nuevo)
        reg.cambio.connect(self.update)
        self.clicked.connect(lambda: abrir_registro(self.window()))

    def _paso_h(self, v):
        self._hover = float(v)
        self.update()

    def _paso_s(self, v):
        self._salto = float(v)
        self.update()

    def _nuevo(self, e):
        if e.nivel in ('aviso', 'error') and not _quieto():
            self._a_s.stop()
            self._a_s.start()
        self.update()

    def enterEvent(self, e):
        self._a_h.stop()
        self._a_h.setStartValue(self._hover)
        self._a_h.setEndValue(1.0)
        self._a_h.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._a_h.stop()
        self._a_h.setStartValue(self._hover)
        self._a_h.setEndValue(0.0)
        self._a_h.start()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        avisos, errores = registro.registro().sin_leer()
        h = self._hover
        s = self._salto
        brinco = -4.0 * math.sin(s * math.pi) * (1.0 - s) if s < 1.0 else 0.0
        p.translate(0, brinco)
        borde = QColor(ui.mezclar('#1E2A42', '#4589FF', h * 0.8) if hasattr(ui, 'mezclar') else '#1E2A42')
        p.setPen(QPen(borde, 1.0))
        p.setBrush(QColor('#111D33' if h < 0.5 else '#14243F'))
        p.drawRoundedRect(QRectF(0.5, 0.5, 33, 33), 10, 10)
        # icono: tres renglones de registro con su viñeta; se desplazan al pasar el cursor
        col = QColor('#B4C0D6' if h < 0.5 else '#FFFFFF')
        p.setPen(QPen(col, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(3):
            y = 11.5 + i * 5.5
            dx = h * (1.5 if i % 2 else -1.5)
            p.drawPoint(QPointF(10.5, y))
            p.drawLine(QPointF(14.5 + dx, y), QPointF(23.5 + dx - (i == 2) * 3.5, y))
        # insignia con el número
        if errores or avisos:
            n = errores or avisos
            c = QColor('#FF6B6B' if errores else '#F5B84B')
            esc = 1.0 + 0.35 * math.sin(s * math.pi) if s < 1.0 else 1.0
            p.setPen(QPen(QColor('#0A1224'), 1.6))
            p.setBrush(c)
            p.save()
            p.translate(27, 7)
            p.scale(esc, esc)
            p.drawEllipse(QPointF(0, 0), 6.5, 6.5)
            p.restore()
            p.setPen(QColor('#10131A'))
            p.setFont(ui.fuente(9, peso='negrita'))
            p.drawText(QRectF(20.5, 0.5, 13, 13), int(Qt.AlignmentFlag.AlignCenter), str(min(n, 99)))
        p.end()


class TarjetaEntrada(QFrame):
    """Un aviso o error del Registro: título claro, qué pasó y qué hacer. Un clic en la cabecera la abre o la cierra."""
    def __init__(self, entrada, abierta, al_copiar, padre=None):
        super().__init__(padre)
        import registro_ayuda
        self._e = entrada
        self._ayuda = registro_ayuda.explicar(entrada)
        self._abierta = bool(abierta)
        self._al_copiar = al_copiar
        self._color = QColor(COLOR_NIVEL.get(entrada.nivel, '#4589FF'))
        self._hover = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        v = QVBoxLayout(self)
        v.setContentsMargins(58, 12, 16, 12)
        v.setSpacing(4)
        a = self._ayuda
        # cabecera: título + hora
        self._cab = QWidget()
        self._cab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        hc = QHBoxLayout(self._cab)
        hc.setContentsMargins(0, 0, 0, 0)
        hc.setSpacing(10)
        hc.addWidget(Etiqueta(a.titulo, 15, peso='negrita', color='#FFFFFF'), 1)
        veces = f'  ×{entrada.veces}' if entrada.veces > 1 else ''
        hc.addWidget(Etiqueta(entrada.hora() + veces, 12, color='#7F8DA8'))
        v.addWidget(self._cab)
        resumen = __import__('i18n').tr_libre(entrada.mensaje).replace('\n', ' ')
        if len(resumen) > 160:
            resumen = resumen[:157] + '…'
        self._resumen = Etiqueta(resumen, 12, color='#8D9BB5', envolver=True)
        self._resumen.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        v.addWidget(self._resumen)
        # cuerpo (solo abierta)
        self._cuerpo = QWidget()
        cb = QVBoxLayout(self._cuerpo)
        cb.setContentsMargins(0, 8, 0, 0)
        cb.setSpacing(6)
        import registro_ayuda as ra
        impacto = tr(ra.ETIQUETA_IMPACTO.get(a.impacto, ''))
        if a.que:
            cb.addWidget(Etiqueta(tr('Qué pasó'), 11, peso='negrita', color=COLOR_NIVEL.get(entrada.nivel, '#4589FF')))
            cb.addWidget(Etiqueta(a.que, 13, color='#DCE6F5', envolver=True, seleccionable=True))
        if impacto:
            cb.addWidget(Etiqueta(impacto, 12, peso='medio', color={'bloquea': '#FF8F8F', 'parcial': '#F5B84B'}.get(a.impacto, '#24D18F')))
        if a.pasos:
            cb.addSpacing(2)
            cb.addWidget(Etiqueta(tr('Qué hacer'), 11, peso='negrita', color='#24D18F'))
            for i, paso in enumerate(a.pasos, 1):
                cb.addWidget(Etiqueta(f'{i}.  {paso}', 13, color='#DCE6F5', envolver=True, seleccionable=True))
        if entrada.origen:
            cb.addSpacing(2)
            cb.addWidget(Etiqueta(tr('Dónde: {o}', o=entrada.origen), 12, color='#7F8DA8', envolver=True))
        fila, cf = caja_h(espacio=8)
        self._btn_det = Boton(tr('Ver detalle técnico'), self._alternar_detalle, alto=30, ancho=170, tam=12)
        cf.addWidget(self._btn_det)
        cf.addWidget(Boton(tr('Copiar este error'), lambda: self._al_copiar(self._e), alto=30, ancho=150, tam=12))
        cf.addStretch(1)
        cb.addWidget(fila)
        self._det = QPlainTextEdit()
        self._det.setReadOnly(True)
        self._det.setPlainText((entrada.detalle.strip() or entrada.mensaje))
        f = ui.fuente(11)
        f.setFamily('Consolas')
        self._det.setFont(f)
        self._det.setFixedHeight(130)
        self._det.setStyleSheet(ui.traducir_hoja('QPlainTextEdit { background-color: #070D1A; border: 1px solid #1E2A42; border-radius: 8px; padding: 6px; color: #9FB0CC; }'))
        self._det.hide()
        cb.addWidget(self._det)
        v.addWidget(self._cuerpo)
        self._cuerpo.setVisible(self._abierta)

    def _alternar_detalle(self):
        self._det.setVisible(not self._det.isVisible())
        self._btn_det.setText(tr('Ocultar detalle técnico') if self._det.isVisible() else tr('Ver detalle técnico'))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < self._cab.height() + self._resumen.height() + 26:
            self._abierta = not self._abierta
            self._cuerpo.setVisible(self._abierta)
            self.updateGeometry()
            self.update()
            e.accept()
            return
        super().mousePressEvent(e)

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
        c = self._color
        fondo = QColor(c)
        fondo.setAlpha(26 if self._abierta else (18 if self._hover else 10))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0E1628'))
        p.drawRoundedRect(r, 14, 14)
        p.setBrush(fondo)
        p.drawRoundedRect(r, 14, 14)
        borde = QColor(c)
        borde.setAlpha(110 if self._abierta else 55)
        p.setPen(QPen(borde, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 14, 14)
        _icono_nivel(p, self._e.nivel, 30.0, 26.0, 13.0, c)
        # flecha de abrir/cerrar
        p.setPen(QPen(QColor('#7F8DA8'), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = 30.0, 54.0
        if self._abierta:
            p.drawPolyline([QPointF(x - 4, y + 1.5), QPointF(x, y - 2.5), QPointF(x + 4, y + 1.5)])
        else:
            p.drawPolyline([QPointF(x - 4, y - 1.5), QPointF(x, y + 2.5), QPointF(x + 4, y - 1.5)])
        p.end()


class DialogoRegistro(Dialogo):
    """El historial de avisos y errores, explicado: cada anotación dice qué pasó y qué hacer."""
    MAXIMO = 120

    def __init__(self, padre=None):
        super().__init__(padre, tr('Registro'), 900, 640, redimensionable=True, minimo=(680, 460))
        self._nivel = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(24, 20, 24, 18)
        capa.setSpacing(12)
        cab, cc = caja_h(espacio=12)
        col, ct = caja_v(espacio=2)
        ct.addWidget(Etiqueta(tr('Registro'), 22, peso='extra', color='#FFFFFF'))
        ct.addWidget(Etiqueta(tr('Qué pasó en CineCaptions y qué hacer. Toca una tarjeta para ver los pasos.'), 13, color='#8D9BB5'))
        cc.addWidget(col, 1)
        self._opciones = [tr('Todo'), tr('Avisos'), tr('Errores')]
        self._var = StringVar(self._opciones[0])
        seg = Segmentado(self._opciones, self._var, self._filtrar, alto=34, tam=13)
        cc.addWidget(seg)
        capa.addWidget(cab)
        self._resumen = Etiqueta('', 13, peso='medio', color='#DCE6F5')
        capa.addWidget(self._resumen)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(ui.traducir_hoja('QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }'))
        self._lista = QWidget()
        self._cl = QVBoxLayout(self._lista)
        self._cl.setContentsMargins(0, 0, 8, 0)
        self._cl.setSpacing(10)
        self._cl.addStretch(1)
        self._scroll.setWidget(self._lista)
        capa.addWidget(self._scroll, 1)
        pie, cp = caja_h(espacio=10)
        self._cuenta = Etiqueta('', 12, color='#8D9BB5')
        cp.addWidget(self._cuenta, 1)
        cp.addWidget(Boton(tr('Copiar informe'), self._copiar, alto=38, ancho=140, tam=13))
        cp.addWidget(Boton(tr('Abrir el archivo'), self._abrir, alto=38, ancho=140, tam=13))
        cp.addWidget(Boton(tr('Limpiar'), self._limpiar, alto=38, ancho=100, tam=13))
        cp.addWidget(Boton(tr('Cerrar'), self.close, tipo='primario', alto=38, ancho=110, tam=13, negrita=True))
        capa.addWidget(pie)
        self._pendiente = QTimer(self)
        self._pendiente.setSingleShot(True)
        self._pendiente.timeout.connect(self._refrescar)
        registro.registro().nueva.connect(self._pedir_refresco)
        self._refrescar()
        registro.registro().marcar_leidas()

    def _pedir_refresco(self, *_):
        """Llega una anotación nueva con la ventana abierta: se repinta la lista (agrupando las ráfagas). Si la ventana ya se
        destruyó, se desengancha (una excepción aquí se anotaba a sí misma sin parar)."""
        try:
            self._pendiente.start(150)
        except RuntimeError:
            try:
                registro.registro().nueva.disconnect(self._pedir_refresco)
            except Exception:
                pass

    def _filtrar(self, _v=None):
        i = self._opciones.index(self._var.get())
        self._nivel = (None, 'aviso', 'error')[i]
        self._refrescar()

    def _datos(self):
        reg = registro.registro()
        if self._nivel == 'error':
            return [e for e in reg.lista() if e.nivel == 'error']
        if self._nivel == 'aviso':
            return [e for e in reg.lista() if e.nivel in ('aviso', 'error')]
        return reg.lista()

    def _refrescar(self, *_):
        datos = list(reversed(self._datos()))
        while self._cl.count() > 1:
            it = self._cl.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        todos = registro.registro().lista()
        n_err = sum(1 for e in todos if e.nivel == 'error')
        n_av = sum(1 for e in todos if e.nivel == 'aviso')
        if n_err:
            self._resumen.setText(tr('{n} errores y {m} avisos. Empieza por el más reciente.', n=n_err, m=n_av))
            self._resumen.poner_color('#FF8F8F')
        elif n_av:
            self._resumen.setText(tr('Sin errores. {m} avisos que puedes revisar.', m=n_av))
            self._resumen.poner_color('#F5B84B')
        else:
            self._resumen.setText(tr('Todo en orden: no hay errores ni avisos.'))
            self._resumen.poner_color('#24D18F')
        primero_error = True
        for e in datos[:self.MAXIMO]:
            abierta = primero_error and e.nivel == 'error'
            if e.nivel == 'error':
                primero_error = False
            self._cl.insertWidget(self._cl.count() - 1, TarjetaEntrada(e, abierta, self._copiar_una))
        if not datos:
            vacio = Etiqueta(tr('Sin avisos ni errores.'), 14, color='#6C7B96', alineacion=Qt.AlignmentFlag.AlignCenter)
            self._cl.insertWidget(0, vacio)
        extra = ' · ' + tr('mostrando las {n} más recientes', n=self.MAXIMO) if len(datos) > self.MAXIMO else ''
        self._cuenta.setText(tr('{n} anotaciones', n=len(datos)) + extra)
        registro.registro().marcar_leidas()

    @staticmethod
    def _bloque(e):
        import registro_ayuda
        a = registro_ayuda.explicar(e)
        partes = [e.linea(), f'  {a.titulo}']
        if a.que:
            partes.append(f'  {a.que}')
        partes += [f'  {i}. {p}' for i, p in enumerate(a.pasos, 1)]
        if e.detalle:
            partes.append('  --- detalle técnico ---')
            partes += [f'  {l}' for l in e.detalle.strip().splitlines()]
        return '\n'.join(partes)

    def _copiar_una(self, e):
        ui.copiar_al_portapapeles(self._cabecera() + '\n\n' + self._bloque(e))

    @staticmethod
    def _cabecera():
        try:
            import platform
            from version import APP_VERSION
            return f'CineCaptions v{APP_VERSION} · {platform.platform()}'
        except Exception:
            return 'CineCaptions'

    def _copiar(self):
        # v5.11: además de lo que se ve en pantalla, el informe de soporte (entorno Windows/Mac, librerías, errores.log, fallo nativo): lo que se necesita
        # para diagnosticar sin pedir nada más
        try:
            soporte = registro.reporte_soporte(80)
        except Exception:
            soporte = ''
        ui.copiar_al_portapapeles(self._cabecera() + '\n\n' + '\n\n'.join(self._bloque(e) for e in reversed(self._datos())) + ('\n\n' + soporte if soporte else ''))

    def _abrir(self):
        try:
            if registro.ruta_archivo().exists():
                if sys.platform.startswith('win'):
                    os.startfile(str(registro.ruta_archivo()))
                else:
                    import subprocess
                    subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(registro.ruta_archivo())])
        except Exception as ex:
            registro.aviso(tr('No pude abrir el archivo del registro: {e}', e=ex), 'registro')

    def _limpiar(self):
        registro.registro().limpiar()
        self._refrescar()


_ABIERTO = [None]


def abrir_registro(padre=None):
    """Abre (o trae al frente) la ventana Registro."""
    d = _ABIERTO[0]
    if d is not None and ui.vivo(d):
        d.traer()
        return d
    d = DialogoRegistro(padre)
    _ABIERTO[0] = d
    d.show()
    return d
