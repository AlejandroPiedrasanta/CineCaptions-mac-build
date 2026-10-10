# CineCaptions · By Cinema Productions
# 1_codigo/efectos_pagina.py — la página «Efectos»: elegir la intro (con su sonido), las transiciones de los cortes y los iconos flotantes (y en qué palabras salen).
"""
efectos_pagina.py  (v5.4.7)
---------------------------
Tres tarjetas —Intro, Transiciones en los cortes, Iconos flotantes— con una vista previa animada de cada efecto (2_recursos/efectos/previas, hechas con
hacer_previas_efectos.py y reproducidas con vistas_slider.Reproductor solo mientras se ven). Lo que se elige se guarda en las preferencias y lo lee
efectos_visuales.planificar al hacer GO:

    fx_intro / fx_intro_sonido / fx_intro_zoom  la intro, su sonido (el Viral Hooks Riser de fábrica, el Riser 1, otro archivo o 'ninguno' = silenciada) y el golpe de zoom en su pico
    fx_sonido_corte                       el sonido de las transiciones (auto | shutter | whoosh | glitch | power_up | ninguno)
    fx_cortes / fx_cortes_cuanto          la transición de los cortes y cuántas
    fx_iconos_activo / fx_iconos          los iconos flotantes (interruptor general y packs activos)
    fx_iconos_palabras {pack: [palabras]} en qué palabras sale cada pack (clic en el pack); fx_iconos_extra = también en frases importantes
    fx_iconos_cuanto                      cuántos iconos

v5.4.26: los efectos vienen ACTIVADOS y la página NO tiene interruptor general: cada sección se apaga con su tarjeta «Sin …». El chip «Visuales» de Inicio (go_efectos_visuales) sigue apagándolos todos.
"""
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

import efectos_visuales as F
import qt_kit as ui
from qt_kit import Boton, Dialogo, Etiqueta, Interruptor, Segmentado, StringVar, Tarjeta, Tooltip, caja_h
from qt_kit import QColor
from i18n import tr

VERDE = ui.VERDE
TEXT_MUTED = ui.TEXT_MUTED


def _guardar(cambios):
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs(cambios)
    except Exception:
        pass


# ====================================================================================== una tarjeta de efecto
class TarjetaEfecto(QWidget):
    """Una vista previa 9:16 (el mp4 del efecto sobre una foto, en bucle mientras se ve), su nombre y una línea. Tocarla la elige. Con `pack=True` (iconos) el clic abre
    «en qué palabras sale» y lleva abajo su interruptor (activo / no) y el botón «Palabras»."""
    clic = Signal(str)
    cambio = Signal(str, bool)               # (ident, activo) — solo en los packs de iconos
    ANCHO = 156
    ALTO_IMAGEN = int((ANCHO - 16) * 16 / 9)

    def __init__(self, ident, nombre, detalle, previa=None, poster=None, ninguna=False, pack=False, padre=None):
        super().__init__(padre)
        self.ident = ident
        self.nombre = nombre
        self.detalle = detalle
        self._ninguna = bool(ninguna)
        self._pack = bool(pack)
        self._sel = False
        self._hover = False
        self._apagada = False
        self._poster = QImage(str(poster)) if poster else None
        self._reprod = None
        if previa:
            import vistas_slider
            self._reprod = vistas_slider.Reproductor(previa)
        self.setFixedSize(self.ANCHO, self.ALTO_IMAGEN + 84 + (40 if pack else 0))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        Tooltip(self, detalle)
        self._var_activo = ui.BooleanVar(False)
        if pack:
            self._sw = Interruptor('', self._var_activo, self._al_interruptor, tam=12, padre=self)
            self._sw.setToolTip(tr('Activar o desactivar este pack de iconos'))
            self._sw.move(self.ANCHO - 58, self.ALTO_IMAGEN + 88)
            self._b = Boton(tr('Palabras'), self.clic_palabras, alto=26, tam=11, padre=self)
            self._b.setGeometry(8, self.ALTO_IMAGEN + 88, 78, 26)
            Tooltip(self._b, tr('Elige en qué palabras sale este pack de iconos.'))

    def clic_palabras(self):
        self.clic.emit(self.ident)

    def _al_interruptor(self):
        self._sel = bool(self._var_activo.get())
        self.update()
        self.cambio.emit(self.ident, self._sel)

    def poner_seleccionada(self, v):
        if bool(v) != self._sel:
            self._sel = bool(v)
            self.update()
        if self._pack and bool(self._var_activo.get()) != self._sel:
            self._var_activo.set(self._sel)

    def poner_apagada(self, v):
        """El interruptor general de los iconos está apagado: la tarjeta se ve atenuada y no responde."""
        self._apagada = bool(v)
        self.setEnabled(not v)
        self.update()

    def poner_visible(self, visible):
        if self._reprod is not None:
            if visible and not self._apagada:
                self._reprod.arrancar()
            else:
                self._reprod.parar()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self.ident)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._apagada or (self._pack and not self._sel):
            p.setOpacity(0.55)
        marco = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setBrush(QColor('#13203A' if (self._sel or self._hover) else '#0F1A30'))
        p.setPen(QPen(QColor(VERDE if self._sel else ('#2C4068' if self._hover else '#1E2A42')), 2.2 if self._sel else 1.0))
        p.drawRoundedRect(marco, 14, 14)
        rect = QRectF(8, 8, self.ANCHO - 16, self.ALTO_IMAGEN)
        camino = QPainterPath()
        camino.addRoundedRect(rect, 12, 12)
        p.save()
        p.setClipPath(camino)
        if self._ninguna:
            p.fillRect(rect, QColor('#0B1424'))
            p.setPen(QColor(TEXT_MUTED))
            p.setFont(ui.fuente(34))
            p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), '∅')
        else:
            img = self._reprod.imagen() if self._reprod is not None else None
            if img is None:
                img = self._poster
            if img is not None:
                p.drawImage(rect, img)
            else:
                p.fillRect(rect, QColor('#0B1424'))
        p.restore()
        p.setPen(QColor('#FFFFFF'))
        for _tam in (13, 12, 11, 10):                                     # el nombre se achica hasta caber («Fondo desenfocado», «Grano de película»)
            p.setFont(ui.fuente(_tam, True))
            if QFontMetricsF(p.font()).horizontalAdvance(self.nombre) <= self.width() - 26:
                break
        p.drawText(QRectF(10, self.ALTO_IMAGEN + 14, self.width() - 20, 20), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.nombre)
        p.setPen(QColor(TEXT_MUTED))
        p.setFont(ui.fuente(10))
        p.drawText(QRectF(10, self.ALTO_IMAGEN + 36, self.width() - 20, 40), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), self.detalle)
        if self._sel:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(VERDE))
            p.drawEllipse(QRectF(self.ANCHO - 36, 14, 22, 22))
            p.setPen(QPen(QColor('#07140E'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(int(self.ANCHO - 30), 25, int(self.ANCHO - 26), 29)
            p.drawLine(int(self.ANCHO - 26), 29, int(self.ANCHO - 20), 21)
        p.end()


# ====================================================================================== una fila de tarjetas con ejemplo
class FilaCartas(QWidget):
    """Una fila de TarjetaEfecto (cada una con su ejemplo animado) de la que se elige UNA: «sin efecto» (∅) y cada variante. Es como la intro: se ve cómo queda antes de elegirlo.
    Las vistas previas son `previas/<tipo>_<clave>.mp4` (hacer_previas_efectos.py / hacer_previas_nuevas.py). `opciones` = [(clave, nombre, detalle[, ninguna])]; `al_elegir(clave)`."""

    def __init__(self, tipo, opciones, actual, al_elegir=None, padre=None):
        super().__init__(padre)
        self.tipo = tipo
        self._al_elegir = al_elegir
        self.tarjetas = []
        self._por_clave = {}
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(12)
        carpeta = F.carpeta_efectos() / 'previas'
        for op in opciones:
            clave, nombre, detalle = op[0], op[1], op[2]
            ninguna = bool(op[3]) if len(op) > 3 else clave in ('', 'no')
            previa = poster = None
            if not ninguna:
                m, j = carpeta / f'{tipo}_{clave}.mp4', carpeta / f'{tipo}_{clave}.jpg'
                previa = m if m.is_file() else None
                poster = j if j.is_file() else None
            c = TarjetaEfecto(clave, nombre, detalle, previa, poster, ninguna=ninguna)
            c.clic.connect(self._tocar)
            capa.addWidget(c)
            self.tarjetas.append(c)
            self._por_clave[clave] = c
        capa.addStretch(1)
        self.poner(actual)

    def poner(self, clave):
        self._actual = clave if clave in self._por_clave else next(iter(self._por_clave))
        for k, c in self._por_clave.items():
            c.poner_seleccionada(k == self._actual)

    def valor(self):
        return self._actual

    def _tocar(self, clave):
        self.poner(clave)
        if self._al_elegir:
            self._al_elegir(clave)


# ====================================================================================== «en qué palabras sale»
class DialogoPalabras(Dialogo):
    """Las palabras (o frases cortas) que hacen salir un pack de iconos. Se escriben separadas por comas; al guardar, el pack sale cuando se dice una de ellas."""
    def __init__(self, padre, pack, nombre, al_guardar):
        super().__init__(padre, tr('Palabras de «{n}»', n=nombre), 560, 470, minimo=(480, 400))
        self._pack = pack
        self._al_guardar = al_guardar
        capa = QVBoxLayout(self)
        capa.setContentsMargins(22, 20, 22, 18)
        capa.setSpacing(12)
        capa.addWidget(Etiqueta(tr('Palabras de «{n}»', n=nombre), 20, peso='extra', color='#FFFFFF'))
        capa.addWidget(Etiqueta(tr('El icono sale en el momento en que se dice una de estas palabras. Escríbelas separadas por comas (también valen frases cortas, como «no lo hagas»). Si la lista queda vacía, este pack solo sale en las frases importantes.'),
                                13, color='#B4C0D6', envolver=True))
        self._caja = QPlainTextEdit()
        self._caja.setFont(ui.fuente(14))
        self._caja.setPlainText(', '.join(F.palabras_de_pack(pack)))
        self._caja.setMinimumHeight(170)
        capa.addWidget(self._caja, 1)
        self._nota = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        capa.addWidget(self._nota)
        fila, cf = caja_h(espacio=10)
        self._b_fabrica = Boton(tr('Volver a las de fábrica'), self._fabrica, tipo='fantasma', alto=36, tam=13)
        cf.addWidget(self._b_fabrica)
        cf.addStretch(1)
        cf.addWidget(Boton(tr('Cancelar'), self.cerrar, alto=36, ancho=110, tam=13))
        cf.addWidget(Boton(tr('Guardar'), self._guardar, tipo='primario', alto=36, ancho=130, tam=13, negrita=True))
        capa.addWidget(fila)
        self._caja.textChanged.connect(self._contar)
        self._contar()

    @staticmethod
    def _lista(texto):
        vistas, salida = set(), []
        for t in str(texto).replace('\n', ',').replace(';', ',').split(','):
            t = ' '.join(t.split())
            if t and t.lower() not in vistas:
                vistas.add(t.lower())
                salida.append(t)
        return salida

    def _contar(self):
        n = len(self._lista(self._caja.toPlainText()))
        self._nota.configure(text=tr('{n} palabras', n=n) if n != 1 else tr('1 palabra'))

    def _fabrica(self):
        self._caja.setPlainText(', '.join(F.PALABRAS_POR_DEFECTO.get(self._pack, ())))

    def _guardar(self):
        self._al_guardar(self._pack, self._lista(self._caja.toPlainText()))
        self.cerrar()


# ====================================================================================== vista previa de 3 s
class DialogoVistaPrevia(Dialogo):
    """Los efectos que están encendidos, sobre fotos de muestra, en un bucle de 3 s (vista_previa_fx.py). Se prepara en un hilo y se mueve solo mientras la ventana está abierta."""
    def __init__(self, padre):
        super().__init__(padre, tr('Vista previa de 3 segundos'), 440, 800, redimensionable=False)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(20, 18, 20, 16)
        capa.setSpacing(10)
        capa.addWidget(Etiqueta(tr('Vista previa de 3 segundos'), 18, peso='extra', color='#FFFFFF'))
        self._lienzo = _Lienzo()
        capa.addWidget(self._lienzo, 0, Qt.AlignmentFlag.AlignHCenter)
        self._nota = Etiqueta(tr('Preparando la vista previa…'), 12, color=TEXT_MUTED, envolver=True)
        capa.addWidget(self._nota)
        capa.addStretch(1)
        fila, cf = caja_h(espacio=10)
        cf.addStretch(1)
        cf.addWidget(Boton(tr('Cerrar'), self.cerrar, alto=36, ancho=120, tam=13))
        capa.addWidget(fila)
        self._reprod = None
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._lienzo.update)
        ui.correr_en_hilo(self, self._preparar, self._listo)

    @staticmethod
    def _preparar():
        import vista_previa_fx
        return vista_previa_fx.renderizar()

    def _listo(self, ruta, error):
        if error is not None or not ruta:
            self._nota.configure(text=tr('No pude preparar la vista previa.'))
            return
        import vistas_slider
        self._reprod = vistas_slider.Reproductor(ruta)
        self._lienzo.reprod = self._reprod
        self._reprod.arrancar()
        self._reloj.start(33)
        self._nota.configure(text=tr('El zoom, el temblor y las transiciones que mueven el video se ven aquí de forma aproximada; en Resolve salen con la calidad completa.'))

    def cerrar(self):
        if self._reprod is not None:
            self._reprod.parar()
        self._reloj.stop()
        super().cerrar()

    def closeEvent(self, e):
        if self._reprod is not None:
            self._reprod.parar()
        self._reloj.stop()
        super().closeEvent(e)


class _Lienzo(QWidget):
    def __init__(self):
        super().__init__()
        self.reprod = None
        self.setFixedSize(360, 640)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(0, 0, 360, 640)
        camino = QPainterPath()
        camino.addRoundedRect(rect, 14, 14)
        p.setClipPath(camino)
        p.fillRect(rect, QColor('#0B1424'))
        img = self.reprod.imagen() if self.reprod is not None else None
        if img is not None:
            p.drawImage(rect, img)
        p.end()


# ====================================================================================== la página
class PaginaEfectos(QWidget):
    TIC_MS = 40

    def __init__(self, padre=None, al_cambiar=None):
        super().__init__(padre)
        self._al_cambiar = al_cambiar               # se llama tras cambiar el interruptor general (para que Inicio repinte su chip)
        self._tarjetas = []
        self._dialogo = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(18)
        op = F.opciones_guardadas()
        # ---- v5.4.26: sin interruptor general; los efectos vienen activos y cada sección tiene su tarjeta «Sin …» (el chip «Visuales» de Inicio sigue apagándolos todos)
        fila_i, ci = caja_h(espacio=10)
        ci.addStretch(1)
        ci.addWidget(Boton(tr('Vista previa de 3 s'), self._abrir_vista_previa, alto=34, tam=12))
        capa.addWidget(fila_i)
        # ---- intro (y su sonido)
        self._intro = op.get('fx_intro') or ''
        t1 = self._tarjeta(tr('Intro'), tr('Un destello de luz con su sonido: sube el riser (sus últimos 2 s) y, justo en su pico, el destello cubre la imagen y el cuadro se suelta con un golpe de zoom.'))
        fila_s, cs = caja_h(espacio=12)
        self._var_sonido = ui.BooleanVar(F.fuente_sonido_intro(op) is not None)
        self._sw_sonido = Interruptor(tr('Sonido en la intro'), self._var_sonido, self._cambio_sonido_on, tam=14, color='#FFFFFF')
        cs.addWidget(self._sw_sonido)
        self._lbl_sonido = Etiqueta('', 13, color='#B4C0D6')
        cs.addWidget(self._lbl_sonido)
        cs.addStretch(1)
        self._b_oir = Boton(tr('Oír'), self._oir_sonido, tipo='fantasma', alto=30, tam=12)
        cs.addWidget(self._b_oir)
        self._b_cambiar = Boton(tr('Cambiar sonido…'), self._cambiar_sonido, alto=30, tam=12)
        cs.addWidget(self._b_cambiar)
        self._b_original = Boton(tr('Viral Hooks Riser'), self._sonido_original, tipo='fantasma', alto=30, tam=12)
        Tooltip(self._b_original, tr('Volver al sonido que trae el programa (los últimos 2 segundos del Viral Hooks Riser, que acaban en su pico).'))
        cs.addWidget(self._b_original)
        t1.capa.addWidget(fila_s)
        fila1, c1 = caja_h(espacio=12)
        self._c_intro = {}
        for ident, nombre, detalle in [('', tr('Sin intro'), tr('El video empieza limpio.'))] + [(i, tr(n), tr(d)) for i, n, d in F.INTROS]:
            self._c_intro[ident] = self._carta(ident, nombre, detalle, 'intro', c1)
        c1.addStretch(1)
        t1.capa.addWidget(fila1)
        self._f_zoom_intro = self._fila(t1.capa, 'zoomintro', tr('Zoom en la intro'), tr('El cuadro se acerca mientras sube el riser y se suelta de golpe, con el destello, justo en su pico.'),
                                        self._niveles(tr('Sin zoom'), tr('El cuadro no se acerca.'), tr('Un acercamiento discreto.'), tr('Un acercamiento claro.'), tr('Un acercamiento grande.')),
                                        op.get('fx_intro_zoom'), 'fx_intro_zoom')
        capa.addWidget(t1)
        self._pintar_unico(self._c_intro, self._intro)
        self._refrescar_sonido()
        # ---- transiciones
        self._cortes = op.get('fx_cortes') or ''
        t2 = self._tarjeta(tr('Transiciones en los cortes'), tr('Se detecta cada salto entre tomas del video y se esconde con un efecto.'))
        self._f_cortes = self._fila(t2.capa, 'cuantoscortes', tr('Cuántos cortes'), tr('Cuántos de los cortes del video llevan transición.'),
                                    [('pocos', tr('Pocos'), tr('Solo los cortes más marcados.'), False), ('normal', tr('Normales'), tr('Un buen puñado de cortes.'), False),
                                     ('todos', tr('Todos'), tr('Todos los cortes del video.'), False)], op.get('fx_cortes_cuanto'), 'fx_cortes_cuanto', defecto='pocos')
        self._sonidos_corte = (('auto', tr('Automático')), ('shutter', tr('Obturador')), ('whoosh', tr('Whoosh')), ('ninguno', tr('Sin sonido')))
        fila2s, c2s = caja_h(espacio=10)
        c2s.addWidget(Etiqueta(tr('Sonido de la transición'), 13, color=TEXT_MUTED))
        self._v_corte_sonido = StringVar(self._texto_cuanto(op.get('fx_sonido_corte') or 'auto', self._sonidos_corte))
        seg_cs = Segmentado([t for _k, t in self._sonidos_corte], self._v_corte_sonido, self._cambio_corte_sonido, alto=32, tam=13)
        Tooltip(seg_cs, tr('Automático: el destello suena como el disparo de una cámara (Shuter 11 y 13) y las demás transiciones con un whoosh o un glitch. El clic o el pico del sonido cae justo en el corte.'))
        c2s.addWidget(seg_cs)
        c2s.addStretch(1)
        t2.capa.addWidget(fila2s)
        fila2, c2 = caja_h(espacio=12)
        self._c_cortes = {}
        for ident, nombre, detalle in [('', tr('Sin transición'), tr('Los cortes quedan secos.'))] + [(i, tr(n), tr(d)) for i, n, d in F.TRANSICIONES]:
            self._c_cortes[ident] = self._carta(ident, nombre, detalle, 'corte', c2)
        c2.addStretch(1)
        t2.capa.addWidget(fila2)
        capa.addWidget(t2)
        self._pintar_unico(self._c_cortes, self._cortes)
        # ---- movimiento del video (Fusion)
        t4 = self._tarjeta(tr('Movimiento del video'), tr('Se aplica al propio video con una composición de Fusion: tu corrección de color sigue valiendo y no se duplica nada. Zoom lento todo el rato, temblor en los golpes de sonido y, si el video no llena el cuadro, un fondo desenfocado.'))
        self._f_zoom = self._fila(t4.capa, 'zoom', tr('Zoom lento'), tr('El cuadro crece poco a poco durante todo el video (en el ejemplo se ve acelerado).'),
                                  self._niveles(tr('Sin zoom'), tr('El cuadro no se mueve.'), tr('Crece despacio, casi sin notarse.'), tr('Crece poco a poco.'), tr('Crece de forma notoria.')), op.get('fx_zoom'), 'fx_zoom')
        self._f_temblor = self._fila(t4.capa, 'temblor', tr('Temblor en los golpes'), tr('El cuadro se sacude un instante con cada golpe de sonido.'),
                                     self._niveles(tr('Sin temblor'), tr('El cuadro no se sacude.'), tr('Un golpecito discreto.'), tr('Un golpe claro con cada sonido.'), tr('Un golpe fuerte y marcado.')), op.get('fx_temblor'), 'fx_temblor')
        self._f_fondo = self._fila(t4.capa, 'fondo', tr('Si el video no llena el cuadro'), tr('Por ejemplo un video horizontal en un timeline vertical.'),
                                   [('no', tr('Barras negras'), tr('Se ven barras negras arriba y abajo.'), False), ('si', tr('Fondo desenfocado'), tr('Una copia desenfocada llena el cuadro.'), False)],
                                   'si' if bool(op.get('fx_fondo', True)) else 'no', None, guardar=lambda k: _guardar({'fx_fondo': k == 'si'}))
        capa.addWidget(t4)
        # ---- ritmo: quitar pausas (jump cuts) y zoom alterno
        t5 = self._tarjeta(tr('Ritmo: quitar pausas'), tr('GO corta los silencios del video en Resolve (los tramos con voz quedan pegados) ANTES de poner los captions, que ya salen con los tiempos nuevos. Solo en el video que sueltas en Inicio: nunca toca un timeline tuyo.'))
        self._f_pausas = self._fila(t5.capa, 'pausas', tr('Quitar pausas'), tr('Los silencios se cortan y los tramos con voz quedan pegados (en el ejemplo, las pausas rojas de la línea de tiempo se cierran).'),
                                    [('no', tr('No quitar'), tr('El video queda tal cual.')), ('suave', tr('Pocas pausas'), tr('Solo las pausas más largas.'), False),
                                     ('normal', tr('Normal'), tr('Las pausas normales y largas.'), False), ('fuerte', tr('Todas'), tr('Todas las pausas, sin respirar.'), False)], op.get('fx_pausas'), 'fx_pausas')
        self._f_saltos = self._fila(t5.capa, 'saltos', tr('Zoom alterno en cada corte'), tr('Con las pausas quitadas, el cuadro se acerca en un tramo sí y en el siguiente no, para que el corte seco parezca intencionado.'),
                                    self._niveles(tr('Sin zoom'), tr('Todos los tramos igual.'), tr('Un acercamiento discreto.'), tr('Un acercamiento claro.'), tr('Un acercamiento grande.')), op.get('fx_zoom_saltos'), 'fx_zoom_saltos')
        capa.addWidget(t5)
        # ---- iconos
        self._iconos = set(op.get('fx_iconos') or [])
        t3 = self._tarjeta(tr('Iconos flotantes'), tr('Salen iconos animados cuando se dice una palabra que tú eliges (haz clic en un pack para escribirlas) y, si quieres, también en las frases importantes: un número, un aviso, una pregunta o el gancho.'))
        fila3g, c3g = caja_h(espacio=14)
        self._var_iconos_on = ui.BooleanVar(bool(op.get('fx_iconos_activo', True)))
        self._sw_iconos = Interruptor(tr('Iconos flotantes'), self._var_iconos_on, self._cambio_iconos_on, tam=14, color='#FFFFFF')
        c3g.addWidget(self._sw_iconos)
        self._var_extra = ui.BooleanVar(bool(op.get('fx_iconos_extra', True)))
        self._sw_extra = Interruptor(tr('También en frases importantes'), self._var_extra, self._cambio_extra, tam=13, color='#E0EBFB')
        c3g.addWidget(self._sw_extra)
        c3g.addStretch(1)
        t3.capa.addWidget(fila3g)
        self._v_iconos = StringVar(self._texto_cuanto(op.get('fx_iconos_cuanto'), (('pocos', tr('Pocos')), ('normal', tr('Normales')), ('muchos', tr('Muchos')))))
        fila3a, c3a = caja_h(espacio=10)
        c3a.addWidget(Etiqueta(tr('Cuántos iconos'), 13, color=TEXT_MUTED))
        c3a.addWidget(Segmentado([tr('Pocos'), tr('Normales'), tr('Muchos')], self._v_iconos, self._cambio_iconos, alto=32, tam=13))
        c3a.addStretch(1)
        t3.capa.addWidget(fila3a)
        fila3, c3 = caja_h(espacio=12)
        self._c_iconos = {}
        for ident, nombre, detalle in F.PACKS_ICONOS:
            self._c_iconos[ident] = self._carta(ident, tr(nombre), tr(detalle), 'iconos', c3, pack=True)
        c3.addStretch(1)
        t3.capa.addWidget(fila3)
        capa.addWidget(t3)
        for ident, c in self._c_iconos.items():
            c.poner_seleccionada(ident in self._iconos)
        self._aplicar_iconos_on()
        # ---- más efectos (plegados tras un botón: números, pegatinas, énfasis, ambiente, cierre y mis efectos)
        from efectos_extra_ui import SeccionExtras
        self._mas = SeccionExtras()                    # v5.4.23: siempre a la vista (antes plegado: había efectos activos que no se veían)
        self._tarjetas.extend(self._mas.tarjetas)
        capa.addWidget(self._mas)
        capa.addStretch(1)
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)
        self._reloj.start(self.TIC_MS)

    # -- construcción
    def _tarjeta(self, titulo, descripcion):
        t = Tarjeta(espacio=12, margenes=(22, 18, 22, 18))
        t.capa.addWidget(Etiqueta(titulo, 18, peso='medio', color='#FFFFFF'))
        t.capa.addWidget(Etiqueta(descripcion, 13, color=TEXT_MUTED, envolver=True))
        return t

    @staticmethod
    def _niveles(nombre_no, detalle_no, d_suave, d_normal, d_fuerte):
        return [('no', nombre_no, detalle_no), ('suave', tr('Suave'), d_suave, False), ('normal', tr('Normal'), d_normal, False), ('fuerte', tr('Fuerte'), d_fuerte, False)]

    def _fila(self, capa, tipo, titulo, ayuda, opciones, actual, pref, defecto='no', guardar=None):
        """Un ajuste con su ejemplo: título, una línea de ayuda y la fila de tarjetas animadas (una por opción). Lo que se toca se guarda en la preferencia `pref`."""
        capa.addWidget(Etiqueta(titulo, 15, peso='medio', color='#E0EBFB'))
        if ayuda:
            capa.addWidget(Etiqueta(ayuda, 12, color=TEXT_MUTED, envolver=True))
        validas = {o[0] for o in opciones}
        fila = FilaCartas(tipo, opciones, actual if actual in validas else defecto, guardar or (lambda k, p=pref: _guardar({p: k})))
        capa.addWidget(fila)
        self._tarjetas.extend(fila.tarjetas)
        return fila

    def _carta(self, ident, nombre, detalle, tipo, capa, pack=False):
        previa = poster = None
        carpeta = F.carpeta_efectos() / 'previas'
        nombre_archivo = (f'{tipo}_{ident}' if tipo != 'iconos' else f'iconos_{ident}') if ident else None
        if nombre_archivo:
            m, j = carpeta / f'{nombre_archivo}.mp4', carpeta / f'{nombre_archivo}.jpg'
            previa = m if m.is_file() else None
            poster = j if j.is_file() else None
        c = TarjetaEfecto(ident, nombre, detalle, previa, poster, ninguna=not ident, pack=pack)
        if pack:
            c.clic.connect(self._abrir_palabras)
            c.cambio.connect(self._pack_activo)
        else:
            c.clic.connect(lambda i, t=tipo: self._tocar(t, i))
        capa.addWidget(c)
        self._tarjetas.append(c)
        return c

    @staticmethod
    def _texto_cuanto(clave, opciones):
        return next((t for k, t in opciones if k == clave), opciones[0][1])

    @staticmethod
    def _pintar_unico(cartas, elegido):
        for ident, c in cartas.items():
            c.poner_seleccionada(ident == (elegido or ''))

    # -- cambios
    def refrescar(self):
        """Al volver a la página: el interruptor general puede haberse movido desde el chip de Inicio y, desde la v5.5, las opciones pueden haber cambiado al elegir un estilo
        (la recomendación de cada estilo deja la intro, el zoom, las transiciones y los iconos ya configurados): se vuelve a leer todo."""
        try:
            op = F.opciones_guardadas()
            for fila, clave in ((self._f_zoom_intro, 'fx_intro_zoom'), (self._f_zoom, 'fx_zoom'), (self._f_temblor, 'fx_temblor'), (self._f_saltos, 'fx_zoom_saltos'),
                                (self._f_pausas, 'fx_pausas'), (self._f_cortes, 'fx_cortes_cuanto')):
                fila.poner(op.get(clave))
            self._f_fondo.poner('si' if bool(op.get('fx_fondo', True)) else 'no')
            self._v_iconos.set(self._texto_cuanto(op.get('fx_iconos_cuanto'), (('pocos', tr('Pocos')), ('normal', tr('Normales')), ('muchos', tr('Muchos')))))
            self._v_corte_sonido.set(self._texto_cuanto(op.get('fx_sonido_corte') or 'auto', self._sonidos_corte))
            self._intro, self._cortes = op.get('fx_intro') or '', op.get('fx_cortes') or ''
            self._pintar_unico(self._c_intro, self._intro)
            self._pintar_unico(self._c_cortes, self._cortes)
            self._var_iconos_on.set(bool(op.get('fx_iconos_activo', True)))
            self._var_extra.set(bool(op.get('fx_iconos_extra', True)))
            self._iconos = set(op.get('fx_iconos') or [])
            for ident, c in self._c_iconos.items():
                c.poner_seleccionada(ident in self._iconos)
            self._aplicar_iconos_on()
            self._refrescar_sonido()
            self._mas.refrescar()
        except Exception:
            pass

    def _tocar(self, tipo, ident):
        if tipo == 'intro':
            self._intro = ident
            _guardar({'fx_intro': ident})
            self._pintar_unico(self._c_intro, ident)
        else:
            self._cortes = ident
            _guardar({'fx_cortes': ident})
            self._pintar_unico(self._c_cortes, ident)

    def _abrir_vista_previa(self):
        if self._dialogo is not None and ui.vivo(self._dialogo):
            self._dialogo.close()
        self._dialogo = DialogoVistaPrevia(self.window())
        self._dialogo.show()

    def _cambio_corte_sonido(self, _v=None):
        _guardar({'fx_sonido_corte': {t: k for k, t in self._sonidos_corte}.get(self._v_corte_sonido.get(), 'auto')})

    # -- el sonido de la intro
    def _refrescar_sonido(self):
        op = F.opciones_guardadas()
        f = F.fuente_sonido_intro(op)
        on = f is not None
        if bool(self._var_sonido.get()) != on:
            self._var_sonido.set(on)
        de_fabrica = str(op.get('fx_intro_sonido') or 'viral_hooks_riser') in {i for i, _n, _a in F.SONIDOS_INTRO}
        self._lbl_sonido.configure(text=(F.nombre_sonido_intro(op) + (' · ' + tr('últimos 2 s') if de_fabrica else ''))
                                   if on else tr('Silenciado'))
        self._b_oir.setEnabled(on)
        self._b_original.setVisible(on and str(op.get('fx_intro_sonido') or 'viral_hooks_riser') != 'viral_hooks_riser')

    def _cambio_sonido_on(self):
        if self._var_sonido.get():
            actual = F.opciones_guardadas().get('fx_intro_sonido')
            _guardar({'fx_intro_sonido': 'viral_hooks_riser' if str(actual or 'ninguno').lower() in ('ninguno', '') else actual})
        else:
            _guardar({'fx_intro_sonido': 'ninguno'})
        self._refrescar_sonido()

    def _cambiar_sonido(self):
        try:
            ruta = ui.filedialog.askopenfilename(title=tr('Elige el sonido de la intro'), filetypes=[(tr('Audio'), '*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.aiff *.aif'), (tr('Todos'), '*.*')],
                                                 parent=self.window())
        except Exception:
            ruta = ''
        if ruta:
            _guardar({'fx_intro_sonido': str(ruta)})
            self._refrescar_sonido()

    def _sonido_original(self):
        _guardar({'fx_intro_sonido': 'viral_hooks_riser'})
        self._refrescar_sonido()

    def _oir_sonido(self):
        try:
            F.oir_sonido_intro()
        except Exception:
            pass

    # -- los iconos
    def _aplicar_iconos_on(self):
        apagados = not bool(self._var_iconos_on.get())
        for c in self._c_iconos.values():
            c.poner_apagada(apagados)
        self._sw_extra.setEnabled(not apagados)

    def _cambio_iconos_on(self):
        _guardar({'fx_iconos_activo': bool(self._var_iconos_on.get())})
        self._aplicar_iconos_on()

    def _cambio_extra(self):
        _guardar({'fx_iconos_extra': bool(self._var_extra.get())})

    def _pack_activo(self, ident, activo):
        if activo:
            self._iconos.add(ident)
        else:
            self._iconos.discard(ident)
        _guardar({'fx_iconos': [p for p, _n, _d in F.PACKS_ICONOS if p in self._iconos]})

    def _abrir_palabras(self, ident):
        nombre = next((tr(n) for p, n, _d in F.PACKS_ICONOS if p == ident), ident)
        if self._dialogo is not None and ui.vivo(self._dialogo):
            self._dialogo.close()
        self._dialogo = DialogoPalabras(self.window(), ident, nombre, self._guardar_palabras)
        self._dialogo.show()

    def _guardar_palabras(self, pack, lista):
        propias = dict(F.opciones_guardadas().get('fx_iconos_palabras') or {})
        if [p.lower() for p in lista] == [p.lower() for p in F.PALABRAS_POR_DEFECTO.get(pack, ())]:
            propias.pop(pack, None)                       # igual que las de fábrica: no hace falta guardarlas
        else:
            propias[pack] = lista
        _guardar({'fx_iconos_palabras': propias})

    def _cambio_iconos(self, _v=None):
        clave = {tr('Pocos'): 'pocos', tr('Normales'): 'normal', tr('Muchos'): 'muchos'}.get(self._v_iconos.get(), 'normal')
        _guardar({'fx_iconos_cuanto': clave})

    # -- las vistas previas solo se mueven mientras se ven
    def _tic(self):
        visible_pagina = self.isVisible()
        for c in self._tarjetas:
            v = visible_pagina and not c.visibleRegion().isEmpty()
            c.poner_visible(v)
            if v:
                c.update()
