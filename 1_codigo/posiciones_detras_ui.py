# CineCaptions · By Cinema Productions
# 1_codigo/posiciones_detras_ui.py — Efectos › «Captions detrás de ti» › Posición con el diseño nuevo (v5.32): cabecera, visor, panel y tira.
"""
v5.32 (el usuario, con su maqueta: «aplica ese diseño»): la vista «Posición» de «Captions detrás de ti» en cuatro zonas.
  · CABECERA (CabeceraDetras): volver, el título con su resumen, el estado del proyecto y «Elegir video» · «Quitar todas» · «Listo».
  · VISOR (VisorDetras): cómo queda el caption detrás de ti en el cabezal (posiciones_pro.vista_detras) y, al darle a reproducir, el video con
    su sonido (ReproductorVisor: PyAV en un hilo, sin Qt multimedia); debajo, reproducir, el tiempo, la barra para moverse, sonido y ampliar.
  · PANEL (PanelDetras) con pestañas: Ajustes (modo de marcas; posición del caption —en vertical, siempre arriba; en horizontal arriba,
    izquierda o derecha (edicion_pro.posicion_detras)—; intensidad; el estado de la detección de la persona; una sugerencia), Marcas y
    Sugerencias.
  · TIRA: posiciones_pro.LineaTiempo en modo compacto (solo fotogramas, marcas y el cabezal).
Los datos y las reglas siguen en posiciones_pro (LineaTiempo) y edicion_pro; aquí solo se dibuja y se reparte. armar(vista) lo monta dentro de
posiciones_pro.VistaPosiciones con los mismos nombres que usan sus métodos (_v_modo, _botones, _fila_prog…).
"""
import threading
import time

from i18n import tr
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

import qt_kit as ui
from qt_kit import Boton, Etiqueta, QColor, QColorReal, StringVar, fuente

MUTED = '#8EA2C6'
CLARO = '#E6EEFB'
VERDE, AMBAR, ROJO = '#34D399', '#F5B544', '#F87171'
_ICONOS = {}


def _icono(nombre, color='#C9D6EC'):
    """Un icono de línea (Phosphor) en caché por nombre y color; None si qtawesome no está."""
    k = (nombre, color)
    if k not in _ICONOS:
        _ICONOS[k] = ui.icono_linea('ph.' + nombre, color)
    return _ICONOS[k]


def _alfa(color, a):
    q = QColor(color)                                                    # (el del tema; QColorReal no acepta la subclase al copiar)
    return QColorReal(q.red(), q.green(), q.blue(), int(a))


def _acento():
    return QColor(ui.ACCENT)


def _pintar_icono(p, nombre, color, rect):
    ic = _icono(nombre, color)
    if ic is not None:
        ic.paint(p, rect.toRect())


class _Texto:
    """Lo que antes era una etiqueta de la vista (el nombre del video, la nota del modo): aquí lo pinta otro (`al_cambiar`)."""
    def __init__(self, al_cambiar=None):
        self._t = ''
        self._f = al_cambiar

    def setText(self, t):
        self._t = str(t or '')
        if self._f:
            self._f()

    def text(self):
        return self._t


class _Caja(QWidget):
    """Un panel del diseño: fondo apenas más claro, borde de 1 px y esquinas redondas (pintado; sin efectos de Qt)."""
    def __init__(self, padre=None, margenes=(14, 12, 14, 12), espacio=8, horizontal=False, radio=16, fondo=(255, 255, 255, 7),
                 borde=(255, 255, 255, 24)):
        super().__init__(padre)
        self.capa = (QHBoxLayout if horizontal else QVBoxLayout)(self)
        self.capa.setContentsMargins(*margenes)
        self.capa.setSpacing(espacio)
        self._radio, self._fondo, self._borde = radio, fondo, borde

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColorReal(*self._borde), 1))
        p.setBrush(QColorReal(*self._fondo))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self._radio, self._radio)
        p.end()


class _Pestana(QAbstractButton):
    """Una pestaña del panel: icono + texto; la elegida en el color de acento con su raya debajo."""
    def __init__(self, texto, icono, padre=None):
        super().__init__(padre)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(48)
        self._texto, self._ic = texto, icono

    def poner_texto(self, t):
        if t != self._texto:
            self._texto = t
            self.updateGeometry()
            self.update()

    def sizeHint(self):
        return QSize(int(QFontMetricsF(fuente(14, peso='medio')).horizontalAdvance(self._texto)) + 62, 48)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        acento = _acento()
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alfa(acento, 24))
            p.drawRoundedRect(r.adjusted(2, 2, -2, -1), 10, 10)
            p.fillRect(QRectF(r.left() + 10, r.bottom() - 2.5, r.width() - 20, 2.5), acento)
        elif self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColorReal(255, 255, 255, 10))
            p.drawRoundedRect(r.adjusted(2, 2, -2, -1), 10, 10)
        color = acento.name() if self.isChecked() else '#C9D6EC'
        p.setFont(fuente(14, peso='medio'))
        w_txt = QFontMetricsF(p.font()).horizontalAdvance(self._texto)
        x = r.center().x() - (w_txt + 26) / 2.0
        _pintar_icono(p, self._ic, color, QRectF(x, r.center().y() - 9, 18, 18))
        p.setPen(QColor(color))
        p.drawText(QRectF(x + 26, r.top(), w_txt + 4, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._texto)
        p.end()


class _Opcion(QAbstractButton):
    """Una opción del «Modo de marcas»: círculo de radio, título y una línea; la elegida con el borde de acento."""
    def __init__(self, titulo, detalle, padre=None):
        super().__init__(padre)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setMinimumHeight(64)
        self._titulo, self._detalle = titulo, detalle

    def sizeHint(self):
        return QSize(200, 64)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        acento = _acento()
        sel = self.isChecked()
        p.setPen(QPen(acento if sel else QColorReal(255, 255, 255, 30 if self.underMouse() else 22), 1.6 if sel else 1.0))
        p.setBrush(_alfa(acento, 26) if sel else QColorReal(255, 255, 255, 8))
        p.drawRoundedRect(r, 12, 12)
        c = QPointF(r.left() + 19, r.center().y())
        p.setPen(QPen(acento if sel else QColorReal(255, 255, 255, 120), 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, 8, 8)
        if sel:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(acento)
            p.drawEllipse(c, 4.5, 4.5)
        x = r.left() + 36
        ancho = max(10.0, r.right() - x - 10)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(14, peso='medio'))
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(x, r.top() + 11, ancho, 22), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   fm.elidedText(self._titulo, Qt.TextElideMode.ElideRight, ancho))
        p.setPen(QColor(MUTED))
        p.setFont(fuente(12))
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(x, r.top() + 33, ancho, 20), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   fm.elidedText(self._detalle, Qt.TextElideMode.ElideRight, ancho))
        p.end()


class _Mosaico(QAbstractButton):
    """Una posición del caption: la silueta de la persona y la barra del texto arriba, a la izquierda o a la derecha de su cabeza."""
    def __init__(self, clave, nombre, padre=None):
        super().__init__(padre)
        self.clave, self._nombre = clave, nombre
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedSize(QSize(100, 104))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        acento = _acento()
        sel = self.isChecked()
        caja = QRectF(2, 2, self.width() - 4, 70)
        p.setPen(QPen(acento if sel else QColorReal(255, 255, 255, 34 if self.underMouse() else 22), 1.8 if sel else 1.0))
        p.setBrush(_alfa(acento, 30) if sel else QColorReal(255, 255, 255, 10))
        p.drawRoundedRect(caja, 10, 10)
        cx, cy = caja.center().x(), caja.top() + 32
        barra = _alfa(acento if sel else QColor('#C9D6EC'), 235 if sel else 170)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(barra)
        if self.clave == 'arriba':                                   # (la cabeza tapa un poco el borde de abajo del texto)
            p.drawRoundedRect(QRectF(cx - 22, caja.top() + 12, 44, 10), 3, 3)
        elif self.clave == 'izquierda':
            p.drawRoundedRect(QRectF(cx - 40, cy - 6, 32, 11), 3, 3)
        else:
            p.drawRoundedRect(QRectF(cx + 8, cy - 6, 32, 11), 3, 3)
        persona = QColorReal(205, 214, 232, 255) if sel else QColorReal(150, 163, 188, 255)
        p.setBrush(persona)
        p.drawEllipse(QPointF(cx, cy), 10.5, 10.5)
        hombros = QPainterPath()
        hombros.moveTo(cx - 23, caja.bottom() - 1)
        hombros.cubicTo(cx - 22, cy + 12, cx + 22, cy + 12, cx + 23, caja.bottom() - 1)
        hombros.closeSubpath()
        p.save()
        recorte = QPainterPath()
        recorte.addRoundedRect(caja, 10, 10)
        p.setClipPath(recorte)
        p.drawPath(hombros)
        p.restore()
        p.setPen(acento if sel else QColor('#C9D6EC'))
        p.setFont(fuente(12, peso='medio' if sel else None))
        p.drawText(QRectF(0, 76, self.width(), 24), int(Qt.AlignmentFlag.AlignCenter), self._nombre)
        p.end()


class _TarjetaEstado(QWidget):
    """«Estado del tracking»: si la IA encuentra a la persona en el video (de posiciones_pro.analizar_detras)."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self.setMinimumHeight(84)
        self._d = ('espera', '', '')

    def poner(self, nivel, chip, texto):
        if (nivel, chip, texto) != self._d:
            self._d = (nivel, chip, texto)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColorReal(255, 255, 255, 24), 1))
        p.setBrush(QColorReal(255, 255, 255, 7))
        p.drawRoundedRect(r, 14, 14)
        nivel, chip, texto = self._d
        color = {'bien': VERDE, 'regular': AMBAR, 'mal': ROJO}.get(nivel, MUTED)
        c = QPointF(r.left() + 30, r.center().y())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_alfa(color, 40))
        p.drawEllipse(c, 16, 16)
        p.setBrush(QColor(color))
        p.drawEllipse(c, 12, 12)
        _pintar_icono(p, {'bien': 'check', 'regular': 'warning', 'mal': 'x'}.get(nivel, 'spinner'), '#0B1220', QRectF(c.x() - 8, c.y() - 8, 16, 16))
        x = r.left() + 58
        p.setFont(fuente(12, peso='medio'))
        w_chip = QFontMetricsF(p.font()).horizontalAdvance(chip) + 22 if chip else 0.0
        if chip:
            caja = QRectF(r.right() - 12 - w_chip, r.top() + 12, w_chip, 24)
            p.setBrush(_alfa(color, 34))
            p.drawRoundedRect(caja, 12, 12)
            p.setPen(QColor(color))
            p.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), chip)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(14, peso='medio'))
        p.drawText(QRectF(x, r.top() + 12, max(10.0, r.width() - (x - r.left()) - w_chip - 20), 24),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr('Estado del tracking'))
        p.setPen(QColor(MUTED))
        p.setFont(fuente(12))
        p.drawText(QRectF(x, r.top() + 38, r.right() - x - 12, r.height() - 44),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), texto)
        p.end()


class _TarjetaAyuda(QWidget):
    """«Sugerencia»: un consejo (o, en ámbar, la última nota de la tira: por qué una marca no va). La ✕ la esconde hasta la próxima nota."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self._titulo, self._texto, self._aviso = tr('Sugerencia'), '', False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMinimumHeight(80)

    def poner(self, texto, aviso=False):
        titulo = tr('Aviso') if aviso else tr('Sugerencia')
        if (texto, aviso) != (self._texto, self._aviso):
            self._titulo, self._texto, self._aviso = titulo, texto, aviso
            self._ajustar()
            self.update()

    def _cerrar_rect(self):
        return QRectF(self.width() - 34, 8, 24, 24)

    def _ajustar(self):
        fm = QFontMetricsF(fuente(12))
        alto = fm.boundingRect(QRectF(0, 0, max(60.0, self.width() - 70), 1000),
                               int(Qt.TextFlag.TextWordWrap), self._texto).height()
        self.setMinimumHeight(int(max(80, 44 + alto + 14)))

    def resizeEvent(self, e):
        self._ajustar()
        super().resizeEvent(e)

    def mousePressEvent(self, e):
        if self._cerrar_rect().contains(e.position()):
            self.hide()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        color = AMBAR if self._aviso else '#F5C451'
        p.setPen(QPen(_alfa(color, 70) if self._aviso else QColorReal(255, 255, 255, 24), 1))
        p.setBrush(_alfa(color, 16) if self._aviso else QColorReal(255, 255, 255, 7))
        p.drawRoundedRect(r, 14, 14)
        _pintar_icono(p, 'warning' if self._aviso else 'lightbulb', color, QRectF(r.left() + 16, r.top() + 14, 24, 24))
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(14, peso='medio'))
        p.drawText(QRectF(r.left() + 52, r.top() + 12, r.width() - 96, 26), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self._titulo)
        _pintar_icono(p, 'x', '#8EA2C6', self._cerrar_rect().adjusted(5, 5, -5, -5))
        p.setPen(QColor(CLARO if self._aviso else MUTED))
        p.setFont(fuente(12))
        p.drawText(QRectF(r.left() + 52, r.top() + 40, r.width() - 68, r.height() - 46),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), self._texto)
        p.end()


class _Pildora(QWidget):
    """El estado del proyecto en la cabecera: un punto de color y su texto."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self._t, self._c = '', MUTED
        self.setFixedHeight(32)

    def poner(self, texto, color):
        if (texto, color) != (self._t, self._c):
            self._t, self._c = texto, color
            self.setMinimumWidth(int(QFontMetricsF(fuente(13, peso='medio')).horizontalAdvance(texto)) + 40)
            self.update()

    def paintEvent(self, _e):
        if not self._t:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_alfa(self._c, 50))
        p.drawEllipse(QPointF(r.left() + 12, r.center().y()), 7, 7)
        p.setBrush(QColor(self._c))
        p.drawEllipse(QPointF(r.left() + 12, r.center().y()), 4.5, 4.5)
        p.setPen(QColor('#C9D6EC'))
        p.setFont(fuente(13, peso='medio'))
        p.drawText(QRectF(r.left() + 26, r.top(), r.width() - 26, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self._t)
        p.end()


# ======================================================================================================================== el reproductor
class ReproductorVisor:
    """El video del visor: PyAV lo decodifica en un hilo desde un segundo, al ritmo real, y deja el cuadro de ahora (QImage, ya derecho) y su
    segundo; el sonido (mono) suena aparte con sfx_audio.Reproductor. Sin Qt multimedia (no va en el programa)."""
    def __init__(self):
        self._parar = threading.Event()
        self._parar.set()
        self._hilo = None
        self._sonido = None
        self.img = None
        self.t = 0.0

    @property
    def activo(self):
        return self._hilo is not None and self._hilo.is_alive() and not self._parar.is_set()

    def arrancar(self, video, desde, t0, dur, audio=None, alto=540):
        self.parar()
        self._parar = threading.Event()
        self.t, self.img = float(t0), None
        self._hilo = threading.Thread(target=self._correr, args=(self._parar, str(video), float(desde or 0.0), float(t0), float(dur),
                                                                 str(audio) if audio else None, int(alto)), daemon=True, name='visor-detras')
        self._hilo.start()

    def parar(self):
        self._parar.set()
        s, self._sonido = self._sonido, None
        if s is not None:
            try:
                s.detener()
            except Exception:
                pass

    @staticmethod
    def _audio(ruta, t0, dur):
        """El sonido de [t0, t0 + dur] en mono float32 a sfx_audio.SAMPLE_RATE, o None."""
        import av
        import numpy as np
        import sfx_audio
        sr = sfx_audio.SAMPLE_RATE
        quiero = int(max(0.2, dur) * sr)
        partes, total = [], 0
        with av.open(ruta) as c:
            if not c.streams.audio:
                return None
            st = c.streams.audio[0]
            c.seek(int(max(0.0, t0 - 0.3) / st.time_base), stream=st, backward=True)
            rs = av.AudioResampler(format='flt', layout='mono', rate=sr)
            for fr in c.decode(st):
                if fr.pts is None:
                    continue
                ft = float(fr.pts * st.time_base)
                for g in rs.resample(fr):
                    a = g.to_ndarray().reshape(-1)
                    if ft < t0:
                        a = a[min(len(a), int((t0 - ft) * sr)):]
                    partes.append(a)
                    total += len(a)
                if total >= quiero:
                    break
        if not partes:
            return None
        return np.concatenate(partes)[:quiero].astype(np.float32)

    def _correr(self, parar, video, desde, t0, dur, audio, alto):
        try:
            import av
            import numpy as np
            import rotacion_video as RV
            sonido, onda = None, None
            if audio:
                try:
                    onda = self._audio(audio, t0, dur - t0)
                    if onda is not None:
                        import sfx_audio
                        sonido = sfx_audio.Reproductor()
                except Exception:
                    sonido, onda = None, None
            with av.open(video) as c:
                vs = c.streams.video[0]
                vs.thread_type = 'AUTO'
                c.seek(int(max(0.0, t0 + desde - 0.4) / vs.time_base), stream=vs, backward=True)
                reloj = None
                for fr in c.decode(vs):
                    if parar.is_set():
                        return
                    if fr.pts is None:
                        continue
                    ft = float(fr.pts * vs.time_base) - desde
                    if ft < t0 - 0.02:
                        continue
                    if ft > dur:
                        break
                    if reloj is None:                                     # (el primer cuadro: arranca el sonido y el reloj a la vez)
                        if sonido is not None and not parar.is_set():
                            sonido.reproducir(onda)
                            self._sonido = sonido
                        reloj = time.perf_counter() - (ft - t0)
                    espera = reloj + (ft - t0) - time.perf_counter()
                    if espera > 0:
                        if parar.wait(espera):
                            return
                    elif espera < -0.25:
                        continue                                          # (atrasado: se salta el cuadro, el sonido no espera)
                    q = RV.cuartos(fr)
                    w, h = fr.width, fr.height
                    alto_real = w if q % 2 else h
                    s = min(1.0, float(alto) / max(1.0, float(alto_real)))
                    a = fr.reformat(width=max(2, int(w * s) // 2 * 2), height=max(2, int(h * s) // 2 * 2), format='rgb24').to_ndarray()
                    a = np.ascontiguousarray(RV.derecho_nd(a, q))
                    hh, ww = a.shape[:2]
                    self.img = QImage(a.data, ww, hh, 3 * ww, QImage.Format.Format_RGB888).copy()
                    self.t = ft
        except Exception:
            pass
        finally:
            parar.set()


# ======================================================================================================================== el visor
class VisorDetras(QWidget):
    """La vista grande: cómo queda en el cabezal (o el video, reproduciéndose) y su barra de reproducción."""
    ampliar = Signal()
    ALTO_BARRA = 52

    def __init__(self, vista, padre=None):
        super().__init__(padre)
        self.vista = vista
        self.linea = vista.linea
        self.rep = ReproductorVisor()
        self._reloj = QTimer(self)
        self._reloj.setInterval(33)
        self._reloj.timeout.connect(self._tic)
        self._mudo = False
        self._arrastre = False
        self._ampliado = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMinimumSize(QSize(420, 380))

    # -- geometría
    def _area(self):
        return QRectF(0, 0, self.width(), self.height() - self.ALTO_BARRA - 8)

    def _barra(self):
        return QRectF(0, self.height() - self.ALTO_BARRA, self.width(), self.ALTO_BARRA)

    def _b_play(self):
        b = self._barra()
        return QRectF(b.left() + 14, b.center().y() - 17, 34, 34)

    def _b_ampliar(self):
        b = self._barra()
        return QRectF(b.right() - 44, b.center().y() - 15, 30, 30)

    def _b_sonido(self):
        return self._b_ampliar().translated(-42, 0)

    def _pista(self):
        b = self._barra()
        izq = b.left() + 186
        return QRectF(izq, b.center().y() - 3, max(40.0, self._b_sonido().left() - 22 - izq), 6)

    def _t_de_x(self, x):
        r = self._pista()
        return max(0.0, min(self.linea.dur, (x - r.left()) / max(1.0, r.width()) * self.linea.dur))

    def resizeEvent(self, e):
        self.linea.alto_vista = max(120.0, self._area().height() - 8)
        super().resizeEvent(e)

    # -- reproducir
    def reproduciendo(self):
        return self.rep.activo

    def alternar(self):
        if self.reproduciendo():
            self.parar()
        else:
            self.reproducir()

    def reproducir(self):
        ln = self.linea
        if ln.dur <= 0 or not ln.ruta:
            return
        t0 = ln.cabezal if ln.cabezal is not None else ln.t_ver()
        if t0 >= ln.dur - 0.25:
            t0 = 0.0
        img = getattr(ln, '_imagen', None) or (str(ln.ruta), 0.0, None)
        dpr = max(1.0, float(self.devicePixelRatioF()))
        self.rep.arrancar(img[0] or ln.ruta, img[1] or 0.0, t0, ln.dur, audio=None if self._mudo else ln.ruta,
                          alto=int(min(1080, self._area().height() * dpr)))
        ln.poner_cabezal(t0)
        self._reloj.start()
        self.update()

    def parar(self):
        if self._reloj.isActive() or self.rep.activo:
            self.rep.parar()
            self._reloj.stop()
            self.linea.poner_cabezal(self.rep.t)
        self.update()

    def _tic(self):
        if not self.rep.activo:
            self.parar()
            return
        self.linea.cabezal = self.rep.t
        self.linea.update()
        self.update()

    def hideEvent(self, e):
        self.parar()
        super().hideEvent(e)

    # -- ratón y teclado
    def mousePressEvent(self, e):
        pos = e.position()
        if e.button() != Qt.MouseButton.LeftButton or self.linea.dur <= 0 or self.linea.bloqueada:
            return
        if self._b_play().adjusted(-4, -4, 4, 4).contains(pos) or self._area().contains(pos):
            self.alternar()
        elif self._b_sonido().contains(pos):
            self._mudo = not self._mudo
            if self.reproduciendo():                                     # (con o sin sonido desde donde va)
                self.linea.cabezal = self.rep.t
                self.reproducir()
            self.update()
        elif self._b_ampliar().contains(pos):
            self._ampliado = not self._ampliado
            self.ampliar.emit()
            self.update()
        elif self._pista().adjusted(-6, -14, 6, 14).contains(pos):
            self.parar()
            self._arrastre = True
            self.linea.poner_cabezal(self._t_de_x(pos.x()))
            self.update()

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._arrastre:
            self.linea.poner_cabezal(self._t_de_x(pos.x()))
            self.update()
        mano = (self._b_play().contains(pos) or self._b_sonido().contains(pos) or self._b_ampliar().contains(pos)
                or self._pista().adjusted(-6, -14, 6, 14).contains(pos) or self._area().contains(pos))
        self.setCursor(Qt.CursorShape.PointingHandCursor if mano else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._arrastre = False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            self.alternar()
        else:
            super().keyPressEvent(e)

    # -- dibujo
    def _chip(self, p, x, y, texto, fondo=(0, 0, 0, 160), color='#FFFFFF', derecha=False):
        p.setFont(fuente(12, peso='medio'))
        w = QFontMetricsF(p.font()).horizontalAdvance(texto) + 20
        caja = QRectF(x - w if derecha else x, y, w, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColorReal(*fondo))
        p.drawRoundedRect(caja, 8, 8)
        p.setPen(QColor(color))
        p.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), texto)
        return caja

    def paintEvent(self, _e):
        import posiciones_pro as POS
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        ln = self.linea
        area = self._area()
        camino = QPainterPath()
        camino.addRoundedRect(area, 16, 16)
        p.fillPath(camino, QColorReal(5, 9, 18, 255))
        hay = ln.dur > 0 and not ln.aviso
        jugando = self.reproduciendo()
        t = self.rep.t if jugando else (ln.t_ver() if hay else 0.0)
        info, est, color = None, '', None
        if hay:
            if jugando and self.rep.img is not None:
                img = self.rep.img
                origen, dibujar = QRectF(img.rect()), (lambda r: p.drawImage(r, img, QRectF(img.rect())))
            else:
                pm, info, _m, est, color = ln.vista_en(t)
                origen = QRectF(pm.rect()) if pm is not None and not pm.isNull() else None
                dibujar = (lambda r: p.drawPixmap(r, pm, QRectF(pm.rect()))) if origen is not None else None
            if origen is not None and origen.width() > 0 and origen.height() > 0:
                k = min(area.width() / origen.width(), area.height() / origen.height())
                w, h = origen.width() * k, origen.height() * k
                r = QRectF(area.center().x() - w / 2, area.center().y() - h / 2, w, h)
                p.save()
                p.setClipPath(camino)
                dibujar(r)
                p.restore()
        else:
            p.setPen(QColor(MUTED))
            p.setFont(fuente(14, peso='medio'))
            p.drawText(area, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), ln.aviso or tr('Sin video.'))
        p.setPen(QPen(QColorReal(255, 255, 255, 30), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(camino)
        nombre = self.vista._lbl_video.text()
        if nombre:
            self._chip(p, area.left() + 14, area.top() + 14, nombre)
        tema = (ln.captions or {}).get('nombre') or ''
        if tema and hay:
            self._chip(p, area.right() - 14, area.top() + 14, tema, derecha=True)
        if hay and not jugando and est:                                   # ¿aquí queda bien? (verde / ámbar)
            p.setFont(fuente(13, peso='medio'))
            fm = QFontMetricsF(p.font())
            texto = fm.elidedText(est, Qt.TextElideMode.ElideRight, area.width() - 80)
            w = fm.horizontalAdvance(texto) + 40
            caja = QRectF(area.left() + 14, area.bottom() - 44, w, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColorReal(4, 8, 16, 215))
            p.drawRoundedRect(caja, 15, 15)
            p.setBrush(QColor(color or MUTED))
            p.drawEllipse(QPointF(caja.left() + 16, caja.center().y()), 4.5, 4.5)
            p.setPen(QColor(color or MUTED))
            p.drawText(caja.adjusted(28, 0, -10, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)
        # ---- la barra de reproducción
        barra = self._barra()
        p.setPen(QPen(QColorReal(255, 255, 255, 24), 1))
        p.setBrush(QColorReal(255, 255, 255, 7))
        p.drawRoundedRect(barra.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        acento = _acento()
        bp = self._b_play()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColorReal(255, 255, 255, 16))
        p.drawEllipse(bp)
        _pintar_icono(p, 'pause' if jugando else 'play', '#FFFFFF', bp.adjusted(8, 8, -8, -8))
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(14, peso='medio'))
        txt_t = POS.texto_t(t)
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(bp.right() + 14, barra.top(), 200, barra.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), txt_t)
        p.setPen(QColor(MUTED))
        p.setFont(fuente(13))
        p.drawText(QRectF(bp.right() + 16 + fm.horizontalAdvance(txt_t), barra.top(), 120, barra.height()),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), '/ ' + POS.texto_t(ln.dur))
        pista = self._pista()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColorReal(255, 255, 255, 34))
        p.drawRoundedRect(pista, 3, 3)
        f = (t / ln.dur) if ln.dur > 0 else 0.0
        p.setBrush(acento)
        p.drawRoundedRect(QRectF(pista.left(), pista.top(), max(6.0, pista.width() * f), pista.height()), 3, 3)
        for tm in ln.marcas:                                              # (las marcas, como puntos sobre la barra)
            xm = pista.left() + pista.width() * (tm / ln.dur if ln.dur > 0 else 0.0)
            p.setBrush(QColor(AMBAR) if ln.queda_mal(tm) else QColorReal(255, 255, 255, 210))
            p.drawEllipse(QPointF(xm, pista.center().y()), 2.6, 2.6)
        xk = pista.left() + pista.width() * f
        p.setBrush(_alfa(acento, 70))
        p.drawEllipse(QPointF(xk, pista.center().y()), 11, 11)
        p.setBrush(acento)
        p.setPen(QPen(QColor('#FFFFFF'), 2))
        p.drawEllipse(QPointF(xk, pista.center().y()), 7, 7)
        _pintar_icono(p, 'speaker-slash' if self._mudo else 'speaker-high', '#C9D6EC', self._b_sonido().adjusted(4, 4, -4, -4))
        _pintar_icono(p, 'corners-in' if self._ampliado else 'corners-out', '#C9D6EC', self._b_ampliar().adjusted(4, 4, -4, -4))
        p.end()


# ======================================================================================================================== el panel
def _scroll(widget):
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
    s.setWidget(widget)
    return s


def _limpiar(capa):
    while capa.count():
        it = capa.takeAt(0)
        w = it.widget()
        if w is not None:                                                # (oculto YA: con solo deleteLater la fila vieja seguía pintada)
            w.hide()
            w.deleteLater()
        elif it.layout() is not None:
            _limpiar(it.layout())


class PanelDetras(QWidget):
    """Ajustes · Marcas · Sugerencias."""
    def __init__(self, vista, padre=None):
        super().__init__(padre)
        import edicion_pro as EP
        self.vista = vista
        self.linea = vista.linea
        self.setMinimumWidth(420)
        self.setMaximumWidth(580)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(10, 8, 10, 10)
        capa.setSpacing(6)
        fila = QHBoxLayout()
        fila.setSpacing(4)
        self.p_ajustes = _Pestana(tr('Ajustes'), 'sliders-horizontal')
        self.p_marcas = _Pestana(tr('Marcas'), 'map-pin')
        self.p_sug = _Pestana(tr('Sugerencias'), 'lightbulb')
        self.pila = QStackedWidget()
        for i, b in enumerate((self.p_ajustes, self.p_marcas, self.p_sug)):
            b.clicked.connect(lambda _c=False, i=i: self.pila.setCurrentIndex(i))
            fila.addWidget(b)
        fila.addStretch(1)
        capa.addLayout(fila)
        capa.addWidget(self.pila, 1)
        self.p_ajustes.setChecked(True)
        # ---- Ajustes
        aj = QWidget()
        ca = QVBoxLayout(aj)
        ca.setContentsMargins(8, 10, 8, 6)
        ca.setSpacing(10)
        ca.addWidget(Etiqueta(tr('Modo de marcas'), 14, peso='medio', color=CLARO))
        fm_ = QHBoxLayout()
        fm_.setSpacing(10)
        self.op_solo = _Opcion(tr('Solo mis marcas'), tr('Usa solo las que tú coloques'))
        self.op_suma = _Opcion(tr('Mis marcas + automático'), tr('Combina tus marcas con IA'))
        for clave, op in (('solo', self.op_solo), ('suma', self.op_suma)):
            op.clicked.connect(lambda _c=False, k=clave: self._elegir_modo(k))
            fm_.addWidget(op, 1)
        ca.addLayout(fm_)
        fp = QHBoxLayout()
        fp.addWidget(Etiqueta(tr('Posición del caption'), 14, peso='medio', color=CLARO))
        fp.addStretch(1)
        self.lbl_pos = Etiqueta('', 12, color=MUTED)
        fp.addWidget(self.lbl_pos)
        ca.addLayout(fp)
        ft = QHBoxLayout()
        ft.setSpacing(10)
        self.mosaicos = {}
        for clave, nombre in (('arriba', tr('Arriba')), ('izquierda', tr('Izquierda')), ('derecha', tr('Derecha'))):
            m = _Mosaico(clave, nombre)
            m.clicked.connect(lambda _c=False, k=clave: self._elegir_posicion(k))
            ft.addWidget(m)
            self.mosaicos[clave] = m
        ft.addStretch(1)
        ca.addLayout(ft)
        fi = QHBoxLayout()
        fi.addWidget(Etiqueta(tr('Intensidad / tamaño'), 14, peso='medio', color=CLARO))
        fi.addStretch(1)
        self.lbl_int = Etiqueta('', 13, peso='medio', color='#FFFFFF')
        fi.addWidget(self.lbl_int)
        ca.addLayout(fi)
        self._niveles = list(EP.NIVELES_DETRAS)
        self._v_int = StringVar(EP.intensidad_detras())
        self.desl = ui.DeslizadorValores(self._niveles, self._v_int, self._cambio_intensidad)
        ca.addWidget(self.desl)
        self.estado = _TarjetaEstado()
        ca.addWidget(self.estado)
        self.ayuda = _TarjetaAyuda()
        ca.addWidget(self.ayuda)
        ca.addStretch(1)
        self.pila.addWidget(_scroll(aj))
        # ---- Marcas y Sugerencias (se rehacen al cambiar)
        self.pag_marcas = QWidget()
        self.capa_marcas = QVBoxLayout(self.pag_marcas)
        self.capa_marcas.setContentsMargins(8, 10, 8, 6)
        self.capa_marcas.setSpacing(8)
        self.pila.addWidget(_scroll(self.pag_marcas))
        self.pag_sug = QWidget()
        self.capa_sug = QVBoxLayout(self.pag_sug)
        self.capa_sug.setContentsMargins(8, 10, 8, 6)
        self.capa_sug.setSpacing(8)
        self.pila.addWidget(_scroll(self.pag_sug))
        self._firma_marcas = None
        self._nota = None
        self._pintar_intensidad()
        self.refrescar()
        self.pintar_sugeridas()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColorReal(255, 255, 255, 24), 1))
        p.setBrush(QColorReal(255, 255, 255, 6))
        p.drawRoundedRect(r, 16, 16)
        p.setPen(QPen(QColorReal(255, 255, 255, 20), 1))
        p.drawLine(QPointF(r.left() + 10, 57.5), QPointF(r.right() - 10, 57.5))
        p.end()

    # -- ajustes
    def refrescar(self):
        """El modo y la posición, como están en la tira (lo llama también VistaPosiciones.abrir: antes era el Segmentado)."""
        modo = self.linea.modo
        self.op_solo.setChecked(modo == 'solo')
        self.op_suma.setChecked(modo != 'solo')
        horizontal = self.linea.horizontal()
        pos = self.linea.posicion()
        for clave, m in self.mosaicos.items():
            m.setVisible(horizontal or clave == 'arriba')
            m.setChecked(clave == pos)
            m.setEnabled(horizontal)
        self.lbl_pos.setText(tr('Horizontal: elige el lado') if horizontal else tr('Vertical: siempre arriba'))

    def _elegir_modo(self, clave):
        nombre = tr(dict(self.vista.MODOS_UI)[clave])
        self.vista._v_modo.set(nombre)
        self.vista._cambio_modo()
        self.refrescar()

    def _elegir_posicion(self, clave):
        self.linea.poner_posicion(clave)
        self.refrescar()

    def _pintar_intensidad(self):
        nombres = {'suave': tr('Suave'), 'media': tr('Media'), 'fuerte': tr('Fuerte')}
        self.lbl_int.setText(nombres.get(str(self._v_int.get()), str(self._v_int.get())))

    def _cambio_intensidad(self, *_a):
        self._pintar_intensidad()
        self.linea.poner_intensidad(str(self._v_int.get()))

    def sincronizar(self):
        """Lo que depende de la tira (se llama cada vez que se pinta: solo cambia lo que cambió)."""
        ln = self.linea
        d = ln.deteccion()
        if ln.analizando():
            self.estado.poner('espera', tr('Analizando…'), tr('Buscando a la persona en tu video… {p} %', p=int(round(100 * ln._progreso[0]))))
        elif d is None:
            self.estado.poner('espera', '', tr('Aún no se ha mirado este video.'))
        else:
            pc = int(round(100 * d[0]))
            nivel = 'bien' if d[0] >= 0.7 else ('regular' if d[0] >= 0.35 else 'mal')
            chip = {'bien': tr('Funcionando bien'), 'regular': tr('Regular'), 'mal': tr('Casi no se ve a nadie')}[nivel]
            self.estado.poner(nivel, chip, tr('La persona se detecta en el {p} % de los fotogramas del video.', p=pc))
        nota = ln.nota or ''
        if nota != self._nota:
            self._nota = nota
            if nota:
                self.ayuda.poner(nota, aviso=True)
                self.ayuda.show()
            else:
                self.ayuda.poner(tr('Coloca las marcas en los momentos clave donde quieras que aparezca un caption detrás de ti. '
                                    'Puedes ajustar la posición y la intensidad.'))
        if self.op_solo.isChecked() != (ln.modo == 'solo') or self.mosaicos['izquierda'].isVisible() != ln.horizontal():
            self.refrescar()
        self.pintar_marcas()

    # -- marcas
    def _estado_marca(self, t, aplicadas):
        ln = self.linea
        if any(abs(t - x) < 0.06 for x in aplicadas):
            return tr('En tu timeline'), VERDE
        if ln.queda_mal(t):
            m = ln.motivo_go(t) or ln.texto_motivo(t)
            return (tr('No se puede: {m}', m=m) if m else tr('No se puede aquí')), AMBAR
        if ln.estado_go(t) is None and isinstance(ln._reglas, dict):
            return tr('Comprobando…'), MUTED
        return (tr('Nueva') if ln._aplicados is not None else tr('Guardada: GO la aplica')), '#FFFFFF'

    def _texto_en(self, t):
        import posiciones_pro as POS
        cues = (self.linea.captions or {}).get('cues') or []
        k = POS._cue_en(cues, float(t)) if cues else None
        return POS.texto_cue(cues[k], 7) if k is not None else ''

    def pintar_marcas(self, forzar=False):
        import posiciones_pro as POS
        ln = self.linea
        est = ln.estado_marcas()
        aplicadas, quitadas = (est[0], est[2]) if est else ([], [])
        filas = [(t, *self._estado_marca(t, aplicadas)) for t in ln.marcas]
        firma = (tuple(filas), tuple(quitadas), ln._sel, bool(ln.captions), ln.bloqueada)
        n = len(ln.marcas)
        self.p_marcas.poner_texto(tr('Marcas') + f' ({n})')
        if firma == self._firma_marcas and not forzar:
            return
        self._firma_marcas = firma
        _limpiar(self.capa_marcas)
        tope = POS.TOPE_MARCAS.get(ln.seccion, 8)
        self.capa_marcas.addWidget(Etiqueta(tr('{n} de {m} marcas', n=n, m=tope), 13, peso='medio', color=CLARO))
        if not ln.marcas and not quitadas:
            self.capa_marcas.addWidget(Etiqueta(tr('Aún no hay marcas: haz clic en la tira de abajo o toca una sugerencia.'), 12, color=MUTED,
                                                envolver=True))
        for i, (t, texto, color) in enumerate(filas):
            self.capa_marcas.addWidget(self._fila(t, texto, color, self._texto_en(t), sel=i == ln._sel,
                                                  acciones=[(tr('Ver'), lambda t=t, i=i: self._ver(t, i)),
                                                            ('', lambda i=i: ln._quitar(i), 'trash')]))
        for t in quitadas:
            self.capa_marcas.addWidget(self._fila(t, tr('Se quita de tu timeline'), ROJO, self._texto_en(t),
                                                  acciones=[(tr('Recuperar'), lambda t=t: ln.recuperar(t))]))
        self.capa_marcas.addStretch(1)

    def _fila(self, t, estado, color, texto, sel=False, acciones=()):
        import posiciones_pro as POS
        caja = _Caja(margenes=(12, 8, 8, 8), espacio=10, horizontal=True, radio=12,
                     fondo=(255, 255, 255, 14 if sel else 7), borde=(255, 255, 255, 46 if sel else 22))
        chip = Etiqueta(POS.texto_t(t), 13, peso='negrita', color='#FFFFFF')
        chip.setFixedWidth(58)
        caja.capa.addWidget(chip)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(Etiqueta(estado, 12, peso='medio', color=color))
        if texto:
            col.addWidget(ui.Elidida(texto, 12, color=MUTED) if hasattr(ui, 'Elidida') else Etiqueta(texto, 12, color=MUTED))
        caja.capa.addLayout(col, 1)
        for a in acciones:
            b = Boton(a[0], a[1], tipo='fantasma', alto=30, tam=12, icono=_icono(a[2]) if len(a) > 2 else None)
            b.setEnabled(not self.linea.bloqueada)
            caja.capa.addWidget(b)
        return caja

    def _ver(self, t, i):
        self.linea._sel = i
        self.linea.poner_cabezal(t)

    # -- sugerencias
    def pintar_sugeridas(self):
        import posiciones_pro as POS
        sug = list(self.linea.sugeridas)
        self.p_sug.poner_texto(tr('Sugerencias') + f' ({len(sug)})')
        _limpiar(self.capa_sug)
        if sug:
            self.capa_sug.addWidget(Etiqueta(tr('Donde GO lo pone detrás de ti y queda bien. Un toque y queda marcada.'), 12, color=MUTED,
                                             envolver=True))
            for t, txt in sug:
                b = Boton('+ ' + POS.texto_t(t) + (f' · {txt}' if txt else ''), lambda t=t: self.vista._poner(t), tipo='neutro', alto=38, tam=13)
                self.capa_sug.addWidget(b)
            if len(sug) > 1:
                self.capa_sug.addWidget(Boton(tr('Poner las {n}', n=len(sug)), self.vista._poner_todas, tipo='primario', alto=38, tam=13))
        else:
            self.capa_sug.addWidget(Etiqueta(tr('Ahora no hay sugerencias: ya están marcadas, o tu video aún se está analizando.'), 12,
                                             color=MUTED, envolver=True))
        self.capa_sug.addStretch(1)


# ======================================================================================================================== la cabecera
class CabeceraDetras(QWidget):
    volver = Signal()
    ayuda = Signal()

    def __init__(self, vista, padre=None):
        super().__init__(padre)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(12)
        self.b_volver = Boton('', self.volver.emit, tipo='neutro', alto=40, icono=_icono('caret-left', '#E6EEFB'), lado_icono=18)
        self.b_volver.setFixedWidth(40)
        capa.addWidget(self.b_volver)
        col = QVBoxLayout()
        col.setSpacing(0)
        ft = QHBoxLayout()
        ft.setSpacing(6)
        ft.addWidget(Etiqueta(tr('Captions detrás de ti'), 21, peso='negrita', color='#FFFFFF'))
        self.b_info = Boton('', self.ayuda.emit, tipo='fantasma', alto=26, icono=_icono('info', '#8EA2C6'), lado_icono=16)
        self.b_info.setFixedWidth(28)
        ft.addWidget(self.b_info)
        ft.addStretch(1)
        col.addLayout(ft)
        self.lbl_resumen = ui.Elidida('', 13, color=MUTED) if hasattr(ui, 'Elidida') else Etiqueta('', 13, color=MUTED)
        col.addWidget(self.lbl_resumen)
        capa.addLayout(col, 1)
        self.pildora = _Pildora()
        capa.addWidget(self.pildora)
        self.b_elegir = Boton(tr('Elegir video'), vista._elegir_video, tipo='neutro', alto=42, tam=13, icono=_icono('folder-open', '#E6EEFB'))
        self.b_quitar = Boton(tr('Quitar todas'), vista._quitar_todas, tipo='neutro', alto=42, tam=13, icono=_icono('trash', '#E6EEFB'))
        self.b_listo = Boton(tr('Listo'), vista._listo, tipo='primario', alto=42, ancho=136, tam=14, negrita=True,
                             icono=_icono('check-circle', '#FFFFFF'), lado_icono=18)
        for b in (self.b_elegir, self.b_quitar, self.b_listo):
            capa.addWidget(b)
        self._estado_fijo = None

    def poner_resumen(self, texto):
        self.lbl_resumen.setText(str(texto or ''))

    def poner_estado(self, texto=None, color=None):
        """Un estado que manda sobre el del proyecto (aplicando, error); None = el del proyecto otra vez."""
        self._estado_fijo = (texto, color) if texto else None

    def sincronizar(self, linea, a_mano):
        if self._estado_fijo:
            self.pildora.poner(*self._estado_fijo)
        elif not linea.ruta:
            self.pildora.poner(tr('Sin video'), MUTED)
        elif a_mano:
            self.pildora.poner(tr('Video elegido a mano: GO lo aplica'), MUTED)
        elif linea._aplicados is not None:
            self.pildora.poner(tr('Proyecto listo'), VERDE)
        else:
            self.pildora.poner(tr('Pulsa GO una vez con este video'), AMBAR)


# ======================================================================================================================== montaje
class _Nuevo:
    """Lo del diseño nuevo que guarda la vista (cabecera, visor, panel) y lo que los pone al día."""
    def __init__(self, vista, cab, visor, panel):
        self.vista, self.cab, self.visor, self.panel = vista, cab, visor, panel
        self._pendiente = False

    def sincronizar(self):
        """Lo llama la tira al pintarse: el visor se repinta ya; el panel y la cabecera, al volver al bucle (no se rehacen filas dentro de
        un paintEvent) y una vez aunque la tira se pinte varias veces seguidas."""
        self.visor.update()
        if not self._pendiente:
            self._pendiente = True
            QTimer.singleShot(0, self._hacer)

    def _hacer(self):
        self._pendiente = False
        try:
            self.panel.sincronizar()
            self.cab.sincronizar(self.vista.linea, self.vista.a_mano())
        except RuntimeError:                                             # (la vista ya no existe)
            pass


def _pista(icono, texto):
    w = QWidget()
    c = QHBoxLayout(w)
    c.setContentsMargins(0, 0, 0, 0)
    c.setSpacing(6)
    ic = _icono(icono, '#8EA2C6')
    if ic is not None:
        lbl = QLabel()
        lbl.setPixmap(ic.pixmap(16, 16))
        c.addWidget(lbl)
    c.addWidget(Etiqueta(texto, 12, color=MUTED))
    return w


def armar(vista):
    """Monta el diseño nuevo dentro de `vista` (posiciones_pro.VistaPosiciones de «detrás de ti») con los nombres que usan sus métodos."""
    import posiciones_pro as POS
    capa = QVBoxLayout(vista)
    capa.setContentsMargins(0, 2, 0, 4)
    capa.setSpacing(14)
    vista.linea = POS.LineaTiempo(vista.seccion)
    ln = vista.linea
    ln.compacta = True
    ln.setMinimumHeight(140)
    ln.setMaximumHeight(150)
    # ---- cabecera y la barra de «Listo» (v5.31)
    cab = CabeceraDetras(vista)
    capa.addWidget(cab)
    vista._fila_prog = QWidget()
    cp = QVBoxLayout(vista._fila_prog)
    cp.setContentsMargins(0, 0, 0, 0)
    cp.setSpacing(2)
    vista._lbl_prog = Etiqueta('', 12, peso='medio', color='#C9D6EC')
    cp.addWidget(vista._lbl_prog)
    vista._barra = ui.BarraProgreso(alto=8)
    cp.addWidget(vista._barra)
    vista._fila_prog.setVisible(False)
    capa.addWidget(vista._fila_prog)
    vista._prog = {'f': 0.0, 't': ''}
    vista._reloj_prog = QTimer(vista)
    vista._reloj_prog.setInterval(120)
    vista._reloj_prog.timeout.connect(vista._pintar_prog)
    # ---- visor y panel
    cuerpo = QHBoxLayout()
    cuerpo.setSpacing(14)
    visor = VisorDetras(vista)
    cuerpo.addWidget(visor, 3)
    vista._lbl_video = _Texto(visor.update)
    nombres = [tr(n) for _k, n in vista.MODOS_UI]
    vista._v_modo = StringVar(nombres[0])
    panel = PanelDetras(vista)
    cuerpo.addWidget(panel, 2)
    capa.addLayout(cuerpo, 1)
    visor.ampliar.connect(lambda: panel.setVisible(not panel.isVisible()))
    # ---- la tira
    caja = _Caja(margenes=(16, 12, 16, 8), espacio=4)
    fila = QHBoxLayout()
    fila.setSpacing(18)
    ic = _icono('sliders', '#E6EEFB')
    if ic is not None:
        lbl = QLabel()
        lbl.setPixmap(ic.pixmap(20, 20))
        fila.addWidget(lbl)
    fila.addWidget(Etiqueta(tr('Timeline'), 16, peso='negrita', color='#FFFFFF'))
    fila.addStretch(1)
    for icono, texto in (('map-pin', tr('Clic para añadir marcas')), ('hand-grabbing', tr('Arrastra para mover')),
                         ('arrows-left-right', tr('← → para afinar')), ('trash', tr('Doble clic o clic derecho para quitar'))):
        fila.addWidget(_pista(icono, texto))
    caja.capa.addLayout(fila)
    caja.capa.addWidget(ln)
    capa.addWidget(caja)
    # ---- lo que usan los métodos de VistaPosiciones
    vista._seg = panel
    vista._botones = [panel.op_solo, panel.op_suma, cab.b_elegir, cab.b_quitar, cab.b_listo] + list(panel.mosaicos.values())
    vista._fila_sug = panel.pag_sug
    vista._capa_sug = panel.capa_sug
    vista._lbl_modo = _Texto()
    vista._nuevo = _Nuevo(vista, cab, visor, panel)
    cab.volver.connect(vista.volver.emit)
    cab.ayuda.connect(lambda: (panel.setVisible(True), panel.p_ajustes.click(), panel.ayuda.show()))
    ln.cambio.connect(vista._al_cambiar)
    ln.cargado.connect(vista._al_cargar)
    ln.sugerencias.connect(vista._pintar_sugeridas)
    ln.pintada.connect(vista._nuevo.sincronizar)
