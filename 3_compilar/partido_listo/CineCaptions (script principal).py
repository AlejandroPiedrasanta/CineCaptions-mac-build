# CineCaptions · By Cinema Productions
# 1_codigo/CineCaptions (script principal).py — el programa: ventana principal (Inicio/GO, Proyecto, Editor, SFX Lab), editor de palabras, licencia, generar y colocar en Resolve, main().
"""
CineCaptions (script principal).py
----------------------------
Ventana grafica para CineCaptions.

Hace exactamente lo mismo que subtitle_transcriber.py (la version de consola),
pero con una ventana normal en vez de preguntas escritas en la terminal, y con
una barra de progreso real.

Se abre solo al hacer doble clic en el acceso directo. Tambien acepta la ruta
de un video como argumento (asi funciona el arrastrar el video sobre el icono
del lanzador).

Nota de arquitectura: esto NO reimplementa nada. Importa y llama las mismas
funciones de subtitle_transcriber.py que usa la version de consola, para que
las dos siempre produzcan resultados identicos.

v5.0.0: la interfaz pasa de CustomTkinter a Qt (PySide6) y el programa a
Python 3.14.8 (pedido literal: «actualiza todo mi programa con Python 3.14.8 y
PySide6 para mejorar la interfaz y fluidez»), con la propuesta de panel de 5
pantallas (Inicio, Nuevo proyecto, Editor de palabras, Estilos y composición,
SFX Lab) y un menu lateral. La LOGICA es la de la v4.1.0: lo que cambia es
como se ve y donde vive cada control. Lo comun de la interfaz (colores,
controles, mensajes, hilos) esta en qt_kit.py; la copia de la interfaz Tk
anterior quedo en interfaz_tk_v4.1.0/.
"""
import json
import os
import sys
if sys.platform.startswith('win'):
    if sys.stdout is None:
        try:
            sys.stdout = open(os.devnull, 'w', encoding='utf-8')
        except Exception:
            pass
    if sys.stderr is None:
        try:
            sys.stderr = open(os.devnull, 'w', encoding='utf-8')
        except Exception:
            pass
os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
import datetime
import math
import queue
import shutil
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from PySide6.QtCore import QEasingCurve, QEvent, QEventLoop, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import (QCursor, QFont, QFontDatabase, QFontMetricsF, QGuiApplication,
                           QIcon, QImage, QKeySequence, QPainter, QPainterPath, QPen, QShortcut)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)
import qt_kit as ui
import estilos_slider
from qt_kit import (BarraProgreso, BooleanVar, Boton, BotonNav, Casilla, Chip, Combo,
                    ComboBuscable, Deslizador, DeslizadorValores, Desplazable, Dialogo,
                    Enlace, Entrada, Etiqueta, IconoEstado, Interruptor, MarcoVista, Menu,
                    Onda, Pasos, Pila, Punto, Radio, Segmentado, Separador, StringVar,
                    Tarjeta, Tooltip, ZonaSoltar, caja_h, caja_v, cancelar, correr_en_hilo,
                    despues, ejecutar_en_ui, filedialog, limpiar_capa, messagebox,
                    simpledialog, vivo)
# v5.1: QColor del tema (Ajustes > Interfaz); QColorReal para colores de subtitulos
from qt_kit import QColor, QColorReal
from i18n import tr, idioma as idioma_ui, nombre_idioma
import subtitle_transcriber as st
import archivos_seguros
import sidecar_lua
import proyectos
import sugerencias_ia
import emojis_animados
import ortografia
import ensure_lang_pack as lang_packs
from ensure_lang_pack import ensure_lang_pack
import plantillas
import composicion
# v5.5: las librerias con extension en C (numpy, Pillow) se cargan AQUI, en el hilo principal y antes de arrancar ningun hilo de
# fondo: cargarlas por primera vez desde dos hilos a la vez (emojis, ondas, fuentes) puede tumbar el proceso.
try:
    import numpy  # noqa: F401
    import PIL.Image  # noqa: F401
    import PIL.ImageDraw  # noqa: F401
    import PIL.ImageFont  # noqa: F401
    import PIL.ImageFilter  # noqa: F401
except Exception:
    pass
import packs_drt
import fuentes_sistema
import instalar_fuentes
import licencia
from sfx_rules import CARPETA_USUARIO as _CARPETA_SFX_USUARIO
from version import APP_VERSION
import registro
import registro_ui
# v5.4.44: lo que antes estaba aquí vive en estos módulos (mismo código; ver 1_codigo/ui_comun.py y las ventanas)
from ui_comun import (
    ACCENT, ACCENT_HOVER, BASE_RECURSOS, BG_COLOR, BORDER_COLOR, CADUCA_EL, CARD_COLOR, CODIGO_POR_NOMBRE_ES, COMPOSICION_VISIBLE, CREDIT_TEXT,
    CREDIT_URL, ESTILO_PINTADO_DEFECTO, FS_MENOR, FS_NORMAL, FS_SECCION, FS_TITULO, IDIOMAS_FRECUENTES, IDIOMAS_FRECUENTES_UI, IDIOMAS_RENOMBRADOS,
    IDIOMAS_RESTO, IDIOMAS_RESTO_UI, LANGUAGES, LANG_CODE_BY_NAME, LANG_MENU, LANG_NAMES, LOGO_MARCA_PATH, LOGO_PATH, MAX_HISTORIAL, MENSAJE_CADUCADA,
    MESES, MODEL_SIZE, NOMBRE_POR_CODIGO, PAD_LG, PAD_MD, PAD_SANGRIA, PAD_SM, PAD_XS, SEPARADOR_FAVORITOS, SEPARADOR_IDIOMAS, TEXTOS_MUESTRA,
    TEXT_COLOR, TEXT_MUTED, _CACHE_ESTILOS, _ESTILO_DEFECTO, _ESTILO_FIJO, _FAMILIA_CACHE, _ICONO_CACHE, _base_recursos, _capa_dialogo, _codigo_de,
    _combinacion_visible, _correr_en_hilo, _en_la_interfaz, _estilo_rol, _estilo_rol_n, _hex_de, _icono_carpeta, _icono_estrella, _idioma_en_frase,
    _nota, _plegar, _titulo, cargar_marcas, estilo_fijo, estilos_de_pack, familia_legible, fecha_caducidad_texto, fuente, guardar_log_de_error,
    guardar_marcas, lineas_de_vista, poner_estilo_fijo, prueba_caducada, resumen_composicion, ruta_marcas, sfx_ruta_reglas_usuario
)  # noqa: F401
from selector_emojis import (
    EmojiPickerWindow, _RejillaEmojis
)  # noqa: F401
from ventanas_idioma import (
    BuscadorIdiomaWindow, IdiomasTraduccionWindow, ProyectosWindow, _nombre_es
)  # noqa: F401
from ventana_composicion import (
    ComposicionWindow, _MiniVariante, _PreviaComposicion, _TileLayout
)  # noqa: F401
from ventana_plantillas import (
    PlantillasWindow, _EstructuraPack
)  # noqa: F401
from editor_palabras import (
    LienzoPalabras, PincelesBar, WordTagWindow, _AvisoToast, _Ev, _EvGlobal, _Pildora, _PopupSfx, _SinBarra, _color_de_variante, _fuente_puntos,
    _mezclar_hex, _tc_fino, _tc_largo, _timecode
)  # noqa: F401
from instalador_scripts import MENU_SCRIPTS, SUBCARPETA_SCRIPTS, carpeta_scripts_resolve, carpetas_scripts_resolve, informe_scripts_resolve, instalar_scripts_en_resolve, problema_mac_app_store, raices_scripts_resolve, resolve_esta_corriendo, resolve_esta_instalado, scripts_instalados
def _sangria(widget, extra=PAD_SANGRIA - PAD_MD):
    """El padx=PAD_SANGRIA de la v4: lo de dentro de una tarjeta, corrido."""
    widget.setContentsMargins(extra, 0, 0, 0)
    return widget
# v5.2.1: la ventana de la licencia es ventana_licencia.DialogoLicencia (el formato de la de
# CineSlide: Lemon Squeezy, ya no correo + código de Hotmart)
# ---------------------------------------------------------------------------
# v5.0.0: las piezas del panel (menu lateral + 5 pantallas)
def _hace(ts):
    """'hoy' / 'ayer' / 'hace 3 días' / la fecha."""
    try:
        dias = (datetime.date.today() - datetime.date.fromtimestamp(float(ts))).days
    except (TypeError, ValueError, OSError, OverflowError):
        return '—'
    if dias <= 0:
        return tr('hoy')
    if dias == 1:
        return tr('ayer')
    if dias < 30:
        return tr('hace {n} días', n=dias)
    try:
        return time.strftime('%d/%m/%Y', time.localtime(float(ts)))
    except Exception:
        return '—'
def _duracion_legible(segundos):
    try:
        t = max(0, int(round(float(segundos))))
    except (TypeError, ValueError):
        return ''
    return '%02d:%02d:%02d' % (t // 3600, t % 3600 // 60, t % 60)
def _medir_fuente(ruta, n=96):
    """Duracion, tamaño y una onda de 'n' barras del archivo (v5.0.0, la
    tarjeta «Fuente»). Corre en un hilo: abre el archivo con PyAV (viaja con
    faster-whisper) y lee unos pocos fotogramas de AUDIO repartidos por todo
    el archivo — nunca decodifica el video. Cualquier fallo deja lo que haya."""
    import av
    info = {'duracion': None, 'ancho': 0, 'alto': 0, 'picos': [], 'audio': False}
    with av.open(str(ruta)) as c:
        v = c.streams.video[0] if c.streams.video else None
        if v is not None:
            try:
                info['ancho'] = int(v.codec_context.width or 0)
                info['alto'] = int(v.codec_context.height or 0)
            except Exception:
                pass
            try:
                if v.duration and v.time_base:
                    info['duracion'] = float(v.duration * v.time_base)
            except Exception:
                pass
        if not info['duracion'] and c.duration:
            info['duracion'] = float(c.duration / av.time_base)
        a = c.streams.audio[0] if c.streams.audio else None
        info['audio'] = a is not None
        dur = info['duracion']
        if a is None or not dur:
            return info
        import numpy as np
        picos = []
        for k in range(n):
            t = dur * (k + 0.5) / n
            valor = 0.0
            try:
                c.seek(int(t * av.time_base), any_frame=False, backward=True)
                for i, frame in enumerate(c.decode(a)):
                    x = frame.to_ndarray()
                    if x.size:
                        if np.issubdtype(x.dtype, np.integer):
                            x = x.astype(np.float32) / float(np.iinfo(x.dtype).max)
                        valor = max(valor, float(np.sqrt(np.mean(np.square(x, dtype=np.float32)))))
                    if i >= 1:
                        break
            except Exception:
                pass
            picos.append(valor)
        tope = max(picos) if picos else 0.0
        if tope > 0:
            info['picos'] = [min(1.0, (p / tope) ** 0.7) for p in picos]
    return info
def _lineas_look(look):
    """La vista previa (aprox.) de los looks destacados."""
    blanco, oro = ('#FFFFFF', ui.ROL_PRINCIPAL)
    if look == 'hormozi':
        return [(tr('CÓMO DUPLICAMOS'), {'familia': 'Montserrat', 'peso': 'Black', 'tam': 0.17, 'color': blanco, 'contorno': '#000000'}),
                (tr('LAS VENTAS'), {'familia': 'Montserrat', 'peso': 'Black', 'tam': 0.17, 'color': oro, 'contorno': '#000000'})]
    if look == 'gadzhi':
        return [(tr('Cómo duplicamos'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.16, 'color': blanco}),
                (tr('las ventas'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.16, 'color': blanco})]
    if look == 'acumulativo':
        return [(tr('Cómo duplicamos'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.15, 'color': blanco}),
                (tr('las ventas…'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.15, 'color': '#4F607A'})]
    return [(tr('Cómo duplicamos'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.15, 'color': blanco}),
            (tr('las ventas'), {'familia': 'Montserrat', 'peso': 'Bold', 'tam': 0.15, 'color': oro})]
def _recetas_por_defecto():
    """Las tres recetas de la propuesta, hasta que el usuario guarde las suyas."""
    return [{'nombre': tr('Dinámicos · Vertical · con SFX'), 'detalle': tr('3 líneas · diseño automático'), 'modo': 'dinamico', 'formato_video': 'v', 'sfx': True},
            {'nombre': tr('Hormozi · Vertical'), 'detalle': tr('Contorno grueso, mayúsculas'), 'modo': 'destacados', 'look': 'hormozi', 'formato_video': 'v', 'sfx': False},
            {'nombre': tr('Normales + traducción a inglés'), 'detalle': tr('Subtítulos básicos · Argos sin internet'), 'modo': 'normal', 'traducir': True, 'idioma_destino': 'en', 'sfx': False}]
class _Marca(QLabel):
    """El logo de CineCaptions en la marca del lateral (logo_cinecaptions.png)."""
    def __init__(self, lado=40):
        super().__init__()
        self.setFixedSize(lado, lado)
        pm = ui.pixmap_de_archivo(LOGO_PATH, lado) if LOGO_PATH.exists() else None
        if pm is not None:
            self.setPixmap(pm)
class _Sumidero:
    """v5.1: la licencia ya no tiene linea propia en el lateral (va en
    Ajustes y en la tarjeta de Inicio); esto absorbe lo que _pintar_licencia
    le mandaba, sin tocar esa logica."""
    def poner(self, *_a, **_k):
        pass
    def configure(self, *_a, **_k):
        pass
class _MosaicoModo(QFrame):
    """Un mosaico de «Formato de los subtítulos» (imagen 02)."""
    def __init__(self, titulo, detalle, comando):
        super().__init__()
        self.setObjectName('mosaico')
        self.setProperty('clicable', True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._comando = comando
        capa = QVBoxLayout(self)
        capa.setContentsMargins(16, 14, 16, 14)
        capa.setSpacing(6)
        capa.addWidget(Etiqueta(titulo, 15, peso='medio', color='#FFFFFF'))
        detalle_lbl = Etiqueta(detalle, 12, color=TEXT_MUTED, envolver=True)
        capa.addWidget(detalle_lbl)
        self.setMinimumHeight(82)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    def poner_elegida(self, si):
        if self.property('elegida') != bool(si):
            self.setProperty('elegida', bool(si))
            ui.repulir(self)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._comando()
            e.accept()
            return
        super().mousePressEvent(e)
class _RejillaModos(QWidget):
    """Los 6 mosaicos: normales, dinámicos y los 4 looks destacados
    (v5.0.0: el modo «destacados» de la v4 vuelve a estar a la vista)."""
    def __init__(self, opciones, al_elegir):
        super().__init__()
        rejilla = QGridLayout(self)
        rejilla.setContentsMargins(0, 0, 0, 0)
        rejilla.setSpacing(14)
        self._mosaicos = {}
        for k, (clave, titulo, detalle) in enumerate(opciones):
            m = _MosaicoModo(titulo, detalle, lambda c=clave: al_elegir(c))
            rejilla.addWidget(m, k // 3, k % 3)
            self._mosaicos[clave] = m
        for c in range(3):
            rejilla.setColumnStretch(c, 1)
    def marcar(self, clave):
        for c, m in self._mosaicos.items():
            m.poner_elegida(c == clave)
    def configure(self, state=None, **_):
        if state is not None:
            self.setEnabled(state != 'disabled')
# la etiqueta que termina en «…» vive en qt_kit (la usa tambien el SFX Lab)
_Elidida = ui.Elidida
class _TarjetaEstado(Tarjeta):
    """Una de las cuatro tarjetas de arriba de «Inicio»."""
    def __init__(self, nombre, comando=None):
        super().__init__(clicable=comando is not None, margenes=(20, 16, 20, 16), espacio=6)
        if comando is not None:
            self.clic.connect(comando)
        fila, cf = caja_h(espacio=8)
        self.punto = Punto(TEXT_MUTED, 8)
        cf.addWidget(self.punto, 0, Qt.AlignmentFlag.AlignVCenter)
        cf.addWidget(Etiqueta(nombre, 13, color=TEXT_MUTED))
        cf.addStretch(1)
        self.capa.addWidget(fila)
        self.valor = _Elidida('…', 22, peso='extra', color='#FFFFFF')
        self.capa.addWidget(self.valor)
        self.detalle = _Elidida('', 12, color=TEXT_MUTED)
        self.capa.addWidget(self.detalle)
    def poner(self, color, valor, detalle=''):
        self.punto.poner(color)
        self.valor.configure(text=valor)
        self.detalle.configure(text=detalle)
class _FilaProyecto(QFrame):
    """Una fila de «Proyectos recientes» (o su cabecera)."""
    ANCHOS = (None, 86, 120, 150, 104)
    def __init__(self, celdas, comando=None, cabecera=False, ultima=False):
        super().__init__()
        self.setObjectName('filaProyecto')
        self._comando = comando
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        borde = 'none' if ultima else '1px solid #182238'
        hover = '' if cabecera or comando is None else 'QFrame#filaProyecto:hover { background-color: #0F1A2E; }'
        self.setStyleSheet(ui.traducir_hoja(f'QFrame#filaProyecto {{ border: none; border-bottom: {borde}; border-radius: 0px; }} {hover}'))
        if comando is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(4, 0 if cabecera else 14, 4, 10 if cabecera else 14)
        capa.setSpacing(10)
        for celda, ancho in zip(celdas, self.ANCHOS):
            if isinstance(celda, str):
                celda = Etiqueta(celda, 12 if cabecera else 14, color=TEXT_MUTED if cabecera else '#E0EBFB',
                                 peso=None if cabecera else ('medio' if ancho is None else None))
            if ancho is None:
                celda.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                capa.addWidget(celda, 1)
            else:
                caja = QWidget()
                caja.setFixedWidth(ancho)
                cc = QHBoxLayout(caja)
                cc.setContentsMargins(0, 0, 0, 0)
                cc.addWidget(celda)
                cc.addStretch(1)
                capa.addWidget(caja)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._comando is not None:
            self._comando()
            e.accept()
            return
        super().mousePressEvent(e)
class _EtiquetaPlantilla(Enlace):
    """El valor «Pack de estilos» de la Receta: la etiqueta de siempre
    (_etiqueta_plantilla_completa) sin la flecha « >» del boton de la v4;
    un clic lleva a «Estilos y composición»."""
    def configure(self, text=None, text_color=None, **kw):
        if text is not None:
            text = str(text).rstrip().rstrip('>').rstrip()
            self.setToolTip(text)
        super().configure(text=text, text_color=text_color, **kw)
class BarraTitulo(Tarjeta):
    """El título de cada pantalla (Proyecto, Creativo, Sonido): una barra con la insignia numerada
    en naranja, el título en grande, una línea de apoyo y el «?» con la ayuda completa."""

    def __init__(self, numero, titulo, subtitulo=''):
        super().__init__(horizontal=True, margenes=(16, 11, 16, 11), espacio=14)
        from PySide6.QtWidgets import QToolTip
        self.insignia = QFrame()
        self.insignia.setObjectName('insigniaTitulo')
        self.insignia.setFixedSize(36, 36)
        ac = QColor(ui.ACCENT)
        self.insignia.setStyleSheet(f'QFrame#insigniaTitulo {{ background: rgba({ac.red()}, {ac.green()}, {ac.blue()}, 34);'
                                    f' border: 1px solid rgba({ac.red()}, {ac.green()}, {ac.blue()}, 120); border-radius: 10px; }}')
        ci = QVBoxLayout(self.insignia)
        ci.setContentsMargins(0, 0, 0, 0)
        ci.addWidget(Etiqueta(str(numero), 14, peso='extra', color=ui.ACCENT_CLARO, alineacion=Qt.AlignmentFlag.AlignCenter))
        self.capa.addWidget(self.insignia)
        import mograf_ui
        self.titulo = mograf_ui.EtiquetaCinetica(titulo, 21, peso='extra', color='#FFFFFF')
        self.capa.addWidget(self.titulo)
        self.sub = registro_ui.SubtituloVivo(subtitulo, 13, TEXT_MUTED)       # la línea de apoyo, y donde salen los avisos
        self.capa.addWidget(self.sub, 1)
        self.registro_btn = registro_ui.BotonRegistro()
        self.capa.addWidget(self.registro_btn)
        self._texto_ayuda = str(subtitulo)
        self.ayuda = Boton('?', lambda: QToolTip.showText(QCursor.pos(), self._texto_ayuda, self.ayuda),
                           tipo='icono', alto=34, ancho=34, tam=14, negrita=True)
        self.ayuda.setFixedWidth(34)
        self.ayuda.setToolTip(self._texto_ayuda)
        self.capa.addWidget(self.ayuda)
        import brillo_ui
        brillo_ui.barrido_periodico(self, 11000, radio=14.0)          # un barrido de luz por la barra cada tanto

    def poner_subtitulo(self, texto):
        self.sub.configure(text=texto)
        self._texto_ayuda = str(texto)
        self.ayuda.setToolTip(self._texto_ayuda)


NUMERO_PAGINA = {'nuevo': '01', 'estilos': '01', 'editor': '02', 'sfx': '03', 'efectos': '04'}


class SubtitleApp(QWidget):
    """La ventana principal (v5.0.0: panel con menu lateral y 5 pantallas).

    La logica es la de la v4.1.0 — mismos metodos, mismos nombres, la misma
    cola de mensajes de _run_pipeline y el mismo _tag_event —; lo nuevo es
    donde vive cada control. El titulo de la ventana NO cambia: de el
    dependen la instancia unica y el puente con Resolve.
    """
    # v5.2 (pedido: «hay muchos pasos entre pestañas muy redundantes, unifícalos»):
    # «Nuevo proyecto» y «Estilos y composición» son UNA entrada del menú
    # («Proyecto»), con un conmutador arriba; Inicio elige pack, idioma, efectos
    # y formato con chips debajo de GO.
    PAGINAS = (('inicio', 'Inicio'), ('nuevo', 'Proyecto'), ('editor', 'Creativo'),
               ('sfx', 'Sonido'), ('efectos', 'Efectos'))
    ANCHO_PLEGAR = 1400
    def __init__(self, initial_video=None):
        super().__init__()
        self.setWindowTitle('CineCaptions')
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)      # v5.5: los controles de la ventana viven dentro de la interfaz (isla_ui)
        self.setAcceptDrops(True)
        self._colocar_ventana()
        self._ultimo_idioma = NOMBRE_POR_CODIGO['es']
        self.msg_queue = queue.Queue()
        self.worker = None
        self._tag_event = threading.Event()
        self._tag_result = None
        self._trabajo_desde = None
        self._editor = None
        self._entradas_activas = True
        self._meta_fuente = None
        self._video_id = None
        self._estado_sistema = {}
        self._recogiendo = False
        self._calentando = set()
        self._cache_estimados = None
        self._generado_para = None
        self.recetas = None
        self._chips_recetas = []
        self._estudio_ventana = None
        self._plantillas_ventana = None
        self._composicion_ventana = None
        try:                                              # v5.4.26: los efectos vienen activos (una sola vez se encienden en las preferencias de antes)
            import efectos_visuales as _fxv
            _fxv.migrar_a_efectos_activos()
        except Exception:
            pass
        self._paginas = {}
        self._cabeceras = {}
        self._nav = {}
        self._pagina_actual = None
        self._plegado = None
        # v5.1, Ajustes > Interfaz > «Barra lateral al iniciar» (None = segun el ancho)
        import tema
        _aj = tema.leer()
        self._plegado_manual = {'expandida': False, 'compacta': True, 'recordar': _aj['lateral_ultimo']}.get(_aj['lateral'])
        self._build_ui()
        self._set_window_icon()
        try:
            import ajustes_ui
            if ajustes_ui.leer_prefs().get('ventana_encima'):
                self.poner_encima(True)
        except Exception:
            pass
        self._cargar_preferencias()
        self._on_modo_change()
        self._pintar_recetas()
        self._pintar_licencia()
        self.ir_a('inicio', animar=False)
        self._caducada = prueba_caducada()
        if self._caducada:
            self._bloquear_por_caducidad()
        else:
            self._sin_licencia = not licencia.vigente()
            self._revisar_licencia_al_arrancar()
            despues(2500, self._ofrecer_fuentes_al_arrancar, self)
            if initial_video:
                self.video_var.set(str(initial_video))
                self.ir_a('nuevo', animar=False)
            else:
                self._detectar_desde_resolve(silencioso=True)
            self._ultimo_error_scripts = None
            try:
                self.status_var.set(tr('Comprobando Resolve…'))
            except Exception:
                pass
            def sondear():
                import resolve_bridge
                resolve_bridge.conectar()
            _correr_en_hilo(self, sondear, self._tras_sondear_resolve)
            despues(100, self._poll_queue, self)
        self._refrescar_estado()
        # v5.2: el chequeo de librerias, siempre, en segundo plano (salud.py)
        despues(3500, self._chequear_librerias, self)
        # v5.4: el indice de fuentes del sistema (~1100 archivos) se arma en un hilo nada mas abrir, no al pulsar «Estilos»
        despues(400, self._precalentar_fuentes, self)
        despues(1800, self._ofrecer_reanudar_go, self)                 # v5.4.8: un GO que quedó a medias se ofrece reanudar
        despues(9000, self._precargar_al_abrir, self)                  # v5.4.40: la voz y la IA de texto se cargan en segundo plano al abrir (el primer GO se ahorra ~14 s de carga)
        despues(45000, self._limpiar_caches, self)               # v5.4.8: tope de MB por caché (mantenimiento.py), 45 s después de abrir y en un hilo
        try:                                                     # v5.4.8: lo de fondo (cola_trabajos) cede ante GO
            import cola_trabajos
            cola_trabajos.registrar_alta(lambda: bool(getattr(self, '_go_corriendo', False)))
        except Exception:
            pass
        despues(1500, self._precalentar_packs, self)
        despues(6000, self._descargar_emojis_animados, self)
        despues(2500, self._precalentar_mcp, self)
        despues(9000, self._precalentar_secuencias_emoji, self)
        despues(12000, self._precalentar_ondas_sfx, self)
    def palabras_de_la_ultima_transcripcion(self):
        """[{'word', 'start', 'end'}] de la ultima transcripcion (la de la sesion o la guardada del video actual); [] si no hay."""
        sesion = getattr(self, '_sfx_palabras', None)
        if sesion:
            return [{'word': p['texto'], 'start': p['t'], 'end': p.get('fin', p['t'])} for p in sesion]
        try:
            ruta = self.video_var.get().strip().strip('"')
            if ruta:
                guardadas = cargar_marcas(Path(ruta).expanduser().stem)
                if guardadas:
                    return [{'word': w.get('word', ''), 'start': w.get('start'), 'end': w.get('end')} for w in guardadas[0]]
        except Exception:
            pass
        return []
    def _precalentar_mcp(self):
        """v5.5: la conexion con Resolve (ResolveMCP) se abre ya, en un hilo, SIN abrir Resolve: asi el primer «Obtener» o la primera
        vista real no pagan el arranque del puente."""
        def trabajo():
            import resolve_mcp
            if resolve_mcp.ruta_exe() is not None:
                resolve_mcp.cliente(arrancar=True)
        _correr_en_hilo(self, trabajo, lambda _r, _e: None)
    def _precalentar_ondas_sfx(self):
        """v5.5: la onda de los primeros sonidos de cada categoria de la biblioteca, en un hilo: al abrir Sonido ya estan."""
        try:
            import sfx_rules
            import sfx_studio
            rutas = []
            for cat in sfx_rules.categorias_disponibles():
                rutas += [str(r) for r in sfx_rules._rutas_de(cat)[:3]]
            import cola_trabajos
            cola_trabajos.lanzar_bajo(lambda: sfx_studio.precalentar_picos(rutas), 'ondas-sfx')
        except Exception:
            pass
    def _precalentar_secuencias_emoji(self):
        try:
            import cola_trabajos
            import emojis
            cola_trabajos.lanzar_bajo(emojis.precalentar_secuencias, 'secuencias-emoji')
        except Exception:
            pass
    def _limpiar_caches(self):
        def trabajo():
            import mantenimiento
            mb, n = mantenimiento.limpiar_todo()
            if n:
                registro.info(f'Cachés: {n} entradas viejas borradas ({mb:.0f} MB liberados)', 'mantenimiento')
        _correr_en_hilo(self, trabajo, lambda _r, _e: None, baja=True)
    def _precalentar_fuentes(self):
        try:
            import fuentes_sistema
            fuentes_sistema.precalentar()
        except Exception:
            pass
    def _precalentar_packs(self):
        """v5.4: leer los .drb de los packs (descomprimir sus comps) costaba ~0,3 s al abrir «Estilos» por primera vez;
        se hace antes, en un hilo, y la pantalla solo encuentra los datos ya leidos (Pack y _CACHE_ESTILOS)."""
        def trabajo():
            for pack in plantillas.listar_packs():
                if getattr(pack, 'es_basicos', False):
                    continue
                estilos_de_pack(pack.nombre)
                pack.fuentes()
        _correr_en_hilo(self, trabajo, lambda _r, _e: None, baja=True)
    def _descargar_emojis_animados(self):
        """v5.4: baja en segundo plano todos los emojis animados del catalogo (Noto Animated Emoji) para que el selector los
        muestre moviéndose al instante; el progreso se ve en «Detalles y estado del sistema»."""
        try:
            import emojis
            glifos = [(e.get('glifo') or '') for e in emojis.catalogo()]
            emojis_animados.precargar_todo(glifos)
        except Exception:
            return
        self._vigilar_emojis_animados()
    def _vigilar_emojis_animados(self):
        if not vivo(self):
            return
        hechos, total, activo, fallos = emojis_animados.estado()
        fila = getattr(self, '_filas_sistema', {}).get('emojis_anim')
        if fila:
            icono, valor, _w = fila
            try:
                if activo:
                    icono.poner('aviso')
                    valor.configure(text=tr('descargando {a} de {b}…', a=hechos, b=total))
                else:
                    icono.poner('ok' if total and fallos < total else 'aviso')
                    valor.configure(text=tr('{a} animados listos', a=max(0, total - fallos)) if total else '—')
            except Exception:
                pass
        if activo:
            despues(1500, self._vigilar_emojis_animados, self)
        elif total and not getattr(self, '_emojis_anim_anotado', False):
            self._emojis_anim_anotado = True
            if emojis_animados._DESCARGA.get('sin_red'):
                registro.aviso(f'Emojis animados: sin conexión, {total - fallos} listos de {total}; se reintenta al abrir otra vez', 'emojis')
            else:
                registro.info(f'Emojis animados: {total - fallos} listos de {total} ({fallos} sin versión animada)', 'emojis')
    def _chequear_librerias(self):
        def trabajo():
            import salud
            return salud.comprobar()
        def fin(filas, _error):
            if not filas or not vivo(self):
                return
            import salud
            texto, ok = salud.resumen(filas)
            fila = getattr(self, '_filas_sistema', {}).get('librerias')
            if fila:
                icono, valor, _w = fila
                try:
                    icono.poner('ok' if ok else 'aviso')
                except Exception:
                    pass
                valor.configure(text=texto)
                Tooltip(valor, salud.informe(filas))
            if ok is False:
                import ui_toast
                ui_toast.mostrar(self, tr('Chequeo de librerías: {t}. Detalles y estado del sistema tiene el informe.', t=texto), duracion_ms=7000)
        _correr_en_hilo(self, trabajo, fin)
    def _colocar_ventana(self):
        """1440 x 900 si cabe; minimo 1100 x 700 (o lo que deje la pantalla)."""
        pantalla = QGuiApplication.primaryScreen()
        area = pantalla.availableGeometry() if pantalla is not None else QRect(0, 0, 1440, 900)
        ancho = min(1440, int(area.width() * 0.94))
        alto = min(900, int(area.height() * 0.92))
        self.setMinimumSize(min(1100, area.width() - 40), min(700, area.height() - 40))
        self.resize(max(ancho, self.minimumWidth()), max(alto, self.minimumHeight()))
        self.move(area.left() + (area.width() - self.width()) // 2, area.top() + max(0, (area.height() - self.height()) // 3))
    def showEvent(self, e):
        if not getattr(self, '_oscura', False):
            self._oscura = True
            ui.barra_oscura(self)
        super().showEvent(e)
    def _tras_sondear_resolve(self, _resultado=None, _error=None):
        """Lo que hasta la v3.3.2 corria sincrono al arrancar, ahora
        cuando el hilo del sondeo termino. v5.4: copiar/comparar los scripts (~1 MB) iba aqui, en el hilo de la
        interfaz, y congelaba la ventana recien abierta; ahora lo hace un hilo y la interfaz solo recibe el resultado."""
        def trabajo():
            return instalar_scripts_en_resolve()
        def fin(resultado, _e):
            try:
                if resultado:
                    self._asegurar_scripts_instalados(_resultado=resultado)
            except Exception:
                pass
            self._avisar_modo_ejecucion()
            self._refrescar_estado()
        _correr_en_hilo(self, trabajo, fin)
    def _avisar_modo_ejecucion(self):
        """Deja en el status como se van a ejecutar los scripts en Resolve.

        El caso 'manual' se abre en tres, porque antes mandaba SIEMPRE a
        correr el Puente desde el menu de Resolve, incluso cuando ese menu
        todavia no podia mostrarlo. El usuario iba al menu, no veia nada, y
        no habia forma de salir de ahi.
        """
        try:
            import resolve_bridge
            modo = resolve_bridge.modo_actual(pasivo=True)
        except Exception:
            return
        if modo == 'mcp':
            self.status_var.set(tr('Resolve conectado por MCP: todo se ejecuta solo.'))
            return
        if modo == 'studio':
            self.status_var.set(tr('Resolve Studio conectado: todo se ejecuta solo.'))
            return
        try:
            if resolve_bridge.scripting_desactivado(pasivo=True):
                self.msg_queue.put(('scripting_cerrado', ''))
        except Exception:
            pass
        if modo == 'puente':
            try:
                if resolve_bridge.puente_desactualizado():
                    self.msg_queue.put(('puente_viejo', resolve_bridge.version_del_puente() or '?'))
                    self.status_var.set(tr('El Puente de Resolve quedó de una versión anterior: ciérralo y vuelve a correr CineCaptions_Puente.'))
                    return
            except Exception:
                pass
            self.status_var.set(tr('Puente activo en Resolve: todo se ejecuta solo.'))
            return
        try:
            import instalador_scripts as _ins
            if _ins.edicion_de_resolve() == 'studio':
                self.status_var.set(tr('Abre DaVinci Resolve con tu proyecto: desde ahí todo se ejecuta solo.'))
                return
        except Exception:
            pass
        if not scripts_instalados():
            detalle = getattr(self, '_ultimo_error_scripts', None)
            self.status_var.set(
                tr('No pude dejar los scripts en Resolve')
                + (f': {detalle.splitlines()[0][:90]}' if detalle
                   else tr('. Usa el enlace de abajo para instalarlos.')))
            return
        self.status_var.set(tr('Falta lanzar el Puente: en Resolve, Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente (una vez por sesión).'))
    def _load_logo(self):
        """El logo listo para mostrar, o None si no se puede cargar."""
        if not LOGO_PATH.exists():
            return
        try:
            return ui.pixmap_redondeado(ui.pixmap_de_archivo(LOGO_PATH, 40), 9)
        except Exception:
            return None
    def _open_credit_url(self, event=None):
        if not CREDIT_URL:
            return None
        try:
            webbrowser.open_new_tab(CREDIT_URL)
        except Exception:
            return None
    def _cambiar_idioma_ui(self, nombre):
        """El selector de idioma de la interfaz: guarda el idioma para el
        proximo arranque (i18n.guardar_idioma, el mismo idioma.ini del
        instalador)."""
        import i18n
        codigo = next((c for c, n in i18n.IDIOMAS_UI.items() if n == nombre), None)
        if codigo is None:
            return
        if not i18n.guardar_idioma(codigo):
            messagebox.showwarning(tr('Idioma'), tr('No pude guardar el idioma en {ruta}.', ruta=i18n.ARCHIVO_INI), parent=self)
            return
        if codigo != idioma_ui():
            messagebox.showinfo(tr('Idioma'), tr('Listo: el programa se verá en {idioma} la próxima vez que lo abras.', idioma=nombre), parent=self)
    def _menu_idioma_ui(self):
        import i18n
        menu = Menu(self)
        for codigo, nombre in i18n.IDIOMAS_UI.items():
            menu.agregar(('✓  ' if codigo == idioma_ui() else '      ') + nombre, lambda n=nombre: self._cambiar_idioma_ui(n))
        menu.mostrar(QCursor.pos())
    def _set_window_icon(self):
        """Pone el logo como icono de la ventana (barra de tareas)."""
        if not LOGO_PATH.exists():
            return
        try:
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        except Exception:
            return None
    # -- armado --------------------------------------------------------------
    def _build_ui(self):
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        self._build_lateral()                       # v5.5: el menu lateral pasa a la isla (isla_ui); se construye oculto porque sus piezas siguen en uso
        self.lateral.setParent(self)
        self.lateral.hide()
        # v5.2: el escenario animado detras de todas las pantallas (efectos_ui)
        import efectos_ui
        import ritmo_ui
        ritmo_ui.ritmo.iniciar()           # v5.3: regulador del ritmo de las animaciones (alarga el intervalo si la interfaz va justa)
        self.fondo = efectos_ui.FondoVivo()
        cf = QVBoxLayout(self.fondo)
        cf.setContentsMargins(0, 0, 0, 0)
        self.pila = Pila()
        cf.addWidget(self.pila)
        capa.addWidget(self.fondo, 1)
        self._pagina_inicio()
        # v5.2.1: la escena 3D de Inicio (esfera de partículas, absorción, cometas, explosión) va debajo de las pantallas
        import escena_go
        self.escena_go = escena_go.EscenaGo(self.fondo)
        self.escena_go.lower()
        self.go_panel.conectar_escena(self.escena_go)
        self.escena_go.setGeometry(self.fondo.rect())
        self.fondo.installEventFilter(self)
        self.fondo.proveedor_excluidas = self._zonas_opacas
        self._build_isla()
        self.go_panel.celebrar.connect(lambda g: self.fondo.explosion(*self._en_fondo(g)))
        self.go_panel.pulso.connect(lambda g: self.fondo.onda(*self._en_fondo(g)))
        self._pagina_nuevo()
        self._pagina_editor()
        self._pagina_estilos()
        self._pagina_sfx()
        self._pagina_efectos()
    def _build_lateral(self):
        self.lateral = QFrame()
        self.lateral.setObjectName('lateral')
        self.lateral.setFixedWidth(250)
        cl = QVBoxLayout(self.lateral)
        cl.setContentsMargins(14, 26, 14, 18)
        cl.setSpacing(6)
        import ajustes_ui
        self._marca_fila, cm = caja_h(espacio=10, margenes=(4, 0, 0, 0))
        self._marca_capa = cm
        cm.addWidget(_Marca(42))
        self._marca_textos, ct = caja_v(espacio=0)
        ct.addWidget(Etiqueta('CineCaptions', 18, peso='extra', color='#FFFFFF'))
        ct.addWidget(Etiqueta(tr('Subtítulos para Resolve'), 11, color=TEXT_MUTED))
        cm.addWidget(self._marca_textos, 1)
        self.plegar_btn = ajustes_ui.BotonIcono('plegar', tr('Plegar / desplegar el menú'), lado=24, borde=False, radio=7)
        self.plegar_btn.clicked.connect(self._alternar_lateral)
        cm.addWidget(self.plegar_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        cl.addWidget(self._marca_fila)
        cl.addSpacing(28)
        for clave, nombre in self.PAGINAS:
            b = BotonNav(tr(nombre), clave)
            b.clicked.connect(lambda _=False, c=clave: self.ir_a(c))
            cl.addWidget(b)
            self._nav[clave] = b
        cl.addStretch(1)
        # v5.1 (pedido con una referencia): la esquina de abajo lleva la copia
        # de seguridad, el estado de Resolve con «Comprobar conexión»,
        # «Ajustes» con el alfiler para fijar la ventana, y la version.
        # la copia de seguridad vive solo en Ajustes > General
        self.lat_tarjeta = QFrame()
        self.lat_tarjeta.setObjectName('tarjetaEstado')
        ct2 = QVBoxLayout(self.lat_tarjeta)
        ct2.setContentsMargins(16, 15, 14, 14)
        ct2.setSpacing(5)
        fila, cf = caja_h(espacio=10)
        self.lat_punto_resolve = Punto(TEXT_MUTED, 10)
        cf.addWidget(self.lat_punto_resolve, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lat_resolve = _Elidida(tr('Comprobando Resolve…'), 15, peso='negrita', color='#FFFFFF')
        cf.addWidget(self.lat_resolve, 1)
        ct2.addWidget(fila)
        self.lat_resolve_det = _Elidida('', 12, color=TEXT_MUTED)
        ct2.addWidget(self.lat_resolve_det)
        ct2.addSpacing(4)
        self.lat_comprobar = Enlace(tr('Comprobar conexión'), self._comprobar_conexion_lateral, 13, color=ui.ACCENT_CLARO, color_hover='#FFFFFF', subrayada=False, peso='negrita')
        ct2.addWidget(self.lat_comprobar)
        # la licencia y el idioma ahora viven en Ajustes (y la licencia, en Inicio)
        self.lat_punto_licencia = _Sumidero()
        self.lat_licencia = _Sumidero()
        self.licencia_lbl = None
        cl.addSpacing(8)
        self._fila_ajustes, ca = caja_h(espacio=8)
        self._fila_ajustes_capa = ca
        self.ajustes_btn = Boton(tr('Ajustes'), self._abrir_ajustes_rapido, tipo='neutro', alto=48, tam=14, negrita=True)
        self.ajustes_btn.setIcon(ajustes_ui.icono('engranaje', ui.ACCENT_CLARO, 20))
        self.ajustes_btn.setIconSize(QSize(20, 20))
        ca.addWidget(self.ajustes_btn, 1)
        self.pin_btn = ajustes_ui.BotonIcono('chincheta', tr('Mantener CineCaptions encima de Resolve'), lado=48, conmutable=True)
        self.pin_btn.clicked.connect(lambda: self.poner_encima(self.pin_btn.isChecked(), guardar=True))
        ca.addWidget(self.pin_btn)
        cl.addWidget(self._fila_ajustes)
        # v5.2: la marca y la version en dos lineas (en una sola, la version
        # cortaba «Cinema Productions»)
        self.lat_pie, cp = caja_v(espacio=1, margenes=(6, 10, 4, 0))
        self.credit = Etiqueta(CREDIT_TEXT, 12, peso='negrita', color='#FFFFFF')
        cp.addWidget(self.credit)
        self.lat_version = Etiqueta('', 11, color='#4F607A')
        cp.addWidget(self.lat_version)
        cl.addWidget(self.lat_pie)
        self._pintar_pie_lateral()
        return self.lateral
    def _build_isla(self):
        """v5.5: la isla dinamica (navegacion), los controles de la ventana, el borde y el panel del estado de Resolve."""
        import isla_ui
        self.isla = isla_ui.IslaNav(self, self.PAGINAS)
        self.isla.pagina.connect(self.ir_a)
        self.isla.accion.connect(self._accion_isla)
        self.ctrl_ventana = isla_ui.ControlesVentana(self)
        self.ctrl_ventana.accion.connect(self._accion_isla)
        self.marca_cinema = isla_ui.MarcaCinema(self, LOGO_MARCA_PATH if LOGO_MARCA_PATH.exists() else None)       # el logo, arriba a la izquierda de Inicio
        self.marca_cinema.poner_en_inicio(getattr(self, '_pagina_actual', 'inicio') == 'inicio')
        self.marco_ventana = isla_ui.MarcoVentana(self)
        self.marco_ventana.setGeometry(self.rect())
        # el estado de Resolve (la tarjeta de antes) sale debajo del punto de la isla
        self._pop_estado = Tarjeta(self, margenes=(8, 8, 8, 8))
        self._pop_estado.setFixedWidth(300)
        self._pop_estado.capa.addWidget(self.lat_tarjeta)
        self._pop_estado.hide()
        self._bordes_ventana = isla_ui.BordesVentana(self, self._clic_fuera_de_paneles)
        self._subir_isla()
    def _subir_isla(self):
        for w in (getattr(self, '_pop_estado', None), getattr(self, 'isla', None), getattr(self, 'ctrl_ventana', None), getattr(self, 'marco_ventana', None)):
            if w is not None:
                w.raise_()
        marca = getattr(self, 'marca_cinema', None)
        if marca is not None and marca.isVisible():
            marca.raise_()
    def _reposicionar_isla(self):
        if not hasattr(self, 'isla'):
            return
        self.isla.reposicionar()
        self.ctrl_ventana.reposicionar()
        if hasattr(self, 'marca_cinema'):
            self.marca_cinema.reposicionar(self.isla)
        self.marco_ventana.setGeometry(self.rect())
        self.ctrl_ventana.poner_maximizada(self.isMaximized())
        self._subir_isla()
    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.WindowStateChange and hasattr(self, 'ctrl_ventana'):
            self.ctrl_ventana.poner_maximizada(self.isMaximized())
            self.marco_ventana.update()
    def _accion_isla(self, clave, rect=None):
        if clave == 'estado':
            self._alternar_pop_estado()
        elif clave == 'ajustes':
            self._abrir_ajustes_rapido()
        elif clave == 'pin':
            self.poner_encima(not bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint), guardar=True)
        elif clave == 'min':
            self.showMinimized()
        elif clave in ('max', 'maximizar'):
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        elif clave == 'cerrar':
            self.close()
    def _alternar_pop_estado(self):
        pop = self._pop_estado
        if pop.isVisible():
            pop.hide()
            return
        import isla_ui
        pop.adjustSize()
        r = self.isla.rect_de('estado')
        x = int(min(max(12, r.center().x() - pop.width() / 2), self.width() - pop.width() - 12))
        y = int(self.isla.y() + isla_ui.MARGEN + isla_ui.ALTO + 10)
        pop.move(x, y)
        pop.show()
        pop.raise_()
        self.lat_tarjeta.show()
        try:
            import mograf_ui
            mograf_ui.entrada_escalonada([pop], retardo=0, duracion=420, subida=10)
        except Exception:
            pass
    def _clic_fuera_de_paneles(self, obj):
        """Un clic fuera del panel del estado lo cierra."""
        pop = getattr(self, '_pop_estado', None)
        if pop is None or not pop.isVisible():
            return
        w = obj
        while w is not None:
            if w is pop or w is getattr(self, 'isla', None):
                return
            w = w.parentWidget()
        pop.hide()
    def _plegar_lateral(self, plegar):
        """Plegado: el lateral queda solo con iconos (por ancho de ventana o a
        mano con el boton de la marca; Ajustes > Interfaz elige al arrancar)."""
        if plegar == self._plegado:
            return
        self._plegado = plegar
        self.lateral.setFixedWidth(76 if plegar else 250)
        self._marca_textos.setVisible(not plegar)
        self.lat_tarjeta.setVisible(not plegar)
        self.lat_pie.setVisible(not plegar)
        from PySide6.QtWidgets import QBoxLayout
        direccion = QBoxLayout.Direction.TopToBottom if plegar else QBoxLayout.Direction.LeftToRight
        self._fila_ajustes_capa.setDirection(direccion)
        self._marca_capa.setDirection(direccion)
        self._marca_capa.setContentsMargins(0 if plegar else 12, 0, 0, 0)
        self.ajustes_btn.setText('' if plegar else tr('Ajustes'))
        self.ajustes_btn.setToolTip(tr('Ajustes') if plegar else '')
        self.plegar_btn._clave = 'desplegar' if plegar else 'plegar'
        self.plegar_btn.update()
        for b in self._nav.values():
            b.plegado = plegar
            b.update()
    def _alternar_lateral(self):
        self._plegado_manual = not bool(self._plegado)
        self._plegar_lateral(self._plegado_manual)
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'lateral_plegado': bool(self._plegado_manual)})
        except Exception:
            pass
    def resizeEvent(self, e):
        super().resizeEvent(e)
        manual = getattr(self, '_plegado_manual', None)
        self._plegar_lateral(self.width() < self.ANCHO_PLEGAR if manual is None else manual)
        self._ajustar_densidad()
        self._reposicionar_isla()
    def _ajustar_densidad(self):
        """v5.2 (pedido: «que sea adaptable a diferentes pantallas»): en
        pantallas bajas o angostas las cabeceras y los margenes se compactan
        (el contenido gana el sitio); en grandes vuelven a su tamaño."""
        alto, ancho = self.height(), self.width()
        nivel = 2 if (alto < 760 or ancho < 1180) else (1 if (alto < 900 or ancho < 1440) else 0)
        if nivel == getattr(self, '_densidad', None):
            return
        self._densidad = nivel
        tam_t = {0: 34, 1: 28, 2: 24}[nivel]
        tam_barra = {0: 21, 1: 19, 2: 17}[nivel]
        margenes = {0: (40, 86, 28, 22), 1: (28, 78, 22, 16), 2: (20, 72, 16, 10)}[nivel]
        for clave, (t, s) in getattr(self, '_cabeceras', {}).items():
            try:
                t.setFont(fuente(tam_t if clave == 'inicio' else tam_barra, peso='extra'))
                if hasattr(s, 'poner_compacto'):
                    s.poner_compacto(nivel >= 2)
                    s.setVisible(clave != 'inicio')
                else:
                    s.setVisible(nivel < 2 and clave != 'inicio')
            except Exception:
                pass
        for capa in getattr(self, '_capas_pagina', {}).values():
            try:
                capa.setContentsMargins(*margenes)
                capa.setSpacing(18 if nivel == 0 else 12)
            except Exception:
                pass
        ed = getattr(self, '_editor', None)
        if ed is not None:
            try:
                ed.ajustar_densidad(nivel)
            except Exception:
                pass
    # -- v5.1: la esquina del lateral y Ajustes ---------------------------------
    def _pintar_pie_lateral(self):
        import ajustes_ui
        self.lat_version.configure(text=f'v{APP_VERSION} · ' + ajustes_ui.texto_canal())
    def _comprobar_conexion_lateral(self):
        """«Comprobar conexión»: rehace el estado de Resolve ahora (MCP)."""
        self.lat_punto_resolve.poner(TEXT_MUTED)
        self.lat_resolve.configure(text=tr('Comprobando Resolve…'))
        self.lat_resolve_det.configure(text='')
        def trabajo():
            import resolve_mcp
            return resolve_mcp.estado(refrescar=True)
        _correr_en_hilo(self, trabajo, lambda _r, _e: self._refrescar_estado())
    def _abrir_ajustes_rapido(self):
        import ajustes_ui
        panel = getattr(self, '_panel_rapido', None)
        if panel is not None and ui.vivo(panel):
            panel.cerrar()
            return
        self._panel_rapido = ajustes_ui.PanelRapido(self, lambda: self._abrir_ajustes('general'))
        self._panel_rapido.abrir(self.isla, rect=self.isla.rect_de('ajustes'))
    def _abrir_ajustes(self, pestana='general'):
        import ajustes_ui
        self._ventana_ajustes = ajustes_ui.VentanaAjustes(self, pestana)
        self._ventana_ajustes.abrir()
    def poner_encima(self, si, guardar=False):
        """El alfiler: CineCaptions por delante de Resolve (WindowStaysOnTop)."""
        si = bool(si)
        if hasattr(self, 'pin_btn') and self.pin_btn.isChecked() != si:
            self.pin_btn.setChecked(si)
        if hasattr(self, 'isla'):
            self.isla.poner_pin(si)
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != si:
            visible = self.isVisible()
            geo = self.geometry()
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, si)
            if visible:
                self.setGeometry(geo)
                self.show()
        if guardar:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'ventana_encima': si})
    def reiniciar_programa(self):
        """Cierra y vuelve a abrir CineCaptions (para aplicar tema, tamaño o idioma)."""
        import subprocess
        self._guardar_preferencias()
        if getattr(sys, 'frozen', False):
            orden = [sys.executable, '--reinicio']
        else:
            orden = [sys.executable, str(Path(sys.argv[0]).resolve()), '--reinicio']
        flags = 0x00000008 | 0x00000200 if sys.platform.startswith('win') else 0
        subprocess.Popen(orden, creationflags=flags, close_fds=True)
        QApplication.instance().quit()
    def _nueva_pagina(self, clave, titulo, subtitulo, desplazable=True):
        pag = QWidget()
        capa = QVBoxLayout(pag)
        capa.setContentsMargins(40, 86, 28, 22)
        capa.setSpacing(18)
        if clave in NUMERO_PAGINA:
            barra = BarraTitulo(NUMERO_PAGINA[clave], titulo, subtitulo)
            t, s = barra.titulo, barra.sub
            capa.addWidget(barra)
        else:
            cab, cc = caja_v(espacio=6)
            import mograf_ui
            t = mograf_ui.EtiquetaCinetica(titulo, 34, peso='extra', color='#FFFFFF')
            s = _Elidida(subtitulo, 15, color=TEXT_MUTED)
            cc.addWidget(t)
            cc.addWidget(s)
            capa.addWidget(cab)
        self._cabeceras[clave] = (t, s)
        if not hasattr(self, '_capas_pagina'):
            self._capas_pagina = {}
        self._capas_pagina[clave] = capa
        if desplazable:
            d = Desplazable(espacio=20, margenes=(0, 4, 12, 8), estirar_final=False)
            capa.addWidget(d, 1)
            contenido = d.capa
            if not hasattr(self, '_desplazables'):
                self._desplazables = {}
            self._desplazables[clave] = d
        else:
            w = QWidget()
            contenido = QVBoxLayout(w)
            contenido.setContentsMargins(0, 0, 12, 0)
            contenido.setSpacing(20)
            capa.addWidget(w, 1)
        self.pila.agregar(pag)
        self._paginas[clave] = pag
        return (pag, contenido)
    def ir_a(self, clave, animar=True):
        """Cambia de pantalla. «Estilos» y «SFX Lab» se arman la primera vez
        que se abren (leer los packs y la biblioteca de sonidos cuesta).

        «Proyecto» es ahora solo «Estilos y composición»: la pantalla «Nuevo proyecto» (vista previa,
        receta, Generar) ya no se muestra; GO, en Inicio, hace ese trabajo. Sus widgets se siguen
        construyendo, fuera de pantalla, porque el resto del programa lee y guarda sus valores."""
        if clave == 'nuevo':
            clave = 'estilos'
        if (clave == 'estilos' and self._plantillas_ventana is None) or (clave == 'sfx' and self._estudio_ventana is None):
            # v5.4: la primera vez armar la pantalla cuesta unas decimas de segundo: el boton del menu ya se ve
            # pulsado antes de empezar (si no, parece que el clic no hizo nada)
            self._marcar_nav('nuevo' if clave == 'estilos' else clave)
            for b in self._nav.values():
                b.repaint()
        if clave == 'estilos':
            self._asegurar_estilos()
        elif clave == 'sfx' and not self._asegurar_sfx():
            self._marcar_nav(self._pagina_actual)
            return
        elif clave == 'efectos' and not self._asegurar_efectos():
            self._marcar_nav(self._pagina_actual)
            return
        pagina = self._paginas.get(clave)
        if pagina is None:
            return
        cambio = self._pagina_actual != clave
        self._pagina_actual = clave
        self._marcar_nav('nuevo' if clave == 'estilos' else clave)
        for c, var in getattr(self, '_conmutadores', {}).items():
            try:
                var.set(tr('Estilos y composición') if clave == 'estilos' else tr('Proyecto'))
            except Exception:
                pass
        self.pila.mostrar(pagina, animar=animar)
        # v5.2: Inicio con todo el espectaculo; el resto, el mismo fondo tenue
        # y las tarjetas entrando una tras otra
        try:
            self.fondo.poner_intensidad(1.0 if clave == 'inicio' else 0.38)
            self.fondo.poner_pagina(clave)
            self.escena_go.setVisible(clave == 'inicio')
            self.fondo.poner_cubierto(clave == 'inicio')       # v5.4: la escena 3D lo tapa entero: no se pinta ni se anima
            if animar and cambio:
                import efectos_ui
                import mograf_ui
                despues(10, lambda p=pagina: mograf_ui.entrada_escalonada(efectos_ui.tarjetas_de(p)), self)
                titulo_pagina = self._cabeceras.get(clave, (None, None))[0]
                if hasattr(titulo_pagina, 'revelar'):
                    despues(40, titulo_pagina.revelar, self)
        except Exception:
            pass
        if clave == 'inicio':
            self._refrescar_recientes()
            self._pintar_go_reposo()
        if hasattr(self, 'marca_cinema'):
            self.marca_cinema.poner_en_inicio(clave == 'inicio')
        if clave == 'editor':
            self._al_entrar_en_creativo()          # v5.3.2: detecta el audio / la línea de tiempo de Proyecto (y abre el editor si ya hay palabras)
    def _marcar_nav(self, clave):
        for c, b in self._nav.items():
            b.setChecked(c == clave)
        if hasattr(self, 'isla'):
            self.isla.marcar(clave)
    def _conmutador_proyecto(self, capa, clave):
        """v5.2: el conmutador «Proyecto | Estilos y composición» arriba de las
        dos pantallas que comparten la entrada «Proyecto» del menu."""
        if not hasattr(self, '_conmutadores'):
            self._conmutadores = {}
        opciones = [tr('Proyecto'), tr('Estilos y composición')]
        var = StringVar(opciones[1] if clave == 'estilos' else opciones[0])
        def elegir(_v=None):
            self.ir_a('estilos' if var.get() == opciones[1] else 'nuevo')
        seg = Segmentado(opciones, var, elegir, alto=38, tam=14)
        fila, cf = caja_h(espacio=0)
        cf.addWidget(seg)
        cf.addStretch(1)
        capa.insertWidget(1, fila)
        self._conmutadores[clave] = var
    def _en_fondo(self, punto_global):
        p = self.fondo.mapFromGlobal(punto_global)
        return (float(p.x()), float(p.y()))
    def _zonas_opacas(self):
        """Las tarjetas de la pantalla actual (en coordenadas del fondo): el
        fondo animado no las repinta (efectos_ui.FondoVivo)."""
        pag = self._paginas.get(self._pagina_actual)
        if pag is None or not pag.isVisible():
            return []
        import efectos_ui
        salida = []
        for w in efectos_ui.tarjetas_de(pag, maximo=60):
            if w.graphicsEffect() is not None:
                continue
            esquina = w.mapTo(self.fondo, QPoint(0, 0))
            salida.append(QRect(esquina, w.size()).adjusted(8, 8, -8, -8))
        return salida
    def eventFilter(self, obj, ev):
        if obj is getattr(self, 'fondo', None) and ev.type() == QEvent.Type.Resize and getattr(self, 'escena_go', None) is not None:
            self.escena_go.setGeometry(self.fondo.rect())
        return super().eventFilter(obj, ev)
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and self._entradas_activas:
            e.acceptProposedAction()
    def dropEvent(self, e):
        for url in e.mimeData().urls():
            ruta = url.toLocalFile()
            if ruta:
                self._soltar_archivo(ruta)
                break
    def _soltar_archivo(self, ruta):
        """Un video o audio soltado en la ventana (o en la zona de Inicio)."""
        p = Path(ruta)
        if not self._entradas_activas:
            try:
                self.aviso_inicio.configure(text=tr('CineCaptions está trabajando: espera a que termine antes de soltar otro video.'))
            except Exception:
                pass
            return
        if not p.is_file():                               # antes se ignoraba en silencio: el usuario no sabía por qué no pasaba nada
            texto = tr('No encuentro «{n}»: ¿lo moviste o le cambiaste el nombre?', n=p.name) if not p.exists() else tr('«{n}» es una carpeta: suelta el archivo de video.', n=p.name)
            registro.aviso(texto, 'GO · soltar archivo')
            try:
                self.aviso_inicio.configure(text=texto)
            except Exception:
                pass
            return
        if p.suffix.lower() not in self.EXTENSIONES_MEDIO:
            registro.aviso(tr('«{n}» no parece un video ni un audio.', n=p.name), 'GO · soltar archivo')
            try:
                self.aviso_inicio.configure(text=tr('«{n}» no parece un video ni un audio.', n=p.name))
            except Exception:
                pass
            return
        self.video_var.set(str(p))
        self._olvidar_marca(tr('soltaste un archivo'))
        if self._pagina_actual == 'inicio':
            # v5.10 (pedido: «arrastro mi video a Inicio y que lo meta a captions y le ponga los captions»): soltarlo ARRANCA GO solo; GO
            # arma un timeline nuevo en Resolve con ese video y le pone los captions (antes quedaba «listo» y había que pulsar GO, y los
            # captions caían en el timeline que estuviera abierto)
            self._go_archivo = str(p)
            self._pintar_go_reposo()
            if not getattr(self, '_go_corriendo', False):
                despues(120, self._go, self)
        else:
            self.ir_a('estilos')
    EXTENSIONES_MEDIO = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v', '.mxf', '.mts', '.m2ts', '.wmv', '.flv', '.mpg', '.mpeg', '.3gp',
                         '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.wma'}
    def closeEvent(self, e):
        ed = self._editor
        if ed is not None:
            try:
                ed._cancelar()
            except Exception:
                pass
        try:
            self._guardar_preferencias()
        except Exception:
            pass
        if self._estudio_ventana is not None:
            try:
                self._estudio_ventana._al_cerrar()
            except Exception:
                pass
        super().closeEvent(e)
    # -- Inicio ---------------------------------------------------------------
    def _pagina_inicio(self):
        _pag, capa = self._nueva_pagina('inicio', tr('Inicio'), tr('Todo lo necesario para subtitular tu próximo video, de un vistazo'))
        # v5.1 (pedido: «la página de inicio solo un botón GO que lo haga todo
        # con un clic, ultra minimalista, con animaciones»): arriba el GO; el
        # panel de antes queda plegado en «Detalles» (sus tarjetas siguen
        # vivas: el resto del programa las pinta igual)
        t_cab, s_cab = self._cabeceras['inicio']
        t_cab.hide()
        s_cab.hide()
        import un_clic_ui
        # v5.2.1: en Inicio (sin barra de título) los avisos y errores salen en esta fila, con el botón del registro
        fila_reg, cfr = caja_h(espacio=10)
        self.aviso_inicio = registro_ui.SubtituloVivo('', 13, TEXT_MUTED)
        cfr.addWidget(self.aviso_inicio, 1)
        cfr.addWidget(registro_ui.BotonRegistro())
        capa.addWidget(fila_reg)
        self.go_panel = un_clic_ui.PanelGo(self._alternar_detalles_inicio)
        self.go_panel.al_ver_resolve = self._go_ver_en_resolve
        self.go_panel.al_editar = lambda: self.ir_a('editor')
        self.go_panel.go.connect(self._go)
        capa.addWidget(self.go_panel)
        capa_pagina = capa
        self._inicio_detalles, capa = caja_v(espacio=20)
        capa_pagina.addWidget(self._inicio_detalles)
        self._inicio_detalles.hide()
        fila, cf = caja_h(espacio=20)
        self.tarjeta_resolve = _TarjetaEstado(tr('DaVinci Resolve'), self._ver_ultimo_resultado)
        Tooltip(self.tarjeta_resolve, tr('Clic: lo último que respondió Resolve.'))
        self.tarjeta_motor = _TarjetaEstado(tr('Motor de voz'))
        self.tarjeta_traduccion = _TarjetaEstado(tr('Traducción'), self._abrir_idiomas_traduccion)
        Tooltip(self.tarjeta_traduccion, tr('Clic: buscar y descargar más idiomas de traducción.'))
        self.tarjeta_licencia = _TarjetaEstado(tr('Licencia'), self._abrir_licencia)
        for t in (self.tarjeta_resolve, self.tarjeta_motor, self.tarjeta_traduccion, self.tarjeta_licencia):
            cf.addWidget(t, 1)
        self.tarjeta_motor.poner(ui.VERDE, f'Whisper {MODEL_SIZE}', tr('Local · usa GPU si hay CUDA'))
        capa.addWidget(fila)
        medio, cm = caja_h(espacio=20)
        zona_t = Tarjeta(margenes=(22, 22, 22, 22))
        self.zona = ZonaSoltar(self._soltar_archivo)
        cz = QVBoxLayout(self.zona)
        cz.setContentsMargins(24, 26, 24, 26)
        cz.setSpacing(10)
        cz.addStretch(1)
        onda = Onda(ui.ACCENT_CLARO, alto=58, barra=4.0, hueco=3.4)
        onda.poner_picos([0.16 + 0.84 * abs(math.sin(i * 0.55) * math.cos(i * 0.21)) for i in range(36)])
        onda.setFixedWidth(270)
        cz.addWidget(onda, 0, Qt.AlignmentFlag.AlignHCenter)
        cz.addSpacing(8)
        cz.addWidget(Etiqueta(tr('Arrastra un video o audio aquí'), 21, peso='extra', color='#FFFFFF', alineacion=Qt.AlignmentFlag.AlignCenter))
        cz.addWidget(Etiqueta(tr('Se transcribe en tu equipo, sin subir nada a internet'), 14, color=TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignCenter))
        cz.addSpacing(8)
        botones, cb = caja_h(espacio=12)
        cb.addStretch(1)
        self.browse_btn2 = Boton(tr('Buscar archivo…'), self._browse, tipo='primario', alto=42, ancho=190)
        cb.addWidget(self.browse_btn2)
        self.detect_btn2 = Boton(tr('Detectar de Resolve'), self._detectar_e_ir, alto=42, ancho=210)
        cb.addWidget(self.detect_btn2)
        cb.addStretch(1)
        cz.addWidget(botones)
        cz.addStretch(1)
        zona_t.capa.addWidget(self.zona)
        cm.addWidget(zona_t, 8)
        # v5.2: soltar un vídeo ya lo hace GO (en toda la ventana) y la tarjeta
        # «Fuente» de Proyecto: esta zona repetía lo mismo y queda retirada
        zona_t.hide()
        recetas_t = Tarjeta(espacio=12)
        cab, cc = caja_h(espacio=8)
        cc.addWidget(Etiqueta(tr('Recetas rápidas'), 16, peso='medio', color='#FFFFFF'))
        cc.addStretch(1)
        guardar = Enlace(tr('+ Guardar la actual'), self._guardar_receta_actual, 12, color=ui.ACCENT_CLARO, color_hover='#8FC7FF', subrayada=False, peso='medio')
        Tooltip(guardar, tr('Guarda el modo, el formato, los efectos y la traducción que tienes elegidos ahora como una receta de un clic. Clic derecho sobre una receta para quitarla.'))
        cc.addWidget(guardar)
        recetas_t.capa.addWidget(cab)
        self.recetas_w, self.recetas_capa = caja_v(espacio=12)
        recetas_t.capa.addWidget(self.recetas_w)
        recetas_t.capa.addStretch(1)
        cm.addWidget(recetas_t, 5)
        capa.addWidget(medio)
        abajo, ca = caja_h(espacio=20)
        recientes_t = Tarjeta(espacio=6)
        cab, cc = caja_h(espacio=8)
        cc.addWidget(Etiqueta(tr('Proyectos recientes'), 16, peso='medio', color='#FFFFFF'))
        cc.addStretch(1)
        cc.addWidget(Enlace(tr('Todos…'), self._abrir_proyectos_guardados_main, 12, color=TEXT_MUTED, color_hover=ui.ACCENT_CLARO, subrayada=False, peso='medio'))
        recientes_t.capa.addWidget(cab)
        recientes_t.capa.addSpacing(8)
        recientes_t.capa.addWidget(_FilaProyecto([tr('Proyecto'), tr('Idioma'), tr('Modo'), tr('Estado'), tr('Cuándo')], cabecera=True))
        self.recientes_w, self.recientes_capa = caja_v(espacio=0)
        recientes_t.capa.addWidget(self.recientes_w)
        recientes_t.capa.addStretch(1)
        self.recientes_row = self.recientes_w
        ca.addWidget(recientes_t, 8)
        sistema_t = Tarjeta(titulo=tr('Estado del sistema'), espacio=4)
        sistema_t.capa.addSpacing(8)
        self._filas_sistema = {}
        for clave, nombre in [('librerias', tr('Librerías')), ('scripts', tr('Scripts en Resolve')), ('tipografias', tr('Tipografías')), ('modelo', tr('Modelo de voz')), ('traduccion', tr('Traducción sin internet')), ('emojis', tr('Emojis')), ('emojis_anim', tr('Emojis animados')), ('efectos', tr('Biblioteca de efectos'))]:
            f, cfs = caja_h(espacio=12, margenes=(0, 7, 0, 7))
            icono = IconoEstado('info')
            cfs.addWidget(icono)
            cfs.addWidget(Etiqueta(nombre, 14, color='#E0EBFB'))
            cfs.addStretch(1)
            valor = Etiqueta('…', 13, color=TEXT_MUTED)
            cfs.addWidget(valor)
            sistema_t.capa.addWidget(f)
            self._filas_sistema[clave] = (icono, valor, f)
        sistema_t.capa.addStretch(1)
        sistema_t.capa.addSpacing(8)
        self.diag_btn = Boton(tr('Ejecutar diagnóstico'), self._ejecutar_diagnostico, alto=40)
        Tooltip(self.diag_btn, tr('¿Problemas con el Puente? Copia al portapapeles todo lo que hace falta para cerrar el caso de un vistazo.'))
        sistema_t.capa.addWidget(self.diag_btn)
        enlaces, ce = caja_h(espacio=14, margenes=(0, 6, 0, 0))
        ce.addStretch(1)
        for texto, pista, accion in [(tr('Reinstalar scripts'), tr('¿No ves los scripts en el menú de Resolve? Los deja otra vez en su sitio, sin reinstalar el programa.'), self._instalar_en_resolve), (tr('Qué respondió Resolve'), tr('¿Corriste el script y no pasó nada? Los scripts corren dentro de Resolve, donde el mensaje va a una consola que nadie tiene abierta. Aquí se lee.'), self._ver_ultimo_resultado)]:
            lbl = Enlace(texto, accion, 12, color=TEXT_MUTED, color_hover=ui.ACCENT_CLARO)
            Tooltip(lbl, pista)
            ce.addWidget(lbl)
        ce.addStretch(1)
        sistema_t.capa.addWidget(enlaces)
        ca.addWidget(sistema_t, 5)
        capa.addWidget(abajo)
        capa.addStretch(1)
    def _detectar_e_ir(self):
        self.ir_a('estilos')
        self._detectar_desde_resolve(silencioso=False)
    # -- v5.1: GO, todo con un clic ------------------------------------------------
    def _alternar_detalles_inicio(self):
        ver = not self._inicio_detalles.isVisible()
        self._inicio_detalles.setVisible(ver)
        self.go_panel.detalles.configure(text=tr('Ocultar detalles') if ver else tr('Detalles y estado del sistema'))
        if ver:
            self._refrescar_recientes()
    def _pintar_go_reposo(self):
        """La linea bajo el GO: con que va a trabajar si lo pulsas ahora."""
        panel = getattr(self, 'go_panel', None)
        if panel is None or getattr(self, '_go_corriendo', False):
            return
        try:
            self._pintar_opciones_go()
        except Exception:
            pass
        mcp = (getattr(self, '_estado_sistema', {}) or {}).get('mcp') or {}
        ruta = self.video_var.get().strip().strip('"') if hasattr(self, 'video_var') else ''
        archivo = getattr(self, '_go_archivo', None)
        # v5.5: la línea dice QUÉ Resolve hay (Studio o Free) y por dónde se le habla; en ámbar/rojo cuando GO no podría colocar nada
        try:
            import colocacion
            det = colocacion.detectar_resolve(getattr(self, '_estado_sistema', None))
        except Exception:
            det = {'texto': '', 'tono': None, 'edicion': None}
        ed = det.get('edicion')
        tono = det.get('tono') if (getattr(self, '_estado_sistema', None) and det.get('texto')) else None
        try:
            from PySide6.QtGui import QFontMetricsF
            _fm = QFontMetricsF(panel.linea.font())
        except Exception:
            _fm = None

        def _ajusta(base, *extras):
            """La línea de Inicio mide 640 px y corta con «…»: lo importante (la edición de Resolve) va siempre; lo demás solo si cabe."""
            texto = base
            for e in extras:
                if not e:
                    continue
                if _fm is not None and _fm.horizontalAdvance(texto + ' · ' + e) > 610:
                    break
                texto += ' · ' + e
            return texto
        archivo_ok = archivo and Path(archivo).exists()
        ruta_ok = bool(ruta) and Path(ruta).exists()
        if (archivo_ok or ruta_ok) and det.get('texto') and getattr(self, '_estado_sistema', None):
            nombre_v = Path(archivo if archivo_ok else ruta).name
            panel.reposo(_ajusta(det['texto'], tr('«{n}»', n=nombre_v), tr('suelta otro vídeo para cambiarlo')), tono=tono)
        elif archivo_ok or ruta_ok:
            panel.reposo(tr('Listo con «{n}» (suelta otro vídeo para cambiarlo)', n=Path(archivo if archivo_ok else ruta).name))
        elif mcp.get('conectado') and mcp.get('timeline'):
            panel.reposo(_ajusta(det['texto'], tr('timeline «{t}»', t=mcp['timeline']), f"{mcp['ancho']}×{mcp['alto']}" if mcp.get('ancho') else '', tr('suelta un video aquí')), tono=tono)
        elif (getattr(self, '_estado_sistema', {}) or {}).get('modo') in ('studio', 'puente'):
            panel.reposo(_ajusta(det['texto'], tr('pulsa GO con tu timeline abierto')), tono=tono)
        elif det.get('texto') and getattr(self, '_estado_sistema', None):
            panel.reposo(det['texto'], listo=True, tono=tono)
        else:
            panel.reposo(tr('Suelta un video aquí y le pongo los captions · o abre DaVinci Resolve con tu timeline'), listo=True)
    # -- v5.2: las opciones rapidas de GO (sin pasar por otras pestañas) -------------
    def _go_sfx(self):
        try:
            import ajustes_ui
            return ajustes_ui.leer_prefs().get('go_sfx', True) is not False
        except Exception:
            return True
    def _pintar_opciones_go(self):
        panel = getattr(self, 'go_panel', None)
        if panel is None or not hasattr(self, 'lang_var'):
            return
        limpiar_capa(panel.opciones_capa)
        pack = self._plantilla_un_clic()
        nombre_pack = tr('Diseño automático') if pack in ('auto', 'dinamico', 'Base títulos dinámicos') else plantillas.nombre_visible(pack)
        formato = self.formato_var.get() if hasattr(self, 'formato_var') else tr('Detectar solo')
        chips = [(tr('Estilo: {p}', p=nombre_pack), self._menu_estilo_go,
                  tr('Clic: elegir el tema de GO (Tema 1 = títulos de gancho, Tema 2 = captions palabra a palabra, Tema 3 = subtítulos virales).') if plantillas.SOLO_TEMAS
                  else tr('Clic: elegir el estilo de GO (Referencia = captions palabra a palabra, línea fina y negrita + palabra grande; Diseño automático = 3 líneas).')),
                 (tr('Emojis: {v}', v=tr('sí') if self._go_emojis() else tr('no')), self._alternar_emojis_go,
                  tr('Clic: con o sin emojis en los subtítulos.')),
                 (tr('Efectos: {v}', v=tr('sí') if self._go_sfx() else tr('no')), self._alternar_sfx_go,
                  tr('Clic: con o sin efectos de sonido por palabra.')),
                 (tr('Visuales: {v}', v=tr('sí') if self._go_visuales() else tr('no')), self._alternar_visuales_go,
                  tr('Clic: con o sin efectos visuales (intro, transiciones en los cortes e iconos flotantes). Se eligen en la página «Efectos».')),
                 (tr('Proyecto: {p}', p=self._go_proyecto() or tr('el abierto')), self._alternar_proyecto_go,
                  tr('Al soltar un video en Inicio: se arma en el proyecto «CineCaptions» de Resolve (se abre o se crea solo) o en el proyecto que tengas abierto. Clic: cambiar.'))]
        chips = [(t, f, a, ui.ACCENT_CLARO) for t, f, a in chips]
        act = getattr(self, '_actualizacion', None)
        if isinstance(act, dict) and act.get('version'):
            try:
                import actualizaciones
                if actualizaciones.es_mas_nueva(act['version'], APP_VERSION):
                    chips.insert(0, (tr('Nueva versión {v} ↑', v=act['version']), self._ofrecer_actualizacion,
                                     tr('Hay una versión nueva de CineCaptions. Clic: descargarla, comprobar que es auténtica e instalarla (se cierra y se vuelve a abrir solo).'), ui.AMBAR))
            except Exception:
                pass
        # v5.8 (auditoría del flujo): lo que cambia el resultado y GO no enseñaba (se quedaba guardado de otra vez) sale en ámbar y se quita con un clic
        # (con un pack «guion» —palabra a palabra— el planificador decide posición y estilo: esos dos ajustes no se aplican y no se avisa de ellos)
        try:
            p_guion = plantillas.buscar_pack(pack)
            es_guion = bool(p_guion is not None and (getattr(p_guion, 'guion', None) or getattr(p_guion, 'mezcla', False)))
        except Exception:
            es_guion = False
        if not es_guion and not composicion.es_defecto(getattr(self, 'composicion', None)):
            chips.append((tr('Posición ajustada ✕'), self._quitar_ajuste_fino,
                          tr('Tu «Ajuste fino» de Proyecto mueve los subtítulos ({d}) respecto a la posición exacta del estilo. Clic: quitarlo.',
                             d=resumen_composicion(getattr(self, 'composicion', None))), ui.AMBAR))
        try:
            hay_varios = len(plantillas.variantes_de(pack, self._formato_en_juego())) > 1
        except Exception:
            hay_varios = False
        if estilo_fijo() and hay_varios and not es_guion:
            chips.append((tr('Solo el estilo {n} ✕', n=estilo_fijo()), self._quitar_estilo_fijo,
                          tr('Todos los bloques usan el mismo estilo del pack. Clic: volver a alternar los estilos.'), ui.AMBAR))
        for texto, fn, ayuda, color in chips:
            ch = Chip(texto, color, fn, alto=32, tam=13)
            Tooltip(ch, ayuda)
            panel.opciones_capa.addWidget(ch)
    def _menu_estilo_go(self):
        """El chip «Estilo» de Inicio: elegir el estilo de GO sin salir de la página."""
        menu = Menu(self)
        actual = self._plantilla_un_clic()
        base = 'Base títulos dinámicos'
        try:
            import ajustes_ui
            ocultos = {n for n in ajustes_ui.leer_prefs().get('packs_ocultos', []) if isinstance(n, str) and not plantillas.es_de_fabrica(n)}
            packs = [p for p in plantillas.listar_packs() if plantillas.sirve_en_go(p) and p.nombre not in ocultos]
            packs = [p for p in packs if plantillas.pack_permitido(p.nombre)]
            _orden_temas = list(plantillas.FABRICA)
            packs.sort(key=lambda p: _orden_temas.index(p.nombre) if p.nombre in _orden_temas else len(_orden_temas))
        except Exception:
            packs = []
        formato = self._formato_para_temas()
        guion = [p for p in packs if getattr(p, 'guion', None)]
        otros = [p for p in packs if not getattr(p, 'guion', None) and p.nombre != base]
        for p in guion:
            marca = '✓  ' if p.nombre == actual else '      '
            extra = '' if plantillas.sirve_en_go(p, formato) else tr('  (solo vertical)')
            etiqueta = (tr('{n} · subtítulos virales', n=plantillas.nombre_visible(p.nombre)) if getattr(p, 'viral', False)
                        else tr('{n} · títulos de gancho', n=plantillas.nombre_visible(p.nombre)) if getattr(p, 'kinetic', False)
                        else tr('{n} · captions limpios', n=plantillas.nombre_visible(p.nombre)) if p.nombre == 'Tema4'
                        else tr('{n} · captions palabra a palabra', n=plantillas.nombre_visible(p.nombre)))
            menu.agregar(marca + etiqueta + extra, lambda n=p.nombre: self._poner_go_pack(n))
        if not plantillas.SOLO_TEMAS:
            marca = '✓  ' if actual in (base, 'dinamico', 'auto') else '      '
            menu.agregar(marca + tr('Diseño automático · 3 líneas'), lambda: self._poner_go_pack('auto'))
        for p in otros:                                 # (con SOLO_TEMAS: solo los packs del usuario)
            marca = '✓  ' if p.nombre == actual else '      '
            menu.agregar(marca + plantillas.nombre_visible(p.nombre), lambda n=p.nombre: self._poner_go_pack(n))
        if otros or not plantillas.SOLO_TEMAS:
            menu.separador()
        menu.agregar(tr('Ver los temas…') if plantillas.SOLO_TEMAS else tr('Más estilos y vista real…'), lambda: self.ir_a('estilos'))
        menu.mostrar(QCursor.pos())
    def _quitar_ajuste_fino(self):
        """El chip «Posición ajustada ✕» de Inicio: vuelve a la posición exacta del estilo (no toca lo que ya está en el timeline)."""
        self.composicion = composicion.valida(None)
        try:
            cv = getattr(self, '_composicion_ventana', None)
            if cv is not None and cv.existe():
                cv.valor = composicion.valida(None)
                for clave in ('altura', 'horizontal'):
                    getattr(cv, f'_desl_{clave}').set(0.0)
                    getattr(cv, f'{clave}_lbl').configure(text='+0 %')
                cv._refrescar()
        except Exception:
            registro.excepcion(origen='quitar ajuste fino')
        self._guardar_preferencias()
        self._pintar_opciones_go()
    def _quitar_estilo_fijo(self):
        """El chip «Solo el estilo N ✕» de Inicio: vuelve a alternar los estilos del pack."""
        poner_estilo_fijo(0)
        try:
            cv = getattr(self, '_composicion_ventana', None)
            if cv is not None and cv.existe():
                cv._actualizar_pager()
                cv._reflejar_en_packs()
        except Exception:
            registro.excepcion(origen='quitar estilo fijo')
        self._pintar_opciones_go()
    def _texto_chip_idioma(self):
        """«Idioma: Inglés», o con «Automático» el que GO oyó en el último video: «Idioma: Inglés (detectado)»."""
        nombre = self.lang_var.get()
        if LANG_CODE_BY_NAME.get(nombre) == 'auto':
            oido = getattr(self, '_idioma_detectado_go', None)
            if oido:
                return tr('Idioma: {i} (detectado)', i=NOMBRE_POR_CODIGO.get(oido, oido))
            return tr('Idioma: automático')
        return tr('Idioma: {i}', i=nombre)
    def _cambiar_idioma_go(self, nombre):
        """Elegir el idioma desde Inicio. Si GO ya terminó con otro idioma, se deja listo para repetirlo con el correcto (un solo clic en GO)."""
        self._elegir_idioma(nombre)
        self._pintar_opciones_go()
        ultimo = getattr(self, '_ultimo_go_archivo', None)
        if ultimo and getattr(self, '_go_termino', False) and not getattr(self, '_go_corriendo', False) and Path(ultimo).exists():
            self._go_archivo = ultimo
            self.go_panel.reposo(tr('Idioma: {i}. Pulsa GO para repetir «{n}» con ese idioma.', i=nombre, n=Path(ultimo).name), forzar=True)
    def _menu_idioma_go(self):
        menu = Menu(self)
        favoritos = [NOMBRE_POR_CODIGO.get(f, f) for f in (getattr(self, 'favoritos_idiomas', []) or [])]
        frecuentes = [NOMBRE_POR_CODIGO.get(c, n) for n, c in IDIOMAS_FRECUENTES]
        vistos = set()
        for nombre in favoritos + frecuentes:
            if nombre in vistos or nombre not in LANG_MENU:
                continue
            vistos.add(nombre)
            marca = '✓  ' if nombre == self.lang_var.get() else '      '
            menu.agregar(marca + nombre, lambda n=nombre: self._cambiar_idioma_go(n))
        menu.separador()
        menu.agregar(tr('Más idiomas…'), lambda: (self._abrir_buscador_idioma(), despues(400, self._pintar_opciones_go, self)))
        menu.mostrar(QCursor.pos())
    def _go_emojis(self):
        try:
            import ajustes_ui
            return ajustes_ui.leer_prefs().get('go_emojis', True) is not False
        except Exception:
            return True
    def _alternar_emojis_go(self):
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'go_emojis': not self._go_emojis()})
        except Exception:
            pass
        self._pintar_opciones_go()
    def _go_visuales(self):
        try:
            import efectos_visuales
            return efectos_visuales.activado()
        except Exception:
            return False
    def _alternar_visuales_go(self):
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'go_efectos_visuales': not self._go_visuales()})
        except Exception:
            pass
        if getattr(self, '_efectos_widget', None) is not None:
            self._efectos_widget.refrescar()
        self._pintar_opciones_go()
    def _alternar_sfx_go(self):
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'go_sfx': not self._go_sfx()})
        except Exception:
            pass
        self._sincronizar_sfx()
        self._pintar_opciones_go()
    # -- v5.11: vigilancia de GO / Generar (ver vigilancia.py) -----------------------------
    PISTAS_ATASCO = {
        'timeline': 'Revisa que DaVinci Resolve esté abierto con un proyecto y con el control externo en «Local» (Preferencias > General).',
        'voz': 'Si el modelo de voz no responde, cambio al de respaldo solo.',
        'ia': 'Si la IA de texto no responde, sigo con el motor de reglas.',
        'resolve': 'Mira si Resolve tiene un diálogo abierto o está ocupado.',
        'colocar': 'Mira si Resolve tiene un diálogo abierto o está ocupado.',
    }
    def _vigilar_tarea(self, nombre, paso='', hilo=None):
        try:
            import vigilancia
            self._vig_nombre = nombre
            def al_aviso(texto):
                pista = self.PISTAS_ATASCO.get(getattr(self, '_go_paso_actual', '') or paso or '', '')
                self.msg_queue.put(('vigia', (texto + ' ' + pista).strip()))          # (kind 'vigia' no cuenta como señal de vida)
            vigilancia.iniciar(nombre, hilo=hilo, paso=paso, al_aviso=al_aviso, al_atasco=self._destrabar)
        except Exception:
            registro.excepcion(origen='vigilancia · iniciar')
    def _fin_tarea(self, ok=True, motivo=''):
        nombre = getattr(self, '_vig_nombre', None)
        if not nombre:
            return
        self._vig_nombre = None
        try:
            import vigilancia
            vigilancia.terminar(nombre, ok, motivo)
        except Exception:
            pass
    def _esperando_al_usuario(self, esperando):
        """El editor de palabras o un diálogo tienen detenido el trabajo A PROPÓSITO: el vigía no debe contarlo como atasco."""
        nombre = getattr(self, '_vig_nombre', None)
        if not nombre:
            return
        try:
            import vigilancia
            (vigilancia.pausar if esperando else vigilancia.reanudar)(nombre)
        except Exception:
            pass
    def _destrabar(self, paso):
        """El vigía decidió que `paso` está atascado: se matan los motores (voz / IA de texto) o el puente con Resolve para que la llamada colgada FALLE y
        el flujo siga solo con el respaldo (Whisper, motor de reglas) o termine con un mensaje claro en vez de quedarse esperando. Corre en el hilo del vigía."""
        try:
            if paso in ('voz', 'ia', 'diseno', ''):
                import motor_voz
                import ia_texto
                cerrado = (ia_texto if paso == 'ia' else motor_voz).abortar()
                if cerrado:
                    registro.aviso(f'Destrabado: cerré el motor de {"IA de texto" if paso == "ia" else "voz"} que no respondía; sigue el modelo de respaldo.', 'vigilancia')
                else:
                    registro.aviso('No hay ningún motor externo que cerrar: el paso corre dentro del programa (Whisper en CPU/GPU). Si de verdad está colgado, cierra y '
                                   'vuelve a abrir CineCaptions; el Registro tiene la pila del hilo para diagnosticarlo.', 'vigilancia')
            elif paso in ('timeline', 'resolve', 'colocar', 'sfx'):
                import resolve_mcp
                resolve_mcp.cerrar()
                registro.aviso('Destrabado: cerré la conexión con Resolve que no respondía; se reintenta al siguiente paso.', 'vigilancia')
        except Exception:
            registro.excepcion(origen='vigilancia · destrabar')
    def _chequeo_de_arranque(self):
        """Unos segundos después de abrir: librerías, motores, MCP, disco y memoria. Cada falla queda en el Registro (errores.log) y se avisa en pantalla."""
        def trabajo():
            import vigilancia
            vigilancia.revisar_ahora()
            return vigilancia.revisar_salud_al_arrancar()
        def fin(fallas, error):
            if error is not None or not fallas:
                return
            try:
                import ui_toast
                ui_toast.mostrar(self, tr('Hay {n} falla(s) al iniciar: {lista}. Mira el Registro para ver qué hacer.', n=len(fallas), lista=', '.join(f[0] for f in fallas[:3])),
                                 duracion_ms=10000, color='#3A1414')
            except Exception:
                pass
        _correr_en_hilo(self, trabajo, fin)
        despues(8000, self._iniciar_vigia_actualizaciones, self)        # v5.4.2: desde aquí mira cada 10 s si hay una versión nueva y avisa al momento
        despues(5000, self._mostrar_novedades_si_toca, self)            # v5.4.2: recién actualizado, sale el cuadro con TODAS las mejoras
    # -- v5.3.5: actualizaciones automáticas (actualizaciones.py) ----------------------------------------------------------
    def _iniciar_vigia_actualizaciones(self):
        """v5.4.2: un reloj que cada 10 s (actualizaciones.INTERVALO_AUTO_S) pregunta por una versión nueva. Con ETag casi no gasta red; sin internet pasa a un
        minuto y no llena el Registro. Se apaga con Ajustes > Acerca de > «Avisarme de las actualizaciones»."""
        if getattr(self, '_reloj_actualizaciones', None) is not None:
            return
        import actualizaciones
        self._act_errores = 0
        self._comprobando_act = False
        self._aviso_act_visto = None
        self._reloj_actualizaciones = ui.QTimer(self)
        self._reloj_actualizaciones.setInterval(int(actualizaciones.INTERVALO_AUTO_S * 1000))
        self._reloj_actualizaciones.timeout.connect(self._revisar_actualizaciones_auto)
        self._reloj_actualizaciones.start()
        self._revisar_actualizaciones_auto()
    def _revisar_actualizaciones_auto(self, forzar=False):
        """Un sondeo (cada 10 s desde el reloj): consulta el version.json publicado; si hay una versión más nueva aparece el chip «Nueva versión», un aviso con
        sus mejoras y el botón «Actualizar» de Ajustes. Nunca instala sola: pregunta."""
        if getattr(self, '_comprobando_act', False):
            return
        try:
            import actualizaciones
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            return
        if prefs.get('actualizaciones_auto', True) is False or not actualizaciones.configurado():
            return
        pendiente = prefs.get('actualizacion_pendiente')
        if getattr(self, '_actualizacion', None) is None and isinstance(pendiente, dict) and pendiente.get('version'):
            if actualizaciones.es_mas_nueva(pendiente['version'], APP_VERSION):
                self._actualizacion = pendiente
                self._pintar_opciones_go()
            else:                                           # ya la instalaste: se olvida
                ajustes_ui.guardar_prefs({'actualizacion_pendiente': None})
        self._comprobando_act = True
        def fin(r, error):
            self._comprobando_act = False
            if error is not None or not isinstance(r, dict):
                return
            if r.get('estado') == 'error':
                self._act_errores = getattr(self, '_act_errores', 0) + 1
                if self._act_errores == 3:                  # sin internet: se espacia y se anota UNA vez
                    registro.info('Actualizaciones: no pude consultar el canal (' + str(r.get('mensaje'))[:120] + '); sigo intentándolo cada minuto.', 'actualizaciones')
                    try:
                        self._reloj_actualizaciones.setInterval(int(actualizaciones.INTERVALO_SIN_RED_S * 1000))
                    except Exception:
                        pass
                return
            if self._act_errores:
                self._act_errores = 0
                try:
                    self._reloj_actualizaciones.setInterval(int(actualizaciones.INTERVALO_AUTO_S * 1000))
                except Exception:
                    pass
            if r.get('estado') == 'nueva':
                nueva = {k: r.get(k) for k in ('version', 'url', 'notas', 'fecha', 'archivo')}
                cambio = (getattr(self, '_actualizacion', None) or {}).get('version') != nueva['version']
                self._actualizacion = nueva
                if cambio:
                    try:
                        ajustes_ui.guardar_prefs({'actualizacion_pendiente': nueva, 'actualizacion_revisada': time.time()})
                    except Exception:
                        pass
                    self._pintar_opciones_go()
                    registro.info(f"Hay una versión nueva de CineCaptions: {r.get('version')} (la instalada es la {APP_VERSION}).", 'actualizaciones')
                self._avisar_actualizacion()
            elif r.get('estado') == 'al_dia':
                self._act_comprobada = True
                if getattr(self, '_actualizacion', None) is not None:
                    self._actualizacion = None
                    try:
                        ajustes_ui.guardar_prefs({'actualizacion_pendiente': None})
                    except Exception:
                        pass
                    self._pintar_opciones_go()
        correr_en_hilo(self, lambda: actualizaciones.comprobar_ligero(APP_VERSION, False), fin)
    def _trabajando_ahora(self):
        return getattr(self, '_go_corriendo', False) or getattr(self, '_editor', None) is not None or (getattr(self, 'worker', None) is not None and self.worker.is_alive())
    def _avisar_actualizacion(self):
        """Avisa de la versión nueva con sus mejoras, UNA vez por versión en cada sesión: «Actualizar ahora» / «Más tarde». Si GO o el editor están trabajando
        espera al siguiente sondeo (10 s) para no interrumpirlos."""
        r = getattr(self, '_actualizacion', None)
        if not r or not r.get('version') or getattr(self, '_aviso_act_visto', None) == r['version'] or getattr(self, '_dlg_act_abierto', False):
            return
        if self._trabajando_ahora():
            return
        self._aviso_act_visto = r['version']
        try:
            import ui_toast
            ui_toast.mostrar(self, tr('Hay una versión nueva de CineCaptions: {v}', v=r['version']), duracion_ms=6000)
        except Exception:
            pass
        self._dlg_act_abierto = True
        try:
            import ajustes_ui
            quiere = ajustes_ui.pedir_actualizacion(self, r)
        except Exception:
            registro.excepcion(origen='actualizar · aviso')
            quiere = False
        finally:
            self._dlg_act_abierto = False
        if quiere:
            self._ofrecer_actualizacion(r, confirmado=True)
    def _mostrar_novedades_si_toca(self):
        """Tras instalar una versión nueva (o la primera vez que se abre una instalación): el cuadro con las mejoras de lo nuevo, una sola vez."""
        try:
            import ajustes_ui
            vista = ajustes_ui.leer_prefs().get('version_vista')
        except Exception:
            return
        if vista == APP_VERSION:
            return
        if self._trabajando_ahora() or getattr(self, '_dlg_act_abierto', False):
            despues(15000, self._mostrar_novedades_si_toca, self)
            return
        try:
            ajustes_ui.guardar_prefs({'version_vista': APP_VERSION})
            self._dlg_act_abierto = True
            ajustes_ui.mostrar_novedades(self, vista)
        except Exception:
            registro.excepcion(origen='novedades · cuadro')
        finally:
            self._dlg_act_abierto = False
    def _ofrecer_actualizacion(self, r=None, confirmado=False):
        """«Actualizar»: pregunta (con las mejoras), descarga con avance, comprueba la huella y lanza el instalador (que cierra y vuelve a abrir CineCaptions)."""
        r = r or getattr(self, '_actualizacion', None)
        if not r or not r.get('version'):
            return
        if self._trabajando_ahora():
            messagebox.showinfo(tr('Actualización disponible'), tr('Termina lo que estás haciendo (GO o el editor) y vuelve a pulsar «Nueva versión»: la actualización cierra CineCaptions.'), parent=self)
            return
        archivo = r.get('archivo')
        if not archivo:
            notas = ('\n\n' + r['notas']) if r.get('notas') else ''
            if messagebox.askyesno(tr('Actualización disponible'), tr('Hay una versión nueva: {v}', v=r['version']) + notas + '\n\n' + tr('¿Abrir la descarga?'), parent=self) and r.get('url'):
                webbrowser.open(r['url'])
            return
        if not confirmado:
            import ajustes_ui
            if not ajustes_ui.pedir_actualizacion(self, r):
                return
        self._descargar_actualizacion(r)
    def _descargar_actualizacion(self, r):
        import actualizaciones
        import editor_ui
        if getattr(self, '_descargando_actualizacion', False):          # v5.4.41: un segundo clic (o dos avisos a la vez) no arranca otra descarga encima de la primera
            return
        archivo = r['archivo']
        try:
            dlg = Dialogo(self, tr('Actualizando CineCaptions'), 500, 430, redimensionable=False)
            capa = _capa_dialogo(dlg, (0, 0, 0, 0), 0)
            panel = editor_ui.PanelAsistencia(tr('Actualizando CineCaptions'), tr('Listo'), tr('Descargando…'),
                                              [tr('Descargar la versión nueva'), tr('Comprobar que es auténtica'), tr('Instalarla')], f"v{r['version']}",
                                              tr('CineCaptions se cierra y se vuelve a abrir solo'))
            capa.addWidget(panel, 1)
            dlg.show()
        except Exception:
            registro.excepcion(origen='actualizar · ventana')
            return
        est = {'texto': '', 'fase': 0, 'ruta': None, 'error': None, 'cancelado': False}
        dlg.finished.connect(lambda _r: est.__setitem__('cancelado', True))
        def progreso(h, t):
            est['texto'] = tr('{h} de {t} MB', h=f'{h / 1048576:.0f}', t=f'{(t or h) / 1048576:.0f}')
            if t and h >= t:
                est['fase'] = 1
        def trabajo():
            try:
                est['ruta'] = actualizaciones.descargar(archivo, APP_VERSION, progreso=progreso, cancelado=lambda: est['cancelado'])
            except BaseException as e:
                est['error'] = str(e) or type(e).__name__
        self._descargando_actualizacion = True
        def trabajo_y_liberar():
            try:
                trabajo()
            finally:
                self._descargando_actualizacion = False
        hilo = threading.Thread(target=trabajo_y_liberar, daemon=True, name='descarga-actualizacion')
        hilo.start()
        def revisar():
            if hilo.is_alive():
                if vivo(dlg):
                    panel.poner_fase(est['fase'])
                    if est['texto']:
                        panel.poner_detalle(est['texto'])
                    despues(150, revisar, self)
                return
            if est['cancelado'] and not est['ruta']:
                return
            if est['error'] or not est['ruta']:
                try:
                    dlg.cerrar()
                except Exception:
                    pass
                registro.error('No se pudo actualizar: ' + str(est['error']), 'actualizaciones', detalle=str(archivo.get('url')))
                if messagebox.askyesno(tr('No se pudo actualizar'), tr('La descarga o la comprobación falló: {e}', e=str(est['error'])[:200]) + '\n\n' +
                                       tr('Tu versión sigue como estaba. ¿Abrir la descarga en el navegador?'), parent=self) and r.get('url'):
                    webbrowser.open(r['url'])
                return
            panel.poner_fase(2)
            panel.poner_detalle(tr('Lanzando el instalador…'))
            ok = actualizaciones.instalar(est['ruta'])
            registro.info(f"Actualización a {r['version']}: instalador lanzado ({est['ruta']})" if ok else 'Actualización: no pude lanzar el instalador', 'actualizaciones')
            if not ok:
                try:
                    dlg.cerrar()
                except Exception:
                    pass
                messagebox.showerror(tr('No se pudo actualizar'), tr('No pude abrir el instalador descargado: {r}', r=str(est['ruta'])), parent=self)
                return
            panel.terminar(tr('Instalando…'))
            if sys.platform.startswith('win'):
                despues(1500, lambda: QApplication.instance().quit(), self)       # el instalador ya está en marcha: CineCaptions se cierra y él lo vuelve a abrir
            else:
                despues(1200, lambda: dlg.cerrar(), self)
                messagebox.showinfo(tr('Actualización descargada'), tr('Se abrió el disco de CineCaptions {v}: abre «Instalar_CineCaptions.pkg» para terminar.', v=r['version']), parent=self)
        despues(150, revisar, self)
    def _sincronizar_sfx(self):
        """Auditoría v5.11: «Efectos» de Inicio (go_sfx) manda sobre la casilla vieja (sfx_var), que es la que miran los puntos de sonido del editor."""
        try:
            self.sfx_var.set(self._go_sfx())
        except Exception:
            pass
    def _ciclar_formato_go(self):
        opciones = list(self.FORMATOS_VIDEO.keys())
        actual = self.formato_var.get()
        self.formato_var.set(opciones[(opciones.index(actual) + 1) % len(opciones)] if actual in opciones else opciones[0])
        self._guardar_preferencias()
        self._pintar_opciones_go()
    GO_PACK_DEFECTO = 'Referencia'
    def _go_pack_pref(self):
        """Lo que el usuario eligió en el chip «Estilo» de Inicio: un pack, 'auto' (el diseño de 3 líneas de siempre) o '' (no ha elegido)."""
        try:
            import ajustes_ui
            v = str(ajustes_ui.leer_prefs().get('go_pack') or '')
        except Exception:
            return ''
        if v and plantillas.SOLO_TEMAS and not plantillas.pack_permitido(v):       # v5.4.19: lo guardado de antes que ya no se enseña (otro pack del programa o «auto») cuenta como «sin elegir»
            return ''
        return v
    def _aplicar_recomendacion(self, pack):
        """v5.5: al ELEGIR un estilo con recomendación (VIRAL, Kinetic, Referencia) el sonido y la página Efectos quedan ya configurados como le van a ese estilo
        (recomendaciones.py); un aviso lo dice y se puede cambiar después en Sonido y en Efectos."""
        try:
            import recomendaciones
            texto = recomendaciones.aplicar(pack)
            if not texto:
                return
            w = getattr(self, '_efectos_widget', None)
            if w is not None:
                w.refrescar()
            self._pintar_opciones_go()
            import ui_toast
            ui_toast.mostrar(self, tr('Recomendado para {t}. Puedes cambiarlo en Sonido y en Efectos.', t=texto), duracion_ms=8000)
        except Exception:
            registro.excepcion(origen='recomendación por estilo')

    def _poner_go_pack(self, valor):
        anterior = None
        try:
            import ajustes_ui
            anterior = str(ajustes_ui.leer_prefs().get('go_pack') or '')
            ajustes_ui.guardar_prefs({'go_pack': valor})
        except Exception:
            pass
        if anterior is not None and valor != anterior:
            self._aplicar_recomendacion(valor)
        # auditoría v5.11: lo que se elige en el chip es también el pack de Estilos / Creativo / Generar (antes quedaban dos dueños)
        nuevo = self._plantilla_un_clic()
        if nuevo != getattr(self, 'plantilla_sel', None):
            self.plantilla_sel = nuevo
            try:
                self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
                self._refrescar_vista_estilo()
                self._refrescar_receta()
                pv = getattr(self, '_plantillas_ventana', None)
                if pv is not None and pv.existe():
                    pv.seleccion.set(nuevo)
                    pv._recargar(nuevo)
            except Exception:
                registro.excepcion(origen='chip Estilo · sincronizar')
            self._guardar_preferencias()
        self._pintar_opciones_go()
    def _sincronizar_go_pack(self, valor):
        """Estilos → GO: el pack elegido en Estilos pasa a ser el de GO ('auto' = el diseño de 3 líneas)."""
        if valor in ('auto', 'dinamico', 'Base títulos dinámicos'):
            guardar = 'auto'
        elif valor == 'media_pool' or not valor:
            return
        else:
            guardar = valor
        try:
            import ajustes_ui
            if str(ajustes_ui.leer_prefs().get('go_pack') or '') != guardar:
                ajustes_ui.guardar_prefs({'go_pack': guardar})
                self._aplicar_recomendacion(guardar)
        except Exception:
            pass
    def _plantilla_un_clic(self):
        """El pack que usa GO. v5.10: por defecto el estilo «Referencia» (los captions palabra a palabra: línea fina y negrita + palabra grande),
        porque con el diseño de 3 líneas GO dejaba «todo igual» (pedido: «arrastro mi video y no aplica el estilo de la referencia»).
        Manda lo que se elija en el chip «Estilo» de Inicio ('auto' = el diseño de 3 líneas de antes); si no se eligió nada, el pack que ya uses
        (si es de verdad un pack) y, si no, Referencia. Los packs sin formato vertical (Referencia lo es) no valen para un video horizontal."""
        actual = getattr(self, 'plantilla_sel', '') or ''
        formato = self._formato_para_temas()
        try:
            nombres = [p.nombre for p in plantillas.listar_packs() if plantillas.sirve_en_go(p)]
        except Exception:
            nombres = []

        def sirve(n):
            try:
                p = plantillas.buscar_pack(n)
                return plantillas.sirve_en_go(p, formato)
            except Exception:
                return False
        base = 'Base títulos dinámicos' if 'Base títulos dinámicos' in nombres else 'dinamico'
        elegido = self._go_pack_pref()
        if elegido == 'auto':
            return base
        if elegido and elegido in nombres and sirve(elegido):
            return elegido
        if not elegido:
            if actual in nombres and actual not in (base, 'dinamico') and sirve(actual) and plantillas.pack_permitido(actual):
                return actual
            if self.GO_PACK_DEFECTO in nombres and sirve(self.GO_PACK_DEFECTO):
                return self.GO_PACK_DEFECTO
        return actual if actual in nombres and sirve(actual) and plantillas.pack_permitido(actual) else base
    def _go(self):
        if getattr(self, '_go_corriendo', False) or self._editor_abierto():
            return
        if getattr(self, '_caducada', False):
            messagebox.showwarning(tr('Versión de prueba'), MENSAJE_CADUCADA, parent=self)
            return
        if not self._licencia_lista():
            # v5.2.1: la licencia manda igual que en «Generar subtítulos» (licencia.py)
            self.go_panel.reposo(tr('Activa tu licencia para usar GO'), listo=True)
            return
        if not self._entradas_activas:
            return
        self._go_corriendo = True
        self._un_clic = True
        self._pausa_go = False                # v5.4.8: «Pausar» / «Cancelar» (se miran en los puntos de control del trabajo)
        self._cancelar_go = False
        self._go_termino = False
        self._idioma_detectado_go = None
        self.go_panel.al_pausar = self._go_pausar
        self.go_panel.al_cancelar = self._go_cancelar
        self._go_paso_actual = 'timeline'
        self._vigilar_tarea('go', 'timeline')          # v5.11: desde el primer paso (Resolve apagado / sin responder) hay alguien mirando
        self._resumen_ia = None
        self._ultimos_bloques = None
        self.go_panel.empezar()
        self.go_panel.paso('timeline')
        self._go_decir_edicion()
        self._precargar_motores()          # v5.3: la voz y la IA de texto se cargan y se calientan mientras Resolve da el audio
        archivo = getattr(self, '_go_archivo', None)
        if archivo:
            self._ultimo_go_archivo = archivo
            self._marcar_go_en_curso(archivo)
        import resolve_mcp
        hay_mcp = resolve_mcp.ruta_exe() is not None
        self._go_tl_listo = None
        self._go_tl_error = None
        try:                                              # v5.4.29: sin el chip «Idioma» en Inicio, GO SIEMPRE detecta el idioma al transcribir (un idioma elegido antes ya no se queda escondido)
            if 'auto' in NOMBRE_POR_CODIGO and LANG_CODE_BY_NAME.get(self.lang_var.get()) != 'auto':
                self.lang_var.set(NOMBRE_POR_CODIGO['auto'])
        except Exception:
            pass
        try:                                              # v5.4.27: una línea con el contexto de ESTE GO, para entender cualquier error que venga después
            import efectos_visuales as _fxl
            import plantillas as _pl
            registro.info('GO empieza · %s · tema «%s» · Resolve %s · efectos %s · emojis %s' % (
                ('video «%s»' % Path(str(archivo)).name) if archivo else 'audio del timeline de Resolve', _pl.nombre_visible(self._plantilla_un_clic()),
                'Studio (MCP)' if hay_mcp else 'Free (Puente)', 'sí' if _fxl.activado() else 'no', 'sí' if self._go_emojis() else 'no'), 'GO')
        except Exception:
            pass
        if archivo and Path(archivo).exists():
            self._go_archivo = None
            self.video_var.set(archivo)
            # v5.10: el video soltado manda: su orientación decide el formato (y con él el pack de GO) y Resolve le arma un timeline nuevo
            medio = resolve_mcp.medir_medio(archivo)
            self._ancho_timeline, self._alto_timeline, self._fps_timeline = medio['tl_ancho'], medio['tl_alto'], medio['tl_fps']
            modo_sis = (getattr(self, '_estado_sistema', {}) or {}).get('modo')
            if not modo_sis:                         # soltado en los primeros segundos: el estado del sistema aún no llegó; sin MCP es Free (Puente), no «uso tu archivo»
                import resolve_bridge as _rb
                modo_sis = _rb.modo_actual(pasivo=True)
            libre_puente = (not hay_mcp) and modo_sis in ('puente', 'manual')       # DaVinci Resolve Free: se habla por el Puente
            self.go_panel.paso('timeline', 'saltado', tr('tu video, en un timeline nuevo') if (hay_mcp or libre_puente) else tr('uso tu archivo'))
            if hay_mcp:
                # v5.2: Resolve se va abriendo mientras se transcribe (para colocar al final); v5.10: y se le arma el timeline con el video
                self._go_tl_listo = threading.Event()
                threading.Thread(target=self._go_timeline_del_video, args=(archivo, medio), daemon=True, name='abrir-resolve').start()
            elif libre_puente:
                # v5.4.16: lo mismo en Resolve Free, por el Puente (CineCaptions_ArmarVideo.lua): proyecto nuevo + timeline con el video; los captions caen ahí, no en el timeline que hubiera abierto
                self._go_tl_listo = threading.Event()
                threading.Thread(target=self._go_timeline_del_video_libre, args=(archivo, medio), daemon=True, name='armar-video-free').start()
            self._go_generar()
            return
        self.go_panel.linea.configure(text=tr('Pidiéndole a Resolve el audio del timeline…'))
        def trabajo():
            import resolve_bridge
            if hay_mcp:
                # v5.10: una vista real de los estilos en curso crea un timeline TEMPORAL y lo deja como el actual; GO le pedía el audio a ese
                # (vacío) y fallaba con «Whisper no devolvió palabras». Se espera a que termine y se repara antes de tocar nada.
                self._esperar_vistas_reales()
                # v5.2 (pedido: «debe abrir automáticamente Resolve si está
                # cerrado y abrir el proyecto más reciente; control total por
                # MCP»): abre Resolve, el proyecto más reciente, su timeline y Edit
                prep = resolve_mcp.preparar_resolve(abrir=True, pagina='edit',
                                                    al_estado=lambda t: self.msg_queue.put(('status', t)))
                try:
                    import vistas_reales
                    if prep.get('ok') and vistas_reales._es_temporal_de_vista(prep.get('timeline')):
                        vistas_reales.reparar_pendiente()
                        prep = resolve_mcp.preparar_resolve(abrir=True, pagina='edit', al_estado=lambda t: self.msg_queue.put(('status', t)))
                except Exception:
                    registro.excepcion(origen='GO · reparar vista')
                if not prep.get('ok'):
                    return ('sin_resolve', prep.get('motivo') or '')
                self.msg_queue.put(('status', tr('Resolve listo · proyecto «{p}» · timeline «{t}». Exportando el audio…',
                                                 p=prep.get('proyecto') or '—', t=prep.get('timeline') or '—')))
            elif resolve_bridge.modo_actual() == 'manual':
                if sys.platform != 'darwin' and not sys.platform.startswith('win'):
                    return ('sin_resolve', '')
                self.msg_queue.put(('status', tr('Lanzando el Puente en Resolve…')))
                if not resolve_bridge.lanzar_puente_auto():         # Resolve Free: Mac por el menu del Puente; Windows por la consola F6 de Resolve
                    return ('sin_resolve', '')
            ok, err = resolve_bridge.ejecutar('detectar', timeout=600)
            return ('ok' if ok else 'error', err)
        def fin(r, error):
            estado, err = r if r else ('error', str(error))
            if estado == 'ok':
                try:
                    self._detectar_desde_resolve_archivo(silencioso=True)
                except Exception:
                    pass
            ruta = self.video_var.get().strip().strip('"')
            if estado == 'ok' and ruta and Path(ruta).exists():
                self.go_panel.paso('timeline', 'hecho', Path(ruta).stem[:26])
                self._go_generar()
            elif ruta and Path(ruta).exists():
                self.go_panel.paso('timeline', 'saltado', tr('uso tu archivo'))
                self._go_generar()
            else:
                self._go_fallo('timeline', (tr('Resolve no entregó el audio del timeline (código {c}).', c=str(err).strip()) if str(err or '').strip().isdigit() else err) or tr('Abre DaVinci Resolve con tu timeline, o suelta un vídeo en la ventana, y pulsa GO otra vez.'))
        _correr_en_hilo(self, trabajo, fin)
    def _go_decir_edicion(self):
        """v5.5: al empezar GO la línea dice con qué Resolve va a trabajar (Studio o Free) y por qué camino; el Registro lo anota. Después sigue el proceso."""
        try:
            import colocacion
            det = colocacion.detectar_resolve(getattr(self, '_estado_sistema', None))
            self._go_resolve = det
            if det.get('texto'):
                self.go_panel.linea.configure(text=det['texto'])
                registro.info(det['texto'], 'GO · Resolve')
            if det.get('camino') == 'sin_puente' and not det.get('listo'):
                registro.aviso(tr('Resolve Free necesita el Puente para colocar los subtítulos'), 'GO · Resolve', detalle=det.get('ayuda') or '')
        except Exception:
            self._go_resolve = None
    def _sin_palabras_mensaje(self):
        """Por qué no hay palabras. Caso típico: el archivo del video ya no está donde estaba (lo moviste o le cambiaste el nombre): Resolve lo marca
        «Archivo no encontrado», su audio sale en silencio y no es que el video no tenga voz."""
        try:
            import resolve_bridge
            ruta = str((resolve_bridge.video_detectado() or {}).get('clip_principal') or '')
            if ruta and not Path(ruta).exists():
                return tr('El archivo del video ya no está donde estaba ({r}).\nResolve lo muestra como «Archivo no encontrado» y por eso no hay audio: ¿lo moviste o le cambiaste el nombre? Devuélvelo a su sitio (o suéltalo otra vez en CineCaptions) y pulsa GO.', r=ruta)
        except Exception:
            pass
        return tr('Whisper no devolvio palabras.\nRevisa que el video tenga audio con voz.')
    def _abortar_si_fallo_el_timeline(self):
        """GO con un video soltado: si Resolve no pudo armar el proyecto/timeline con ese video, GO se detiene con un mensaje claro. NUNCA se colocan los
        captions en el timeline que hubiera abierto (otro video, sin su sonido: así se perdía el audio y se ensuciaba el proyecto del usuario)."""
        err = getattr(self, '_go_tl_error', None)
        if err:
            raise SystemExit(tr('No pude armar el proyecto con tu video en Resolve ({m}).\nNo toqué ningún otro timeline. Abre Resolve y vuelve a soltar el video.', m=err))
    GO_PROYECTO_DEFECTO = 'CineCaptions'
    def _go_proyecto(self):
        """El proyecto de Resolve donde GO arma el timeline de un video soltado: 'CineCaptions' (por defecto) o '' = el que esté abierto (chip «Proyecto»)."""
        try:
            import ajustes_ui
            v = str(ajustes_ui.leer_prefs().get('go_proyecto') or self.GO_PROYECTO_DEFECTO)
        except Exception:
            v = self.GO_PROYECTO_DEFECTO
        return '' if v == 'actual' else v
    def _alternar_proyecto_go(self):
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'go_proyecto': 'actual' if self._go_proyecto() else self.GO_PROYECTO_DEFECTO})
        except Exception:
            pass
        self._pintar_opciones_go()
    def _esperar_vistas_reales(self, tope_s=150):
        """Con una vista real de los estilos en curso (timeline temporal en Resolve) GO no toca Resolve: espera a que acabe (en un hilo, nunca en la UI)."""
        try:
            import vistas_reales
            t0 = time.time()
            while vistas_reales._ACTIVOS[0] > 0 and time.time() - t0 < tope_s:
                self.msg_queue.put(('status', tr('Esperando a que Resolve termine la vista real de los estilos…')))
                time.sleep(1.0)
        except Exception:
            pass
    def _go_timeline_del_video(self, archivo, medio):
        """Hilo de GO con un video soltado: abre Resolve si hace falta y le arma un timeline NUEVO con ese video (orientación y fps del video),
        que queda como el actual: ahí caen los captions. Si algo falla, GO se detiene (`_abortar_si_fallo_el_timeline`) y no toca ningún otro timeline."""
        import resolve_mcp
        try:
            self._esperar_vistas_reales()
            nombre_proyecto = self._go_proyecto()
            al_estado = lambda t: self.msg_queue.put(('status', t))
            if nombre_proyecto:
                # v5.10: el video soltado vive en el proyecto «CineCaptions» (se abre Resolve, se abre o se crea el proyecto y se arma el timeline)
                prep = resolve_mcp.preparar_proyecto(nombre_proyecto, abrir=True, al_estado=al_estado)
                listo = bool(prep.get('ok'))
            else:
                # «Proyecto: el abierto»: se usa el que tenga Resolve (aunque esté vacío: ahí se arma el timeline)
                prep = resolve_mcp.preparar_resolve(abrir=True, pagina=None, al_estado=al_estado)
                listo = bool(prep.get('proyecto'))
            if not listo:
                self._go_tl_error = prep.get('motivo') or tr('Resolve no está listo')
                registro.aviso(tr('No pude preparar Resolve para tu video ({m}): GO se detiene (no se toca ningún otro timeline).', m=self._go_tl_error),
                               'GO · timeline del video')
                return
            self.msg_queue.put(('status', tr('Armando en Resolve un timeline con tu video…')))
            try:
                import efectos_visuales as _fx
                con_broll = bool(_fx.activado() and _fx.opciones_guardadas().get('fx_broll') and _fx.broll_clave(_fx.opciones_guardadas()))
            except Exception:
                con_broll = False
            r = resolve_mcp.crear_timeline_con_video(archivo, ancho=medio['tl_ancho'], alto=medio['tl_alto'], fps=medio['tl_fps'], pista_broll=con_broll)
            if r.get('error'):
                self._go_tl_error = r['error']
                registro.aviso(tr('Resolve no armó el timeline con tu video ({m}): GO se detiene (no se toca ningún otro timeline).', m=r['error']),
                               'GO · timeline del video')
                return
            self._go_tl_info = r
            if r.get('clip_con_audio'):
                if r.get('audio_repuesto'):
                    registro.aviso(tr('Resolve metió solo la imagen de tu video: añadí su audio original a la pista A1.'), 'GO · timeline del video')
                elif not r.get('audio_a1'):
                    registro.aviso(tr('Tu video tiene audio pero no pude ponerlo en la pista A1 del timeline. Arrástralo tú desde el Media Pool.'), 'GO · timeline del video')
            self._ancho_timeline = r.get('ancho') or medio['tl_ancho']
            self._alto_timeline = r.get('alto') or medio['tl_alto']
            registro.info(tr('Timeline «{t}» armado con tu video en el proyecto «{p}» ({w}×{h}, {f:g} fps).', t=r.get('timeline'), p=r.get('proyecto') or '—',
                             w=self._ancho_timeline, h=self._alto_timeline, f=r.get('fps') or medio['tl_fps']), 'proceso')
        except Exception as e:
            self._go_tl_error = f'{type(e).__name__}: {e}'
            registro.excepcion(origen='GO · timeline del video')
        finally:
            ev = getattr(self, '_go_tl_listo', None)
            if ev is not None:
                ev.set()
    def _go_timeline_del_video_libre(self, archivo, medio):
        """Hilo de GO con un video soltado en DaVinci Resolve FREE (sin MCP): le pide al Puente que cree el proyecto «CineCaptions» y arme el timeline con ese video
        (CineCaptions_ArmarVideo.lua, la gemela de lo que en Studio hace el MCP). Si algo falla, GO se detiene (`_abortar_si_fallo_el_timeline`)."""
        import resolve_bridge
        self._go_tl_args = (archivo, medio)                     # (para volver a armar el timeline si Resolve se cuelga más adelante)
        try:
            self._esperar_vistas_reales()
            al_estado = lambda t: self.msg_queue.put(('status', t))
            try:                                                   # v5.4.41: Resolve se revisa ANTES de empezar (colgado, sin ventana, o Puente que latía pero no contesta): se arregla YA, sin esperar minutos
                import colocacion
                colocacion.preparar_resolve_para_go(decir=al_estado)
            except Exception:
                registro.excepcion(origen='GO · revisar Resolve antes de empezar')
            if resolve_bridge.modo_actual() == 'manual':
                al_estado(tr('Lanzando el Puente en Resolve…'))
                if not resolve_bridge.lanzar_puente_auto():
                    self._go_tl_error = tr('No pude lanzar el Puente en Resolve Free: abre Resolve con un proyecto (la pantalla de proyectos no vale) y repite.')
                    registro.aviso(self._go_tl_error, 'GO · timeline del video')
                    return
            try:
                import efectos_visuales as _fx
                con_broll = bool(_fx.activado() and _fx.opciones_guardadas().get('fx_broll') and _fx.broll_clave(_fx.opciones_guardadas()))
            except Exception:
                con_broll = False
            orden = {'ruta': str(archivo), 'ancho': int(medio['tl_ancho']), 'alto': int(medio['tl_alto']), 'fps': float(medio['tl_fps']), 'pista_broll': bool(con_broll),
                     'proyecto': self._go_proyecto(), 'nombre': ('CineCaptions · ' + Path(str(archivo)).stem)[:60]}
            import colocacion
            if getattr(colocacion, 'PROYECTO_INICIAL', None):                # el proyecto vacío que la app creó para pasar el Organizador de proyectos: ArmarVideo lo borra
                orden['descartar'] = str(colocacion.PROYECTO_INICIAL)
            import archivos_seguros
            import sidecar_lua
            ruta_orden = st.SHARED_FOLDER / 'armar_video.json'
            archivos_seguros.escribir_json(ruta_orden, orden)
            sidecar_lua.escribir_sidecar(ruta_orden, orden)
            al_estado(tr('Armando en Resolve un timeline con tu video…'))
            desde = time.time()
            ok, err = resolve_bridge.ejecutar('armar_video', timeout=240)
            for _reintento in range(2):                              # v5.4.40: Resolve colgado o cerrado a mitad → se cierra, se reabre y se arma otra vez (hasta 2 veces)
                if ok or not resolve_bridge.es_resolve_atascado(err):
                    break
                if not colocacion.recuperar_resolve(err, decir=al_estado):
                    break
                orden.pop('descartar', None)                         # (el proyecto vacío de arranque murió con Resolve)
                archivos_seguros.escribir_json(ruta_orden, orden)
                sidecar_lua.escribir_sidecar(ruta_orden, orden)
                al_estado(tr('Armando en Resolve un timeline con tu video…'))
                desde = time.time()
                ok, err = resolve_bridge.ejecutar('armar_video', timeout=240)
            colocacion.PROYECTO_INICIAL = None                       # (ya se uso: ArmarVideo borró ese proyecto vacío)
            rep = next((r for r in reversed(resolve_bridge.reportes_del_registro()) if r.get('script') == 'CineCaptions_ArmarVideo' and (r.get('cuando') or 0) >= desde - 2), None)
            info = (rep or {}).get('armado')
            if not ok or not isinstance(info, dict):
                self._go_tl_error = str(err or (rep or {}).get('mensaje') or tr('Resolve no armó el timeline'))[:300]
                registro.aviso(tr('Resolve no armó el timeline con tu video ({m}): GO se detiene (no se toca ningún otro timeline).', m=self._go_tl_error), 'GO · timeline del video')
                return
            self._go_tl_info = info
            if info.get('clip_con_audio'):
                if info.get('audio_repuesto'):
                    registro.aviso(tr('Resolve metió solo la imagen de tu video: añadí su audio original a la pista A1.'), 'GO · timeline del video')
                elif not info.get('audio_a1'):
                    registro.aviso(tr('Tu video tiene audio pero no pude ponerlo en la pista A1 del timeline. Arrástralo tú desde el Media Pool.'), 'GO · timeline del video')
            self._ancho_timeline = info.get('ancho') or medio['tl_ancho']
            self._alto_timeline = info.get('alto') or medio['tl_alto']
            try:                                     # lo que los efectos visuales necesitan saber del timeline (en Studio lo pregunta el MCP)
                import efectos_visuales
                efectos_visuales.INFO_LIBRE = {'timeline': info.get('timeline'), 'proyecto': info.get('proyecto'), 'ancho': int(info['ancho']), 'alto': int(info['alto']),
                                               'fps': float(info['fps']), 'inicio': int(info['inicio']), 'v1': info.get('v1') if isinstance(info.get('v1'), list) else []}
            except Exception:
                pass
            nombre_tl = info.get('timeline')
            if '?' in str(nombre_tl or '') and '?' not in orden['nombre']:       # el registro de Resolve cambia lo que no es ASCII (el «·» del nombre) por «?»
                nombre_tl = orden['nombre']
            registro.info(tr('Timeline «{t}» armado con tu video en el proyecto «{p}» ({w}×{h}, {f:g} fps).', t=nombre_tl, p=info.get('proyecto') or '—',
                             w=self._ancho_timeline, h=self._alto_timeline, f=info.get('fps') or medio['tl_fps']), 'proceso')
        except Exception as e:
            self._go_tl_error = f'{type(e).__name__}: {e}'
            registro.excepcion(origen='GO · timeline del video (Free)')
        finally:
            ev = getattr(self, '_go_tl_listo', None)
            if ev is not None:
                ev.set()
    def _go_rearmar_en_resolve(self, motivo):
        """v5.4.40: Resolve (Free) se colgó o se cerró SOLO a mitad de colocar → se cierra del todo, se reabre, se relanza el Puente y se vuelve a armar el timeline con el video.
        True si el timeline quedó armado otra vez (entonces el GO repite el paso que falló). Corre en el hilo de colocar, nunca en la interfaz."""
        try:
            import colocacion
            args = getattr(self, '_go_tl_args', None)
            if not args:
                return False
            if not colocacion.recuperar_resolve(motivo, decir=lambda t: self.msg_queue.put(('status', t))):
                return False
            self._go_tl_error = None
            self._go_timeline_del_video_libre(*args)
            return not getattr(self, '_go_tl_error', None)
        except Exception:
            registro.excepcion(origen='GO · rearmar en Resolve')
            return False
    def _precargar_al_abrir(self):
        """v5.4.40: con la GPU holgada (modo «residente» o «solapado»: ≥ 14,5 GB) el motor de VOZ (no la IA de texto) se carga y se calienta nada más abrir el programa, en un hilo, para que el primer GO no
        gaste ~14 s en cargarlo (medido: «Modelo listo en 12,4 s» + calentamiento 1,7 s). Con la GPU justa (modo «secuencial») no: dejaría a Resolve sin memoria de vídeo. Se apaga con
        la preferencia `precargar_al_abrir` = False. Nunca bloquea ni lanza."""
        try:
            import ajustes_ui
            import motor_voz
            if ajustes_ui.leer_prefs().get('precargar_al_abrir', True) is False:
                return
            if getattr(self, '_go_corriendo', False) or motor_voz.modo_gpu() not in ('residente', 'solapado'):
                return
            codigo = LANG_CODE_BY_NAME.get(self.lang_var.get(), 'es')
            def trabajo():
                try:                                           # SOLO la voz (~6 GB): la IA de texto (~9,5 GB) se carga al pulsar GO, no con Resolve abierto y la GPU compartida
                    if motor_voz.motor_para(codigo) == 'qwen3':
                        motor_voz.precargar()
                    else:
                        st.precargar_whisper(MODEL_SIZE)
                except Exception:
                    pass
            threading.Thread(target=trabajo, daemon=True, name='precarga-voz-al-abrir').start()
        except Exception:
            pass
    def _precargar_motores(self):
        """v5.3: arranca EN SEGUNDO PLANO el motor de voz y la IA de texto (carga + calentamiento). Cargar el motor de voz
        cuesta ~11 s de imports + ~8 s de modelo y su primera pasada ~20 s; ya cargado, 24 s de audio se transcriben en ~5 s.
        Se llama al pulsar GO u «Obtener»: Resolve tarda unos segundos en dar el audio y, mientras, los motores se preparan.
        Nunca bloquea ni lanza."""
        codigo = LANG_CODE_BY_NAME.get(self.lang_var.get(), 'es')
        def trabajo():
            try:
                import motor_voz
                if motor_voz.motor_para(codigo) == 'qwen3':
                    motor_voz.precargar()
                else:
                    st.precargar_whisper(MODEL_SIZE)
                if motor_voz.modo_gpu() in ('residente', 'solapado'):
                    import ia_texto
                    ia_texto.precargar()
            except Exception:
                pass
        threading.Thread(target=trabajo, daemon=True, name='precarga-motores').start()
    def _go_generar(self):
        """Pone la receta de GO (dinamico 3 lineas + pack + efectos) y arranca
        el mismo _run_pipeline de «Generar subtítulos», sin preguntas."""
        self._elegir_mosaico('dinamico')
        self.plantilla_sel = self._plantilla_un_clic()
        try:
            self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        except Exception:
            pass
        self.sfx_var.set(self._go_sfx())
        self.translate_var.set(False)
        media_path = Path(self.video_var.get().strip().strip('"')).expanduser()
        source_lang = LANG_CODE_BY_NAME.get(self.lang_var.get(), 'es')
        self._reusando = False
        self._generado_para = None
        self._set_inputs_enabled(False)
        self._guardar_preferencias()
        self._arrancar_reloj()
        try:
            self.go_panel.estimador.poner_efectos(self._go_visuales())
        except Exception:
            pass
        self._go_paso_actual = 'voz'
        self.go_panel.paso('voz')
        # v5.10: «Efectos: no» de Inicio se respeta (antes GO ponía los sonidos aunque el chip dijera «no»)
        self.worker = threading.Thread(target=self._run_pipeline, args=(media_path.resolve(), source_lang, False, 0, 0, 'dinamico', bool(self.sfx_var.get()), None, None), daemon=True)
        self.worker.start()
    # -- v5.4.8: pausar, cancelar y reanudar GO ---------------------------------------------------------------------------------------------------------------
    def _go_pausar(self):
        self._pausa_go = not getattr(self, '_pausa_go', False)
        self.go_panel.poner_pausa(self._pausa_go)
        self.status_var.set(tr('GO en pausa: pulsa «Reanudar» para seguir.') if self._pausa_go else tr('Sigo con GO…'))
    def _go_cancelar(self):
        if getattr(self, '_cancelar_go', False):
            return
        if not messagebox.askyesno(tr('Cancelar GO'), tr('¿Cancelo GO? Lo ya hecho se conserva (la voz transcrita no se repite) y puedes reanudarlo.'), parent=self):
            return
        self._cancelar_go = True
        self._pausa_go = False
        try:
            import motor_voz
            motor_voz.abortar()                       # la voz de Qwen (otro proceso) se corta ya; Whisper para al siguiente avance
        except Exception:
            pass
        self.go_panel.linea.configure(text=tr('Cancelando…'))
    def _punto_control_go(self):
        """Lo llama el HILO de trabajo en cada avance: si GO está en pausa espera; si se canceló, termina (SystemExit llega al manejo de errores de siempre)."""
        if not getattr(self, '_un_clic', False):
            return
        while getattr(self, '_pausa_go', False) and not getattr(self, '_cancelar_go', False):
            time.sleep(0.2)
        if getattr(self, '_cancelar_go', False):
            raise SystemExit(tr('GO cancelado.'))
    def _go_cancelado(self):
        """El trabajo paró por la cancelación del usuario: el panel lo dice sin alarma y ofrece «Reanudar»."""
        registro.info('GO cancelado por el usuario', 'GO')
        self._fin_tarea(False, tr('GO cancelado'))
        self._borrar_go_en_curso()
        self._go_corriendo = False
        self._un_clic = False
        self._cancelar_go = False
        self._pausa_go = False
        self._set_inputs_enabled(True)
        if getattr(self, '_ultimo_go_archivo', None):
            self._go_archivo = self._ultimo_go_archivo           # «Reanudar» (el orbe) vuelve a lanzar GO con ese mismo video
        self.go_panel.cancelado(tr('Lo ya hecho se conserva: al reanudar, la voz no se transcribe otra vez.'))
    def _ruta_go_en_curso(self):
        return Path.home() / 'DaVinciSubtitles' / 'go_en_curso.json'
    def _marcar_go_en_curso(self, archivo):
        """Si el programa se cierra a mitad de GO, al abrirlo se ofrece reanudarlo (go_en_curso.json)."""
        try:
            archivos_seguros.escribir_json(self._ruta_go_en_curso(), {'archivo': str(archivo), 'cuando': time.time()})
        except Exception:
            pass
    def _borrar_go_en_curso(self):
        try:
            self._ruta_go_en_curso().unlink(missing_ok=True)
        except Exception:
            pass
    def _ofrecer_reanudar_go(self):
        """Al abrir: un GO que quedó a medias (el programa se cerró o se apagó el equipo) se ofrece reanudar en el propio botón."""
        try:
            f = self._ruta_go_en_curso()
            if getattr(self, '_go_corriendo', False) or not f.is_file():
                return                                   # con un GO en marcha la marca es suya: no se toca
            d = json.loads(f.read_text(encoding='utf-8'))
            f.unlink(missing_ok=True)
            ruta = d.get('archivo')
            if ruta and Path(ruta).exists() and time.time() - float(d.get('cuando') or 0) < 3 * 86400 and not getattr(self, '_go_corriendo', False):
                self._go_archivo = ruta
                self._ultimo_go_archivo = ruta
                self.go_panel.reposo(tr('Quedó a medias el GO de «{n}»: pulsa GO para reanudarlo.', n=Path(ruta).name), forzar=True)
        except Exception:
            pass
    def _go_fallo(self, clave, mensaje):
        self._borrar_go_en_curso()
        registro.error(str(mensaje).splitlines()[0][:200] if mensaje else tr('GO no pudo terminar'), f'GO · {clave}', detalle=str(mensaje or ''))
        self._fin_tarea(False, str(mensaje).splitlines()[0][:160] if mensaje else '')
        self.go_panel.paso_fallido = clave
        self.go_panel.paso(clave, 'error')
        self.go_panel.terminar(False, str(mensaje).splitlines()[0][:160] if mensaje else '')
        try:
            import avisos_sistema
            avisos_sistema.avisar(self, tr('GO no pudo terminar'), (str(mensaje).splitlines()[0] if mensaje else tr('Abre CineCaptions para ver qué pasó.'))[:140], error=True)
        except Exception:
            pass
        self._go_corriendo = False
        self._un_clic = False
        self._set_inputs_enabled(True)
    def _go_vista_previa(self, n_cues, langs, folder):
        """Antes de lanzar al timeline: los bloques con su estilo sobre los
        fotogramas reales (MCP), y «Lanzar» o «Revisar en el editor»."""
        self.go_panel.paso('sfx', 'hecho')
        # v5.2.1 (pedido: «sin vistas previas redundantes»): la esfera estalla y, en el pico, se coloca todo directo en el timeline
        try:
            import ajustes_ui
            con_vista = bool(ajustes_ui.leer_prefs().get('go_vista_previa', False))
        except Exception:
            con_vista = False
        if not con_vista:
            self._go_paso_actual = 'resolve'
            self.go_panel.explosion_final(lambda: self._go_lanzar(n_cues, langs, folder))
            return
        self._go_paso_actual = 'preview'
        self.go_panel.paso('preview')
        bloques = [b for b in (getattr(self, '_ultimos_bloques', None) or []) if b.get('lines')]
        con_main = [b for b in bloques if any(l.get('role') == 'main' for l in b['lines'])] or bloques
        n = min(5, len(con_main))
        elegidos = [con_main[int(i * (len(con_main) - 1) / max(1, n - 1))] for i in range(n)] if n else []
        marca = self._offset_frames()
        pack_go = self.plantilla_sel if self.plantilla_sel not in ('dinamico', 'media_pool', '', None) else None
        formato_go = self._formato_en_juego()
        self.go_panel.linea.configure(text=tr('Resolve está renderizando la vista previa real…'))
        def trabajo():
            imagenes, reales = [], False
            rutas = [None] * len(elegidos)
            try:
                import resolve_mcp
                if resolve_mcp.estado_cacheado().get('conectado') or resolve_mcp.disponible():
                    # v5.2 (pedido: «vistas previas renders reales»): Resolve coloca
                    # los bloques de muestra con el pack sobre una COPIA temporal de
                    # tu timeline y exporta el fotograma de cada uno
                    try:
                        import vistas_reales
                        rutas = vistas_reales.renderizar_bloques(pack_go or 'auto', formato_go or 'v', elegidos, marca)
                        reales = any(rutas)
                    except Exception:
                        guardar_log_de_error(traceback.format_exc())
                        rutas = [None] * len(elegidos)
                    if not reales:
                        rutas = resolve_mcp.fotogramas_de([float(b['start']) + 0.3 for b in elegidos], marca)
            except Exception:
                rutas = [None] * len(elegidos)
            for r in rutas:
                img = QImage(r) if r else QImage()
                if not img.isNull():
                    modo = Qt.AspectRatioMode.KeepAspectRatio if reales else Qt.AspectRatioMode.KeepAspectRatioByExpanding
                    img = img.scaled(1280, 1280 if reales else 720, modo, Qt.TransformationMode.SmoothTransformation)
                imagenes.append(img if not img.isNull() else None)
            return (imagenes, reales)
        def fin(resultado, _error):
            imagenes, reales = resultado if resultado else ([None] * len(elegidos), False)
            pack = pack_go
            formato = formato_go
            ejemplos = []
            for b, img in zip(elegidos, imagenes):
                lineas = [l for l in b['lines'] if l.get('text')]
                vista = lineas_de_vista(pack, formato, textos=[l['text'] for l in lineas], roles=[l.get('role') or 'base' for l in lineas])
                seg = float(b.get('start') or 0)
                ejemplos.append((img, vista, tr('Bloque en {m}:{s:04.1f}', m=int(seg // 60), s=seg % 60), bool(reales and img is not None)))
            r = getattr(self, '_resumen_ia', None) or {}
            resumen = [tr('{n} bloques', n=n_cues), tr('{n} grupos destacados', n=r.get('grupos', '—'))]
            if r.get('ia'):
                resumen.append(tr('IA: {n} correcciones', n=r.get('cambios', 0)))
            else:
                resumen.append(tr('Palabras: motor clásico (instala la IA en Ajustes)'))
            if r.get('emojis'):
                resumen.append(tr('{n} emojis', n=r.get('emojis')))
            if reales:
                resumen.append(tr('Render real de Resolve'))
            # v5.2: el formato forzado a mano que no coincide con el timeline se avisa
            try:
                import resolve_mcp
                est = resolve_mcp.estado_cacheado()
                ancho, alto = int(est.get('ancho') or 0), int(est.get('alto') or 0)
                forzado = self._formato_forzado()
                if ancho and alto and forzado in ('h', 'v') and forzado != ('v' if alto > ancho else 'h'):
                    resumen.append(tr('Ojo: formato {f} forzado y el timeline es {t}', f=tr('vertical') if forzado == 'v' else tr('horizontal'),
                                      t=tr('vertical') if alto > ancho else tr('horizontal')))
            except Exception:
                pass
            n_sfx = sum(1 for b in bloques if b.get('sfx'))
            if n_sfx:
                resumen.append(tr('{n} efectos de sonido', n=n_sfx))
            import un_clic_ui
            if not ejemplos:
                self._go_lanzar(n_cues, langs, folder)
                return
            self._vista_go = un_clic_ui.VistaPreviaGo(ejemplos, resumen, lambda: self._go_lanzar(n_cues, langs, folder), self._go_editor)
            self._vista_go.abrir(self)
        _correr_en_hilo(self, trabajo, fin)
    def _go_lanzar(self, n_cues, langs, folder):
        self.go_panel.paso('preview', 'hecho')
        self._go_paso_actual = 'resolve'
        self.go_panel.paso('resolve')
        self.go_panel.linea.configure(text=tr('Colocando los subtítulos en tu timeline…'))
        self._al_terminar_generacion(n_cues, langs, folder)
        # si no hay forma automatica (ni MCP, ni Studio, ni Puente) queda a mano
        if not getattr(self, '_go_corriendo', False):
            return
        try:
            import resolve_bridge
            if resolve_bridge.modo_actual(pasivo=True) == 'manual':
                self._go_fin(False, tr('Generado. Falta un clic en Resolve: Scripts > CineCaptions_Subtitulos.'))
        except Exception:
            pass
    def _go_fin(self, ok, texto='', detalle=''):
        if not getattr(self, '_go_corriendo', False):
            return
        if ok:
            registro.ok(texto or tr('GO terminó: ya está en tu timeline.'), 'GO')
        else:
            registro.error(texto or tr('GO no pudo colocar los subtítulos.'), 'GO · resolve', detalle=detalle)
        self._fin_tarea(ok, '' if ok else str(texto or '')[:160])
        if not ok:
            self.go_panel.paso_fallido = 'resolve'
        self.go_panel.paso('resolve', 'hecho' if ok else 'error')
        self._go_termino = bool(ok)
        try:
            import avisos_sistema
            if ok:
                avisos_sistema.avisar(self, tr('GO terminó'), tr('Tus subtítulos ya están en el timeline de Resolve.'))
            else:
                avisos_sistema.avisar(self, tr('GO no pudo terminar'), str(texto or tr('Abre CineCaptions para ver qué pasó.'))[:140], error=True)
        except Exception:
            pass
        if ok and not texto and getattr(self, '_idioma_detectado_go', None):
            texto = tr('Ya está en tu timeline · idioma oído: {i}. Si no era ese, cámbialo arriba y pulsa GO.', i=NOMBRE_POR_CODIGO.get(self._idioma_detectado_go, self._idioma_detectado_go))
        self.go_panel.terminar(ok, texto or (tr('Ya está en tu timeline. Pulsa GO para otro.') if ok else ''), self._go_estadisticas() if ok else None)
        self._borrar_go_en_curso()
        self._go_corriendo = False
        self._un_clic = False
        if ok:
            def ir():
                try:
                    import resolve_mcp
                    info = resolve_mcp.asegurar_audio_original()           # el audio original del video no se quita: se comprueba y, si faltara, se repone
                    if info.get('repuestos'):
                        registro.aviso(tr('El audio original del video no estaba en A1 al terminar: lo repuse.'), 'GO · resolve')
                    elif info.get('v1') and not info.get('a1_ahora'):
                        registro.aviso(tr('El video no tiene audio en la pista A1 del timeline (¿el archivo no tiene sonido o está «Archivo no encontrado» en Resolve?).'), 'GO · resolve')
                    resolve_mcp.ir_a_pagina('edit')
                except Exception:
                    pass
            threading.Thread(target=ir, daemon=True).start()
    def _go_estadisticas(self):
        """Los contadores del final: bloques, palabras, duración y (si hay) efectos y emojis."""
        try:
            bloques = [b for b in (getattr(self, '_ultimos_bloques', None) or []) if b.get('lines')]
            palabras = sum(len((l.get('text') or '').split()) for b in bloques for l in b['lines'])
            if bloques:
                dur = max(float(b.get('end') or 0) for b in bloques) - min(float(b.get('start') or 0) for b in bloques)
            else:
                dur = 0.0
            items = [(len(bloques), tr('bloques'), 'n'), (palabras, tr('palabras'), 'n'), (dur, tr('duración'), 't')]
            n_sfx = sum(1 for b in bloques if b.get('sfx'))
            if n_sfx:
                items.append((n_sfx, tr('efectos'), 'n'))
            r = getattr(self, '_resumen_ia', None) or {}
            if r.get('emojis'):
                items.append((r.get('emojis'), tr('emojis'), 'n'))
            return items
        except Exception:
            return None
    # -- v5.8: el recorrido visual por la interfaz (recorrido_ui.py) ---------------------------------------------------------------------
    def _pasos_recorrido(self):
        """Los pasos del recorrido guiado: a qué pantalla ir, qué zona iluminar y qué contar (todo en el idioma de la interfaz)."""
        import recorrido_ui
        P = recorrido_ui.Paso

        def aqui(*nombres):
            def f():
                o = self
                for n in nombres:
                    o = getattr(o, n, None)
                    if o is None:
                        return None
                return o
            return f

        def isla():
            r = QRectF()
            for c in ('inicio', 'nuevo', 'editor', 'sfx', 'estado', 'ajustes', 'pin'):
                r = r.united(self.isla.rect_de(c))
            return r

        def reglas():
            est = getattr(self, '_estudio_ventana', None)
            if est is None:
                return None
            try:
                it = est.tarjeta_reglas.capa.itemAt(0)
                return it.widget() if it is not None and it.widget() is not None else est
            except Exception:
                return est

        def editor():
            ed = getattr(self, '_editor', None)
            if ed is not None:
                return ed
            vacio = getattr(self, '_editor_vacio', None)
            return next(iter(vacio.findChildren(Tarjeta)), None) if vacio is not None else None
        return [
            P(tr('Bienvenido a CineCaptions'),
              tr('Te enseño la interfaz en un minuto: dónde está cada cosa y para qué sirve. Puedes salir cuando quieras con Esc, y volver a verlo o desactivarlo desde Ajustes.'),
              None, 'inicio'),
            P(tr('Tu barra de navegación'),
              tr('Aquí cambias de pantalla: Inicio, Proyecto (audio y estilos), Creativo (retocar palabras) y Sonido (efectos). A la derecha, el estado de Resolve, los Ajustes y el pin para mantener CineCaptions encima de Resolve.'),
              isla, 'inicio', lado='abajo', margen=8),
            P(tr('GO: todo en un clic'),
              tr('Pulsa GO y CineCaptions pide el audio a Resolve, lo transcribe, arma los bloques con su estilo, añade sonidos y emojis y lo coloca todo en tu timeline. También puedes soltar un video sobre la ventana.'),
              aqui('go_panel', 'boton'), 'inicio', lado='derecha', margen=-34, redondeo=400),
            P(tr('Tus opciones de un vistazo'),
              tr('Debajo de GO eliges el estilo, los emojis, los efectos de sonido y el formato. Si algo cambia el resultado sin que se vea (una posición ajustada, un estilo fijo) aparece en ámbar: un clic lo quita.'),
              aqui('go_panel', 'opciones'), 'inicio', lado='arriba'),
            P(tr('Proyecto: el audio'),
              tr('«Obtener» trae el audio de tu timeline de Resolve y lo transcribe con la IA. Casi nunca lo necesitas: GO lo hace por ti; sirve para repetir solo la transcripción.'),
              aqui('_tarjeta_audio'), 'estilos', lado='abajo'),
            P(tr('Proyecto: pack de estilos'),
              tr('Cada tarjeta es un pack. Haz clic en uno para elegirlo (el resaltado es el que usas). Un pack trae hasta 3 estilos, cada uno con su línea de arriba, principal y abajo. Con el lápiz lo editas en Resolve y con la papelera lo quitas.'),
              aqui('_plantillas_ventana'), 'estilos', lado='derecha'),
            P(tr('Crea tu estilo'),
              tr('Abre una galería de ejemplos con vista animada: toca hasta 3 que te gusten, ponle nombre y pulsa «Crear mi pack». Aparece en el slider, listo para usar.'),
              aqui('_plantillas_ventana', 'crear_btn'), 'estilos', lado='abajo', margen=8),
            P(tr('Creativo: retoca las palabras'),
              tr('Después de GO se abre aquí el editor: pinta cada palabra con su rol (Arriba, Principal, Abajo o Simple). Al tocar un texto ves qué estilo lleva y dónde cae, y puedes cambiarlo. «Generar» lo vuelve a colocar en Resolve.'),
              editor, 'editor', lado='abajo'),
            P(tr('Sonido'),
              tr('La biblioteca de efectos y las reglas automáticas por palabra (Simple y Emojis, donde cada emoji suena distinto). Se aplican solas al generar con GO.'),
              reglas, 'sfx', lado='abajo'),
            P(tr('El estado de un vistazo'),
              tr('El punto de color indica si Resolve, la IA y la licencia están listos. Tócalo para ver el detalle.'),
              lambda: self.isla.rect_de('estado'), 'inicio', lado='abajo', margen=6),
            P(tr('Ajustes'),
              tr('Idioma, tema, animaciones, motor de voz y más. Aquí también puedes volver a ver este recorrido o desactivarlo para que no aparezca.'),
              lambda: self.isla.rect_de('ajustes'), 'inicio', lado='abajo', margen=6),
            P(tr('Todo listo'),
              tr('Ya conoces CineCaptions. Para empezar, abre tu timeline en Resolve y pulsa GO. Si algo no queda como quieres, retócalo en Creativo.'),
              None, 'inicio'),
        ]

    def iniciar_recorrido(self, manual=False):
        """Muestra el recorrido guiado. manual=True (Ajustes > «Ver el recorrido») lo lanza aunque esté desactivado. Devuelve True si arrancó."""
        if getattr(self, '_recorrido', None) is not None:
            return False
        if self._trabajando() or getattr(self, '_editor', None) is not None:
            if manual:
                import ui_toast
                ui_toast.mostrar(self, tr('Termina primero lo que estás haciendo y vuelve a intentarlo.'))
            return False
        try:
            import recorrido_ui
            self._recorrido = recorrido_ui.Recorrido(self, self._pasos_recorrido(), self._recorrido_fin, self._recorrido_no_mostrar)
        except Exception:
            self._recorrido = None
            registro.excepcion(origen='recorrido guiado')
            return False
        return True

    def _recorrido_fin(self, completo):
        """El recorrido terminó (o se salió): se recuerda que ya se vio y se vuelve a Inicio."""
        self._recorrido = None
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'recorrido_visto': True})
        except Exception:
            pass
        try:
            self.ir_a('inicio', animar=False)
        except Exception:
            pass
        try:         # las vistas reales que se aplazaron mientras duraba el recorrido
            import resolve_mcp
            if getattr(self, '_plantillas_ventana', None) is not None and resolve_mcp.estado_cacheado().get('conectado'):
                despues(1500, lambda: self._plantillas_ventana._renderizar_reales(silencioso=True), self)
        except Exception:
            pass

    def _recorrido_no_mostrar(self):
        try:
            import ajustes_ui
            import ui_toast
            ajustes_ui.guardar_prefs({'recorrido_activo': False, 'recorrido_visto': True})
            ui_toast.mostrar(self, tr('Listo: el recorrido no volverá a salir. Puedes verlo cuando quieras en Ajustes.'))
        except Exception:
            pass

    def _recorrido_auto(self, intento=0):
        """Al abrir el programa por primera vez (o hasta que se vea / se desactive), arranca solo el recorrido cuando no hay nada en medio."""
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            return
        if prefs.get('recorrido_activo', True) is False or prefs.get('recorrido_visto') or getattr(self, '_caducada', False):
            return
        ocupado = (QApplication.activeModalWidget() is not None or not self.isVisible() or self.isMinimized() or self._trabajando()
                   or getattr(self, '_editor', None) is not None or getattr(self, '_lic_pidiendo', False) or not licencia.vigente())
        if ocupado:
            if intento < 8:
                despues(4000, lambda: self._recorrido_auto(intento + 1), self)
            return
        self.iniciar_recorrido()
    def _go_ver_en_resolve(self):
        def ir():
            try:
                import resolve_mcp
                resolve_mcp.ir_a_pagina('edit')
            except Exception:
                pass
        threading.Thread(target=ir, daemon=True).start()
    def _go_editor(self):
        """«Revisar en el editor»: las marcas de la IA ya estan guardadas; el
        editor las abre y al Continuar regenera y coloca (Editar marcas)."""
        self._go_corriendo = False
        self._un_clic = False
        self.go_panel.paso('preview', 'saltado', tr('al editor'))
        self.go_panel.terminar(True, tr('Revisa las palabras y pulsa Continuar: se coloca solo.'))
        try:
            self._on_update()
        except Exception as e:
            messagebox.showerror(tr('Editor'), str(e), parent=self)
    def _lista_recetas(self):
        if isinstance(self.recetas, list):
            return [dict(r) for r in self.recetas if isinstance(r, dict)]
        return _recetas_por_defecto()
    def _pintar_recetas(self):
        capa = getattr(self, 'recetas_capa', None)
        if capa is None:
            return
        limpiar_capa(capa)
        self._chips_recetas = []
        lista = self._lista_recetas()
        if not lista:
            capa.addWidget(Etiqueta(tr('Sin recetas. Elige tus ajustes en «Nuevo proyecto» y pulsa «+ Guardar la actual».'), 13, color=TEXT_MUTED, envolver=True))
            return
        for k, rec in enumerate(lista):
            fila = QFrame()
            fila.setObjectName('fila')
            cf = QHBoxLayout(fila)
            cf.setContentsMargins(16, 12, 14, 12)
            cf.setSpacing(10)
            info, ci = caja_v(espacio=3)
            nombre = _Elidida(rec.get('nombre') or '—', 14, peso='medio', color='#FFFFFF')
            ci.addWidget(nombre)
            detalle = _Elidida(rec.get('detalle') or '', 12, color=TEXT_MUTED)
            ci.addWidget(detalle)
            cf.addWidget(info, 1)
            chip = Chip(tr('Usar'), ui.ACCENT_CLARO, lambda r=rec: self._usar_receta(r), alto=28)
            chip.setEnabled(self._entradas_activas)
            cf.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
            self._chips_recetas.append(chip)
            fila.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            fila.customContextMenuRequested.connect(lambda _pos, i=k: self._menu_receta(i))
            capa.addWidget(fila)
    def _menu_receta(self, indice):
        menu = Menu(self)
        menu.agregar(tr('Quitar esta receta'), lambda: self._quitar_receta(indice))
        menu.agregar(tr('Volver a las recetas de ejemplo'), self._recetas_de_ejemplo)
        menu.mostrar(QCursor.pos())
    def _quitar_receta(self, indice):
        lista = self._lista_recetas()
        if 0 <= indice < len(lista):
            del lista[indice]
            self.recetas = lista
            self._guardar_preferencias()
            self._pintar_recetas()
    def _recetas_de_ejemplo(self):
        self.recetas = None
        self._guardar_preferencias()
        self._pintar_recetas()
    def _guardar_receta_actual(self):
        """«+ Guardar la actual»: los ajustes de «Nuevo proyecto» como receta."""
        titulos = {c: t for c, t, _d in self.MOSAICOS}
        partes = [titulos.get(self._mosaico_actual(), '')]
        forzado = self._formato_forzado()
        if forzado:
            partes.append(plantillas.ETIQUETA_FORMATO[forzado])
        if self.sfx_var.get() and self._modo() != 'normal':
            partes.append(tr('con SFX'))
        if self.translate_var.get() and self._modo() == 'normal':
            partes.append(tr('traducción a {idioma}', idioma=self.destino_var.get()))
        sugerido = ' · '.join(p for p in partes if p)
        nombre = simpledialog.askstring(tr('Guardar receta'), tr('¿Cómo llamas a esta receta?'), initialvalue=sugerido, parent=self)
        if not nombre or not nombre.strip():
            return
        detalle = self._etiqueta_plantilla_completa().rstrip().rstrip('>').rstrip() if self._modo() != 'destacados' else titulos.get(self._look(), '')
        rec = {'nombre': nombre.strip(), 'detalle': detalle, 'modo': self._modo(),
               'look': self._look() if self._modo() == 'destacados' else None,
               'formato_video': self._formato_forzado() or 'auto', 'sfx': bool(self.sfx_var.get()),
               'traducir': bool(self.translate_var.get()), 'idioma_destino': self._idioma_destino(),
               'plantilla': self.plantilla_sel}
        lista = self._lista_recetas()
        lista.insert(0, rec)
        self.recetas = lista[:8]
        self._guardar_preferencias()
        self._pintar_recetas()
        self.status_var.set(tr('Receta «{nombre}» guardada.', nombre=rec['nombre']))
    def _usar_receta(self, rec):
        """«Usar»: pone el modo, el formato, los efectos y la traducción de la
        receta y lleva a «Nuevo proyecto». Lo demas no se toca."""
        if not self._entradas_activas:
            return
        modo = rec.get('modo')
        if modo in ('normal', 'dinamico', 'destacados'):
            self.modo_var.set(self._etiqueta_de_modo[modo])
        if modo == 'destacados' and rec.get('look') in self.LOOKS.values():
            self.look_var.set(self._etiqueta_de_look[rec['look']])
        fmt = rec.get('formato_video')
        self.formato_var.set(self._etiqueta_de_formato.get(None if fmt in (None, '', 'auto') else fmt, tr('Detectar solo')))
        self.translate_var.set(bool(rec.get('traducir')) and modo == 'normal')
        destino = _codigo_de(rec.get('idioma_destino'))
        if destino in NOMBRE_POR_CODIGO:
            self.destino_var.set(NOMBRE_POR_CODIGO[destino])
            if self.translate_var.get():
                self._refrescar_destinos()
        elegido = rec.get('plantilla')
        if elegido in ('auto', 'media_pool') or (elegido and any(pk.nombre == elegido for pk in plantillas.listar_packs())):
            self.plantilla_sel = elegido
        sfx = bool(rec.get('sfx'))
        self.sfx_var.set(sfx)
        if sfx and not getattr(self, '_sfx_categoria_elegida', None):
            try:
                import sfx_rules
                if 'Esenciales' in sfx_rules.categorias_disponibles():
                    self._sfx_categoria_elegida = 'Esenciales'
                    self._actualizar_etiqueta_sfx()
                else:
                    self._on_sfx_toggle()
            except Exception:
                self._on_sfx_toggle()
        self._on_modo_change()
        self._refrescar_formato_detectado()
        self._guardar_preferencias()
        self.status_var.set(tr('Receta «{nombre}» aplicada.', nombre=rec.get('nombre') or ''))
        self.ir_a('nuevo')
    def _refrescar_recientes(self):
        """Repuebla «Proyectos recientes» de Inicio."""
        capa = getattr(self, 'recientes_capa', None)
        if capa is None:
            return
        limpiar_capa(capa)
        try:
            lista = [p for p in proyectos.listar(limite=12) if p.get('existe')][:5]
        except Exception:
            lista = []
        if not lista:
            vacio = Etiqueta(tr('Aún no hay proyectos. Genera los subtítulos de un video y aparecerá aquí.'), 13, color=TEXT_MUTED, envolver=True)
            vacio.setContentsMargins(4, 16, 4, 16)
            capa.addWidget(vacio)
            return
        modos = {'normal': tr('Normales'), 'dinamico': tr('Dinámicos')}
        looks = {'hormozi': tr('Hormozi'), 'gadzhi': tr('Gadzhi'), 'acumulativo': tr('Acumulativo'), 'pintado': tr('Pintado')}
        for k, proy in enumerate(lista):
            nombre = proyectos.nombre_display(proy)
            langs = str(proy.get('ultima_gen_langs') or '')
            codigos = [c.strip() for c in langs.split(',') if c.strip()]
            if len(codigos) > 1:
                idioma = f'{codigos[0]} > {codigos[1]}'
            else:
                idioma = (codigos[0] if codigos else str(proy.get('idioma') or '—')).upper()
            modo = proy.get('modo')
            modo_txt = looks.get(proy.get('look'), tr('Destacados')) if modo == 'destacados' else modos.get(modo, '—')
            if proy.get('ultima_gen_bloques'):
                estado = Chip(tr('Traducido'), ui.ACCENT_CLARO, alto=26, tam=12) if len(codigos) > 1 else Chip(tr('Listo'), ui.VERDE, alto=26, tam=12)
            elif ruta_marcas(proy.get('project_name') or Path(nombre).stem).exists():
                estado = Chip(tr('Editando marcas'), ui.AMBAR, alto=26, tam=12)
            else:
                estado = Chip(tr('Sin generar'), TEXT_MUTED, alto=26, tam=12)
            celda_nombre = _Elidida(nombre, 14, peso='medio', color='#FFFFFF')
            celda_nombre.setToolTip(str(proy.get('video_path') or nombre))
            fila = _FilaProyecto([celda_nombre, idioma, modo_txt, estado, _hace(proy.get('modificado_en'))],
                                 comando=lambda p=proy: (self._cargar_proyecto(p), self.ir_a('nuevo')),
                                 ultima=k == len(lista) - 1)
            capa.addWidget(fila)
    def _ejecutar_diagnostico(self):
        """«Ejecutar diagnóstico»: el informe de siempre (diagnostico.txt) y
        el del Puente al portapapeles."""
        self.diag_btn.configure(state='disabled', text=tr('Revisando…'))
        def fin(_resultado, _error):
            self.diag_btn.configure(state='normal', text=tr('Ejecutar diagnóstico'))
            self._refrescar_estado()
            self._copiar_diagnostico_scripts()
        _correr_en_hilo(self, escribir_diagnostico, fin)
    def _refrescar_estado(self):
        """Las tarjetas de estado (Inicio y lateral), en un hilo."""
        if self._recogiendo:
            return
        self._recogiendo = True
        _correr_en_hilo(self, self._recoger_estado, self._pintar_estado)
    @staticmethod
    def _recoger_estado():
        """Corre en un hilo: NO toca widgets."""
        d = {}
        try:
            # v5.1: la conexion MCP oficial (Resolve 21.1+) se pregunta de
            # verdad aqui, en el hilo; arrancar ResolveMCP cuesta 0,2-4 s
            import resolve_mcp
            d['mcp'] = resolve_mcp.estado(refrescar=True)
        except Exception:
            d['mcp'] = {}
        try:
            import resolve_bridge
            d['modo'] = resolve_bridge.modo_actual(pasivo=True)
        except Exception:
            d['modo'] = None
        try:
            import colocacion
            d['proceso'] = colocacion.resolve_en_proceso()          # v5.5: ¿Resolve está abierto?, para decir «cerrado» en vez de «falta el Puente»
        except Exception:
            d['proceso'] = None
        try:
            import motor_voz
            d['motor'] = motor_voz.info_instalado()
            d['motor_pref'] = motor_voz._leer_preferencia()
        except Exception:
            d['motor'] = None
        try:
            import instalador_scripts as ins
            d['edicion'] = ins.edicion_de_resolve()
            d['instalado'] = ins.resolve_esta_instalado()
            nuestros = [a.name for a in ins._nuestros_scripts()]
            mejor = 0
            for carpeta in ins.carpetas_scripts_resolve():
                if carpeta.is_dir():
                    mejor = max(mejor, sum((1 for n in nuestros if (carpeta / n).exists())))
            d['scripts'] = (mejor, len(nuestros))
        except Exception:
            pass
        try:
            pares = set()
            for pack in plantillas.packs_incorporados():
                try:
                    pares.update(pack.fuentes())
                except Exception:
                    pass
            arreglables, sin_remedio = instalar_fuentes.faltantes(sorted(pares))
            d['fuentes'] = (len(pares), len(arreglables), len(sin_remedio))
        except Exception:
            pass
        try:
            hub = os.environ.get('HF_HUB_CACHE')
            raiz = Path(hub) if hub else Path(os.environ.get('HF_HOME') or Path.home() / '.cache' / 'huggingface') / 'hub'
            d['modelo'] = any(raiz.glob(f'models--*faster-whisper-{MODEL_SIZE}*'))
        except Exception:
            d['modelo'] = None
        try:
            d['cuda'] = bool(st._hay_cuda_usable())
        except Exception:
            d['cuda'] = None
        try:
            d['argos'] = len(lang_packs.paquetes_instalados())
        except Exception:
            d['argos'] = None
        try:
            import emojis
            d['emojis'] = len(emojis.catalogo())
        except Exception:
            d['emojis'] = None
        try:
            import sfx_rules
            d['efectos'] = sum((len(v) for v in sfx_rules.categorias_disponibles().values()))
        except Exception:
            d['efectos'] = None
        return d
    def _pintar_estado(self, d, error):
        self._recogiendo = False
        if error is not None or not isinstance(d, dict):
            return
        self._estado_sistema = d
        modo, edicion, instalado = (d.get('modo'), d.get('edicion'), d.get('instalado'))
        hechos, total = d.get('scripts') or (0, 0)
        mcp = d.get('mcp') or {}
        if modo == 'mcp' and mcp.get('conectado'):
            edicion_txt = 'Studio' if 'Studio' in str(mcp.get('producto') or '') else 'Free'
            tarjeta = (ui.VERDE, tr('{e} · conectado', e=edicion_txt), tr('MCP oficial · {v}', v=mcp.get('version') or ''))
            lateral = (ui.VERDE, tr('Resolve conectado'), f"{mcp.get('producto') or 'DaVinci Resolve'} {mcp.get('version') or ''}".strip())
        elif modo == 'studio':
            tarjeta = (ui.VERDE, tr('Studio · conectado'), tr('API externa, sin Puente'))
            lateral = (ui.VERDE, tr('Resolve Studio conectado'), tr('API externa, sin Puente'))
        elif modo == 'puente':
            tarjeta = (ui.VERDE, tr('Free · Puente activo'), tr('Scripts instalados: {a} de {b}', a=hechos, b=total))
            lateral = (ui.VERDE, tr('Resolve · Puente activo'), tr('Todo se ejecuta solo'))
        elif mcp.get('mcp') and not mcp.get('conectado'):
            # Resolve 21.1+ instalado (hay ResolveMCP) pero cerrado
            tarjeta = (ui.AMBAR, tr('Resolve cerrado'), tr('Ábrelo con tu proyecto: se conecta solo (MCP)'))
            lateral = (ui.AMBAR, tr('Resolve cerrado'), tr('DaVinci Resolve {v} · ábrelo', v=mcp.get('version') or '').replace('  ', ' '))
        elif edicion == 'studio':
            tarjeta = (ui.AMBAR, tr('Studio · cerrado'), tr('Abre Resolve con tu proyecto'))
            lateral = (ui.AMBAR, tr('Resolve Studio cerrado'), tr('Ábrelo con tu proyecto'))
        elif instalado is False:
            tarjeta = (ui.ROJO, tr('No encontrado'), tr('¿Está instalado DaVinci Resolve?'))
            lateral = (ui.ROJO, tr('Resolve no encontrado'), tr('¿Está instalado?'))
        else:
            tarjeta = (ui.AMBAR, tr('Free · sin Puente'), tr('Scripts instalados: {a} de {b}', a=hechos, b=total))
            lateral = (ui.AMBAR, tr('Resolve · sin Puente'), tr('Lanza CineCaptions_Puente en Resolve'))
        self.tarjeta_resolve.poner(*tarjeta)
        self.lat_punto_resolve.poner(lateral[0])
        if hasattr(self, 'isla'):
            self.isla.poner_estado(lateral[0])
        self.lat_resolve.configure(text=lateral[1])
        self.lat_resolve_det.configure(text=lateral[2])
        cuda = d.get('cuda')
        motor = d.get('motor')
        if motor and d.get('motor_pref', 'qwen3') == 'qwen3':
            # v5.1: Qwen3-ASR instalado (motor_voz); Whisper queda de respaldo
            self.tarjeta_motor.poner(ui.VERDE, f"Qwen3-ASR {motor.get('modelo') or ''}".strip(),
                                     tr('Local · {d} · Whisper de respaldo', d=(motor.get('gpu') or 'CPU')))
        else:
            detalle = tr('Local · GPU (CUDA)') if cuda else (tr('Local · CPU') if cuda is False else tr('Local · usa GPU si hay CUDA'))
            if d.get('modelo') is False:
                detalle += ' · ' + tr('se descarga la 1.ª vez')
            self.tarjeta_motor.poner(ui.VERDE, f'Whisper {MODEL_SIZE}', detalle)
        n = d.get('argos')
        if n:
            self.tarjeta_traduccion.poner(ui.ACCENT_CLARO, tr('Sin internet'), tr('Argos · {n} paquetes instalados', n=n))
        else:
            self.tarjeta_traduccion.poner(ui.ACCENT_CLARO, tr('Sin paquetes'), tr('Argos · se descargan al traducir'))
        filas = self._filas_sistema
        def poner(clave, tipo, texto, ayuda=''):
            icono, valor, fila = filas[clave]
            icono.poner(tipo)
            valor.configure(text=texto)
            fila.setToolTip(ayuda)
        if modo == 'mcp':
            poner('scripts', 'ok', tr('no hacen falta'), tr('Con la conexión MCP de Resolve 21 el programa se conecta directo: el menú Scripts es solo el plan B.'))
        elif modo == 'studio' or edicion == 'studio':
            poner('scripts', 'ok', tr('no hacen falta'), tr('Con Resolve Studio el programa se conecta directo: el menú Scripts es solo para la versión gratuita.'))
        elif total and hechos == total:
            poner('scripts', 'ok', tr('{a} de {b}', a=hechos, b=total))
        elif total:
            poner('scripts', 'aviso', tr('{a} de {b}', a=hechos, b=total), tr('Usa «Reinstalar scripts».'))
        else:
            poner('scripts', 'error', tr('no encontrados'))
        f = d.get('fuentes')
        if f is None:
            poner('tipografias', 'info', '—')
        elif f[1] + f[2] == 0:
            poner('tipografias', 'ok', tr('{n} incluidas', n=f[0]))
        else:
            poner('tipografias', 'aviso', tr('faltan {n}', n=f[1] + f[2]), tr('Resolve solo ve las fuentes instaladas en el sistema. Instálalas desde «Estilos y composición».'))
        modelo = d.get('modelo')
        if motor and d.get('motor_pref', 'qwen3') == 'qwen3':
            poner('modelo', 'ok', f"Qwen3-ASR {motor.get('modelo') or ''}".strip(), tr('Motor de voz Qwen3-ASR instalado (Ajustes > General).'))
        else:
            poner('modelo', 'ok' if modelo else 'info', f'{MODEL_SIZE} · 1,5 GB' if modelo else tr('se descarga al primer uso'))
        poner('traduccion', 'ok' if n else 'info', tr('lista') if n else tr('sin paquetes'))
        e = d.get('emojis')
        poner('emojis', 'ok' if e else 'aviso', f'~{e:,}'.replace(',', ' ') if e else tr('no disponibles'))
        s = d.get('efectos')
        poner('efectos', 'ok' if s else 'aviso', tr('{n} sonidos', n=s) if s else tr('sin sonidos'))
        self._refrescar_receta()
        self._pintar_go_reposo()
    def _pintar_licencia(self, _est=None):
        """La tarjeta «Licencia» de Inicio (v5.2.1: el estado guardado de Lemon Squeezy, sin red)."""
        try:
            d = licencia.resumen()
        except Exception:
            return
        color = {'ok': ui.VERDE, 'aviso': ui.AMBAR}.get(d['nivel'], ui.ROJO)
        self.tarjeta_licencia.poner(color, d['estado'], d['detalle'])
        self.lat_punto_licencia.poner(color)
        self.lat_licencia.configure(text=tr('Licencia activa') if d['activa'] else tr('Activar licencia'))
    # -- Nuevo proyecto --------------------------------------------------------
    def _pagina_nuevo(self):
        _pag, capa = self._nueva_pagina('nuevo', tr('Nuevo proyecto'), tr('Revisa la receta y genera los subtítulos (el video se elige en «Estilos y composición»)'))
        self.pasos = Pasos([tr('Estilo'), tr('Generar')])
        capa.addWidget(self.pasos)
        cuerpo, cc = caja_h(espacio=20)
        der, cd = caja_v(espacio=20)
        cc.addWidget(der, 1, Qt.AlignmentFlag.AlignTop)
        # Proyecto unificado: «Fuente» (el video) vive ahora arriba de «Estilos y composición»; «Idioma hablado» y
        # «Formato de los subtítulos» ya no se muestran aquí (el idioma, los efectos y el formato del
        # video se eligen con los chips de GO en Inicio). Sus widgets se siguen construyendo, fuera de
        # pantalla, porque el resto del programa lee y guarda sus valores.
        self._tarjetas_ocultas = []
        capa.addWidget(cuerpo)
        capa.addStretch(1)
        # Audio (v5.3, antes «Fuente»): un solo botón, «Obtener», que trae el audio del timeline de Resolve por MCP
        # v5.4.3: el audio es UNA franja compacta que se coloca arriba de «Pack de estilos» (dentro de su tarjeta): Obtener · archivo · onda · duración · motor
        t = Tarjeta(nombre='franja_audio', margenes=(0, 0, 0, 0), espacio=0)
        self._tarjeta_audio = t
        self._insignias_audio = {}
        def _numero(n):
            # (las insignias 1 y 2 ya no se ven en la franja; el resto del programa sigue pintándolas según el paso)
            lbl = QLabel(str(n), t)
            lbl.setFixedSize(26, 26)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(ui.fuente(12, peso='negrita'))
            lbl.setStyleSheet(ui.traducir_hoja('QLabel { background-color: #12301F; border: 1px solid #22B573; border-radius: 13px; color: #6FE3AE; }'))
            lbl.hide()
            self._insignias_audio[n] = lbl
            return lbl
        self.insignia = QLabel('—')
        self.insignia.setObjectName('insignia')
        self.insignia.setFixedSize(40, 40)
        self.insignia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insignia.setFont(ui.fuente(11, peso='negrita'))
        self.insignia.setStyleSheet(ui.traducir_hoja('QLabel#insignia { background-color: #111D33; border: 1px solid #1E2A42; border-radius: 9px; color: #4589FF; }'))
        info, cinf = caja_v(espacio=1)
        self.fuente_nombre = _Elidida(tr('Ningún archivo elegido'), 14, peso='medio', color='#FFFFFF')
        cinf.addWidget(self.fuente_nombre)
        self.fuente_meta = _Elidida(tr('Pulsa «Obtener» para traer el audio de tu timeline de Resolve'), 12, color=TEXT_MUTED)
        cinf.addWidget(self.fuente_meta)
        self.fuente_onda = Onda(ui.ACCENT_CLARO, alto=36, barra=3.0, hueco=2.6)
        self.fuente_onda.setMinimumWidth(110)
        self.fuente_onda.setMaximumWidth(260)
        # La entrada, «Buscar» y «Proyectos guardados» siguen existiendo (el resto del programa lee y bloquea sus
        # valores) pero fuera de pantalla: aquí solo se ve «Obtener». Soltar un video en la ventana y el clic derecho
        # sobre esta franja siguen sirviendo para elegir un archivo a mano.
        oculto = QWidget()
        co = QHBoxLayout(oculto)
        co.setContentsMargins(0, 0, 0, 0)
        self.video_var = StringVar()
        self.video_entry = Entrada(self.video_var, placeholder=tr('Arrastra tu video al lanzador, o busca el archivo...'), alto=38, tam=13)
        co.addWidget(self.video_entry, 1)
        self.browse_btn = Boton(tr('Buscar...'), self._browse, tipo='primario', alto=38, ancho=100, tam=13)
        co.addWidget(self.browse_btn)
        proy_btn = Boton('', self._abrir_proyectos_guardados_main, tipo='icono', alto=38, ancho=42, icono=_icono_carpeta(17), lado_icono=17)
        co.addWidget(proy_btn)
        oculto.hide()
        t.capa.addWidget(oculto)
        fila, cf = caja_h(espacio=12)
        _numero(1)
        _numero(2)
        self.detect_btn = Boton(tr('Obtener'), lambda: self._detectar_desde_resolve(silencioso=False), tipo='primario', alto=40, ancho=132, tam=14, negrita=True)
        icono_obtener = ui.icono_linea('ph.download-simple-bold', '#FFFFFF')
        if icono_obtener is not None:
            self.detect_btn.setIcon(icono_obtener)
            self.detect_btn.setIconSize(QSize(16, 16))
        Tooltip(self.detect_btn, tr('Trae el audio del timeline que tienes abierto en Resolve (conexión MCP, rápida). Si Resolve está cerrado, lo abre.'))
        cf.addWidget(self.detect_btn)
        cf.addWidget(self.insignia)
        cf.addWidget(info, 2)
        cf.addWidget(self.fuente_onda, 1)
        col_t, ct_ = caja_v(espacio=0)
        self.fuente_duracion = Etiqueta('--:--', 22, peso='extra', color='#FFFFFF', alineacion=Qt.AlignmentFlag.AlignRight)
        ct_.addWidget(self.fuente_duracion)
        self.fuente_duracion_lbl = Etiqueta(tr('duración'), 10, color=TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignRight)
        ct_.addWidget(self.fuente_duracion_lbl)
        cf.addWidget(col_t)
        cf.addSpacing(10)
        self.obtener_nota = Etiqueta(tr('Del timeline abierto en Resolve · conexión MCP'), 12, color=TEXT_MUTED, envolver=True)
        self.obtener_nota.hide()
        # el motor que transcribe ese audio: la IA (Qwen3-ASR) o Whisper large-v3-turbo; el mismo ajuste que Ajustes > General
        cf.addWidget(Etiqueta(tr('Transcribir con'), 13, color='#E0EBFB'))
        self._motores_voz = {tr('IA · Qwen3-ASR'): 'qwen3', tr('Whisper large-v3-turbo'): 'whisper'}
        try:
            import ajustes_ui
            motor_guardado = str(ajustes_ui.leer_prefs().get('motor_voz') or 'qwen3')
        except Exception:
            motor_guardado = 'qwen3'
        self.motor_var = StringVar(next((k for k, v in self._motores_voz.items() if v == motor_guardado), tr('IA · Qwen3-ASR')))
        self.motor_seg = Segmentado(list(self._motores_voz.keys()), self.motor_var, self._cambio_motor_voz, alto=32, tam=12)
        Tooltip(self.motor_seg, tr('Qué motor convierte la voz en palabras con su tiempo. La IA (Qwen3-ASR) usa la GPU y es la más fina; Whisper large-v3-turbo es el de respaldo y entiende 99 idiomas.'))
        cf.addWidget(self.motor_seg)
        self.motor_nota = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        self.motor_nota.hide()                       # (el detalle de GPU/modelo queda en el tooltip del selector)
        t.capa.addWidget(fila)
        self._pintar_motor_voz()
        t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        t.customContextMenuRequested.connect(lambda _pos: self._menu_audio())
        self.video_var.observar(self._al_cambiar_video, self)
        self._tarjeta_fuente = t
        # Idioma
        t = Tarjeta(titulo=tr('Idioma hablado en el video'), espacio=14)
        fila, cf = caja_h(espacio=8)
        self.lang_var = StringVar(NOMBRE_POR_CODIGO['es'])
        self.lang_menu = ComboBuscable(LANG_MENU, self.lang_var, self._on_idioma_elegido, plegar=_plegar, alto=40)
        self.lang_menu.setSizeAdjustPolicy(self.lang_menu.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.lang_menu.setFixedWidth(250)
        Tooltip(self.lang_menu, tr('🔍 Escribe aquí para buscar entre los 99 idiomas. No hay nada que descargar: el modelo ya los entiende todos.'))
        cf.addWidget(self.lang_menu)
        self.favoritos_idiomas = []
        self.fav_btn = Boton('☆', self._alternar_favorito, tipo='icono', alto=40, ancho=40, tam=17)
        self.fav_btn.setFixedWidth(40)
        Tooltip(self.fav_btn, tr('Marca este idioma como favorito: quedará arriba de la lista para elegirlo de un vistazo.'))
        cf.addWidget(self.fav_btn)
        self.buscar_idioma_btn = Boton('🔍', self._abrir_buscador_idioma, tipo='icono', alto=40, ancho=40, tam=14)
        self.buscar_idioma_btn.setFixedWidth(40)
        Tooltip(self.buscar_idioma_btn, tr('Buscar entre los 99 idiomas escribiendo (sin tildes también)'))
        cf.addWidget(self.buscar_idioma_btn)
        cf.addSpacing(10)
        self.idiomas_chips_w = QWidget()
        self.idiomas_chips = ui.FlujoCapa(self.idiomas_chips_w, 8, 8)
        cf.addWidget(self.idiomas_chips_w, 1)
        self.lang_row = fila
        t.capa.addWidget(fila)
        self.traduccion_row, ctr = caja_h(espacio=8)
        self.translate_var = BooleanVar(False)
        self.translate_check = Interruptor(tr('Traducir a otro idioma'), self.translate_var, self._on_traducir_toggle, tam=14, color='#C9D6EC')
        ctr.addWidget(self.translate_check)
        ctr.addSpacing(14)
        self.destino_var = StringVar(NOMBRE_POR_CODIGO['en'])
        self.destino_menu = Combo([NOMBRE_POR_CODIGO['en']], self.destino_var, lambda _v=None: self._refrescar_receta(), ancho=170, alto=36, tam=13)
        ctr.addWidget(self.destino_menu)
        self.buscar_destino_btn = Boton('🔍', self._abrir_buscador_destino, tipo='icono', alto=36, ancho=38, tam=13)
        self.buscar_destino_btn.setFixedWidth(38)
        Tooltip(self.buscar_destino_btn, tr('Buscar el idioma de destino escribiendo (sin tildes también)'))
        ctr.addWidget(self.buscar_destino_btn)
        self.idiomas_btn = Boton('＋', self._abrir_idiomas_traduccion, tipo='icono', alto=36, ancho=38, tam=15, negrita=True)
        self.idiomas_btn.setFixedWidth(38)
        Tooltip(self.idiomas_btn, tr('Buscar y descargar más idiomas de traducción'))
        ctr.addWidget(self.idiomas_btn)
        # v5.2: iconos de linea (QtAwesome) en vez de emojis de color
        for boton, nombre in ((self.buscar_idioma_btn, 'ph.magnifying-glass'), (self.buscar_destino_btn, 'ph.magnifying-glass'),
                              (self.idiomas_btn, 'ph.plus-bold')):
            icono = ui.icono_linea(nombre, '#C9D6EC')
            if icono is not None:
                boton.setText('')
                boton.setIcon(icono)
                boton.setIconSize(QSize(17, 17))
        self.nota_traduccion = Etiqueta(tr('(solo disponible en Subtítulos normales)'), 13, color=TEXT_MUTED)
        ctr.addWidget(self.nota_traduccion)
        ctr.addStretch(1)
        t.capa.addWidget(self.traduccion_row)
        self.fmt_frame = QWidget()
        cfm = QHBoxLayout(self.fmt_frame)
        self.chars_label = Etiqueta(tr('Palabras por línea'), 12, color=TEXT_MUTED)
        cfm.addWidget(self.chars_label)
        self.chars_var = StringVar('7')
        self.chars_entry = Combo(['5', '6', '7', '8', '9', '10', '12', '15', '18', '20', '25', '30', '42'], self.chars_var, ancho=80, alto=30)
        cfm.addWidget(self.chars_entry)
        self.lines_label = Etiqueta(tr('Cantidad de líneas'), 12, color=TEXT_MUTED)
        cfm.addWidget(self.lines_label)
        self.lines_var = StringVar('3')
        self.lines_entry = Combo(['1', '2', '3', '4'], self.lines_var, ancho=80, alto=30)
        cfm.addWidget(self.lines_entry)
        self.fmt_frame.hide()
        t.capa.addWidget(self.fmt_frame)
        t.hide()
        self._tarjetas_ocultas.append(t)
        # Formato
        t = Tarjeta(titulo=tr('Formato de los subtítulos'), espacio=16)
        self.diseno_dinamico = None
        self.plantilla_sel = 'auto'
        self.composicion = composicion.valida(None)
        if not COMPOSICION_VISIBLE:
            try:
                composicion.retirar_orden()
            except Exception:
                pass
        self.basicos_sel = ''
        self.basicos_pack = plantillas.NOMBRE_BASICOS
        self._marca_entrada = None
        self._marca_salida = None
        self._ancho_timeline = 0
        self._alto_timeline = 0
        self.MODOS = {tr('Subtítulos normales'): 'normal', tr('Dinámicos (3 líneas)'): 'dinamico', tr('Destacados'): 'destacados'}
        self._modo_de_etiqueta = self.MODOS
        self._etiqueta_de_modo = {v: k for k, v in self.MODOS.items()}
        self.modo_var = StringVar(self._etiqueta_de_modo['dinamico'])
        self.LOOKS = {tr('Hormozi (contorno grueso, mayúsculas)'): 'hormozi', tr('Gadzhi (grande y limpio)'): 'gadzhi', tr('Acumulativo (el texto va creciendo)'): 'acumulativo', tr('Pintado palabra por palabra'): 'pintado'}
        self._etiqueta_de_look = {v: k for k, v in self.LOOKS.items()}
        self.look_var = StringVar(self._etiqueta_de_look['hormozi'])
        self.MOSAICOS = [('normal', tr('Subtítulos normales'), tr('Líneas cortas, con traducción')),
                         ('dinamico', tr('Dinámicos (3 líneas)'), tr('Arriba, principal, abajo e imagen')),
                         ('hormozi', tr('Hormozi'), tr('Contorno grueso, mayúsculas')),
                         ('gadzhi', tr('Gadzhi'), tr('Grande y limpio')),
                         ('acumulativo', tr('Acumulativo'), tr('El texto va creciendo')),
                         ('pintado', tr('Pintado'), tr('Palabra por palabra'))]
        self.modo_btn = _RejillaModos(self.MOSAICOS, self._elegir_mosaico)
        t.capa.addWidget(self.modo_btn)
        self.look_frame = QWidget()
        self.look_frame.hide()
        t.capa.addSpacing(4)
        self.basico_var = StringVar('2')
        self.basico_frame, cb = caja_h(espacio=16)
        lbl = Etiqueta(tr('Palabras por bloque'), 14, color='#E0EBFB')
        lbl.setFixedWidth(190)
        cb.addWidget(lbl)
        cb.addWidget(DeslizadorValores([str(n) for n in range(2, 6)], self.basico_var, lambda _v=None: self._refrescar_receta()), 1)
        self.basico_valor = Etiqueta(self.basico_var.get(), 14, peso='negrita', color='#FFFFFF')
        self.basico_valor.setFixedWidth(120)
        cb.addWidget(self.basico_valor)
        self.basico_var.observar(lambda: self.basico_valor.configure(text=str(self.basico_var.get())), self)
        Tooltip(self.basico_frame, tr('Cuántas palabras van juntas en cada bloque (de 2 a 5). Es el máximo que verás en pantalla, con un margen de una palabra cuando la frase lo pide. Manda en los subtítulos normales y en las palabras sueltas de los dinámicos.'))
        t.capa.addWidget(self.basico_frame)
        self.adelanto_var = StringVar('0')
        self.adelanto_frame, ca = caja_h(espacio=16)
        lbl = Etiqueta(tr('Aparecer antes'), 14, color='#E0EBFB')
        lbl.setFixedWidth(190)
        ca.addWidget(lbl)
        ca.addWidget(DeslizadorValores([str(n) for n in [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30]], self.adelanto_var), 1)
        self.adelanto_valor = Etiqueta('', 14, peso='negrita', color='#FFFFFF')
        self.adelanto_valor.setFixedWidth(120)
        ca.addWidget(self.adelanto_valor)
        def _poner_adelanto():
            self.adelanto_valor.configure(text=tr('{n} fotogramas', n=self.adelanto_var.get()))
        _poner_adelanto()
        self.adelanto_var.observar(_poner_adelanto, self)
        Tooltip(self.adelanto_frame, tr('Cuántos fotogramas antes de que se diga la palabra entra el bloque. Solo afecta a los bloques de 2 y 3 líneas; las palabras sueltas van siempre pegadas al habla.'))
        t.capa.addWidget(self.adelanto_frame)
        formato_row, cfo = caja_h(espacio=16)
        lbl = Etiqueta(tr('Formato del vídeo'), 14, color='#E0EBFB')
        lbl.setFixedWidth(190)
        cfo.addWidget(lbl)
        self.FORMATOS_VIDEO = {tr('Detectar solo'): None, tr('Horizontal'): 'h', tr('Vertical'): 'v'}
        self._etiqueta_de_formato = {v: k for k, v in self.FORMATOS_VIDEO.items()}
        self.formato_var = StringVar(tr('Detectar solo'))
        cfo.addWidget(Segmentado(list(self.FORMATOS_VIDEO.keys()), self.formato_var, lambda _v=None: self._refrescar_receta(), alto=38, tam=13))
        self.formato_detectado_lbl = Etiqueta('', FS_MENOR, color=TEXT_MUTED)
        cfo.addWidget(self.formato_detectado_lbl)
        cfo.addStretch(1)
        Tooltip(formato_row, tr('Qué versión del pack de estilos usar. «Detectar solo» mira la resolución del timeline; elígelo a mano si vas a recortar a otro formato después.'))
        self.formato_var.trace_add('write', lambda *_: self._refrescar_formato_detectado())
        t.capa.addWidget(formato_row)
        sfx_row, cs = caja_h(espacio=16)
        self.sfx_var = BooleanVar(False)
        self.sfx_check = Interruptor(tr('Efectos de sonido por palabra'), self.sfx_var, self._on_sfx_toggle, tam=14, color='#E8F1FF')
        cs.addWidget(self.sfx_check)
        self.sfx_fuente_lbl = Chip(tr('Elegir fuente'), ui.ACCENT_CLARO, self._cambiar_fuente_sfx, alto=28, tam=12)
        Tooltip(self.sfx_fuente_lbl, tr('De qué carpeta salen los efectos (Esenciales, una categoría, tu carpeta o favoritos). Suena uno en cada palabra.'))
        cs.addWidget(self.sfx_fuente_lbl)
        cs.addStretch(1)
        t.capa.addWidget(sfx_row)
        t.hide()
        self._tarjetas_ocultas.append(t)
        # Columna derecha: vista previa, receta, progreso
        t = Tarjeta(titulo=tr('Vista previa del estilo'), espacio=12)
        self.vista_estilo = MarcoVista(alto_min=220)
        self.vista_estilo.setFixedHeight(236)
        t.capa.addWidget(self.vista_estilo)
        self.chips_roles_w, crl = caja_h(espacio=8)
        for texto, color in [(tr('arriba'), ui.ROL_CONTEXTO), (tr('principal'), ui.ROL_PRINCIPAL), (tr('abajo'), ui.ROL_COMPLEMENTO), (tr('imagen'), ui.ROL_IMAGEN)]:
            crl.addWidget(Chip(texto, color, alto=26, tam=12))
        crl.addStretch(1)
        t.capa.addWidget(self.chips_roles_w)
        # v5.1: la vista previa sobre el fotograma real del timeline (MCP de Resolve 21.1+)
        fila_fondo, cff = caja_h(espacio=10)
        self.fondo_btn = Enlace(tr('Ver sobre el fotograma de Resolve'), self._fondo_desde_resolve, 13, color=ui.ACCENT_CLARO, color_hover='#FFFFFF', subrayada=False, peso='negrita')
        Tooltip(self.fondo_btn, tr('Trae el fotograma donde está el cabezal de tu timeline (conexión MCP, Resolve 21.1 o más nuevo) y dibuja el estilo encima.'))
        cff.addWidget(self.fondo_btn)
        cff.addStretch(1)
        t.capa.addWidget(fila_fondo)
        cd.addWidget(t)
        t = Tarjeta(titulo=tr('Receta'), espacio=10)
        self._receta = {}
        for clave, nombre in [('modo', tr('Modo')), ('pack', tr('Pack de estilos')), ('bloques', tr('Bloques estimados')), ('pistas', tr('Pistas')), ('colocacion', tr('Colocación'))]:
            fila, cf = caja_h(espacio=10)
            cf.addWidget(Etiqueta(nombre, 13, color=TEXT_MUTED))
            cf.addStretch(1)
            if clave == 'pack':
                valor = _EtiquetaPlantilla(tr('Diseño automático'), self._abrir_plantillas, 13, color='#FFFFFF', color_hover=ui.ACCENT_CLARO, subrayada=False, peso='medio')
                Tooltip(valor, tr('Clic: elegir el pack en «Estilos y composición».'))
                self.plantilla_lbl = valor
            else:
                valor = Etiqueta('—', 13, color='#FFFFFF', peso='medio')
            cf.addWidget(valor)
            self._receta[clave] = valor
            t.capa.addWidget(fila)
        cd.addWidget(t)
        t = Tarjeta(espacio=12)
        fila, cf = caja_h(espacio=10)
        self.status_var = StringVar(tr('Listo para empezar.'))
        self.status_label = Etiqueta(self.status_var.get(), 13, color='#C9D6EC', envolver=True)
        cf.addWidget(self.status_label, 1)
        self.porcentaje_lbl = Etiqueta('', 13, peso='negrita', color='#FFFFFF')
        cf.addWidget(self.porcentaje_lbl, 0, Qt.AlignmentFlag.AlignTop)
        self.time_label = Etiqueta('', 12, color=TEXT_MUTED)
        cf.addWidget(self.time_label, 0, Qt.AlignmentFlag.AlignTop)
        t.capa.addWidget(fila)
        self.progress = BarraProgreso(8)
        self.progress.set(0)
        t.capa.addWidget(self.progress)
        # v5.5: las etapas con nombre (no solo un porcentaje): la actual en color, las hechas en verde
        fila_e, cfe = caja_h(espacio=6)
        self._etapas = {}
        for clave, nombre in (('modelo', tr('Modelo')), ('transcribir', tr('Transcribir')), ('ia', tr('IA')), ('estilo', tr('Estilo')), ('resolve', tr('Resolve'))):
            chip = Chip(nombre, '#4F607A', None, alto=24, tam=11)
            self._etapas[clave] = chip
            cfe.addWidget(chip)
        cfe.addStretch(1)
        t.capa.addWidget(fila_e)
        botones, cb = caja_h(espacio=12, margenes=(0, 4, 0, 0))
        self.generate_btn = Boton(tr('Generar subtítulos'), self._on_generate, tipo='primario', alto=44, tam=15, negrita=True)
        cb.addWidget(self.generate_btn, 3)
        self.update_btn = Boton(tr('Editar marcas'), self._on_update, alto=44)
        Tooltip(self.update_btn, tr('Vuelve a abrir las marcas del último vídeo y regenera. No transcribe otra vez, así que es instantáneo.'))
        cb.addWidget(self.update_btn, 2)
        t.capa.addWidget(botones)
        cd.addWidget(t)
        self.status_var.observar(lambda: self.status_label.configure(text=str(self.status_var.get())), self)
    def _elegir_mosaico(self, clave):
        """Un clic en un mosaico de «Formato de los subtítulos»."""
        if clave in ('normal', 'dinamico'):
            self.modo_var.set(self._etiqueta_de_modo[clave])
        else:
            self.modo_var.set(self._etiqueta_de_modo['destacados'])
            self.look_var.set(self._etiqueta_de_look[clave])
        self._on_modo_change()
        self._guardar_preferencias()
    def _mosaico_actual(self):
        return self._look() if self._modo() == 'destacados' else self._modo()
    def _pintar_chips_idioma(self):
        """Los chips junto al idioma: ★ favoritos y los frecuentes."""
        capa = getattr(self, 'idiomas_chips', None)
        if capa is None:
            return
        limpiar_capa(capa)
        actual = self.lang_var.get()
        nombres = [n for n in self.favoritos_idiomas if n in LANG_CODE_BY_NAME]
        for codigo in ('es', 'en', 'pt', 'auto'):
            n = NOMBRE_POR_CODIGO.get(codigo)
            if n and n not in nombres and len(nombres) < 6:
                nombres.append(n)
        for n in nombres:
            corto = tr('Detectar solo') if LANG_CODE_BY_NAME.get(n) == 'auto' else n
            chip = Chip(corto, ui.ACCENT_CLARO if n == actual else TEXT_MUTED, lambda v=n: self._elegir_idioma(v), alto=28, tam=12,
                        lleno=n == actual, estrella=n in self.favoritos_idiomas)
            chip.setEnabled(self._entradas_activas)
            capa.addWidget(chip)
    def _elegir_idioma(self, nombre):
        self.lang_var.set(nombre)
        self._on_idioma_elegido()
    ETAPAS_ORDEN = ('modelo', 'transcribir', 'ia', 'estilo', 'resolve')
    def _poner_etapa(self, actual):
        """Pinta las etapas: las anteriores a 'actual' en verde, 'actual' rellena, el resto apagadas. None = todas apagadas; 'fin' = todas hechas."""
        chips = getattr(self, '_etapas', None)
        if not chips:
            return
        k = len(self.ETAPAS_ORDEN) if actual == 'fin' else (self.ETAPAS_ORDEN.index(actual) if actual in self.ETAPAS_ORDEN else -1)
        for i, clave in enumerate(self.ETAPAS_ORDEN):
            chip = chips[clave]
            if actual is None:
                color, lleno = '#4F607A', False
            elif i < k:
                color, lleno = '#22B573', False
            elif i == k:
                color, lleno = ui.ACCENT_CLARO, True
            else:
                color, lleno = '#4F607A', False
            chip._color = QColor(color)
            chip._lleno = lleno
            chip.update()
    @staticmethod
    def _etapa_de_estado(texto):
        t = (texto or '').lower()
        for clave, palabras in (('resolve', ('timeline', 'resolve', 'colocando', 'colocad', 'efectos de sonido', 'emoji')),
                                ('estilo', ('diseño', 'diseno', 'pack', 'estilo', 'generando con')),
                                ('ia', ('ia ', 'marcando', 'ortograf', 'corrig', 'roles', 'analiz')),
                                ('transcribir', ('transcrib',)),
                                ('modelo', ('modelo', 'preparando', 'cargando'))):
            if any(p in t for p in palabras):
                return clave
        return None
    def _refrescar_pasos(self):
        pasos = getattr(self, 'pasos', None)
        if pasos is None:
            return
        ruta = self.video_var.get().strip().strip('"')
        try:
            hay_fuente = bool(ruta) and Path(ruta).expanduser().is_file()
        except OSError:
            hay_fuente = False
        trabajando = self._trabajo_desde is not None or (self.worker is not None and self.worker.is_alive())
        if not hay_fuente:
            estados = ['actual', 'pendiente', 'pendiente', 'pendiente']
        elif self._generado_para and self._generado_para == ruta and not trabajando:
            estados = ['hecho', 'hecho', 'hecho', 'hecho']
        elif trabajando:
            estados = ['hecho', 'hecho', 'hecho', 'actual']
        else:
            estados = ['hecho', 'hecho', 'actual', 'pendiente']
        pasos.poner(estados)
        # v5.5: las insignias 1-2-3 de la tarjeta Audio: apagadas (pendiente), verdes (en curso) y rellenas con ✓ (hecho)
        hecho = {1: hay_fuente and getattr(self, '_meta_fuente', None) is not None, 2: estados[-1] == 'hecho' and hay_fuente}
        for n_i, lbl_i in getattr(self, '_insignias_audio', {}).items():
            try:
                if hecho.get(n_i):
                    lbl_i.setText('✓')
                    lbl_i.setStyleSheet(ui.traducir_hoja('QLabel { background-color: #22B573; border: 1px solid #22B573; border-radius: 13px; color: #06210F; }'))
                else:
                    lbl_i.setText(str(n_i))
                    pendiente = n_i > 1 and not hecho.get(n_i - 1)
                    lbl_i.setStyleSheet(ui.traducir_hoja('QLabel { background-color: #101826; border: 1px solid #2A3A58; border-radius: 13px; color: #6B7C99; }' if pendiente else 'QLabel { background-color: #12301F; border: 1px solid #22B573; border-radius: 13px; color: #6FE3AE; }'))
            except Exception:
                pass
    def _al_cambiar_video(self):
        try:
            self._refrescar_editor_vacio()          # Creativo se entera al instante del audio nuevo de Proyecto
        except Exception:
            pass
        cancelar(self._video_id)
        self._video_id = despues(300, self._medir_video_actual, self)
    def _medir_video_actual(self):
        """La tarjeta «Fuente»: nombre, duracion, tamaño y onda (en un hilo)."""
        self._video_id = None
        ruta = self.video_var.get().strip().strip('"')
        self._refrescar_pasos()
        if not ruta:
            self.insignia.setText('—')
            self.fuente_nombre.configure(text=tr('Ningún archivo elegido'))
            self.fuente_duracion.configure(text='--:--')
            self.fuente_meta.configure(text=tr('Pulsa «Obtener» para traer el audio de tu timeline de Resolve'), text_color=TEXT_MUTED)
            self.fuente_onda.poner_picos([])
            self._meta_fuente = None
            self._refrescar_receta()
            return
        p = Path(ruta).expanduser()
        self.insignia.setText((p.suffix[1:5] or '?').upper())
        self.fuente_nombre.configure(text=p.name)
        if not p.is_file():
            self.fuente_meta.configure(text=tr('No encuentro este archivo'), text_color=ui.ROJO)
            self.fuente_onda.poner_picos([])
            self._meta_fuente = None
            self._refrescar_receta()
            return
        if self._meta_fuente and self._meta_fuente.get('ruta') == ruta:
            return
        self.fuente_meta.configure(text=tr('Leyendo el archivo…'), text_color=TEXT_MUTED)
        def fin(info, error):
            if self.video_var.get().strip().strip('"') != ruta:
                return
            info = dict(info or {})
            info['ruta'] = ruta
            self._meta_fuente = info
            self._refrescar_pasos()
            partes = []
            if info.get('duracion'):
                partes.append(_duracion_legible(info['duracion']))
                try:
                    t_d = int(round(float(info['duracion'])))
                    self.fuente_duracion.configure(text=('%d:%02d:%02d' % (t_d // 3600, t_d % 3600 // 60, t_d % 60)) if t_d >= 3600 else ('%d:%02d' % (t_d // 60, t_d % 60)))
                except Exception:
                    pass
            w, h = (info.get('ancho') or 0, info.get('alto') or 0)
            if w and h:
                partes.append(f'{w}×{h}')
                partes.append(tr('formato detectado: {f}', f=plantillas.ETIQUETA_FORMATO.get(plantillas.formato_de(w, h), '?')))
            elif info.get('audio'):
                partes.append(tr('solo audio'))
            if error is not None and not partes:
                partes.append(tr('No pude leer el archivo ({name})', name=type(error).__name__))
            self.fuente_meta.configure(text=' · '.join(partes), text_color=TEXT_MUTED)
            self.fuente_onda.poner_picos(info.get('picos') or [])
            self._refrescar_receta()
        _correr_en_hilo(self, lambda: _medir_fuente(p), fin)
    def _refrescar_vista_estilo(self):
        vista = getattr(self, 'vista_estilo', None)
        if vista is None:
            return
        modo = self._modo()
        formato = self._formato_en_juego()
        roles_vis = False
        if modo == 'dinamico':
            nombre = self.plantilla_sel
            if nombre not in ('media_pool', '', None, 'dinamico') and nombre not in _CACHE_ESTILOS:
                if nombre not in self._calentando:
                    self._calentando.add(nombre)
                    _correr_en_hilo(self, lambda n=nombre: estilos_de_pack(n), lambda _r, _e: self._refrescar_vista_estilo())
                lineas = lineas_de_vista(None, formato)
            else:
                lineas = lineas_de_vista(nombre if nombre != 'dinamico' else None, formato)
            roles_vis = True
        elif modo == 'normal':
            lineas = [(tr('Así se ve un subtítulo normal'), {'familia': 'Montserrat', 'peso': 'SemiBold', 'tam': 0.1, 'color': '#FFFFFF'})]
        else:
            lineas = _lineas_look(self._look())
        imagen = None
        if roles_vis:
            try:
                imagen = dict(plantillas.bloque_imagen(self.plantilla_sel, formato), pix=None)
            except Exception:
                imagen = {'donde': 'abajo', 'zoom': 1.0, 'pix': None}
        vista.poner(lineas, imagen=imagen)
        self.chips_roles_w.setVisible(roles_vis)
    def _fondo_desde_resolve(self):
        """«Ver sobre el fotograma de Resolve»: el fotograma del cabezal, por
        MCP (~50 ms dentro de Resolve), de fondo en la vista previa."""
        if self.vista_estilo.tiene_fondo():
            self.vista_estilo.poner_fondo(None)
            self.fondo_btn.configure(text=tr('Ver sobre el fotograma de Resolve'))
            return
        self.fondo_btn.configure(text=tr('Trayendo el fotograma…'))
        def trabajo():
            import tempfile
            import resolve_mcp
            ruta = Path(tempfile.gettempdir()) / 'cinecaptions_fotograma.png'
            if resolve_mcp.exportar_fotograma(ruta) is None:
                raise RuntimeError(tr('No pude traer el fotograma: hace falta DaVinci Resolve 21.1 o más nuevo, abierto con un timeline.'))
            img = QImage(str(ruta))
            if img.isNull():
                raise RuntimeError(tr('Resolve dejó un fotograma que no se puede leer.'))
            return img.scaled(1280, 720, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        def fin(img, error):
            if not ui.vivo(self.fondo_btn):
                return
            if error is not None or img is None:
                self.fondo_btn.configure(text=tr('Ver sobre el fotograma de Resolve'))
                messagebox.showwarning(tr('Vista previa'), str(error), parent=self)
                return
            self.vista_estilo.poner_fondo(img)
            self.fondo_btn.configure(text=tr('Quitar el fotograma'))
        _correr_en_hilo(self, trabajo, fin)
    def _bloques_estimados(self):
        ruta = self.video_var.get().strip().strip('"')
        if not ruta:
            return '—'
        modo = self._modo()
        nombre = Path(ruta).expanduser().stem
        try:
            sello = ruta_marcas(nombre).stat().st_mtime
        except OSError:
            sello = None
        clave = (ruta, modo, self._palabras_por_basico(), sello, bool(self._meta_fuente))
        if self._cache_estimados and self._cache_estimados[0] == clave:
            return self._cache_estimados[1]
        texto = '—'
        guardadas = cargar_marcas(nombre) if sello is not None else None
        if guardadas and modo != 'destacados':
            palabras, roles = guardadas
            try:
                import dynamic_subtitles as dyn
                texto = str(len(dyn.build_manual_cues(palabras, roles if modo == 'dinamico' else [None] * len(palabras), palabras_por_basico=self._palabras_por_basico(), tamanos=self._tamanos_lineas(), peso_conector=getattr(self, 'peso_conectores', None))))
            except Exception:
                texto = '—'
        elif self._meta_fuente and self._meta_fuente.get('ruta') == ruta and self._meta_fuente.get('duracion'):
            palabras = float(self._meta_fuente['duracion']) * 2.4
            por = {'normal': float(self._palabras_por_basico()), 'dinamico': 3.2}.get(modo, 4.0)
            texto = f'~{max(1, round(palabras / por))}'
        self._cache_estimados = (clave, texto)
        return texto
    def _refrescar_receta(self):
        r = getattr(self, '_receta', None)
        if not r:
            return
        modo = self._modo()
        titulos = {c: t for c, t, _d in self.MOSAICOS}
        r['modo'].configure(text=titulos.get(self._mosaico_actual(), '—'))
        if modo == 'destacados':
            r['pack'].configure(text=tr('No aplica (look destacado)'))
        else:
            texto = self._etiqueta_plantilla_completa()
            formato = self._formato_en_juego()
            if modo == 'dinamico' and formato:
                texto = texto.rstrip().rstrip('>').rstrip() + f' · {formato.upper()}'
            r['pack'].configure(text=texto)
        r['bloques'].configure(text=self._bloques_estimados())
        sfx = bool(self.sfx_var.get()) and modo != 'normal'
        if modo == 'normal':
            pistas = tr('1 de subtítulos') + (tr(' + 1 traducida') if self.translate_var.get() else '')
        elif modo == 'dinamico':
            pistas = tr('3 de vídeo') + (tr(' + 1 de audio SFX') if sfx else '')
        else:
            pistas = tr('1 de vídeo') + (tr(' + 1 de audio SFX') if sfx else '')
        r['pistas'].configure(text=pistas)
        estado = self._estado_sistema.get('modo')
        r['colocacion'].configure(text={'mcp': tr('Automática en Resolve'), 'studio': tr('Automática en Resolve'), 'puente': tr('Automática en Resolve'), 'manual': tr('Un clic en Resolve (CineCaptions_Subtitulos)')}.get(estado, '—'))
        self._refrescar_pasos()
    # -- Editor de palabras ----------------------------------------------------
    def _pagina_editor(self):
        _pag, capa = self._nueva_pagina('editor', tr('Retocar las palabras'), tr('Pinta cada palabra con su rol; el bloque se arma solo'), desplazable=False)
        self._editor_capa = capa
        self._editor_vacio = QWidget()
        cv = QVBoxLayout(self._editor_vacio)
        cv.setContentsMargins(0, 40, 0, 0)
        t = Tarjeta(margenes=(36, 32, 36, 32), espacio=12)
        t.setMaximumWidth(640)
        t.setMinimumHeight(236)   # el texto largo con salto de línea dejaba los botones cortados
        # v5.3.2: esta tarjeta MIRA lo que hay en Proyecto (el audio traído de Resolve o el video elegido, y si ya tiene palabras transcritas / la línea de
        # tiempo abierta en Resolve) y se adapta sola; si ya hay palabras, el editor se abre solo al entrar (ver _refrescar_editor_vacio)
        self._ev_titulo = Etiqueta(tr('No hay ninguna sesión abierta'), 20, peso='extra', color='#FFFFFF')
        t.capa.addWidget(self._ev_titulo)
        self._ev_texto = Etiqueta(tr('Se abre solo después de transcribir con GO. Para retocar un video ya transcrito, pulsa «Editar marcas»: no se vuelve a transcribir.'), 14, color=TEXT_MUTED, envolver=True)
        t.capa.addWidget(self._ev_texto)
        self._ev_detalle = Etiqueta('', 13, color=ui.ACCENT_CLARO, envolver=True)
        t.capa.addWidget(self._ev_detalle)
        t.capa.addSpacing(8)
        fila, cf = caja_h(espacio=12)
        self.editar_btn2 = Boton(tr('Editar marcas del video elegido'), self._on_update, tipo='primario', alto=42)
        cf.addWidget(self.editar_btn2)
        self._ev_btn2 = Boton(tr('Ir a Proyecto'), lambda: self.ir_a('estilos'), alto=42)
        cf.addWidget(self._ev_btn2)
        cf.addStretch(1)
        t.capa.addWidget(fila)
        cv.addWidget(t, 0, Qt.AlignmentFlag.AlignHCenter)
        cv.addStretch(1)
        capa.addWidget(self._editor_vacio, 1)
    # -- v5.3.2: Creativo detecta solo el audio / la línea de tiempo de Proyecto ----------------------------------------
    def _estado_creativo(self):
        """Qué hay disponible para retocar, SIN tocar Resolve ni leer archivos grandes (corre en el hilo de la interfaz):
        ('ocupado'|'marcas'|'audio'|'timeline'|'nada', nombre_del_audio, nombre_de_la_linea_de_tiempo, nombre_del_proyecto_de_Resolve)."""
        try:
            ruta = self.video_var.get().strip().strip('"')
        except Exception:
            ruta = ''
        p = Path(ruta).expanduser() if ruta else None
        hay_audio = bool(p) and p.is_file()
        mcp = (getattr(self, '_estado_sistema', None) or {}).get('mcp') or {}
        tl = str(mcp.get('timeline') or '') if mcp.get('conectado') else ''
        proy = str(mcp.get('proyecto') or '') if mcp.get('conectado') else ''
        trabajando = getattr(self, '_go_corriendo', False) or (getattr(self, 'worker', None) is not None and self.worker.is_alive())
        if trabajando:
            return ('ocupado', p.name if hay_audio else '', tl, proy)
        if hay_audio:
            try:
                tiene = ruta_marcas(p.stem).is_file()
            except Exception:
                tiene = False
            return ('marcas' if tiene else 'audio', p.name, tl, proy)
        if tl:
            return ('timeline', '', tl, proy)
        return ('nada', '', '', '')
    def _refrescar_editor_vacio(self):
        """Pone en la tarjeta «sin sesión» de Creativo lo que de verdad hay: el audio de Proyecto, si ya tiene palabras, o la línea de tiempo abierta."""
        if getattr(self, '_editor', None) is not None or not hasattr(self, '_ev_titulo'):
            return
        modo, nombre, tl, proy = self._estado_creativo()
        detalle = ''
        if nombre:
            detalle += tr('Audio: «{n}»', n=nombre)
        if tl:
            detalle += ('   ·   ' if detalle else '') + tr('Resolve: «{t}»', t=tl) + (tr(' (proyecto «{p}»)', p=proy) if proy else '')
        b1, b2 = self.editar_btn2, self._ev_btn2
        b2.configure(text=tr('Ir a Proyecto'))
        b2.poner_comando(lambda: self.ir_a('estilos'))
        b1.setVisible(True)
        b1.configure(state='normal')
        if modo == 'ocupado':
            titulo, texto = tr('Transcribiendo…'), tr('En cuanto termine la transcripción, el editor se abre solo con todas las palabras para que pintes su rol.')
            b1.setVisible(False)
        elif modo == 'marcas':
            titulo = tr('Audio detectado en Proyecto')
            texto = tr('Ya está transcrito y tiene tus marcas guardadas: retócalas aquí. No se vuelve a transcribir.')
            b1.configure(text=tr('Retocar las palabras'))
            b1.poner_comando(self._on_update)
        elif modo == 'audio':
            titulo = tr('Audio detectado en Proyecto')
            texto = tr('Todavía no está transcrito. Se transcribe y el editor se abre solo para que pintes cada palabra.')
            b1.configure(text=tr('Transcribir y retocar'))
            b1.poner_comando(self._on_generate)
        elif modo == 'timeline':
            titulo = tr('Hay una línea de tiempo abierta en Resolve')
            texto = tr('Trae su audio, se transcribe y el editor se abre solo. También puedes pulsar GO en Inicio.')
            b1.configure(text=tr('Traer el audio de Resolve'))
            b1.poner_comando(lambda: self._detectar_desde_resolve(silencioso=False))
        else:
            titulo = tr('No hay ninguna sesión abierta')
            texto = tr('Aún no hay audio. En Proyecto pulsa «Obtener» (o suelta un video en la ventana) y vuelve aquí: lo detecto solo. Con GO todo se hace en un clic.')
            b1.setVisible(False)
        self._ev_titulo.configure(text=titulo)
        self._ev_texto.configure(text=texto)
        self._ev_detalle.configure(text=detalle)
        self._ev_detalle.setVisible(bool(detalle))
        return modo
    def _vigilar_editor_vacio(self):
        """Mientras Creativo está a la vista sin sesión, la tarjeta se mantiene al día (el audio llega, termina un GO, Resolve cambia de timeline...)."""
        if not vivo(self) or self._pagina_actual != 'editor' or getattr(self, '_editor', None) is not None:
            self._ev_vigia = False
            return
        self._refrescar_editor_vacio()
        despues(1500, self._vigilar_editor_vacio, self)
    def _al_entrar_en_creativo(self):
        """Al abrir Creativo sin sesión: se refresca la tarjeta y, si el audio de Proyecto YA tiene palabras, el editor se abre solo."""
        if getattr(self, '_editor', None) is not None:
            return
        modo = self._refrescar_editor_vacio()
        if not getattr(self, '_ev_vigia', False):
            self._ev_vigia = True
            despues(1500, self._vigilar_editor_vacio, self)
        if modo == 'marcas':
            despues(350, self._abrir_editor_solo, self)
    def _abrir_editor_solo(self):
        if not vivo(self) or self._pagina_actual != 'editor' or getattr(self, '_editor', None) is not None:
            return
        if self._estado_creativo()[0] != 'marcas':
            return
        registro.info('Creativo: el audio de Proyecto ya tiene palabras; abro el editor solo.', 'creativo')
        self._on_update()
    def _sesion_editor(self, ventana, volver='nuevo'):
        """Muestra el editor como pantalla, espera a «Continuar» o
        «Cancelar» (ventana.esperar) y lo retira. Devuelve su resultado."""
        self._editor = ventana
        self._editor_vacio.hide()
        self._editor_capa.addWidget(ventana, 1)
        try:
            ventana.ajustar_densidad(getattr(self, '_densidad', 0) or 0)
        except Exception:
            pass
        t, s = self._cabeceras['editor']
        t.configure(text=ventana.titulo())
        s.configure(text=ventana.subtitulo())
        self.ir_a('editor')
        elegido = None
        try:
            resultado = ventana.esperar()
            elegido = getattr(ventana, '_proyecto_elegido', None)
        finally:
            self._editor = None
            try:
                ventana.hide()
                self._editor_capa.removeWidget(ventana)
                ventana.setParent(None)
                ventana.deleteLater()
            except Exception:
                pass
            self._editor_vacio.show()
            t.configure(text=tr('Retocar las palabras'))
            s.configure(text=tr('Pinta cada palabra con su rol; el bloque se arma solo'))
            if vivo(self) and self.isVisible():
                self.ir_a(volver)
        if elegido:
            self._cargar_proyecto(elegido)
            self.status_var.set(tr('Proyecto cargado: {nombre}', nombre=Path(elegido).name))
        if resultado is not None:
            self._receta_generar()
        return resultado
    # -- v5.7: el popup de «Generar» del editor ---------------------------------------
    def _receta_generar(self):
        """«Generar» del editor hace lo mismo que GO: bloques con tus marcas, efectos de sonido (el interruptor de GO), emojis y colocarlo en
        Resolve, con un popup de avance."""
        try:
            self.sfx_var.set(self._go_sfx())
        except Exception:
            pass
        if self._modo() == 'dinamico':
            self._asegurar_pack_luxe()
        self._gen_abrir()
    def _asegurar_pack_luxe(self):
        """v5.8 (pedido: «todos los textos plus deben ser del paquete Luxe Title Pack, sin excepción»): como GO, el dinámico se genera con un
        pack de verdad (el que ya uses si es un pack; si no, «Base títulos dinámicos»), nunca con el diseño automático ni un Text+ suelto."""
        nuevo = self._plantilla_un_clic()
        if nuevo == self.plantilla_sel:
            return
        self.plantilla_sel = nuevo
        try:
            self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        except Exception:
            pass
        self._guardar_preferencias()
    def _gen_abrir(self):
        import editor_ui
        self._gen_fin(False)
        claves = {'dinamico': ['armar', 'sfx', 'emojis', 'colocar'], 'destacados': ['armar', 'sfx', 'colocar']}.get(self._modo(), ['armar', 'colocar'])
        nombres = {'armar': tr('Armar los bloques con tus marcas'), 'sfx': tr('Elegir los efectos de sonido'), 'emojis': tr('Preparar los emojis'),
                   'colocar': tr('Colocar todo en tu timeline')}
        try:
            dlg = Dialogo(self, tr('Generando'), 500, 430, redimensionable=False)
            capa = _capa_dialogo(dlg, (0, 0, 0, 0), 0)
            panel = editor_ui.PanelAsistencia(tr('Generando tus subtítulos'), tr('Todo listo'), tr('Preparando…'), [nombres[c] for c in claves], '',
                                              tr('Subtítulos, sonidos y emojis, directo a tu timeline'))
            capa.addWidget(panel, 1)
            dlg.show()
        except Exception:
            registro.excepcion(origen='Generar · popup')
            return
        g = {'dlg': dlg, 'panel': panel, 'claves': claves}
        self._gen = g
        despues(300000, lambda: self._gen_fin(False) if getattr(self, '_gen', None) is g else None, self)      # por si algo no avisa nunca
    def _gen_fase(self, clave):
        g = getattr(self, '_gen', None)
        if g and vivo(g['dlg']) and clave in g['claves']:
            g['panel'].poner_fase(g['claves'].index(clave))
    def _gen_detalle(self, texto):
        g = getattr(self, '_gen', None)
        if g and vivo(g['dlg']):
            g['panel'].poner_detalle(str(texto).strip()[:150])
    def _gen_fin(self, ok, detalle=''):
        g = getattr(self, '_gen', None)
        self._gen = None
        if not g or not vivo(g['dlg']):
            return
        if ok:
            g['panel'].terminar(detalle)
            despues(1300, g['dlg'].cerrar, self)
        else:
            g['dlg'].cerrar()
    def _editor_abierto(self):
        """Una sola sesion del editor a la vez (la v4 lo garantizaba con el
        modal; ahora el resto de pantallas sigue a mano)."""
        if self._editor is None:
            return False
        messagebox.showinfo(tr('El editor está abierto'), tr('Termina o cancela primero la sesión del editor de palabras.'), parent=self)
        self.ir_a('editor')
        return True
    # -- Estilos y composición -------------------------------------------------
    def _pagina_estilos(self):
        _pag, capa = self._nueva_pagina('estilos', tr('Elegir audio y tema') if plantillas.SOLO_TEMAS else tr('Elegir audio y estilo'),
                                        tr('Obtén el audio de tu timeline, elige un tema y mira cómo queda') if plantillas.SOLO_TEMAS
                                        else tr('Obtén el audio de tu timeline, elige el pack de estilos y mira cómo queda cada estilo en tu bloque'), desplazable=False)
        self._estilos_capa = capa                     # v5.4.3: la página NO se desplaza: todo cabe y el slider se lleva el alto que sobra
        # el audio («Fuente», se construye en _pagina_nuevo) va dentro de la tarjeta de «Pack de estilos» (ver _asegurar_estilos)
    def _cambio_motor_voz(self, _v=None):
        motor = self._motores_voz.get(self.motor_var.get(), 'qwen3')
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'motor_voz': motor})
        except Exception:
            pass
        self._pintar_motor_voz()
    def _pintar_motor_voz(self):
        """La nota bajo el selector: qué se va a usar de verdad (GPU, modelo, o por qué cae a Whisper)."""
        motor = self._motores_voz.get(self.motor_var.get(), 'qwen3')
        try:
            import motor_voz
            info = motor_voz.info_instalado() or {}
            if motor == 'qwen3':
                if motor_voz.instalado():
                    texto = tr('Qwen3-ASR {m} · {d}', m=info.get('modelo') or '1.7B', d=info.get('gpu') or 'CPU')
                else:
                    texto = tr('Qwen3-ASR no está instalado (Ajustes > General): se usará Whisper.')
            else:
                texto = tr('Whisper large-v3-turbo · usa la GPU si hay CUDA')
        except Exception:
            texto = ''
        self.motor_nota.configure(text=texto)
        try:
            Tooltip(self.motor_seg, tr('Qué motor convierte la voz en palabras con su tiempo. La IA (Qwen3-ASR) usa la GPU y es la más fina; Whisper large-v3-turbo es el de respaldo y entiende 99 idiomas.') + '\n\n' + texto)
        except Exception:
            pass
    def _menu_audio(self):
        """Clic derecho sobre «Audio»: lo que ya no tiene botón (elegir un archivo a mano, proyectos guardados)."""
        menu = Menu(self)
        menu.agregar(tr('Elegir un archivo…'), self._browse)
        menu.agregar(tr('Proyectos guardados'), self._abrir_proyectos_guardados_main)
        menu.mostrar(QCursor.pos())
    def _crear_tu_estilo(self, ids=None):
        """«Crea tu estilo»: abre en Resolve (por MCP) el timeline-guía con la estructura de un pack: los bloques
        arriba · principal · abajo uno encima del otro. Con 'ids' (el botón «Vista real · Resolve» de una tarjeta) carga SOLO esos ejemplos."""
        if getattr(self, '_creando_estilo', False):
            return
        import ejemplos_estilo
        solo = [int(i) for i in ids] if ids else None
        uno = ejemplos_estilo.por_id(solo[0]) if solo and len(solo) == 1 else None
        nombre_tl = f"Estilo \u00b7 {uno['nombre']}" if uno else 'Crea tu estilo'
        guia = BASE_RECURSOS / 'guia_estilo' / 'construir_guia.py'
        bloques = BASE_RECURSOS / 'guia_estilo' / 'Crea tu estilo.drb'
        if not guia.is_file() or not bloques.is_file():
            messagebox.showwarning(tr('Crea tu estilo'), tr('No encuentro la guía incluida:\n{ruta}', ruta=guia), parent=self)
            return
        self._creando_estilo = True
        if uno:
            self.status_var.set(tr('Cargando «{n}» en la línea de tiempo de Resolve…', n=ejemplos_estilo.nombre_visible(uno)))
        else:
            self.status_var.set(tr('Armando la guía «Crea tu estilo» en Resolve (48 ejemplos, unos segundos)…'))
        def trabajo():
            import resolve_mcp
            prep = resolve_mcp.preparar_resolve(abrir=True, al_estado=lambda t: self.msg_queue.put(('status', t)))
            if not prep.get('ok'):
                return (False, prep.get('motivo') or tr('No pude preparar Resolve.'))
            return resolve_mcp.abrir_guia(guia, nombre_tl, ejemplos_estilo.datos_guia(bloques, amro=bloques.with_name('Amro principales.drb'), solo=solo))
        def fin(resultado, error):
            self._creando_estilo = False
            if not vivo(self):
                return
            ok, mensaje = resultado if (resultado and not error) else (False, str(error or ''))
            if ok and uno:
                self.status_var.set(tr('«{n}» está cargado en la línea de tiempo de Resolve: solo ese estilo. Retócalo, ponle el nombre exacto y exporta el timeline (.drt).', n=ejemplos_estilo.nombre_visible(uno)))
                import ui_toast
                ui_toast.mostrar(self, tr('«{n}» está en la línea de tiempo de Resolve', n=ejemplos_estilo.nombre_visible(uno)))
            elif ok:
                self.status_var.set(tr('Timeline «Crea tu estilo» listo en Resolve: 48 ejemplos con Luxe Shine, Luxe Slide y Amro. Quédate con los que quieras, ponles el nombre exacto y exporta el timeline (.drt).'))
                import ui_toast
                ui_toast.mostrar(self, tr('La guía «Crea tu estilo» está abierta en Resolve'))
            else:
                self.status_var.set(tr('No pude abrir la guía: {m}', m=mensaje))
                messagebox.showwarning(tr('Crea tu estilo'), tr('No pude armar la guía en Resolve: {m}', m=mensaje), parent=self)
        _correr_en_hilo(self, trabajo, fin)
    def _basicos_actual(self):
        return f'{self.basicos_pack}||{self.basicos_sel}' if self.basicos_sel else ''
    def _vistas_reales_solas(self):
        """v5.4.4: ya no hay botón «Vista real · Resolve»: con Resolve conectado, las vistas que falten se piden solas (silencioso: no abre Resolve)."""
        try:
            import resolve_mcp
            if (self._plantillas_ventana is not None and getattr(self, '_recorrido', None) is None
                    and resolve_mcp.estado_cacheado().get('conectado')):
                despues(1200, lambda: self._plantillas_ventana._renderizar_reales(silencioso=True), self)
        except Exception:
            pass
    def _asegurar_estilos(self):
        if self._plantillas_ventana is not None:
            self._vistas_reales_solas()
            return
        cuerpo, cc = caja_h(espacio=20)
        self._plantillas_ventana = PlantillasWindow(self, seleccion=self.plantilla_sel, on_elegir=self._plantilla_elegida, on_importar=self._importar_estilos, on_importar_drt=self._importar_estilos_drt, formato=self._formato_en_juego(), diseno_actual=getattr(self, 'diseno_dinamico', None), on_diseno=self._plantilla_diseno, basicos_actual=self._basicos_actual(), on_basicos=self._plantilla_basicos, modo=self._modo(), franja=self._tarjeta_fuente)
        cc.addWidget(self._plantillas_ventana, 8)
        # v5.2: con Resolve conectado, las vistas reales que falten se renderizan solas
        try:
            import resolve_mcp
            if resolve_mcp.estado_cacheado().get('conectado') and getattr(self, '_recorrido', None) is None:      # (con el recorrido en pantalla se aplaza)
                despues(1200, lambda: self._plantillas_ventana._renderizar_reales(silencioso=True), self)
        except Exception:
            pass
        if COMPOSICION_VISIBLE:
            self._composicion_ventana = ComposicionWindow(self)
            self._composicion_ventana.poner_habilitado(self._modo() != 'normal')
            cc.addWidget(self._composicion_ventana, 5, Qt.AlignmentFlag.AlignTop)
        self._estilos_capa.addWidget(cuerpo, 1)
        # en Proyecto la rueda del ratón mueve el slider de packs en cualquier punto de la pantalla (la página ya no se desplaza)
        self._rueda_estilos = ui.RuedaHacia(self._paginas['estilos'], lambda ev: self._plantillas_ventana is not None and self._plantillas_ventana.carrusel.desplazar_con_rueda(ev))
    def _plantilla_elegida(self, valor):
        self.plantilla_sel = valor
        self._sincronizar_go_pack(valor)          # auditoría v5.11: el pack de Estilos y el chip «Estilo» de Inicio son UNA sola elección
        self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        self._guardar_preferencias()
        self._pintar_opciones_go()
        self._refrescar_vista_estilo()
        self._refrescar_receta()
        comp = self._composicion_ventana
        if comp is not None and comp.existe():
            comp._recalcular_vistas()
    def _plantilla_diseno(self, d):
        self.diseno_dinamico = d
        self.plantilla_sel = 'dinamico'
        self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        self._guardar_preferencias()
        self._refrescar_receta()
    def _plantilla_basicos(self, valor):
        pack_n, _, combinacion = (valor or '').partition('||')
        if combinacion:
            self.basicos_pack = pack_n or plantillas.NOMBRE_BASICOS
            self.basicos_sel = combinacion
        else:
            self.basicos_sel = ''
        self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        self._guardar_preferencias()
        self._refrescar_receta()
    # -- SFX Lab ---------------------------------------------------------------
    def _pagina_sfx(self):
        _pag, capa = self._nueva_pagina('sfx', tr('Elegir y retocar sonidos'), tr('Elige el sonido de cada momento, recórtalo y ajusta su volumen · se aplica al generar con GO'))
        self._sfx_capa = capa
    # -- Efectos visuales (v5.4.6): intro, transiciones en los cortes e iconos flotantes -------------------------------------------------------------------
    def _pagina_efectos(self):
        _pag, capa = self._nueva_pagina('efectos', tr('Efectos visuales'), tr('Intro, transiciones en los cortes e iconos flotantes que acompañan a los captions · se aplican al generar con GO'))
        self._efectos_capa = capa
        self._efectos_widget = None
    def _asegurar_efectos(self):
        """Arma la página Efectos la primera vez que se abre (lee las vistas previas); las demás veces solo sincroniza su interruptor."""
        if self._efectos_widget is not None:
            self._efectos_widget.refrescar()
            return True
        try:
            import efectos_pagina
            self._efectos_widget = efectos_pagina.PaginaEfectos(self, al_cambiar=self._pintar_opciones_go)
            self._efectos_capa.addWidget(self._efectos_widget)
        except Exception:
            self._efectos_widget = None
            registro.excepcion(origen='página Efectos')
            return False
        return True
    def _asegurar_sfx(self):
        """Arma el SFX Lab la primera vez (av/numpy solo si se usa)."""
        if self._estudio_ventana is not None:
            try:
                self._estudio_ventana.poner_video(self.video_var.get().strip().strip('"') or None)
            except Exception:
                pass
            return True
        try:
            import sfx_rules
            import sfx_studio
        except Exception as e:
            messagebox.showerror(tr('No pude abrir el estudio'), tr('Falta algo para poder abrir el estudio de sonidos:\n\n{name}: {e}', name=type(e).__name__, e=e), parent=self)
            return False
        biblioteca = sfx_rules.carpeta_libreria()
        if not biblioteca.is_dir():
            messagebox.showwarning(tr('No hay biblioteca de sonidos'), tr('No encuentro la carpeta:\n{biblioteca}\n\nSin ella no hay sonidos para retocar.', biblioteca=biblioteca), parent=self)
            return False
        video = self.video_var.get().strip().strip('"') or None
        try:
            self._estudio_ventana = sfx_studio.SfxStudio(self, biblioteca, video_actual=video, carpeta_scripts_resolve=self._carpeta_scripts_resolve(), origen_scripts_resolve=BASE_RECURSOS / 'resolve_scripts')
        except Exception as e:
            self._estudio_ventana = None
            log = guardar_log_de_error(traceback.format_exc())
            msg = tr('El estudio no pudo abrirse:\n\n{name}: {e}', name=type(e).__name__, e=e)
            if log:
                msg += f'\n\nDetalle en:\n{log}'
            messagebox.showerror(tr('Algo salio mal'), msg, parent=self)
            return False
        self._sfx_capa.addWidget(self._estudio_ventana, 1)
        return True
    # -- logica (la de la v4.1.0) ---------------------------------------------
    def _tamanos_lineas(self):
        """(arriba, principal, abajo): el maximo de palabras por linea de «Tamaño del bloque» (Creativo). Los bloques lo respetan siempre."""
        import dynamic_subtitles as dyn
        return dyn.normalizar_tamanos(getattr(self, 'tamanos_grupo', None))
    def _palabras_por_basico(self):
        """Cuantas palabras sueltas van juntas en un bloque, en 2..5.

        v1.0.69: el rango pedido es 2-5; una preferencia vieja con 1 (o
        cualquier valor raro) cae aqui a los limites, sin tocar el json.
        """
        try:
            return min(5, max(2, int(self.basico_var.get())))
        except (ValueError, AttributeError):
            return 2
    def _preparar_emojis(self, bloques, palabras, roles=None):
        """Los emojis de las palabras clave (v3.3.0): los pasa de las
        palabras a sus bloques (cue['emoji'] + cue['emoji_linea']), mide el
        ancho de esa linea con la tipografia del pack elegido (v3.3.1,
        emojis.medir_anchos_emoji: el gemelo lo pone al FINAL de la linea) y
        devuelve las claves del track ({'emojis': {id: ruta}}) o {}. Lo
        que no se pudo medir se DICE en el estado (sale encima del bloque,
        como en la v3.3.0); nunca se pierde un emoji. Un fallo aqui NO
        puede tumbar la generacion: sin emojis, todo lo demas sale igual."""
        try:
            import emojis
            total = emojis.asignar(bloques, palabras, roles)
            if not total:
                return {}
            origenes = {}
            for b in bloques:
                if b.get('emoji'):
                    o = emojis.origen_de(b['emoji'])[0] or 'fluent'
                    origenes[o] = origenes.get(o, 0) + 1
            nombres = {'sistema': tr('del sistema'), 'usuario': tr('tuyos'), 'fluent': 'Fluent'}
            detalle = ', '.join((f'{n} {nombres.get(o, o)}' for o, n in sorted(origenes.items())))
            aviso = tr('Emojis: {n} en el bloque «imagen» o debajo del texto ({detalle}).', n=total, detalle=detalle)
            try:
                self.msg_queue.put(('status', aviso))
            except Exception:
                pass
            try:
                import ajustes_ui
                eleccion = str(ajustes_ui.leer_prefs().get('emoji_posicion') or '')
            except Exception:
                eleccion = ''
            forzar = eleccion in ('abajo', 'arriba')
            if forzar:
                # si el pack ya pone el icono donde se pidio, manda su bloque «imagen» (posicion y tamaño exactos)
                try:
                    info = plantillas.bloque_imagen(self.plantilla_sel, None)
                    if info.get('bloque') and info.get('donde') == eleccion:
                        forzar = False
                except Exception:
                    pass
            donde = 'abajo'
            try:
                donde = plantillas.bloque_imagen(self.plantilla_sel, None).get('donde') or 'abajo'            # el emoji del Tema 4 va ARRIBA del texto
            except Exception:
                pass
            return emojis.para_manifiesto(bloques, eleccion if eleccion in ('abajo', 'arriba') else donde, forzar=forzar, fps=getattr(self, '_fps_timeline', None))
        except Exception:
            return {}
    def _sfx_de_emojis(self, bloques, pista_sfx):
        """v5.7: cada emoji suena (fuego → fuego, beso → beso…). Suma un evento de sonido por bloque con emoji y devuelve la pista de efectos
        (con la categoría «Emojis»). Un fallo aquí NO tumba la generación: sin sonidos de emojis, todo lo demás sale igual."""
        try:
            import emojis_sfx
            n, pista = emojis_sfx.agregar_eventos(bloques, pista_sfx)
            if n:
                self.msg_queue.put(('status', tr('Sonidos de emojis: {n}.', n=n)))
            return pista
        except Exception:
            registro.excepcion(origen='Sonidos de emojis')
            return pista_sfx
    def _capitalizar(self):
        """«Mayúscula inicial» de los dinamicos (v3.3.0; desde la v3.3.1 es
        la casilla de la VENTANA de palabras, que escribe self.capitalizar).

        Ante cualquier rareza (un doble de prueba sin el atributo) devuelve
        True: lo de siempre.
        """
        try:
            return getattr(self, 'capitalizar', True) is not False
        except Exception:
            return True
    def _menu_idiomas(self):
        """El desplegable de esta instancia: ★ favoritos arriba, y el resto.

        Se arma al vuelo y no de una constante porque los favoritos cambian
        en caliente. Los favoritos NO se quitan de su seccion de origen:
        quitar "Español" de los frecuentes por estar en favoritos haria que
        quien lo busca donde siempre no lo encuentre.
        """
        favoritos = [n for n in self.favoritos_idiomas if n in LANG_CODE_BY_NAME]
        if not favoritos:
            return LANG_MENU
        return favoritos + [SEPARADOR_FAVORITOS] + LANG_MENU
    def _alternar_favorito(self):
        nombre = self.lang_var.get()
        if nombre not in LANG_CODE_BY_NAME:
            return
        if nombre in self.favoritos_idiomas:
            self.favoritos_idiomas.remove(nombre)
        else:
            self.favoritos_idiomas.append(nombre)
        self._refrescar_estrella()
        try:
            self.lang_menu.configure(values=self._menu_idiomas())
        except Exception:
            pass
        self._guardar_preferencias()
    def _refrescar_estrella(self):
        try:
            es_fav = self.lang_var.get() in self.favoritos_idiomas
            icono = ui.icono_linea('ph.star-fill' if es_fav else 'ph.star', '#FFD166' if es_fav else '#C9D6EC')
            if icono is not None:
                self.fav_btn.setIcon(icono)
                self.fav_btn.setIconSize(QSize(18, 18))
                self.fav_btn.configure(text='')
            else:
                self.fav_btn.configure(text='★' if es_fav else '☆')
                self.fav_btn.setStyleSheet('QPushButton { color: #FFD166; }' if es_fav else '')
        except Exception:
            pass
        self._pintar_chips_idioma()
    def _on_idioma_elegido(self, valor=None):
        """Los separadores del desplegable no son idiomas: se ignoran."""
        if self.lang_var.get() in (SEPARADOR_IDIOMAS, SEPARADOR_FAVORITOS):
            self.lang_var.set(self._ultimo_idioma)
            self._refrescar_estrella()
        else:
            self._refrescar_estrella()
            if self.lang_var.get() in LANG_CODE_BY_NAME:
                self._ultimo_idioma = self.lang_var.get()
            self._refrescar_destinos()
    def _filtrar_idiomas(self, evento=None):
        """Con 99 idiomas, escribir dos letras tiene que acortar la lista.
        v5.0.0: lo hace el propio desplegable (ComboBuscable, sin tildes)."""
        return None
    def _abrir_buscador_idioma(self):
        """La lupa del idioma de transcripcion (v1.0.68)."""
        nombres = list(dict.fromkeys(
            n for n in self._menu_idiomas()
            if n not in (SEPARADOR_IDIOMAS, SEPARADOR_FAVORITOS)))
        def al_elegir(nombre):
            self.lang_var.set(nombre)
            self._on_idioma_elegido()
        self._abrir_buscador(tr('¿En qué idioma se habla?'), nombres, al_elegir)
    def _abrir_buscador_destino(self):
        """La lupa del idioma destino de la traduccion (v1.0.68)."""
        try:
            nombres = list(self.destino_menu.cget('values'))
        except Exception:
            nombres = [NOMBRE_POR_CODIGO['en']]
        def al_elegir(nombre):
            self.destino_var.set(nombre)
            self._guardar_preferencias()
            self._refrescar_receta()
        self._abrir_buscador(tr('¿A qué idioma traduzco?'), nombres, al_elegir)
    def _abrir_buscador(self, titulo, nombres, al_elegir):
        ventana = BuscadorIdiomaWindow(self, titulo, nombres, al_elegir)
        try:
            ventana.exec()
        except Exception:
            return None
    def _on_traducir_toggle(self):
        if self.translate_var.get():
            self._refrescar_destinos()
        self._refrescar_receta()
    def _idioma_destino(self):
        """Codigo del idioma al que traducir. \'en\' si algo va raro."""
        return LANG_CODE_BY_NAME.get(self.destino_var.get(), 'en')
    def _refrescar_destinos(self):
        """Rellena el menu de destinos: lo instalado YA, y el catalogo
        completo de Argos en cuanto llega.

        Hasta la v1.0.31 solo se ofrecia lo instalado, y estrenar el
        programa dejaba un menu con solo "Inglés" — parecia que no se podia
        traducir a nada mas. Ahora se ofrece todo lo que Argos publica
        (directo o via ingles: el paquete que falte se descarga al
        generar). El catalogo se pide en un HILO porque la primera vez baja
        el indice de internet; sin red, queda lo instalado, como antes.
        """
        origen = self._codigo_idioma()
        def _nombres_de(destinos):
            return sorted((NOMBRE_POR_CODIGO[c] for c in destinos
                           if c != origen and c in NOMBRE_POR_CODIGO), key=_plegar)
        def _poner(nombres):
            if not nombres:
                nombres = [NOMBRE_POR_CODIGO['en']]
            try:
                self.destino_menu.configure(values=nombres)
                if self.destino_var.get() not in nombres:
                    ingles = NOMBRE_POR_CODIGO['en']
                    self.destino_var.set(
                        ingles if ingles in nombres else nombres[0])
            except Exception:
                pass
        try:
            instalados = lang_packs.paquetes_instalados()
        except Exception:
            instalados = []
        _poner(_nombres_de({p['to'] for p in instalados
                            if origen in ('auto', '') or p['from'] == origen}))
        if getattr(self, '_catalogo_argos', None) is not None:
            self._aplicar_catalogo_destinos(origen)
            return
        def _bajar():
            try:
                catalogo = lang_packs.paquetes_disponibles(refrescar=True)
            except Exception:
                catalogo = []
            def _en_ui():
                if not vivo(self):
                    return
                self._catalogo_argos = catalogo
                self._aplicar_catalogo_destinos(origen)
            ejecutar_en_ui(_en_ui)
        threading.Thread(target=_bajar, daemon=True).start()
    def _aplicar_catalogo_destinos(self, origen):
        """Con el catalogo en mano: destinos directos + alcanzables via en."""
        catalogo = self._catalogo_argos or []
        directos = {p['to'] for p in catalogo
                    if origen in ('auto', '') or p['from'] == origen}
        hay_a_en = origen in ('auto', '', 'en') or any(
            p['from'] == origen and p['to'] == 'en'
            for p in catalogo)
        via_en = ({p['to'] for p in catalogo if p['from'] == 'en'}
                  if hay_a_en else set())
        destinos = (directos | via_en | {'en'}) - {origen}
        nombres = sorted((NOMBRE_POR_CODIGO[c] for c in destinos
                          if c in NOMBRE_POR_CODIGO), key=_plegar)
        if not nombres:
            return
        try:
            self.destino_menu.configure(values=nombres)
            if self.destino_var.get() not in nombres:
                ingles = NOMBRE_POR_CODIGO['en']
                self.destino_var.set(
                    ingles if ingles in nombres else nombres[0])
        except Exception:
            pass
    def _abrir_idiomas_traduccion(self):
        ventana = IdiomasTraduccionWindow(self)
        try:
            ventana.exec()
        except Exception:
            return None
        self._refrescar_estado()
    def _fin_video(self):
        """Donde termina el medio transcrito, en segundos; None si no se sabe.

        v2.0.6: el ultimo bloque termina CON el video (dyn._cerrar_huecos).
        Se mide del archivo con PyAV (viaja con faster-whisper; leer la
        duracion no decodifica nada), asi que vale igual al generar y al
        regenerar, con el render de Resolve (con marcas: el tramo marcado)
        o con un archivo elegido a mano. Manda la pista de VIDEO si la hay
        (fotogramas exactos; la de audio puede traer relleno del codec);
        sin ella, el contenedor. Cualquier fallo -> None = hold de siempre.
        """
        try:
            import av
            ruta = self.video_var.get().strip().strip('"')
            with av.open(ruta) as contenedor:
                for pista in contenedor.streams.video:
                    if pista.duration and pista.time_base:
                        return float(pista.duration * pista.time_base)
                if contenedor.duration:
                    return float(contenedor.duration / av.time_base)
        except Exception:
            pass
        return None
    def _offset_frames(self):
        """El fotograma del timeline donde arranca lo transcrito.

        Sin marcas es el inicio del timeline (lo de siempre). Con marcas es
        la de entrada: el audio empieza ahi, asi que ahi tienen que empezar
        los subtitulos.

        Devuelve None cuando no hay nada que decir, y entonces el script de
        Resolve usa timeline:GetStartFrame() como hasta ahora. Esa es la
        diferencia entre "no toques nada" y "colocalo en el fotograma 0",
        que no es lo mismo: los timelines suelen arrancar en 01:00:00:00.
        """
        marca = getattr(self, '_marca_entrada', None)
        if marca is None:
            return
        try:
            return max(0, int(marca))
        except (TypeError, ValueError):
            return None
    def _zona_marcada_legible(self):
        """La zona marcada en timecode, para enseñarsela al usuario."""
        ini = getattr(self, '_marca_entrada', None)
        fin = getattr(self, '_marca_salida', None)
        fps = getattr(self, '_fps_timeline', 0.0) or 0.0
        base = getattr(self, '_inicio_timeline', 0) or 0
        if ini is None or fin is None:
            return ''
        if fps <= 0:
            return f'fotogramas {ini} a {fin}'
        def tc(frame):
            total = max(0, int(frame) - int(base))
            seg, f = divmod(total, max(1, int(round(fps))))
            h, resto = divmod(seg, 3600)
            m, s = divmod(resto, 60)
            return f'{h:02d}:{m:02d}:{s:02d}:{f:02d}'
        dur = (int(fin) - int(ini)) / fps
        return f'{tc(ini)} → {tc(fin)}  ({dur:.0f} s)'
    def _adelanto_frames(self):
        """Fotogramas que se adelantan los bloques destacados.

        No se convierte a segundos aqui: el numero viaja tal cual en el
        manifiesto y lo aplica Resolve, que es el unico que sabe a cuantos fps
        va el timeline. Un valor invalido se trata como 0: esto nunca debe
        impedir generar.
        """
        try:
            return max(0, int(self.adelanto_var.get()))
        except (ValueError, AttributeError):
            return 0
    def _modo(self):
        """El modo elegido ('normal' / 'dinamico' / 'destacados'), a partir
        de la etiqueta en español que muestra el selector."""
        return self._modo_de_etiqueta.get(self.modo_var.get(), 'dinamico')
    def _look(self):
        """El look elegido del modo destacados (\'hormozi\'/\'gadzhi\'/...)."""
        return self.LOOKS.get(self.look_var.get(), 'hormozi')
    def _on_modo_change(self, _valor=None):
        """En modo dinamico y en destacados el largo se decide por frases,
        no por caracteres, y hay una ventana de marcas de por medio.

        Los campos que no aplican se ESCONDEN en vez de quedar grises: dejar
        ahi algo que no se puede tocar era ocupar media ventana sin motivo.
        v5.0.0: «Estilos y composición» es una pantalla: en vez de cerrarse
        al cambiar de modo, se actualiza.
        """
        modo = self._modo()
        try:
            self.modo_btn.marcar(self._mosaico_actual())
        except Exception:
            pass
        ventana = getattr(self, '_plantillas_ventana', None)
        if ventana is not None and ventana.existe():
            try:
                ventana.actualizar(seleccion=self.plantilla_sel, basicos_actual=self._basicos_actual(), modo=modo, formato=self._formato_en_juego())
            except Exception:
                guardar_log_de_error(traceback.format_exc())
        try:
            self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        except Exception:
            pass
        ventana_c = getattr(self, '_composicion_ventana', None)
        if ventana_c is not None and ventana_c.existe():
            ventana_c.poner_habilitado(modo != 'normal')
        es_normal = modo == 'normal'
        if not es_normal and self.translate_var.get():
            self.translate_var.set(False)
            try:
                self.status_var.set(tr('Traducción desactivada: está disponible en «Subtítulos normales».'))
            except Exception:
                pass
        self.translate_check.setEnabled(es_normal and self._entradas_activas)
        for w in (self.destino_menu, self.buscar_destino_btn, self.idiomas_btn):
            w.setVisible(es_normal)
        self.nota_traduccion.setVisible(not es_normal)
        self.basico_frame.setVisible(modo in ('normal', 'dinamico'))
        self.adelanto_frame.setVisible(modo == 'dinamico')
        self.look_frame.hide()
        self.fmt_frame.hide()
        self._refrescar_vista_estilo()
        self._refrescar_receta()
    def _carpeta_scripts_resolve(self):
        """Donde Resolve busca los scripts del menu Scripts."""
        return carpeta_scripts_resolve()
    def _abrir_en_el_explorador(self, carpeta):
        """Abre una carpeta en el Finder / Explorador de archivos.

        Es la salida manual: si en la maquina de alguien la copia
        automatica falla por permisos, todavia puede arrastrar los cuatro
        archivos de una carpeta a la otra y seguir trabajando.
        """
        carpeta = Path(carpeta)
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            import subprocess
            if sys.platform.startswith('win'):
                os.startfile(str(carpeta))
            else:
                if sys.platform == 'darwin':
                    subprocess.Popen(['open', str(carpeta)])
                else:
                    subprocess.Popen(['xdg-open', str(carpeta)])
        except Exception as e:
            messagebox.showerror(tr('No pude abrir la carpeta'), f'{carpeta}\n\n{e}', parent=self)
    def _avisar_falta_python(self):
        """Explica que Resolve necesita un Python instalado en el sistema.

        Es la unica pieza que no podemos resolver por codigo: Resolve corre
        los scripts del menu con un interprete del sistema, no con el que
        lleva adentro nuestro programa. Sin el, ni siquiera los lista.
        """
        if getattr(self, '_aviso_python_dado', False):
            return
        self._aviso_python_dado = True
        donde = 'python.org/downloads' if sys.platform == 'darwin' else 'python.org/downloads'
        seguir = messagebox.askyesno(tr('Falta Python en el sistema'), tr('DaVinci Resolve necesita tener Python instalado en el sistema para poder correr los scripts de su menú.\n\nEn este equipo no encontré ninguno') + (tr(' (macOS ya no lo trae de fábrica desde la versión 12.3).') if sys.platform == 'darwin' else '.') + tr('\n\nPor eso el menú de Resolve aparece vacío aunque los scripts estén instalados.\n\n¿Abro {donde} para descargarlo?\nDespués de instalarlo, reinicia DaVinci Resolve.', donde=donde), parent=self)
        if seguir:
            try:
                webbrowser.open('https://www.python.org/downloads/')
            except Exception:
                return None
    def _dialogo_scripts_no_instalados(self):
        """Ventana con salidas de verdad cuando no se pudo instalar.

        Un messagebox seco dejaba al usuario sin nada que hacer. Aca hay
        tres salidas: reintentar, copiar el diagnostico para mandarlo, y
        abrir las dos carpetas para arrastrar los archivos a mano.
        """
        dlg = Dialogo(self, tr('No pude instalar los scripts en Resolve'), 580, 340, redimensionable=False)
        detalle = getattr(self, '_ultimo_error_scripts', None)
        if not resolve_esta_instalado():
            explicacion = tr('No encuentro DaVinci Resolve en este equipo.\n¿Está instalado?')
        else:
            if detalle:
                explicacion = detalle
            else:
                explicacion = tr('No pude dejar los scripts en la carpeta de DaVinci Resolve.')
        capa = _capa_dialogo(dlg, (22, 20, 22, 18), 10)
        capa.addWidget(_titulo(tr('No pude instalar los scripts en Resolve'), 16))
        capa.addWidget(_nota(explicacion, 13))
        capa.addWidget(Etiqueta(tr('Si no se puede automáticamente, arrastra los 4 archivos de una carpeta a la otra:'), 13, envolver=True))
        fila, cf = caja_h(espacio=8)
        cf.addWidget(Boton(tr('Abrir carpeta con los scripts'), lambda: self._abrir_en_el_explorador(BASE_RECURSOS / 'resolve_scripts'), tipo='neutro', alto=36), 1)
        cf.addWidget(Boton(tr('Abrir carpeta de Resolve'), lambda: self._abrir_en_el_explorador(carpeta_scripts_resolve()), tipo='neutro', alto=36), 1)
        capa.addWidget(fila)
        capa.addStretch(1)
        pie, cp = caja_h(espacio=8)
        cp.addWidget(Boton(tr('Copiar diagnóstico'), self._copiar_diagnostico_scripts, tipo='neutro', alto=36))
        cp.addStretch(1)
        def reintentar():
            dlg.cerrar()
            self._instalar_en_resolve()
        cp.addWidget(Boton(tr('Reintentar'), reintentar, tipo='primario', alto=36, ancho=110))
        cp.addWidget(Boton(tr('Cerrar'), dlg.cerrar, tipo='neutro', alto=36, ancho=90))
        capa.addWidget(pie)
        dlg.exec()
    def _copiar_diagnostico_scripts(self):
        """Deja TODO el diagnostico en el portapapeles.

        Sirve para que cualquiera pueda mandarlo pegado sin tener que buscar
        archivos ni abrir una terminal.

        Desde la v1.0.25 lleva ademas el estado VIVO del Puente: hasta
        entonces solo informaba de la instalacion, y los fallos de conexion
        que quedaban llegaban como "no me conecta" sin un solo dato con el
        que trabajar.
        """
        partes = []
        try:
            import resolve_bridge
            partes.append(resolve_bridge.diagnostico())
            partes.append('')
        except Exception as e:
            partes.append(tr('(no pude leer el estado del Puente: {e})', e=e))
            partes.append('')
        partes.append(informe_scripts_resolve())
        try:
            import instalador_scripts as ins
            if ins.ARCHIVO_REGISTRO.exists():
                partes.append('')
                partes.append(ins.ARCHIVO_REGISTRO.read_text(encoding='utf-8'))
        except Exception:
            pass
        try:
            ruta_err = Path.home() / 'DaVinciSubtitles' / 'error_ventana.txt'
            if ruta_err.exists():
                lineas = ruta_err.read_text(encoding='utf-8', errors='replace').splitlines()
                partes.append('')
                partes.append('ultimo error de la interfaz (error_ventana.txt, ultimas lineas):')
                partes.extend(lineas[(-15):])
        except Exception:
            pass
        texto = '\n'.join(partes)
        try:
            ui.copiar_al_portapapeles(texto)
            messagebox.showinfo(tr('Diagnóstico copiado'), tr('Ya está en tu portapapeles. Pégalo donde quieras mandarlo.'), parent=self)
        except Exception:
            messagebox.showinfo(tr('Diagnóstico'), texto, parent=self)
    def _asegurar_scripts_instalados(self, ruidoso=False, _resultado=None):
        """Deja nuestros scripts en la carpeta de Resolve.

        Se llama al abrir el programa y antes de cada accion que necesite
        a Resolve. Es barato (son cuatro archivos chicos y solo reescribe
        los que quedaron viejos), y sin esto el menu de Resolve nunca
        muestra la categoria Edit: ni 'Detectar Video' ni el 'Puente'
        aparecen, que era exactamente el problema.

        Con ruidoso=False no interrumpe nunca: si Resolve no esta
        instalado no hay nada que avisar.
        """
        copiados, error, _detalle = _resultado if _resultado is not None else instalar_scripts_en_resolve()
        if error:
            if not resolve_esta_instalado():
                return False
            self._ultimo_error_scripts = error
            if ruidoso or not getattr(self, '_aviso_fallo_scripts_dado', False):
                self._aviso_fallo_scripts_dado = True
                despues(600, self._dialogo_scripts_no_instalados, self)
            return False
        aviso_mac = problema_mac_app_store()
        if aviso_mac and (not getattr(self, '_aviso_mac_app_store_dado', False)):
                self._aviso_mac_app_store_dado = True
                despues(900, lambda: messagebox.showwarning(tr('Resolve de la Mac App Store'), aviso_mac, parent=self), self)
        if copiados:
            if resolve_esta_corriendo():
                self._pedir_reinicio_resolve()
                return True
            if ruidoso:
                self.status_var.set(tr('Scripts actualizados en Resolve ({len}).', len=len(copiados)))
        return True
    def _pedir_reinicio_resolve(self):
        """Avisa una sola vez de que hay que reiniciar Resolve."""
        if getattr(self, '_aviso_reinicio_dado', False):
            return
        self._aviso_reinicio_dado = True
        self.status_var.set(tr('Scripts instalados. Reinicia DaVinci Resolve para verlos en el menú.'))
        try:
            import ui_toast
            ui_toast.mostrar(self, tr('Dejé los scripts en Resolve. Como Resolve arma su menú al abrirse, ciérralo y vuelve a abrirlo para que aparezcan en Scripts.'), duracion_ms=7000)
        except Exception:
            return
    def _etiqueta_plantilla(self):
        if self.plantilla_sel == 'media_pool':
            return tr('Mis plantillas del Media Pool  >')
        if self.plantilla_sel in ['auto', '', None]:
            return tr('Diseño automático  >')
        if self.plantilla_sel == 'dinamico':
            d = getattr(self, 'diseno_dinamico', None) or {}
            preset = d.get('preset') or 'clasico'
            nombre = plantillas.PRESETS_DINAMICOS.get(preset, {}).get('nombre', preset)
            return tr('Diseño dinámico: {nombre}  >', nombre=nombre)
        return f'Pack: {plantillas.nombre_visible(self.plantilla_sel)}  >'
    def _pista_basicos(self):
        """Las claves 'plantilla_basicos' para los tracks SRT, o {}.

        v1.0.69: SOLO en modo normal (los subtitulos basicos) y con una
        combinacion elegida. En modo dinamico la pista traducida queda
        EXACTAMENTE como siempre (plantilla 'base' del pack + escalon).
        Si hay eleccion pero el pack no la puede servir (bundle roto),
        se avisa — nunca en silencio.
        """
        combinacion = getattr(self, 'basicos_sel', '')
        if not combinacion or self._modo() != 'normal':
            return {}
        pack_n = getattr(self, 'basicos_pack', plantillas.NOMBRE_BASICOS)
        pista = plantillas.basicos_para_manifiesto(combinacion, self._formato_forzado(), pack_nombre=pack_n)
        if not pista:
            self.msg_queue.put(('status', tr('No encontré la plantilla de básicos «{pack_n} · {combinacion}»: genero con la plantilla clásica.', pack_n=pack_n, combinacion=combinacion)))
        return pista
    def _etiqueta_plantilla_completa(self):
        """La etiqueta del card, POR MODO (v1.0.70).

        En modo normal habla de basicos («Básicos: inferior 2», con el
        nombre del pack delante si no es el incorporado); en modo
        dinamico la etiqueta dinamica de SIEMPRE, sin sufijos — el
        pedido literal: «el modo dinamico dejalo tal cual estaba».
        """
        if self._modo() != 'normal':
            return self._etiqueta_plantilla()
        combinacion = getattr(self, 'basicos_sel', '')
        if not combinacion:
            return tr('Básicos: Clásica  >')
        pack_n = getattr(self, 'basicos_pack', plantillas.NOMBRE_BASICOS)
        if pack_n and pack_n != plantillas.NOMBRE_BASICOS:
            return tr('Básicos: {pack_n} · {combinacion}  >', pack_n=pack_n, combinacion=_combinacion_visible(combinacion))
        return tr('Básicos: {combinacion}  >', combinacion=_combinacion_visible(combinacion))
    def _abrir_composicion(self):
        self.ir_a('estilos')
    def _clave_timeline(self):
        """Con que timeline se habla: 'proyecto|timeline' de la ultima
        deteccion, o 'ultimo' si no se sabe (v3.4.0: el estado de la
        composicion es por timeline)."""
        import resolve_bridge
        try:
            v = resolve_bridge.video_detectado() or {}
        except Exception:
            v = {}
        p, t = (v.get('project_name'), v.get('timeline_name'))
        return f'{p}|{t}' if p or t else 'ultimo'
    def _cues_ultimo_manifiesto(self):
        """(cues, idioma, pack) de la pista dinamica del ultimo manifiesto,
        o ([], 'es', None)."""
        try:
            m = json.loads((st.SHARED_FOLDER / 'subtitles_manifest.json').read_text(encoding='utf-8'))
            for t in m.get('tracks') or []:
                if t.get('style') != 'dynamic':
                    continue
                cues = json.loads(Path(t['data_path']).read_text(encoding='utf-8')).get('cues') or []
                p = t.get('plantilla')
                pack = p.get('pack') if isinstance(p, dict) else None
                return (cues, t.get('language') or 'es', pack)
        except Exception:
            pass
        return ([], 'es', None)
    def _estilos_de_bloques(self, bloques, palabras):
        """v5.8: la APP decide el estilo (variante del pack) de cada bloque —la rueda, el fijo o el que el usuario cambió en Creativo— y lo escribe en el bloque
        (b['estilo']): lo que enseña «Así se verá este bloque» es lo que Resolve coloca, en Studio y en Free. Sin pack (Media Pool, diseño) no toca nada."""
        try:
            import estilos_bloque
            if self.plantilla_sel in ('media_pool', 'dinamico', '', None):
                return
            numeros = [v['n'] for v in plantillas.variantes_de(self.plantilla_sel, self._formato_en_juego()) if v.get('n')]
            if numeros:
                estilos_bloque.asignar(bloques, palabras, numeros, estilo_fijo())
        except Exception:
            registro.excepcion(origen='estilos por bloque')
    def _pista_composicion(self, bloques):
        """v3.4.0: {'composicion': {...}} si no es la plantilla tal cual —
        y entonces mide TODAS las lineas con la tipografia del pack para
        que los gemelos alineen (emojis.medir_anchos_lineas). {} por
        defecto: el manifiesto no cambia. Lo que no se pudo medir se DICE."""
        extra = {'estilo_fijo': estilo_fijo()} if estilo_fijo() else {}
        if not COMPOSICION_VISIBLE:
            self._composicion_enviada = composicion.valida(None)
            return extra
        comp = composicion.valida(getattr(self, 'composicion', None))
        self._composicion_enviada = comp
        if composicion.es_defecto(comp):
            return extra
        try:
            if comp['layout'] != 'cc':
                import emojis
                estilos = plantillas.estilos_para_medir(self.plantilla_sel)
                n, sin = emojis.medir_anchos_lineas(bloques, estilos) if estilos else (0, [])
                if not estilos:
                    aviso = tr('Composición: esta plantilla no permite alinear (sin tipografías medibles): solo Altura y Horizontal.')
                else:
                    if sin:
                        aviso = tr('Composición: no pude medir {f}; esas líneas quedan como la plantilla.', f=', '.join(sin))
                    else:
                        aviso = tr('Composición: layout {l}, {n} líneas medidas.', l=comp['layout'], n=n)
                try:
                    self.msg_queue.put(('status', aviso))
                except Exception:
                    pass
        except Exception:
            pass
        return dict(extra, composicion=comp)
    def _registrar_colocacion_composicion(self):
        try:
            composicion.registrar_colocacion(self._clave_timeline(), getattr(self, '_composicion_enviada', None))
        except Exception:
            return None
    def _aplicar_composicion(self, desde, al_terminar=None):
        """«Aplicar desde el cabezal» / «a todo» (v3.4.0): deja la orden
        (json + sidecar) y corre la accion 'subtitulos' de siempre; el
        gemelo la ve antes del manifiesto y recompone. Al volver, la orden
        se retira SIEMPRE y el estado por timeline se anota con el fotograma
        que el gemelo dice. Free sin Puente: la orden queda 10 min para el
        clic en CineCaptions_Subtitulos y se vigila el resultado."""
        import emojis
        import resolve_bridge
        comp = composicion.valida(getattr(self, 'composicion', None))
        clave = self._clave_timeline()
        cues, lang, pack = self._cues_ultimo_manifiesto()
        medidas, aviso, estilos = ({}, '', {})
        if comp['layout'] != 'cc':
            estilos = plantillas.estilos_para_medir(pack) if pack else {}
            if estilos and cues:
                    try:
                        emojis.medir_anchos_lineas(cues, estilos)
                        medidas = composicion.medidas_para_orden(cues)
                    except Exception:
                        medidas = {}
            if not medidas:
                aviso = tr('Esta plantilla no permite alinear (no tengo sus tipografías): solo se aplican Altura y Horizontal.')
        orden = composicion.armar_orden(comp, desde, composicion.tramos(clave), medidas, lang, estilos)
        try:
            composicion.dejar_orden(orden)
        except OSError as e:
            if al_terminar:
                al_terminar(False, tr('No pude dejar la orden: {e}', e=e))
            return
        empezo = time.time()
        try:
            resolve_bridge.limpiar_resultado_viejo()
        except Exception:
            pass
        self.status_var.set(tr('Recomponiendo en Resolve…'))
        def trabajo():
            return resolve_bridge.ejecutar('subtitulos')
        def terminar(res, err):
            ok, mensaje = res if isinstance(res, tuple) and len(res) == 2 else (False, str(err or res))
            if not ok and resolve_bridge.modo_actual(pasivo=True) == 'manual':
                self._vigilar_recomposicion(empezo, clave, comp, desde, aviso, al_terminar)
                if al_terminar:
                    al_terminar(None, tr('Pulsa CineCaptions_Subtitulos en el menú de Resolve (Workspace > Scripts) en los próximos 10 minutos: la composición se aplica ahí.'))
                return None
            composicion.retirar_orden()
            self._cerrar_recomposicion(ok, str(mensaje or ''), empezo, clave, comp, desde, aviso, al_terminar)
        _correr_en_hilo(self, trabajo, terminar)
    def _cerrar_recomposicion(self, ok, mensaje, empezo, clave, comp, desde, aviso, al_terminar):
        import re
        import resolve_bridge
        m = re.search('fotograma (\\d+)', mensaje or '')
        if ok and m is None:
                try:
                    res = resolve_bridge.ultimo_resultado(desde=empezo) or {}
                    m = re.search('fotograma (\\d+)', str(res.get('mensaje') or ''))
                except Exception:
                    m = None
        if ok:
            if desde == 'todo':
                composicion.registrar_aplicacion(clave, 0, comp)
            else:
                if m:
                    composicion.registrar_aplicacion(clave, int(m.group(1)), comp)
            texto = (mensaje or tr('Listo.')) + (' ' + aviso if aviso else '')
        else:
            texto = tr('No pude recomponer: {e}', e=(mensaje or '?')[:400])
        try:
            self.status_var.set(texto)
        except Exception:
            pass
        if al_terminar:
            al_terminar(ok, texto)
    def _vigilar_recomposicion(self, empezo, clave, comp, desde, aviso, al_terminar):
        import resolve_bridge
        hasta = time.time() + composicion.ORDEN_VALE_S
        def mirar():
            try:
                res = resolve_bridge.ultimo_resultado(desde=empezo)
            except Exception:
                res = None
            if res:
                composicion.retirar_orden()
                self._cerrar_recomposicion(bool(res.get('ok')), str(res.get('mensaje') or ''), empezo, clave, comp, desde, aviso, al_terminar)
                return
            if time.time() > hasta:
                composicion.retirar_orden()
                return
            despues(2000, mirar, self)
        despues(2000, mirar, self)
    def _abrir_plantillas(self):
        self.ir_a('estilos')
    def _importar_estilos_drt(self, cuando_termine=None):
        """Añade un pack a partir de un archivo .drt. SIN abrir Resolve.

        Este es el camino bueno desde la v1.0.27: el pack ES el .drt, no
        una extracción de sus valores. El motivo esta medido: al abrir los
        .drt de verdad se vio que cada "Text+" es un GroupOperator entero
        (SoftGlow + TextPlus + StyledTextFollower + PolyPath + curvas de
        animacion), y el extractor guardaba SOLO el nodo TextPlus. Con el
        se iba la animacion y, sobre todo, la POSICION -que vive en el
        PolyPath, no en el 'Center' del Text+-. Ese era el bug que se
        reportaba como "el bloque 2 no respeta su posicion".

        Y se lee aqui, con packs_drt.py, sin pedirle nada a Resolve: un
        .drt es un ZIP con XML adentro. Asi lo que se le enseña al usuario
        -cuantos sets hay, cuales faltan, que tipografias pide- sale del
        archivo de verdad y no puede mentir. Hasta la v1.0.26 esto pasaba
        por Resolve y el resultado era el "simula que los importa".
        """
        ruta = filedialog.askopenfilename(parent=self, title=tr('Elige la bandeja (.drb) o el timeline (.drt) exportado de tu plantilla'), filetypes=[(tr('Bandeja o timeline de Resolve'), '*.drb *.drt'), (tr('Todos los archivos'), '*.*')])
        if not ruta:
            return
        es_drb = str(ruta).lower().endswith('.drb')
        info = packs_drt.leer_drb(ruta) if es_drb else packs_drt.leer(ruta)
        if not info.get('ok'):
            titulo = tr('No pude leer ese .drb') if es_drb else tr('No pude leer ese .drt')
            messagebox.showerror(titulo, info.get('error') or tr('No encontré ningún estilo utilizable.'), parent=self)
            return
        formato = self._preguntar_formato(Path(ruta).name)
        if formato is None:
            return
        nombre = simpledialog.askstring(tr('Nombre del pack'), tr('¿Cómo quieres llamar a este pack?\n\nSi ya existe uno con ese nombre, se le añade este formato y se conservan los demás.'), initialvalue=Path(ruta).stem, parent=self)
        if not nombre or not nombre.strip():
            return None
        guardar = plantillas.guardar_drb if es_drb else plantillas.guardar_drt
        pack, avisos = guardar(nombre.strip(), formato, ruta)
        if pack is None:
            messagebox.showerror(tr('No pude guardar el pack'), '\n'.join(avisos), parent=self)
            return
        _CACHE_ESTILOS.pop(pack.nombre, None)
        if getattr(pack, 'es_basicos', False):
            basicos = info.get('basicos') or {}
            partes = [f'{_combinacion_visible(pos)} '
                      f"{', '.join(map(str, sorted(ns)))}"
                      for pos, ns in sorted(basicos.items()) if ns]
            total = sum((len(ns) for ns in basicos.values()))
            extra = '' if self._modo() == 'normal' else tr('\n\nOJO: es una plantilla de SUBTÍTULOS BÁSICOS — se elige y se usa en el modo «Subtítulos normales».')
            messagebox.showinfo(tr('Plantilla de básicos añadida'), tr('«{nombre}» ({lower}): {total} combinaciones — ', nombre=pack.nombre, lower=plantillas.ETIQUETA_FORMATO[formato].lower(), total=total) + ' · '.join(partes) + extra, parent=self)
            self._guardar_preferencias()
            if cuando_termine:
                cuando_termine(None)
            return None
        resumen = f'«{pack.nombre}» ({plantillas.ETIQUETA_FORMATO[formato].lower()}): ' + packs_drt.resumen(info)
        if self._modo() == 'normal':
            resumen += tr('\n\nOJO: es un pack de títulos DINÁMICOS — se elige y se usa en el modo «Dinámicos (3 líneas)».')
        if not info.get('completos'):
            messagebox.showwarning(tr('Pack añadido, pero sin combinaciones completas'), resumen + tr('\n\nNingún set tiene los tres roles (arriba, principal y abajo), así que no hay nada que usar todavía.'), parent=self)
        else:
            messagebox.showinfo(tr('Pack añadido'), resumen, parent=self)
        self.plantilla_sel = pack.nombre
        self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        self._guardar_preferencias()
        self._refrescar_vista_estilo()
        self._refrescar_receta()
        if cuando_termine:
            cuando_termine(pack.nombre)
    def _preguntar_formato(self, nombre_archivo):
        """Horizontal, vertical o cuadrado. None si el usuario cancela.

        Lo elige el usuario y no se deduce del archivo porque la resolucion
        del timeline NO es legible fuera de Resolve: vive en un blob binario
        propio. Se propone lo que diga el nombre del archivo, que es como
        la gente los nombra de todos modos.
        """
        minus = nombre_archivo.lower()
        sugerido = next((f for pista, f in plantillas._PISTAS_FORMATO
                         if pista in minus), 'h')
        dlg = Dialogo(self, tr('Formato del pack'), 400, 230, redimensionable=False)
        capa = _capa_dialogo(dlg, (22, 20, 22, 18), 8)
        capa.addWidget(Etiqueta(tr('¿Para qué formato es esta plantilla?'), FS_NORMAL + 2, peso='negrita', alineacion=Qt.AlignmentFlag.AlignCenter))
        capa.addWidget(Etiqueta(nombre_archivo, FS_MENOR, color=TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignCenter))
        var = StringVar(sugerido)
        if var.get() not in ['h', 'v']:
            var.set('h')
        fila, cf = caja_h(espacio=18, margenes=(0, 10, 0, 0))
        cf.addStretch(1)
        for f in ['h', 'v']:
            cf.addWidget(Radio(plantillas.ETIQUETA_FORMATO[f], var, f, tam=FS_NORMAL))
        cf.addStretch(1)
        capa.addWidget(fila)
        capa.addStretch(1)
        elegido = {'valor': None}
        def aceptar():
            elegido['valor'] = var.get()
            dlg.cerrar()
        pie, cp = caja_h(espacio=10)
        cp.addStretch(1)
        cp.addWidget(Boton(tr('Cancelar'), dlg.cerrar, tipo='neutro', alto=36, ancho=100))
        cp.addWidget(Boton(tr('Añadir'), aceptar, tipo='primario', alto=36, ancho=100))
        cp.addStretch(1)
        capa.addWidget(pie)
        dlg.exec()
        return elegido['valor']
    def _importar_estilos(self, cuando_termine=None, ruta_drt=None):
        """Le pide a Resolve que extraiga los estilos de un timeline: el que
        esté abierto, o -si se pasa 'ruta_drt'- uno importado desde un
        archivo .drt.

        El script de Resolve solo EXTRAE; convertir eso en un pack lo hace
        plantillas.py, aca. Asi la validacion vive en un solo sitio.
        """
        nombre = simpledialog.askstring(tr('Nombre del pack'), tr('¿Cómo quieres llamar a este pack de estilos?\n\nSi ya existe uno con ese nombre, se le añade el formato que estés importando (horizontal o vertical) sin borrar el otro.'), parent=self, initialvalue='Mis estilos')
        if not nombre or not nombre.strip():
            return None
        try:
            plantillas.RUTA_IMPORTACION.unlink()
        except OSError:
            pass
        marcador_drt = st.SHARED_FOLDER / 'importar_drt.txt'
        if ruta_drt:
            try:
                st.SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
                marcador_drt.write_text(str(Path(ruta_drt).resolve()) + '\n', encoding='utf-8')
            except OSError as e:
                messagebox.showerror(tr('No pude preparar la importación'), tr('No pude escribir el archivo temporal: {e}', e=e), parent=self)
                return None
        else:
            try:
                marcador_drt.unlink()
            except OSError:
                pass
        import resolve_bridge
        ok, mensaje = resolve_bridge.ejecutar('importar_estilos')
        if not ok:
            messagebox.showerror(tr('No pude importar los estilos'), mensaje or tr('Resolve no respondió.'), parent=self)
            return
        datos, error = plantillas.leer_importacion()
        if error:
            messagebox.showerror(tr('No pude importar los estilos'), error, parent=self)
            return
        pack, avisos = plantillas.importar_desde(datos, nombre.strip())
        if pack is None:
            messagebox.showerror(tr('No pude importar los estilos'), '\n'.join(avisos) or tr('No había ningún estilo utilizable.'), parent=self)
            return
        _CACHE_ESTILOS.pop(pack.nombre, None)
        formato = 'vertical' if datos.get('formato') == 'v' else 'horizontal'
        n_sets = len(pack.numeros_de_set(datos.get('formato') or 'h'))
        resumen = tr('Importé «{nombre}» ({formato}): {n_sets} sets.', nombre=pack.nombre, formato=formato, n_sets=n_sets)
        if avisos:
            messagebox.showwarning(tr('Pack importado, con avisos'), resumen + tr('\n\nPero hay cosas que no salieron:\n  · ') + '\n  · '.join(avisos), parent=self)
        else:
            messagebox.showinfo(tr('Pack importado'), resumen, parent=self)
        self.plantilla_sel = pack.nombre
        self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        self._guardar_preferencias()
        self._refrescar_vista_estilo()
        self._refrescar_receta()
        if cuando_termine:
            cuando_termine(pack.nombre)
    def _refrescar_formato_detectado(self):
        """La etiqueta de al lado del selector: que formato va a entrar.

        Se enseña ANTES de generar y no despues, que era el reporte: 'no
        respeta si es vertical, horizontal o cuadrado'. Sin resolucion
        todavia se dice 'sin detectar', no se inventa un formato.
        """
        etiqueta = getattr(self, 'formato_detectado_lbl', None)
        if etiqueta is None:
            return
        forzado = self._formato_forzado()
        ancho = getattr(self, '_ancho_timeline', 0)
        alto = getattr(self, '_alto_timeline', 0)
        if forzado:
            texto = tr('· usaré: {v}', v=plantillas.ETIQUETA_FORMATO[forzado])
        else:
            if ancho > 0 and alto > 0:
                detectado = plantillas.formato_de(ancho, alto)
                texto = f'· {ancho}×{alto} → {plantillas.ETIQUETA_FORMATO[detectado]}'
            else:
                texto = tr('· sin detectar todavía')
        try:
            etiqueta.configure(text=texto)
        except Exception:
            return None
        self._refrescar_vista_estilo()
        ventana = getattr(self, '_plantillas_ventana', None)
        if ventana is not None and ventana.existe():
            try:
                ventana.actualizar(formato=self._formato_en_juego())
            except Exception:
                pass
    def _formato_en_juego(self):
        """El formato que se va a usar: el elegido a mano, o el detectado.

        None si todavia no se sabe (nada elegido y sin detectar). Es lo mismo
        que enseña la etiqueta de al lado del selector, y lo que decide con
        que pestaña abre la ventana de plantillas.
        """
        forzado = self._formato_forzado()
        if forzado:
            return forzado
        ancho = getattr(self, '_ancho_timeline', 0)
        alto = getattr(self, '_alto_timeline', 0)
        if ancho > 0 and alto > 0:
            return plantillas.formato_de(ancho, alto)
        return None
    def _formato_forzado(self):
        """v5.4.23: siempre None (se detecta dentro de Resolve). El chip «Formato» de Inicio ya no existe: GO arma un timeline vertical y un «Horizontal» guardado de antes dejaba los
        temas verticales (Tema 1 y 2) sin poder aplicarse («no puedo aplicar el tema»)."""
        return None
    def _formato_para_temas(self):
        """El formato con el que se decide si un tema sirve: vertical (el timeline que arma GO), salvo que se haya apagado «Abrir siempre en vertical»."""
        try:
            import ajustes_ui
            if ajustes_ui.leer_prefs().get('go_vertical', True) is not False:
                return 'v'
        except Exception:
            pass
        return self._formato_en_juego() or 'v'
    def _pista_plantilla(self):
        """El campo 'plantilla' del manifiesto, ya resuelto.

        El pack viaja RESUELTO —los sets de los dos formatos y las carpetas de
        los .setting— para que los scripts de Resolve no tengan que leer
        estilos.json: asi hay un solo parser y no dos que se separen.

        La logica vive en plantillas.para_manifiesto para poder probarla sin
        abrir la interfaz. Devuelve {} con el diseño automatico y con las
        plantillas del Media Pool, que mandan sobre el pack.
        """
        if self.plantilla_sel == 'dinamico':
            try:
                return plantillas.diseno_para_manifiesto(getattr(self, 'diseno_dinamico', None))
            except Exception as exc:
                self._avisar_sin_pack(tr('no pude armar el diseño ({name})', name=type(exc).__name__))
                return {}
        else:
            try:
                pista = plantillas.para_manifiesto(self.plantilla_sel, formato_forzado=self._formato_forzado())
            except Exception as exc:
                self._avisar_sin_pack(tr('no pude leerlo ({name})', name=type(exc).__name__))
                return {}
            if not pista and self.plantilla_sel not in ('media_pool', '', None):
                    self._avisar_sin_pack(tr('no encontré sus archivos'))
            return pista
    def _anunciar_receta(self, pista_plantilla, pista_sfx):
        """Dice EN PANTALLA con que diseño y con que efectos se genera.

        Hasta la v1.0.35 esto era invisible: ni la app ni el aviso final
        nombraban la plantilla, asi que una corrida con el diseño equivocado
        se veia igual que una correcta y el usuario solo lo descubria mirando
        el timeline. Ahora la linea de estado lo dice antes de empezar.
        """
        # el pack viaja dentro de 'plantilla' (plantillas.para_manifiesto); antes
        # solo se miraba arriba y el aviso decia «diseño automático» con un pack puesto
        pack_puesto = pista_plantilla.get('pack') or (pista_plantilla.get('plantilla') or {}).get('pack')
        if pista_plantilla.get('diseno'):
            _p = pista_plantilla['diseno'].get('preset') or 'personalizado'
            diseño = tr('el Diseño dinámico «{p}»', p=_p)
        else:
            if pack_puesto:
                diseño = tr('el pack «{v}»', v=plantillas.nombre_visible(pack_puesto))
            else:
                if self.plantilla_sel == 'media_pool':
                    diseño = tr('tus plantillas del Media Pool')
                else:
                    diseño = tr('el diseño automático')
        if pista_sfx:
            resumen = pista_sfx.get('sfx_resumen') or {}
            cuantos = sum(resumen.values())
            fuentes = ', '.join((f'«{c}»' for c in sorted(resumen)))
            efectos = tr('{cuantos} efectos de sonido de {fuentes}', cuantos=cuantos, fuentes=fuentes) if fuentes else tr('{cuantos} efectos de sonido', cuantos=cuantos)
        else:
            efectos = tr('sin efectos')
        try:
            self.msg_queue.put(('status', tr('Generando con {dise_o}, {efectos}.', dise_o=diseño, efectos=efectos)))
        except Exception:
            return None
    def _avisar_sin_pack(self, motivo):
        """Dice, donde el usuario lo ve, que se genera SIN el pack pedido."""
        nombre = (tr('el diseño automático') if self.plantilla_sel in ('auto', '')
                  else tr('el pack «{plantilla_sel}»', plantilla_sel=plantillas.nombre_visible(self.plantilla_sel)))
        texto = tr('Pediste {nombre} pero {motivo}: genero con las plantillas del Media Pool.', nombre=nombre, motivo=motivo)
        try:
            self.msg_queue.put(('status', texto))
        except Exception:
            try:
                self.status_var.set(texto)
            except Exception:
                pass
    def _abrir_estudio(self):
        """Abre el estudio de sonidos (v5.0.0: la pantalla «SFX Lab»).

        Se importa al abrirlo (no arriba) para que la ventana principal
        arranque sin cargar av/numpy si el usuario no lo va a usar.
        """
        self.ir_a('sfx')
    def _al_terminar_generacion(self, n_cues, langs, folder):
        """Cuando termina la transcripcion + preparacion del manifest.

        Si estamos con Resolve **Studio**, corre el script principal
        directamente por la API externa y evita el paso 'ahora andá al
        menu'. Con Free, muestra el mensaje habitual.
        """
        try:
            raw_path = self.video_var.get().strip().strip('\"')
            if raw_path:
                proyectos.guardar(raw_path, project_name=Path(raw_path).expanduser().stem, idioma=self._codigo_idioma(), traducir_ingles=bool(self.translate_var.get()) if hasattr(self, 'translate_var') else False, extra={'ultima_gen_bloques': n_cues, 'ultima_gen_langs': langs, 'modo': self._modo(), 'look': self._look() if self._modo() == 'destacados' else None})
                self._generado_para = raw_path
                self._refrescar_recientes()
        except Exception:
            pass
        self._refrescar_pasos()
        self._asegurar_scripts_instalados()
        if self._colocar_en_resolve(n_cues, langs):
            return
        self._gen_fin(False)
        self.status_var.set(tr('Listo: {n_cues} bloques ({langs}). Guardado en {folder}.', n_cues=n_cues, langs=langs, folder=folder))
        self._avisar_correr_a_mano(tr('Subtítulos listos'), tr('Se generaron {n_cues} bloques ({langs}).', n_cues=n_cues, langs=langs))
    # -- efectos visuales (página «Efectos»): intro, transiciones en los cortes e iconos flotantes en las frases clave ---------------------------------------
    def _buscar_cortes_en_paralelo(self, media_path):
        """Si los efectos están activos y hay transiciones, un hilo busca los cortes entre tomas mientras la voz se transcribe. Devuelve un contenedor con .resultado."""
        import types
        caja = types.SimpleNamespace(resultado=None, hilo=None)
        try:
            import efectos_visuales
            if efectos_visuales.activado() and efectos_visuales.opciones_guardadas().get('fx_cortes'):
                def buscar():
                    try:
                        caja.resultado = efectos_visuales.detectar_cortes(str(media_path))
                    except Exception:
                        registro.excepcion(origen='efectos visuales (cortes)')
                caja.hilo = threading.Thread(target=buscar, daemon=True, name='fx-cortes')
                caja.hilo.start()
        except Exception:
            registro.excepcion(origen='efectos visuales (inicio)')
        return caja
    def _recortar_pausas(self, words, media_path):
        """Con «Quitar pausas» encendido y un timeline que GO armó con ESTE video, recorta los silencios de V1/A1 en Resolve y devuelve las palabras con los tiempos nuevos.
        Si algo falla o no hay casi nada que quitar, las palabras quedan como estaban."""
        self._recorte = None
        try:
            import efectos_visuales
            import pausas
            nivel = efectos_visuales.opciones_guardadas().get('fx_pausas')
            tl_listo = getattr(self, '_go_tl_listo', None)
            if nivel not in pausas.UMBRALES or not getattr(self, '_un_clic', False) or tl_listo is None or not words:
                return words
            tl_listo.wait(120)
            self._abortar_si_fallo_el_timeline()
            dur = efectos_visuales.duracion_video(media_path) or float(words[-1].get('end') or 0.0)
            fps = float(getattr(self, '_fps_timeline', 0) or 30.0)
            info = pausas.calcular(words, dur, fps, nivel)
            if not info:
                registro.info('Quitar pausas: casi no hay silencios que quitar', 'GO')
                return words
            self.msg_queue.put(('status', tr('Quitando las pausas…')))
            r = pausas.recortar_en_resolve(info['segmentos'])
            if not r.get('ok'):
                registro.aviso('Quitar pausas no se pudo aplicar: ' + str(r.get('error') or r)[:160], 'GO')
                return words
            self._recorte = info
            registro.info('Quitar pausas: %.1f s menos (%d tramos)' % (info['quitado'], len(info['segmentos'])), 'GO')
            return pausas.remapear_palabras(words, info['segmentos'])
        except SystemExit:
            raise
        except Exception:
            registro.excepcion(origen='GO · quitar pausas')
            return words
    def _planificar_efectos(self, media_path, words, cortes_fx, avisar=True):
        """El plan de efectos de ESTE video (nunca rompe GO: si algo falla, se sigue sin efectos). Con avisar=False (en segundo plano, mientras la IA corrige el texto) no toca la línea de estado."""
        self._efectos_plan = None
        try:
            import efectos_visuales
            visuales = efectos_visuales.activado()
            if visuales:
                if avisar:
                    self.msg_queue.put(('status', tr('Preparando los efectos visuales…')))
                if cortes_fx is not None and cortes_fx.hilo is not None:
                    cortes_fx.hilo.join(120)
            cortes = cortes_fx.resultado if (cortes_fx is not None and visuales) else None
            duracion, saltos = None, None
            recorte = getattr(self, '_recorte', None)
            if recorte:                                # con las pausas quitadas, los tiempos de la fuente ya no valen: se pasan al timeline recortado
                import pausas
                cortes = pausas.remapear_cortes(cortes, recorte['segmentos']) if cortes else cortes
                duracion, saltos = recorte['duracion_nueva'], recorte['saltos']
            if visuales:
                plan = efectos_visuales.planificar(str(media_path), words, duracion=duracion, cortes=cortes, saltos=saltos)
            else:                                      # sin efectos visuales el audio extra (música, sonidos de gancho) sale igual
                dur = duracion or (efectos_visuales.duracion_video(str(media_path)) or (float(words[-1].get('end') or 0.0) if words else 0.0))
                plan = {'eventos': [], 'duracion': dur, 'resumen': '', 'zonas': [], 'solo_audio': True}
            plan['video'] = str(media_path)
            # v5.4.8: el audio extra (música de fondo, sonidos de las transiciones, riser + golpe del gancho) y los efectos que se acercan al pulso
            try:
                import sonidos_extra
                evs = plan.get('eventos') or []
                tiempos_corte = sorted([float(e['ini']) for e in evs if e.get('tipo') == 'corte'] + [float(t) for e in evs if e.get('tipo') == 'v1' for t in (e.get('cortes') or [])])
                trans = next((e.get('asset') for e in evs if e.get('tipo') == 'corte'), None) or next((e.get('transicion') for e in evs if e.get('tipo') == 'v1' and e.get('transicion')), None)
                audio_extra, resumen_audio = sonidos_extra.planificar(str(media_path), words, plan.get('duracion') or duracion, cortes=tiempos_corte, transicion=trans, saltos=saltos,
                                                                       eventos_visuales=evs, al_estado=(lambda t: self.msg_queue.put(('status', tr(t)))) if avisar else (lambda t: None))
                if audio_extra:
                    evs.extend(audio_extra)
                    plan['eventos'] = evs
                    plan['resumen'] = ', '.join(x for x in ([plan.get('resumen')] + resumen_audio) if x)
            except Exception:
                registro.excepcion(origen='GO · audio extra')
            if not plan.get('eventos'):
                return
            self._efectos_plan = plan
            registro.info('Efectos: ' + plan.get('resumen', ''), 'efectos')
        except Exception:
            registro.excepcion(origen='efectos visuales (plan)')
    def _colocar_efectos(self):
        """Pone el plan de efectos en el timeline de Resolve (tras los captions). Devuelve un texto corto para el estado, o ''."""
        plan = getattr(self, '_efectos_plan', None)
        if not plan or not plan.get('eventos'):
            return ''
        try:                                   # el plan es de un video: si ahora hay otro cargado (regenerar), no se aplica el de antes
            actual = self.video_var.get().strip().strip('"')
            if plan.get('video') and actual and Path(plan['video']).resolve() != Path(actual).expanduser().resolve():
                return ''
        except Exception:
            pass
        try:
            import efectos_visuales
            self.msg_queue.put(('status', tr('Colocando los efectos visuales en Resolve…')))
            try:
                n_golpes = efectos_visuales.completar_golpes(plan, getattr(self, '_ultimos_bloques', None))      # el temblor sigue los golpes de sonido reales
                if n_golpes:
                    registro.info(f'Efectos visuales: el temblor sigue {n_golpes} golpes de sonido', 'efectos')
            except Exception:
                pass
            ok, mensaje = efectos_visuales.aplicar(plan, al_estado=lambda t: self.msg_queue.put(('status', str(t))), offset_frames=self._offset_frames())
            if not ok:
                registro.aviso(f'Efectos visuales: {mensaje}', 'efectos')
                try:
                    import resolve_bridge
                    self._efectos_atascado = resolve_bridge.es_resolve_atascado(mensaje)          # v5.4.40: Resolve se colgó colocando los efectos: el GO lo reinicia y repite
                except Exception:
                    pass
                return tr('Los efectos visuales no se pudieron colocar: {m}', m=str(mensaje)[:120])
            return tr('con efectos visuales')
        except Exception:
            registro.excepcion(origen='efectos visuales (colocar)')
            return ''
    def _colocar_en_resolve(self, n_cues, langs):
        """Manda los subtitulos (y los SFX si toca) a Resolve, en un hilo.

        Devuelve True si quedo lanzado. Lo usan LOS DOS botones: el de
        generar y el de "editar marcas y regenerar". Antes esto vivia
        dentro de _al_terminar_generacion y el de regenerar no lo llamaba,
        asi que ese boton nunca coloco nada solo: escribia el manifest y
        mandaba al usuario a correr el script a mano, tanto en Studio como
        en Free. Tampoco respetaba la casilla de efectos.
        """
        try:
            import resolve_bridge
        except Exception:
            return False
        self.status_var.set(tr('Colocando los subtítulos en Resolve...'))
        self._gen_fase('colocar')
        def worker():
            empezo = time.time()
            try:
                resolve_bridge.limpiar_resultado_viejo()
            except Exception:
                pass
            try:
                composicion.retirar_orden()
            except Exception:
                pass
            # v5.5: «Listo» ya no se da por el simple hecho de que el script de Resolve terminara: se mira cuántas líneas colocó de verdad (colocacion.veredicto),
            # si no colocó nada se repara lo reparable y se reintenta UNA vez, y la vista final (página Edit, disposición de pantalla, cabezal al inicio) viaja en el manifiesto
            try:
                import colocacion
            except Exception:
                colocacion = None
            det = getattr(self, '_go_resolve', None) or {}
            inicio_total = empezo
            if colocacion:
                colocacion.vista_en_manifiesto(st.SHARED_FOLDER / 'subtitles_manifest.json')
            ok, err = resolve_bridge.ejecutar('subtitulos')
            for _reintento in range(2):                              # v5.4.40: Resolve colgado o cerrado colocando los captions → se reinicia, se arma el timeline otra vez y se repite
                if ok or not resolve_bridge.es_resolve_atascado(err) or not getattr(self, '_go_corriendo', False):
                    break
                if not self._go_rearmar_en_resolve(err):
                    break
                self.msg_queue.put(('status', tr('Vuelvo a colocar los subtítulos en Resolve…')))
                empezo = time.time()
                try:
                    resolve_bridge.limpiar_resultado_viejo()
                    composicion.retirar_orden()
                except Exception:
                    pass
                ok, err = resolve_bridge.ejecutar('subtitulos')
            veredicto, reparado = None, []
            if colocacion and ok:
                try:
                    veredicto = colocacion.veredicto(ok, err, empezo, n_cues)
                    if not veredicto['ok']:
                        reparado = colocacion.reparar(veredicto, al_estado=lambda t: self.msg_queue.put(('status', t)))
                        if reparado:
                            self.msg_queue.put(('status', tr('Vuelvo a colocar los subtítulos en Resolve…')))
                            empezo = time.time()
                            try:
                                resolve_bridge.limpiar_resultado_viejo()
                                composicion.retirar_orden()
                            except Exception:
                                pass
                            ok, err = resolve_bridge.ejecutar('subtitulos')
                            veredicto = colocacion.veredicto(ok, err, empezo, n_cues) if ok else None
                except Exception:
                    registro.excepcion(origen='colocar · veredicto')
            if veredicto is not None:
                try:
                    colocacion.registrar(veredicto, det.get('edicion'), det.get('camino'), time.time() - inicio_total, reparado)
                except Exception:
                    pass
                if not veredicto['ok']:
                    ok = False                         # el script corrió pero NO colocó nada: ya no se dice «Listo»
                    err = colocacion.frase_de_fallo(veredicto)
            self._efectos_atascado = False
            nota_fx = self._colocar_efectos() if ok else ''
            if ok and getattr(self, '_efectos_atascado', False) and getattr(self, '_go_corriendo', False):          # v5.4.40: Resolve se colgó con los efectos: se rehace todo
                self._efectos_atascado = False
                if self._go_rearmar_en_resolve('efectos visuales'):
                    self.msg_queue.put(('status', tr('Vuelvo a colocar los subtítulos en Resolve…')))
                    empezo = time.time()
                    try:
                        resolve_bridge.limpiar_resultado_viejo()
                        composicion.retirar_orden()
                    except Exception:
                        pass
                    ok, err = resolve_bridge.ejecutar('subtitulos')
                    nota_fx = self._colocar_efectos() if ok else ''
            if not ok and veredicto is None:
                try:
                    if resolve_bridge.modo_actual() == 'manual':
                        self._vigilar_clic_manual(empezo, n_cues, langs)
                except Exception:
                    pass
            if ok and colocacion and getattr(self, '_go_corriendo', False):
                try:
                    import ajustes_ui
                    if ajustes_ui.leer_prefs().get('go_reproducir', True) is not False:
                        self.msg_queue.put(('status', tr('Reproduciendo el timeline desde el principio…')))
                        rep_ok, rep_txt = colocacion.reproducir_desde_inicio()
                        (registro.info if rep_ok else registro.aviso)(rep_txt, 'GO · reproducir')
                except Exception:
                    registro.excepcion(origen='GO · reproducir')
            extra = ''
            version_ajena = None
            try:
                resultado = resolve_bridge.ultimo_resultado(desde=empezo)
                if ok:
                    resumen = (resultado or {}).get('mensaje', '').strip()
                    if resumen:
                        extra = f' ({resumen})'
                version_ajena = resolve_bridge.desajuste_de_version(APP_VERSION, resultado)
            except Exception:
                pass
            if version_ajena:
                self.msg_queue.put(('version_ajena', version_ajena))
            if not ok and err and resolve_bridge.es_scripting_cerrado(err):
                self.msg_queue.put(('scripting_cerrado', str(err)))
            try:
                paso = resolve_bridge.paso_manual_pendiente(resolve_bridge.texto_ultimo_resultado(desde=empezo))
                if paso:
                    self.msg_queue.put(('paso_manual', paso))
            except Exception:
                pass
            try:
                if resolve_bridge.puente_activo() and resolve_bridge.version_del_puente() != resolve_bridge.VERSION_PUENTE_ESPERADA:
                        self.msg_queue.put(('puente_viejo', resolve_bridge.version_del_puente() or '?'))
            except Exception:
                pass
            if nota_fx:
                extra = (extra + ' · ' if extra else ' (') + nota_fx + ('' if extra else ')')
            self.msg_queue.put(('colocado_en_resolve', (ok, err, extra, n_cues, langs, veredicto)))
        threading.Thread(target=worker, daemon=True).start()
        return True
    def _avisar_correr_a_mano(self, titulo, cabecera):
        """Manda a correr el script a mano, diciendo POR QUE hizo falta.

        Reusa mensaje_para_el_usuario(), que distingue el scripting externo
        apagado de "falta lanzar el Puente" (la rama de "reinicia Resolve" se
        retiro en la v3.1.3: se disparaba con Resolve abierto aunque el menu
        llevara semanas armado). Es el respaldo, no el camino normal.
        """
        try:
            import resolve_bridge
            motivo = '\n\n' + resolve_bridge.mensaje_para_el_usuario()
        except Exception:
            motivo = ''
        messagebox.showinfo(titulo, tr('{cabecera}\n\nAhora, con tu timeline activo:\n\nÁrea de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Subtitulos\n(en inglés: Workspace > Scripts)', cabecera=cabecera) + motivo, parent=self)
    def _vigilar_clic_manual(self, desde, n_cues, langs, segundos=900):
        """Free sin Puente (v3.1.6): el usuario pulsa CineCaptions_Subtitulos a mano y
        esta ventana se entera SOLA cuando termina — en 21.0.x por
        ultimo_resultado.json, en 21.1 por el reporte que el script deja en
        el registro de Resolve (el menu sin io no escribe archivos). Hasta
        aqui el messagebox era una despedida: ni el exito ni el error del
        script llegaban nunca, y en 21.1 no habia NINGUN otro sitio donde
        verlos. El resultado entra por el mismo handler que el automatico.
        Una generacion nueva reemplaza la vigilia (desde/n/langs), no apila
        otro hilo.
        """
        self._vigilia_clic = {'desde': desde, 'n': n_cues, 'langs': langs, 'hasta': time.time() + segundos}
        if getattr(self, '_vigilando_clic', False):
            return
        self._vigilando_clic = True
        import resolve_bridge
        def worker():
            try:
                while True:
                    v = self._vigilia_clic
                    if time.time() > v['hasta']:
                        return
                    time.sleep(2)
                    try:
                        res = resolve_bridge.ultimo_resultado(desde=v['desde'])
                    except Exception:
                        res = None
                    if not res:
                        continue
                    ok = bool(res.get('ok'))
                    mensaje = str(res.get('mensaje') or '').strip()
                    extra = f' ({mensaje})' if ok and mensaje else ''
                    try:
                        paso = resolve_bridge.paso_manual_pendiente(resolve_bridge.texto_ultimo_resultado(desde=v['desde']))
                        if paso:
                            self.msg_queue.put(('paso_manual', paso))
                    except Exception:
                        pass
                    self.msg_queue.put(('colocado_en_resolve', (ok, mensaje, extra, v['n'], v['langs'])))
                    return
            finally:
                self._vigilando_clic = False
        threading.Thread(target=worker, daemon=True).start()
    def _vigilar_deteccion(self, desde, segundos=900):
        """El gemelo de _vigilar_clic_manual para CineCaptions_DetectarVideo: cuando
        aparece una deteccion posterior a 'desde' (json o registro de
        Resolve), entra por el handler 'detect_ready' como si la hubiera
        traido el Puente."""
        self._vigilia_deteccion = {'desde': desde, 'hasta': time.time() + segundos}
        if getattr(self, '_vigilando_deteccion', False):
            return
        self._vigilando_deteccion = True
        import resolve_bridge
        def worker():
            try:
                while True:
                    v = self._vigilia_deteccion
                    if time.time() > v['hasta']:
                        return
                    time.sleep(2)
                    try:
                        datos = resolve_bridge.video_detectado()
                    except Exception:
                        datos = None
                    if datos and (datos.get('detectado_en') or 0) >= v['desde'] - 2:
                        self.msg_queue.put(('detect_ready', (True, '')))
                        return
            finally:
                self._vigilando_deteccion = False
        threading.Thread(target=worker, daemon=True).start()
    def _pedir_detectar_a_mano(self, aviso=''):
        """Free sin Puente: pedir el clic en CineCaptions_DetectarVideo y quedarse
        vigilando su resultado (v3.1.6). Antes, rechazar una deteccion vieja
        mostraba MENSAJE_SIN_PUENTE, que habla de CineCaptions_Subtitulos: el script
        equivocado para este paso — y en 21.1, donde el Puente no puede
        correr, el PRIMER boton era un callejon sin salida (16-09)."""
        self._vigilar_deteccion(time.time())
        self.status_var.set(tr('Esperando que pulses CineCaptions_DetectarVideo en Resolve…'))
        messagebox.showinfo(tr('Falta correr el script en Resolve'), aviso + tr('En Resolve, con tu timeline abierto:\n\n{MENU_SCRIPTS}  >  CineCaptions_DetectarVideo\n\nEso renderiza el audio de la línea de tiempo y lo deja listo acá: este programa se entera solo cuando termine.\n\nTruco: si en vez de ese corres una sola vez CineCaptions_Puente, todos los botones pasan a funcionar solos.', MENU_SCRIPTS=MENU_SCRIPTS), parent=self)
    def _podar_renders_viejos(self):
        """Los renders de audio con la hora en el nombre (Free 21.1: el
        script no tiene os.remove y no puede borrar el anterior) se
        acumulan en Descargas. Fuera los de mas de un dia; solo NUESTROS
        archivos (`*_audio_<epoch>…`), nunca otra cosa de esa carpeta."""
        import re
        limite = time.time() - 86400
        for base in [Path.home() / 'Downloads', Path.home() / 'Descargas', Path.home()]:
            carpeta = base / 'CineCaptions Audio'
            try:
                if not carpeta.is_dir():
                    continue
                for f in carpeta.iterdir():
                    if re.search('_audio_\\d{9,}', f.name) and f.is_file() and (f.stat().st_mtime < limite):
                                f.unlink()
            except OSError:
                pass
    def _ver_ultimo_resultado(self):
        """Muestra lo que reporto el ultimo script que corrio en Resolve.

        Los scripts dejan su resultado en ~/DaVinciSubtitles. Sirve tanto
        si los ejecuto la app como si el usuario los corrio a mano desde el
        menu: en los dos casos aca sale el motivo exacto.
        """
        try:
            import resolve_bridge
            datos = resolve_bridge.ultimo_resultado()
            salida = resolve_bridge.texto_ultimo_resultado()
        except Exception as e:
            messagebox.showerror(tr('No pude leerlo'), f'{type(e).__name__}: {e}', parent=self)
            return
        if not datos:
            messagebox.showinfo(tr('Todavía no hay nada'), tr('Ningún script de Resolve ha dejado un resultado todavía.\n\nCorre uno (por ejemplo Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Subtitulos) y vuelve a mirar aquí: va a aparecer el motivo exacto, hayas visto algo en pantalla o no.'), parent=self)
            return
        cuando = datos.get('cuando')
        aviso_edad = ''
        try:
            edad_s = time.time() - float(cuando or 0)
            if edad_s > 3600:
                cuanto = tr('{v:.0f} días', v=edad_s / 86400) if edad_s > 86400 else tr('{v:.0f} horas', v=edad_s / 3600)
                aviso_edad = tr('OJO: esto es de hace {cuanto}. Si acabas de generar, el script NO llegó a correr esta vez.\n\n', cuanto=cuanto)
        except (TypeError, ValueError):
            pass
        try:
            cuando = time.strftime('%d/%m %H:%M:%S', time.localtime(cuando))
        except Exception:
            cuando = '?'
        estado = tr('terminó bien') if datos.get('ok') else tr('FALLÓ')
        texto = aviso_edad + f"{datos.get('script', '?')}  ({cuando})\n" + tr('Resultado: {estado}', estado=estado) + '\n'
        if datos.get('mensaje'):
            texto += '\n' + tr('Motivo:') + f"\n{datos['mensaje']}\n"
        if salida:
            lineas = salida.strip().splitlines()
            ultimas = lineas[(-25):]
            marca = '\n' + tr('Lo que fue haciendo:')
            texto += marca + '\n' + '\n'.join(ultimas)
            try:
                ui.copiar_al_portapapeles(texto.split(marca)[0] + '\n' + tr('Registro completo:') + '\n' + salida)
                texto += tr('\n\nEl registro completo ({len} líneas) quedó copiado al portapapeles: pégalo en el chat.', len=len(lineas))
            except Exception:
                pass
        if datos.get('ok'):
            messagebox.showinfo(tr('Lo último que hizo Resolve'), texto, parent=self)
        else:
            messagebox.showwarning(tr('Lo último que hizo Resolve'), texto, parent=self)
    def _instalar_en_resolve(self):
        """Reinstala los scripts en Resolve, a pedido del usuario.

        Normalmente esto ya pasa solo al abrir el programa. El boton queda
        para cuando el usuario instalo Resolve despues, lo reinstalo, o
        simplemente quiere comprobar que estan puestos.
        """
        copiados, error, detalle = instalar_scripts_en_resolve(forzar=True)
        if error:
            log = guardar_log_de_error(error + '\n\n' + informe_scripts_resolve())
            msg = error
            if not resolve_esta_instalado():
                msg += tr('\n\nNo encuentro DaVinci Resolve en este equipo. ¿Está instalado?')
            if log:
                msg += f'\n\nDetalle en:\n{log}'
            messagebox.showerror(tr('No pude instalar los scripts'), msg, parent=self)
            return
        try:
            import instalador_scripts as _ins
            if _ins.edicion_de_resolve() == 'studio':
                self.status_var.set(tr('Resolve Studio: no hacen falta scripts en el menú.'))
                messagebox.showinfo(tr('No hace falta'), tr('Tienes DaVinci Resolve Studio.\n\nAhí el programa se conecta directo con Resolve, así que no hay que instalar nada en el menú ni correr el Puente: los botones ya funcionan solos.\n\n(El menú Scripts es solo para la versión gratuita.)'), parent=self)
                return
        except Exception:
            pass
        ok = [c for c, _cop, err in detalle if err is None]
        donde = '\n'.join((f'  • {c}' for c in ok))
        nombres = '\n'.join((f'  • {n}' for n in sorted(copiados)))
        self.status_var.set(tr('Scripts instalados en Resolve ({len} carpeta(s)).', len=len(ok)))
        aviso = ''
        if resolve_esta_corriendo():
            aviso = tr('\n\nOJO: Resolve está abierto. Resolve arma su menú de Scripts solo al arrancar, así que CIÉRRALO Y VUELVE A ABRIRLO para que aparezcan.')
        messagebox.showinfo(tr('Listo'), tr('Dejé los scripts en:\n{donde}\n\n{nombres}\n\nLos vas a encontrar en:\n{MENU_SCRIPTS}{aviso}', donde=donde, nombres=nombres, MENU_SCRIPTS=MENU_SCRIPTS, aviso=aviso), parent=self)
        self._refrescar_estado()
    def _on_sfx_toggle(self):
        """Al prender la casilla, pregunta de donde tomar los efectos.

        Dos opciones: los 'esenciales' que trae el programa, o una carpeta
        del usuario. La eleccion se guarda en preferencias y se recuerda
        para las proximas veces.
        """
        if not self.sfx_var.get():
            self._guardar_preferencias()
            self._refrescar_receta()
            return
        try:
            import sfx_rules
            categorias = sfx_rules.categorias_disponibles()
        except Exception:
            categorias = {}
        if not categorias:
            self.sfx_var.set(False)
            self.status_var.set(tr('No encontré ningún sonido para usar: revisa la carpeta de efectos (Estudio de sonidos).'))
            self._guardar_preferencias()
            return
        actual = getattr(self, '_sfx_categoria_elegida', None)
        if actual is not None and actual not in categorias:
                actual = None
        preferencia = self._preguntar_fuente_sfx(categorias, actual=actual)
        if preferencia is None:
            if actual is None:
                self.sfx_var.set(False)
                self.status_var.set(tr('Efectos desactivados: no elegiste de dónde tomarlos.'))
                self._guardar_preferencias()
                self._refrescar_receta()
                return
            preferencia = actual
        self._sfx_categoria_elegida = preferencia
        self._actualizar_etiqueta_sfx()
        self.status_var.set(tr('Efectos: tomando de «{preferencia}».', preferencia=preferencia))
        self._guardar_preferencias()
        self._refrescar_receta()
    def _preguntar_fuente_sfx(self, categorias_disponibles, actual=None):
        """Diálogo modal: esenciales, mi carpeta, favoritos O CUALQUIER
        categoria de la libreria.

        Devuelve el nombre de la categoria elegida (por ejemplo 'esenciales'
        o 'usuario/mi_pack') o None si el usuario cancelo.

        Hasta la v1.0.58 recibia 'categorias_disponibles' y LO IGNORABA:
        solo ofrecia Esenciales / carpeta nueva / favoritos, asi que
        'Glitch', 'Riser' o una carpeta ya registrada no se podian elegir
        (pedido literal 09-09: «mi carpeta, los por defecto o los
        favoritos» — y todo lo demas que ya existe).

        'actual' (v1.0.65) es la fuente VIGENTE: se marca con la palomita
        y preselecciona el desplegable. Hasta ahora el dialogo nacia en
        blanco con el desplegable en la primera alfabetica («Bass Hit»)
        — reabierto parecia que no habia guardado nada, y «Usar esta»
        sin tocar el menu mandaba «Bass Hit» en silencio.
        """
        dlg = Dialogo(self, tr('Efectos de sonido: ¿de dónde?'), 500, 440, redimensionable=False)
        capa = _capa_dialogo(dlg, (22, 20, 22, 18), 8)
        capa.addWidget(_titulo(tr('¿De dónde quieres que tome los efectos?'), 16))
        capa.addWidget(_nota(tr('Los agrega en una pista de audio \'SFX\', uno por bloque destacado (los que tienen principal o dos líneas o más).'), 13))
        if actual:
            capa.addWidget(Etiqueta(tr('Fuente actual: «{actual}»', actual=actual), 13, peso='negrita', color=ui.ACCENT_CLARO))
        capa.addSpacing(6)
        resultado = {'eleccion': None}
        def cerrar():
            dlg.cerrar()
        def usar_esenciales():
            resultado['eleccion'] = 'Esenciales'
            cerrar()
        def elegir_carpeta():
            carpeta = filedialog.askdirectory(parent=dlg, title=tr('Elige la carpeta con tus efectos'), mustexist=True)
            if not carpeta:
                return
            try:
                import sfx_rules
                import sfx_studio
                carpetas = sfx_studio.cargar_carpetas_usuario()
                if carpeta not in carpetas:
                    carpetas.append(carpeta)
                    sfx_studio.guardar_carpetas_usuario(carpetas)
                nombre = f'{sfx_rules.PREFIJO_USUARIO}{Path(carpeta).name}'
                if nombre not in sfx_rules.categorias_disponibles():
                    messagebox.showwarning(tr('Esa carpeta está vacía'), tr('No encontré ningún sonido en:\n\n{carpeta}\n\nTiene que tener archivos .wav, .mp3, .aif, .m4a, .flac u .ogg directamente dentro (no en subcarpetas).', carpeta=carpeta), parent=dlg)
                    return
                resultado['eleccion'] = nombre
            except Exception as e:
                messagebox.showerror(tr('No pude usar esa carpeta'), f'{type(e).__name__}: {e}', parent=dlg)
                return
            cerrar()
        def usar_favoritos():
            import sfx_rules
            if sfx_rules.CATEGORIA_FAVORITOS not in sfx_rules.categorias_disponibles():
                messagebox.showinfo(tr('Aún no tienes favoritos'), tr('Marca sonidos con la estrella en el SFX Lab y vuelve aquí: podrás usar justo esos, vengan de donde vengan.'), parent=dlg)
                return
            resultado['eleccion'] = sfx_rules.CATEGORIA_FAVORITOS
            cerrar()
        import sfx_rules as _sfx
        marca_esencial = '✓  ' if actual == 'Esenciales' else ''
        marca_carpeta = '✓  ' if (actual or '').startswith(_sfx.PREFIJO_USUARIO) else ''
        marca_fav = '✓  ' if actual == _sfx.CATEGORIA_FAVORITOS else ''
        capa.addWidget(Boton(tr('{marca_esencial}Los que trae el programa (12 esenciales)', marca_esencial=marca_esencial), usar_esenciales, tipo='primario', alto=42))
        capa.addWidget(Boton(tr('{marca_carpeta}Elegir una carpeta mía', marca_carpeta=marca_carpeta), elegir_carpeta, tipo='neutro', alto=42))
        capa.addWidget(Boton(tr('{marca_fav}★  Mis favoritos del SFX Lab', marca_fav=marca_fav), usar_favoritos, tipo='neutro', alto=42))
        otras = sorted(categorias_disponibles or {})
        if otras:
            fila_cat, cf = caja_h(espacio=8, margenes=(0, 4, 0, 0))
            cf.addWidget(Etiqueta(tr('O una categoría:'), 13, color='#B4C0D6'))
            eleccion_cat = StringVar(actual if actual in otras else otras[0])
            cf.addWidget(Combo(otras, eleccion_cat, ancho=200, alto=36, tam=13), 1)
            def usar_categoria():
                resultado['eleccion'] = eleccion_cat.get()
                cerrar()
            cf.addWidget(Boton(tr('Usar esta'), usar_categoria, tipo='primario', alto=36, ancho=90))
            capa.addWidget(fila_cat)
        capa.addStretch(1)
        capa.addWidget(Boton(tr('Cancelar'), cerrar, tipo='fantasma', alto=36))
        dlg.exec()
        return resultado['eleccion']
    def _cambiar_fuente_sfx(self):
        """Cambia la fuente de los efectos SIN apagar y prender la casilla.

        Hasta la v1.0.58 el dialogo solo salia al prender la casilla con
        la preferencia vacia (_on_sfx_toggle): para cambiar de carpeta
        habia que apagar y volver a prender. Ahora es un enlace directo.
        """
        import sfx_rules
        categorias = sfx_rules.categorias_disponibles()
        if not categorias:
            messagebox.showwarning(tr('Sin sonidos'), tr('No encontré ningún sonido para usar (ni los del programa ni carpetas tuyas).'), parent=self)
            return
        eleccion = self._preguntar_fuente_sfx(categorias, actual=getattr(self, '_sfx_categoria_elegida', None))
        if eleccion:
            self._sfx_categoria_elegida = eleccion
            self._actualizar_etiqueta_sfx()
            self._guardar_preferencias()
            try:
                self.status_var.set(tr('Efectos: tomando de «{eleccion}».', eleccion=eleccion))
            except Exception:
                return None
    def _actualizar_etiqueta_sfx(self):
        """El chip junto al interruptor NOMBRA la fuente vigente.

        v1.0.65: decia «cambiar fuente» a secas — ninguna pantalla
        confirmaba cual fuente estaba activa, asi que una eleccion que
        SI viajaba parecia ignorada («cualquiera que elijas toma la por
        defecto»). Lo que se promete recordar, se enseña.
        """
        actual = getattr(self, '_sfx_categoria_elegida', None)
        texto = tr('Fuente: {actual}', actual=actual) if actual else tr('Elegir fuente')
        try:
            self.sfx_fuente_lbl.configure(text=texto)
        except Exception:
            return None
    def _detectar_con_bridge(self):
        """Dispara el script 'Detectar Video' via API externa en un hilo.

        El render de audio puede tardar minutos; correrlo en primer plano
        congela la ventana. En cuanto termina, un mensaje va al queue del
        poll para que el hilo principal autocomplete el video.
        """
        self.status_var.set(tr('Renderizando el audio del timeline en Resolve...'))
        self._set_inputs_enabled(False)
        self._arrancar_reloj()
        import resolve_bridge
        def worker():
            empezo = time.time()
            try:
                exito, err = resolve_bridge.ejecutar('detectar', timeout=600)
            except Exception as e:
                exito, err = (False, f'{type(e).__name__}: {e}')
            try:
                version_ajena = resolve_bridge.desajuste_de_version(APP_VERSION, resolve_bridge.ultimo_resultado(desde=empezo))
                if version_ajena:
                    self.msg_queue.put(('version_ajena', version_ajena))
            except Exception:
                pass
            if not exito and err and resolve_bridge.es_scripting_cerrado(err):
                        self.msg_queue.put(('scripting_cerrado', str(err)))
            try:
                if resolve_bridge.puente_activo() and resolve_bridge.version_del_puente() != resolve_bridge.VERSION_PUENTE_ESPERADA:
                        self.msg_queue.put(('puente_viejo', resolve_bridge.version_del_puente() or '?'))
            except Exception:
                pass
            self.msg_queue.put(('detect_ready', (exito, err)))
        threading.Thread(target=worker, daemon=True).start()
    def _detectar_desde_resolve(self, silencioso=False):
        """Autocompleta el video con el audio de la linea de tiempo activa.

        Tres caminos, en orden:
          1) Resolve **Studio**: se conecta por la API externa y dispara el
             script 'Detectar Video' en segundo plano (el render puede
             tardar minutos). El usuario no toca nada.
          2) Resolve **Free con el Puente corriendo**: se le encola el
             trabajo al puente y pasa exactamente lo mismo.
          3) Sin ninguno de los dos: se lee el JSON que haya dejado el
             script si el usuario lo corrio a mano alguna vez.
        """
        if silencioso:
            self._detectar_desde_resolve_archivo(silencioso=True)
            return
        self._podar_renders_viejos()
        self._precargar_motores()
        # v5.7: preguntar el modo a Resolve (MCP) tarda hasta ~3 s: en un hilo, no en el de la interfaz (el registro mostraba 7 congelaciones ahí)
        self.status_var.set(tr('Hablando con Resolve…'))
        def trabajo():
            import resolve_bridge
            return resolve_bridge.modo_actual()
        def fin(modo, error):
            if error is None and modo not in (None, 'manual'):
                self._detectar_con_bridge()
                return
            self._detectar_desde_resolve_archivo(silencioso=False)
        correr_en_hilo(self, trabajo, fin)
    def _forzar_deteccion_nueva(self):
        """Renderiza otra vez el audio del timeline que esta abierto ahora.

        Se llama cuando el usuario rechaza una deteccion vieja. Si no hay
        forma automatica (ni API de Studio ni Puente), en vez de dejarlo sin
        respuesta se le explica como habilitarla.
        """
        self.status_var.set(tr('Hablando con Resolve…'))
        def trabajo():
            import resolve_bridge
            return resolve_bridge.modo_actual()          # v5.7: en un hilo (el MCP puede tardar ~3 s en contestar)
        def fin(modo, error):
            if error is not None:
                self.status_var.set(tr('No pude hablar con Resolve: {e}', e=error))
                return
            if modo != 'manual':
                self._detectar_con_bridge()
                return
            self._pedir_detectar_a_mano()
        correr_en_hilo(self, trabajo, fin)
    def _detectar_desde_resolve_archivo(self, silencioso=False):
        """Camino manual: leer el JSON que dejo el script de Detectar Video
        cuando se corrio a mano desde Resolve (o cuando el bridge termino)."""
        try:
            import resolve_bridge
            datos = resolve_bridge.video_detectado()
        except Exception:
            datos = None
        if not datos:
            if not silencioso:
                recien = self._asegurar_scripts_instalados()
                if not scripts_instalados():
                    self._dialogo_scripts_no_instalados()
                    return
                aviso = ''
                if recien:
                    aviso = tr('Ya te dejé los scripts en el menú de Resolve.\nSi Resolve estaba abierto, ciérralo y vuelve a abrirlo para que aparezcan.\n\n')
                self._pedir_detectar_a_mano(aviso)
            return None
        video_path = datos.get('video_path')
        if not video_path or not Path(video_path).exists():
            if not silencioso:
                messagebox.showwarning(tr('Video no encontrado'), tr('Resolve detectó un video, pero ya no está en esa ruta:\n{v}', v=video_path or '(vacío)'), parent=self)
            return None
        edad_minutos = (time.time() - datos.get('detectado_en', 0)) / 60
        limite = 10 if silencioso else 30
        if edad_minutos > limite:
            if silencioso:
                return
            seguir = messagebox.askyesno(tr('Detección antigua'), tr('La última detección en Resolve fue hace {edad_minutos:.0f} minutos; puede que ya no sea el timeline que tienes abierto ahora.\n\nSÍ = usar la detección anterior\nNO = detectar de nuevo el timeline que tienes abierto', edad_minutos=edad_minutos), parent=self)
            if not seguir:
                self._forzar_deteccion_nueva()
                return
        self.video_var.set(video_path)
        nombre_tl = datos.get('timeline_name', '')
        self._marca_entrada = datos.get('mark_in')
        self._marca_salida = datos.get('mark_out')
        self._fps_timeline = datos.get('fps') or 0.0
        self._inicio_timeline = datos.get('timeline_start_frame') or 0
        try:
            self._ancho_timeline = int(datos.get('ancho') or 0)
            self._alto_timeline = int(datos.get('alto') or 0)
        except (TypeError, ValueError):
            self._ancho_timeline = self._alto_timeline = 0
        self._refrescar_formato_detectado()
        if datos.get('desde_timeline'):
            if self._marca_entrada is not None:
                zona = self._zona_marcada_legible()
                self.status_var.set(tr('Solo la zona marcada de \'{nombre_tl}\': {zona}. Los subtítulos van a caer ahí.', nombre_tl=nombre_tl, zona=zona))
            else:
                self.status_var.set(tr('Audio de la línea de tiempo \'{nombre_tl}\' listo para transcribir.', nombre_tl=nombre_tl))
        else:
            self.status_var.set(tr('OJO: esto NO es el audio del timeline, es el archivo \'{name}\'.', name=Path(video_path).name))
            if silencioso:
                return
            motivo = datos.get('diagnostico') or []
            if not datos.get('version'):
                detalle = tr('El script que corriste dentro de Resolve es una versión vieja.\n\nUsa «Reinstalar scripts» en esta ventana, reinicia Resolve, y corre otra vez\nÁrea de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_DetectarVideo')
            else:
                if motivo:
                    detalle = tr('Resolve no pudo renderizar el audio del timeline. Lo que reportó:\n\n• ') + '\n• '.join(motivo[(-4):])
                else:
                    detalle = tr('Resolve no pudo renderizar el audio del timeline.')
            messagebox.showwarning(tr('No es el audio de la línea de tiempo'), tr('{detalle}\n\nPor ahora quedó puesto el archivo de un clip suelto ({name}). Si tu timeline está armado con varios videos, los tiempos NO van a coincidir.\n\nEl detalle completo está en Resolve, en Workspace > Console.', detalle=detalle, name=Path(video_path).name), parent=self)
    def _browse(self):
        path = filedialog.askopenfilename(parent=self, title=tr('Elige tu video'), filetypes=[(tr('Video / audio'), tr('*.mp4 *.mov *.mkv *.avi *.m4v *.webm *.mp3 *.wav *.m4a *.aac *.flac')), (tr('Todos los archivos'), '*.*')])
        if path:
            self.video_var.set(path)
            self._olvidar_marca(tr('elegiste un archivo a mano'))
            self.ir_a('estilos')
    def _olvidar_marca(self, motivo=''):
        """Deja de aplicar el recorte de la deteccion anterior.

        La marca es un offset GLOBAL: mueve todos los subtitulos. Si se queda
        pegada de una deteccion vieja, el proyecto entero sale corrido. Se
        limpia siempre que el audio deja de ser el de esa deteccion.
        """
        tenia = getattr(self, '_marca_entrada', None) is not None
        self._marca_entrada = None
        self._marca_salida = None
        self._ancho_timeline = 0
        self._alto_timeline = 0
        self._refrescar_formato_detectado()
        if tenia and motivo:
                self.status_var.set(tr('Ya no aplico el tramo marcado del timeline anterior ({motivo}).', motivo=motivo))
    def _cargar_proyecto(self, proyecto):
        """Setea el video del proyecto en el selector."""
        vp = proyecto.get('video_path') if isinstance(proyecto, dict) else proyecto
        if not vp or not Path(vp).exists():
            messagebox.showwarning(tr('Video no encontrado'), tr('El archivo original ya no está en su lugar.'), parent=self)
            return
        self.video_var.set(vp)
    def _abrir_proyectos_guardados_main(self):
        win = ProyectosWindow(self, on_load=lambda vp: (self._cargar_proyecto(vp), self.ir_a('nuevo')))
        try:
            win.exec()
        except Exception:
            return None
        self._refrescar_recientes()
    def _arrancar_reloj(self):
        """Muestra cuanto lleva trabajando.

        Transcribir un video largo puede tardar varios minutos, y una barra
        que avanza a saltos sin ningun numero da la sensacion de que se
        colgo. Con el tiempo a la vista se sabe que sigue vivo.
        """
        self._trabajo_desde = time.time()
        self._tick_reloj()
        self._refrescar_pasos()
    def _tick_reloj(self):
        if not self._trabajo_desde:
            self.time_label.configure(text='')
            return
        seg = int(time.time() - self._trabajo_desde)
        self.time_label.configure(text=f'{seg // 60}:{seg % 60:02d}')
        despues(1000, self._tick_reloj, self)
    def _parar_reloj(self):
        self._trabajo_desde = None
        self._refrescar_pasos()
    def _guardar_preferencias(self):
        """Recuerda idioma y opciones para la proxima vez.

        v5.1: se MEZCLA con lo que ya habia: Ajustes guarda en el mismo
        archivo claves que esta funcion no conoce (tema, acento, motor de
        voz, canal beta...) y reescribirlo entero las borraba."""
        try:
            st.SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
            ruta_prefs = st.SHARED_FOLDER / 'preferencias.json'
            cambios = ({
                'idioma': _codigo_de(self.lang_var.get()) or 'es',
                'idiomas_favoritos': [c for c in (
                    _codigo_de(n) for n in self.favoritos_idiomas) if c],
                'traducir': self.translate_var.get(),
                'idioma_destino': _codigo_de(self.destino_var.get())
                or 'en',
                'modo': self._modo(),
                'look': self._look(),
                'formato_video': self._formato_forzado() or 'auto',
                'max_chars': self.chars_var.get(),
                'max_lines': self.lines_var.get(),
                'palabras_por_basico': self.basico_var.get(),
                'tamanos_grupo': getattr(self, 'tamanos_grupo', None),
                'tam_letra_palabras': getattr(self, 'tam_letra_palabras',
                                              None),
                'adelanto_frames': self.adelanto_var.get(),
                'plantilla': self.plantilla_sel,
                'plantilla_basicos': (
                    {'pack': getattr(self, 'basicos_pack',
                                     plantillas.NOMBRE_BASICOS),
                     'combinacion': self.basicos_sel}
                    if getattr(self, 'basicos_sel', '') else ''),
                'diseno_dinamico': getattr(self, 'diseno_dinamico', None),
                'sfx': bool(self.sfx_var.get()),
                'sfx_categoria': getattr(self, '_sfx_categoria_elegida', None),
                'capitalizar': getattr(self, 'capitalizar', True)
                is not False,
                'peso_conectores': getattr(self, 'peso_conectores', None),
                'estilo_palabras': getattr(self, 'estilo_palabras', None),
                'espacio_frases': getattr(self, 'espacio_frases', None),
                'espacio_parrafos': getattr(self, 'espacio_parrafos', None),
                'composicion': composicion.valida(
                    getattr(self, 'composicion', None)),
                'emojis_sistema': getattr(self, 'emojis_sistema', True)
                is not False,
                'emoji_estilo': getattr(self, 'emoji_estilo', 'animado'),
                'aviso_ajustes_visto': bool(getattr(
                    self, 'aviso_ajustes_visto', False)),
                'recetas': self.recetas if isinstance(getattr(self, 'recetas', None), list) else None,
            })
            archivos_seguros.mezclar_json(ruta_prefs, cambios)       # mezcla bajo cerrojo y escritura atómica
        except Exception:
            pass
    def _cargar_preferencias(self):
        try:
            ruta = st.SHARED_FOLDER / 'preferencias.json'
            if not ruta.exists():
                self._refrescar_estrella()
                return
            p = json.loads(ruta.read_text(encoding='utf-8'))
        except Exception:
            return
        codigo = _codigo_de(p.get('idioma'))
        if codigo in NOMBRE_POR_CODIGO:
            idioma = NOMBRE_POR_CODIGO[codigo]
            self.lang_var.set(idioma)
            self._ultimo_idioma = idioma
        favoritos = p.get('idiomas_favoritos')
        if isinstance(favoritos, list):
            self.favoritos_idiomas = [
                NOMBRE_POR_CODIGO[c] for c in (_codigo_de(n) for n in favoritos)
                if c in NOMBRE_POR_CODIGO]
            try:
                self.lang_menu.configure(values=self._menu_idiomas())
            except Exception:
                pass
        self._refrescar_estrella()
        destino = _codigo_de(p.get('idioma_destino'))
        if destino in NOMBRE_POR_CODIGO:
            self.destino_var.set(NOMBRE_POR_CODIGO[destino])
        self._refrescar_destinos()
        self.translate_var.set(bool(p.get('traducir')))
        modo = p.get('modo')
        if modo not in self.MODOS.values():
            modo = 'dinamico' if p.get('dinamico') else 'normal'
        self.modo_var.set(self._etiqueta_de_modo[modo])
        look = p.get('look')
        if look in self.LOOKS.values():
            self.look_var.set(self._etiqueta_de_look[look])
        fmt = p.get('formato_video')
        if fmt in self._etiqueta_de_formato:
            self.formato_var.set(self._etiqueta_de_formato[fmt])
        for var, clave in ((self.chars_var, 'max_chars'),
                           (self.lines_var, 'max_lines'),
                           (self.basico_var, 'palabras_por_basico'),
                           (self.adelanto_var, 'adelanto_frames')):
            if str(p.get(clave, '')).isdigit():
                var.set(str(p[clave]))
        self.tamanos_grupo = p.get('tamanos_grupo')
        self.tam_letra_palabras = p.get('tam_letra_palabras')
        self.peso_conectores = p.get('peso_conectores')
        self.estilo_palabras = p.get('estilo_palabras')
        self.espacio_frases = p.get('espacio_frases')
        self.espacio_parrafos = p.get('espacio_parrafos')
        self.composicion = (composicion.valida(p.get('composicion'))
                            if COMPOSICION_VISIBLE else composicion.valida(None))
        self.emojis_sistema = p.get('emojis_sistema', True) is not False
        self.emoji_estilo = p.get('emoji_estilo') if p.get('emoji_estilo') in ('animado', 'fluent3d', 'noto', 'sistema') else 'animado'          # v5.5: el estilo de los emojis (por defecto animado/3D)
        self.aviso_ajustes_visto = bool(p.get('aviso_ajustes_visto'))
        recetas = p.get('recetas')
        self.recetas = [r for r in recetas if isinstance(r, dict)] if isinstance(recetas, list) else None
        try:
            import emojis
            emojis.estilo(self.emoji_estilo)
        except Exception:
            pass
        self.diseno_dinamico = p.get('diseno_dinamico') or None
        elegido = p.get('plantilla')
        if elegido == 'dinamico':
            elegido = 'auto'
        if elegido in ('auto', 'media_pool'):
            self.plantilla_sel = elegido
        elif elegido and any(pk.nombre == elegido
                             for pk in plantillas.listar_packs()):
            incorporado = plantillas.pack_incorporado()
            if incorporado is not None and elegido == incorporado.nombre:
                self.plantilla_sel = 'auto'
            else:
                self.plantilla_sel = elegido
        bruto_b = p.get('plantilla_basicos')
        if isinstance(bruto_b, dict):
            pack_b = str(bruto_b.get('pack') or '')
            combinacion = str(bruto_b.get('combinacion') or '')
        else:
            pack_b = plantillas.NOMBRE_BASICOS
            combinacion = str(bruto_b or '')
        pos_b, _, n_b = combinacion.partition(' ')
        if (pos_b in ('inferior', 'superior') and n_b.isdigit()
                and int(n_b) >= 1 and pack_b):
            self.basicos_sel = f'{pos_b} {int(n_b)}'
            self.basicos_pack = pack_b
        self.sfx_var.set(bool(p.get('sfx')))
        self.capitalizar = p.get('capitalizar') is not False
        categoria = p.get('sfx_categoria')
        if categoria:
            self._sfx_categoria_elegida = categoria
        self._actualizar_etiqueta_sfx()
        self.plantilla_lbl.configure(text=self._etiqueta_plantilla_completa())
        self._on_modo_change()
    def _set_inputs_enabled(self, enabled: bool):
        if enabled and getattr(self, '_caducada', False):
            return
        if enabled and getattr(self, '_sin_licencia', False):
            return
        self._entradas_activas = bool(enabled)
        for w in [self.video_entry, self.browse_btn, self.detect_btn, self.lang_menu, self.translate_check, self.modo_btn, self.sfx_check, self.generate_btn, self.update_btn,
                  self.browse_btn2, self.detect_btn2, self.zona, self.fav_btn, self.buscar_idioma_btn, self.editar_btn2]:
            w.setEnabled(bool(enabled))
        for chip in self._chips_recetas:
            chip.setEnabled(bool(enabled))
        self._pintar_chips_idioma()
        self._nav['sfx'].setEnabled(bool(enabled) or self._pagina_actual == 'sfx')
        if enabled:
            self._on_modo_change()
        else:
            for w in [self.chars_entry, self.lines_entry]:
                w.configure(state='disabled')
    def _bloquear_por_caducidad(self):
        """Deja la ventana abierta pero sin poder generar.

        Se limita a apagar controles y avisar: no borra nada ni toca disco.
        Los subtitulos que el usuario ya tenga colocados en su timeline son
        suyos y se quedan donde estan.
        """
        self._set_inputs_enabled(False)
        try:
            self.status_label.configure(text=tr('Versión de prueba vencida') + (f' ({fecha_caducidad_texto()})' if CADUCA_EL else '') + '.', text_color='#FF8A80')
        except Exception:
            pass
        despues(200, lambda: messagebox.showinfo(tr('Versión de prueba'), MENSAJE_CADUCADA, parent=self), self)
    def _ofrecer_fuentes_al_arrancar(self):
        """Ofrece instalar TODAS las tipografias de las plantillas incluidas.

        v2.0.1 (reporte literal: «algunas tipografias no estan siendo
        incrustadas: Tempting...»): SI viajaban en fonts/, pero Fusion solo
        ve las del sistema y el boton de instalar vivia escondido en la
        tarjeta de cada plantilla — un cliente nuevo nunca lo encontraba.
        Sigue siendo decision del usuario (toca su sistema): una pregunta,
        una vez por version (marcador en la carpeta compartida). Medir va
        en un hilo: indexar las fuentes byte a byte tarda.
        """
        marcador = st.SHARED_FOLDER / 'fuentes_ofrecidas.txt'
        try:
            if marcador.read_text(encoding='utf-8').strip() == APP_VERSION:
                return
        except OSError:
            pass
        def medir():
            pares = set()
            for pack in plantillas.packs_incorporados():
                try:
                    pares.update(pack.fuentes())
                except Exception:
                    pass
            return instalar_fuentes.faltantes(sorted(pares))[0]
        def preguntar(arreglables, error):
            if error is not None or not arreglables:
                return
            try:
                st.SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
                marcador.write_text(APP_VERSION, encoding='utf-8')
            except OSError:
                pass
            familias = sorted({f for (f, _), _ in arreglables})
            if not messagebox.askyesno(tr('Tipografías de las plantillas'), tr('Las plantillas incluidas usan {len} tipografías que todavía no están instaladas en tu equipo ({join}).\n\nSin instalarlas, Resolve pone otra letra en su lugar.\n\n¿Las instalo ahora? (vienen con el programa)', len=len(arreglables), join=', '.join(familias)), parent=self):
                return
            _correr_en_hilo(self, lambda: instalar_fuentes.instalar(sorted({r for _, r in arreglables})), terminado)
        def terminado(resultado, error):
            instaladas, fallos = resultado or ([], [])
            if error is not None:
                fallos = [(tr('(todas)'), str(error))]
            texto = tr('Instalé {len} tipografías.', len=len(instaladas))
            if sys.platform == 'darwin' and instaladas:
                texto += tr(' Reinicia Resolve para que las vea (lee las tipografías al arrancar).')
            if fallos:
                texto += tr('\n\nNo pude instalar:\n') + '\n'.join((f'· {n}: {m}' for n, m in fallos[:8]))
            messagebox.showinfo(tr('Tipografías'), texto, parent=self)
            self._refrescar_estado()
        _correr_en_hilo(self, medir, preguntar)
    # -- Licencia (v5.2.1: Lemon Squeezy, el sistema de CineSlide; ver licencia.py) -------------
    def _revisar_licencia_al_arrancar(self):
        """La licencia ya se pidió ANTES de abrir la ventana (main -> _licencia_al_abrir). Aquí se
        pinta su estado, se verifica en línea en segundo plano a los 3 s y luego cada 30 min mira
        si pasaron LIC_REVALIDAR_HORAS desde la última verificación (la ventana nunca espera)."""
        self._licencia_refrescar()
        despues(3000, self._licencia_revisar, self)
        self._t_licencia = ui.QTimer(self)
        self._t_licencia.setInterval(30 * 60 * 1000)
        self._t_licencia.timeout.connect(lambda: self._licencia_revisar(False))
        self._t_licencia.start()
    def _trabajando(self):
        """True mientras se transcribe o se genera (no se corta un trabajo a medias)."""
        w = getattr(self, 'worker', None)
        return bool(getattr(self, '_go_corriendo', False) or (w is not None and w.is_alive()))
    def _licencia_revisar(self, forzar=True, manual=False):
        """Verifica la licencia con la tienda en un hilo. forzar=False (reloj de 30 min): solo si la
        última verificación correcta tiene más de LIC_REVALIDAR_HORAS horas."""
        if getattr(self, '_lic_revisando', False):
            return
        if not forzar and licencia.local() and not licencia.toca_revalidar():
            return
        self._lic_revisando = True
        def fin(r, error):
            self._lic_revisando = False
            if r is None:
                r = licencia.ResultadoLicencia(False, 'error', str(error))
            self._licencia_resultado(r, manual)
        _correr_en_hilo(self, lambda: licencia.seguro(licencia.comprobar), fin)
    def _licencia_resultado(self, r, manual=False):
        self._licencia_refrescar()
        if r.ok or (r.codigo in ('sin_conexion', 'error') and licencia.vigente()):
            if manual:
                self.status_var.set(tr('Licencia verificada: activa.') if r.codigo == 'activa' else r.mensaje)
            return
        if self._trabajando():
            despues(60000, self._licencia_revisar, self)
            return
        self._licencia_pedir(r.mensaje, verificar=False)
    def _licencia_lista(self):
        """Antes de GO, generar o regenerar: True si hay una licencia vigente (si no, la pide)."""
        if licencia.vigente():
            return True
        return self._licencia_pedir(tr('Para generar subtítulos activa tu licencia.'))
    def _licencia_pedir(self, motivo='', verificar=True):
        """La ventana de activación. Si se cierra sin una licencia activa, CineCaptions se cierra
        (igual que CineSlide)."""
        if getattr(self, '_lic_pidiendo', False):
            return False
        self._lic_pidiendo = True
        try:
            import ventana_licencia
            ok = ventana_licencia.DialogoLicencia(self, motivo, verificar=verificar and bool(licencia.local())).ejecutar()
        finally:
            self._lic_pidiendo = False
        self._licencia_refrescar()
        if ok:
            self.status_var.set(tr('Licencia activa. ¡Gracias por usar CineCaptions!'))
            return True
        despues(0, self.close, self)
        return False
    def _licencia_refrescar(self):
        """Lleva el estado guardado (sin red) a la tarjeta de Inicio, a Ajustes y a los botones."""
        antes = getattr(self, '_sin_licencia', False)
        self._sin_licencia = not licencia.vigente()
        self._pintar_licencia()
        try:
            ventana = getattr(self, '_ventana_ajustes', None)
            if ventana is not None and vivo(ventana) and hasattr(ventana, '_pintar_licencia'):
                ventana._pintar_licencia()
        except Exception:
            pass
        if self._sin_licencia and not self._trabajando():
            self._set_inputs_enabled(False)
        elif antes and not self._sin_licencia and not getattr(self, '_caducada', False):
            self._set_inputs_enabled(True)
            self.status_var.set(tr('Licencia activa: ya puedes generar subtítulos.'))
    def _abrir_licencia(self):
        """Tarjeta «Licencia» de Inicio y Ajustes: con la licencia activa muestra sus datos (y
        «Desactivar este equipo»); sin ella, la ventana de activar."""
        if not licencia.vigente():
            self._licencia_pedir(verificar=True)
            return
        if getattr(self, '_lic_pidiendo', False):
            return
        self._lic_pidiendo = True
        try:
            import ventana_licencia
            sigue = ventana_licencia.DialogoLicencia(self).ejecutar()
        finally:
            self._lic_pidiendo = False
        self._licencia_refrescar()
        if not sigue:
            # se desactivó este equipo (y no se activó otra clave): sin licencia no se sigue
            despues(0, self.close, self)
    def _on_update(self):
        """Reabre la pantalla de marcas de un video ya transcrito y vuelve a
        generar los subtitulos, sin pasar otra vez por Whisper.

        Es lo que permite retocar un bloque despues de verlo en Resolve: se
        corrige, se regenera, y se vuelve a correr el script de Resolve.
        """
        if self._editor_abierto():
            return
        if not self._licencia_lista():
            return
        raw_path = self.video_var.get().strip().strip('\"')
        if not raw_path:
            messagebox.showwarning(tr('Falta el video'), tr('Elige el mismo video que ya transcribiste, para saber qué marcas cargar.'), parent=self)
            return
        project_name = Path(raw_path).expanduser().stem
        guardadas = cargar_marcas(project_name)
        if not guardadas:
            messagebox.showinfo(tr('No hay marcas guardadas'), tr('No encontré marcas guardadas para \'{project_name}\'.\n\nGenera los subtítulos una primera vez (las marcas se guardan solas al continuar) y después podrás volver acá para retocarlas.', project_name=project_name), parent=self)
            return
        palabras, roles = guardadas
        modo = self._modo()
        if modo == 'dinamico':
            self._asegurar_pack_luxe()          # auditoría v5.11: el editor se construye con el MISMO pack con el que luego se genera
        self._sincronizar_sfx()
        ventana = WordTagWindow(self, palabras, roles, project_name, modo=WordTagWindow.MODO_TEXTO if modo == 'normal' else WordTagWindow.MODO_MARCAS, idioma=self._codigo_idioma())
        resultado = self._sesion_editor(ventana)
        if resultado is None:
            self.status_var.set(tr('Edición cancelada, no se cambió nada.'))
            return
        palabras_finales, roles_finales = resultado
        self._registrar_sfx_manuales(palabras_finales)
        base_lang = LANG_CODE_BY_NAME[self.lang_var.get()]
        if base_lang == 'auto':
            base_lang = 'es'
        if modo == 'normal':
            try:
                self._regenerar_normal(project_name, palabras_finales, base_lang)
            except Exception as e:
                self._gen_fin(False)
                log = guardar_log_de_error(traceback.format_exc())
                msg = f'{type(e).__name__}: {e}'
                if log:
                    msg += tr('\n\nDetalle tecnico guardado en:\n{log}', log=log)
                messagebox.showerror(tr('Algo salio mal'), msg, parent=self)
            return
        self._gen_fase('armar')
        def trabajo():
            try:
                return self._regenerar_marcas(modo, project_name, palabras_finales, roles_finales, base_lang)
            except Exception as e:
                log = guardar_log_de_error(traceback.format_exc())
                msg = f'{type(e).__name__}: {e}'
                if log:
                    msg += tr('\n\nDetalle tecnico guardado en:\n{log}', log=log)
                raise RuntimeError(msg)
        def fin(n_bloques, error):
            if error is not None or n_bloques is None:
                self._gen_fin(False)
                messagebox.showerror(tr('Algo salio mal'), str(error) if error is not None else tr('Sin resultado'), parent=self)
                return
            try:
                self._asegurar_scripts_instalados()
            except Exception:
                pass
            if self._colocar_en_resolve(n_bloques, base_lang.upper()):
                return
            self._gen_fin(False)
            self.status_var.set(tr('Regenerado: {len} bloques. Corre el script en Resolve.', len=n_bloques))
            self._avisar_correr_a_mano(tr('Subtítulos regenerados'), tr('Se regeneraron {len} bloques con tus marcas.', len=n_bloques))
        correr_en_hilo(self, trabajo, fin)
    def _regenerar_marcas(self, modo, project_name, palabras_finales, roles_finales, base_lang):
        """Corre en un hilo (v5.7; antes en el de la interfaz): arma los bloques con las marcas del editor, elige los efectos y los emojis,
        escribe el manifiesto y devuelve cuántos bloques hay. No toca widgets: los avisos van por la cola."""
        import dynamic_subtitles as dyn
        avisar = lambda m: self.msg_queue.put(('status', m))
        estilos_previos = ('destacados',) if modo == 'destacados' else ('dynamic', 'destacados', 'guion', 'kinetic')
        manifest_path = st.SHARED_FOLDER / 'subtitles_manifest.json'
        manifest = {'project': project_name, 'tracks': []}
        pista_previa = {}
        if manifest_path.exists():
            try:
                previo = json.loads(manifest_path.read_text(encoding='utf-8'))
                if previo.get('project') == project_name:
                    for t in previo.get('tracks', []):
                        if t.get('style') in estilos_previos:
                            pista_previa = t
                            break
            except Exception:
                pass
        if modo == 'destacados':
            look = self._look()
            estilo_pintado = None
            medir_ancho = None
            if look == 'pintado':
                estilo_pintado = dict(ESTILO_PINTADO_DEFECTO)
                try:
                    import medir_texto
                    medir_ancho = medir_texto.medidor(estilo_pintado['font'], estilo_pintado['style'], estilo_pintado['size'], tracking=estilo_pintado['tracking'])
                except Exception:
                    medir_ancho = None
                if medir_ancho is None:
                    look = 'acumulativo'
                    estilo_pintado = None
            bloques = dyn.build_destacados_cues(palabras_finales, roles_finales, look=look, medir_ancho=medir_ancho, fin_video=self._fin_video())
            if bloques is None:
                look = 'acumulativo'
                estilo_pintado = None
                bloques = dyn.build_destacados_cues(palabras_finales, roles_finales, look=look, fin_video=self._fin_video())
            pista_sfx = {}
            if self.sfx_var.get():
                self.msg_queue.put(('gen_fase', 'sfx'))
                pista_sfx = self._preparar_sfx(bloques)
            json_path, srt_path = st.write_destacados(bloques, look, project_name, base_lang, st.SHARED_FOLDER, estilo_pintado=estilo_pintado)
            manifest['tracks'].insert(0, {'language': base_lang, 'style': 'destacados', 'data_path': str(json_path), 'srt_path': str(srt_path), 'offset_frames': self._offset_frames(), **pista_sfx})
        else:
            pista_plantilla = self._pista_plantilla()
            con_sfx = bool(self.sfx_var.get())
            if con_sfx:
                self.msg_queue.put(('gen_fase', 'sfx'))
            con_motor = self._generar_con_motor(dyn, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, con_sfx, avisar)
            if con_motor is not None:
                bloques, track_motor, pista_sfx = con_motor
                self._anunciar_receta(pista_plantilla, pista_sfx)
                self._poner_pistas_motor(manifest, track_motor, 0)
            else:
                bloques = dyn.build_manual_cues(palabras_finales, roles_finales, palabras_por_basico=self._palabras_por_basico(), fin_video=self._fin_video(), capitalizar=self._capitalizar(), tamanos=self._tamanos_lineas(), peso_conector=getattr(self, 'peso_conectores', None))
                pista_sfx = {}
                if con_sfx:
                    pista_sfx = self._preparar_sfx(bloques)
                self.msg_queue.put(('gen_fase', 'emojis'))
                pista_emojis = self._preparar_emojis(bloques, palabras_finales, roles_finales)
                if con_sfx:
                    pista_sfx = self._sfx_de_emojis(bloques, pista_sfx)
                pista_composicion = self._pista_composicion(bloques)
                self._anunciar_receta(pista_plantilla, pista_sfx)
                self._estilos_de_bloques(bloques, palabras_finales)
                json_path, srt_path = st.write_dynamic(bloques, project_name, base_lang, st.SHARED_FOLDER)
                manifest['tracks'].insert(0, {'language': base_lang, 'style': 'dynamic', 'data_path': str(json_path), 'srt_path': str(srt_path), 'fonts': pista_previa.get('fonts') or {}, 'adelanto_frames': self._adelanto_frames(), 'offset_frames': self._offset_frames(), **pista_plantilla, **pista_sfx, **pista_emojis, **pista_composicion})
        archivos_seguros.escribir_json(manifest_path, manifest, indent=2)
        sidecar_lua.escribir_sidecar(manifest_path, manifest)
        return len(bloques)
    def _regenerar_normal(self, project_name, palabras_finales, base_lang):
        """La rama NORMAL de regenerar (v1.0.71).

        Reconstruye el .srt con los ajustes VIGENTES (el mismo motor de
        tandas y el mismo selector de palabras que generar) y, si la
        casilla de traducir esta activa, RE-TRADUCE en un hilo (la
        traduccion tarda; congelada aqui la ventana era el «no
        responde»). Los tracks SIN 'style' del manifiesto (el normal y
        el traducido viejos) se reemplazan; los que llevan 'style'
        (dynamic/destacados) se respetan — la simetria exacta de la rama
        dinamica, que hace lo inverso. Con la casilla apagada, la
        traduccion vieja simplemente se retira: dejarla era la
        desincronizada del reporte.
        """
        import dynamic_subtitles as dyn
        manifest_path = st.SHARED_FOLDER / 'subtitles_manifest.json'
        manifest = {'project': project_name, 'tracks': []}
        bloques = dyn.build_manual_cues(palabras_finales, [None] * len(palabras_finales), palabras_por_basico=self._palabras_por_basico(), fin_video=self._fin_video())
        base_cues = [st.Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
        base_srt = st.SHARED_FOLDER / f'{project_name}.{base_lang}.srt'
        st.write_srt(base_cues, 42, 2, base_srt)
        offset = self._offset_frames()
        pista_b = self._pista_basicos()
        manifest['tracks'].append({'language': base_lang, 'srt_path': str(base_srt), 'offset_frames': offset, **pista_b})
        def terminar():
            archivos_seguros.escribir_json(manifest_path, manifest, indent=2)
            sidecar_lua.escribir_sidecar(manifest_path, manifest)
            try:
                self._asegurar_scripts_instalados()
            except Exception:
                pass
            if self._colocar_en_resolve(len(bloques), base_lang.upper()):
                return
            self._gen_fin(False)
            self.status_var.set(tr('Regenerado: {len} bloques. Corre el script en Resolve.', len=len(bloques)))
            self._avisar_correr_a_mano(tr('Subtítulos regenerados'), tr('Se regeneraron {len} bloques con tus marcas.', len=len(bloques)))
        if not self.translate_var.get():
            terminar()
            return
        destino = self._idioma_destino()
        self._set_inputs_enabled(False)
        self.status_var.set(tr('Re-traduciendo los bloques…'))
        def traducir_y_terminar():
            error = None
            try:
                def _log(m):
                    ejecutar_en_ui(lambda m=m: self.status_var.set(str(m)))
                try:
                    ensure_lang_pack(base_lang, destino, log=_log)
                except SystemExit as e:
                    if isinstance(e, lang_packs.SinConexion):
                        raise
                    if base_lang == 'en' or destino == 'en':
                        raise
                    _log(tr('No hay paquete directo {base_lang}->{destino}: voy vía inglés.', base_lang=base_lang, destino=destino))
                    ensure_lang_pack(base_lang, 'en', log=_log)
                    ensure_lang_pack('en', destino, log=_log)
                traducidos = st.translate_cues(base_cues, base_lang, destino)
                srt_destino = st.SHARED_FOLDER / f'{project_name}.{destino}.srt'
                st.write_srt(traducidos, 42, 2, srt_destino)
                manifest['tracks'].append({'language': destino, 'srt_path': str(srt_destino), 'traducida': True, 'offset_frames': offset, **pista_b})
            except SystemExit as e:
                error = str(e)
            except Exception as e:
                error = f'{type(e).__name__}: {e}'
            def en_ui():
                self._set_inputs_enabled(True)
                if error:
                    messagebox.showerror(tr('No pude re-traducir'), tr('{error}\n\nLos subtítulos normales sí se regeneraron; la traducción vieja se retiró para no dejar una desincronizada. Vuelve a regenerar cuando el problema esté resuelto.', error=error), parent=self)
                terminar()
            ejecutar_en_ui(en_ui)
        threading.Thread(target=traducir_y_terminar, daemon=True).start()
    def _on_generate(self):
        if self._editor_abierto():
            return
        if not self._licencia_lista():
            return
        raw_path = self.video_var.get().strip().strip('\"')
        if not raw_path:
            messagebox.showwarning(tr('Falta el video'), tr('Elige un video primero (boton \'Buscar...\').'), parent=self)
            return
        media_path = Path(raw_path).expanduser()
        if not media_path.exists():
            messagebox.showerror(tr('No encuentro el archivo'), tr('No existe este archivo:\n\n{media_path}\n\nRevisa que la ruta este bien escrita.', media_path=media_path), parent=self)
            return
        modo = self._modo()
        con_sfx = modo != 'normal' and self.sfx_var.get()
        max_chars, max_lines = (0, 0)
        source_lang = LANG_CODE_BY_NAME[self.lang_var.get()]
        translate = self.translate_var.get() and modo == 'normal'
        if translate and source_lang == self._idioma_destino():
            nombre = NOMBRE_POR_CODIGO.get(source_lang, source_lang)
            messagebox.showwarning(tr('Traducción innecesaria'), tr('El vídeo ya está en {lower}: traducirlo al mismo idioma no haría nada.\n\nElige otro idioma de destino o quita la casilla de traducir.', lower=_idioma_en_frase(nombre)), parent=self)
            return
        reusar = None
        guardadas = cargar_marcas(media_path.stem)
        if guardadas and guardadas[0]:
                if messagebox.askyesno(tr('Ya transcribiste este video'), tr('Encontré la transcripción de «{stem}» (con tus correcciones y marcas).\n\n¿La reutilizo? Es instantáneo.\n\n(Si dices que no, se vuelve a transcribir el audio.)', stem=media_path.stem), parent=self):
                    reusar = guardadas
        self._reusando = reusar is not None
        self._generado_para = None
        self._set_inputs_enabled(False)
        self.progress.configure(mode='indeterminate')
        self.progress.start()
        self.porcentaje_lbl.configure(text='')
        self._etapa_actual = 'modelo'
        self._poner_etapa('modelo')
        self.status_var.set(tr('Preparando el modelo de IA...'))
        self._guardar_preferencias()
        self._arrancar_reloj()
        self.worker = threading.Thread(target=self._run_pipeline, args=(media_path.resolve(), source_lang, translate, max_chars, max_lines, modo, con_sfx, None, reusar), daemon=True)
        self.worker.start()
    def _registrar_sfx_manuales(self, palabras):
        """v5.4: los sonidos que el usuario cambio a mano en el editor (clic en el punto de una palabra), por tiempo de
        inicio: {inicio_s: ruta, '' = sin sonido}. _preparar_sfx los aplica al generar."""
        self._sfx_manuales = {round(float(w.get('start') or 0), 3): w.get('sfx_archivo') for w in (palabras or []) if 'sfx_archivo' in w}
        self._sfx_inicios = [round(float(w.get('start') or 0), 3) for w in (palabras or []) if str(w.get('word', '')).strip()]
        self._sfx_palabras = [{'t': round(float(w.get('start') or 0), 3), 'fin': round(float(w.get('end') or w.get('start') or 0), 3), 'texto': str(w.get('word', '')).strip()} for w in (palabras or []) if str(w.get('word', '')).strip()]
    def _preparar_sfx(self, bloques, principales=None):
        """Le pone a cada bloque su categoria de efecto y devuelve lo que
        Resolve necesita para encontrar los audios.

        Corre en el hilo de trabajo. Si algo falla (falta la biblioteca, el
        JSON de reglas esta roto), se sigue sin efectos: los subtitulos son
        lo importante y no se pierden por esto.

        `principales` (v5.5): los instantes en que el estilo (VIRAL, Kinetic, «guion») hace entrar su palabra clave; con el modo simple en «Solo la principal»
        el sonido cae ahí. Sin esto se deduce del rol de cada palabra en el bloque.
        """
        if getattr(self, '_un_clic', False):
            self.msg_queue.put(('paso', 'sfx'))
        try:
            import sfx_rules
        except Exception:
            return {}
        try:
            config = sfx_rules.cargar_reglas()
            elegida = getattr(self, '_sfx_categoria_elegida', None)
            disponibles = sfx_rules.categorias_disponibles()
            if not disponibles:
                self.msg_queue.put(('status', tr('No encontré ningún sonido (ni en \'sfx_library\' ni en tus carpetas): se generan los subtítulos sin efectos.')))
                return {}
            sfx_rules.asignar_sfx(bloques, config, categoria=elegida)
            sfx_rules.asignar_archivos(bloques, getattr(self, '_sfx_manuales', None))     # v5.4: el archivo de cada bloque (y lo que cambio el usuario)
            try:                                               # dos risers seguidos abruman: si la página Efectos ya pone el suyo en la intro (con su destello y su zoom), el modo simple no pone otro
                import efectos_visuales as _fx
                if _fx.activado() and _fx.fuente_sonido_intro() is not None:
                    config['simple_intro'] = False
            except Exception:
                pass
            try:
                import recomendaciones
                config['categoria_por_clave'] = recomendaciones.categoria_de_clave          # el sonido propio de cada efecto (solo con «Solo la principal»)
            except Exception:
                pass
            sfx_rules.asignar_eventos_por_palabra(bloques, getattr(self, '_sfx_inicios', None), getattr(self, '_sfx_manuales', None), config=config, palabras=getattr(self, '_sfx_palabras', None), principales=principales)   # modo simple: un sonido por palabra
            perdidas = set()
            for bloque in bloques:
                if bloque.get('sfx') and bloque['sfx'] not in disponibles and not bloque.get('sfx_manual'):
                        perdidas.add(bloque.pop('sfx'))
            cuenta = sfx_rules.resumen(bloques)
            registro.info(f"Efectos de sonido: {sum(len(b.get('sfx_eventos') or [1]) for b in bloques if b.get('sfx'))} sonidos en {sum(1 for b in bloques if b.get('sfx'))} de {len(bloques)} bloques ({', '.join(f'{c}: {n}' for c, n in cuenta.items())}); manuales: {sum(1 for v in (getattr(self, '_sfx_manuales', None) or {}).values())}", 'sfx')
            if not cuenta:
                detalle = tr(' No encontré sonidos en: {join}.', join=', '.join(sorted(perdidas))) if perdidas else ''
                self.msg_queue.put(('status', tr('No pude asignar ningún efecto de sonido.') + detalle + tr(' Los subtítulos se generan igual.')))
                return {}
            archivos = {cat: sfx_rules.archivos_de(cat) for cat in cuenta}
            return {'sfx_library': str(sfx_rules.carpeta_libreria()), 'sfx_archivos': {c: a for c, a in archivos.items() if a}, 'sfx_config': {'nombre_pista_audio': config.get('nombre_pista_audio'), 'volumen_db': config.get('volumen_db'), 'al_inicio': bool(config.get('al_inicio'))}, 'sfx_resumen': cuenta}
        except Exception:
            return {}
    def _pack_guion(self):
        """El pack elegido si es de estilo «guion» (Referencia…: la frase se arma palabra a palabra), o None."""
        try:
            p = plantillas.buscar_pack(getattr(self, 'plantilla_sel', '') or '')
        except Exception:
            return None
        return p if p is not None and getattr(p, 'guion', None) and not getattr(p, 'kinetic', False) else None
    def _pack_kinetic(self):
        """El pack elegido si es el estilo «Kinetic» (títulos de gancho: elementos sueltos —héroe, cintas, anillos…—; kinetic_planificador.py), o None."""
        try:
            p = plantillas.buscar_pack(getattr(self, 'plantilla_sel', '') or '')
        except Exception:
            return None
        return p if p is not None and getattr(p, 'kinetic', False) else None
    def _instantes_main(self, bloques, cues=None):
        """v5.5: los instantes en que entra la palabra PRINCIPAL de cada bloque de un estilo con planificador (la grande de «guion», el héroe de Kinetic, la clave de VIRAL): la línea
        con rol 'main' lleva en 'start' el momento en que sale. Con el modo simple en «Solo la principal» el sonido cae ahí. Devuelve [(instante, clip del efecto o None)]: con los `cues`
        se sabe qué EFECTO lleva (VIRAL: 'v shatter rosa'…; Kinetic: 'k hero …') y el sonido se elige por efecto (recomendaciones.SONIDO_POR_CLAVE)."""
        salida = []
        for i, b in enumerate(bloques):
            clave = None
            cue = cues[i] if cues is not None and i < len(cues) else None
            if cue:
                claves = [str(r.get('k') or '') for r in (cue.get('runs') or [])]
                clave = next((k for k in claves if k.startswith('v shatter') or k.startswith('v select') or k.startswith('v drag')), None) or next((k for k in claves if k.startswith('k hero')), None)
            for l in (b.get('lines') or []):
                if l.get('role') == 'main' and l.get('start') is not None:
                    salida.append((float(l['start']), clave))
        return salida
    def _emojis_con_la_palabra_grande(self, bloques):
        """Estilo «guion»: el emoji de un bloque entra junto con su PALABRA GRANDE (sin ella, con la palabra del emoji) y se queda hasta que se va la
        pila, como los captions. (emojis.asignar lo había pegado a una línea por rol y lo dejaba vivo solo lo que dura la palabra.)"""
        for b in bloques:
            if not b.get('emoji'):
                continue
            lineas = b.get('lines') or []
            if not lineas:
                continue
            k = next((i for i, l in enumerate(lineas) if l.get('role') == 'main'), None)
            if k is None:
                t_w = float(b.get('emoji_ini') or b['start'])
                k = max([i for i, l in enumerate(lineas) if float(l.get('start') or 0) <= t_w + 0.06] or [0])
            b['emoji_linea'] = k
            b['emoji_ini'] = float(lineas[k].get('start') or b['start'])
            b['emoji_fin'] = float(b['end'])
    def _generar_con_guion(self, pack, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, avisar, con_sfx=False):
        """v5.9, el estilo «guion» (pack Referencia): el planificador (guion_planificador.py) arma frases, palabra grande, negritas, pila y
        estilo de cada bloque a partir de las palabras con tiempos, y el script de Resolve coloca cada palabra como su propio clip.
        v5.10: también los SONIDOS (un efecto por palabra cuando entra, según el modo de Sonido) y los EMOJIS (con la palabra grande, y su sonido).
        Devuelve (bloques, track, pista_sfx) con el .json ya escrito (el mismo contrato que _generar_con_motor), o None si no se puede."""
        formato = self._formato_forzado() or self._formato_en_juego() or 'v'
        if formato != 'v' or 'v' not in pack.formatos:
            avisar(tr('El estilo «{p}» es para vídeo vertical: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)))
            return None
        import guion_captions as gc
        import guion_planificador as gp
        try:
            import ajustes_ui
            ancla = str(ajustes_ui.leer_prefs().get('guion_ancla', 'medio'))
        except Exception:
            ancla = 'medio'
        # GO lo decide todo solo; con el editor (Generar / Editar marcas) mandan las marcas del usuario: Principal = grande, Abajo = negrita, Arriba = fina
        # y el estilo que dejó en cada bloque. v5.10: es la MISMA función que usa el editor para «Así se verá este bloque» (guion_editor.planear):
        # lo que se ve ahí es, por construcción, lo que se escribe aquí para Resolve.
        import guion_editor
        res_plan = guion_editor.planear(palabras_finales, roles_finales, pack.nombre, ancla=ancla, fin_video=self._fin_video(), idioma=base_lang,
                                        automatico=bool(getattr(self, '_un_clic', False)))
        cues, plan = res_plan['cues'], res_plan['plan']
        if not cues:
            avisar(tr('No encontré palabras para armar el estilo «{p}»: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)))
            return None
        bloques = []
        for c, b in zip(cues, plan):
            runs = sorted(c['runs'], key=lambda r: r.get('t', 0))
            bloques.append({'start': c['start'], 'end': c['end'], 'fin_hablado': c['end'],
                            'lines': [{'role': {'main': 'main', 'context': 'context', 'complement': 'complement'}.get(r['rol'], 'base'), 'text': r['texto'], 'start': r.get('t', c['start'])} for r in runs]})
        # v5.10: sonidos y emojis, con las mismas piezas del diseño de 3 líneas (sfx_rules, emojis, emojis_sfx) sobre estos bloques: cada palabra es una
        # «línea» con su momento, así que un sonido por palabra cae justo cuando entra y el emoji sale con la palabra grande.
        pista_sfx, pista_emojis = {}, {}
        try:
            self._registrar_sfx_manuales(palabras_finales)          # los inicios de cada palabra, para los modos de un sonido por palabra
            if con_sfx:
                self.msg_queue.put(('status', tr('Eligiendo los efectos de sonido...')))
                pista_sfx = self._preparar_sfx(bloques, self._instantes_main(bloques, cues))
            self.msg_queue.put(('gen_fase', 'emojis'))
            pista_emojis = self._preparar_emojis(bloques, palabras_finales, roles_finales)
            self._emojis_con_la_palabra_grande(bloques)
            if con_sfx:
                pista_sfx = self._sfx_de_emojis(bloques, pista_sfx)
        except Exception:
            registro.excepcion(origen='estilo guion · sonidos y emojis')
        for c, b in zip(cues, bloques):
            c['lines'] = b['lines']                                  # el script de Resolve ubica el golpe del sonido en la palabra grande
            for k in ('sfx', 'sfx_archivo', 'sfx_nombre', 'sfx_manual', 'sfx_original', 'sfx_eventos', 'emoji', 'emoji_ini', 'emoji_fin', 'emoji_linea'):
                if k in b:
                    c[k] = b[k]
        json_path = gc.escribir(cues, st.SHARED_FOLDER / f'{project_name}.{base_lang}.guion.json', base_lang)
        srt_path = st.SHARED_FOLDER / f'{project_name}.{base_lang}.srt'
        try:
            st.write_srt([st.Cue(start=b['start'], end=b['end'], text=' '.join(l['text'] for l in b['lines'])) for b in bloques], 42, 2, srt_path)
        except Exception:
            srt_path = ''
        track = {'language': base_lang, 'style': 'guion', 'data_path': str(json_path), 'srt_path': str(srt_path), 'fonts': {}, 'adelanto_frames': 0,
                 'offset_frames': self._offset_frames(), **pista_plantilla, **pista_sfx, **pista_emojis}
        n_sonidos = sum(len(b.get('sfx_eventos') or [1]) for b in bloques if b.get('sfx'))
        n_emojis = sum(1 for b in bloques if b.get('emoji'))
        avisar(tr('Estilo «{p}»: {n} bloques, {m} con palabra grande · {s} sonidos · {e} emojis.', p=plantillas.nombre_visible(pack.nombre), n=len(cues), m=sum(1 for b in plan if b['mains']), s=n_sonidos, e=n_emojis))
        return (bloques, track, pista_sfx)
    def _generar_con_kinetic(self, pack, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, avisar, con_sfx=False):
        """El estilo «Kinetic» (pack Kinetic: títulos de gancho): el planificador (kinetic_planificador.py) parte lo hablado en bloques, elige la palabra
        héroe y una receta (héroe con degradado, líneas pequeñas, cintas, serif, pincel, anillo, subrayado) y apila los elementos; el script de Resolve
        coloca cada elemento como su propio clip del pack. Con el editor mandan las palabras marcadas como Principal (héroes forzados); GO decide solo.
        Sonidos: el mismo modo de Sonido (un golpe cuando entra la palabra héroe). Sin emojis (no forman parte de este estilo).
        Devuelve (bloques, track, pista_sfx) con el .json ya escrito (el mismo contrato que _generar_con_guion), o None si no se puede."""
        formato = self._formato_forzado() or self._formato_en_juego() or 'v'
        es_viral = bool(getattr(pack, 'viral', False))
        if formato not in (('v', 'h') if es_viral else ('v',)) or formato not in pack.formatos:
            avisar(tr('El estilo «{p}» es para vídeo vertical u horizontal: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)) if es_viral
                   else tr('El estilo «{p}» es para vídeo vertical: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)))
            return None          # el estilo «VIRAL» comparte este camino (mismo contrato de bloques, sonidos y colocador de Resolve): otro planificador y otros clips
        if es_viral:
            import viral_captions as kc
            import viral_planificador as kp
        else:
            import kinetic_captions as kc
            import kinetic_planificador as kp
        try:
            import ajustes_ui
            ancla = str(ajustes_ui.leer_prefs().get('viral_ancla' if es_viral else 'kinetic_ancla', 'bajo'))
        except Exception:
            ancla = 'bajo'
        mains = None
        if not getattr(self, '_un_clic', False):
            try:
                import guion_editor
                mains = guion_editor.parametros_de_marcas(palabras_finales, roles_finales)[0]
            except Exception:
                mains = None
        if es_viral:
            ancho_tl, alto_tl = int(getattr(self, '_ancho_timeline', 0) or 0), int(getattr(self, '_alto_timeline', 0) or 0)
            if not (ancho_tl > 0 and alto_tl > 0):
                ancho_tl, alto_tl = (1920, 1080) if formato == 'h' else (1080, 1920)
            res = kp.planificar(palabras_finales, idioma=base_lang, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, fin_video=self._fin_video())
        else:
            res = kp.planificar(palabras_finales, idioma=base_lang, ancla=ancla, mains=mains, fin_video=self._fin_video())
        cues, plan = res['cues'], res['plan']
        if not cues:
            avisar(tr('No encontré palabras para armar el estilo «{p}»: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)))
            return None
        bloques = [{'start': c['start'], 'end': c['end'], 'fin_hablado': c['end'],
                    'lines': [{'role': l['role'], 'text': l['text'], 'start': l['start']} for l in c['lines']]} for c in cues]
        pista_sfx, pista_emojis = {}, {}
        try:
            self._registrar_sfx_manuales(palabras_finales)
            if con_sfx:
                self.msg_queue.put(('status', tr('Eligiendo los efectos de sonido...')))
                pista_sfx = self._preparar_sfx(bloques, self._instantes_main(bloques, cues))
            if es_viral:                                          # VIRAL sí lleva emojis (Kinetic no): con la palabra clave, y su sonido, como el estilo «guion»
                self.msg_queue.put(('gen_fase', 'emojis'))
                pista_emojis = self._preparar_emojis(bloques, palabras_finales, roles_finales)
                self._emojis_con_la_palabra_grande(bloques)
                if con_sfx:
                    pista_sfx = self._sfx_de_emojis(bloques, pista_sfx)
        except Exception:
            registro.excepcion(origen='estilo kinetic · sonidos' if not es_viral else 'estilo viral · sonidos y emojis')
        for c, b in zip(cues, bloques):
            for k in ('sfx', 'sfx_archivo', 'sfx_nombre', 'sfx_manual', 'sfx_original', 'sfx_eventos', 'emoji', 'emoji_ini', 'emoji_fin', 'emoji_linea'):
                if k in b:
                    c[k] = b[k]
        json_path = kc.escribir(cues, st.SHARED_FOLDER / f'{project_name}.{base_lang}.kinetic.json', base_lang)
        srt_path = st.SHARED_FOLDER / f'{project_name}.{base_lang}.srt'
        try:
            st.write_srt([st.Cue(start=b['start'], end=b['end'], text=' '.join(l['text'] for l in b['lines'])) for b in bloques], 42, 2, srt_path)
        except Exception:
            srt_path = ''
        track = {'language': base_lang, 'style': 'kinetic', 'data_path': str(json_path), 'srt_path': str(srt_path), 'fonts': {}, 'adelanto_frames': 0,
                 'offset_frames': self._offset_frames(), **pista_plantilla, **pista_sfx, **pista_emojis}
        if es_viral:
            track['clip_prueba'] = 'v fina'                       # el clip que prueba que el bin del pack VIRAL está completo (el de Kinetic es «k hero blanco»)
        n_sonidos = sum(len(b.get('sfx_eventos') or [1]) for b in bloques if b.get('sfx'))
        avisar(tr('Estilo «{p}»: {n} bloques de títulos · {s} sonidos.', p=plantillas.nombre_visible(pack.nombre), n=len(cues), s=n_sonidos))
        return (bloques, track, pista_sfx)
    def _pack_mezcla(self):
        """El pack elegido si es un estilo propio que MEZCLA looks de los tres temas («Crea tu estilo», mezcla_planificador.py), o None."""
        try:
            p = plantillas.buscar_pack(getattr(self, 'plantilla_sel', '') or '')
        except Exception:
            return None
        return p if p is not None and getattr(p, 'mezcla', False) else None
    def _generar_con_mezcla(self, pack, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, avisar, con_sfx=False):
        """v5.4.30, «Crea tu estilo» con looks de los TRES temas: mezcla_planificador.py parte lo hablado en tramos (una o varias frases) y a cada uno le pone un look de la lista del pack
        (Tema 1 = Kinetic, Tema 2 = Referencia, Tema 3 = VIRAL) con el planificador de ESE tema. Salen dos listas de bloques: las de formato «kinetic» (Tema 1 y Tema 3, mismo colocador de
        Resolve) y las de formato «guion» (Tema 2): dos pistas de datos en el manifiesto (manifest['mezcla'] = True: Resolve las coloca en la misma corrida sin que una borre a la otra).
        Los sonidos van por todos los bloques; los emojis, solo en los de VIRAL y «guion» (los títulos de Kinetic no llevan).
        Devuelve (bloques, track, pista_sfx) como los demás generadores; las pistas de más viajan en track['mezcla_pistas'] (las separa _poner_pistas_motor), o None si no se puede."""
        formato = self._formato_forzado() or self._formato_en_juego() or 'v'
        if formato != 'v':
            avisar(tr('El estilo «{p}» es para vídeo vertical: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)))
            return None
        import guion_captions as gc
        import kinetic_captions as kc
        import mezcla_planificador as mp
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            prefs = {}
        mains = None
        if not getattr(self, '_un_clic', False):
            try:
                import guion_editor
                mains = guion_editor.parametros_de_marcas(palabras_finales, roles_finales)[0]
            except Exception:
                mains = None
        ancho_tl, alto_tl = int(getattr(self, '_ancho_timeline', 0) or 0), int(getattr(self, '_alto_timeline', 0) or 0)
        if not (ancho_tl > 0 and alto_tl > 0):
            ancho_tl, alto_tl = 1080, 1920
        res = mp.planificar(palabras_finales, pack.looks, base_lang, ancho_tl, alto_tl, ancla_kinetic=str(prefs.get('kinetic_ancla', 'bajo')), ancla_viral=str(prefs.get('viral_ancla', 'bajo')),
                            ancla_guion=str(prefs.get('guion_ancla', 'medio')), mains=mains, fin_video=self._fin_video())
        orden = res['orden']                                            # [(motor, cue)] por tiempo: 'kinetic' | 'viral' | 'guion'
        if not orden:
            avisar(tr('No encontré palabras para armar el estilo «{p}»: uso el diseño de siempre.', p=plantillas.nombre_visible(pack.nombre)))
            return None
        cues_orden = [c for _m, c in orden]
        bloques = []
        for motor, c in orden:
            if motor == 'guion':
                lineas = [{'role': {'main': 'main', 'context': 'context', 'complement': 'complement'}.get(r['rol'], 'base'), 'text': r['texto'], 'start': r.get('t', c['start'])}
                          for r in sorted(c['runs'], key=lambda r: r.get('t', 0))]
            else:
                lineas = [{'role': l['role'], 'text': l['text'], 'start': l['start']} for l in c['lines']]
            bloques.append({'start': c['start'], 'end': c['end'], 'fin_hablado': c['end'], 'lines': lineas})
        pista_sfx, pista_emojis = {}, {}
        try:
            self._registrar_sfx_manuales(palabras_finales)
            if con_sfx:
                self.msg_queue.put(('status', tr('Eligiendo los efectos de sonido...')))
                pista_sfx = self._preparar_sfx(bloques, self._instantes_main(bloques, cues_orden))
            self.msg_queue.put(('gen_fase', 'emojis'))
            con_emoji = [b for b, (m, _c) in zip(bloques, orden) if m != 'kinetic']
            if con_emoji:
                pista_emojis = self._preparar_emojis(con_emoji, palabras_finales, roles_finales)
                self._emojis_con_la_palabra_grande(con_emoji)
            if con_sfx:
                pista_sfx = self._sfx_de_emojis(bloques, pista_sfx)
        except Exception:
            registro.excepcion(origen='estilo mezclado · sonidos y emojis')
        for c, b in zip(cues_orden, bloques):
            c['lines'] = b['lines']                                    # el script de Resolve ubica el golpe del sonido en la palabra grande
            for k in ('sfx', 'sfx_archivo', 'sfx_nombre', 'sfx_manual', 'sfx_original', 'sfx_eventos', 'emoji', 'emoji_ini', 'emoji_fin', 'emoji_linea'):
                if k in b:
                    c[k] = b[k]
        srt_path = st.SHARED_FOLDER / f'{project_name}.{base_lang}.srt'
        try:
            st.write_srt([st.Cue(start=b['start'], end=b['end'], text=' '.join(l['text'] for l in b['lines'])) for b in bloques], 42, 2, srt_path)
        except Exception:
            srt_path = ''
        comun = {'language': base_lang, 'srt_path': str(srt_path), 'fonts': {}, 'adelanto_frames': 0, 'offset_frames': self._offset_frames(), **pista_sfx, **pista_emojis}
        forzado = self._formato_forzado()
        pistas = []
        lado_k = [c for m, c in orden if m in ('kinetic', 'viral')]
        lado_g = [c for m, c in orden if m == 'guion']
        if lado_k:
            hay_t1, hay_t3 = 'kinetic' in res['packs'], 'viral' in res['packs']
            json_k = kc.escribir(lado_k, st.SHARED_FOLDER / f'{project_name}.{base_lang}.kinetic.json', base_lang)
            track_k = {**comun, 'style': 'kinetic', 'data_path': str(json_k), **plantillas.para_manifiesto('Kinetic' if hay_t1 else 'VIRAL', formato_forzado=forzado)}
            if not hay_t1:
                track_k['clip_prueba'] = 'v fina'                       # el clip que prueba que el bin del pack VIRAL está completo (el de Kinetic es «k hero blanco»)
            elif hay_t3:
                extra = plantillas.para_manifiesto('VIRAL', formato_forzado=forzado)
                if extra.get('plantilla'):
                    track_k['plantillas_extra'] = [{'plantilla': extra['plantilla'], 'clip_prueba': 'v fina'}]      # los clips «v …» de VIRAL junto a los «k …» de Kinetic
            pistas.append(track_k)
        if lado_g:
            json_g = gc.escribir(lado_g, st.SHARED_FOLDER / f'{project_name}.{base_lang}.guion.json', base_lang)
            pistas.append({**comun, 'style': 'guion', 'data_path': str(json_g), **plantillas.para_manifiesto('Referencia', formato_forzado=forzado)})
        track = pistas[0]
        track['mezcla_pistas'] = pistas[1:]
        n_sonidos = sum(len(b.get('sfx_eventos') or [1]) for b in bloques if b.get('sfx'))
        n_emojis = sum(1 for b in bloques if b.get('emoji'))
        avisar(tr('Estilo «{p}»: {n} bloques de {t} tramos · {s} sonidos · {e} emojis.', p=plantillas.nombre_visible(pack.nombre), n=len(cues_orden), t=len(res['tramos']), s=n_sonidos, e=n_emojis))
        return (bloques, track, pista_sfx)
    def _poner_pistas_motor(self, manifest, track_motor, posicion=None):
        """Mete en el manifiesto la pista del generador (y, en un estilo mezclado, las demás: track['mezcla_pistas'], marcando manifest['mezcla'] para que Resolve limpie una sola vez)."""
        extra = track_motor.pop('mezcla_pistas', None)
        pistas = [track_motor] + list(extra or [])
        if extra is not None:
            manifest['mezcla'] = True
        if posicion is None:
            manifest['tracks'].extend(pistas)
        else:
            manifest['tracks'][posicion:posicion] = pistas
    def _generar_con_motor(self, dyn, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, con_sfx, avisar):
        """El MOTOR del preset del Diseño dinámico (v1.0.51).

        Un preset ya no es solo colores: 'motor' cambia la ESTRUCTURA de
        los bloques (Gadzhi = 2 lineas apiladas, Hormozi = karaoke
        pintado), y esa estructura se arma AQUI, antes de escribir el
        manifiesto — los gemelos de Resolve nunca ven 'motor', ven bloques
        ya armados.

        Devuelve None si el diseño elegido no trae motor (el llamador arma
        las 3 lineas de siempre), o (bloques, track, pista_sfx) con el
        .json ya escrito. Se usa desde GENERAR y desde REGENERAR: una sola
        implementacion, no dos que se separen (la regla de repartir_bloque).

        'avisar' recibe los mensajes de estado (la cola en el hilo de
        generar, status_var en regenerar): las degradaciones no son mudas.
        """
        pack_mezcla = self._pack_mezcla()
        if pack_mezcla is not None:
            return self._generar_con_mezcla(pack_mezcla, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, avisar, con_sfx)
        pack_kinetic = self._pack_kinetic()
        if pack_kinetic is not None:
            return self._generar_con_kinetic(pack_kinetic, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, avisar, con_sfx)
        pack_guion = self._pack_guion()
        if pack_guion is not None:
            return self._generar_con_guion(pack_guion, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, avisar, con_sfx)
        diseno = (pista_plantilla or {}).get('diseno') or {}
        motor = diseno.get('motor')
        if not motor:
            return
        roles = list(roles_finales)
        if not any((r is not None for r in roles)):
            roles = dyn.suggest_roles(palabras_finales)
            avisar(tr('Palabras clave elegidas automáticamente (no marcaste ninguna; puedes retocarlas en «Editar marcas»).'))
        if motor == 'dos_lineas':
            bloques = dyn.build_manual_cues(palabras_finales, roles, palabras_por_basico=self._palabras_por_basico(), fin_video=self._fin_video(), tamanos=self._tamanos_lineas(), peso_conector=getattr(self, 'peso_conectores', None))
            bloques = dyn.a_dos_lineas(bloques)
            pista_sfx = {}
            if con_sfx:
                avisar(tr('Eligiendo los efectos de sonido...'))
                pista_sfx = self._preparar_sfx(bloques)
            json_path, srt_path = st.write_dynamic(bloques, project_name, base_lang, st.SHARED_FOLDER)
            track = {'language': base_lang, 'style': 'dynamic', 'data_path': str(json_path), 'srt_path': str(srt_path), 'fonts': {}, 'adelanto_frames': self._adelanto_frames(), 'offset_frames': self._offset_frames(), **pista_plantilla, **pista_sfx}
            return (bloques, track, pista_sfx)
        if motor != 'pintado':
            avisar(tr('Motor \'{motor}\' desconocido: uso las 3 líneas de siempre.', motor=motor))
            return
        roles_clave = [r if r == 'main' else None for r in roles]
        look = 'pintado'
        formato = self._formato_forzado() or self._formato_en_juego() or 'h'
        limite = dyn.CHARS_POR_FILA_PINTADO.get(formato, dyn.CHARS_POR_FILA_PINTADO['h'])
        cfg = plantillas.pintado_para_manifiesto(diseno, formato)
        estilo_destacados = plantillas.destacados_para_manifiesto(diseno)
        base_e = cfg['estilo_base']
        medir_ancho = None
        try:
            import medir_texto
            medir_ancho = medir_texto.medidor(base_e['font'], base_e['style'], base_e['size'], tracking=base_e['tracking'])
        except Exception:
            medir_ancho = None
        if medir_ancho is None:
            avisar(tr('No encontré la fuente \'{v}\' para medir el pintado: uso texto acumulativo con los mismos colores.', v=base_e['font']))
            look = 'acumulativo'
        else:
            if cfg.get('size_capado'):
                avisar(tr('Tamaño ajustado a {v:.3f} para que quepan {limite} caracteres por fila en este formato.', v=base_e['size'], limite=limite))
        bloques = dyn.build_destacados_cues(palabras_finales, roles_clave, look=look, medir_ancho=medir_ancho, limite_chars=limite, filas_max=cfg['filas_max'], modo_pintado=cfg['modo'], fin_video=self._fin_video())
        if bloques is None:
            avisar(tr('No pude medir todas las palabras para el pintado: uso texto acumulativo con los mismos colores.'))
            look = 'acumulativo'
            bloques = dyn.build_destacados_cues(palabras_finales, roles_clave, look=look, fin_video=self._fin_video())
        pista_sfx = {}
        if con_sfx:
            avisar(tr('Eligiendo los efectos de sonido...'))
            pista_sfx = self._preparar_sfx(bloques)
        json_path, srt_path = st.write_destacados(bloques, look, project_name, base_lang, st.SHARED_FOLDER, estilo_destacados=estilo_destacados, pintado=cfg if look == 'pintado' else None)
        track = {'language': base_lang, 'style': 'destacados', 'data_path': str(json_path), 'srt_path': str(srt_path), 'offset_frames': self._offset_frames(), **pista_plantilla, **pista_sfx}
        return (bloques, track, pista_sfx)
    def _run_pipeline(self, media_path, source_lang, translate, max_chars,
                      max_lines, modo='dinamico', con_sfx=False,
                      fuentes=None, reusar=None):
        ui.prioridad_hilo(-1)            # el trabajo pesado cede el paso a la interfaz
        if not getattr(self, '_un_clic', False):
            self._vigilar_tarea('generar', 'voz', hilo=threading.current_thread())          # v5.11 (GO ya se vigila desde _go)
        """Corre en un hilo aparte. NO toca widgets: solo escribe en la cola.

        Ojo: subtitle_transcriber usa `raise SystemExit(msg)` para reportar
        errores, lo cual esta bien en consola pero dentro de un hilo mataria
        el hilo en silencio y la barra se quedaria congelada para siempre.
        Por eso se captura SystemExit explicitamente aca abajo.
        """
        try:
            if not licencia.vigente():
                raise SystemExit(licencia.mensaje_sin_licencia())
            st.SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
            try:                          # v5.5: mientras se transcribe, las secuencias de los emojis populares se van dejando listas
                import emojis as _emo
                _emo.precalentar_secuencias()
            except Exception:
                pass
            project_name = media_path.stem
            try:
                self.msg_queue.put(('duracion', st._duracion_segundos(str(media_path))))           # los tiempos esperados de GO dependen de ella
            except Exception:
                pass
            self._efectos_plan = None
            cortes_fx = self._buscar_cortes_en_paralelo(media_path)           # v5.4.6: la página «Efectos» (si está activa) busca los cortes mientras se transcribe
            try:                                                              # v5.4.8: y deja listas las secuencias de los iconos (no hay que esperarlas al colocar)
                import efectos_visuales as _fx
                _fx.precalentar_secuencias(media_path)
            except Exception:
                pass
            transcribe_share = 0.7 if translate else 1.0
            def on_model_loaded():
                self.msg_queue.put(('phase_determinate', None))
                self.msg_queue.put(('status', tr('Transcribiendo el audio...')))
            def on_transcribe_progress(frac):
                self._punto_control_go()
                self.msg_queue.put(('progress', frac * transcribe_share))
            if reusar:
                words = [dict(w) for w in reusar[0]]
                self._registrar_sfx_manuales(words)
            else:
                # v5.4.8: la misma voz (mismo video, idioma, motor y modelo) no se transcribe dos veces
                words = None
                try:
                    import cache_voz
                    words = cache_voz.leer(media_path, source_lang, MODEL_SIZE)
                except Exception:
                    words = None
                if words:
                    registro.info(f'Voz: transcripción reutilizada ({len(words)} palabras)', 'voz')
                    self.msg_queue.put(('status', tr('Este video ya estaba transcrito: uso esa transcripción.')))
                    self.msg_queue.put(('progress', transcribe_share))
                else:
                    words = st.transcribe(str(media_path), source_lang, MODEL_SIZE, progress_callback=on_transcribe_progress, model_loaded_callback=on_model_loaded, status_callback=lambda t: self.msg_queue.put(('status', t)))
                    try:
                        import cache_voz
                        cache_voz.guardar(media_path, source_lang, MODEL_SIZE, words)
                    except Exception:
                        pass
            self._punto_control_go()
            if not words:
                raise SystemExit(self._sin_palabras_mensaje())
            self._abortar_si_fallo_el_timeline()          # un video soltado sin su timeline en Resolve: no se sigue (ni se gastan los minutos de la IA)
            words = self._recortar_pausas(words, media_path)         # v5.4.8: «Quitar pausas» (si el usuario lo pidió): los tiempos de las palabras pasan a ser los del video recortado
            # v5.4.40: el plan de efectos (cortes, música, golpes de sonido) solo depende de las palabras oídas: con GO se hace en OTRO hilo mientras la IA corrige el texto
            self._efectos_hilo = None
            if getattr(self, '_un_clic', False):
                self._efectos_hilo = threading.Thread(target=self._planificar_efectos, args=(media_path, words, cortes_fx, False), daemon=True, name='fx-plan')
                self._efectos_hilo.start()
            base_lang = source_lang
            if source_lang == 'auto':
                # con «auto» el idioma es el que se OYÓ (antes se daba por español y la corrección del texto «arreglaba» el inglés con palabras en español)
                base_lang = st.idioma_detectado(words) or 'es'
                registro.info(f'Idioma detectado: {base_lang}', 'voz')
                self.msg_queue.put(('idioma', base_lang))
            manifest = {'project': project_name, 'tracks': []}
            if modo == 'destacados':
                import dynamic_subtitles as dyn
                palabras = [w for w in words if w['word'].strip()]
                sugeridos = [None] * len(palabras)
                self.msg_queue.put(('phase_determinate', None))
                self.msg_queue.put(('progress', 1.0))
                self._tag_event.clear()
                self.msg_queue.put(('need_tags', (palabras, sugeridos, project_name)))
                self._tag_event.wait()
                if self._tag_result is None:
                    raise SystemExit(tr('Generación cancelada por el usuario.'))
                self.msg_queue.put(('phase_indeterminate', None))
                self.msg_queue.put(('status', tr('Armando los bloques destacados...')))
                self.msg_queue.put(('gen_fase', 'armar'))
                palabras_finales, roles_finales = self._tag_result
                self._registrar_sfx_manuales(palabras_finales)
                con_sfx = bool(self.sfx_var.get())              # el editor aplica la receta de GO (efectos según su interruptor)
                look = self._look()
                estilo_pintado = None
                medir_ancho = None
                if look == 'pintado':
                    estilo_pintado = dict(ESTILO_PINTADO_DEFECTO)
                    try:
                        import medir_texto
                        medir_ancho = medir_texto.medidor(estilo_pintado['font'], estilo_pintado['style'], estilo_pintado['size'], tracking=estilo_pintado['tracking'])
                    except Exception:
                        medir_ancho = None
                    if medir_ancho is None:
                        self.msg_queue.put(('status', tr('No encontré la fuente \'{v}\' para medir el pintado: uso \'acumulativo\' en su lugar.', v=estilo_pintado['font'])))
                        look = 'acumulativo'
                        estilo_pintado = None
                bloques = dyn.build_destacados_cues(palabras_finales, roles_finales, look=look, medir_ancho=medir_ancho, fin_video=self._fin_video())
                if bloques is None:
                    self.msg_queue.put(('status', tr('No pude medir todas las palabras para el pintado: uso \'acumulativo\' en su lugar.')))
                    look = 'acumulativo'
                    estilo_pintado = None
                    bloques = dyn.build_destacados_cues(palabras_finales, roles_finales, look=look, fin_video=self._fin_video())
                pista_sfx = {}
                if con_sfx:
                    self.msg_queue.put(('gen_fase', 'sfx'))
                    self.msg_queue.put(('status', tr('Eligiendo los efectos de sonido...')))
                    pista_sfx = self._preparar_sfx(bloques)
                json_path, base_srt = st.write_destacados(bloques, look, project_name, base_lang, st.SHARED_FOLDER, estilo_pintado=estilo_pintado)
                manifest['tracks'].append({'language': base_lang, 'style': 'destacados', 'data_path': str(json_path), 'srt_path': str(base_srt), 'offset_frames': self._offset_frames(), **pista_sfx})
                base_cues = [st.Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
                n_bloques = len(bloques)
            else:
                if modo == 'dinamico':
                    import dynamic_subtitles as dyn
                    palabras = [w for w in words if w['word'].strip()]
                    sugeridos = [None] * len(palabras)
                    if getattr(self, '_un_clic', False):
                        # v5.1, el boton GO: la IA corrige el texto y elige las
                        # palabras (sin abrir el editor); queda guardado para
                        # retocarlo luego con «Editar marcas»
                        import ia_texto
                        self.msg_queue.put(('paso', 'ia'))
                        self.msg_queue.put(('phase_determinate', None))
                        self.msg_queue.put(('status', tr('La IA corrige el texto y elige las palabras clave…')))
                        palabras_finales, roles_finales, resumen_ia = ia_texto.marcar_todo(
                            palabras, base_lang, progreso=lambda f: self.msg_queue.put(('progress', f)),
                            estado=lambda t: self.msg_queue.put(('status', t)),
                            tamanos=getattr(self, 'tamanos_grupo', None), peso_conector=getattr(self, 'peso_conectores', None),
                            con_emojis=self._go_emojis())           # auditoría v5.11: el chip «Emojis: no» de Inicio se respetaba solo de palabra
                        self._resumen_ia = resumen_ia
                        roles_guardar = roles_finales
                        try:
                            # auditoría v5.11: con un pack «guion» GO ignora los roles de la IA (los de 3 líneas) y arma con el planificador; lo que queda
                            # guardado para «Editar marcas» tiene que ser lo que GO colocó, no roles de otro diseño que el editor leería distinto
                            import guion_editor
                            pack_g = self._pack_guion()
                            formato_g = self._formato_forzado() or self._formato_en_juego() or 'v'
                            if pack_g is not None and guion_editor.es_guion(pack_g.nombre, formato_g):
                                try:
                                    import ajustes_ui
                                    ancla_g = str(ajustes_ui.leer_prefs().get('guion_ancla', 'medio'))
                                except Exception:
                                    ancla_g = 'medio'
                                roles_guardar = guion_editor.roles_automaticos(palabras_finales, pack_g.nombre, ancla=ancla_g, fin_video=self._fin_video(), idioma=base_lang)
                        except Exception:
                            registro.excepcion(origen='GO · marcas del estilo guion')
                        try:
                            guardar_marcas(project_name, palabras_finales, roles_guardar)
                        except Exception:
                            pass
                        self.msg_queue.put(('paso', 'diseno'))
                    else:
                        self.msg_queue.put(('phase_determinate', None))
                        self.msg_queue.put(('progress', 1.0))
                        self._tag_event.clear()
                        self.msg_queue.put(('need_tags', (palabras, sugeridos, project_name)))
                        self._tag_event.wait()
                        if self._tag_result is None:
                            raise SystemExit(tr('Generación cancelada por el usuario.'))
                        palabras_finales, roles_finales = self._tag_result
                        self._registrar_sfx_manuales(palabras_finales)
                        con_sfx = bool(self.sfx_var.get())          # el editor aplica la receta de GO (efectos según su interruptor)
                    self.msg_queue.put(('phase_indeterminate', None))
                    self.msg_queue.put(('status', tr('Armando los bloques con tus marcas...')))
                    self.msg_queue.put(('gen_fase', 'armar'))
                    pista_plantilla = self._pista_plantilla()
                    if con_sfx:
                        self.msg_queue.put(('gen_fase', 'sfx'))
                    con_motor = self._generar_con_motor(dyn, palabras_finales, roles_finales, pista_plantilla, project_name, base_lang, con_sfx, lambda m: self.msg_queue.put(('status', m)))
                    if con_motor is not None:
                        bloques, track_motor, pista_sfx = con_motor
                        self._anunciar_receta(pista_plantilla, pista_sfx)
                        self._poner_pistas_motor(manifest, track_motor)
                    else:
                        bloques = dyn.build_manual_cues(palabras_finales, roles_finales, palabras_por_basico=self._palabras_por_basico(), fin_video=self._fin_video(), capitalizar=self._capitalizar(), tamanos=self._tamanos_lineas(), peso_conector=getattr(self, 'peso_conectores', None))
                        pista_sfx = {}
                        if con_sfx:
                            self.msg_queue.put(('status', tr('Eligiendo los efectos de sonido...')))
                            pista_sfx = self._preparar_sfx(bloques)
                        self.msg_queue.put(('gen_fase', 'emojis'))
                        pista_emojis = self._preparar_emojis(bloques, palabras_finales, roles_finales)
                        if con_sfx:
                            pista_sfx = self._sfx_de_emojis(bloques, pista_sfx)
                        pista_composicion = self._pista_composicion(bloques)
                        self._anunciar_receta(pista_plantilla, pista_sfx)
                        self._estilos_de_bloques(bloques, palabras_finales)
                        json_path, base_srt = st.write_dynamic(bloques, project_name, base_lang, st.SHARED_FOLDER)
                        manifest['tracks'].append({'language': base_lang, 'style': 'dynamic', 'data_path': str(json_path), 'srt_path': str(base_srt), 'fonts': fuentes or {}, 'adelanto_frames': self._adelanto_frames(), 'offset_frames': self._offset_frames(), **pista_plantilla, **pista_sfx, **pista_emojis, **pista_composicion})
                    self._ultimos_bloques = bloques  # v5.1: la vista previa de GO
                    base_cues = [st.Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
                    n_bloques = len(bloques)
                else:
                    import dynamic_subtitles as dyn
                    palabras = [w for w in words if w['word'].strip()]
                    self.msg_queue.put(('phase_determinate', None))
                    self.msg_queue.put(('progress', 1.0))
                    self._tag_event.clear()
                    self.msg_queue.put(('need_text', (palabras, project_name, base_lang)))
                    self._tag_event.wait()
                    if self._tag_result is None:
                        raise SystemExit(tr('Generación cancelada por el usuario.'))
                    palabras_finales, _ = self._tag_result
                    self.msg_queue.put(('phase_indeterminate', None))
                    self.msg_queue.put(('status', tr('Armando los bloques de subtitulo...')))
                    self.msg_queue.put(('gen_fase', 'armar'))
                    bloques = dyn.build_manual_cues(palabras_finales, [None] * len(palabras_finales), palabras_por_basico=self._palabras_por_basico(), fin_video=self._fin_video())
                    base_cues = [st.Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
                    base_srt = st.SHARED_FOLDER / f'{project_name}.{base_lang}.srt'
                    st.write_srt(base_cues, 42, 2, base_srt)
                    manifest['tracks'].append({'language': base_lang, 'srt_path': str(base_srt), 'offset_frames': self._offset_frames(), **self._pista_basicos()})
                    n_bloques = len(base_cues)
            if translate:
                destino = self._idioma_destino()
                nombre_destino = NOMBRE_POR_CODIGO.get(destino, destino)
                self.msg_queue.put(('status', tr('Preparando el traductor (la primera vez descarga el paquete de idioma)...')))
                self.msg_queue.put(('phase_indeterminate', None))
                _log = lambda m: self.msg_queue.put(('status', m))
                try:
                    ensure_lang_pack(base_lang, destino, log=_log)
                except SystemExit as e:
                    if isinstance(e, lang_packs.SinConexion):
                        raise
                    if base_lang == 'en' or destino == 'en':
                        raise
                    _log(tr('No hay paquete directo {base_lang}->{destino}: descargo los dos tramos vía inglés.', base_lang=base_lang, destino=destino))
                    ensure_lang_pack(base_lang, 'en', log=_log)
                    ensure_lang_pack('en', destino, log=_log)
                self.msg_queue.put(('phase_determinate', None))
                self.msg_queue.put(('status', tr('Traduciendo al {lower}...', lower=_idioma_en_frase(nombre_destino))))
                def on_translate_progress(frac):
                    self.msg_queue.put(('progress', transcribe_share + frac * (1.0 - transcribe_share)))
                traducidos = st.translate_cues(base_cues, base_lang, destino, progress_callback=on_translate_progress)
                srt_destino = st.SHARED_FOLDER / f'{project_name}.{destino}.srt'
                en_chars = max_chars if max_chars > 0 else 42
                en_lines = max_lines if max_lines > 0 else 2
                st.write_srt(traducidos, en_chars, en_lines, srt_destino)
                manifest['tracks'].append({'language': destino, 'srt_path': str(srt_destino), 'traducida': True, 'offset_frames': self._offset_frames(), **self._pista_basicos()})
            manifest_path = st.SHARED_FOLDER / 'subtitles_manifest.json'
            archivos_seguros.escribir_json(manifest_path, manifest, indent=2)
            sidecar_lua.escribir_sidecar(manifest_path, manifest)
            langs = ', '.join((t['language'].upper() for t in manifest['tracks']))
            self._punto_control_go()
            hilo_fx = getattr(self, '_efectos_hilo', None)
            self._efectos_hilo = None
            if hilo_fx is not None:
                hilo_fx.join(300)                                    # (ya suele estar hecho: corrió mientras la IA trabajaba)
            else:
                self._planificar_efectos(media_path, words, cortes_fx)
            ev_tl = getattr(self, '_go_tl_listo', None)
            if ev_tl is not None and not ev_tl.is_set():
                # GO con un video soltado: Resolve todavía está armando el timeline con él (los captions se colocan ahí)
                self.msg_queue.put(('status', tr('Esperando a que Resolve termine el timeline con tu video…')))
                ev_tl.wait(240)
            self._go_tl_listo = None
            self._abortar_si_fallo_el_timeline()
            self.msg_queue.put(('done', (n_bloques, langs, str(st.SHARED_FOLDER))))
        except SystemExit as e:
            guardar_log_de_error(traceback.format_exc())
            self.msg_queue.put(('error', str(e)))
            return None
        except Exception as e:
            log = guardar_log_de_error(traceback.format_exc())
            msg = f'{type(e).__name__}: {e}'
            if log:
                msg += tr('\n\nDetalle tecnico guardado en:\n{log}', log=log)
            self.msg_queue.put(('error', msg))
            return None
    def _anotar_estado(self, texto):
        """Las notas del proceso (transcribiendo, colocando…) van al registro, sin saturarlo."""
        try:
            t = str(texto or '').strip()
            ahora = time.time()
            if t and t != getattr(self, '_ultima_nota', '') and ahora - getattr(self, '_ultima_nota_t', 0.0) > 0.8:
                self._ultima_nota, self._ultima_nota_t = t, ahora
                registro.info(t, 'proceso')
        except Exception:
            pass
    def _poll_queue(self):
        """Corre en el hilo principal. Es el unico que toca los widgets."""
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                un_clic = getattr(self, '_un_clic', False)
                nombre_vig = getattr(self, '_vig_nombre', None)
                if nombre_vig and kind != 'vigia':
                    # v5.11: cada mensaje del trabajo es una señal de vida para el vigía (vigilancia.py); si dejan de llegar avisa y destraba
                    try:
                        import vigilancia
                        paso_vig = getattr(self, '_go_paso_actual', None) if un_clic else (payload if kind in ('paso', 'gen_fase') else None)
                        vigilancia.latido(nombre_vig, paso=paso_vig, detalle=str(payload)[:120] if kind == 'status' else '')
                    except Exception:
                        pass
                if kind == 'vigia':
                    self.status_var.set(str(payload))
                    self._gen_detalle(payload)
                    if un_clic and getattr(self, '_go_corriendo', False):
                        self.go_panel.linea.configure(text=str(payload))
                elif kind == 'progress':
                    self.progress.set(payload)
                    try:
                        self.porcentaje_lbl.configure(text=f'{int(round(float(payload) * 100))} %')
                    except (TypeError, ValueError):
                        pass
                    if un_clic:
                        try:
                            self.go_panel.avance_dentro(getattr(self, '_go_paso_actual', 'voz'), float(payload))
                        except (TypeError, ValueError):
                            pass
                elif kind == 'duracion':
                    if un_clic:
                        self.go_panel.estimar_duracion(payload)
                elif kind == 'paso':
                    # v5.1: los pasos de GO (los manda el hilo de trabajo)
                    if un_clic:
                        anterior = getattr(self, '_go_paso_actual', None)
                        if anterior and anterior != payload:
                            self.go_panel.paso(anterior, 'hecho')
                        self._go_paso_actual = payload
                        self.go_panel.paso(payload)
                elif kind == 'status':
                    try:
                        from i18n import tr_libre
                        payload = tr_libre(payload)          # un mensaje armado en otro modulo o por un script de Resolve (en español) sale en el idioma elegido
                    except Exception:
                        pass
                    self.status_var.set(payload)
                    self._anotar_estado(payload)
                    self._gen_detalle(payload)
                    try:
                        et = self._etapa_de_estado(str(payload))
                        if et and self.ETAPAS_ORDEN.index(et) >= self.ETAPAS_ORDEN.index(getattr(self, '_etapa_actual', 'modelo')):
                            self._etapa_actual = et
                            self._poner_etapa(et)
                    except Exception:
                        pass
                    if un_clic:
                        self.go_panel.linea.configure(text=str(payload))
                elif kind == 'idioma':
                    self._idioma_detectado_go = payload
                    if un_clic:
                        self._pintar_opciones_go()
                elif kind == 'gen_fase':
                    self._gen_fase(payload)
                elif kind == 'phase_indeterminate':
                    self.progress.configure(mode='indeterminate')
                    self.progress.start()
                    self.porcentaje_lbl.configure(text='')
                elif kind == 'phase_determinate':
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                    self.progress.set(0)
                    self.porcentaje_lbl.configure(text='0 %')
                elif kind == 'need_tags':
                    palabras, sugeridos, proyecto = payload
                    self._abrir_ventana_etiquetado(palabras, sugeridos, proyecto)
                elif kind == 'need_text':
                    palabras, proyecto, idioma = payload
                    self._abrir_ventana_texto(palabras, proyecto, idioma)
                elif kind == 'scripting_cerrado':
                    if not getattr(self, '_aviso_scripting_dado', False):
                        self._aviso_scripting_dado = True
                        import resolve_bridge
                        messagebox.showwarning(tr('Resolve no acepta scripts'), tr('Resolve está abierto pero no acepta scripts externos.\n\n') + resolve_bridge.PASOS_SCRIPTING, parent=self)
                elif kind == 'paso_manual':
                    if not getattr(self, '_aviso_paso_dado', False):
                        self._aviso_paso_dado = True
                        if payload.get('tipo') == 'elegir':
                            messagebox.showwarning(tr('Elige UNA salida (solo una vez)'), tr('Tu versión de Resolve no deja pasar los clips del pack al Media Pool por script. Tienes dos salidas, las dos de una sola vez:\n\nRÁPIDA (5 segundos): arrastra UN Text+ cualquiera (Effects > Titles > Text+) al Media Pool y vuelve a generar. Todo sale en automático con los estilos del pack (posición aproximada por rol).\n\nCOMPLETA (1 minuto): abre el timeline «{get}», selecciona TODOS sus clips de texto incluido \'base\' (Cmd/Ctrl+A) y arrástralos al bin «{get2}» del Media Pool. La posición y la animación quedan EXACTAS. El programa intenta dejarlo permanente solo; si tu Resolve no lo permite, el registro te dirá cómo exportar el bin tú una única vez (clic derecho → Exportar bandeja…).', get=payload.get('timeline'), get2=payload.get('bin')), parent=self)
                        elif payload.get('tipo') == 'arrastrar':
                            messagebox.showwarning(tr('Falta UN paso (solo una vez)'), tr('Tu versión de Resolve no deja pasar los clips del pack al Media Pool por script. Hazlo tú una sola vez:\n\n1. En Resolve, abre el timeline «{get}» (quedó en tu proyecto).\n2. Selecciona TODOS sus clips de texto, incluido el clip \'base\' (Cmd/Ctrl+A sobre el timeline).\n3. Arrástralos al bin «{get2}» del Media Pool.\n4. Vuelve a generar.\n\nDesde ahí, el automático queda completo en este proyecto (con la posición y la animación del pack).', get=payload.get('timeline'), get2=payload.get('bin')), parent=self)
                        else:
                            messagebox.showwarning(tr('Falta un Text+ en el Media Pool'), tr('No hay ningún Text+ en el Media Pool y tu versión de Resolve no me deja crear uno por script.\n\nArrastra un Text+ (Effects > Titles > Text+) al Media Pool una sola vez y vuelve a generar.'), parent=self)
                elif kind == 'puente_viejo':
                    if not getattr(self, '_aviso_puente_dado', False):
                        self._aviso_puente_dado = True
                        import resolve_bridge
                        messagebox.showwarning(tr('Relanza el Puente en Resolve'), tr('El Puente que está corriendo dentro de Resolve es de la versión {payload}, y este programa trae la {VERSION_PUENTE_ESPERADA} (el Puente tiene numeración propia, distinta de la del programa).\n\nSigue funcionando, pero le faltan los arreglos de conexión nuevos.\n\nCómo actualizarlo (10 segundos):\nÁrea de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente — el nuevo releva al viejo solo.\n\nSi este aviso reaparece, cierra DaVinci Resolve por completo y ábrelo de nuevo.', payload=payload, VERSION_PUENTE_ESPERADA=resolve_bridge.VERSION_PUENTE_ESPERADA), parent=self)
                elif kind == 'version_ajena':
                    if not getattr(self, '_aviso_version_dado', False):
                        self._aviso_version_dado = True
                        messagebox.showwarning(tr('Hay otra versión instalada'), tr('Tu Resolve ejecutó los scripts de la versión {payload}, pero este programa es la {APP_VERSION}.\n\nEso pasa cuando queda otra copia del programa instalada: al abrirla, reinstala SUS scripts en el menú de Resolve y pisa los nuevos.\n\nCómo arreglarlo:\n1. Cierra Resolve.\n2. Desinstala la copia vieja del programa (Panel de control > Aplicaciones), o al menos no vuelvas a abrirla.\n3. Abre este programa otra vez: reinstalará sus scripts.\n4. Abre Resolve y vuelve a lanzar el Puente.', payload=payload, APP_VERSION=APP_VERSION), parent=self)
                elif kind == 'colocado_en_resolve':
                    ok, err, extra, n_cues, langs, *_resto = payload
                    veredicto = _resto[0] if _resto else None
                    nada_colocado = bool(veredicto) and not veredicto.get('ok')          # v5.5: el script corrió pero no colocó nada (antes salía «Listo»)
                    detalle_fallo = ''
                    if nada_colocado:
                        try:
                            import colocacion
                            detalle_fallo = colocacion.detalle_de_fallo(veredicto)
                        except Exception:
                            detalle_fallo = ''
                    era_go = getattr(self, '_go_corriendo', False)
                    if not era_go:
                        self._fin_tarea(bool(ok), '' if ok else str(err).strip().splitlines()[0][:160] if str(err).strip() else '')
                    if not ok and not era_go:          # (GO ya lo anota en _go_fin)
                        registro.error(str(err).strip().splitlines()[0][:200] if str(err).strip() else 'No se pudo colocar en Resolve', 'colocar en Resolve', detalle=detalle_fallo or str(err))
                    self._gen_fin(ok, tr('{n} bloques colocados en tu timeline', n=n_cues) if ok else '')
                    if era_go:
                        # v5.2: GO ya enseña el resultado en su pantalla (sin el aviso encima)
                        self._go_fin(ok, tr('{n} bloques en tu timeline. Pulsa GO para otro vídeo.', n=n_cues) if ok else str(err).splitlines()[0][:400], detalle=detalle_fallo)
                    if ok:
                        self._registrar_colocacion_composicion()
                        import ui_toast
                        self.status_var.set(tr('✓ Listo: {n_cues} bloques colocados en Resolve.', n_cues=n_cues))
                        if not era_go:
                            ui_toast.mostrar(self, tr('Se generaron {n_cues} bloques ({langs}){extra} y ya quedaron puestos en tu timeline. Revisa Resolve.', n_cues=n_cues, langs=langs, extra=extra), duracion_ms=4500)
                    elif nada_colocado:
                        self.status_var.set(tr('No se colocó nada en Resolve: {c}', c=str(err).splitlines()[0][:160]))
                        if not era_go:
                            try:
                                import colocacion
                                messagebox.showwarning(tr('No se colocó nada en Resolve'), colocacion.texto_para_usuario(veredicto), parent=self)
                            except Exception:
                                pass
                    else:
                        self.status_var.set(tr('Listo: {n_cues} bloques ({langs}). Falta correrlo en Resolve.', n_cues=n_cues, langs=langs))
                        messagebox.showinfo(tr('Subtítulos listos'), tr('Se generaron {n_cues} bloques ({langs}).\n\n{err}', n_cues=n_cues, langs=langs, err=err), parent=self)
                elif kind == 'detect_ready':
                    exito, err = payload
                    self._parar_reloj()
                    self._set_inputs_enabled(True)
                    if exito:
                        self._detectar_desde_resolve_archivo()
                    else:
                        self.status_var.set(tr('No pude detectar el audio: {v}', v=err[:180]))
                        messagebox.showerror(tr('Detectar de Resolve'), tr('Resolve respondió con error:\n\n') + err[:600], parent=self)
                elif kind == 'done':
                    n_cues, langs, folder = payload
                    self._parar_reloj()
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                    self.progress.set(1.0)
                    self.porcentaje_lbl.configure(text='100 %')
                    self._poner_etapa('fin')
                    self._set_inputs_enabled(True)
                    if un_clic and getattr(self, '_go_corriendo', False):
                        self._go_vista_previa(n_cues, langs, folder)
                    else:
                        self._al_terminar_generacion(n_cues, langs, folder)
                elif kind == 'error' and un_clic and getattr(self, '_cancelar_go', False):
                    self._gen_fin(False)
                    self._parar_reloj()
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                    self.progress.set(0)
                    self.porcentaje_lbl.configure(text='')
                    self.status_var.set(tr('GO cancelado.'))
                    self._go_cancelado()
                elif kind == 'error':
                    self._gen_fin(False)
                    self._fin_tarea(False, str(payload).strip().splitlines()[0][:160] if str(payload).strip() else '')
                    registro.error(str(payload).strip().splitlines()[0][:200] if str(payload).strip() else 'Error sin mensaje', 'GO' if un_clic else 'generar',
                                   detalle=str(payload))                     # v5.11: todo error que llega a la pantalla queda también en errores.log
                    self._parar_reloj()
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                    self.progress.set(0)
                    self.porcentaje_lbl.configure(text='')
                    self.status_var.set(tr('Hubo un problema. Mira el mensaje.'))
                    self._set_inputs_enabled(True)
                    if un_clic and getattr(self, '_go_corriendo', False):
                        self._go_fallo(getattr(self, '_go_paso_actual', 'voz'), payload)
                    def _abrir_resolve_hilo():
                        def trabajo():
                            import resolve_mcp
                            resolve_mcp.preparar_resolve(abrir=True, al_estado=lambda t: self.msg_queue.put(('status', t)))
                        _correr_en_hilo(self, trabajo, lambda _r, _e: None)
                    ui.error_con_acciones(tr('Algo salio mal'), payload, parent=self, reintentar=self._on_generate, abrir_resolve=_abrir_resolve_hilo)
        except queue.Empty:
            pass
        except Exception:
            guardar_log_de_error(traceback.format_exc())
        if vivo(self):
            despues(100, self._poll_queue, self)
    def _abrir_ventana_etiquetado(self, palabras, sugeridos, proyecto=None):
        """Corre en el hilo principal: muestra el editor de palabras, guarda
        el resultado y libera al hilo de trabajo que esta esperando en
        self._tag_event."""
        guardadas = cargar_marcas(proyecto) if proyecto else None
        if guardadas and len(guardadas[0]) == len(palabras) and getattr(self, '_reusando', False):
            palabras, sugeridos = guardadas
        else:
            if guardadas and len(guardadas[0]) == len(palabras):
                    usar = messagebox.askyesno(tr('Tienes marcas de antes'), tr('Encontré las marcas de \'{proyecto}\' tal como las dejaste.\n\n¿Sigues desde ahí?\n\n(Si dices que no, se empieza en blanco y esas marcas se pierden.)', proyecto=proyecto), parent=self)
                    if usar:
                        palabras, sugeridos = guardadas
        self._tag_result = None
        self._esperando_al_usuario(True)          # v5.11: el trabajo espera al usuario a propósito: el vigía no lo cuenta
        try:
            if self._modo() == 'dinamico':
                self._asegurar_pack_luxe()      # auditoría v5.11: el editor se construye con el MISMO pack con el que luego se genera
            self._sincronizar_sfx()
            ventana = WordTagWindow(self, palabras, sugeridos, proyecto, idioma=self._codigo_idioma())
            self._tag_result = self._sesion_editor(ventana)
        finally:
            self._esperando_al_usuario(False)
            self._tag_event.set()
    def _abrir_ventana_texto(self, palabras, proyecto, idioma):
        """El mismo editor, en modo texto, para los subtitulos normales.

        Aqui no hay roles que elegir: se devuelve una lista de roles vacia
        (todo None) que el hilo de trabajo ignora, y lo que importa son las
        palabras ya corregidas.
        """
        roles = [None] * len(palabras)
        guardadas = cargar_marcas(proyecto) if proyecto else None
        if guardadas and len(guardadas[0]) == len(palabras) and getattr(self, '_reusando', False):
            palabras, roles = guardadas
        else:
            if guardadas and len(guardadas[0]) == len(palabras):
                    usar = messagebox.askyesno(tr('Tienes texto corregido de antes'), tr('Encontré el texto de \'{proyecto}\' tal como lo dejaste (correcciones incluidas).\n\n¿Sigues desde ahí?\n\n(Si dices que no, se parte de la transcripción recién hecha y esas correcciones se pierden.)', proyecto=proyecto), parent=self)
                    if usar:
                        palabras, roles = guardadas
        self._tag_result = None
        self._esperando_al_usuario(True)
        try:
            ventana = WordTagWindow(self, palabras, roles, proyecto, modo=WordTagWindow.MODO_TEXTO, idioma=idioma)
            self._tag_result = self._sesion_editor(ventana)
        finally:
            self._esperando_al_usuario(False)
            self._tag_event.set()
    def _codigo_idioma(self):
        """El codigo del idioma elegido ('es', 'en'...). 'auto' se devuelve
        tal cual: quien lo reciba decide si puede trabajar sin saberlo."""
        try:
            return LANG_CODE_BY_NAME.get(self.lang_var.get(), 'es')
        except Exception:
            return 'es'
def escribir_diagnostico():
    """Deja un informe de rutas y recursos en un archivo de texto.

    Compilado no hay consola donde imprimir nada, asi que esta es la unica
    forma de ver desde afuera si el programa encuentra sus propios archivos.
    Se pide con:  "CineCaptions.exe" --diagnostico
    """
    import platform
    import sfx_rules
    lineas = ['CineCaptions · By Cinema Productions - diagnostico', '==============================================', f'version        : {APP_VERSION}', f'sistema        : {platform.platform()}', f'python         : {sys.version.split()[0]}', f"compilado      : {getattr(sys, 'frozen', False)}", f'base recursos  : {BASE_RECURSOS}', f'logo           : {LOGO_PATH} -> existe={LOGO_PATH.exists()}']
    try:
        import PySide6
        lineas.append(f'interfaz       : PySide6 {PySide6.__version__}')
    except Exception as e:
        lineas.append(f'interfaz       : PySide6 FALLA: {e}')
    lineas.extend(licencia.resumen_diagnostico())
    scripts = BASE_RECURSOS / 'resolve_scripts'
    lineas.append(f'scripts resolve: {scripts} -> existe={scripts.is_dir()}')
    if scripts.is_dir():
        for a in sorted(scripts.iterdir()):
            lineas.append(f'    - {a.name}')
    lineas.append(f'reglas sfx     : {sfx_rules.ruta_reglas()} -> existe={sfx_rules.ruta_reglas().exists()}')
    lib = sfx_rules.carpeta_libreria()
    lineas.append(f'libreria sfx   : {lib} -> existe={lib.is_dir()}')
    for cat, audios in sfx_rules.categorias_disponibles().items():
        lineas.append(f'    - {cat}: {len(audios)} audios')
    cfg = sfx_rules.cargar_reglas()
    lineas.append(f"categoria x defecto: {cfg.get('categoria_por_defecto')}")
    lineas.append(f"reglas cargadas    : {len(cfg.get('reglas', []))}")
    for modulo in ['faster_whisper', 'ctranslate2', 'PySide6.QtWidgets', 'PIL', 'av', 'argostranslate']:
        try:
            __import__(modulo)
            lineas.append(f'import {modulo:<16} OK')
        except Exception as e:
            lineas.append(f'import {modulo:<16} FALLA: {e}')
    try:
        import salud
        lineas.append('')
        lineas.append('chequeo de librerias (v5.2):')
        lineas.append(salud.informe(salud.ultimo() or salud.comprobar()))
    except Exception as e:
        lineas.append(f'chequeo de librerias: no pude ({e})')
    try:
        prefs = json.loads((st.SHARED_FOLDER / 'preferencias.json').read_text(encoding='utf-8'))
    except Exception:
        prefs = {}
    lineas.append(f"plantilla elegida : {prefs.get('plantilla')!r}")
    lineas.append(f"efectos (sfx)     : {prefs.get('sfx')!r}  categoria={prefs.get('sfx_categoria')!r}")
    try:
        manifiesto = json.loads((st.SHARED_FOLDER / 'subtitles_manifest.json').read_text(encoding='utf-8'))
        for i, pista in enumerate(manifiesto.get('tracks', []), 1):
            plant = pista.get('plantilla')
            lineas.append(f"  manifiesto pista {i}: idioma={pista.get('language')} estilo={pista.get('style')} pack={(plant or {}).get('pack') if plant else None} sfx={('si' if pista.get('sfx_archivos') else 'no')}")
    except Exception as e:
        lineas.append(f'  manifiesto: no pude leerlo ({e})')
    incorporado = plantillas.pack_incorporado()
    lineas.append('pack incrustado   : ' + (f'{incorporado.nombre} -> formatos {sorted(incorporado.formatos)}' if incorporado else 'NO SE ENCUENTRA (revisar plantillas_incluidas/)'))
    lineas.append(f'carpeta compartida: {st.SHARED_FOLDER}')
    try:
        import resolve_bridge
        lineas.append(f'modo de ejecucion : {resolve_bridge.descripcion_modo()}')
        lineas.append(f"PYTHON3HOME       : {os.environ.get('PYTHON3HOME', '(sin fijar)')}")
        _c = resolve_bridge._carpeta_del_python3_dll()
        lineas.append(f"python3.dll usado : {(_c / 'python3.dll' if _c else 'NO ENCONTRADO')}")
        if not resolve_bridge.disponible():
            lineas.append('  (sin API externa: es Free, o Resolve esta cerrado)')
        if not resolve_bridge.puente_activo():
            lineas.append(f'  (puente no detectado en {resolve_bridge.ARCHIVO_LATIDO})')
    except Exception as e:
        lineas.append(f'modo de ejecucion : no pude averiguarlo ({e})')
    try:
        lineas.append('')
        lineas.append('scripts en Resolve:')
        lineas.append(informe_scripts_resolve())
    except Exception as e:
        lineas.append(f'scripts en Resolve: no pude averiguarlo ({e})')
    destino = st.SHARED_FOLDER / 'diagnostico.txt'
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text('\n'.join(lineas), encoding='utf-8')
    except Exception:
        destino = None
    return (destino, lineas)
_SINGLE_INSTANCE_SOCKET = None
_SINGLE_INSTANCE_LOCK = None
def _asegurar_instancia_unica():
    """Garantiza que solo exista una ventana abierta a la vez.

    Se usa UN archivo lock, tomado con un candado del sistema operativo:
    fcntl.flock en Mac/Linux y msvcrt.locking en Windows. La ventaja
    frente al socket que habia antes es que el candado lo libera el
    kernel cuando el proceso muere, pase lo que pase, asi que un cierre
    forzado no deja la app trabada para siempre. El PID se escribe
    dentro para poder activar la ventana que ya existe.

    Antes esto usaba un socket TCP fijo en 127.0.0.1:54321. Dos
    problemas: cualquier otro programa que ocupara ese puerto dejaba
    nuestra app sin abrir y sin decir por que, y ademas no protegia del
    caso real de Mac (ver _traer_instancia_existente_al_frente).
    """
    global _SINGLE_INSTANCE_LOCK
    lock_path = Path.home() / '.cinecaptions.lock'
    try:
        try:
            f = open(lock_path, 'r+', encoding='utf-8')
        except FileNotFoundError:
            f = open(lock_path, 'w+', encoding='utf-8')
    except Exception:
        return True
    tomado = False
    try:
        if sys.platform.startswith('win'):
            import msvcrt
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                tomado = True
            except OSError:
                tomado = False
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                tomado = True
            except OSError:
                tomado = False
    except Exception:
        return True
    if not tomado:
        pid_previo = None
        try:
            f.seek(0)
            pid_previo = int((f.read() or '').strip() or 0)
        except Exception:
            pid_previo = None
        try:
            f.close()
        except Exception:
            pass
        _traer_instancia_existente_al_frente(pid_previo)
        return False
    try:
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
    except Exception:
        pass
    _SINGLE_INSTANCE_LOCK = f
    return True
def _proceso_vivo(pid):
    """True si el PID corresponde a un proceso vivo en el sistema."""
    if pid <= 0:
        return False
    if sys.platform.startswith('win'):
        try:
            import ctypes
            PROCESS_QUERY_INFO = 1024
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFO, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong(0)
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return bool(ok) and exit_code.value == 259
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
def _traer_instancia_existente_al_frente(pid_previo=None):
    """Best-effort: activa la ventana de la instancia que ya esta corriendo.

    OJO con Mac: aca habia un
        osascript -e 'tell application "CineCaptions" to activate'
    y ESA era la causa de las dos ventanas. En AppleScript,
    'tell application "X" to activate' LANZA la app si LaunchServices no
    la considera corriendo, y LaunchServices resuelve por RUTA de bundle:
    si la copia abierta es la de Descargas (o una movida por App
    Translocation) y no la de /Applications, no la reconoce y abre una
    copia NUEVA. O sea que el guardia contra instancias duplicadas era
    justamente quien creaba la duplicada.

    Ahora se activa por PID, que apunta al proceso que de verdad esta
    corriendo y nunca puede lanzar nada.
    """
    if sys.platform == 'darwin':
        if not pid_previo:
            return
        try:
            import subprocess
            subprocess.run(['osascript', '-e', f'tell application "System Events" to set frontmost of (first process whose unix id is {int(pid_previo)}) to true'], capture_output=True, timeout=2)
        except Exception:
            pass
    elif sys.platform.startswith('win'):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            titulo = ctypes.create_unicode_buffer(512)
            @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
            def enum_cb(h, _):
                user32.GetWindowTextW(h, titulo, 512)
                if 'CineCaptions' in (titulo.value or ''):
                    user32.ShowWindow(h, 9)
                    user32.SetForegroundWindow(h)
                    return 0
                return 1
            user32.EnumWindows(enum_cb, 0)
        except Exception:
            pass
def _licencia_al_abrir():
    """v5.2.1 (como CineSlide 9.20): antes de mostrar la ventana. Con una licencia vigente abre al
    instante (se vuelve a verificar en línea con la ventana ya abierta); si no hay, o pasó el plazo
    sin conexión, primero la ventana de activación. False = no se abre CineCaptions."""
    try:
        if licencia.vigente():
            return True
        import ventana_licencia
        return bool(ventana_licencia.DialogoLicencia(None, verificar=bool(licencia.local())).ejecutar())
    except Exception:
        guardar_log_de_error(traceback.format_exc())
        return False
def main():
    ui.ajustar_planificacion()
    if '--tarea' in sys.argv:
        import tareas_instalador
        sys.exit(tareas_instalador.ejecutar(sys.argv))
    if '--licencia-liberar' in sys.argv:
        # v5.2.1 (como CineSlide): libera esta computadora en la tienda sin abrir la ventana
        r = licencia.seguro(licencia.desactivar)
        print(r.codigo, r.mensaje)
        sys.exit(0 if r.ok else 1)
    if '--diagnostico' in sys.argv:
        # antes iba despues del candado de instancia unica: con el programa abierto el diagnostico no hacia nada
        destino, lineas = escribir_diagnostico()
        print('\n'.join(lineas))
        if destino:
            try:
                ui.crear_app(sys.argv[:1], carpeta_fuentes=BASE_RECURSOS / 'fonts')
                messagebox.showinfo(tr('Diagnostico'), tr('Informe guardado en:\n{destino}', destino=destino))
            except Exception:
                return None
        return None
    # v5.1: --reinicio lo pone Ajustes al reiniciar: la instancia anterior
    # todavia esta cerrando, asi que se espera a que suelte el candado
    reinicio = '--reinicio' in sys.argv
    limite = time.time() + (15 if reinicio else 0)
    while not _asegurar_instancia_unica():
        if time.time() >= limite:
            print(tr('CineCaptions ya se encuentra en ejecución.'))
            return
        time.sleep(0.3)
    argumentos = [a for a in sys.argv[1:] if not a.startswith('--')]
    initial = argumentos[0] if argumentos else None
    if initial:
        initial = initial.strip().strip('\"')
    if sys.platform.startswith('win'):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('CineCaptions.App')
        except Exception:
            pass
    app = ui.crear_app(sys.argv[:1], carpeta_fuentes=BASE_RECURSOS / 'fonts')
    ui.AL_ERROR = guardar_log_de_error
    registro.instalar_ganchos()
    _vigia_ui = registro.vigilar_congelaciones()      # v5.4: anota cuando la interfaz se queda sin responder y donde
    import vigilancia
    vigilancia.iniciar_monitor()                      # v5.11: disco, memoria y escritura cada 60 s (solo anota lo que cambia)
    ui.poner_icono_app(LOGO_PATH)
    if not prueba_caducada() and not _licencia_al_abrir():
        return
    vigilancia.vigilar_arranque(45)                   # v5.11: si la ventana no termina de abrir en 45 s queda el error con la pila de todos los hilos
    ventana = SubtitleApp(initial_video=initial)
    ventana.show()
    vigilancia.arranque_listo()
    ui.despues(3000, ventana._chequeo_de_arranque, ventana)      # v5.11: librerías / motores / MCP: lo que falle queda en el Registro y se avisa
    ui.despues(4000, ui.congelar_gc, ventana)          # con todo ya cargado: el recolector de basura deja de recorrerlo (menos microcortes)
    app.exec()
    try:
        import resolve_mcp
        resolve_mcp.cerrar()
    except Exception:
        pass
if __name__ == '__main__':
    try:
        main()
    except Exception:
        detalle = traceback.format_exc()
        log = guardar_log_de_error(detalle)
        aviso = tr('CineCaptions no pudo iniciar.\n\n')
        if log:
            aviso += tr('El detalle quedo guardado en:\n{log}\n\n', log=log)
        aviso += detalle
        try:
            messagebox.showerror(tr('No se pudo abrir la ventana'), aviso)
        except Exception:
            pass
