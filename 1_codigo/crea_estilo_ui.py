# CineCaptions · By Cinema Productions
# 1_codigo/crea_estilo_ui.py — «Crea tu estilo»: la lista de los Temas 1-6 sobre negro (se tocan en el orden que se quiera) con el cajón de letra y colores, y el popup de la estructura de nombres.
"""
Dos ventanas:

  * CreaEstiloDialogo : v5.56 (maqueta A aprobada por el usuario). Fondo negro, una FILA por tema (Tema 1…6) con su caption de verdad sobre negro
    (vista_estilos.imagenes: la misma frase en los seis, dibujada con el render de GO sin Resolve). Se tocan los que se quieran y en el orden que se
    quiera (número amarillo 1, 2, 3…; tocar otra vez lo quita): se turnan por frases. El botón «Personalizar letra y colores» abre un CAJÓN a la
    derecha (resorte amortiguado, sin rebote) con la tipografía y los colores del texto principal y del de arriba y abajo; al cambiarlos las filas se
    vuelven a dibujar en UN hilo. «Crear mi pack» llama a al_crear(nombre, temas, terminado, ajustes): temas = ['t3', 't1', …] en el orden de toque,
    ajustes = {'fuente_principal': 'Familia|Estilo' | '', 'fuente_secundaria', 'color_principal': '#RRGGBB' | '', 'color_secundario'} (vacío = lo del
    tema). terminado(ok) cierra la ventana si salió bien. Lo último del cajón se recuerda en ~/DaVinciSubtitles/crea_tu_estilo.json (archivos_seguros;
    NO en las prefs globales de fuente).
  * AyudaEstilo       : el popup del «!»: por qué los clips se llaman principal / arriba / abajo / simple, qué son principal 2 y principal 3,
    qué pasa si falta una pieza y cómo se exporta. Con dibujos, porque «sin esa estructura el estilo no funciona».
"""
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor as QColorReal
from PySide6.QtGui import QConicalGradient, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

import fuente_usuario
import qt_kit as ui
from qt_kit import Boton, Desplazable, Dialogo, Enlace, Entrada, Etiqueta, FlujoCapa, caja_h, caja_v
from qt_kit import QColor
from i18n import tr

AMARILLO = '#FDE047'
VERDE = '#34D399'
ROJO = '#FB7185'
AMBAR = ui.AMBAR
TEXT_MUTED = ui.TEXT_MUTED

# los colores de la maqueta A
BORDE = '#1B2130'
BORDE_HOVER = '#2C4068'
ANILLO = '#2A3346'
PANEL = '#07090D'
CAMPO = '#0B0F17'
GRIS = '#8D9BB5'
ETIQUETA = '#8AA0C2'

TEMAS = (1, 2, 3, 4, 5, 6)
CLAVES = ('fuente_principal', 'fuente_secundaria', 'color_principal', 'color_secundario')
COLORES_PRINCIPAL = ('#FFFFFF', '#FDE047', '#A3E635', '#22D3EE', '#F472B6', '#EF4444', '#3B82F6', '#FB923C')
COLORES_SECUNDARIO = ('#FFFFFF', '#E5E7EB', '#9CA3AF', '#FDE047', '#22D3EE', '#F472B6')
LETRAS_SECUNDARIAS = ('Montserrat', 'Poppins')          # arriba y abajo: solo letras de texto corrido (como la maqueta aprobada)
RUTA_ESTADO = Path.home() / 'DaVinciSubtitles' / 'crea_tu_estilo.json'
ASPECTO_IMAGEN = 3.2                                    # las imágenes de las filas: ancho = 3,2 × alto (el caption más ancho cabe por alto)


def _hoja(css):
    return ui.traducir_hoja(css)


def _mezcla(a, b, p):
    return a + (b - a) * p


def _ajustes_limpios(datos):
    """Los cuatro ajustes del CONTRATO, validados por encima (lo raro = «lo del tema»)."""
    datos = datos if isinstance(datos, dict) else {}
    salida = {}
    for k in CLAVES:
        v = str(datos.get(k) or '').strip()
        if k.startswith('color'):
            v = v.upper() if (len(v) == 7 and v[0] == '#' and all(c in '0123456789ABCDEFabcdef' for c in v[1:])) else ''
        elif v and (len(v) > 160 or not v.split('|')[0].strip()):
            v = ''
        salida[k] = v
    return salida


# ====================================================================================== memoria de las imágenes y del cajón
_IMAGENES = {}                 # (ajustes, ancho, alto) -> {n: QImage}: volver a una letra o color ya visto (o reabrir la ventana) es al instante
_MAX_IMAGENES = 8


def _clave_imagenes(ajustes, ancho, alto):
    return (tuple(ajustes.get(k, '') for k in CLAVES), int(ancho), int(alto))


def _recordar_imagenes(clave, imagenes):
    _IMAGENES.pop(clave, None)
    _IMAGENES[clave] = imagenes
    while len(_IMAGENES) > _MAX_IMAGENES:
        _IMAGENES.pop(next(iter(_IMAGENES)))


def _a_qimage(im):
    """PIL.Image -> QImage propia (se hace en el hilo de trabajo; el QPixmap, en el de la interfaz)."""
    im = im.convert('RGB')
    return QImage(im.tobytes('raw', 'RGB'), im.width, im.height, im.width * 3, QImage.Format.Format_RGB888).copy()


def leer_estado():
    """Lo último del cajón: {'ajustes': {...}, 'propios': {'color_principal': '#…', 'color_secundario': '#…'}} (un JSON de pocos bytes)."""
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(RUTA_ESTADO, {}) or {}
    except Exception:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    propios = _ajustes_limpios(datos.get('propios'))
    return {'ajustes': _ajustes_limpios(datos.get('ajustes')),
            'propios': {k: propios[k] for k in ('color_principal', 'color_secundario')}}


_GUARDADO = {'cerrojo': threading.Lock(), 'ocupado': False, 'pendiente': None}


def guardar_estado(datos):
    """Escribe lo último del cajón en un hilo (archivos_seguros, atómico). Varios cambios seguidos: gana el último, sin dos hilos a la vez."""
    g = _GUARDADO
    with g['cerrojo']:
        g['pendiente'] = datos
        if g['ocupado']:
            return
        g['ocupado'] = True

    def trabajo():
        import archivos_seguros
        while True:
            with g['cerrojo']:
                actual, g['pendiente'] = g['pendiente'], None
                if actual is None:
                    g['ocupado'] = False
                    return
            try:
                archivos_seguros.escribir_json(RUTA_ESTADO, actual, indent=1)
            except Exception as e:
                try:
                    import registro
                    registro.aviso(tr('«Crea tu estilo» no pudo recordar la letra y los colores: {e}', e=e), 'crea_estilo_ui')
                except Exception:
                    pass
    ui.correr_en_hilo(None, trabajo, lambda _r, _e: None)


# ====================================================================================== piezas pintadas
def _degradado_tema(rect):
    """El círculo «del tema»: el degradado cónico de la maqueta (CSS conic-gradient from 210deg: lima, azul, rosa, amarillo)."""
    g = QConicalGradient(rect.center(), 240.0)
    for pos, c in ((0.0, '#C6F432'), (0.25, '#FDE047'), (0.5, '#F472B6'), (0.75, '#3B82F6'), (1.0, '#C6F432')):
        g.setColorAt(pos, QColorReal(c))
    return g


class _UnToque:
    """Un doble clic = dos toques, nunca tres. Por la ruta normal de Qt el segundo clic llega como dblclick EN LUGAR del press (press, release,
    dblclick, release) y QWidget.mouseDoubleClickEvent lo pasa a mousePressEvent: dos toques, bien. Si además llega su press (press, release,
    press, dblclick, release, el orden que puede mandar la plataforma), ese dblclick repetiría el toque: se descarta el dblclick que sigue a un
    press sin release entre medias."""
    _ultimo_raton = None

    def event(self, e):
        t = e.type()
        if t == QEvent.Type.MouseButtonDblClick:
            previo, self._ultimo_raton = self._ultimo_raton, t
            if previo == QEvent.Type.MouseButtonPress:
                e.accept()
                return True
        elif t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            self._ultimo_raton = t
        return super().event(e)


class _Lista(_UnToque, QWidget):
    """Las seis filas en UN widget pintado a mano (sin una capa por fila: el cajón la redimensiona en cada cuadro y solo cuesta copiar seis imágenes).
    Las medidas van de la lista sola (Lista_A: filas de 88, caption de 68, píldora «Añadir / Puesto») a la lista con el cajón (Panel_A: filas de 84,
    caption de 62, sin píldora) según el avance del cajón."""
    HALO = 4
    SEP = 8
    ALTO_MAX = 88

    def __init__(self, al_tocar):
        super().__init__()
        self._al_tocar = al_tocar
        self._orden = []
        self._pix = {}
        self._fondo = QColorReal('#000000')     # el fondo de la fila = el de sus imágenes (vista_estilos.fondo: gris si un color elegido es oscuro)
        self._p = 0.0
        self._hover = None
        self._rehaciendo = False
        self.setMouseTracking(True)
        self.setMinimumHeight(2 * self.HALO + 6 * self.ALTO_MAX + 5 * self.SEP)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._f_tema = ui.fuente(13, peso='negrita')
        self._f_num = ui.fuente(14, peso='extra')
        self._f_pild = ui.fuente(13, peso='negrita')
        self._textos = {n: tr('Tema {n}', n=n) for n in TEMAS}
        self._t_puesto, self._t_anadir = tr('Puesto'), tr('Añadir')
        fm = QFontMetricsF(self._f_pild)
        self._ancho_pild = 14 + 10 + 6 + max(fm.horizontalAdvance(self._t_puesto), fm.horizontalAdvance(self._t_anadir)) + 14

    def sizeHint(self):
        return QSize(600, self.minimumHeight())

    # -- estado
    def poner_orden(self, orden):
        self._orden = list(orden)
        self.update()

    def poner_imagenes(self, pix, fondo=None):
        self._pix = dict(pix)
        if fondo is not None:
            self._fondo = QColorReal(*[int(v) for v in fondo[:3]])
        self.update()

    def poner_rehaciendo(self, si):
        if bool(si) != self._rehaciendo:
            self._rehaciendo = bool(si)
            self.update()

    def poner_avance(self, p):
        p = max(0.0, min(1.0, float(p)))
        if abs(p - self._p) > 1e-4:
            self._p = p
            self.update()

    # -- medidas
    def _medidas(self):
        p = self._p
        return {'alto': _mezcla(88, 84, p), 'pad': _mezcla(18, 16, p), 'gap': _mezcla(16, 14, p), 'etq': _mezcla(64, 60, p),
                'caja': _mezcla(68, 62, p), 'pild': max(0.0, 1.0 - 2.0 * p)}

    def _fila(self, k, m):
        return QRectF(self.HALO, self.HALO + k * (m['alto'] + self.SEP), self.width() - 2 * self.HALO, m['alto'])

    def _tema_en(self, pos):
        m = self._medidas()
        for k, n in enumerate(TEMAS):
            if self._fila(k, m).contains(QPointF(pos)):
                return n
        return None

    # -- dibujo
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        m = self._medidas()
        for k, n in enumerate(TEMAS):
            self._pintar_fila(p, self._fila(k, m), n, m)
        p.end()

    def _pintar_fila(self, p, r, n, m):
        elegido = n in self._orden
        if elegido:                                                     # el halo verde al 10 % (box-shadow 0 0 0 4px)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColorReal(52, 211, 153, 26))
            p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 18, 18)
        p.setBrush(self._fondo)
        if elegido:
            p.setPen(QPen(QColor(VERDE), 2))
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 13, 13)
        else:
            p.setPen(QPen(QColor(BORDE_HOVER if self._hover == n else BORDE), 1))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 13.5, 13.5)
        cy = r.center().y()
        x = r.x() + m['pad']
        marca = QRectF(x, cy - 13, 26, 26)
        if elegido:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(AMARILLO))
            p.drawEllipse(marca)
            p.setFont(self._f_num)
            p.setPen(QColor('#101626'))
            p.drawText(marca, int(Qt.AlignmentFlag.AlignCenter), str(self._orden.index(n) + 1))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(ANILLO), 2))
            p.drawEllipse(marca.adjusted(1, 1, -1, -1))
        x += 26 + m['gap']
        p.setFont(self._f_tema)
        p.setPen(QColor(GRIS))
        p.drawText(QRectF(x, r.y(), m['etq'] + 30, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._textos[n])
        x += m['etq'] + m['gap']
        derecha = r.right() - m['pad'] - (self._ancho_pild + m['gap']) * (1.0 - self._p)
        if m['pild'] > 0.01:
            self._pintar_pildora(p, r, m, elegido)
        pm = self._pix.get(n)
        if pm is not None and not pm.isNull() and derecha - x > 8:
            dpr = pm.devicePixelRatio() or 1.0
            pw, ph = pm.width() / dpr, pm.height() / dpr
            f = min(m['caja'] / ph, (derecha - x) / pw)
            w, h = pw * f, ph * f
            p.setOpacity(0.45 if self._rehaciendo else 1.0)
            p.drawPixmap(QRectF(x + (derecha - x - w) / 2.0, cy - h / 2.0, w, h), pm, QRectF(0, 0, pm.width(), pm.height()))
            p.setOpacity(1.0)

    def _pintar_pildora(self, p, r, m, elegido):
        """«＋ Añadir» / «✓ Puesto» de la lista sola; se desvanece al abrir el cajón."""
        p.setOpacity(m['pild'])
        caja = QRectF(r.right() - m['pad'] - self._ancho_pild, r.center().y() - 16, self._ancho_pild, 32)
        color = QColor(VERDE if elegido else '#E8F1FF')
        if elegido:
            p.setPen(QPen(QColor(VERDE), 1))
            p.setBrush(QColorReal(52, 211, 153, 26))
        else:
            p.setPen(QPen(QColor(ANILLO), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), 15.5, 15.5)
        ix, iy = caja.x() + 14, caja.center().y()
        p.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if elegido:
            p.drawPolyline([QPointF(ix + 0.5, iy + 0.5), QPointF(ix + 3.8, iy + 3.6), QPointF(ix + 9.5, iy - 3.5)])
        else:
            p.drawLine(QPointF(ix + 5, iy - 4.5), QPointF(ix + 5, iy + 4.5))
            p.drawLine(QPointF(ix + 0.5, iy), QPointF(ix + 9.5, iy))
        p.setFont(self._f_pild)
        p.setPen(color)
        p.drawText(QRectF(ix + 16, caja.y(), caja.width() - 30, caja.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self._t_puesto if elegido else self._t_anadir)
        p.setOpacity(1.0)

    # -- ratón
    def mouseMoveEvent(self, e):
        n = self._tema_en(e.position())
        if n != self._hover:
            self._hover = n
            self.setCursor(Qt.CursorShape.PointingHandCursor if n else Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            n = self._tema_en(e.position())
            if n:
                self._al_tocar(n)
                e.accept()
                return
        super().mousePressEvent(e)


class _Interruptor(_UnToque, QWidget):
    """«Personalizar letra y colores ▾/▴»: la pastilla de la cabecera que abre y cierra el cajón (encendida = verde)."""
    def __init__(self, al_tocar):
        super().__init__()
        self._al_tocar = al_tocar
        self._on = False
        self._hover = False
        self._texto = tr('Personalizar letra y colores')
        self._f = ui.fuente(13, peso='negrita')
        self._f_aa = ui.fuente(10, peso='extra')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(int(10 + 22 + 8 + QFontMetricsF(self._f).horizontalAdvance(self._texto) + 6 + 7 + 14 + 1), 34)

    def poner(self, si):
        if bool(si) != self._on:
            self._on = bool(si)
            self.update()

    def encendido(self):
        return self._on

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._on:
            p.setPen(QPen(QColor(VERDE), 1))
            p.setBrush(QColorReal(52, 211, 153, 26))
            color = QColor(VERDE)
        else:
            p.setPen(QPen(QColor('#3A4A66' if self._hover else ANILLO), 1))
            p.setBrush(QColor(PANEL))
            color = QColor('#E8F1FF')
        p.drawRoundedRect(r, 16.5, 16.5)
        ico = QRectF(10, 6, 22, 22)
        g = QConicalGradient(ico.center(), 90.0)
        for pos, c in ((0.0, '#FDE047'), (0.2, '#A3E635'), (0.4, '#22D3EE'), (0.6, '#3B82F6'), (0.8, '#F472B6'), (1.0, '#FDE047')):
            g.setColorAt(pos, QColorReal(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(ico)
        p.setFont(self._f_aa)
        p.setPen(QColorReal('#000000'))
        p.drawText(ico, int(Qt.AlignmentFlag.AlignCenter), 'Aa')
        p.setFont(self._f)
        p.setPen(color)
        tw = QFontMetricsF(self._f).horizontalAdvance(self._texto)
        p.drawText(QRectF(40, 0, tw + 2, self.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._texto)
        x, cy = 40 + tw + 6, self.height() / 2.0
        flecha = QPainterPath()
        if self._on:                                   # ▴
            flecha.moveTo(x, cy + 2)
            flecha.lineTo(x + 7, cy + 2)
            flecha.lineTo(x + 3.5, cy - 2)
        else:                                          # ▾
            flecha.moveTo(x, cy - 2)
            flecha.lineTo(x + 7, cy - 2)
            flecha.lineTo(x + 3.5, cy + 2)
        flecha.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(flecha)
        p.end()

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
            self._al_tocar()
            e.accept()
            return
        super().mousePressEvent(e)


class _Ficha(_UnToque, QWidget):
    """Una ficha de letra del cajón (76×54): «Aa» con esa letra y su nombre debajo. Marcada = borde verde de 2 px."""
    def __init__(self, familia, estilo, etiqueta, al_tocar):
        super().__init__()
        self.valor = fuente_usuario.a_texto(familia, estilo)
        self._al_tocar = al_tocar
        self._etiqueta = etiqueta
        self._marcada = False
        self._hover = False
        if familia:
            f = QFont(familia)
            f.setStyleName(estilo)
            f.setPixelSize(20)
            self._f_aa = f
        else:
            self._f_aa = ui.fuente(20, peso='extra')
        self._f_nom = ui.fuente(10)
        self.setFixedSize(76, 54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def marcar(self, si):
        if bool(si) != self._marcada:
            self._marcada = bool(si)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setBrush(QColor(CAMPO))
        if self._marcada:
            p.setPen(QPen(QColor(VERDE), 2))
            p.drawRoundedRect(QRectF(1, 1, 74, 52), 9, 9)
        else:
            p.setPen(QPen(QColor(BORDE_HOVER if self._hover else BORDE), 1))
            p.drawRoundedRect(QRectF(0.5, 0.5, 75, 53), 9.5, 9.5)
        p.setFont(self._f_aa)
        p.setPen(QColorReal('#FFFFFF'))
        p.drawText(QRectF(0, 6, 76, 27), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom), 'Aa')
        p.setFont(self._f_nom)
        p.setPen(QColor(GRIS))
        p.drawText(QRectF(2, 34, 72, 14), int(Qt.AlignmentFlag.AlignCenter), self._etiqueta)
        p.end()

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
            self._al_tocar(self.valor)
            e.accept()
            return
        super().mousePressEvent(e)


class _Paleta(_UnToque, QWidget):
    """Una fila de círculos de 26 px: «del tema» (degradado), la paleta y «+» (color a elección; lleva el último elegido). La elegida, con el anillo
    verde a 2 px (box-shadow 0 0 0 2px negro, 0 0 0 4px verde)."""
    LADO = 26
    PASO = 34                                         # 26 + 8 de hueco

    def __init__(self, colores, al_elegir, al_mas):
        super().__init__()
        self._colores = tuple(colores)
        self._al_elegir = al_elegir
        self._al_mas = al_mas
        self.valor = ''
        self.propio = ''
        self._hover = None
        n = len(self._colores) + 2
        self.setFixedSize(n * self.PASO, self.LADO + 8)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, valor, propio):
        self.valor, self.propio = str(valor or ''), str(propio or '')
        self.update()

    def _indice_elegido(self):
        if not self.valor:
            return 0
        if self.valor in self._colores:
            return 1 + self._colores.index(self.valor)
        return len(self._colores) + 1

    def _circulo(self, i):
        return QRectF(4 + i * self.PASO, 4, self.LADO, self.LADO)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        borde = QPen(QColorReal(255, 255, 255, 46), 1)
        ultimo = len(self._colores) + 1
        for i in range(ultimo + 1):
            c = self._circulo(i)
            if i == 0:
                p.setPen(borde)
                p.setBrush(_degradado_tema(c))
                p.drawEllipse(c.adjusted(0.5, 0.5, -0.5, -0.5))
            elif i < ultimo:
                p.setPen(borde)
                p.setBrush(QColorReal(self._colores[i - 1]))
                p.drawEllipse(c.adjusted(0.5, 0.5, -0.5, -0.5))
            else:
                self._pintar_mas(p, c)
            if i == self._hover and i != self._indice_elegido():
                p.setPen(QPen(QColor(BORDE_HOVER), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(c.adjusted(-3, -3, 3, 3))
        anillo = self._circulo(self._indice_elegido()).adjusted(-3, -3, 3, 3)
        p.setPen(QPen(QColor(VERDE), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(anillo)
        p.end()

    def _pintar_mas(self, p, c):
        if self.propio:
            fondo = QColorReal(self.propio)
            p.setPen(QPen(QColorReal(255, 255, 255, 46), 1))
            p.setBrush(fondo)
            p.drawEllipse(c.adjusted(0.5, 0.5, -0.5, -0.5))
            claro = (0.299 * fondo.red() + 0.587 * fondo.green() + 0.114 * fondo.blue()) > 150
            trazo = QColorReal(0, 0, 0, 170) if claro else QColorReal(255, 255, 255, 220)
        else:
            p.setPen(QPen(QColor('#4D5A72'), 1, Qt.PenStyle.DashLine))
            p.setBrush(QColor(CAMPO))
            p.drawEllipse(c.adjusted(0.5, 0.5, -0.5, -0.5))
            trazo = QColor(GRIS)
        p.setPen(QPen(trazo, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = c.center().x(), c.center().y()
        p.drawLine(QPointF(cx - 4.5, cy), QPointF(cx + 4.5, cy))
        p.drawLine(QPointF(cx, cy - 4.5), QPointF(cx, cy + 4.5))

    def _en(self, pos):
        for i in range(len(self._colores) + 2):
            if self._circulo(i).adjusted(-3, -3, 3, 3).contains(QPointF(pos)):
                return i
        return None

    def mouseMoveEvent(self, e):
        i = self._en(e.position())
        if i != self._hover:
            self._hover = i
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(e)
        i = self._en(e.position())
        if i is None:
            return super().mousePressEvent(e)
        e.accept()
        if i == 0:
            self._al_elegir('')
        elif i <= len(self._colores):
            self._al_elegir(self._colores[i - 1])
        else:
            self._al_mas()


class _Resumen(QWidget):
    """«Tu estilo: (1) Tema 3 → (2) Tema 1 → … · letra y colores del tema»: los chips numerados en el orden de toque."""
    def __init__(self):
        super().__init__()
        self._orden = []
        self._sufijo = ''
        self._f = ui.fuente(13)
        self._f_chip = ui.fuente(12, peso='negrita')
        self._f_num = ui.fuente(11, peso='extra')
        self._t_estilo = tr('Tu estilo:')
        self._t_vacio = tr('ninguno todavía: toca los temas que quieras')
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, orden, sufijo):
        self._orden, self._sufijo = list(orden), str(sufijo)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        h = float(self.height())
        medio = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.setFont(self._f)
        p.setPen(QColor('#E0EBFB'))
        fm = QFontMetricsF(self._f)
        tw = fm.horizontalAdvance(self._t_estilo)
        p.drawText(QRectF(0, 0, tw + 2, h), medio, self._t_estilo)
        x = tw + 8
        if not self._orden:
            p.setPen(QColor('#7F8BA3'))
            p.drawText(QRectF(x, 0, max(0.0, self.width() - x), h), medio, fm.elidedText(self._t_vacio, Qt.TextElideMode.ElideRight, max(0.0, self.width() - x)))
            p.end()
            return
        fc = QFontMetricsF(self._f_chip)
        for k, n in enumerate(self._orden):
            if k:
                p.setFont(self._f)
                p.setPen(QColor('#4D5A72'))
                p.drawText(QRectF(x, 0, 16, h), medio, '→')
                x += fm.horizontalAdvance('→') + 8
            texto = tr('Tema {n}', n=n)
            ancho = 3 + 18 + 6 + fc.horizontalAdvance(texto) + 10
            chip = QRectF(x, 0, ancho, 24)
            p.setPen(QPen(QColor(BORDE), 1))
            p.setBrush(QColor('#0E131D'))
            p.drawRoundedRect(chip.adjusted(0.5, 0.5, -0.5, -0.5), 11.5, 11.5)
            num = QRectF(x + 3, 3, 18, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(AMARILLO))
            p.drawEllipse(num)
            p.setFont(self._f_num)
            p.setPen(QColor('#101626'))
            p.drawText(num, int(Qt.AlignmentFlag.AlignCenter), str(k + 1))
            p.setFont(self._f_chip)
            p.setPen(QColor('#E8F1FF'))
            p.drawText(QRectF(x + 27, 0, ancho - 27, h), medio, texto)
            x += ancho + 8
        if self._sufijo and x < self.width() - 20:
            p.setFont(self._f)
            p.setPen(QColor('#7F8BA3'))
            resto = self.width() - x
            p.drawText(QRectF(x, 0, resto, h), medio, fm.elidedText('· ' + self._sufijo, Qt.TextElideMode.ElideRight, resto))
        p.end()


class _Cajon(QWidget):
    """El hueco del cajón: su ANCHO se anima (0 → 14 de separación + 372 + 4) y el panel de dentro no cambia de tamaño (no se recoloca nada al
    animar): queda pegado a la izquierda del hueco, así que entra deslizándose desde la derecha."""
    ANCHO = 372
    IZQ = 10                      # 14 de hueco con la fila menos los 4 px del halo de la lista
    DER = 4

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        panel.setParent(self)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def ancho_total(self):
        return self.IZQ + self.ANCHO + self.DER

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.panel.setGeometry(self.IZQ, 4, self.ANCHO, max(0, self.height() - 8))


class CreaEstiloDialogo(Dialogo):
    """«Crea tu estilo» (v5.56, maqueta A): las seis filas Tema 1…6 sobre negro, el cajón de letra y colores y el pie con «Tu estilo», el nombre y
    «Crear mi pack». al_crear(nombre, temas, terminado, ajustes); el resto de argumentos (al_resolve, al_ayuda, al_resolve_uno) se aceptan solo por
    compatibilidad con la llamada de la app y no se usan."""
    K_RESORTE = 300.0
    C_RESORTE = 34.6              # 2·√k: amortiguado crítico (el ancho no rebota)

    def __init__(self, padre, al_crear, *_compat, **_compat_kw):
        super().__init__(padre, tr('Crea tu estilo'), 1040, 800, minimo=(960, 560))
        self.setObjectName('creaEstilo')
        self.setStyleSheet(_hoja('QDialog#creaEstilo { background-color: #000000; }'))
        self._al_crear = al_crear
        self._orden = []
        self._creando = False
        self._cerrado = False
        estado = leer_estado()
        self._ajustes = estado['ajustes']
        self._propios = estado['propios']
        self._trabajando = False
        self._pedido = None
        self._clave_actual = None
        self._resorte = ui.Resorte(0.0, self.K_RESORTE, self.C_RESORTE)
        self._abierto = False

        capa = QVBoxLayout(self)
        capa.setContentsMargins(16, 18, 16, 16)       # 20 de la maqueta menos los 4 px del halo de las filas (cabecera y pie llevan +4)
        capa.setSpacing(0)
        cab, cc = caja_h(espacio=12, margenes=(4, 0, 4, 0))
        cc.addWidget(Etiqueta(tr('Crea tu estilo'), 22, peso='extra', color='#FFFFFF'))
        cc.addStretch(1)
        self._interruptor = _Interruptor(self._alternar_cajon)
        cc.addWidget(self._interruptor)
        capa.addWidget(cab)
        capa.addSpacing(10)
        sub = Etiqueta(tr('Toca los captions que quieras, en el orden que quieras: se turnan por frases.'), 13, color='#A9B4C8', envolver=True)
        sub.setContentsMargins(4, 0, 4, 0)
        capa.addWidget(sub)
        capa.addSpacing(6)

        cuerpo, cb = caja_h(espacio=0)
        self._lista = _Lista(self._tocar)
        desp = QScrollArea()
        desp.setWidgetResizable(True)
        desp.setFrameShape(QFrame.Shape.NoFrame)
        desp.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desp.setWidget(self._lista)
        desp.viewport().setAutoFillBackground(False)
        self._lista.setAutoFillBackground(False)
        cb.addWidget(desp, 1)
        self._cajon = _Cajon(self._armar_panel())
        self._cajon.setFixedWidth(0)
        self._cajon.hide()
        cb.addWidget(self._cajon)
        capa.addWidget(cuerpo, 1)
        capa.addSpacing(6)
        capa.addWidget(self._armar_pie())

        self._solo_letras_instaladas()
        self._marcar_cajon()
        self._resumir()
        self._rehacer_imagenes()

    # ------------------------------------------------------------------ el cajón
    def _armar_panel(self):
        panel = QFrame()
        panel.setObjectName('cajonEstilo')
        panel.setStyleSheet(_hoja('QFrame#cajonEstilo { background-color: %s; border: 1px solid %s; border-radius: 16px; }' % (PANEL, BORDE)))
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(1, 1, 1, 1)
        desp = Desplazable(margenes=(15, 13, 15, 13), espacio=10, estirar_final=False)
        pv.addWidget(desp)
        hay = {f.lower() for f in QFontDatabase.families()}
        instaladas = [o for o in fuente_usuario.OPCIONES if o[0].lower() in hay]
        tema = ('', '', tr('Del tema'))
        self._fichas = {}
        desp.agregar(self._titulo(tr('Tipografía')))
        desp.agregar(self._bloque_letras('fuente_principal', tr('Texto principal'), [tema] + instaladas))
        desp.agregar(self._bloque_letras('fuente_secundaria', tr('Arriba y abajo'), [tema] + [o for o in instaladas if o[0] in LETRAS_SECUNDARIAS]))
        desp.agregar(self._titulo(tr('Colores')))
        self._paletas = {}
        for clave, etq, colores in (('color_principal', tr('Texto principal'), COLORES_PRINCIPAL),
                                    ('color_secundario', tr('Arriba y abajo'), COLORES_SECUNDARIO)):
            bloque, bv = caja_v(espacio=2)              # (la paleta lleva 4 px alrededor para el anillo: 2 + 4 = los 6 de la maqueta)
            bv.addWidget(Etiqueta(etq, 11.5, color=ETIQUETA))
            paleta = _Paleta(colores, lambda v, c=clave: self._poner_ajuste(c, v), lambda c=clave: self._color_propio(c))
            self._paletas[clave] = paleta
            bv.addWidget(paleta)
            desp.agregar(bloque)
        desp.agregar(Etiqueta(tr('El círculo de colores = los del tema. Se aplica a todos los captions que elijas.'), 11, color='#6B7891', envolver=True))
        desp.capa.addStretch(1)
        self._volver = Enlace(tr('Volver a la letra y los colores del tema'), self._volver_al_tema, tam=12, color=ETIQUETA)
        desp.capa.addWidget(self._volver, 0, Qt.AlignmentFlag.AlignLeft)
        return panel

    @staticmethod
    def _titulo(texto):
        return Etiqueta(texto, 13, peso='extra', color='#FFFFFF')

    def _bloque_letras(self, clave, etiqueta, opciones):
        bloque, bv = caja_v(espacio=6)
        bv.addWidget(Etiqueta(etiqueta, 11.5, color=ETIQUETA))
        zona = QWidget()
        flujo = FlujoCapa(zona, espacio_h=6, espacio_v=6)
        self._fichas[clave] = []
        for familia, estilo, nombre in opciones:
            ficha = _Ficha(familia, estilo, nombre, lambda v, c=clave: self._poner_ajuste(c, v))
            self._fichas[clave].append(ficha)
            flujo.addWidget(ficha)
        bv.addWidget(zona)
        return bloque

    def _solo_letras_instaladas(self):
        """Una letra recordada que ya no está en el cajón (desinstalada, o de otro equipo) vuelve a «Del tema»: así siempre hay una ficha marcada,
        el pie no dice «tu letra» de algo que no se ve y al_crear no recibe una letra que Resolve no tiene."""
        quitadas = []
        for clave, fichas in self._fichas.items():
            v = self._ajustes.get(clave, '')
            if v and v not in {f.valor for f in fichas}:
                self._ajustes[clave] = ''
                quitadas.append(v.split('|')[0])
        if quitadas:
            try:
                import registro
                registro.aviso(tr('«Crea tu estilo»: la letra {f} no está instalada; se usa la del tema.', f=', '.join(quitadas)), 'crea_estilo_ui')
            except Exception:
                pass

    def _marcar_cajon(self):
        for clave, fichas in self._fichas.items():
            for f in fichas:
                f.marcar(f.valor == self._ajustes.get(clave, ''))
        for clave, paleta in self._paletas.items():
            paleta.poner(self._ajustes.get(clave, ''), self._propios.get(clave, ''))

    def _alternar_cajon(self):
        self._abrir_cajon(not self._abierto)

    def _abrir_cajon(self, si):
        self._abierto = bool(si)
        self._interruptor.poner(self._abierto)
        self._resorte.objetivo = 1.0 if self._abierto else 0.0
        if self._abierto:
            self._cajon.show()
        ui.motor_resortes.pedir(self)

    def paso_resorte(self, dt):
        if self._cerrado or not ui.vivo(self):
            return False
        sigue = self._resorte.paso(dt)
        if not sigue:
            self._resorte.poner(self._resorte.objetivo)
        self._aplicar_cajon(self._resorte.x)
        return sigue

    def _aplicar_cajon(self, x):
        x = max(0.0, min(1.0, x))
        self._cajon.setFixedWidth(int(round(self._cajon.ancho_total() * x)))
        self._cajon.setVisible(x > 0.002)
        self._lista.poner_avance(x)

    def _parar_animacion(self):
        """El cajón salta a donde iba y sale del motor de resortes (al cerrar u ocultar la ventana)."""
        self._resorte.poner(self._resorte.objetivo)
        try:
            ui.motor_resortes._activos.discard(self)
        except Exception:
            pass
        if not self._cerrado and ui.vivo(self):
            self._aplicar_cajon(self._resorte.x)

    # ------------------------------------------------------------------ letra y colores
    def _poner_ajuste(self, clave, valor):
        valor = str(valor or '')
        if self._ajustes.get(clave, '') == valor:
            return
        self._ajustes[clave] = valor
        self._cambio_de_ajustes()

    def _color_propio(self, clave):
        """El «+»: un color a elección (QColorDialog). Uno de la paleta se elige tal cual; otro queda en el «+»."""
        inicial = self._propios.get(clave) or self._ajustes.get(clave) or '#FFFFFF'
        _rgb, hexa = ui.elegir_color(self, inicial, tr('Color personalizado'))
        if not hexa or self._cerrado or not ui.vivo(self):
            return
        hexa = str(hexa).upper()
        paleta = COLORES_PRINCIPAL if clave == 'color_principal' else COLORES_SECUNDARIO
        if hexa not in paleta:
            self._propios[clave] = hexa
        if self._ajustes.get(clave, '') == hexa:
            self._marcar_cajon()
            self._guardar()
            return
        self._ajustes[clave] = hexa
        self._cambio_de_ajustes()

    def _volver_al_tema(self):
        if not any(self._ajustes.values()):
            return
        self._ajustes = {k: '' for k in CLAVES}
        self._cambio_de_ajustes()

    def _cambio_de_ajustes(self):
        self._marcar_cajon()
        self._resumir()
        self._guardar()
        self._rehacer_imagenes()

    def _guardar(self):
        guardar_estado({'ajustes': dict(self._ajustes), 'propios': dict(self._propios)})

    def ajustes(self):
        return dict(self._ajustes)

    # ------------------------------------------------------------------ las imágenes de las filas (UN hilo)
    def _tam_imagen(self):
        dpr = self.devicePixelRatioF() or 1.0
        alto = int(round(68 * dpr))
        return int(round(alto * ASPECTO_IMAGEN)), alto

    def _poner_pixmaps(self, qimagenes):
        dpr = self.devicePixelRatioF() or 1.0
        pix = {}
        for n, q in (qimagenes or {}).items():
            if not isinstance(n, int) or q is None or q.isNull():
                continue
            pm = QPixmap.fromImage(q)
            pm.setDevicePixelRatio(dpr)
            pix[n] = pm
        self._lista.poner_imagenes(pix, (qimagenes or {}).get('fondo'))

    def _rehacer_imagenes(self):
        ancho, alto = self._tam_imagen()
        clave = _clave_imagenes(self._ajustes, ancho, alto)
        self._clave_actual = clave
        hechas = _IMAGENES.get(clave)
        if hechas is not None:
            self._pedido = None
            self._poner_pixmaps(hechas)
            self._lista.poner_rehaciendo(False)
            return
        self._pedido = (dict(self._ajustes), ancho, alto, clave)
        if not self._trabajando:
            self._lanzar()
        else:
            self._lista.poner_rehaciendo(True)

    def _lanzar(self):
        ajustes, ancho, alto, clave = self._pedido
        self._pedido = None
        self._trabajando = True
        self._lista.poner_rehaciendo(bool(self._lista._pix))

        def trabajo():
            errores = []
            try:
                import vista_estilos
                imagenes = vista_estilos.imagenes(ajustes, ancho, alto, errores=errores)
                salida = {int(n): _a_qimage(im) for n, im in imagenes.items() if im is not None}
                salida['fondo'] = tuple(vista_estilos.fondo(ajustes))       # (la fila se pinta del mismo fondo que sus imágenes)
            except Exception as e:
                salida = None
                errores.append(str(e))
            if errores:
                try:
                    import registro
                    registro.aviso(tr('«Crea tu estilo» no pudo dibujar algún caption: {e}', e='; '.join(errores)[:400]), 'crea_estilo_ui')
                except Exception:
                    pass
            return salida

        def fin(salida, _error):
            self._trabajando = False
            if self._cerrado:
                return
            if salida:
                _recordar_imagenes(clave, salida)
                if clave == self._clave_actual:
                    self._poner_pixmaps(salida)
            if self._pedido is not None:
                if self._pedido[3] in _IMAGENES:
                    self._rehacer_imagenes()
                else:
                    self._lanzar()
                return
            self._lista.poner_rehaciendo(False)
        ui.correr_en_hilo(self, trabajo, fin)

    # ------------------------------------------------------------------ elegir
    def _tocar(self, n):
        if n in self._orden:
            self._orden.remove(n)
        else:
            self._orden.append(n)
        self._lista.poner_orden(self._orden)
        self._resumir()

    def temas(self):
        return [f't{n}' for n in self._orden]

    def _resumir(self):
        propios = any(self._ajustes.get(k) for k in CLAVES)
        self._resumen.poner(self._orden, tr('tu letra y tus colores') if propios else tr('letra y colores del tema'))
        self._b_crear.setEnabled(bool(self._orden) and not self._creando)

    # ------------------------------------------------------------------ el pie y crear
    def _armar_pie(self):
        fuera, fv = caja_v(espacio=0, margenes=(4, 0, 4, 0))
        pie = QFrame()
        pie.setObjectName('pieCreaEstilo')
        pie.setStyleSheet(_hoja('QFrame#pieCreaEstilo { background-color: %s; border: 1px solid %s; border-radius: 14px; }' % (PANEL, BORDE)))
        pv = QVBoxLayout(pie)
        pv.setContentsMargins(14, 10, 14, 12)
        pv.setSpacing(8)
        self._resumen = _Resumen()
        pv.addWidget(self._resumen)
        fila, cf = caja_h(espacio=10)
        self._nombre = Entrada(placeholder=tr('Nombre de tu estilo'), alto=38, tam=14)
        self._nombre.setObjectName('nombreEstilo')
        self._nombre.setStyleSheet(_hoja('QLineEdit#nombreEstilo { background-color: %s; border: 1px solid %s; border-radius: 10px; padding: 0px 13px; '
                                         'color: #FFFFFF; } QLineEdit#nombreEstilo:focus { border-color: #0F62FE; }' % (CAMPO, BORDE)))
        self._nombre.setText(tr('Mi estilo'))
        self._nombre.returnPressed.connect(self._crear)
        cf.addWidget(self._nombre, 1)
        self._b_crear = Boton(tr('Crear mi pack'), self._crear, tipo='primario', alto=38, ancho=170, tam=14, negrita=True)
        self._b_crear.setFixedWidth(170)
        cf.addWidget(self._b_crear)
        pv.addWidget(fila)
        fv.addWidget(pie)
        return fuera

    def _llamar_al_crear(self, nombre, temas, ajustes):
        """al_crear(nombre, temas, terminado, ajustes). (Una app de antes con al_crear(nombre, ids, terminado) recibe solo los tres.)"""
        fn = self._al_crear
        try:
            import inspect
            params = list(inspect.signature(fn).parameters.values())
            cuatro = any(q.kind == q.VAR_POSITIONAL for q in params) or \
                sum(q.kind in (q.POSITIONAL_ONLY, q.POSITIONAL_OR_KEYWORD) for q in params) >= 4
        except (TypeError, ValueError):
            cuatro = True
        if cuatro:
            fn(nombre, temas, self._termino, ajustes)
        else:
            fn(nombre, temas, self._termino)

    def _crear(self):
        if not self._orden or self._creando:
            return
        nombre = self._nombre.text().strip() or tr('Mi estilo')
        self._creando = True
        self._b_crear.setEnabled(False)
        self._b_crear.setText(tr('Creando…'))
        try:
            self._llamar_al_crear(nombre, self.temas(), dict(self._ajustes))
        except Exception:
            ui._registrar_excepcion(*sys.exc_info())
            self._termino(False)

    def _termino(self, ok):
        """Lo llama la app cuando el pack ya está (o falló): si salió bien la ventana se cierra."""
        if not ui.vivo(self):
            return
        self._creando = False
        self._b_crear.setText(tr('Crear mi pack'))
        self._resumir()
        if ok:
            self.cerrar()

    # ------------------------------------------------------------------ cerrar
    def hideEvent(self, e):
        self._parar_animacion()
        super().hideEvent(e)

    def closeEvent(self, e):
        self._parar_animacion()
        self._cerrado = True
        self._pedido = None
        super().closeEvent(e)


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
    import ejemplos_estilo as E                   # (solo este dibujo del popup lo usa)
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
