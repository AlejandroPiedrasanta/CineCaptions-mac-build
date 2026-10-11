# CineCaptions · By Cinema Productions
# 1_codigo/crea_estilo_ui.py — «Crea tu estilo»: la galería de 48 ejemplos (con su vista real de Resolve) para armar un pack en un clic y el popup que explica la estructura de nombres.
"""
Dos ventanas (v5.4.30: la galería trae también TODOS los looks de los tres temas, que se mezclan por frases: mezcla_planificador.py, vistas en mezcla_vista.py):

  * CreaEstiloDialogo : 48 ejemplos (30 con Luxe Shine de principal y 18 con un preset de Amro.Films Captions) de posición × tipografía × colores en UNA galería, ordenada
    con tres botones «Texto alto / medio / bajo». Cada uno se ve sobre una foto de muestra con su animación COMPLETA (entrada, texto y salida) renderizada por Resolve: un
    clip de 4 s por ejemplo (hacer_vistas_guia_video.py → 2_recursos/guia_estilo/vistas/ej_NN.mp4). Se tocan hasta 3 (serán las variantes 1, 2 y 3 del pack), se le pone
    nombre y «Crear mi pack» lo arma en el acto con los macros reales del Luxe Title Pack. Los ejemplos y sus vistas viven en ejemplos_estilo.py.
  * AyudaEstilo       : el popup del «!»: por qué los clips se llaman principal / arriba / abajo / simple, qué son principal 2 y principal 3,
    qué pasa si falta una pieza y cómo se exporta. Con dibujos, porque «sin esa estructura el estilo no funciona».
"""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QSizePolicy, QVBoxLayout, QWidget

import ejemplos_estilo as E
import mezcla_planificador as MP
import qt_kit as ui
from qt_kit import Boton, Desplazable, Dialogo, Entrada, Etiqueta, Segmentado, StringVar, Tooltip, caja_h, despues
from qt_kit import QColor
from i18n import tr

AMARILLO = '#FDE047'
VERDE = '#34D399'
ROJO = '#FB7185'
AMBAR = ui.AMBAR
TEXT_MUTED = ui.TEXT_MUTED


def _hoja(css):
    return ui.traducir_hoja(css)


# ====================================================================================== la galería
class _Tarjeta(QWidget):
    """Un ejemplo sobre una FOTO de muestra (las del slider de packs): su animación COMPLETA de Resolve —entrada, texto sostenido y SALIDA— reproduciéndose en
    bucle y mezclada en «Screen» sobre la foto (hacer_vistas_guia_video.py renderiza un clip de 4 s por ejemplo). Sin clip todavía, los fotogramas de la entrada
    y, sin ellos, la aproximación pintada. Tocarlo lo elige (1.º, 2.º o 3.º = variante 1, 2 o 3). El reloj de la galería solo mueve las tarjetas que se ven."""
    ANCHO = 168
    ALTO_IMAGEN = int((ANCHO - 16) * 16 / 9)
    SOSTENER_MS = 1700           # (solo sin clip) el resultado final se queda a la vista antes de volver a empezar
    PAUSA_MS = 350

    def __init__(self, ej, al_tocar, padre=None):
        super().__init__(padre)
        self.ej = ej
        self._al_tocar = al_tocar
        self._orden = 0
        self._hover = False
        self._cuadros = None            # [QImage] de la entrada (sin clip)
        self._foto = None               # QPixmap de la foto de muestra, ya redondeada
        self._foto_idx = int(ej['id'])  # cuál de las fotos de muestra (la galería reparte distintas a las tarjetas vecinas)
        self._clip = None               # vistas_slider.Reproductor del clip de 4 s (o None)
        self._clip_listo = False
        self._ms = (ej['id'] * 337) % 1600       # sin clip: cada tarjeta arranca en un punto distinto
        self.setFixedSize(self.ANCHO, self.ALTO_IMAGEN + 66)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        Tooltip(self, tr('Toca para elegirlo (hasta 3). Toca otra vez para quitarlo.'))

    # -- la foto de fondo y los fotogramas
    def recargar(self):
        """Tras renderizar vistas nuevas: se vuelven a leer."""
        self._cuadros = None
        self._clip_listo = False
        self.update()

    def _rect_imagen(self):
        return QRectF(8, 8, self.ANCHO - 16, self.ALTO_IMAGEN)

    def _camino(self):
        from PySide6.QtGui import QPainterPath
        c = QPainterPath()
        c.addRoundedRect(self._rect_imagen(), 12, 12)
        return c

    def _foto_px(self):
        """La foto de muestra de este ejemplo (cubre la tarjeta, oscurecida un poco para que el texto claro se lea)."""
        if self._foto is None:
            from PySide6.QtGui import QPixmap
            import estilos_slider
            dpr = self.devicePixelRatioF()
            ancho, alto = self.ANCHO - 16, self.ALTO_IMAGEN
            pm = QPixmap(int(ancho * dpr), int(alto * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.black)
            fs = estilos_slider.fotos()
            if fs:
                img = fs[self._foto_idx % len(fs)]
                esc = max(ancho * dpr / img.width(), alto * dpr / img.height())
                ver = img.scaled(int(img.width() * esc + 1), int(img.height() * esc + 1), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                q = QPainter(pm)
                q.drawImage(0, 0, ver, (ver.width() - pm.width()) // 2, (ver.height() - pm.height()) // 2, pm.width(), pm.height())
                q.fillRect(0, 0, pm.width(), pm.height(), QColor(0, 0, 0, 70))
                q.end()
            self._foto = pm
        return self._foto

    def poner_foto(self, k):
        if k != self._foto_idx:
            self._foto_idx = k
            self._foto = None
            self.update()

    def _cargar(self):
        from PySide6.QtGui import QImage
        lista = []
        for ruta in E.rutas_vista(self.ej):
            img = QImage(str(ruta))
            if not img.isNull():
                lista.append(img)
        self._cuadros = lista

    def _tiempos(self, n):
        return [int(s * 1000) for s in E.CUADROS_VISTA_S][:n]

    def poner_visible(self, visible):
        """El reloj de la galería avisa si la tarjeta se ve: el clip solo suena mientras tanto."""
        if self._clip is None and not self._clip_listo:
            self._clip_listo = True
            ruta = self._ruta_video()
            if ruta is not None:
                import vistas_slider
                self._clip = vistas_slider.Reproductor(ruta, pausa_s=0)            # en bucle seguido: entra, sale y vuelve a entrar sin quedarse vacío
        if self._clip is not None:
            if visible:
                self._clip.arrancar()
            else:
                self._clip.parar()

    def avanzar(self, ms):
        self._ms += ms
        self.update()

    def _fotograma(self):
        """(fotograma, siguiente, mezcla 0..1) de los fotogramas de la entrada (sin clip)."""
        cuadros = self._cuadros
        tiempos = self._tiempos(len(cuadros))
        ciclo = tiempos[-1] + self.SOSTENER_MS + self.PAUSA_MS
        t = self._ms % ciclo
        if t >= tiempos[-1] + self.SOSTENER_MS:
            return None, None, 0.0
        if t >= tiempos[-1]:
            return cuadros[-1], None, 0.0
        if t < tiempos[0]:
            return None, cuadros[0], t / max(1, tiempos[0])
        for k in range(len(tiempos) - 1):
            if tiempos[k] <= t < tiempos[k + 1]:
                return cuadros[k], cuadros[k + 1], (t - tiempos[k]) / max(1, tiempos[k + 1] - tiempos[k])
        return cuadros[-1], None, 0.0

    def poner_orden(self, k):
        if k != self._orden:
            self._orden = k
            self.update()

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
            self._al_tocar(self.ej['id'])

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        marco = QRectF(1, 1, self.width() - 2, self.height() - 2)
        elegido = self._orden > 0
        p.setBrush(QColor('#13203A' if (elegido or self._hover) else '#0F1A30'))
        p.setPen(QPen(QColor(AMARILLO if elegido else ('#2C4068' if self._hover else '#1E2A42')), 2.0 if elegido else 1.0))
        p.drawRoundedRect(marco, 14, 14)
        # la foto de muestra y, encima, el texto del ejemplo mezclado en «Screen» (el negro del render no tapa nada)
        rect = self._rect_imagen()
        p.save()
        p.setClipPath(self._camino())
        if self._pintar_propio(p, rect):                  # (la tarjeta de un look de los temas trae su imagen ya hecha)
            p.restore()
            self._pintar_pie(p, elegido)
            return
        p.drawPixmap(rect.toRect().topLeft(), self._foto_px())
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        clip = self._clip.imagen() if self._clip is not None else None
        if clip is not None:
            p.drawImage(rect, clip)
        elif self._clip is None or not self._clip.activo:
            if self._cuadros is None:
                self._cargar()
            if self._cuadros:
                actual, siguiente, mezcla = self._fotograma()
                if actual is not None:
                    p.drawImage(rect, actual)
                if siguiente is not None:
                    p.setOpacity(mezcla)
                    p.drawImage(rect, siguiente)
                    p.setOpacity(1.0)
            else:
                p.drawPixmap(rect.toRect().topLeft(), E.miniatura(self.ej, self.ANCHO - 16, self.devicePixelRatioF()))
        p.restore()
        self._pintar_pie(p, elegido)

    def _ruta_video(self):
        return E.ruta_video(self.ej)

    def _titulo(self):
        return E.nombre_visible(self.ej)

    def _tam_titulo(self):
        return 13

    def _subtitulo(self):
        return tr(E.etiqueta_posicion(self.ej))

    def _pintar_propio(self, _p, _rect):
        return False

    def _pintar_pie(self, p, elegido):
        # nombre y qué es
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(self._tam_titulo(), True))
        p.drawText(QRectF(10, self.ALTO_IMAGEN + 14, self.width() - 20, 20), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._titulo())
        p.setPen(QColor(TEXT_MUTED))
        p.setFont(ui.fuente(11))
        p.drawText(QRectF(10, self.ALTO_IMAGEN + 36, self.width() - 20, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._subtitulo())
        if elegido:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(AMARILLO))
            p.drawEllipse(QRectF(14, 14, 26, 26))
            p.setPen(QColor('#101626'))
            p.setFont(ui.fuente(14, True))
            p.drawText(QRectF(14, 14, 26, 26), int(Qt.AlignmentFlag.AlignCenter), str(self._orden))
        p.end()


class _TarjetaLook(_Tarjeta):
    """Un look de Tema 1, 2 o 3 (mezcla_planificador.catalogo): su vista aproximada —hecha con el plan real de su tema sobre una foto de muestra— y su nombre. Tocarlo lo suma a la mezcla (el
    número es el orden en que rotan por la voz)."""

    def __init__(self, look, al_tocar, padre=None):
        super().__init__({'id': 0, 'nombre': look['nombre']}, lambda _i: al_tocar(look['id']), padre)
        self.look = look
        self._imagen = None            # QImage de la maqueta (llega de un hilo): solo se ve mientras el look no tenga su clip real
        Tooltip(self, tr('Toca para sumarlo a tu estilo. Los que elijas se turnan por frases mientras se habla. Toca otra vez para quitarlo.'))

    def poner_imagen(self, imagen):
        self._imagen = imagen
        self.update()

    def recargar(self):
        if self._clip is not None:
            self._clip.parar()
        self._clip = None
        self._clip_listo = False
        self.update()

    def _ruta_video(self):
        import mezcla_vista
        return mezcla_vista.ruta_clip(self.look['id'])

    def avanzar(self, ms):
        if self._clip is not None:                       # (un look con clip se repinta solo por su reproductor; sin clip no hay nada que mover)
            self.update()

    def _titulo(self):
        return self.look['nombre']

    def _tam_titulo(self):
        return 11

    def _subtitulo(self):
        return tr('Tema {n}', n=self.look['tema'])

    def _pintar_propio(self, p, rect):
        clip = self._clip.imagen() if self._clip is not None else None
        if clip is not None or (self._clip is not None and self._clip.activo):
            p.drawPixmap(rect.toRect().topLeft(), self._foto_px())          # la foto y, encima, el clip de Resolve en «Screen» (el negro del render no tapa nada)
            if clip is not None:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
                p.drawImage(rect, clip)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            return True
        if self._imagen is not None:
            p.drawImage(rect, self._imagen)
        else:
            p.fillRect(rect, QColor('#10192B'))
        return True


class CreaEstiloDialogo(Dialogo):
    """«Crea tu estilo», simple: una galería con los ejemplos (fondo de muestra y animación completa), tres botones «Texto alto / medio / bajo» para ordenarlos,
    se tocan hasta 3, se le pone nombre y «Crear mi pack» lo arma. al_crear(nombre, ids, terminado) arma el pack. al_resolve / al_ayuda / al_resolve_uno ya
    no tienen botón: se aceptan solo por compatibilidad."""
    COLUMNAS = 5
    TIC_MS = 40
    GRUPOS = (('Tema 1', 1), ('Tema 2', 2), ('Tema 3', 3), ('Texto alto', ('superior', 'alto')), ('Texto medio', ('centro',)), ('Texto bajo', ('bajo', 'inferior')))
    GRUPO_INICIAL = 'Tema 1'

    def __init__(self, padre, al_crear, al_resolve=None, al_ayuda=None, al_resolve_uno=None):
        super().__init__(padre, tr('Crea tu estilo'), 1040, 800, minimo=(960, 560))
        self._al_crear = al_crear
        self._elegidos = []
        self._tarjetas = {}
        capa = QVBoxLayout(self)
        capa.setContentsMargins(20, 18, 20, 16)
        capa.setSpacing(10)
        cab, cc = caja_h(espacio=10)
        cc.addWidget(Etiqueta(tr('Crea tu estilo'), 22, peso='extra', color='#FFFFFF'))
        cc.addStretch(1)
        self._estado_real = Etiqueta('', 12, color=TEXT_MUTED)
        cc.addWidget(self._estado_real)
        capa.addWidget(cab)
        capa.addWidget(Etiqueta(tr('Toca los estilos de los Temas 1, 2 y 3 que quieras (se turnan por frases) o hasta 3 de «Texto alto / medio / bajo»  ·  Ponle un nombre y pulsa «Crear mi pack».'),
                                13, color='#B4C0D6', envolver=True))
        # tres botones para ordenar la galería por la altura del texto
        self._grupos = {tr(n): pos for n, pos in self.GRUPOS}
        self._pos_var = StringVar(tr(self.GRUPO_INICIAL))
        fila_pos, cp = caja_h(espacio=10)
        cp.addWidget(Segmentado(list(self._grupos.keys()), self._pos_var, lambda _v=None: self._pintar(), alto=34, tam=13))
        cp.addStretch(1)
        capa.addWidget(fila_pos)
        # la galería
        self._desp = Desplazable(margenes=(0, 4, 8, 4), espacio=0, estirar_final=False)
        self._rejilla_w = QWidget()
        self._rejilla = QGridLayout(self._rejilla_w)
        self._rejilla.setContentsMargins(0, 0, 0, 0)
        self._rejilla.setHorizontalSpacing(10)
        self._rejilla.setVerticalSpacing(10)
        self._desp.agregar(self._rejilla_w)
        capa.addWidget(self._desp, 1)
        for ej in E.EJEMPLOS:
            self._tarjetas[ej['id']] = _Tarjeta(ej, self._tocar)
        self._looks = MP.catalogo()
        for look in self._looks:
            self._tarjetas[look['id']] = _TarjetaLook(look, self._tocar)
        # abajo: lo elegido + nombre + crear
        pie = QFrame()
        pie.setObjectName('pieCreaEstilo')
        pie.setStyleSheet(_hoja('QFrame#pieCreaEstilo { background-color: #0F1A30; border: 1px solid #1E2A42; border-radius: 14px; }'))
        pv = QVBoxLayout(pie)
        pv.setContentsMargins(14, 10, 14, 12)
        pv.setSpacing(8)
        self._resumen = Etiqueta('', 13, color='#E0EBFB', envolver=True)
        pv.addWidget(self._resumen)
        fila, cf = caja_h(espacio=10)
        self._nombre = Entrada(placeholder=tr('Nombre de tu estilo'), alto=38, tam=14)
        self._nombre.setText(tr('Mi estilo'))
        cf.addWidget(self._nombre, 1)
        self._b_crear = Boton(tr('Crear mi pack'), self._crear, tipo='primario', alto=38, ancho=170, tam=14, negrita=True)
        cf.addWidget(self._b_crear)
        pv.addWidget(fila)
        capa.addWidget(pie)
        self._renderizando = False
        self._pintar()
        self._resumir()
        self._preparar_vistas_looks()
        self._reloj = QTimer(self)             # el reloj de las vistas: solo mueve (y hace sonar el clip de) las tarjetas que se ven
        self._reloj.timeout.connect(self._tic)
        self._reloj.start(self.TIC_MS)
        despues(700, self._auto_vistas, self)

    def _tic(self):
        for t in self._tarjetas.values():
            visible = (not t.isHidden()) and (not t.visibleRegion().isEmpty())
            t.poner_visible(visible)
            if visible:
                t.avanzar(self.TIC_MS)

    # -- las vistas reales de Resolve (solo si faltan: de fábrica ya vienen los clips)
    def _auto_vistas(self):
        try:
            import resolve_mcp
            import vistas_guia
            if vistas_guia.faltan() and resolve_mcp.estado_cacheado().get('conectado'):
                self._renderizar()
        except Exception:
            pass

    def _renderizar(self):
        if self._renderizando or not ui.vivo(self):
            return
        self._renderizando = True
        estado = {'texto': tr('Preparando las vistas…')}

        def trabajo():
            import vistas_guia
            return vistas_guia.renderizar(al_estado=lambda t: estado.__setitem__('texto', str(t)), abrir_resolve=False)

        def avance():
            if self._renderizando and ui.vivo(self):
                self._estado_real.configure(text=estado['texto'])
                despues(300, avance, self)

        def fin(_resultado, _error):
            self._renderizando = False
            if not ui.vivo(self):
                return
            self._estado_real.configure(text='')
            for t in self._tarjetas.values():
                t.recargar()
        avance()
        ui.correr_en_hilo(self, trabajo, fin)

    # -- la galería, ordenada por la altura del texto
    def _filtrados(self):
        pos = self._grupos.get(self._pos_var.get()) or ()
        if isinstance(pos, int):                                  # un Tema: todos sus looks
            return [l for l in self._looks if l['tema'] == pos]
        return [ej for ej in E.EJEMPLOS if ej['posicion'] in pos]

    def _preparar_vistas_looks(self):
        """Las vistas de los looks de los temas (Pillow, sin Resolve): se hacen en un hilo y las tarjetas se llenan al terminar."""
        def trabajo():
            import mezcla_vista
            salida = {}
            for k, look in enumerate(self._looks):
                try:
                    salida[look['id']] = mezcla_vista.vista(look['id'], foto=k, ancho=int(_Tarjeta.ANCHO - 16) * 2)
                except Exception:
                    salida[look['id']] = None
            return salida

        def fin(resultado, _error):
            if not ui.vivo(self) or not resultado:
                return
            from PySide6.QtGui import QImage
            for ident, im in resultado.items():
                t = self._tarjetas.get(ident)
                if t is None or im is None:
                    continue
                q = QImage(im.tobytes('raw', 'RGB'), im.width, im.height, im.width * 3, QImage.Format.Format_RGB888).copy()
                t.poner_imagen(q)
        ui.correr_en_hilo(self, trabajo, fin)

    def _pintar(self):
        while self._rejilla.count():
            it = self._rejilla.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()
        for k, ej in enumerate(self._filtrados()):
            t = self._tarjetas[ej['id']]
            t.poner_foto(k)
            self._rejilla.addWidget(t, k // self.COLUMNAS, k % self.COLUMNAS, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            t.show()
        self._rejilla.setColumnStretch(self.COLUMNAS, 1)
        self._poner_ordenes()

    # -- elegir
    def _poner_ordenes(self):
        for i, t in self._tarjetas.items():
            t.poner_orden(self._elegidos.index(i) + 1 if i in self._elegidos else 0)

    def _tocar(self, ident):
        """Los looks de los Temas (ids 't1:…') y los ejemplos de «Texto alto / medio / bajo» (números) NO se mezclan en un pack: tocar de la otra familia empieza una elección nueva."""
        de_temas = isinstance(ident, str)
        if ident in self._elegidos:
            self._elegidos.remove(ident)
        else:
            if self._elegidos and isinstance(self._elegidos[0], str) != de_temas:
                self._elegidos = []
            tope = MP.MAX_LOOKS if de_temas else E.MAX_ELEGIDOS
            if len(self._elegidos) >= tope:
                self._resumen.configure(text=tr('Ya elegiste {n} (el máximo). Toca uno elegido para quitarlo.', n=tope), text_color=AMBAR)
                return
            self._elegidos.append(ident)
        self._poner_ordenes()
        self._resumir()

    def _resumir(self):
        if not self._elegidos:
            self._resumen.configure(text=tr('Aún no has elegido ninguno: toca los estilos que te gusten.'), text_color=TEXT_MUTED)
            self._b_crear.setEnabled(False)
            return
        partes = [f"{k} · " + (f"T{(MP.look_de(i) or {}).get('tema', '?')} {(MP.look_de(i) or {}).get('nombre', i)}" if isinstance(i, str) else E.nombre_visible(E.por_id(i)))
                  for k, i in enumerate(self._elegidos, 1)]
        self._resumen.configure(text=tr('Elegidos: ') + '   ·   '.join(partes), text_color='#E0EBFB')
        self._b_crear.setEnabled(True)

    # -- crear
    def _crear(self):
        if not self._elegidos:
            return
        nombre = self._nombre.text().strip() or tr('Mi estilo')
        self._b_crear.setEnabled(False)
        self._b_crear.setText(tr('Creando…'))
        self._al_crear(nombre, list(self._elegidos), self._termino)

    def _termino(self, ok):
        """Lo llama la app cuando el pack ya está (o falló): si salió bien la galería se cierra."""
        if not ui.vivo(self):
            return
        self._b_crear.setText(tr('Crear mi pack'))
        self._resumir()
        if ok:
            self.cerrar()


def _boton_ayuda(comando):
    """El «!» ámbar: abre la explicación de la estructura."""
    b = Boton('!', comando, alto=32, ancho=34, tam=16, negrita=True)
    b.setFixedWidth(34)
    b.setStyleSheet(_hoja('QPushButton { color: #1B1305; background-color: %s; border: none; border-radius: 16px; font-weight: 800; }'
                          'QPushButton:hover { background-color: #FFCB6B; }' % AMBAR))
    Tooltip(b, tr('Cómo funciona «Crea tu estilo»: por qué los clips deben llamarse principal, arriba, abajo o simple, y qué son las variantes 2 y 3. Sin esa estructura el estilo no funciona.'))
    return b


def boton_ayuda(comando):
    return _boton_ayuda(comando)


# ====================================================================================== el popup que explica la estructura
def _pildora(p, x, y, texto, bien=None, ancho=None, color=None):
    """Una «etiqueta de clip» dibujada: verde con ✔ si vale, roja con ✘ si no. Devuelve el ancho."""
    p.setFont(ui.fuente(12, True))
    ancho = ancho or (p.fontMetrics().horizontalAdvance(texto) + (46 if bien is not None else 26))
    c = QColor(color or (VERDE if bien else ROJO if bien is False else '#9FB0CC'))
    p.setPen(QPen(c, 1.4))
    fondo = QColor(c)
    fondo.setAlpha(36)
    p.setBrush(fondo)
    p.drawRoundedRect(QRectF(x, y, ancho, 28), 14, 14)
    p.setPen(QColor('#F1F5FB'))
    p.drawText(QRectF(x + (30 if bien is not None else 0), y, ancho - (30 if bien is not None else 0) - (8 if bien is not None else 0), 28),
               int((Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if bien is not None else Qt.AlignmentFlag.AlignHCenter))), texto)
    if bien is not None:
        p.setPen(QPen(c, 2.0))
        cx, cy = x + 15, y + 14
        if bien:
            p.drawLine(int(cx - 4), int(cy), int(cx - 1), int(cy + 3))
            p.drawLine(int(cx - 1), int(cy + 3), int(cx + 5), int(cy - 4))
        else:
            p.drawLine(int(cx - 4), int(cy - 4), int(cx + 4), int(cy + 4))
            p.drawLine(int(cx + 4), int(cy - 4), int(cx - 4), int(cy + 4))
    return ancho


class _Dibujo(QWidget):
    def __init__(self, alto, pintar):
        super().__init__()
        self._pintar = pintar
        self.setMinimumHeight(alto)
        self.setFixedHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._pintar(p, self.width(), self.height())
        p.end()


def _dibujo_bloques(p, w, h):
    """El teléfono con las tres líneas apiladas y, a la derecha, el nombre y el efecto de cada bloque."""
    tel = QRectF(14, 8, 118, 210)
    p.setPen(QPen(QColor('#2C4068'), 2))
    p.setBrush(QColor('#0B1426'))
    p.drawRoundedRect(tel, 16, 16)
    E.dibujar(p, tel.adjusted(5, 5, -5, -5), E.por_id(15), escala_texto=1.0)
    nombres = (('arriba', 'Luxe Slide', 'la línea de contexto, encima'), ('principal', 'Luxe Shine', 'la palabra clave, grande y con brillo'),
               ('abajo', 'Luxe Slide', 'la línea que va debajo'))
    y0 = 52
    for k, (nombre, efecto, nota) in enumerate(nombres):
        y = y0 + k * 44
        p.setPen(QPen(QColor(AMARILLO), 1.2, Qt.PenStyle.DashLine))
        p.drawLine(int(tel.right() - 6), int(tel.top() + 70 + k * 30), 150, int(y + 14))
        _pildora(p, 150, y, nombre, None, ancho=118, color=AMARILLO)
        p.setPen(QColor('#E0EBFB'))
        p.setFont(ui.fuente(13, True))
        p.drawText(QRectF(280, y - 2, w - 290, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), efecto)
        p.setPen(QColor(TEXT_MUTED))
        p.setFont(ui.fuente(12))
        p.drawText(QRectF(280, y + 14, w - 290, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr(nota))
    y = y0 + 3 * 44 + 6
    _pildora(p, 150, y, 'imagen', None, ancho=118, color='#9FB0CC')
    p.setPen(QColor(TEXT_MUTED))
    p.setFont(ui.fuente(12))
    p.drawText(QRectF(280, y, w - 290, 28), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr('(opcional) el hueco del emoji, sin texto'))
    _pildora(p, 150, y + 36, 'simple', None, ancho=118, color='#9FB0CC')
    p.setPen(QColor(TEXT_MUTED))
    p.setFont(ui.fuente(12))
    p.drawText(QRectF(280, y + 36, w - 290, 28), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr('(opcional) una sola línea para palabras sueltas'))


def _dibujo_guion(p, w, h):
    """El estilo «palabra a palabra» (pack Referencia): un bloque de ejemplo y qué hace cada nombre (arriba = fina, abajo = negrita, principal = grande)."""
    tel = QRectF(14, 8, 118, 218)
    p.setPen(QPen(QColor('#2C4068'), 2))
    p.setBrush(QColor('#0B1426'))
    p.drawRoundedRect(tel, 16, 16)
    cx = tel.center().x()

    def linea(y, tramos):
        """[(texto, tam, negrita, color)] centrado en el teléfono, a la altura y."""
        anchos = []
        for t, tam, neg, _c in tramos:
            p.setFont(ui.fuente(tam, neg))
            anchos.append(p.fontMetrics().horizontalAdvance(t + ' '))
        x = cx - sum(anchos) / 2.0
        for (t, tam, neg, c), a in zip(tramos, anchos):
            p.setFont(ui.fuente(tam, neg))
            p.setPen(QColor(c))
            p.drawText(QRectF(x, y, a + 4, tam + 10), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), t)
            x += a
    linea(78, [('Seamos', 10, False, '#DCE6F7'), ('sinceros', 10, True, '#FFFFFF'), ('tú', 10, False, '#DCE6F7')])
    linea(100, [('LLEVARÍAS', 17, True, '#FFD98A')])
    linea(130, [('niños a tu', 10, False, '#DCE6F7'), ('boda', 10, True, '#FFFFFF')])
    filas = (('arriba', 'Luxe Slide FINO', 'las palabras en letra regular', 80, 38), ('abajo', 'Luxe Slide en NEGRITA', 'las palabras que se resaltan (no significa «debajo»)', 84, 94),
             ('principal', 'Luxe Shine o un preset de Amro', 'la palabra grande: la que manda en la frase', 100, 150))
    for nombre, efecto, nota, y_tel, y in filas:
        p.setPen(QPen(QColor(AMARILLO), 1.2, Qt.PenStyle.DashLine))
        p.drawLine(int(tel.right() - 8), int(y_tel + 6), 150, int(y + 14))
        _pildora(p, 150, y, nombre, None, ancho=118, color=AMARILLO)
        p.setPen(QColor('#E0EBFB'))
        p.setFont(ui.fuente(13, True))
        p.drawText(QRectF(280, y - 2, w - 290, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), efecto)
        p.setPen(QColor(TEXT_MUTED))
        p.setFont(ui.fuente(12))
        p.drawText(QRectF(280, y + 14, w - 290, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr(nota))


def _dibujo_nombres(p, w, h):
    p.setFont(ui.fuente(11, True))
    p.setPen(QColor(VERDE))
    p.drawText(QRectF(8, 0, 300, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr('SE RECONOCEN').upper())
    x, y = 8, 24
    for t in ('principal', 'arriba', 'abajo', 'imagen', 'simple', 'Principal 2', 'arriba 3'):
        a = p.fontMetrics().horizontalAdvance(t) + 46
        if x + a > w - 8:
            x, y = 8, y + 34
        x += _pildora(p, x, y, t, True) + 8
    y += 48
    p.setFont(ui.fuente(11, True))
    p.setPen(QColor(ROJO))
    p.drawText(QRectF(8, y, 400, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr('NO SE RECONOCEN: EL PROGRAMA LOS IGNORA').upper())
    x, y = 8, y + 24
    for t in ('Luxe Shine', 'Luxe Slide', 'Texto 1', 'título', 'principal grande', 'principal 4'):
        a = p.fontMetrics().horizontalAdvance(t) + 46
        if x + a > w - 8:
            x, y = 8, y + 34
        x += _pildora(p, x, y, t, False) + 8


def _dibujo_variantes(p, w, h):
    ancho_col = (w - 30) / 4.0
    titulos = (tr('Variante 1'), tr('Variante 2'), tr('Variante 3'), tr('Variante 4'))
    for k in range(4):
        x = 8 + k * (ancho_col + 4)
        ok = k < 3
        suf = '' if k == 0 else f' {k + 1}'
        c = QColor(AMARILLO if ok else ROJO)
        p.setPen(QPen(c, 1.2, Qt.PenStyle.SolidLine if ok else Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, 2, ancho_col - 4, h - 6), 12, 12)
        p.setFont(ui.fuente(12, True))
        p.setPen(c)
        p.drawText(QRectF(x, 8, ancho_col - 4, 20), int(Qt.AlignmentFlag.AlignCenter), titulos[k])
        for j, nombre in enumerate(('arriba', 'principal', 'abajo')):
            _pildora(p, x + 8, 36 + j * 34, nombre + suf, ok if k else True, ancho=ancho_col - 20, color=None if ok else ROJO)
        if not ok:
            p.setPen(QColor(ROJO))
            p.setFont(ui.fuente(11))
            p.drawText(QRectF(x + 6, 36 + 3 * 34, ancho_col - 16, 34), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), tr('Más de 3: se ignora'))


class AyudaEstilo(Dialogo):
    """El popup del «!»: la estructura de nombres, las variantes y el paso a paso, con dibujos."""

    def __init__(self, padre):
        super().__init__(padre, tr('Cómo funciona «Crea tu estilo»'), 700, 780, minimo=(620, 480))
        capa = QVBoxLayout(self)
        capa.setContentsMargins(20, 18, 20, 16)
        capa.setSpacing(10)
        cab, cc = caja_h(espacio=10)
        cc.addWidget(Etiqueta(tr('Cómo funciona «Crea tu estilo»'), 20, peso='extra', color='#FFFFFF'), 1)
        capa.addWidget(cab)
        desp = Desplazable(margenes=(0, 0, 10, 4), espacio=12, estirar_final=False)
        capa.addWidget(desp, 1)
        desp.agregar(Etiqueta(tr('Un estilo es un grupo de bloques de texto. CineCaptions los reconoce SOLO por su nombre: no mira el diseño, ni los colores, ni la tipografía.'),
                              14, color='#E0EBFB', envolver=True))
        aviso = QFrame()
        aviso.setObjectName('avisoEstructura')
        aviso.setStyleSheet(_hoja('QFrame#avisoEstructura { background-color: #2A2108; border: 1px solid %s; border-radius: 12px; }' % AMBAR))
        av = QVBoxLayout(aviso)
        av.setContentsMargins(14, 10, 14, 10)
        av.addWidget(Etiqueta(tr('Si un clip no se llama exactamente como pide la estructura, el programa no sabe qué hace y lo ignora. Sin esa estructura, el estilo no funciona.'),
                              13, peso='medio', color='#FFD98A', envolver=True))
        desp.agregar(aviso)
        # 1
        desp.agregar(self._titulo(tr('1 · Los bloques y el efecto de cada uno')))
        desp.agregar(_Dibujo(272, _dibujo_bloques))
        desp.agregar(Etiqueta(tr('Los textos tienen que ser SOLO del Luxe Title Pack (Efectos > Títulos > Luxe Title Pack): Luxe Shine para el principal y Luxe Slide para arriba y abajo. Un estilo necesita como mínimo arriba + principal + abajo.'),
                              13, color='#B4C0D6', envolver=True))
        desp.agregar(Etiqueta(tr('Los presets de Amro.Films Captions (Highlight, Underline, Fire, Strike…) valen SOLO para el texto principal, como alternativa a Luxe Shine; arriba y abajo siguen siendo siempre Luxe Slide.'),
                              13, color='#B4C0D6', envolver=True))
        # 1 bis: el estilo palabra a palabra (pack Referencia)
        desp.agregar(self._titulo(tr('Estilo «palabra a palabra» (como el pack Referencia)')))
        desp.agregar(Etiqueta(tr('Los captions virales no son una pila fija de 3 líneas: cada PALABRA es su propio clip y entra justo cuando se dice; al acabar la frase se va toda la pila a la vez. Se arma con los mismos nombres, pero con otro papel:'),
                              13, color='#B4C0D6', envolver=True))
        desp.agregar(_Dibujo(238, _dibujo_guion))
        desp.agregar(Etiqueta(tr('«arriba» = las palabras en letra FINA (regular), «abajo» = las palabras en NEGRITA (aquí no quiere decir «debajo») y «principal» = la palabra grande. Dónde cae cada palabra y qué peso lleva lo decide GO al leer tu voz (una palabra en negrita por línea, una o dos grandes por frase); el pack solo pone el aspecto de cada papel.'),
                              13, color='#B4C0D6', envolver=True))
        desp.agregar(Etiqueta(tr('Un pack funciona así cuando su pack.json lleva «guion» (el pack «Referencia» ya viene así, con 8 estilos de palabra grande: 4 de Luxe Shine y 4 de Amro). Los packs que armas aquí usan el diseño de 3 líneas de arriba. En Inicio, el chip «Estilo» de GO elige uno u otro.'),
                              13, color='#B4C0D6', envolver=True))
        # 2
        desp.agregar(self._titulo(tr('2 · El nombre tiene que ser exacto')))
        desp.agregar(Etiqueta(tr('Da igual si escribes mayúsculas o minúsculas. Lo que no vale es cualquier otro nombre: Resolve llama a los clips «Luxe Shine» y «Luxe Slide» y esos nombres NO se reconocen; hay que cambiárselos por principal, arriba, abajo…'),
                              13, color='#B4C0D6', envolver=True))
        desp.agregar(_Dibujo(214, _dibujo_nombres))
        # 3
        desp.agregar(self._titulo(tr('3 · Las variantes: principal, principal 2 y principal 3')))
        desp.agregar(Etiqueta(tr('Para que todo el video no se vea igual puedes crear hasta 3 variantes del mismo estilo (otro color, otra posición, otra letra). La primera lleva solo el nombre; la segunda y la tercera llevan el número al final. El programa las agrupa por ese número: todo lo que termina en 2 forma la variante 2.'),
                              13, color='#B4C0D6', envolver=True))
        desp.agregar(_Dibujo(150, _dibujo_variantes))
        desp.agregar(Etiqueta(tr('Por eso cada variante necesita sus tres bloques con el mismo número: si falta uno, esa variante no se usa. Un número mayor que 3 (por ejemplo «principal 4») se ignora y el programa te avisa. Los bloques del video van alternando las variantes, o usan una fija si la eliges en «Estilo fijo».'),
                              13, color='#B4C0D6', envolver=True))
        # 4
        desp.agregar(self._titulo(tr('4 · Paso a paso')))
        pasos = (tr('Pulsa «Crea tu estilo», toca hasta 3 de los 48 ejemplos y pulsa «Crear mi pack». Ya viene con los nombres bien puestos.'),
                 tr('¿Quieres retocarlos? Pulsa «Abrir los 48 en Resolve»: se arma un timeline con los ejemplos hechos con Luxe Shine, Luxe Slide y los presets de Amro. Cambia fuente, color, tamaño y posición en el Inspector.'),
                 tr('Quédate con los que quieras (máximo 3 variantes), borra el resto y ponles el nombre exacto: clic derecho sobre el clip > cambiar nombre (principal, arriba, abajo, y «2» o «3» para las variantes).'),
                 tr('Exporta: Archivo > Exportar > Timeline (.drt), o clic derecho sobre un bin > Exportar bin (.drb).'),
                 tr('En CineCaptions, en «Pack de estilos», pulsa la tarjeta «Añadir plantilla (.drb)» y elige tu archivo. Si falta algo, el programa te dice qué.'))
        for k, texto in enumerate(pasos, 1):
            fila, cf = caja_h(espacio=10)
            n = Etiqueta(str(k), 13, peso='extra', color='#101626', alineacion=Qt.AlignmentFlag.AlignCenter)
            n.setFixedSize(26, 26)
            n.setStyleSheet(_hoja('background-color: %s; border-radius: 13px;' % AMARILLO))
            cf.addWidget(n, 0, Qt.AlignmentFlag.AlignTop)
            cf.addWidget(Etiqueta(texto, 13, color='#E0EBFB', envolver=True), 1)
            desp.agregar(fila)
        cerrar = Boton(tr('Entendido'), self.cerrar, tipo='primario', alto=38, tam=14, negrita=True)
        capa.addWidget(cerrar)

    @staticmethod
    def _titulo(texto):
        return Etiqueta(texto, 16, peso='extra', color=AMARILLO)
