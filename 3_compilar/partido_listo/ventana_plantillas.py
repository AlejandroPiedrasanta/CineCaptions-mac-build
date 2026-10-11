# CineCaptions · By Cinema Productions
# 1_codigo/ventana_plantillas.py — La pantalla «Estilos»: elegir el diseño de los subtítulos.
"""
ventana_plantillas.py
---------------------
La pantalla «Estilos»: elegir el diseño de los subtítulos.

Salió de «CineCaptions (script principal).py» (v5.4.44) SIN cambiar su código: el principal conserva la ventana principal (SubtitleApp) y vuelve a importar estos nombres, así que `cc_main.NombreDeClase` sigue existiendo.
"""
import sys
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QCursor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
import qt_kit as ui
import estilos_slider
from qt_kit import (Boton, Chip, Etiqueta, Menu, StringVar, Tarjeta, Tooltip, caja_h, despues, ejecutar_en_ui, limpiar_capa, messagebox, simpledialog, vivo)
from qt_kit import QColor
from i18n import tr
import plantillas
import fuentes_sistema
import instalar_fuentes
from ui_comun import (TEXT_MUTED, _CACHE_ESTILOS, _combinacion_visible, _correr_en_hilo, fuente, lineas_de_vista)
class _EstructuraPack(QWidget):
    """La estructura de un pack de un vistazo: arriba · principal · abajo · imagen (cada uno con el color de su rol) y
    cuantas variantes trae. Un bloque que el pack no trae sale hueco y apagado."""
    def __init__(self, datos):
        super().__init__()
        self._d = dict(datos or {})
        self.setFixedHeight(26)
        faltan = []
        if not self._d.get('imagen'):
            faltan.append(tr('Sin bloque «imagen»: el emoji va debajo del texto.'))
        self.setToolTip(' '.join(faltan) or tr('Trae los cuatro bloques: arriba, principal, abajo e imagen.'))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(fuente(10, peso='medio'))
        fm = QFontMetricsF(p.font())
        cy = self.height() / 2
        etiquetas = (('arriba', tr('arriba')), ('principal', tr('principal')), ('abajo', tr('abajo')), ('imagen', tr('imagen')))
        n = int(self._d.get('variantes') or 0)
        texto_n = (tr('{n} variantes', n=n) if n != 1 else tr('1 variante')) if n else ''
        total = sum(10 + fm.horizontalAdvance(t) + 10 for _k, t in etiquetas) - 10 + ((18 + fm.horizontalAdvance(texto_n)) if texto_n else 0)
        x = max(2.0, (self.width() - total) / 2.0)                 # v5.4.20: centrada (antes quedaba pegada a la izquierda)
        for clave, texto, color in (('arriba', tr('arriba'), ui.ROL_CONTEXTO), ('principal', tr('principal'), ui.ROL_PRINCIPAL),
                                    ('abajo', tr('abajo'), ui.ROL_COMPLEMENTO), ('imagen', tr('imagen'), ui.ROL_IMAGEN)):
            hay = bool(self._d.get(clave))
            c = QColor(color)
            if hay:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
            else:
                p.setPen(QPen(c, 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                c.setAlpha(110)
            p.drawEllipse(QPointF(x + 3.5, cy), 3.2, 3.2)
            p.setPen(QColor('#C9D6EC') if hay else QColor('#4F607A'))
            ancho = fm.horizontalAdvance(texto)
            p.drawText(QRectF(x + 10, 0, ancho + 4, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
            x += 10 + ancho + 10
        if texto_n:
            p.setPen(QColor('#7F8DA8'))
            p.drawText(QRectF(x + 8, 0, fm.horizontalAdvance(texto_n) + 6, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto_n)
        p.end()
class PlantillasWindow(QWidget):
    """Elegir el diseño de los subtitulos. DOS vistas, una por MODO
    (v1.0.70, pedido literal: «las nuevas plantillas solo deben ser
    visibles en los subtitulos normales... el modo dinamico dejalo tal
    cual estaba»):

    - modo "dinamico" (y los destacados): Media Pool / diseño automatico /
      packs importados, con el orden de prioridad que aplican los scripts
      dentro de Resolve. Nada de basicos.
    - modo "normal": SOLO las plantillas de SUBTITULOS BASICOS —
      «Clasica (Subtitle Template)» + un mosaico por pack de basicos con
      sus combinaciones 'inferior/superior N'.

    Un pack es una BANDEJA de Resolve exportada a .drb. Se importa una vez y
    queda en ~/DaVinciSubtitles/plantillas/, fuera del instalador. Tu
    eleccion se aplica al tocarla (on_elegir / on_basicos).
    v5.0.0: es el panel izquierdo de «Estilos y composición» (cuadricula de
    mosaicos con vista previa) + la tarjeta «Tipografías que usa el pack».
    """
    MOSTRAR_PRESETS = False
    def __init__(self, master, seleccion=None, on_elegir=None,
                 on_importar=None, on_importar_drt=None, formato=None,
                 diseno_actual=None, on_diseno=None,
                 basicos_actual=None, on_basicos=None, modo='dinamico', franja=None):
        super().__init__()
        self.app = master
        self.on_elegir = on_elegir
        self.on_importar = on_importar
        self.on_importar_drt = on_importar_drt
        self.on_diseno = on_diseno
        self._diseno = dict(diseno_actual or {'preset': 'clasico'})
        self._preset_retirado = None
        if not self.MOSTRAR_PRESETS and (self._diseno.get('preset') or 'clasico') != 'clasico':
            self._preset_retirado = self._diseno.get('preset')
            self._diseno = {'preset': 'clasico'}
        self.seleccion = StringVar(seleccion or 'auto')
        self.modo_real = modo
        self.modo = modo if modo in ('normal', 'dinamico') else 'dinamico'
        self.on_basicos = on_basicos
        self.basicos_var = StringVar(basicos_actual or '')
        self._formato_juego = formato
        self._tarjetas = {}
        self._fuentes_cache = {}
        self._envolver = []
        import estilos_slider
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(8)
        # v5.3.6: «Pack de estilos» = un slider horizontal de tarjetas VERTICALES sobre fotos de video (estilos_slider) y, debajo, el panel del
        # estilo que está al centro. Sin filtro de formato (las vistas son siempre verticales) y sin la tarjeta de tipografías.
        self.tarjeta = Tarjeta(espacio=8, margenes=(18, 12, 18, 10))
        if franja is not None:                        # v5.4.3: el audio (Obtener · archivo · onda · motor) va en UNA franja arriba de «Pack de estilos», en la misma tarjeta
            self.tarjeta.capa.addWidget(franja)
            separador = QFrame()
            separador.setFixedHeight(1)
            separador.setStyleSheet(ui.traducir_hoja('QFrame { background-color: #1E2A42; border: none; }'))
            self.tarjeta.capa.addWidget(separador)
        cab, ch = caja_h(espacio=12)
        ch.addWidget(Etiqueta(tr('Temas') if plantillas.SOLO_TEMAS else tr('Pack de estilos'), 18, peso='medio', color='#FFFFFF'))
        self.cuenta_lbl = Etiqueta('', 13, color=TEXT_MUTED)
        ch.addWidget(self.cuenta_lbl)
        ch.addStretch(1)
        if not plantillas.SOLO_TEMAS:
            ch.addWidget(Etiqueta(tr('Rueda, ← → o arrastra  ·  clic en la del centro para usarla'), 12, color=TEXT_MUTED))
        # «Crea tu estilo»: el único botón de la cabecera (las vistas reales de Resolve se piden solas)
        self.crear_btn = Boton(tr('Crea tu estilo'), self._crear_estilo, tipo='primario', alto=32, tam=13, negrita=True)
        icono_crear = ui.icono_linea('ph.sparkle-bold', '#FFFFFF')
        if icono_crear is not None:
            self.crear_btn.setIcon(icono_crear)
            self.crear_btn.setIconSize(QSize(15, 15))
        Tooltip(self.crear_btn, tr('Elige hasta 3 estilos de una galería y crea tu propio pack en un clic.'))
        ch.addWidget(self.crear_btn)
        self.tarjeta.capa.addWidget(cab)
        self.nota_modo = Etiqueta('', 13, color=ui.AMBAR, envolver=True)
        self.nota_modo.hide()
        self.tarjeta.capa.addWidget(self.nota_modo)
        self.filtro = StringVar(tr('Todos'))             # (sin filtro de formato: _formato_del_filtro() siempre es None)
        self.carrusel = estilos_slider.CarruselPacks(alto=480, flexible=True)
        self.carrusel.elegida.connect(self._elegir)
        self.carrusel.centrada.connect(self._pintar_info)
        self.carrusel.anadir.connect(self._importar_drt)
        self.tarjeta.capa.addWidget(self.carrusel, 1)
        # el panel del estilo que está al centro: nombre, aviso de tipografías, nota, estructura y botones
        self._carta_actual = None
        self.info_w = QWidget()
        iv = QVBoxLayout(self.info_w)
        iv.setContentsMargins(6, 0, 6, 0)
        iv.setSpacing(4)
        fila_n, cn = caja_h(espacio=12)
        cn.addStretch(1)
        self.info_nombre = Etiqueta('', 28, peso='extra', color='#FFFFFF')
        cn.addWidget(self.info_nombre)
        self.info_fuentes = ui.Enlace('', self._instalar_fuentes_central, 12, color=ui.AMBAR, color_hover=ui.NARANJA)
        self.info_fuentes.hide()
        cn.addWidget(self.info_fuentes)
        cn.addStretch(1)
        iv.addWidget(fila_n)
        self.info_sub = Etiqueta('', 12, peso='medio', color=ui.ACCENT_CLARO, alineacion=Qt.AlignmentFlag.AlignHCenter)      # v5.4.20: la frase corta del tema (en mayúsculas)
        iv.addWidget(self.info_sub)
        self.info_nota = Etiqueta('', 13, color=TEXT_MUTED, envolver=True, alineacion=Qt.AlignmentFlag.AlignHCenter)
        self.info_nota.setFixedWidth(620)               # (con la alineación al centro el texto envuelto se quedaba en ~300 px)
        self.info_nota.setMinimumHeight(40)             # dos líneas: sin esto la segunda se cortaba
        iv.addWidget(self.info_nota, 0, Qt.AlignmentFlag.AlignHCenter)
        self.info_extra = QVBoxLayout()
        self.info_extra.setContentsMargins(0, 0, 0, 0)
        self.info_extra.setSpacing(6)
        iv.addLayout(self.info_extra)
        fila_b, cb = caja_h(espacio=8)
        cb.addStretch(1)
        self.info_izq = QWidget()                      # v5.4.20: del ancho de los botones de la derecha, para que «Usar este tema» quede justo en el centro
        cb.addWidget(self.info_izq)
        self.usar_btn = Boton(tr('Usar este tema') if plantillas.SOLO_TEMAS else tr('Usar este estilo'), self._usar_central, tipo='primario', alto=40, ancho=220, tam=14, negrita=True)
        cb.addWidget(self.usar_btn)
        self.info_acciones_w = QWidget()
        self.info_acciones = QHBoxLayout(self.info_acciones_w)
        self.info_acciones.setContentsMargins(0, 0, 0, 0)
        self.info_acciones.setSpacing(6)
        cb.addWidget(self.info_acciones_w)
        cb.addStretch(1)
        iv.addWidget(fila_b)
        self.tarjeta.capa.addWidget(self.info_w)
        self.ocultos_lnk = ui.Enlace('', self._mostrar_ocultos, 12, color=TEXT_MUTED, color_hover=ui.ACCENT_CLARO)
        self.ocultos_lnk.hide()
        self.tarjeta.capa.addWidget(self.ocultos_lnk, 0, Qt.AlignmentFlag.AlignLeft)
        capa.addWidget(self.tarjeta, 1)
        self._recargar()
    def actualizar(self, seleccion=None, basicos_actual=None, modo=None, formato=None, diseno_actual=None):
        """La app avisa de un cambio de modo, formato o eleccion."""
        if seleccion is not None:
            self.seleccion.set(seleccion)
        if basicos_actual is not None:
            self.basicos_var.set(basicos_actual)
        if diseno_actual is not None:
            self._diseno = dict(diseno_actual)
        if modo is not None:
            self.modo_real = modo
            self.modo = modo if modo in ('normal', 'dinamico') else 'dinamico'
        if formato is not None:
            self._formato_juego = formato
        self._recargar(self.seleccion.get())
    def existe(self):
        return vivo(self)
    def cerrar(self):
        return None
    def _crear_estilo(self):
        """«Crea tu estilo»: una galería simple de ejemplos con imagen. Se tocan hasta 3, se le pone nombre y «Crear mi pack» arma el pack en el acto."""
        import crea_estilo_ui
        actual = getattr(self, '_galeria_estilo', None)
        if actual is not None and vivo(actual):
            actual.traer()
            return
        self._galeria_estilo = crea_estilo_ui.CreaEstiloDialogo(self.app, self._crear_pack_de_ejemplos, self._abrir_guia_resolve, self._ayuda_estilo,
                                                                al_resolve_uno=lambda i: self._abrir_guia_resolve([i]))
        self._galeria_estilo.show()
    def _ayuda_estilo(self):
        """El «!»: por qué los clips se llaman principal / arriba / abajo / simple, qué son las variantes 2 y 3 y cómo se exporta."""
        import crea_estilo_ui
        actual = getattr(self, '_ayuda_dlg', None)
        if actual is not None and vivo(actual):
            actual.traer()
            return
        self._ayuda_dlg = crea_estilo_ui.AyudaEstilo(self.app)
        self._ayuda_dlg.show()
    def _abrir_guia_resolve(self, ids=None):
        crear = getattr(self.app, '_crear_tu_estilo', None)
        if crear:
            crear(ids)
    def _crear_pack_de_ejemplos(self, nombre, ids, terminado):
        """Arma el pack con los ejemplos elegidos (en un hilo) y avisa a la galería con terminado(ok)."""
        existente = plantillas.buscar_pack(nombre)
        if existente is not None and getattr(existente, 'incorporado', False):
            ui.error_con_acciones(tr('Crea tu estilo'), tr('«{n}» es el nombre de un pack del programa. Elige otro nombre.', n=nombre), parent=self)
            terminado(False)
            return
        if existente is not None and not messagebox.askyesno(tr('Crea tu estilo'), tr('Ya tienes un pack llamado «{n}». ¿Lo reemplazo por este?', n=nombre), parent=self):
            terminado(False)
            return
        def trabajo():
            if ids and isinstance(ids[0], str):                      # v5.4.30: looks de los tres temas (mezcla_planificador): un pack de mezcla
                import mezcla_planificador
                return mezcla_planificador.crear_pack(nombre, ids)
            import ejemplos_estilo
            return ejemplos_estilo.crear_pack(nombre, ids)
        def fin(resultado, error):
            if not vivo(self):
                return
            if error or not resultado:
                ui.error_con_acciones(tr('Crea tu estilo'), tr('No pude armar el pack: {e}', e=error or '?'), parent=self)
                terminado(False)
                return
            nombre_final, _carpeta = resultado
            try:
                self._recargar(self.seleccion.get())
            except Exception:
                pass
            import ui_toast
            ui_toast.mostrar(self.app, tr('Pack «{n}» creado con {k} variantes. Búscalo en «Pack de estilos».', n=nombre_final, k=len(ids)), duracion_ms=6000)
            terminado(True)
        _correr_en_hilo(self, trabajo, fin)
    def _ajustar_wrap(self, evento=None):
        """En Qt el ajuste de linea sigue solo al ancho."""
        return None
    _FUENTES_DINAMICO = ('Montserrat', 'Open Sans', 'Arial', 'Impact', 'Verdana', 'Georgia', 'Tahoma', 'Segoe UI')
    _ESTILOS_FUENTE = ('Light', 'Regular', 'SemiBold', 'Bold', 'ExtraBold', 'Black', 'Italic')
    _ROLES_DINAMICO = (('context', 'Arriba'), ('main', 'Principal'), ('complement', 'Abajo'))
    def _diseno_resuelto(self):
        """El diseño con preset y retoques ya mezclados (via plantillas)."""
        return plantillas.diseno_para_manifiesto(self._diseno)['diseno']
    def _emitir_diseno(self):
        """Aplica en el acto: guarda el estado y elige el modo."""
        if self.on_diseno:
            self.on_diseno(dict(self._diseno))
        self.seleccion.set('dinamico')
        self._realzar()
    def _tocar_rol(self, rol, campo, valor):
        estilos = self._diseno.setdefault('estilos', {})
        estilos.setdefault(rol, {})[campo] = valor
        self._emitir_diseno()
    def _elegir(self, valor):
        """Marca ese valor Y LO APLICA en el acto (la eleccion ya esta
        guardada antes de que el usuario piense en irse)."""
        if self.modo == 'normal':
            if valor == '__clasica__':
                self.basicos_var.set('')
                if callable(self.on_basicos):
                    self.on_basicos('')
                self._realzar()
            return
        self.seleccion.set(valor)
        self._realzar()
        if self.on_elegir:
            self.on_elegir(valor)
    def _valor_actual(self):
        """El valor que está en uso (el de la tarjeta con «En uso»)."""
        if self.modo == 'normal':
            return (self.basicos_var.get() or '').split('||')[0] or '__clasica__'
        return self.seleccion.get()
    def _realzar(self):
        """Marca en el slider la tarjeta en uso y actualiza el botón del panel."""
        self.carrusel.poner_elegida(self._valor_actual())
        self._pintar_boton_usar()
    def _pintar_info(self, carta=None):
        """El panel de debajo del slider con lo de la tarjeta que llegó al centro."""
        carta = carta or self.carrusel.carta_central()
        self._carta_actual = carta
        limpiar_capa(self.info_acciones)
        limpiar_capa(self.info_extra)
        if carta is None:
            self.info_w.hide()
            return
        self.info_w.show()
        self.info_nombre.setText(tr('Trae tu propio estilo') if carta.tipo == 'anadir' else carta.titulo)
        if carta.pack is not None and carta.estado and carta.color_estado not in (ui.VERDE, TEXT_MUTED):
            self.info_fuentes.configure(text='⚠ ' + carta.estado + ' · ' + tr('instalar'))
            self.info_fuentes.show()
        else:
            self.info_fuentes.hide()
        solo_temas = plantillas.SOLO_TEMAS and carta.pack is not None and plantillas.es_de_fabrica(carta.pack.nombre)       # v5.4.22: de un tema de fábrica solo se ve el NOMBRE y el BOTÓN (sin frase, descripción, leyenda, lápiz ni «⋯»)
        self.info_sub.setVisible(False)
        texto = '' if solo_temas else (carta.nota or carta.detalle)
        self.info_nota.setText(texto)
        self.info_nota.setVisible(bool(texto))
        if carta.estructura and not solo_temas and not carta.estructura.get('mezcla'):          # (un estilo mezclado no tiene arriba / principal / abajo: su nota lista los looks)
            e = _EstructuraPack(carta.estructura)
            e.setFixedWidth(360)
            self.info_extra.addWidget(e, 0, Qt.AlignmentFlag.AlignHCenter)
        if carta.extra is not None:
            self.info_extra.addWidget(carta.extra(), 0, Qt.AlignmentFlag.AlignHCenter)
        for icono, glifo, ayuda, fn in ([] if solo_temas else carta.acciones):         # v5.8: ✎ editar en Resolve y 🗑 quitar
            ic = ui.icono_linea(icono, '#C9D6EC')
            b = Boton('' if ic is not None else glifo, lambda _=False, f=fn: f(), tipo='fantasma', alto=36, ancho=40, tam=14, icono=ic)
            b.setFixedWidth(42)
            Tooltip(b, ayuda)
            self.info_acciones.addWidget(b)
        menu_carta = None if solo_temas else carta.menu
        if menu_carta:
            m = Boton('⋯', lambda menu=menu_carta: self._menu_carta(menu), tipo='fantasma', alto=36, ancho=40, tam=16)
            m.setFixedWidth(42)
            self.info_acciones.addWidget(m)
        self.info_izq.setVisible(self.info_acciones.count() > 0)
        self.info_izq.setFixedWidth(max(0, self.info_acciones.count() * 48 - 6))
        self._pintar_boton_usar()
    def _menu_carta(self, opciones):
        menu = Menu(self)
        for texto, fn in opciones:
            menu.agregar(texto, fn)
        menu.mostrar(QCursor.pos())
    def _pintar_boton_usar(self):
        c = getattr(self, '_carta_actual', None)
        if c is None:
            return
        if c.tipo == 'anadir':
            self.usar_btn.setText(tr('Añadir plantilla (.drb)'))
            self.usar_btn.setEnabled(True)
            self.usar_btn.setVisible(True)
            return
        # en el modo «normal» la elección es la combinación (chips de abajo), no el pack
        self.usar_btn.setVisible(not (self.modo == 'normal' and c.valor != '__clasica__'))
        en_uso = c.valor == self._valor_actual()
        self.usar_btn.setText('✓ ' + tr('En uso') if en_uso else (tr('Usar este tema') if plantillas.SOLO_TEMAS else tr('Usar este estilo')))
        self.usar_btn.setEnabled(not en_uso)
        # «En uso» no es un botón apagado: es una confirmación (verde)
        self.usar_btn.setStyleSheet(ui.traducir_hoja('QPushButton:disabled { background-color: #0F2A22; border: 1px solid #1F7A56; color: #6FE3AE; }') if en_uso else '')
    def _usar_central(self):
        c = getattr(self, '_carta_actual', None)
        if c is None:
            return
        if c.tipo == 'anadir':
            self._importar_drt()
        else:
            self._elegir(c.valor)
    def _instalar_fuentes_central(self):
        c = getattr(self, '_carta_actual', None)
        if c is not None and c.pack is not None:
            self._instalar_fuentes(c.pack)
    def _hacer_clicable(self, widget, valor):
        """Compat: el mosaico entero ya elige."""
        return None
    def _pack_de(self, valor):
        if valor in ('media_pool', '', None):
            return None
        if valor == 'auto':
            return plantillas.pack_incorporado()
        return plantillas.buscar_pack(valor)
    def _fuentes_listas(self):
        """El índice de fuentes terminó: las tarjetas se repintan con el estado real de las tipografías."""
        self._fuentes_esperando = False
        try:
            if vivo(self):
                self._recargar(self.seleccion.get())
        except Exception:
            pass
    def _estado_fuentes(self, pack):
        """('Tipografías ok', verde) / ('Faltan N tipografías', ambar)."""
        if pack is None:
            return (None, None)
        try:                                   # v5.4.8: sin esperar al primer índice de fuentes (la interfaz no se queda parada): se muestra «Comprobando…» y se refresca al terminar
            if not fuentes_sistema.indice_listo():
                if not getattr(self, '_fuentes_esperando', False):
                    self._fuentes_esperando = True
                    fuentes_sistema.al_estar_listo(lambda: ejecutar_en_ui(self._fuentes_listas))
                return (tr('Comprobando tipografías…'), TEXT_MUTED)
        except Exception:
            pass
        try:
            arreglables, sin_remedio = instalar_fuentes.faltantes(pack.fuentes())
        except Exception:
            return (None, None)
        if sin_remedio:
            return (tr('Faltan {n} tipografías', n=len(arreglables) + len(sin_remedio)), ui.ROJO)
        if arreglables:
            return (tr('Faltan {n} tipografías', n=len(arreglables)), ui.AMBAR)
        return (tr('Tipografías ok'), ui.VERDE)
    def _texto_formatos(self, pack):
        letras = [plantillas.ETIQUETA_FORMATO[f][0] for f in ('h', 'v', 'c') if pack is not None and f in pack.formatos]
        return ' · '.join(letras) if letras else None
    def _miniatura(self, pack):
        if pack is None:
            return None
        try:
            for n in list(pack.numeros_de_set(pack.formatos[0] if pack.formatos else 'h'))[:1] + ['base']:
                ruta = pack.ruta_miniatura(n)
                if ruta:
                    return ui.pixmap_de_archivo(ruta, 200)
        except Exception:
            pass
        return None
    def _formato_vista(self, pack):
        """Las vistas previas son SIEMPRE verticales (9:16); un pack sin vertical enseña su primer formato."""
        if pack is None:
            return None
        if 'v' in (pack.formatos or ()):
            return 'v'
        return pack.formatos[0] if pack.formatos else None
    def _formato_edicion(self, pack):
        """El formato con el que se abre un pack en Resolve para editarlo: el del timeline en juego si el pack lo trae."""
        f = self._formato_juego
        if pack is not None and f not in (pack.formatos or ()):
            return pack.formatos[0] if pack.formatos else None
        return f
    # -- v5.2: vistas previas REALES (renderizadas por Resolve) -------------------
    def _real_de(self, pack):
        """(sets, recortes) del render real ya hecho de ese pack, o None."""
        if pack is None:
            return None
        try:
            import vistas_reales
            formato = self._formato_vista(pack) or (pack.formatos[0] if pack.formatos else 'v')
            sets = vistas_reales.cacheadas(pack.nombre, formato)
            return (sets, vistas_reales.recortes(pack.nombre, formato)) if sets else None
        except Exception:
            return None
    def _renderizar_reales(self, solo=None, silencioso=False):
        """Resolve renderiza la vista real de los packs visibles que aun no
        la tienen (o de 'solo'). En un hilo; la cuadricula se rehace al final."""
        if getattr(self, '_renderizando', False):
            return
        import vistas_slider
        packs = []
        if solo is not None:
            packs = [solo]
        else:
            formato = self._formato_del_filtro()
            vistos = set()
            for p in [plantillas.pack_incorporado()] + [p for p in plantillas.listar_packs() if not getattr(p, 'es_basicos', False)]:
                if p is None or (formato is not None and formato not in p.formatos) or p.nombre in vistos:
                    continue
                vistos.add(p.nombre)
                if not self._real_de(p) and not vistas_slider.ruta_video(p.nombre):
                    packs.append(p)
        if not packs:
            if not silencioso:
                self.cuenta_lbl.configure(text=tr('Todas las vistas reales están al día'))
            return
        self._renderizando = True
        estado = {'texto': tr('Abriendo Resolve…'), 'hechos': 0, 'errores': []}
        def trabajo():
            import vistas_reales
            for pack in packs:
                estado['texto'] = tr('Resolve renderiza «{p}» ({n} de {t})…', p=pack.nombre, n=estado['hechos'] + 1, t=len(packs))
                formato = self._formato_vista(pack) or (pack.formatos[0] if pack.formatos else 'v')
                ok, r = vistas_reales.renderizar_pack(pack.nombre, formato, al_estado=lambda t: estado.__setitem__('texto', t),
                                                      abrir_resolve=not silencioso)
                if not ok:
                    estado['errores'].append(f'{pack.nombre}: {r}')
                    if 'Resolve' in str(r) and not estado['hechos']:
                        break
                estado['hechos'] += 1
        def avance():
            if getattr(self, '_renderizando', False) and vivo(self):
                self.cuenta_lbl.configure(text=estado['texto'])
                despues(300, avance, self)
        def fin(_r, _e):
            self._renderizando = False
            if not vivo(self):
                return
            self._recargar(self.seleccion.get())
            if estado['errores'] and not silencioso:
                messagebox.showwarning(tr('Vista real'), '\n'.join(estado['errores'][:4]), parent=self)
        avance()
        _correr_en_hilo(self, trabajo, fin)
    def _carta_simple(self, valor, titulo, detalle):
        """Media Pool / Diseño automático."""
        pack = self._pack_de(valor)
        if valor == 'media_pool':
            lineas = [(tr('Tus Text+'), {'familia': ui.familia_ui(), 'peso': 'Medium', 'tam': 0.13, 'color': '#C9D6EC'}),
                      (tr('del Media Pool'), {'familia': ui.familia_ui(), 'peso': 'Bold', 'tam': 0.17, 'color': '#FFFFFF'})]
            estado, color = (tr('Manda sobre todo'), TEXT_MUTED)
        else:
            lineas = lineas_de_vista(valor, self._formato_vista(pack))
            estado, color = self._estado_fuentes(pack)
        est = plantillas.estructura_de(pack) if pack else None
        return estilos_slider.Carta(valor, titulo, lineas=lineas, real=self._real_de(pack) if pack else None,
                                    formatos=self._texto_formatos(pack) or '', meta=self._meta_de(est) or (tr('Manda sobre todo') if valor == 'media_pool' else ''),
                                    estado=estado, color_estado=color, estructura=est, detalle=detalle, pack=pack,
                                    acciones=self._acciones_de(pack, quitable=False) if pack else None)
    @staticmethod
    def _meta_de(estructura):
        if (estructura or {}).get('mezcla'):
            return tr('Mezcla de temas')
        if (estructura or {}).get('viral'):
            return tr('Subtítulos virales')
        if (estructura or {}).get('kinetic'):
            return tr('Títulos de gancho')
        n = int((estructura or {}).get('variantes') or 0)
        return (tr('{n} variantes', n=n) if n != 1 else tr('1 variante')) if n else ''
    def _cartas_basicos(self):
        """La vista del MODO NORMAL (v1.0.70): «Clásica (Subtitle Template)» + una tarjeta por pack de SUBTITULOS BASICOS; las combinaciones
        'inferior/superior N' (leidas del PROPIO pack, info_drb) salen como chips en el panel de la tarjeta del centro. El valor es pack-scoped
        («<pack>||inferior 2») sobre basicos_var; se aplica AL TOCAR via on_basicos."""
        cartas = [estilos_slider.Carta('__clasica__', tr('Clásica (Subtitle Template)'),
                                       lineas=[(tr('Así se ven'), {'familia': 'Montserrat', 'peso': 'SemiBold', 'tam': 0.13, 'color': '#FFFFFF'}),
                                               (tr('tus subtítulos'), {'familia': 'Montserrat', 'peso': 'SemiBold', 'tam': 0.13, 'color': '#FFFFFF'})],
                                       estado=tr('Tu Media Pool'), color_estado=TEXT_MUTED, meta=tr('Tu Media Pool'),
                                       detalle=tr('El Text+ «Subtitle Template» de tu Media Pool, como siempre.'))]
        packs = [p for p in plantillas.listar_packs() if getattr(p, 'es_basicos', False)]
        elegido_pack = (self.basicos_var.get() or '').split('||')[0]
        if elegido_pack and not any(p.nombre == elegido_pack for p in packs):
            self.basicos_var.set('')
        self._chips_basicos = []
        for pack in packs:
            menu = None if pack.incorporado else [(tr('Quitar'), lambda n=pack.nombre: self._quitar_basicos(n))]
            estado, color = self._estado_fuentes(pack)
            cartas.append(estilos_slider.Carta(pack.nombre, pack.nombre,
                                               lineas=[(tr('Así se ven'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.13, 'color': '#FFFFFF'}),
                                                       (tr('tus subtítulos'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.13, 'color': ui.ROL_PRINCIPAL})],
                                               formatos=self._texto_formatos(pack) or '', estado=estado, color_estado=color, menu=menu, pack=pack,
                                               extra=lambda pk=pack: self._widget_combos(pk)))
        cartas.append(estilos_slider.Carta('__anadir__', tr('Añadir plantilla (.drb)'), tipo='anadir', detalle=tr('Exporta una bandeja desde Resolve y súbela aquí: queda guardada como un estilo más.')))
        if not packs:
            self.nota_modo.configure(text=tr('No hay plantillas de básicos: añade un .drb con clips \'basico inferior 1\', \'traducion inferior 1\'… (botón de arriba), o queda la clásica.'), text_color='#E0A030')
            self.nota_modo.show()
        try:
            self.cuenta_lbl.configure(text=tr('{len} de básicos', len=len(packs)) if packs else '')
        except Exception:
            pass
        return cartas
    def _widget_combos(self, pack):
        """Los chips con las combinaciones de básicos de un pack (en el panel de su tarjeta)."""
        combos = {}
        for f in pack.formatos:
            info = pack.info_drb(f) or {}
            for pos, numeros in (info.get('basicos') or {}).items():
                combos.setdefault(pos, set()).update(numeros)
        flujo_w = QWidget()
        flujo = ui.FlujoCapa(flujo_w, 6, 6)
        for pos in plantillas.POSICIONES_BASICOS:
            for n in sorted(combos.get(pos, ())):
                valor = f'{pack.nombre}||{pos} {n}'
                chip = Chip(_combinacion_visible(f'{pos} {n}').capitalize(), ui.ACCENT_CLARO, lambda v=valor: self._elegir_basicos(v), alto=26, tam=12)
                chip._valor = valor
                flujo.addWidget(chip)
                self._chips_basicos.append(chip)
        flujo_w.setMaximumWidth(620)
        self._pintar_basicos_chips()
        return flujo_w
    def _elegir_basicos(self, valor):
        self.basicos_var.set(valor)
        if callable(self.on_basicos):
            self.on_basicos(valor)
        self._realzar()
        self._pintar_basicos_chips()
    def _pintar_basicos_chips(self):
        actual = self.basicos_var.get() or ''
        self._chips_basicos = [c for c in getattr(self, '_chips_basicos', []) if vivo(c)]
        for chip in self._chips_basicos:
            chip.poner(lleno=chip._valor == actual)
    def _quitar_basicos(self, nombre):
        """Borra un pack de basicos del usuario (con confirmacion)."""
        if not messagebox.askyesno(tr('Quitar plantilla'), tr('¿Quitar la plantilla de básicos «{nombre}»?\n\nSolo se borra del programa; tu .drb original no se toca.', nombre=nombre), parent=self):
            return
        try:
            plantillas.borrar_pack(nombre)
        except Exception as e:
            messagebox.showerror(tr('No pude quitarla'), str(e), parent=self)
        self._recargar(self.seleccion.get())
    def _recargar(self, seleccionar=None):
        """Rehace el slider. Con 'seleccionar', ademas apunta ese pack (hasta la v1.0.26 no lo hacia y un pack recien importado se pisaba
        con "auto": «simula que los importa pero al generar no los toma»). Se queda en la tarjeta que estaba al centro."""
        if seleccionar:
            self.seleccion.set(seleccionar)
        self.setUpdatesEnabled(False)
        try:
            self._envolver = []
            self.nota_modo.hide()
            self.ocultos_lnk.hide()
            if self.modo == 'normal':
                self.carrusel.poner_cartas(self._cartas_basicos(), self._valor_actual())
                self._realzar()
                return
            if self.modo_real == 'destacados':
                self.nota_modo.configure(text=tr('Los looks destacados (Hormozi, Gadzhi, Acumulativo y Pintado) traen su propio diseño: el pack se usa en los Dinámicos.'), text_color=ui.AMBAR)
                self.nota_modo.show()
            cartas = []                               # v5.4.4: solo packs de verdad (nada de «Media Pool» ni «Diseño automático»)
            import ajustes_ui
            ocultos = [n for n in ajustes_ui.leer_prefs().get('packs_ocultos', []) if isinstance(n, str)]
            todos = [p for p in plantillas.listar_packs()
                     if not (getattr(p, 'incorporado', False)
                             and p.nombre == plantillas.NOMBRE_INCORPORADO)
                     and not getattr(p, 'es_basicos', False)]
            packs = [p for p in todos if not (p.incorporado and p.nombre in ocultos and not plantillas.es_de_fabrica(p.nombre))]
            packs = [p for p in packs if plantillas.pack_permitido(p.nombre)]                 # v5.4.22: los tres temas de fábrica + los packs del usuario
            _orden_temas = list(plantillas.FABRICA)
            packs.sort(key=lambda p: _orden_temas.index(p.nombre) if p.nombre in _orden_temas else len(_orden_temas))       # Tema 1, 2, 3, 4 en ese orden (después, los del usuario)
            quitados = len(todos) - len(packs)
            self.ocultos_lnk.hide()                   # v5.4.5: sin «Mostrar los packs quitados» (se quitó el enlace de Proyecto)
            for pack in packs:
                cartas.append(self._carta_pack(pack))
            cartas.append(estilos_slider.Carta('__anadir__', tr('Añadir plantilla (.drb)'), tipo='anadir', detalle=tr('Exporta una bandeja desde Resolve y súbela aquí: queda guardada como un estilo más.')))
            self.carrusel.poner_cartas(cartas, self._valor_actual())
            try:
                self.cuenta_lbl.configure(text='' if plantillas.SOLO_TEMAS else (tr('1 pack') if len(packs) == 1 else tr('{n} packs', n=len(packs))))
            except Exception:
                pass
            self._realzar()
        finally:
            self.setUpdatesEnabled(True)
    def _formato_del_filtro(self):
        """Ya no hay filtro de formato (las vistas son siempre verticales): siempre None = todos los packs."""
        return None
    def _carta_pack(self, pack):
        """La tarjeta de un pack importado o incluido (II inferior/superior)."""
        menu = [(tr('✎ Descripción'), lambda p=pack.nombre: self._editar_descripcion(p))]
        if getattr(pack, 'notas', None) or pack.problemas:
            menu.append((tr('Detalles…'), lambda p=pack: self._detalles(p)))
        if not pack.incorporado:
            menu.append((tr('Quitar'), lambda p=pack.nombre: self._borrar(p)))
        estado, color = self._estado_fuentes(pack)
        aviso = '\n'.join('· ' + p for p in pack.problemas) if pack.problemas else None
        est = plantillas.estructura_de(pack)
        import vistas_slider
        return estilos_slider.Carta(pack.nombre, plantillas.nombre_visible(pack.nombre), lineas=lineas_de_vista(pack.nombre, self._formato_vista(pack)),
                                    video=vistas_slider.ruta_video(pack.nombre), poster=vistas_slider.ruta_poster(pack.nombre) or self._poster_mezcla(pack),
                                    real=self._real_de(pack), formatos=self._texto_formatos(pack) or '', meta=self._meta_de(est),
                                    estado=estado, color_estado=color, nota=plantillas.leer_descripciones().get(pack.nombre, '') or self._nota_mezcla(pack),
                                    aviso=aviso, acciones=self._acciones_de(pack, quitable=not plantillas.es_de_fabrica(pack.nombre)), menu=menu, estructura=est, pack=pack)
    @staticmethod
    def _nota_mezcla(pack):
        """Lo que mezcla un estilo propio de «Crea tu estilo» (sus looks, con el tema de cada uno); '' si no es de mezcla."""
        if not getattr(pack, 'mezcla', False):
            return ''
        try:
            import mezcla_planificador
            partes = [f"T{l['tema']} · {l['nombre']}" for l in (mezcla_planificador.look_de(i) for i in pack.looks) if l]
            return tr('Mezcla: {l}', l='  ·  '.join(partes)) if partes else ''
        except Exception:
            return ''
    @staticmethod
    def _poster_mezcla(pack):
        """La foto de la tarjeta de un estilo mezclado («Crea tu estilo»): vista_mezcla.jpg, que se hizo al crearlo (o se rehace si falta)."""
        if not getattr(pack, 'mezcla', False):
            return None
        ruta = Path(pack.carpeta) / 'vista_mezcla.jpg'
        if not ruta.is_file():
            try:
                import mezcla_vista
                mezcla_vista.poster(pack.looks, foto=0, ancho=540).save(ruta, quality=88)
            except Exception:
                return None
        return ruta
    def _acciones_de(self, pack, quitable=True):
        """Los botones de la tarjeta de un estilo: ✎ editar en Resolve y 🗑 quitar (los incluidos no se borran del disco: se quitan de la lista)."""
        acciones = [] if getattr(pack, 'mezcla', False) else [('ph.pencil-simple-bold', '✎', tr('Editar en Resolve: abre el timeline de este estilo para cambiar fuente, color, tamaño o posición. Luego lo exportas (.drt) y lo añades de nuevo. También con doble clic.'),
                     lambda p=pack: self._editar_en_resolve(p))]          # (un estilo mezclado no se edita en Resolve: se vuelve a crear en «Crea tu estilo»)
        if quitable:
            ayuda = tr('Quitar de la lista (es un pack incluido en el programa: no se borra del disco)') if pack.incorporado else tr('Quitar este estilo')
            acciones.append(('ph.trash-bold', '🗑', ayuda, lambda p=pack: self._quitar_pack(p)))
        return acciones
    def _quitar_pack(self, pack):
        if plantillas.es_de_fabrica(pack.nombre):            # v5.4.5: los Shine vienen de fábrica y no se quitan
            return
        if not pack.incorporado:
            self._borrar(pack.nombre)
            return
        if not messagebox.askyesno(tr('Quitar el pack'), tr('¿Quitar «{nombre}» de la lista?\n\nEs un pack incluido en el programa: no se borra del disco y puedes volver a mostrarlo cuando quieras.', nombre=pack.nombre), parent=self):
            return
        import ajustes_ui
        ocultos = [n for n in ajustes_ui.leer_prefs().get('packs_ocultos', []) if isinstance(n, str)]
        if pack.nombre not in ocultos:
            ocultos.append(pack.nombre)
        ajustes_ui.guardar_prefs({'packs_ocultos': ocultos})
        if self.seleccion.get() == pack.nombre:
            self.seleccion.set('auto')
            if self.on_elegir:
                self.on_elegir('auto')
        self._recargar()
    def _mostrar_ocultos(self):
        import ajustes_ui
        ajustes_ui.guardar_prefs({'packs_ocultos': []})
        self._recargar()
    def _editar_en_resolve(self, pack):
        """✎ / doble clic: abre el timeline del pack en Resolve para modificarlo (edicion_pack.py)."""
        if getattr(self, '_editando_pack', False) or pack is None or getattr(pack, 'mezcla', False):          # (un estilo mezclado no tiene timeline que editar)
            return
        self._editando_pack = True
        formato = self._formato_edicion(pack) or (pack.formatos[0] if pack.formatos else 'v')
        self.app.status_var.set(tr('Abriendo «{n}» en Resolve para editarlo…', n=pack.nombre))
        def trabajo():
            import edicion_pack
            return edicion_pack.abrir_en_resolve(pack, formato, al_estado=lambda t: self.app.msg_queue.put(('status', t)))
        def fin(resultado, error):
            self._editando_pack = False
            if not vivo(self):
                return
            ok, mensaje = resultado if (resultado and not error) else (False, str(error or ''))
            if ok:
                self.app.status_var.set(tr('Listo: «{n}» está abierto en Resolve. Cambia lo que quieras y exporta el timeline (Archivo > Exportar > Timeline, .drt); luego añádelo con «Añadir plantilla (.drb)».', n=pack.nombre))
                import ui_toast
                ui_toast.mostrar(self.app, tr('«{n}» está abierto en Resolve para editarlo', n=pack.nombre))
            else:
                self.app.status_var.set(tr('No pude abrir el pack en Resolve: {m}', m=mensaje))
                messagebox.showwarning(tr('Editar en Resolve'), tr('No pude abrir el pack en Resolve: {m}', m=mensaje), parent=self)
        _correr_en_hilo(self, trabajo, fin)
    def _detalles(self, pack):
        lineas = []
        if pack.problemas:
            lineas.append('\n'.join('⚠ ' + p for p in pack.problemas))
        cuentas = {f: len(pack.numeros_de_set(f)) for f in ('h', 'v') if f in pack.formatos}
        if cuentas:
            lineas.append(' · '.join(f'{plantillas.ETIQUETA_FORMATO[f]}: ' + (tr('{n} combinación', n=n) if n == 1 else tr('{n} combinaciones', n=n)) for f, n in cuentas.items()))
        if getattr(pack, 'notas', None):
            lineas.append(tr('Combinaciones completas por formato.\n\nDetalle:\n') + '\n'.join('· ' + n for n in pack.notas))
        messagebox.showinfo(pack.nombre, '\n\n'.join(lineas) or tr('Sin combinaciones'), parent=self)
    def _editar_descripcion(self, nombre):
        """Pide la descripcion corta del pack y la guarda por nombre (v1.0.67:
        una nota del usuario para ubicar cada plantilla; vacio la borra)."""
        actual = plantillas.leer_descripciones().get(nombre, '')
        nueva = simpledialog.askstring(tr('Descripción de la plantilla'), tr('Una nota corta para «{nombre}»\n(cómo es, para qué la usas — vacío la borra):', nombre=nombre), initialvalue=actual, parent=self)
        if nueva is None:
            return
        plantillas.guardar_descripcion(nombre, nueva)
        self._recargar(self.seleccion.get())
    def _instalar_fuentes(self, pack):
        """Instala en el sistema las tipografias del pack que falten.

        Instalar fuentes TOCA EL SISTEMA del usuario, asi que nunca pasa
        solo: siempre detras de un boton y contandole que se instalo y que
        no. Y se VERIFICA despues.
        """
        instaladas, fallos, sin_remedio, verificadas = instalar_fuentes.instalar_faltantes(pack.fuentes())
        self._fuentes_cache.clear()
        try:
            fuentes_sistema.invalidar_cache()
        except Exception:
            pass
        lineas = []
        if verificadas:
            lineas.append(tr('Instalé {len} tipografías.', len=len(verificadas)))
            if sys.platform == 'darwin':
                lineas.append(tr('Reinicia Resolve para que las vea (lee las tipografías al arrancar).'))
        else:
            if instaladas:
                lineas.append(tr('Copié {len} archivos, pero el sistema todavía no las reconoce. Prueba a reiniciar Resolve.', len=len(instaladas)))
        if fallos:
            lineas.append(tr('No pude con: ') + '; '.join((f'{n} ({m})' for n, m in fallos)))
        if sin_remedio:
            lineas.append(tr('Estas no las traigo incluidas: ') + ', '.join((f'{f} {e}' for f, e in sin_remedio)))
        if not lineas:
            lineas.append(tr('No faltaba ninguna: ya estaban todas instaladas.'))
        if fallos or sin_remedio:
            messagebox.showwarning(tr('Tipografías'), '\n\n'.join(lineas), parent=self)
        else:
            messagebox.showinfo(tr('Tipografías'), '\n\n'.join(lineas), parent=self)
        self._recargar(self.seleccion.get())
    def _borrar(self, nombre):
        if not messagebox.askyesno(tr('Quitar el pack'), tr('¿Quitar «{nombre}»?\n\nSolo se borra el pack. Tu timeline de Resolve y tus proyectos no se tocan, y puedes volver a importarlo cuando quieras.', nombre=nombre), parent=self):
            return
        plantillas.borrar_pack(nombre)
        _CACHE_ESTILOS.pop(nombre, None)
        if self.seleccion.get() == nombre:
            self.seleccion.set('auto')
            if self.on_elegir:
                self.on_elegir('auto')
        self._recargar()
    def _importar(self):
        if self.on_importar:
            self.on_importar(self._recargar)
    def _importar_drt(self):
        if self.on_importar_drt:
            self.on_importar_drt(self._recargar)
    def _aceptar(self):
        """Compat: la eleccion ya viaja al tocarla (_elegir)."""
        if self.on_elegir:
            self.on_elegir(self.seleccion.get())
