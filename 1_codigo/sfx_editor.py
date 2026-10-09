# CineCaptions · By Cinema Productions
# 1_codigo/sfx_editor.py — la ventana «Editar» de un sonido: elegir de forma visual qué parte suena (onda con asas) y su volumen.
"""
sfx_editor.py
-------------
La ventana que sale al tocar «Editar» junto a un sonido (modo Simple y modo Avanzado de la pantalla Sonido).

  * Se ve la onda del sonido. Dos asas (inicio y fin) marcan la parte que se usa: se arrastran, se mueve toda la
    selección agarrándola por el medio, y un doble clic vuelve a elegir todo el sonido.
  * Un deslizador baja o sube el volumen de ESE sonido.
  * «Escuchar selección» suena justo lo que se va a usar (con el volumen puesto) y un cabezal recorre la onda.
  * Al guardar, el recorte y el volumen quedan en ~/DaVinciSubtitles (sfx_recortes.json y sfx_volumenes.json) y se
    hornean en el WAV que viaja a la línea de tiempo (sfx_rules.con_volumen).

Todo lo que se mueve (barras que suben al abrir, asas que crecen al tocarlas, burbujas con el tiempo, destello de los
valores, altavoz que cambia con el volumen) es dibujo propio: no usa ninguna librería de animación.
"""
import math
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QDialog, QGraphicsOpacityEffect, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
from qt_kit import (Boton, Combo, Deslizador, Dialogo, Enlace, Etiqueta, StringVar, Tooltip, caja_h, caja_v)
from qt_kit import QColor
import sfx_audio
import sfx_rules
from i18n import tr

ACENTO = '#4589FF'


def _brillo_boton(boton):
    try:
        import brillo_ui
        brillo_ui.entrar(boton)
    except Exception:
        pass


def _seg(v):
    return f'{float(v):.2f} s'.replace('.', ',')


def _picos(audio, n=260):
    """n barras 0..1 que dibujan la onda."""
    a = np.abs(np.asarray(audio, dtype=np.float32))
    if not a.size:
        return []
    trozos = np.array_split(a, min(n, a.size))
    pk = [float(t.max()) if t.size else 0.0 for t in trozos]
    tope = max(pk) or 1.0
    return [min(1.0, (p / tope) ** 0.75) for p in pk]


def _reducir_animaciones():
    try:
        import efectos_ui
        return bool(efectos_ui.reducir_animaciones())
    except Exception:
        return False


def _aparecer(widget, retraso=0, dur=320):
    """Fundido de entrada con retraso (los bloques de la ventana entran uno tras otro). El efecto se quita al terminar."""
    if _reducir_animaciones():
        return
    try:
        ef = QGraphicsOpacityEffect(widget)
        ef.setOpacity(0.0)
        widget.setGraphicsEffect(ef)
        anim = QVariantAnimation(widget)
        anim.setDuration(int(dur))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def paso(v, e=ef):
            try:
                e.setOpacity(float(v))
            except RuntimeError:
                pass

        def fin(w=widget):
            try:
                if ui.vivo(w):
                    w.setGraphicsEffect(None)
            except RuntimeError:
                pass
        anim.valueChanged.connect(paso)
        anim.finished.connect(fin)
        ui.despues(int(retraso), anim.start, widget)
    except Exception:
        pass


class _OndaRecorte(QWidget):
    """La onda con las dos asas. Emite cambio(inicio_s, fin_s) mientras se arrastra."""
    cambio = Signal(float, float)
    terminado = Signal()
    MINIMO = 0.03

    def __init__(self, color=ACENTO, padre=None):
        super().__init__(padre)
        self._color = QColor(color)
        self._picos = []
        self._dur = 0.0
        self._ini = 0.0
        self._fin = 0.0
        self._arr = None            # 'ini' | 'fin' | 'mov' mientras se arrastra
        self._dx = 0.0
        self._sobre = None          # lo que está bajo el cursor
        self._hi = 0.0              # brillo de cada asa (0..1, suavizado)
        self._hf = 0.0
        self._entrada = 1.0 if _reducir_animaciones() else 0.0
        self._quieto = _reducir_animaciones()
        self._fase = 0.0
        self._play = None
        self._pos = None
        self._mx = None             # x del cursor sobre la onda (las barras de alrededor crecen)
        self._lupa = 0.0            # 0..1 suavizado
        self._rebote_i = 0.0        # rebote de cada asa al soltarla
        self._rebote_f = 0.0
        self.mensaje = ''
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._reloj = QTimer(self)
        self._reloj.setInterval(22)
        self._reloj.timeout.connect(self._tick)
        self._reloj.start()

    # -- datos
    def poner_datos(self, picos, dur, ini, fin):
        self._picos = list(picos)
        self._dur = float(dur)
        self._ini = max(0.0, float(ini))
        self._fin = min(float(dur), float(fin)) if dur else 0.0
        self._entrada = 1.0 if self._quieto else 0.0
        self._play = None
        self._pos = None
        self.update()

    def rango(self):
        return self._ini, self._fin

    def elegir_todo(self):
        self._ini, self._fin = 0.0, self._dur
        self.cambio.emit(self._ini, self._fin)
        self.update()

    def poner_reproduccion(self, ini, fin):
        self._play = (time.perf_counter(), float(ini), float(fin))
        self._pos = float(ini)

    def detener_reproduccion(self):
        self._play = None
        self._pos = None
        self.update()

    def reproduciendo(self):
        return self._play is not None

    # -- geometría
    def _caja(self):
        W, H = float(self.width()), float(self.height())
        return 22.0, W - 22.0, 40.0, H - 34.0

    def _x(self, t):
        x0, x1, _a, _b = self._caja()
        return x0 + (t / self._dur if self._dur else 0.0) * (x1 - x0)

    def _t(self, x):
        x0, x1, _a, _b = self._caja()
        return max(0.0, min(self._dur, (x - x0) / max(1.0, x1 - x0) * self._dur))

    # -- animación
    def _tick(self):
        if not self.isVisible():
            return
        if self._entrada < 1.0:
            self._entrada = min(1.0, self._entrada + 0.04)
        luz_i = 1.0 if (self._arr in ('ini', 'mov') or self._sobre in ('ini', 'mov')) else 0.0
        luz_f = 1.0 if (self._arr in ('fin', 'mov') or self._sobre in ('fin', 'mov')) else 0.0
        self._hi += (luz_i - self._hi) * 0.3
        self._hf += (luz_f - self._hf) * 0.3
        self._lupa += ((1.0 if self._mx is not None else 0.0) - self._lupa) * 0.22
        self._rebote_i *= 0.86
        self._rebote_f *= 0.86
        if not self._quieto:
            self._fase = (self._fase + 0.010) % 1.4
        if self._play is not None:
            t0, ini, fin = self._play
            self._pos = ini + (time.perf_counter() - t0)
            if self._pos >= fin:
                self._play = None
                self._pos = None
                self.terminado.emit()
        self.update()

    # -- ratón
    def _asa_en(self, x):
        di, df = abs(x - self._x(self._ini)), abs(x - self._x(self._fin))
        if min(di, df) <= 11:
            return 'ini' if di <= df else 'fin'
        return None

    def _mover(self, que, x):
        if que == 'ini':
            self._ini = max(0.0, min(self._t(x), self._fin - self.MINIMO))
        elif que == 'fin':
            self._fin = min(self._dur, max(self._t(x), self._ini + self.MINIMO))
        else:
            largo = self._fin - self._ini
            ini = max(0.0, min(self._t(x - self._dx), self._dur - largo))
            self._ini, self._fin = ini, ini + largo
        self.cambio.emit(self._ini, self._fin)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self._picos:
            return
        x = e.position().x()
        a = self._asa_en(x)
        if a is None:
            if self._x(self._ini) < x < self._x(self._fin):
                self._arr = 'mov'
                self._dx = x - self._x(self._ini)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return
            a = 'ini' if abs(x - self._x(self._ini)) < abs(x - self._x(self._fin)) else 'fin'
            self._mover(a, x)
        self._arr = a
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def mouseMoveEvent(self, e):
        x = e.position().x()
        self._mx = x
        if self._arr:
            self._mover(self._arr, x)
            return
        a = self._asa_en(x)
        dentro = self._x(self._ini) < x < self._x(self._fin)
        self._sobre = a or ('mov' if dentro else None)
        self.setCursor(Qt.CursorShape.SizeHorCursor if a else (Qt.CursorShape.OpenHandCursor if dentro else Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, _e):
        if self._arr in ('ini', 'mov'):
            self._rebote_i = 1.0
        if self._arr in ('fin', 'mov'):
            self._rebote_f = 1.0
        self._arr = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, _e):
        if self._picos:
            self.elegir_todo()

    def leaveEvent(self, _e):
        self._sobre = None
        self._mx = None

    # -- dibujo
    def paintEvent(self, _e):
        W, H = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QColor(self._color)
        p.setPen(QPen(QColor('#1E2A42'), 1))
        p.setBrush(QColor('#0A1224'))
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 14, 14)
        if not self._picos or self._dur <= 0:
            p.setPen(QColor('#8D9BB5'))
            p.setFont(ui.fuente(13))
            p.drawText(QRectF(0, 0, W, H), int(Qt.AlignmentFlag.AlignCenter), self.mensaje or tr('Sin audio'))
            p.end()
            return
        x0, x1, top, bot = self._caja()
        yc, alto = (top + bot) / 2.0, (bot - top) / 2.0
        xi, xf = self._x(self._ini), self._x(self._fin)
        # lo elegido: fondo con degradado y borde
        sel = QLinearGradient(0, top, 0, bot)
        c1, c2 = QColor(base), QColor(base)
        c1.setAlpha(46)
        c2.setAlpha(10)
        sel.setColorAt(0.0, c1)
        sel.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sel)
        zona = QRectF(xi, top - 8, max(1.0, xf - xi), bot - top + 16)
        p.drawRoundedRect(zona, 8, 8)
        borde = QColor(base)
        borde.setAlpha(int(110 + 60 * max(self._hi, self._hf) + 30 * math.sin(self._fase * 9.0)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(borde, 1.2))
        p.drawRoundedRect(zona, 8, 8)
        p.setPen(Qt.PenStyle.NoPen)
        # eje
        eje = QColor('#1E2A42')
        p.setBrush(eje)
        p.drawRect(QRectF(x0, yc - 0.5, x1 - x0, 1.0))
        # barras: suben al abrir; lo elegido se ve en color y lo descartado apagado; un destello lo recorre; lo ya sonado se aclara
        n = len(self._picos)
        ranura = (x1 - x0) / n
        ancho = max(1.6, ranura * 0.58)
        fx = self._fase
        for i, pk in enumerate(self._picos):
            cx = x0 + (i + 0.5) * ranura
            t = (i + 0.5) / n * self._dur
            e = max(0.0, min(1.0, self._entrada * 1.7 - (i / n) * 0.7))
            e = 1.0 - (1.0 - e) ** 3
            h = max(1.5, pk * alto * 0.9 * e)
            if self._mx is not None and self._lupa > 0.02:             # las barras cerca del cursor crecen (lupa suave)
                cerca = max(0.0, 1.0 - abs(cx - self._mx) / 46.0)
                h *= 1.0 + 0.30 * self._lupa * cerca * cerca
            if self._ini <= t <= self._fin:
                col = QColor(base)
                if self._pos is not None and t <= self._pos:
                    col = QColor(base).lighter(165)
                    col.setAlpha(255)
                else:
                    brillo = max(0.0, 1.0 - abs((cx - x0) / (x1 - x0) - fx) * 7.0)
                    if brillo > 0.0:
                        col = QColor(base).lighter(100 + int(55 * brillo))
                    col.setAlpha(228)
            else:
                col = QColor('#2B3A5C')
                col.setAlpha(150)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(cx - ancho / 2.0, yc - h, ancho, h * 2.0), ancho / 2.0, ancho / 2.0)
        # regla de tiempo
        p.setFont(ui.fuente(10))
        paso = next((s for s in (0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60) if self._dur / s <= 9), 120)
        k = 0
        while k * paso <= self._dur + 1e-6:
            tx = self._x(k * paso)
            p.setPen(QPen(QColor('#2B3A5C'), 1))
            p.drawLine(QPointF(tx, bot + 10), QPointF(tx, bot + 14))
            p.setPen(QColor('#8D9BB5'))
            etiqueta = (f'{k * paso:g}'.replace('.', ',')) + ' s'
            p.drawText(QRectF(tx - 26, bot + 15, 52, 16), int(Qt.AlignmentFlag.AlignCenter), etiqueta)
            k += 1
        p.setPen(Qt.PenStyle.NoPen)
        # asas: crecen y se encienden al tocarlas
        for x, luz, valor, reb in ((xi, self._hi, self._ini, self._rebote_i), (xf, self._hf, self._fin, self._rebote_f)):
            grosor = 9.0 + 6.0 * luz + 5.0 * reb * math.sin(self._fase * 40.0)
            if luz > 0.02:
                halo = QColor(base)
                halo.setAlpha(int(80 * luz))
                p.setBrush(halo)
                p.drawRoundedRect(QRectF(x - grosor / 2 - 6, top - 14, grosor + 12, bot - top + 28), 10, 10)
            asa = QLinearGradient(0, top - 10, 0, bot + 10)
            a1, a2 = QColor(base).lighter(130), QColor(base)
            asa.setColorAt(0.0, a1)
            asa.setColorAt(1.0, a2)
            p.setBrush(asa)
            p.setPen(QPen(QColor(255, 255, 255, 150), 1.0))
            p.drawRoundedRect(QRectF(x - grosor / 2, top - 10, grosor, bot - top + 20), 5, 5)
            p.setPen(QPen(QColor(255, 255, 255, 215), 1.4))
            for dy in (-6, 0, 6):
                p.drawLine(QPointF(x - 1.6, yc + dy), QPointF(x + 1.6, yc + dy))
            p.setPen(Qt.PenStyle.NoPen)
            if luz > 0.05:                                    # burbuja con el tiempo exacto
                texto = _seg(valor)
                fm = p.fontMetrics()
                bw = fm.horizontalAdvance(texto) + 18
                bx = max(4.0, min(W - bw - 4.0, x - bw / 2))
                by = 8.0 - (1.0 - luz) * 6.0
                fondo = QColor(base)
                fondo.setAlpha(int(240 * luz))
                p.setBrush(fondo)
                p.drawRoundedRect(QRectF(bx, by, bw, 22), 11, 11)
                tx = QColor('#FFFFFF')
                tx.setAlpha(int(255 * luz))
                p.setPen(tx)
                p.drawText(QRectF(bx, by, bw, 22), int(Qt.AlignmentFlag.AlignCenter), texto)
                p.setPen(Qt.PenStyle.NoPen)
        # lo que dura lo elegido (se desvanece cuando se toca un asa)
        reposo = 1.0 - max(self._hi, self._hf)
        if reposo > 0.05 and xf - xi > 84:
            texto = _seg(self._fin - self._ini)
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(texto) + 18
            fondo = QColor(base)
            fondo.setAlpha(int(70 * reposo))
            p.setBrush(fondo)
            p.drawRoundedRect(QRectF((xi + xf) / 2 - bw / 2, 8, bw, 22), 11, 11)
            tx = QColor('#FFFFFF')
            tx.setAlpha(int(235 * reposo))
            p.setPen(tx)
            p.drawText(QRectF((xi + xf) / 2 - bw / 2, 8, bw, 22), int(Qt.AlignmentFlag.AlignCenter), texto)
            p.setPen(Qt.PenStyle.NoPen)
        # cabezal de reproducción
        if self._pos is not None:
            px = self._x(self._pos)
            p.setPen(QPen(QColor(255, 255, 255, 60), 7))
            p.drawLine(QPointF(px, top - 8), QPointF(px, bot + 8))
            p.setPen(QPen(QColor(255, 255, 255, 235), 1.6))
            p.drawLine(QPointF(px, top - 8), QPointF(px, bot + 8))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 240))
            p.drawEllipse(QPointF(px, top - 8), 3.5, 3.5)
        p.end()


class _Dato(QWidget):
    """Un valor con su título (Inicio / Fin / Usa). Destella un instante cuando cambia."""
    def __init__(self, titulo, color=ACENTO, padre=None):
        super().__init__(padre)
        self._titulo = titulo
        self._valor = '—'
        self._color = QColor(color)
        self._pulso = 0.0
        self.setFixedHeight(54)
        self.setMinimumWidth(116)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(520)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.valueChanged.connect(self._paso)

    def _paso(self, v):
        self._pulso = float(v)
        self.update()

    def poner(self, valor):
        if valor != self._valor:
            self._valor = valor
            if not _reducir_animaciones() and self._anim.state() != QVariantAnimation.State.Running:
                self._anim.start()
            self.update()

    def paintEvent(self, _e):
        W, H = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fondo = QColor('#0F1A30')
        p.setBrush(fondo)
        borde = QColor(self._color)
        borde.setAlpha(int(40 + 170 * self._pulso))
        p.setPen(QPen(borde, 1.0 + 0.6 * self._pulso))
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 11, 11)
        p.setPen(QColor('#8D9BB5'))
        p.setFont(ui.fuente(10, peso='negrita'))
        p.drawText(QRectF(14, 7, W - 28, 14), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._titulo)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(17, peso='extra'))
        p.drawText(QRectF(14, 22, W - 28, 26), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._valor)
        p.end()


class _Altavoz(QWidget):
    """Un altavoz cuyas ondas suben y bajan con el volumen (con animación suave)."""
    def __init__(self, color=ACENTO, padre=None):
        super().__init__(padre)
        self.setFixedSize(38, 38)
        self._color = QColor(color)
        self._nivel = 1.0
        self._meta = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(240)
        self._anim.valueChanged.connect(self._paso)

    def _paso(self, v):
        self._nivel = float(v)
        self.update()

    def poner(self, v):
        self._meta = float(v)
        if _reducir_animaciones():
            self._nivel = self._meta
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._nivel)
        self._anim.setEndValue(self._meta)
        self._anim.start()

    def paintEvent(self, _e):
        from PySide6.QtGui import QPolygonF
        L = 38.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fondo = QColor(self._color)
        fondo.setAlpha(34)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(0, 0, L, L), 11, 11)
        col = QColor(self._color).lighter(125)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(9, 15, 5, 8), 1.5, 1.5)
        p.drawPolygon(QPolygonF([QPointF(13, 15), QPointF(20, 9.5), QPointF(20, 28.5), QPointF(13, 23)]))
        if self._nivel < 0.02:
            p.setPen(QPen(QColor('#FF6B6B'), 2.0))
            p.drawLine(QPointF(23, 14), QPointF(31, 24))
            p.drawLine(QPointF(31, 14), QPointF(23, 24))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(3):
                a = max(0.0, min(1.0, self._nivel * 2.2 - i * 0.75))
                if a <= 0.02:
                    continue
                c = QColor(col)
                c.setAlpha(int(255 * a))
                p.setPen(QPen(c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                r = 5.0 + i * 4.5
                p.drawArc(QRectF(21 - r + 2, 19 - r, r * 2, r * 2), -45 * 16, 90 * 16)
        p.end()


class DialogoEditarSonido(Dialogo):
    """La ventana «Editar». ruta=None (solo con 'fuente') empieza sin sonido concreto.

    fuente (modo Avanzado): {'categoria': 'Riser', 'archivos': [Path...], 'actual': Path|None, 'al_elegir': fn(Path|None)}
    permite elegir entre «cualquiera de la categoría» y uno de sus sonidos.
    icono: un QWidget ya creado (el icono animado de la sección) para la cabecera."""
    VARIADO = None

    def __init__(self, padre, ruta=None, al_guardar=None, color=ACENTO, titulo=None, icono=None, fuente=None, contexto=''):
        super().__init__(padre, tr('Editar sonido'), 720, 600, redimensionable=True, minimo=(640, 540))
        self.setModal(True)
        self._rep = sfx_audio.Reproductor()
        self._al_guardar = al_guardar
        self._fuente = fuente
        self._color = color
        self._contexto = contexto
        self._ruta = None
        self._audio = None
        self._dur = 0.0
        capa = QVBoxLayout(self)
        capa.setContentsMargins(24, 20, 24, 18)
        capa.setSpacing(14)
        # cabecera
        cab, cc = caja_h(espacio=14)
        if icono is not None:
            cc.addWidget(icono, 0, Qt.AlignmentFlag.AlignVCenter)
        col_t, ct = caja_v(espacio=2)
        self._titulo = ui.Elidida(titulo or '', 19, peso='extra', color='#FFFFFF')
        self._sub = Etiqueta('', 12, color='#8D9BB5')
        ct.addWidget(self._titulo)
        ct.addWidget(self._sub)
        cc.addWidget(col_t, 1)
        capa.addWidget(cab)
        # fuente de la regla
        if fuente:
            self.VARIADO = tr('Variado · cualquiera de «{c}»', c=fuente['categoria'])
            filaf, cf = caja_h(espacio=10)
            cf.addWidget(Etiqueta(tr('Sonido de esta regla'), 12, peso='medio', color='#B4C0D6'))
            nombres = [self.VARIADO] + [Path(a).name for a in fuente['archivos']]
            actual = Path(fuente['actual']).name if fuente.get('actual') else self.VARIADO
            self._v_fuente = StringVar(actual if actual in nombres else self.VARIADO)
            self._combo = Combo(nombres, self._v_fuente, self._elegir_fuente, ancho=360, alto=34, tam=13)
            cf.addWidget(self._combo, 1)
            capa.addWidget(filaf)
        # onda
        self._onda = _OndaRecorte(color)
        self._onda.cambio.connect(self._rango_cambio)
        self._onda.terminado.connect(self._fin_reproduccion)
        capa.addWidget(self._onda, 1)
        capa.addWidget(Etiqueta(tr('Arrastra las asas para elegir la parte que se usa · agarra el medio para moverla · doble clic = todo el sonido'), 11, color='#8D9BB5', alineacion=Qt.AlignmentFlag.AlignHCenter))
        # datos
        filad, cd = caja_h(espacio=10)
        self._d_ini = _Dato(tr('INICIO'), color)
        self._d_fin = _Dato(tr('FIN'), color)
        self._d_uso = _Dato(tr('SE USA'), color)
        for d in (self._d_ini, self._d_fin, self._d_uso):
            cd.addWidget(d, 1)
        todo = Boton(tr('Todo el sonido'), self._onda.elegir_todo, alto=54, tam=12)
        Tooltip(todo, tr('Vuelve a usar el sonido completo.'))
        cd.addWidget(todo, 0)
        capa.addWidget(filad)
        # volumen
        filav, cv = caja_h(espacio=12)
        self._altavoz = _Altavoz(color)
        cv.addWidget(self._altavoz, 0)
        cv.addWidget(Etiqueta(tr('Volumen del efecto'), 13, peso='medio', color='#E0EBFB'))
        self._vol = Deslizador(0.0, 2.0, 200, self._vol_cambio, 1.0)
        self._vol.setMinimumWidth(200)
        self._vol.sliderReleased.connect(self._escuchar)
        cv.addWidget(self._vol, 1)
        self._vol_txt = Etiqueta('100 %', 16, peso='extra', color='#FFFFFF')
        self._vol_txt.setMinimumWidth(62)
        cv.addWidget(self._vol_txt)
        reiniciar = Boton('↺', lambda _=False: self._poner_volumen(1.0), tipo='icono', alto=32, ancho=36, tam=14)
        reiniciar.setFixedWidth(36)
        Tooltip(reiniciar, tr('Volumen original (100 %)'))
        cv.addWidget(reiniciar)
        capa.addWidget(filav)
        # botones
        filab, cb = caja_h(espacio=10)
        self._btn_oir = Boton(tr('▶  Escuchar selección'), self._escuchar, tipo='primario', alto=44, tam=14, negrita=True)
        self._btn_oir.setMinimumWidth(190)
        cb.addWidget(self._btn_oir)
        cb.addStretch(1)
        cancelar_b = Boton(tr('Cancelar'), self.reject, alto=44, ancho=110, tam=14)
        self._btn_guardar = Boton(tr('Guardar'), self._guardar, tipo='primario', alto=44, ancho=130, tam=14, negrita=True)
        cb.addWidget(cancelar_b)
        cb.addWidget(self._btn_guardar)
        capa.addWidget(filab)
        for b in self.findChildren(Boton):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._saliendo = False
        # entrada escalonada de los bloques de la ventana
        for k, w in enumerate((cab, self._onda, filad, filav, filab)):
            _aparecer(w, 40 + 70 * k)
        # mientras suena, el botón de escuchar da un destello de luz cada poco
        self._t_play = QTimer(self)
        self._t_play.setInterval(850)
        self._t_play.timeout.connect(lambda: _brillo_boton(self._btn_oir) if self._onda.reproduciendo() else None)
        self._t_play.start()
        if ruta is not None:
            self._cargar(Path(ruta))
        else:
            self._sin_sonido()

    # -- carga
    def _sin_sonido(self):
        self._ruta = None
        self._audio = None
        self._dur = 0.0
        self._onda.mensaje = tr('Elige un sonido concreto para recortarlo y ajustar su volumen')
        self._onda.poner_datos([], 0.0, 0.0, 0.0)
        self._sub.setText(' · '.join(x for x in (self._contexto, tr('Con «Variado» suena cualquiera de la categoría, tal como viene.')) if x))
        for d in (self._d_ini, self._d_fin, self._d_uso):
            d.poner('—')
        self._vol.setEnabled(False)
        self._btn_oir.setEnabled(False)

    def _cargar(self, ruta):
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            audio, sr = sfx_audio.cargar(ruta)
        except Exception as e:
            audio, sr = None, 0
            self._sub.setText(tr('No pude abrir el sonido: {e}', e=e))
        finally:
            self.unsetCursor()
        if audio is None or not len(audio):
            self._sin_sonido()
            return
        self._ruta = Path(ruta)
        self._audio = np.asarray(audio, dtype=np.float32)
        self._dur = len(audio) / float(sr)
        self._titulo.setText(self._ruta.name)
        self._titulo.setToolTip(str(self._ruta))
        self._sub.setText(' · '.join(x for x in (self._contexto, tr('Duración total {d}', d=_seg(self._dur))) if x))
        rec = sfx_rules.recorte_de(self._ruta)
        ini, fin = (rec[0], min(rec[1], self._dur)) if rec else (0.0, self._dur)
        self._onda.mensaje = ''
        self._onda.poner_datos(_picos(self._audio), self._dur, ini, fin)
        self._poner_volumen(sfx_rules.volumen_de(self._ruta), mover=True)
        self._rango_cambio(ini, fin)
        self._vol.setEnabled(True)
        self._btn_oir.setEnabled(True)

    def _elegir_fuente(self, valor):
        self._detener()
        if valor == self.VARIADO:
            self._sin_sonido()
            self._titulo.setText(tr('Regla · {c}', c=self._fuente['categoria']))
            return
        for a in self._fuente['archivos']:
            if Path(a).name == valor:
                self._cargar(Path(a))
                return

    # -- cambios
    def _rango_cambio(self, ini, fin):
        self._d_ini.poner(_seg(ini))
        self._d_fin.poner(_seg(fin))
        self._d_uso.poner(_seg(fin - ini))

    def _vol_cambio(self, v):
        self._vol_txt.setText(f'{int(round(v * 100))} %')
        self._altavoz.poner(v)

    def _poner_volumen(self, v, mover=True):
        if mover:
            self._vol.set(v)
        self._vol_cambio(v)

    # -- escuchar
    def _segmento(self):
        ini, fin = self._onda.rango()
        i, j = int(ini * sfx_audio.SAMPLE_RATE), int(fin * sfx_audio.SAMPLE_RATE)
        seg = np.array(self._audio[i:j], dtype=np.float32)
        paso = min(int(sfx_audio.SAMPLE_RATE * 0.004), len(seg) // 2)
        if paso > 1:
            rampa = np.linspace(0.0, 1.0, paso, dtype=np.float32)
            seg[:paso] *= rampa
            seg[-paso:] *= rampa[::-1]
        return np.clip(seg * float(self._vol.get()), -1.0, 1.0)

    def _escuchar(self, *_):
        if self._audio is None:
            return
        if self._onda.reproduciendo() and not self.sender() is self._vol:
            self._detener()
            return
        seg = self._segmento()
        if not len(seg):
            return
        try:
            self._rep.reproducir(seg)
        except Exception:
            return
        ini, fin = self._onda.rango()
        self._onda.poner_reproduccion(ini, fin)
        self._btn_oir.configure(text=tr('■  Detener'))

    def _detener(self):
        try:
            self._rep.detener()
        except Exception:
            pass
        self._onda.detener_reproduccion()
        self._btn_oir.configure(text=tr('▶  Escuchar selección'))

    def _fin_reproduccion(self):
        self._btn_oir.configure(text=tr('▶  Escuchar selección'))

    # -- guardar
    def _guardar(self):
        if self._saliendo:
            return
        self._detener()
        if self._ruta is not None and self._audio is not None:
            sfx_rules.guardar_volumen(self._ruta, self._vol.get())
            ini, fin = self._onda.rango()
            sfx_rules.guardar_recorte(self._ruta, ini, fin, self._dur)
        if self._fuente:
            self._fuente['al_elegir'](self._ruta)
        if self._al_guardar:
            self._al_guardar(self._ruta)
        # un instante de «Guardado ✓» antes de cerrar
        self._btn_guardar.configure(text='✓  ' + tr('Guardado'))
        _brillo_boton(self._btn_guardar)
        if _reducir_animaciones():
            self.accept()
        else:
            ui.despues(300, self.accept, self)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            self._escuchar()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._guardar()
            return
        super().keyPressEvent(e)

    def done(self, r):
        self._detener()
        if self._saliendo or _reducir_animaciones() or not self.isVisible():
            QDialog.done(self, r)
            return
        self._saliendo = True                     # fundido de salida
        anim = QVariantAnimation(self)
        anim.setDuration(130)
        anim.setStartValue(float(self.windowOpacity()))
        anim.setEndValue(0.0)
        anim.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))
        anim.finished.connect(lambda: QDialog.done(self, r))
        anim.start()
