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
        # ---- colores
        fila, cf = caja_h(espacio=8)
        cf.addWidget(Etiqueta(tr('Colores'), 13, color=TEXT_MUTED))
        self.chips = {}
        for hueco, etiqueta in seccion['colores']:
            ch = ChipColor(hueco, tr(etiqueta))
            ch.clic.connect(self._abrir_tira)
            cf.addWidget(ch)
            self.chips[hueco] = ch
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
        self.mostrar_posiciones(not getattr(self, '_en_pos', False))

    def mostrar_posiciones(self, si):
        import posiciones_pro as POS
        self._en_pos = bool(si)
        if si and self._pos is None:
            self._pos = POS.VistaPosiciones(self.clave)
            self._pos.listo.connect(lambda: self.mostrar_posiciones(False))
            self._pos.cambio.connect(self.refrescar)
            self.capa.addWidget(self._pos)
        if not self._abierta:
            self._abierta = True
            self._cab.poner_abierta(True)
        self._cuerpo.setVisible(not si)
        if self._pos is not None:
            self._pos.setVisible(si)
            if si:
                self._pos.abrir()
        self._b_pos.setProperty('tipo', 'primario' if si else 'neutro')
        self._b_pos.style().unpolish(self._b_pos)
        self._b_pos.style().polish(self._b_pos)
        self.refrescar()

    def mouseDoubleClickEvent(self, e):
        """Doble clic en cualquier sitio de la sección (fuera de un control): la «Posición»."""
        if e.button() == Qt.MouseButton.LeftButton:
            self.alternar_posiciones()

    # -- estado
    def refrescar(self):
        est = EST.leer()
        d = est.get(self.clave) or {}
        actual = d.get('v') or ''
        for ident, c in self.cartas.items():
            c.poner_seleccionada(ident == actual)
        v, col = EST.resolver(self.clave, est=est)
        propios = d.get('c') or {}
        for hueco, ch in self.chips.items():
            ch.poner(propios.get(hueco, ''), activo=hueco == self._hueco)
        try:
            import pro_lateral_ui as LAT
            on = bool(LAT.estado(self.clave))
        except Exception:
            on = False
        if bool(self._var_on.get()) != on:
            self._var_on.set(on)
        nombre = tr(v['nombre']) if v else tr('Automático')
        self._lbl_estado.setText(tr('GO usará: ') + nombre + ('' if on else tr(' · ahora está apagada (enciéndela aquí o en el menú de Proyecto)')))
        extra = ''
        try:                                             # v5.22: las posiciones marcadas para el video de Inicio
            import posiciones_pro as POS
            if self._pos is not None and getattr(self, '_en_pos', False):
                self._pos.al_volver()                    # (v5.23: otro video en Inicio, p. ej. tras «Obtener»: se carga ese)
            ruta = POS.video_actual()
            n, modo = POS.resumen(ruta, self.clave) if ruta else (0, 'solo')
            if n:
                extra = ' · ' + (tr('1 posición') if n == 1 else tr('{n} posiciones', n=n)) + ('' if modo == 'solo' else tr(' + automático'))
        except Exception:
            pass
        self._cab.poner_resumen(nombre + (tr(' · colores propios') if propios else '') + extra)
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
        self._tira.setVisible(True)
        self.refrescar()

    def _cerrar_tira(self):
        self._hueco = None
        self._tira.setVisible(False)
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
        capa.setSpacing(18)
        cab = Tarjeta(espacio=6, margenes=(22, 16, 22, 16))
        cab.capa.addWidget(Etiqueta(tr('Edición PRO: estilos'), 20, peso='medio', color='#FFFFFF'))
        cab.capa.addWidget(Etiqueta(tr('Elige cómo se ve cada función de la Edición PRO. Lo que pone (el lugar, la cifra, el icono…) sale de tu video; '
                                       'aquí decides la forma y los colores. Se aplica cuando la función está encendida.'), 13, color=TEXT_MUTED, envolver=True))
        capa.addWidget(cab)
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
