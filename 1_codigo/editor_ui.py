# CineCaptions · By Cinema Productions
# 1_codigo/editor_ui.py — piezas del editor Creativo: barra de herramientas, tarjeta del párrafo, palabras por línea, play y el panel de avance de Asistencia/Generar.
"""
  * BarraHerramientas  una sola barra de cristal con las herramientas en grupos separados por una línea fina (antes: 12 botones
                       sueltos, cada uno con su borde).
  * PanelTamanos       «Palabras por línea»: para Arriba / Principal / Abajo una fila con su color, cuadritos que muestran el MÁXIMO
                       permitido y un contador − n +. El bloque respeta siempre ese máximo (dynamic_subtitles.build_manual_cues).
"""
import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QConicalGradient, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
from i18n import tr
from qt_kit import Etiqueta, FlujoCapa, QColor, fuente


class BarraHerramientas(QFrame):
    """Contenedor de cristal para los botones de herramientas, con separadores entre grupos. Los hijos se añaden con agregar()/separador();
    lo que debe verse SIEMPRE (el tamaño del párrafo, «Generar») va a la derecha con agregar_fijo()."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setObjectName('barraHerr')
        self.setStyleSheet(ui.traducir_hoja('QFrame#barraHerr { background: rgba(255, 255, 255, 0.025); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 16px; }'))
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 10, 6)
        h.setSpacing(14)
        self._interior = QWidget()
        self._interior.setStyleSheet('background: transparent;')
        self.flujo = FlujoCapa(self._interior, 6, 6)
        h.addWidget(self._interior, 1)
        self._hueco = QWidget()                      # ocupa el sitio de las herramientas cuando están ocultas: lo fijo sigue a la derecha
        self._hueco.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hueco.setFixedHeight(1)
        self._hueco.hide()
        h.addWidget(self._hueco, 1)
        self._fijos = QHBoxLayout()
        self._fijos.setContentsMargins(0, 0, 0, 0)
        self._fijos.setSpacing(12)
        h.addLayout(self._fijos)

    def agregar(self, w):
        self.flujo.addWidget(w)

    addWidget = agregar                       # misma interfaz que un layout (los botones se añaden como siempre)

    def agregar_fijo(self, w):
        self._fijos.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)

    def mostrar_herramientas(self, si):
        self._interior.setVisible(bool(si))
        self._hueco.setVisible(not si)

    def separador(self):
        s = QFrame()
        s.setFixedSize(1, 22)
        s.setStyleSheet('background: rgba(255, 255, 255, 0.10); border: none;')
        self.flujo.addWidget(s)


class BotonPlay(QAbstractButton):
    """El botón redondo de reproducir (▶) que pasa a detener (■) mientras suena. configure(text=...) se acepta por compatibilidad."""

    def __init__(self, tip_play='', tip_stop='', lado=36, padre=None):
        super().__init__(padre)
        self._tips = (tip_play, tip_stop)
        self._activo = False
        self._hover = False
        self.setFixedSize(lado, lado)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tip_play)

    def poner_activo(self, si):
        self._activo = bool(si)
        self.setToolTip(self._tips[1] if self._activo else self._tips[0])
        self.update()

    def configure(self, text=None, **_):
        if text is not None:
            self.poner_activo(str(text).lstrip().startswith('\u25a0'))

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
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        base = QColor(ui.ACCENT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base.lighter(112) if self._hover else base)
        p.drawEllipse(r)
        c = r.center()
        blanco = QColor('#FFFFFF')
        p.setBrush(blanco)
        if self._activo:
            p.setPen(QPen(blanco, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawRoundedRect(QRectF(c.x() - 5, c.y() - 5, 10, 10), 2.0, 2.0)
        else:
            p.setPen(QPen(blanco, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            tri = QPainterPath()
            tri.moveTo(c.x() - 3.6, c.y() - 6.2)
            tri.lineTo(c.x() - 3.6, c.y() + 6.2)
            tri.lineTo(c.x() + 6.4, c.y())
            tri.closeSubpath()
            p.drawPath(tri)
        p.end()


class _Paso(QAbstractButton):
    """El − o el + del contador: un círculo fino que se enciende al pasar el ratón."""

    def __init__(self, mas, padre=None):
        super().__init__(padre)
        self._mas = mas
        self._hover = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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
        act = self.isEnabled()
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(QPen(QColor(255, 255, 255, (70 if self._hover else 40) if act else 18), 1.0))
        p.setBrush(QColor(255, 255, 255, (22 if self._hover else 8) if act else 0))
        p.drawEllipse(r)
        c = r.center()
        p.setPen(QPen(QColor('#FFFFFF' if (self._hover and act) else ('#C9D6EC' if act else '#4F607A')), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() - 4.5, c.y()), QPointF(c.x() + 4.5, c.y()))
        if self._mas:
            p.drawLine(QPointF(c.x(), c.y() - 4.5), QPointF(c.x(), c.y() + 4.5))
        p.end()


class _Cuadritos(QWidget):
    """Una fila de cuadritos: tantos como el máximo del rango, los permitidos encendidos con el color del rol."""

    def __init__(self, color, maximo, padre=None):
        super().__init__(padre)
        self._color = QColor(color)
        self._max = maximo
        self._n = 1
        self.setFixedHeight(30)
        self.setMinimumWidth(maximo * 24)

    def poner(self, n):
        self._n = n
        self.update()

    def sizeHint(self):
        return QSize(self._max * 24, 30)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self._max):
            r = QRectF(i * 24 + 1, 6, 20, 18)
            if i < self._n:
                p.setBrush(QColor(self._color.red(), self._color.green(), self._color.blue(), 210))
                p.drawRoundedRect(r, 5, 5)
            else:
                p.setBrush(QColor(255, 255, 255, 14))
                p.drawRoundedRect(r, 5, 5)
        p.end()


class PanelTamanos(QWidget):
    """«Palabras por línea»: tres filas (Arriba / Principal / Abajo) con el máximo de cada una. cambio(indice, valor)."""
    cambio = Signal(int, int)

    def __init__(self, valores, rangos, colores, nombres=None, padre=None):
        super().__init__(padre)
        self._rangos = rangos
        self._valores = list(valores)
        self._filas = []
        nombres = nombres or (tr('Arriba'), tr('Principal'), tr('Abajo'))
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        for k, nombre in enumerate(nombres):
            fila = QFrame()
            fila.setObjectName('filaTam')
            fila.setStyleSheet(ui.traducir_hoja('QFrame#filaTam { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 12px; }'))
            h = QHBoxLayout(fila)
            h.setContentsMargins(12, 6, 8, 6)
            h.setSpacing(10)
            punto = QWidget()
            punto.setFixedSize(9, 9)
            c = QColor(colores[k])
            punto.setStyleSheet(f'background: rgb({c.red()}, {c.green()}, {c.blue()}); border-radius: 4px;')
            h.addWidget(punto, 0, Qt.AlignmentFlag.AlignVCenter)
            etiqueta = Etiqueta(nombre, 13, peso='medio', color='#E3EAF6')
            etiqueta.setMinimumWidth(66)
            h.addWidget(etiqueta)
            cuadros = _Cuadritos(colores[k], rangos[k][1])
            cuadros.poner(self._valores[k])
            h.addWidget(cuadros, 1)
            menos, mas = _Paso(False), _Paso(True)
            numero = Etiqueta(str(self._valores[k]), 15, peso='negrita', color='#FFFFFF', alineacion=Qt.AlignmentFlag.AlignCenter)
            numero.setFixedWidth(22)
            menos.clicked.connect(lambda _=False, i=k: self._mover(i, -1))
            mas.clicked.connect(lambda _=False, i=k: self._mover(i, 1))
            h.addWidget(menos)
            h.addWidget(numero)
            h.addWidget(mas)
            v.addWidget(fila)
            self._filas.append((cuadros, numero, menos, mas))
        self._habilitar()

    def _mover(self, k, d):
        mn, mx = self._rangos[k]
        nuevo = max(mn, min(mx, self._valores[k] + d))
        if nuevo == self._valores[k]:
            return
        self.poner(k, nuevo)
        self.cambio.emit(k, nuevo)

    def poner(self, k, valor):
        self._valores[k] = int(valor)
        cuadros, numero, _m, _p = self._filas[k]
        cuadros.poner(int(valor))
        numero.setText(str(int(valor)))
        self._habilitar()

    def _habilitar(self):
        for k, (_c, _n, menos, mas) in enumerate(self._filas):
            mn, mx = self._rangos[k]
            menos.setEnabled(self._valores[k] > mn)
            mas.setEnabled(self._valores[k] < mx)
            menos.update()
            mas.update()


class MarcoPapel(QFrame):
    """La tarjeta del párrafo: fondo oscuro con esquinas muy redondeadas y un borde fino. El lienzo de palabras va transparente encima."""
    RADIO = 24

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setObjectName('marcoPapel')

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        p.setBrush(QColor(ui.CARD_COLOR))
        p.drawRoundedRect(r, self.RADIO, self.RADIO)
        p.end()


class PistaPincel(QWidget):
    """Una línea sobre el párrafo que dice, con el color del pincel elegido, QUÉ pasa al tocar una palabra."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self._color = QColor('#8D9BB5')
        self._nombre = ''
        self._texto = ''
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, nombre, color, texto):
        self._nombre, self._color, self._texto = nombre, QColor(color), texto
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        f_n, f_t = fuente(13, True), fuente(12)
        x = 16.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._color.red(), self._color.green(), self._color.blue(), 60))
        pil = QRectF(x, 3, QFontMetricsF(f_n).horizontalAdvance(self._nombre) + 30, h - 6)
        p.drawRoundedRect(pil, pil.height() / 2, pil.height() / 2)
        p.setBrush(self._color)
        p.drawEllipse(QPointF(pil.left() + 12, h / 2), 4.0, 4.0)
        p.setFont(f_n)
        p.setPen(QColor('#FFFFFF'))
        p.drawText(QRectF(pil.left() + 22, 0, pil.width() - 22, h), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._nombre)
        p.setFont(f_t)
        p.setPen(QColor('#8D9BB5'))
        x = pil.right() + 12
        texto = QFontMetricsF(f_t).elidedText(self._texto, Qt.TextElideMode.ElideRight, max(10, self.width() - x - 12))
        p.drawText(QRectF(x, 0, self.width() - x, h), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
        p.end()


class ControlTamano(QWidget):
    """«A ──●── A  100 %»: agranda o achica las palabras del párrafo. comando(n) con el tamaño (puntos) mientras se arrastra."""

    def __init__(self, valor, minimo, maximo, referencia, comando, padre=None):
        super().__init__(padre)
        self._ref = float(referencia)
        self._comando = comando
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(8)
        chica = Etiqueta('A', 11, color='#8D9BB5')
        grande = Etiqueta('A', 18, peso='negrita', color='#C9D6EC')
        self.deslizador = ui.Deslizador(minimo, maximo, maximo - minimo, comando=self._cambio, inicial=valor)
        self.deslizador.setFixedWidth(132)
        self.porcentaje = Etiqueta('', 12, color='#C9D6EC', alineacion=Qt.AlignmentFlag.AlignCenter)
        self.porcentaje.setFixedWidth(44)
        for w in (chica, self.deslizador, grande, self.porcentaje):
            h.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setFixedHeight(34)
        self._texto(valor)

    def _texto(self, n):
        self.porcentaje.setText(f'{round(float(n) / self._ref * 100)} %')

    def _cambio(self, v):
        n = int(round(v))
        self._texto(n)
        if self._comando:
            self._comando(n)

    def poner(self, n):
        self.deslizador.set(n)
        self._texto(n)


class PanelAsistencia(QWidget):
    """El panel de «Asistencia» mientras trabaja: un orbe que gira, los pasos reales (leer, corregir, palabras clave, emojis) con su
    estado, una barra de avance y la versión. poner_fase(k) marca los pasos hechos; terminar() lo cierra en «Listo»."""

    def __init__(self, titulo, listo, inicial, pasos, version, pie, padre=None):
        super().__init__(padre)
        self._titulo, self._listo, self._detalle0 = titulo, listo, inicial
        self._pasos = list(pasos)
        self._version, self._pie = version, pie
        self._detalle = inicial
        self._detalle_fin = ''
        self._fase = 0
        self._fin = False
        self._t = 0.0
        self._t_fase = 0.0
        self._prog = 0.0
        self._hecho = [None] * len(self._pasos)
        self._t_fin = None
        self._ult = time.perf_counter()
        self._f_titulo, self._f_texto, self._f_chico = ui.fuente(18, True), ui.fuente(13), ui.fuente(12)
        self._f_paso, self._f_paso_a = ui.fuente(14), ui.fuente(14, True)
        self._reloj = ui.QTimer(self)
        self._reloj.setInterval(16)
        self._reloj.setTimerType(Qt.TimerType.PreciseTimer)
        self._reloj.timeout.connect(self._tic)
        self.setMinimumSize(480, 340)

    def showEvent(self, e):
        self._ult = time.perf_counter()
        self._reloj.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)

    def poner_fase(self, k):
        k = max(0, min(len(self._pasos), int(k)))
        if k > self._fase:
            for j in range(self._fase, k):
                if self._hecho[j] is None:
                    self._hecho[j] = self._t
            self._fase = k
            self._t_fase = self._t

    def poner_detalle(self, texto):
        if texto and texto != self._detalle:
            self._detalle = str(texto)

    def terminar(self, detalle=''):
        self.poner_fase(len(self._pasos))
        self._fin = True
        self._t_fin = self._t
        self._detalle_fin = str(detalle or '')

    def _meta(self):
        n = max(1, len(self._pasos))
        if self._fin:
            return 1.0
        crece = 0.88 * (1.0 - math.exp(-(self._t - self._t_fase) / 5.0))          # dentro de un paso la barra sigue avanzando despacio
        return min(0.98, (self._fase + crece) / n)

    def _tic(self):
        ahora = time.perf_counter()
        dt = min(0.05, ahora - self._ult)
        self._ult = ahora
        self._t += dt
        self._prog += (self._meta() - self._prog) * min(1.0, dt * 4.0)
        self.update()

    def _orbe(self, p, cx, cy, r):
        acento = QColor(ui.ACCENT_CLARO)
        halo = QRadialGradient(cx, cy, r * 1.9)
        halo.setColorAt(0.0, QColor(acento.red(), acento.green(), acento.blue(), 95 if not self._fin else 130))
        halo.setColorAt(1.0, QColor(acento.red(), acento.green(), acento.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), r * 1.9, r * 1.9)
        p.setBrush(QColor(255, 255, 255, 10))
        p.setPen(QPen(QColor(255, 255, 255, 30), 3.0))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._fin:
            p.setPen(QPen(acento, 3.5))
            p.drawEllipse(QPointF(cx, cy), r, r)
            k = min(1.0, (self._t - (self._t_fin or 0.0)) / 0.3)
            camino = QPainterPath()
            camino.moveTo(cx - r * 0.36 * k, cy + r * 0.02)
            camino.lineTo(cx - r * 0.1, cy + r * 0.3 * k + r * 0.02 * (1 - k))
            camino.lineTo(cx + r * 0.42 * k, cy - r * 0.28 * k)
            p.setPen(QPen(QColor('#FFFFFF'), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(camino)
            return
        cg = QConicalGradient(cx, cy, -(self._t * 230.0) % 360.0)
        cg.setColorAt(0.0, QColor(acento.red(), acento.green(), acento.blue(), 255))
        cg.setColorAt(0.55, QColor(acento.red(), acento.green(), acento.blue(), 0))
        cg.setColorAt(1.0, QColor(acento.red(), acento.green(), acento.blue(), 0))
        p.setPen(QPen(QBrush(cg), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(Qt.PenStyle.NoPen)
        for k, (radio, vel, tam) in enumerate(((r * 1.32, -1.3, 2.6), (r * 1.18, 0.9, 2.0))):
            a = self._t * vel + k * 2.4
            p.setBrush(QColor(255, 255, 255, 190))
            p.drawEllipse(QPointF(cx + math.cos(a) * radio, cy + math.sin(a) * radio), tam, tam)
        pulso = 0.88 + 0.12 * math.sin(self._t * 3.2)
        e = r * 0.52 * pulso
        estrella = QPainterPath()
        for i in range(8):
            ang = -math.pi / 2 + i * math.pi / 4
            rr = e if i % 2 == 0 else e * 0.3
            pt = QPointF(cx + math.cos(ang) * rr, cy + math.sin(ang) * rr)
            if i == 0:
                estrella.moveTo(pt)
            else:
                estrella.lineTo(pt)
        estrella.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawPath(estrella)

    def _en_dos_lineas(self, texto, ancho):
        """El texto recortado con «…» para que quepa en dos líneas del ancho dado (se calcula una vez por texto y ancho)."""
        clave = (texto, int(ancho))
        if getattr(self, '_cache_dos', (None, ''))[0] == clave:
            return self._cache_dos[1]
        fm = QFontMetricsF(self._f_texto)
        limite = fm.lineSpacing() * 2 + 1
        corte = texto
        while corte and fm.boundingRect(QRectF(0, 0, ancho, 10000), int(Qt.TextFlag.TextWordWrap), corte).height() > limite:
            corte = corte[:max(0, len(corte) - 8)].rstrip()
            texto_final = corte + '…'
            if fm.boundingRect(QRectF(0, 0, ancho, 10000), int(Qt.TextFlag.TextWordWrap), texto_final).height() <= limite:
                corte = texto_final
                break
        self._cache_dos = (clave, corte)
        return corte

    def _icono_paso(self, p, cx, cy, j):
        acento = QColor(ui.ACCENT_CLARO)
        if self._hecho[j] is not None:
            k = min(1.0, (self._t - self._hecho[j]) / 0.25)
            esc = 0.6 + 0.4 * (1 - (1 - k) ** 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(acento.red(), acento.green(), acento.blue(), 46))
            p.drawEllipse(QPointF(cx, cy), 11 * esc, 11 * esc)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(acento, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            c = QPainterPath()
            c.moveTo(cx - 4.5 * esc, cy + 0.2)
            c.lineTo(cx - 1.2 * esc, cy + 3.4 * esc)
            c.lineTo(cx + 4.8 * esc, cy - 3.2 * esc)
            p.drawPath(c)
        elif j == self._fase:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 30), 2.0))
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            p.setPen(QPen(acento, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(cx - 9, cy - 9, 18, 18), int(-self._t * 300 * 16) % (360 * 16), 100 * 16)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 38), 1.6))
            p.drawEllipse(QPointF(cx, cy), 8, 8)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        m = 28
        acento = QColor(ui.ACCENT_CLARO)
        # un resplandor suave arriba, detrás del orbe
        fondo = QRadialGradient(m + 38, 62, 260)
        fondo.setColorAt(0.0, QColor(acento.red(), acento.green(), acento.blue(), 26))
        fondo.setColorAt(1.0, QColor(acento.red(), acento.green(), acento.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawRect(self.rect())
        self._orbe(p, m + 34, 66, 28)
        # título + línea de estado
        x_t = m + 90
        p.setFont(self._f_titulo)
        p.setPen(QColor('#FFFFFF'))
        p.drawText(QRectF(x_t, 36, w - x_t - m, 28), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._listo if self._fin else self._titulo)
        p.setFont(self._f_texto)
        p.setPen(QColor('#8D9BB5'))
        p.drawText(QRectF(x_t, 66, w - x_t - m, 40), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
                   self._en_dos_lineas(self._detalle_fin if self._fin else self._detalle, w - x_t - m))
        # la versión (si la hay)
        p.setFont(self._f_chico)
        if self._version:
            ancho_v = QFontMetricsF(self._f_chico).horizontalAdvance(self._version) + 24
            pil = QRectF(w - m - ancho_v, 12, ancho_v, 24)
            p.setPen(QPen(QColor(acento.red(), acento.green(), acento.blue(), 120), 1.0))
            p.setBrush(QColor(acento.red(), acento.green(), acento.blue(), 30))
            p.drawRoundedRect(pil, 12, 12)
            p.setPen(QColor('#DCE8FF'))
            p.drawText(pil, int(Qt.AlignmentFlag.AlignCenter), self._version)
        # los pasos
        y0 = 124
        alto = 38
        for j, texto in enumerate(self._pasos):
            y = y0 + j * (alto + 4)
            if j == self._fase and not self._fin:
                p.setPen(QPen(QColor(255, 255, 255, 14), 1.0))
                p.setBrush(QColor(255, 255, 255, 12))
                p.drawRoundedRect(QRectF(m - 8, y, w - 2 * m + 16, alto), 14, 14)
            self._icono_paso(p, m + 14, y + alto / 2, j)
            hecho = self._hecho[j] is not None
            activo = j == self._fase and not self._fin
            p.setFont(self._f_paso_a if activo else self._f_paso)
            p.setPen(QColor('#FFFFFF' if activo else ('#C9D6EC' if hecho else '#5F6F8A')))
            p.drawText(QRectF(m + 42, y, w - 2 * m - 42, alto), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
        # barra de avance
        yb = h - 66
        pista = QRectF(m, yb, w - 2 * m - 52, 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 18))
        p.drawRoundedRect(pista, 4, 4)
        ancho = max(8.0, pista.width() * self._prog)
        relleno = QRectF(pista.left(), pista.top(), ancho, pista.height())
        degradado = QLinearGradient(relleno.left(), 0, relleno.right(), 0)
        degradado.setColorAt(0.0, QColor(ui.ACCENT))
        degradado.setColorAt(1.0, acento)
        p.setBrush(QColor(acento.red(), acento.green(), acento.blue(), 50))
        p.drawRoundedRect(relleno.adjusted(-2, -3, 2, 3), 7, 7)
        p.setBrush(degradado)
        p.drawRoundedRect(relleno, 4, 4)
        p.setFont(self._f_chico)
        p.setPen(QColor('#C9D6EC'))
        p.drawText(QRectF(pista.right() + 8, yb - 8, 44, 24), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), f'{round(self._prog * 100)} %')
        p.setPen(QColor('#5F6F8A'))
        p.drawText(QRectF(m, h - 34, w - 2 * m, 22), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter), self._pie)
        p.end()


class MiniPosicion(QWidget):
    """El cuadro del video en miniatura (vertical u horizontal) con una barra por línea del bloque —arriba, principal, abajo— donde las pone el estilo: de un
    vistazo se ve si el estilo va arriba, al centro o abajo. Es el Tilt del pack (aproximado). v5.8: «Así se verá este bloque» enseña también DÓNDE."""
    COLORES = ('#4589FF', '#F5B84B', '#B388FF')

    def __init__(self, padre=None):
        super().__init__(padre)
        self._formato = 'v'
        self._ys = None
        self._dx = 0.0
        self._lay = 'cc'
        self._color = '#F5B84B'
        self.setFixedWidth(62)
        self.setMinimumHeight(150)

    def poner(self, formato, ys, color=None, comp=None):
        """comp = la composición de Proyecto (Ajuste fino): altura y horizontal mueven el grupo; el layout alinea las líneas de apoyo a la principal."""
        self._formato = formato if formato in ('v', 'h', 'c') else 'v'
        comp = comp or {}
        self._dx = float(comp.get('horizontal') or 0.0)
        altura = float(comp.get('altura') or 0.0)
        self._ys = tuple(y + altura for y in ys) if ys else None
        lay = str(comp.get('layout') or 'cc')
        self._lay = lay if len(lay) == 2 else 'cc'
        from PySide6.QtGui import QColor
        if color and QColor(str(color)).isValid():
            self._color = str(color)
        self.update()

    def etiqueta(self):
        if not self._ys:
            return ''
        y = self._ys[1]
        return tr('Arriba') if y > 0.62 else tr('Abajo') if y < 0.38 else tr('Centro')

    def paintEvent(self, _e):
        if not self._ys:
            return
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QColor, QPainter, QPen
        import qt_kit as _ui
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        libre = QRectF(2, 2, self.width() - 4, self.height() - 22)
        relacion = {'v': 9 / 16, 'h': 16 / 9, 'c': 1.0}[self._formato]
        ancho = min(libre.width(), libre.height() * relacion)
        alto = ancho / relacion
        marco = QRectF(libre.center().x() - ancho / 2, libre.center().y() - alto / 2, ancho, alto)
        p.setPen(QPen(QColor('#2C4068'), 1.4))
        p.setBrush(QColor('#05080F'))
        p.drawRoundedRect(marco, 6, 6)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        for f in (1 / 3, 2 / 3):
            p.drawLine(int(marco.left() + 3), int(marco.top() + marco.height() * f), int(marco.right() - 3), int(marco.top() + marco.height() * f))
        p.setPen(Qt.PenStyle.NoPen)
        anchos = (0.62, 0.84, 0.5)
        cx = marco.center().x() + self._dx * marco.width()
        izq_p, der_p = cx - marco.width() * anchos[1] / 2, cx + marco.width() * anchos[1] / 2
        for i, (y, color, a) in enumerate(zip(self._ys, (self.COLORES[0], self._color, self.COLORES[2]), anchos)):
            y = min(0.96, max(0.04, y))
            alto_barra = max(2.5, marco.height() * (0.05 if color == self._color else 0.03))
            w = marco.width() * a
            lado = self._lay[0] if i == 0 else self._lay[1] if i == 2 else 'c'      # layout: (contexto, complemento) respecto al borde de la principal
            x = izq_p if lado == 'i' else der_p - w if lado == 'd' else cx - w / 2
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, marco.top() + marco.height() * (1 - y) - alto_barra / 2, w, alto_barra), 1.5, 1.5)
        p.setPen(QColor(_ui.TEXT_MUTED))
        p.setFont(_ui.fuente(10))
        p.drawText(QRectF(0, self.height() - 18, self.width(), 16), int(Qt.AlignmentFlag.AlignCenter), self.etiqueta())
        p.end()
