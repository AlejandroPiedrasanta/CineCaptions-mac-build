# CineCaptions · By Cinema Productions
# 1_codigo/recorrido_ui.py — recorrido visual por pasos: una capa sobre la ventana que ilumina cada zona de la interfaz y la explica (se desactiva en Ajustes).
"""
recorrido_ui.py  (v5.8)
-----------------------
El «recorrido guiado»: una capa transparente encima de TODA la ventana que oscurece lo demás, deja un hueco iluminado (con un halo que
late) sobre la zona del paso y pone al lado una tarjeta con el título, la explicación y los botones Atrás / Siguiente.

  * Cada Paso dice a qué pantalla ir (`pagina`), qué iluminar (`objetivo`: una función que devuelve un widget, un QRect/QRectF en coordenadas de
    la ventana o None = sin foco, tarjeta al centro) y qué contar. El objetivo se vuelve a pedir ~30 veces por segundo: si la zona se mueve
    (se desplaza la lista, cambia el tamaño de la ventana, termina la animación de la pantalla) el foco la sigue.
  * Teclado: → / Intro / Espacio = siguiente, ← = atrás, Esc = salir.
  * La capa se pinta ella misma (no usa QGraphicsOpacityEffect sobre páginas) y solo repinta el halo mientras late.
  * Quién lo lanza y los pasos concretos viven en el script principal (SubtitleApp.iniciar_recorrido / _pasos_recorrido); aquí solo el motor.
"""
import math
import time

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QPoint, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

import qt_kit as ui
from i18n import tr

ANCHO_TARJETA = 410
MARGEN_VENTANA = 18


class Paso:
    """Un paso del recorrido. `objetivo` = función sin argumentos que devuelve un QWidget, un QRect/QRectF (coordenadas de la ventana) o None."""
    __slots__ = ('titulo', 'texto', 'objetivo', 'pagina', 'lado', 'margen', 'antes', 'redondeo')

    def __init__(self, titulo, texto, objetivo=None, pagina=None, lado='auto', margen=10, antes=None, redondeo=16):
        self.titulo = titulo
        self.texto = texto
        self.objetivo = objetivo
        self.pagina = pagina
        self.lado = lado
        self.margen = margen
        self.antes = antes
        self.redondeo = redondeo            # radio de las esquinas del foco (muy grande = círculo)


class _Puntos(QWidget):
    """Los puntitos de avance: el del paso actual es alargado."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self._n = 1
        self._i = 0
        self.setFixedHeight(10)

    def poner(self, n, i):
        self._n, self._i = max(1, n), i
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        x, y = 0.0, self.height() / 2.0
        for k in range(self._n):
            actual = k == self._i
            ancho = 18.0 if actual else 6.0
            c = QColor(ui.ACCENT_CLARO if actual else ('#3B5A8A' if k < self._i else '#26324A'))
            p.setBrush(c)
            p.drawRoundedRect(QRectF(x, y - 3, ancho, 6), 3, 3)
            x += ancho + 5


class Recorrido(QWidget):
    """La capa del recorrido. Se crea con la ventana principal y la lista de pasos; se cierra sola al terminar (llama a `al_terminar(completo)`)."""

    def __init__(self, ventana, pasos, al_terminar=None, al_no_mostrar=None):
        super().__init__(ventana)
        self._v = ventana
        self.pasos = list(pasos)
        self._i = -1
        self._fin = al_terminar
        self._no_mostrar = al_no_mostrar
        self._cerrado = False
        self._rect = QRectF()              # el hueco que se ve (animado)
        self._dest = None                  # el hueco al que va (None = sin foco)
        self._opac = 0.0
        self._t0 = time.perf_counter()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._a_rect = QVariantAnimation(self)
        self._a_rect.valueChanged.connect(self._paso_rect)
        self._a_card = QVariantAnimation(self)
        self._a_card.valueChanged.connect(lambda v: self.card.move(v.toPoint() if hasattr(v, 'toPoint') else v))
        self._a_op = QVariantAnimation(self)
        self._a_op.setDuration(260)
        self._a_op.setStartValue(0.0)
        self._a_op.setEndValue(1.0)
        self._a_op.valueChanged.connect(self._paso_op)
        self._reloj = QTimer(self)
        self._reloj.setInterval(33)
        self._reloj.timeout.connect(self._tick)
        self._construir_tarjeta()
        ventana.installEventFilter(self)
        self.setGeometry(ventana.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._a_op.start()
        self._reloj.start()
        self._ir(0)

    # ---------------------------------------------------------------- la tarjeta
    def _construir_tarjeta(self):
        c = QFrame(self)
        c.setObjectName('recTarjeta')
        c.setStyleSheet(ui.traducir_hoja(f'QFrame#recTarjeta {{ background-color: #0C1526; border: 1px solid {ui.ACCENT_CLARO}; border-radius: 18px; }}'))
        c.setFixedWidth(ANCHO_TARJETA)
        capa = QVBoxLayout(c)
        capa.setContentsMargins(24, 20, 24, 18)
        capa.setSpacing(10)
        fila, cf = ui.caja_h(espacio=8)
        self.paso_lbl = ui.Etiqueta('', 12, peso='negrita', color=ui.ACCENT_CLARO)
        cf.addWidget(self.paso_lbl)
        cf.addStretch(1)
        self.saltar = ui.Enlace(tr('Saltar recorrido'), lambda: self.cerrar(False), 12, color=ui.TEXT_MUTED, color_hover='#FFFFFF', subrayada=False)
        cf.addWidget(self.saltar)
        capa.addWidget(fila)
        self.titulo_lbl = ui.Etiqueta('', 19, peso='extra', color='#FFFFFF', envolver=True)
        capa.addWidget(self.titulo_lbl)
        self.texto_lbl = ui.Etiqueta('', 14, color='#C9D6EC', envolver=True)
        capa.addWidget(self.texto_lbl)
        self.puntos = _Puntos()
        capa.addSpacing(2)
        capa.addWidget(self.puntos)
        capa.addSpacing(4)
        fb, cb = ui.caja_h(espacio=10)
        self.atras_btn = ui.Boton(tr('Atrás'), self.anterior, alto=38, tam=14)
        self.sig_btn = ui.Boton(tr('Siguiente'), self.siguiente, tipo='primario', alto=38, tam=14, negrita=True)
        cb.addWidget(self.atras_btn)
        cb.addStretch(1)
        cb.addWidget(self.sig_btn)
        capa.addWidget(fb)
        self.nomas = ui.Enlace(tr('No volver a mostrar este recorrido'), self._pedir_no_mostrar, 12, color='#6B7B97', color_hover='#FFFFFF', subrayada=False)
        capa.addWidget(self.nomas, 0, Qt.AlignmentFlag.AlignHCenter)
        for w in (self.atras_btn, self.sig_btn):
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.card = c

    def _pintar_tarjeta(self, paso):
        n = len(self.pasos)
        self.paso_lbl.configure(text=tr('Paso {i} de {n}', i=self._i + 1, n=n))
        self.titulo_lbl.configure(text=paso.titulo)
        self.texto_lbl.configure(text=paso.texto)
        self.puntos.poner(n, self._i)
        ultimo = self._i >= n - 1
        self.atras_btn.setVisible(self._i > 0)
        self.sig_btn.setText(tr('¡Listo!') if ultimo else tr('Siguiente'))
        self.saltar.setVisible(not ultimo)
        self.nomas.setVisible(True)
        lay = self.card.layout()
        lay.activate()
        alto = lay.totalHeightForWidth(ANCHO_TARJETA)
        self.card.setFixedHeight(alto if alto > 0 else self.card.sizeHint().height())

    # ---------------------------------------------------------------- navegación
    def siguiente(self):
        if self._i >= len(self.pasos) - 1:
            self.cerrar(True)
        else:
            self._ir(self._i + 1)

    def anterior(self):
        if self._i > 0:
            self._ir(self._i - 1)

    def _ir(self, k):
        k = max(0, min(len(self.pasos) - 1, k))
        paso = self.pasos[k]
        self._i = k
        try:
            if paso.pagina and getattr(self._v, '_pagina_actual', None) != paso.pagina:
                self._v.ir_a(paso.pagina, animar=False)
            if paso.antes:
                paso.antes()
        except Exception:
            pass
        self._pintar_tarjeta(paso)
        self._dest = None                   # el siguiente _tick recoloca el foco y la tarjeta
        for ms in (40, 260, 700):
            QTimer.singleShot(ms, self._asegurar_visible)
        self._tick(forzar=True)
        self.setFocus()

    def cerrar(self, completo):
        if self._cerrado:
            return
        self._cerrado = True
        self._reloj.stop()
        try:
            self._v.removeEventFilter(self)
        except Exception:
            pass
        self.hide()
        fin = self._fin
        self.deleteLater()
        if fin:
            try:
                fin(bool(completo))
            except Exception:
                pass

    def _pedir_no_mostrar(self):
        if self._no_mostrar:
            try:
                self._no_mostrar()
            except Exception:
                pass
        self.cerrar(False)

    # ---------------------------------------------------------------- el foco
    def _widget_objetivo(self):
        try:
            paso = self.pasos[self._i]
            o = paso.objetivo() if paso.objetivo else None
        except Exception:
            return None
        return o if isinstance(o, QWidget) else None

    def _asegurar_visible(self):
        """Si la zona está dentro de una lista que se desplaza, la lleva a la vista."""
        w = self._widget_objetivo()
        if w is None or not ui.vivo(w):
            return
        p = w.parentWidget()
        while p is not None and p is not self._v:
            if isinstance(p, QScrollArea):
                try:
                    p.ensureWidgetVisible(w, 24, 70)
                except Exception:
                    pass
            p = p.parentWidget()

    def _rect_objetivo(self):
        paso = self.pasos[self._i]
        if paso.objetivo is None:
            return None
        try:
            o = paso.objetivo()
        except Exception:
            return None
        if o is None:
            return None
        if isinstance(o, (QRect, QRectF)):
            r = QRectF(o)
        elif isinstance(o, QWidget):
            if not ui.vivo(o) or not o.isVisible():
                return None
            esq = o.mapTo(self._v, QPoint(0, 0))
            r = QRectF(esq.x(), esq.y(), o.width(), o.height())
            p = o.parentWidget()
            while p is not None and p is not self._v:         # lo que no cabe en el visor de una lista, no se ilumina
                if isinstance(p, QScrollArea):
                    vp = p.viewport()
                    e = vp.mapTo(self._v, QPoint(0, 0))
                    r = r.intersected(QRectF(e.x(), e.y(), vp.width(), vp.height()))
                p = p.parentWidget()
        else:
            return None
        if r.width() < 6 or r.height() < 6:
            return None
        m = float(paso.margen)
        return r.adjusted(-m, -m, m, m)

    @staticmethod
    def _cerca(a, b):
        return (abs(a.x() - b.x()) < 1.5 and abs(a.y() - b.y()) < 1.5 and abs(a.width() - b.width()) < 1.5 and abs(a.height() - b.height()) < 1.5)

    def _tick(self, forzar=False):
        if self._cerrado or not ui.vivo(self):
            return
        padre = self.parentWidget()
        if padre is not None and padre.children() and padre.children()[-1] is not self:
            self.raise_()                     # la isla se sube sola al cambiar de pantalla: la capa siempre encima
        if self.geometry() != padre.rect():
            self.setGeometry(padre.rect())
        nuevo = self._rect_objetivo()
        mismo = (nuevo is None and self._dest is None) or (nuevo is not None and self._dest is not None and self._cerca(nuevo, self._dest))
        if mismo and not forzar:
            if self._dest is not None and not self._a_rect.state() == QAbstractAnimation.State.Running:
                self.update(self._dest.adjusted(-26, -26, 26, 26).toAlignedRect())     # solo el halo late
            return
        primera = self._dest is None and not self._rect.isValid()
        self._dest = nuevo
        self._mover_foco(nuevo, rapido=not primera and self._a_rect.state() != QAbstractAnimation.State.Running and not forzar)
        self._mover_tarjeta(nuevo)
        self.update()

    def _mover_foco(self, dest, rapido=False):
        self._a_rect.stop()
        if dest is None:
            self._rect = QRectF()
            return
        if not self._rect.isValid() or self._rect.isEmpty():
            c = dest.center()
            self._rect = QRectF(c.x() - 4, c.y() - 4, 8, 8)
        self._a_rect.setDuration(140 if rapido else 420)
        self._a_rect.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_rect.setStartValue(self._rect)
        self._a_rect.setEndValue(dest)
        self._a_rect.start()

    def _paso_rect(self, v):
        self._rect = QRectF(v)
        self.update()

    def _paso_op(self, v):
        self._opac = float(v)
        self.update()

    # ---------------------------------------------------------------- la tarjeta junto al foco
    def _posicion_tarjeta(self, foco):
        W, H = self.width(), self.height()
        cw, ch = self.card.width(), self.card.height()
        m = MARGEN_VENTANA

        def en_x(x):
            return int(max(m, min(W - cw - m, x)))

        def en_y(y):
            return int(max(m, min(H - ch - m, y)))
        if foco is None:
            return QPoint(en_x((W - cw) / 2), en_y((H - ch) / 2))

        def cabe(pt):
            return pt.x() >= m and pt.y() >= m and pt.x() + cw <= W - m and pt.y() + ch <= H - m
        lado = self.pasos[self._i].lado
        orden = ['abajo', 'derecha', 'izquierda', 'arriba']
        if lado in orden:
            orden = [lado] + [s for s in orden if s != lado]
        for s in orden:
            if s == 'abajo':
                pt = QPoint(en_x(foco.center().x() - cw / 2), int(foco.bottom() + 18))
            elif s == 'arriba':
                pt = QPoint(en_x(foco.center().x() - cw / 2), int(foco.top() - 18 - ch))
            elif s == 'derecha':
                pt = QPoint(int(foco.right() + 18), en_y(foco.center().y() - ch / 2))
            else:
                pt = QPoint(int(foco.left() - 18 - cw), en_y(foco.center().y() - ch / 2))
            if cabe(pt):
                return pt
        # el foco ocupa casi toda la ventana: la tarjeta va dentro, abajo y centrada
        return QPoint(en_x(foco.center().x() - cw / 2), en_y(H - ch - m))

    def _mover_tarjeta(self, foco):
        destino = self._posicion_tarjeta(foco)
        self._a_card.stop()
        if not self.card.isVisible():
            self.card.move(destino)
            self.card.show()
            self.card.raise_()
            return
        self._a_card.setDuration(380)
        self._a_card.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_card.setStartValue(self.card.pos())
        self._a_card.setEndValue(destino)
        self._a_card.start()

    # ---------------------------------------------------------------- pintado y eventos
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = QPainterPath()
        total.addRect(QRectF(self.rect()))
        hueco = self._rect if (self._dest is not None and self._rect.isValid() and not self._rect.isEmpty()) else None
        radio = float(self.pasos[self._i].redondeo) if 0 <= self._i < len(self.pasos) else 16.0
        if hueco is not None:
            h = QPainterPath()
            h.addRoundedRect(hueco, radio, radio)
            total = total.subtracted(h)
        p.fillPath(total, QColor(3, 8, 15, int(198 * self._opac)))
        if hueco is not None:
            pulso = 0.5 + 0.5 * math.sin((time.perf_counter() - self._t0) * 3.4)
            base = QColor(ui.ACCENT_CLARO)
            for grosor, alfa, ext in ((12.0, 26, 5.0), (7.0, 58, 2.5), (2.4, 240, 0.0)):
                c = QColor(base)
                c.setAlpha(int(alfa * self._opac * ((0.55 + 0.45 * pulso) if grosor > 3 else 1.0)))
                p.setPen(QPen(c, grosor))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(hueco.adjusted(-ext, -ext, ext, ext), radio + ext, radio + ext)
        p.end()

    def mousePressEvent(self, e):
        e.accept()                # la capa se come los clics: el recorrido no deja tocar lo de abajo

    def mouseReleaseEvent(self, e):
        e.accept()

    def mouseDoubleClickEvent(self, e):
        e.accept()

    def wheelEvent(self, e):
        e.accept()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.cerrar(False)
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.siguiente()
        elif k == Qt.Key.Key_Left:
            self.anterior()
        else:
            e.accept()

    def eventFilter(self, obj, ev):
        if obj is self._v and ev.type() == QEvent.Type.Resize and not self._cerrado:
            self.setGeometry(self._v.rect())
            self._tick(forzar=True)
        return False
