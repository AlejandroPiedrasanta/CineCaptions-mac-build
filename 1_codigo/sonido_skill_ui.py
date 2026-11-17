# CineCaptions · By Cinema Productions
# 1_codigo/sonido_skill_ui.py — la página SONIDO (v5.43, diseño A+B elegido por el usuario): editor visual de lo que decidió sonido_skill.
"""
Reemplaza a la página del «AI Sound Director» (ya no se muestra).
v5.67 (el usuario eligió la propuesta C, «Mezclador»): TRES columnas sin desplazar la página: izquierda (Sonido, estado, ESTILO en lista con
radio, OPCIONES, BIBLIOTECA, Aplicar a Resolve / Rehacer), centro (MEZCLA: la línea de tiempo llena el alto, − / + / Ajustar, y el inspector
debajo) y derecha (el móvil con el cuadro del momento y la MÚSICA). El aro de tipos y la tira de momentos siguen construidos y escondidos.
v5.93 (el usuario eligió la C del «Oído»): el inspector es el Oído (sonido_oido.escuchar): «Para revisar» (tocar = arreglar), «Cuadro a
cuadro» (CuadroACuadro) y el sello con tres medidores (SelloOido); rayas de estado bajo cada bloque de la mezcla.
Antes (v5.43-v5.66), de arriba a abajo (todo dentro de un desplazable vertical):

    cabecera     logo, «Sonido», video · tema · cuántos sonidos, pastilla de estado, «Rehacer» y «Aplicar a Resolve»
    estilos (B)  cinco tarjetas (Automático · Elegante · Dinámico · Lista · Cinética), el aro de tipos (cuántos de cada pista) y los
                 interruptores Gancho al inicio / Fiesta o mar
    música       (v5.48) 3 opciones de 02_MUSICA de carpetas distintas + «Sin música», ▶ Escuchar, nivel, crédito CC BY y su interruptor
    (v5.48, pulido A + C elegido por el usuario) la línea muestra solo los carriles que suenan y un carril «Música»; el inspector recorre ◀ Anterior / Siguiente ▶
    editor (A)   el cuadro del video en el momento elegido (con su etiqueta) | el inspector: ícono, tipo y segundo, la onda del sonido,
                 POR QUÉ suena ahí y ▶ Escuchar · Otra variante · ◀/▶ un fotograma · Quitar
    línea (A)    tira de fotogramas, onda de la voz y un carril por pista (bloques de color con su ícono y su onda; línea en el PICO), cabezal
                 rojo en el momento elegido, zoom − / +
    momentos (B) una tarjeta compacta por sonido (miniatura, tipo · segundo, nombre y porqué); tocar = elegir (y mover el editor ahí)

Datos: sonido_skill.resumen (diseño) + sonido_skill.visual (miniaturas, voz, ondas; en caché). Todo lo que cuesta va por correr_en_hilo.
"""
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
from i18n import tr
from qt_kit import Boton, Etiqueta, Interruptor, QColor, Tarjeta, caja_h  # (v5.63: el QColor del tema: los azules siguen a Negro profundo)

MUT = ui.TEXT_MUTED
ESTILOS = (('auto', 'Automático', 'según el estilo'), ('elegante', 'Elegante', 'pocos y suaves'), ('dinamico', 'Dinámico', 'pop en cada clave'),
           ('lista', 'Lista', 'mismo sonido por ítem'), ('cinetica', 'Cinética', 'palabra por palabra'))
NOMBRE_TIPO = {'gancho': 'Gancho', 'acento': 'Acento', 'texto_grande': 'Palabra clave', 'texto_chico': 'Subtítulo', 'aro': 'Aro',
               'corte': 'Corte', 'corte_fuerte': 'Cambio de escena', 'transicion': 'Transición', 'flash': 'Flash', 'logo': 'Logo',
               'barrido_luz': 'Brillo', 'neon': 'Neón', 'icono': 'Ícono', 'tarjeta': 'Tarjeta', 'foto': 'Foto', 'numero_precio': 'Dinero',
               'check': 'Check', 'boton_on': 'Botón ON', 'boton_off': 'Botón OFF', 'cursor_click': 'Click', 'notificacion': 'Notificación',
               'barra_carga': 'Carga', 'pagina': 'Página', 'glitch': 'Glitch', 'tachado': 'Tachado', 'positivo': 'Positivo',
               'negativo': 'Negativo', 'grafica': 'Gráfica', 'pegatina': 'Pegatina', 'sube': 'Tarjeta sube', 'barrido_kit': 'Barrido',
               'tarjeta_kit': 'Tarjeta', 'logo_kit': 'Logo'}
CARRILES = (('AI SFX MOTION', 'Movimiento', '#4589FF'), ('AI SFX IMPACTS', 'Impactos', '#FF5D73'), ('AI SFX TONAL', 'Acentos', '#F5C451'),
            ('AI SFX UI', 'Interfaz', '#2BD4A4'), ('AI SFX TEXTURE', 'Textura', '#B07CFF'))
COLOR = {p: c for p, _, c in CARRILES}
COLOR_MUSICA = '#B19BDA'
FPS = 30.0


def _mmss(t):
    t = float(t or 0)
    return f'{int(t // 60)}:{t % 60:05.2f}'


def color_de(f):
    return QColor(COLOR.get((f or {}).get('pista'), '#2BD4A4'))


def pintar_icono(p, tipo, r, color, grosor=2.0):
    """Íconos de línea simples, dibujados (sin archivos): uno por tipo de evento."""
    p.save()
    p.setPen(QPen(color, grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    if tipo == 'gancho':
        p.drawLine(QPointF(cx, cy + s * .7), QPointF(cx, cy - s * .7))
        p.drawLine(QPointF(cx - s * .55, cy - s * .15), QPointF(cx, cy - s * .7))
        p.drawLine(QPointF(cx + s * .55, cy - s * .15), QPointF(cx, cy - s * .7))
    elif tipo in ('acento', 'positivo'):
        import math
        path = QPainterPath()
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = s * (.8 if k % 2 == 0 else .35)
            pt = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a))
            path.moveTo(pt) if k == 0 else path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)
    elif tipo == 'aro':
        p.drawEllipse(QPointF(cx, cy), s * .8, s * .5)
        p.drawLine(QPointF(cx - s * .35, cy), QPointF(cx + s * .35, cy))
    elif tipo in ('corte', 'corte_fuerte', 'transicion'):
        p.drawEllipse(QPointF(cx - s * .45, cy - s * .45), s * .25, s * .25)
        p.drawEllipse(QPointF(cx - s * .45, cy + s * .45), s * .25, s * .25)
        p.drawLine(QPointF(cx - s * .25, cy - s * .3), QPointF(cx + s * .75, cy + s * .55))
        p.drawLine(QPointF(cx - s * .25, cy + s * .3), QPointF(cx + s * .75, cy - s * .55))
    elif tipo in ('tarjeta', 'foto', 'pagina'):
        p.drawRoundedRect(QRectF(cx - s * .75, cy - s * .5, s * 1.5, s), 3, 3)
        p.drawLine(QPointF(cx - s * .75, cy - s * .15), QPointF(cx + s * .75, cy - s * .15))
    elif tipo == 'numero_precio':
        f = p.font()
        f.setPixelSize(max(8, int(s * 1.5)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, '$')
    elif tipo in ('barra_carga',):
        p.drawRoundedRect(QRectF(cx - s * .8, cy - s * .3, s * 1.6, s * .6), s * .3, s * .3)
        p.drawLine(QPointF(cx - s * .5, cy), QPointF(cx + s * .1, cy))
    elif tipo in ('icono', 'check', 'boton_on', 'boton_off', 'cursor_click', 'notificacion'):
        p.drawRoundedRect(QRectF(cx - s * .65, cy - s * .65, s * 1.3, s * 1.3), s * .35, s * .35)
    else:                                                       # palabra clave: un destello
        p.drawEllipse(QPointF(cx, cy), s * .28, s * .28)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (.7, .7), (-.7, -.7), (.7, -.7), (-.7, .7)):
            p.drawLine(QPointF(cx + dx * s * .5, cy + dy * s * .5), QPointF(cx + dx * s * .85, cy + dy * s * .85))
    p.restore()


def pintar_onda(p, r, barras, color):
    if not barras:
        return
    n = len(barras)
    w = r.width() / n
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    for i, v in enumerate(barras):
        h = max(1.5, float(v) * r.height())
        p.drawRoundedRect(QRectF(r.left() + i * w, r.center().y() - h / 2, max(1.0, w - 1), h), 1, 1)
    p.restore()


def pixmap(ruta, cache={}):          # noqa: B006 — caché de QPixmap por ruta (hilo de la interfaz)
    if not ruta:
        return None
    pm = cache.get(ruta)
    if pm is None:
        pm = QPixmap(str(ruta))
        cache[ruta] = pm
    return pm if not pm.isNull() else None


def miniatura(vis, t):
    m = (vis or {}).get('miniaturas') or []
    return m[max(0, min(len(m) - 1, int(round(float(t or 0)))))] if m else None


# ====================================================================================== piezas
class TarjetaEstilo(QWidget):
    clic = Signal(str)

    def __init__(self, clave, nombre, desc, padre=None):
        super().__init__(padre)
        self.clave, self.nombre, self.desc, self.activa = clave, nombre, desc, False
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _e):
        # v5.67 (propuesta C): una fila de la lista ESTILO con su radio; la elegida con el color de resaltado
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        ac = QColor(ui.ACCENT)
        if self.activa:
            fondo, borde = QColor(ac), QColor(ac)
            fondo.setAlpha(38)
            borde.setAlpha(150)
            p.setPen(QPen(borde, 1.2))
            p.setBrush(fondo)
            p.drawRoundedRect(r, 12, 12)
        c = QPointF(r.left() + 20, r.center().y())
        p.setPen(QPen(ac if self.activa else QColor('#5E6E8C'), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, 7.5, 7.5)
        if self.activa:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ac)
            p.drawEllipse(c, 3.8, 3.8)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(14, peso='negrita'))
        p.drawText(r.adjusted(40, 6, -8, -24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr(self.nombre))
        p.setPen(QColor(MUT))
        p.setFont(ui.fuente(11.5))
        p.drawText(r.adjusted(40, 26, -8, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr(self.desc))
        p.end()

    def mousePressEvent(self, _e):
        self.clic.emit(self.clave)


class AroTipos(QWidget):
    """El aro con cuántos sonidos hay de cada pista, y su leyenda."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.cuenta = {}
        self.setFixedSize(190, 70)

    def poner(self, filas):
        self.cuenta = {}
        for f in filas:
            self.cuenta[f.get('pista')] = self.cuenta.get(f.get('pista'), 0) + 1
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = sum(self.cuenta.values()) or 1
        r = QRectF(6, 8, 54, 54)
        ang = 90 * 16
        for pista, _n, col in CARRILES:
            n = self.cuenta.get(pista, 0)
            if not n:
                continue
            tramo = -int(n / total * 360 * 16)
            p.setPen(QPen(QColor(col), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(r, ang, tramo)
            ang += tramo
        p.setFont(ui.fuente(11))
        y = 8
        for pista, nombre, col in CARRILES:
            n = self.cuenta.get(pista, 0)
            if n:
                p.setPen(QColor(col))
                p.drawText(QRectF(74, y, 120, 14), Qt.AlignmentFlag.AlignLeft, f'● {n} {tr(nombre).lower()}')
                y += 14
        p.end()


class CuadroVideo(QWidget):
    """El cuadro del video en el momento elegido, redondeado, con la etiqueta del sonido."""
    clic = Signal()

    def __init__(self, padre=None):
        super().__init__(padre)
        self.pm, self.etiqueta, self.col = None, '', QColor('#4589FF')
        self.setFixedSize(288, 512)                          # (v5.67, propuesta C: el móvil de la columna derecha; la página lo ajusta al alto)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, pm, etiqueta, col):
        self.pm, self.etiqueta, self.col = pm, etiqueta, col
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        camino = QPainterPath()
        camino.addRoundedRect(r, 20, 20)
        p.setClipPath(camino)
        p.fillRect(r, QColor('#05080F'))
        if self.pm:
            esc = self.pm.scaled(int(r.width()), int(r.height()), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int((r.width() - esc.width()) / 2), int((r.height() - esc.height()) / 2), esc)
        if self.etiqueta:
            p.setFont(ui.fuente(12, peso='negrita'))
            w = p.fontMetrics().horizontalAdvance(self.etiqueta) + 18
            caja = QRectF(10, r.height() - 38, w, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.col)
            p.drawRoundedRect(caja, 7, 7)
            p.setPen(QColor('#0B1220'))
            p.drawText(caja, Qt.AlignmentFlag.AlignCenter, self.etiqueta)
        p.setPen(Qt.PenStyle.NoPen)                             # ▶ en el centro: escuchar
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawEllipse(r.center(), 26, 26)
        p.setBrush(QColor('#FFFFFF'))
        c = r.center()
        tri = QPainterPath()
        tri.moveTo(c.x() - 8, c.y() - 12)
        tri.lineTo(c.x() + 13, c.y())
        tri.lineTo(c.x() - 8, c.y() + 12)
        tri.closeSubpath()
        p.drawPath(tri)
        p.end()

    def mousePressEvent(self, _e):
        self.clic.emit()


class IconoGrande(QWidget):
    def __init__(self, padre=None):
        super().__init__(padre)
        self.tipo, self.col = '', QColor('#4589FF')
        self.setFixedSize(58, 58)

    def poner(self, tipo, col):
        self.tipo, self.col = tipo, col
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fondo = QColor(self.col)
        fondo.setAlpha(40)
        borde = QColor(self.col)
        borde.setAlpha(120)
        p.setPen(QPen(borde, 1))
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 16, 16)
        pintar_icono(p, self.tipo, QRectF(14, 14, 30, 30), self.col, 2.4)
        p.end()


class Onda(QWidget):
    def __init__(self, alto=70, padre=None):
        super().__init__(padre)
        self.barras, self.col = [], QColor('#4589FF')
        self.setFixedHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, barras, col):
        self.barras, self.col = barras or [], col
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0B1424'))
        p.drawRoundedRect(r, 14, 14)
        pintar_onda(p, r.adjusted(16, 10, -16, -10), self.barras, self.col)
        p.end()


# ====================================================================================== el «Oído» (v5.93, propuesta C elegida por el usuario)
# El inspector se vuelve el Oído (sonido_oido.escuchar): a la izquierda lo de siempre + «Para revisar» (4 acciones, tocar = arreglar), en el
# centro «Cuadro a cuadro» (la onda real del sonido sobre una regla de −4 a +12 cuadros, la zona de ±1 cuadro y la de 100 ms, cuándo empieza
# la animación y cuándo suena) y a la derecha un sello con el veredicto y tres medidores (volumen, pico, rango) con frases simples.
VERDE_OK, AMBAR, ROJO = '#24D18F', '#F5C451', '#FF5D73'
COLOR_ESTADO = {'verde': VERDE_OK, 'ambar': AMBAR, 'rojo': ROJO}
ETI = '#7E8CA6'


def _con_alfa(c, a):
    q = QColor(c)
    q.setAlphaF(a)
    return q


def texto_accion(a):
    """(corto, botón) de una acción del Oído, en palabras simples y traducibles."""
    tipo = tr(NOMBRE_TIPO.get(a.get('tipo') or '', str(a.get('tipo') or tr('Sonido')).replace('_', ' ').capitalize()))
    que = a.get('que')
    if que in ('tarde', 'antes'):
        return (tr('{t} {n} ms tarde', t=tipo, n=a.get('ms')) if que == 'tarde' else tr('{t} {n} ms antes', t=tipo, n=a.get('ms')),
                tr('Adelantar') if que == 'tarde' else tr('Atrasar'))
    if que == 'pisa':
        return tr('{t} tapa la voz', t=tipo), tr('Bajar {n} dB', n=f"{abs(float(a.get('db') or 0)):g}")
    if que == 'tapado':
        return tr('{t} tapado por la música', t=tipo), tr('Subir {n} dB', n=f"{abs(float(a.get('db') or 0)):g}")
    if que == 'juntos':
        return tr('Dos sonidos a {n} ms', n=a.get('ms')), tr('Quitar')
    if que == 'pico_video':
        return tr('El video ya satura ({n} dB)', n=f"{float(a.get('db') or 0):+.1f}".replace('-', '−')), tr('Al exportar')
    if que == 'pico':
        return tr('Pico alto ({n} dB)', n=f"{float(a.get('db') or 0):+.1f}".replace('-', '−')), tr('Al exportar')
    if que == 'volumen':
        return tr('Volumen {n} LUFS', n=f"{float(a.get('db') or 0):.0f}".replace('-', '−')), tr('Al exportar')
    return str(a.get('texto') or ''), ''


class ChipAccion(QWidget):
    """Una acción de «Para revisar»: punto de color, tiempo, qué pasa y, en verde, el arreglo. Tocar = arreglar (si tiene arreglo)."""
    clic = Signal(object)

    def __init__(self, padre=None):
        super().__init__(padre)
        self.a, self._encima = None, False
        self.setFixedHeight(26)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def poner(self, a):
        self.a = a
        self.setCursor(Qt.CursorShape.PointingHandCursor if a and a.get('arreglo') else Qt.CursorShape.ArrowCursor)
        self.setVisible(a is not None)
        self.update()

    def enterEvent(self, _e):
        self._encima = True
        self.update()

    def leaveEvent(self, _e):
        self._encima = False
        self.update()

    def mousePressEvent(self, _e):
        if self.a and self.a.get('arreglo'):
            self.clic.emit(self.a)

    def paintEvent(self, _e):
        if not self.a:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        arreglable = bool(self.a.get('arreglo'))
        p.setPen(QPen(QColor('#3A4A66') if self._encima and arreglable else QColor('#222B3B'), 1))
        p.setBrush(QColor('#1A2335') if self._encima and arreglable else QColor('#151C29'))
        p.drawRoundedRect(r, 8, 8)
        x = 10.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLOR_ESTADO.get(self.a.get('estado'), AMBAR)))
        p.drawEllipse(QPointF(x + 4, r.center().y()), 4, 4)
        x += 14
        corto, boton = texto_accion(self.a)
        if self.a.get('tiempo'):
            p.setFont(ui.fuente(12, peso='negrita'))
            p.setPen(QColor('#FFFFFF'))
            t = str(self.a['tiempo'])
            p.drawText(QRectF(x, 0, 60, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, t)
            x += p.fontMetrics().horizontalAdvance(t) + 8
        p.setFont(ui.fuente(12, peso='negrita'))
        ancho_b = p.fontMetrics().horizontalAdvance(boton) if boton else 0
        p.setPen(QColor(VERDE_OK if arreglable else MUT))
        p.drawText(QRectF(r.right() - 10 - ancho_b, 0, ancho_b, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, boton)
        p.setFont(ui.fuente(12))
        p.setPen(QColor('#E8F1FF'))
        hueco = max(0, int(r.right() - 18 - ancho_b - x))
        p.drawText(QRectF(x, 0, hueco, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   p.fontMetrics().elidedText(corto, Qt.TextElideMode.ElideRight, hueco))
        p.end()


def _pastilla(p, r, col, fuerte, suave):
    """Una píldora con punto, texto fuerte (de color) y texto suave, alineada a la derecha de r.right()."""
    p.setFont(ui.fuente(12, peso='negrita'))
    a1 = p.fontMetrics().horizontalAdvance(fuerte)
    p.setFont(ui.fuente(12))
    a2 = p.fontMetrics().horizontalAdvance(suave) if suave else 0
    ancho = 10 + 8 + 6 + a1 + (6 + a2 if suave else 0) + 10
    caja = QRectF(r.right() - ancho, r.top(), ancho, r.height())
    p.setPen(QPen(_con_alfa(col, .4), 1))
    p.setBrush(_con_alfa(col, .12))
    p.drawRoundedRect(caja, caja.height() / 2, caja.height() / 2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(col))
    p.drawEllipse(QPointF(caja.left() + 14, caja.center().y()), 4, 4)
    p.setFont(ui.fuente(12, peso='negrita'))
    p.setPen(QColor(col))
    p.drawText(QRectF(caja.left() + 24, caja.top(), a1, caja.height()), Qt.AlignmentFlag.AlignVCenter, fuerte)
    if suave:
        p.setFont(ui.fuente(12))
        p.setPen(QColor(MUT))
        p.drawText(QRectF(caja.left() + 30 + a1, caja.top(), a2, caja.height()), Qt.AlignmentFlag.AlignVCenter, suave)


class CuadroACuadro(QWidget):
    """«Cuadro a cuadro»: la onda real del sonido elegido colocado como en Resolve, sobre una regla de cuadros (−4 a +12) desde el 1.er cuadro
    de su animación; zona verde = ±1 cuadro de donde debe sonar, ámbar = hasta 100 ms; línea blanca = empieza la animación; discontinua =
    suena. Los datos los da sonido_oido.escuchar (s['onda'], 'suena_ms', 'esperado_ms', 'estado')."""
    F0, F1 = -4, 12

    def __init__(self, padre=None):
        super().__init__(padre)
        self.s, self.fps, self.col, self.aviso = None, 30.0, QColor('#B07CFF'), ''
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def poner(self, s, fps=None, col=None, aviso=''):
        self.s, self.fps, self.aviso = s, float(fps or 30.0), aviso
        if col is not None:
            self.col = col
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0B1424'))
        p.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)
        p.setFont(ui.fuente(11, peso='negrita'))
        p.setPen(QColor(ETI))
        titulo = tr('Cuadro a cuadro').upper()
        p.drawText(QRectF(14, 6, w, 20), Qt.AlignmentFlag.AlignVCenter, titulo)
        x = 14 + p.fontMetrics().horizontalAdvance(titulo) + 14
        p.setFont(ui.fuente(10))
        for col, a, txt in ((VERDE_OK, .45, tr('±1 cuadro')), (AMBAR, .3, tr('hasta 100 ms'))):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_con_alfa(col, a))
            p.drawRoundedRect(QRectF(x, 12, 10, 8), 2, 2)
            p.setPen(QColor(MUT))
            p.drawText(QRectF(x + 14, 6, 120, 20), Qt.AlignmentFlag.AlignVCenter, txt)
            x += 14 + p.fontMetrics().horizontalAdvance(txt) + 12
        s = self.s
        if not s:
            p.setFont(ui.fuente(12))
            p.setPen(QColor(MUT))
            p.drawText(QRectF(0, 30, w, h - 30), Qt.AlignmentFlag.AlignCenter, self.aviso or tr('Elige un sonido'))
            p.end()
            return
        estado = s.get('estado') or 'verde'
        suena = s.get('suena_ms')
        col_e = COLOR_ESTADO.get(estado, VERDE_OK)
        fuerte = {'verde': tr('Al cuadro'), 'ambar': tr('Casi'), 'rojo': tr('Fuera de cuadro')}.get(estado, '')
        if suena is None:
            fuerte, col_e = tr('Sin sonido'), ROJO
        _pastilla(p, QRectF(0, 6, w - 14, 22), col_e, fuerte, '' if suena is None else f'{float(suena):+.0f} ms')
        gx0, gx1, gy0, gy1 = 16.0, w - 16.0, 52.0, h - 26.0      # (las etiquetas de las marcas van en su propia fila, encima)
        if gx1 - gx0 < 40 or gy1 - gy0 < 20:
            p.end()
            return

        def fx(fr):
            return gx0 + (fr - self.F0) / (self.F1 - self.F0) * (gx1 - gx0)
        esp = float(s.get('esperado_ms') or 0) / 1000.0 * self.fps     # dónde debe sonar, en cuadros
        a100 = 0.1 * self.fps
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_con_alfa(AMBAR, .07))
        p.drawRect(QRectF(fx(max(self.F0, esp - a100)), gy0, fx(min(self.F1, esp + a100)) - fx(max(self.F0, esp - a100)), gy1 - gy0))
        p.setBrush(_con_alfa(VERDE_OK, .13))
        p.drawRect(QRectF(fx(esp - 1), gy0, fx(esp + 1) - fx(esp - 1), gy1 - gy0))
        p.setFont(ui.fuente(10))
        for fr in range(self.F0, self.F1 + 1):
            xx = fx(fr)
            p.setPen(QPen(QColor(255, 255, 255, 10), 1))
            p.drawLine(QPointF(xx, gy0), QPointF(xx, gy1))
            p.setPen(QPen(QColor('#4D5C77'), 1))
            p.drawLine(QPointF(xx, gy1), QPointF(xx, gy1 + (6 if fr % 5 else 9)))
            if fr % 2 == 0:
                p.setPen(QColor(MUT))
                p.drawText(QRectF(xx - 14, gy1 + 9, 28, 14), Qt.AlignmentFlag.AlignCenter, f"{'+' if fr > 0 else ''}{fr}")
        onda = s.get('onda') or []
        if onda:
            mid, amp = (gy0 + gy1) / 2, (gy1 - gy0) / 2 - 4
            paso = (self.F1 - self.F0) / len(onda)
            ancho = max(1.2, (fx(self.F0 + paso) - fx(self.F0)) * 0.7)
            barra = QColor(self.col)
            barra.setAlphaF(.9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(barra)
            for k, v in enumerate(onda):
                if v > 0.005:
                    alto = max(1.0, 2 * float(v) * amp)
                    p.drawRoundedRect(QRectF(fx(self.F0 + k * paso), mid - alto / 2, ancho, alto), 1, 1)
        xa = fx(0)
        fila = QRectF(gx0, gy0 - 20, gx1 - gx0, 16)
        p.setPen(QPen(QColor('#FFFFFF'), 2))
        p.drawLine(QPointF(xa, fila.top() + 2), QPointF(xa, gy1))
        p.setFont(ui.fuente(11, peso='negrita'))
        p.drawText(QRectF(gx0, fila.top(), xa - 6 - gx0, fila.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   tr('empieza la animación'))
        if suena is not None:
            xs = fx(max(self.F0, min(self.F1, float(suena) / 1000.0 * self.fps)))
            p.setPen(QPen(QColor('#0B1424'), 5))                  # contorno oscuro: se lee aunque caiga sobre la onda
            p.drawLine(QPointF(xs, gy0), QPointF(xs, gy1))
            pen = QPen(QColor(col_e), 2, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([2, 1.5])
            p.setPen(pen)
            p.drawLine(QPointF(xs, fila.center().y()), QPointF(xs, gy1))
            p.setPen(QColor(col_e))
            p.drawText(QRectF(max(xs, xa) + 6, fila.top(), 120, fila.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       tr('suena'))
        p.end()


class SelloOido(QWidget):
    """El veredicto como un sello (LISTO / CASI / REVISAR y cuántas cosas revisar) y tres medidores con su zona buena y una frase simple."""
    # (nombre, clave en 'mezcla', escala min–max, zona buena, formato)
    MEDIDORES = (('Volumen', 'lufs', (-30.0, -6.0), (-16.0, -12.0), '{:.1f}'), ('Pico', 'tp_db', (-12.0, 3.0), (-12.0, -1.0), '{:.1f} dB'),
                 ('Rango', 'lra', (0.0, 15.0), (2.0, 10.0), '{:.1f} LU'))

    def __init__(self, padre=None):
        super().__init__(padre)
        self.d, self.cargando = None, False
        self.setFixedWidth(288)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def poner(self, d, cargando=False):
        self.d, self.cargando = d, cargando
        self.update()

    @staticmethod
    def nota(clave, v):
        if clave == 'lufs':
            return tr('bien para redes') if -16 <= v <= -12 else (tr('bajo para redes') if v < -16 else tr('alto para redes'))
        if clave == 'tp_db':
            return tr('sin saturar') if v <= -1 else tr('satura: limita al exportar')
        return tr('cómodo en el móvil') if v <= 10 else tr('mucha diferencia fuerte / suave')

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0B1424'))
        p.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)
        d = self.d or {}
        nivel = d.get('nivel')
        col = {0: VERDE_OK, 1: AMBAR, 2: ROJO}.get(nivel, '#5A6B87')
        palabra = {0: tr('Listo'), 1: tr('Casi'), 2: tr('Revisar')}.get(nivel, '…').upper()
        n = len([a for a in d.get('acciones') or []])
        abajo = (tr('Escuchando…') if self.cargando else tr('Sin datos')) if nivel is None else \
            (tr('{n} por revisar', n=n) if n else tr('todo en orden'))
        r = max(30.0, min(56.0, h / 2 - 12))
        cx, cy = 14 + r, h / 2
        p.setPen(QPen(QColor(col), 2.5))
        p.setBrush(_con_alfa(col, .07))
        p.drawEllipse(QPointF(cx, cy), r, r)
        pen = QPen(_con_alfa(col, .5), 1, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([2, 4])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r - 7, r - 7)
        p.save()
        p.translate(cx, cy)
        p.rotate(-8)
        f = ui.fuente(24, peso='extra')
        p.setFont(f)
        while p.fontMetrics().horizontalAdvance(palabra) > 2 * r - 20 and f.pixelSize() > 12:
            f.setPixelSize(f.pixelSize() - 1)
            p.setFont(f)
        p.setPen(QColor(col))
        p.drawText(QRectF(-r, -r * .55, 2 * r, r * .7), Qt.AlignmentFlag.AlignCenter, palabra)
        p.setFont(ui.fuente(11))
        p.setPen(QColor('#E8F1FF'))
        p.drawText(QRectF(-r + 6, r * .12, 2 * r - 12, 18), Qt.AlignmentFlag.AlignCenter, abajo)
        p.restore()
        mx = cx + r + 16
        ancho = w - mx - 16
        mezcla = d.get('mezcla') or {}
        alto_m = max(44.0, (h - 24) / 3)
        for k, (nombre, clave, (lo, hi), (z0, z1), fmt) in enumerate(self.MEDIDORES):
            y = 14 + k * alto_m
            v = mezcla.get(clave)
            p.setFont(ui.fuente(10, peso='negrita'))
            p.setPen(QColor(ETI))
            p.drawText(QRectF(mx, y, ancho, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, tr(nombre).upper())
            p.setFont(ui.fuente(12, peso='negrita'))
            p.setPen(QColor('#E8F1FF'))
            p.drawText(QRectF(mx, y, ancho, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       '—' if v is None else fmt.format(float(v)).replace('-', '−').replace('.', ','))
            barra = QRectF(mx, y + 21, ancho, 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#1E2A42'))
            p.drawRoundedRect(barra, 2.5, 2.5)
            fz = lambda val: max(0.0, min(1.0, (val - lo) / (hi - lo)))   # noqa: E731
            p.setBrush(_con_alfa(VERDE_OK, .22))
            p.drawRoundedRect(QRectF(barra.left() + fz(z0) * ancho, barra.top(), (fz(z1) - fz(z0)) * ancho, 5), 2.5, 2.5)
            if v is not None:
                bien = z0 <= float(v) <= z1 or (clave == 'lra' and float(v) < z0)
                c2 = VERDE_OK if bien else (ROJO if clave == 'tp_db' else AMBAR)
                frac = fz(float(v))
                p.setBrush(QColor(c2))
                p.drawRoundedRect(QRectF(barra.left(), barra.top(), frac * ancho, 5), 2.5, 2.5)
                p.setBrush(QColor('#FFFFFF'))
                p.drawRoundedRect(QRectF(barra.left() + frac * ancho - 1.5, barra.top() - 3, 3, 11), 1.5, 1.5)
                p.setFont(ui.fuente(10))
                p.setPen(QColor(MUT))
                p.drawText(QRectF(mx, y + 30, ancho, 14), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.nota(clave, float(v)))
        p.end()


class LineaTiempo(QWidget):
    """Editor (A): tira de fotogramas, voz, CAPTIONS (cada bloque con su palabra clave y si suena), un carril por pista y la música;
    clic en un bloque o en un caption con sonido = seleccionado(índice en filas)."""
    seleccionado = Signal(int)
    IZQ, TIRA, VOZ, CAP, ALTO, REGLA = 108, 56, 38, 46, 34, 22
    TOL_CAPTION = 0.06                                      # un sonido a menos de esto del momento de la palabra clave es «su» sonido

    def __init__(self, padre=None):
        super().__init__(padre)
        self.filas, self.vis, self.sel, self.pps, self.dur = [], {}, -1, 70.0, 5.0
        self.musica = None                                  # {'titulo', 'onda', 'dur'}: un carril más, debajo de los SFX
        self.captions = []                                  # [{'ini', 'fin', 'texto', 'clave', 't'}] de sonido_skill.bloques_captions
        self._cajas_cap = []
        self.carriles = list(CARRILES)
        self._cajas = []
        self.estados = {}                                   # v5.93 (Oído): {índice: 'verde'|'ambar'|'rojo'} → raya de color bajo cada bloque
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def poner(self, filas, vis, duracion, musica=None, captions=None):
        self.filas, self.vis, self.musica, self.captions = filas or [], vis or {}, musica, captions or []
        usadas = {f.get('pista') for f in self.filas}
        self.carriles = [c for c in CARRILES if c[0] in usadas] or list(CARRILES[:1])   # solo las pistas que suenan
        self.dur = max([float(duracion or 0)] + [float(f.get('segundo') or 0) + 1.5 for f in self.filas] + [5.0])
        self._medir()

    def zoom(self, factor):
        self.pps = max(20.0, min(320.0, self.pps * factor))
        self._medir()

    def ajustar_alto(self, alto):
        """v5.67 (propuesta C, la mezcla protagonista): reparte el alto disponible: la voz se lleva ~un tercio y cada carril lo demás
        (con topes, para que nunca queden ni enanos ni gigantes)."""
        fijo = self.TIRA + (self.CAP if self.captions else 0) + self.REGLA + 30
        libre = max(0.0, float(alto) - fijo)
        n = max(1, self.n_carriles())
        self.VOZ = int(max(38, min(104, libre * 0.34)))     # v5.93 (Oído, C): la voz hasta 104 (antes 170): el inspector crece
        self.ALTO = int(max(34, min(112, (libre - self.VOZ) / n)))
        self._medir()

    def ajustar_ancho(self, ancho):
        """v5.67: «Ajustar»: todo el video cabe en el ancho visible."""
        self.pps = max(20.0, min(320.0, (float(ancho) - self.IZQ - 34) / max(1.0, self.dur)))
        self._medir()

    def n_carriles(self):
        return len(self.carriles) + (1 if self.musica else 0)

    def alto_total(self):
        return int(self.TIRA + self.VOZ + (self.CAP if self.captions else 0) + self.n_carriles() * self.ALTO + self.REGLA + 24)

    def sonido_de(self, c):
        """Índice del sonido que cae en la palabra clave de ese caption (o -1)."""
        cerca = [(abs(float(f.get('segundo') or 0) - c['t']), i) for i, f in enumerate(self.filas)]
        d, i = min(cerca or [(9.0, -1)])
        return i if d <= self.TOL_CAPTION else -1

    def _medir(self):
        self.setFixedSize(int(self.IZQ + self.dur * self.pps + 30), self.alto_total())
        self.update()

    def x_de(self, t):
        return self.IZQ + float(t) * self.pps

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        p.fillRect(QRectF(0, 0, w, h), QColor('#0B1424'))
        p.setFont(ui.fuente(12))
        # tira de fotogramas: uno por segundo (o cada 2 / 5 si el zoom es chico). v5.67: no en la C (TIRA 0: el cuadro va en el móvil)
        y = 6
        if self.TIRA > 0:
            p.setPen(QColor(MUT))
            p.drawText(QRectF(12, y, self.IZQ - 16, self.TIRA - 8), Qt.AlignmentFlag.AlignVCenter, tr('Video'))
            paso = 1 if self.pps >= 50 else 2 if self.pps >= 28 else 5
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self.IZQ, y, self.dur * self.pps, self.TIRA - 8), 8, 8)
            p.save()
            p.setClipPath(clip)
            for s in range(0, int(self.dur) + 1, paso):
                pm = pixmap(miniatura(self.vis, s))
                if pm:
                    ancho = self.pps * paso - 2
                    esc = pm.scaled(int(ancho), int(self.TIRA - 8), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    p.setOpacity(.85)
                    p.drawPixmap(QRectF(self.x_de(s), y, ancho, self.TIRA - 8), esc,
                                 QRectF((esc.width() - ancho) / 2, (esc.height() - (self.TIRA - 8)) / 2, ancho, self.TIRA - 8))
            p.restore()
        # voz (v5.67: con el verde de la voz y su fondo, como un carril más)
        y = self.TIRA + 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 8))
        p.drawRoundedRect(QRectF(self.IZQ, y, w - self.IZQ - 14, self.VOZ), 10, 10)
        p.setPen(QColor(ui.tc('#7FE0B5')))
        p.setFont(ui.fuente(13, peso='negrita'))
        p.drawText(QRectF(12, y, self.IZQ - 16, self.VOZ), Qt.AlignmentFlag.AlignVCenter, tr('Voz'))
        p.setFont(ui.fuente(12))
        voz = self.vis.get('voz') or []
        dv = float(self.vis.get('duracion') or self.dur) or self.dur
        onda_voz = QColor(ui.tc('#7FE0B5'))
        onda_voz.setAlpha(200)
        pintar_onda(p, QRectF(self.IZQ + 4, y + 8, dv * self.pps - 8, self.VOZ - 16), voz, onda_voz)
        # captions: cada bloque con su texto; la palabra clave en blanco y su marca (verde = suena, gris = sin sonido)
        self._cajas_cap = []
        if self.captions:
            yc = self.TIRA + self.VOZ + 4
            p.setPen(QColor('#E0EBFB'))
            p.drawText(QRectF(12, yc, self.IZQ - 16, self.CAP - 6), Qt.AlignmentFlag.AlignVCenter, tr('Captions'))
            for c in self.captions:
                i = self.sonido_de(c)
                caja = QRectF(self.x_de(c['ini']), yc + 3, max(18.0, (c['fin'] - c['ini']) * self.pps - 3), self.CAP - 12)
                self._cajas_cap.append((caja, i))
                activa = i >= 0 and i == self.sel
                p.setPen(QPen(QColor('#FFFFFF'), 1.6) if activa else QPen(QColor('#22324F'), 1))
                p.setBrush(QColor('#16233D'))
                p.drawRoundedRect(caja, 7, 7)
                xt = self.x_de(c['t'])
                col = QColor('#2BD4A4') if i >= 0 else QColor('#5A6B87')
                p.setPen(QPen(col, 2))
                p.drawLine(QPointF(xt, caja.top() + 3), QPointF(xt, caja.bottom() - 3))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawEllipse(QPointF(xt, caja.top() + 3), 3.2, 3.2)
                texto = QRectF(caja.left() + 8, caja.top(), caja.width() - 12, caja.height())
                if texto.width() > 16:
                    clave = c.get('clave') or ''
                    p.setFont(ui.fuente(11, peso='negrita'))
                    fm = p.fontMetrics()
                    ancho_clave = min(fm.horizontalAdvance(clave), int(texto.width())) if clave else 0
                    p.setPen(QColor('#FFFFFF'))
                    if clave:
                        p.drawText(texto, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(clave, Qt.TextElideMode.ElideRight, int(texto.width())))
                    resto = texto.adjusted(ancho_clave + (6 if clave else 0), 0, 0, 0)
                    if resto.width() > 24:
                        p.setFont(ui.fuente(11))
                        p.setPen(QColor(MUT))
                        p.drawText(resto, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                   p.fontMetrics().elidedText(c.get('texto') or '', Qt.TextElideMode.ElideRight, int(resto.width())))
            p.setFont(ui.fuente(12))
        # carriles de sonido
        y0 = self.TIRA + self.VOZ + 6 + (self.CAP if self.captions else 0)
        fila_de = {c[0]: k for k, c in enumerate(self.carriles)}
        for k, (_pista, nombre, col) in enumerate(self.carriles):
            yy = y0 + k * self.ALTO
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 8))
            p.drawRoundedRect(QRectF(self.IZQ, yy, w - self.IZQ - 14, self.ALTO - 6), 10, 10)
            p.setPen(QColor(col))
            p.setFont(ui.fuente(13, peso='negrita'))
            p.drawText(QRectF(12, yy, self.IZQ - 16, self.ALTO - 6), Qt.AlignmentFlag.AlignVCenter, tr(nombre))
            p.setFont(ui.fuente(12))
        if self.musica:                                     # la música: una barra a lo largo de todo el video, con su onda y su nombre
            yy = y0 + len(self.carriles) * self.ALTO
            p.setPen(QColor(COLOR_MUSICA))
            p.drawText(QRectF(12, yy, self.IZQ - 16, self.ALTO - 6), Qt.AlignmentFlag.AlignVCenter, tr('Música'))
            barra = QRectF(self.IZQ, yy + 3, float(self.musica.get('dur') or self.dur) * self.pps, self.ALTO - 12)
            fondo = QColor(COLOR_MUSICA)
            fondo.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fondo)
            p.drawRoundedRect(barra, 7, 7)
            pintar_onda(p, barra.adjusted(8, 4, -8, -4), self.musica.get('onda') or [], QColor(COLOR_MUSICA))
            p.setFont(ui.fuente(11, peso='negrita'))
            texto = '♪  ' + str(self.musica.get('titulo') or '')
            caja = QRectF(barra.left() + 8, barra.top() + 3, p.fontMetrics().horizontalAdvance(texto) + 16, barra.height() - 6)
            p.setBrush(QColor('#0B1424'))
            p.drawRoundedRect(caja, 6, 6)
            p.setPen(QColor(COLOR_MUSICA))
            p.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)
            p.setFont(ui.fuente(12))
        self._cajas = []
        ondas = self.vis.get('ondas') or {}
        for i, f in enumerate(self.filas):
            k = fila_de.get(f.get('pista'), 3)
            col = color_de(f)
            ini = float(f.get('ini') if f.get('ini') is not None else f.get('segundo') or 0)
            caja = QRectF(self.x_de(ini), y0 + k * self.ALTO + 3, max(22.0, float(f.get('dur') or 0.3) * self.pps), self.ALTO - 12)
            self._cajas.append((caja, i))
            sel = i == self.sel
            relleno = QColor(col)
            relleno.setAlpha(255 if sel else 165)
            p.setPen(QPen(QColor('#FFFFFF'), 2) if sel else Qt.PenStyle.NoPen)
            p.setBrush(relleno)
            p.drawRoundedRect(caja, 7, 7)
            pintar_icono(p, f.get('tipo'), QRectF(caja.left() + 4, caja.top() + 3, caja.height() - 6, caja.height() - 6), QColor('#0B1220'), 1.6)
            if caja.width() > 30:
                pintar_onda(p, QRectF(caja.left() + caja.height(), caja.top() + 5, caja.width() - caja.height() - 4, caja.height() - 10),
                            ondas.get(f.get('wav')) or [], QColor(11, 18, 32, 140))
            est = self.estados.get(i)
            if est:                                         # v5.93 (Oído): raya de su estado; ámbar / rojo además con borde que brilla
                ce = QColor(COLOR_ESTADO.get(est, VERDE_OK))
                if est != 'verde':
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(_con_alfa(ce, .28), 6))
                    p.drawRoundedRect(caja.adjusted(-3, -3, 3, 3), 9, 9)
                    p.setPen(QPen(ce, 2))
                    p.drawRoundedRect(caja.adjusted(-3, -3, 3, 3), 9, 9)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(ce if est != 'verde' else _con_alfa(ce, .75))
                p.drawRoundedRect(QRectF(caja.left() + 2, caja.bottom() + 3, max(6.0, caja.width() - 4), 3), 1.5, 1.5)
        # regla y cabezal
        p.setPen(QColor(MUT))
        p.setFont(ui.fuente(11))
        yr = y0 + self.n_carriles() * self.ALTO + 4
        for s in range(0, int(self.dur) + 1, 2 if self.pps >= 40 else 5):
            p.drawText(QRectF(self.x_de(s) - 20, yr, 40, 16), Qt.AlignmentFlag.AlignCenter, _mmss(s)[:-3])
        if 0 <= self.sel < len(self.filas):                 # v5.67 (C): cabezal blanco con su tiempo arriba
            seg = float(self.filas[self.sel].get('segundo') or 0)
            x = self.x_de(seg)
            p.setPen(QPen(QColor('#FFFFFF'), 2))
            p.drawLine(QPointF(x, 18), QPointF(x, yr))
            p.setFont(ui.fuente(11, peso='negrita'))
            texto = _mmss(seg)
            ancho = p.fontMetrics().horizontalAdvance(texto) + 14
            caja = QRectF(min(max(2.0, x - ancho / 2), w - ancho - 2), 0, ancho, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#FFFFFF'))
            p.drawRoundedRect(caja, 6, 6)
            p.setPen(QColor('#0B1222'))
            p.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)
        p.end()

    def mousePressEvent(self, ev):
        pos = ev.position()
        for caja, i in reversed(self._cajas):
            if caja.contains(pos):
                self.seleccionado.emit(i)
                return
        for caja, i in self._cajas_cap:
            if caja.contains(pos) and i >= 0:
                self.seleccionado.emit(i)
                return


class TarjetaMomento(QWidget):
    """Momentos (v5.48, compactos; el usuario eligió A + C): miniatura a la izquierda, tipo · segundo, archivo y porqué. Tocar = elegir."""
    clic = Signal(int)
    ANCHO, ALTO = 268, 78

    def __init__(self, i, f, pm, padre=None):
        super().__init__(padre)
        self.i, self.f, self.pm, self.activa = i, f, pm, False
        self.setFixedSize(self.ANCHO, self.ALTO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, _e):
        self.clic.emit(self.i)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        col = color_de(self.f)
        p.setPen(QPen(col, 2) if self.activa else QPen(QColor('#1C2A45'), 1))
        p.setBrush(QColor('#0F1A2F'))
        p.drawRoundedRect(r, 14, 14)
        foto = QRectF(r.left() + 7, r.top() + 7, 50, r.height() - 14)
        camino = QPainterPath()
        camino.addRoundedRect(foto, 9, 9)
        p.save()
        p.setClipPath(camino)
        p.fillRect(foto, QColor('#000000'))
        if self.pm:
            esc = self.pm.scaled(int(foto.width()), int(foto.height()), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(foto, esc, QRectF((esc.width() - foto.width()) / 2, (esc.height() - foto.height()) / 2, foto.width(), foto.height()))
        p.restore()
        x = foto.right() + 12
        ancho = r.right() - x - 10
        p.setPen(col)
        p.setFont(ui.fuente(12, peso='negrita'))
        tipo = tr(NOMBRE_TIPO.get(self.f.get('tipo'), self.f.get('tipo') or ''))
        p.drawText(QRectF(x, r.top() + 9, ancho, 17), Qt.AlignmentFlag.AlignLeft, f"{tipo}  ·  {_mmss(self.f.get('segundo'))[:-1]}")
        p.setPen(QColor('#E8F1FF'))
        p.setFont(ui.fuente(12))
        nombre = Path(self.f.get('archivo') or '').stem.split(' - ', 1)[-1]
        p.drawText(QRectF(x, r.top() + 29, ancho, 16), Qt.AlignmentFlag.AlignLeft, p.fontMetrics().elidedText(nombre, Qt.TextElideMode.ElideRight, int(ancho)))
        p.setPen(QColor(MUT))
        p.setFont(ui.fuente(11))
        porque = (self.f.get('por_que') or '').replace('caption ', '')
        p.drawText(QRectF(x, r.top() + 49, ancho, 16), Qt.AlignmentFlag.AlignLeft, p.fontMetrics().elidedText(porque, Qt.TextElideMode.ElideRight, int(ancho)))
        p.end()


# ====================================================================================== la página
class PaginaSonido(QWidget):
    """La página SONIDO. `video` = función que da el video de Inicio; `offset` = desplazamiento de GO en el timeline (Aplicar)."""

    def __init__(self, padre=None, video=None, offset=None, por_partes=False):
        super().__init__(padre)
        self._video_fn = video or (lambda: '')
        self._offset_fn = offset or (lambda: 0)
        self._ocupado = False
        self._res, self._vis, self._sel = {}, {}, -1
        self._momentos = []
        # v5.83 (el usuario: «utiliza todos los hilos y memoria para que CineCaptions sea fluido y rápido»): se arma con un generador; con
        # por_partes=True quien la crea la termina a trozos (armar_paso) entre cuadro y cuadro de Inicio; si no, entera aquí, como siempre
        self._pasos = self._armar()
        if not por_partes:
            self.completar()

    def armar_paso(self):
        """v5.83: un trozo del armado (unos ms); False cuando ya está entera."""
        if self._pasos is None:
            return False
        try:
            next(self._pasos)
            return True
        except StopIteration:
            self._pasos = None
            return False
        except BaseException:
            self._pasos = None
            raise

    def completar(self):
        while self.armar_paso():
            pass

    def _armar(self):
        import sonido_skill as S
        prefs = S._prefs()
        # v5.67 (el usuario eligió la propuesta C, «Mezclador», entre tres maquetas): TRES columnas, sin desplazar la página
        #   izquierda  «Sonido», video · sonidos, estado; ESTILO (lista con radio), OPCIONES (gancho, fiesta o mar, música, sonido en los
        #              próximos GO), BIBLIOTECA y abajo «Aplicar a Resolve» / «Rehacer»
        #   centro     MEZCLA: la línea de tiempo protagonista (carriles altos que llenan el alto: voz, captions, una pista por tipo y la música;
        #              − / + / Ajustar) y, debajo, el inspector del momento elegido
        #   derecha    el móvil con el cuadro del momento y la MÚSICA (3 opciones de la biblioteca, sin música, escuchar, crédito)
        # Lo que no está en la C (el aro de tipos y la tira de momentos) sigue construido y escondido: lo leen los mismos métodos.
        externa = QHBoxLayout(self)
        externa.setContentsMargins(0, 0, 0, 0)
        externa.setSpacing(16)

        def eti(texto):
            e = Etiqueta(texto.upper(), 11, peso='negrita', color='#7E8CA6')
            return e

        def columna(ancho, margenes):
            t = Tarjeta(self, espacio=10, margenes=margenes)        # (v5.84: hija de la página desde ya: re-colgarla llena costaba ms)
            t.setFixedWidth(ancho)
            return t

        # ---- izquierda
        izq = columna(330, (20, 20, 20, 18))
        desp_izq = QScrollArea(izq)                          # (en ventanas bajas la columna se desplaza sola; los botones quedan abajo)
        desp_izq.setWidgetResizable(True)
        desp_izq.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desp_izq.setStyleSheet('QScrollArea{background:transparent;border:none}')
        desp_izq.viewport().setStyleSheet('background:transparent')
        dentro = QWidget()
        dentro.setStyleSheet('background:transparent')
        desp_izq.setWidget(dentro)                           # (v5.84: VACÍA y luego se llena: puesta llena bajo su hoja de estilo, ~10 ms de golpe)
        ci = QVBoxLayout(dentro)
        ci.setContentsMargins(0, 0, 0, 0)
        ci.setSpacing(8)
        cab, cc = caja_h(espacio=12)
        logo = Etiqueta('')
        try:                                                 # (v5.83: el PNG de 1024 px ya decodificado en otro hilo al abrir: vistas_slider)
            import sfx_rules
            import vistas_slider
            img = vistas_slider.imagen_de(sfx_rules.base_recursos() / 'logo_cinecaptions.png')
            if not img.isNull():
                from PySide6.QtGui import QGuiApplication
                dpr = QGuiApplication.instance().devicePixelRatio()          # (como ui.pixmap_de_archivo)
                fis = max(1, int(round(30 * dpr)))
                pm = QPixmap.fromImage(img.scaled(fis, fis, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                pm.setDevicePixelRatio(dpr)
                logo.setPixmap(pm)
        except Exception:
            pass
        cc.addWidget(logo)
        cc.addWidget(Etiqueta(tr('Sonido'), 24, peso='extra', color='#FFFFFF'), 1)
        ci.addWidget(cab)
        self._lbl_video = ui.Elidida('', 13, color=MUT)
        ci.addWidget(self._lbl_video)
        self._lbl_pend = Etiqueta('', 12, color='#F5C451')
        ci.addWidget(self._lbl_pend)
        self._lbl_estado = Etiqueta(tr('Haz GO con un video: aquí ves qué sonido va en cada momento y por qué.'), 12, color=MUT, envolver=True)
        ci.addWidget(self._lbl_estado)
        ci.addSpacing(6)
        yield
        ci.addWidget(eti(tr('Estilo')))
        self._estilos = {}
        actual = prefs.get(S.PREF_ESTILO) or 'auto'
        for clave, nombre, desc in ESTILOS:
            t = TarjetaEstilo(clave, nombre, desc)
            t.activa = clave == actual
            t.clic.connect(self._cambio_estilo)
            self._estilos[clave] = t
            ci.addWidget(t)
        ci.addSpacing(8)
        yield
        ci.addWidget(eti(tr('Opciones')))
        import sonido_musica as M
        self._var_gancho = ui.BooleanVar(prefs.get(S.PREF_GANCHO, True) is not False)
        self._var_fiesta = ui.BooleanVar(prefs.get(S.PREF_FIESTA, False) is True)
        self._var_musica = ui.BooleanVar(M.activa(prefs))
        self._var_on = ui.BooleanVar(S.activo(prefs))
        for texto, var, cmd in ((tr('Gancho al inicio'), self._var_gancho, lambda: self._pref(S.PREF_GANCHO, bool(self._var_gancho.get()))),
                                (tr('Fiesta o mar'), self._var_fiesta, lambda: self._pref(S.PREF_FIESTA, bool(self._var_fiesta.get()))),
                                (tr('Música en los próximos GO'), self._var_musica, lambda: self._pref(M.PREF_MUSICA, bool(self._var_musica.get()))),
                                (tr('Sonido en los próximos GO'), self._var_on, lambda: self._pref(S.PREF_ON, bool(self._var_on.get())))):
            ci.addWidget(Interruptor(texto, var, cmd, tam=13, color='#E0EBFB'))
        ci.addSpacing(8)
        yield
        ci.addWidget(eti(tr('Biblioteca')))
        self._lbl_lib = ui.Elidida('', 13, color='#E0EBFB')
        ci.addWidget(self._lbl_lib)
        ci.addWidget(Boton(tr('Cambiar carpeta…'), self._elegir_carpeta, alto=32, tam=12), 0, Qt.AlignmentFlag.AlignLeft)
        ci.addStretch(1)
        self._aro = AroTipos(dentro)                         # (no está en la C: escondido; poner() lo sigue llenando)
        self._aro.hide()
        yield
        izq.capa.addWidget(desp_izq, 1)
        self._b_aplicar = Boton(tr('Aplicar a Resolve'), self._aplicar, tipo='primario', alto=46, tam=14, negrita=True)
        izq.capa.addWidget(self._b_aplicar)
        self._b_rehacer = Boton(tr('Rehacer'), self._rehacer, alto=38, tam=13)
        izq.capa.addWidget(self._b_rehacer)
        externa.addWidget(izq)
        yield

        # ---- centro: la mezcla
        cen = Tarjeta(self, espacio=10, margenes=(18, 14, 18, 16))   # (v5.84: cada pieza nace ya en su sitio)
        fila, cfz = caja_h(espacio=8)
        cfz.addWidget(eti(tr('Mezcla')), 1)
        self._b_ant = Boton('◀', lambda: self._elegir(self._sel - 1), alto=30, ancho=36, tam=12)   # recorrer los sonidos, junto al zoom
        self._lbl_pos = Etiqueta('', 12, color=MUT)
        self._b_sig = Boton('▶', lambda: self._elegir(self._sel + 1), alto=30, ancho=36, tam=12)
        cfz.addWidget(self._b_ant)
        cfz.addWidget(self._lbl_pos)
        cfz.addWidget(self._b_sig)
        cfz.addSpacing(14)
        cfz.addWidget(Boton('−', lambda: self._linea.zoom(1 / 1.4), alto=30, ancho=36, tam=14))
        cfz.addWidget(Boton('+', lambda: self._linea.zoom(1.4), alto=30, ancho=36, tam=14))
        cfz.addWidget(Boton(tr('Ajustar'), self._ajustar_zoom, alto=30, tam=12))
        cen.capa.addWidget(fila)
        yield
        self._linea = LineaTiempo()
        self._linea.TIRA = 0                                 # (en la C el cuadro del momento va en el móvil de la derecha)
        self._linea.seleccionado.connect(self._elegir)
        self._scroll = QScrollArea(cen)
        self._scroll.setWidget(self._linea)
        self._scroll.setWidgetResizable(False)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(ui.traducir_hoja('QScrollArea{background:#0B1424;border:none;border-radius:12px}'))   # (v5.63: sigue al tema)
        self._scroll.viewport().setStyleSheet(ui.traducir_hoja('background:#0B1424'))
        self._scroll.setMinimumHeight(220)
        self._scroll.viewport().installEventFilter(self)    # (v5.83: la mezcla sigue al alto de su recuadro: eventFilter)
        cen.capa.addWidget(self._scroll, 1)
        yield
        ins = QWidget(cen)                                  # el inspector, debajo de la mezcla
        ins.setObjectName('inspSonido')
        ins.setStyleSheet(ui.traducir_hoja('#inspSonido{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px}'))
        # v5.93 (el usuario eligió la C del «Oído»): el inspector crece (218) y es el Oído: izquierda lo de siempre + «Para revisar»,
        # centro «Cuadro a cuadro», derecha el sello y los medidores. En un recuadro estrecho se esconden primero el cuadro y luego el sello.
        ins.setFixedHeight(218)
        ins.installEventFilter(self)
        self._ins = ins
        cins_h = QHBoxLayout(ins)
        cins_h.setContentsMargins(14, 12, 14, 12)
        cins_h.setSpacing(14)
        izq_i = QWidget(ins)
        izq_i.setObjectName('insIzq')
        izq_i.setStyleSheet('#insIzq{background:transparent}')    # (sin selector se heredaba y los botones perdían su color)
        izq_i.setMinimumWidth(540)
        cins = QVBoxLayout(izq_i)
        cins.setContentsMargins(2, 2, 0, 0)
        cins.setSpacing(8)
        top, ct = caja_h(espacio=14)
        self._ico = IconoGrande()
        ct.addWidget(self._ico)
        tt = QVBoxLayout()
        tt.setSpacing(2)
        self._lbl_sel = Etiqueta(tr('Elige un sonido'), 18, peso='extra', color='#FFFFFF')
        tt.addWidget(self._lbl_sel)
        self._lbl_archivo = Etiqueta('', 12, color=MUT)
        tt.addWidget(self._lbl_archivo)
        self._lbl_porque = Etiqueta(tr('Toca un sonido de la mezcla para ver por qué suena ahí.'), 13, color='#E8F1FF')   # (v5.93: una línea)
        self._lbl_porque.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        tt.addWidget(self._lbl_porque)
        ct.addLayout(tt, 1)
        self._onda = Onda(58, ins)                          # (v5.93: la onda va en «Cuadro a cuadro»; esta queda construida y escondida)
        self._onda.hide()
        cins.addWidget(top)
        bot, cb = caja_h(espacio=8)
        self._b_oir = Boton(tr('▶ Escuchar'), self._oir, tipo='primario', alto=36, tam=13)
        self._b_var = Boton(tr('Otra variante'), lambda: self._editar('variante'), alto=36, tam=13)
        self._b_izq = Boton(tr('◀ 1 fotograma'), lambda: self._editar('mover', -1 / FPS), alto=36, tam=13)
        self._b_der = Boton(tr('1 fotograma ▶'), lambda: self._editar('mover', 1 / FPS), alto=36, tam=13)
        self._b_quitar = Boton(tr('Quitar'), lambda: self._editar('quitar'), alto=36, tam=13)
        for b in (self._b_oir, self._b_var, self._b_izq, self._b_der, self._b_quitar):
            cb.addWidget(b)
        cb.addStretch(1)
        cins.addWidget(bot)
        self._lbl_para = Etiqueta(tr('Para revisar').upper(), 11, peso='negrita', color=ETI)
        cins.addWidget(self._lbl_para)
        from PySide6.QtWidgets import QGridLayout
        rejilla = QGridLayout()
        rejilla.setContentsMargins(0, 0, 0, 0)
        rejilla.setHorizontalSpacing(8)
        rejilla.setVerticalSpacing(6)
        self._chips = []
        for k in range(4):
            chip = ChipAccion(izq_i)
            chip.clic.connect(self._arreglar_accion)
            chip.hide()
            rejilla.addWidget(chip, k // 2, k % 2)
            self._chips.append(chip)
        cins.addLayout(rejilla)
        self._lbl_revision = Etiqueta('', 12, color=MUT, envolver=True)
        cins.addWidget(self._lbl_revision)
        cins.addStretch(1)
        cins_h.addWidget(izq_i, 5)
        self._cuadro_oido = CuadroACuadro(ins)
        cins_h.addWidget(self._cuadro_oido, 4)
        self._sello = SelloOido(ins)
        cins_h.addWidget(self._sello)
        self._oido, self._oido_n = None, 0
        cen.capa.addWidget(ins)
        externa.addWidget(cen, 1)
        yield

        # ---- derecha: el móvil y la música
        der = columna(326, (16, 16, 16, 16))
        self._cuadro = CuadroVideo()
        self._cuadro.clic.connect(self._oir)
        der.capa.addWidget(self._cuadro, 0, Qt.AlignmentFlag.AlignHCenter)
        der.capa.addSpacing(6)
        der.capa.addWidget(eti(tr('Música')))
        self._lbl_musica = ui.Etiqueta('', 12, color=MUT)          # v5.83: en dos líneas (cortado con «…» no se leía qué hacer)
        self._lbl_musica.setWordWrap(True)
        der.capa.addWidget(self._lbl_musica)
        fila_m = QWidget()
        fila_m.setStyleSheet('background:transparent')
        self._capa_musica = QVBoxLayout(fila_m)
        self._capa_musica.setContentsMargins(0, 0, 0, 0)
        self._capa_musica.setSpacing(6)
        self._capa_musica.addStretch(1)
        der.capa.addWidget(fila_m)
        self._lbl_credito = Etiqueta('', 11, color=MUT, envolver=True)
        der.capa.addWidget(self._lbl_credito)
        der.capa.addStretch(1)
        self._botones_musica = []
        externa.addWidget(der)
        self._columnas = (izq, cen, der)
        yield

        # ---- la tira de momentos (no está en la C): construida y escondida, _llenar_momentos y _elegir la siguen usando
        self._tira = QWidget()
        self._tira_capa = QHBoxLayout(self._tira)
        self._tira_capa.setContentsMargins(0, 0, 0, 0)
        self._tira_capa.addStretch(1)
        self._scroll_momentos = QScrollArea(self)
        self._scroll_momentos.setWidget(self._tira)
        self._scroll_momentos.hide()
        self._botones_sel(False)

    # ------------------------------------------------------------------ medidas (v5.67, propuesta C)
    def _ajustar_linea(self):
        """La mezcla llena el alto de su recuadro (carriles más altos en ventanas altas)."""
        self._linea.ajustar_alto(max(220, self._scroll.viewport().height()))

    def eventFilter(self, obj, ev):
        """v5.83: la mezcla se vuelve a medir cada vez que cambia el ALTO de su recuadro, no solo cuando cambia la página. Se medía al
        pintar los sonidos, antes de que la pista de música y el inspector tomaran su sitio: en una ventana baja se salía por abajo y
        escondía Interfaz, Textura y la regla de tiempo (ya en la 5.82); armada por partes en Inicio, se medía escondida (220) y quedaba corta."""
        try:
            if ev.type() == QEvent.Type.Resize and obj is self._scroll.viewport() and ev.size().height() != ev.oldSize().height():
                self._ajustar_linea()
            elif ev.type() == QEvent.Type.Resize and obj is getattr(self, '_ins', None):
                self._ajustar_ins(ev.size().width())
        except (AttributeError, RuntimeError):
            pass
        return super().eventFilter(obj, ev)

    def _ajustar_ins(self, ancho):
        """v5.93: en un recuadro estrecho se esconde primero «Cuadro a cuadro» y después el sello (lo de la izquierda siempre cabe)."""
        self._sello.setVisible(ancho >= 540 + 288 + 14 + 30)
        self._cuadro_oido.setVisible(ancho >= 540 + 288 + 260 + 28 + 30)
        self._rotulo_para()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._elidir_porque)            # (cuando la etiqueta ya tomó su nuevo ancho)

    def _elidir_porque(self):
        texto = getattr(self, '_porque', None)
        if texto:
            ancho = max(80, self._lbl_porque.width())
            self._lbl_porque.setText(self._lbl_porque.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, ancho))

    def _ajustar_zoom(self):
        self._linea.ajustar_ancho(self._scroll.viewport().width())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pasos is not None:                          # (v5.83: aún armándose por partes)
            return
        alto = self._columnas[2].height() - 32              # el móvil: 9:16, sin pasar de 288 de ancho y dejando sitio a la música
        h = int(max(280, min(512, alto - 300)))
        self._cuadro.setFixedSize(int(h * 9 / 16), h)
        self._ajustar_linea()

    def zonas(self):
        """Las tres columnas, en coordenadas de esta página (para que el cielo de fondo no las repinte en cada tic)."""
        return [c.geometry() for c in self._columnas if c.isVisible()]

    # ------------------------------------------------------------------ datos
    def video(self):
        try:
            return str(self._video_fn() or '').strip().strip('"')
        except Exception:
            return ''

    def _estado(self, texto):
        self._lbl_estado.setText(str(texto))
        self._lbl_estado.setVisible(bool(str(texto or '').strip()))

    def _pref(self, clave, valor):
        import sonido_skill as S
        try:
            S.poner_pref(**{clave: valor})
        except Exception:
            pass

    def _cambio_estilo(self, clave):
        for k, t in self._estilos.items():
            t.activa = k == clave
            t.update()
        self._pref('sonido_estilo', clave)
        self._estado(tr('Estilo guardado. Pulsa «Rehacer» para oírlo en este video.'))

    def _elegir_carpeta(self):
        import sonido_skill as S
        ruta = ui.filedialog.askdirectory(title=tr('Elige la carpeta de tu biblioteca de sonidos (la que tiene MAPA_SFX.md)'), parent=self.window())
        if ruta:
            self._pref(S.PREF_LIB, str(ruta))
            self._lbl_lib.setText(Path(ruta).name or str(ruta))      # (el rótulo «Biblioteca» ya va encima)
            self._estado(tr('Biblioteca cambiada. Pulsa «Rehacer».'))

    def refrescar(self):
        if self._ocupado:
            return
        import sonido_skill as S
        v = self.video()
        self._lbl_video.setText(Path(v).name if v else tr('Sin video'))

        def trabajo():
            res = S.resumen(v)
            vis = S.visual(v, res['filas']) if v and res['filas'] else {}
            return res, vis
        ui.correr_en_hilo(self, trabajo, self._al_datos)

    def _al_datos(self, r, err=None):
        if err is not None or not r:
            self._estado(tr('No pude leer el sonido del video: {e}', e=err))
            return
        self._pintar(*r)

    def _pintar(self, res, vis=None):
        import sonido_skill as S
        self._res = res or {}
        if vis is not None:
            self._vis = vis
        filas = self._res.get('filas') or []
        if self._res.get('video'):
            estilo = S.NOMBRE_ESTILO.get(self._res.get('estilo') or '', '')
            self._lbl_video.setText(f"{Path(self._res['video']).name}  ·  {len(filas)} {tr('sonidos')}" + (f'  ·  {estilo}' if estilo else ''))
        self._lbl_lib.setText(Path(self._res.get('biblioteca') or '').name)
        self._lbl_pend.setText(tr('● cambios sin aplicar') if self._res.get('pendiente') and filas else '')
        self._aro.poner(filas)
        self._pintar_musica(self._res.get('musica') or {})
        guia = self._res.get('guia') or {}
        self._linea.poner(filas, self._vis, guia.get('duracion'), self._musica_linea(self._res.get('musica') or {}), guia.get('bloques'))
        self._ajustar_linea()
        if not getattr(self, '_ya_ajustado', False) and filas:          # (la 1.ª vez con sonidos: todo el video a la vista)
            self._ya_ajustado = True
            self._ajustar_zoom()
        self._llenar_momentos(filas)
        self._avisos = S.revisar(filas) if filas else []
        self._oido = None                                    # v5.93: el Oído de ESTE diseño llega de un hilo (en caché si no cambió)
        self._pintar_oido()
        self._escuchar()
        if not filas:
            self._estado(tr('Haz GO con este video: el sonido sale de tu biblioteca y aquí ves cada decisión.'))
        elif self._res.get('pendiente'):
            self._estado('')                                 # ya lo dice la pastilla «● cambios sin aplicar» de la cabecera
        else:
            self._estado(tr('Al día en Resolve ({f}).', f=self._res.get('en_resolve') or self._res.get('fecha') or ''))
        self._elegir(self._sel if 0 <= self._sel < len(filas) else (0 if filas else -1))

    # ------------------------------------------------------------------ el Oído (v5.93)
    def _escuchar(self):
        """sonido_oido.escuchar en un hilo; si mientras tanto cambió el diseño, la respuesta vieja se descarta."""
        v, filas = self.video(), self._res.get('filas') or []
        self._oido_n += 1
        if not v or not filas:
            return
        n = self._oido_n

        def trabajo():
            import sonido_oido as O
            return O.escuchar(v)

        def fin(r, err=None):
            if n != self._oido_n:
                return
            self._oido = r if err is None else None
            self._pintar_oido(fallo=err is not None)
        ui.correr_en_hilo(self, trabajo, fin)

    def _pintar_oido(self, fallo=False):
        d = self._oido
        filas = self._res.get('filas') or []
        self._linea.estados = {int(s['i']): s.get('estado') for s in (d or {}).get('sonidos') or [] if s.get('i') is not None}
        self._linea.update()
        acc = (d or {}).get('acciones') or []
        for k, chip in enumerate(self._chips):
            chip.poner(acc[k] if k < len(acc) else None)
        if not filas:
            texto = ''
        elif fallo:
            texto = tr('No pude escuchar la mezcla (detalle en el Registro).')
        elif d is None:
            texto = tr('Escuchando la mezcla…')
        elif not acc:
            texto = tr('Todo en orden: cada sonido en su cuadro y se oye bien.') + (
                '  ·  ' + ' · '.join(getattr(self, '_avisos', [])[:2]) if getattr(self, '_avisos', None) else '')
        else:
            texto = ''
        self._lbl_revision.setText(texto)
        self._lbl_revision.setVisible(bool(texto))
        self._sello.poner(d, cargando=d is None and bool(filas) and not fallo)
        self._rotulo_para()
        self._pintar_cuadro()

    def _rotulo_para(self):
        """Sin sitio para el sello (ventana estrecha), el veredicto va junto a «Para revisar»."""
        nivel = (self._oido or {}).get('nivel')
        texto = tr('Para revisar').upper()
        if nivel is not None and not self._sello.isVisible():
            texto += '  ·  ' + {0: tr('Listo'), 1: tr('Casi'), 2: tr('Revisar')}.get(nivel, '').upper()
        self._lbl_para.setText(texto)
        self._lbl_para.poner_color({0: VERDE_OK, 1: AMBAR, 2: ROJO}.get(nivel, ETI) if not self._sello.isVisible() else ETI)

    def _pintar_cuadro(self):
        filas = self._res.get('filas') or []
        d, i = self._oido, self._sel
        s = next((x for x in (d or {}).get('sonidos') or [] if x.get('i') == i), None) if d else None
        f = filas[i] if 0 <= i < len(filas) else None
        aviso = tr('Escuchando la mezcla…') if d is None and filas else ''
        self._cuadro_oido.poner(s, (d or {}).get('fps') or FPS, color_de(f) if f else None, aviso)

    def _arreglar_accion(self, a):
        """Tocar una acción de «Para revisar»: se aplica su arreglo (y los demás de ese sonido) en una sola horneada."""
        import sonido_skill as S
        i = (a or {}).get('i')
        if i is None or not (a or {}).get('arreglo'):
            return
        v = self.video()
        self._sel = int(i)

        def trabajo():
            import sonido_oido as O
            ok, msg = O.arreglar(v, solo={int(i)})
            res = S.resumen(v)
            return ok, msg, res, S.visual(v, res['filas'])

        def fin(r):
            ok, msg, res, vis = r
            if a['arreglo'].get('accion') == 'quitar':
                self._sel = min(int(i), len(res.get('filas') or []) - 1)
            self._pintar(res, vis)
            self._estado(tr('Arreglado · pendiente de «Aplicar a Resolve».') if ok else str(msg))
        self._trabajar(tr('Arreglando…'), trabajo, fin)

    def _musica_linea(self, m):
        """La música elegida para su carril: {'titulo', 'onda', 'dur'} (la onda se lee una vez y queda en memoria)."""
        import sonido_skill as S
        cands, el = m.get('candidatos') or [], m.get('elegida')
        if el is None or not 0 <= el < len(cands) or not cands[el].get('wav'):
            return None
        c = cands[el]
        cache = self.__dict__.setdefault('_ondas_musica', {})
        if c['wav'] not in cache:
            try:
                cache[c['wav']] = S._envolvente(S.leer_audio(c['wav'], 4000), max(60, int(float(m.get('dur') or 30) * 6)))
            except Exception:
                cache[c['wav']] = []
        return {'titulo': c['titulo'], 'onda': cache[c['wav']], 'dur': m.get('dur')}

    def _llenar_momentos(self, filas):
        for m in self._momentos:
            m.setParent(None)
            m.deleteLater()
        self._momentos = []
        for i, f in enumerate(filas):
            m = TarjetaMomento(i, f, pixmap(miniatura(self._vis, f.get('segundo'))))
            m.clic.connect(self._elegir)
            self._tira_capa.insertWidget(self._tira_capa.count() - 1, m)
            self._momentos.append(m)

    def _pintar_musica(self, m):
        import sonido_musica as M
        for b in self._botones_musica:
            b.setParent(None)
            b.deleteLater()
        self._botones_musica = []
        cands, el = m.get('candidatos') or [], m.get('elegida')
        corto = lambda t: t if len(t) <= 30 else t[:29].rstrip() + '…'   # noqa: E731
        botones = [Boton(('● ' if i == el else '') + corto(c['titulo']), lambda i=i: self._musica(i), tipo='primario' if i == el else 'secundario',
                         alto=36, tam=12) for i, c in enumerate(cands)]
        if cands:
            botones.append(Boton(('● ' if el is None else '') + tr('Sin música'), lambda: self._musica(None),
                                 tipo='primario' if el is None else 'secundario', alto=36, tam=12))
            self._b_oir_musica = Boton(tr('▶ Escuchar'), self._oir_musica, alto=36, tam=12)
            self._b_oir_musica.setEnabled(el is not None)
            botones.append(self._b_oir_musica)
        for b in botones:
            self._capa_musica.insertWidget(self._capa_musica.count() - 1, b)
        self._botones_musica = botones
        c = cands[el] if el is not None and 0 <= el < len(cands) else None
        if c:
            como = tr('debajo de tu voz, baja sola al hablar') if 'bajo la voz' in (c.get('nivel') or '') else tr('de fondo')
            carpeta = c.get('carpeta') or ''                          # (un estado guardado sin esos datos daba KeyError al pintar)
            self._lbl_musica.setText(f"{M.NOMBRE_CARPETA.get(carpeta, carpeta) or c.get('titulo', '')} · {float(c.get('bpm') or 0):.0f} BPM · {como}")
        elif m.get('apagada'):
            self._lbl_musica.setText(tr('Apagada: enciéndela y pulsa «Rehacer».'))
        else:
            self._lbl_musica.setText(tr('Sin música') if cands else tr('Haz GO o «Rehacer»: aquí eliges entre 3 músicas de tu biblioteca.'))
        self._lbl_credito.setText(tr('Crédito obligatorio en la descripción: {c}', c=c['credito'].replace('\n', ' · ')) if c and c.get('credito') else '')
        self._lbl_credito.setVisible(bool(c and c.get('credito')))

    def _musica(self, i):
        import sonido_musica as M
        import sonido_skill as S
        v = self.video()

        def trabajo():
            ok, msg = M.elegir(v, i)
            return ok, msg, S.resumen(v)

        def fin(r):
            ok, msg, res = r
            self._pintar(res)
            self._estado(msg)
        self._trabajar(tr('Cambiando la música…'), trabajo, fin)

    def _oir_musica(self):
        import director_sonido_sesion as DS
        m = self._res.get('musica') or {}
        cands, el = m.get('candidatos') or [], m.get('elegida')
        if el is not None and 0 <= el < len(cands) and cands[el].get('wav'):
            try:
                DS.reproducir(cands[el]['wav'])
            except Exception as e:
                self._estado(tr('No pude reproducirlo: {e}', e=e))

    def _botones_sel(self, si):
        for b in (self._b_oir, self._b_var, self._b_izq, self._b_der, self._b_quitar):
            b.setEnabled(bool(si))

    def _elegir(self, i):
        filas = self._res.get('filas') or []
        self._sel = i
        self._linea.sel = i
        self._linea.update()
        for m in self._momentos:
            m.activa = m.i == i
            m.update()
        self._lbl_pos.setText(f'{i + 1} / {len(filas)}' if 0 <= i < len(filas) else '')
        self._b_ant.setEnabled(i > 0)
        self._b_sig.setEnabled(0 <= i < len(filas) - 1)
        if not 0 <= i < len(filas):
            self._botones_sel(False)
            self._cuadro.poner(None, '', QColor('#4589FF'))
            if hasattr(self, '_cuadro_oido'):
                self._pintar_cuadro()
            return
        f = filas[i]
        col = color_de(f)
        tipo = NOMBRE_TIPO.get(f.get('tipo'), f.get('tipo') or '')
        nombre = Path(f.get('archivo') or '').stem.split(' - ', 1)[-1]
        self._ico.poner(f.get('tipo'), col)
        self._lbl_sel.setText(f"{tr(tipo)}  ·  {_mmss(f.get('segundo'))}")
        self._lbl_archivo.setText(f"{nombre}  ·  {next((n for p, n, _ in CARRILES if p == f.get('pista')), '')}")
        self._onda.poner(((self._vis or {}).get('ondas') or {}).get(f.get('wav')) or [], col)
        import re
        # (v5.93: «Tema 1: …» del diseño → «Estilo 1: …»: en la interfaz nunca «tema»; una sola línea con «…»)
        porque = re.sub(r'\bTema (\d+)', lambda m: tr('Estilo {n}', n=m.group(1)), (f.get('por_que') or '—').replace('caption ', ''))
        self._porque = tr('Por qué: {p}', p=porque)
        self._elidir_porque()
        if hasattr(self, '_cuadro_oido'):
            self._pintar_cuadro()
        self._cuadro.poner(pixmap(miniatura(self._vis, f.get('segundo'))), f"{tr(tipo).upper()} · {nombre.upper().split()[0][:12]}", col)
        self._botones_sel(True)
        x = int(self._linea.x_de(f.get('segundo') or 0) - self._scroll.viewport().width() / 2)   # el editor se va a ese momento
        self._scroll.horizontalScrollBar().setValue(max(0, x))

    # ------------------------------------------------------------------ acciones
    def _trabajar(self, texto, trabajo, fin):
        if self._ocupado:
            return
        self._ocupado = True
        for b in (self._b_rehacer, self._b_aplicar):
            b.setEnabled(False)
        self._estado(texto)

        def listo(r, err):
            self._ocupado = False
            for b in (self._b_rehacer, self._b_aplicar):
                b.setEnabled(True)
            if err is not None:
                self._estado(tr('Algo falló: {e}', e=err))
                return
            fin(r)
        ui.correr_en_hilo(self, trabajo, listo)

    def _oir(self):
        import director_sonido_sesion as DS
        filas = self._res.get('filas') or []
        if 0 <= self._sel < len(filas) and filas[self._sel].get('wav'):
            try:
                DS.reproducir(filas[self._sel]['wav'])
            except Exception as e:
                self._estado(tr('No pude reproducirlo: {e}', e=e))

    def _editar(self, accion, valor=None):
        import sonido_skill as S
        v, i = self.video(), self._sel

        def trabajo():
            ok, msg = S.editar(v, i, accion, valor)
            res = S.resumen(v)
            return ok, msg, res, S.visual(v, res['filas'])

        def fin(r):
            ok, msg, res, vis = r
            if accion == 'quitar':
                self._sel = min(i, len(res.get('filas') or []) - 1)
            self._pintar(res, vis)
            self._estado(msg)
        self._trabajar(tr('Cambiando el sonido…'), trabajo, fin)

    def _rehacer(self):
        import sonido_skill as S
        v = self.video()
        if not v:
            self._estado(tr('Primero carga un video en Inicio.'))
            return

        def trabajo():
            ok, msg = S.rehacer(v)
            res = S.resumen(v)
            return ok, msg, res, S.visual(v, res['filas'])

        def fin(r):
            ok, msg, res, vis = r
            self._sel = 0
            self._pintar(res, vis)
            self._estado(msg)
        self._trabajar(tr('Rehaciendo el sonido con tu biblioteca…'), trabajo, fin)

    def _aplicar(self):
        import director_sonido_sesion as DS
        import sonido_skill as S
        v = self.video()
        try:
            off = int(self._offset_fn() or 0)
        except Exception:
            off = 0

        def trabajo():
            ok, msg = DS.aplicar(v, offset_frames=off)
            return ok, msg, S.resumen(v)

        def fin(r):
            ok, msg, res = r
            self._pintar(res)
            self._estado(tr('Puesto en Resolve: los sonidos de la biblioteca en sus pistas; los de siempre, apagados.') if ok
                         else tr('No se pudo poner en Resolve: {m}', m=str(msg)[:160]))
        self._trabajar(tr('Poniendo el sonido en Resolve…'), trabajo, fin)
