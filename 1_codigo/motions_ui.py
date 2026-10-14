# CineCaptions · By Cinema Productions
# 1_codigo/motions_ui.py — la sección «Motions de la Edición PRO» de la página Efectos: un carrusel con TODOS los motions (v5.5.7)
"""
El usuario: «agrega un slider con todos los motions disponibles para que la IA sepa que esos puede usar exclusivamente y respete la decisión; y deja
el modo automático para que la IA escoja el adecuado».

    SeccionMotions          la tarjeta: Automático / Solo los que elija, filtro por grupo, el carrusel, Todos / Ninguno y la cuenta
    CarruselMotions         la tira de tarjetas (una sola QWidget pintada: con ~150 motions no se crean ~150 widgets). Solo se pintan las visibles,
                            las miniaturas (2_recursos/edicion_pro/previas_motions, hacer_previas_motions.py) se cargan al verse y el desplazamiento
                            va con un resorte del motor común (qt_kit.motor_resortes: sin temporizadores propios encendidos).

Se guarda en las opciones de la PRO (edicion_pro.guardar_opciones): `pro_motions_modo` ('auto' | 'elegidos') y `pro_motions` (ids). Lo leen
motions_catalogo.permitido/filtrar en el planificador y al final del plan. Con «Solo los que elija» y ninguno marcado, la IA elige entre todos.
"""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

import motions_catalogo as MC
import qt_kit as ui
from qt_kit import Boton, Etiqueta, Resorte, Segmentado, StringVar, Tarjeta, caja_h, despues, motor_resortes
from qt_kit import QColor
from i18n import tr

# color de cada grupo (miniaturas que faltan y la marca de grupo)
_COLOR_GRUPO = {'plantilla': '#C9A46A', 'kit': '#7C5CFF', 'escena': '#FF6B8A', 'grafico': '#4589FF', 't5': '#24D18F'}
_GLIFO_GRUPO = {'plantilla': 'Aa', 'kit': '✦', 'escena': '▣', 'grafico': '◆', 't5': '◎'}


def _opciones():
    try:
        import edicion_pro
        return edicion_pro.opciones_guardadas()
    except Exception:
        return {}


def _guardar(cambios):
    try:
        import edicion_pro
        edicion_pro.guardar_opciones(cambios)
    except Exception:
        pass


# ====================================================================================== la tira de tarjetas
class CarruselMotions(QWidget):
    tocado = Signal(str)                    # id del motion
    ANCHO, IMG_W, IMG_H, HUECO = 124, 112, 199, 10
    ALTO = IMG_H + 62

    def __init__(self, padre=None):
        super().__init__(padre)
        self._items = []                    # [{'id', 'nombre', 'grupo'}]
        self._elegidos = set()
        self._auto = True
        self._imagenes = {}                 # id -> QImage | None (cargada al verse)
        self._hover = -1
        self._flecha_hover = 0              # -1 izquierda, 1 derecha
        self._res = Resorte(0.0, 220.0, 30.0)
        self._arrastre = None               # (x inicial, desplazamiento inicial) mientras se arrastra
        self._movido = False
        self.setFixedHeight(self.ALTO + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # -- datos
    def poner(self, items, elegidos, auto):
        cambio_lista = [m['id'] for m in items] != [m['id'] for m in self._items]
        self._items = list(items)
        self._elegidos = set(elegidos)
        self._auto = bool(auto)
        if cambio_lista:
            self._res.poner(0.0)
        self._limitar()
        self.update()

    def _total(self):
        return max(0.0, len(self._items) * (self.ANCHO + self.HUECO) - self.HUECO)

    def _max_desp(self):
        return max(0.0, self._total() - (self.width() - 8))

    def _limitar(self):
        m = self._max_desp()
        self._res.objetivo = min(max(0.0, self._res.objetivo), m)
        if self._res.x > m or self._res.x < 0:
            self._res.poner(min(max(0.0, self._res.x), m))

    def _ir(self, objetivo):
        self._res.objetivo = min(max(0.0, float(objetivo)), self._max_desp())
        motor_resortes.pedir(self)

    def paso_resorte(self, dt):
        sigue = self._res.paso(dt)
        self.update()
        return sigue

    def resizeEvent(self, e):
        self._limitar()
        super().resizeEvent(e)

    # -- geometría
    def _x_de(self, k):
        return 4 + k * (self.ANCHO + self.HUECO) - self._res.x

    def _indice_en(self, x):
        k = int((x - 4 + self._res.x) // (self.ANCHO + self.HUECO))
        if 0 <= k < len(self._items) and (x - self._x_de(k)) <= self.ANCHO:
            return k
        return -1

    def _flechas(self):
        """Los botones redondos de los lados (solo si hay para dónde moverse)."""
        r = 17
        y = 4 + self.IMG_H / 2 + 6
        izq = QRectF(10, y - r, 2 * r, 2 * r) if self._res.objetivo > 1 else None
        der = QRectF(self.width() - 10 - 2 * r, y - r, 2 * r, 2 * r) if self._res.objetivo < self._max_desp() - 1 else None
        return izq, der

    def _imagen(self, mid):
        if mid not in self._imagenes:
            f = MC.carpeta_previas() / MC.archivo_previa(mid)
            img = QImage(str(f)) if f.is_file() else None
            self._imagenes[mid] = img if (img is not None and not img.isNull()) else None
        return self._imagenes[mid]

    # -- ratón
    def wheelEvent(self, e):
        d = e.angleDelta()
        paso = d.x() if abs(d.x()) > abs(d.y()) else d.y()
        if not paso:
            return super().wheelEvent(e)
        objetivo = self._res.objetivo - paso * 1.1
        if (paso > 0 and self._res.objetivo <= 0.5) or (paso < 0 and self._res.objetivo >= self._max_desp() - 0.5):
            e.ignore()                       # en un extremo la rueda vuelve a mover la página
            return
        self._ir(objetivo)
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = (e.position().x(), self._res.objetivo)
            self._movido = False

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self._arrastre is not None:
            dx = x - self._arrastre[0]
            if abs(dx) > 6:
                self._movido = True
            if self._movido:
                self._res.objetivo = min(max(0.0, self._arrastre[1] - dx), self._max_desp())
                self._res.poner(self._res.objetivo)
                self.update()
                return
        izq, der = self._flechas()
        pos = e.position()
        fl = -1 if (izq is not None and izq.contains(pos)) else (1 if (der is not None and der.contains(pos)) else 0)
        k = -1 if fl else self._indice_en(x)
        if k != self._hover or fl != self._flecha_hover:
            self._hover, self._flecha_hover = k, fl
            self.update()

    def mouseReleaseEvent(self, e):
        arrastre, movido = self._arrastre, self._movido
        self._arrastre, self._movido = None, False
        if arrastre is None or movido or e.button() != Qt.MouseButton.LeftButton:
            return
        izq, der = self._flechas()
        pos = e.position()
        pagina = max(self.ANCHO + self.HUECO, (self.width() - 80) // (self.ANCHO + self.HUECO) * (self.ANCHO + self.HUECO))
        if izq is not None and izq.contains(pos):
            self._ir(self._res.objetivo - pagina)
            return
        if der is not None and der.contains(pos):
            self._ir(self._res.objetivo + pagina)
            return
        k = self._indice_en(pos.x())
        if k >= 0:
            self.tocado.emit(self._items[k]['id'])

    def leaveEvent(self, e):
        if self._hover != -1 or self._flecha_hover:
            self._hover, self._flecha_hover = -1, 0
            self.update()
        super().leaveEvent(e)

    # -- pintura
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._items:
            p.setPen(QColor(ui.TEXT_MUTED))
            p.setFont(ui.fuente(13))
            p.drawText(QRectF(0, 0, self.width(), self.height()), int(Qt.AlignmentFlag.AlignCenter), tr('No hay motions en este grupo.'))
            p.end()
            return
        primero = max(0, int(self._res.x // (self.ANCHO + self.HUECO)))
        for k in range(primero, len(self._items)):
            x = self._x_de(k)
            if x > self.width():
                break
            self._carta(p, k, x)
        # bordes que se desvanecen (indican que hay más) y flechas
        for lado in (0, 1):
            if (lado == 0 and self._res.x > 1) or (lado == 1 and self._res.x < self._max_desp() - 1):
                g = QLinearGradient(QPointF(0 if lado == 0 else self.width(), 0), QPointF(36 if lado == 0 else self.width() - 36, 0))
                g.setColorAt(0, QColor(8, 14, 26, 210))
                g.setColorAt(1, QColor(8, 14, 26, 0))
                p.fillRect(QRectF(0 if lado == 0 else self.width() - 36, 0, 36, self.height()), g)
        izq, der = self._flechas()
        for r, lado in ((izq, -1), (der, 1)):
            if r is None:
                continue
            p.setPen(QPen(QColor('#3A5584' if self._flecha_hover == lado else '#2C4068'), 1.2))
            p.setBrush(QColor('#1A2B4C' if self._flecha_hover == lado else '#122039'))
            p.drawEllipse(r)
            c = r.center()
            p.setPen(QPen(QColor('#E0EBFB'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            punta, cola = c.x() + 3 * lado, c.x() - 2 * lado
            p.drawLine(QPointF(cola, c.y() - 6), QPointF(punta, c.y()))
            p.drawLine(QPointF(punta, c.y()), QPointF(cola, c.y() + 6))
        p.end()

    def _carta(self, p, k, x):
        m = self._items[k]
        sel = m['id'] in self._elegidos
        hover = k == self._hover
        apagada = (not self._auto) and not sel
        p.save()
        p.setOpacity(0.42 if apagada and not hover else (0.7 if apagada else 1.0))
        marco = QRectF(x, 4, self.ANCHO, self.ALTO)
        p.setBrush(QColor('#13203A' if (hover or (sel and not self._auto)) else '#0F1A30'))
        borde = ui.VERDE if (sel and not self._auto) else ('#2C4068' if hover else '#1E2A42')
        p.setPen(QPen(QColor(borde), 2.0 if (sel and not self._auto) else 1.0))
        p.drawRoundedRect(marco, 12, 12)
        rect = QRectF(x + 6, 10, self.IMG_W, self.IMG_H)
        camino = QPainterPath()
        camino.addRoundedRect(rect, 9, 9)
        p.save()
        p.setClipPath(camino)
        img = self._imagen(m['id'])
        if img is not None:
            p.drawImage(rect, img)
        else:                                  # sin miniatura: degradado del color del grupo y su glifo
            col = QColor(_COLOR_GRUPO.get(m['grupo'], '#4589FF'))
            g = QLinearGradient(rect.topLeft(), rect.bottomRight())
            g.setColorAt(0, QColor(col.red() // 3, col.green() // 3, col.blue() // 3 + 18))
            g.setColorAt(1, QColor(12, 18, 32))
            p.fillRect(rect, g)
            p.setPen(col)
            p.setFont(ui.fuente(30, True))
            p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), _GLIFO_GRUPO.get(m['grupo'], '◆'))
        p.restore()
        # marca del grupo (punto de color) y la de elegido
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_COLOR_GRUPO.get(m['grupo'], '#4589FF')))
        p.drawEllipse(QRectF(x + 12, 16, 7, 7))
        if sel and not self._auto:
            p.setBrush(QColor(ui.VERDE))
            p.drawEllipse(QRectF(x + self.ANCHO - 30, 14, 20, 20))
            p.setPen(QPen(QColor('#07140E'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(QPointF(x + self.ANCHO - 25, 24), QPointF(x + self.ANCHO - 21.5, 27.5))
            p.drawLine(QPointF(x + self.ANCHO - 21.5, 27.5), QPointF(x + self.ANCHO - 15.5, 20))
        # el nombre (hasta 2 líneas)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(10, True))
        texto = tr(m['nombre'])
        fm = QFontMetricsF(p.font())
        caja = QRectF(x + 8, self.IMG_H + 14, self.ANCHO - 16, 40)
        if fm.horizontalAdvance(texto) > caja.width() * 2 - 8:
            texto = fm.elidedText(texto, Qt.TextElideMode.ElideRight, caja.width() * 2 - 12)
        p.drawText(caja, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), texto)
        p.restore()


# ====================================================================================== la sección
class SeccionMotions(Tarjeta):
    """La tarjeta de la página Efectos. `al_cambiar()` (opcional) tras guardar."""
    MODOS = ('auto', 'elegidos')

    def __init__(self, padre=None, al_cambiar=None):
        super().__init__(padre, espacio=12, margenes=(22, 18, 22, 18))
        self._al_cambiar = al_cambiar
        orden = {g: k for k, g in enumerate(('kit', 'escena', 't5', 'grafico', 'plantilla'))}      # lo más visual primero; las 100 plantillas por frase al final
        self._todos = sorted(MC.catalogo(), key=lambda m: orden.get(m['grupo'], 9))
        self._grupo = ''
        self._guardar_pendiente = None
        self.capa.addWidget(Etiqueta(tr('Motions de la Edición PRO'), 18, peso='medio', color='#FFFFFF'))
        self.capa.addWidget(Etiqueta(tr('Los gráficos animados que la Edición PRO pone sobre tu video. En Automático la IA elige el adecuado para cada frase; '
                                        'si marcas los tuyos, la IA usará SOLO esos.'), 13, color=ui.TEXT_MUTED, envolver=True))
        fila, c = caja_h(espacio=12)
        self._txt_modos = (tr('Automático'), tr('Solo los que elija'))
        self._v_modo = StringVar(self._txt_modos[0])
        c.addWidget(Segmentado(list(self._txt_modos), self._v_modo, self._cambio_modo, alto=32, tam=13))
        self._lbl_cuenta = Etiqueta('', 13, color='#B4C0D6')
        c.addWidget(self._lbl_cuenta)
        c.addStretch(1)
        self._b_todos = Boton(tr('Todos'), lambda: self._marcar_grupo(True), tipo='fantasma', alto=30, tam=12)
        self._b_ninguno = Boton(tr('Ninguno'), lambda: self._marcar_grupo(False), tipo='fantasma', alto=30, tam=12)
        c.addWidget(self._b_todos)
        c.addWidget(self._b_ninguno)
        self.capa.addWidget(fila)
        cortos = {'plantilla': tr('Por frase'), 'kit': tr('Kit'), 'escena': tr('Escenas'), 'grafico': tr('Gráficos'), 't5': tr('Temas 5 y 6')}
        self._grupos = [('', tr('Todos') + f' {len(self._todos)}')] + [
            (g, cortos.get(g, g) + f' {sum(1 for m in self._todos if m["grupo"] == g)}') for g in sorted(dict(MC.GRUPOS), key=lambda g: orden.get(g, 9)) if any(m['grupo'] == g for m in self._todos)]
        self._v_grupo = StringVar(self._grupos[0][1])
        fila_g, cg = caja_h(espacio=10)
        cg.addWidget(Segmentado([t for _g, t in self._grupos], self._v_grupo, self._cambio_grupo, alto=30, tam=12))
        cg.addStretch(1)
        self.capa.addWidget(fila_g)
        self.carrusel = CarruselMotions()
        self.carrusel.tocado.connect(self._tocar)
        self.capa.addWidget(self.carrusel)
        self._lbl_pro = Etiqueta('', 12, color=ui.AMBAR, envolver=True)
        self.capa.addWidget(self._lbl_pro)
        self.refrescar()

    # -- estado
    def _estado(self):
        op = _opciones()
        modo = 'elegidos' if str(op.get('pro_motions_modo') or 'auto') == 'elegidos' else 'auto'
        validos = {m['id'] for m in self._todos}
        return modo, [i for i in (op.get('pro_motions') or []) if i in validos]

    def refrescar(self):
        modo, elegidos = self._estado()
        self._modo, self._elegidos = modo, set(elegidos)
        self._v_modo.set(self._txt_modos[self.MODOS.index(modo)])
        self._pintar()
        try:
            import edicion_pro
            pro = edicion_pro.en_juego()                         # (los Temas 5 y 6 usan la PRO aunque su interruptor esté apagado)
        except Exception:
            pro = True
        self._lbl_pro.setText('' if pro else tr('La Edición PRO está apagada: estos motions se usan cuando la actives en Inicio.'))
        self._lbl_pro.setVisible(not pro)

    def _visibles(self):
        return [m for m in self._todos if not self._grupo or m['grupo'] == self._grupo]

    def _pintar(self):
        auto = self._modo == 'auto'
        self.carrusel.poner(self._visibles(), self._elegidos, auto)
        self._b_todos.setVisible(not auto)
        self._b_ninguno.setVisible(not auto)
        n, total = len(self._elegidos), len(self._todos)
        if auto:
            txt = tr('La IA elige entre los {n}', n=total)
        elif not n:
            txt = tr('Ninguno marcado: la IA elige entre todos')
        else:
            txt = tr('{a} de {b} · la IA usará solo estos', a=n, b=total)
        self._lbl_cuenta.setText(txt)

    def _guardar_luego(self):
        """Los clics seguidos se guardan juntos (un solo archivo de preferencias escrito ~0,4 s después del último)."""
        if self._guardar_pendiente is not None:
            ui.cancelar(self._guardar_pendiente)
        self._guardar_pendiente = despues(400, self._guardar_ya, self)

    def _guardar_ya(self):
        self._guardar_pendiente = None
        orden = [m['id'] for m in self._todos if m['id'] in self._elegidos]
        _guardar({'pro_motions_modo': self._modo, 'pro_motions': orden})
        if self._al_cambiar:
            try:
                self._al_cambiar()
            except Exception:
                pass

    # -- cambios
    def _cambio_modo(self, _v=None):
        modo = self.MODOS[self._txt_modos.index(self._v_modo.get())] if self._v_modo.get() in self._txt_modos else 'auto'
        if modo == self._modo:
            return
        self._modo = modo
        self._pintar()
        self._guardar_luego()

    def _cambio_grupo(self, _v=None):
        self._grupo = next((g for g, t in self._grupos if t == self._v_grupo.get()), '')
        self._pintar()

    def _tocar(self, mid):
        if self._modo == 'auto':                 # tocar un motion en Automático = empezar a elegir, con ese
            self._modo = 'elegidos'
            self._v_modo.set(self._txt_modos[1])
            self._elegidos = {mid}
        elif mid in self._elegidos:
            self._elegidos.discard(mid)
        else:
            self._elegidos.add(mid)
        self._pintar()
        self._guardar_luego()

    def _marcar_grupo(self, si):
        ids = {m['id'] for m in self._visibles()}
        if si:
            self._elegidos |= ids
        else:
            self._elegidos -= ids
        self._pintar()
        self._guardar_luego()
