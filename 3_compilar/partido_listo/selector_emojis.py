# CineCaptions · By Cinema Productions
# 1_codigo/selector_emojis.py — El selector de emojis de una palabra.
"""
selector_emojis.py
------------------
El selector de emojis de una palabra.

Salió de «CineCaptions (script principal).py» (v5.4.44) SIN cambiar su código: el principal conserva la ventana principal (SubtitleApp) y vuelve a importar estos nombres, así que `cc_main.NombreDeClase` sigue existiendo.
"""
import os
import sys
import threading
import time
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget
import qt_kit as ui
from qt_kit import Boton, Entrada, Etiqueta, Menu, Segmentado, StringVar, Tarjeta, Tooltip, caja_h, vivo
from qt_kit import QColor
from i18n import tr
import emojis_animados
from ui_comun import (TEXT_MUTED, _titulo, fuente)
class _RejillaEmojis(QWidget):
    """La rejilla del selector de emojis: UN widget que pinta solo las celdas
    a la vista (la v4 usaba un Canvas de Tk con 1 400 imagenes)."""
    def __init__(self, selector):
        super().__init__()
        self._sel = selector
        self.secciones = []
        self.celdas = []
        self._hover = None
        self._glifos = {}
        self._t0 = time.perf_counter()
        self._reloj = ui.QTimer(self)         # v5.4: emojis animados (Noto Animated Emoji): solo se redibuja lo que se ve
        self._reloj.timeout.connect(self._tic_animacion)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def showEvent(self, e):
        self._reloj.start(50)
        super().showEvent(e)
    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)
    def _tic_animacion(self):
        if not ui.vivo(self):
            return
        if self.isVisible() and self.celdas:
            self.update(self.visibleRegion())
    def _anim_lista(self, _glifo):
        if ui.vivo(self):
            self.update()
    def _glifo_de(self, eid):
        g = self._glifos.get(eid)
        if g is None:
            g = (self._sel._emojis.por_id(eid) or {}).get('glifo') or ''
            self._glifos[eid] = g
        return g
    def armar(self, secciones):
        self.secciones = secciones
        S = self._sel
        y = 4
        self.celdas = []
        self._titulos = []
        self._vacios = []
        for titulo, ids in secciones:
            if titulo:
                self._titulos.append((y, titulo))
                y += 20
            if not ids:
                self._vacios.append(y)
                y += 24
            for k, eid in enumerate(ids):
                col = k % S.COLUMNAS
                if k and col == 0:
                    y += S.CELDA
                x0 = col * S.CELDA
                self.celdas.append((x0, y, x0 + S.CELDA, y + S.CELDA, eid))
            y += S.CELDA + 8
        self.setFixedSize(S.COLUMNAS * S.CELDA, max(1, y))
        self.update()
    def celda_en(self, x, y):
        for x0, y0, x1, y1, eid in self.celdas:
            if x0 <= x < x1 and y0 <= y < y1:
                return eid
        return None
    def mouseMoveEvent(self, e):
        p = e.position()
        h = self.celda_en(p.x(), p.y())
        if h != self._hover:
            self._hover = h
            self.update()
    def leaveEvent(self, e):
        self._hover = None
        self.update()
        super().leaveEvent(e)
    def mousePressEvent(self, e):
        p = e.position()
        if e.button() == Qt.MouseButton.LeftButton:
            eid = self.celda_en(p.x(), p.y())
            if eid is not None:
                self._sel._elegir(eid)
            return
        if e.button() == Qt.MouseButton.RightButton:
            self._sel._menu_celda(p.x(), p.y(), e.globalPosition().toPoint())
    def paintEvent(self, ev):
        S = self._sel
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        zona = ev.rect()
        p.setFont(fuente(10, True))
        p.setPen(QColor(TEXT_MUTED))
        for y, titulo in self._titulos:
            p.drawText(QRectF(4, y, self.width() - 8, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), titulo)
        for y in self._vacios:
            p.setFont(fuente(12))
            p.drawText(QRectF(4, y, self.width() - 8, 22), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr('(nada con «{texto}»)', texto=S.buscar_var.get().strip()))
        glifo = QFont(S.FUENTE_GLIFO)
        glifo.setPixelSize(22)
        for x0, y0, x1, y1, eid in self.celdas:
            if y1 < zona.top() or y0 > zona.bottom():
                continue
            if eid == self._hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#1A2D4C'))
                p.drawRoundedRect(QRectF(x0 + 2, y0 + 2, S.CELDA - 4, S.CELDA - 4), 8, 8)
            img = S._imagen(eid)
            glifo_anim = self._glifo_de(eid)
            anim = emojis_animados.frame(glifo_anim, time.perf_counter() - self._t0, self._anim_lista) if glifo_anim else None
            if anim is not None:
                lado = S.LADO
                p.drawPixmap(QRectF(x0 + (S.CELDA - lado) / 2, y0 + (S.CELDA - lado) / 2, lado, lado), anim, QRectF(anim.rect()))
            elif img is not None:
                lado = S.LADO
                p.drawPixmap(QRectF(x0 + (S.CELDA - lado) / 2, y0 + (S.CELDA - lado) / 2, lado, lado), img, QRectF(img.rect()))
            else:
                e = S._emojis.por_id(eid) or {}
                p.setFont(glifo)
                p.setPen(QColor('#E0EBFB'))
                p.drawText(QRectF(x0, y0, S.CELDA, S.CELDA), int(Qt.AlignmentFlag.AlignCenter), e.get('glifo') or '▫')
        p.end()
class EmojiPickerWindow(QFrame):
    """El emoji de UNA palabra (v3.3.0, pedido literal: «poner emojis a las
    palabras claves, bonitos y estéticos como los de iOS»).

    Arriba los SUGERIDOS para esa palabra (emojis.sugerir: las palabras
    clave de CLDR en el idioma del video), despues los del usuario y todo el
    catalogo; el buscador filtra por esas mismas claves. El clic aplica EN
    EL ACTO y cierra, como el buscador de idiomas.

    v3.3.2: es un PANEL dentro de la ventana de palabras, no una ventana
    aparte (una ventana hija de un modal es justo la pieza que solo falla en
    otro sistema). Si una imagen no carga, la celda dibuja el glifo y el pie
    dice por que: nunca una rejilla vacia sin explicacion. Conserva la firma
    y los nombres (buscar_var, _celdas, _pintar, _elegir; withdraw es un
    no-op; destroy() es cerrar()).
    """
    COLUMNAS = 9
    CELDA = 46
    LADO = 36
    ANCHO = 480
    ALTO = 440
    FUENTE_GLIFO = 'Apple Color Emoji' if sys.platform == 'darwin' else 'Segoe UI Emoji'
    def __init__(self, master, palabra, idioma, actual, al_elegir, idx=None):
        super().__init__(master)
        self.setObjectName('panelEmoji')
        self.master = master
        import emojis
        self._emojis = emojis
        self._al_elegir = al_elegir
        self._idx = idx
        self._idioma = idioma or 'es'
        self._imagenes = {}
        self._celdas = []
        self._error_imagenes = None
        self._cerrado = False
        self.hide()
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 10, 14, 12)
        capa.setSpacing(6)
        cab, cc = caja_h()
        cc.addWidget(_titulo(tr('Emoji para «{palabra}»', palabra=palabra), 14), 1)
        cc.addWidget(Boton('✕', self.cerrar, tipo='fantasma', alto=26, ancho=28))
        capa.addWidget(cab)
        self.buscar_var = StringVar()
        self.entrada = Entrada(self.buscar_var, placeholder=tr('🔍  Buscar (fuego, dinero, idea...)'), alto=32)
        self.entrada.textEdited.connect(lambda _t: self._pintar())
        self.entrada.returnPressed.connect(self._primero)
        capa.addWidget(self.entrada)
        marco = Tarjeta(margenes=(6, 6, 2, 6))
        self.area = QScrollArea()
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setWidgetResizable(False)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rejilla = _RejillaEmojis(self)
        self.area.setWidget(self.rejilla)
        self.area.viewport().setAutoFillBackground(False)
        marco.capa.addWidget(self.area)
        capa.addWidget(marco, 1)
        self.pie = Etiqueta('', 11, color='#FF6B6B', envolver=True)
        self.pie.hide()
        capa.addWidget(self.pie)
        botones, cb = caja_h(espacio=6)
        estilo = dict(alto=30, tam=12)
        if actual:
            cb.addWidget(Boton(tr('Quitar emoji'), lambda: self._elegir(None), ancho=100, **estilo))
        if getattr(master, '_poner_mi_png', None) and idx is not None:
            png_btn = Boton(tr('➕ Mi PNG…'), self._mi_png, ancho=100, **estilo)
            cb.addWidget(png_btn)
            Tooltip(png_btn, tr('Elige un PNG de tu equipo: aparece en esta palabra y queda en tu biblioteca («Míos») para la próxima vez. Clic derecho sobre un emoji: usar tu PNG en su lugar.'))
        carpeta_btn = Boton('📁', self._abrir_carpeta, ancho=36, **estilo)
        cb.addWidget(carpeta_btn)
        Tooltip(carpeta_btn, tr('Tus PNG en {carpeta}. Un archivo llamado como el emoji (🔥.png, 1F525.png o fire.png) reemplaza su imagen; cualquier otro aparece en «Míos».', carpeta=emojis.carpeta_usuario()))
        # v5.5: el ESTILO de los emojis: 3D (Fluent, de Microsoft), Google (Noto) o los del sistema (planos). Lo que el programa no trae se baja la primera vez que se usa y queda guardado.
        self._estilos = [('animado', tr('Animado')), ('fluent3d', tr('3D')), ('noto', tr('Google'))] + ([('sistema', tr('Sistema'))] if emojis.fuente_sistema() is not None else [])
        self.estilo_var = StringVar(next((n for k, n in self._estilos if k == emojis.estilo()), self._estilos[0][1]))
        seg_estilo = Segmentado([n for _k, n in self._estilos], self.estilo_var, self._on_estilo, alto=28, tam=12)
        cb.addWidget(seg_estilo)
        Tooltip(seg_estilo, tr('El estilo de los emojis. Animado: los emojis que se mueven (Noto Animated, de Google) y, los que no, en 3D. 3D: Fluent de Microsoft (licencia MIT), fijos. Google: Noto, fijos. '
                               'Sistema: la fuente de tu equipo (Apple Color Emoji en Mac, Segoe UI Emoji en Windows; planos). Lo que no trae el programa se baja la primera vez que se usa y queda guardado; '
                               'sin internet, o si ese estilo no lo tiene, sale el del sistema.'))
        self.bajar_btn = Boton(tr('⬇ Bajar todos'), self._bajar_todos, ancho=104, **estilo)
        cb.addWidget(self.bajar_btn)
        Tooltip(self.bajar_btn, tr('Baja ahora todos los emojis de este estilo (~40 MB): aparecen al instante y funcionan sin internet.'))
        self.bajar_btn.setVisible(emojis.estilo() != 'sistema')
        self._descarga = {'activo': False, 'hechos': 0, 'total': 0, 'fallos': 0, 'cancelar': False}
        self._reloj_sets = ui.QTimer(self)
        self._reloj_sets.timeout.connect(self._tic_sets)
        self._reloj_sets.start(1200)
        cb.addStretch(1)
        capa.addWidget(botones)
        self._sugeridos = emojis.sugerir(palabra, self._idioma)
        self._pintar()
    def mostrar_en(self, x, y, ancho=None, alto=None):
        """Aparece en esas coordenadas DE LA VENTANA y toma el teclado. Quien
        lo coloca es WordTagWindow._colocar_junto_a."""
        self.setGeometry(int(x), int(y), int(ancho or self.ANCHO), int(alto or self.ALTO))
        self.show()
        self.raise_()
        self.entrada.setFocus()
    def withdraw(self):
        """Compat: hasta la v3.3.1 era una ventana. Un panel no se retira."""
        return
    def existe(self):
        return vivo(self) and not self._cerrado
    def contiene(self, x_root, y_root):
        """Si ese punto de pantalla cae dentro del panel."""
        try:
            if not self.existe() or not self.isVisible():
                return False
            p = self.mapFromGlobal(QPoint(int(x_root), int(y_root)))
            return self.rect().contains(p)
        except Exception:
            return False
    def cerrar(self):
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self._reloj_sets.stop()
            self._descarga['cancelar'] = True
        except Exception:
            pass
        try:
            self.hide()
            self.deleteLater()
        except Exception:
            pass
        try:
            if getattr(self.master, '_popover', None) is self:
                self.master._popover = None
        except Exception:
            pass
    destroy = cerrar
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._escape()
            e.accept()
            return
        super().keyPressEvent(e)
    def _escape(self, _evento=None):
        self.cerrar()
        return 'break'
    def _primero(self, _evento=None):
        """Enter en el buscador elige el primer resultado: un camino por
        teclado por si el clic en la rejilla fallara en algun equipo."""
        if self._celdas:
            self._elegir(self._celdas[0][4])
        return 'break'
    def _on_estilo(self, _v=None):
        clave = next((k for k, n in self._estilos if n == self.estilo_var.get()), 'animado')
        self._emojis.estilo(clave)
        recordar = getattr(self.master, '_recordar', None)
        if recordar:
            recordar('emoji_estilo', clave)
            recordar('emojis_sistema', clave == 'sistema')
        if clave == 'sistema' and not self._emojis.puede_dibujar_sistema():
            self._avisar(tr('Tu equipo no tiene una fuente de emojis que pueda dibujar: se usan los 3D.'))
        self.bajar_btn.setVisible(clave != 'sistema')
        self._imagenes.clear()
        self._error_imagenes = None
        self._pintar()
        try:
            refrescar = getattr(self.master, '_redibujar_manteniendo_vista', None)
            if refrescar:
                self.master._imgs_emoji.clear()
                refrescar()
        except Exception:
            pass
    def _bajar_todos(self):
        """Baja en segundo plano todos los emojis del estilo elegido que faltan (con el progreso en el pie)."""
        import threading
        d = self._descarga
        if d['activo']:
            d['cancelar'] = True
            return
        estilo = 'noto' if self._emojis.estilo() == 'noto' else 'fluent3d'
        import emojis_sets
        d.update(activo=True, hechos=0, total=len(emojis_sets.faltan(estilo, self._emojis.catalogo())), fallos=0, cancelar=False)
        if not d['total']:
            d['activo'] = False
            self._avisar(tr('Ya están todos bajados.'))
            return
        self.bajar_btn.configure(text=tr('Parar'))

        def trabajo():
            try:
                emojis_sets.bajar_todo(estilo, self._emojis.catalogo(), al_progreso=lambda h, t, f: d.update(hechos=h, fallos=f), cancelar=lambda: d['cancelar'])
            finally:
                d['activo'] = False
        threading.Thread(target=trabajo, daemon=True).start()
    def _tic_sets(self):
        """Cada ~1 s: si están llegando emojis (en segundo plano) las imágenes se vuelven a leer, y el pie cuenta cuántos van."""
        if self._cerrado or not vivo(self):
            return
        d = self._descarga
        try:
            import emojis_sets
            if d['activo']:
                self._avisar(tr('Bajando emojis… {h} de {t}', h=d['hechos'], t=d['total']) + (tr(' ({f} sin internet o sin versión)', f=d['fallos']) if d['fallos'] else ''))
                self._imagenes.clear()
            elif d['total'] and d['hechos'] + d['fallos'] >= d['total'] - 0 and self.bajar_btn.text() != tr('⬇ Bajar todos'):
                self.bajar_btn.configure(text=tr('⬇ Bajar todos'))
                self._avisar(tr('Listo: {h} emojis bajados.', h=d['hechos']) + (tr(' {f} no se pudieron bajar (el del sistema los sustituye).', f=d['fallos']) if d['fallos'] else ''))
                self._imagenes.clear()
            elif emojis_sets.pendientes():
                self._imagenes.clear()
        except Exception:
            pass
    def _abrir_carpeta(self):
        carpeta = self._emojis.carpeta_usuario()
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith('win'):
                os.startfile(str(carpeta))
            else:
                import subprocess
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(carpeta)])
        except Exception as e:
            self._avisar(tr('No pude abrir {carpeta}: {e}', carpeta=carpeta, e=e))
            return None
    def _avisar(self, texto):
        self.pie.configure(text=texto)
        self.pie.show()
    def _imagen(self, eid):
        if eid not in self._imagenes:
            try:
                ruta = self._emojis.ruta_mini(eid, fabricar=False)
                if ruta is None:
                    self._imagenes[eid] = None
                    return None
                self._imagenes[eid] = ui.pixmap_de_archivo(ruta, self.LADO)
            except Exception as e:
                self._imagenes[eid] = None
                if self._error_imagenes is None:
                    self._error_imagenes = f'{type(e).__name__}: {e}'
        return self._imagenes[eid]
    def _pintar(self):
        emojis = self._emojis
        texto = self.buscar_var.get().strip()
        if texto:
            secciones = [(None, [e['id'] for e in emojis.buscar(
                texto, (self._idioma, 'es', 'en'))])]
        else:
            mios = [e['id'] for e in emojis.catalogo()
                    if e.get('grupo') == emojis.GRUPO_USUARIO
                    and e['id'] not in self._sugeridos]
            resto = [e['id'] for e in emojis.catalogo()
                     if e['id'] not in self._sugeridos
                     and e.get('grupo') != emojis.GRUPO_USUARIO]
            # v5.5: Recientes arriba y el resto POR CATEGORIA (caras, gestos, objetos...), no una lista de 1 400
            recientes = [r for r in self._recientes() if r not in self._sugeridos]
            por_grupo = {}
            for e in emojis.catalogo():
                if e['id'] in self._sugeridos or e.get('grupo') == emojis.GRUPO_USUARIO or e['id'] in recientes:
                    continue
                por_grupo.setdefault(str(e.get('grupo') or 'otros'), []).append(e['id'])
            nombres_grupo = {'caras': tr('Caras'), 'manos': tr('Manos y gestos'), 'corazones': tr('Corazones'), 'personas': tr('Personas'),
                             'naturaleza': tr('Naturaleza y animales'), 'comida': tr('Comida'), 'ocio': tr('Ocio y deporte'), 'viajes': tr('Viajes y lugares'),
                             'objetos': tr('Objetos'), 'trabajo': tr('Trabajo'), 'dinero': tr('Dinero'), 'simbolos': tr('Símbolos'), 'varios': tr('Varios')}
            orden_g = list(nombres_grupo)
            por_grupo = dict(sorted(por_grupo.items(), key=lambda kv: orden_g.index(kv[0]) if kv[0] in orden_g else 99))
            secciones = (([(tr('Sugeridos'), self._sugeridos)] if self._sugeridos else [])
                         + ([(tr('Recientes'), recientes)] if recientes else [])
                         + ([(tr('Míos'), mios)] if mios else [])
                         + [(nombres_grupo.get(g, g.capitalize()), ids) for g, ids in por_grupo.items() if ids])
        self.rejilla.armar(secciones)
        self._celdas = self.rejilla.celdas
        self.area.verticalScrollBar().setValue(0)
        if self._error_imagenes:
            self._avisar(tr('No pude cargar las imágenes: {error}', error=self._error_imagenes))
    @staticmethod
    def _recientes():
        try:
            import ajustes_ui
            return [str(x) for x in (ajustes_ui.leer_prefs().get('emojis_recientes') or [])][:16]
        except Exception:
            return []
    def _elegir(self, eid):
        try:
            try:
                import ajustes_ui
                lista = [eid] + [r for r in self._recientes() if r != eid]
                ajustes_ui.guardar_prefs({'emojis_recientes': lista[:16]})
            except Exception:
                pass
            self._al_elegir(eid)
        finally:
            self.cerrar()
    def _mi_png(self):
        """«➕ Mi PNG…»: lo hace la ventana (unico sitio con el dialogo);
        el panel se cierra al aplicar."""
        poner = getattr(self.master, '_poner_mi_png', None)
        if poner and self._idx is not None:
            poner(self._idx)
    def _menu_celda(self, x, y, pos_global):
        """Clic derecho sobre un emoji (v3.3.4): usar tu PNG en su lugar,
        volver al original, o quitar uno tuyo de la biblioteca. Lo ejecuta
        la ventana de palabras (que redibuja y confirma)."""
        eid = self.rejilla.celda_en(x, y)
        if eid is None:
            return 'break'
        e = self._emojis.por_id(eid) or {}
        reemplazar = getattr(self.master, '_reemplazar_emoji_con_png', None)
        quitar = getattr(self.master, '_quitar_de_biblioteca', None)
        menu = Menu(self)
        if str(eid).startswith('mio_'):
            if quitar:
                menu.agregar(tr('Quitar de mi biblioteca'), lambda: quitar(eid))
        else:
            if reemplazar:
                menu.agregar(tr('Usar mi PNG en lugar de este emoji…'), lambda: reemplazar(eid))
            if e.get('usuario') and quitar:
                menu.agregar(tr('Volver al emoji original'), lambda: quitar(eid))
        if menu.vacio():
            return 'break'
        menu.mostrar(pos_global)
        return 'break'
