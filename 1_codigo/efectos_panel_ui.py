# CineCaptions · By Cinema Productions
# 1_codigo/efectos_panel_ui.py — v5.93: las piezas de la página Efectos «Escenario» (propuesta A, elegida por el usuario entre tres reales):
# pestañas arriba, «GO usará» y «Personaliza» a la izquierda, el ejemplo en grande en el centro y las opciones en tarjetas verticales.
"""
    icono_ui(nombre, tam)     PNG de 2_recursos/efectos/iconos_ui (hechos con Higgsfield, ver DOCUMENTACION/temas/efectos.md) o None
    animacion_ui(nombre, tam) los cuadros de su animación (`<nombre>_anim.png`, tira con transparencia suave) o []
    icono_tenido(nombre, tam, color)  el icono en un solo color (las secciones apagadas)
    MarcaSeccion / TiraTiempo       v5.99 «Línea de tiempo»: arriba, tu video en fotogramas y el icono de cada efecto donde va (clic = abrirlo)
    PestanaSeccion / BarraPestanas  las pestañas de antes (v5.93-5.98; ya no se usan en la página)
    TarjetaVertical / RejillaOpciones  una opción (todo póster, con su nombre encima) y la rejilla (5 + 4 si caben)
    TarjetaUsara / LineaDonde       «GO usará …» y «Dónde va en tu video» (desde la v5.99, ocultas: lo dicen el check y la tira)
    PanelVista                      el escenario: el mp4 de la opción en bucle en un móvil, su nombre, «Ver otra vez» y «Usar …»
Lo que se elige y se guarda sigue en efectos_pro_ui.SeccionEstilo (estilos_pro): aquí solo cómo se ve. Sin globos ni tooltips.
"""
import math
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

import qt_kit as ui
from i18n import tr
from qt_kit import Boton, Etiqueta, Interruptor, QColor

VERDE = ui.VERDE
MUT = ui.TEXT_MUTED
_CACHE = {}


def carpeta_iconos():
    try:
        import sfx_rules
        return Path(sfx_rules.base_recursos()) / 'efectos' / 'iconos_ui'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'efectos' / 'iconos_ui'


def icono_ui(nombre, tam=20):
    """QPixmap del icono `nombre` a `tam` px lógicos (nítido con la escala de la pantalla), o None si no está."""
    clave = (nombre, tam)
    if clave in _CACHE:
        return _CACHE[clave]
    pm = None
    ruta = carpeta_iconos() / f'{nombre}.png'
    if ruta.is_file():
        try:
            from PySide6.QtGui import QGuiApplication
            dpr = QGuiApplication.instance().devicePixelRatio() if QGuiApplication.instance() else 1.0
            img = QPixmap(str(ruta))
            if not img.isNull():
                fis = max(1, int(round(tam * dpr)))
                pm = img.scaled(fis, fis, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                pm.setDevicePixelRatio(dpr)
        except Exception:
            pm = None
    _CACHE[clave] = pm
    return pm


def icono_tenido(nombre, tam, color):
    """El icono `nombre` en un solo color (la barra: las secciones que no están abiertas van apagadas, en gris azulado)."""
    clave = (nombre, tam, color)
    if clave in _CACHE:
        return _CACHE[clave]
    base = icono_ui(nombre, tam)
    pm = None
    if base is not None and not base.isNull():
        pm = QPixmap(base.size())
        pm.setDevicePixelRatio(base.devicePixelRatio())
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.drawPixmap(0, 0, base)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), QColor(color))
        p.end()
    _CACHE[clave] = pm
    return pm


def animacion_ui(nombre, tam=24):
    """Los cuadros de la animación del icono (v5.93, ronda 2: `<nombre>_anim.png`, una tira horizontal de cuadros cuadrados con
    transparencia suave; antes un GIF de transparencia binaria, con bordes dentados) a `tam` px lógicos, o [] si no hay."""
    clave = ('anim', nombre, tam)
    if clave in _CACHE:
        return _CACHE[clave]
    cuadros = []
    ruta = carpeta_iconos() / f'{nombre}_anim.png'
    if ruta.is_file():
        try:
            from PySide6.QtGui import QGuiApplication
            dpr = QGuiApplication.instance().devicePixelRatio() if QGuiApplication.instance() else 1.0
            tira = QPixmap(str(ruta))
            lado = tira.height()
            fis = max(1, int(round(tam * dpr)))
            for k in range(tira.width() // lado if lado else 0):
                c = tira.copy(k * lado, 0, lado, lado).scaled(fis, fis, Qt.AspectRatioMode.KeepAspectRatio,
                                                              Qt.TransformationMode.SmoothTransformation)
                c.setDevicePixelRatio(dpr)
                cuadros.append(c)
        except Exception:
            cuadros = []
    _CACHE[clave] = cuadros
    return cuadros


ANIM_MS = 50                                           # lo que dura cada cuadro de las animaciones de Higgsfield (24 cuadros ≈ 1,2 s)


def _reloj_ms():
    import time
    return time.perf_counter() * 1000.0


def _suave(t):
    """0 → 1 con salida suave (ease-out cúbica)."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


# ====================================================================================== las pestañas de arriba
class PestanaSeccion(QWidget):
    """Una sección en las pestañas de arriba (propuesta A «Escenario», elegida por el usuario): su icono, su nombre y un punto verde si GO la
    pone. La abierta: fondo verde y su icono animado (la tira de Higgsfield: se mueve 1,2 s y descansa); las apagadas, el icono en gris; al
    pasar por encima, en color y su animación una vez. Los cuadros los avanza el reloj de la página (tic): ningún temporizador por pestaña."""
    clic = Signal(str)
    LADO_ICONO = 24
    PAUSA_MS = 1600
    APAGADO = '#A6B4C9'

    def __init__(self, clave, titulo, icono, icono_qt=None, padre=None):
        super().__init__(padre)
        self.clave, self.titulo, self._icono, self._icono_qt = clave, titulo, icono, icono_qt
        self.activa, self._hover, self.on, self.estado = False, False, False, ''
        self._t0, self._k = 0.0, -1
        self.setFixedHeight(46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ajustar()

    _CAJA = QRectF(10, 7, 32, 32)

    def _ajustar(self):
        fm = QFontMetricsF(ui.fuente(14, peso='negrita'))
        self.setFixedWidth(int(48 + fm.horizontalAdvance(self.titulo) + 12 + 7 + 16))

    def _cuadros(self):
        return animacion_ui(self._icono, self.LADO_ICONO) if self._icono else []

    def _cuadro(self):
        cuadros = self._cuadros()
        if not cuadros or not (self.activa or self._hover):
            return 0
        n = len(cuadros)
        dur = n * ANIM_MS
        t = _reloj_ms() - self._t0
        if self.activa:
            t %= dur + self.PAUSA_MS
        return min(n - 1, int(t // ANIM_MS)) if 0 <= t < dur else 0

    def tic(self):
        k = self._cuadro()
        if k != self._k:
            self._k = k
            self.update(self._CAJA.toAlignedRect().adjusted(-2, -2, 2, 2))

    def poner(self, activa=None, estado=None, on=None):
        if activa is not None and bool(activa) != self.activa:
            self.activa = bool(activa)
            self._t0 = _reloj_ms()
        if estado is not None:
            self.estado = str(estado)
        if on is not None:
            self.on = bool(on)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        if not self.activa:
            self._t0 = _reloj_ms()                     # una vuelta de su animación
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self.clave)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self.activa:
            p.setBrush(QColor(46, 211, 155, 26))
            p.setPen(QPen(QColor(46, 211, 155, 105), 1))
            p.drawRoundedRect(r, 13, 13)
        elif self._hover:
            p.setBrush(QColor(255, 255, 255, 12))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 13, 13)
        lado = self.LADO_ICONO
        caja = self._CAJA
        x0, y0 = int(caja.center().x() - lado / 2), int(caja.center().y() - lado / 2)
        color = self.activa or self._hover or self.on
        cuadros = self._cuadros() if (self.activa or self._hover) else []
        if cuadros:
            k = self._cuadro()
            self._k = k
            p.drawPixmap(x0, y0, cuadros[k])
        else:
            pm = None
            if self._icono:
                pm = icono_ui(self._icono, lado) if color else icono_tenido(self._icono, lado, self.APAGADO)
            if pm is not None and not pm.isNull():
                p.drawPixmap(x0, y0, pm)
            elif self._icono_qt is not None:
                p.drawPixmap(int(caja.center().x() - 10), int(caja.center().y() - 10), self._icono_qt.pixmap(20, 20))
        p.setFont(ui.fuente(14, peso='negrita'))
        p.setPen(QColor('#FFFFFF') if (self.activa or self._hover) else QColor('#C4CEDD'))
        fm = QFontMetricsF(p.font())
        x = 48
        ancho_t = fm.horizontalAdvance(self.titulo)
        p.drawText(QRectF(x, 0, ancho_t + 2, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.titulo)
        c = QRectF(x + ancho_t + 12, self.height() / 2 - 3.5, 7, 7)   # el punto: verde si GO la pone
        p.setPen(Qt.PenStyle.NoPen)
        if self.on:
            p.setBrush(QColor(46, 211, 155, 70))
            p.drawEllipse(c.adjusted(-3, -3, 3, 3))
            p.setBrush(QColor(VERDE))
        else:
            p.setBrush(QColor('#3A4762'))
        p.drawEllipse(c)
        p.end()


class _AreaHorizontal(QScrollArea):
    """Una fila que se desliza de lado (sin barra) si las pestañas no caben: la rueda la mueve."""

    def wheelEvent(self, e):
        d = e.angleDelta()
        paso = d.y() if abs(d.y()) >= abs(d.x()) else d.x()
        barra = self.horizontalScrollBar()
        if barra.maximum() > 0:
            barra.setValue(barra.value() - int(paso / 2))
            e.accept()
        else:
            e.ignore()


class BarraPestanas(QWidget):
    """Las pestañas de arriba: una por sección (+ Ritmo); tocar una la abre. `filas` (como la barra lateral de antes: las herramientas de
    los tutoriales la buscan así)."""
    elegida = Signal(str)

    def __init__(self, padre=None):
        super().__init__(padre)
        self.filas = {}
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        self._area = _AreaHorizontal(self)
        self._area.setWidgetResizable(True)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._area.setStyleSheet('QScrollArea{background:transparent;border:none}')
        self._area.viewport().setStyleSheet('background:transparent')
        dentro = QWidget()
        dentro.setObjectName('pestanasEf')
        dentro.setStyleSheet('#pestanasEf{background:transparent}')
        self._capa = QHBoxLayout(dentro)
        self._capa.setContentsMargins(0, 0, 0, 0)
        self._capa.setSpacing(6)
        self._capa.addStretch(1)
        self._area.setWidget(dentro)
        capa.addWidget(self._area)
        self.setFixedHeight(46)

    def agregar(self, fila):
        fila.clic.connect(self._tocar)
        self._capa.insertWidget(self._capa.count() - 1, fila)
        self.filas[fila.clave] = fila
        return fila

    def _tocar(self, clave):
        self.marcar(clave)
        self.elegida.emit(clave)

    def marcar(self, clave):
        for k, f in self.filas.items():
            f.poner(activa=k == clave)
        f = self.filas.get(clave)
        if f is not None:
            self._area.ensureWidgetVisible(f, 40, 0)

    def tic(self):
        """Avanza las animaciones (la pestaña abierta y la que está bajo el ratón; las demás no repintan)."""
        for f in self.filas.values():
            if f.activa or f._hover or f._k > 0:
                f.tic()


# ====================================================================================== v5.99 «Línea de tiempo»: la tira de tu video
class MarcaSeccion(PestanaSeccion):
    """Una sección en la tira de tu video (propuesta A «Línea de tiempo», elegida por el usuario): solo su icono en una cajita, en el
    punto del video donde va. La abierta: verde, más grande y animada; las que GO no pone, tenues. Lo demás, como PestanaSeccion."""
    LADO = 50
    encima_de = Signal(str, bool)                      # (clave, dentro): la tira dice su nombre a la izquierda mientras el ratón está encima

    def __init__(self, clave, titulo, icono, icono_qt=None, padre=None):
        super().__init__(clave, titulo, icono, icono_qt, padre)
        self.fijo = False                              # True: va en un segundo marcado (o el gancho, en el primero)

    def enterEvent(self, e):
        super().enterEvent(e)
        self.encima_de.emit(self.clave, True)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.encima_de.emit(self.clave, False)

    _CAJA = QRectF(8, 8, 28, 28)

    def _ajustar(self):
        self.setFixedSize(self.LADO, self.LADO)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(3.5, 3.5, self.width() - 7, self.height() - 7) if self.activa else QRectF(6.5, 6.5, self.width() - 13, self.height() - 13)
        if self.activa:
            p.setPen(QPen(QColor(46, 211, 155, 55), 4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), 14, 14)
            p.setBrush(QColor(46, 211, 155, 48))
            p.setPen(QPen(QColor(VERDE), 1.4))
        else:
            p.setBrush(QColor(22, 36, 53, 240) if not self._hover else QColor(34, 52, 72, 250))
            p.setPen(QPen(QColor(255, 255, 255, 55 if self._hover else 28), 1))
        p.drawRoundedRect(r, 12, 12)
        if self.on and not self.activa:                # (el punto verde: GO la pone, como en las pestañas de antes)
            p.setPen(QPen(QColor('#0B1424'), 2))
            p.setBrush(QColor(VERDE))
            p.drawEllipse(QRectF(r.right() - 6, r.top() - 2, 8, 8))
        lado = 28 if self.activa else 24
        x0, y0 = int(self.width() / 2 - lado / 2), int(self.height() / 2 - lado / 2)
        cuadros = (animacion_ui(self._icono, lado) if self._icono else []) if (self.activa or self._hover) else []
        if cuadros:
            k = min(len(cuadros) - 1, self._cuadro())
            self._k = k
            p.drawPixmap(x0, y0, cuadros[k])
        else:
            pm = None
            if self._icono:
                pm = icono_ui(self._icono, lado) if (self.on or self._hover) else icono_tenido(self._icono, lado, '#6E7D95')
            if pm is not None and not pm.isNull():
                p.drawPixmap(x0, y0, pm)
            elif self._icono_qt is not None:
                p.drawPixmap(int(self.width() / 2 - 10), int(self.height() / 2 - 10), self._icono_qt.pixmap(20, 20))
        p.end()

    def _cuadros(self):
        return animacion_ui(self._icono, 28 if self.activa else 24) if self._icono else []

    def tic(self):
        k = self._cuadro()
        if k != self._k:
            self._k = k
            self.update()


class TiraTiempo(QWidget):
    """Arriba de la página Efectos (v5.99, propuesta A «Línea de tiempo»; antes, pestañas): tu video de Inicio en una tira de fotogramas
    con su regla, y encima el icono de cada efecto en el punto donde va (el gancho, en el primer segundo; los demás, en su primera posición
    marcada o, sin marcar, repartidos con la raya punteada: GO elige dónde). Clic en un icono = abre esa sección. Lo mismo que BarraPestanas
    hacia fuera (`elegida`, `agregar`, `filas`, `marcar`, `tic`). Los fotogramas los lee un hilo (posiciones_pro.fotogramas, en caché)."""
    elegida = Signal(str)
    ALTO = 132
    IZQ = 230                                          # el texto de la izquierda («Tu video», su nombre y la pista)
    ARRIBA_TIRA = 62                                   # donde empieza la tira de fotogramas
    ALTO_TIRA = 44

    def __init__(self, padre=None):
        super().__init__(padre)
        self.filas = {}
        self._orden = []
        self._lugares = {}                             # clave → (duración | None, [(ini, fin)])
        self._ruta, self._fotos, self._dur = None, [], None
        self._pedida = None
        self._encima = None                            # el icono bajo el ratón: su nombre sale a la izquierda (sin globos)
        self.setFixedHeight(self.ALTO)

    # -- lo mismo que BarraPestanas
    def agregar(self, fila):
        fila.setParent(self)
        fila.clic.connect(self._tocar)
        if hasattr(fila, 'encima_de'):
            fila.encima_de.connect(self._al_encima)
        self.filas[fila.clave] = fila
        self._orden.append(fila.clave)
        fila.show()
        self._colocar()
        return fila

    def _tocar(self, clave):
        self.marcar(clave)
        self.elegida.emit(clave)

    def _al_encima(self, clave, dentro):
        nuevo = clave if dentro else (None if self._encima == clave else self._encima)
        if nuevo != self._encima:
            self._encima = nuevo
            self.update(0, 0, self.IZQ, self.height())

    ENTRA_MS = 280                                     # el tramo de la sección abierta entra: se abre desde su centro y se enciende

    def marcar(self, clave):
        anterior = next((k for k, f in self.filas.items() if f.activa), None)
        for k, f in self.filas.items():
            f.poner(activa=k == clave)
            if k == clave:
                f.raise_()
        if clave != anterior:
            self._t_marca = _reloj_ms()
        self.update()

    def _entrada(self):
        return _suave((_reloj_ms() - getattr(self, '_t_marca', 0.0)) / self.ENTRA_MS)

    def tic(self):
        for f in self.filas.values():
            if f.activa or f._hover or f._k > 0:
                f.tic()
        if _reloj_ms() - getattr(self, '_t_marca', 0.0) < self.ENTRA_MS + 60:   # (solo mientras entra el tramo: después, quieta)
            self.update(self._pista().adjusted(-4, -4, 4, 4).toAlignedRect())

    # -- el video y dónde va cada efecto
    def poner_video(self, ruta):
        """El video de Inicio (o None). Sus fotogramas se leen en un hilo, una vez por video."""
        ruta = str(ruta) if ruta else None
        if ruta == self._ruta:
            return
        self._ruta, self._fotos, self._dur = ruta, [], None
        self.update()
        if not ruta or self._pedida == ruta:
            return
        self._pedida = ruta

        def leer():
            import posiciones_pro as POS
            d = POS.fotogramas(ruta)
            if not d:
                return None
            from PySide6.QtGui import QImage
            fotos = []
            for _t, f in d.get('fotos') or []:
                img = QImage(str(f))
                if not img.isNull():
                    fotos.append(img)
            return float(d.get('dur') or 0.0), fotos

        def fin(r, error):
            self._pedida = None
            if ruta != self._ruta or error is not None or not r:
                return
            self._dur, self._fotos = r[0] or None, r[1]
            self._colocar()
            self.update()
        ui.correr_en_hilo(self, leer, fin)

    def poner_lugar(self, clave, duracion, tramos):
        """Dónde va la sección `clave`: tramos = [(ini_s, fin_s)] (vacío: GO elige)."""
        nuevo = (float(duracion) if duracion else None, [(float(a), float(b)) for a, b, *_r in (tramos or [])])
        if self._lugares.get(clave) != nuevo:
            self._lugares[clave] = nuevo
            if nuevo[0] and not self._dur:
                self._dur = nuevo[0]
            self._colocar()
            self.update()

    def _pista(self):
        return QRectF(self.IZQ + 22, self.ARRIBA_TIRA, max(60.0, self.width() - self.IZQ - 22 - 20), self.ALTO_TIRA)

    def _duracion(self):
        if self._dur:
            return self._dur
        fines = [b for _d, ts in self._lugares.values() for _a, b in ts]
        return max(fines + [30.0])                     # (sin la duración: una de referencia de 30 s, como «Dónde va»)

    def _colocar(self):
        """Pone cada icono sobre su punto de la tira; los que no tienen segundo, repartidos; sin pisarse."""
        if not self._orden:
            return
        pista, dur = self._pista(), self._duracion()
        lado = MarcaSeccion.LADO
        xs = {}
        libres = []
        for k in self._orden:
            ts = (self._lugares.get(k) or (None, []))[1]
            if ts:
                xs[k] = pista.left() + pista.width() * min(1.0, max(0.0, ts[0][0] / dur))
                self.filas[k].fijo = True
            else:
                libres.append(k)
                self.filas[k].fijo = False
        n = len(libres)
        for i, k in enumerate(libres):                 # (repartidos entre el 9 % y el final, en el orden de las secciones)
            xs[k] = pista.left() + pista.width() * (0.09 + 0.91 * (i + 0.5) / max(1, n))
        orden = sorted(self._orden, key=lambda k: (xs[k], self._orden.index(k)))
        hueco = lado + 4
        mins = pista.left() + lado / 2 - 4
        for k in orden:                                # (que no se pisen: empujados a la derecha y, si se salen, de vuelta)
            xs[k] = max(xs[k], mins)
            mins = xs[k] + hueco
        maxs = pista.right() - lado / 2 + 4
        for k in reversed(orden):
            xs[k] = min(xs[k], maxs)
            maxs = xs[k] - hueco
        self._xs = xs
        for k in self._orden:
            self.filas[k].move(int(round(xs[k] - lado / 2)), 2)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._colocar()

    def _pintar_fotos(self, p, pista, solo):
        """Los fotogramas a lo largo de `pista`, recortados a lo ancho (alto × 1,35) con una raya de 2 px; `solo` = [QRectF]: solo los
        que tocan esos tramos (los del tramo abierto, encima de la capa guardada)."""
        n = len(self._fotos)
        ancho_f = pista.height() * 1.35
        cuantos = max(1, int(round(pista.width() / ancho_f)))
        ancho_f = pista.width() / cuantos
        for i in range(cuantos):
            r = QRectF(pista.left() + i * ancho_f, pista.top(), ancho_f - 2, pista.height())
            if solo is not None and not any(r.intersects(t) for t in solo):
                continue
            img = self._fotos[min(n - 1, int((i + 0.5) / cuantos * n))]
            esc = max(r.width() / img.width(), r.height() / img.height())
            w, h = img.width() * esc, img.height() * esc
            p.save()
            p.setClipRect(r, Qt.ClipOperation.IntersectClip)
            p.drawImage(QRectF(r.center().x() - w / 2, r.center().y() - h * 0.42, w, h), img)
            p.restore()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # ---- a la izquierda: «Tu video», su nombre y qué es esto (con el ratón sobre un icono: el nombre de ese efecto y cómo está)
        x, ancho = 4, self.IZQ - 8
        izq_txt = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
        f_enc = self.filas.get(self._encima) if self._encima else None
        p.setFont(ui.fuente(10.5, peso='negrita'))
        p.setPen(QColor('#6F7E98'))
        p.drawText(QRectF(x, 6, ancho, 16), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   (tr('Efecto') if f_enc is not None else tr('Tu video')).upper())
        p.setFont(ui.fuente(15, peso='negrita'))
        p.setPen(QColor('#FFFFFF'))
        fm = QFontMetricsF(p.font())
        nombre = f_enc.titulo if f_enc is not None else (Path(self._ruta).name if self._ruta else tr('Sin video'))
        p.drawText(QRectF(x, 26, ancho, 24), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   fm.elidedText(nombre, Qt.TextElideMode.ElideMiddle if f_enc is None else Qt.TextElideMode.ElideRight, ancho))
        p.setFont(ui.fuente(12))
        if f_enc is not None:
            p.setPen(QColor('#5FD9AE') if f_enc.on else QColor('#8592AA'))
            sub = (f_enc.estado or tr('Activado')) if f_enc.on else tr('Apagado: GO no lo pone.')
            p.drawText(QRectF(x, 56, ancho, 66), izq_txt, sub + '\n' + tr('Clic para abrirlo.'))
        else:
            p.setPen(QColor(MUT))
            pista_txt = (tr('Cada icono es un efecto, donde GO lo pondrá. Clic en uno para cambiarlo.') if self._ruta else
                         tr('Suelta un video en Inicio para verlo aquí. Clic en un icono para cambiar ese efecto.'))
            p.drawText(QRectF(x, 56, ancho, 66), izq_txt, pista_txt)
        # ---- la tira de fotogramas (cuadros recortados, con una raya fina entre ellos)
        pista, dur = self._pista(), self._duracion()
        abierta = next((k for k, f in self.filas.items() if f.activa), None)
        tramos = []
        e = self._entrada()                            # 0 → 1 al cambiar de sección (se abre desde su centro)
        for ini, fin in (self._lugares.get(abierta) or (None, []))[1]:
            x0 = pista.left() + pista.width() * max(0.0, ini) / dur
            x1 = pista.left() + pista.width() * min(dur, fin) / dur
            ancho = max(16.0, x1 - x0) * (0.55 + 0.45 * e)
            tramos.append(QRectF((x0 + max(16.0, x1 - x0) / 2) - ancho / 2, pista.top(), ancho, pista.height()))
        camino = QPainterPath()
        camino.addRoundedRect(pista, 10, 10)
        # v5.99: la capa de abajo (fondo + fotogramas apagados, o la tira rayada) se pinta UNA vez en un pixmap; en cada repintado solo
        # se copia (antes, 60 fotogramas recortados y escalados cada vez: ~2,5 ms)
        dpr = self.devicePixelRatioF()
        clave = (round(pista.width()), round(pista.height()), round(dpr, 3), id(self._fotos), len(self._fotos))
        if getattr(self, '_base_tira', (None,))[0] != clave:
            pm = QPixmap(int(math.ceil(pista.width() * dpr)), int(math.ceil(pista.height() * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            local = QRectF(0, 0, pista.width(), pista.height())
            cam_l = QPainterPath()
            cam_l.addRoundedRect(local, 10, 10)
            q.setClipPath(cam_l)
            q.fillRect(local, QColor('#0A1220'))
            if self._fotos:
                q.setOpacity(0.5)
                self._pintar_fotos(q, local, None)
            else:
                q.setPen(QPen(QColor(255, 255, 255, 14), 1))
                xx = 0.0
                while xx < local.right():              # (sin video: la tira rayada)
                    q.drawLine(int(xx), 0, int(xx + local.height() * 0.6), int(local.bottom()))
                    xx += 14.0
            q.end()
            self._base_tira = (clave, pm)
        p.drawPixmap(pista.topLeft(), self._base_tira[1])
        if self._fotos and tramos:                     # los del tramo de la sección abierta, a todo color (solo esos fotogramas)
            p.save()
            cam_t = QPainterPath()
            for r in tramos:
                cam_t.addRect(r)
            p.setClipPath(cam_t.intersected(camino))
            p.setOpacity(0.5 + 0.5 * e)
            self._pintar_fotos(p, pista, tramos)
            p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawRoundedRect(pista.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        # ---- dónde va la sección abierta: su marco verde sobre la tira
        for r in tramos:
            p.setBrush(QColor(46, 211, 155, int((28 if self._fotos else 50) * e)))
            borde = QColor(VERDE)
            borde.setAlpha(int(255 * e))
            p.setPen(QPen(borde, 2))
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)
        # ---- la raya de cada icono hasta la tira (punteada: GO elige el sitio)
        xs = getattr(self, '_xs', {})
        for k, f in self.filas.items():
            if k not in xs:
                continue
            xx = xs[k]
            color = QColor(VERDE) if f.activa else QColor(255, 255, 255, 70 if f.on else 35)
            pen = QPen(color, 1.4 if f.activa else 1)
            if not f.fijo:
                pen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(pen)
            p.drawLine(QRectF(xx, 2 + MarcaSeccion.LADO - 3, 0, 0).topLeft(), QRectF(xx, pista.top(), 0, 0).topLeft())
        # ---- la regla: pasos redondos (1, 2, 5, 10, 15, 30 s…), una rayita en cada uno y el total al final
        p.setFont(ui.fuente(10.5))
        fm = QFontMetricsF(p.font())
        paso = next((s for s in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600) if dur / s <= 10), 1200)
        y_r = pista.bottom() + 4
        t = 0.0
        ult_x = -1e9
        fin_x = pista.right() - fm.horizontalAdvance(_mmss(dur)) - 10
        while t < dur - paso * 0.35:
            xx = pista.left() + pista.width() * t / dur
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.drawLine(QRectF(xx, y_r, 0, 0).topLeft(), QRectF(xx, y_r + 4, 0, 0).topLeft())
            texto = _mmss(t)
            if xx - ult_x > 46 and xx < fin_x:
                p.setPen(QColor('#7F8CA4'))
                p.drawText(QRectF(xx + (0 if t == 0 else -30), y_r + 5, 60, 15),
                           int((Qt.AlignmentFlag.AlignLeft if t == 0 else Qt.AlignmentFlag.AlignHCenter) | Qt.AlignmentFlag.AlignVCenter), texto)
                ult_x = xx
            t += paso
        p.setPen(QColor('#9AA6BA'))
        p.drawText(QRectF(pista.right() - 60, y_r + 5, 60, 15), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), _mmss(dur))
        p.end()


# ====================================================================================== las opciones de una sección
class TarjetaVertical(QWidget):
    """Una opción en vertical: su póster grande (el de la app; quieto: el que se mueve es el del escenario), su nombre y su descripción.
    Clic = la elige (v5.27, el usuario: «si le doy clic… que ya quede lista la selección»); quedarse encima = verla en grande en el
    escenario. La elegida: borde verde y su check (aparece con un rebote); la que se ve en grande: borde blanco y «Viendo»."""
    clic = Signal(str)
    encima = Signal(str)
    ALTO = 212
    ESPERA_MS = 260                                    # pasar de largo (camino de «Usar …») no cambia el escenario; quedarse encima, sí
    POP_MS = 320

    def __init__(self, ident, nombre, detalle, poster=None, padre=None):
        super().__init__(padre)
        self.ident, self.nombre, self.detalle = ident, nombre, detalle
        self._sel = self._vista = self._hover = False
        self._h, self._t_sel = 0.0, 0.0
        self._poster = None
        if poster:
            try:
                import vistas_slider
                self._poster = vistas_slider.imagen_de(poster)
            except Exception:
                self._poster = None
        self.setFixedHeight(self.ALTO)                 # v5.99 «Línea de tiempo»: todo póster, con el nombre encima (sin descripción:
        self.setCursor(Qt.CursorShape.PointingHandCursor)   # la dice el escenario al verla)

    # (lo mismo que TarjetaEfecto, para que la página y la sección las traten igual)
    def poner_seleccionada(self, v):
        if bool(v) != self._sel:
            self._sel = bool(v)
            self._t_sel = _reloj_ms() if self._sel else 0.0
            self.update()

    def poner_vista(self, v):
        if bool(v) != self._vista:
            self._vista = bool(v)
            self.update()

    def poner_visible(self, _v):
        pass

    def refrescar_vista(self):
        """El reloj de la página (solo con la tarjeta a la vista): el resalte entra y sale suave y el check rebota."""
        obj = 1.0 if (self._hover or self._vista) else 0.0
        cambia = abs(self._h - obj) > 0.01
        if cambia:
            self._h += (obj - self._h) * 0.38
            if abs(self._h - obj) <= 0.01:
                self._h = obj
        if cambia or (self._sel and _reloj_ms() - self._t_sel < self.POP_MS + 40):
            self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        if getattr(self, '_reloj_encima', None) is None:
            from PySide6.QtCore import QTimer
            self._reloj_encima = QTimer(self)
            self._reloj_encima.setSingleShot(True)
            self._reloj_encima.setInterval(self.ESPERA_MS)
            self._reloj_encima.timeout.connect(lambda: self.encima.emit(self.ident))
        self._reloj_encima.start()

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        if getattr(self, '_reloj_encima', None) is not None:
            self._reloj_encima.stop()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self.ident)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        h = self._h
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        if self._sel:
            p.setBrush(QColor(46, 211, 155, 18 + int(6 * h)))
            p.setPen(QPen(QColor(46, 211, 155, 150 + int(60 * h)), 1.6))
        elif self._vista:
            p.setBrush(QColor(255, 255, 255, 15))
            p.setPen(QPen(QColor(255, 255, 255, 105), 1.4))
        else:
            p.setBrush(QColor(255, 255, 255, 6 + int(9 * h)))
            p.setPen(QPen(QColor(255, 255, 255, 16 + int(30 * h)), 1))
        p.drawRoundedRect(r, 14, 14)
        if self._sel:                                  # el halo de la elegida
            p.setPen(QPen(QColor(46, 211, 155, 30), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), 15, 15)
        borde = 2.0 if (self._sel or self._vista) else 1.0
        mini = QRectF(borde, borde, self.width() - 2 * borde, self.height() - 2 * borde)
        camino = QPainterPath()
        camino.addRoundedRect(mini, 13, 13)
        p.save()
        p.setClipPath(camino)
        if self._poster is not None and not self._poster.isNull():
            img = self._poster
            esc = max(mini.width() / img.width(), mini.height() / img.height()) * (1.0 + 0.05 * h)
            w, hh = img.width() * esc, img.height() * esc
            destino = QRectF(mini.center().x() - w / 2, mini.center().y() - hh / 2, w, hh)
            if h < 0.005:                              # v5.99: quieta, el póster ya escalado (antes se reescalaba en cada repintado)
                dpr = self.devicePixelRatioF()
                clave = (round(w * dpr), round(hh * dpr))
                if getattr(self, '_poster_esc', (None,))[0] != clave:
                    pm = QPixmap.fromImage(img.scaled(clave[0], clave[1], Qt.AspectRatioMode.IgnoreAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
                    pm.setDevicePixelRatio(dpr)
                    self._poster_esc = (clave, pm)
                p.drawPixmap(destino.topLeft(), self._poster_esc[1])
            else:
                p.drawImage(destino, img)
        else:
            p.fillRect(mini, QColor('#0B1424'))
            p.setPen(QColor(MUT))
            p.setFont(ui.fuente(26))
            p.drawText(mini, int(Qt.AlignmentFlag.AlignCenter), 'A')
        if self._vista and not self._sel:              # la que se ve en el escenario (la elegida ya lleva su check)
            p.setFont(ui.fuente(11.5, peso='negrita'))
            texto = tr('Viendo')
            ancho = QFontMetricsF(p.font()).horizontalAdvance(texto) + 34
            b = QRectF(mini.left() + 8, mini.top() + 8, ancho, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(8, 14, 26, 195))
            p.drawRoundedRect(b, 13, 13)
            tri = QPainterPath()
            tri.moveTo(b.left() + 11, b.center().y() - 4.5)
            tri.lineTo(b.left() + 18, b.center().y())
            tri.lineTo(b.left() + 11, b.center().y() + 4.5)
            tri.closeSubpath()
            p.setBrush(QColor('#FFFFFF'))
            p.drawPath(tri)
            p.setPen(QColor('#FFFFFF'))
            p.drawText(QRectF(b.left() + 24, b.top(), ancho - 26, b.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
        from PySide6.QtGui import QLinearGradient       # el nombre, sobre un degradado oscuro al pie del póster
        pie = QRectF(mini.left(), mini.bottom() - 62, mini.width(), 62)
        g = QLinearGradient(pie.topLeft(), pie.bottomLeft())
        g.setColorAt(0.0, QColor(4, 9, 18, 0))
        g.setColorAt(1.0, QColor(4, 9, 18, 235))
        p.fillRect(pie, g)
        x, ancho = mini.left() + 12, mini.width() - 24
        p.setPen(QColor('#FFFFFF') if (self._sel or h > 0.5) else QColor('#EDF2FA'))
        p.setFont(ui.fuente(13.5, peso='negrita'))
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(x, mini.bottom() - 32, ancho, 22), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   fm.elidedText(self.nombre, Qt.TextElideMode.ElideRight, ancho))
        p.restore()
        if self._sel:                                  # la que usará GO (al elegirla, el check rebota: 0,55 → 1,08 → 1)
            t = min(1.0, (_reloj_ms() - self._t_sel) / self.POP_MS) if self._t_sel else 1.0
            s = 1.70158
            esc = 0.55 + 0.45 * (1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2)
            c0 = QRectF(mini.right() - 34, mini.top() + 10, 24, 24)
            c = QRectF(c0.center().x() - 12 * esc, c0.center().y() - 12 * esc, 24 * esc, 24 * esc)
            if t < 1.0:
                p.setPen(QPen(QColor(46, 211, 155, int(120 * (1 - t))), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                anillo = 12 + 9 * t
                p.drawEllipse(c0.center(), anillo, anillo)
            p.setPen(QPen(QColor(5, 32, 22, 60), 4))
            p.setBrush(QColor(VERDE))
            p.drawEllipse(c)
            p.setPen(QPen(QColor('#052016'), 2.5 * esc, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            k, ox, oy = esc, c.left(), c.top()
            ch = QPainterPath()
            ch.moveTo(ox + 6.5 * k, oy + 12.5 * k)
            ch.lineTo(ox + 10.2 * k, oy + 16 * k)
            ch.lineTo(ox + 17.5 * k, oy + 8 * k)
            p.drawPath(ch)
        if self._sel or self._vista:                   # (el borde, encima del póster)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(VERDE) if self._sel else QColor(255, 255, 255, 150), 2))
            p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 14, 14)
        p.end()


class RejillaOpciones(QWidget):
    """Las opciones de una sección en columnas: las justas para que quepan en DOS filas (5 para 9 opciones, 6 para 11-12), menos si la
    columna es estrecha; cada tarjeta entre ANCHO_MIN y ANCHO_MAX (alineadas a la izquierda)."""
    ANCHO_MIN, ANCHO_MAX, HUECO = 132, 320, 14
    PROPORCION = 1.12                                  # alto / ancho de cada tarjeta
    alto_max = None                                    # v5.99: el alto que hay (lo pone la página): las tarjetas crecen hasta llenarlo

    def __init__(self, cartas, padre=None):
        super().__init__(padre)
        self.cartas = list(cartas)
        self._capa = QGridLayout(self)
        self._capa.setContentsMargins(0, 0, 0, 0)
        self._capa.setHorizontalSpacing(self.HUECO)
        self._capa.setVerticalSpacing(self.HUECO)
        self._capa.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)   # (v5.99: centrada, sin banda vacía a un lado)
        # (el mínimo NO lo pone la rejilla: con 6 columnas serían ~1100 px y nunca podría repartir menos; se reparte al cambiar de ancho)
        self._capa.setSizeConstraint(QGridLayout.SizeConstraint.SetNoConstraint)
        self._cols, self._ancho_c = 0, 0
        self._repartir(max(1, min(3, len(self.cartas))), self.ANCHO_MAX)

    def _cols_para(self, ancho):
        import math
        n = max(1, len(self.cartas))
        cols = max(1, min(6, max(3, math.ceil(n / 2)), n))
        while cols > 1 and ancho < cols * self.ANCHO_MIN + (cols - 1) * self.HUECO:
            cols -= 1
        return cols

    def _repartir(self, cols, ancho_c):
        if cols != self._cols:
            self._cols = cols
            for c in self.cartas:
                self._capa.removeWidget(c)
            for i, c in enumerate(self.cartas):
                self._capa.addWidget(c, i // cols, i % cols)
        if ancho_c != self._ancho_c:
            self._ancho_c = ancho_c
            for c in self.cartas:                      # (v5.99: casi cuadradas, todo póster: 5 + 4 caben sin desplazar)
                c.setFixedSize(ancho_c, int(ancho_c * self.PROPORCION))
        self.updateGeometry()

    def _alto(self):
        import math
        filas = math.ceil(len(self.cartas) / max(1, self._cols)) if self.cartas else 0
        alto_c = self.cartas[0].height() if self.cartas else 0
        return filas * alto_c + max(0, filas - 1) * self.HUECO

    def minimumSizeHint(self):
        return QSize(self.ANCHO_MIN, self._alto())

    def sizeHint(self):
        return QSize(self.ANCHO_MIN, self._alto())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reajustar()

    def poner_alto_max(self, alto):
        alto = int(alto) if alto and alto > 0 else None
        if alto != self.alto_max:
            self.alto_max = alto
            self._reajustar()

    def _reajustar(self):
        import math
        a = self.width()
        cols = self._cols_para(a)
        ancho_c = (a - (cols - 1) * self.HUECO) / cols
        if self.alto_max:                              # (que las filas quepan en el alto que hay, sin desplazar)
            filas = math.ceil(len(self.cartas) / cols) if self.cartas else 1
            ancho_c = min(ancho_c, (self.alto_max - (filas - 1) * self.HUECO) / filas / self.PROPORCION)
        self._repartir(cols, int(max(self.ANCHO_MIN, min(self.ANCHO_MAX, ancho_c))))

    def mostrar(self, _carta):
        pass                                           # (la rejilla no se desliza: se ven todas)


# ====================================================================================== «GO usará» y «Dónde va en tu video»
class TarjetaUsara(QWidget):
    """«GO usará: Violeta · con Riser 1»: el póster de la elegida, su nombre en grande y lo que la acompaña; apagada, en gris («Apagada»)."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFixedHeight(128)
        self._img, self._nombre, self._sub, self._on = None, '', '', False
        self._ruta = None

    def poner(self, poster, nombre, sub, on):
        ruta = str(poster) if poster else None
        if ruta != self._ruta:
            self._ruta = ruta
            try:
                import vistas_slider
                self._img = vistas_slider.imagen_de(ruta) if ruta else None
            except Exception:
                self._img = None
        self._nombre, self._sub, self._on = nombre, sub, bool(on)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._on:
            p.setBrush(QColor(46, 211, 155, 18))
            p.setPen(QPen(QColor(46, 211, 155, 80), 1))
        else:
            p.setBrush(QColor(255, 255, 255, 8))
            p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawRoundedRect(r, 16, 16)
        mini = QRectF(12, 12, 62, self.height() - 24)
        camino = QPainterPath()
        camino.addRoundedRect(mini, 10, 10)
        p.save()
        p.setClipPath(camino)
        if self._img is not None and not self._img.isNull():
            img = self._img
            esc = max(mini.width() / img.width(), mini.height() / img.height())
            w, h = img.width() * esc, img.height() * esc
            if not self._on:
                p.setOpacity(0.45)
            p.drawImage(QRectF(mini.center().x() - w / 2, mini.center().y() - h / 2, w, h), img)
            p.setOpacity(1.0)
        else:
            p.fillRect(mini, QColor('#0B1424'))
        p.restore()
        x = mini.right() + 16
        ancho = self.width() - x - (52 if self._on else 16)
        p.setFont(ui.fuente(11, peso='negrita'))
        p.setPen(QColor('#5FD9AE') if self._on else QColor('#7F8CA4'))
        p.drawText(QRectF(x, 30, ancho, 16), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   (tr('GO usará') if self._on else tr('Apagada')).upper())
        p.setFont(ui.fuente(20, peso='extra'))
        p.setPen(QColor('#FFFFFF') if self._on else QColor('#AEBBCF'))
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(x, 48, ancho, 30), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   fm.elidedText(self._nombre, Qt.TextElideMode.ElideRight, ancho))
        p.setFont(ui.fuente(12))
        p.setPen(QColor(MUT))
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(x, 80, ancho, 18), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   fm.elidedText(self._sub, Qt.TextElideMode.ElideRight, ancho))
        if self._on:
            c = QRectF(self.width() - 42, self.height() / 2 - 13, 26, 26)
            p.setPen(QPen(QColor(46, 211, 155, 50), 4))
            p.setBrush(QColor(VERDE))
            p.drawEllipse(c)
            p.setPen(QPen(QColor('#052016'), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            ch = QPainterPath()
            ch.moveTo(c.left() + 7, c.top() + 13.5)
            ch.lineTo(c.left() + 11, c.top() + 17.5)
            ch.lineTo(c.left() + 19, c.top() + 9)
            p.drawPath(ch)
        p.end()


def _mmss(s):
    s = max(0, int(round(s)))
    return f'{s // 60}:{s % 60:02d}'


class LineaDonde(QWidget):
    """«Dónde va en tu video»: la duración del video de Inicio y los tramos donde va el efecto (el gancho: el primer segundo; los demás: las
    posiciones marcadas). Sin video o sin duración aún, solo la pista."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFixedHeight(56)
        self._dur, self._tramos = None, []

    def poner(self, duracion, tramos):
        """tramos = [(ini_s, fin_s, color)]."""
        self._dur = float(duracion) if duracion else None
        self._tramos = list(tramos or [])
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(QColor(255, 255, 255, 8))
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.drawRoundedRect(r, 12, 12)
        pista = QRectF(12, 14, self.width() - 24, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(pista, 6, 6)
        # (sin la duración del video, una de referencia de 30 s: el primer segundo del gancho se ve como lo que es, un trocito al principio)
        dur = self._dur or max([f for _i, f, _c in self._tramos] + [30.0])
        if dur > 0:
            for ini, fin, color in self._tramos:
                x0 = pista.left() + pista.width() * max(0.0, ini) / dur
                x1 = pista.left() + pista.width() * min(dur, fin) / dur
                ancho = max(14.0, x1 - x0)
                c = QColor(color)
                fuerte = c.name().upper() == QColor(VERDE).name().upper()
                if fuerte:
                    halo = QColor(c)
                    halo.setAlpha(70)
                    p.setBrush(halo)
                    p.drawRoundedRect(QRectF(x0 - 3, pista.top() - 5, ancho + 6, pista.height() + 10), 8, 8)
                    p.setBrush(c)
                    p.drawRoundedRect(QRectF(x0, pista.top() - 3, ancho, pista.height() + 6), 6, 6)
                else:
                    c.setAlpha(150)
                    p.setBrush(c)
                    p.drawRoundedRect(QRectF(x0, pista.top(), ancho, pista.height()), 6, 6)
        if self._dur:
            p.setFont(ui.fuente(11.5))
            p.setPen(QColor('#7F8CA4'))
            for frac, al in ((0.0, Qt.AlignmentFlag.AlignLeft), (0.5, Qt.AlignmentFlag.AlignHCenter), (1.0, Qt.AlignmentFlag.AlignRight)):
                x = pista.left() + pista.width() * frac
                caja = QRectF(x - (0 if frac == 0 else (60 if frac == 1 else 30)), 32, 60, 18)
                p.drawText(caja, int(al | Qt.AlignmentFlag.AlignVCenter), _mmss(self._dur * frac))
        p.end()


_DURACIONES, _ESPERAN = {}, {}


def duracion_video(ruta, quien, al_saber):
    """La duración del video (s) si ya se sabe; si no, None y se averigua en un hilo (al saberla llama a los al_saber() que esperan: una
    lectura por video aunque la pidan todas las secciones). Sin leer nada en la interfaz."""
    if not ruta:
        return None
    k = str(ruta)
    if _DURACIONES.get(k):
        return _DURACIONES[k]
    esperan = _ESPERAN.get(k)
    if esperan is not None:                            # (ya se está leyendo)
        if al_saber not in esperan:
            esperan.append(al_saber)
        return None
    if k in _DURACIONES:                               # (se leyó y no se pudo)
        return None
    _ESPERAN[k] = [al_saber]

    def leer():
        import posiciones_pro as POS
        return POS._duracion(k)

    def fin(r, error):
        _DURACIONES[k] = float(r or 0.0) if error is None else 0.0
        for f in _ESPERAN.pop(k, []):
            try:
                f()
            except RuntimeError:                       # (la sección ya no existe)
                pass
    ui.correr_en_hilo(quien, leer, fin)
    return None


class _Pantalla(QWidget):
    """El ejemplo en grande (9:16): el cuadro del reproductor o el póster.
    v5.93 (ronda 2): al cambiar de opción, la anterior se funde (FUNDIDO_MS) en vez de cortar; tras «Usar», la animación de
    confirmación de Higgsfield (`ok_anim.png`: aro + check que se dibujan) sobre un velo, y se va sola."""
    FUNDIDO_MS = 260
    OK_QUIETO_MS = 520                                 # el check terminado, quieto, antes de irse
    OK_SALIDA_MS = 260

    def __init__(self, padre=None):
        super().__init__(padre)
        self.reprod, self.poster, self._img = None, None, None
        self._antes, self._t_cambio = None, 0.0        # lo que se veía antes del cambio (se funde)
        self._t_ok = 0.0                               # cuándo se pulsó «Usar» (0 = nada)

    def _anima(self):
        ahora = _reloj_ms()
        if self._antes is not None and ahora - self._t_cambio < self.FUNDIDO_MS + 40:
            return True
        return bool(self._t_ok) and ahora - self._t_ok < self._dur_ok() + 40

    def _dur_ok(self):
        n = len(animacion_ui('ok', 120)) or 12
        return n * 40 + self.OK_QUIETO_MS + self.OK_SALIDA_MS

    def tic(self):
        img = self.reprod.imagen() if self.reprod is not None else None
        if img is not self._img or self._anima():
            self.update()
        elif self._antes is not None and _reloj_ms() - self._t_cambio >= self.FUNDIDO_MS:
            self._antes = None
        if self._t_ok and _reloj_ms() - self._t_ok >= self._dur_ok():
            self._t_ok = 0.0
            self.update()

    def cambiar(self):
        """Lo que se ve ahora pasa a fundirse (llamar ANTES de poner el reproductor / póster nuevos)."""
        img = self._img or self.poster
        self._antes = img if (img is not None and not img.isNull()) else None
        self._t_cambio = _reloj_ms()

    def confirmar(self):
        self._t_ok = _reloj_ms()
        self.update()

    BRILLO = 16                                        # el margen del halo alrededor del móvil (propuesta A: el ejemplo es el protagonista)

    def _rect(self):
        m = self.BRILLO
        ancho = min(self.width() - 2 * m, (self.height() - 2 * m) * 9 / 16)
        alto = ancho * 16 / 9
        return QRectF((self.width() - ancho) / 2, (self.height() - alto) / 2, ancho, alto)

    def tam_fisico(self):
        """(ancho, alto) en píxeles de pantalla del cuadro 9:16: el reproductor escala ahí (en su hilo), no al pintar."""
        ancho = self._rect().width()
        dpr = self.devicePixelRatioF()
        return (int(ancho * dpr), int(ancho * 16 / 9 * dpr)) if ancho > 8 else None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.reprod is not None:
            self.reprod.tam = self.tam_fisico()

    @staticmethod
    def _cubrir(p, r, img, opacidad=1.0):
        if img is None or img.isNull():
            return
        esc = max(r.width() / img.width(), r.height() / img.height())
        w, h = img.width() * esc, img.height() * esc
        if opacidad < 1.0:
            p.setOpacity(opacidad)
        p.drawImage(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), img)
        p.setOpacity(1.0)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self._rect()
        p.setPen(Qt.PenStyle.NoPen)                    # el halo: unas capas suaves alrededor del móvil (dibujadas, sin efectos de Qt)
        for k in range(6, 0, -1):
            p.setBrush(QColor(70, 200, 210, int(5 + 3 * (6 - k))))
            p.drawRoundedRect(r.adjusted(-2.4 * k, -2.4 * k, 2.4 * k, 2.4 * k), 28 + 2 * k, 28 + 2 * k)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawRoundedRect(r.adjusted(-0.5, -0.5, 0.5, 0.5), 28, 28)
        camino = QPainterPath()
        camino.addRoundedRect(r, 28, 28)
        p.setClipPath(camino)
        ahora = _reloj_ms()
        img = self.reprod.imagen() if self.reprod is not None else None
        self._img = img
        img = img or self.poster
        if img is not None and not img.isNull():
            self._cubrir(p, r, img)
        else:
            p.fillRect(r, QColor('#0B1424'))
        if self._antes is not None:                    # la opción de antes, fundiéndose
            k = (ahora - self._t_cambio) / self.FUNDIDO_MS
            if k < 1.0:
                self._cubrir(p, r, self._antes, 1.0 - _suave(k))
        rep = self.reprod
        dur = float(getattr(rep, 'duracion', 0) or 0) if rep is not None else 0.0
        if dur > 0:                                      # la barra de avance del ejemplo (abajo, como un reproductor)
            pos = min(dur, float(getattr(rep, 'posicion', 0) or 0))
            barra = QRectF(r.left() + 14, r.bottom() - 54, r.width() - 28, 40)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(8, 14, 26, 170))
            p.drawRoundedRect(barra, 20, 20)
            cy = barra.center().y()
            tri = QPainterPath()
            tri.moveTo(barra.left() + 16, cy - 6)
            tri.lineTo(barra.left() + 26, cy)
            tri.lineTo(barra.left() + 16, cy + 6)
            tri.closeSubpath()
            p.setBrush(QColor('#FFFFFF'))
            p.drawPath(tri)
            p.setFont(ui.fuente(11))
            p.setPen(QColor('#E6EDF8'))
            t0, t1 = f'{int(pos) // 60}:{int(pos) % 60:02d}', f'{int(round(dur)) // 60}:{int(round(dur)) % 60:02d}'
            p.drawText(QRectF(barra.left() + 34, barra.top(), 40, barra.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), t0)
            p.drawText(QRectF(barra.right() - 50, barra.top(), 36, barra.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), t1)
            pista = QRectF(barra.left() + 74, cy - 2, barra.width() - 74 - 58, 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 60))
            p.drawRoundedRect(pista, 2, 2)
            p.setBrush(QColor('#FFFFFF'))
            p.drawRoundedRect(QRectF(pista.left(), pista.top(), pista.width() * pos / dur, pista.height()), 2, 2)
        if self._t_ok:                                   # «Usar»: el aro y el check se dibujan sobre un velo y se van
            self._pintar_ok(p, r, ahora - self._t_ok)
        p.end()

    def _pintar_ok(self, p, r, t):
        cuadros = animacion_ui('ok', 120)
        n = len(cuadros)
        dibujo = n * 40 if n else 360
        salida = max(0.0, t - dibujo - self.OK_QUIETO_MS) / self.OK_SALIDA_MS
        if salida >= 1.0:
            return
        vis = (min(1.0, t / 140.0)) * (1.0 - _suave(salida))
        c = r.center()
        p.setOpacity(vis)
        p.fillRect(r, QColor(5, 10, 20, 120))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 16, 30, 200))
        p.drawEllipse(c, 74, 74)
        if cuadros:
            k = min(n - 1, int(t // 40))
            pm = cuadros[k]
            lado = pm.width() / pm.devicePixelRatio()
            p.drawPixmap(int(c.x() - lado / 2), int(c.y() - lado / 2), pm)
        else:                                            # (sin la animación: un check dibujado que se traza)
            k = _suave(min(1.0, t / dibujo))
            p.setPen(QPen(QColor(VERDE), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(c.x() - 44, c.y() - 44, 88, 88), 90 * 16, int(-360 * 16 * k))
            if k > 0.5:
                camino = QPainterPath()
                camino.moveTo(c.x() - 18, c.y() + 2)
                camino.lineTo(c.x() - 5, c.y() + 15)
                camino.lineTo(c.x() + 20, c.y() - 13)
                p.drawPath(camino)
        p.setOpacity(1.0)


class PanelVista(QWidget):
    """El escenario (propuesta A): el ejemplo de la opción que se mira en grande, en un móvil con su halo; debajo su nombre y su
    descripción, «Ver otra vez» y «Usar …» (o «En uso», con su check, si ya es la elegida)."""
    usar = Signal(str)
    otra_vez = Signal(str)

    def __init__(self, padre=None):
        super().__init__(padre)
        self.ident, self.nombre, self._ruta, self._en_uso = '', '', None, False
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(4)
        self.pantalla = _Pantalla(self)
        capa.addWidget(self.pantalla, 1)
        capa.addSpacing(4)
        self._titulo = Etiqueta('', 17, peso='negrita', color='#FFFFFF')
        self._titulo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        capa.addWidget(self._titulo)
        self._sub = Etiqueta('', 12, color=MUT, envolver=True)
        self._sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        capa.addWidget(self._sub)
        capa.addSpacing(10)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        from PySide6.QtGui import QIcon
        pm_o, self._ico_ok = icono_ui('b_otra_vez', 18), icono_ui('b_usar', 18)
        self._ico_ok = QIcon(self._ico_ok) if self._ico_ok is not None else QIcon()
        self._b_otra = Boton(tr('Ver otra vez'), lambda: self.otra_vez.emit(self.ident), alto=42, tam=13,
                             icono=QIcon(pm_o) if pm_o is not None else None, lado_icono=18)
        self._b_usar = Boton('', self._pulsar_usar, tipo='primario', alto=42, tam=13, negrita=True)
        self._b_usar.setIconSize(QSize(18, 18))
        fila.addWidget(self._b_otra, 1)
        fila.addWidget(self._b_usar, 1)
        capa.addLayout(fila)

    def _pulsar_usar(self):
        if not self._en_uso:                           # («En uso» ya es la elegida: pulsarlo no hace nada)
            self.usar.emit(self.ident)

    def confirmar(self):
        """Tras «Usar»: la animación de confirmación sobre el ejemplo."""
        self.pantalla.confirmar()

    def poner(self, ident, nombre, mp4=None, jpg=None, en_uso=False, detalle=''):
        """Enseña la opción `ident` (su mp4 en bucle; el póster mientras arranca)."""
        from PySide6.QtGui import QIcon
        self.ident, self.nombre, self._en_uso = ident, nombre, bool(en_uso)
        self._titulo.setText(nombre)
        self._sub.setText(detalle or tr('El ejemplo de cómo queda; GO lo adapta a tu video.'))
        self._b_usar.setText(tr('En uso') if en_uso else tr('Usar {n}', n=nombre))
        self._b_usar.poner_tipo('secundario' if en_uso else 'primario')
        self._b_usar.setIcon(self._ico_ok if en_uso else QIcon())
        self._b_usar.setCursor(Qt.CursorShape.ArrowCursor if en_uso else Qt.CursorShape.PointingHandCursor)
        ruta = str(mp4) if mp4 else None
        if ruta != self._ruta:
            self.pantalla.cambiar()                    # la de antes se funde
            if self.pantalla.reprod is not None:
                self.pantalla.reprod.parar()
            self.pantalla.reprod = None
            self._ruta = ruta
            if ruta:
                try:
                    import vistas_slider
                    self.pantalla.reprod = vistas_slider.Reproductor(ruta)
                    self.pantalla.reprod.tam = self.pantalla.tam_fisico()
                    if self.isVisible():
                        self.pantalla.reprod.arrancar()
                except Exception:
                    self.pantalla.reprod = None
            try:
                import vistas_slider
                self.pantalla.poster = vistas_slider.imagen_de(jpg) if jpg else None
            except Exception:
                self.pantalla.poster = None
        self.pantalla.update()

    def reiniciar(self):
        r = self.pantalla.reprod
        if r is not None:
            r.parar()
            try:
                import vistas_slider
                self.pantalla.cambiar()
                self.pantalla.reprod = vistas_slider.Reproductor(self._ruta)
                self.pantalla.reprod.tam = self.pantalla.tam_fisico()
                self.pantalla.reprod.arrancar()
            except Exception:
                pass

    def tic(self, visible):
        r = self.pantalla.reprod
        if not visible:
            if r is not None:
                r.parar()
            return
        if r is not None:
            r.arrancar()
        self.pantalla.tic()
