# CineCaptions · By Cinema Productions
# 1_codigo/crea_estilo_ui.py — «Crea tu estilo»: texto base + textos principales con su previa ANIMADA sobre negro, la previa vertical con letra y color, y el popup de la estructura de nombres.
"""
Dos ventanas:

  * CreaEstiloDialogo : v5.75 (la maqueta animada que eligió el usuario: «que no sean repetidos; en base 4-6 como mucho y en principales todo lo
    que tenga efecto»). 1 · TEXTO BASE: 6 previas (mezcla_planificador.BASES_CREA), una o ninguna; su letra va en las líneas de arriba y abajo de
    todos los principales. 2 · TEXTOS PRINCIPALES: 18 previas con efecto (PRINCIPALES_CREA: círculo, barrido, fondo, fuego, tachado, caja, cristal,
    arrastre, corte, giro 3D, resaltado, línea, brillo…), las que se quieran, numeradas en el orden en que se turnan por frases. Lo que solo cambiaba
    de color sale una vez. Cada previa es 2_recursos/guia_estilo/crea/<id>.mp4 (el caption solo, animado sobre negro; vistas_slider.Reproductor,
    solo mientras la ventana se ve), sin texto debajo.
    v5.76 (el usuario: «rediseña la página… más moderna, la preview a la derecha en formato vertical, y la opción letra y color que se abra abajo
    de la preview para verse en la preview»): a la DERECHA la previa vertical 9:16 (la base y los principales turnándose, con el color elegido
    aplicado en vivo y la palabra principal con la letra elegida) y debajo «Letra» y «Color», que abren su panel bajo la previa (alto con resorte
    amortiguado, sin rebote). Arriba a la derecha, el nombre y «Crear mi tema» → al_crear(nombre, looks, terminado, ajustes, base):
    looks = ['t2:6', 't3:select', 't5'], base = 'b_t2' | None, ajustes = {'fuente_principal': 'Familia|Estilo' | '', 'fuente_secundaria': '' (la
    pone el texto base), 'color_principal': '#RRGGBB' | '', 'color_secundario'} (vacío = lo del tema). terminado(ok) cierra la ventana si salió
    bien. Lo último de letra y color se recuerda en ~/DaVinciSubtitles/crea_tu_estilo.json (archivos_seguros; NO en las prefs globales de fuente).
  * AyudaEstilo       : el popup del «!»: por qué los clips se llaman principal / arriba / abajo / simple, qué son principal 2 y principal 3,
    qué pasa si falta una pieza y cómo se exporta. Con dibujos, porque «sin esa estructura el estilo no funciona».
"""
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QColor as QColorReal
from PySide6.QtGui import (QBrush, QConicalGradient, QFont, QFontDatabase, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QStandardItem, QStandardItemModel, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QListView, QScrollArea, QSizePolicy, QStyle, QStyledItemDelegate,
                               QVBoxLayout, QWidget)

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

CLAVES = ('fuente_principal', 'fuente_secundaria', 'color_principal', 'color_secundario')
COLORES_PRINCIPAL = ('#FFFFFF', '#FDE047', '#A3E635', '#22D3EE', '#F472B6', '#EF4444', '#3B82F6', '#FB923C')
COLORES_SECUNDARIO = ('#FFFFFF', '#E5E7EB', '#9CA3AF', '#FDE047', '#22D3EE', '#F472B6')
RUTA_ESTADO = Path.home() / 'DaVinciSubtitles' / 'crea_tu_estilo.json'


def _hoja(css):
    return ui.traducir_hoja(css)


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


# ====================================================================================== memoria del cajón
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


# ====================================================================================== las previas animadas (v5.75)
def ruta_clip(ident):
    """2_recursos/guia_estilo/crea/<id>.mp4: el caption de esa base o ese principal SOLO, animado sobre negro (render real de Resolve:
    herramientas_dev/hacer_vistas_crea.py); None si falta."""
    try:
        from sfx_rules import base_recursos
        ruta = Path(base_recursos()) / 'guia_estilo' / 'crea' / f'{ident}.mp4'
    except Exception:
        ruta = Path(__file__).resolve().parent.parent / '2_recursos' / 'guia_estilo' / 'crea' / f'{ident}.mp4'
    try:
        return ruta if ruta.is_file() else None
    except OSError:
        return None


def _ultimo_cuadro(ruta):
    """El último cuadro del clip (el caption ya entero) como PIL.Image RGB, o None. Sin Qt: para el hilo de trabajo."""
    try:
        import av
        ultimo = None
        with av.open(str(ruta)) as contenedor:
            flujo = contenedor.streams.video[0]
            flujo.thread_type = 'NONE'
            for cuadro in contenedor.decode(flujo):
                ultimo = cuadro
        return ultimo.to_image().convert('RGB') if ultimo is not None else None
    except Exception:
        return None


def poster(base, principales, ancho=540, alto=960):
    """La foto vertical de la tarjeta del estilo en el slider (negro): la base arriba y los principales debajo, cada uno con el último cuadro de su
    previa (como mucho 6 piezas). None si no hay ninguna previa. Para el hilo de trabajo (decodifica)."""
    from PIL import Image
    piezas = []
    for ident in ([base] if base else []) + list(principales or []):
        ruta = ruta_clip(ident)
        im = _ultimo_cuadro(ruta) if ruta else None
        if im is not None:
            piezas.append(im)
    if not piezas:
        return None
    piezas = piezas[:6]
    margen = 24
    alto_fila = min(int((ancho - 2 * margen) * 9 / 16), int((alto - 2 * margen) / len(piezas)))
    ancho_fila = int(round(alto_fila * 16 / 9))
    lienzo = Image.new('RGB', (int(ancho), int(alto)), (0, 0, 0))
    y = int((alto - alto_fila * len(piezas)) / 2)
    for im in piezas:
        lienzo.paste(im.resize((ancho_fila, alto_fila), Image.LANCZOS), (int((ancho - ancho_fila) / 2), y))
        y += alto_fila
    return lienzo


class _Rejilla(_UnToque, QWidget):
    """Una rejilla de tarjetas 16:9 con el caption animado sobre negro (vistas_slider.Reproductor: un hilo por tarjeta, solo mientras la página se
    ve), SIN texto debajo (v5.76, el usuario: «solo deja la preview y que no tenga texto abajo… se verá más limpio»). varios=False (texto base):
    se elige una o ninguna (✓); varios=True (principales): las que se quieran, numeradas en el orden de toque. Todo en UN widget pintado a mano
    (sin una capa por tarjeta)."""
    HALO = 4
    GAP_X = 12
    GAP_Y = 12
    ETQ = 0                                           # (antes 30: la etiqueta «Tema 2» y la píldora del efecto)

    def __init__(self, items, columnas, varios, al_tocar, ancho_min=None):
        super().__init__()
        import vistas_slider
        self._items = list(items)                     # [{'id', 'texto', 'efecto' ('' en las bases)}]
        self._cols = max(1, int(columnas))
        self._ancho_min = ancho_min                   # v5.76: con él, las columnas salen del ancho (cada tarjeta ≥ ancho_min px)
        self._varios = bool(varios)
        self._al_tocar = al_tocar
        self._orden = []
        self._hover = None
        self._reprod = {}
        for it in self._items:
            ruta = ruta_clip(it['id'])
            self._reprod[it['id']] = vistas_slider.Reproductor(ruta, pausa_s=0) if ruta else None
        self._f_num = ui.fuente(12, peso='extra')
        self._f_falta = ui.fuente(11)
        self._t_falta = tr('Sin previa')
        self.setMouseTracking(True)
        politica = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        politica.setHeightForWidth(True)                # (el alto sale del ancho; forzarlo en resizeEvent hacía entrar y salir la barra sin fin)
        self.setSizePolicy(politica)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, ancho):
        return self._alto_para(ancho)

    def sizeHint(self):
        return QSize(960, self._alto_para(960))

    # -- medidas
    def _cols_para(self, ancho):
        if not self._ancho_min:
            return self._cols
        util = max(10.0, float(ancho) - 2 * self.HALO)
        return max(2, min(max(1, len(self._items)), int((util + self.GAP_X) // (self._ancho_min + self.GAP_X))))

    def _tarjeta_wh(self, ancho):
        util = max(10.0, float(ancho) - 2 * self.HALO)
        cols = self._cols_para(ancho)
        cw = (util - (cols - 1) * self.GAP_X) / cols
        return cw, cw * 9.0 / 16.0

    def _alto_para(self, ancho):
        _cw, ch = self._tarjeta_wh(ancho)
        cols = self._cols_para(ancho)
        filas = (len(self._items) + cols - 1) // cols
        return int(round(2 * self.HALO + filas * (ch + self.ETQ) + max(0, filas - 1) * self.GAP_Y))

    def resizeEvent(self, e):
        """Cada previa se decodifica ya al tamaño de su tarjeta en píxeles reales (Reproductor.tam): pintar es copiar, sin escalar 20 videos."""
        super().resizeEvent(e)
        r0 = self._rect(0)
        dpr = self.devicePixelRatioF() or 1.0
        tam = (int(round(r0.width() * dpr)), int(round(r0.height() * dpr)))
        for r in self._reprod.values():
            if r is not None:
                r.tam = tam

    def _rect(self, k):
        """La tarjeta k AJUSTADA a píxeles reales de la pantalla (con escala 1,5 una esquina fraccionaria dejaba una costura en el borde)."""
        cw, ch = self._tarjeta_wh(self.width())
        fila, col = divmod(k, self._cols_para(self.width()))
        dpr = self.devicePixelRatioF() or 1.0
        x = round((self.HALO + col * (cw + self.GAP_X)) * dpr)
        y = round((self.HALO + fila * (ch + self.ETQ + self.GAP_Y)) * dpr)
        return QRectF(x / dpr, y / dpr, int(cw * dpr) / dpr, int(ch * dpr) / dpr)

    def _en(self, pos):
        for k, it in enumerate(self._items):
            r = self._rect(k)
            if r.adjusted(0, 0, 0, self.ETQ).contains(QPointF(pos)):
                return it['id']
        return None

    # -- estado
    def poner_orden(self, orden):
        self._orden = [i for i in orden if i in self._reprod]
        self.update()

    def imagen(self, ident):
        r = self._reprod.get(ident)
        return r.imagen() if r is not None else None

    def poner_visible(self, visible):
        for r in self._reprod.values():
            if r is None:
                continue
            if visible:
                r.arrancar()
            else:
                r.parar()

    # -- dibujo
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for k, it in enumerate(self._items):
            self._pintar(p, self._rect(k), it)
        p.end()

    def _pintar(self, p, r, it):
        ident = it['id']
        elegido = ident in self._orden
        if elegido:                                                         # el halo verde (box-shadow 0 0 0 4px al 16 %)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColorReal(36, 209, 143, 40))
            p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 14, 14)
        img = self.imagen(ident)
        p.setPen(Qt.PenStyle.NoPen)
        if img is not None and not img.isNull():
            # la previa como TEXTURA del rectángulo redondeado (setClipPath con escala 1,5 dejaba una costura de rayitas en el borde)
            pincel = QBrush(img)
            t = QTransform()
            t.translate(r.x(), r.y())
            t.scale(r.width() / img.width(), r.height() / img.height())
            pincel.setTransform(t)
            p.setBrush(pincel)
        else:
            p.setBrush(QColorReal('#000000'))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)       # (con antialias el relleno dejaba rayitas de 1 px en el borde izquierdo a 1,5)
        p.drawRoundedRect(r, 10, 10)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)        # el borde de encima (con antialias) alisa la esquina
        if img is None and self._reprod.get(ident) is None:
            p.setFont(self._f_falta)
            p.setPen(QColor(GRIS))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), self._t_falta)
        if elegido:
            p.setPen(QPen(QColor(VERDE), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 9, 9)
        else:
            p.setPen(QPen(QColor(BORDE_HOVER) if self._hover == ident else QColorReal(255, 255, 255, 24), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 9.5, 9.5)
        marca = QRectF(r.right() - 30, r.y() + 7, 23, 23)
        if elegido:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(VERDE))
            p.drawEllipse(marca)
            if self._varios:
                p.setFont(self._f_num)
                p.setPen(QColorReal('#03140D'))
                p.drawText(marca, int(Qt.AlignmentFlag.AlignCenter), str(self._orden.index(ident) + 1))
            else:
                ix, iy = marca.center().x(), marca.center().y()
                p.setPen(QPen(QColorReal('#03140D'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawPolyline([QPointF(ix - 5, iy + 0.5), QPointF(ix - 1.5, iy + 4), QPointF(ix + 5.5, iy - 4)])
        else:
            p.setPen(QPen(QColorReal(255, 255, 255, 110), 1.6))
            p.setBrush(QColorReal(0, 0, 0, 40))
            p.drawEllipse(marca.adjusted(1.5, 1.5, -1.5, -1.5))

    # -- ratón
    def mouseMoveEvent(self, e):
        i = self._en(e.position())
        if i != self._hover:
            self._hover = i
            self.setCursor(Qt.CursorShape.PointingHandCursor if i else Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            i = self._en(e.position())
            if i:
                self._al_tocar(i)
                e.accept()
                return
        super().mousePressEvent(e)


class _Paso(QWidget):
    """El título de una sección: el número en su círculo verde, el nombre y la explicación en gris."""
    def __init__(self, numero, titulo, detalle):
        super().__init__()
        self._n, self._t, self._d = str(numero), titulo, detalle
        self._f_n = ui.fuente(12, peso='extra')
        self._f_t = ui.fuente(15, peso='extra')
        self._f_d = ui.fuente(12)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = QRectF(4, 3, 22, 22)
        p.setPen(QPen(QColorReal(36, 209, 143, 115), 1))
        p.setBrush(QColorReal(36, 209, 143, 36))
        p.drawEllipse(c)
        p.setFont(self._f_n)
        p.setPen(QColor(VERDE))
        p.drawText(c, int(Qt.AlignmentFlag.AlignCenter), self._n)
        medio = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.setFont(self._f_t)
        p.setPen(QColorReal('#FFFFFF'))
        tw = QFontMetricsF(self._f_t).horizontalAdvance(self._t)
        p.drawText(QRectF(36, 0, tw + 2, self.height()), medio, self._t)
        p.setFont(self._f_d)
        p.setPen(QColor(GRIS))
        x = 36 + tw + 12
        resto = max(0.0, self.width() - x)
        p.drawText(QRectF(x, 0, resto, self.height()), medio, QFontMetricsF(self._f_d).elidedText(self._d, Qt.TextElideMode.ElideRight, resto))
        p.end()


# ====================================================================================== la lista de letras del equipo (v5.75)
ESTILOS_GRUESOS = ('Bold', 'Black', 'ExtraBold', 'Extra Bold', 'Heavy', 'SemiBold', 'Semibold', 'Semi Bold', 'Medium', 'Regular', 'Normal', 'Book')


def letras_instaladas():
    """Las familias de letra del equipo (QFontDatabase: las del sistema y las del programa), sin las privadas ni las verticales «@…», por orden
    alfabético. En el hilo de la interfaz (Qt)."""
    vistas = set()
    salida = []
    for f in QFontDatabase.families():
        if not f or f.startswith('@') or f.lower() in vistas:
            continue
        try:
            if QFontDatabase.isPrivateFamily(f):
                continue
        except Exception:
            pass
        vistas.add(f.lower())
        salida.append(f)
    return sorted(salida, key=str.lower)


def estilo_grueso(familia):
    """El estilo con el que se aplica una letra al tocarla: el más grueso de los habituales (Bold, Black…); si no tiene ninguno, el primero."""
    estilos = list(QFontDatabase.styles(familia) or [])
    for e in ESTILOS_GRUESOS:
        if e in estilos:
            return e
    return estilos[0] if estilos else 'Regular'


class _DelegadoLetra(QStyledItemDelegate):
    """Una fila de la lista: el nombre ESCRITO con su letra (y, a la derecha, en la letra del programa por si es de símbolos). Solo se dibujan
    las filas que se ven: con mil letras abrir la lista no carga mil fuentes."""
    ALTO = 36

    def __init__(self, padre):
        super().__init__(padre)
        self._fuentes = {}
        self._f_nombre = ui.fuente(10)
        self._f_tema = ui.fuente(14, peso='negrita')

    def sizeHint(self, _opcion, _indice):
        return QSize(120, self.ALTO)

    def _fuente(self, familia):
        f = self._fuentes.get(familia)
        if f is None:
            f = QFont(familia)
            f.setPixelSize(18)
            if len(self._fuentes) > 400:
                self._fuentes.clear()
            self._fuentes[familia] = f
        return f

    def paint(self, p, opcion, indice):
        familia = indice.data(Qt.ItemDataRole.UserRole) or ''
        texto = indice.data(Qt.ItemDataRole.DisplayRole) or ''
        r = QRectF(opcion.rect).adjusted(2, 1, -2, -1)
        elegida = bool(opcion.state & QStyle.StateFlag.State_Selected)
        encima = bool(opcion.state & QStyle.StateFlag.State_MouseOver)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if elegida:
            p.setPen(QPen(QColor(VERDE), 1.2))
            p.setBrush(QColorReal(36, 209, 143, 30))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        elif encima:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColorReal(255, 255, 255, 12))
            p.drawRoundedRect(r, 8, 8)
        medio = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        derecha = r.right() - 10
        if familia:
            p.setFont(self._f_nombre)
            fm = QFontMetricsF(self._f_nombre)
            corto = fm.elidedText(familia, Qt.TextElideMode.ElideRight, 110)
            ancho = fm.horizontalAdvance(corto)
            p.setPen(QColor(GRIS))
            p.drawText(QRectF(derecha - ancho, r.y(), ancho + 2, r.height()), medio, corto)
            derecha -= ancho + 10
            p.setFont(self._fuente(familia))
        else:
            p.setFont(self._f_tema)
        p.setPen(QColor(VERDE) if elegida else QColorReal('#FFFFFF'))
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(r.x() + 12, r.y(), max(0.0, derecha - r.x() - 12), r.height()), medio,
                   fm.elidedText(texto, Qt.TextElideMode.ElideRight, max(0.0, derecha - r.x() - 12)))
        p.restore()


class _ChipEstilo(_UnToque, QWidget):
    """Un estilo de la letra elegida («Bold», «Black», «Italic»…) escrito con ese estilo; marcado = verde."""
    def __init__(self, familia, estilo, al_tocar):
        super().__init__()
        self.estilo = estilo
        self._al_tocar = al_tocar
        self._marcado = False
        f = QFont(familia)
        f.setStyleName(estilo)
        f.setPixelSize(13)
        self._f = f
        self.setFixedSize(int(QFontMetricsF(f).horizontalAdvance(estilo) + 24), 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def marcar(self, si):
        if bool(si) != self._marcado:
            self._marcado = bool(si)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(VERDE) if self._marcado else QColor(BORDE), 1.2 if self._marcado else 1))
        p.setBrush(QColorReal(36, 209, 143, 30) if self._marcado else QColor(CAMPO))
        p.drawRoundedRect(r, 13.5, 13.5)
        p.setFont(self._f)
        p.setPen(QColor(VERDE) if self._marcado else QColorReal('#E8F1FF'))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), self.estilo)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._al_tocar(self.estilo)
            e.accept()
            return
        super().mousePressEvent(e)


class _ListaLetras(QWidget):
    """«Texto principal» del cajón: TODAS las letras instaladas en el equipo (200 o mil) en una lista con buscador; cada nombre escrito con su letra.
    Tocar una la aplica («Familia|Estilo» con su estilo más grueso: estilo_grueso) y debajo salen sus estilos para cambiarlo. «Del tema» (la
    primera) = la letra de cada tema. al_elegir(valor): '' o 'Familia|Estilo'."""
    ALTO_LISTA = 252

    def __init__(self, al_elegir, alto_lista=None):
        super().__init__()
        self._al_elegir = al_elegir
        self._valor = ''
        self._alto_lista = int(alto_lista or self.ALTO_LISTA)
        self.familias = letras_instaladas()
        self._en_minusculas = {f.lower(): f for f in self.familias}
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(6)
        self._buscar = Entrada(placeholder=tr('Buscar entre tus {n} letras…', n=len(self.familias)), alto=32, tam=12)
        self._buscar.setObjectName('buscarLetra')
        self._buscar.setStyleSheet(_hoja('QLineEdit#buscarLetra { background-color: %s; border: 1px solid %s; border-radius: 9px; padding: 0px 10px; '
                                         'color: #FFFFFF; } QLineEdit#buscarLetra:focus { border-color: #0F62FE; }' % (CAMPO, BORDE)))
        self._buscar.textChanged.connect(self._filtrar)
        capa.addWidget(self._buscar)
        self._modelo = QStandardItemModel(self)
        tema = QStandardItem(tr('Del estilo'))
        tema.setData('', Qt.ItemDataRole.UserRole)
        self._modelo.appendRow(tema)
        for f in self.familias:
            it = QStandardItem(f)
            it.setData(f, Qt.ItemDataRole.UserRole)
            self._modelo.appendRow(it)
        self._filtro = QSortFilterProxyModel(self)
        self._filtro.setSourceModel(self._modelo)
        self._filtro.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._vista = QListView()
        self._vista.setObjectName('listaLetras')
        self._vista.setModel(self._filtro)
        self._vista.setItemDelegate(_DelegadoLetra(self._vista))
        self._vista.setUniformItemSizes(True)
        self._vista.setMouseTracking(True)
        self._vista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._vista.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._vista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._vista.setFixedHeight(self._alto_lista)
        self._vista.setStyleSheet(_hoja('QListView#listaLetras { background-color: %s; border: 1px solid %s; border-radius: 10px; padding: 3px; '
                                        'outline: none; }' % (CAMPO, BORDE)))
        self._vista.clicked.connect(self._tocada)
        capa.addWidget(self._vista)
        self._caja_estilos = QVBoxLayout()
        self._caja_estilos.setContentsMargins(0, 0, 0, 0)
        capa.addLayout(self._caja_estilos)
        self._zona_estilos = None

    # -- buscar y elegir
    def _filtrar(self, texto):
        self._filtro.setFilterFixedString(str(texto or '').strip())
        self._seleccionar_actual(desplazar=False)

    def _tocada(self, indice):
        familia = indice.data(Qt.ItemDataRole.UserRole) or ''
        valor = fuente_usuario.a_texto(familia, estilo_grueso(familia)) if familia else ''
        if familia and self._valor.split('|')[0] == familia:
            return                                                   # (la misma letra: se queda su estilo)
        self._al_elegir(valor)

    def _estilo_tocado(self, estilo):
        familia = self._valor.split('|')[0]
        if familia:
            self._al_elegir(fuente_usuario.a_texto(familia, estilo))

    def instalada(self, valor):
        """¿Está esta letra («Familia|Estilo») en el equipo? '' (del tema) siempre."""
        familia = str(valor or '').split('|')[0].strip()
        return not familia or familia.lower() in self._en_minusculas

    # -- marcar lo elegido
    def marcar(self, valor):
        self._valor = str(valor or '')
        self._seleccionar_actual(desplazar=True)
        self._poner_estilos()

    def _seleccionar_actual(self, desplazar):
        familia = self._valor.split('|')[0]
        fila = 0
        if familia:
            real = self._en_minusculas.get(familia.lower())
            fila = (self.familias.index(real) + 1) if real else 0
        indice = self._filtro.mapFromSource(self._modelo.index(fila, 0))
        sel = self._vista.selectionModel()
        if indice.isValid():
            sel.setCurrentIndex(indice, sel.SelectionFlag.ClearAndSelect)
            if desplazar:
                self._vista.scrollTo(indice, QAbstractItemView.ScrollHint.PositionAtCenter)
        else:
            sel.clearSelection()

    def _poner_estilos(self):
        """Los estilos de la letra elegida, en una zona NUEVA cada vez (la capa de flujo no sabe quitar piezas)."""
        if self._zona_estilos is not None:
            self._caja_estilos.removeWidget(self._zona_estilos)
            self._zona_estilos.hide()
            self._zona_estilos.deleteLater()
            self._zona_estilos = None
        partes = self._valor.split('|')
        familia = partes[0]
        estilos = list(QFontDatabase.styles(familia) or [])[:14] if familia else []
        if not estilos:
            return
        actual = partes[1] if len(partes) > 1 else 'Regular'
        zona = QWidget()
        flujo = FlujoCapa(zona, espacio_h=6, espacio_v=6)
        for estilo in estilos:
            chip = _ChipEstilo(familia, estilo, self._estilo_tocado)
            chip.marcar(estilo == actual)
            flujo.addWidget(chip)
        self._caja_estilos.addWidget(zona)
        self._zona_estilos = zona


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


def _dibujar_centro(p, destino, img, ancho_rel=0.92, alto_rel=0.70):
    """Dibuja el CENTRO de una previa 16:9 (donde está la tinta: las previas dejan ~84 % × 62 % para el caption) encajado (sin deformar) y centrado
    en `destino`."""
    if img is None or img.isNull():
        return
    sw, sh = float(img.width()), float(img.height())
    fuente = QRectF(sw * (1 - ancho_rel) / 2, sh * (1 - alto_rel) / 2, sw * ancho_rel, sh * alto_rel)
    f = min(destino.width() / fuente.width(), destino.height() / fuente.height())
    w, h = fuente.width() * f, fuente.height() * f
    p.drawImage(QRectF(destino.center().x() - w / 2, destino.center().y() - h / 2, w, h), img, fuente)


def _tenido(img, hexa):
    """La previa con el color elegido, en vivo: su luminancia × el color (las previas son captions claros sobre negro: el negro sigue negro y el
    blanco sale del color elegido, como en el pack derivado). Sin color, la previa tal cual."""
    if img is None or img.isNull() or not hexa:
        return img
    g = img.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(g)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    p.fillRect(g.rect(), QColorReal(hexa))
    p.end()
    return g


def _hex_rgb(hexa, defecto):
    h = str(hexa or '').strip().lstrip('#')
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else defecto
    except ValueError:
        return defecto


def _tenido_rojo(img, principal, secundario):
    """v5.78, la previa del Estilo 7 (blanco + la palabra que suena en rojo, con contorno y sombra negros): cada píxel es blanco × kb + rojo × kr
    sobre negro; el rojo pasa al color principal y el blanco al secundario (como el pack derivado: pack_personalizado.ajuste_de_clip). Sin
    colores, tal cual."""
    if img is None or img.isNull() or not (principal or secundario):
        return img
    import numpy as np
    g = img.convertToFormat(QImage.Format.Format_RGB32)
    w, h = g.width(), g.height()
    a = np.frombuffer(g.constBits(), np.uint8).reshape(h, g.bytesPerLine())[:, :w * 4].reshape(h, w, 4).astype(np.float32)
    kb = np.minimum(a[..., 0], a[..., 1]) / 250.0                       # (BGRA: el blanco sube G y B; el rojo de la referencia, casi nada)
    kr = np.clip(a[..., 2] - 250.0 * kb, 0.0, None) / 226.0
    cp = np.array(_hex_rgb(principal, (226, 6, 18)), np.float32)
    cs = np.array(_hex_rgb(secundario, (250, 250, 250)), np.float32)
    rgb = np.clip(kb[..., None] * cs + kr[..., None] * cp, 0, 255).astype(np.uint8)
    salida = np.empty((h, w, 4), np.uint8)
    salida[..., 0], salida[..., 1], salida[..., 2], salida[..., 3] = rgb[..., 2], rgb[..., 1], rgb[..., 0], 255
    return QImage(salida.tobytes(), w, h, w * 4, QImage.Format.Format_RGB32).copy()


def _letra_de(valor):
    """'Familia|Estilo' -> QFont de esa letra (o None: la del tema)."""
    partes = str(valor or '').split('|')
    familia = partes[0].strip()
    if not familia:
        return None
    f = QFont(familia)
    if len(partes) > 1 and partes[1].strip():
        f.setStyleName(partes[1].strip())
    return f


class _Previa(QWidget):
    """La previa VERTICAL de la derecha (v5.76, el usuario: «la preview a la derecha en formato vertical… letra y color… para verse en la
    preview»): un cuadro 9:16 con la base elegida arriba y los principales TURNÁNDOSE debajo (una vuelta de su previa cada uno), con el color
    elegido aplicado en vivo (_tenido) y, con una letra elegida, la palabra principal escrita con ella debajo (las previas son videos de Resolve:
    la letra no cambia dentro de ellos). Sus propios Reproductor (dos hilos), solo mientras la ventana se ve. El cuadro encoge al abrirse
    Letra o Color debajo: siempre el 9:16 más grande que cabe."""
    MUESTRA = 'Increíbles'                         # la palabra de las previas de los principales
    RADIO = 18

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)
        self._base = None
        self._principales = []
        self._ajustes = {}
        self._k = 0
        self._rb = None
        self._rp = None
        self._visible = False
        self._f_vacio = ui.fuente(13)
        self._t_vacio = tr('Elige un texto principal')

    @staticmethod
    def _nuevo(ident):
        import vistas_slider
        ruta = ruta_clip(ident) if ident else None
        return vistas_slider.Reproductor(ruta, pausa_s=0) if ruta else None

    def _cambiar(self, cual):
        viejo = self._rb if cual == 'b' else self._rp
        if viejo is not None:
            viejo.parar()
        if cual == 'b':
            nuevo = self._rb = self._nuevo(self._base)
        else:
            nuevo = self._rp = self._nuevo(self._principales[self._k] if self._principales else None)
        self._tam()
        if self._visible and nuevo is not None:
            nuevo.arrancar()

    def poner(self, base, principales, ajustes=None):
        self._ajustes = dict(ajustes or {})
        if base != self._base:
            self._base = base
            self._cambiar('b')
        principales = list(principales)
        if principales != self._principales:
            actual = self._principales[self._k] if self._k < len(self._principales) else None
            self._principales = principales
            self._k = principales.index(actual) if actual in principales else 0
            if actual is None or actual not in principales or self._rp is None:
                self._cambiar('p')
        self.update()

    def poner_visible(self, visible):
        self._visible = bool(visible)
        for r in (self._rb, self._rp):
            if r is not None:
                if visible:
                    r.arrancar()
                else:
                    r.parar()

    def tic(self):
        """Cuando el principal que se ve termina su vuelta, entra el siguiente (como en el video: se turnan frase a frase)."""
        if self._rp is not None and len(self._principales) > 1 and getattr(self._rp, 'vueltas', 0) >= 1:
            self._k = (self._k + 1) % len(self._principales)
            self._cambiar('p')
        self.update()

    def cerrar(self):
        self._visible = False
        for r in (self._rb, self._rp):
            if r is not None:
                r.parar()

    # -- medidas
    def tarjeta(self):
        """El 9:16 más grande que cabe, centrado a lo ancho y pegado arriba."""
        w, h = float(self.width()), float(self.height())
        ch = max(10.0, min(h - 1.0, (w - 1.0) * 16.0 / 9.0))
        cw = ch * 9.0 / 16.0
        return QRectF(round((w - cw) / 2.0) + 0.5, 0.5, cw, ch)

    def _tam(self):
        """Cada previa se decodifica ya a su tamaño en pantalla (Reproductor.tam): pintar es copiar."""
        r = self.tarjeta()
        dpr = self.devicePixelRatioF() or 1.0
        ancho = max(64, int(r.width() * 0.96 * dpr / 0.92)) // 2 * 2
        tam = (ancho, int(ancho * 9 / 16) // 2 * 2)
        for rep in (self._rb, self._rp):
            if rep is not None:
                rep.tam = tam

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._tam()

    # -- dibujo
    def _muestra(self, p, rect, letra, color):
        """La palabra principal escrita con la letra elegida, encajada en `rect`."""
        f = QFont(letra)
        f.setPixelSize(max(8, int(rect.height() * 0.62)))
        ancho = QFontMetricsF(f).horizontalAdvance(self.MUESTRA)
        if ancho > rect.width():
            f.setPixelSize(max(8, int(f.pixelSize() * rect.width() / ancho)))
        p.setFont(f)
        p.setPen(QColorReal(color or '#FFFFFF'))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self.MUESTRA)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self.tarjeta()
        camino = QPainterPath()
        camino.addRoundedRect(r, self.RADIO, self.RADIO)
        p.save()
        p.setClipPath(camino)
        fondo = QLinearGradient(r.topLeft(), r.bottomLeft())
        for pos, c in ((0.0, '#0C1424'), (0.45, '#05080F'), (1.0, '#000000')):
            fondo.setColorAt(pos, QColorReal(c))
        p.fillRect(r, fondo)
        if self._principales:
            ancho = r.width() * 0.96
            alto_p = ancho / 2.336                      # (el centro de una previa 16:9 que dibuja _dibujar_centro: 92 % × 70 %)
            letra = _letra_de(self._ajustes.get('fuente_principal'))
            cy = r.top() + r.height() * (0.50 if letra else 0.54)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)     # (el negro de las previas desaparece sobre el fondo)
            if self._base:
                alto_b = alto_p * 0.62
                _dibujar_centro(p, QRectF(r.center().x() - ancho * 0.41, cy - alto_p / 2 - alto_b * 0.9, ancho * 0.82, alto_b),
                                _tenido(self._rb.imagen() if self._rb else None, self._ajustes.get('color_secundario')))
            img_p = self._rp.imagen() if self._rp else None
            if self._principales[self._k % len(self._principales)] == 'p_t7':    # v5.78: el Estilo 7, cada color en lo suyo
                img_p = _tenido_rojo(img_p, self._ajustes.get('color_principal'), self._ajustes.get('color_secundario'))
            else:
                img_p = _tenido(img_p, self._ajustes.get('color_principal'))
            _dibujar_centro(p, QRectF(r.center().x() - ancho / 2, cy - alto_p / 2, ancho, alto_p), img_p)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            if letra is not None:
                self._muestra(p, QRectF(r.left() + r.width() * 0.08, cy + alto_p / 2 + 4, r.width() * 0.84, alto_p * 0.62), letra,
                              self._ajustes.get('color_principal'))
        else:
            p.setFont(self._f_vacio)
            p.setPen(QColor(GRIS))
            p.drawText(r.adjusted(16, 0, -16, 0), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self._t_vacio)
        p.restore()
        p.setPen(QPen(QColorReal(255, 255, 255, 34), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, self.RADIO, self.RADIO)
        p.end()


class _Pestana(_UnToque, QWidget):
    """«Letra» / «Color» bajo la previa: una pastilla que abre su panel debajo (abierta = verde). La de letra enseña «Aa» con la letra elegida; la
    de color, un círculo con el color elegido (el degradado = el del tema)."""
    ALTO = 40

    def __init__(self, texto, tipo, al_tocar):
        super().__init__()
        self._texto = texto
        self._tipo = tipo
        self._al_tocar = al_tocar
        self._on = False
        self._hover = False
        self.valor = ''
        self._f = ui.fuente(13, peso='negrita')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.ALTO)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, on=None, valor=None):
        if on is not None:
            self._on = bool(on)
        if valor is not None:
            self.valor = str(valor or '')
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._on:
            p.setPen(QPen(QColor(VERDE), 1.2))
            p.setBrush(QColorReal(52, 211, 153, 30))
            color = QColor(VERDE)
        else:
            p.setPen(QPen(QColorReal('#3A4A66') if self._hover else QColorReal('#243049'), 1))
            p.setBrush(QColorReal('#101826') if self._hover else QColorReal('#0C1320'))
            color = QColorReal('#E8F1FF')
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        fm = QFontMetricsF(self._f)
        tw = fm.horizontalAdvance(self._texto)
        ancho_ico = 22
        x = (self.width() - (ancho_ico + 8 + tw + 6 + 8)) / 2.0
        cy = self.height() / 2.0
        ico = QRectF(x, cy - ancho_ico / 2, ancho_ico, ancho_ico)
        if self._tipo == 'color':
            p.setPen(QPen(QColorReal(255, 255, 255, 70), 1))
            p.setBrush(QColorReal(self.valor) if self.valor else _degradado_tema(ico))
            p.drawEllipse(ico.adjusted(2, 2, -2, -2))
        else:
            letra = _letra_de(self.valor)
            f = QFont(letra) if letra is not None else ui.fuente(14, peso='extra')
            f.setPixelSize(17)
            p.setFont(f)
            p.setPen(color)
            p.drawText(ico, int(Qt.AlignmentFlag.AlignCenter), 'Aa')
        p.setFont(self._f)
        p.setPen(color)
        p.drawText(QRectF(ico.right() + 8, 0, tw + 2, self.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._texto)
        fx = ico.right() + 8 + tw + 7
        flecha = QPainterPath()
        if self._on:                                   # ▴
            flecha.moveTo(fx, cy + 2)
            flecha.lineTo(fx + 7, cy + 2)
            flecha.lineTo(fx + 3.5, cy - 2)
        else:                                          # ▾
            flecha.moveTo(fx, cy - 2)
            flecha.lineTo(fx + 7, cy - 2)
            flecha.lineTo(fx + 3.5, cy + 2)
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


class _Desplegable(QWidget):
    """El panel que se abre bajo la previa: su ALTO se anima y la página de dentro no cambia de tamaño (no se recoloca nada al animar): queda pegada
    arriba, así que se descubre de arriba abajo."""

    def __init__(self, paginas):
        super().__init__()
        self.paginas = dict(paginas)
        for w in self.paginas.values():
            w.setParent(self)
            w.hide()
        self.actual = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(0)

    def alto_de(self, nombre):
        w = self.paginas.get(nombre)
        if w is None:
            return 0
        capa = w.layout()
        ancho = max(1, self.width())
        if capa is not None and capa.hasHeightForWidth():
            return int(capa.totalHeightForWidth(ancho))
        return int(w.sizeHint().height())

    def mostrar(self, nombre):
        self.actual = nombre
        for k, w in self.paginas.items():
            w.setVisible(k == nombre)
        self._colocar()

    def _colocar(self):
        w = self.paginas.get(self.actual)
        if w is not None:
            w.setGeometry(0, 0, self.width(), self.alto_de(self.actual))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._colocar()


class CreaEstiloDialogo(Dialogo):
    """«Crea tu estilo» (v5.75, la maqueta animada que eligió el usuario; v5.76, rediseño con la previa vertical a la derecha): a la izquierda
    1 · TEXTO BASE (6 previas; una o ninguna) y 2 · TEXTOS PRINCIPALES (18 previas con efecto; las que se quieran, numeradas en el orden en que se
    turnan), todo animado sobre negro y sin texto debajo; a la derecha la previa vertical (la base y los principales turnándose, con el color y la
    letra elegidos) y debajo «Letra» y «Color», que abren su panel bajo la previa; arriba a la derecha el nombre y «Crear mi tema». La letra es la
    del texto principal (la de arriba y abajo la da el texto base). al_crear(nombre, looks, terminado, ajustes, base): looks = ['t2:6', 't3:select',
    't5'] en el orden de toque, base = 'b_t2' o None (mezcla_planificador.crear_estilo pone su letra en 'fuente_secundaria'). El resto de argumentos
    (al_resolve, al_ayuda, al_resolve_uno) se aceptan solo por compatibilidad con la llamada de la app y no se usan."""
    K_RESORTE = 300.0
    C_RESORTE = 34.6              # 2·√k: amortiguado crítico (el alto del panel no rebota)
    TIC_MS = 40
    ANCHO_DER = 392               # la columna de la previa (la paleta de 10 círculos mide 340)

    def __init__(self, padre, al_crear, *_compat, **_compat_kw):
        import mezcla_planificador as MP
        super().__init__(padre, tr('Crea tu estilo'), 1320, 840, minimo=(1060, 640))
        self.setObjectName('creaEstilo')
        self.setStyleSheet(_hoja('QDialog#creaEstilo { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0B1220, stop:1 #070A11); }'))
        self._al_crear = al_crear
        self._base = None
        self._orden = []
        self._creando = False
        self._cerrado = False
        estado = leer_estado()
        self._ajustes = estado['ajustes']
        self._ajustes['fuente_secundaria'] = ''        # (v5.75: la letra de arriba y abajo la pone el TEXTO BASE)
        self._propios = estado['propios']
        self._resorte = ui.Resorte(0.0, self.K_RESORTE, self.C_RESORTE)
        self._abierto = None                           # 'letra' | 'color' | None: lo que está abierto bajo la previa

        capa = QVBoxLayout(self)
        capa.setContentsMargins(24, 20, 24, 20)
        capa.setSpacing(0)
        # cabecera: el título | el nombre y «Crear mi tema»
        cab, cc = caja_h(espacio=12)
        textos, tv = caja_v(espacio=4)
        tv.addWidget(Etiqueta(tr('Crea tu estilo'), 24, peso='extra', color='#FFFFFF'))
        tv.addWidget(Etiqueta(tr('Arma tu estilo: un texto base y los textos principales que quieras. El color y la letra los eliges aparte.'), 13,
                              color='#A9B4C8', envolver=True))
        cc.addWidget(textos, 1)
        self._nombre = Entrada(placeholder=tr('Nombre de tu estilo'), alto=44, tam=14)
        self._nombre.setObjectName('nombreEstilo')
        self._nombre.setStyleSheet(_hoja('QLineEdit#nombreEstilo { background-color: %s; border: 1px solid %s; border-radius: 22px; padding: 0px 18px; '
                                         'color: #FFFFFF; } QLineEdit#nombreEstilo:focus { border-color: #34D399; }' % ('#0C1320', '#243049')))
        self._nombre.setText(tr('Mi estilo'))
        self._nombre.setFixedWidth(232)
        self._nombre.returnPressed.connect(self._crear)
        cc.addWidget(self._nombre, 0, Qt.AlignmentFlag.AlignVCenter)
        self._b_crear = Boton(tr('Crear mi estilo'), self._crear, tipo='primario', alto=44, ancho=184, tam=14, negrita=True)
        self._b_crear.setFixedWidth(184)
        self._b_crear.setObjectName('crearEstilo')                  # (pastilla verde, como lo elegido en las tarjetas)
        self._b_crear.setStyleSheet(_hoja('QPushButton#crearEstilo { background-color: #34D399; color: #03140D; border: none; border-radius: 22px; } '
                                          'QPushButton#crearEstilo:hover { background-color: #4ADEA9; } '
                                          'QPushButton#crearEstilo:disabled { background-color: #13231F; color: #4E6B62; }'))
        cc.addWidget(self._b_crear, 0, Qt.AlignmentFlag.AlignVCenter)
        capa.addWidget(cab)
        capa.addSpacing(18)

        cuerpo, cb = caja_h(espacio=22)
        # izquierda: las dos rejillas (se desplazan)
        contenido = QWidget()
        cv = QVBoxLayout(contenido)
        cv.setContentsMargins(0, 0, 8, 0)
        cv.setSpacing(0)
        cv.addWidget(_Paso(1, tr('Texto base'), tr('las palabras normales de arriba y abajo · elige uno (o ninguno: cada estilo con el suyo)')))
        cv.addSpacing(10)
        bases = [{'id': b['id'], 'texto': MP.nombre_crea(b), 'efecto': ''} for b in MP.BASES_CREA]
        self._rej_base = _Rejilla(bases, 6, False, self._tocar_base, ancho_min=118)
        cv.addWidget(self._rej_base)
        cv.addSpacing(22)
        cv.addWidget(_Paso(2, tr('Textos principales'), tr('la palabra con efecto · elige los que quieras: se turnan frase a frase')))
        cv.addSpacing(10)
        principales = [{'id': q['id'], 'texto': tr('Estilo {n}', n=q['tema']), 'efecto': tr(q['efecto'])} for q in MP.PRINCIPALES_CREA]
        self._rej_prin = _Rejilla(principales, 5, True, self._tocar_principal, ancho_min=150)
        cv.addWidget(self._rej_prin)
        cv.addStretch(1)
        desp = QScrollArea()
        desp.setWidgetResizable(True)
        desp.setFrameShape(QFrame.Shape.NoFrame)
        desp.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        desp.setWidget(contenido)
        desp.viewport().setAutoFillBackground(False)
        contenido.setAutoFillBackground(False)
        cb.addWidget(desp, 1)
        # derecha: la previa vertical y, debajo, Letra / Color con su panel
        der = QFrame()
        der.setObjectName('columnaPrevia')
        der.setStyleSheet(_hoja('QFrame#columnaPrevia { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0F1828, stop:1 #0A101B); '
                                'border: 1px solid #1B2740; border-radius: 22px; }'))
        der.setFixedWidth(self.ANCHO_DER)
        dv = QVBoxLayout(der)
        dv.setContentsMargins(14, 14, 14, 14)
        dv.setSpacing(12)
        self._previa = _Previa()
        dv.addWidget(self._previa, 1)
        fila, fh = caja_h(espacio=8)
        self._p_letra = _Pestana(tr('Letra'), 'letra', lambda: self._alternar('letra'))
        self._p_color = _Pestana(tr('Color'), 'color', lambda: self._alternar('color'))
        fh.addWidget(self._p_letra, 1)
        fh.addWidget(self._p_color, 1)
        dv.addWidget(fila)
        self._desp = _Desplegable({'letra': self._armar_letra(), 'color': self._armar_color()})
        dv.addWidget(self._desp)
        cb.addWidget(der)
        capa.addWidget(cuerpo, 1)

        self._reloj = QTimer(self)
        self._reloj.setInterval(self.TIC_MS)
        self._reloj.timeout.connect(self._tic)     # las previas solo se mueven mientras la ventana se ve (showEvent / hideEvent)
        self._solo_letras_instaladas()
        self._marcar_cajon()
        self._resumir()

    # ------------------------------------------------------------------ Letra y Color (bajo la previa)
    def _armar_letra(self):
        pag = QWidget()
        v = QVBoxLayout(pag)
        v.setContentsMargins(0, 2, 0, 2)
        v.setSpacing(8)
        self._letras = _ListaLetras(lambda val: self._poner_ajuste('fuente_principal', val), alto_lista=176)    # todas las letras del equipo
        v.addWidget(self._letras)
        v.addWidget(Etiqueta(tr('La letra de arriba y abajo la pone el texto base.'), 11, color='#6B7891', envolver=True))
        return pag

    def _armar_color(self):
        pag = QWidget()
        v = QVBoxLayout(pag)
        v.setContentsMargins(0, 2, 0, 2)
        v.setSpacing(10)
        self._paletas = {}
        for clave, etq, colores in (('color_principal', tr('Texto principal'), COLORES_PRINCIPAL),
                                    ('color_secundario', tr('Arriba y abajo'), COLORES_SECUNDARIO)):
            bloque, bv = caja_v(espacio=2)              # (la paleta lleva 4 px alrededor para el anillo)
            bv.addWidget(Etiqueta(etq, 11.5, color=ETIQUETA))
            paleta = _Paleta(colores, lambda val, c=clave: self._poner_ajuste(c, val), lambda c=clave: self._color_propio(c))
            self._paletas[clave] = paleta
            bv.addWidget(paleta)
            v.addWidget(bloque)
        v.addWidget(Etiqueta(tr('El círculo de colores = los del estilo. Se aplica a todos los captions que elijas.'), 11, color='#6B7891', envolver=True))
        self._volver = Enlace(tr('Volver a la letra y los colores del estilo'), self._volver_al_tema, tam=12, color=ETIQUETA)
        v.addWidget(self._volver, 0, Qt.AlignmentFlag.AlignLeft)
        return pag

    def _solo_letras_instaladas(self):
        """Una letra recordada que ya no está en el equipo (desinstalada, o de otro equipo) vuelve a «Del tema»: así siempre hay una fila marcada
        y al_crear no recibe una letra que Resolve no tiene."""
        quitadas = []
        v = self._ajustes.get('fuente_principal', '')
        if v and not self._letras.instalada(v):
            self._ajustes['fuente_principal'] = ''
            quitadas.append(v.split('|')[0])
        if quitadas:
            try:
                import registro
                registro.aviso(tr('«Crea tu estilo»: la letra {f} no está instalada; se usa la del estilo.', f=', '.join(quitadas)), 'crea_estilo_ui')
            except Exception:
                pass

    def _marcar_cajon(self):
        self._letras.marcar(self._ajustes.get('fuente_principal', ''))
        for clave, paleta in self._paletas.items():
            paleta.poner(self._ajustes.get(clave, ''), self._propios.get(clave, ''))
        self._p_letra.poner(valor=self._ajustes.get('fuente_principal', ''))
        self._p_color.poner(valor=self._ajustes.get('color_principal', ''))
        if self._abierto:                              # (los estilos de la letra elegida cambian el alto del panel)
            QTimer.singleShot(0, self._reajustar)

    def _alternar(self, nombre):
        self._abrir(None if self._abierto == nombre else nombre)

    def _abrir(self, nombre):
        self._abierto = nombre
        self._p_letra.poner(on=(nombre == 'letra'))
        self._p_color.poner(on=(nombre == 'color'))
        if nombre:
            self._desp.mostrar(nombre)
        self._resorte.objetivo = float(self._desp.alto_de(nombre)) if nombre else 0.0
        ui.motor_resortes.pedir(self)

    def _reajustar(self):
        if self._cerrado or not ui.vivo(self) or not self._abierto:
            return
        self._desp.mostrar(self._abierto)
        self._resorte.objetivo = float(self._desp.alto_de(self._abierto))
        ui.motor_resortes.pedir(self)

    def paso_resorte(self, dt):
        if self._cerrado or not ui.vivo(self):
            return False
        sigue = self._resorte.paso(dt)
        if not sigue:
            self._resorte.poner(self._resorte.objetivo)
        self._aplicar_alto(self._resorte.x)
        return sigue

    def _aplicar_alto(self, x):
        alto = max(0, int(round(x)))
        self._desp.setFixedHeight(alto)
        if alto == 0 and not self._abierto:
            self._desp.mostrar(None)

    def _parar_animacion(self):
        """El panel salta a donde iba y sale del motor de resortes (al cerrar u ocultar la ventana)."""
        self._resorte.poner(self._resorte.objetivo)
        try:
            ui.motor_resortes._activos.discard(self)
        except Exception:
            pass
        if not self._cerrado and ui.vivo(self):
            self._aplicar_alto(self._resorte.x)

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

    def _guardar(self):
        guardar_estado({'ajustes': dict(self._ajustes), 'propios': dict(self._propios)})

    def ajustes(self):
        return dict(self._ajustes)

    # ------------------------------------------------------------------ elegir
    def _tocar_base(self, ident):
        self._base = None if self._base == ident else ident
        self._resumir()

    def _tocar_principal(self, ident):
        if ident in self._orden:
            self._orden.remove(ident)
        else:
            self._orden.append(ident)
        self._resumir()

    def base(self):
        return self._base

    def temas(self):
        """Los looks de los principales elegidos, en el orden en que se turnan ('t2:6', 't3:select', 't5'…)."""
        import mezcla_planificador as MP
        return [MP.principal_crea(i)['look'] for i in self._orden if MP.principal_crea(i)]

    def _resumir(self):
        self._rej_base.poner_orden([self._base] if self._base else [])
        self._rej_prin.poner_orden(self._orden)
        self._previa.poner(self._base, self._orden, self._ajustes)
        self._b_crear.setEnabled(bool(self._orden) and not self._creando)

    # ------------------------------------------------------------------ las previas: solo mientras se ven
    def _tic(self):
        visible = self.isVisible() and not self.isMinimized()
        for rej in (self._rej_base, self._rej_prin):
            ve = visible and not rej.visibleRegion().isEmpty()
            rej.poner_visible(ve)
            if ve:
                rej.update()
        self._previa.poner_visible(visible)
        if visible:
            self._previa.tic()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._cerrado and not self._reloj.isActive():
            self._reloj.start()

    def _parar_previas(self):
        try:
            self._reloj.stop()
        except Exception:
            pass
        for rej in (self._rej_base, self._rej_prin):
            rej.poner_visible(False)
        self._previa.cerrar()

    # ------------------------------------------------------------------ crear
    def _llamar_al_crear(self, nombre, temas, ajustes, base):
        """al_crear(nombre, looks, terminado, ajustes, base). (Una app de antes recibe solo los argumentos que acepta: 4 o 3.)"""
        fn = self._al_crear
        try:
            import inspect
            params = list(inspect.signature(fn).parameters.values())
            if any(q.kind == q.VAR_POSITIONAL for q in params):
                n = 5
            else:
                n = sum(q.kind in (q.POSITIONAL_ONLY, q.POSITIONAL_OR_KEYWORD) for q in params)
        except (TypeError, ValueError):
            n = 5
        if n >= 5:
            fn(nombre, temas, self._termino, ajustes, base)
        elif n == 4:
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
        ajustes = dict(self._ajustes)
        ajustes['fuente_secundaria'] = ''                # (la pone crear_estilo con la letra del texto base)
        try:
            self._llamar_al_crear(nombre, self.temas(), ajustes, self._base)
        except Exception:
            ui._registrar_excepcion(*sys.exc_info())
            self._termino(False)

    def _termino(self, ok):
        """Lo llama la app cuando el pack ya está (o falló): si salió bien la ventana se cierra."""
        if not ui.vivo(self):
            return
        self._creando = False
        self._b_crear.setText(tr('Crear mi estilo'))
        self._resumir()
        if ok:
            self.cerrar()

    # ------------------------------------------------------------------ cerrar
    def hideEvent(self, e):
        self._parar_animacion()
        self._parar_previas()
        super().hideEvent(e)

    def closeEvent(self, e):
        self._parar_animacion()
        self._parar_previas()
        self._cerrado = True
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
