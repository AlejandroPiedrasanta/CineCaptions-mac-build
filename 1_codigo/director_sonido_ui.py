# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_ui.py — la página SONIDO = «AI Sound Director» (fase 6): la IA hace el 95 % del sonido; el usuario lo dirige (5 %).
"""
Al pulsar SONIDO se abre esta página directamente (la de antes —Simple / Emojis / Edición PRO— ya no se ve; su código sigue como motor interno).
Nada técnico a la vista (ni EQ, ni compresores, ni dB): lo que la IA hizo, por qué, y pocas maneras de pedirle otra cosa.

    cabecera     AI Sound Director, video visible, interruptor y Sound Score secundario
    trabajo      A/B del tramo elegido, línea y lista de eventos; inspector al lado o debajo según el ancho
    cambios      Se guardan en el diseño; solo «Aplicar a Resolve» modifica el timeline
    dirección    Una frase, seis controles compactos y creación/restauración de versiones
    diagnóstico Voz, ruido, música, ambiente, motions, mezcla, master y material, plegados de inicio

Todo lo que cuesta (leer el estado, rediseñar, mezclas A/B, Resolve) va por correr_en_hilo; sin globos ni avisos flotantes: una línea de estado.
El motor: director_sonido_sesion.
"""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
from qt_kit import Boton, Combo, Entrada, Etiqueta, IconoEstado, Interruptor, Menu, StringVar, Tarjeta, caja_h
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
        self.setFixedSize(72, 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr('Ver desglose del Sound Score'))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clic.emit()
            e.accept()
        else:
            super().keyPressEvent(e)

    def poner(self, v):
        self._v = None if v is None else int(round(float(v)))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / 88.0, self.height() / 88.0)
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
        self._cargando = False
        self._mensaje_estado = ''
        self._ancho_distribuido = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(12)
        # ---- cabecera
        cab = Tarjeta(espacio=12, margenes=(20, 14, 20, 14), horizontal=True)
        col = QVBoxLayout()
        col.setSpacing(3)
        fila, cf = caja_h(espacio=14)
        cf.addWidget(Etiqueta(tr('AI Sound Director'), 20, peso='negrita', color='#FFFFFF'))
        cf.addStretch(1)
        self._var_on = ui.BooleanVar(False)
        self._sw = Interruptor(tr('Activado'), self._var_on, self._cambio_on, tam=13, color='#E0EBFB')
        cf.addWidget(self._sw)
        col.addWidget(fila)
        self._lbl_video = ui.Elidida(tr('Tu diseño de sonido'), 16, peso='medio', color='#FFFFFF')
        col.addWidget(self._lbl_video)
        self._lbl_tema = ui.Elidida('', 12, color='#B4C0D6')
        col.addWidget(self._lbl_tema)
        self._lbl_estado = Etiqueta(tr('Abre esta página después de GO para dirigir el sonido.'), 12, color=TEXT_MUTED, envolver=True)
        col.addWidget(self._lbl_estado)
        cab.capa.addLayout(col, 1)
        score_col = QVBoxLayout()
        score_col.setSpacing(0)
        self._score = Puntuacion()
        self._score.clic.connect(self._desglose)
        score_col.addWidget(self._score, 0, Qt.AlignmentFlag.AlignHCenter)
        self._lbl_score = Etiqueta('', 10, color=TEXT_MUTED)
        self._lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_col.addWidget(self._lbl_score)
        cab.capa.addLayout(score_col)
        capa.addWidget(cab)
        # ---- vacío (sin GO con el director todavía)
        self._vacio = Tarjeta(espacio=8, margenes=(22, 18, 22, 18))
        self._lbl_vacio = Etiqueta(tr('Activa AI Sound Director y haz GO con un video. Aquí aparecerán su línea de sonido y los eventos para ajustar.'),
                                  14, color='#E0EBFB', envolver=True)
        self._vacio.capa.addWidget(self._lbl_vacio)
        capa.addWidget(self._vacio)
        # ---- el resto (solo con diseño)
        self._cuerpo = QWidget()
        cc = QVBoxLayout(self._cuerpo)
        cc.setContentsMargins(0, 0, 0, 0)
        cc.setSpacing(12)
        # ---- el trabajo principal aparece antes de los controles y del diagnóstico
        zona = QWidget()
        self._zona_layout = QGridLayout(zona)
        self._zona_layout.setContentsMargins(0, 0, 0, 0)
        self._zona_layout.setSpacing(12)
        self._tarjeta_linea = lt = Tarjeta(espacio=8, margenes=(18, 14, 18, 14))
        fila, cf = caja_h(espacio=10)
        cf.addWidget(Etiqueta(tr('Línea de sonido'), 15, peso='medio', color='#FFFFFF'), 1)
        self._b_aplicar = Boton(tr('Aplicar a Resolve'), self._aplicar, alto=36, tam=13)
        self._b_aplicar.setToolTip(tr('Envía a Resolve los cambios pendientes de este diseño.'))
        cf.addWidget(self._b_aplicar)
        lt.capa.addWidget(fila)
        self._fila_resolve, cr = caja_h(espacio=8)
        self._ico_resolve = IconoEstado('ok')
        cr.addWidget(self._ico_resolve)
        self._lbl_resolve = Etiqueta('', 12, peso='medio', color='#E0EBFB', envolver=True)
        cr.addWidget(self._lbl_resolve, 1)
        lt.capa.addWidget(self._fila_resolve)
        self._lbl_destino = ui.Elidida('', 11, color=TEXT_MUTED)
        lt.capa.addWidget(self._lbl_destino)
        acc, ca = caja_h(espacio=8)
        self._b_orig = Boton(tr('▶  Original'), lambda: self._oir('original'), tipo='fantasma', alto=32, tam=12)
        self._b_ai = Boton(tr('▶  AI Sound'), lambda: self._oir('ai'), alto=32, tam=12)
        self._b_parar = Boton(tr('■'), self._parar, tipo='fantasma', alto=32, ancho=36, tam=12, tooltip=tr('Detener previa'))
        self._b_parar.setAccessibleName(tr('Detener previa'))
        for b in (self._b_orig, self._b_ai, self._b_parar):
            ca.addWidget(b)
        ca.addStretch(1)
        lt.capa.addWidget(acc)
        self._lbl_tramo = Etiqueta('', 11, color=TEXT_MUTED)
        lt.capa.addWidget(self._lbl_tramo)
        self._linea = LineaSonido()
        self._linea.elegido.connect(self._elegir)
        self._linea.setAccessibleName(tr('Línea de sonido. Usa la lista de eventos para seleccionar con el teclado.'))
        lt.capa.addWidget(self._linea)
        self._lbl_eventos = Etiqueta('', 12, peso='medio', color='#B4C0D6')
        lt.capa.addWidget(self._lbl_eventos)
        self._lista_eventos = QListWidget()
        self._lista_eventos.setFont(ui.fuente(12))
        self._lista_eventos.setFixedHeight(100)
        self._lista_eventos.setMinimumWidth(0)
        self._lista_eventos.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._lista_eventos.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._lista_eventos.setAccessibleName(tr('Eventos de sonido. Flechas para elegir y Enter para oír el momento.'))
        self._lista_eventos.currentItemChanged.connect(self._evento_de_lista)
        self._lista_eventos.itemActivated.connect(lambda _item: self._oir_evento())
        lt.capa.addWidget(self._lista_eventos)
        self._tarjeta_inspector = ins = Tarjeta(espacio=8, margenes=(18, 16, 18, 16))
        ins.capa.addWidget(Etiqueta(tr('Inspector de sonido'), 13, peso='medio', color=TEXT_MUTED))
        self._lbl_ev = Etiqueta('', 16, peso='medio', color='#FFFFFF', envolver=True)
        self._lbl_diseno = Etiqueta('', 13, color=ui.ACCENT_CLARO, envolver=True)
        self._lbl_material = ui.Elidida('', 12, color='#B4C0D6')
        self._lbl_porque = Etiqueta('', 12, color='#B4C0D6', envolver=True)
        self._lbl_imp = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        for w in (self._lbl_ev, self._lbl_diseno, self._lbl_material, self._lbl_porque, self._lbl_imp):
            w.setMinimumWidth(0)
            w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            ins.capa.addWidget(w)
        cb = QGridLayout()
        cb.setSpacing(8)
        self._b_oir_ev = Boton(tr('▶  Oír'), self._oir_evento, tipo='fantasma', alto=32, tam=12)
        self._b_menos = Boton(tr('Menos…'), lambda: self._menu('menos'), alto=32, tam=12)
        self._b_mas = Boton(tr('Más…'), lambda: self._menu('mas'), alto=32, tam=12)
        self._b_regen = Boton(tr('Regenerar'), lambda: self._retocar('regenerar'), alto=32, tam=12)
        self._b_silencio = Boton(tr('Silenciar'), lambda: self._retocar('silenciar'), tipo='fantasma', alto=32, tam=12)
        self._b_bloq = Boton(tr('Bloquear'), lambda: self._retocar('bloquear'), tipo='fantasma', alto=32, tam=12)
        for i, b in enumerate((self._b_menos, self._b_mas, self._b_regen, self._b_oir_ev, self._b_silencio, self._b_bloq)):
            cb.addWidget(b, i // 2, i % 2)
        ins.capa.addLayout(cb)
        ins.capa.addStretch(1)
        self._botones_ev = (self._b_oir_ev, self._b_menos, self._b_mas, self._b_regen, self._b_silencio, self._b_bloq)
        self._zona_layout.addWidget(lt, 0, 0)
        self._zona_layout.addWidget(ins, 1, 0)
        cc.addWidget(zona)
        # «dile a AI Sound Director»
        dile = Tarjeta(espacio=8, margenes=(18, 12, 18, 12))
        fd, cdl = caja_h(espacio=10)
        self._var_frase = StringVar('')
        self._entrada = Entrada(self._var_frase, placeholder=tr('Dile a AI Sound Director qué quieres cambiar…  («menos sonidos», «la voz más clara», «rediseña el final»)'),
                                alto=38, tam=13)
        self._entrada.returnPressed.connect(self._frase)
        cdl.addWidget(self._entrada, 1)
        self._b_enviar = Boton(tr('Enviar'), self._frase, alto=38, tam=13)
        cdl.addWidget(self._b_enviar)
        dile.capa.addWidget(fd)
        cc.addWidget(dile)
        # Controles de la misma biblioteca visual del resto de CineCaptions.
        ctl = Tarjeta(espacio=10, margenes=(18, 14, 18, 14))
        ctl.capa.addWidget(Etiqueta(tr('Dirige el sonido'), 15, peso='medio', color='#FFFFFF'))
        ctl.capa.addWidget(Etiqueta(tr('Para este diseño y próximos GO · En Auto decide la IA'), 11, color=TEXT_MUTED, envolver=True))
        self._controles_layout = QGridLayout()
        self._controles_layout.setHorizontalSpacing(16)
        self._controles_layout.setVerticalSpacing(10)
        self._vars, self._controles, self._grupos_control = {}, {}, []
        for k in OPCIONES:
            grupo = QWidget()
            g = QVBoxLayout(grupo)
            g.setContentsMargins(0, 0, 0, 0)
            g.setSpacing(4)
            g.addWidget(Etiqueta(tr(TITULO_CONTROL[k]), 12, color=TEXT_MUTED))
            self._vars[k] = StringVar(tr('Auto'))
            control = Combo([tr(t) for _v, t in OPCIONES[k]], self._vars[k], lambda etiqueta, k=k: self._cambio_control(k, etiqueta), alto=32, tam=12)
            control.setAccessibleName(tr(TITULO_CONTROL[k]))
            g.addWidget(control)
            self._controles[k] = control
            self._grupos_control.append(grupo)
        ctl.capa.addLayout(self._controles_layout)
        acciones, ca = caja_h(espacio=8)
        self._b_redisenar = Boton(tr('Crear otra versión'), self._redisenar, alto=34, tam=12)
        self._b_redisenar.setToolTip(tr('Crea otras variaciones y conserva los sonidos bloqueados.'))
        self._b_deshacer = Boton(tr('Restaurar diseño IA'), self._deshacer, tipo='fantasma', alto=34, tam=12)
        self._b_deshacer.setToolTip(tr('Quita los retoques y devuelve los controles a Auto, también para próximos GO.'))
        ca.addWidget(self._b_redisenar)
        ca.addWidget(self._b_deshacer)
        ca.addStretch(1)
        ctl.capa.addWidget(acciones)
        cc.addWidget(ctl)
        # El diagnóstico conserva las ocho notas originales, sin desplazar el trabajo.
        est = Tarjeta(espacio=10, margenes=(18, 10, 18, 10))
        self._b_diagnostico = Boton(tr('Ver diagnóstico de la IA'), self._alternar_diagnostico, tipo='fantasma', alto=32, tam=13)
        self._b_diagnostico.setCheckable(True)
        est.capa.addWidget(self._b_diagnostico)
        self._diagnostico = QWidget()
        self._diagnostico_layout = QGridLayout(self._diagnostico)
        self._diagnostico_layout.setContentsMargins(0, 4, 0, 6)
        self._diagnostico_layout.setHorizontalSpacing(24)
        self._diagnostico_layout.setVerticalSpacing(12)
        self._filas = {}
        for i, k in enumerate(('voz', 'ruido', 'musica', 'ambiente', 'motion', 'mezcla', 'master', 'material')):
            self._filas[k] = FilaEstado()
            self._diagnostico_layout.addWidget(self._filas[k], i // 2, i % 2)
        est.capa.addWidget(self._diagnostico)
        self._diagnostico.hide()
        cc.addWidget(est)
        capa.addWidget(self._cuerpo)
        capa.addStretch(1)                                           # (el sobrante, abajo: las tarjetas con su alto natural)
        self._acciones = (self._b_orig, self._b_ai, self._b_parar, self._b_redisenar, self._b_aplicar, self._b_deshacer) + self._botones_ev
        self._distribuir()
        self._pintar_evento(None)
        self._cuerpo.hide()
        self._actualizar_disponibles()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._distribuir()

    def _distribuir(self):
        """Solo redistribuye widgets de esta página; no modifica el marco de la aplicación."""
        ancho = self.width()
        modo = (ancho >= 1000, 3 if ancho >= 740 else (2 if ancho >= 480 else 1), 2 if ancho >= 680 else 1)
        if self._ancho_distribuido == modo:
            return
        self._ancho_distribuido = modo
        lateral, columnas, columnas_notas = modo
        for w in (self._tarjeta_linea, self._tarjeta_inspector):
            self._zona_layout.removeWidget(w)
        self._zona_layout.addWidget(self._tarjeta_linea, 0, 0)
        self._zona_layout.addWidget(self._tarjeta_inspector, 0 if lateral else 1, 1 if lateral else 0)
        self._zona_layout.setColumnStretch(0, 3 if lateral else 1)
        self._zona_layout.setColumnStretch(1, 2 if lateral else 0)
        for w in self._grupos_control:
            self._controles_layout.removeWidget(w)
        for c in range(3):
            self._controles_layout.setColumnStretch(c, 1 if c < columnas else 0)
        for i, w in enumerate(self._grupos_control):
            self._controles_layout.addWidget(w, i // columnas, i % columnas)
        for w in self._filas.values():
            self._diagnostico_layout.removeWidget(w)
        for i, w in enumerate(self._filas.values()):
            self._diagnostico_layout.addWidget(w, i // columnas_notas, i % columnas_notas)

    def _alternar_diagnostico(self):
        abierto = self._b_diagnostico.isChecked()
        self._diagnostico.setVisible(abierto)
        self._b_diagnostico.setText(tr('Ocultar diagnóstico de la IA') if abierto else tr('Ver diagnóstico de la IA'))

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
        if self._ocupado or self._cargando:
            return
        import director_sonido_sesion as S
        v = self.video()
        self._cargando = True
        self._estado(tr('Leyendo el diseño de sonido…'))
        if not self._res.get('hay'):
            self._lbl_vacio.setText(tr('Cargando el diseño de sonido del video…'))
            self._vacio.show()
        self._actualizar_disponibles()
        ui.correr_en_hilo(self, lambda: S.resumen(v), self._al_resumen)

    def _al_resumen(self, res, err):
        self._cargando = False
        if err is not None:
            if not self._res.get('hay'):
                self._lbl_vacio.setText(tr('No se pudo cargar el diseño. Vuelve a abrir Sonido para reintentar.'))
            self._estado(tr('No pude leer el diseño de sonido: {e}', e=err))
            self._actualizar_disponibles()
            return
        self._mensaje_estado = ''
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
        self._lbl_estado.setText(self._mensaje_estado or self._texto_on())
        if not hay:
            self._ev = None
            self._linea.poner({})
            self._lbl_video.setText(tr('Tu diseño de sonido'))
            self._lbl_tema.setText(tr('La IA diseña el sonido en GO; aquí lo diriges.'))
            self._lbl_vacio.setText(tr(self._res.get('motivo') or 'Activa AI Sound Director y haz GO con un video para empezar.'))
            self._score.poner(None)
            self._lbl_score.setText('')
            self._actualizar_disponibles()
            return
        estilo = self._res.get('estilo_usuario')
        sonic = self._res.get('sonic_style') or ''
        if estilo:
            sonic = tr(dict(OPCIONES['estilo']).get(estilo, estilo)) + ' ' + tr('(elegido por ti)')
        nombre = self._res.get('nombre_video') or self._res.get('video') or tr('Video sin nombre')
        self._lbl_video.setText(tr('{v} · último diseño de GO', v=nombre) if self._res.get('otro_video') else str(nombre))
        self._lbl_video.setToolTip(str(self._res.get('video') or nombre))
        self._lbl_tema.setText(tr('Tema: {t}', t=self._res.get('tema') or '—') + '   ·   ' + tr('AI Sonic Style: {s}', s=sonic or '—'))
        viejo = bool(self._res.get('sound_score_viejo'))
        self._score.poner(None if viejo else self._res.get('sound_score'))
        self._lbl_score.setText(tr('Medición pendiente') if viejo else '')
        self._score.setToolTip(tr('La mezcla cambió. El score anterior era {s}; vuelve a medirse en GO.', s=self._res.get('sound_score') or '—')
                               if viejo else tr('Ver desglose del Sound Score'))
        for n in self._res.get('notas') or []:
            if n.get('clave') in self._filas:
                self._filas[n['clave']].poner(n)
        self._pintar_resolve()
        sel = (self._ev or {}).get('clave')
        self._ev = next((e for e in self._res.get('eventos') or [] if e.get('clave') == sel), None)
        self._linea.poner(self._res, sel if self._ev else None)
        self._llenar_eventos()
        self._pintar_evento(self._ev)
        self._pintar_tramo()
        self._actualizar_disponibles()

    def _pintar_resolve(self):
        """Al día en Resolve (y desde cuándo) o con cambios sin poner; con cambios, «Aplicar a Resolve» pasa a ser el botón principal."""
        hay = bool(self._res.get('hay'))
        self._fila_resolve.setVisible(hay)
        pendiente = bool(self._res.get('pendiente_resolve'))
        if not hay:
            return
        if pendiente:
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Cambios pendientes · pulsa Aplicar a Resolve'))
        elif self._res.get('puede_aplicar') and self._res.get('en_resolve'):
            self._ico_resolve.poner('ok')
            cuando = str(self._res.get('en_resolve') or '')[-8:-3]
            self._lbl_resolve.setText(tr('En Resolve y al día') + (f'  ·  {cuando}' if cuando else ''))
        elif self._res.get('puede_aplicar'):
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Listo para aplicar · envío a Resolve sin confirmar'))
        else:
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Haz GO con AI Sound Director encendido para ponerlo en Resolve'))
        destino = self._res.get('destino') or self._res.get('destination') or {}
        if isinstance(destino, dict):
            destino = ' · '.join(str(destino[k]) for k in ('proyecto', 'timeline') if destino.get(k))
        self._lbl_destino.setText(tr('Destino: {d}', d=destino) if destino else '')
        self._lbl_destino.setVisible(bool(destino))
        for b, t in ((self._b_aplicar, 'primario' if pendiente else 'secundario'),):
            if b.property('tipo') != t:
                b.setProperty('tipo', t)
                b.style().unpolish(b)
                b.style().polish(b)

    def _texto_on(self):
        if self._res.get('activo'):
            return tr('Activo en próximos GO. Los ajustes se guardan aquí; Aplicar a Resolve los envía al timeline.')
        return tr('Desactivado en próximos GO. Puedes seguir ajustando el diseño que ya existe.')

    def _llenar_eventos(self):
        seleccion = (self._ev or {}).get('clave')
        self._lista_eventos.blockSignals(True)
        try:
            self._lista_eventos.clear()
            eventos = [e for e in self._res.get('eventos') or [] if e.get('suena') or e.get('silenciado')]
            for e in sorted(eventos, key=lambda e: float(e.get('ancla') or 0)):
                estado = (' · ' + tr('Silenciado') if e.get('silenciado') else '') + (' · ' + tr('Bloqueado') if e.get('bloqueado') else '')
                item = QListWidgetItem(f"{_tiempo(e.get('ancla'))}   {e.get('nombre') or tr('Sonido')}{estado}")
                item.setData(Qt.ItemDataRole.UserRole, e.get('clave'))
                item.setToolTip(item.text())
                self._lista_eventos.addItem(item)
                if e.get('clave') == seleccion:
                    self._lista_eventos.setCurrentItem(item)
            if not eventos:
                item = QListWidgetItem(tr('Este diseño no tiene eventos de sonido IA.'))
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self._lista_eventos.addItem(item)
            self._lbl_eventos.setText(tr('Eventos · {n} · elige con clic o con las flechas', n=len(eventos)))
        finally:
            self._lista_eventos.blockSignals(False)

    def _evento_de_lista(self, item, _anterior):
        if item is None or self._ocupado or self._cargando:
            return
        clave = item.data(Qt.ItemDataRole.UserRole)
        evento = next((e for e in self._res.get('eventos') or [] if e.get('clave') == clave), None)
        self._elegir(evento)

    def _tramo(self, segundos=15.0, ancla=None):
        dur = max(0.0, float(self._res.get('duracion') or 0.0))
        cursor = self._linea.cursor() if ancla is None else float(ancla or 0.0)
        inicio = max(0.0, min(dur, cursor) - 2.0)
        return inicio, min(dur, inicio + segundos)

    def _pintar_tramo(self):
        inicio, fin = self._tramo()
        self._lbl_tramo.setText(tr('Comparar tramo {a} – {b} · clic en la línea para moverlo', a=_tiempo(inicio), b=_tiempo(fin)))

    def _actualizar_disponibles(self):
        libre = not (self._ocupado or self._cargando)
        hay = bool(self._res.get('hay'))
        for b in self._acciones:
            b.setEnabled(libre and hay)
        self._b_aplicar.setEnabled(libre and hay and bool(self._res.get('puede_aplicar')))
        for w in (self._entrada, self._b_enviar, self._linea, self._lista_eventos):
            w.setEnabled(libre and hay)
        self._sw.setEnabled(libre)
        for w in self._controles.values():
            w.setEnabled(libre and hay)
        self._pintar_evento(self._ev)

    def _pintar_evento(self, e):
        if not e:
            self._lbl_ev.setText(tr('Selecciona un sonido'))
            self._lbl_diseno.setText('')
            self._lbl_material.setText('')
            self._lbl_porque.setText(tr('Elige un evento en la línea o en la lista. Aquí podrás escuchar el momento y ajustar lo que decidió la IA.'))
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
        libre = not (self._ocupado or self._cargando)
        for b in self._botones_ev:
            b.setEnabled(libre)
        bloq = bool(e.get('bloqueado'))
        for b in (self._b_menos, self._b_mas, self._b_regen):
            b.setEnabled(libre and not bloq and not e.get('silenciado'))
        self._b_oir_ev.setEnabled(libre and bool(e.get('suena')))

    def _estado(self, texto):
        self._mensaje_estado = str(texto)
        self._lbl_estado.setText(self._mensaje_estado)

    def _desglose(self):
        """El Sound Score parte por parte (cada número sale de una medida de la mezcla)."""
        partes = self._res.get('score_partes') or {}
        if not partes:
            self._estado(tr('El Sound Score se mide con la mezcla completa en el próximo GO.'))
            return
        nombres = {'voz': 'voz', 'ruido': 'ruido', 'sincronia': 'sincronía', 'musica': 'música', 'consistencia': 'consistencia', 'proteccion': 'protección de la voz',
                   'mezcla': 'mezcla final'}
        prefijo = tr('Medición anterior · ') if self._res.get('sound_score_viejo') else ''
        self._estado(prefijo + tr('Sound Score {s}: ', s=self._res.get('sound_score')) + ' · '.join(
            f"{tr(nombres.get(k, k))} {v.get('puntos')}" for k, v in partes.items()))

    def _offset(self):
        try:
            return self._offset_fn()
        except Exception:
            return 0

    def _trabajar(self, texto, trabajo, al_terminar=None):
        """Acepta un único trabajo y conserva los errores al repintar. Solo _aplicar envía a Resolve."""
        if self._ocupado or self._cargando:
            return False
        self._ocupado = True
        self._actualizar_disponibles()
        self._estado(texto)

        def fin(r, err):
            self._ocupado = False
            if err is not None:
                self._pintar(self._res)
                self._estado(tr('No se pudo: {e}', e=err))
                self._actualizar_disponibles()
                return
            if al_terminar:
                al_terminar(r)
            else:
                self._pintar(r)
            self._actualizar_disponibles()
        try:
            ui.correr_en_hilo(self, trabajo, fin)
        except Exception as err:
            self._ocupado = False
            self._actualizar_disponibles()
            self._estado(tr('No se pudo iniciar: {e}', e=err))
            return False
        return True

    # ---------------------------------------------------------------- acciones
    def _cambio_on(self):
        import director_sonido_sesion as S
        si = bool(self._var_on.get())
        if self._pintando:
            return
        if self._ocupado or self._cargando:
            self._var_on.set(bool(self._res.get('activo')))
            return
        v = self._video_mostrado()

        def trabajo():
            S.poner_activo(si)
            return S.resumen(v)
        self._trabajar(tr('Guardando la activación del director…'), trabajo,
                       lambda r: (self._pintar(r), self._estado(self._texto_on())))

    def _cambio_control(self, clave, etiqueta):
        if self._pintando:
            return
        if self._ocupado or self._cargando:
            self._pintar(self._res)
            return
        import director_sonido_sesion as S
        valor = next((v for v, t in OPCIONES[clave] if tr(t) == etiqueta), 'auto')
        v = self._video_mostrado()

        def trabajo():
            S.poner_control(clave, valor)
            return S._rehacer(v, capas=clave in ('musica', 'ambiente')) if self._res.get('hay') else S.resumen(v)
        self._trabajar(tr('Rediseñando con «{c}: {v}»…', c=tr(TITULO_CONTROL[clave]), v=etiqueta), trabajo,
                       lambda r: (self._pintar(r), self._estado(tr('Guardado: {c} en «{v}». Aplica los cambios cuando termines.', c=tr(TITULO_CONTROL[clave]), v=etiqueta))))

    def _elegir(self, e):
        if self._ocupado or self._cargando:
            return
        self._ev = e
        if e:
            self._linea._cursor = max(0.0, float(e.get('ancla') or 0.0))
        clave = (e or {}).get('clave')
        self._linea.poner(self._res, clave)
        self._lista_eventos.blockSignals(True)
        try:
            if e is None:
                self._lista_eventos.clearSelection()
                self._lista_eventos.setCurrentRow(-1)
            else:
                for i in range(self._lista_eventos.count()):
                    item = self._lista_eventos.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == clave:
                        self._lista_eventos.setCurrentItem(item)
                        self._lista_eventos.scrollToItem(item)
                        break
        finally:
            self._lista_eventos.blockSignals(False)
        self._pintar_evento(e)
        self._pintar_tramo()

    def _menu(self, cual):
        import director_sonido_sesion as S
        if not self._ev or self._ocupado or self._cargando:
            return
        m = Menu(self)
        for op, texto in (S.MENOS if cual == 'menos' else S.MAS):
            m.agregar(tr(texto), lambda op=op: self._retocar(f'{cual}:{op}'))
        b = self._b_menos if cual == 'menos' else self._b_mas
        m.mostrar(b.mapToGlobal(b.rect().bottomLeft()))

    def _retocar(self, accion):
        import director_sonido_sesion as S
        if not self._ev or self._ocupado or self._cargando:
            return
        v, clave = self._video_mostrado(), self._ev.get('clave')
        res = {}

        def trabajo():
            r, hecho = S.retocar(v, clave, accion)
            res['hecho'] = hecho
            return r
        self._trabajar(tr('Rehaciendo solo este sonido…'), trabajo, lambda r: (self._pintar(r), self._estado(tr(res.get('hecho') or 'Hecho.'))))

    def _redisenar(self):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        self._trabajar(tr('Rediseñando el sonido (lo bloqueado se queda)…'), lambda: S.redisenar(v),
                       lambda r: (self._pintar(r), self._estado(tr('Nueva versión guardada. Los sonidos bloqueados se conservan.'))))

    def _deshacer(self):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        self._trabajar(tr('Volviendo a lo que decidió la IA…'), lambda: S.deshacer_todo(v),
                       lambda r: (self._pintar(r), self._estado(tr('Diseño IA restaurado: sin retoques y controles en Auto, también para próximos GO.'))))

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
        t0, t1 = self._tramo()
        if t1 <= t0:
            self._estado(tr('Este diseño no tiene un tramo de audio para comparar.'))
            return

        def trabajo():
            ruta = S.previa(v, cual, t0, t1)
            S.reproducir(ruta)
            return ruta
        etiqueta = tr('Original') if cual == 'original' else tr('AI Sound')
        self._trabajar(tr('Preparando «{c}»…', c=etiqueta), trabajo,
                       lambda _r: (self._pintar(self._res), self._estado(tr('Previa «{c}» abierta: {a} – {b}.', c=etiqueta, a=_tiempo(t0), b=_tiempo(t1)))))

    def _oir_evento(self):
        import director_sonido_sesion as S
        if not self._ev or self._ocupado or self._cargando:
            return
        v = self._video_mostrado()
        t0, t1 = self._tramo(4.5, self._ev.get('ancla'))
        if t1 <= t0:
            return
        self._trabajar(tr('Preparando este momento…'), lambda: (S.reproducir(S.previa(v, 'ai', t0, t1)), None)[1],
                       lambda _r: (self._pintar(self._res), self._estado(tr('Previa del momento abierta: {a} – {b}.', a=_tiempo(t0), b=_tiempo(t1)))))

    def _parar(self):
        import director_sonido_sesion as S
        S.detener()
        self._estado(tr('Parado.'))

    def _frase(self):
        import director_sonido_sesion as S
        if self._ocupado or self._cargando:
            return
        texto = str(self._var_frase.get() or '').strip()
        if not texto:
            return
        r = S.interpretar(texto, self._res.get('duracion'))
        if not r['acciones']:
            aclaracion = ', '.join(r.get('entendido') or []) if r.get('requiere_aclaracion') else ''
            self._estado(aclaracion or tr('No lo entendí. Prueba con: «menos sonidos», «la voz más clara», «más cinematográfico», «quita el sonido de …», «rediseña el final».'))
            return
        v = self._video_mostrado()
        entendido = ', '.join(r['entendido'])

        def fin(res):
            self._pintar(res)
            self._var_frase.set('')
            self._estado(tr('Guardado: {q}. Aplica los cambios cuando termines.', q=entendido))
        self._trabajar(tr('Entendido: {q}…', q=entendido), lambda: S.ejecutar(v, r['acciones'])[0], fin)

    def hideEvent(self, e):
        try:
            import director_sonido_sesion as S
            S.detener()
        except Exception:
            pass
        super().hideEvent(e)
