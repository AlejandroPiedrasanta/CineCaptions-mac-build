# CineCaptions · By Cinema Productions
# 1_codigo/efectos_pro_ui.py — v5.20: la página Efectos › «Edición PRO»: una sección por función de la PRO (las del menú lateral de Proyecto) con
# «Automático» y 10 estilos con su ejemplo animado, la fila de colores propios y el interruptor de la función.
"""
El usuario (2026-10-19): «todos los efectos de la edición PRO en la página de Efectos por sección, con varios ejemplos para escoger con su render;
lo que escoja es lo que se aplica si activo esa función, adaptándose al video; y poder personalizar un poco los colores». El catálogo (estilos,
paletas, cómo se aplica) está en estilos_pro.py; aquí solo se elige y se guarda (pro_estilos). El interruptor de cada sección es el MISMO que el
del menú lateral de Proyecto (pro_lateral_ui.estado / poner): encender aquí lo enciende allí y al revés.

Sin cuadros ni globos (pedido del usuario): los colores se eligen en una tira que se abre debajo de la sección, no en un diálogo.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

import estilos_pro as EST
import qt_kit as ui
from i18n import tr
from qt_kit import Boton, Entrada, Etiqueta, Interruptor, StringVar, Tarjeta, caja_h

TEXT_MUTED = ui.TEXT_MUTED
VERDE = ui.VERDE
SIN_POSICION = ('gancho',)          # v5.33: la intro del gancho va siempre en el primer segundo: sin «Posición»


def _marcar(b, si):
    """Una píldora de las tiras de opciones: verde si es la elegida."""
    t = 'primario' if si else 'fantasma'
    if b.property('tipo') != t:
        b.setProperty('tipo', t)
        b.style().unpolish(b)
        b.style().polish(b)


# ====================================================================================== el slider de tarjetas (una fila que se desliza)
class _Flecha(QWidget):
    """Un círculo con una flecha a un lado del slider (solo se ve si hay más tarjetas hacia ese lado)."""
    clic = Signal()

    def __init__(self, lado, padre=None):
        super().__init__(padre)
        self.lado = lado
        self._hover = False
        self.setFixedSize(38, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 235 if self._hover else 205))
        p.setPen(QPen(QColor(0, 0, 0, 60), 1))
        p.drawEllipse(QRectF(1, 1, 36, 36))
        p.setPen(QPen(QColor('#0B1222'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        k = -1 if self.lado < 0 else 1
        camino = QPainterPath()
        camino.moveTo(19 - 3 * k, 12)
        camino.lineTo(19 + 3 * k, 19)
        camino.lineTo(19 - 3 * k, 26)
        p.drawPath(camino)
        p.end()


class SliderCartas(QWidget):
    """Las 11 tarjetas de una sección en UNA fila que se desliza (el usuario: «que sean de slider para que no ocupe mucho espacio»): flechas a
    los lados, arrastrar con el ratón y la rueda horizontal del trackpad. La rueda vertical sigue moviendo la página (no se la queda)."""
    HUECO = 12

    def __init__(self, cartas, padre=None):
        super().__init__(padre)
        self.cartas = list(cartas)
        alto = self.cartas[0].height() if self.cartas else 330
        self.setFixedHeight(alto)
        self._area = QScrollArea(self)
        self._area.setFrameShape(QFrame.Shape.NoFrame)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._area.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
        fila = QWidget()
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(self.HUECO)
        for c in self.cartas:
            capa.addWidget(c)
        fila.setFixedSize(fila.sizeHint())
        self._area.setWidget(fila)
        self._area.viewport().installEventFilter(self)
        for c in self.cartas:                               # (también encima de las tarjetas: el clic sin arrastre la elige)
            c.installEventFilter(self)
        self._barra = self._area.horizontalScrollBar()
        self._barra.valueChanged.connect(self._flechas)
        self._barra.rangeChanged.connect(self._flechas)
        self._anim = QPropertyAnimation(self._barra, b'value', self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._izq, self._der = _Flecha(-1, self), _Flecha(1, self)
        self._izq.clic.connect(lambda: self.mover(-1))
        self._der.clic.connect(lambda: self.mover(1))
        self._arrastre = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._area.setGeometry(0, 0, self.width(), self.height())
        y = int(self.height() * 0.36)
        self._izq.move(6, y)
        self._der.move(self.width() - 44, y)
        self._flechas()

    def _flechas(self, *_):
        v, mx = self._barra.value(), self._barra.maximum()
        self._izq.setVisible(v > 2)
        self._der.setVisible(v < mx - 2)
        self._izq.raise_()
        self._der.raise_()

    def mover(self, sentido):
        paso = (self.cartas[0].width() + self.HUECO) * max(1, int(self.width() * 0.8 // (self.cartas[0].width() + self.HUECO)))
        destino = max(0, min(self._barra.maximum(), self._barra.value() + sentido * paso))
        self._anim.stop()
        self._anim.setStartValue(self._barra.value())
        self._anim.setEndValue(destino)
        self._anim.start()

    def mostrar(self, carta):
        """Lleva al centro la tarjeta elegida (al abrir la sección)."""
        if carta is None:
            return
        x = carta.x() + carta.width() / 2 - self.width() / 2
        self._barra.setValue(int(max(0, min(self._barra.maximum(), x))))

    def eventFilter(self, obj, e):                         # arrastrar con el ratón y la rueda horizontal
        t = e.type()
        if t == e.Type.Wheel:
            d = e.angleDelta()
            if abs(d.x()) > abs(d.y()):
                self._anim.stop()
                self._barra.setValue(self._barra.value() - d.x())
                return True
            return False                                   # (la vertical, para la página)
        carta = obj if obj in self.cartas else None
        if t == e.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = (e.globalPosition().x(), self._barra.value(), False)
            return carta is not None                       # (la tarjeta se elige al soltar, si no se arrastró)
        if t == e.Type.MouseMove and self._arrastre:
            x0, v0, movido = self._arrastre
            dx = e.globalPosition().x() - x0
            if movido or abs(dx) > 6:
                self._anim.stop()
                self._barra.setValue(int(v0 - dx))
                self._arrastre = (x0, v0, True)
                return True
        elif t == e.Type.MouseButtonRelease and self._arrastre:
            movido = self._arrastre[2]
            self._arrastre = None
            if carta is not None and not movido:
                carta.clic.emit(carta.ident)
            return movido or carta is not None
        return False


# ====================================================================================== un color (botón de la fila «Colores»)
class ChipColor(QWidget):
    """«● Fondo» con su color (o el aro punteado de Automático). Clic = abre la tira de colores de ese hueco."""
    clic = Signal(str)

    def __init__(self, hueco, etiqueta, padre=None):
        super().__init__(padre)
        self.hueco = hueco
        self.etiqueta = etiqueta
        self.color = ''
        self.activo = False
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self._ajustar()

    def _ajustar(self):
        from PySide6.QtGui import QFontMetricsF
        texto = f'{self.etiqueta}: {self.color or tr("Automático")}'
        self.setFixedWidth(int(46 + QFontMetricsF(ui.fuente(12)).horizontalAdvance(texto)))

    def poner(self, color, activo=None):
        self.color = color or ''
        if activo is not None:
            self.activo = bool(activo)
        self._ajustar()
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self.hueco)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(QColor('#16233D' if (self.activo or self._hover) else '#101A2E'))
        p.setPen(QPen(QColor(VERDE if self.activo else '#2A3A5C'), 1.6 if self.activo else 1.0))
        p.drawRoundedRect(r, 17, 17)
        c = QRectF(9, 8, 18, 18)
        if self.color:
            p.setBrush(QColor(self.color[:7]))
            p.setPen(QPen(QColor(255, 255, 255, 90), 1))
            p.drawEllipse(c)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#8EA2C6'), 1.4, Qt.PenStyle.DashLine))
            p.drawEllipse(c)
        p.setPen(QColor('#E0EBFB'))
        p.setFont(ui.fuente(12))
        p.drawText(QRectF(34, 0, self.width() - 40, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   f'{self.etiqueta}: {self.color or tr("Automático")}')
        p.end()


class ChipOpcion(ChipColor):
    """v5.33: «🔊 Sonido: El de la intro» / «⤢ Zoom: Golpe seco» en la fila «Personaliza» del gancho, con el mismo aspecto que los de color.
    Clic = abre su tira debajo. `icono` = un icono de Phosphor (en el sitio del círculo de color)."""

    def __init__(self, hueco, etiqueta, icono, padre=None):
        super().__init__(hueco, etiqueta, padre)
        self.nombre = ''
        try:
            self._icono = ui.icono_linea(icono, '#8EA2C6').pixmap(16, 16)
        except Exception:
            self._icono = None

    def _texto(self):
        return f'{self.etiqueta}: {getattr(self, "nombre", "") or tr("El de la intro")}'

    def _ajustar(self):
        from PySide6.QtGui import QFontMetricsF
        self.setFixedWidth(int(46 + QFontMetricsF(ui.fuente(12)).horizontalAdvance(self._texto())))

    def poner(self, nombre, activo=None):
        self.nombre = nombre or ''
        if activo is not None:
            self.activo = bool(activo)
        self._ajustar()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(QColor('#16233D' if (self.activo or self._hover) else '#101A2E'))
        p.setPen(QPen(QColor(VERDE if self.activo else '#2A3A5C'), 1.6 if self.activo else 1.0))
        p.drawRoundedRect(r, 17, 17)
        if self._icono is not None and not self._icono.isNull():
            p.drawPixmap(10, (self.height() - 16) // 2, self._icono)
        else:
            p.setPen(QColor('#8EA2C6'))
            p.setFont(ui.fuente(14, peso='negrita'))
            p.drawText(QRectF(8, 0, 22, self.height()), int(Qt.AlignmentFlag.AlignCenter), '♪' if self.hueco == 'sonido' else '⤢')
        p.setPen(QColor('#E0EBFB'))
        p.setFont(ui.fuente(12))
        p.drawText(QRectF(34, 0, self.width() - 40, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._texto())
        p.end()


class Muestra(QWidget):
    """Un círculo de color de la tira."""
    clic = Signal(str)

    def __init__(self, color, padre=None):
        super().__init__(padre)
        self.color = color
        self.sel = False
        self._hover = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self.color)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = 1.5 if (self._hover or self.sel) else 3.5
        p.setBrush(QColor(self.color))
        p.setPen(QPen(QColor(VERDE) if self.sel else QColor(255, 255, 255, 70), 2.2 if self.sel else 1.0))
        p.drawEllipse(QRectF(k, k, 30 - 2 * k, 30 - 2 * k))
        p.end()


# ====================================================================================== plegar / abrir
class _Cabecera(QWidget):
    """La cabecera de una sección: flecha (abierta / plegada), el título y el estilo que va a usar GO; un clic la abre o la pliega.
    v5.22: el doble clic abre la «Posición» (el clic sencillo espera un instante para no plegar y desplegar en un doble clic)."""
    clic = Signal()
    doble = Signal()

    def __init__(self, titulo, padre=None):
        super().__init__(padre)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self._abierta = False
        self._giro = ui.Resorte(0.0, 420.0, 26.0)
        self.capa = QHBoxLayout(self)
        self.capa.setContentsMargins(30, 0, 0, 0)
        self.capa.setSpacing(12)
        self._titulo = Etiqueta(titulo, 18, peso='medio', color='#FFFFFF')
        self._resumen = Etiqueta('', 13, color='#8EA2C6')
        for w in (self._titulo, self._resumen):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.capa.addWidget(self._titulo)
        self.capa.addWidget(self._resumen)
        self.capa.addStretch(1)

    def poner_resumen(self, texto):
        self._resumen.setText('· ' + texto if texto else '')

    def poner_abierta(self, si):
        self._abierta = bool(si)
        self._giro.objetivo = 1.0 if si else 0.0
        try:
            ui.motor_resortes.pedir(self)
        except Exception:
            self._giro.poner(self._giro.objetivo)
            self.update()

    def paso_resorte(self, dt):
        sigue = self._giro.paso(dt)
        self.update()
        return sigue

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            if getattr(self, '_tras_doble', False):
                self._tras_doble = False
                return
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication
            if getattr(self, '_espera', None) is None:
                self._espera = QTimer(self)
                self._espera.setSingleShot(True)
                self._espera.timeout.connect(self.clic.emit)
            self._espera.start(min(260, QApplication.doubleClickInterval()))

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if getattr(self, '_espera', None) is not None:
                self._espera.stop()
            self._tras_doble = True
            self.doble.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(9, self.height() / 2)
        p.rotate(90.0 * self._giro.x)                       # ▸ plegada · ▾ abierta
        p.setPen(QPen(QColor('#C9D6EC'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        camino = QPainterPath()
        camino.moveTo(-3, -6)
        camino.lineTo(3, 0)
        camino.lineTo(-3, 6)
        p.drawPath(camino)
        p.end()


# ====================================================================================== una sección (una función de la PRO)
class SeccionEstilo(Tarjeta):
    cambio = Signal()

    def __init__(self, seccion, opcion, padre=None):
        super().__init__(padre, espacio=12, margenes=(22, 18, 22, 18))
        from efectos_pagina import TarjetaEfecto
        self.s = seccion
        self.clave = seccion['clave']
        self._hueco = None
        self.capa.setContentsMargins(22, 12, 22, 12)
        # ---- la cabecera: siempre a la vista; un clic la abre o la pliega (el interruptor va aparte)
        self._cab = _Cabecera(tr(seccion['titulo']))
        self._cab.clic.connect(self.alternar)
        self._cab.doble.connect(self.alternar_posiciones)
        cc = self._cab.capa
        # v5.22: «Posición»: la línea de tiempo del video para marcar en qué segundos va este efecto (posiciones_pro)
        try:
            icono = ui.icono_linea('ph.map-pin', '#C9D6EC')
        except Exception:
            icono = None
        self._b_pos = Boton(tr('Posición'), self.alternar_posiciones, tipo='neutro', alto=32, tam=12, icono=icono)
        cc.addWidget(self._b_pos)
        self._b_pos.setVisible(self.clave not in SIN_POSICION)
        self._var_on = ui.BooleanVar(False)
        self._sw = Interruptor(tr('Activado en GO'), self._var_on, self._cambio_on, tam=13, color='#E0EBFB')
        cc.addWidget(self._sw)
        self.capa.addWidget(self._cab)
        self._pos = None                                 # la vista «Posición» (se arma la primera vez)
        self._cuerpo = QWidget()
        cuerpo = QVBoxLayout(self._cuerpo)
        cuerpo.setContentsMargins(0, 4, 0, 6)
        cuerpo.setSpacing(12)
        self.capa.addWidget(self._cuerpo)
        cuerpo.addWidget(Etiqueta(tr(seccion['detalle']) + (' ' + tr('Solo con DaVinci Resolve Studio.') if opcion and opcion.get('solo_studio') else ''),
                                  13, color=TEXT_MUTED, envolver=True))
        self._lbl_estado = Etiqueta('', 12, color='#8EA2C6', envolver=True)
        cuerpo.addWidget(self._lbl_estado)
        self.cartas = {}
        lista = []
        for ident, nombre, detalle in [('', tr('Automático'), tr('Lo decide el tema y el video, como siempre.'))] + \
                                      [(v['id'], tr(v['nombre']), tr(v['detalle'])) for v in seccion['variantes']]:
            mp4, jpg = EST.previa(self.clave, ident)
            c = TarjetaEfecto(ident, nombre, detalle, mp4, jpg)
            c.clic.connect(self._elegir)
            self.cartas[ident] = c
            lista.append(c)
        self.slider = SliderCartas(lista)
        cuerpo.addWidget(self.slider)
        # ---- colores (v5.33, el gancho: «Personaliza» = colores + sonido + zoom en UNA fila; cada botón abre su tira debajo, una a la vez)
        fila, cf = caja_h(espacio=8)
        extras = seccion.get('sonidos') or seccion.get('zooms')
        cf.addWidget(Etiqueta(tr('Personaliza') if extras else tr('Colores'), 13, color=TEXT_MUTED))
        self.chips = {}
        for hueco, etiqueta in seccion['colores']:
            ch = ChipColor(hueco, tr(etiqueta))
            ch.clic.connect(self._abrir_tira)
            cf.addWidget(ch)
            self.chips[hueco] = ch
        self._chip_sonido = self._chip_zoom = None
        if seccion.get('sonidos'):
            self._chip_sonido = ChipOpcion('sonido', tr('Sonido'), 'ph.speaker-high')
            self._chip_sonido.clic.connect(lambda _h='': self._abrir_tira_de('sonido'))
            cf.addWidget(self._chip_sonido)
        if seccion.get('zooms'):
            self._chip_zoom = ChipOpcion('zoom', tr('Zoom'), 'ph.arrows-out')
            self._chip_zoom.clic.connect(lambda _h='': self._abrir_tira_de('zoom'))
            cf.addWidget(self._chip_zoom)
        cf.addStretch(1)
        cuerpo.addWidget(fila)
        self._tira = QWidget()
        ct = QHBoxLayout(self._tira)
        ct.setContentsMargins(0, 0, 0, 0)
        ct.setSpacing(6)
        ct.addWidget(Boton(tr('Automático'), lambda: self._poner_color(''), tipo='fantasma', alto=30, tam=12))
        self._muestras = []
        for col in EST.MUESTRAS:
            m = Muestra(col)
            m.clic.connect(self._poner_color)
            ct.addWidget(m)
            self._muestras.append(m)
        self._v_hex = StringVar('')
        self._hex = Entrada(self._v_hex, placeholder='#RRGGBB', alto=30, tam=12, ancho=104)
        self._hex.editingFinished.connect(lambda: self._poner_color(str(self._v_hex.get() or '')))
        ct.addWidget(self._hex)
        ct.addWidget(Boton(tr('Cerrar'), self._cerrar_tira, tipo='fantasma', alto=30, tam=12))
        ct.addStretch(1)
        self._tira.setVisible(False)
        cuerpo.addWidget(self._tira)
        # ---- v5.33, el gancho: la tira del SONIDO (el usuario: «por si el sonido por defecto no me gusta»: el de la intro, el de otra,
        # ninguno o uno tuyo; cada uno suena al tocarlo) y la del ZOOM («te faltó el botón de efecto de zoom»: el de la intro, otro o ninguno)
        self._tira_s = self._tira_z = self._b_propio = None
        self._botones_s, self._botones_z = {}, {}
        if seccion.get('sonidos'):
            import intros_gancho
            ops = ([('', tr('El de la intro'))] + [(v['id'], tr(v['nombre'])) for v in seccion['variantes']]
                   + [(intros_gancho.SIN_SONIDO, tr('Sin sonido'))])
            self._tira_s, self._botones_s = self._tira_opciones(ops, self._poner_sonido)
            self._b_propio = Boton(tr('Tu sonido…'), self._elegir_sonido_propio, tipo='fantasma', alto=30, tam=12)
            self._tira_s.layout().addWidget(self._b_propio)
            cuerpo.addWidget(self._tira_s)
        if seccion.get('zooms'):
            import intros_gancho
            ops = ([('', tr('El de la intro'))] + [(z, tr(n)) for z, n in intros_gancho.NOMBRES_ZOOM.items()]
                   + [(intros_gancho.SIN_ZOOM, tr('Sin zoom'))])
            self._tira_z, self._botones_z = self._tira_opciones(ops, self._poner_zoom)
            cuerpo.addWidget(self._tira_z)
        # v5.25: filas propias de la sección (Emojis animados: «Dónde» e «Intensidad»; las mismas preferencias que la píldora del menú lateral)
        self._ajustes = []
        for pref, etiqueta, opciones in seccion.get('ajustes') or []:
            fila_a, ca = caja_h(espacio=10)
            ca.addWidget(Etiqueta(tr(etiqueta), 13, color=TEXT_MUTED))
            nombres = [tr(n) for _k, n in opciones]
            var = StringVar(nombres[0])
            seg = ui.Segmentado(nombres, var, lambda *_a, p=pref, o=opciones, v=var: self._cambio_ajuste(p, o, v), alto=30, tam=12)
            ca.addWidget(seg)
            ca.addStretch(1)
            cuerpo.addWidget(fila_a)
            self._ajustes.append((pref, opciones, var))
        self._abierta = True                            # v5.21 (el usuario: «siempre deja desplegadas las secciones»): abiertas al entrar
        self._cuerpo.setVisible(self._abierta)
        self._cab.poner_abierta(self._abierta)
        self.refrescar()

    def alternar(self):
        self._abierta = not self._abierta
        en_pos = bool(getattr(self, '_en_pos', False))
        self._cuerpo.setVisible(self._abierta and not en_pos)
        if self._pos is not None:
            self._pos.setVisible(self._abierta and en_pos)
        self._cab.poner_abierta(self._abierta)
        if self._abierta and not en_pos:
            sel = next((c for c in self.cartas.values() if c._sel), None)
            self.slider.mostrar(sel)

    # -- v5.22: la vista «Posición» (en qué segundos del video va este efecto)
    def alternar_posiciones(self):
        if self.clave in SIN_POSICION:
            return
        self.mostrar_posiciones(not getattr(self, '_en_pos', False))

    def mostrar_posiciones(self, si):
        import posiciones_pro as POS
        self._en_pos = bool(si)
        if si and self._pos is None:
            self._pos = POS.VistaPosiciones(self.clave)
            self._pos.listo.connect(self._listo_posiciones)
            self._pos.linea.marca_puesta.connect(self._encender_al_marcar)
            self._pos.cambio.connect(self.refrescar)
            self._pos.volver.connect(lambda: self.mostrar_posiciones(False))
            self.capa.addWidget(self._pos)
        if not self._abierta:
            self._abierta = True
            self._cab.poner_abierta(True)
        # v5.32: con el diseño nuevo («detrás de ti») la vista trae su propia cabecera (volver, título, Listo): la de la sección se esconde
        self._cab.setVisible(not (si and getattr(self._pos, '_nuevo', None) is not None))
        self._cuerpo.setVisible(not si)
        if self._pos is not None:
            self._pos.setVisible(si)
            if si:
                self._pos.abrir()
        self._b_pos.setProperty('tipo', 'primario' if si else 'neutro')
        self._b_pos.style().unpolish(self._b_pos)
        self._b_pos.style().polish(self._b_pos)
        self.refrescar()

    def _encender_al_marcar(self):
        """v5.27 (el usuario: «si le doy clic a una sugerencia, que ya quede lista la selección»): poner una marca enciende el efecto en GO
        (antes había que acordarse de «Activado en GO» o de «Listo»)."""
        try:
            import pro_lateral_ui as LAT
            if not LAT.estado(self.clave):
                LAT.poner(self.clave, True)
                self.refrescar()
                self.cambio.emit()
        except Exception:
            pass

    def _listo_posiciones(self):
        """v5.27 (el usuario: «cuando le doy Listo que quede guardado y cuando vuelva a la página de Inicio lo aplique»): con marcas, el efecto
        queda ENCENDIDO en GO (si no, para_plan las saltaba) y, si el video se eligió a mano, pasa a ser el de Inicio; el Registro lo dice."""
        from pathlib import Path
        import posiciones_pro as POS
        pos = self._pos
        ruta = pos.linea.ruta if pos is not None else None
        n = len(pos.linea.marcas) if pos is not None else 0
        if ruta and n:
            hechos = []
            try:
                import pro_lateral_ui as LAT
                if not LAT.estado(self.clave) and LAT.poner(self.clave, True) is not False:
                    hechos.append('lo encendí en GO')
            except Exception:
                pass
            if pos.a_mano() and POS.poner_video_inicio(ruta):
                hechos.append('ahora es el video de Inicio')
            ya = self._al_timeline(pos)                                # v5.29: va YA al timeline (abajo)
            try:
                import registro
                modo = '' if pos.linea.modo == 'solo' else ' + automático'
                registro.info(f'Efectos › {self.s["titulo"]}: {n} {"posición guardada" if n == 1 else "posiciones guardadas"}{modo} para '
                              f'«{Path(str(ruta)).name}»' + (f' ({", ".join(hechos)})' if hechos else '') +
                              ((('. La pongo' if n == 1 else '. Las pongo') + ' ya en tu timeline de Resolve.') if ya else
                               ('. GO la aplica.' if n == 1 else '. GO las aplica.')), 'Efectos')
            except Exception:
                pass
        if ruta and self.clave == 'detras' and pos is not None and not pos.a_mano() and pos.linea.dur > 0 and pos.linea._aplicados is not None:
            if pos.linea.igual_que_timeline():                         # v5.30: nada cambió respecto al timeline: ni se toca Resolve
                import registro
                registro.info('Captions detrás de ti: ya está así en tu timeline.', 'Efectos')
            elif self._poner_en_timeline(ruta, list(pos.linea.marcas), pos.linea.modo, vista=pos):
                self.cambio.emit()                                     # v5.31: la vista sigue abierta con su barra y enseña cómo quedó
                return
        self.mostrar_posiciones(False)
        self.cambio.emit()

    def _al_timeline(self, pos):
        """¿«Listo» lo pone YA en Resolve? Solo «detrás de ti», con el video de Inicio, si GO ya pasó por ese video (la tira sabe lo que hay en
        su timeline: v5.31, sin GO antes solo se guarda y GO lo aplica) y si algo cambió."""
        return (self.clave == 'detras' and pos is not None and not pos.a_mano() and pos.linea._aplicados is not None
                and not pos.linea.igual_que_timeline())

    def _poner_en_timeline(self, ruta, marcas=None, modo='solo', vista=None):
        """v5.29 (el usuario: «cuando le dé Listo debe ponerlo automáticamente en la línea de tiempo; va a ser más útil que generar todo»):
        «detrás de ti» con las marcas de ahora en el timeline ABIERTO de Resolve (edicion_pro.aplicar_detras: la persona con el matte de la IA,
        los captions subidos; lo demás de la PRO no se toca), en un hilo. La cabecera dice cómo va; el Registro, cómo acabó. Sin GO de ese video
        (o con otro timeline abierto) solo se guarda y lo dice. v5.31: con `vista` (la de Posición) la barra enseña el avance y, al acabar, la tira
        lo que quedó. → True si empezó."""
        import registro
        if getattr(self, '_aplicando', False):
            return False
        if getattr(self.window(), '_go_corriendo', False):
            registro.info('Captions detrás de ti: GO está trabajando; tus posiciones van en este GO o en el próximo.', 'Efectos')
            return False
        try:
            import edicion_pro as EP
            if not EP.detras_disponible():
                return False
        except Exception:
            return False
        self._aplicando = True
        self._estado_tl = tr('poniéndolo en tu timeline…')
        self.refrescar()
        if vista is not None:
            vista.empezar_aplicar()

        def fin(r, error):
            self._aplicando = False
            ok, mensaje, n = r if (error is None and r) else (False, f'{type(error).__name__}: {error}' if error else '', 0)
            if vista is not None:
                try:
                    vista.terminar_aplicar(ok, mensaje, marcas)
                except RuntimeError:                               # (la vista ya no existe)
                    pass
            if ok:
                self._estado_tl = tr('en tu timeline') if n else ''
                registro.info(f'Captions detrás de ti: {n} {"tramo puesto" if n == 1 else "tramos puestos"} en tu timeline de Resolve (la persona '
                              f'recortada con IA delante de los captions), sin rehacer GO.' if n else
                              'Captions detrás de ti: quitado de tu timeline (ya no queda ninguno).', 'Efectos')
            else:
                self._estado_tl = ''
                registro.aviso(f'Captions detrás de ti no se pudo poner en tu timeline: {mensaje}', 'Efectos')
            self.refrescar()
            self.cambio.emit()
        ui.correr_en_hilo(self, lambda: EP.aplicar_detras(ruta, marcas_tira=marcas, modo=modo,
                                                          al_progreso=vista.progreso_hilo if vista is not None else None), fin)
        return True

    def mouseDoubleClickEvent(self, e):
        """Doble clic en cualquier sitio de la sección (fuera de un control): la «Posición»."""
        if e.button() == Qt.MouseButton.LeftButton:
            self.alternar_posiciones()

    def _cambio_ajuste(self, pref, opciones, var):
        inv = {tr(n): k for k, n in opciones}
        valor = inv.get(str(var.get()))
        if valor is None:
            return
        try:
            import edicion_pro
            edicion_pro.guardar_opciones({pref: valor})
        except Exception:
            return
        self.cambio.emit()

    # -- estado
    def refrescar(self):
        if getattr(self, '_ajustes', None):
            try:
                import edicion_pro
                op = edicion_pro.opciones_guardadas()
            except Exception:
                op = {}
            for pref, opciones, var in self._ajustes:
                actual = dict(opciones).get(op.get(pref)) or opciones[0][1]
                if str(var.get()) != tr(actual):
                    var.set(tr(actual))
        est = EST.leer()
        d = est.get(self.clave) or {}
        actual = d.get('v') or ''
        for ident, c in self.cartas.items():
            c.poner_seleccionada(ident == actual)
        v, col = EST.resolver(self.clave, est=est)
        propios = d.get('c') or {}
        for hueco, ch in self.chips.items():
            ch.poner(propios.get(hueco, ''), activo=hueco == self._hueco)
        extra_s = ''
        if self._chip_sonido is not None:                # v5.33: el sonido elegido (chip, opción marcada y resumen)
            import intros_gancho
            s = d.get('s', '')
            propio = bool(s) and s != intros_gancho.SIN_SONIDO and EST.variante(self.clave, s) is None
            self._chip_sonido.poner(tr(intros_gancho.nombre_sonido(s)), activo=not self._tira_s.isHidden())
            for valor, b in self._botones_s.items():
                _marcar(b, valor == s)
            _marcar(self._b_propio, propio)
            self._b_propio.setText(tr('Tu sonido: ') + intros_gancho.nombre_sonido(s) if propio else tr('Tu sonido…'))
            if s:
                extra_s = tr(' · sonido: ') + tr(intros_gancho.nombre_sonido(s))
        if self._chip_zoom is not None:                  # v5.33: el zoom elegido
            import intros_gancho
            z = d.get('z', '')
            self._chip_zoom.poner(tr(intros_gancho.nombre_zoom(z)), activo=not self._tira_z.isHidden())
            for valor, b in self._botones_z.items():
                _marcar(b, valor == z)
            if z:
                extra_s += tr(' · zoom: ') + tr(intros_gancho.nombre_zoom(z))
        try:
            import pro_lateral_ui as LAT
            on = bool(LAT.estado(self.clave))
        except Exception:
            on = False
        if bool(self._var_on.get()) != on:
            self._var_on.set(on)
        nombre = tr(v['nombre']) if v else tr('Automático')
        self._lbl_estado.setText(tr('GO usará: ') + nombre + extra_s + ('' if on else tr(' · ahora está apagada (enciéndela aquí o en el menú de Proyecto)')))
        extra = extra_s
        try:                                             # v5.22: las posiciones marcadas para el video de Inicio
            import posiciones_pro as POS
            if self._pos is not None and getattr(self, '_en_pos', False):
                self._pos.al_volver()                    # (v5.23: otro video en Inicio, p. ej. tras «Obtener»: se carga ese)
            ruta = POS.video_actual()
            if self._pos is not None and self._pos.linea.ruta and POS.es_de_inicio(self._pos.linea.ruta):
                ruta = self._pos.linea.ruta              # (v5.27: el de la vista, ya con su video si Inicio tiene el audio de un timeline)
            n, modo = POS.resumen(ruta, self.clave) if ruta and self.clave not in SIN_POSICION else (0, 'solo')
            if n:
                extra += ' · ' + (tr('1 posición') if n == 1 else tr('{n} posiciones', n=n)) + ('' if modo == 'solo' else tr(' + automático'))
        except Exception:
            pass
        if getattr(self, '_estado_tl', ''):                # v5.29: «Listo» → al timeline: cómo va
            extra += ' · ' + self._estado_tl
        self._cab.poner_resumen(nombre + (tr(' · colores propios') if propios else '') + extra)
        if self._pos is not None and hasattr(self._pos, 'poner_resumen'):
            self._pos.poner_resumen(nombre + (tr(' · colores propios') if propios else '') + extra)
        self._pintar_muestras()

    def _pintar_muestras(self):
        actual = ((EST.leer().get(self.clave) or {}).get('c') or {}).get(self._hueco or '', '')
        for m in self._muestras:
            m.sel = bool(actual) and m.color.upper() == actual[:7].upper()
            m.update()

    # -- acciones
    def _elegir(self, ident):
        EST.guardar_variante(self.clave, ident)
        self.refrescar()
        self.cambio.emit()
        if self.clave == 'gancho':                       # v5.33: la intro suena al elegirla (su golpe es la mitad de la intro)
            self._oir_gancho(ident)

    def _oir_gancho(self, ident=None, eleccion=None):
        """Suena lo que GO pondría: la intro `ident` (None = la elegida) con el sonido `eleccion` (None = el guardado). En un hilo."""
        if getattr(self, '_reproductor', None) is None:
            import sfx_audio
            self._reproductor = sfx_audio.Reproductor()
        import intros_gancho
        if ident is None:
            ident = (EST.leer().get(self.clave) or {}).get('v') or ''
        ui.correr_en_hilo(self, lambda: intros_gancho.oir(ident, self._reproductor, eleccion), lambda *_a: None)

    # -- v5.33: «Sonido» y «Zoom» del gancho (sus tiras se abren debajo de «Personaliza», una a la vez)
    def _tira_opciones(self, opciones, al_elegir):
        """Una tira de opciones en píldoras que saltan de línea si no caben: (widget oculto, {valor: botón})."""
        w = QWidget()
        flujo = ui.FlujoCapa(w, espacio_h=6, espacio_v=6)
        botones = {}
        for valor, texto in opciones:
            b = Boton(texto, lambda v=valor: al_elegir(v), tipo='fantasma', alto=30, tam=12)
            flujo.addWidget(b)
            botones[valor] = b
        w.setVisible(False)
        return w, botones

    def _abrir_tira_de(self, cual):
        tira = {'sonido': self._tira_s, 'zoom': self._tira_z}.get(cual)
        if tira is None:
            return
        abrir = tira.isHidden()
        self._cerrar_tira(refrescar=False)
        for t in (self._tira_s, self._tira_z):
            if t is not None:
                t.setVisible(False)
        tira.setVisible(abrir)
        self.refrescar()

    def _poner_zoom(self, valor):
        EST.guardar_zoom(self.clave, valor)
        self.refrescar()
        self.cambio.emit()

    def _poner_sonido(self, valor):
        EST.guardar_sonido(self.clave, valor)
        self.refrescar()
        self.cambio.emit()
        self._oir_gancho(eleccion=valor)

    def _elegir_sonido_propio(self):
        ruta = ui.filedialog.askopenfilename(title=tr('Elige tu sonido'), parent=self.window(),
                                             filetypes=[(tr('Audio'), '*.wav *.mp3 *.m4a *.aif *.aiff *.flac *.ogg'), (tr('Todos los archivos'), '*.*')])
        if ruta:
            self._poner_sonido(ruta)

    def _cambio_on(self):
        si = bool(self._var_on.get())
        try:
            import pro_lateral_ui as LAT
            ok = LAT.poner(self.clave, si)
        except Exception:
            ok = False
        if ok is False and not si:                      # (el último grupo de motions no se apaga: lo dice el Registro)
            try:
                import registro
                registro.aviso(f'«{self.s["titulo"]}» es lo único que queda encendido de los motions: para no poner ninguno, apaga la Edición PRO.', 'Efectos')
            except Exception:
                pass
        self.refrescar()
        self.cambio.emit()

    def _abrir_tira(self, hueco):
        if self._tira.isVisible() and self._hueco == hueco:
            self._cerrar_tira()
            return
        self._hueco = hueco
        actual = ((EST.leer().get(self.clave) or {}).get('c') or {}).get(hueco, '')
        self._v_hex.set(actual)
        for t in (self._tira_s, self._tira_z):          # (v5.33: una tira a la vez)
            if t is not None:
                t.setVisible(False)
        self._tira.setVisible(True)
        self.refrescar()

    def _cerrar_tira(self, refrescar=True):
        self._hueco = None
        self._tira.setVisible(False)
        if refrescar:
            self.refrescar()

    def _poner_color(self, color):
        if not self._hueco:
            return
        color = str(color or '').strip()
        if color and not EST._hex(color):
            return                                       # (un texto que no es un color: no se guarda)
        EST.guardar_color(self.clave, self._hueco, color or None)
        self._v_hex.set(EST._hex(color)[:7] if color else '')
        self.refrescar()
        self.cambio.emit()


# ====================================================================================== el bloque entero
class SeccionEstilosPro(QWidget):
    """Todas las secciones de la PRO, en el orden del menú lateral de Proyecto (las que se ven en este equipo: sin Studio no sale «detrás de ti»)."""
    cambio = Signal()

    def __init__(self, padre=None):
        super().__init__(padre)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(18)                              # (sin la tarjeta «Edición PRO: estilos» de cabecera: el usuario, «elimina esto»)
        try:
            import pro_lateral_ui as LAT
            visibles = LAT.opciones_visibles()
        except Exception:
            visibles = []
        por = {o['clave']: o for o in visibles}
        orden = list(por)                                # v5.23 (el usuario: «ordena la página de Efectos conforme al menú»): el orden del menú lateral
        self.secciones = []
        for s in sorted(EST.SECCIONES, key=lambda s: orden.index(s['clave']) if s['clave'] in orden else len(orden)):
            if visibles and s['clave'] not in por:
                continue
            sec = SeccionEstilo(s, por.get(s['clave']))
            sec.cambio.connect(self.cambio.emit)
            capa.addWidget(sec)
            self.secciones.append(sec)

    @property
    def tarjetas(self):
        return [c for s in self.secciones for c in s.cartas.values()]

    def refrescar(self):
        for s in self.secciones:
            s.refrescar()
