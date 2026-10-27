# CineCaptions · By Cinema Productions
# 1_codigo/sonido_skill_ui.py — la página SONIDO (v5.43, diseño A+B elegido por el usuario): editor visual de lo que decidió sonido_skill.
"""
Reemplaza a la página del «AI Sound Director» (ya no se muestra). De arriba a abajo (todo dentro de un desplazable vertical):

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

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
from i18n import tr
from qt_kit import Boton, Etiqueta, Interruptor, Tarjeta, caja_h

MUT = ui.TEXT_MUTED
ESTILOS = (('auto', 'Automático', 'según el tema'), ('elegante', 'Elegante', 'pocos y suaves'), ('dinamico', 'Dinámico', 'pop en cada clave'),
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
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor('#4589FF' if self.activa else '#22324F'), 1.4))
        p.setBrush(QColor('#16305E' if self.activa else '#0F1A2F'))
        p.drawRoundedRect(r, 14, 14)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(14, peso='negrita'))
        p.drawText(r.adjusted(16, 10, -8, -30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr(self.nombre))
        p.setPen(QColor(MUT))
        p.setFont(ui.fuente(12))
        p.drawText(r.adjusted(16, 32, -8, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr(self.desc))
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
        self.setFixedSize(200, 356)
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
        camino.addRoundedRect(r, 16, 16)
        p.setClipPath(camino)
        p.fillRect(r, QColor('#000000'))
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
        # tira de fotogramas: uno por segundo (o cada 2 / 5 si el zoom es chico)
        y = 6
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
        # voz
        y = self.TIRA + 2
        p.setPen(QColor(MUT))
        p.drawText(QRectF(12, y, self.IZQ - 16, self.VOZ), Qt.AlignmentFlag.AlignVCenter, tr('Voz'))
        voz = self.vis.get('voz') or []
        dv = float(self.vis.get('duracion') or self.dur) or self.dur
        pintar_onda(p, QRectF(self.IZQ, y + 4, dv * self.pps, self.VOZ - 8), voz, QColor('#2F4A72'))
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
            p.drawRoundedRect(QRectF(self.IZQ, yy, w - self.IZQ - 14, self.ALTO - 6), 8, 8)
            p.setPen(QColor(col))
            p.drawText(QRectF(12, yy, self.IZQ - 16, self.ALTO - 6), Qt.AlignmentFlag.AlignVCenter, tr(nombre))
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
        # regla y cabezal
        p.setPen(QColor(MUT))
        p.setFont(ui.fuente(11))
        yr = y0 + self.n_carriles() * self.ALTO + 4
        for s in range(0, int(self.dur) + 1, 2 if self.pps >= 40 else 5):
            p.drawText(QRectF(self.x_de(s) - 20, yr, 40, 16), Qt.AlignmentFlag.AlignCenter, _mmss(s)[:-3])
        if 0 <= self.sel < len(self.filas):
            x = self.x_de(self.filas[self.sel].get('segundo') or 0)
            p.setPen(QPen(QColor('#FF4D5E'), 2))
            p.drawLine(QPointF(x, 0), QPointF(x, yr))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#FF4D5E'))
            tri = QPainterPath()
            tri.moveTo(x - 7, 0)
            tri.lineTo(x + 7, 0)
            tri.lineTo(x, 9)
            tri.closeSubpath()
            p.drawPath(tri)
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

    def __init__(self, padre=None, video=None, offset=None):
        super().__init__(padre)
        import sonido_skill as S
        self._video_fn = video or (lambda: '')
        self._offset_fn = offset or (lambda: 0)
        self._ocupado = False
        self._res, self._vis, self._sel = {}, {}, -1
        self._momentos = []
        prefs = S._prefs()
        externa = QVBoxLayout(self)
        externa.setContentsMargins(0, 0, 0, 0)
        desp = QScrollArea()
        desp.setWidgetResizable(True)
        desp.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desp.setStyleSheet('QScrollArea{background:transparent;border:none}')
        cuerpo = QWidget()
        cuerpo.setObjectName('cuerpoSonido')
        cuerpo.setStyleSheet('#cuerpoSonido{background:transparent}')
        desp.setWidget(cuerpo)
        externa.addWidget(desp)
        capa = QVBoxLayout(cuerpo)
        capa.setContentsMargins(0, 0, 8, 0)
        capa.setSpacing(14)

        # ---- cabecera
        cab, cc = caja_h(espacio=14)
        logo = Etiqueta('')
        try:
            import sfx_rules
            pm = ui.pixmap_de_archivo(sfx_rules.base_recursos() / 'logo_cinecaptions.png', 36)
            if pm is not None:
                logo.setPixmap(pm)
        except Exception:
            pass
        cc.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(Etiqueta(tr('Sonido'), 24, peso='extra', color='#FFFFFF'))
        self._lbl_video = ui.Elidida('', 13, color=MUT)
        col.addWidget(self._lbl_video)
        cc.addLayout(col, 1)
        self._lbl_pend = Etiqueta('', 12, color='#F5C451')
        cc.addWidget(self._lbl_pend)
        self._b_rehacer = Boton(tr('Rehacer'), self._rehacer, alto=40, tam=13)
        cc.addWidget(self._b_rehacer)
        self._b_aplicar = Boton(tr('Aplicar a Resolve'), self._aplicar, tipo='primario', alto=40, tam=13, negrita=True)
        cc.addWidget(self._b_aplicar)
        bloques = {'cab': cab}
        self._lbl_estado = Etiqueta(tr('Haz GO con un video: aquí ves qué sonido va en cada momento y por qué.'), 12, color=MUT, envolver=True)
        bloques['estado'] = self._lbl_estado

        # ---- (B) estilos + aro de tipos + interruptores
        est = QWidget()
        ce = QVBoxLayout(est)
        ce.setContentsMargins(0, 0, 0, 0)
        ce.setSpacing(12)
        bloques['estilos'] = est
        fila, cf = caja_h(espacio=10)
        self._estilos = {}
        actual = prefs.get(S.PREF_ESTILO) or 'auto'
        for clave, nombre, desc in ESTILOS:
            t = TarjetaEstilo(clave, nombre, desc)
            t.activa = clave == actual
            t.clic.connect(self._cambio_estilo)
            self._estilos[clave] = t
            cf.addWidget(t, 1)
        ce.addWidget(fila)
        fila, cf = caja_h(espacio=16)
        self._aro = AroTipos()
        cf.addWidget(self._aro)
        self._var_gancho = ui.BooleanVar(prefs.get(S.PREF_GANCHO, True) is not False)
        cf.addWidget(Interruptor(tr('Gancho al inicio'), self._var_gancho, lambda: self._pref(S.PREF_GANCHO, bool(self._var_gancho.get())),
                                 tam=13, color='#E0EBFB'))
        self._var_fiesta = ui.BooleanVar(prefs.get(S.PREF_FIESTA, False) is True)
        cf.addWidget(Interruptor(tr('Fiesta o mar'), self._var_fiesta, lambda: self._pref(S.PREF_FIESTA, bool(self._var_fiesta.get())),
                                 tam=13, color='#E0EBFB'))
        cf.addStretch(1)
        self._lbl_lib = ui.Elidida('', 12, color=MUT)
        cf.addWidget(self._lbl_lib, 1)
        cf.addWidget(Boton(tr('Cambiar carpeta…'), self._elegir_carpeta, alto=32, tam=12))
        ce.addWidget(fila)

        # ---- música (v5.48): 3 opciones de 02_MUSICA (carpetas distintas), escuchar, sin música, crédito CC BY
        import sonido_musica as M
        mu = Tarjeta(espacio=10, margenes=(20, 14, 20, 14))
        top, ct = caja_h(espacio=12)
        ct.addWidget(Etiqueta(tr('Música'), 15, peso='medio', color='#FFFFFF'))
        self._lbl_musica = ui.Elidida('', 12, color=MUT)
        ct.addWidget(self._lbl_musica, 1)
        self._var_musica = ui.BooleanVar(M.activa(prefs))
        ct.addWidget(Interruptor(tr('En los próximos GO'), self._var_musica, lambda: self._pref(M.PREF_MUSICA, bool(self._var_musica.get())),
                                 tam=13, color='#E0EBFB'))
        mu.capa.addWidget(top)
        fila_m, self._capa_musica = caja_h(espacio=10)
        self._capa_musica.addStretch(1)
        mu.capa.addWidget(fila_m)
        self._lbl_credito = Etiqueta('', 12, color=MUT, envolver=True)
        mu.capa.addWidget(self._lbl_credito)
        bloques['musica'] = mu
        self._botones_musica = []

        # ---- (A) cuadro del video + inspector
        fila = QWidget()
        cf = QHBoxLayout(fila)
        cf.setContentsMargins(0, 0, 0, 0)
        cf.setSpacing(14)
        tv = Tarjeta(espacio=8, margenes=(14, 14, 14, 14))
        self._cuadro = CuadroVideo()
        self._cuadro.clic.connect(self._oir)
        tv.capa.addWidget(self._cuadro, 0, Qt.AlignmentFlag.AlignHCenter)
        cf.addWidget(tv)
        ins = Tarjeta(espacio=12, margenes=(22, 20, 22, 20))
        top, ct = caja_h(espacio=14)
        self._ico = IconoGrande()
        ct.addWidget(self._ico)
        tt = QVBoxLayout()
        tt.setSpacing(2)
        self._lbl_sel = Etiqueta(tr('Elige un sonido'), 22, peso='extra', color='#FFFFFF')
        tt.addWidget(self._lbl_sel)
        self._lbl_archivo = Etiqueta('', 13, color=MUT)
        tt.addWidget(self._lbl_archivo)
        ct.addLayout(tt, 1)
        ins.capa.addWidget(top)
        self._onda = Onda(78)
        ins.capa.addWidget(self._onda)
        self._lbl_porque = Etiqueta(tr('Toca un momento o un bloque de la línea para ver por qué suena ahí.'), 15, color='#E8F1FF', envolver=True)
        ins.capa.addWidget(self._lbl_porque)
        bot, cb = caja_h(espacio=10)
        self._b_oir = Boton(tr('▶ Escuchar'), self._oir, alto=40, tam=13)
        self._b_var = Boton(tr('⇄ Otra variante'), lambda: self._editar('variante'), alto=40, tam=13)
        self._b_izq = Boton(tr('◀ 1 fotograma'), lambda: self._editar('mover', -1 / FPS), alto=40, tam=13)
        self._b_der = Boton(tr('1 fotograma ▶'), lambda: self._editar('mover', 1 / FPS), alto=40, tam=13)
        self._b_quitar = Boton(tr('Quitar'), lambda: self._editar('quitar'), alto=40, tam=13)
        for b in (self._b_oir, self._b_var, self._b_izq, self._b_der, self._b_quitar):
            cb.addWidget(b)
        cb.addStretch(1)
        ins.capa.addWidget(bot)
        self._lbl_revision = Etiqueta('', 12, color=MUT, envolver=True)
        ins.capa.addWidget(self._lbl_revision)
        ins.capa.addStretch(1)
        nav, cn = caja_h(espacio=10)                        # recorrer los momentos sin bajar a la tira
        self._b_ant = Boton(tr('◀ Anterior'), lambda: self._elegir(self._sel - 1), alto=34, tam=12)
        self._lbl_pos = Etiqueta('', 12, color=MUT)
        self._b_sig = Boton(tr('Siguiente ▶'), lambda: self._elegir(self._sel + 1), alto=34, tam=12)
        cn.addWidget(self._b_ant)
        cn.addWidget(self._lbl_pos)
        cn.addWidget(self._b_sig)
        cn.addStretch(1)
        ins.capa.addWidget(nav)
        cf.addWidget(ins, 1)
        bloques['editor'] = fila

        # ---- (A) línea de tiempo tipo editor
        lt = Tarjeta(espacio=8, margenes=(14, 12, 14, 12))
        fila, cfz = caja_h(espacio=8)
        cfz.addWidget(Etiqueta(tr('Línea de tiempo'), 15, peso='medio', color='#FFFFFF'), 1)
        cfz.addWidget(Boton('−', lambda: self._linea.zoom(1 / 1.4), alto=30, ancho=36, tam=14))
        cfz.addWidget(Boton('+', lambda: self._linea.zoom(1.4), alto=30, ancho=36, tam=14))
        lt.capa.addWidget(fila)
        self._linea = LineaTiempo()
        self._linea.seleccionado.connect(self._elegir)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._linea)
        self._scroll.setWidgetResizable(False)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet('QScrollArea{background:#0B1424;border:none;border-radius:10px}')
        self._scroll.viewport().setStyleSheet('background:#0B1424')
        self._scroll.setFixedHeight(self._linea.alto_total() + 16)
        lt.capa.addWidget(self._scroll)
        bloques['linea'] = lt

        # ---- (B) momentos
        bloques['t_momentos'] = Etiqueta(tr('Momentos con sonido · toca uno para verlo, escucharlo o cambiarlo'), 15, peso='medio', color='#FFFFFF')
        self._tira = QWidget()
        self._tira_capa = QHBoxLayout(self._tira)
        self._tira_capa.setContentsMargins(0, 0, 0, 0)
        self._tira_capa.setSpacing(12)
        self._tira_capa.addStretch(1)
        tm = QScrollArea()
        tm.setWidget(self._tira)
        tm.setWidgetResizable(True)
        tm.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tm.setFixedHeight(TarjetaMomento.ALTO + 18)
        tm.setStyleSheet('QScrollArea{background:transparent;border:none}')
        tm.viewport().setStyleSheet('background:transparent')
        self._tira.setStyleSheet('background:transparent')
        self._scroll_momentos = tm
        bloques['momentos'] = tm

        on = Tarjeta(espacio=12, margenes=(20, 10, 20, 10), horizontal=True)
        on.capa.addWidget(Etiqueta(tr('Poner el sonido con la biblioteca en los próximos GO'), 13, peso='medio', color='#E0EBFB'), 1)
        self._var_on = ui.BooleanVar(S.activo(prefs))
        on.capa.addWidget(Interruptor(tr('Activado'), self._var_on, lambda: self._pref(S.PREF_ON, bool(self._var_on.get())), tam=13, color='#E0EBFB'))
        bloques['on'] = on
        for clave in ('cab', 'estado', 'estilos', 'musica', 'editor', 'linea', 't_momentos', 'momentos', 'on'):
            capa.addWidget(bloques[clave])
        capa.addStretch(1)
        self._botones_sel(False)

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
            self._lbl_lib.setText(tr('Biblioteca: {r}', r=ruta))
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
        self._lbl_lib.setText(tr('Biblioteca: {r}', r=Path(self._res.get('biblioteca') or '').name))
        self._lbl_pend.setText(tr('● cambios sin aplicar') if self._res.get('pendiente') and filas else '')
        self._aro.poner(filas)
        self._pintar_musica(self._res.get('musica') or {})
        guia = self._res.get('guia') or {}
        self._linea.poner(filas, self._vis, guia.get('duracion'), self._musica_linea(self._res.get('musica') or {}), guia.get('bloques'))
        self._scroll.setFixedHeight(self._linea.alto_total() + 16)
        self._llenar_momentos(filas)
        avisos = S.revisar(filas) if filas else []
        self._lbl_revision.setText(tr('Revisión: todo en orden.') if filas and not avisos else ('Revisión: ' + ' · '.join(avisos[:3]) if avisos else ''))
        if not filas:
            self._estado(tr('Haz GO con este video: el sonido sale de tu biblioteca y aquí ves cada decisión.'))
        elif self._res.get('pendiente'):
            self._estado('')                                 # ya lo dice la pastilla «● cambios sin aplicar» de la cabecera
        else:
            self._estado(tr('Al día en Resolve ({f}).', f=self._res.get('en_resolve') or self._res.get('fecha') or ''))
        self._elegir(self._sel if 0 <= self._sel < len(filas) else (0 if filas else -1))

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
            self._lbl_musica.setText(f"{M.NOMBRE_CARPETA.get(c['carpeta'], c['carpeta'])} · {c['bpm']:.0f} BPM · {como}")
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
            return
        f = filas[i]
        col = color_de(f)
        tipo = NOMBRE_TIPO.get(f.get('tipo'), f.get('tipo') or '')
        nombre = Path(f.get('archivo') or '').stem.split(' - ', 1)[-1]
        self._ico.poner(f.get('tipo'), col)
        self._lbl_sel.setText(f"{tr(tipo)}  ·  {_mmss(f.get('segundo'))}")
        self._lbl_archivo.setText(f"{nombre}  ·  {next((n for p, n, _ in CARRILES if p == f.get('pista')), '')}")
        self._onda.poner(((self._vis or {}).get('ondas') or {}).get(f.get('wav')) or [], col)
        self._lbl_porque.setText(tr('Por qué: {p}', p=(f.get('por_que') or '—').replace('caption ', '')))
        self._cuadro.poner(pixmap(miniatura(self._vis, f.get('segundo'))), f"{tr(tipo).upper()} · {nombre.upper().split()[0][:12]}", col)
        self._botones_sel(True)
        x = int(self._linea.x_de(f.get('segundo') or 0) - self._scroll.viewport().width() / 2)   # el editor se va a ese momento
        self._scroll.horizontalScrollBar().setValue(max(0, x))
        if 0 <= i < len(self._momentos):
            self._scroll_momentos.ensureWidgetVisible(self._momentos[i], 40, 0)

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
