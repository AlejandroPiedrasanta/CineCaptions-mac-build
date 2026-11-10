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

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
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
    """El botón redondo de reproducir (▶) que pasa a pausa (❚❚) mientras suena. configure(text=...) se acepta por compatibilidad.
    v5.5.10 (pedido: «mejora el botón de play»): de cristal con el disco verde brillante, anillo con el avance mientras suena, crece un poco al
    pasar el ratón y, sonando, se queda tenue (no tapa los captions) hasta que el ratón vuelve."""

    def __init__(self, tip_play='', tip_stop='', lado=36, padre=None):
        super().__init__(padre)
        self._tips = (tip_play, tip_stop)
        self._activo = False
        self._hover = False
        self._progreso = 0.0
        self.setFixedSize(lado, lado)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tip_play)

    def poner_activo(self, si):
        self._activo = bool(si)
        if not self._activo:
            self._progreso = 0.0
        self.setToolTip(self._tips[1] if self._activo else self._tips[0])
        self.update()

    def poner_progreso(self, fraccion):
        self._progreso = max(0.0, min(1.0, float(fraccion or 0.0)))
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
        lado = float(min(self.width(), self.height()))
        if self._activo and not self._hover:
            p.setOpacity(0.5)                                        # sonando: tenue, para ver los captions de abajo
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        p.translate(c)
        if self._hover:
            p.scale(1.06, 1.06)
        R = lado / 2.0 - 2.0
        # halo verde (más fuerte al pasar el ratón) y cristal
        halo = QRadialGradient(QPointF(0, 0), R * 1.05)
        verde = ui.QColorReal(ui.VERDE)
        h0 = ui.QColorReal(verde)
        h0.setAlpha(120 if self._hover else 70)
        halo.setColorAt(0.70, h0)
        halo.setColorAt(1.0, ui.QColorReal(verde.red(), verde.green(), verde.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(0, 0), R, R)
        p.setBrush(ui.QColorReal(255, 255, 255, 38))
        p.setPen(QPen(ui.QColorReal(255, 255, 255, 120), 1.0))
        p.drawEllipse(QPointF(0, 0), R * 0.86, R * 0.86)
        # el disco verde con brillo arriba
        r_in = R * 0.70
        disco = QLinearGradient(QPointF(0, -r_in), QPointF(0, r_in))
        disco.setColorAt(0.0, verde.lighter(125))
        disco.setColorAt(1.0, verde.darker(130))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(disco))
        p.drawEllipse(QPointF(0, 0), r_in, r_in)
        brillo = QLinearGradient(QPointF(0, -r_in), QPointF(0, 0))
        brillo.setColorAt(0.0, ui.QColorReal(255, 255, 255, 110))
        brillo.setColorAt(1.0, ui.QColorReal(255, 255, 255, 0))
        p.setBrush(QBrush(brillo))
        p.drawEllipse(QRectF(-r_in * 0.82, -r_in * 0.95, r_in * 1.64, r_in * 1.1))
        # el anillo del avance mientras suena
        if self._activo:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(ui.QColorReal(255, 255, 255, 55), max(2.0, R * 0.09)))
            p.drawEllipse(QPointF(0, 0), R * 0.93, R * 0.93)
            if self._progreso > 0.001:
                p.setPen(QPen(ui.QColorReal(255, 255, 255, 235), max(2.0, R * 0.09), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                rr = R * 0.93
                p.drawArc(QRectF(-rr, -rr, 2 * rr, 2 * rr), 90 * 16, -int(360 * 16 * self._progreso))
        # el icono: ▶ redondeado o ❚❚
        blanco = ui.QColorReal('#FFFFFF')
        p.setPen(QPen(blanco, max(1.4, r_in * 0.10), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(blanco)
        u = r_in * 0.42
        if self._activo:
            for dx in (-0.45, 0.45):
                p.drawRoundedRect(QRectF(dx * u - 0.18 * u, -0.72 * u, 0.36 * u, 1.44 * u), 0.12 * u, 0.12 * u)
        else:
            tri = QPainterPath()
            tri.moveTo(-0.55 * u, -0.85 * u)
            tri.lineTo(-0.55 * u, 0.85 * u)
            tri.lineTo(0.95 * u, 0.0)
            tri.closeSubpath()
            p.drawPath(tri)
        p.end()


class BotonSonido(QAbstractButton):
    """v5.5.10 (pedido: «al pasar el mouse por el play, que salga un icono de mutear sonido»): el altavoz junto al play. Un clic silencia (o
    devuelve) los sonidos de la reproducción; `mudo` dice cómo está."""

    def __init__(self, mudo=False, lado=38, padre=None):
        super().__init__(padre)
        self.mudo = bool(mudo)
        self._hover = False
        self.setFixedSize(lado, lado)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._alternar)
        self._tip()

    def _tip(self):
        self.setToolTip(tr('Activar el sonido') if self.mudo else tr('Silenciar el sonido'))

    def _alternar(self):
        self.mudo = not self.mudo
        self._tip()
        self.update()

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
        lado = float(min(self.width(), self.height()))
        p.translate(self.width() / 2.0, self.height() / 2.0)
        R = lado / 2.0 - 1.5
        p.setPen(QPen(ui.QColorReal(255, 255, 255, 150 if self._hover else 95), 1.0))
        p.setBrush(ui.QColorReal(10, 14, 24, 200 if self._hover else 165))
        p.drawEllipse(QPointF(0, 0), R, R)
        u = R * 0.5
        blanco = ui.QColorReal(255, 255, 255, 240)
        cuerpo = QPainterPath()                                         # el altavoz
        cuerpo.moveTo(-0.95 * u, -0.38 * u)
        cuerpo.lineTo(-0.45 * u, -0.38 * u)
        cuerpo.lineTo(0.12 * u, -0.85 * u)
        cuerpo.lineTo(0.12 * u, 0.85 * u)
        cuerpo.lineTo(-0.45 * u, 0.38 * u)
        cuerpo.lineTo(-0.95 * u, 0.38 * u)
        cuerpo.closeSubpath()
        p.setPen(QPen(blanco, max(1.0, 0.12 * u), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(blanco)
        p.drawPath(cuerpo)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.mudo:                                                   # una X
            p.setPen(QPen(ui.QColorReal('#FF6B6B'), max(1.4, 0.18 * u), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(0.42 * u, -0.38 * u), QPointF(1.1 * u, 0.38 * u))
            p.drawLine(QPointF(0.42 * u, 0.38 * u), QPointF(1.1 * u, -0.38 * u))
        else:                                                           # dos ondas
            p.setPen(QPen(blanco, max(1.2, 0.15 * u), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for r_o in (0.55, 0.95):
                rr = r_o * u
                p.drawArc(QRectF(0.2 * u - rr, -rr, 2 * rr, 2 * rr), -45 * 16, 90 * 16)
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


def _suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _tramo(u, a, b):
    """0 antes de a, 1 después de b y suave entre medias."""
    return _suave((u - a) / (b - a)) if b > a else float(u >= a)


class MuestraPalabras(QWidget):
    """v5.66 (el usuario: «si no hay sesión o audio, pulir mejor el aviso»): la cabecera del aviso del Corrector sin sesión: una frase de
    ejemplo como se ve aquí, cada palabra en su píldora con el color de su rol (Arriba / Principal / Abajo / sin marcar) y, debajo, qué
    significa cada color.
    v5.66 (el usuario: «púlelo más, que se corta el sombreado, y métele más animaciones»): el halo de la principal cabe en el widget (antes
    se cortaba arriba y abajo) y la frase ENSEÑA lo que hace el Corrector en un bucle de 8 s: las palabras entran una a una; «ganamoz»
    sale subrayada en rojo, el puntero va, la corrige («ganamos», con su ✓) y luego pinta «10.000» como Principal (el color entra de
    izquierda a derecha, el halo respira y un brillo la cruza); al final vuelve a empezar. Solo se repinta ella, a 30/s mientras se ve;
    quieta (corregida y pintada) con «Reducir animaciones»."""
    FRASE = (('Así', 'context'), ('ganamos', 'context'), ('10.000', 'main'), ('euros', 'complement'), ('en', None), ('un', None), ('mes', 'complement'))
    ERRATA, PRINCIPAL = (1, 'ganamoz'), 2
    ALTO, Y, H, HUECO = 124.0, 34.0, 36.0, 8.0               # (el halo de la principal llega a Y + H/2 ± H: cabe entre 0 y la leyenda)
    ENTRADA, CICLO, FPS = 1.0, 8.0, 30

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFixedHeight(int(self.ALTO))
        self.setMinimumWidth(460)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._t0 = time.perf_counter()
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)

    # -- reloj --------------------------------------------------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self._t0 = time.perf_counter()                              # (cada vez que se ve, entra de nuevo)
        if not self._quieto():
            self._reloj.start(int(1000 / self.FPS))
        self.update()

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

    def _tic(self):
        v = self.window()
        if v is not None and v.isMinimized():
            return
        if self._quieto():
            self._reloj.stop()
        self.update()

    def _estado(self):
        """Lo que se ve en este instante: entrada por palabra, errata, ✓, pintado de la principal, puntero, brillo y halo."""
        if self._quieto():
            return {'entrada': 1.0, 'errata': 0.0, 'visto': 0.0, 'pintado': 1.0, 'puntero': None, 'brillo': None, 'halo': 0.85}
        t = time.perf_counter() - self._t0
        u = max(0.0, t - self.ENTRADA) % self.CICLO if t > self.ENTRADA else 0.0
        vuelta = 1.0 - _tramo(u, 7.0, 7.6)
        errata = 1.0 - _tramo(u, 2.1, 2.35) * vuelta
        pintado = _tramo(u, 3.3, 3.9) * vuelta
        visto = math.sin(math.pi * _tramo(u, 2.1, 2.9)) if 2.1 <= u <= 2.9 else 0.0
        puntero = None
        alfa = _tramo(u, 1.0, 1.3) * (1.0 - _tramo(u, 3.9, 4.3))
        if alfa > 0.0:                                       # (de antes de la 1.ª palabra a la errata y de ahí a la principal)
            puntero = (_tramo(u, 1.4, 2.1), _tramo(u, 2.6, 3.3), alfa)
        brillo = None
        for a in (4.4, 6.0):
            if a <= u <= a + 0.6:
                brillo = (u - a) / 0.6
        halo = pintado * (0.78 + 0.22 * math.sin(2.0 * math.pi * t / 2.4))
        return {'entrada': t, 'errata': errata, 'visto': visto, 'pintado': pintado, 'puntero': puntero, 'brillo': brillo, 'halo': halo}

    # -- dibujo -------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _color(rol):
        return QColor({'context': ui.ROL_CONTEXTO, 'main': ui.ROL_PRINCIPAL, 'complement': ui.ROL_COMPLEMENTO}.get(rol, ui.ROL_BASE))

    def _cajas(self, fm):
        """[(QRectF, palabra, rol)] con el ancho de la palabra MÁS LARGA entre la errata y la buena (no salta al corregir)."""
        x, cajas = 1.0, []
        for i, (palabra, rol) in enumerate(self.FRASE):
            texto = max((palabra, self.ERRATA[1]) if i == self.ERRATA[0] else (palabra,), key=fm.horizontalAdvance)
            ancho = fm.horizontalAdvance(texto) + 26.0
            cajas.append((QRectF(x, self.Y, ancho, self.H), palabra, rol))
            x += ancho + self.HUECO
        return cajas

    def _pildora(self, p, r, c, lleno, alfa):
        if alfa <= 0.0:
            return
        p.save()
        p.setOpacity(p.opacity() * alfa)
        if lleno:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(r, self.H / 2, self.H / 2)
        else:
            rol = c != QColor(ui.ROL_BASE)
            p.setBrush(QColor(c.red(), c.green(), c.blue(), 30 if rol else 14))
            p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 150 if rol else 70), 1.2))
            p.drawRoundedRect(r.adjusted(0.6, 0.6, -0.6, -0.6), self.H / 2, self.H / 2)
        p.restore()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = fuente(15, peso='negrita')
        fm = QFontMetricsF(f)
        p.setFont(f)
        st = self._estado()
        cajas = self._cajas(fm)
        principal = self._color('main')
        for i, (r, palabra, rol) in enumerate(cajas):
            a = _suave((st['entrada'] - i * 0.09) / 0.38)            # entrada: sube y aparece, una tras otra
            if a <= 0.0:
                continue
            p.save()
            p.setOpacity(a)
            p.translate(0.0, (1.0 - a) * 9.0)
            if i == self.PRINCIPAL:
                if st['halo'] > 0.0:                              # el halo que respira (dentro del widget: Y + H/2 ± H)
                    c = principal
                    halo = QRadialGradient(r.center(), r.width() * 0.8)
                    halo.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), int(95 * st['halo'])))
                    halo.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(halo)
                    p.drawEllipse(r.center(), r.width() * 0.8, self.H * 0.95)
                self._pildora(p, r, self._color(None), False, 1.0 - st['pintado'])
                if st['pintado'] > 0.0:                           # el color entra de izquierda a derecha
                    p.save()
                    p.setClipRect(QRectF(r.left() - 1.0, r.top() - 1.0, (r.width() + 2.0) * st['pintado'], r.height() + 2.0))
                    self._pildora(p, r, principal, True, 1.0)
                    p.restore()
                if st['brillo'] is not None and st['pintado'] > 0.99:
                    camino = QPainterPath()
                    camino.addRoundedRect(r, self.H / 2, self.H / 2)
                    p.save()
                    p.setClipPath(camino)
                    x = r.left() - 30.0 + (r.width() + 60.0) * st['brillo']
                    lg = QLinearGradient(QPointF(x - 22.0, r.top()), QPointF(x + 22.0, r.bottom()))
                    lg.setColorAt(0.0, QColor(255, 255, 255, 0))
                    lg.setColorAt(0.5, QColor(255, 255, 255, 120))
                    lg.setColorAt(1.0, QColor(255, 255, 255, 0))
                    p.fillRect(r, lg)
                    p.restore()
                fondo = principal if st['pintado'] > 0.5 else None
                p.setPen(QColor(ui._texto_sobre(principal.name())) if fondo is not None else QColor('#8A97AE'))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, palabra)
            else:
                self._pildora(p, r, self._color(rol), False, 1.0)
                if i == self.ERRATA[0]:
                    e = st['errata']
                    for texto, alfa in ((self.ERRATA[1], e), (palabra, 1.0 - e)):
                        if alfa > 0.0:
                            p.save()
                            p.setOpacity(p.opacity() * alfa)
                            p.setPen(QColor('#E8EEF8'))
                            p.drawText(r, Qt.AlignmentFlag.AlignCenter, texto)
                            p.restore()
                    if e > 0.0:                                   # la ola roja de «mal oída»
                        ancho = fm.horizontalAdvance(self.ERRATA[1])
                        x0, y0 = r.center().x() - ancho / 2, r.bottom() - 7.0
                        ola = QPainterPath(QPointF(x0, y0))
                        k = 0.0
                        while k < ancho:
                            k += 3.0
                            ola.lineTo(QPointF(x0 + k, y0 + (1.6 if int(k / 3) % 2 else -1.6)))
                        p.setPen(QPen(QColor(255, 107, 107, int(220 * e)), 1.3))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawPath(ola)
                    if st['visto'] > 0.0:                         # el ✓ verde que salta encima
                        v = st['visto']
                        centro = QPointF(r.center().x(), r.top() - 13.0 + (1.0 - v) * 4.0)
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QColor(36, 209, 143, int(235 * v)))
                        p.drawEllipse(centro, 9.0 * (0.7 + 0.3 * v), 9.0 * (0.7 + 0.3 * v))
                        lapiz = QPen(QColor(11, 18, 34, int(255 * v)), 2.0)
                        lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(lapiz)
                        p.drawPolyline([centro + QPointF(-4.0, 0.2), centro + QPointF(-1.0, 3.2), centro + QPointF(4.2, -2.8)])
                else:
                    p.setPen(QColor('#E8EEF8') if rol else QColor('#8A97AE'))
                    p.drawText(r, Qt.AlignmentFlag.AlignCenter, palabra)
            p.restore()
        if st['puntero'] is not None:                             # el puntero: entra, va a la errata y luego a la principal
            ida, vuelta, alfa = st['puntero']
            def punta(r):
                return QPointF(r.center().x() + r.width() * 0.18, r.top() + self.H * 0.62)
            a0 = QPointF(cajas[0][0].left() - 6.0, self.Y + self.H + 6.0)
            a1, a2 = punta(cajas[self.ERRATA[0]][0]), punta(cajas[self.PRINCIPAL][0])
            pos = a0 + (a1 - a0) * ida + (a2 - a1) * vuelta
            flecha = [QPointF(0, 0), QPointF(0, 17), QPointF(4.2, 13.2), QPointF(7.2, 19.4), QPointF(9.8, 18.2), QPointF(6.9, 12.2), QPointF(12.2, 12.2)]
            p.save()
            p.setOpacity(alfa)
            p.translate(pos)
            p.setPen(QPen(QColor(8, 12, 22, 200), 1.4))
            p.setBrush(QColor('#FFFFFF'))
            p.drawPolygon(flecha)
            p.restore()
        f2 = fuente(11.5, peso='medio')                             # la leyenda
        p.setFont(f2)
        fm2 = QFontMetricsF(f2)
        x, y = 3.0, self.Y + self.H + 32.0
        p.setOpacity(_suave((st['entrada'] - 0.6) / 0.5))
        for rol, nombre in (('context', tr('Arriba')), ('main', tr('Principal')), ('complement', tr('Abajo')), (None, tr('Sin marcar'))):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._color(rol))
            p.drawEllipse(QPointF(x + 4.0, y - 4.0), 4.0, 4.0)
            p.setPen(QColor('#9AA8C0'))
            p.drawText(QPointF(x + 13.0, y), nombre)
            x += 13.0 + fm2.horizontalAdvance(nombre) + 18.0
        p.end()

    def sizeHint(self):
        fm = QFontMetricsF(fuente(15, peso='negrita'))
        return QSize(int(sum(r.width() + self.HUECO for r, _p, _r in self._cajas(fm)) + 4), int(self.ALTO))


class _MovilDemo(ui.MarcoVista):
    """El móvil del Corrector sin el resplandor de abajo: en la tarjeta, su halo se cortaba en el borde del widget (un rectángulo)."""
    def _resplandor(self, p, caja):
        return


def _ruta_creativo(nombre):
    """2_recursos/creativo/<nombre> si existe (base_recursos: en el .exe no está junto al .py), o None."""
    try:
        import instalador_scripts
        from pathlib import Path
        ruta = Path(instalador_scripts.BASE_RECURSOS) / 'creativo' / nombre
        return ruta if ruta.is_file() else None
    except Exception:
        return None


class DemoCorrector(QWidget):
    """v5.78 (el usuario: «mejora el ejemplo y da más ejemplos, ortografía, y que se puedan cambiar los colores y tipografías»; eligió la
    propuesta B): en el Corrector sin audio, TRES ejemplos reales a la vez, cada uno un móvil como el del Corrector con su VIDEO
    (2_recursos/creativo/demo_{principal,ortografia,colores}.mp4, hechos con herramientas_dev/hacer_demos_corrector.py: el mismo dibujo que
    el móvil del Corrector) y encima lo que se toca, al compás del video (demo_corrector.json = dónde empieza cada tramo):
        Principal        «que nadie te»: el puntero toca «nadie» y se pinta de ámbar → «NADIE» pasa a ser la grande (Estilo 2)
        Ortografía       «ganamoz» (ola roja) → «ganamos ✓» → el video lo corrige (Estilo 2)
        Colores y letra  el círculo elegido y el nombre de la letra (de fábrica → amarillo · Montserrat → violeta · serif → verde · Antagon; Estilo 1)
    Los videos los decodifica vistas_slider.Reproductor (un hilo cada uno, solo mientras se ve); con «Reducir animaciones», los .jpg quietos y
    lo de encima en su último paso."""
    DEMOS = (('principal', 'ph.sparkle', 'Principal'), ('ortografia', 'ph.pencil-simple', 'Ortografía'), ('colores', 'ph.palette', 'Colores y letra'))
    TRAMOS = {'principal': [0.0, 2.233], 'ortografia': [0.0, 3.533], 'colores': [0.0, 3.167, 6.333, 9.5]}
    COLORES = (('#FFFFFF', ''), ('#FFD23F', 'Montserrat|Black'), ('#B388FF', 'Instrument Serif|Regular'), ('#24D18F', 'Antagon|Regular'))
    TITULO, TIRA, PIE = 24, 52, 28

    def __init__(self, padre=None):
        super().__init__(padre)
        self.moviles = {ident: _MovilDemo(self, alto_min=120, movil=True) for ident, _i, _t in self.DEMOS}
        self._tramos = dict(self.TRAMOS)
        try:
            import json
            ruta = _ruta_creativo('demo_corrector.json')
            if ruta is not None:
                self._tramos.update({k: [float(x) for x in v] for k, v in json.loads(ruta.read_text(encoding='utf-8')).items() if k in self.TRAMOS})
        except Exception:
            pass
        from PySide6.QtGui import QImage
        for ident, marco in self.moviles.items():
            ruta = _ruta_creativo(f'demo_{ident}.jpg')
            if ruta is not None:
                marco.poner_cuadro(QImage(str(ruta)))
        self._rep, self._ultimo, self._iconos = {}, {}, {}
        self.quieto = False
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(1000, 540)

    def minimumSizeHint(self):
        return QSize(560, 250)

    # -- videos -------------------------------------------------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.quieto = MuestraPalabras._quieto()
        if not self.quieto:
            try:
                import vistas_slider
                for ident in self.moviles:
                    ruta = _ruta_creativo(f'demo_{ident}.mp4')
                    if ruta is not None and ident not in self._rep:
                        self._rep[ident] = vistas_slider.Reproductor(ruta, pausa_s=0.4)
                for r in self._rep.values():
                    r.arrancar()
            except Exception:
                self._rep = {}
            self._reloj.start(33)
        self.update()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._reloj.stop()
        for r in self._rep.values():
            r.parar()

    def _tic(self):
        v = self.window()
        if v is not None and v.isMinimized():
            return
        if MuestraPalabras._quieto():
            self._reloj.stop()
            self.quieto = True
        for ident, marco in self.moviles.items():
            r = self._rep.get(ident)
            if r is None:
                continue
            r.tam = marco.tamano_pantalla()
            img = r.imagen()
            if img is not None and img is not self._ultimo.get(ident):
                self._ultimo[ident] = img
                marco.poner_cuadro(img)
        for i in range(len(self.DEMOS)):                                      # (solo las tiras de encima: los móviles se repintan solos)
            self.update(self._tira(i).toAlignedRect().adjusted(-40, -10, 40, 40))

    def _estado(self, ident):
        """(tramo, k, t): el tramo del video que se ve, cuánto lleva (0→1 en 0,35 s) y el instante del video."""
        tr_ = self._tramos.get(ident) or [0.0]
        r = self._rep.get(ident)
        if self.quieto or r is None:
            return len(tr_) - 1, 1.0, 1e9
        t = float(r.posicion or 0.0)
        i = max(j for j, a in enumerate(tr_) if a <= t + 1e-6) if any(a <= t + 1e-6 for a in tr_) else 0
        return i, _suave((t - tr_[i]) / 0.35) if i > 0 else 1.0, t

    # -- sitio --------------------------------------------------------------------------------------------------------------------------
    def _columna(self, i):
        w = self.width() / float(len(self.DEMOS))
        return QRectF(i * w, 0, w, self.height())

    def _tira(self, i):
        c = self._columna(i)
        return QRectF(c.left() + 6, self.TITULO + 6, c.width() - 12, self.TIRA)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        arriba = self.TITULO + 6 + self.TIRA + 6
        alto_m = max(140, self.height() - arriba - self.PIE + 46)        # (MarcoVista deja 46 abajo: ahí va el pie)
        for i, (ident, _ic, _t) in enumerate(self.DEMOS):
            c = self._columna(i)
            ancho_m = int(min(c.width() - 8, (alto_m - 54) * 0.499 + 36))
            self.moviles[ident].setGeometry(int(c.center().x() - ancho_m / 2.0), arriba, ancho_m, alto_m)

    # -- dibujo -------------------------------------------------------------------------------------------------------------------------
    def _icono(self, nombre, color):
        clave = (nombre, color, round(self.devicePixelRatioF(), 2))
        if clave not in self._iconos:
            ic = ui.icono_linea(nombre, color)
            self._iconos[clave] = ic.pixmap(QSize(17, 17), self.devicePixelRatioF()) if ic is not None else None
        return self._iconos[clave]

    def _chip(self, p, r, texto, f, borde=None, fondo=None, color='#D2DCEB', alfa=1.0):
        p.save()
        p.setOpacity(p.opacity() * alfa)
        p.setPen(QPen(QColor(borde or '#26324A'), 1.6 if borde else 1.0))
        p.setBrush(QColor(fondo or '#111A2C'))
        p.drawRoundedRect(r, 10.0, 10.0)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), texto)
        p.restore()

    @staticmethod
    def _puntero(p, punta, alfa):
        if alfa <= 0.0:
            return
        flecha = [QPointF(0, 0), QPointF(0, 19), QPointF(4.7, 14.7), QPointF(8.0, 21.6), QPointF(10.9, 20.3), QPointF(7.7, 13.6), QPointF(13.6, 13.6)]
        p.save()
        p.setOpacity(alfa)
        p.translate(punta)
        p.setPen(QPen(QColor(8, 12, 22, 220), 1.4))
        p.setBrush(QColor('#FFFFFF'))
        p.drawPolygon(flecha)
        p.restore()

    @staticmethod
    def _toque(t, cambio):
        """(ida 0→1, alfa del puntero, onda 0→1 o None) para un toque en `cambio` s (el puntero llega 1 s antes)."""
        ida = _tramo(t, cambio - 1.05, cambio - 0.2)
        alfa = _tramo(t, cambio - 1.25, cambio - 1.0) * (1.0 - _tramo(t, cambio + 0.5, cambio + 0.8))
        onda = (t - (cambio - 0.12)) / 0.55 if cambio - 0.12 <= t <= cambio + 0.43 else None
        return ida, alfa, onda

    def _onda(self, p, centro, o):
        if o is None:
            return
        c = QColor(ui.ROL_PRINCIPAL)
        p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), int(210 * (1.0 - o))), 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rad = 8.0 + 26.0 * o
        p.drawEllipse(centro, rad, rad)

    def _tira_principal(self, p, r):
        i, k, t = self._estado('principal')
        f, fb = fuente(15), fuente(15, peso='negrita')
        ambar = QColor(ui.ROL_PRINCIPAL)
        palabras = ('que', 'nadie', 'te')
        anchos = [QFontMetricsF(fb).horizontalAdvance(w) + 26.0 for w in palabras]
        x = r.center().x() - (sum(anchos) + 6.0 * (len(anchos) - 1)) / 2.0
        y = r.center().y() - 18.0
        obj = None
        for w, a in zip(palabras, anchos):
            caja = QRectF(x, y, a, 36.0)
            if w == 'nadie':
                obj = caja
                pint = k if i >= 1 else 0.0
                self._chip(p, caja, w, f)
                if pint > 0.0:
                    p.save()
                    p.setClipRect(QRectF(caja.left() - 2, caja.top() - 2, (caja.width() + 4) * pint, caja.height() + 4))
                    self._chip(p, caja, w, fb, borde=ambar.name(), fondo=QColor(ambar.red(), ambar.green(), ambar.blue(), 46).name(QColor.NameFormat.HexArgb),
                               color='#FFFFFF')
                    p.restore()
            else:
                self._chip(p, caja, w, f)
            x += a + 6.0
        tr_ = self._tramos.get('principal') or [0.0, 0.0]
        if obj is not None and len(tr_) > 1 and not self.quieto:
            ida, alfa, onda = self._toque(t, tr_[1])
            self._onda(p, obj.center(), onda)
            a0 = QPointF(obj.left() - 30.0, obj.bottom() + 22.0)
            self._puntero(p, a0 + (QPointF(obj.center().x() + 4.0, obj.center().y() + 2.0) - a0) * ida, alfa)

    def _tira_ortografia(self, p, r):
        i, k, t = self._estado('ortografia')
        f, fb = fuente(15), fuente(15, peso='negrita')
        verde, rojo = QColor(ui.ACCENT_CLARO), QColor(ui.ROJO)
        a_mala = QFontMetricsF(f).horizontalAdvance('ganamoz') + 26.0
        a_buena = QFontMetricsF(fb).horizontalAdvance('ganamos') + 46.0
        total = a_mala + 34.0 + a_buena
        x = r.center().x() - total / 2.0
        y = r.center().y() - 18.0
        mala, buena = QRectF(x, y, a_mala, 36.0), QRectF(x + a_mala + 34.0, y, a_buena, 36.0)
        hecho = k if i >= 1 else 0.0
        self._chip(p, mala, 'ganamoz', f, color='#FFFFFF', alfa=1.0 - 0.55 * hecho)
        if hecho < 1.0:                                                      # la ola roja de «mal oída»
            ancho = QFontMetricsF(f).horizontalAdvance('ganamoz')
            x0, y0 = mala.center().x() - ancho / 2.0, mala.bottom() - 8.0
            ola = QPainterPath(QPointF(x0, y0))
            j = 0.0
            while j < ancho:
                j += 3.0
                ola.lineTo(QPointF(x0 + j, y0 + (1.5 if int(j / 3) % 2 else -1.5)))
            p.setPen(QPen(QColor(rojo.red(), rojo.green(), rojo.blue(), int(220 * (1.0 - hecho))), 1.3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ola)
        lapiz = QPen(verde, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(lapiz)
        cy = y + 18.0
        ax = mala.right() + 8.0
        p.drawLine(QPointF(ax, cy), QPointF(ax + 17.0, cy))
        p.drawPolyline([QPointF(ax + 11.0, cy - 6.0), QPointF(ax + 17.0, cy), QPointF(ax + 11.0, cy + 6.0)])
        self._chip(p, buena, 'ganamos', fb, borde=verde.name() if hecho > 0.5 else None,
                   fondo=QColor(verde.red(), verde.green(), verde.blue(), 36).name(QColor.NameFormat.HexArgb) if hecho > 0.5 else None,
                   color='#FFFFFF', alfa=0.4 + 0.6 * hecho)
        if hecho > 0.0:                                                      # el ✓
            p.save()
            p.setOpacity(hecho)
            c = QPointF(buena.right() - 15.0, buena.center().y())
            p.setPen(QPen(verde, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline([c + QPointF(-4.0, 0.3), c + QPointF(-1.2, 3.1), c + QPointF(4.0, -2.8)])
            p.restore()
        tr_ = self._tramos.get('ortografia') or [0.0, 0.0]
        if len(tr_) > 1 and not self.quieto:
            ida, alfa, onda = self._toque(t, tr_[1])
            self._onda(p, mala.center(), onda)
            a0 = QPointF(mala.left() - 26.0, mala.bottom() + 22.0)
            self._puntero(p, a0 + (QPointF(mala.center().x() + 4.0, mala.center().y() + 2.0) - a0) * ida, alfa)

    def _tira_colores(self, p, r):
        i, _k, _t = self._estado('colores')
        i = max(0, min(i, len(self.COLORES) - 1))
        lado, paso = 24.0, 32.0
        letra = self.COLORES[i][1]
        familia = letra.split('|')[0]
        fl = fuente(16, peso='negrita') if not familia else ui.QFont(familia)
        if familia:
            fl.setPixelSize(17)
            estilo = letra.split('|')[1] if '|' in letra else ''
            if estilo:
                fl.setStyleName(estilo)
        nombre = familia or tr('Del estilo')
        an = QFontMetricsF(fl).horizontalAdvance(nombre)
        total = len(self.COLORES) * paso + 10.0 + an
        x = r.center().x() - total / 2.0
        cy = r.center().y()
        fondo = QRectF(x - 12.0, cy - 22.0, total + 24.0, 44.0)
        p.setPen(QPen(QColor(ui.BORDER_COLOR), 1.0))
        p.setBrush(QColor(255, 255, 255, 6))
        p.drawRoundedRect(fondo, 14.0, 14.0)
        for j, (c, _l) in enumerate(self.COLORES):
            centro = QPointF(x + j * paso + lado / 2.0, cy)
            p.setPen(QPen(QColor(255, 255, 255, 46), 1.0))
            p.setBrush(QColor(c))
            p.drawEllipse(centro, lado / 2.0, lado / 2.0)
            if j == i:
                p.setPen(QPen(QColor('#FFFFFF'), 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(centro, lado / 2.0 + 4.0, lado / 2.0 + 4.0)
        p.setFont(fl)
        p.setPen(QColor(self.COLORES[i][0]) if i else QColor('#FFFFFF'))
        p.drawText(QRectF(x + len(self.COLORES) * paso + 6.0, cy - 16.0, an + 8.0, 32.0), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), nombre)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        verde = QColor(ui.ACCENT_CLARO).name()
        pies = (tr('«nadie» pasa a ser la GRANDE'), tr('Lo mal oído se corrige en el video'), tr('Tu color y tu letra en el estilo'))
        for i, (ident, icono, titulo) in enumerate(self.DEMOS):
            c = self._columna(i)
            f = fuente(15, peso='negrita')
            texto = tr(titulo)
            an = QFontMetricsF(f).horizontalAdvance(texto)
            x = c.center().x() - (an + 24.0) / 2.0
            pm = self._icono(icono, verde)
            if pm is not None and not pm.isNull():
                p.drawPixmap(QPointF(x, (self.TITULO - 17) / 2.0), pm)
            p.setFont(f)
            p.setPen(QColor('#FFFFFF'))
            p.drawText(QRectF(x + 24.0, 0, an + 4.0, self.TITULO), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
            r = self._tira(i)
            if ident == 'principal':
                self._tira_principal(p, r)
            elif ident == 'ortografia':
                self._tira_ortografia(p, r)
            else:
                self._tira_colores(p, r)
            caja, _pant, _r = self.moviles[ident].geometria_movil()
            y = self.moviles[ident].y() + caja.bottom() + 10.0
            p.setFont(fuente(13))
            p.setPen(QColor(ui.TEXT_MUTED))
            p.drawText(QRectF(c.left(), y, c.width(), 22.0), int(Qt.AlignmentFlag.AlignCenter), pies[i])
        p.end()


class _BotonLetra(QAbstractButton):
    """La letra elegida («Del estilo» o su familia, escrita con ella) y el chevrón; abre la lista de letras del equipo."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.valor = ''
        self._h = False
        self.setFixedHeight(30)
        self.setMinimumWidth(92)                          # (crece con el hueco que deja la paleta: «Montserrat» entero)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, valor):
        self.valor = str(valor or '')
        self.update()

    def enterEvent(self, e):
        self._h = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._h = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        p.setPen(QPen(QColor('#3A4D72' if self._h else '#2A3854'), 1.0))
        p.setBrush(QColor(255, 255, 255, 14 if self._h else 8))
        p.drawRoundedRect(r, 9.0, 9.0)
        partes = self.valor.split('|')
        if partes[0]:
            f = ui.QFont(partes[0])
            f.setPixelSize(13)
            if len(partes) > 1 and partes[1]:
                f.setStyleName(partes[1])
            texto = partes[0]
        else:
            f, texto = fuente(12, peso='medio'), tr('Del estilo')
        p.setFont(f)
        p.setPen(QColor('#FFFFFF'))
        p.drawText(QRectF(9, 0, self.width() - 28, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   QFontMetricsF(f).elidedText(texto, Qt.TextElideMode.ElideRight, self.width() - 30))
        x, cy = self.width() - 15.0, self.height() / 2.0
        p.setPen(QPen(QColor(ui.TEXT_MUTED), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(x - 3.5, cy - 1.8), QPointF(x, cy + 1.8))
        p.drawLine(QPointF(x, cy + 1.8), QPointF(x + 3.5, cy - 1.8))
        p.end()


class _PopupLetras(QWidget):
    """La lista de letras del equipo (crea_estilo_ui._ListaLetras: buscador, cada nombre con su letra, sus estilos) en una ventana Popup."""

    def __init__(self, padre, valor, al_elegir):
        super().__init__(padre, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        import crea_estilo_ui
        capa = QVBoxLayout(self)
        capa.setContentsMargins(12, 12, 12, 12)
        self._al_elegir = al_elegir
        self.lista = crea_estilo_ui._ListaLetras(self._elegida, alto_lista=250)
        self.lista._poner_estilos = lambda: None          # (sin los estilos debajo: se montaban sobre la lista; va el más grueso, estilo_grueso)
        self.lista.marcar(valor)
        capa.addWidget(self.lista)
        self.setFixedWidth(300)

    def _elegida(self, valor):
        """Se aplica y se cierra (con su estilo más grueso: Bold, Black…)."""
        self.close()
        self._al_elegir(valor)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(ui.BORDER_COLOR), 1.0))
        p.setBrush(QColor(ui.CARD_COLOR))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14.0, 14.0)
        p.end()


class TarjetaColores(QFrame):
    """v5.78 (propuesta B): «Colores y letra» bajo el móvil del Corrector: el color y la letra de la palabra GRANDE y del texto pequeño del
    estilo elegido (los cuatro ajustes de «Crea tu estilo»: color_principal, fuente_principal, color_secundario, fuente_secundaria). Cada fila,
    la paleta de «Crea tu estilo» (crea_estilo_ui._Paleta, más pequeña: «del estilo», 4 colores y «+» = el que quieras) y la letra (lista de
    letras del equipo). «Del estilo» lo deja como venía. al_cambiar(ajustes) a cada toque; quien la usa los guarda y rehace la vista."""
    CLAVES = ('color_principal', 'fuente_principal', 'color_secundario', 'fuente_secundaria')
    COLORES_P = ('#FDE047', '#22D3EE', '#F472B6', '#EF4444')
    COLORES_S = ('#FFFFFF', '#FDE047', '#22D3EE', '#9CA3AF')

    def __init__(self, al_cambiar, padre=None):
        super().__init__(padre)
        import crea_estilo_ui as CE

        class _PaletaChica(CE._Paleta):
            LADO, PASO = 22, 29

        self._al_cambiar = al_cambiar
        self._aj = {k: '' for k in self.CLAVES}
        self._propios = {}
        self.setObjectName('tarjetaColores')
        self.setStyleSheet(ui.traducir_hoja('QFrame#tarjetaColores { background-color: #0E1729; border: 1px solid #1E2A42; border-radius: 14px; }'))
        capa = QVBoxLayout(self)
        capa.setContentsMargins(12, 10, 12, 10)
        capa.setSpacing(6)
        cab = QHBoxLayout()
        cab.setSpacing(8)
        ic = ui.icono_linea('ph.palette', QColor(ui.ACCENT_CLARO).name())
        if ic is not None:
            from PySide6.QtWidgets import QLabel
            lbl = QLabel()
            lbl.setStyleSheet('background: transparent; border: none;')
            lbl.setPixmap(ic.pixmap(QSize(16, 16), self.devicePixelRatioF()))
            cab.addWidget(lbl)
        cab.addWidget(Etiqueta(tr('Colores y letra'), 14, peso='negrita', color='#FFFFFF'))
        self._etq_estilo = Etiqueta('', 12, color=ui.TEXT_MUTED)
        cab.addWidget(self._etq_estilo)
        cab.addStretch(1)
        self._volver = ui.Enlace(tr('Del estilo'), self._volver_al_estilo, tam=12, color=ui.TEXT_MUTED)
        cab.addWidget(self._volver)
        capa.addLayout(cab)
        self._paletas, self._letras = {}, {}
        for clave_c, clave_f, etq, colores in (('color_principal', 'fuente_principal', tr('Grande'), self.COLORES_P),
                                               ('color_secundario', 'fuente_secundaria', tr('Pequeño'), self.COLORES_S)):
            fila = QHBoxLayout()
            fila.setSpacing(6)
            e = Etiqueta(etq, 12.5, color=ui.TEXT_MUTED)
            e.setFixedWidth(52)
            fila.addWidget(e)
            pal = _PaletaChica(colores, lambda val, c=clave_c: self._poner(c, val), lambda c=clave_c: self._color_propio(c))
            self._paletas[clave_c] = pal
            fila.addWidget(pal)
            b = _BotonLetra()
            b.clicked.connect(lambda _=False, c=clave_f, bt=b: self._abrir_letras(c, bt))
            self._letras[clave_f] = b
            fila.addWidget(b, 1)
            capa.addLayout(fila)
        self._nota = Etiqueta('', 11, color='#6B7891', envolver=True)
        self._nota.hide()
        capa.addWidget(self._nota)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, ajustes, nombre_estilo='', nota=''):
        """Lo que hay ahora (sin avisar a nadie): los cuatro ajustes, el nombre del estilo y una nota (o '')."""
        a = ajustes or {}
        self._aj = {k: str(a.get(k) or '') for k in self.CLAVES}
        self._etq_estilo.configure(text=('· ' + nombre_estilo) if nombre_estilo else '')
        self._nota.configure(text=nota or '')
        self._nota.setVisible(bool(nota))
        self._marcar()

    def _marcar(self):
        for clave, pal in self._paletas.items():
            valor = self._aj.get(clave, '')
            colores = self.COLORES_P if clave == 'color_principal' else self.COLORES_S
            propio = self._propios.get(clave) or (valor if valor and valor not in colores else '')
            pal.poner(valor, propio)
        for clave, b in self._letras.items():
            b.poner(self._aj.get(clave, ''))
        self._volver.setVisible(any(self._aj.values()))

    def _poner(self, clave, valor):
        if self._aj.get(clave, '') == (valor or ''):
            return
        self._aj[clave] = valor or ''
        self._marcar()
        self._al_cambiar(dict(self._aj))

    def _color_propio(self, clave):
        inicial = self._propios.get(clave) or self._aj.get(clave) or '#FFFFFF'
        _rgb, hexa = ui.elegir_color(self, inicial, tr('Color personalizado'))
        if not hexa or not ui.vivo(self):
            return
        hexa = str(hexa).upper()
        colores = self.COLORES_P if clave == 'color_principal' else self.COLORES_S
        if hexa not in colores:
            self._propios[clave] = hexa
        self._poner(clave, hexa)

    def _abrir_letras(self, clave, boton):
        pop = _PopupLetras(self.window(), self._aj.get(clave, ''), lambda val, c=clave: self._poner(c, val))
        pop.adjustSize()
        g = boton.mapToGlobal(boton.rect().topRight())
        pop.move(int(g.x() - pop.width()), int(g.y() - pop.height() - 6))       # (la tarjeta va abajo del todo: la lista sale encima)
        pop.show()

    def _volver_al_estilo(self):
        if not any(self._aj.values()):
            return
        self._aj = {k: '' for k in self.CLAVES}
        self._propios = {}
        self._marcar()
        self._al_cambiar(dict(self._aj))


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

    def __init__(self, valor, minimo, maximo, referencia, comando, padre=None, grande=False):
        super().__init__(padre)
        self._ref = float(referencia)
        self._comando = comando
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(10 if grande else 8)
        # v5.5.10 (pedido: «quita la barra; sube el tamaño de texto y el botón Generar»): versión grande, a lo ancho de la columna derecha
        chica = Etiqueta('A', 14 if grande else 11, color='#8D9BB5')
        grande_a = Etiqueta('A', 26 if grande else 18, peso='negrita', color='#C9D6EC')
        self.deslizador = ui.Deslizador(minimo, maximo, maximo - minimo, comando=self._cambio, inicial=valor)
        if not grande:
            self.deslizador.setFixedWidth(132)
        self.porcentaje = Etiqueta('', 15 if grande else 12, peso='medio' if grande else None, color='#C9D6EC', alineacion=Qt.AlignmentFlag.AlignCenter)
        self.porcentaje.setFixedWidth(58 if grande else 44)
        for w in (chica, self.deslizador, grande_a, self.porcentaje):
            h.addWidget(w, 1 if (grande and w is self.deslizador) else 0, Qt.AlignmentFlag.AlignVCenter)
        self.setFixedHeight(46 if grande else 34)
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
