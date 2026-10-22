# CineCaptions · By Cinema Productions
# 1_codigo/qt_kit.py — kit de interfaz Qt: colores, tipografía Inter, controles, mensajes, hilos (correr_en_hilo, despues).
"""
qt_kit.py  (v5.0.0)
-------------------
La interfaz de CineCaptions en Qt (PySide6), en UN solo sitio.

Hasta la v4.1.0 la ventana era CustomTkinter: cada esquina redondeada era un
dibujo en un Canvas de Tk y cada boton una pila de widgets, asi que abrir la
ventana de palabras con un guion largo o el selector de emojis se notaba
lento, y el redimensionado parpadeaba. Desde la v5.0.0 (pedido literal:
Python 3.15.1 y PySide6; el motor auxiliar mantiene las extensiones nativas en Python 3.14.9,
y despues la propuesta de 5 pantallas tipo panel) todo
se pinta con Qt.

Aqui vive lo comun a todas las pantallas:
  - el sistema visual de la propuesta (fondo, lateral, tarjetas de radio 14,
    botones de radio 10 y alto 40, la tipografia Inter que viaja en fonts/);
  - los controles con la interfaz minima que el programa ya usaba (Var con
    get/set/trace_add, Boton/Etiqueta.configure(text=.., text_color=..,
    state=..), messagebox/filedialog/simpledialog con las firmas de Tk) —
    asi la logica del programa no cambia, solo lo que se ve;
  - las piezas nuevas del panel: menu lateral, chips, onda, indicador de
    pasos, zona para soltar archivos, marco de vista previa;
  - el puente entre hilos: Qt, igual que Tk, solo deja tocar la interfaz
    desde el hilo principal. ejecutar_en_ui() lleva una llamada a ese hilo,
    despues() es el after() de Tk y correr_en_hilo() el patron de siempre.
"""
import math
import time
import os
import sys
import tempfile
import weakref
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QPoint, QPointF, QRect, QRectF,
                            QSize, QSizeF, Qt, QThread, QTimer, QVariantAnimation, Signal, Slot)
from PySide6.QtGui import (QBrush, QFont, QFontDatabase, QFontMetricsF,
                           QCursor, QGuiApplication, QIcon, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPalette, QPen, QPixmap, QRadialGradient, QRegion,
                           QStandardItem, QStandardItemModel)
from PySide6.QtGui import QColor as QColorReal
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QApplication, QCheckBox, QColorDialog,
                               QComboBox, QCompleter, QDialog, QFileDialog, QFrame,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLayout,
                               QLineEdit, QMenu, QPlainTextEdit, QPushButton, QRadioButton,
                               QScrollArea, QSizePolicy, QSlider, QStyle, QStyledItemDelegate, QTextEdit, QVBoxLayout, QWidget)
import shiboken6

from i18n import tr
import brillo_ui as _brillo

# ---------------------------------------------------------------------------
# Colores (los de siempre + los de la propuesta)
ACCENT = '#0F62FE'
ACCENT_HOVER = '#0052CC'
ACCENT_CLARO = '#4589FF'
CIAN = '#00C8FF'
BG_COLOR = '#080C14'
LATERAL = '#0A101C'
CARD_COLOR = '#0D1627'
CARD_2 = '#111D33'
BORDER_COLOR = '#1E2A42'
TEXT_COLOR = '#E8F1FF'
TEXT_MUTED = '#8D9BB5'
VERDE = '#24D18F'
AMBAR = '#F5B84B'
NARANJA = '#FFB86B'
ROJO = '#FF6B6B'
VIOLETA = '#B388FF'
# (#4589FE y no #4589FF: el rol «contexto» no sigue al color de resaltado
# del tema; ver tema.EXCLUIDOS)
ROL_CONTEXTO = '#4589FE'
ROL_PRINCIPAL = '#F5B84B'
ROL_COMPLEMENTO = '#B388FF'
ROL_BASE = '#6B7A99'
ROL_IMAGEN = '#4ADE80'      # v5.3: el bloque «imagen» (icono o imagen debajo del texto)

# Lo que el programa pide al registrar un error de la interfaz (lo pone el
# script principal: guardar_log_de_error -> error_ventana.txt).
AL_ERROR = None

# v5.1, Ajustes > Interfaz: el traductor de colores del tema (tema.py). Se pone
# al final de este modulo, antes de que nadie importe las constantes.
_TRADUCTOR = None


def tc(c):
    """Un '#RRGGBB' de la casa, en el tema elegido."""
    if _TRADUCTOR is not None and isinstance(c, str) and len(c) == 7 and c[:1] == '#':
        return _TRADUCTOR(c)
    return c


def traducir_hoja(texto):
    """Una hoja de estilo (o cualquier texto) con sus colores en el tema."""
    if _TRADUCTOR is None or not texto:
        return texto
    import re
    return re.sub(r'#[0-9A-Fa-f]{6}\b', lambda m: tc(m.group(0)), texto)


class QColor(QColorReal):
    """QColor que entiende el tema: QColor('#0F62FE') sale del color de
    resaltado elegido. Para colores que NO son de la interfaz (los de un
    subtitulo, una plantilla) usa QColorReal."""

    def __init__(self, *args):
        if len(args) == 1:
            a = args[0]
            if isinstance(a, str):
                args = (tc(a),)
            elif isinstance(a, QColorReal):
                # copia de otro color (PySide no acepta la subclase en el
                # constructor de copia): se copian sus componentes
                super().__init__(a.red(), a.green(), a.blue(), a.alpha())
                return
        super().__init__(*args)


def _color(c):
    """Acepta '#RRGGBB' y los grises de Tk ('gray60') que usaba la v4."""
    c = str(c or TEXT_COLOR)
    if c.startswith('gray') or c.startswith('grey'):
        try:
            n = int(c[4:])
            v = round(n * 255 / 100)
            return '#%02X%02X%02X' % (v, v, v)
        except ValueError:
            return TEXT_COLOR
    return tc(c)


def mezclar(color, fondo, fraccion):
    """El color a 'fraccion' del camino entre el fondo y el color."""
    a, b = QColor(_color(color)), QColor(_color(fondo))
    f = max(0.0, min(1.0, float(fraccion)))
    return QColor(round(b.red() + (a.red() - b.red()) * f),
                  round(b.green() + (a.green() - b.green()) * f),
                  round(b.blue() + (a.blue() - b.blue()) * f))


# ---------------------------------------------------------------------------
# Tipografia: Inter (viaja en fonts/, se carga sin instalarla en el sistema)
_FAMILIAS = {'regular': None, 'negrita': None, 'titulo': None}


def registrar_fuentes(carpeta):
    """Carga en la aplicacion las .ttf/.otf de 'carpeta' (Inter para la
    interfaz y las de los packs para las vistas previas). No toca el
    sistema: es solo para este proceso."""
    try:
        for ruta in sorted(Path(carpeta).glob('*.[ot]tf')):
            QFontDatabase.addApplicationFont(str(ruta))
    except Exception:
        pass
    familias = set(QFontDatabase.families())
    if 'Inter 18pt' in familias:
        _FAMILIAS['regular'] = 'Inter 18pt'
    if 'Inter 24pt' in familias:
        _FAMILIAS['negrita'] = 'Inter 24pt'
    if 'Inter 28pt' in familias:
        _FAMILIAS['titulo'] = 'Inter 28pt'


def familia_ui():
    if _FAMILIAS['regular']:
        return _FAMILIAS['regular']
    if sys.platform.startswith('win'):
        return 'Segoe UI'
    if sys.platform == 'darwin':
        return '.AppleSystemUIFont'
    return 'Sans Serif'


def fuente(tam=13, negrita=False, italica=False, subrayada=False, familia=None, peso=None):
    """Una QFont en PIXELES (tamaño 13 = 13 px a 100 % de escala; Qt la
    escala sola con el monitor). peso: 'medio' | 'negrita' | 'extra'."""
    if peso is None and negrita:
        peso = 'negrita'
    if familia is None:
        if peso == 'extra' or (peso == 'negrita' and tam >= 24):
            familia = _FAMILIAS['titulo'] or _FAMILIAS['negrita'] or familia_ui()
        elif peso == 'negrita':
            familia = _FAMILIAS['negrita'] or familia_ui()
        else:
            familia = familia_ui()
    f = QFont(familia)
    f.setPixelSize(max(6, int(round(tam))))
    if peso == 'medio':
        f.setWeight(QFont.Weight.Medium)
    elif peso == 'negrita':
        f.setWeight(QFont.Weight.Bold)
    elif peso == 'extra':
        f.setWeight(QFont.Weight.ExtraBold)
    f.setItalic(bool(italica))
    f.setUnderline(bool(subrayada))
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


# ---------------------------------------------------------------------------
# Hilos: el despachador lleva llamadas al hilo de la interfaz
def _registrar_excepcion(tipo, valor, tb):
    texto = ''.join(traceback.format_exception(tipo, valor, tb))
    try:
        if AL_ERROR is not None:
            AL_ERROR(texto)
    except Exception:
        pass
    try:
        if sys.__stderr__ is not None:
            sys.__stderr__.write(texto)
    except Exception:
        pass


class _Despachador(QObject):
    llamada = Signal(object)

    def __init__(self):
        super().__init__()
        self.llamada.connect(self._correr, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _correr(self, fn):
        try:
            fn()
        except Exception:
            _registrar_excepcion(*sys.exc_info())


_DESPACHADOR = None


def ejecutar_en_ui(fn):
    """Corre fn() en el hilo de la interfaz, en cuanto pueda (el after(0, fn)
    de Tk, pero seguro desde cualquier hilo)."""
    d = _DESPACHADOR
    if d is not None:
        try:
            d.llamada.emit(fn)
        except RuntimeError:
            return None              # la aplicación ya se está cerrando (el despachador murió): nadie recibirá la llamada


def en_hilo_ui():
    app = QApplication.instance()
    return app is not None and QThread.currentThread() == app.thread()


def vivo(widget):
    """El winfo_exists() de Tk: el widget sigue existiendo del lado de Qt."""
    try:
        return widget is not None and shiboken6.isValid(widget)
    except Exception:
        return False


_TIMERS_SUELTOS = set()


def despues(ms, fn, contexto=None):
    """El after() de Tk. Con 'contexto' (un widget) el temporizador muere con
    el: nunca dispara sobre una ventana ya cerrada. Devuelve un id para
    cancelar()."""
    if contexto is not None and vivo(contexto):
        t = QTimer(contexto)
    else:
        t = QTimer()
        _TIMERS_SUELTOS.add(t)
    t.setSingleShot(True)

    def disparo():
        _TIMERS_SUELTOS.discard(t)
        try:
            fn()
        except Exception:
            _registrar_excepcion(*sys.exc_info())
    t.timeout.connect(disparo)
    t.start(max(0, int(ms)))
    return t


def cancelar(t):
    """El after_cancel() de Tk."""
    try:
        if t is not None and vivo(t):
            t.stop()
    except Exception:
        pass
    _TIMERS_SUELTOS.discard(t)


def prioridad_hilo(nivel):
    """Prioridad del hilo ACTUAL en Windows (-2..2: 0 normal, 1 sobre lo normal, -1 bajo lo normal). La interfaz va un escalón por
    encima y el trabajo pesado (voz, IA) uno por debajo: así las animaciones no se congelan mientras el equipo trabaja al máximo."""
    try:
        if sys.platform.startswith('win'):
            import ctypes
            k = ctypes.windll.kernel32
            k.SetThreadPriority(k.GetCurrentThread(), int(nivel))
    except Exception:
        pass


def ajustar_planificacion():
    """Al arrancar: el hilo de la interfaz sube un escalón y Python cede el GIL cada 1 ms (por defecto 5 ms: un hilo de trabajo
    en Python puro dejaba a la interfaz sin turno y las animaciones se trababan)."""
    try:
        sys.setswitchinterval(0.0001)
    except Exception:
        pass
    prioridad_hilo(1)
    # el recolector de basura: lo ya creado al arrancar pasa a una zona permanente (no se vuelve a recorrer) y se recolecta menos
    # a menudo; las pausas del recolector eran microcortes visibles en las animaciones
    try:
        import gc
        gc.collect()
        gc.freeze()
        gc.set_threshold(20000, 20, 20)
    except Exception:
        pass


def congelar_gc():
    """Lo que ya existe (la interfaz entera, los módulos) pasa a la zona permanente del recolector: las pasadas siguientes solo
    recorren lo nuevo y casi no se notan."""
    try:
        import gc
        gc.collect()
        gc.freeze()
    except Exception:
        pass


def correr_en_hilo(contexto, trabajo, al_terminar, baja=False):
    """Corre trabajo() en un hilo y llama al_terminar(resultado, error) en el
    hilo de la interfaz — si 'contexto' (la ventana que lo pidio) sigue viva.
    La red de las licencias o un render de Resolve no congelan la ventana."""
    caja = {}

    def correr():
        prioridad_hilo(-1)
        try:
            caja['r'] = trabajo()
        except BaseException as e:            # también SystemExit (el transcriptor lo usa para avisar): si no, al_terminar nunca se llamaba
            caja['e'] = e

        def fin():
            if contexto is not None and not vivo(contexto):
                return
            al_terminar(caja.get('r'), caja.get('e'))
        ejecutar_en_ui(fin)
    if baja:                                  # v5.4.8: trabajo de fondo: cola_trabajos (máx. 2 a la vez, cede ante GO)
        try:
            import cola_trabajos
            cola_trabajos.lanzar_bajo(correr, 'correr_en_hilo')
            return
        except Exception:
            pass
    threading.Thread(target=correr, daemon=True).start()


# ---------------------------------------------------------------------------
# Variables (el StringVar/BooleanVar de Tk): valor Python puro, asi un hilo
# de trabajo puede LEERLAS sin tocar un widget.
class Var:
    __slots__ = ('_valor', '_obs')

    def __init__(self, value=None):
        self._valor = value
        self._obs = []

    def get(self):
        return self._valor

    def set(self, valor):
        self._valor = valor
        if not self._obs:
            return
        if en_hilo_ui():
            self._avisar()
        else:
            ejecutar_en_ui(self._avisar)

    def trace_add(self, _modo, fn):
        self._obs.append((fn, None))
        return fn

    def observar(self, fn, dueno=None):
        self._obs.append((fn, dueno))

    def _avisar(self):
        vivos = []
        for fn, dueno in list(self._obs):
            if dueno is not None and not vivo(dueno):
                continue
            vivos.append((fn, dueno))
            try:
                fn()
            except Exception:
                _registrar_excepcion(*sys.exc_info())
        self._obs = vivos


def StringVar(value=''):
    return Var('' if value is None else value)


def BooleanVar(value=False):
    return Var(bool(value))


# ---------------------------------------------------------------------------
# Imagenes de la hoja de estilos (flecha del desplegable, palomita): SVG,
# nitido a cualquier escala de pantalla.
def _carpeta_imagenes():
    d = Path(tempfile.gettempdir()) / 'cinecaptions_interfaz'
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def _svg(nombre, contenido):
    ruta = _carpeta_imagenes() / nombre
    try:
        if not ruta.exists() or ruta.read_text(encoding='utf-8') != contenido:
            ruta.write_text(contenido, encoding='utf-8')
    except OSError:
        pass
    return ruta.as_posix()


def _imagenes_estilo():
    flecha = ('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
              '<path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="{c}" stroke-width="1.7" '
              'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    derecha = ('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
               '<path d="M4 2.2 L8.6 6 L4 9.8 Z" fill="{c}"/></svg>')
    abajo = ('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
             '<path d="M2.2 4 L9.8 4 L6 8.6 Z" fill="{c}"/></svg>')
    palomita = ('<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">'
                '<path d="M3 7.4 L5.8 10 L11 4.2" fill="none" stroke="#FFFFFF" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return {
        'FLECHA': _svg('flecha.svg', flecha.format(c=tc('#8FA3C7'))),
        'FLECHA_OFF': _svg('flecha_off.svg', flecha.format(c=tc('#3A4A66'))),
        'DERECHA': _svg('triangulo_derecha.svg', derecha.format(c=tc('#8D9BB5'))),
        'ABAJO': _svg('triangulo_abajo.svg', abajo.format(c=tc('#8D9BB5'))),
        'PALOMITA': _svg('palomita.svg', palomita),
    }


_HOJA = """
QToolTip { color: #E0EBFB; background-color: #101A2E; border: 1px solid #22324F;
           border-radius: 6px; padding: 6px 9px; }
QScrollArea { background: transparent; border: none; }
QWidget#interiorScroll { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 1px 2px 1px; }
QScrollBar::handle:vertical { background: #22324F; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #2E4A7A; }
QScrollBar::handle:vertical:pressed { background: #0F62FE; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 1px 2px 1px 2px; }
QScrollBar::handle:horizontal { background: #22324F; border-radius: 4px; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: #2E4A7A; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

QLineEdit { background-color: #111D33; border: 1px solid #1E2A42; border-radius: 10px;
            padding: 4px 12px; color: #FFFFFF; selection-background-color: #0F62FE; }
QLineEdit:hover { border-color: #2A3F66; }
QLineEdit:focus { border-color: #0F62FE; }
QLineEdit:disabled { color: #5A6B87; background-color: #0C1424; border-color: #172238; }

QComboBox { background-color: #111D33; border: 1px solid #1E2A42; border-radius: 10px;
            padding: 2px 28px 2px 12px; color: #E8F1FF; }
QComboBox:hover { border-color: #2E4A7A; background-color: #14223C; }
QComboBox:on { border-color: #0F62FE; }
QComboBox:disabled { color: #5A6B87; background-color: #0C1424; border-color: #172238; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right;
                       width: 24px; border: none; }
QComboBox::down-arrow { image: url(FLECHA); width: 11px; height: 11px; }
QComboBox::down-arrow:disabled { image: url(FLECHA_OFF); }
QComboBox QAbstractItemView { background-color: #0F192D; border: 1px solid #22324F; border-radius: 14px;
                              padding: 8px; outline: 0; color: #E0EBFB;
                              selection-background-color: transparent; selection-color: #FFFFFF; }
QComboBox QLineEdit { border: none; background: transparent; padding: 0px; }

QCheckBox, QRadioButton { spacing: 8px; color: #E8F1FF; background: transparent; }
QCheckBox:disabled, QRadioButton:disabled { color: #5A6B87; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px;
                       border: 1px solid #2E3F63; background-color: #0B1220; }
QCheckBox::indicator:hover { border-color: #0F62FE; }
QCheckBox::indicator:checked { background-color: #0F62FE; border-color: #0F62FE; image: url(PALOMITA); }
QCheckBox::indicator:disabled { background-color: #0E1626; border-color: #1B2740; }
QRadioButton::indicator { width: 16px; height: 16px; border-radius: 9px;
                          border: 1px solid #2E3F63; background-color: #0B1220; }
QRadioButton::indicator:hover { border-color: #0F62FE; }
QRadioButton::indicator:checked { border-color: #0F62FE;
    background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #FFFFFF, stop:0.34 #FFFFFF, stop:0.42 #0F62FE, stop:1 #0F62FE); }

QMenu { background-color: #0F192D; border: 1px solid #22324F; padding: 5px; color: #E8F1FF; }
QMenu::item { padding: 7px 24px 7px 14px; border-radius: 6px; background: transparent; }
QMenu::item:selected { background-color: #0F62FE; color: #FFFFFF; }
QMenu::item:disabled { color: #5A6B87; }
QMenu::separator { height: 1px; background: #1E2A42; margin: 4px 6px; }
QMenu[pildora="true"] { background-color: #0F192D; border: 1px solid #22324F; border-radius: 14px; padding: 8px; }
QMenu[pildora="true"]::item { padding: 9px 26px 9px 20px; margin: 3px 0px; border: 1px solid #1E2A42; border-radius: 14px; background: transparent; }
QMenu[pildora="true"]::item:selected { background-color: #13203A; border-color: #2C4068; color: #FFFFFF; }
QMenu[pildora="true"]::item:checked { background-color: #0F62FE; border-color: #0F62FE; color: #FFFFFF; }
QMenu[pildora="true"]::item:checked:selected { background-color: #2A74FF; border-color: #2A74FF; color: #FFFFFF; }
QMenu[pildora="true"]::item:disabled { color: #5A6B87; border-color: #172238; background: transparent; }
QMenu[pildora="true"]::indicator { width: 0px; height: 0px; image: none; }
QMenu[pildora="true"]::separator { height: 1px; background: #1E2A42; margin: 6px 14px; }

QSlider { background: transparent; }
QSlider::groove:horizontal { height: 6px; background: #1C2840; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #0F62FE; border-radius: 3px; }
QSlider::handle:horizontal { background: #FFFFFF; border: 2px solid #0F62FE; width: 14px;
                             height: 14px; margin: -6px 0px; border-radius: 9px; }
QSlider::handle:horizontal:hover { border-color: #4589FF; }
QSlider::sub-page:horizontal:disabled { background: #2A3550; }
QSlider::handle:horizontal:disabled { border-color: #2A3550; background: #5A6B87; }

QPlainTextEdit { background-color: #0A0F1E; border: 1px solid #1E2A42; border-radius: 10px;
                 color: #C9D6EC; selection-background-color: #0F62FE; padding: 4px; }

QTreeWidget, QListWidget { background-color: transparent; border: none; color: #C9D6EC; outline: 0; }
QTreeWidget::item, QListWidget::item { min-height: 32px; padding: 0px 6px; border-radius: 8px; }
QTreeWidget::item:hover, QListWidget::item:hover { background-color: #111D33; color: #FFFFFF; }
QTreeWidget::item:selected, QListWidget::item:selected { background-color: #13213D; color: #FFFFFF; }
QTreeView { show-decoration-selected: 0; }
QTreeView::branch, QTreeView::branch:selected, QTreeView::branch:hover { background: transparent; }
QTreeView::branch:has-children:closed { image: url(DERECHA); }
QTreeView::branch:has-children:open { image: url(ABAJO); }

QFrame#tarjeta { background-color: transparent; border: none; }
QFrame#mosaico { background-color: #111D33; border: 1px solid #1E2A42; border-radius: 12px; }
QFrame#mosaico[clicable="true"]:hover { border-color: #2E5BCC; }
QFrame#mosaico[elegida="true"] { border: 2px solid #0F62FE; background-color: #10224A; }
QFrame#fila { background-color: #111D33; border: 1px solid #1E2A42; border-radius: 12px; }
QFrame#filaSuave { background-color: #0D1627; border: none; border-radius: 8px; }
QFrame#marcoLista { background-color: #0A0F1E; border: 1px solid #1E2A42; border-radius: 14px; }
QFrame#panelEmoji { background-color: #0A101C; border: 1px solid #2A3D5D; border-radius: 14px; }
QFrame#bandaVioleta { background-color: #2A2347; border: 1px solid #4A3D7A; border-radius: 10px; }
QFrame#separador { background-color: #1E2A42; border: none; }
QFrame#lateral { background-color: #0A101C; border: none; border-right: 1px solid #131C2D; }
QFrame#tarjetaEstado { background-color: #0D1627; border: 1px solid #1E2A42; border-radius: 12px; }

QPushButton { border-radius: 10px; padding: 0px 16px; color: #C9D6EC; background-color: transparent;
              border: 1px solid #2A3A58; }
QPushButton:hover { background-color: #14223C; border-color: #34507F; color: #FFFFFF; }
QPushButton:pressed { background-color: #0F1830; }
QPushButton:disabled { color: #4F607A; background-color: transparent; border-color: #1A2438; }
QPushButton[tipo="primario"] { color: #FFFFFF; border: none; background-color: #0F62FE; }
QPushButton[tipo="primario"]:hover { background-color: #2A74FF; }
QPushButton[tipo="primario"]:pressed { background-color: #0B4FD0; }
QPushButton[tipo="primario"]:disabled { background-color: #17284A; color: #6E82A6; }
QPushButton[tipo="suave"] { background-color: #111D33; border-color: #1E2A42; color: #FFFFFF; }
QPushButton[tipo="suave"]:hover { background-color: #182846; }
QPushButton[tipo="neutro"] { background-color: #111D33; border-color: #2A3D5D; color: #FFFFFF; }
QPushButton[tipo="neutro"]:hover { background-color: #182846; }
QPushButton[tipo="peligro"] { background-color: #3A1A1F; border-color: #6A2A2A; color: #FFD9D9; }
QPushButton[tipo="peligro"]:hover { background-color: #4D2228; }
QPushButton[tipo="peligro_fuerte"] { background-color: #7A2E2E; border-color: #9B3B3B; color: #FFFFFF; }
QPushButton[tipo="peligro_fuerte"]:hover { background-color: #9B3B3B; }
QPushButton[tipo="cancelar_go"] { background-color: #E0313F; border: none; color: #FFFFFF; }
QPushButton[tipo="cancelar_go"]:hover { background-color: #F04452; }
QPushButton[tipo="cancelar_go"]:pressed { background-color: #C2222F; }
QPushButton[tipo="cancelar_go"]:disabled { background-color: #6B1E26; color: #F3C9CD; }
QPushButton[tipo="rosa"] { background-color: #3A2430; border-color: #54303F; color: #FFE0EA; }
QPushButton[tipo="rosa"]:hover { background-color: #54303F; }
QPushButton[tipo="exito"] { background-color: #0F2A21; border-color: #1E5A44; color: #24D18F; }
QPushButton[tipo="exito"]:hover { background-color: #143A2D; }
QPushButton[tipo="violeta"] { background-color: #241E3D; border-color: #4A3D7A; color: #E6DCFF; }
QPushButton[tipo="violeta"]:hover { background-color: #30285A; }
QPushButton[tipo="fantasma"] { background-color: transparent; border: none; color: #8D9BB5; }
QPushButton[tipo="fantasma"]:hover { background-color: #14223C; color: #E0EBFB; }
QPushButton[tipo="icono"] { padding: 0px; }
"""


def hoja_de_estilo():
    hoja = traducir_hoja(_HOJA)
    for clave, ruta in _imagenes_estilo().items():
        hoja = hoja.replace(f'url({clave})', f'url("{ruta}")')
    return hoja


def paleta():
    p = QPalette()
    R = QPalette.ColorRole
    def poner(rol, color, grupo=None):
        if grupo is None:
            p.setColor(rol, QColor(color))
        else:
            p.setColor(grupo, rol, QColor(color))
    poner(R.Window, BG_COLOR)
    poner(R.WindowText, TEXT_COLOR)
    poner(R.Base, '#111D33')
    poner(R.AlternateBase, CARD_COLOR)
    poner(R.Text, '#FFFFFF')
    poner(R.Button, '#111D33')
    poner(R.ButtonText, TEXT_COLOR)
    poner(R.BrightText, '#FFFFFF')
    poner(R.Highlight, ACCENT)
    poner(R.HighlightedText, '#FFFFFF')
    poner(R.ToolTipBase, '#101A2E')
    poner(R.ToolTipText, '#E0EBFB')
    poner(R.PlaceholderText, '#5A6B87')
    poner(R.Link, ACCENT_CLARO)
    poner(R.Light, '#22324F')
    poner(R.Midlight, '#1A2840')
    poner(R.Mid, '#16223A')
    poner(R.Dark, '#070A12')
    poner(R.Shadow, '#000000')
    D = QPalette.ColorGroup.Disabled
    for rol in (R.WindowText, R.Text, R.ButtonText):
        poner(rol, '#5A6B87', D)
    return p


def crear_app(argv=None, carpeta_fuentes=None):
    """La QApplication con el aspecto de la casa. Idempotente."""
    global _DESPACHADOR
    app = QApplication.instance()
    if app is None:
        # Ajustes > Interfaz > Tamaño: Qt lo lee al crear la aplicacion
        try:
            import os
            import tema
            factor = tema.escala()
            if abs(factor - 1.0) > 0.01 and 'QT_SCALE_FACTOR' not in os.environ:
                os.environ['QT_SCALE_FACTOR'] = f'{factor:.2f}'
        except Exception:
            pass
        try:
            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            pass
        app = QApplication(list(argv or sys.argv[:1]))
        app.setApplicationName('CineCaptions')
        app.setOrganizationName('CineCaptions')
        app.setStyle('Fusion')
        if carpeta_fuentes:
            registrar_fuentes(carpeta_fuentes)
        app.setPalette(paleta())
        app.setFont(fuente(14))
        app.setStyleSheet(hoja_de_estilo())
        app.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, True)
        app.setEffectEnabled(Qt.UIEffect.UI_FadeTooltip, True)
        sys.excepthook = _registrar_excepcion
    if _DESPACHADOR is None:
        _DESPACHADOR = _Despachador()
    return app


def barra_oscura(ventana):
    """Barra de titulo oscura en Windows 10/11, del color del fondo: la
    ventana se ve de una pieza (antes la barra blanca de Windows cortaba)."""
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        hwnd = int(ventana.winId())
        dwm = ctypes.windll.dwmapi
        si = ctypes.c_int(1)
        if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(si), 4) != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(si), 4)
        fondo = QColor(BG_COLOR)
        titulo = ctypes.c_int(fondo.red() | (fondo.green() << 8) | (fondo.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(titulo), 4)
        borde = QColor(BORDER_COLOR)
        b = ctypes.c_int(borde.red() | (borde.green() << 8) | (borde.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(b), 4)
    except Exception:
        pass


def repulir(widget):
    """Vuelve a aplicar la hoja de estilos (tras cambiar una propiedad)."""
    try:
        st = widget.style()
        st.unpolish(widget)
        st.polish(widget)
        widget.update()
    except Exception:
        pass


def copiar_al_portapapeles(texto):
    QGuiApplication.clipboard().setText(str(texto))


def ventana_activa():
    return QApplication.activeWindow()


# ---------------------------------------------------------------------------
# Cajas de layout
def caja_h(padre=None, espacio=6, margenes=(0, 0, 0, 0)):
    w = QWidget(padre)
    capa = QHBoxLayout(w)
    capa.setContentsMargins(*margenes)
    capa.setSpacing(espacio)
    return w, capa


def caja_v(padre=None, espacio=6, margenes=(0, 0, 0, 0)):
    w = QWidget(padre)
    capa = QVBoxLayout(w)
    capa.setContentsMargins(*margenes)
    capa.setSpacing(espacio)
    return w, capa


def limpiar_capa(capa):
    """Borra todo lo que hay en un layout (el winfo_children()+destroy())."""
    while capa.count():
        item = capa.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            limpiar_capa(item.layout())


class Tooltip:
    """El globo de ayuda. v5.4.22 (pedido del usuario): ya NO sale ningún mensaje al dejar el ratón quieto; queda la firma de la v4 para no tocar a los llamadores."""
    def __init__(self, widget, texto, retraso_ms=450):
        pass


def _sin_globos(self, *_a, **_k):
    return None


QWidget.setToolTip = _sin_globos            # (los `setToolTip` sueltos de toda la app: ninguno enseña nada)


# ---------------------------------------------------------------------------
# Controles
class Etiqueta(QLabel):
    def __init__(self, texto='', tam=13, negrita=False, color=TEXT_COLOR, envolver=False,
                 padre=None, italica=False, subrayada=False, alineacion=None,
                 seleccionable=False, familia=None, peso=None):
        super().__init__(padre)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(str(texto))
        self.setFont(fuente(tam, negrita, italica, subrayada, familia, peso))
        self.setWordWrap(bool(envolver))
        self._color = None
        self.poner_color(color)
        if alineacion is not None:
            self.setAlignment(alineacion)
        if seleccionable:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def poner_color(self, color):
        color = _color(color)
        if color == self._color:
            return
        self._color = color
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.WindowText, QColor(color))
        self.setPalette(pal)

    def configure(self, text=None, text_color=None, **_):
        if text is not None:
            self.setText(str(text))
        if text_color is not None:
            self.poner_color(text_color)

    def cget(self, clave):
        return self.text() if clave == 'text' else self._color


class Elidida(Etiqueta):
    """Una etiqueta de una linea que, si no cabe, termina en «…» (el texto
    completo queda en el globo de ayuda) en vez de cortarse a secas."""
    def __init__(self, texto='', *args, **kw):
        self._completo = str(texto)
        super().__init__(texto, *args, **kw)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(16)
        self._elidir()

    def configure(self, text=None, text_color=None, **kw):
        if text is not None:
            self._completo = str(text)
        super().configure(text=None, text_color=text_color, **kw)
        self._elidir()

    def setText(self, texto):
        self._completo = str(texto)
        self._elidir()

    def text(self):
        return self._completo

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elidir()

    def _elidir(self):
        completo = self._completo
        corto = self.fontMetrics().elidedText(completo, Qt.TextElideMode.ElideRight, max(16, self.width()))
        QLabel.setText(self, corto)
        self.setToolTip(completo if corto != completo else '')


class Enlace(Etiqueta):
    """Texto clicable (los enlaces subrayados de la v4)."""
    def __init__(self, texto='', comando=None, tam=12, color=TEXT_MUTED, color_hover=ACCENT_CLARO,
                 negrita=False, subrayada=True, padre=None, peso=None):
        super().__init__(texto, tam=tam, negrita=negrita, color=color, subrayada=subrayada,
                         padre=padre, peso=peso)
        self._comando = comando
        self._normal = color
        self._hover = color_hover
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner_comando(self, comando):
        self._comando = comando

    def configure(self, text=None, text_color=None, **kw):
        if text_color is not None:
            self._normal = text_color
        super().configure(text=text, text_color=text_color)

    def enterEvent(self, e):
        super().poner_color(self._hover)
        super().enterEvent(e)

    def leaveEvent(self, e):
        super().poner_color(self._normal)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._comando:
            self._comando()
            e.accept()
            return
        super().mousePressEvent(e)


GLIFOS_A_ICONOS = {'▶': 'ph.play-fill', '✕': 'ph.x-bold', '⋯': 'ph.dots-three-bold', '↺': 'ph.arrow-counter-clockwise-bold',
                   '⟲': 'ph.arrow-counter-clockwise-bold', '🔍': 'ph.magnifying-glass-bold', '📁': 'ph.folder-simple-bold',
                   '←': 'ph.arrow-left-bold', '→': 'ph.arrow-right-bold', '−': 'ph.minus-bold', '+': 'ph.plus-bold'}


class Boton(QPushButton):
    def __init__(self, texto='', comando=None, tipo='secundario', alto=40, ancho=None,
                 tam=14, negrita=False, icono=None, lado_icono=16, padre=None, tooltip=None):
        super().__init__(str(texto), padre)
        self.setProperty('tipo', tipo)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(fuente(tam, peso='negrita' if negrita else 'medio'))
        self.setAutoDefault(False)
        self.setDefault(False)
        if alto:
            self.setFixedHeight(int(alto))
        if ancho:
            self.setMinimumWidth(int(ancho))
        if icono is None and str(texto) in GLIFOS_A_ICONOS:
            # v5.5: iconos de LINEA uniformes en vez de glifos de texto (▶ ✕ ⋯ ↺ 🔍 📁 ← →): mismo trazo en toda la interfaz
            ic = icono_linea(GLIFOS_A_ICONOS[str(texto)], '#C9D6EC')
            if ic is not None:
                icono = ic
                self.setText('')
                lado_icono = max(14, min(20, int(tam) + 2))
        if icono is not None:
            self.setIcon(icono if isinstance(icono, QIcon) else QIcon(icono))
            self.setIconSize(QSize(lado_icono, lado_icono))
        if tooltip:
            self.setToolTip(tooltip)
        self._comando = comando
        self._esc = Resorte(1.0, 620.0, 19.0)        # pulsar = encoge a 0,97 y vuelve con un rebote pequeño (resorte seco)
        self._pintando_esc = False
        self.clicked.connect(self._pulsado)

    def _pulsado(self):
        if self._comando:
            self._comando()

    def paso_resorte(self, dt):
        sigue = self._esc.paso(dt)
        self.update()
        return sigue

    def paintEvent(self, e):
        s = self._esc.x
        if self._pintando_esc or abs(s - 1.0) < 0.003:
            return super().paintEvent(e)
        # mientras el resorte se mueve, el boton se dibuja en una imagen y se pinta escalado desde su centro
        self._pintando_esc = True
        try:
            dpr = self.devicePixelRatioF()
            pm = QPixmap(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            self.render(pm, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
        finally:
            self._pintando_esc = False
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        p.translate(c)
        p.scale(s, s)
        p.translate(-c)
        p.drawPixmap(0, 0, pm)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._esc.objetivo = 0.97
            motor_resortes.pedir(self)
            _brillo.presionar(self, e)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._esc.objetivo = 1.0
        motor_resortes.pedir(self)
        super().mouseReleaseEvent(e)

    def poner_comando(self, comando):
        self._comando = comando

    def poner_tipo(self, tipo):
        if self.property('tipo') != tipo:
            self.setProperty('tipo', tipo)
            repulir(self)

    def configure(self, text=None, state=None, tipo=None, **_):
        if text is not None:
            self.setText(str(text))
        if state is not None:
            self.setEnabled(state != 'disabled')
        if tipo is not None:
            self.poner_tipo(tipo)

    # v5.2.1: micro-animaciones (brillo_ui): barrido al pasar el cursor, onda al pulsar, destello de los principales
    def enterEvent(self, e):
        _brillo.entrar(self)
        super().enterEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        _brillo.ajustar(self)

    def showEvent(self, e):
        super().showEvent(e)
        _brillo.mostrado(self)


# ---------------------------------------------------------------------------------------------------------------------
# v5.5 «Aurora»: fisicas de RESORTE. Todo movimiento de la interfaz (brillo de una tarjeta, pulsar un boton, cambio de color del
# fondo) es un resorte, no una curva de tiempo fija: rebota natural y se puede interrumpir sin saltos.
#   k (rigidez) alto = responde rapido; c (amortiguacion) bajo = rebota mas. Estas parejas se midieron a ojo en pantalla:
#   brillo de tarjeta k=170 c=22 (suave, sin rebote), pulsar boton k=620 c=19 (seco, un rebote pequeño), fondo k=26 c=7 (lento).
class Resorte:
    __slots__ = ('x', 'v', 'objetivo', 'k', 'c')

    def __init__(self, x=0.0, k=170.0, c=22.0):
        self.x = float(x)
        self.v = 0.0
        self.objetivo = float(x)
        self.k = float(k)
        self.c = float(c)

    def paso(self, dt):
        """Avanza dt segundos (integracion semi-implicita en trozos de 8 ms: estable con k altos). True si todavia se mueve."""
        restante = dt
        while restante > 1e-6:
            h = min(0.008, restante)
            restante -= h
            a = self.k * (self.objetivo - self.x) - self.c * self.v
            self.v += a * h
            self.x += self.v * h
        return abs(self.objetivo - self.x) > 0.0015 or abs(self.v) > 0.02

    def poner(self, valor):
        self.x = self.objetivo = float(valor)
        self.v = 0.0


class _MotorResortes:
    """Un SOLO temporizador (16 ms) para todos los resortes de la interfaz; se apaga solo cuando nada se mueve."""
    def __init__(self):
        self._activos = set()
        self._reloj = None
        self._ultimo = 0.0

    def pedir(self, objeto):
        self._activos.add(objeto)
        if self._reloj is None:
            self._reloj = QTimer()
            self._reloj.setTimerType(Qt.TimerType.PreciseTimer)       # el temporizador normal de Windows tiene saltos de ~15,6 ms
            self._reloj.setInterval(16)
            self._reloj.timeout.connect(self._tic)
        if not self._reloj.isActive():
            self._ultimo = time.perf_counter()
            self._reloj.start()

    def _tic(self):
        ahora = time.perf_counter()
        dt = min(0.05, ahora - self._ultimo)
        self._ultimo = ahora
        for o in list(self._activos):
            try:
                sigue = o.paso_resorte(dt)
            except RuntimeError:             # el widget ya no existe
                sigue = False
            if not sigue:
                self._activos.discard(o)
        if not self._activos and self._reloj is not None:
            self._reloj.stop()


motor_resortes = _MotorResortes()


def _mezcla_rgba(color, alfa):
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alfa))))
    return c


class Tarjeta(QFrame):
    """Una tarjeta del panel: vidrio líquido (translúcido, deja ver la aurora del fondo), borde de 1 px, radio 18."""
    clic = Signal()
    _vivas = weakref.WeakSet()           # para que el fondo las refresque ~2 veces por segundo (la aurora se mueve despacio)
    fondo = None                          # el FondoVivo (efectos_ui) que las contiene: de él se toma la muestra de aurora

    def __init__(self, padre=None, clicable=False, nombre='tarjeta', margenes=(20, 18, 20, 18),
                 espacio=10, horizontal=False, titulo=None):
        super().__init__(padre)
        self.setObjectName(nombre)
        self.setProperty('clicable', bool(clicable))
        self.capa = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        self.capa.setContentsMargins(*margenes)
        self.capa.setSpacing(espacio)
        self._clicable = bool(clicable)
        self.habilitada = True
        # v5.5 «Aurora»: tarjeta de vidrio OPACO (no deja ver el fondo animado: asi el fondo no se repinta debajo) con borde de 1 px,
        # luz en el borde de arriba, brillo de neon en el de abajo y un foco que sigue al mouse. Todo con resortes.
        self._vidrio = (nombre == 'tarjeta')
        self._neon = Resorte(0.06, 170.0, 22.0)
        self._foco = Resorte(0.0, 140.0, 20.0)
        self._foco_xy = [0.5, 0.5]
        self._neon_base = 0.06
        self._encima = False
        if self._vidrio:
            Tarjeta._vivas.add(self)
        if clicable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        if titulo:
            self.titulo = Etiqueta(titulo, 16, peso='medio', color='#FFFFFF')
            self.capa.addWidget(self.titulo)

    def poner_neon(self, valor):
        """El brillo de reposo del borde de abajo (0..1): las tarjetas principales de cada pagina lo llevan mas alto."""
        self._neon_base = max(0.0, min(1.0, float(valor)))
        self._neon.objetivo = self._neon_base + (0.40 if self._encima else 0.0)
        motor_resortes.pedir(self)

    def paso_resorte(self, dt):
        sigue = self._neon.paso(dt)
        sigue = self._foco.paso(dt) or sigue
        if self.isVisible():
            self.update()
        return sigue

    def paintEvent(self, e):
        if not self._vidrio:
            return super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radio = 18.0
        camino = QPainterPath()
        camino.addRoundedRect(r, radio, radio)
        elegida = bool(self.property('elegida'))
        apagada = bool(self.property('apagada'))
        acento = QColor(_color(ACCENT_CLARO))
        # 1) Liquid Glass: bajo el cristal se ve la aurora del fondo (muestra de baja resolucion = ya viene desenfocada),
        #    tapada por un tinte oscuro translucido; asi las tarjetas parecen vidrio esmerilado sobre la luz.
        alfa_c = 255
        fv = Tarjeta.fondo
        if fv is not None and not apagada:
            try:
                img, src = fv.muestra_aurora(QRectF(self.mapTo(fv, QPoint(0, 0)), QSizeF(self.size())))
                p.setClipPath(camino)
                p.fillRect(r, QColor(_color(BG_COLOR)))
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                p.drawImage(r, img, src)
                p.setClipping(False)
                alfa_c = 228 if not elegida else 236
            except Exception:
                alfa_c = 255
        # los colores pasan por el traductor del tema (Noche / Negro / Grafito): las tarjetas siguen al tema elegido
        def _cristal(hexa):
            c = QColor(_color(hexa))
            c.setAlpha(alfa_c)
            return c
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        if elegida:
            g.setColorAt(0.0, _cristal('#12234A'))
            g.setColorAt(1.0, _cristal('#0C1730'))
        elif apagada:
            g.setColorAt(0.0, QColor(_color('#0C1423')))
            g.setColorAt(1.0, QColor(_color('#09101C')))
        else:
            g.setColorAt(0.0, _cristal('#101A2E'))
            g.setColorAt(1.0, _cristal('#0A111F'))
        p.fillPath(camino, g)
        p.save()
        p.setClipPath(camino)
        # 4) la luz del borde de arriba
        lg = QLinearGradient(r.topLeft(), r.topRight())
        lg.setColorAt(0.0, QColor(255, 255, 255, 0))
        lg.setColorAt(0.5, QColor(255, 255, 255, 56))
        lg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(r.left() + radio, r.top(), r.width() - 2 * radio, 1.2), lg)
        if alfa_c < 255:                                  # reflejo especular: una banda de luz difusa arriba a la izquierda
            sg = QLinearGradient(r.topLeft(), QPointF(r.left() + r.width() * 0.55, r.top() + r.height() * 0.55))
            sg.setColorAt(0.0, QColor(255, 255, 255, 20))
            sg.setColorAt(0.5, QColor(255, 255, 255, 5))
            sg.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(r, sg)
        p.restore()
        # 5) el borde de 1 px: blanco translucido; elegida = acento; con el mouse encima, se tiñe de acento
        # v5.7 (pedido: «no me gusta que se resalten las cartas y secciones»): ninguna tarjeta se ilumina al pasar el mouse. Solo la
        # elegida lleva el acento (fino) y las pulsables aclaran su borde en blanco, sin color.
        if elegida:
            p.setPen(QPen(QColor(acento.red(), acento.green(), acento.blue(), 210), 1.6))
        else:
            mezcla = 0.09 + (0.10 * max(0.0, min(1.0, self._foco.x)) if self._clicable else 0.0)
            p.setPen(QPen(QColor(255, 255, 255, int(255 * mezcla)), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(camino)
        p.end()

    def enterEvent(self, e):
        self._encima = True
        if self._clicable:
            self._foco.objetivo = 1.0
            motor_resortes.pedir(self)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._encima = False
        if self._clicable:
            self._foco.objetivo = 0.0
            motor_resortes.pedir(self)
        super().leaveEvent(e)

    def poner_habilitada(self, si):
        self.habilitada = bool(si)
        self.setProperty('clicable', bool(self._clicable and si))
        self.setProperty('apagada', not si)
        self.setCursor(Qt.CursorShape.PointingHandCursor if (self._clicable and si)
                       else Qt.CursorShape.ArrowCursor)
        repulir(self)

    def poner_elegida(self, si):
        if self.property('elegida') != bool(si):
            self.setProperty('elegida', bool(si))
            repulir(self)

    def mousePressEvent(self, e):
        if self._clicable and self.habilitada and e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit()
            e.accept()
            return
        super().mousePressEvent(e)


class Separador(QFrame):
    def __init__(self, padre=None, vertical=False):
        super().__init__(padre)
        self.setObjectName('separador')
        if vertical:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)


class Entrada(QLineEdit):
    def __init__(self, var=None, placeholder='', alto=40, tam=14, padre=None, ancho=None,
                 centrada=False):
        super().__init__(padre)
        self.setFont(fuente(tam))
        if placeholder:
            self.setPlaceholderText(str(placeholder))
        if alto:
            self.setFixedHeight(int(alto))
        if ancho:
            self.setFixedWidth(int(ancho))
        if centrada:
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._var = var
        if var is not None:
            self.setText(str(var.get() or ''))
            self.textEdited.connect(lambda t: var.set(t))
            var.observar(self._desde_var, self)

    def _desde_var(self):
        v = str(self._var.get() or '')
        if v != self.text():
            self.setText(v)

    def get(self):
        return self.text()

    def insert(self, _indice, texto):
        """Compat Tk: Entry.insert(0, texto)."""
        self.setText(str(texto) + self.text())

    def configure(self, state=None, **_):
        if state is not None:
            self.setEnabled(state != 'disabled')


class _DelegadoPildora(QStyledItemDelegate):
    """v5.4.21: cada opción de una lista desplegable es una PÍLDORA: la que está en uso va rellena de azul con un visto, la que toca el ratón (o el teclado) con fondo y borde claros y
    las demás con un borde fino. `combo` = el QComboBox de la lista (para saber cuál es la actual); sin él (lista de sugerencias) la elegida va rellena de azul."""
    ALTO = 30

    def __init__(self, combo=None, padre=None):
        super().__init__(padre)
        self._combo = combo

    @staticmethod
    def _es_separador(index):
        return index.data(Qt.ItemDataRole.AccessibleDescriptionRole) == 'separator'

    def sizeHint(self, option, index):
        if self._es_separador(index):
            return QSize(option.rect.width(), 12)
        base = super().sizeHint(option, index)
        return QSize(base.width() + 48, self.ALTO + 8)

    def paint(self, p, option, index):
        if self._es_separador(index):
            p.save()
            p.setPen(QPen(QColorReal('#1E2A42'), 1))
            y = option.rect.center().y()
            p.drawLine(option.rect.left() + 14, y, option.rect.right() - 14, y)
            p.restore()
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect).adjusted(2, 3, -2, -3)
        sobre = bool(option.state & QStyle.StateFlag.State_MouseOver)
        marcada = bool(option.state & QStyle.StateFlag.State_Selected)
        actual = (index.row() == self._combo.currentIndex()) if self._combo is not None else marcada
        if actual:
            fondo, borde, texto = QColorReal(ACCENT), QColorReal(ACCENT), QColorReal('#FFFFFF')
        elif sobre or marcada:
            fondo, borde, texto = QColorReal('#13203A'), QColorReal('#2C4068'), QColorReal('#FFFFFF')
        else:
            fondo, borde, texto = QColorReal(0, 0, 0, 0), QColorReal(BORDER_COLOR), QColorReal('#E0EBFB')
        p.setPen(QPen(borde, 1.0))
        p.setBrush(fondo)
        radio = r.height() / 2.0
        p.drawRoundedRect(r, radio, radio)
        p.setFont(option.font)
        p.setPen(texto)
        etiqueta = QFontMetricsF(option.font).elidedText(str(index.data(Qt.ItemDataRole.DisplayRole) or ''), Qt.TextElideMode.ElideRight, r.width() - 54)
        p.drawText(QRectF(r.left() + 20, r.top(), r.width() - 54, r.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), etiqueta)
        if actual:
            cx, cy = r.right() - 24, r.center().y()
            p.setPen(QPen(QColorReal('#FFFFFF'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(QPointF(cx - 5, cy), QPointF(cx - 1.5, cy + 4))
            p.drawLine(QPointF(cx - 1.5, cy + 4), QPointF(cx + 5, cy - 4))
        p.restore()


def _panel_translucido(ventana):
    """La ventana de una lista desplegable sin fondo propio ni sombra del sistema: así se ven las esquinas redondeadas del panel. Nunca lanza."""
    try:
        ventana.setWindowFlags(ventana.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        ventana.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    except Exception:
        pass


class Combo(QComboBox):
    """El CTkOptionMenu: lista fija, valor en una Var y command(valor)."""
    SEPARADORES = set()

    def __init__(self, valores=(), var=None, comando=None, ancho=None, alto=36, tam=14,
                 padre=None):
        super().__init__(padre)
        self.setFont(fuente(tam))
        if alto:
            self.setFixedHeight(int(alto))
        if ancho:
            self.setMinimumWidth(int(ancho))
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMaxVisibleItems(14)
        try:                                           # v5.4.21: la lista que se despliega, en píldoras sobre un panel redondeado
            self.setItemDelegate(_DelegadoPildora(self, self))
            _cont = self.view().window()
            if _cont is not None and _cont is not self.window():
                _panel_translucido(_cont)
        except Exception:
            pass
        self._var = var
        self._comando = comando
        self._valores = []
        self.poner_valores(valores)
        self.activated.connect(self._elegido)
        if var is not None:
            var.observar(self._desde_var, self)

    def wheelEvent(self, e):
        # La rueda sobre un desplegable cerrado NO cambia el valor (se
        # desplazaba la pantalla y de paso se cambiaba el idioma sin querer).
        e.ignore()

    def poner_valores(self, valores):
        actual = self._var.get() if self._var is not None else self.currentText()
        self.blockSignals(True)
        self.clear()
        self._valores = []
        for v in valores:
            if v in Combo.SEPARADORES:
                self.insertSeparator(self.count())
            else:
                self.addItem(str(v))
                self._valores.append(str(v))
        self._mostrar(actual)
        self.blockSignals(False)

    def valores(self):
        return list(self._valores)

    def _mostrar(self, valor):
        if valor is None:
            return
        i = self.findText(str(valor), Qt.MatchFlag.MatchExactly)
        if i < 0 and str(valor) and not self.isEditable():
            self.addItem(str(valor))
            i = self.count() - 1
        if i >= 0:
            self.setCurrentIndex(i)
        elif self.isEditable():
            self.setEditText(str(valor))

    def _elegido(self, i):
        texto = self.itemText(i)
        if self._var is not None:
            self._var.set(texto)
        if self._comando:
            self._comando(texto)

    def _desde_var(self):
        v = self._var.get()
        if self.currentText() != str(v):
            self.blockSignals(True)
            self._mostrar(v)
            self.blockSignals(False)

    def set(self, valor):
        if self._var is not None:
            self._var.set(valor)
        else:
            self.blockSignals(True)
            self._mostrar(valor)
            self.blockSignals(False)

    def get(self):
        return self._var.get() if self._var is not None else self.currentText()

    def configure(self, values=None, state=None, **_):
        if values is not None:
            self.poner_valores(values)
        if state is not None:
            self.setEnabled(state != 'disabled')

    def cget(self, clave):
        if clave == 'values':
            return self.valores()
        return None


class _CompletadorPlegado(QCompleter):
    """Busca sin tildes ni mayusculas («espanol» encuentra «Español»)."""
    ROL = Qt.ItemDataRole.UserRole + 1

    def __init__(self, modelo, plegar, padre=None):
        super().__init__(modelo, padre)
        self._plegar = plegar
        self.setCompletionRole(self.ROL)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setMaxVisibleItems(14)

    def splitPath(self, ruta):
        return [self._plegar(ruta)]

    def pathFromIndex(self, indice):
        return str(indice.data(Qt.ItemDataRole.DisplayRole) or '')


class ComboBuscable(Combo):
    """El CTkComboBox del idioma: se puede escribir para buscar. Lo escrito
    solo cuenta al confirmarlo (Enter, elegirlo o salir del campo): un texto
    que no es un idioma vuelve al ultimo valido (en la v4 quedaba escrito y
    «Generar» reventaba con un KeyError)."""

    def __init__(self, valores=(), var=None, comando=None, plegar=None, ancho=None, alto=40,
                 tam=14, padre=None):
        super().__init__((), var, comando, ancho, alto, tam, padre)
        self._plegar = plegar or (lambda t: str(t).lower())
        self._modelo = QStandardItemModel(self)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        comp = _CompletadorPlegado(self._modelo, self._plegar, self)
        comp.popup().setFont(fuente(tam))
        try:                                           # v5.4.21: las sugerencias, en píldoras también
            comp.popup().setItemDelegate(_DelegadoPildora(None, comp.popup()))
            comp.popup().setStyleSheet('QListView { background-color: #0F192D; border: 1px solid #22324F; padding: 8px; outline: 0; }')       # (sin esquinas redondeadas: un popup propio con fondo translúcido no pinta el de la lista)
        except Exception:
            pass
        comp.activated.connect(self._confirmar_texto)
        self.setCompleter(comp)
        self.lineEdit().editingFinished.connect(self._confirmar_edicion)
        self.lineEdit().setFont(fuente(tam))
        self.poner_valores(valores)
        if var is not None:
            self.blockSignals(True)
            self._mostrar(var.get())
            self.blockSignals(False)

    def poner_valores(self, valores):
        super().poner_valores(valores)
        modelo = getattr(self, '_modelo', None)
        if modelo is not None:
            modelo.clear()
            for v in self._valores:
                it = QStandardItem(v)
                it.setData(self._plegar(v), _CompletadorPlegado.ROL)
                modelo.appendRow(it)

    def _confirmar_texto(self, texto):
        self._aplicar(str(texto))

    def _confirmar_edicion(self):
        texto = self.currentText().strip()
        if texto in self._valores:
            if self._var is None or texto != self._var.get():
                self._aplicar(texto)
            return
        buscado = self._plegar(texto)
        candidato = None
        if buscado:
            empiezan = [v for v in self._valores if self._plegar(v).startswith(buscado)]
            contienen = [v for v in self._valores if buscado in self._plegar(v)]
            candidato = (empiezan or contienen or [None])[0]
        if candidato:
            self._aplicar(candidato)
        else:
            self.blockSignals(True)
            self._mostrar(self._var.get() if self._var is not None else '')
            self.blockSignals(False)

    def _aplicar(self, texto):
        self.blockSignals(True)
        self._mostrar(texto)
        self.blockSignals(False)
        if self._var is not None:
            self._var.set(texto)
        if self._comando:
            self._comando(texto)


class Casilla(QCheckBox):
    def __init__(self, texto='', var=None, comando=None, tam=14, color=None, padre=None):
        super().__init__(str(texto), padre)
        self.setFont(fuente(tam))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if color:
            self.setStyleSheet(f'QCheckBox {{ color: {_color(color)}; }}')
        self._var = var
        self._comando = comando
        if var is not None:
            self.setChecked(bool(var.get()))
            var.observar(self._desde_var, self)
        self.clicked.connect(self._clic)

    def _clic(self, marcado):
        if self._var is not None:
            self._var.set(bool(marcado))
        if self._comando:
            self._comando()

    def _desde_var(self):
        v = bool(self._var.get())
        if v != self.isChecked():
            self.blockSignals(True)
            self.setChecked(v)
            self.blockSignals(False)

    def get(self):
        return self.isChecked()

    def configure(self, state=None, **_):
        if state is not None:
            self.setEnabled(state != 'disabled')


class Interruptor(QAbstractButton):
    """El CTkSwitch: un interruptor con su texto, animado."""
    def __init__(self, texto='', var=None, comando=None, tam=14, color=TEXT_COLOR, padre=None):
        super().__init__(padre)
        self.setText(str(texto))
        self.setCheckable(True)
        self.setFont(fuente(tam))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = _color(color)
        self._pos = 0.0
        self._res = Resorte(0.0, 520.0, 24.0)          # v5.5: la bolita viaja con un resorte (rebota un poco al llegar)
        self._var = var
        self._comando = comando
        if var is not None:
            self.setChecked(bool(var.get()))
            self._pos = 1.0 if self.isChecked() else 0.0
            self._res.poner(self._pos)
            var.observar(self._desde_var, self)
        self.toggled.connect(self._animar)
        self.clicked.connect(self._clic)

    def paso_resorte(self, dt):
        sigue = self._res.paso(dt)
        self._pos = self._res.x
        self.update()
        return sigue

    def _animar(self, marcado):
        self._res.objetivo = 1.0 if marcado else 0.0
        motor_resortes.pedir(self)

    def _clic(self, marcado):
        if self._var is not None:
            self._var.set(bool(marcado))
        if self._comando:
            self._comando()

    def _desde_var(self):
        v = bool(self._var.get())
        if v != self.isChecked():
            self.blockSignals(True)
            self.setChecked(v)
            self.blockSignals(False)
            self._pos = 1.0 if v else 0.0
            self._res.poner(self._pos)
            self.update()

    def get(self):
        return self.isChecked()

    def configure(self, state=None, **_):
        if state is not None:
            self.setEnabled(state != 'disabled')

    def sizeHint(self):
        fm = QFontMetricsF(self.font())
        ancho = 40 + (12 + fm.horizontalAdvance(self.text()) if self.text() else 0)
        return QSize(int(ancho) + 2, max(24, int(fm.height()) + 4))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        pista = QRectF(1, (h - 22) / 2, 40, 22)
        t = self._pos
        color = mezclar(ACCENT, '#1C2840', t)
        if not self.isEnabled():
            color = QColor('#16223A')
        p.setPen(Qt.PenStyle.NoPen)
        if self.isEnabled() and t > 0.05:
            for grosor, alfa in ((9.0, 22), (4.0, 52)):          # el neon del interruptor encendido
                halo = QColor(ACCENT)
                halo.setAlpha(int(alfa * min(1.0, t)))
                p.setBrush(halo)
                p.drawRoundedRect(pista.adjusted(-grosor / 2, -grosor / 2, grosor / 2, grosor / 2), 11 + grosor / 2, 11 + grosor / 2)
        p.setBrush(color)
        p.drawRoundedRect(pista, 11, 11)
        x = pista.left() + 3 + t * (pista.width() - 22)
        p.setBrush(QColor('#FFFFFF' if self.isEnabled() else '#5A6B87'))
        p.drawEllipse(QRectF(x, pista.top() + 3, 16, 16))
        if self.text():
            p.setPen(QColor(self._color if self.isEnabled() else '#5A6B87'))
            p.setFont(self.font())
            p.drawText(QRectF(pista.right() + 12, 0, self.width() - pista.right() - 12, h),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()


class Radio(QRadioButton):
    """Un radio ligado a una Var compartida (puede vivir en tarjetas
    distintas: la exclusion la hace la Var, no el padre)."""
    def __init__(self, texto='', var=None, valor='', comando=None, tam=14, negrita=False,
                 color=None, padre=None):
        super().__init__(str(texto), padre)
        self.setAutoExclusive(False)
        self.setFont(fuente(tam, peso='medio' if negrita else None))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if color:
            self.setStyleSheet(f'QRadioButton {{ color: {_color(color)}; }}')
        self._var = var
        self._valor = valor
        self._comando = comando
        if var is not None:
            self.setChecked(var.get() == valor)
            var.observar(self._desde_var, self)
        self.clicked.connect(self._clic)

    def nextCheckState(self):
        self.setChecked(True)

    def _clic(self, _marcado=True):
        if self._var is not None:
            self._var.set(self._valor)
        if self._comando:
            self._comando()

    def _desde_var(self):
        v = self._var.get() == self._valor
        if v != self.isChecked():
            self.blockSignals(True)
            self.setChecked(v)
            self.blockSignals(False)


class Segmentado(QWidget):
    """El CTkSegmentedButton, con la pastilla elegida que se DESLIZA."""
    def __init__(self, valores, var=None, comando=None, alto=36, tam=14, padre=None,
                 iguales=False):
        super().__init__(padre)
        self._valores = [str(v) for v in valores]
        self._var = var
        self._comando = comando
        self._iguales = bool(iguales)
        self._sel = self._valores[0] if (var is None and self._valores) else None
        self._hover = -1
        self.setFixedHeight(int(alto))
        self.setFont(fuente(tam, peso='medio'))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._pos = float(max(0, self._indice()))
        self._res = Resorte(self._pos, 360.0, 25.0)           # v5.5: resorte (k=360, c=25): llega rapido y rebota apenas
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        if var is not None:
            var.observar(self._desde_var, self)

    def _indice(self):
        v = self._var.get() if self._var is not None else self._sel
        try:
            return self._valores.index(str(v))
        except ValueError:
            return -1

    def _mover(self, v):
        self._pos = float(v)
        self.update()

    def _ir_a(self, i, animar=True):
        if i < 0:
            self.update()
            return
        if not animar or not self.isVisible():
            self._res.poner(i)
            self._pos = float(i)
            self.update()
            return
        self._res.objetivo = float(i)
        motor_resortes.pedir(self)

    def paso_resorte(self, dt):
        sigue = self._res.paso(dt)
        self._pos = max(0.0, min(float(len(self._valores) - 1), self._res.x))
        self.update()
        return sigue

    def _desde_var(self):
        self._ir_a(self._indice())

    def poner_valores(self, valores):
        self._valores = [str(v) for v in valores]
        self._pos = float(max(0, self._indice()))
        self._res.poner(self._pos)
        self.updateGeometry()
        self.update()

    def set(self, valor):
        if self._var is not None:
            self._var.set(valor)
        else:
            self._sel = valor
            self._ir_a(self._indice())

    def get(self):
        return self._var.get() if self._var is not None else self._sel

    def configure(self, state=None, values=None, **_):
        if values is not None:
            self.poner_valores(values)
        if state is not None:
            self.setEnabled(state != 'disabled')

    def _anchos(self):
        fm = QFontMetricsF(self.font())
        if self._iguales:
            base = [1.0] * max(1, len(self._valores))
        else:
            base = [fm.horizontalAdvance(v) + 32 for v in self._valores] or [1]
        total = sum(base)
        disponible = max(1.0, self.width() - 8.0)
        return [b * disponible / total for b in base]

    def sizeHint(self):
        fm = QFontMetricsF(self.font())
        return QSize(int(sum(fm.horizontalAdvance(v) + 32 for v in self._valores) + 10), self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def _rect(self, i):
        anchos = self._anchos()
        x = 4.0 + sum(anchos[:i])
        return QRectF(x, 4, anchos[i], self.height() - 8)

    def _rect_pos(self, pos):
        i = int(pos)
        f = pos - i
        a = self._rect(min(i, len(self._valores) - 1))
        if f <= 0 or i + 1 >= len(self._valores):
            return a
        b = self._rect(i + 1)
        return QRectF(a.x() + (b.x() - a.x()) * f, a.y(), a.width() + (b.width() - a.width()) * f, a.height())

    def _en(self, x):
        acum = 4.0
        for i, w in enumerate(self._anchos()):
            if acum <= x < acum + w:
                return i
            acum += w
        return -1

    def mouseMoveEvent(self, e):
        h = self._en(e.position().x())
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if not self.isEnabled() or e.button() != Qt.MouseButton.LeftButton:
            return
        i = self._en(e.position().x())
        if i < 0:
            return
        valor = self._valores[i]
        if i != self._indice():
            if self._var is not None:
                self._var.set(valor)
            else:
                self._sel = valor
                self._ir_a(i)
        if self._comando:
            self._comando(valor)

    def paintEvent(self, _e):
        if not self._valores:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(BORDER_COLOR), 1))
        p.setBrush(QColor('#0B1322'))
        p.drawRoundedRect(r, 10, 10)
        en = self.isEnabled()
        if self._indice() >= 0:
            sel = self._rect_pos(self._pos)
            p.setPen(Qt.PenStyle.NoPen)
            if en:
                # el resplandor de la pastilla elegida (dos capas translucidas)
                for grosor, alfa in ((8.0, 26), (4.0, 54)):
                    halo = QColor(ACCENT)
                    halo.setAlpha(alfa)
                    p.setBrush(halo)
                    p.drawRoundedRect(sel.adjusted(-grosor / 2, -grosor / 2, grosor / 2, grosor / 2), 7 + grosor / 2, 7 + grosor / 2)
            p.setBrush(QColor(ACCENT if en else '#1B2A48'))
            p.drawRoundedRect(sel, 7, 7)
        p.setFont(self.font())
        elegido = self._indice()
        for i, v in enumerate(self._valores):
            rr = self._rect(i)
            if i == elegido:
                c = '#FFFFFF' if en else '#8D9BB5'
            elif i == self._hover and en:
                c = '#E0EBFB'
            else:
                c = '#8D9BB5' if en else '#4F607A'
            p.setPen(QColor(c))
            p.drawText(rr, int(Qt.AlignmentFlag.AlignCenter), v)
        p.end()


class Deslizador(QSlider):
    """El CTkSlider: valor real entre 'desde' y 'hasta' en 'pasos' pasos;
    set() no dispara el comando (igual que en ctk)."""
    def __init__(self, desde=0.0, hasta=1.0, pasos=100, comando=None, inicial=None, padre=None):
        super().__init__(Qt.Orientation.Horizontal, padre)
        self._a = float(desde)
        self._b = float(hasta)
        self._n = max(1, int(pasos))
        self.setRange(0, self._n)
        self.setSingleStep(1)
        self.setPageStep(max(1, self._n // 10))
        self.setFixedHeight(24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._comando = comando
        if inicial is not None:
            self.set(inicial)
        self.valueChanged.connect(self._cambio)

    def wheelEvent(self, e):
        if not self.hasFocus():
            e.ignore()
            return
        super().wheelEvent(e)

    def get(self):
        return self._a + (self._b - self._a) * self.value() / self._n

    def set(self, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return
        k = round((v - self._a) / (self._b - self._a) * self._n) if self._b != self._a else 0
        self.blockSignals(True)
        self.setValue(max(0, min(self._n, int(k))))
        self.blockSignals(False)

    def _cambio(self, _v):
        if self._comando:
            self._comando(self.get())


class DeslizadorValores(QSlider):
    """Un deslizador sobre una lista FIJA de valores (los mismos del
    desplegable de la v4: «Aparecer antes» 0, 1, 2… 30). La Var guarda el
    valor como texto, igual que el CTkOptionMenu de antes."""
    def __init__(self, valores, var, comando=None, padre=None):
        super().__init__(Qt.Orientation.Horizontal, padre)
        self._valores = [str(v) for v in valores]
        self._var = var
        self._comando = comando
        self.setRange(0, max(0, len(self._valores) - 1))
        self.setSingleStep(1)
        self.setPageStep(1)
        self.setFixedHeight(24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._desde_var()
        self.valueChanged.connect(self._cambio)
        var.observar(self._desde_var, self)

    def wheelEvent(self, e):
        if not self.hasFocus():
            e.ignore()
            return
        super().wheelEvent(e)

    def _desde_var(self):
        v = str(self._var.get())
        i = self._valores.index(v) if v in self._valores else 0
        if i != self.value():
            self.blockSignals(True)
            self.setValue(i)
            self.blockSignals(False)

    def _cambio(self, i):
        v = self._valores[max(0, min(i, len(self._valores) - 1))]
        if v != str(self._var.get()):
            self._var.set(v)
        if self._comando:
            self._comando(v)

    def configure(self, state=None, **_):
        if state is not None:
            self.setEnabled(state != 'disabled')


class BarraProgreso(QWidget):
    """La barra de progreso: relleno del color de acento con un brillo que la
    recorre mientras avanza y modo indeterminado (un tramo que va y viene)."""
    def __init__(self, alto=8, padre=None, color=ACCENT, color2=None):
        super().__init__(padre)
        self._alto_barra = int(alto)
        self.setFixedHeight(int(alto) + 14)            # v5.5: 7 px de aire arriba y abajo para el resplandor de neon
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._color = QColor(color)
        self._color2 = QColor(color2) if color2 else None
        self._valor = 0.0
        self._visto = 0.0
        self._modo = 'determinate'
        self._fase = 0.0
        self._reloj = QTimer(self)
        self._reloj.setInterval(16)
        self._reloj.timeout.connect(self._tic)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._mover)

    def _mover(self, v):
        self._visto = float(v)
        self.update()

    def _tic(self):
        self._fase = (self._fase + 0.012) % 1.6
        self.update()

    # v5.39: oculta (otra página) no repinta a 60 fps; al volver a verse sigue donde iba
    def hideEvent(self, e):
        self._pausada = self._reloj.isActive()
        self._reloj.stop()
        super().hideEvent(e)

    def showEvent(self, e):
        if getattr(self, '_pausada', False):
            self._pausada = False
            self._reloj.start()
        super().showEvent(e)

    def set(self, valor):
        try:
            v = max(0.0, min(1.0, float(valor)))
        except (TypeError, ValueError):
            return
        self._valor = v
        if self._modo == 'determinate':
            self._anim.stop()
            self._anim.setStartValue(self._visto)
            self._anim.setEndValue(v)
            self._anim.start()
            if 0.0 < v < 1.0:
                if not self._reloj.isActive():
                    self._reloj.start()
            elif self._reloj.isActive():
                self._reloj.stop()

    def get(self):
        return self._valor

    def configure(self, mode=None, **_):
        if mode:
            self._modo = mode
            if mode == 'determinate':
                self._fase = 0.0
            self.update()

    def start(self):
        if not self._reloj.isActive():
            self._reloj.start()

    def stop(self):
        if self._modo == 'indeterminate' or not (0.0 < self._valor < 1.0):
            self._reloj.stop()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 7, self.width(), self._alto_barra)
        radio = r.height() / 2
        # el carril: vidrio oscuro con el borde de 1 px
        p.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radio, radio)
        p.setPen(Qt.PenStyle.NoPen)
        if self._modo == 'indeterminate':
            ancho = r.width() * 0.32
            x = -ancho + (self._fase / 1.6) * (r.width() + ancho)
            tramo = QRectF(max(0.0, x), r.top(), min(r.width(), x + ancho) - max(0.0, x), r.height())
            if tramo.width() > 0:
                for grosor, alfa in ((10.0, 26), (5.0, 60)):
                    halo = QColor(self._color)
                    halo.setAlpha(alfa)
                    p.setBrush(halo)
                    p.drawRoundedRect(tramo.adjusted(-grosor / 2, -grosor / 2, grosor / 2, grosor / 2), radio + grosor / 2, radio + grosor / 2)
                g = QLinearGradient(QPointF(x, 0), QPointF(x + ancho, 0))
                c0 = QColor(self._color)
                c0.setAlpha(0)
                g.setColorAt(0, c0)
                g.setColorAt(0.5, self._color)
                g.setColorAt(1, c0)
                p.setBrush(QBrush(g))
                p.drawRoundedRect(tramo, radio, radio)
            p.end()
            return
        if self._visto <= 0.0005:
            p.end()
            return
        w = max(r.height(), r.width() * self._visto)
        relleno = QRectF(0, r.top(), w, r.height())
        camino = QPainterPath()
        camino.addRoundedRect(relleno, radio, radio)
        # el resplandor de neon: dos capas translucidas mas anchas detras del relleno
        for grosor, alfa in ((12.0, 24), (6.0, 56)):
            halo = QColor(self._color)
            halo.setAlpha(alfa)
            p.setBrush(halo)
            p.drawRoundedRect(relleno.adjusted(-grosor / 2, -grosor / 2, grosor / 2, grosor / 2), radio + grosor / 2, radio + grosor / 2)
        if self._color2 is not None:
            g = QLinearGradient(QPointF(0, 0), QPointF(r.width(), 0))
            g.setColorAt(0, self._color)
            g.setColorAt(1, self._color2)
            p.fillPath(camino, QBrush(g))
        else:
            p.fillPath(camino, self._color)
        if self._reloj.isActive() and self._visto < 1.0:
            x = (self._fase / 1.6) * (w + 120) - 60
            brillo = QLinearGradient(QPointF(x - 60, 0), QPointF(x + 60, 0))
            brillo.setColorAt(0, QColor(255, 255, 255, 0))
            brillo.setColorAt(0.5, QColor(255, 255, 255, 90))
            brillo.setColorAt(1, QColor(255, 255, 255, 0))
            p.save()
            p.setClipPath(camino)
            p.fillRect(QRectF(x - 60, r.top(), 120, r.height()), QBrush(brillo))
            p.restore()
        if 0.0 < self._visto < 1.0:
            # la bolita de luz que va en la punta, como en el termometro de neon de las referencias
            cx, cy = w - radio, r.center().y()
            halo = QRadialGradient(QPointF(cx, cy), r.height() * 1.8)
            halo.setColorAt(0.0, QColor(255, 255, 255, 190))
            halo.setColorAt(0.35, QColor(self._color.red(), self._color.green(), self._color.blue(), 120))
            halo.setColorAt(1.0, QColor(self._color.red(), self._color.green(), self._color.blue(), 0))
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(cx, cy), r.height() * 1.8, r.height() * 1.8)
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(QPointF(cx, cy), r.height() * 0.62, r.height() * 0.62)
        p.end()


class Desplazable(QScrollArea):
    """El CTkScrollableFrame: un QScrollArea con su columna de widgets."""
    def __init__(self, padre=None, margenes=(0, 0, 0, 0), espacio=8, estirar_final=True):
        super().__init__(padre)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.interior = QWidget()
        self.interior.setObjectName('interiorScroll')
        self.capa = QVBoxLayout(self.interior)
        self.capa.setContentsMargins(*margenes)
        self.capa.setSpacing(espacio)
        self._estirar = bool(estirar_final)
        if self._estirar:
            self.capa.addStretch(1)
        self.setWidget(self.interior)
        self.viewport().setAutoFillBackground(False)
        self.interior.setAutoFillBackground(False)
        self.rueda_a = None       # opcional: función(evento) -> bool; si la pantalla quiere la rueda para otra cosa (el slider de Proyecto), la toma ella

    def agregar(self, w, estirar=0, alineacion=None):
        pos = self.capa.count() - 1 if self._estirar else self.capa.count()
        if alineacion is not None:
            self.capa.insertWidget(pos, w, estirar, alineacion)
        else:
            self.capa.insertWidget(pos, w, estirar)
        return w

    def limpiar(self):
        limpiar_capa(self.capa)
        if self._estirar:
            self.capa.addStretch(1)

    def arriba(self):
        self.verticalScrollBar().setValue(0)

    def wheelEvent(self, e):
        f = self.rueda_a
        if f is not None:
            try:
                if f(e):
                    e.accept()
                    return
            except Exception:
                pass
        super().wheelEvent(e)


class RuedaHacia(QObject):
    """La rueda del ratón sobre CUALQUIER widget de `zona` (y los que se añadan luego) llama a `funcion(evento)`; si devuelve True se consume y la zona no
    se desplaza. Se instala un filtro por widget (no uno global: costaría un paso por Python por cada evento de la aplicación). Los desplegables, campos
    numéricos, deslizadores, listas y cuadros de texto conservan su propia rueda."""
    def __init__(self, zona, funcion):
        super().__init__(zona)
        self._funcion = funcion
        self._excluidos = (QComboBox, QAbstractSpinBox, QAbstractSlider, QAbstractItemView, QTextEdit, QPlainTextEdit)
        self._poner(zona)

    def _poner(self, w):
        w.installEventFilter(self)
        if w.isWidgetType():
            for h in w.findChildren(QWidget):
                h.installEventFilter(self)

    def eventFilter(self, o, e):
        t = e.type()
        if t == QEvent.Type.Wheel:
            if not isinstance(o, self._excluidos):
                try:
                    if self._funcion(e):
                        e.accept()
                        return True
                except Exception:
                    return False
        elif t == QEvent.Type.ChildAdded:
            h = e.child()
            if h is not None and h.isWidgetType():
                self._poner(h)
        return False


class Menu(QMenu):
    """El tk.Menu de clic derecho."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFont(fuente(13))
        self.setProperty('pildora', True)              # v5.4.21: opciones en píldoras (ver la hoja de estilos)
        _panel_translucido(self)

    def agregar(self, texto, fn):
        a = self.addAction(str(texto))
        if str(texto).lstrip().startswith('✓'):        # la opción en uso (los llamadores le ponen «✓  » delante): su píldora va rellena de azul
            a.setCheckable(True)
            a.setChecked(True)
        a.triggered.connect(lambda _=False, f=fn: f())
        return a

    def add_command(self, label='', command=None):
        return self.agregar(label, command or (lambda: None))

    def separador(self):
        self.addSeparator()

    add_separator = separador

    def vacio(self):
        return not self.actions()

    def mostrar(self, x, y=None):
        pos = x if y is None else QPoint(int(x), int(y))
        self.exec(pos)


# ---------------------------------------------------------------------------
# Piezas del panel (la propuesta de 5 pantallas)
class Chip(QAbstractButton):
    """Una pastilla con borde de color: estados («Listo», «Traducido»),
    chips clicables («Usar», «Fuente: Esenciales», idiomas frecuentes) y
    etiquetas de rol. 'punto' pinta un circulito delante; 'estrella' una ★
    ambar delante; 'lleno' rellena el fondo con el color al 18 %."""
    def __init__(self, texto='', color=ACCENT_CLARO, comando=None, punto=None, estrella=False,
                 alto=28, tam=13, lleno=False, padre=None, fondo=None):
        super().__init__(padre)
        self.setText(str(texto))
        self._color = QColor(_color(color))
        self._punto = QColor(_color(punto)) if punto else None
        self._estrella = bool(estrella)
        self._lleno = bool(lleno)
        self._fondo = QColor(_color(fondo)) if fondo else None
        self._hover = False
        self._h = 0.0
        self._a_h = QVariantAnimation(self)
        self._a_h.setDuration(150)
        self._a_h.valueChanged.connect(self._paso_h)
        self._comando = comando
        self.setFont(fuente(tam, peso='medio'))
        self.setFixedHeight(int(alto))
        if comando:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.clicked.connect(lambda: self._comando() if self._comando else None)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def poner(self, texto=None, color=None, lleno=None, punto=None):
        if texto is not None:
            self.setText(str(texto))
        if color is not None:
            self._color = QColor(_color(color))
        if lleno is not None:
            self._lleno = bool(lleno)
        if punto is not None:
            self._punto = QColor(_color(punto)) if punto else None
        self.updateGeometry()
        self.update()

    def poner_comando(self, comando):
        if self._comando is None:
            self.clicked.connect(lambda: self._comando() if self._comando else None)
        self._comando = comando
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def configure(self, text=None, state=None, **_):
        """Compat v4 (Boton.configure): texto y estado."""
        if text is not None:
            self.poner(texto=text)
        if state is not None:
            self.setEnabled(state != 'disabled')
            self.update()

    def sizeHint(self):
        fm = QFontMetricsF(self.font())
        extra = (14 if self._punto is not None else 0) + (16 if self._estrella else 0)
        return QSize(int(fm.horizontalAdvance(self.text()) + 24 + extra), self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def _paso_h(self, v):
        self._h = float(v)
        self.update()

    def _ir_h(self, meta):
        self._a_h.stop()
        self._a_h.setStartValue(self._h)
        self._a_h.setEndValue(float(meta))
        self._a_h.start()

    def enterEvent(self, e):
        self._hover = True
        self._ir_h(1.0)
        if self._comando:
            _brillo.entrar(self)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._ir_h(0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if self._comando and e.button() == Qt.MouseButton.LeftButton:
            _brillo.presionar(self, e)
        super().mousePressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        _brillo.ajustar(self)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        c = QColor(self._color)
        if not self.isEnabled():
            c = QColor('#3A4A66')
        fondo = self._fondo
        if self._lleno:
            fondo = mezclar(c, '#0D1627', 0.22 + 0.06 * self._h)
        elif self._comando and self._h > 0.01:
            fondo = mezclar(c, '#0D1627', 0.12 * self._h)
        p.setPen(QPen(c, 1))
        p.setBrush(fondo if fondo is not None else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        x = 12.0
        if self._estrella:
            p.setPen(QColor(AMBAR))
            p.setFont(fuente(self.font().pixelSize(), peso='medio'))
            p.drawText(QRectF(x - 2, 0, 16, self.height()), int(Qt.AlignmentFlag.AlignVCenter), '★')
            x += 16
        if self._punto is not None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._punto)
            p.drawEllipse(QRectF(x, self.height() / 2 - 4, 8, 8))
            x += 14
        p.setPen(c if self.isEnabled() else QColor('#5A6B87'))
        p.setFont(self.font())
        p.drawText(QRectF(x, 0, self.width() - x - 10, self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()


class Punto(QWidget):
    """El circulito de estado (verde / ambar / rojo / azul)."""
    def __init__(self, color=VERDE, lado=8, padre=None):
        super().__init__(padre)
        self._color = QColor(_color(color))
        self.setFixedSize(lado + 2, lado + 2)

    def poner(self, color):
        self._color = QColor(_color(color))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(1, 1, self.width() - 2, self.height() - 2))
        p.end()


class IconoEstado(QWidget):
    """El ✓ verde (o ! ambar, ✕ rojo) de «Estado del sistema»."""
    def __init__(self, tipo='ok', padre=None):
        super().__init__(padre)
        self._tipo = tipo
        self.setFixedSize(20, 20)
        self._k = 1.0
        self._a_k = QVariantAnimation(self)
        self._a_k.setDuration(380)
        self._a_k.setStartValue(0.0)
        self._a_k.setEndValue(1.0)
        self._a_k.setEasingCurve(QEasingCurve.Type.OutBack)
        self._a_k.valueChanged.connect(self._paso_k)

    def _paso_k(self, v):
        self._k = float(v)
        self.update()

    def poner(self, tipo):
        cambio = tipo != self._tipo
        self._tipo = tipo
        if cambio and not _brillo.quieto() and self.isVisible():
            self._a_k.stop()
            self._a_k.start()
        self.update()

    def paintEvent(self, _e):
        color = {'ok': VERDE, 'aviso': AMBAR, 'error': ROJO, 'info': ACCENT_CLARO}.get(self._tipo, VERDE)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._k < 1.0:
            esc = max(0.05, 0.4 + 0.6 * self._k)
            p.translate(10, 10)
            p.scale(esc, esc)
            p.translate(-10, -10)
        c = QColor(color)
        fondo = QColor(c)
        fondo.setAlpha(46)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawEllipse(QRectF(0, 0, 20, 20))
        p.setPen(QPen(c, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self._tipo == 'ok':
            p.drawPolyline([QPointF(6, 10.4), QPointF(8.8, 13), QPointF(14, 7.4)])
        elif self._tipo == 'error':
            p.drawLine(QPointF(7, 7), QPointF(13, 13))
            p.drawLine(QPointF(13, 7), QPointF(7, 13))
        else:
            p.drawLine(QPointF(10, 5.5), QPointF(10, 11))
            p.drawPoint(QPointF(10, 14.2))
        p.end()


class Onda(QWidget):
    """Una forma de onda en barras (fuente de video y sonidos del SFX Lab).
    picos: lista de 0..1. Sin picos dibuja una onda de muestra tenue.
    v5.5: reproducir(segundos) la recorre con un cabezal: las barras ya «sonadas» se encienden (el sonido de una regla)."""
    def __init__(self, color=ACCENT_CLARO, alto=48, barra=3.0, hueco=2.5, padre=None):
        super().__init__(padre)
        self._color = QColor(_color(color))
        self._picos = []
        self._barra = float(barra)
        self._hueco = float(hueco)
        self._prog = None            # None = quieta; 0..1 = el cabezal
        self._anim = None
        self.setMinimumHeight(int(alto))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner_picos(self, picos):
        self._picos = [max(0.0, min(1.0, float(v))) for v in (picos or [])]
        self.update()

    def tiene_picos(self):
        return bool(self._picos)

    def reproducir(self, segundos):
        """El cabezal va de 0 a 1 en 'segundos' y se apaga solo."""
        try:
            if self._anim is not None:
                self._anim.stop()
            self._anim = QVariantAnimation(self)
            self._anim.setDuration(int(max(0.15, float(segundos)) * 1000))
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.valueChanged.connect(self._paso_prog)
            self._anim.finished.connect(self._fin_prog)
            self._anim.start()
        except Exception:
            self._prog = None

    def _paso_prog(self, v):
        self._prog = float(v)
        self.update()

    def _fin_prog(self):
        self._prog = None
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        paso = self._barra + self._hueco
        n = max(1, int(w // paso))
        picos = self._picos
        tenue = not picos
        if tenue:
            picos = [0.25 + 0.55 * abs(math.sin(i * 0.37) * math.cos(i * 0.11)) for i in range(n)]
        c = QColor(self._color)
        if tenue or self._prog is not None:
            c.setAlpha(70)
        encendida = QColor(self._color).lighter(135)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        for i in range(n):
            k = int(i * len(picos) / n)
            v = picos[min(k, len(picos) - 1)]
            alto = max(4.0, v * (h - 4))
            x = i * paso
            if self._prog is not None and (i / n) <= self._prog:
                p.setBrush(encendida)
            elif self._prog is not None:
                p.setBrush(c)
            p.drawRoundedRect(QRectF(x, (h - alto) / 2, self._barra, alto), self._barra / 2, self._barra / 2)
        p.end()


def icono_onda(lado=64, color=ACCENT_CLARO):
    """El dibujo de la zona para soltar: una onda simetrica de barras."""
    def dibujar(p, s):
        c = QColor(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        n = 27
        paso = s / n
        for i in range(n):
            v = 0.18 + 0.82 * abs(math.sin(i * 0.55) * math.cos(i * 0.21))
            alto = max(s * 0.08, v * s * 0.9)
            p.drawRoundedRect(QRectF(i * paso, (s - alto) / 2, paso * 0.62, alto), paso * 0.3, paso * 0.3)
    return icono_dibujado(dibujar, lado)


class Pasos(QWidget):
    """El indicador de 4 pasos de «Nuevo proyecto»: solo visual, no bloquea.
    estados: lista de 'hecho' | 'actual' | 'pendiente'."""
    def __init__(self, nombres, padre=None):
        super().__init__(padre)
        self._nombres = list(nombres)
        self._estados = ['pendiente'] * len(self._nombres)
        self.setFixedHeight(40)
        self.setFont(fuente(16, peso='medio'))

    def poner(self, estados):
        estados = list(estados)
        if estados != self._estados:
            self._estados = estados
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self._nombres)
        tramo = self.width() / max(1, n)
        cy = self.height() / 2
        fm = QFontMetricsF(self.font())
        for i, nombre in enumerate(self._nombres):
            x = i * tramo
            estado = self._estados[i] if i < len(self._estados) else 'pendiente'
            color = {'hecho': VERDE, 'actual': ACCENT}.get(estado, '#1B2740')
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x, cy - 14, 28, 28))
            p.setPen(QColor('#FFFFFF' if estado != 'pendiente' else '#C9D6EC'))
            p.setFont(fuente(13, peso='negrita'))
            p.drawText(QRectF(x, cy - 14, 28, 28), int(Qt.AlignmentFlag.AlignCenter), str(i + 1))
            p.setFont(self.font())
            p.setPen(QColor('#FFFFFF' if estado != 'pendiente' else TEXT_MUTED))
            ancho_txt = fm.horizontalAdvance(nombre)
            p.drawText(QRectF(x + 38, 0, ancho_txt + 4, self.height()),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), nombre)
            if i + 1 < n:
                x0 = x + 38 + ancho_txt + 20
                x1 = (i + 1) * tramo - 20
                if x1 > x0:
                    hecho = estado == 'hecho'
                    p.setPen(QPen(QColor(VERDE if hecho else '#1E2A42'), 2))
                    p.drawLine(QPointF(x0, cy), QPointF(x1, cy))
        p.end()


class ZonaSoltar(QFrame):
    """La zona punteada de «Inicio»: se le puede soltar un video o audio."""
    def __init__(self, al_soltar=None, padre=None):
        super().__init__(padre)
        self._al_soltar = al_soltar
        self._encima = False
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._encima = True
            self.update()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._encima = False
        self.update()

    def dropEvent(self, e):
        self._encima = False
        self.update()
        for url in e.mimeData().urls():
            ruta = url.toLocalFile()
            if ruta and self._al_soltar:
                self._al_soltar(ruta)
                break

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self._encima:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(15, 98, 254, 26))
            p.drawRoundedRect(r, 10, 10)
        pen = QPen(QColor(ACCENT_CLARO if self._encima else '#2A3A58'), 1.6)
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 10, 10)
        p.end()


class MarcoVista(QWidget):
    """El marco negro de las vistas previas: hasta tres lineas con su
    tipografia, tamaño relativo y color. Es APROXIMADO (pedido: «dibujarlas y
    marcarlas aprox.»): Resolve es quien manda; aqui se ve la intencion."""
    _MOVIL = None                    # (marco QImage, info, fondo QImage) de 2_recursos/creativo, cargado una vez

    def __init__(self, padre=None, alto_min=160, aprox=True, movil=False):
        super().__init__(padre)
        self._lineas = []
        self._imagen = None
        self._movil = bool(movil)    # v5.5.10: dentro de un móvil, sobre una foto de muestra (Creativo › «Así se verá este bloque»)
        self._aprox = bool(aprox) and not self._movil
        self._cuadro = None          # v5.5.10: el cuadro EXACTO del tema (vista_tema.py), ya con foto y captions: se ve tal cual en la pantalla
        self._progreso = None        # 0..1 mientras se reproduce (la barrita de abajo, como en un reel)
        self.al_cambiar_tamano = None
        self._animador = None        # v5.5.10: {'cu': vista_tema.Cuadros, 'k': cue en bucle, 't': instante fijo} -> los captions ANIMADOS
        self._t0_bucle = 0.0
        self._reloj_anim = None
        self._boton_sec = None
        self._pie = ''
        self._fondo = None
        self._t_anim = None          # v5.4: segundos desde que entro el bloque (None = quieto, como siempre)
        self._salida = 0.0           # 0..1: el bloque se desvanece al terminar
        self.setMinimumHeight(int(alto_min))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def poner(self, lineas, pie=None, imagen=None):
        """lineas: [(texto, {'familia','peso','italica','tam' (0..1 del alto),
        'color', 'contorno'})]
        imagen (v5.3): el espacio del bloque «imagen», {'donde': 'abajo'|'arriba', 'zoom': 1.0, 'pix': QPixmap|None}:
        un recuadro punteado donde irá el icono o la imagen, o el emoji ya dentro."""
        self._lineas = list(lineas or [])
        self._imagen = dict(imagen) if imagen else None
        if pie is not None:
            self._pie = pie
        self.update()

    def animar(self, t, salida=0.0):
        """v5.4: la vista REAL del bloque: t = segundos desde que entro. Cada linea entra una tras otra con rebote
        (escala + subida + fundido), como los bloques que coloca Resolve. t=None vuelve a la vista quieta."""
        self._t_anim = t
        self._salida = float(salida or 0.0)
        self.update()

    def animar_bucle(self, si, periodo=2.6):
        """v5.5: la vista previa se anima EN BUCLE (entrada de cada linea, quieta, salida) mientras 'si'; al soltar vuelve a la vista fija.
        Un solo temporizador de 33 ms, que solo existe mientras se ve la animacion."""
        if not si:
            t = getattr(self, '_reloj_bucle', None)
            if t is not None:
                t.stop()
            self.animar(None)
            return
        if getattr(self, '_reloj_bucle', None) is None:
            self._reloj_bucle = QTimer(self)
            self._reloj_bucle.timeout.connect(self._tic_bucle)
        self._periodo_bucle = float(periodo)
        self._t0_bucle = time.perf_counter()
        self._reloj_bucle.start(33)

    def _tic_bucle(self):
        if not self.isVisible():
            self._reloj_bucle.stop()
            return
        t = (time.perf_counter() - self._t0_bucle) % self._periodo_bucle
        salida = max(0.0, min(1.0, (t - (self._periodo_bucle - 0.35)) / 0.3))
        self.animar(t, salida=salida)

    @staticmethod
    def _rebote(x):
        x = max(0.0, min(1.0, x))
        s = 1.70158
        x -= 1
        return x * x * ((s + 1) * x + s) + 1

    def _dibujar_imagen(self, p, dentro, y, lado, img):
        """El espacio «imagen»: el emoji si ya lo hay, o un recuadro punteado verde con su etiqueta."""
        caja = QRectF(dentro.center().x() - lado / 2, y, lado, lado)
        verde = QColor(ROL_IMAGEN)
        pix = img.get('pix')
        p.save()
        if pix is not None and not pix.isNull():
            p.drawPixmap(caja, pix, QRectF(pix.rect()))
        else:
            pen = QPen(verde, 1.4)
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([3.0, 3.0])
            fondo = QColor(verde)
            fondo.setAlpha(26)
            p.setPen(pen)
            p.setBrush(fondo)
            p.drawRoundedRect(caja, lado * 0.24, lado * 0.24)
            p.setPen(QPen(verde, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            c = caja.center()
            p.drawEllipse(QPointF(c.x(), c.y() - lado * 0.06), lado * 0.13, lado * 0.13)
            if lado >= 44:
                p.setFont(fuente(9, peso='medio'))
                p.drawText(QRectF(caja.left(), caja.bottom() - lado * 0.32, caja.width(), lado * 0.28),
                           int(Qt.AlignmentFlag.AlignCenter), tr('imagen'))
        p.restore()

    def poner_fondo(self, imagen, real=False):
        """v5.1: un fotograma de verdad (QImage, p. ej. el de Resolve por MCP)
        detras del texto, o None para el fondo negro de siempre.
        v5.2: real=True es un fotograma YA renderizado por Resolve con los
        subtitulos puestos: se ve entero (sin recortar ni oscurecer) y con
        el sello «Render real» en vez de «aprox.»."""
        self._fondo = imagen if imagen is not None and not imagen.isNull() else None
        self._real = bool(real) and self._fondo is not None
        self.update()

    def tiene_fondo(self):
        return self._fondo is not None

    # -- v5.5.10 (pedido: «un mockup de móvil con el fondo dentro y encima los captions»): el modo móvil ----------------------------
    @classmethod
    def _recursos_movil(cls):
        """El marco del móvil (PNG con la pantalla transparente), dónde está su pantalla (fracciones del PNG) y la foto de muestra."""
        if cls._MOVIL is None:
            try:
                import instalador_scripts
                base = Path(instalador_scripts.BASE_RECURSOS) / 'creativo'
            except Exception:
                base = Path(__file__).resolve().parent.parent / '2_recursos' / 'creativo'
            info = {'pantalla': [0.0625, 0.0272, 0.9363, 0.9728], 'radio': 0.127, 'aspecto': 0.499}
            try:
                import json
                info.update(json.loads((base / 'movil.json').read_text(encoding='utf-8')))
            except Exception:
                pass
            cls._MOVIL = (QImage(str(base / 'movil_marco.png')), info, QImage(str(base / 'movil_fondo.jpg')))
        return cls._MOVIL

    def geometria_movil(self):
        """(caja del móvil, su pantalla, radio de la pantalla): el móvil entero cabe en el widget, centrado."""
        _marco, info, _fondo = self._recursos_movil()
        r = QRectF(self.rect()).adjusted(18, 8, -18, -46)               # (sitio para la sombra y el resplandor de abajo)
        asp = float(info.get('aspecto') or 0.5)
        h = r.height()
        w = h * asp
        if w > r.width():
            w = r.width()
            h = w / asp
        caja = QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)
        a = info.get('pantalla') or [0.0625, 0.0272, 0.9363, 0.9728]
        pant = QRectF(caja.left() + a[0] * w, caja.top() + a[1] * h, (a[2] - a[0]) * w, (a[3] - a[1]) * h)
        return caja, pant, float(info.get('radio') or 0.127) * pant.width()

    def poner_boton_en_pantalla(self, boton):
        """Un botón (el play de Creativo) DENTRO de la pantalla del móvil, abajo al centro; se recoloca al cambiar de tamaño."""
        self._boton_pantalla = boton
        boton.setParent(self)
        boton.show()
        self._colocar_boton_pantalla()

    def _colocar_boton_pantalla(self):
        b = getattr(self, '_boton_pantalla', None)
        if b is None:
            return
        if self._movil:
            _caja, pant, _r = self.geometria_movil()
            x, y = pant.center().x() - b.width() / 2, pant.bottom() - b.height() - pant.height() * 0.045
        else:
            x, y = self.width() - b.width() - 14, self.height() - b.height() - 14
        b.move(int(x), int(y))
        b.raise_()
        s = self._boton_sec
        if s is not None:                                               # el secundario (silenciar), a la derecha del play
            s.move(int(x + b.width() + 10), int(y + (b.height() - s.height()) / 2))
            s.raise_()

    def poner_boton_secundario(self, boton):
        """v5.5.10 (pedido: «al pasar el mouse por el play, que salga un icono de mutear sonido»): un botón pequeño junto al play que solo se ve
        mientras el ratón está sobre el play o sobre él."""
        self._boton_sec = boton
        boton.setParent(self)
        boton.hide()
        for w in (getattr(self, '_boton_pantalla', None), boton):
            if w is not None:
                w.installEventFilter(self)
        self._colocar_boton_pantalla()

    def eventFilter(self, obj, ev):
        s = self._boton_sec
        if s is not None and obj in (s, getattr(self, '_boton_pantalla', None)):
            if ev.type() == QEvent.Type.Enter:
                s.show()
                s.raise_()
            elif ev.type() == QEvent.Type.Leave:
                QTimer.singleShot(650, self._quizas_ocultar_secundario)
        return super().eventFilter(obj, ev)

    def _quizas_ocultar_secundario(self):
        s, b = self._boton_sec, getattr(self, '_boton_pantalla', None)
        if s is not None and vivo(s) and not s.underMouse() and not (b is not None and b.underMouse()):
            s.hide()

    # -- v5.5.10: los captions ANIMADOS del tema (vista_tema.Cuadros.pintar) --------------------------------------------------------------
    def poner_animador(self, cuadros, k=None, t=None):
        """cuadros = vista_tema.Cuadros (None: sin vista exacta). k: el cue que se repite en bucle (vista quieta, con su propio reloj);
        t: un instante fijo (lo marca el play en cada tic)."""
        anterior = self._animador
        self._animador = None if cuadros is None else {'cu': cuadros, 'k': k, 't': t}
        if cuadros is not None and k is not None:
            if anterior is None or anterior.get('cu') is not cuadros or anterior.get('k') != k or anterior.get('t') is not None:
                self._t0_bucle = time.perf_counter()
            if self._reloj_anim is None:
                self._reloj_anim = QTimer(self)
                self._reloj_anim.timeout.connect(self._tic_anim)
                try:
                    import ritmo_ui
                    ritmo_ui.ritmo.poner(self._reloj_anim, 16)
                except Exception:
                    self._reloj_anim.setInterval(16)
            if not self._reloj_anim.isActive():
                self._reloj_anim.start()
        elif self._reloj_anim is not None:
            self._reloj_anim.stop()
        self.update()

    def _tic_anim(self):
        if self._animador is None or self._animador.get('k') is None or not self.isVisible():
            self._reloj_anim.stop()
            return
        self.update()

    def _t_animador(self):
        a = self._animador
        if a.get('t') is not None:
            return float(a['t'])
        ini, fin = a['cu'].tramo(a['k'])
        ciclo = max(0.8, fin - ini) + 0.75                              # el bloque entero (entra, se queda, se va) y una pausa corta
        return ini - 0.05 + (time.perf_counter() - self._t0_bucle) % ciclo

    def showEvent(self, e):
        super().showEvent(e)
        if self._animador is not None and self._animador.get('k') is not None and self._reloj_anim is not None:
            self._reloj_anim.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._colocar_boton_pantalla()
        if callable(self.al_cambiar_tamano):
            self.al_cambiar_tamano()

    def poner_cuadro(self, imagen):
        """El cuadro exacto del tema (QImage del tamaño de tamano_pantalla()) o None para volver al dibujo aproximado."""
        self._cuadro = imagen if imagen is not None and not imagen.isNull() else None
        self.update()

    def poner_progreso(self, fraccion):
        self._progreso = None if fraccion is None else max(0.0, min(1.0, float(fraccion)))
        self.update()

    def tamano_pantalla(self):
        """(ancho, alto) en píxeles REALES de la pantalla del móvil: a ese tamaño se rasterizan los cuadros del tema (nítidos en pantallas HiDPI)."""
        _caja, pant, _r = self.geometria_movil()
        dpr = max(1.0, float(self.devicePixelRatioF() or 1.0))
        return int(round(pant.width() * dpr)), int(round(pant.height() * dpr))

    def _imagen_en_pantalla(self):
        """(QImage, es_render_real) que se ve dentro de la pantalla: el render real de Resolve si lo hay; si no, la foto de muestra."""
        if getattr(self, '_real', False) and self._fondo is not None:
            return self._fondo, True
        return self._recursos_movil()[2], False

    def _pintar_en_pantalla(self, p, pant):
        """Los captions sobre la pantalla: en la franja de abajo-centro, donde los ponen los reels (el tamaño relativo de siempre)."""
        alto = pant.width() * 0.62
        zona = QRectF(pant.left() + pant.width() * 0.02, pant.top() + pant.height() * 0.64 - alto / 2, pant.width() * 0.96, alto)
        self._pintar_contenido(p, zona)

    def _sombra_movil(self, p, caja):
        """Sombra suave alrededor del móvil (capas cada vez más grandes y tenues; un poco hacia abajo, como si flotara sobre la página)."""
        rad = caja.width() * 0.165
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(10, 0, -1):
            g = i * 1.6
            p.setBrush(QColorReal(0, 0, 0, int(7 + (10 - i) * 1.6)))
            p.drawRoundedRect(caja.adjusted(-g, -g * 0.6 + 4, g, g + 8), rad + g, rad + g)
        p.restore()

    def _barra_estado(self, p, pant):
        """La barra de estado del teléfono (hora, cobertura, wifi y batería) a los lados de la isla, y el indicador de inicio abajo."""
        u = pant.width() / 100.0
        cy = pant.top() + pant.height() * 0.032
        blanco = QColorReal(255, 255, 255, 235)
        p.save()
        p.setPen(blanco)
        f = fuente(max(6.0, 4.3 * u), peso='negrita')
        p.setFont(f)
        p.drawText(QRectF(pant.left() + 6 * u, cy - 4 * u, 20 * u, 8 * u), int(Qt.AlignmentFlag.AlignCenter), '9:41')
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(blanco)
        x = pant.right() - 27 * u                                        # cobertura: 4 barras
        for i in range(4):
            h = (1.3 + i * 0.75) * u
            p.drawRoundedRect(QRectF(x + i * 1.55 * u, cy + 1.6 * u - h, 1.05 * u, h), 0.3 * u, 0.3 * u)
        x += 7.6 * u                                                     # wifi: tres arcos
        pen = QPen(blanco, max(1.0, 0.75 * u), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, r in enumerate((3.2, 2.1, 1.0)):
            rr = r * u
            p.drawArc(QRectF(x + 2.4 * u - rr, cy + 1.4 * u - rr, 2 * rr, 2 * rr), 50 * 16, 80 * 16)
        x += 6.2 * u                                                     # batería
        p.setPen(QPen(QColorReal(255, 255, 255, 150), max(1.0, 0.4 * u)))
        cuerpo = QRectF(x, cy - 1.45 * u, 6.6 * u, 3.1 * u)
        p.drawRoundedRect(cuerpo, 0.9 * u, 0.9 * u)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(blanco)
        p.drawRoundedRect(cuerpo.adjusted(0.55 * u, 0.55 * u, -1.6 * u, -0.55 * u), 0.5 * u, 0.5 * u)
        p.setBrush(QColorReal(255, 255, 255, 150))
        p.drawRoundedRect(QRectF(cuerpo.right() + 0.35 * u, cy - 0.55 * u, 0.55 * u, 1.1 * u), 0.2 * u, 0.2 * u)
        p.setBrush(QColorReal(255, 255, 255, 215))                       # indicador de inicio
        p.drawRoundedRect(QRectF(pant.center().x() - 18 * u, pant.bottom() - 2.6 * u, 36 * u, 1.25 * u), 0.62 * u, 0.62 * u)
        p.restore()

    def _brillo_cristal(self, p, pant):
        """El reflejo del cristal: una franja diagonal muy tenue (el móvil deja de parecer una foto pegada)."""
        g = QLinearGradient(pant.topLeft(), QPointF(pant.left() + pant.width() * 0.9, pant.top() + pant.height() * 0.55))
        g.setColorAt(0.0, QColorReal(255, 255, 255, 26))
        g.setColorAt(0.38, QColorReal(255, 255, 255, 8))
        g.setColorAt(0.40, QColorReal(255, 255, 255, 0))
        g.setColorAt(1.0, QColorReal(255, 255, 255, 0))
        p.fillRect(pant, QBrush(g))

    def _resplandor(self, p, caja):
        """v5.5.10 (pedido: «abajo del mockup un resplandor para decorar»): un halo de color bajo el móvil (y un aura muy suave detrás) que late
        despacio mientras se reproduce."""
        latido = 1.0
        if self._progreso is not None:
            latido = 1.0 + 0.22 * math.sin(time.perf_counter() * 3.2)
        base = QColorReal(VERDE)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        aura = QRadialGradient(caja.center(), caja.height() * 0.62)
        c0 = QColorReal(base)
        c0.setAlpha(int(34 * latido))
        aura.setColorAt(0.0, c0)
        aura.setColorAt(1.0, QColorReal(base.red(), base.green(), base.blue(), 0))
        p.setBrush(QBrush(aura))
        p.drawEllipse(caja.center(), caja.width() * 1.05, caja.height() * 0.62)
        centro = QPointF(caja.center().x(), caja.bottom() + 10.0)
        for ancho_f, alto_px, a0, a1 in ((1.05, 46.0, 150, 70), (0.55, 16.0, 235, 120)):      # halo ancho y núcleo brillante
            rx, ry = caja.width() * ancho_f, alto_px
            halo = QRadialGradient(QPointF(0, 0), rx)
            c1 = QColorReal(base)
            c1.setAlpha(min(255, int(a0 * latido)))
            c2 = QColorReal(ACCENT_CLARO)
            c2.setAlpha(min(255, int(a1 * latido)))
            halo.setColorAt(0.0, c1)
            halo.setColorAt(0.5, c2)
            halo.setColorAt(1.0, QColorReal(base.red(), base.green(), base.blue(), 0))
            p.save()
            p.translate(centro)
            p.scale(1.0, ry / rx)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(0, 0), rx, rx)
            p.restore()
        p.restore()
        # y una línea de luz fina justo bajo el móvil (el «suelo» brillante)
        p.save()
        linea = QLinearGradient(QPointF(caja.left(), 0), QPointF(caja.right(), 0))
        for x, a in ((0.0, 0), (0.5, int(200 * min(1.0, latido))), (1.0, 0)):
            cl = QColorReal(base)
            cl.setAlpha(a)
            linea.setColorAt(x, cl)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(linea))
        p.drawRoundedRect(QRectF(caja.left() + caja.width() * 0.08, caja.bottom() + 6.0, caja.width() * 0.84, 2.2), 1.1, 1.1)
        p.restore()

    def _pintar_movil(self, p):
        marco, _info, _fondo = self._recursos_movil()
        caja, pant, radio = self.geometria_movil()
        self._resplandor(p, caja)
        self._sombra_movil(p, caja)
        camino = QPainterPath()
        camino.addRoundedRect(pant, radio, radio)
        p.save()
        p.setClipPath(camino)
        p.fillRect(pant, QColorReal('#05080F'))
        img, real = self._imagen_en_pantalla()
        if not real and self._animador is not None:
            # v5.5.10: los captions del tema ANIMADOS (cada capa entra como su macro), sobre la foto
            try:
                self._animador['cu'].pintar(p, pant, self._t_animador())
            except Exception:
                pass
            img = None
        elif not real and self._cuadro is not None:
            # v5.5.10: el cuadro exacto del tema (foto + captions de render_sin_resolve), ya del tamaño de la pantalla
            p.drawImage(pant, self._cuadro)
            img = None
        if img is not None and not img.isNull():
            iw, ih = max(1, img.width()), max(1, img.height())
            # la foto «cubre» la pantalla; un render real se ve ENTERO (a lo ancho) para no cortar los captions
            esc = (pant.width() / iw) if real else max(pant.width() / iw, pant.height() / ih)
            w, h = iw * esc, ih * esc
            p.drawImage(QRectF(pant.center().x() - w / 2, pant.center().y() - h / 2, w, h), img)
        if not real and self._cuadro is None and self._animador is None and not getattr(self, 'esperando_tema', False):
            # velo suave abajo para que los captions se lean como en un reel
            # (v5.5.10: con un tema que tendrá su vista exacta, mientras se prepara se ve la foto limpia: antes salía un instante la maqueta
            #  aproximada, con otro estilo, y luego saltaba al tema real)
            velo = QLinearGradient(QPointF(0, pant.top() + pant.height() * 0.40), QPointF(0, pant.bottom()))
            velo.setColorAt(0.0, QColorReal(0, 0, 0, 0))
            velo.setColorAt(1.0, QColorReal(0, 0, 0, 120))
            p.fillRect(pant, QBrush(velo))
            self._pintar_en_pantalla(p, pant)
        # arriba, un degradado oscuro fino para que la barra de estado se lea sobre cualquier foto
        arriba = QLinearGradient(QPointF(0, pant.top()), QPointF(0, pant.top() + pant.height() * 0.09))
        arriba.setColorAt(0.0, QColorReal(0, 0, 0, 90))
        arriba.setColorAt(1.0, QColorReal(0, 0, 0, 0))
        p.fillRect(pant, QBrush(arriba))
        if self._progreso is not None:                                   # la barrita de avance del reel
            u = pant.width() / 100.0
            barra = QRectF(pant.left() + 5 * u, pant.bottom() - 6.2 * u, pant.width() - 10 * u, 0.7 * u)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColorReal(255, 255, 255, 70))
            p.drawRoundedRect(barra, 0.35 * u, 0.35 * u)
            p.setBrush(QColorReal(255, 255, 255, 230))
            p.drawRoundedRect(QRectF(barra.left(), barra.top(), barra.width() * self._progreso, barra.height()), 0.35 * u, 0.35 * u)
        self._barra_estado(p, pant)
        self._brillo_cristal(p, pant)
        p.restore()
        if marco is not None and not marco.isNull():
            p.drawImage(caja, marco)
        if real:
            p.setFont(fuente(10, peso='negrita'))
            p.setPen(QColor(ACCENT_CLARO))
            p.drawText(pant.adjusted(0, 0, -12, -12), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), tr('Render real · Resolve'))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._movil:
            self._pintar_movil(p)
            p.end()
            return
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(BORDER_COLOR), 1))
        p.setBrush(QColor('#0B1220'))
        p.drawRoundedRect(r, 12, 12)
        dentro = r.adjusted(8, 8, -8, -8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#05080F'))
        p.drawRoundedRect(dentro, 8, 8)
        if self._fondo is not None:
            # el fotograma «cubre» el marco (como object-fit: cover) y se
            # oscurece un poco para que el texto se lea como en el video
            p.save()
            camino = QPainterPath()
            camino.addRoundedRect(dentro, 8, 8)
            p.setClipPath(camino)
            iw, ih = self._fondo.width(), self._fondo.height()
            real = getattr(self, '_real', False)
            if real:
                esc = min(dentro.width() / max(1, iw), dentro.height() / max(1, ih))
            else:
                esc = max(dentro.width() / max(1, iw), dentro.height() / max(1, ih))
            w, h = iw * esc, ih * esc
            p.drawImage(QRectF(dentro.center().x() - w / 2, dentro.center().y() - h / 2, w, h), self._fondo)
            if not real:
                p.fillRect(dentro, QColorReal(0, 0, 0, 70))
            p.restore()
        if getattr(self, '_real', False) and self._fondo is not None:
            p.setFont(fuente(10, peso='negrita'))
            p.setPen(QColor(ACCENT_CLARO))
            p.drawText(dentro.adjusted(0, 0, -10, -6),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), tr('Render real · Resolve'))
            p.end()
            return
        self._pintar_contenido(p, dentro)
        p.end()

    def _pintar_contenido(self, p, dentro):
        """Las lineas (y el espacio «imagen») dentro de `dentro`, con el painter de quien llama: lo usan este marco y
        las tarjetas del carrusel de estilos (estilos_slider), que pintan los captions sobre una foto."""
        alto = dentro.height()
        medidas = []
        total = 0.0
        pesos = {'thin': QFont.Weight.Thin, 'light': QFont.Weight.Light, 'regular': QFont.Weight.Normal,
                 'medium': QFont.Weight.Medium, 'semibold': QFont.Weight.DemiBold,
                 'bold': QFont.Weight.Bold, 'extrabold': QFont.Weight.ExtraBold,
                 'black': QFont.Weight.Black, 'heavy': QFont.Weight.Black}
        def hacer_fuente(familia, peso_txt, px, italica=False):
            f = QFont(familia or familia_ui())
            f.setPixelSize(int(px))
            peso_txt = str(peso_txt or '').lower()
            for clave, w in pesos.items():
                if clave in peso_txt.replace(' ', ''):
                    f.setWeight(w)
            f.setItalic(bool(italica) or 'italic' in peso_txt)
            return f
        for texto, est in self._lineas:
            tam = max(9.0, float(est.get('tam', 0.12)) * alto)
            if est.get('mayus'):
                texto = texto.upper()
            f = hacer_fuente(est.get('familia'), est.get('peso'), tam, est.get('italica'))
            f2 = None
            partes = texto.split(' ', 1)
            seg = est.get('segundo')
            if seg and len(partes) == 2 and not est.get('contorno'):
                f2 = hacer_fuente(seg.get('familia'), seg.get('peso'), tam)
            def medir(f, f2):
                fm = QFontMetricsF(f)
                if f2 is None:
                    return fm.horizontalAdvance(texto)
                return fm.horizontalAdvance(partes[0] + ' ') + QFontMetricsF(f2).horizontalAdvance(partes[1])
            fm = QFontMetricsF(f)
            ancho = medir(f, f2)
            if ancho > dentro.width() - 24:
                px = max(8, int(tam * (dentro.width() - 24) / max(1.0, ancho)))
                f.setPixelSize(px)
                if f2 is not None:
                    f2.setPixelSize(px)
                fm = QFontMetricsF(f)
            medidas.append((texto, est, f, fm, f2, partes))
            total += fm.height() * (0.86 if est.get('pegado') else 1.05)
        img = self._imagen
        lado_img = 0.0
        if img:
            zoom = max(0.5, min(1.6, float(img.get('zoom') or 1.0)))
            lado_img = max(16.0, min(alto * 0.20 * zoom, dentro.width() * 0.28))
        extra = (lado_img + 6.0) if img else 0.0
        y = dentro.top() + (alto - total - extra) / 2
        if img and img.get('donde') == 'arriba':
            self._dibujar_imagen(p, dentro, y, lado_img, img)
            y += lado_img + 6.0
        for k_linea, (texto, est, f, fm, f2, partes) in enumerate(medidas):
            h = fm.height() * (0.86 if est.get('pegado') else 1.05)
            caja = QRectF(dentro.left() + 12, y, dentro.width() - 24, h)
            contorno = est.get('contorno')
            animada = self._t_anim is not None
            if animada:
                fe = self._rebote((self._t_anim - 0.11 * k_linea) / 0.36)
                p.save()
                p.setOpacity(max(0.0, min(1.0, (self._t_anim - 0.11 * k_linea) / 0.14)) * (1.0 - self._salida))
                p.translate(caja.center().x(), caja.center().y() + (1.0 - fe) * 12)
                esc = 0.78 + 0.22 * fe
                p.scale(esc, esc)
                p.translate(-caja.center().x(), -caja.center().y())
            if contorno:
                camino = QPainterPath()
                ancho = fm.horizontalAdvance(texto)
                x = caja.left() + (caja.width() - ancho) / 2
                camino.addText(QPointF(x, y + fm.ascent()), f, texto)
                # colores del SUBTITULO, no de la interfaz: sin tema (QColorReal)
                p.setPen(QPen(QColorReal(contorno), max(2.0, f.pixelSize() * 0.12),
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(camino)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColorReal(est.get('color') or '#FFFFFF'))
                p.drawPath(camino)
            else:
                p.setPen(QColorReal(est.get('color') or '#FFFFFF'))
                if f2 is None and est.get('degradado'):
                    # v5.5: la palabra PRINCIPAL con degradado (brillo arriba, color abajo), como el barrido de Luxe Shine
                    ancho_t = fm.horizontalAdvance(texto)
                    x_t = caja.left() + (caja.width() - ancho_t) / 2
                    camino_t = QPainterPath()
                    camino_t.addText(QPointF(x_t, y + fm.ascent()), f, texto)
                    base_c = QColorReal(est.get('color') or '#FFFFFF')
                    gr = QLinearGradient(QPointF(x_t, y), QPointF(x_t + ancho_t * 0.35, y + fm.height()))
                    gr.setColorAt(0.0, base_c.lighter(160))
                    gr.setColorAt(0.55, base_c)
                    gr.setColorAt(1.0, base_c.darker(125))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(gr))
                    p.drawPath(camino_t)
                elif f2 is None:
                    p.setFont(f)
                    p.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), texto)
                else:
                    # dos palabras con DOS pesos (la 1.ª ligera, la 2.ª bold...): como el pack las compone en Resolve
                    w1 = fm.horizontalAdvance(partes[0] + ' ')
                    w2 = QFontMetricsF(f2).horizontalAdvance(partes[1])
                    x0 = caja.left() + (caja.width() - w1 - w2) / 2
                    base = y + fm.ascent()
                    p.setFont(f)
                    p.drawText(QPointF(x0, base), partes[0])
                    p.setFont(f2)
                    p.drawText(QPointF(x0 + w1, base), partes[1])
            if animada:
                p.restore()
            y += h
        if img and img.get('donde') != 'arriba':
            if self._t_anim is not None:
                fe = self._rebote((self._t_anim - 0.45) / 0.4)
                p.save()
                p.setOpacity(max(0.0, min(1.0, (self._t_anim - 0.45) / 0.15)) * (1.0 - self._salida))
                cx, cy = dentro.center().x(), y + 6.0 + lado_img / 2
                p.translate(cx, cy)
                p.scale(0.4 + 0.6 * fe, 0.4 + 0.6 * fe)
                p.translate(-cx, -cy)
                self._dibujar_imagen(p, dentro, y + 6.0, lado_img, img)
                p.restore()
            else:
                self._dibujar_imagen(p, dentro, y + 6.0, lado_img, img)
        if self._aprox:
            p.setFont(fuente(10, peso='medio'))
            p.setPen(QColor('#4F607A'))
            p.drawText(dentro.adjusted(0, 0, -10, -6),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), tr('aprox.'))
        if self._pie:
            p.setFont(fuente(10, peso='medio'))
            p.setPen(QColor('#4F607A'))
            p.drawText(dentro.adjusted(10, 0, 0, -6),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom), self._pie)


def dibujar_icono_nav(p, clave, rect, color):
    """Los iconos del menu lateral, dibujados a mano (trazo de 1,6 px)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    def P(a, b):
        return QPointF(x + a * w, y + b * h)
    if clave == 'inicio':
        p.drawPolyline([P(0.2, 0.5), P(0.5, 0.22), P(0.8, 0.5)])
        p.drawPolyline([P(0.3, 0.42), P(0.3, 0.8), P(0.7, 0.8), P(0.7, 0.42)])
    elif clave == 'nuevo':
        p.drawRoundedRect(QRectF(x + 0.2 * w, y + 0.2 * h, 0.6 * w, 0.6 * h), 3, 3)
        p.drawLine(P(0.5, 0.36), P(0.5, 0.64))
        p.drawLine(P(0.36, 0.5), P(0.64, 0.5))
    elif clave == 'editor':
        for k, largo in enumerate((0.6, 0.45, 0.55)):
            yy = 0.32 + k * 0.18
            p.drawLine(P(0.2, yy), P(0.2 + largo, yy))
    elif clave == 'estilos':
        p.drawRoundedRect(QRectF(x + 0.2 * w, y + 0.22 * h, 0.6 * w, 0.56 * h), 3, 3)
        p.drawLine(P(0.32, 0.4), P(0.68, 0.4))
        p.drawLine(P(0.38, 0.55), P(0.62, 0.55))
    elif clave == 'sfx':
        for k, alto in enumerate((0.22, 0.46, 0.3, 0.56, 0.26)):
            xx = 0.22 + k * 0.14
            p.drawLine(P(xx, 0.5 - alto / 2), P(xx, 0.5 + alto / 2))
    p.restore()


class BotonNav(QAbstractButton):
    """Una entrada del menu lateral: icono en su cuadrito, texto y la barra
    azul a la izquierda cuando es la pantalla activa. Plegado (ventana
    angosta) queda solo el icono."""
    def __init__(self, texto, clave, padre=None):
        super().__init__(padre)
        self.setText(str(texto))
        self._clave = clave
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setFont(fuente(15, peso='medio'))
        self.plegado = False
        self._hover = False
        self._h = 0.0                    # hover suave 0..1
        self._pop = 0.0                  # pulso del icono al activarse 0..1
        self._barra = 0.0                # barra azul de la izquierda 0..1
        self._a_h = QVariantAnimation(self)
        self._a_h.setDuration(170)
        self._a_h.valueChanged.connect(self._paso_h)
        self._a_pop = QVariantAnimation(self)
        self._a_pop.setDuration(560)
        self._a_pop.setStartValue(0.0)
        self._a_pop.setEndValue(1.0)
        self._a_pop.valueChanged.connect(self._paso_pop)
        self._a_barra = QVariantAnimation(self)
        self._a_barra.setDuration(260)
        self._a_barra.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_barra.valueChanged.connect(self._paso_barra)
        self.toggled.connect(self._al_marcar)
        self.setToolTip(str(texto))

    def _paso_h(self, v):
        self._h = float(v)
        self.update()

    def _paso_pop(self, v):
        self._pop = float(v)
        self.update()

    def _paso_barra(self, v):
        self._barra = float(v)
        self.update()

    def _al_marcar(self, marcado):
        if _brillo.quieto():
            self._barra = 1.0 if marcado else 0.0
            self.update()
            return
        self._a_barra.stop()
        self._a_barra.setStartValue(self._barra)
        self._a_barra.setEndValue(1.0 if marcado else 0.0)
        self._a_barra.start()
        if marcado:
            self._a_pop.stop()
            self._a_pop.start()

    def _ir_h(self, meta):
        self._a_h.stop()
        self._a_h.setStartValue(self._h)
        self._a_h.setEndValue(float(meta))
        self._a_h.start()

    def enterEvent(self, e):
        self._hover = True
        self._ir_h(1.0)
        _brillo.entrar(self)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._ir_h(0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            _brillo.presionar(self, e)
        super().mousePressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        _brillo.ajustar(self)

    def paintEvent(self, _e):
        import math as _m
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        activo = self.isChecked()
        h = self._h
        if activo:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#13213D'))
            p.drawRoundedRect(r, 10, 10)
        elif h > 0.01:
            fondo = QColor('#0F1A2E')
            fondo.setAlpha(int(255 * h))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fondo)
            p.drawRoundedRect(r, 10, 10)
        if self._barra > 0.01:
            largo = (r.height() - 16) * self._barra
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(QRectF(0, r.center().y() - largo / 2, 3.5, largo), 1.75, 1.75)
        lado = 22
        ix = 18 + 2.0 * h if not self.plegado else (self.width() - lado) / 2
        cuadro = QRectF(ix, r.center().y() - lado / 2, lado, lado)
        esc = 1.0 + 0.10 * h + 0.22 * _m.sin(self._pop * _m.pi) * (1.0 - self._pop) if self._pop < 1.0 else 1.0 + 0.10 * h
        p.save()
        p.translate(cuadro.center())
        p.scale(esc, esc)
        p.translate(-cuadro.center())
        p.setPen(Qt.PenStyle.NoPen)
        base = QColor(ACCENT if activo else '#1A2640')
        if not activo and h > 0.01:
            base = mezclar(ACCENT, '#1A2640', 0.35 * h)
        p.setBrush(base)
        p.drawRoundedRect(cuadro, 6, 6)
        if activo and self._pop < 1.0:                 # halo que sale del icono al activarse
            halo = QColor(ACCENT_CLARO)
            halo.setAlpha(int(110 * (1.0 - self._pop)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(halo, 2.0))
            gr = 3.0 + 9.0 * self._pop
            p.drawRoundedRect(cuadro.adjusted(-gr, -gr, gr, gr), 6 + gr, 6 + gr)
        blanco = '#FFFFFF' if activo else ('#C9D6EC' if h > 0.5 else '#7F8DA8')
        dibujar_icono_nav(p, self._clave, cuadro.adjusted(2, 2, -2, -2), blanco)
        p.restore()
        if not self.plegado:
            p.setFont(self.font())
            p.setPen(QColor('#FFFFFF' if activo else ('#E0EBFB' if h > 0.5 else '#B4C0D6')))
            p.drawText(QRectF(ix + lado + 14, r.top(), self.width() - ix - lado - 18, r.height()),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()


class FlujoCapa(QLayout):
    """Un layout que pone los widgets en fila y salta de linea cuando no
    caben (los chips de idiomas, de tipografias y de combinaciones)."""
    def __init__(self, padre=None, espacio_h=8, espacio_v=8):
        super().__init__(padre)
        self._items = []
        self._eh = espacio_h
        self._ev = espacio_v
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, ancho):
        return self._colocar(QRect(0, 0, ancho, 0), probar=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._colocar(rect, probar=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        tam = QSize()
        for it in self._items:
            tam = tam.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return tam + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _colocar(self, rect, probar):
        m = self.contentsMargins()
        x0 = rect.x() + m.left()
        x, y = x0, rect.y() + m.top()
        derecha = rect.right() - m.right()
        alto_fila = 0
        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():
                continue
            tam = it.sizeHint()
            if x > x0 and x + tam.width() > derecha + 1:
                x = x0
                y += alto_fila + self._ev
                alto_fila = 0
            if not probar:
                it.setGeometry(QRect(QPoint(x, y), tam))
            x += tam.width() + self._eh
            alto_fila = max(alto_fila, tam.height())
        return y + alto_fila - rect.y() + m.bottom()


class Pila(QWidget):
    """Un QStackedWidget. Cambia de pantalla al instante (v5.4: antes llevaba un fundido de 170 ms)."""
    def __init__(self, padre=None):
        super().__init__(padre)
        from PySide6.QtWidgets import QStackedLayout
        self._capa = QStackedLayout(self)
        self._anim = None

    def agregar(self, w):
        self._capa.addWidget(w)
        return self._capa.count() - 1

    def actual(self):
        return self._capa.currentWidget()

    def mostrar(self, w, animar=True):
        if self._capa.currentWidget() is w:
            return
        # Sin QGraphicsOpacityEffect sobre la pagina: cada cuadro del fundido re-rasterizaba el arbol entero (cientos de
        # widgets en el Editor) y la entrada escalonada de las tarjetas (mograf_ui) ya anima el cambio de pantalla.
        self._capa.setCurrentWidget(w)


# ---------------------------------------------------------------------------
# v5.2: iconos de linea modernos (QtAwesome · Phosphor). Sustituyen a los
# botones que dependian de emojis de color (🔍 ☆ ＋): mismos trazos, mismo color
# del tema, nitidos a cualquier escala. Sin QtAwesome devuelve None y el boton
# conserva su texto de siempre.
_QTA = {'mod': False}


def icono_linea(nombre, color=None, color_activo=None):
    if _QTA['mod'] is False:
        try:
            os.environ.setdefault('QT_API', 'pyside6')
            import qtawesome
            import qtawesome.iconic_font as _icf
            # QtAwesome en Windows COPIA sus fuentes a la carpeta de fuentes del
            # usuario y las apunta en el registro (HKCU\...\Fonts) cada vez que
            # arranca. No hace falta (las carga desde memoria igual) y ensucia el
            # sistema: se cargan solo en la aplicacion, desde su propia carpeta.
            _icf.IconicFont._get_fonts_directory = lambda self: os.path.join(
                os.path.dirname(os.path.realpath(_icf.__file__)), 'fonts')
            # v5.39: el programa solo usa Phosphor («ph.»): cargar (y comprobar con MD5) las ~10 familias costaba ~0,1 s al arrancar
            _QTA['todas'] = qtawesome._BUNDLED_FONTS
            qtawesome._BUNDLED_FONTS = tuple(f for f in _QTA['todas'] if f[0] == 'ph') or _QTA['todas']
            _QTA['mod'] = qtawesome
        except Exception:
            _QTA['mod'] = None
    qta = _QTA['mod']
    if qta is None:
        return None
    try:
        c = tc(color or '#C9D6EC')
        if not str(nombre).startswith('ph.') and qta._BUNDLED_FONTS != _QTA.get('todas', qta._BUNDLED_FONTS):
            qta._BUNDLED_FONTS = _QTA['todas']                   # otra familia: se cargan todas (una vez)
            qta._resource['iconic'] = None
        if color_activo:
            return qta.icon(nombre, color=c, color_active=tc(color_activo))
        return qta.icon(nombre, color=c)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ventanas
_ICONO = {'icono': None}


def poner_icono_app(ruta):
    try:
        icono = QIcon(str(ruta))
        if not icono.isNull():
            _ICONO['icono'] = icono
            QApplication.setWindowIcon(icono)
    except Exception:
        pass


class Dialogo(QDialog):
    """La base de las ventanas secundarias (el CTkToplevel de la v4)."""
    def __init__(self, padre=None, titulo='', ancho=None, alto=None, redimensionable=True,
                 minimo=None, maximizable=False):
        super().__init__(padre)
        self.setWindowTitle(str(titulo))
        flags = (Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
                 | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowSystemMenuHint)
        if maximizable:
            flags |= Qt.WindowType.WindowMinMaxButtonsHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        if _ICONO['icono'] is not None:
            self.setWindowIcon(_ICONO['icono'])
        if ancho and alto:
            self.resize(int(ancho), int(alto))
        if minimo:
            self.setMinimumSize(int(minimo[0]), int(minimo[1]))
        if not redimensionable and ancho and alto:
            self.setFixedSize(int(ancho), int(alto))
        self._oscura = False
        self._colocada = False
        self._fundido = None

    def colocar(self, x, y, ancho=None, alto=None):
        if ancho and alto:
            self.resize(int(ancho), int(alto))
        self.move(int(x), int(y))
        self._colocada = True

    def showEvent(self, e):
        if not self._oscura:
            self._oscura = True
            barra_oscura(self)
            if not self._colocada and self.parentWidget() is not None:
                self._centrar_en(self.parentWidget().window())
            self.setWindowOpacity(0.0)
            self._fundido = QVariantAnimation(self)
            self._fundido.setDuration(140)
            self._fundido.setStartValue(0.0)
            self._fundido.setEndValue(1.0)
            self._fundido.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))
            self._fundido.start()
        super().showEvent(e)

    def _centrar_en(self, ventana):
        try:
            if ventana is None or not ventana.isVisible():
                return
            g = ventana.frameGeometry()
            yo = self.frameGeometry()
            x = g.x() + (g.width() - yo.width()) // 2
            y = g.y() + max(20, (g.height() - yo.height()) // 3)
            pantalla = QGuiApplication.screenAt(g.center()) or QGuiApplication.primaryScreen()
            area = pantalla.availableGeometry()
            x = max(area.left(), min(x, area.right() - yo.width()))
            y = max(area.top(), min(y, area.bottom() - yo.height()))
            self.move(x, y)
        except Exception:
            pass

    def existe(self):
        return vivo(self)

    def cerrar(self):
        if vivo(self):
            self.close()

    def traer(self):
        """El lift() + focus_force() de Tk."""
        if not vivo(self):
            return
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()


class _Icono(QWidget):
    """El circulo con el signo de los mensajes."""
    def __init__(self, tipo, padre=None):
        super().__init__(padre)
        self._tipo = tipo
        self.setFixedSize(40, 40)

    def paintEvent(self, _e):
        color, signo = {'info': (ACCENT_CLARO, 'i'), 'aviso': (AMBAR, '!'), 'error': (ROJO, '✕'),
                        'pregunta': (CIAN, '?')}.get(self._tipo, (ACCENT, 'i'))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(color)
        fondo = QColor(c)
        fondo.setAlpha(46)
        p.setPen(QPen(c, 2))
        p.setBrush(fondo)
        p.drawEllipse(QRectF(2, 2, 36, 36))
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(19 if signo != '✕' else 16, True))
        p.drawText(QRectF(2, 1, 36, 36), int(Qt.AlignmentFlag.AlignCenter), signo)
        p.end()


class _Mensaje(Dialogo):
    def __init__(self, padre, tipo, titulo, texto, botones):
        super().__init__(padre, titulo)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setModal(True)
        self.valor = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(24, 22, 24, 20)
        capa.setSpacing(18)
        arriba, ca = caja_h(espacio=16)
        ca.addWidget(_Icono(tipo), 0, Qt.AlignmentFlag.AlignTop)
        texto = str(texto or '')
        largo = texto.count('\n') > 26 or len(texto) > 1800
        if largo:
            caja = QPlainTextEdit()
            caja.setReadOnly(True)
            caja.setPlainText(texto)
            caja.setFont(fuente(13))
            caja.setMinimumSize(580, 380)
            ca.addWidget(caja, 1)
        else:
            lbl = Etiqueta(texto, tam=14, color='#DCE6F5', envolver=True, seleccionable=True)
            lbl.setMinimumWidth(min(540, max(320, QFontMetricsF(lbl.font()).horizontalAdvance(texto) + 10)))
            lbl.setMaximumWidth(580)
            ca.addWidget(lbl, 1)
        capa.addWidget(arriba, 1)
        fila, cf = caja_h(espacio=10)
        cf.addStretch(1)
        self._por_defecto = None
        for etiqueta, valor, estilo in botones:
            b = Boton(etiqueta, tipo=estilo, alto=40, ancho=104)
            b.poner_comando(lambda v=valor: self._elegir(v))
            cf.addWidget(b)
            if estilo == 'primario':
                self._por_defecto = valor
                b.setFocus()
        self._cancelar = botones[-1][1] if len(botones) > 1 else (botones[0][1] if botones else None)
        if self._por_defecto is None and botones:
            self._por_defecto = botones[0][1]
        capa.addWidget(fila)
        self.adjustSize()

    def _elegir(self, valor):
        self.valor = valor
        self.accept()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._elegir(self._por_defecto)
            return
        if e.key() == Qt.Key.Key_Escape:
            self._elegir(self._cancelar)
            return
        super().keyPressEvent(e)

    def reject(self):
        if self.valor is None:
            self.valor = self._cancelar
        super().reject()


def _padre(parent):
    if parent is not None and vivo(parent):
        return parent
    return QApplication.activeWindow()


def mostrar_mensaje(tipo, titulo, texto, parent=None, botones=None):
    crear_app()
    try:
        from i18n import tr_libre            # los mensajes llegan armados desde cualquier modulo (o desde un script de Resolve): se traducen aqui
        titulo, texto = tr_libre(titulo), tr_libre(texto)
    except Exception:
        pass
    try:
        if tipo in ('error', 'aviso'):
            import registro
            primera = next((l.strip() for l in str(texto or '').splitlines() if l.strip()), '')
            registro.anotar('error' if tipo == 'error' else 'aviso', f'{titulo}: {primera}'[:220], 'mensaje', detalle=str(texto or ''))
    except Exception:
        pass
    if botones is None:
        botones = [(tr('Aceptar'), True, 'primario')]
    dlg = _Mensaje(_padre(parent), tipo, titulo, texto, botones)
    dlg.exec()
    valor = dlg.valor
    dlg.deleteLater()
    return valor


class _MessageBox:
    """Las firmas de tkinter.messagebox, con la ventana de la casa."""
    @staticmethod
    def showinfo(title='', message='', parent=None, **_):
        mostrar_mensaje('info', title, message, parent)
        return 'ok'

    @staticmethod
    def showwarning(title='', message='', parent=None, **_):
        mostrar_mensaje('aviso', title, message, parent)
        return 'ok'

    @staticmethod
    def showerror(title='', message='', parent=None, **_):
        mostrar_mensaje('error', title, message, parent)
        return 'ok'

    @staticmethod
    def askyesno(title='', message='', parent=None, **_):
        return bool(mostrar_mensaje('pregunta', title, message, parent,
                                    [(tr('Sí'), True, 'primario'), (tr('No'), False, 'neutro')]))

    @staticmethod
    def askokcancel(title='', message='', parent=None, **_):
        return bool(mostrar_mensaje('pregunta', title, message, parent,
                                    [(tr('Aceptar'), True, 'primario'), (tr('Cancelar'), False, 'neutro')]))


messagebox = _MessageBox()


def error_con_acciones(titulo, texto, parent=None, reintentar=None, abrir_resolve=None, tipo='error'):
    """v5.5: un error con botones que SIRVEN: «Reintentar», «Abrir Resolve» (si el texto habla de Resolve/MCP) y «Copiar detalle»."""
    botones = []
    habla_de_resolve = any(p in str(texto or '').lower() for p in ('resolve', 'mcp', 'timeline'))
    if reintentar is not None:
        botones.append((tr('Reintentar'), 'reintentar', 'primario'))
    if abrir_resolve is not None and habla_de_resolve:
        botones.append((tr('Abrir Resolve'), 'resolve', 'primario' if reintentar is None else 'neutro'))
    botones.append((tr('Copiar detalle'), 'copiar', 'neutro'))
    botones.append((tr('Cerrar'), True, 'neutro'))
    valor = mostrar_mensaje(tipo, titulo, texto, parent, botones)
    try:
        if valor == 'copiar':
            QApplication.clipboard().setText(str(titulo) + chr(10) + chr(10) + str(texto))
        elif valor == 'reintentar' and reintentar is not None:
            reintentar()
        elif valor == 'resolve' and abrir_resolve is not None:
            abrir_resolve()
    except Exception:
        pass
    return valor


def _filtro_qt(filetypes):
    return ';;'.join(f'{nombre} ({patron})' for nombre, patron in (filetypes or []))


class _FileDialog:
    """Las firmas de tkinter.filedialog."""
    @staticmethod
    def askopenfilename(parent=None, title='', filetypes=None, initialdir=None, **_):
        ruta, _f = QFileDialog.getOpenFileName(_padre(parent), str(title), str(initialdir or ''),
                                               _filtro_qt(filetypes))
        return ruta or ''

    @staticmethod
    def askopenfilenames(parent=None, title='', filetypes=None, initialdir=None, **_):
        rutas, _f = QFileDialog.getOpenFileNames(_padre(parent), str(title), str(initialdir or ''),
                                                 _filtro_qt(filetypes))
        return tuple(rutas or ())

    @staticmethod
    def askdirectory(parent=None, title='', initialdir=None, mustexist=True, **_):
        ruta = QFileDialog.getExistingDirectory(_padre(parent), str(title), str(initialdir or ''))
        return ruta or ''

    @staticmethod
    def asksaveasfilename(parent=None, title='', filetypes=None, initialdir=None,
                          initialfile='', **_):
        inicio = str(Path(initialdir or '') / initialfile) if initialfile else str(initialdir or '')
        ruta, _f = QFileDialog.getSaveFileName(_padre(parent), str(title), inicio, _filtro_qt(filetypes))
        return ruta or ''


filedialog = _FileDialog()


class _PedirTexto(Dialogo):
    def __init__(self, padre, titulo, mensaje, inicial):
        super().__init__(padre, titulo)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setModal(True)
        self.valor = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(24, 22, 24, 20)
        capa.setSpacing(14)
        lbl = Etiqueta(mensaje, tam=14, color='#DCE6F5', envolver=True)
        lbl.setMinimumWidth(400)
        capa.addWidget(lbl)
        self.entrada = Entrada(alto=40)
        self.entrada.setText(str(inicial or ''))
        self.entrada.selectAll()
        self.entrada.returnPressed.connect(self._aceptar)
        capa.addWidget(self.entrada)
        fila, cf = caja_h(espacio=10)
        cf.addStretch(1)
        cf.addWidget(Boton(tr('Cancelar'), self.reject, tipo='neutro', ancho=104))
        cf.addWidget(Boton(tr('Aceptar'), self._aceptar, tipo='primario', ancho=104))
        capa.addWidget(fila)
        self.entrada.setFocus()

    def _aceptar(self):
        self.valor = self.entrada.text()
        self.accept()


class _SimpleDialog:
    @staticmethod
    def askstring(title='', prompt='', initialvalue='', parent=None, **_):
        crear_app()
        dlg = _PedirTexto(_padre(parent), title, prompt, initialvalue)
        dlg.exec()
        valor = dlg.valor
        dlg.deleteLater()
        return valor


simpledialog = _SimpleDialog()


def elegir_color(padre=None, inicial='#FFFFFF', titulo=''):
    """El colorchooser.askcolor: ((r, g, b), '#rrggbb') o (None, None)."""
    c = QColorDialog.getColor(QColor(inicial or '#FFFFFF'), _padre(padre), str(titulo or ''))
    if not c.isValid():
        return (None, None)
    return ((c.red(), c.green(), c.blue()), c.name())


# ---------------------------------------------------------------------------
# Dibujos
def pixmap_de_archivo(ruta, lado, dpr=None):
    """Un PNG a 'lado' px logicos, nitido en pantallas al 150/200 %."""
    try:
        if dpr is None:
            app = QGuiApplication.instance()
            dpr = app.devicePixelRatio() if app else 1.0
        img = QImage(str(ruta))
        if img.isNull():
            return None
        fis = max(1, int(round(lado * dpr)))
        img = img.scaled(fis, fis, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        return pm
    except Exception:
        return None


def icono_dibujado(dibujar, lado=18):
    """Un QIcon pintado por codigo (estrellas, carpetas, ondas)."""
    app = QGuiApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    escala = max(2.0, dpr)
    img = QImage(int(lado * escala), int(lado * escala), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(escala, escala)
    dibujar(p, float(lado))
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(escala)
    return QIcon(pm)


def pixmap_redondeado(pixmap, radio):
    """El logo con las esquinas redondeadas (la marca del lateral)."""
    if pixmap is None or pixmap.isNull():
        return pixmap
    dpr = pixmap.devicePixelRatio()
    salida = QPixmap(pixmap.size())
    salida.setDevicePixelRatio(dpr)
    salida.fill(Qt.GlobalColor.transparent)
    p = QPainter(salida)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    camino = QPainterPath()
    w = pixmap.width() / dpr
    h = pixmap.height() / dpr
    camino.addRoundedRect(QRectF(0, 0, w, h), radio, radio)
    p.setClipPath(camino)
    p.drawPixmap(0, 0, pixmap)
    p.end()
    return salida


# ---------------------------------------------------------------------------
# v5.1: el tema guardado (Ajustes > Interfaz) se aplica AQUI, al cargar el
# modulo: quien haga «from qt_kit import ACCENT» ya recibe el color del tema.
def _aplicar_tema_guardado():
    global _TRADUCTOR
    try:
        import tema
        _TRADUCTOR = tema.traductor()
    except Exception:
        _TRADUCTOR = None
    if _TRADUCTOR is None:
        return
    g = globals()
    for nombre in ('ACCENT', 'ACCENT_HOVER', 'ACCENT_CLARO', 'CIAN', 'BG_COLOR', 'LATERAL', 'CARD_COLOR',
                   'CARD_2', 'BORDER_COLOR', 'TEXT_COLOR', 'TEXT_MUTED'):
        g[nombre] = _TRADUCTOR(g[nombre])


_aplicar_tema_guardado()
