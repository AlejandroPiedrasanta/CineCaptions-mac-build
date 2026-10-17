# CineCaptions · By Cinema Productions
# 1_codigo/emojis_sfx_ui.py — pestaña «Emojis» del SFX Lab: todos los emojis en una rejilla y el sonido de cada uno, para cambiarlo.
"""
Tercera opción de «Reglas automáticas por palabra» (Simple · Avanzado · Emojis).

  * Izquierda: los ~1 400 emojis por categoría (o los que casen con lo que escribas). Un punto amarillo marca los que cambiaste y uno
    rojo los que apagaste. Tocar un emoji lo selecciona y suena.
  * Derecha: el sonido de ese emoji (de qué familia es, o el que elegiste) y cómo cambiarlo: otra familia de la lista, el sonido que
    elijas en la biblioteca («Buscar archivo…» abre su popup, que también acepta un archivo tuyo), «sin sonido» o volver al original.

Lo elegido se guarda en preferencias (emojis_sfx.PREF_SONIDOS) y se usa al generar: GO, Generar del editor y las regeneraciones.
La rejilla es UN solo widget que pinta únicamente las celdas a la vista (con 1 400 widgets sueltos la pantalla se arrastraba).
"""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

import emojis
import emojis_sfx
import qt_kit as ui
from qt_kit import (BooleanVar, Boton, Chip, Desplazable, Entrada, Etiqueta, Tooltip, caja_h, caja_v, ejecutar_en_ui, messagebox)
from qt_kit import QColor
from i18n import tr

AMARILLO = '#FDE047'            # el color con que se identifican los emojis y su sonido en la línea de tiempo de Resolve
ROJO = '#FB7185'
TEXT_MUTED = ui.TEXT_MUTED
ORDEN_GRUPOS = ('caras', 'manos', 'corazones', 'personas', 'naturaleza', 'comida', 'viajes', 'ocio', 'objetos', 'simbolos', 'trabajo', 'dinero',
                'varios', 'mios')
NOMBRES_GRUPO = {'caras': 'Caras', 'manos': 'Manos y gestos', 'corazones': 'Corazones', 'personas': 'Personas', 'naturaleza': 'Naturaleza y animales',
                 'comida': 'Comida y bebida', 'viajes': 'Viajes y lugares', 'ocio': 'Actividades', 'objetos': 'Objetos', 'simbolos': 'Símbolos',
                 'trabajo': 'Trabajo', 'dinero': 'Dinero', 'varios': 'Varios', 'mios': 'Mis emojis'}
EXTENSIONES_AUDIO = '*.wav *.mp3 *.flac *.ogg *.m4a *.aif *.aiff'
_MINIS_PEDIDAS = [False]


def nombre_de(eid):
    """El nombre legible de un emoji: la primera palabra clave en español (o inglés) del catálogo; si no, su id."""
    try:
        claves = (emojis.por_id(eid) or {}).get('claves') or {}
        for idioma in ('es', 'en'):
            lista = claves.get(idioma)
            if lista:
                return str(lista[0]).strip().capitalize()
    except Exception:
        pass
    return str(eid).replace('_', ' ').capitalize()


def nombre_de_familia(familia):
    return str(familia).replace('_', ' ').capitalize()


def _hoja(css):
    return ui.traducir_hoja(css)


class _Rejilla(QWidget):
    """Los emojis a la vista: pinta solo lo que se ve. Selección (borde amarillo) y marcas de «cambiado» / «sin sonido»."""
    COLUMNAS = 9
    CELDA = 46
    LADO = 34

    def __init__(self, panel):
        super().__init__()
        self._panel = panel
        self._celdas = []
        self._titulos = []
        self._vacio = None
        self._hover = None
        self._imagenes = {}
        self._sin_imagen = set()
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(self.COLUMNAS * self.CELDA)

    def armar(self, secciones, vacio=None):
        y = 4
        self._celdas, self._titulos, self._vacio = [], [], None
        for titulo, ids in secciones:
            if titulo and ids:
                self._titulos.append((y, titulo))
                y += 22
            for k, eid in enumerate(ids):
                col = k % self.COLUMNAS
                if k and col == 0:
                    y += self.CELDA
                self._celdas.append((col * self.CELDA, y, (col + 1) * self.CELDA, y + self.CELDA, eid))
            if ids:
                y += self.CELDA + 10
        if not self._celdas and vacio:
            self._vacio = (y, vacio)
            y += 30
        self.setFixedSize(self.COLUMNAS * self.CELDA, max(1, y))
        self.update()

    def reintentar(self):
        """Las miniaturas que no estaban listas (se fabrican en segundo plano) se piden otra vez."""
        self._sin_imagen.clear()
        self.update()

    def _imagen(self, eid):
        pm = self._imagenes.get(eid)
        if pm is not None or eid in self._sin_imagen:
            return pm
        try:
            ruta = emojis.ruta_mini(eid, fabricar=False)
            pm = ui.pixmap_de_archivo(ruta, self.LADO) if ruta is not None else None
        except Exception:
            pm = None
        if pm is None:
            self._sin_imagen.add(eid)
        else:
            self._imagenes[eid] = pm
        return pm

    def celda_en(self, x, y):
        for x0, y0, x1, y1, eid in self._celdas:
            if x0 <= x < x1 and y0 <= y < y1:
                return eid
        return None

    def mouseMoveEvent(self, e):
        h = self.celda_en(e.position().x(), e.position().y())
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            eid = self.celda_en(e.position().x(), e.position().y())
            if eid is not None:
                self._panel.elegir(eid, oir=True)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        zona = ev.rect()
        p.setFont(ui.fuente(10, True))
        p.setPen(QColor(TEXT_MUTED))
        for y, titulo in self._titulos:
            if y + 20 < zona.top() or y > zona.bottom():
                continue
            p.drawText(QRectF(6, y, self.width() - 12, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), titulo.upper())
        if self._vacio:
            p.setFont(ui.fuente(12))
            p.drawText(QRectF(6, self._vacio[0], self.width() - 12, 24), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._vacio[1])
        glifo = QFont('Segoe UI Emoji')
        glifo.setPixelSize(22)
        elegido = self._panel.eid
        asignados = self._panel.asignados
        for x0, y0, x1, y1, eid in self._celdas:
            if y1 < zona.top() or y0 > zona.bottom():
                continue
            marco = QRectF(x0 + 2, y0 + 2, self.CELDA - 4, self.CELDA - 4)
            if eid == elegido:
                p.setPen(QPen(QColor(AMARILLO), 1.6))
                p.setBrush(QColor('#1E2B4A'))
                p.drawRoundedRect(marco, 9, 9)
            elif eid == self._hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#1A2D4C'))
                p.drawRoundedRect(marco, 9, 9)
            img = self._imagen(eid)
            if img is not None:
                p.drawPixmap(QRectF(x0 + (self.CELDA - self.LADO) / 2, y0 + (self.CELDA - self.LADO) / 2, self.LADO, self.LADO), img, QRectF(img.rect()))
            else:
                p.setFont(glifo)
                p.setPen(QColor('#E0EBFB'))
                p.drawText(QRectF(x0, y0, self.CELDA, self.CELDA), int(Qt.AlignmentFlag.AlignCenter), (emojis.por_id(eid) or {}).get('glifo') or '▫')
            if eid in asignados:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(ROJO if asignados[eid] == '' else AMARILLO))
                p.drawEllipse(QRectF(x1 - 12, y0 + 5, 7, 7))
        p.end()


class PanelEmojis(QWidget):
    """La pestaña «Emojis»: rejilla a la izquierda y el sonido del emoji elegido a la derecha.

    oir(ruta)   : suena un audio (el reproductor del SFX Lab).
    buscar(subtitulo, al_usar) : abre la biblioteca del SFX Lab en un popup; al_usar(Path) recibe el sonido elegido.
    aviso(txt)  : escribe en la barra de estado del SFX Lab.
    """

    def __init__(self, oir, buscar, aviso, padre=None):
        super().__init__(padre)
        self._oir = oir
        self._abrir_biblioteca = buscar
        self._aviso = aviso
        self.asignados = emojis_sfx.asignados()
        self.eid = None
        self._filas = {}
        self._catalogo = []
        self.setMinimumHeight(580)
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(14)
        raiz.addWidget(self._columna_rejilla())
        raiz.addWidget(self._columna_detalle(), 1)
        try:
            self._catalogo = list(emojis.catalogo())
        except Exception:
            self._catalogo = []
        self._pintar_rejilla()
        inicial = 'fire' if emojis.por_id('fire') else (self._catalogo[0]['id'] if self._catalogo else None)
        if inicial:
            self.elegir(inicial, oir=False)
        self._pedir_minis()

    # -- izquierda: rejilla -------------------------------------------------------
    def _columna_rejilla(self):
        col = QWidget()
        col.setFixedWidth(_Rejilla.COLUMNAS * _Rejilla.CELDA + 24)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self._buscar = Entrada(placeholder=tr('Buscar un emoji (fuego, beso, perro…)'), alto=36, tam=13)
        self._buscar.textEdited.connect(lambda _t: self._pintar_rejilla())
        v.addWidget(self._buscar)
        fila, cf = caja_h(espacio=10)
        self._solo_var = BooleanVar(False)
        solo = ui.Interruptor(tr('Solo los que cambié'), var=self._solo_var, tam=12, comando=self._pintar_rejilla)
        Tooltip(solo, tr('Muestra solo los emojis a los que les cambiaste el sonido (punto amarillo) o se lo quitaste (punto rojo).'))
        cf.addWidget(solo)
        cf.addStretch(1)
        self._contador = Etiqueta('', 12, color=TEXT_MUTED)
        cf.addWidget(self._contador)
        v.addWidget(fila)
        self._rejilla = _Rejilla(self)
        desp = Desplazable(margenes=(0, 0, 6, 0), espacio=0, estirar_final=False)
        desp.agregar(self._rejilla)
        self._desp = desp
        v.addWidget(desp, 1)
        return col

    def _ids_visibles(self):
        texto = self._buscar.text().strip()
        if texto:
            try:
                return [(None, [e['id'] for e in emojis.buscar(texto, ('es', 'en'))])]
            except Exception:
                return [(None, [])]
        por_grupo = {}
        for e in self._catalogo:
            por_grupo.setdefault(str(e.get('grupo') or 'varios'), []).append(e['id'])
        extras = [g for g in por_grupo if g not in ORDEN_GRUPOS]
        return [(tr(NOMBRES_GRUPO.get(g, g.capitalize())), por_grupo[g]) for g in list(ORDEN_GRUPOS) + extras if por_grupo.get(g)]

    def _pintar_rejilla(self):
        secciones = self._ids_visibles()
        if self._solo_var.get():
            secciones = [(t, [i for i in ids if i in self.asignados]) for t, ids in secciones]
        n = len(self.asignados)
        self._contador.configure(text=tr('{n} con sonido cambiado', n=n) if n else tr('{n} emojis', n=len(self._catalogo)))
        self._rejilla.armar(secciones, vacio=tr('(ningún emoji coincide)'))

    def _pedir_minis(self):
        """Las miniaturas se fabrican una vez en segundo plano (el selector de emojis hace lo mismo); mientras tanto se ve el glifo."""
        if _MINIS_PEDIDAS[0]:
            return
        _MINIS_PEDIDAS[0] = True
        try:
            emojis.preparar_minis(al_terminar=lambda: ejecutar_en_ui(self._minis_listas))
        except Exception:
            pass

    def _minis_listas(self):
        if ui.vivo(self):
            self._rejilla.reintentar()
            self._imagen_detalle()

    def showEvent(self, e):
        self._rejilla.reintentar()
        super().showEvent(e)

    # -- derecha: el sonido del emoji elegido ---------------------------------------
    def _columna_detalle(self):
        tarjeta = QFrame()
        tarjeta.setObjectName('detalleSonidoEmoji')
        tarjeta.setStyleSheet(_hoja('QFrame#detalleSonidoEmoji { background-color: #0F1A30; border: 1px solid #1E2A42; border-radius: 14px; }'))
        tarjeta.setMinimumWidth(300)
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        cab, cc = caja_h(espacio=12)
        self._foto = QLabel()
        self._foto.setFixedSize(60, 60)
        self._foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cc.addWidget(self._foto)
        col_n, cn = caja_v(espacio=2)
        self._nombre = ui.Elidida('', 18, peso='extra', color='#FFFFFF')
        self._sub = ui.Elidida('', 12, color=TEXT_MUTED)
        cn.addWidget(self._nombre)
        cn.addWidget(self._sub)
        cc.addWidget(col_n, 1)
        v.addWidget(cab)
        v.addWidget(self._pequena(tr('SUENA ASÍ')))
        fila, cf = caja_h(espacio=8)
        self._chip = Chip('', AMARILLO, alto=26, tam=12)
        cf.addWidget(self._chip)
        self._archivo = ui.Elidida('', 12, color='#B4C0D6')
        cf.addWidget(self._archivo, 1)
        v.addWidget(fila)
        self._estado = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        v.addWidget(self._estado)
        acciones, ca = caja_h(espacio=6)
        self._b_oir = Boton(tr('Escuchar'), self._escuchar, alto=32, tam=12)
        Tooltip(self._b_oir, tr('Suena este emoji tal como saldrá en el video.'))
        ca.addWidget(self._b_oir)
        self._b_silencio = Boton(tr('Sin sonido'), lambda: self._poner(''), alto=32, tam=12)
        Tooltip(self._b_silencio, tr('Este emoji saldrá en el video sin ningún sonido.'))
        ca.addWidget(self._b_silencio)
        self._b_original = Boton(tr('Volver al original'), lambda: self._poner(None), alto=32, tam=12)
        Tooltip(self._b_original, tr('Quita tu cambio y vuelve al sonido que trae el programa para este emoji.'))
        ca.addWidget(self._b_original)
        ca.addStretch(1)
        v.addWidget(acciones)
        v.addSpacing(4)
        v.addWidget(self._pequena(tr('CAMBIAR EL SONIDO')))
        self._buscar_sonido = Entrada(placeholder=tr('Buscar un sonido (fuego, beso, aplauso…)'), alto=32, tam=12)
        self._buscar_sonido.textEdited.connect(self._filtrar_sonidos)
        v.addWidget(self._buscar_sonido)
        self._lista = Desplazable(margenes=(0, 0, 6, 0), espacio=4, estirar_final=True)
        self._armar_lista()
        v.addWidget(self._lista, 1)
        buscar = Boton(tr('Buscar archivo…'), self._buscar_archivo, alto=32, tam=12)
        Tooltip(buscar, tr('Abre la biblioteca de sonidos (o un archivo de tu computadora) para este emoji.'))
        v.addWidget(buscar)
        self._restablecer = ui.Enlace(tr('Quitar todos mis cambios'), self._restablecer_todos, 11, color=TEXT_MUTED, color_hover=ui.ACCENT_CLARO)
        v.addWidget(self._restablecer, 0, Qt.AlignmentFlag.AlignLeft)
        return tarjeta

    @staticmethod
    def _pequena(texto):
        e = Etiqueta(texto, 10, peso='negrita', color=TEXT_MUTED)
        e.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return e

    def _armar_lista(self):
        """Una fila por cada sonido del programa (las «familias»): ▶ para oírlo y Usar para ponérselo al emoji."""
        self._filas = {}
        for familia in emojis_sfx.familias():
            fila = QFrame()
            fila.setObjectName('filaSonidoEmoji')
            h = QHBoxLayout(fila)
            h.setContentsMargins(8, 3, 8, 3)
            h.setSpacing(8)
            oir = Boton('▶', lambda _=False, f=familia: self._oir_familia(f), tipo='icono', alto=26, ancho=30, tam=11)
            oir.setFixedWidth(30)
            h.addWidget(oir)
            h.addWidget(Etiqueta(nombre_de_familia(familia), 13, color='#E0EBFB'), 1)
            usar = Boton(tr('Usar'), lambda _=False, f=familia: self._poner(f), alto=26, tam=11)
            usar.setMinimumWidth(52)
            h.addWidget(usar)
            self._lista.agregar(fila)
            self._filas[familia] = fila
        self._pintar_filas()

    def _pintar_filas(self, actual=None):
        for familia, fila in self._filas.items():
            marcada = familia == actual
            fila.setStyleSheet(_hoja('QFrame#filaSonidoEmoji { background-color: %s; border: 1px solid %s; border-radius: 8px; }'
                                     % (('#1E2B4A', AMARILLO) if marcada else ('#0B1426', '#17233B'))))

    def _filtrar_sonidos(self, texto=''):
        clave = emojis.plegar(self._buscar_sonido.text()) if self._buscar_sonido.text().strip() else ''
        for familia, fila in self._filas.items():
            fila.setVisible(not clave or clave in emojis.plegar(nombre_de_familia(familia)) or clave in emojis.plegar(familia))

    # -- acciones ---------------------------------------------------------------
    def elegir(self, eid, oir=False):
        self.eid = eid
        self._detalle()
        self._rejilla.update()
        if oir:
            self._escuchar()

    def _detalle(self):
        eid = self.eid
        if not eid:
            return
        e = emojis.por_id(eid) or {}
        self._nombre.setText(nombre_de(eid))
        grupo = NOMBRES_GRUPO.get(str(e.get('grupo') or ''), '')
        self._sub.setText('  ·  '.join(x for x in (tr(grupo) if grupo else '', e.get('glifo') or '') if x))
        self._imagen_detalle()
        ruta, origen = emojis_sfx.sonido_de(eid, self.asignados, e.get('grupo'))
        elegido = self.asignados.get(eid)
        if origen == 'silencio':
            self._chip.setText(tr('Sin sonido'))
            self._archivo.setText('')
            self._estado.setText(tr('Este emoji sale sin sonido.'))
            self._pintar_filas(None)
        else:
            familia = emojis_sfx.familia_de(eid, e.get('grupo')) if origen == 'original' else (elegido if elegido in self._filas else None)
            self._chip.setText(nombre_de_familia(familia) if familia else tr('Tu archivo'))
            self._archivo.setText(Path(ruta).name if ruta else tr('(no hay audio)'))
            self._estado.setText(tr('Lo elegiste tú.') if origen == 'tuyo' else tr('El que trae el programa para este emoji.'))
            self._pintar_filas(familia)
        self._b_oir.setEnabled(ruta is not None)
        self._b_original.setEnabled(eid in self.asignados)
        self._b_silencio.setEnabled(origen != 'silencio')
        self._restablecer.setVisible(bool(self.asignados))

    def _imagen_detalle(self):
        if not self.eid:
            return
        pm = None
        try:
            ruta = emojis.ruta_mini(self.eid, fabricar=False)
            pm = ui.pixmap_de_archivo(ruta, 52) if ruta is not None else None
        except Exception:
            pm = None
        if pm is not None:
            self._foto.setText('')
            self._foto.setPixmap(pm)
        else:
            self._foto.setPixmap(QPixmap())
            self._foto.setFont(QFont('Segoe UI Emoji', 28))
            self._foto.setText((emojis.por_id(self.eid) or {}).get('glifo') or '')

    def _escuchar(self):
        if not self.eid:
            return
        ruta = emojis_sfx.sonido_de(self.eid, self.asignados)[0]
        if ruta is None:
            self._aviso(tr('Este emoji no tiene sonido.'), '#E0A030')
            return
        self._oir(ruta)

    def _oir_familia(self, familia):
        ruta = emojis_sfx.ruta_de(familia)
        if ruta is not None:
            self._oir(ruta)

    def _poner(self, valor):
        """valor: familia | ruta de archivo | '' (sin sonido) | None (el original)."""
        if not self.eid:
            return
        try:
            self.asignados = emojis_sfx.asignar(self.eid, valor)
        except Exception as e:
            self._aviso(tr('No pude guardar el sonido: {e}', e=e), '#E0A030')
            return
        self._detalle()
        self._pintar_si_filtrado()
        self._rejilla.update()
        if valor:
            ruta = emojis_sfx.sonido_de(self.eid, self.asignados)[0]
            if ruta is not None:
                self._oir(ruta)
        self._aviso(tr('Listo: el sonido de {nombre} se usará al generar.', nombre=nombre_de(self.eid)), '#7EE0A8')

    def _pintar_si_filtrado(self):
        n = len(self.asignados)
        self._contador.configure(text=tr('{n} con sonido cambiado', n=n) if n else tr('{n} emojis', n=len(self._catalogo)))
        if self._solo_var.get():
            self._pintar_rejilla()

    def _buscar_archivo(self):
        if not self.eid:
            return
        self._abrir_biblioteca(tr('Emoji {nombre}', nombre=nombre_de(self.eid)), lambda ruta: self._poner(str(Path(ruta).resolve())))

    def _restablecer_todos(self):
        if not self.asignados:
            return
        if not messagebox.askyesno(tr('Quitar todos mis cambios'), tr('Todos los emojis volverán a sonar como trae el programa. ¿Seguro?'), parent=self):
            return
        emojis_sfx.restablecer_todos()
        self.asignados = {}
        self._pintar_rejilla()
        self._detalle()
        self._aviso(tr('Listo: todos los emojis suenan como al principio.'), '#7EE0A8')
