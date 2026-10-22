# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_ui.py — la página SONIDO = «AI Sound Director» (fase 6): la IA hace el 95 % del sonido; el usuario lo dirige (5 %).
"""
Al pulsar SONIDO se abre esta página directamente (la de antes —Simple / Emojis / Edición PRO— ya no se ve; su código sigue como motor interno).
Nada técnico a la vista (ni EQ, ni compresores, ni dB): lo que la IA hizo, por qué, y pocas maneras de pedirle otra cosa.

    cabecera     AI Sound Director (interruptor) · Tema · AI Sonic Style · Sound Score · «En Resolve y al día» / «cambios sin poner»
    estado       Voz · Ruido · Música · Ambiente · Sonido de motions · Mezcla · Master · Material (sus bibliotecas), cada uno con su ✓ y una línea
    acciones     ▶ Original / ▶ AI Sound (A/B del tramo elegido, mezclas reales) · ✨ Rediseñar sonido · Aplicar a Resolve · Deshacer todo
    controles    Estilo + 5 (intensidad, densidad de SFX, prioridad de voz, música, ambiente), AUTO por defecto
    línea        VIDEO (cortes y captions) · VOZ · MÚSICA · AMBIENTE · SONIDOS IA · MOTIONS PRO: ver, elegir y oír un evento (no es un DAW)
    inspector    el evento, su diseño IA, el material (archivo de la biblioteca o sintetizado), por qué, importancia y MENOS / MÁS / REGENERAR /
                 SILENCIAR / BLOQUEAR / Oír
Cada cambio va SOLO a Resolve (v5.37, director_sonido_sesion.aplicar_al_momento) si está abierto y el último GO fue con el director.
    «dile…»      una frase («menos sonidos», «la voz más clara», «rediseña el final», «quita el sonido de éxito»)

Todo lo que cuesta (leer el estado, rediseñar, mezclas A/B, Resolve) va por correr_en_hilo; sin globos ni avisos flotantes: una línea de estado.
El motor: director_sonido_sesion.
"""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

import qt_kit as ui
from qt_kit import Boton, Entrada, Etiqueta, IconoEstado, Interruptor, Menu, Segmentado, StringVar, Tarjeta, caja_h
from qt_kit import QColor
from i18n import tr

TEXT_MUTED = ui.TEXT_MUTED
COLOR_TIPO = {'golpe': '#F5B84B', 'whoosh': '#00C8FF', 'giro': '#7FDBFF', 'riser': '#B388FF', 'trazo': '#4ADE80', 'acento': '#FFB86B',
              'tick': '#4589FF', 'pop': '#FF8FB1'}
OPCIONES = {   # control → [(valor, etiqueta)]
    'estilo': [('auto', 'Auto'), ('limpio', 'Limpio'), ('cinematico', 'Cinemático'), ('energico', 'Enérgico'), ('minimo', 'Mínimo')],
    'intensidad': [('auto', 'Auto'), ('poco', 'Suave'), ('medio', 'Media'), ('mucho', 'Potente')],
    'densidad': [('auto', 'Auto'), ('poco', 'Mínima'), ('medio', 'Media'), ('mucho', 'Rica')],
    'voz': [('auto', 'Auto'), ('poco', 'Equilibrio'), ('medio', 'Alta'), ('mucho', 'Máxima')],
    'musica': [('auto', 'Auto'), ('nada', 'Sin'), ('poco', 'Suave'), ('medio', 'Media'), ('mucho', 'Enérgica')],
    'ambiente': [('auto', 'Auto'), ('nada', 'Sin'), ('poco', 'Mínimo'), ('medio', 'Sutil'), ('mucho', 'Inmersivo')],
}
TITULO_CONTROL = {'estilo': 'Estilo', 'intensidad': 'Intensidad', 'densidad': 'Densidad de sonidos', 'voz': 'Prioridad de la voz', 'musica': 'Música',
                  'ambiente': 'Ambiente'}


def _tiempo(t):
    t = max(0.0, float(t or 0.0))
    return f'{int(t // 60)}:{t % 60:04.1f}'.replace('.', ',')


# ====================================================================================== piezas
class Puntuacion(QWidget):
    """El Sound Score en un anillo (o «—» si aún no se midió la mezcla). Un clic pide su desglose."""
    clic = Signal()

    def __init__(self, padre=None):
        super().__init__(padre)
        self._v = None
        self.setFixedSize(88, 88)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit()

    def poner(self, v):
        self._v = None if v is None else int(round(float(v)))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(5, 5, 78, 78)
        p.setPen(QPen(QColor('#1E2A42'), 6))
        p.drawEllipse(r)
        if self._v is not None:
            color = ui.VERDE if self._v >= 85 else (ui.AMBAR if self._v >= 70 else ui.ROJO)
            p.setPen(QPen(QColor(color), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(r, 90 * 16, -int(360 * 16 * max(0, min(100, self._v)) / 100))
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(21, True))
        p.drawText(QRectF(0, 18, 88, 34), int(Qt.AlignmentFlag.AlignCenter), '—' if self._v is None else str(self._v))
        p.setPen(QColor(TEXT_MUTED))
        p.setFont(ui.fuente(8))
        p.drawText(QRectF(12, 50, 64, 14), int(Qt.AlignmentFlag.AlignCenter), tr('SOUND SCORE'))
        p.end()


class FilaEstado(QWidget):
    """✓ Voz · Excelente · «Limpiada (PyAV): fondo −36 → −54 dBFS»."""
    def __init__(self, padre=None):
        super().__init__(padre)
        c = QHBoxLayout(self)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(10)
        self.icono = IconoEstado('ok')
        c.addWidget(self.icono, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        fila = QHBoxLayout()
        fila.setSpacing(8)
        self.titulo = Etiqueta('', 13, peso='medio', color='#FFFFFF')
        self.valor = Etiqueta('', 13, color=ui.ACCENT_CLARO)
        fila.addWidget(self.titulo)
        fila.addWidget(self.valor)
        fila.addStretch(1)
        col.addLayout(fila)
        self.detalle = ui.Elidida('', 11, color=TEXT_MUTED)              # (una línea: en la rejilla, el texto envuelto se pisaba con la fila de abajo)
        col.addWidget(self.detalle)
        c.addLayout(col, 1)

    def poner(self, n):
        self.icono.poner({'ok': 'ok', 'aviso': 'aviso', 'error': 'error'}.get(n.get('nivel'), 'ok' if n.get('nivel') != 'info' else 'aviso'))
        self.titulo.setText(tr(n.get('titulo') or ''))
        self.valor.setText(tr(str(n.get('valor') or '')))
        self.detalle.setText(str(n.get('detalle') or ''))


class LineaSonido(QWidget):
    """La línea de tiempo simple: VIDEO · VOZ · MÚSICA · AMBIENTE · SONIDOS IA · MOTIONS PRO (los sonidos de los motions de la PRO, rehechos por el
    director al colocarlos: se ven, no se eligen). Clic = elegir el evento más cercano (y el instante del A/B)."""
    elegido = Signal(object)                 # el evento (dict) o None
    IZQ, DER, ARRIBA, CARRIL, HUECO = 104, 14, 22, 24, 7
    CARRILES = ('VIDEO', 'VOZ', 'MÚSICA', 'AMBIENTE', 'SONIDOS IA', 'MOTIONS PRO')

    def __init__(self, padre=None):
        super().__init__(padre)
        self._d = {}
        self._sel = None
        self._hover = None
        self._cursor = 0.0
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(self.ARRIBA + len(self.CARRILES) * (self.CARRIL + self.HUECO) + 8)

    def poner(self, res, seleccion=None):
        self._d = res or {}
        self._sel = seleccion
        self.update()

    def cursor(self):
        return self._cursor

    def _x(self, t):
        dur = max(0.5, float(self._d.get('duracion') or 1.0))
        return self.IZQ + (float(t or 0.0) / dur) * max(10.0, self.width() - self.IZQ - self.DER)

    def _t(self, x):
        dur = max(0.5, float(self._d.get('duracion') or 1.0))
        return max(0.0, min(dur, (x - self.IZQ) / max(10.0, self.width() - self.IZQ - self.DER) * dur))

    def _y(self, i):
        return self.ARRIBA + i * (self.CARRIL + self.HUECO)

    def _cerca(self, x, y, siguiente=False):
        """El evento bajo el clic: de los bloques que lo contienen, el de ancla más cercana y, si empatan, el más corto (un riser que acaba en un golpe
        no tapa al golpe); si ninguno lo contiene, el ancla más cercana. `siguiente`: otro clic en el mismo sitio pasa al siguiente solapado."""
        if y < self._y(4) - 4 or y > self._y(5) - 2:
            return None
        visibles = [e for e in self._d.get('eventos') or [] if e.get('suena') or e.get('silenciado')]
        dentro = [e for e in visibles if self._x(e.get('t')) - 3 <= x <= max(self._x(e.get('t')) + 5, self._x(float(e.get('t') or 0) + float(e.get('dur') or 0))) + 3]
        if dentro:
            dentro.sort(key=lambda e: (round(abs(self._x(e.get('ancla')) - x) / 4.0), float(e.get('dur') or 0)))
            claves = [e.get('clave') for e in dentro]
            if siguiente and self._sel in claves:
                return dentro[(claves.index(self._sel) + 1) % len(dentro)]
            return dentro[0]
        mejor, dmin = None, 9.0
        for e in visibles:
            d = abs(self._x(e.get('ancla')) - x)
            if d < dmin:
                mejor, dmin = e, d
        return mejor

    def mouseMoveEvent(self, e):
        h = self._cerca(e.position().x(), e.position().y())
        if (h or {}).get('clave') != (self._hover or {}).get('clave'):
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self._d.get('hay'):
            return
        x = e.position().x()
        self._cursor = self._t(x)
        ev = self._cerca(x, e.position().y(), siguiente=True)
        if ev is not None:
            self._cursor = max(0.0, float(ev.get('ancla') or 0.0))
        self._sel = (ev or {}).get('clave')
        self.update()
        self.elegido.emit(ev)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        d = self._d
        car = d.get('carriles') or {}
        dur = float(d.get('duracion') or 0.0)
        p.setFont(ui.fuente(10, True))
        for i, nombre in enumerate(self.CARRILES):                       # fondos y nombres de los carriles
            y = self._y(i)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#0B1424'))
            p.drawRoundedRect(QRectF(self.IZQ, y, w - self.IZQ - self.DER, self.CARRIL), 6, 6)
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(QRectF(0, y, self.IZQ - 10, self.CARRIL), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), tr(nombre))
        if not d.get('hay') or dur <= 0:
            p.end()
            return
        p.setFont(ui.fuente(9))                                          # regla: cada 10 s
        p.setPen(QColor('#4A5A78'))
        paso = 10.0 if dur <= 120 else (30.0 if dur <= 600 else 120.0)
        t = 0.0
        while t <= dur + 0.01:
            x = self._x(t)
            p.drawLine(int(x), 14, int(x), 19)
            p.drawText(QRectF(x - 30, 0, 60, 13), int(Qt.AlignmentFlag.AlignCenter), _tiempo(t).split(',')[0])
            t += paso
        y0 = self._y(0)                                                  # VIDEO: cortes y captions (los que suenan, más vivos)
        p.setPen(QPen(QColor('#3A4C70'), 1))
        for tc in car.get('cortes') or []:
            p.drawLine(int(self._x(tc)), int(y0 + 3), int(self._x(tc)), int(y0 + self.CARRIL - 3))
        for t_c, dec, _txt in car.get('captions') or []:
            suena = dec not in ('LEAVE_SILENT',)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ui.AMBAR if suena else '#55617A'))
            r = 3.2 if suena else 2.0
            p.drawEllipse(QRectF(self._x(t_c) - r, y0 + self.CARRIL / 2 - r, 2 * r, 2 * r))
        y1 = self._y(1)                                                  # VOZ
        p.setBrush(QColor(0, 200, 255, 110))
        for a, b in car.get('voz') or []:
            p.drawRoundedRect(QRectF(self._x(a), y1 + 5, max(2.0, self._x(b) - self._x(a)), self.CARRIL - 10), 4, 4)
        y2 = self._y(2)                                                  # MÚSICA
        if car.get('musica'):
            p.setBrush(QColor(179, 136, 255, 120))
            for a, b, _q in car['musica']:
                p.drawRoundedRect(QRectF(self._x(a), y2 + 6, max(2.0, self._x(b) - self._x(a)), self.CARRIL - 12), 4, 4)
        else:
            p.setPen(QColor('#4A5A78'))
            p.drawText(QRectF(self.IZQ + 10, y2, 300, self.CARRIL), int(Qt.AlignmentFlag.AlignVCenter), tr('sin música'))
        y3 = self._y(3)                                                  # AMBIENTE: escenas
        for a, b, ctx, dec in car.get('ambiente') or []:
            x0, x1 = self._x(a), self._x(b)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(74, 222, 128, 70 if dec in ('ADD_SUBTLE_AMBIENCE', 'REPLACE_AMBIENCE') else 30))
            p.drawRoundedRect(QRectF(x0 + 1, y3 + 4, max(2.0, x1 - x0 - 2), self.CARRIL - 8), 4, 4)
            if x1 - x0 > 60:
                p.setPen(QColor('#9FB0CC'))
                p.drawText(QRectF(x0 + 6, y3, x1 - x0 - 8, self.CARRIL), int(Qt.AlignmentFlag.AlignVCenter), tr(str(ctx or '')))
        y4 = self._y(4)                                                  # SONIDOS IA
        for e in d.get('eventos') or []:
            if not (e.get('suena') or e.get('silenciado')):
                continue
            x = self._x(e.get('t'))
            ancho = max(5.0, self._x(float(e.get('t') or 0) + float(e.get('dur') or 0.2)) - x)
            color = QColor(COLOR_TIPO.get(e.get('tipo'), ui.ACCENT_CLARO))
            rect = QRectF(x, y4 + 4, ancho, self.CARRIL - 8)
            if e.get('silenciado'):
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#55617A'), 1, Qt.PenStyle.DashLine))
            else:
                color.setAlpha(230 if e.get('clave') in (self._sel, (self._hover or {}).get('clave')) else 170)
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, 4, 4)
            if e.get('clave') == self._sel:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#FFFFFF'), 1.6))
                p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 5, 5)
            if e.get('bloqueado'):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#FFFFFF'))
                p.drawEllipse(QRectF(x + ancho / 2 - 2, y4 - 1, 4, 4))
        y5 = self._y(5)                                                  # MOTIONS PRO (rehechos por el director; los callados, en hueco)
        pro = d.get('pro_eventos') or []
        for t_p, dur_p, tipo_p, dec_p in pro:
            x = self._x(t_p)
            rect = QRectF(x, y5 + 6, max(4.0, self._x(float(t_p or 0) + float(dur_p or 0.2)) - x), self.CARRIL - 12)
            if dec_p == 'GENERATE':
                color = QColor(COLOR_TIPO.get(tipo_p, ui.ACCENT_CLARO))
                color.setAlpha(140)
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#55617A'), 1, Qt.PenStyle.DashLine))
            p.drawRoundedRect(rect, 3, 3)
        if not pro:
            p.setPen(QColor('#4A5A78'))
            p.drawText(QRectF(self.IZQ + 10, y5, 400, self.CARRIL), int(Qt.AlignmentFlag.AlignVCenter), tr('sin motions de la PRO en este GO'))
        xc = self._x(self._cursor)                                       # el instante del A/B
        p.setPen(QPen(QColor(255, 255, 255, 150), 1))
        p.drawLine(int(xc), int(self.ARRIBA - 4), int(xc), int(self._y(5) + self.CARRIL))
        p.end()


# ====================================================================================== la página
class PaginaDirector(QWidget):
    """La página SONIDO. `video` = función que da el video de Inicio; `offset` = función con el desplazamiento de GO en el timeline (Aplicar)."""

    def __init__(self, padre=None, video=None, offset=None):
        super().__init__(padre)
        self._video_fn = video or (lambda: '')
        self._offset_fn = offset or (lambda: 0)
        self._res = {}
        self._ev = None
        self._ocupado = False
        self._pintando = False
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(16)
        # ---- cabecera
        cab = Tarjeta(espacio=10, margenes=(22, 18, 22, 18), horizontal=True)
        col = QVBoxLayout()
        col.setSpacing(4)
        fila, cf = caja_h(espacio=14)
        cf.addWidget(Etiqueta(tr('AI Sound Director'), 22, peso='negrita', color='#FFFFFF'))
        self._var_on = ui.BooleanVar(False)
        self._sw = Interruptor(tr('Activado'), self._var_on, self._cambio_on, tam=13, color='#E0EBFB')
        cf.addWidget(self._sw)
        cf.addStretch(1)
        col.addWidget(fila)
        self._lbl_tema = Etiqueta('', 13, color='#B4C0D6')
        col.addWidget(self._lbl_tema)
        self._lbl_estado = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        col.addWidget(self._lbl_estado)
        fr, cr = caja_h(espacio=8)                                     # dónde está: al día en Resolve o con cambios sin poner
        self._ico_resolve = IconoEstado('ok')
        cr.addWidget(self._ico_resolve, 0, Qt.AlignmentFlag.AlignVCenter)
        self._lbl_resolve = Etiqueta('', 12, peso='medio', color='#E0EBFB')
        cr.addWidget(self._lbl_resolve)
        cr.addStretch(1)
        col.addWidget(fr)
        self._fila_resolve = fr
        cab.capa.addLayout(col, 1)
        self._score = Puntuacion()
        self._score.clic.connect(self._desglose)
        cab.capa.addWidget(self._score, 0, Qt.AlignmentFlag.AlignVCenter)
        capa.addWidget(cab)
        # ---- vacío (sin GO con el director todavía)
        self._vacio = Tarjeta(espacio=8, margenes=(22, 18, 22, 18))
        self._lbl_vacio = Etiqueta('', 14, color='#E0EBFB', envolver=True)
        self._vacio.capa.addWidget(self._lbl_vacio)
        capa.addWidget(self._vacio)
        # ---- el resto (solo con diseño)
        self._cuerpo = QWidget()
        cc = QVBoxLayout(self._cuerpo)
        cc.setContentsMargins(0, 0, 0, 0)
        cc.setSpacing(16)
        est = Tarjeta(espacio=12, margenes=(22, 16, 22, 18))
        est.capa.addWidget(Etiqueta(tr('Lo que decidió para este video'), 15, peso='medio', color='#FFFFFF'))
        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(24)
        rejilla.setVerticalSpacing(12)
        self._filas = {}
        for i, k in enumerate(('voz', 'ruido', 'musica', 'ambiente', 'motion', 'mezcla', 'master', 'material')):
            self._filas[k] = FilaEstado()
            rejilla.addWidget(self._filas[k], i // 2, i % 2)
        est.capa.addLayout(rejilla)
        cc.addWidget(est)
        # acciones
        acc, ca = caja_h(espacio=10)
        self._b_orig = Boton(tr('▶  Original'), lambda: self._oir('original'), tipo='fantasma', alto=36, tam=13)
        self._b_ai = Boton(tr('▶  AI Sound'), lambda: self._oir('ai'), alto=36, tam=13)
        self._b_parar = Boton(tr('■'), self._parar, tipo='fantasma', alto=36, ancho=44, tam=13)
        ca.addWidget(self._b_orig)
        ca.addWidget(self._b_ai)
        ca.addWidget(self._b_parar)
        ca.addStretch(1)
        self._b_deshacer = Boton(tr('Deshacer todo'), self._deshacer, tipo='fantasma', alto=36, tam=13)
        ca.addWidget(self._b_deshacer)
        self._b_aplicar = Boton(tr('Aplicar a Resolve'), self._aplicar, alto=36, tam=13)
        ca.addWidget(self._b_aplicar)
        self._b_redisenar = Boton(tr('Rediseñar sonido'), self._redisenar, tipo='primario', alto=36, tam=13, negrita=True)
        ca.addWidget(self._b_redisenar)
        cc.addWidget(acc)
        # controles
        ctl = Tarjeta(espacio=10, margenes=(22, 16, 22, 16))
        ctl.capa.addWidget(Etiqueta(tr('Dirige el sonido (todo en Auto: decide la IA)'), 15, peso='medio', color='#FFFFFF'))
        rej = QGridLayout()
        rej.setHorizontalSpacing(14)
        rej.setVerticalSpacing(10)
        self._vars = {}
        for i, k in enumerate(OPCIONES):
            rej.addWidget(Etiqueta(tr(TITULO_CONTROL[k]), 13, color=TEXT_MUTED), i, 0)
            self._vars[k] = StringVar(tr('Auto'))
            seg = Segmentado([tr(t) for _v, t in OPCIONES[k]], self._vars[k], lambda etiqueta, k=k: self._cambio_control(k, etiqueta), alto=30, tam=12)
            rej.addWidget(seg, i, 1, Qt.AlignmentFlag.AlignLeft)
        rej.setColumnStretch(2, 1)
        ctl.capa.addLayout(rej)
        cc.addWidget(ctl)
        # línea de tiempo + inspector
        lt = Tarjeta(espacio=10, margenes=(18, 14, 18, 14))
        lt.capa.addWidget(Etiqueta(tr('Línea de sonido · toca un sonido para verlo, oírlo o cambiarlo'), 15, peso='medio', color='#FFFFFF'))
        self._linea = LineaSonido()
        self._linea.elegido.connect(self._elegir)
        lt.capa.addWidget(self._linea)
        cc.addWidget(lt)
        ins = Tarjeta(espacio=8, margenes=(22, 16, 22, 16))
        self._lbl_ev = Etiqueta('', 17, peso='medio', color='#FFFFFF')
        self._lbl_diseno = Etiqueta('', 13, color=ui.ACCENT_CLARO)
        self._lbl_material = ui.Elidida('', 12, color='#B4C0D6')
        self._lbl_porque = Etiqueta('', 12, color='#B4C0D6', envolver=True)
        self._lbl_imp = Etiqueta('', 12, color=TEXT_MUTED)
        for w in (self._lbl_ev, self._lbl_diseno, self._lbl_material, self._lbl_porque, self._lbl_imp):
            ins.capa.addWidget(w)
        bot, cb = caja_h(espacio=8)
        self._b_oir_ev = Boton(tr('▶  Oír'), self._oir_evento, tipo='fantasma', alto=32, tam=12)
        self._b_menos = Boton(tr('Menos…'), lambda: self._menu('menos'), alto=32, tam=12)
        self._b_mas = Boton(tr('Más…'), lambda: self._menu('mas'), alto=32, tam=12)
        self._b_regen = Boton(tr('Regenerar'), lambda: self._retocar('regenerar'), alto=32, tam=12)
        self._b_silencio = Boton(tr('Silenciar'), lambda: self._retocar('silenciar'), tipo='fantasma', alto=32, tam=12)
        self._b_bloq = Boton(tr('Bloquear'), lambda: self._retocar('bloquear'), tipo='fantasma', alto=32, tam=12)
        for b in (self._b_oir_ev, self._b_menos, self._b_mas, self._b_regen, self._b_silencio, self._b_bloq):
            cb.addWidget(b)
        cb.addStretch(1)
        ins.capa.addWidget(bot)
        self._botones_ev = (self._b_oir_ev, self._b_menos, self._b_mas, self._b_regen, self._b_silencio, self._b_bloq)
        cc.addWidget(ins)
        # «dile a AI Sound Director»
        dile = Tarjeta(espacio=8, margenes=(22, 14, 22, 14))
        fd, cdl = caja_h(espacio=10)
        self._var_frase = StringVar('')
        self._entrada = Entrada(self._var_frase, placeholder=tr('Dile a AI Sound Director qué quieres cambiar…  («menos sonidos», «la voz más clara», «rediseña el final»)'),
                                alto=38, tam=13)
        self._entrada.returnPressed.connect(self._frase)
        cdl.addWidget(self._entrada, 1)
        cdl.addWidget(Boton(tr('Enviar'), self._frase, alto=38, tam=13))
        dile.capa.addWidget(fd)
        cc.addWidget(dile)
        capa.addWidget(self._cuerpo)
        capa.addStretch(1)                                           # (el sobrante, abajo: las tarjetas con su alto natural)
        self._acciones =(self._b_orig, self._b_ai, self._b_redisenar, self._b_aplicar, self._b_deshacer) + self._botones_ev
        self._pintar_evento(None)
        self._vacio.hide()
        self._cuerpo.hide()

    # ---------------------------------------------------------------- datos
    def video(self):
        try:
            return str(self._video_fn() or '')
        except Exception:
            return ''

    def _video_mostrado(self):
        """El video cuyo diseño se ve (el de Inicio o, si ese aún no pasó por GO con el director, el último que sí): las acciones van sobre él."""
        return str(self._res.get('video') or self.video())

    def poner_video(self, _ruta=None):
        self.refrescar()

    def refrescar(self):
        """Lee el diseño del video de Inicio (en un hilo) y lo pinta."""
        import director_sonido_sesion as S
        v = self.video()
        ui.correr_en_hilo(self, lambda: S.resumen(v), self._al_resumen)

    def _al_resumen(self, res, err):
        if err is not None:
            self._estado(tr('No pude leer el diseño de sonido: {e}', e=err))
            return
        self._pintar(res)

    def _pintar(self, res):
        self._res = res or {}
        self._pintando = True
        try:
            self._var_on.set(bool(self._res.get('activo')))
            for k, (_v, etiqueta) in ((k, next(((v, t) for v, t in OPCIONES[k] if v == (self._res.get('controles') or {}).get(k, 'auto')), OPCIONES[k][0]))
                                      for k in OPCIONES):
                self._vars[k].set(tr(etiqueta))
        finally:
            self._pintando = False
        hay = bool(self._res.get('hay'))
        self._vacio.setVisible(not hay)
        self._cuerpo.setVisible(hay)
        if not hay:
            self._lbl_tema.setText(tr('El sound designer de GO: escucha el video y decide qué suena, qué no y por qué.'))
            self._lbl_vacio.setText(tr(self._res.get('motivo') or ''))
            self._score.poner(None)
            self._lbl_estado.setText(self._texto_on())
            return
        estilo = self._res.get('estilo_usuario')
        sonic = self._res.get('sonic_style') or ''
        if estilo:
            sonic = tr(dict(OPCIONES['estilo']).get(estilo, estilo)) + ' ' + tr('(elegido por ti)')
        self._lbl_tema.setText(tr('Tema: {t}', t=self._res.get('tema') or '—') + '   ·   ' + tr('AI Sonic Style: {s}', s=sonic) + '   ·   ' +
                               (tr('{v} (el último que pasó por GO)', v=self._res.get('nombre_video')) if self._res.get('otro_video') else self._res.get('nombre_video') or ''))
        self._lbl_estado.setText(self._texto_on())
        self._score.poner(self._res.get('sound_score'))
        for n in self._res.get('notas') or []:
            if n.get('clave') in self._filas:
                self._filas[n['clave']].poner(n)
        self._b_aplicar.setEnabled(bool(self._res.get('puede_aplicar')) and not self._ocupado)
        self._pintar_resolve()
        sel = (self._ev or {}).get('clave')
        self._ev = next((e for e in self._res.get('eventos') or [] if e.get('clave') == sel), None)
        self._linea.poner(self._res, sel if self._ev else None)
        self._pintar_evento(self._ev)

    def _pintar_resolve(self):
        """Al día en Resolve (y desde cuándo) o con cambios sin poner; con cambios, «Aplicar a Resolve» pasa a ser el botón principal."""
        hay = bool(self._res.get('hay'))
        self._fila_resolve.setVisible(hay)
        pendiente = bool(self._res.get('pendiente_resolve'))
        if not hay:
            return
        if pendiente:
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Hay cambios que aún no están en Resolve'))
        elif self._res.get('puede_aplicar'):
            self._ico_resolve.poner('ok')
            cuando = str(self._res.get('en_resolve') or self._res.get('ultimo_go') or '')[-8:-3]
            self._lbl_resolve.setText(tr('En Resolve y al día') + (f'  ·  {cuando}' if cuando else ''))
        else:
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Haz GO con AI Sound Director encendido para ponerlo en Resolve'))
        for b, t in ((self._b_aplicar, 'primario' if pendiente else 'secundario'), (self._b_redisenar, 'secundario' if pendiente else 'primario')):
            if b.property('tipo') != t:
                b.setProperty('tipo', t)
                b.style().unpolish(b)
                b.style().polish(b)

    def _texto_on(self):
        if self._res.get('activo'):
            return tr('Encendido: en cada GO decide el sonido (voz, sonidos, música y ambiente). Lo de abajo es lo que decidió para este video.')
        return tr('Apagado: GO pone los sonidos de siempre. Enciéndelo para que AI Sound Director diseñe el sonido en el próximo GO.')

    def _pintar_evento(self, e):
        if not e:
            self._lbl_ev.setText(tr('Toca un sonido en la línea de tiempo'))
            self._lbl_diseno.setText('')
            self._lbl_material.setText('')
            self._lbl_porque.setText(tr('Verás qué hizo la IA, por qué, y podrás oírlo, pedir menos o más, regenerarlo, silenciarlo o bloquearlo.'))
            self._lbl_imp.setText('')
            for b in self._botones_ev:
                b.setEnabled(False)
            return
        self._lbl_ev.setText(f"{e.get('nombre')}  ·  {_tiempo(e.get('ancla'))}")
        self._lbl_diseno.setText(tr('Diseño IA: {d}', d=tr(e.get('diseno') or '') + (tr(' + capa a la medida') if e.get('con_capa') else '') +
                                    (tr(' + clic') if e.get('con_clic') else '')))
        fuente = str(e.get('fuente') or '')
        if e.get('material'):
            self._lbl_material.setText(tr('Material: «{m}» de tu biblioteca (pasó el Quality Gate)', m=e.get('material')))
        elif 'procedural' in fuente:
            self._lbl_material.setText(tr('Material: sintetizado a la medida de este movimiento'))
        else:
            self._lbl_material.setText(tr('Material: {f}', f=tr(fuente)) if fuente else '')
        self._lbl_porque.setText(tr('Por qué: {p}', p=e.get('por_que') or ''))
        self._lbl_imp.setText(tr('Importancia: {n} %', n=int(round(100 * float(e.get('importancia') or 0)))) +
                              ('   ·   ' + tr('Bloqueado') if e.get('bloqueado') else '') + ('   ·   ' + tr('Silenciado por ti') if e.get('silenciado') else ''))
        self._b_silencio.setText(tr('Que suene') if e.get('silenciado') else tr('Silenciar'))
        self._b_bloq.setText(tr('Desbloquear') if e.get('bloqueado') else tr('Bloquear'))
        for b in self._botones_ev:
            b.setEnabled(not self._ocupado)
        bloq = bool(e.get('bloqueado'))
        for b in (self._b_menos, self._b_mas, self._b_regen):
            b.setEnabled(not self._ocupado and not bloq and not e.get('silenciado'))
        self._b_oir_ev.setEnabled(not self._ocupado and bool(e.get('suena')))

    def _estado(self, texto):
        self._lbl_estado.setText(str(texto))

    def _desglose(self):
        """El Sound Score parte por parte (cada número sale de una medida de la mezcla)."""
        partes = self._res.get('score_partes') or {}
        if not partes:
            self._estado(tr('El Sound Score se mide con la mezcla completa en el próximo GO.'))
            return
        nombres = {'voz': 'voz', 'ruido': 'ruido', 'sincronia': 'sincronía', 'musica': 'música', 'consistencia': 'consistencia', 'proteccion': 'protección de la voz',
                   'mezcla': 'mezcla final'}
        self._estado(tr('Sound Score {s}: ', s=self._res.get('sound_score')) + ' · '.join(
            f"{tr(nombres.get(k, k))} {v.get('puntos')}" for k, v in partes.items()))

    def _offset(self):
        try:
            return self._offset_fn()
        except Exception:
            return 0

    def _trabajar(self, texto, trabajo, al_terminar=None, a_resolve=False):
        """Un trabajo largo en su hilo; la página queda quieta (botones apagados) hasta que vuelve. `a_resolve`: lo cambiado va al timeline en el
        mismo hilo (director_sonido_sesion.aplicar_al_momento: si Resolve está abierto y el último GO fue con el director)."""
        if self._ocupado:
            return
        self._ocupado = True
        for b in self._acciones:
            b.setEnabled(False)
        self._estado(texto)
        en_resolve = {}
        if a_resolve:
            import director_sonido_sesion as S
            v, off, base = self._video_mostrado(), self._offset(), trabajo

            def trabajo():
                r = base()
                ok, msg = S.aplicar_al_momento(v, off)
                en_resolve.update(ok=ok, msg=msg)
                return S.resumen(v) if ok and isinstance(r, dict) else r

        def fin(r, err):
            self._ocupado = False
            for b in self._acciones:
                b.setEnabled(True)
            if err is not None:
                self._estado(tr('No se pudo: {e}', e=err))
                self._pintar(self._res)
                return
            if al_terminar:
                al_terminar(r)
            else:
                self._pintar(r)
            if en_resolve.get('ok') is True:
                self._estado(self._lbl_estado.text() + '  ' + tr('Ya está en Resolve.'))
            elif en_resolve.get('ok') is False:
                self._estado(self._lbl_estado.text() + '  ' + tr('No se pudo poner en Resolve: {m}', m=str(en_resolve.get('msg'))[:140]))
            elif en_resolve.get('msg'):
                self._estado(self._lbl_estado.text() + '  ' + tr(en_resolve['msg']))
        ui.correr_en_hilo(self, trabajo, fin)

    # ---------------------------------------------------------------- acciones
    def _cambio_on(self):
        import director_sonido_sesion as S
        si = bool(self._var_on.get())
        if self._pintando:
            return
        ui.correr_en_hilo(self, lambda: S.poner_activo(si), lambda r, e: (self._res.update(activo=bool(r)), self._estado(self._texto_on())))

    def _cambio_control(self, clave, etiqueta):
        if self._pintando:
            return
        import director_sonido_sesion as S
        valor = next((v for v, t in OPCIONES[clave] if tr(t) == etiqueta), 'auto')
        v = self._video_mostrado()

        def trabajo():
            S.poner_control(clave, valor)
            return S._rehacer(v, capas=clave in ('musica', 'ambiente')) if self._res.get('hay') else S.resumen(v)
        self._trabajar(tr('Rediseñando con «{c}: {v}»…', c=tr(TITULO_CONTROL[clave]), v=etiqueta), trabajo,
                       lambda r: (self._pintar(r), self._estado(tr('Hecho: {c} en «{v}».', c=tr(TITULO_CONTROL[clave]), v=etiqueta))),
                       a_resolve=bool(self._res.get('hay')))

    def _elegir(self, e):
        self._ev = e
        self._pintar_evento(e)

    def _menu(self, cual):
        import director_sonido_sesion as S
        if not self._ev:
            return
        m = Menu(self)
        for op, texto in (S.MENOS if cual == 'menos' else S.MAS):
            m.agregar(tr(texto), lambda op=op: self._retocar(f'{cual}:{op}'))
        b = self._b_menos if cual == 'menos' else self._b_mas
        m.mostrar(b.mapToGlobal(b.rect().bottomLeft()))

    def _retocar(self, accion):
        import director_sonido_sesion as S
        if not self._ev:
            return
        v, clave = self._video_mostrado(), self._ev.get('clave')
        res = {}

        def trabajo():
            r, hecho = S.retocar(v, clave, accion)
            res['hecho'] = hecho
            return r
        self._trabajar(tr('Rehaciendo solo este sonido…'), trabajo, lambda r: (self._pintar(r), self._estado(tr(res.get('hecho') or 'Hecho.'))),
                       a_resolve=True)

    def _redisenar(self):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        self._trabajar(tr('Rediseñando el sonido (lo bloqueado se queda)…'), lambda: S.redisenar(v),
                       lambda r: (self._pintar(r), self._estado(tr('Rediseñado: otras variaciones, mismas decisiones de fondo.'))), a_resolve=True)

    def _deshacer(self):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        self._trabajar(tr('Volviendo a lo que decidió la IA…'), lambda: S.deshacer_todo(v),
                       lambda r: (self._pintar(r), self._estado(tr('Todo como lo decidió la IA (controles en Auto, sin retoques).'))), a_resolve=True)

    def _aplicar(self):
        import director_sonido_sesion as S
        v, off = self._video_mostrado(), self._offset()

        def trabajo():
            ok, msg = S.aplicar(v, offset_frames=off)
            return ok, msg, (S.resumen(v) if ok else None)

        def fin(r):
            ok, msg, nuevo = r or (False, '', None)
            self._pintar(nuevo or self._res)
            self._estado(tr('Puesto en Resolve: sonidos, música, ambiente y voz del director; los de siempre, apagados.') if ok
                         else tr('No se pudo poner en Resolve: {m}', m=str(msg)[:160]))
        self._trabajar(tr('Poniendo el sonido en Resolve…'), trabajo, fin)

    def _oir(self, cual):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        t0 = max(0.0, self._linea.cursor() - 2.0)

        def trabajo():
            ruta = S.previa(v, cual, t0, t0 + 15.0)
            S.reproducir(ruta)
            return ruta
        etiqueta = tr('Original') if cual == 'original' else tr('AI Sound')
        self._trabajar(tr('Preparando «{c}»…', c=etiqueta), trabajo,
                       lambda _r: (self._pintar(self._res), self._estado(tr('Sonando «{c}» desde {t} (15 s).', c=etiqueta, t=_tiempo(t0)))))

    def _oir_evento(self):
        import director_sonido_sesion as S
        if not self._ev:
            return
        v = self._video_mostrado()
        t0 = max(0.0, float(self._ev.get('ancla') or 0.0) - 2.0)
        self._trabajar(tr('Preparando este momento…'), lambda: (S.reproducir(S.previa(v, 'ai', t0, t0 + 4.5)), None)[1],
                       lambda _r: (self._pintar(self._res), self._estado(tr('Sonando este momento con AI Sound.'))))

    def _parar(self):
        import director_sonido_sesion as S
        S.detener()
        self._estado(tr('Parado.'))

    def _frase(self):
        import director_sonido_sesion as S
        texto = str(self._var_frase.get() or '').strip()
        if not texto:
            return
        r = S.interpretar(texto, self._res.get('duracion'))
        if not r['acciones']:
            self._estado(tr('No lo entendí. Prueba con: «menos sonidos», «la voz más clara», «más cinematográfico», «quita el sonido de …», «rediseña el final».'))
            return
        v = self._video_mostrado()
        entendido = ', '.join(r['entendido'])
        self._var_frase.set('')
        self._trabajar(tr('Entendido: {q}…', q=entendido), lambda: S.ejecutar(v, r['acciones'])[0],
                       lambda res: (self._pintar(res), self._estado(tr('Hecho: {q}.', q=entendido))), a_resolve=True)

    def hideEvent(self, e):
        try:
            import director_sonido_sesion as S
            S.detener()
        except Exception:
            pass
        super().hideEvent(e)
