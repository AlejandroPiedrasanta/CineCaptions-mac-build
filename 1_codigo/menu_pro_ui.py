# CineCaptions · By Cinema Productions
# 1_codigo/menu_pro_ui.py — el panel del chip «Edición PRO» de Inicio: interruptor y una fila por ajuste.
"""
El usuario («mejora esto, dame propuestas» → eligió la C): en vez de la lista larga de píldoras (activar, 7 «Estilo de video», 3 «Persona», 3
«Animación», «Otra combinación»), un panel con «Edición PRO» y su interruptor arriba y una fila por ajuste:

    Tipo de video          [Automático ⌄]        (un ui.Menu con edicion_pro.NOMBRES_GENERO)
    Persona                [Recorte con IA ⌄]    (IA local · Magic Mask —solo con Studio— · sin recortar)
    Animación              [Sobria | Media | Espectáculo]
    Colores y tipografías  [Otra combinación]    (debajo, «Combinación N»)

    abrir(padre, leer, poner, alternar, studio, ancla=None) -> PanelPro (ya visible)
        leer() -> (opciones, activa) · poner(clave, valor) guarda (y enciende la PRO) · alternar() la enciende o apaga · studio: ¿Magic Mask?

El panel se queda abierto mientras se ajusta (cada cambio se guarda al momento y el panel se vuelve a leer); un clic fuera o Esc lo cierra.
Fondo, sombra y colocación: los de menu_estilo_ui. Sin tooltips ni efectos Qt.
"""
from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
import menu_estilo_ui as ME
from i18n import tr

ANCHO = 400                     # el panel (sin la sombra)
ALTO_FILA = 52
MAX_VALOR = 190                 # lo más ancho que puede ser el valor de una lista («Inmobiliaria / venta de casas» se recorta con …)
DENSIDADES = ('sobria', 'media', 'espectaculo')


def _tras_dos_puntos(texto):
    """«Animación: media» → «Media» en el idioma de la app (reutiliza las traducciones del menú de antes; «Media» suelta es «Middle»)."""
    t = str(texto)
    for sep in (':', '：'):
        if sep in t:
            t = t.split(sep, 1)[1]
    t = t.strip()
    return t[:1].upper() + t[1:]


def _persona():
    """[(clave, corto, largo)] del recorte de la persona."""
    return [('auto', tr('Recorte con IA'), _tras_dos_puntos(tr('Persona: recorte con IA local (recomendado)'))),
            ('magic', 'Magic Mask', _tras_dos_puntos(tr('Persona: Magic Mask de Resolve Studio (más pesado)'))),
            ('no', _tras_dos_puntos(tr('Persona: sin recortar')), _tras_dos_puntos(tr('Persona: sin recortar')))]


class Icono(QWidget):
    """Un icono Phosphor dentro de una cajita redondeada (la corona dorada de arriba y los de cada fila)."""
    def __init__(self, nombre, caja=30, tam=16, color=None, fondo=None, borde=None, padre=None):
        super().__init__(padre)
        self._nombre, self._tam = nombre, int(tam)
        self._color, self._fondo, self._borde = color, fondo, borde
        self._pm = {}
        self.setFixedSize(int(caja), int(caja))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        p.setPen(QPen(self._borde, 1.0) if self._borde is not None else Qt.PenStyle.NoPen)
        p.setBrush(self._fondo if self._fondo is not None else QColor(255, 255, 255, 13))
        rad = 12.0 if self.width() >= 36 else 9.0
        p.drawRoundedRect(r, rad, rad)
        color = QColor(self._color) if self._color is not None else QColor('#9FB0C9')
        dpr = self.devicePixelRatioF()
        clave = (color.name(), round(dpr, 2))
        if clave not in self._pm:
            ic = ui.icono_linea(self._nombre, color.name())
            self._pm[clave] = ic.pixmap(QSize(self._tam, self._tam), dpr) if ic is not None else None
        pm = self._pm[clave]
        if pm is not None and not pm.isNull():
            p.drawPixmap(int((self.width() - self._tam) / 2), int((self.height() - self._tam) / 2), pm)
        p.end()


class BotonValor(QAbstractButton):
    """El valor de una fila: una pastilla con el texto en negrita y, si `lista`, el chevrón (abre un ui.Menu). `acento`: en el color del tema."""
    ALTO = 32

    def __init__(self, texto, lista=True, acento=False, padre=None):
        super().__init__(padre)
        self._lista, self._acento, self._h = bool(lista), bool(acento), False
        self._f = ui.fuente(13, peso='negrita')
        self.setText(str(texto))
        self.setFixedHeight(self.ALTO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def poner(self, texto):
        self.setText(str(texto))
        self.updateGeometry()
        self.update()

    def _ancho_texto(self):
        return min(float(MAX_VALOR), QFontMetricsF(self._f).horizontalAdvance(self.text()))

    def sizeHint(self):
        return QSize(int(12 + self._ancho_texto() + (8 + 9 if self._lista else 0) + 12) + 1, self.ALTO)

    def minimumSizeHint(self):
        return self.sizeHint()

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
        acento = QColor(ui.ACCENT_CLARO)
        r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        borde = QColor(acento) if self._acento else QColor('#2A3854')
        borde.setAlpha(150 if self._acento and not self._h else 255)
        if self._h and not self._acento:
            borde = QColor('#3A4D72')
        p.setPen(QPen(borde, 1.0))
        p.setBrush(QColor(255, 255, 255, 14 if self._h else 8))
        p.drawRoundedRect(r, 10, 10)
        p.setFont(self._f)
        p.setPen(acento if self._acento else QColor('#FFFFFF'))
        w = self._ancho_texto()
        texto = QFontMetricsF(self._f).elidedText(self.text(), Qt.TextElideMode.ElideRight, w + 1)
        p.drawText(QRectF(12, 0, w + 2, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
        if self._lista:
            x, cy = 12 + w + 8, self.height() / 2.0
            p.setPen(QPen(QColor(ui.TEXT_MUTED), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(QPointF(x, cy - 2.0), QPointF(x + 4.0, cy + 2.0))
            p.drawLine(QPointF(x + 4.0, cy + 2.0), QPointF(x + 8.0, cy - 2.0))
        p.end()


class Fila(QWidget):
    """Icono · nombre (y un texto pequeño debajo, si hay) · el control a la derecha; con la línea de abajo salvo la última."""
    def __init__(self, icono, nombre, control, linea=True, padre=None):
        super().__init__(padre)
        self._linea = bool(linea)
        self.setFixedHeight(ALTO_FILA)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(12)
        capa.addWidget(Icono(icono))
        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(1)
        self.nombre = QLabel(str(nombre))
        self.nombre.setFont(ui.fuente(13))
        self.nombre.setStyleSheet(f'color: {QColor("#D2DCEB").name()}; background: transparent;')
        self.sub = QLabel('')
        self.sub.setFont(ui.fuente(11))
        self.sub.setStyleSheet(f'color: {QColor(ui.TEXT_MUTED).name()}; background: transparent;')
        self.sub.hide()
        textos.addStretch(1)
        textos.addWidget(self.nombre)
        textos.addWidget(self.sub)
        textos.addStretch(1)
        capa.addLayout(textos, 1)
        capa.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

    def poner_sub(self, texto):
        self.sub.setText(str(texto or ''))
        self.sub.setVisible(bool(texto))

    def paintEvent(self, _e):
        if self._linea:
            p = QPainter(self)
            p.setPen(QPen(QColor(ui.BORDER_COLOR), 1.0))
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
            p.end()


class PanelPro(QWidget):
    def __init__(self, padre, leer, poner, alternar, studio):
        super().__init__(padre, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._leer, self._poner, self._alternar, self._studio = leer, poner, alternar, bool(studio)
        self.al_cerrar = None
        import edicion_pro
        self._generos = list(edicion_pro.NOMBRES_GENERO.items())
        S = ME.SOMBRA
        capa = QVBoxLayout(self)
        capa.setContentsMargins(S + 16, S + 16, S + 16, S + 8)
        capa.setSpacing(0)
        # cabecera: la corona, «Edición PRO» + qué hace, el interruptor
        cab = QHBoxLayout()
        cab.setContentsMargins(0, 0, 0, 14)
        cab.setSpacing(12)
        ambar = QColor(ui.AMBAR)
        fondo, borde = QColor(ambar), QColor(ambar)
        fondo.setAlpha(33)
        borde.setAlpha(90)
        cab.addWidget(Icono('ph.crown', caja=38, tam=20, color=ambar, fondo=fondo, borde=borde))
        tit = QVBoxLayout()
        tit.setContentsMargins(0, 0, 0, 0)
        tit.setSpacing(2)
        t = QLabel(tr('Edición PRO'))
        t.setFont(ui.fuente(16, peso='negrita'))
        t.setStyleSheet(f'color: {QColor(ui.TEXT_COLOR).name()}; background: transparent;')
        s = QLabel(tr('Intro, gancho y motion graphics'))
        s.setFont(ui.fuente(12))
        s.setStyleSheet(f'color: {QColor(ui.TEXT_MUTED).name()}; background: transparent;')
        tit.addWidget(t)
        tit.addWidget(s)
        cab.addLayout(tit, 1)
        self.interruptor = ui.Interruptor('', comando=self._al_interruptor)
        cab.addWidget(self.interruptor, 0, Qt.AlignmentFlag.AlignVCenter)
        capa.addLayout(cab)
        linea = QWidget()
        linea.setFixedHeight(1)
        linea.setStyleSheet(f'background: {QColor(ui.BORDER_COLOR).name()};')
        capa.addWidget(linea)
        # las filas
        self.b_tipo = BotonValor('', acento=True)
        self.b_tipo.clicked.connect(self._lista_tipo)
        self.b_persona = BotonValor('')
        self.b_persona.clicked.connect(self._lista_persona)
        self._etq_dens = [_tras_dos_puntos(tr(n)) for n in ('Animación: sobria', 'Animación: media', 'Animación: espectáculo')]
        self.seg = ui.Segmentado(self._etq_dens, comando=self._al_densidad, alto=32, tam=12.5)
        self.b_var = BotonValor(tr('Otra combinación'), lista=False)
        self.b_var.clicked.connect(self._otra)
        self.f_tipo = Fila('ph.video-camera', tr('Tipo de video'), self.b_tipo)
        self.f_persona = Fila('ph.user-focus', tr('Persona'), self.b_persona)
        self.f_anim = Fila('ph.lightning', tr('Animación'), self.seg)
        self.f_var = Fila('ph.shuffle', tr('Colores y tipografías'), self.b_var, linea=False)
        for f in (self.f_tipo, self.f_persona, self.f_anim, self.f_var):
            capa.addWidget(f)
        self._refrescar(animar=False)
        self.setFixedWidth(ANCHO + 2 * S)
        self.adjustSize()
        self._a = QPropertyAnimation(self, b'windowOpacity', self)
        self._a.setDuration(150)
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -- estado ------------------------------------------------------------------------------------------------------------------------------
    def _estado(self):
        try:
            op, activa = self._leer()
            return dict(op or {}), bool(activa)
        except Exception:
            return {}, False

    def _refrescar(self, animar=True):
        op, activa = self._estado()
        if self.interruptor.isChecked() != activa:
            self.interruptor.blockSignals(True)
            self.interruptor.setChecked(activa)
            self.interruptor.blockSignals(False)
            if animar:
                self.interruptor._animar(activa)
            else:                                       # (al abrir, ya en su sitio: sin la bolita viajando)
                self.interruptor._pos = 1.0 if activa else 0.0
                self.interruptor._res.poner(self.interruptor._pos)
                self.interruptor.update()
        genero = op.get('pro_genero', 'auto')
        self.b_tipo.poner(tr(dict(self._generos).get(genero, dict(self._generos).get('auto', ''))))
        masc = str(op.get('pro_mascara', 'auto') or 'auto')
        masc = 'auto' if masc == 'ia' else masc
        self.b_persona.poner(next((corto for c, corto, _l in _persona() if c == masc), _persona()[0][1]))
        dens = op.get('pro_densidad', 'media')
        self.seg.set(self._etq_dens[DENSIDADES.index(dens)] if dens in DENSIDADES else self._etq_dens[1])
        self._var = int(op.get('pro_variacion') or 0)
        self.f_var.poner_sub(tr('Combinación {n}', n=self._var + 1))
        for b in (self.b_tipo, self.b_persona, self.b_var):
            b.adjustSize()

    def _guardar(self, clave, valor):
        try:
            self._poner(clave, valor)
        except Exception:
            pass
        self._refrescar()

    # -- acciones ----------------------------------------------------------------------------------------------------------------------------
    def _al_interruptor(self):
        try:
            self._alternar()
        except Exception:
            pass
        self._refrescar()

    def _lista(self, boton, opciones, actual):
        """Abre un ui.Menu (las píldoras de siempre) debajo del botón; `opciones` = [(clave, texto)]."""
        menu = ui.Menu(self)
        for clave, texto in opciones:
            menu.agregar(('✓  ' if clave == actual else '      ') + texto, lambda c=clave, b=boton: self._elegido(b, c))
        menu.mostrar(boton.mapToGlobal(QPoint(0, boton.height() + 6)), ancla=boton)     # (v5.84: pulsar otra vez el botón la cierra)

    def _elegido(self, boton, clave):
        self._guardar('pro_genero' if boton is self.b_tipo else 'pro_mascara', clave)

    def _lista_tipo(self):
        op, _a = self._estado()
        self._lista(self.b_tipo, [(c, tr(n)) for c, n in self._generos], op.get('pro_genero', 'auto'))

    def _lista_persona(self):
        op, _a = self._estado()
        masc = str(op.get('pro_mascara', 'auto') or 'auto')
        masc = 'auto' if masc == 'ia' else masc
        self._lista(self.b_persona, [(c, largo) for c, _corto, largo in _persona() if c != 'magic' or self._studio], masc)

    def _al_densidad(self, etiqueta):
        if etiqueta in self._etq_dens:
            self._guardar('pro_densidad', DENSIDADES[self._etq_dens.index(etiqueta)])

    def _otra(self):
        self._guardar('pro_variacion', self._var + 1)

    # -- ventana -----------------------------------------------------------------------------------------------------------------------------
    def mostrar(self, ancla=None):
        ME.colocar(self, ancla)
        self.setWindowOpacity(0.0)
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self._a.start()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def hideEvent(self, e):
        if callable(self.al_cerrar):
            try:
                self.al_cerrar()
            except Exception:
                pass
            self.al_cerrar = None
        super().hideEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        S = ME.SOMBRA
        ME.pintar_fondo(p, QRectF(S + 0.5, S + 0.5, self.width() - 2 * S - 1.0, self.height() - 2 * S - 1.0))
        p.end()


def abrir(padre, leer, poner, alternar, studio, ancla=None):
    """Abre el panel encima del chip `ancla` (si lo hay) y lo devuelve; el chip, mientras tanto, con el borde lleno."""
    panel = PanelPro(padre, leer, poner, alternar, studio)
    if ancla is not None and hasattr(ancla, 'poner_abierto'):
        ancla.poner_abierto(True)
        panel.al_cerrar = lambda: ancla.poner_abierto(False)
    ui.no_reabrir(panel, ancla)                  # v5.84: volver a pulsar el chip lo cierra (antes se cerraba y se abría otra vez)
    panel.mostrar(ancla)
    return panel
