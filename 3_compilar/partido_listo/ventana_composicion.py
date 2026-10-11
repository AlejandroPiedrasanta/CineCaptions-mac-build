# CineCaptions · By Cinema Productions
# 1_codigo/ventana_composicion.py — La ventana «Composición» (estilo del bloque; sin uso visible desde la 5.1).
"""
ventana_composicion.py
----------------------
La ventana «Composición» (estilo del bloque; sin uso visible desde la 5.1).

Salió de «CineCaptions (script principal).py» (v5.4.44) SIN cambiar su código: el principal conserva la ventana principal (SubtitleApp) y vuelve a importar estos nombres, así que `cc_main.NombreDeClase` sigue existiendo.
"""
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, QVariantAnimation, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
import qt_kit as ui
from qt_kit import Boton, Chip, Deslizador, Etiqueta, MarcoVista, Segmentado, StringVar, Tarjeta, Tooltip, caja_h, vivo
from qt_kit import QColor, QColorReal
from i18n import tr
import plantillas
import composicion
from ui_comun import (ACCENT, BORDER_COLOR, TEXT_MUTED, estilo_fijo, fuente, lineas_de_vista, poner_estilo_fijo, resumen_composicion)
class _TileLayout(QWidget):
    """Un layout de la rejilla de Composicion: tres barras (contexto blanco,
    principal ambar, complemento violeta) alineadas como quedaran."""
    def __init__(self, ventana, codigo):
        super().__init__()
        self._v = ventana
        self.codigo = codigo
        self.activo = False
        self._hover = False
        self.setMinimumSize(96, 88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(88)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)
    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._v._poner_layout(self.codigo)
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        borde = ACCENT if self.activo else ('#2E5BCC' if self._hover else BORDER_COLOR)
        p.setPen(QPen(QColor(borde), 2 if self.activo else 1))
        p.setBrush(QColor('#10224A' if self.activo else ui.CARD_2))
        p.drawRoundedRect(r, 10, 10)
        lc, ld = composicion.lados(self.codigo)
        w = r.width()
        w_main, w_ctx, w_cmp = (0.56 * w, 0.28 * w, 0.4 * w)
        cx = r.center().x()
        # v5.3: el icono o la imagen va debajo del texto (bloque «imagen») o encima, segun «Icono o imagen»
        arriba_ico = False
        try:
            arriba_ico = self._v._donde_icono() == 'arriba'
        except Exception:
            pass
        y0 = 0.18 if arriba_ico else 0.0
        ComposicionWindow._barra(p, cx, r.top() + (0.40 + y0) * r.height(), w_main, 10, ui.ROL_PRINCIPAL)
        ComposicionWindow._barra(p, cx + composicion.desplazamiento_layout(lc, w_main, w_ctx), r.top() + (0.22 + y0) * r.height(), w_ctx, 6, ui.ROL_CONTEXTO)
        ComposicionWindow._barra(p, cx + composicion.desplazamiento_layout(ld, w_main, w_cmp), r.top() + (0.56 + y0) * r.height(), w_cmp, 6, ui.ROL_COMPLEMENTO)
        verde = QColor(ui.ROL_IMAGEN)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(verde)
        p.drawEllipse(QPointF(cx, r.top() + (0.15 if arriba_ico else 0.76) * r.height()), 6.5, 6.5)
        p.setFont(fuente(10))
        p.setPen(QColor('#5A6B87'))
        p.drawText(QRectF(r.left() + 8, r.bottom() - 18, 40, 16), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.codigo)
        p.end()
class _MiniVariante(MarcoVista):
    """v5.5: la miniatura de UNA variante del pack (con su tipografia y su color): se ve de un vistazo cual elegir y un clic la lleva a la vista."""
    def __init__(self, ventana, k, lineas, activa):
        super().__init__(alto_min=58, aprox=False)
        self._v = ventana
        self._k_var = k
        self._activa = bool(activa)
        self.setFixedSize(92, 62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.poner(lineas)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._v._ir_a_variante(self._k_var)
    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(ui.ACCENT_CLARO if self._activa else '#2A3A58'), 2.2 if self._activa else 1.0))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        p.end()
class _PreviaComposicion(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self._v = ventana
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(190)
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = self._v._pag_t
        if k < 1.0:                      # al pasar de estilo el cuadro entra deslizando desde el lado de la flecha
            e = 1.0 - (1.0 - k) ** 3
            p.translate((1.0 - e) * 28.0 * self._v._pag_dir, 0)
            p.setOpacity(0.25 + 0.75 * e)
        self._v._dibujar_previa(p, self.width(), self.height())
        p.end()
class ComposicionWindow(QWidget):
    """«Composición» (v3.4.0; la referencia del usuario: otro plugin con
    «COMPOSIÇÃO / LAYOUTS»): los 9 layouts + AUTO (la alineacion horizontal
    de contexto y complemento respecto a la principal — el orden vertical lo
    sigue poniendo la plantilla) y los deslizadores Altura / Horizontal del
    grupo entero. Tocar cualquier control GUARDA la preferencia (generar la
    usa); aplicar a Resolve es explicito: «desde el cabezal» (los bloques
    desde el cabezal hacia adelante; los de antes se quedan) o «a todo».
    Por defecto todo sale como la plantilla (la regla v1.0.32).
    v5.0.0: es el panel derecho de la pantalla «Estilos y composición»; la
    logica no cambia (el modelo vive en composicion.py)."""
    REJILLA = (('ii', 'ic', 'id'), ('ci', 'cc', 'cd'), ('di', 'dc', 'dd'))
    APOYO = '#E0EBFB'
    def __init__(self, master):
        super().__init__()
        self.app = master
        self.valor = composicion.valida(getattr(master, 'composicion', None))
        self._formato = self._formato_previa()
        self._tiles = {}
        self._ocupado = False
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        self.tarjeta = Tarjeta(titulo=tr('Estilo del bloque'), espacio=12)
        capa.addWidget(self.tarjeta)
        t = self.tarjeta.capa
        # la vista previa y las flechas de estilo van ARRIBA del todo: lo primero que se ve al elegir una variante
        zona_previa = QWidget()
        arriba = QVBoxLayout(zona_previa)
        arriba.setContentsMargins(0, 0, 0, 0)
        arriba.setSpacing(10)
        t.addWidget(zona_previa)
        # v5.8 (auditoría del flujo): el estilo YA trae su posición exacta; estos controles son un retoque opcional y van plegados en «Ajuste fino»
        self.fino_w = QWidget()
        fv = QVBoxLayout(self.fino_w)
        fv.setContentsMargins(0, 4, 0, 0)
        fv.setSpacing(12)
        fv.addWidget(Etiqueta(tr('El estilo que elegiste ya trae su posición exacta: normalmente no hace falta tocar nada de aquí. Es un retoque opcional: alinear las líneas de apoyo, subir/bajar o mover el grupo, y recolocar los subtítulos que ya están en el timeline.'), 12, color=TEXT_MUTED, envolver=True))
        rejilla = QWidget()
        cr = QGridLayout(rejilla)
        cr.setContentsMargins(0, 4, 0, 0)
        cr.setSpacing(12)
        for fila, codigos in enumerate(self.REJILLA):
            for col, codigo in enumerate(codigos):
                tile = _TileLayout(self, codigo)
                cr.addWidget(tile, fila, col)
                self._tiles[codigo] = tile
        Tooltip(rejilla, tr('A qué borde de la principal se alinea cada línea: filas = arriba, columnas = abajo (izquierda / centro / derecha). El centro es la plantilla tal cual. El icono o la imagen va debajo del texto, o donde lo ponga el bloque «imagen» del pack.'))
        fv.addWidget(rejilla)
        fila_auto, cfa = caja_h(espacio=10)
        self.auto_btn = Chip(tr('AUTO · uno distinto por bloque'), ui.ACCENT_CLARO, self._poner_auto, alto=28)
        Tooltip(self.auto_btn, tr('Un layout distinto en cada bloque.'))
        cfa.addWidget(self.auto_btn)
        self.pista_layout = Etiqueta('', 12, color=TEXT_MUTED)
        cfa.addWidget(self.pista_layout, 1)
        fv.addWidget(fila_auto)
        fv.addSpacing(4)
        self.altura_lbl = self._deslizador(fv, tr('Altura del grupo'), 'altura', tr('Sube o baja el grupo entero (las tres líneas) respecto a donde lo deja la plantilla. 0 = la plantilla.'))
        self.horizontal_lbl = self._deslizador(fv, tr('Horizontal'), 'horizontal', tr('Mueve el grupo entero a los lados. 0 = la plantilla.'))
        # v5.3: dónde va el icono o la imagen, y las flechas para seguir viendo los estilos del pack
        self._vistas = []
        self._k = max(0, estilo_fijo() - 1)
        self._pag_t = 1.0
        self._pag_dir = 1
        self._pag_anim = QVariantAnimation(self)
        self._pag_anim.setDuration(260)
        self._pag_anim.setStartValue(0.0)
        self._pag_anim.setEndValue(1.0)
        self._pag_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pag_anim.valueChanged.connect(self._paso_pagina)
        fila_ico, cfi = caja_h(espacio=10)
        cfi.addWidget(Etiqueta(tr('Icono o imagen'), 14, color='#E0EBFB'))
        self._opciones_icono = {tr('Automático'): '', tr('Abajo'): 'abajo', tr('Arriba'): 'arriba'}
        guardado = ''
        try:
            import ajustes_ui
            guardado = str(ajustes_ui.leer_prefs().get('emoji_posicion') or '')
        except Exception:
            pass
        if guardado not in ('abajo', 'arriba'):
            guardado = ''
        self.icono_var = StringVar(next(k for k, v in self._opciones_icono.items() if v == guardado))
        self.icono_seg = Segmentado(list(self._opciones_icono.keys()), self.icono_var, self._cambio_icono, alto=30, tam=12)
        Tooltip(self.icono_seg, tr('Dónde va el emoji o la imagen de cada bloque. «Automático»: donde lo pone el bloque «imagen» del pack (o debajo del texto si el pack no lo trae). Abajo o Arriba lo fuerzan.'))
        cfi.addStretch(1)
        cfi.addWidget(self.icono_seg)
        t.addWidget(fila_ico)
        self.fino_lnk = ui.Enlace('', self._alternar_fino, 13, color=ui.ACCENT_CLARO, color_hover='#FFFFFF')
        Tooltip(self.fino_lnk, tr('Retoques opcionales sobre el estilo: alineación de las líneas, altura y horizontal del grupo, y recolocar lo que ya está en el timeline.'))
        t.addWidget(self.fino_lnk, 0, Qt.AlignmentFlag.AlignLeft)
        t.addWidget(self.fino_w)
        self.fino_w.hide()
        fila_pag, cfp = caja_h(espacio=8)
        self.pag_ant = Boton('', lambda: self._mover_vista(-1), tipo='icono', alto=30, ancho=34)
        self.pag_sig = Boton('', lambda: self._mover_vista(1), tipo='icono', alto=30, ancho=34)
        for boton, nombre in ((self.pag_ant, 'ph.caret-left-bold'), (self.pag_sig, 'ph.caret-right-bold')):
            icono = ui.icono_linea(nombre, '#C9D6EC')
            if icono is not None:
                boton.setIcon(icono)
                boton.setIconSize(QSize(15, 15))
            else:
                boton.setText('‹' if boton is self.pag_ant else '›')
        Tooltip(self.pag_ant, tr('Estilo anterior'))
        Tooltip(self.pag_sig, tr('Siguiente estilo'))
        self.pag_txt = Etiqueta('', 12, color=TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignCenter)
        cfp.addWidget(self.pag_ant)
        cfp.addWidget(self.pag_txt, 1)
        cfp.addWidget(self.pag_sig)
        self.fijo_chip = Chip('', ui.ACCENT_CLARO, self._alternar_fijo, alto=28)
        Tooltip(self.fijo_chip, tr('«Fijo»: todos los bloques usan este estilo. «Alternando»: cada bloque usa uno distinto del pack.'))
        cfp.addWidget(self.fijo_chip)
        arriba.addWidget(fila_pag)
        self.modo_estilos_lbl = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        arriba.addWidget(self.modo_estilos_lbl)
        self.fila_mini_w = QWidget()
        self.fila_mini = QHBoxLayout(self.fila_mini_w)
        self.fila_mini.setContentsMargins(0, 0, 0, 0)
        self.fila_mini.setSpacing(8)
        arriba.addWidget(self.fila_mini_w)
        self.previa = _PreviaComposicion(self)
        arriba.addWidget(self.previa)
        self.previa_pie = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        arriba.addWidget(self.previa_pie)
        self.aplicar_btn = Boton(tr('Aplicar desde el cabezal'), lambda: self._aplicar('cabezal'), tipo='primario')
        Tooltip(self.aplicar_btn, tr('Mueve en Resolve los subtítulos que ya están puestos, desde donde está el cabezal hacia adelante. Los de antes se quedan como están.'))
        fv.addWidget(self.aplicar_btn)
        fila_b, cfb = caja_h(espacio=10)
        self.todo_btn = Boton(tr('Aplicar a todo'), lambda: self._aplicar('todo'), alto=36)
        cfb.addWidget(self.todo_btn, 1)
        self.reset_btn = Boton(tr('Restablecer'), self._restablecer, alto=36)
        cfb.addWidget(self.reset_btn, 1)
        Tooltip(self.reset_btn, tr('Vuelve a la plantilla tal cual (centro, 0 / 0) y lo aplica a todo.'))
        fv.addWidget(fila_b)
        self.estado = Etiqueta(tr('Se aplica a los textos que ya están en el timeline'), 12, color=TEXT_MUTED, envolver=True, alineacion=Qt.AlignmentFlag.AlignCenter)
        fv.addWidget(self.estado)
        self.aviso_modo = Etiqueta(tr('La composición se aplica a los subtítulos «Dinámicos (3 líneas)».'), 12, color=ui.AMBAR, envolver=True)
        self.aviso_modo.hide()
        t.addWidget(self.aviso_modo)
        self._recalcular_vistas()
        self._refrescar()
    def poner_habilitado(self, si):
        """Solo los Dinamicos tienen tres lineas que alinear."""
        for w in list(self._tiles.values()) + [self.auto_btn, self.aplicar_btn, self.todo_btn, self.reset_btn, self._desl_altura, self._desl_horizontal]:
            w.setEnabled(bool(si) and not self._ocupado)
        self.aviso_modo.setVisible(not si)
    def existe(self):
        return vivo(self)
    # -- v5.3: estilos del pack con el icono arriba o abajo ----------------------------------------------------------
    def _paso_pagina(self, v):
        self._pag_t = float(v)
        self.previa.update()
    def _icono_elegido(self):
        return self._opciones_icono.get(self.icono_var.get(), '')
    def _donde_icono(self, vista=None):
        eleccion = self._icono_elegido()
        if eleccion in ('abajo', 'arriba'):
            return eleccion
        return (vista or {}).get('donde') or (self._vistas[0].get('donde') if self._vistas else None) or 'abajo'
    def _recalcular_vistas(self):
        """Las variantes del pack elegido (una vista cada una); sin pack legible, una sola vista generica."""
        try:
            self._vistas = plantillas.variantes_de(getattr(self.app, 'plantilla_sel', 'auto'), self._formato) or [{'n': None}]
        except Exception:
            self._vistas = [{'n': None}]
        self._k = min(self._k, len(self._vistas) - 1)
        self._actualizar_pager()
        self._pintar_miniaturas()
        self.previa.update()
    def _pintar_miniaturas(self):
        """Una miniatura por variante del pack (hasta 6): la elegida lleva el borde de color."""
        if not hasattr(self, 'fila_mini'):
            return
        while self.fila_mini.count():
            it = self.fila_mini.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        n = len(self._vistas)
        self.fila_mini_w.setVisible(n > 1)
        if n <= 1:
            return
        for k, v in enumerate(self._vistas[:6]):
            try:
                lineas = lineas_de_vista(getattr(self.app, 'plantilla_sel', 'auto'), self._formato, textos=['ARRIBA', 'PRINCIPAL', 'ABAJO'], n=v.get('n'))
            except Exception:
                lineas = []
            self.fila_mini.addWidget(_MiniVariante(self, k, lineas, k == self._k))
        self.fila_mini.addStretch(1)
    def _ir_a_variante(self, k):
        if 0 <= k < len(self._vistas) and k != self._k:
            self._mover_vista(k - self._k)
    def _actualizar_pager(self):
        n = len(self._vistas)
        v = self._vistas[self._k] if self._vistas else {}
        partes = [tr('Estilo {i} de {n}', i=self._k + 1, n=n)] if n > 1 else [tr('Estilo')]
        if v.get('nombre'):
            partes.append(v['nombre'])
        partes.append(tr('icono arriba') if self._donde_icono(v) == 'arriba' else tr('icono abajo'))
        self.pag_txt.configure(text='  ·  '.join(partes))
        fijo = estilo_fijo()
        if hasattr(self, 'modo_estilos_lbl'):
            if n < 2:
                self.modo_estilos_lbl.setText('')
            elif fijo and fijo <= n:
                self.modo_estilos_lbl.configure(text=tr('Ahora TODOS los bloques usan solo el estilo {k}. Para volver a alternar los {n} estilos pulsa «Fijo en este estilo» otra vez.', k=fijo, n=n), text_color=ui.AMBAR)
            else:
                self.modo_estilos_lbl.configure(text=tr('Los {n} estilos se alternan entre los bloques (en Creativo ves cuál lleva cada uno y puedes cambiarlo).', n=n), text_color=TEXT_MUTED)
        if hasattr(self, 'fijo_chip'):
            self.fijo_chip.setText(tr('Fijo en este estilo') if (fijo and fijo == self._k + 1) else (tr('Usar solo este') if n > 1 else tr('Alternando')))
            self.fijo_chip.setVisible(n > 1)
        for boton in (self.pag_ant, self.pag_sig):
            boton.setEnabled(n > 1)
    def _alternar_fijo(self):
        """Fija el estilo que se ve (todos los bloques lo usan) o vuelve a alternar uno distinto por bloque."""
        poner_estilo_fijo(0 if estilo_fijo() == self._k + 1 else self._k + 1)
        self._actualizar_pager()
        self._reflejar_en_packs()
    def _reflejar_en_packs(self):
        """Las tarjetas de los packs y la vista de Creativo dibujan el estilo fijo."""
        try:
            ventana = getattr(self.app, '_plantillas_ventana', None)
            if ventana is not None:
                ventana._recargar(ventana.seleccion.get())
        except Exception:
            pass
        try:
            self.app._pintar_opciones_go()           # el chip «Solo el estilo N» de Inicio
        except Exception:
            pass
        try:
            self.previa.update()
        except Exception:
            pass
    def _mover_vista(self, paso):
        if len(self._vistas) <= 1:
            return
        self._k = (self._k + paso) % len(self._vistas)
        self._pag_dir = 1 if paso > 0 else -1
        self._actualizar_pager()
        self._pintar_miniaturas()
        import mograf_ui
        if not mograf_ui.quieto():
            self._pag_anim.stop()
            self._pag_anim.start()
        else:
            self._pag_t = 1.0
            self.previa.update()
    def _cambio_icono(self, _v=None):
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'emoji_posicion': self._icono_elegido()})
        except Exception:
            pass
        self._actualizar_pager()
        for t in self._tiles.values():
            t.update()
        self.previa.update()
    def _formato_previa(self):
        try:
            f = self.app._formato_forzado()
            if f in ('h', 'v'):
                return f
        except Exception:
            pass
        try:
            import resolve_bridge
            v = resolve_bridge.video_detectado() or {}
            if int(v.get('alto') or 0) > int(v.get('ancho') or 0):
                return 'v'
            if int(v.get('ancho') or 0) > 0:
                return 'h'
        except Exception:
            pass
        return 'v'
    def _deslizador(self, capa, titulo, clave, ayuda):
        fila, cf = caja_h(espacio=12)
        nombre = Etiqueta(titulo, 14)
        nombre.setFixedWidth(140)
        cf.addWidget(nombre)
        etiqueta = Etiqueta('', 13, color=TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        etiqueta.setFixedWidth(52)
        def cambia(v):
            self.valor[clave] = round(float(v), 3)
            etiqueta.configure(text=f'{self.valor[clave] * 100:+.0f} %')
            self._refrescar(tiles=False)
            self._recordar()
        d = Deslizador(-composicion.TOPE, composicion.TOPE, int(composicion.TOPE * 200), cambia, float(self.valor[clave]))
        cf.addWidget(d, 1)
        etiqueta.configure(text=f'{self.valor[clave] * 100:+.0f} %')
        cf.addWidget(etiqueta)
        Tooltip(fila, ayuda)
        setattr(self, f'_desl_{clave}', d)
        capa.addWidget(fila)
        return etiqueta
    @staticmethod
    def _barra(p, cx, cy, w, h, color):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), h / 2, h / 2)
    def _dibujar_previa(self, p, w, h):
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setPen(QPen(QColor(BORDER_COLOR), 1))
        p.setBrush(QColor('#0B1220'))
        p.drawRoundedRect(r, 12, 12)
        dentro = r.adjusted(8, 8, -8, -8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#05080F'))
        p.drawRoundedRect(dentro, 8, 8)
        layout = composicion.layout_del_bloque(self.valor, 0)
        lc, ld = composicion.lados(layout)
        vista = self._vistas[self._k] if self._vistas else {}
        lineas = lineas_de_vista(getattr(self.app, 'plantilla_sel', 'auto'), self._formato, n=vista.get('n'),
                                 color_principal=vista.get('color'))
        if len(lineas) < 3:
            lineas = lineas_de_vista(None)
        # v5.3: el espacio «imagen» (debajo del texto o encima, segun el pack o lo que elijas) entra en el cuadro
        info_img = {'donde': self._donde_icono(vista), 'zoom': vista.get('zoom') or 1.0}
        lado_img = max(14.0, min(dentro.height() * 0.2 * max(0.5, min(1.6, float(info_img.get('zoom') or 1.0))), dentro.width() * 0.3))
        medidas = []
        for texto, est in lineas:
            f = QFont(est['familia'])
            f.setPixelSize(max(9, int(est['tam'] * dentro.height() * 0.60)))
            if 'black' in est['peso'].lower() or 'bold' in est['peso'].lower():
                f.setWeight(QFont.Weight.Black if 'black' in est['peso'].lower() else QFont.Weight.Bold)
            fm = QFontMetricsF(f)
            medidas.append((texto, est, f, fm, fm.horizontalAdvance(texto)))
        w_ctx, w_main, w_cmp = (medidas[0][4], medidas[1][4], medidas[2][4])
        cx = dentro.center().x() + self.valor['horizontal'] * dentro.width()
        cy = (dentro.top() + 0.52 * dentro.height() - self.valor['altura'] * dentro.height()
              + (1 if info_img.get('donde') == 'arriba' else -1) * (lado_img + 6) / 2)
        alto_main = medidas[1][3].height()
        posiciones = [
            (cx + composicion.desplazamiento_layout(lc, w_main, w_ctx), cy - alto_main * 0.5 - medidas[0][3].height() * 0.55),
            (cx, cy),
            (cx + composicion.desplazamiento_layout(ld, w_main, w_cmp), cy + alto_main * 0.5 + medidas[2][3].height() * 0.55),
        ]
        p.save()
        p.setClipRect(dentro)
        for (texto, est, f, fm, ancho), (x, y) in zip(medidas, posiciones):
            p.setFont(f)
            p.setPen(QColorReal(est['color']))
            p.drawText(QRectF(x - ancho / 2 - 4, y - fm.height() / 2, ancho + 8, fm.height()), int(Qt.AlignmentFlag.AlignCenter), texto)
        # v5.3: el espacio «imagen»: debajo del texto (o encima, si el bloque «imagen» del pack va arriba)
        lado = lado_img
        if info_img.get('donde') == 'arriba':
            y_img = posiciones[0][1] - medidas[0][3].height() * 0.55 - 6 - lado / 2
        else:
            y_img = posiciones[2][1] + medidas[2][3].height() * 0.55 + 6 + lado / 2
        centro_img = QPointF(cx + self.valor['horizontal'] * 0, y_img)
        verde = QColor(ui.ROL_IMAGEN)
        relleno = QColor(verde)
        relleno.setAlpha(46)
        lapiz = QPen(verde, 1.4)
        lapiz.setStyle(Qt.PenStyle.CustomDashLine)
        lapiz.setDashPattern([3.0, 3.0])
        p.setPen(lapiz)
        p.setBrush(relleno)
        p.drawRoundedRect(QRectF(centro_img.x() - lado / 2, centro_img.y() - lado / 2, lado, lado), lado * 0.24, lado * 0.24)
        p.setPen(QPen(verde, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(centro_img, lado * 0.14, lado * 0.14)
        p.restore()
        p.setFont(fuente(10, peso='medio'))
        p.setPen(QColor('#4F607A'))
        p.drawText(dentro.adjusted(0, 0, -10, -6), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), tr('aprox.'))
    def _refrescar(self, tiles=True):
        if tiles:
            activo = self.valor['layout']
            for codigo, t in self._tiles.items():
                t.activo = codigo == activo
                t.update()
            es_auto = activo == 'auto'
            self.auto_btn.poner(lleno=es_auto)
            self.pista_layout.configure(text=tr('automático · distinto por bloque') if es_auto else tr('la plantilla tal cual') if activo == 'cc' else tr('arriba {a} · abajo {b}', a=self._nombre_lado(activo[0]), b=self._nombre_lado(activo[1])))
        self.previa.update()
        self._actualizar_pager()
        self._texto_fino()
        self.previa_pie.configure(text=tr('AUTO: cada bloque sale con una forma distinta; aquí se ve una de ellas.') if self.valor['layout'] == 'auto' else '')
        self.previa_pie.setVisible(self.valor['layout'] == 'auto')
    def _alternar_fino(self):
        self.fino_w.setVisible(not self.fino_w.isVisible())
        self._texto_fino()
    def _texto_fino(self):
        """«Ajuste fino ▸» (plegado) o «▾» (abierto); en ámbar y con lo que cambiaste si ya tocaste algo (así no se queda un desplazamiento olvidado)."""
        if not hasattr(self, 'fino_lnk'):
            return
        cambiado = not composicion.es_defecto(self.valor)
        flecha = '▾' if self.fino_w.isVisible() else '▸'
        resumen = f"  ·  {tr('con cambios')}: {resumen_composicion(self.valor)}" if cambiado else ''
        self.fino_lnk.configure(text=f"{flecha} {tr('Ajuste fino (avanzado)')}{resumen}", text_color=ui.AMBAR if cambiado else ui.ACCENT_CLARO)
    @staticmethod
    def _nombre_lado(lado):
        return {'i': tr('izquierda'), 'd': tr('derecha')}.get(lado, tr('centro'))
    def _recordar(self):
        try:
            self.app.composicion = dict(self.valor)
            self.app._guardar_preferencias()
            self.app._pintar_opciones_go()           # los chips de Inicio avisan del ajuste fino
        except Exception:
            return None
    def _poner_layout(self, codigo):
        self.valor['layout'] = codigo
        self._refrescar()
        self._recordar()
    def _poner_auto(self):
        self._poner_layout('cc' if self.valor['layout'] == 'auto' else 'auto')
    def _restablecer(self):
        self.valor = composicion.valida(None)
        for clave in ['altura', 'horizontal']:
            try:
                getattr(self, f'_desl_{clave}').set(0.0)
            except Exception:
                pass
            getattr(self, f'{clave}_lbl').configure(text='+0 %')
        self._refrescar()
        self._recordar()
        self._aplicar('todo')
    def _aplicar(self, desde):
        if self._ocupado:
            return
        self._ocupado = True
        for b in [self.aplicar_btn, self.todo_btn, self.reset_btn]:
            b.configure(state='disabled')
        self.estado.configure(text=tr('Recomponiendo en Resolve…'), text_color=TEXT_MUTED)
        try:
            self.app._aplicar_composicion(desde, self._resultado)
        except Exception as e:
            self._resultado(False, tr('No pude recomponer: {e}', e=f'{type(e).__name__}: {e}'))
    def _resultado(self, ok, mensaje):
        if not self.existe():
            return
        self._ocupado = False
        for b in (self.aplicar_btn, self.todo_btn, self.reset_btn):
            b.configure(state='normal')
        self.estado.configure(
            text=str(mensaje or ''),
            text_color=ui.VERDE if ok else TEXT_MUTED if ok is None
            else ui.ROJO)
