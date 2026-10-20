# CineCaptions · By Cinema Productions
# 1_codigo/estilos_inicio.py — los 10 estilos de la pantalla de Inicio: cada uno es un rediseño completo (héroe, fondo, partículas).
"""
Un estilo = el botón GO dibujado a su manera (`heroe`), el fondo animado de la escena (`fondo`, a 1/3 de resolución; `frente` a
resolución completa si hace falta) y el movimiento de las partículas (`modo`: espiral, ascenso, caida, orbita). Todos entienden los
mismos estados (listo, trabajando con porcentaje, hecho con palomita, error, apagado), las fases de GO y el tono del final.

  astrolabio · synthwave · reactor · agujero · liquido · prisma · ecualizador · plasma · carrete · matrix

Cada estilo trae además su `tema` (superficies de la interfaz), su `acento` y su `aurora` (los 3 colores de luz de todas las páginas):
al elegirlo en Ajustes > Interfaz cambia el aspecto de TODA la interfaz, no solo el Inicio.
Se dibuja con QPainter (vectorial) y cada cuadro hace pocas llamadas a Qt: el hilo de la interfaz tiene que seguir fluido aunque el
equipo esté transcribiendo.
"""
import math
import random

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF, QRadialGradient)

from i18n import tr
from qt_kit import fuente

PI2 = math.tau


def _c(hexa, a=255):
    c = QColor(hexa)
    c.setAlpha(int(max(0, min(255, a))))
    return c


def _pen(col, ancho, cap=Qt.PenCapStyle.RoundCap):
    return QPen(col, max(0.6, ancho), Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin)


class Ctx:
    """Lo que el botón le cuenta al estilo en cada cuadro."""
    __slots__ = ('estado', 't', 'progreso', 'marca', 'flare', 'hover', 'presion', 'fase', 'fase_t', 'tono', 'vibra', 'apagon',
                 'residuo', 'eta', 'texto', 'entrada', 'vel', 'quieto', 'cierre', 'cortes')

    def __init__(self):
        self.estado = 'listo'
        self.t = 0.0
        self.progreso = 0.0
        self.marca = 0.0
        self.flare = 0.0
        self.hover = 0.0
        self.presion = 0.0
        self.fase = ''
        self.fase_t = 9.0
        self.tono = 'ok'
        self.vibra = 0.0
        self.apagon = 0.0
        self.residuo = 0.0
        self.eta = ''
        self.texto = ''
        self.entrada = 9.0
        self.vel = 1.0
        self.quieto = False
        self.cierre = -1.0
        self.cortes = ()                 # v5.22: dónde acaba cada paso de GO (0..1): el anillo de progreso los marca


# --------------------------------------------------------------------------------------------------- piezas comunes
def cifras(f):
    """v5.22: cifras de ancho fijo (tnum): el porcentaje no baila de lado a lado mientras cuenta."""
    try:
        f.setFeature(QFont.Tag('tnum'), 1)
    except Exception:
        pass
    return f


_CABE = {}


def fuente_que_cabe(texto, ancho, tam, minimo=10, peso='medio', tnum=False):
    """v5.22: la fuente más grande (de `tam` a `minimo` px) con la que `texto` cabe en `ancho` px en UNA línea, o None si ni así cabe
    (el centro del botón la omite: la barra de abajo de Inicio ya lo dice). Con caché: se pide en cada cuadro."""
    clave = (texto, int(ancho), int(tam), int(minimo), peso, tnum)
    if clave in _CABE:
        return _CABE[clave]
    elegida = None
    for t in range(int(tam), int(minimo) - 1, -1):
        f = fuente(t, peso=peso)
        if tnum:
            f = cifras(f)
        if QFontMetricsF(f).horizontalAdvance(texto) <= ancho:
            elegida = f
            break
    if len(_CABE) > 400:
        _CABE.clear()
    _CABE[clave] = elegida
    return elegida


def arco_prog(p, rad, ancho, prog, col, col2=None, cortes=()):
    """Un arco de progreso con resplandor (de las 12 en punto, en sentido horario) y una cabeza brillante.
    v5.22 (el usuario: «mejora su barra de progreso»): va sobre una pista del anillo entero (se ve lo que falta), el trazo es más
    grueso y se aclara hacia la cabeza, y unos cortes marcan dónde acaba cada paso de GO (`cortes`: los mismos tramos que la barra
    de abajo de la escena, así las dos cuentan lo mismo)."""
    prog = max(0.004, min(1.0, prog))
    caja = QRectF(-rad, -rad, 2 * rad, 2 * rad)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(QColor(0, 0, 0, 95), ancho * 2.6))                 # la pista: oscura, con un filo del color
    p.drawEllipse(QPointF(0, 0), rad, rad)
    p.setPen(_pen(_c(col.name(), 46), ancho * 1.1))
    p.drawEllipse(QPointF(0, 0), rad, rad)
    for k, al in ((3.6, 26), (2.1, 72)):                             # el resplandor
        p.setPen(_pen(_c(col.name(), al), ancho * k))
        p.drawArc(caja, 90 * 16, -int(360 * 16 * prog))
    claro = col2 or QColor(255, 255, 255)
    g = QConicalGradient(QPointF(0, 0), 90)                          # el trazo: del color (inicio) al claro (cabeza)
    g.setColorAt(0.0, _c(col.name(), 255))
    g.setColorAt(max(0.0005, 1.0 - prog), claro)
    g.setColorAt(1.0, _c(col.name(), 255))
    p.setPen(QPen(QBrush(g), max(0.8, ancho * 1.3), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(caja, 90 * 16, -int(360 * 16 * prog))
    if cortes:                                                       # dónde acaba cada paso
        p.setPen(_pen(QColor(4, 10, 18, 235), max(1.4, ancho * 0.75), Qt.PenCapStyle.FlatCap))
        for f in cortes:
            a = math.radians(90 - 360 * f)
            u = QPointF(math.cos(a), -math.sin(a))
            p.drawLine(u * (rad - ancho * 2.1), u * (rad + ancho * 2.1))
    ang = math.radians(90 - 360 * prog)
    cab = QPointF(rad * math.cos(ang), -rad * math.sin(ang))
    g = QRadialGradient(cab, ancho * 3.0)
    g.setColorAt(0, QColor(255, 255, 255, 255))
    g.setColorAt(0.4, _c(col.name(), 170))
    g.setColorAt(1, _c(col.name(), 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(cab, ancho * 3.0, ancho * 3.0)


def palomita(p, rd, marca, col, alfa=1.0):
    tm = 1 - (1 - max(0.0, min(1.0, marca))) ** 3
    if tm <= 0.001:
        return
    a, b, d = QPointF(-rd * 0.42, rd * 0.02), QPointF(-rd * 0.1, rd * 0.34), QPointF(rd * 0.5, -rd * 0.32)
    cam = QPainterPath()
    cam.moveTo(a)
    if tm < 0.4:
        cam.lineTo(a + (b - a) * (tm / 0.4))
    else:
        cam.lineTo(b)
        cam.lineTo(b + (d - b) * ((tm - 0.4) / 0.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for k, al in ((0.34, 40), (0.2, 90), (0.11, 255)):
        c = col if k > 0.15 else QColor(min(255, col.red() + 90), min(255, col.green() + 40), min(255, col.blue() + 60))
        p.setPen(_pen(_c(c.name(), al * alfa), rd * k))
        p.drawPath(cam)


def play(p, s, col, glow=True):
    """El triángulo de «play», con resplandor."""
    tri = QPainterPath()
    tri.moveTo(-s * 0.42, -s * 0.62)
    tri.lineTo(s * 0.74, 0)
    tri.lineTo(-s * 0.42, s * 0.62)
    tri.closeSubpath()
    if glow:
        for k, al in ((1.5, 28), (1.0, 60)):
            p.setPen(_pen(_c(col.name(), al), s * 0.22 * k))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(tri)
    p.setPen(Qt.PenStyle.NoPen)
    g = QLinearGradient(-s * 0.4, -s * 0.6, s * 0.7, s * 0.6)
    g.setColorAt(0, QColor(255, 255, 255, 250))
    g.setColorAt(1, _c(col.name(), 240))
    p.setBrush(QBrush(g))
    p.drawPath(tri)


def centro_estado(p, ctx, R, rd, col, col2=None, emblema=None, fam='extra'):
    """El contenido del centro según el estado: porcentaje + paso + tiempo restante, palomita, «!» o el emblema en reposo."""
    est = ctx.estado
    if est == 'trabajando':
        # v5.22: un velo oscuro detrás del texto (se lee sobre cualquier estilo), cifras de ancho fijo y nada por debajo de 12 px
        velo = QRadialGradient(QPointF(0, rd * 0.12), rd * 1.1)
        velo.setColorAt(0.0, QColor(2, 6, 14, 105))
        velo.setColorAt(1.0, QColor(2, 6, 14, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(velo))
        p.drawEllipse(QPointF(0, rd * 0.12), rd * 1.1, rd * 1.1)
        p.setPen(QColor(255, 255, 255))
        p.setFont(cifras(fuente(max(20, int(rd * 0.78)), peso=fam)))
        p.drawText(QRectF(-rd, -rd * 0.78, 2 * rd, rd * 1.2), int(Qt.AlignmentFlag.AlignCenter), f'{int(round(ctx.progreso * 100))}%')
        # justo debajo del porcentaje: cuánto falta; debajo, qué se está haciendo. Cada uno en UNA línea que quepa; si no cabe ni a
        # 10 px se omite (la barra de abajo lo dice): antes se partía o se salía del círculo en ventanas pequeñas
        f_eta = fuente_que_cabe(ctx.eta, rd * 1.8, max(12, int(rd * 0.23)), 10, 'extra', True) if ctx.eta else None
        if f_eta is not None:
            p.setPen(QColor(255, 236, 170, 250))
            p.setFont(f_eta)
            p.drawText(QRectF(-rd, rd * 0.36, 2 * rd, rd * 0.32), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), ctx.eta)
        f_txt = fuente_que_cabe(ctx.texto, rd * 1.75, max(12, int(rd * 0.19)), 10, 'medio') if ctx.texto else None
        if f_txt is not None:
            p.setPen(QColor(min(255, col.red() + 70), min(255, col.green() + 70), min(255, col.blue() + 70), 245))
            p.setFont(f_txt)
            p.drawText(QRectF(-rd, rd * (0.7 if f_eta is not None else 0.36), 2 * rd, rd * 0.32), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), ctx.texto)
    elif est == 'hecho':
        palomita(p, rd, ctx.marca, QColor('#FFC857') if ctx.tono == 'aviso' else col)
    elif est == 'error':
        p.setPen(QColor(255, 150, 150, int(255 * (1 - 0.5 * ctx.apagon))))
        p.setFont(fuente(max(30, int(rd * 1.5)), peso='extra'))
        p.drawText(QRectF(-rd, -rd, 2 * rd, 2 * rd), int(Qt.AlignmentFlag.AlignCenter), '!')
    else:
        if ctx.residuo > 0.01:
            palomita(p, rd, 1.0, col, ctx.residuo)
        (emblema or (lambda: play(p, rd * 0.62, col)))()


class Estilo:
    clave = ''
    nombre = ''
    descr = ''
    tema = 'noche'                       # superficies de la interfaz: noche | negro | grafito
    acento = '#22D3EE'                   # color de resaltado de toda la interfaz
    aurora = ('#0F62FE', '#8B5CF6', '#22D3EE')       # las 3 luces del fondo de todas las páginas
    pal = ('#FFFFFF',)                   # colores de las partículas
    modo = 'espiral'                     # espiral | ascenso | caida | orbita
    trazo = True                         # con estela (líneas) o solo puntos/burbujas
    cabeza = 2.4                         # tamaño de la cabeza de la partícula
    hud = False                          # el dial y las órbitas de mograf_ui encima del héroe
    vel_extra = 1.0

    def __init__(self):
        self.rot = [0.0] * 6

    # -- movimiento (cada cuadro)
    def avanzar(self, dt, vel):
        v = max(0.0, vel) * self.vel_extra
        for i, k in enumerate((3.0, -4.5, 7.0, 10.0, -2.0, 5.0)):
            self.rot[i] = (self.rot[i] + k * v * dt) % 360.0

    # -- dibujo
    def dibujar(self, p, c, R, ctx, R_base=None):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(c)
        if ctx.vibra > 0.01:
            p.translate(math.sin(ctx.t * 71.0) * ctx.vibra * R * 0.007, math.cos(ctx.t * 83.0) * ctx.vibra * R * 0.006)
        self.heroe(p, R, ctx)
        if ctx.flare > 0.01:
            f = 1.0 - ctx.flare
            col = QColor('#FFC857') if (ctx.tono == 'aviso' and ctx.estado == 'hecho') else (QColor('#FF6B6B') if ctx.estado == 'error' else QColor(self.acento))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            g = QRadialGradient(QPointF(0, 0), R * (0.6 + 1.1 * f))
            g.setColorAt(0.0, QColor(235, 255, 245, int(150 * ctx.flare ** 1.5)))
            g.setColorAt(0.5, _c(col.name(), 90 * ctx.flare))
            g.setColorAt(1.0, _c(col.name(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(0, 0), R * (0.6 + 1.1 * f), R * (0.6 + 1.1 * f))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(235, 255, 245, int(220 * ctx.flare)), max(1.5, R * 0.03 * ctx.flare)))
            p.drawEllipse(QPointF(0, 0), R * (0.45 + 0.85 * f), R * (0.45 + 0.85 * f))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.restore()

    def heroe(self, p, R, ctx):
        pass

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(10, 30 + int(30 * e), 40 + int(30 * e)))
        g.setColorAt(1.0, QColor(2, 6, 10))
        q.fillRect(QRectF(0, 0, W, H), g)

    def frente(self, p, W, H, c, t, estado):
        pass

    # -- utilidades
    @staticmethod
    def halo(p, R, col, a, radio=1.25):
        g = QRadialGradient(QPointF(0, 0), R * radio)
        g.setColorAt(0.4, _c(col.name(), a))
        g.setColorAt(1.0, _c(col.name(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), R * radio, R * radio)

    @staticmethod
    def atenuar(ctx):
        return (0.5 if ctx.estado == 'apagado' else 1.0) * (1.0 - 0.55 * ctx.apagon)


# =================================================================================================== 1 · ASTROLABIO
class Astrolabio(Estilo):
    clave = 'astrolabio'
    nombre = tr('Astrolabio')
    descr = tr('Engranajes de bronce, runas esmeralda y una gema: una máquina de relojería que trabaja por ti.')
    tema = 'noche'
    acento = '#22B573'
    aurora = ('#0B8F5B', '#1D6B7A', '#B8742C')
    pal = ('#7DFFB2', '#4FFFB0', '#4FD8FF', '#FFFFFF', '#B7FFE0', '#FFD166', '#B388FF', '#FF7BD5', '#FFB35C', '#E6C9FF', '#FFC857', '#FFE3A3')
    modo = 'espiral'
    hud = True

    def __init__(self):
        super().__init__()
        import orbe_mecanica
        self._orb = orbe_mecanica.OrbeMecanica()

    def avanzar(self, dt, vel):
        self._orb.avanzar(dt, vel)

    def dibujar(self, p, c, R, ctx, R_base=None):
        self._orb.dibujar(p, c, R, ctx.t, ctx.estado, ctx.hover, ctx.presion, ctx.progreso, ctx.marca, ctx.texto,
                          1.0 if ctx.apagon > 0 else 0.0, ctx.quieto, ctx.flare, R_base, ctx.fase, ctx.fase_t, ctx.tono, ctx.entrada,
                          ctx.vibra, (0.0, 0.0), ctx.residuo, ctx.apagon, ctx.eta, cortes=ctx.cortes)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(6, 34 + int(36 * e), 30 + int(30 * e)))
        g.setColorAt(0.5, QColor(3, 16, 16))
        g.setColorAt(1.0, QColor(1, 6, 8))
        q.fillRect(QRectF(0, 0, W, H), g)
        if estado == 'explotando':
            return
        grande = max(W, H)
        cg = QConicalGradient(c, -((t * (3.0 + 5.0 * e)) % 360.0))
        alfa_h, ancho_h = int(20 + 28 * e), 0.0085
        cg.setColorAt(0.0, QColor(70, 235, 160, alfa_h))
        cg.setColorAt(ancho_h, QColor(70, 235, 160, 0))
        for i in range(1, 9):
            pos = i / 9.0
            cg.setColorAt(pos - ancho_h, QColor(70, 235, 160, 0))
            cg.setColorAt(pos, QColor(70, 235, 160, alfa_h))
            cg.setColorAt(pos + ancho_h, QColor(70, 235, 160, 0))
        cg.setColorAt(1.0 - ancho_h, QColor(70, 235, 160, 0))
        cg.setColorAt(1.0, QColor(70, 235, 160, alfa_h))
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.fillRect(QRectF(0, 0, W, H), cg)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        velo = QRadialGradient(c, grande * 0.75)
        velo.setColorAt(0.10, QColor(3, 16, 16, 0))
        velo.setColorAt(0.85, QColor(3, 12, 14, 235))
        velo.setColorAt(1.0, QColor(2, 8, 10, 255))
        q.fillRect(QRectF(0, 0, W, H), velo)
        vig = QRadialGradient(QPointF(W / 2, H / 2), grande * 0.72)
        vig.setColorAt(0.55, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 150))
        q.fillRect(QRectF(0, 0, W, H), vig)


# =================================================================================================== 2 · SYNTHWAVE
class Synthwave(Estilo):
    clave = 'synthwave'
    nombre = tr('Synthwave')
    descr = tr('Un sol retro con franjas, anillos de neón y una cuadrícula que avanza hacia ti.')
    tema = 'negro'
    acento = '#E8457E'
    aurora = ('#FF2E93', '#7B2FF7', '#2BD2FF')
    pal = ('#FF3CAC', '#2BD2FF', '#FFE259', '#FFFFFF')
    modo = 'ascenso'
    cabeza = 2.6

    def heroe(self, p, R, ctx):
        rosa, cian = QColor('#FF2E93'), QColor('#2BD2FF')
        a = self.atenuar(ctx)
        p.setOpacity(a)
        self.halo(p, R, rosa, 60 + 40 * math.sin(ctx.t * 2.0) ** 2 + 40 * ctx.hover)
        # el sol
        rs = R * 0.70
        sol = QPainterPath()
        sol.addEllipse(QPointF(0, 0), rs, rs)
        p.save()
        p.setClipPath(sol)
        lg = QLinearGradient(0, -rs, 0, rs)
        lg.setColorAt(0.0, QColor('#FFE259'))
        lg.setColorAt(0.42, QColor('#FF9A3C'))
        lg.setColorAt(0.72, QColor('#FF2E93'))
        lg.setColorAt(1.0, QColor('#8E1FD0'))
        p.fillRect(QRectF(-rs, -rs, 2 * rs, 2 * rs), lg)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 7, 40))
        off = (ctx.t * 0.05 * max(0.4, ctx.vel * 0.5)) % 0.12                     # las franjas suben despacio
        for k in range(8):
            y = (0.02 + k * 0.12 - off) * R
            if y < -0.05 * R:
                continue
            p.drawRect(QRectF(-rs, y, 2 * rs, (0.012 + 0.012 * k) * R))
        p.restore()
        # anillos de neón
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k, al in ((2.6, 30), (1.0, 230)):
            p.setPen(_pen(_c('#FF2E93', al), R * 0.018 * k))
            p.drawEllipse(QPointF(0, 0), R * 0.93, R * 0.93)
        pen = QPen(_c('#2BD2FF', 235), R * 0.014)
        pen.setDashPattern([2.5, 5.0])
        pen.setDashOffset(-self.rot[0] * 0.6)
        p.setPen(pen)
        p.drawEllipse(QPointF(0, 0), R * 0.84, R * 0.84)
        for i in range(2):                                                         # dos satélites de neón
            ang = math.radians(self.rot[2] * 0.9 + i * 180)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_c('#FFFFFF', 255))
            p.drawEllipse(QPointF(R * 0.93 * math.cos(ang), R * 0.93 * math.sin(ang)), R * 0.028, R * 0.028)
        if ctx.estado == 'trabajando':
            arco_prog(p, R * 0.93, R * 0.016, ctx.progreso, cian, cortes=ctx.cortes)
        centro_estado(p, ctx, R, R * 0.42, cian, emblema=lambda: play(p, R * 0.30, QColor('#FFFFFF')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        hor = H * 0.64
        g = QLinearGradient(0, 0, 0, hor)
        g.setColorAt(0.0, QColor('#08011A'))
        g.setColorAt(0.65, QColor('#2A0A4F'))
        g.setColorAt(1.0, QColor(255, 46, 147, 150 + int(40 * e)))
        q.fillRect(QRectF(0, 0, W, hor), g)
        suelo = QLinearGradient(0, hor, 0, H)
        suelo.setColorAt(0.0, QColor('#240742'))
        suelo.setColorAt(1.0, QColor('#07010F'))
        q.fillRect(QRectF(0, hor, W, H - hor), suelo)
        rnd = random.Random(5)
        q.setPen(Qt.PenStyle.NoPen)
        for i in range(70):                                                         # estrellas que titilan
            x, y, f = rnd.random() * W, rnd.random() * hor * 0.85, rnd.random() * PI2
            q.setBrush(QColor(255, 255, 255, int(80 + 140 * (0.5 + 0.5 * math.sin(t * 2.2 + f)))))
            q.drawEllipse(QPointF(x, y), 1.4, 1.4)
        # la cuadrícula en perspectiva que avanza
        q.setPen(QPen(QColor(255, 60, 180, 120), 1.6))
        lines = []
        cx = W / 2
        for i in range(-14, 15):
            lines.append(QLineF(cx + i * 6, hor, cx + i * W * 0.11, H))
        n = 12
        fase = (t * 0.35 * (1.0 + 2.0 * e)) % 1.0
        for k in range(n):
            u = ((k + fase) / n) ** 2.3
            y = hor + (H - hor) * u
            lines.append(QLineF(0, y, W, y))
        q.drawLines(lines)
        glow = QLinearGradient(0, hor - 30, 0, hor + 30)
        glow.setColorAt(0.0, QColor(255, 46, 147, 0))
        glow.setColorAt(0.5, QColor(255, 120, 200, 130))
        glow.setColorAt(1.0, QColor(255, 46, 147, 0))
        q.fillRect(QRectF(0, hor - 30, W, 60), glow)


# =================================================================================================== 3 · REACTOR
class Reactor(Estilo):
    clave = 'reactor'
    nombre = tr('Reactor')
    descr = tr('Un núcleo hexagonal con anillos segmentados que giran en sentidos opuestos, estilo panel de nave.')
    tema = 'noche'
    acento = '#22D3EE'
    aurora = ('#0EA5E9', '#2563EB', '#22D3EE')
    pal = ('#22D3EE', '#FFFFFF', '#7DD3FC', '#38BDF8')
    modo = 'orbita'
    cabeza = 2.2

    def heroe(self, p, R, ctx):
        cian = QColor('#22D3EE')
        a = self.atenuar(ctx)
        p.setOpacity(a)
        self.halo(p, R, cian, 50 + 40 * ctx.hover + (35 if ctx.estado == 'trabajando' else 0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # marcas finas
        p.setPen(QPen(_c('#7DD3FC', 90), 1.2))
        marcas = []
        for i in range(90):
            ang = i * PI2 / 90 + math.radians(self.rot[4])
            l = 0.05 if i % 5 == 0 else 0.025
            marcas.append(QLineF(R * 0.995 * math.cos(ang), R * 0.995 * math.sin(ang), R * (0.995 - l) * math.cos(ang), R * (0.995 - l) * math.sin(ang)))
        p.drawLines(marcas)
        # anillo segmentado exterior (el que muestra el progreso: cada segmento se enciende)
        nseg = 12
        lit = ctx.progreso * nseg if ctx.estado == 'trabajando' else (nseg if ctx.estado == 'hecho' else 0)
        rect = QRectF(-R * 0.86, -R * 0.86, R * 1.72, R * 1.72)
        for i in range(nseg):
            ang0 = i * 360.0 / nseg + self.rot[1] * 0.25
            on = max(0.0, min(1.0, lit - i))
            al = 60 + 195 * on if ctx.estado != 'listo' else 110 + 70 * (0.5 + 0.5 * math.sin(ctx.t * 2 + i * 0.5))
            p.setPen(_pen(_c('#22D3EE', al), R * 0.05, Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, int(-ang0 * 16), int(-24 * 16))
        # anillo intermedio, en sentido contrario
        rect2 = QRectF(-R * 0.70, -R * 0.70, R * 1.40, R * 1.40)
        p.setPen(_pen(_c('#38BDF8', 170), R * 0.028, Qt.PenCapStyle.FlatCap))
        for i in range(8):
            p.drawArc(rect2, int((-i * 45 + self.rot[0] * 1.4) * 16), int(-30 * 16))
        p.setPen(_pen(_c('#FFFFFF', 150), R * 0.012))
        for i in range(3):
            p.drawArc(QRectF(-R * 0.62, -R * 0.62, R * 1.24, R * 1.24), int((i * 120 + self.rot[2]) * 16), 28 * 16)
        # radios
        p.setPen(QPen(_c('#22D3EE', 60), 1.2))
        p.drawLines([QLineF(R * 0.34 * math.cos(math.radians(60 * i + 30)), R * 0.34 * math.sin(math.radians(60 * i + 30)),
                            R * 0.58 * math.cos(math.radians(60 * i + 30)), R * 0.58 * math.sin(math.radians(60 * i + 30))) for i in range(6)])
        # el núcleo hexagonal que late
        lat = 1.0 + 0.05 * math.sin(ctx.t * 3.0) + (0.04 if ctx.estado == 'trabajando' else 0.0)
        hexa = QPolygonF([QPointF(R * 0.40 * lat * math.cos(math.radians(60 * i + 30)), R * 0.40 * lat * math.sin(math.radians(60 * i + 30))) for i in range(6)])
        g = QRadialGradient(QPointF(0, 0), R * 0.42)
        g.setColorAt(0.0, QColor(210, 250, 255, 240))
        g.setColorAt(0.55, QColor(34, 211, 238, 150))
        g.setColorAt(1.0, QColor(8, 60, 90, 230))
        p.setBrush(QBrush(g))
        p.setPen(_pen(_c('#9BE8FF', 220), R * 0.016))
        p.drawPolygon(hexa)
        # esquinas de visor
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(_c('#22D3EE', 150), R * 0.014, Qt.PenCapStyle.SquareCap))
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y, l = sx * R * 1.04, sy * R * 1.04, R * 0.14
            p.drawPolyline([QPointF(x - sx * l, y), QPointF(x, y), QPointF(x, y - sy * l)])
        centro_estado(p, ctx, R, R * 0.36, cian, emblema=lambda: play(p, R * 0.26, QColor('#FFFFFF')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.75)
        g.setColorAt(0.0, QColor(6, 36 + int(30 * e), 62 + int(40 * e)))
        g.setColorAt(1.0, QColor(2, 7, 16))
        q.fillRect(QRectF(0, 0, W, H), g)
        # cuadrícula de planos
        paso = 44.0
        off = (t * 6.0) % paso
        q.setPen(QPen(QColor(34, 211, 238, 24), 1.0))
        lineas = [QLineF(x - off, 0, x - off, H) for x in np.arange(0, W + paso, paso)]
        lineas += [QLineF(0, y - off * 0.5, W, y - off * 0.5) for y in np.arange(0, H + paso, paso)]
        q.drawLines(lineas)
        # círculos de radar y el barrido
        q.setBrush(Qt.BrushStyle.NoBrush)
        q.setPen(QPen(QColor(34, 211, 238, 34), 1.2))
        for k in range(1, 5):
            q.drawEllipse(c, k * max(W, H) * 0.13, k * max(W, H) * 0.13)
        cg = QConicalGradient(c, -((t * (30 + 80 * e)) % 360.0))
        cg.setColorAt(0.0, QColor(34, 211, 238, 70))
        cg.setColorAt(0.12, QColor(34, 211, 238, 0))
        cg.setColorAt(1.0, QColor(34, 211, 238, 0))
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QBrush(cg))
        q.drawEllipse(c, max(W, H) * 0.62, max(W, H) * 0.62)


# =================================================================================================== 4 · AGUJERO NEGRO
class Agujero(Estilo):
    clave = 'agujero'
    nombre = tr('Agujero negro')
    descr = tr('Un disco de acreción incandescente que gira alrededor de un horizonte de sucesos, con estrellas lejanas.')
    tema = 'negro'
    acento = '#F5832F'
    aurora = ('#F97316', '#7C2D12', '#FBBF24')
    pal = ('#FFB35C', '#FFFFFF', '#FF7A18', '#FFD166', '#FFE8B0')
    modo = 'espiral'
    cabeza = 2.6

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        self.halo(p, R, QColor('#FF7A18'), 55 + 35 * ctx.hover + (30 if ctx.estado == 'trabajando' else 0), 1.35)
        rh = R * 0.46                                                              # el horizonte
        # el disco de acreción: un degradado cónico que gira, en una elipse inclinada
        def disco(frente):
            p.save()
            p.rotate(-16)
            if frente:
                clip = QPainterPath()
                clip.addRect(QRectF(-R * 1.2, 0, R * 2.4, R * 1.2))
                p.setClipPath(clip)
            cg = QConicalGradient(QPointF(0, 0), self.rot[0] * 1.6)
            for pos, col in ((0.0, '#FFF4D6'), (0.2, '#FFB35C'), (0.45, '#FF5A1F'), (0.65, '#8A1F0A'), (0.85, '#FF8A2E'), (1.0, '#FFF4D6')):
                cg.setColorAt(pos, QColor(col))
            ex = QPainterPath()
            ex.addEllipse(QPointF(0, 0), R * 1.04, R * 0.21)
            hueco = QPainterPath()
            hueco.addEllipse(QPointF(0, 0), R * 0.50, R * 0.09)
            p.fillPath(ex.subtracted(hueco), QBrush(cg))
            p.restore()
        disco(False)
        # el disco negro y el anillo de fotones
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0))
        p.drawEllipse(QPointF(0, 0), rh, rh)
        # luz del disco doblada por la gravedad, por encima y por debajo del horizonte
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k, al in ((3.0, 46), (1.0, 245)):
            p.setPen(_pen(_c('#FFC070', al), R * 0.024 * k))
            p.drawArc(QRectF(-rh * 1.12, -rh * 1.12, rh * 2.24, rh * 2.24), 6 * 16, 168 * 16)      # la luz de detrás del disco, doblada por arriba
            p.setPen(_pen(_c('#FF8A3C', al * 0.55), R * 0.016 * k))
            p.drawArc(QRectF(-rh * 1.12, -rh * 1.12, rh * 2.24, rh * 2.24), 190 * 16, 160 * 16)     # y por abajo
        p.setPen(_pen(_c('#FFE6B8', 120), R * 0.012))
        p.drawEllipse(QPointF(0, 0), rh * 1.04, rh * 1.04)
        disco(True)
        if ctx.estado == 'trabajando':
            arco_prog(p, rh * 1.04, R * 0.018, ctx.progreso, QColor('#FFC070'), cortes=ctx.cortes)
        centro_estado(p, ctx, R, rh * 0.82, QColor('#FFC070'), emblema=lambda: play(p, rh * 0.62, QColor('#FFC070')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(34 + int(30 * e), 14, 8))
        g.setColorAt(0.5, QColor(10, 5, 8))
        g.setColorAt(1.0, QColor(2, 2, 5))
        q.fillRect(QRectF(0, 0, W, H), g)
        rnd = random.Random(11)
        q.setPen(Qt.PenStyle.NoPen)
        ang0 = t * (0.012 + 0.03 * e)                                               # las estrellas giran despacio alrededor del agujero
        for i in range(120):
            r = (0.06 + rnd.random() ** 0.7 * 0.9) * max(W, H) * 0.7
            a = rnd.random() * PI2 + ang0 * (1.4 - r / (max(W, H) * 0.7))
            tam = 0.8 + rnd.random() * 1.6
            q.setBrush(QColor(255, 235, 210, int(60 + 150 * (0.5 + 0.5 * math.sin(t * 1.6 + i)))))
            q.drawEllipse(QPointF(c.x() + r * math.cos(a), c.y() + 0.8 * r * math.sin(a)), tam, tam)


# =================================================================================================== 5 · LÍQUIDO
class Liquido(Estilo):
    clave = 'liquido'
    nombre = tr('Cristal líquido')
    descr = tr('Una gota de cristal que respira, se llena de luz con el progreso y refleja un fondo de pasteles suaves.')
    tema = 'noche'
    acento = '#8B5CF6'
    aurora = ('#7DD3FC', '#C084FC', '#F9A8D4')
    pal = ('#BAE6FD', '#E9D5FF', '#FBCFE8', '#FFFFFF')
    modo = 'ascenso'
    trazo = False
    cabeza = 5.0

    def _blob(self, R, t, amp, n=72):
        pts = []
        for i in range(n):
            a = i * PI2 / n
            r = R * (1.0 + amp * (0.050 * math.sin(3 * a + t * 1.3) + 0.040 * math.sin(5 * a - t * 1.7) + 0.030 * math.sin(2 * a + t * 0.9)))
            pts.append(QPointF(r * math.cos(a), r * math.sin(a)))
        return QPolygonF(pts)

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        trab = ctx.estado == 'trabajando'
        amp = 1.0 + (1.6 if trab else 0.0) + 1.2 * ctx.hover
        t = ctx.t
        rb = R * 0.80
        blob = self._blob(rb, t, amp)
        ruta = QPainterPath()
        ruta.addPolygon(blob)
        ruta.closeSubpath()
        # sombra suave debajo
        sg = QRadialGradient(QPointF(0, rb * 1.12), rb * 0.9)
        sg.setColorAt(0.0, QColor(10, 10, 40, 110))
        sg.setColorAt(1.0, QColor(10, 10, 40, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(sg))
        p.save()
        p.translate(0, rb * 1.0)
        p.scale(1.0, 0.22)
        p.drawEllipse(QPointF(0, 0), rb, rb)
        p.restore()
        # el cuerpo de cristal
        g = QRadialGradient(QPointF(-rb * 0.35, -rb * 0.4), rb * 1.5)
        g.setColorAt(0.0, QColor(240, 250, 255, 240))
        g.setColorAt(0.35, QColor(125, 211, 252, 215))
        g.setColorAt(0.75, QColor(192, 132, 252, 215))
        g.setColorAt(1.0, QColor(99, 102, 241, 235))
        p.setBrush(QBrush(g))
        p.drawPath(ruta)
        # el líquido que sube con el progreso (o el nivel en reposo)
        nivel = ctx.progreso if trab else (1.0 if ctx.estado == 'hecho' else 0.34)
        y0 = rb * (1.0 - 2.0 * nivel)
        p.save()
        p.setClipPath(ruta)
        agua = QPainterPath()
        agua.moveTo(-rb * 1.1, rb * 1.1)
        for k in range(0, 33):
            x = -rb * 1.1 + k * (rb * 2.2 / 32)
            agua.lineTo(x, y0 + math.sin(x / rb * 5.0 + t * 2.6) * rb * 0.035 * (1 + amp * 0.4))
        agua.lineTo(rb * 1.1, rb * 1.1)
        agua.closeSubpath()
        lg = QLinearGradient(0, y0, 0, rb)
        lg.setColorAt(0.0, QColor(56, 189, 248, 190))
        lg.setColorAt(1.0, QColor(129, 140, 248, 235))
        p.setBrush(QBrush(lg))
        p.drawPath(agua)
        p.restore()
        # reflejos y borde de luz
        p.setBrush(QColor(255, 255, 255, 120))
        p.save()
        p.translate(-rb * 0.34, -rb * 0.46)
        p.rotate(-28)
        p.drawEllipse(QPointF(0, 0), rb * 0.34, rb * 0.15)
        p.restore()
        p.setBrush(QColor(255, 255, 255, 190))
        p.drawEllipse(QPointF(rb * 0.42, -rb * 0.52), rb * 0.06, rb * 0.06)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(QColor(255, 255, 255, 150), R * 0.012))
        p.drawPolygon(blob)
        # burbujas que orbitan
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(6):
            ang = math.radians(self.rot[1] * 0.6 + i * 60)
            rr = R * (0.98 + 0.04 * math.sin(t * 2 + i))
            p.setBrush(QColor(255, 255, 255, 60))
            p.drawEllipse(QPointF(rr * math.cos(ang), rr * 0.9 * math.sin(ang)), R * 0.032, R * 0.032)
        if trab:
            arco_prog(p, R * 0.98, R * 0.012, ctx.progreso, QColor('#E9D5FF'), cortes=ctx.cortes)
        centro_estado(p, ctx, R, R * 0.40, QColor('#FFFFFF'), emblema=lambda: play(p, R * 0.28, QColor('#FFFFFF'), False))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QLinearGradient(0, 0, W, H)
        g.setColorAt(0.0, QColor('#1A1347'))
        g.setColorAt(0.5, QColor('#241257'))
        g.setColorAt(1.0, QColor('#0F2147'))
        q.fillRect(QRectF(0, 0, W, H), g)
        grande = max(W, H)
        for i, (hexa, fx, fy) in enumerate((('#7DD3FC', 0.13, 0.17), ('#C084FC', 0.11, 0.23), ('#F9A8D4', 0.09, 0.19), ('#818CF8', 0.15, 0.13))):
            cx = W * (0.5 + 0.38 * math.sin(t * fx + i * 1.7))
            cy = H * (0.5 + 0.34 * math.cos(t * fy + i * 2.3))
            rg = QRadialGradient(QPointF(cx, cy), grande * 0.42)
            rg.setColorAt(0.0, _c(hexa, 90 + 40 * e))
            rg.setColorAt(1.0, _c(hexa, 0))
            q.fillRect(QRectF(0, 0, W, H), rg)
        rnd = random.Random(3)
        q.setPen(Qt.PenStyle.NoPen)
        for i in range(26):                                                           # bokeh
            x = (rnd.random() * W + t * (4 + 6 * rnd.random())) % W
            y = (rnd.random() * H - t * (5 + 8 * rnd.random())) % H
            q.setBrush(QColor(255, 255, 255, int(14 + 22 * rnd.random())))
            q.drawEllipse(QPointF(x, y), 6 + rnd.random() * 18, 6 + rnd.random() * 18)


# =================================================================================================== 6 · PRISMA
class Prisma(Estilo):
    clave = 'prisma'
    nombre = tr('Prisma')
    descr = tr('Un cristal facetado que gira en 3D y descompone la luz en un abanico de colores.')
    tema = 'grafito'
    acento = '#A78BFA'
    aurora = ('#A78BFA', '#38BDF8', '#F472B6')
    pal = ('#FF6B6B', '#FFD166', '#7DFFB2', '#4FD8FF', '#B388FF', '#FF7BD5', '#FFFFFF')
    modo = 'espiral'
    cabeza = 2.6

    ARCO = ('#FF4D4D', '#FF9F43', '#FFE259', '#4ADE80', '#38BDF8', '#818CF8', '#C084FC')

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        t = ctx.t
        self.halo(p, R, QColor('#A78BFA'), 55 + 35 * ctx.hover)
        rot = math.radians(self.rot[0] * 1.3)
        rad = R * 0.60
        ytop, ybot, yeq = -R * 0.92, R * 0.88, -R * 0.04
        vert = []
        for i in range(6):
            ang = rot + i * PI2 / 6
            vert.append((rad * math.cos(ang), math.sin(ang), ang))
        # los rayos descompuestos salen por la derecha
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        base = math.radians(-14 + 4 * math.sin(t * 0.6))
        for k, col in enumerate(self.ARCO):
            ang = base + math.radians(k * 4.6)
            p.setPen(_pen(_c(col, 150 if ctx.estado != 'apagado' else 60), R * 0.022))
            p.drawLine(QPointF(R * 0.5, -R * 0.04), QPointF(R * 1.55 * math.cos(ang) + R * 0.4, R * 1.55 * math.sin(ang) * 0.9))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # caras: ordenadas por profundidad (las de detrás primero)
        caras = []
        for i in range(6):
            x0, z0, a0 = vert[i]
            x1, z1, a1 = vert[(i + 1) % 6]
            zm = (z0 + z1) / 2
            luz = 0.5 + 0.5 * math.cos((a0 + a1) / 2 - math.radians(-120))
            caras.append((zm, (QPointF(0, ytop), QPointF(x0, yeq), QPointF(x1, yeq)), luz, 0))
            caras.append((zm, (QPointF(0, ybot), QPointF(x1, yeq), QPointF(x0, yeq)), luz * 0.75, 1))
        caras.sort(key=lambda c: c[0])
        lit = ctx.progreso if ctx.estado == 'trabajando' else (1.0 if ctx.estado == 'hecho' else 0.0)
        for idx, (zm, pts, luz, abajo) in enumerate(caras):
            if zm < -0.15 and ctx.estado != 'apagado':
                al = 70
            else:
                al = 215
            k = (idx % 12) / 12.0
            on = 1.0 if (k <= lit) else 0.0
            col = QColor.fromHsvF((0.72 + 0.12 * luz + 0.05 * abajo + 0.08 * on) % 1.0, 0.45 + 0.35 * on, 0.55 + 0.45 * luz, al / 255.0)
            p.setBrush(col)
            p.setPen(_pen(QColor(255, 255, 255, 190 if zm > -0.15 else 70), R * 0.008))
            p.drawPolygon(QPolygonF(list(pts)))
        # destello que cruza una cara
        f = (t % 3.6) / 3.6
        if f < 0.3 and ctx.estado == 'listo':
            x = -rad * 0.6 + (f / 0.3) * rad * 1.2
            sp = QRadialGradient(QPointF(x, -R * 0.25), R * 0.2)
            sp.setColorAt(0, QColor(255, 255, 255, int(230 * math.sin(f / 0.3 * math.pi))))
            sp.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(sp))
            p.drawEllipse(QPointF(x, -R * 0.25), R * 0.2, R * 0.2)
        if ctx.estado == 'trabajando':
            cg = QConicalGradient(QPointF(0, 0), 90)
            arco_prog(p, R * 0.98, R * 0.014, ctx.progreso, QColor('#C4B5FD'), cortes=ctx.cortes)
        centro_estado(p, ctx, R, R * 0.34, QColor('#E9D5FF'), emblema=lambda: None)
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(26, 16, 48 + int(20 * e)))
        g.setColorAt(1.0, QColor(6, 4, 12))
        q.fillRect(QRectF(0, 0, W, H), g)
        # un haz blanco entra por la izquierda y se abre en abanico por la derecha
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.setPen(Qt.PenStyle.NoPen)
        haz = QLinearGradient(0, c.y(), c.x(), c.y())
        haz.setColorAt(0.0, QColor(255, 255, 255, 0))
        haz.setColorAt(1.0, QColor(255, 255, 255, 60))
        pol = QPolygonF([QPointF(0, c.y() - 8), QPointF(c.x(), c.y() - 3), QPointF(c.x(), c.y() + 3), QPointF(0, c.y() + 8)])
        q.setBrush(QBrush(haz))
        q.drawPolygon(pol)
        for k, col in enumerate(self.ARCO):
            ang = math.radians(-8 + k * 4.5 + 3 * math.sin(t * 0.5 + k))
            L = max(W, H)
            lg = QLinearGradient(c, QPointF(c.x() + L * math.cos(ang), c.y() + L * math.sin(ang)))
            lg.setColorAt(0.0, _c(col, 70 + 30 * e))
            lg.setColorAt(1.0, _c(col, 0))
            tri = QPolygonF([c, QPointF(c.x() + L * math.cos(ang - 0.016), c.y() + L * math.sin(ang - 0.016)),
                             QPointF(c.x() + L * math.cos(ang + 0.016), c.y() + L * math.sin(ang + 0.016))])
            q.setBrush(QBrush(lg))
            q.drawPolygon(tri)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        rnd = random.Random(8)
        for i in range(40):
            x, y = rnd.random() * W, rnd.random() * H
            q.setBrush(QColor(255, 255, 255, int(50 + 160 * (0.5 + 0.5 * math.sin(t * 2.4 + i * 1.7)))))
            q.drawEllipse(QPointF(x, y), 1.3, 1.3)


# =================================================================================================== 7 · ECUALIZADOR
class Ecualizador(Estilo):
    clave = 'ecualizador'
    nombre = tr('Ecualizador')
    descr = tr('Un anillo de barras de audio que baila: más grande cuanto más trabaja, con ondas de sonido de fondo.')
    tema = 'noche'
    acento = '#F472B6'
    aurora = ('#EC4899', '#8B5CF6', '#22D3EE')
    pal = ('#F472B6', '#22D3EE', '#FFFFFF', '#C084FC')
    modo = 'ascenso'
    cabeza = 2.8

    N = 64

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        t = ctx.t
        trab = ctx.estado == 'trabajando'
        amp = 0.07 + (0.30 + 0.16 * ctx.progreso if trab else 0.0) + 0.05 * ctx.hover
        if ctx.estado == 'hecho':
            amp = 0.05 + 0.20 * max(0.0, 1.0 - max(0.0, ctx.cierre) / 1.2)
        if ctx.estado == 'error':
            amp = 0.02
        beat = 0.5 + 0.5 * math.sin(t * 8.0) ** 2 if trab else 0.4
        self.halo(p, R, QColor('#F472B6'), 45 + 40 * ctx.hover + 40 * (beat if trab else 0))
        # el disco central
        rc = R * 0.44
        g = QRadialGradient(QPointF(-rc * 0.3, -rc * 0.4), rc * 1.6)
        g.setColorAt(0.0, QColor(60, 30, 90))
        g.setColorAt(1.0, QColor(14, 8, 30))
        p.setPen(_pen(QColor(244, 114, 182, 170), R * 0.014))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), rc, rc)
        # las barras: tres grupos de color por altura (3 llamadas)
        grupos = ([], [], [])
        lit = int(ctx.progreso * self.N) if trab else (self.N if ctx.estado == 'hecho' else -1)
        for i in range(self.N):
            ang = i * PI2 / self.N - math.pi / 2
            ruido = (math.sin(t * 3.1 + i * 0.9) + math.sin(t * 5.3 - i * 0.37) + math.sin(t * 1.7 + i * 2.1)) / 3.0
            h = R * (0.05 + amp * (0.55 + 0.45 * ruido) * (0.7 + 0.5 * beat))
            r0 = R * 0.52
            ca, sa = math.cos(ang), math.sin(ang)
            grupo = 0 if (i <= lit or lit < 0) else 2
            if i > lit >= 0:
                grupo = 2
            elif h > R * 0.2:
                grupo = 1
            grupos[grupo].append(QLineF(r0 * ca, r0 * sa, (r0 + h) * ca, (r0 + h) * sa))
        for lines, col, al in ((grupos[2], '#6B5B95', 140), (grupos[0], '#F472B6', 235), (grupos[1], '#22D3EE', 245)):
            if lines:
                p.setPen(_pen(_c(col, al), R * 0.034))
                p.drawLines(lines)
        # el osciloscopio circular
        pts = []
        for i in range(73):
            ang = i * PI2 / 72
            rr = R * 0.40 + R * 0.02 * math.sin(ang * 6 + t * 5.0) * (1 + 3 * amp)
            pts.append(QPointF(rr * math.cos(ang), rr * math.sin(ang)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(QColor(255, 255, 255, 120), R * 0.01))
        p.drawPolyline(QPolygonF(pts))
        centro_estado(p, ctx, R, R * 0.34, QColor('#F9A8D4'), emblema=lambda: play(p, R * 0.26, QColor('#F9A8D4')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0.0, QColor('#0B0620'))
        g.setColorAt(1.0, QColor('#150A30'))
        q.fillRect(QRectF(0, 0, W, H), g)
        q.setBrush(Qt.BrushStyle.NoBrush)
        for k, (col, fr, ph, am) in enumerate((('#F472B6', 1.6, 0.0, 0.07), ('#22D3EE', 2.3, 1.7, 0.055), ('#C084FC', 1.1, 3.1, 0.09))):
            q.setPen(_pen(_c(col, 56 + 40 * e), 2.4))
            pts = []
            for i in range(0, 49):
                x = W * i / 48
                y = H * (0.5 + 0.12 * (k - 1)) + math.sin(i * 0.5 * fr + t * (1.4 + 0.5 * k) + ph) * H * am * (1 + 1.6 * e)
                pts.append(QPointF(x, y))
            q.drawPolyline(QPolygonF(pts))
        for k in range(5):                                                            # barras de luz verticales que laten
            x = W * (0.12 + 0.19 * k)
            al = 14 + 16 * (0.5 + 0.5 * math.sin(t * 2.0 + k))
            lg = QLinearGradient(0, 0, 0, H)
            lg.setColorAt(0.0, QColor(244, 114, 182, 0))
            lg.setColorAt(0.5, QColor(244, 114, 182, int(al)))
            lg.setColorAt(1.0, QColor(244, 114, 182, 0))
            q.fillRect(QRectF(x - 3, 0, 6, H), lg)


# =================================================================================================== 8 · PLASMA
class Plasma(Estilo):
    clave = 'plasma'
    nombre = tr('Plasma')
    descr = tr('Una esfera de energía en llamas: el plasma se calienta con el progreso y suelta rayos y brasas.')
    tema = 'grafito'
    acento = '#F5832F'
    aurora = ('#EF4444', '#F97316', '#FBBF24')
    pal = ('#FFB35C', '#FF7A18', '#FFE08A', '#FF4D2E', '#FFFFFF')
    modo = 'ascenso'
    cabeza = 2.8
    N = 72

    def __init__(self):
        super().__init__()
        n = self.N
        yy, xx = np.mgrid[-1:1:complex(n), -1:1:complex(n)]
        self._xx, self._yy = xx.astype(np.float32), yy.astype(np.float32)
        self._rr = np.sqrt(xx * xx + yy * yy).astype(np.float32)
        self._mask = np.clip((1.0 - self._rr) * 9.0, 0.0, 1.0).astype(np.float32)
        lut = np.zeros((256, 4), np.uint8)
        for i in range(256):
            u = i / 255.0
            lut[i] = (min(255, int(255 * min(1.0, u * 2.2))), min(255, int(255 * max(0.0, u * 2.0 - 0.45))), min(255, int(255 * max(0.0, u * 3.0 - 2.0))), 255)
        self._lut = lut
        self._buf = None
        self._fase = 0.0

    def avanzar(self, dt, vel):
        super().avanzar(dt, vel)
        self._fase += dt * (0.6 + 0.5 * min(8.0, vel))

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        t = self._fase
        trab = ctx.estado == 'trabajando'
        calor = 0.55 + 0.45 * (ctx.progreso if trab else (1.0 if ctx.estado == 'hecho' else 0.2)) + 0.15 * ctx.hover
        self.halo(p, R, QColor('#FF7A18'), 60 + 70 * calor, 1.3)
        xx, yy, rr = self._xx, self._yy, self._rr
        v = (np.sin(xx * 3.4 + t * 1.3) + np.sin(yy * 3.0 - t * 1.1) + np.sin((xx + yy) * 2.6 + t * 0.9)
             + np.sin(rr * 6.0 - t * 2.0) + np.sin(np.hypot(xx - 0.4 * math.sin(t * 0.7), yy + 0.4 * math.cos(t * 0.6)) * 5.0 - t * 1.5))
        idx = np.clip(((v + 5.0) / 10.0 * calor * 1.25) * 255.0, 0, 255).astype(np.uint8)
        img = self._lut[idx]
        img[..., 3] = (self._mask * 255).astype(np.uint8)
        self._buf = np.ascontiguousarray(img)
        qi = QImage(self._buf.data, self.N, self.N, self.N * 4, QImage.Format.Format_RGBA8888)
        rs = R * 0.80
        p.drawImage(QRectF(-rs, -rs, 2 * rs, 2 * rs), qi)
        # borde brillante (fresnel) y núcleo caliente
        g = QRadialGradient(QPointF(0, 0), rs)
        g.setColorAt(0.78, QColor(255, 120, 30, 0))
        g.setColorAt(1.0, QColor(255, 200, 120, 190))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), rs, rs)
        # rayos que saltan al trabajar
        if trab or ctx.estado == 'hecho':
            rnd = random.Random(int(ctx.t * 14))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for _ in range(3 if trab else 1):
                ang = rnd.random() * PI2
                pts = [QPointF(0, 0)]
                x = y = 0.0
                for k in range(7):
                    ang += rnd.uniform(-0.5, 0.5)
                    x += math.cos(ang) * rs * 0.15
                    y += math.sin(ang) * rs * 0.15
                    pts.append(QPointF(x, y))
                for k, al in ((3.0, 50), (1.0, 230)):
                    p.setPen(_pen(_c('#FFE9B8', al), R * 0.012 * k))
                    p.drawPolyline(QPolygonF(pts))
        if trab:
            arco_prog(p, R * 0.94, R * 0.014, ctx.progreso, QColor('#FFC070'), cortes=ctx.cortes)
        centro_estado(p, ctx, R, R * 0.40, QColor('#FFE9B8'), emblema=lambda: play(p, R * 0.28, QColor('#FFFFFF')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(QPointF(c.x(), c.y() + H * 0.1), max(W, H) * 0.85)
        g.setColorAt(0.0, QColor(70 + int(50 * e), 22, 10))
        g.setColorAt(0.5, QColor(22, 8, 8))
        g.setColorAt(1.0, QColor(6, 3, 4))
        q.fillRect(QRectF(0, 0, W, H), g)
        q.setPen(Qt.PenStyle.NoPen)
        rnd = random.Random(9)
        for i in range(14):                                                           # calor que sube: manchas suaves
            x = rnd.random() * W
            y = (H * 1.1 - ((t * (14 + 10 * rnd.random()) + rnd.random() * H) % (H * 1.2)))
            rg = QRadialGradient(QPointF(x, y), 60 + 50 * rnd.random())
            rg.setColorAt(0.0, QColor(255, 120, 30, int(26 + 20 * e)))
            rg.setColorAt(1.0, QColor(255, 120, 30, 0))
            q.setBrush(QBrush(rg))
            q.drawEllipse(QPointF(x, y), 110, 110)


# =================================================================================================== 9 · CARRETE DE CINE
class Carrete(Estilo):
    clave = 'carrete'
    nombre = tr('Carrete de cine')
    descr = tr('Un carrete de película con su cinta, la luz del proyector y polvo dorado: cine de verdad.')
    tema = 'grafito'
    acento = '#FBBF24'
    aurora = ('#D97706', '#92400E', '#FBBF24')
    pal = ('#FFD27A', '#FFF1CC', '#E0A030', '#FFFFFF')
    modo = 'ascenso'
    cabeza = 2.2

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        trab = ctx.estado == 'trabajando'
        ambar = QColor('#FBBF24')
        self.halo(p, R, QColor('#E0A030'), 40 + 35 * ctx.hover + (25 if trab else 0))
        # la cinta enrollada alrededor del carrete: fotogramas que se encienden con el progreso
        n = 36
        lit = int(ctx.progreso * n) if trab else (n if ctx.estado == 'hecho' else -1)
        p.setPen(Qt.PenStyle.NoPen)
        base = self.rot[1] * 0.3
        rin, rout = R * 0.86, R * 1.02
        for i in range(n):
            ang = base + i * 360.0 / n
            on = i <= lit
            p.save()
            p.rotate(ang)
            p.setBrush(QColor(255, 210, 110, 235) if on else QColor(70, 52, 30, 230))
            p.drawRect(QRectF(-R * 0.045, -rout, R * 0.09, rout - rin))
            p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(QColor(20, 14, 8, 255), R * 0.02))
        p.drawEllipse(QPointF(0, 0), R * 1.03, R * 1.03)
        p.drawEllipse(QPointF(0, 0), R * 0.85, R * 0.85)
        # el disco del carrete (gira)
        rd = R * 0.80
        g = QRadialGradient(QPointF(-rd * 0.35, -rd * 0.4), rd * 1.5)
        g.setColorAt(0.0, QColor('#5A4A38'))
        g.setColorAt(0.6, QColor('#2A2018'))
        g.setColorAt(1.0, QColor('#120D08'))
        p.setPen(_pen(QColor(224, 160, 48, 190), R * 0.014))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), rd, rd)
        p.save()
        p.rotate(self.rot[0] * 1.2)
        fondo_h = QColor(8, 6, 4)
        p.setPen(_pen(QColor(224, 160, 48, 150), R * 0.01))
        for i in range(6):                                                         # los 6 agujeros grandes
            ang = i * PI2 / 6
            p.setBrush(fondo_h)
            p.drawEllipse(QPointF(R * 0.50 * math.cos(ang), R * 0.50 * math.sin(ang)), R * 0.19, R * 0.19)
        # el buje
        p.setBrush(QColor('#3A2E20'))
        p.drawEllipse(QPointF(0, 0), R * 0.20, R * 0.20)
        p.setBrush(fondo_h)
        for i in range(3):
            ang = i * PI2 / 3 + 0.5
            p.drawEllipse(QPointF(R * 0.10 * math.cos(ang), R * 0.10 * math.sin(ang)), R * 0.035, R * 0.035)
        p.restore()
        if trab:
            arco_prog(p, R * 0.855, R * 0.012, ctx.progreso, ambar, cortes=ctx.cortes)
        centro_estado(p, ctx, R, R * 0.26, ambar, emblema=lambda: None)
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(46 + int(30 * e), 28, 12))
        g.setColorAt(1.0, QColor(8, 5, 3))
        q.fillRect(QRectF(0, 0, W, H), g)
        # el cono de luz del proyector, con parpadeo
        parp = 0.85 + 0.15 * math.sin(t * 24.0) * math.sin(t * 7.3)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        origen = QPointF(W * 0.04, H * 0.06)
        lg = QLinearGradient(origen, c)
        lg.setColorAt(0.0, QColor(255, 220, 150, int(90 * parp)))
        lg.setColorAt(1.0, QColor(255, 200, 120, int(24 * parp)))
        cono = QPolygonF([origen, QPointF(c.x() + W * 0.42, c.y() - H * 0.34), QPointF(c.x() + W * 0.34, c.y() + H * 0.5)])
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QBrush(lg))
        q.drawPolygon(cono)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # rayones verticales que aparecen y desaparecen
        rnd = random.Random(int(t * 6))
        q.setPen(QPen(QColor(255, 235, 200, 40), 1.0))
        q.drawLines([QLineF(x, 0, x + rnd.uniform(-2, 2), H) for x in (rnd.random() * W for _ in range(2))])
        # tiras de película que cruzan arriba y abajo
        q.setPen(Qt.PenStyle.NoPen)
        for y, sentido in ((H * 0.07, 1), (H * 0.93, -1)):
            q.setBrush(QColor(14, 10, 6, 235))
            q.drawRect(QRectF(0, y - 14, W, 28))
            off = (t * 26 * sentido) % 30
            q.setBrush(QColor(224, 160, 48, 90))
            for k in range(-1, int(W / 30) + 2):
                q.drawRect(QRectF(k * 30 + off, y - 10, 12, 6))
                q.drawRect(QRectF(k * 30 + off, y + 4, 12, 6))


# =================================================================================================== 10 · MATRIX
class Matrix(Estilo):
    clave = 'matrix'
    nombre = tr('Código')
    descr = tr('Lluvia de código verde, anillos de caracteres que cambian y un porcentaje en consola.')
    tema = 'negro'
    acento = '#22C55E'
    aurora = ('#16A34A', '#065F46', '#22C55E')
    pal = ('#7CFF9B', '#22C55E', '#B6FFC9', '#FFFFFF')
    modo = 'caida'
    cabeza = 2.2
    GLIFOS = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉ0123456789ABCDEF<>/{}[]=+*'

    def __init__(self):
        super().__init__()
        self._rnd = random.Random(2)
        self._anillos = {}
        self._t_anillo = -9.0
        self._tiras = None
        self._tira_clave = None

    def _texto_anillo(self, n):
        return ''.join(self._rnd.choice(self.GLIFOS) for _ in range(n))

    def _pixmap_anillo(self, tam, n, rad, col, dpr):
        """La corona de caracteres dibujada UNA vez (se rehace cada ~0,18 s al cambiar los glifos); luego solo se gira."""
        pm = QPixmap(int(tam * dpr), int(tam * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.translate(tam / 2.0, tam / 2.0)
        txt = self._texto_anillo(n)
        f = fuente(max(9, int(tam * 0.045)), peso='negrita')
        f.setFamily('Consolas')
        q.setFont(f)
        for i, ch in enumerate(txt):
            q.save()
            q.rotate(i * 360.0 / n)
            q.setPen(_c(col, 120 + 135 * self._rnd.random()))
            q.drawText(QRectF(-tam * 0.03, -rad - tam * 0.03, tam * 0.06, tam * 0.06), int(Qt.AlignmentFlag.AlignCenter), ch)
            q.restore()
        q.end()
        return pm

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        verde = QColor('#22C55E')
        trab = ctx.estado == 'trabajando'
        dpr = p.device().devicePixelRatioF() if hasattr(p.device(), 'devicePixelRatioF') else 1.0
        self.halo(p, R, verde, 36 + 30 * ctx.hover + (28 if trab else 0))
        tam = int(R * 2.3)
        if ctx.t - self._t_anillo > (0.18 if trab else 0.5) or not self._anillos:
            self._t_anillo = ctx.t
            self._anillos = {'a': self._pixmap_anillo(tam, 40, R * 0.93, '#7CFF9B', dpr), 'b': self._pixmap_anillo(tam, 28, R * 0.70, '#22C55E', dpr)}
        d = tam
        for clave, giro in (('a', self.rot[0] * 0.8), ('b', -self.rot[1] * 0.6)):
            p.save()
            p.rotate(giro)
            p.drawPixmap(QRectF(-d / 2, -d / 2, d, d), self._anillos[clave], QRectF(self._anillos[clave].rect()))
            p.restore()
        # el marco de consola
        p.setBrush(QColor(2, 14, 6, 235))
        p.setPen(_pen(_c('#22C55E', 200), R * 0.012))
        rc = R * 0.52
        p.drawRoundedRect(QRectF(-rc, -rc, 2 * rc, 2 * rc), R * 0.07, R * 0.07)
        p.setPen(_pen(_c('#7CFF9B', 220), R * 0.02, Qt.PenCapStyle.SquareCap))
        for sx in (-1, 1):                                                          # los corchetes [ ]
            x = sx * rc * 1.12
            p.drawPolyline([QPointF(x - sx * R * 0.09, -rc * 1.02), QPointF(x, -rc * 1.02), QPointF(x, rc * 1.02), QPointF(x - sx * R * 0.09, rc * 1.02)])
        # barrido de línea de escaneo
        y = ((ctx.t * 0.5) % 1.0 * 2.0 - 1.0) * rc
        p.setPen(QPen(_c('#7CFF9B', 70), 1.4))
        p.drawLine(QPointF(-rc, y), QPointF(rc, y))
        if trab:
            arco_prog(p, R * 0.985, R * 0.012, ctx.progreso, verde, cortes=ctx.cortes)
        centro_estado(p, ctx, R, rc * 0.80, verde, emblema=lambda: play(p, rc * 0.46, QColor('#7CFF9B')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(4, 26 + int(26 * e), 10))
        g.setColorAt(1.0, QColor(1, 6, 2))
        q.fillRect(QRectF(0, 0, W, H), g)

    def frente(self, p, W, H, c, t, estado):
        """La lluvia de código: columnas de glifos (tiras pre-dibujadas) que caen a distinta velocidad."""
        dpr = p.device().devicePixelRatioF() if hasattr(p.device(), 'devicePixelRatioF') else 1.0
        if self._tiras is None or self._tira_clave != round(dpr, 2):
            self._tira_clave = round(dpr, 2)
            self._tiras = []
            f = fuente(15, peso='negrita')
            f.setFamily('Consolas')
            rnd = random.Random(21)
            for k in range(4):
                alto = 520
                pm = QPixmap(int(18 * dpr), int(alto * dpr))
                pm.setDevicePixelRatio(dpr)
                pm.fill(Qt.GlobalColor.transparent)
                q = QPainter(pm)
                q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                q.setFont(f)
                for j in range(alto // 17):
                    u = j / (alto / 17.0)
                    q.setPen(QColor(60, 255, 120, int(25 + 190 * u ** 2.4)))
                    q.drawText(QRectF(0, j * 17, 18, 17), int(Qt.AlignmentFlag.AlignCenter), rnd.choice(self.GLIFOS))
                q.end()
                self._tiras.append(pm)
        p.save()
        p.setOpacity(0.55)
        n = int(W / 26) + 1
        for i in range(n):
            x = i * 26.0 + 4
            vel = 60 + (i * 37 % 90)
            y = ((t * vel + i * 211) % (H + 520)) - 520
            p.drawPixmap(QPointF(x, y), self._tiras[i % 4])
        p.restore()


# =================================================================================================== 11 · ORBE (React Bits «Orb»)
class Orbe(Estilo):
    """v5.5.8 (pedido: «incorpora el efecto Orb de React Bits en Inicio»): el shader de Orb —un anillo de luz morado / cian sobre azul profundo,
    de radio ondulado por ruido, con una luz que lo recorre y el resplandor del borde— calculado con numpy a N×N y escalado suave (como Plasma).
    Al pasar el ratón el anillo se ondula y gira más rápido (el «hover intensity» de Orb); al trabajar se enciende con el progreso."""
    clave = 'orbe'
    nombre = tr('Orbe')
    descr = tr('El orbe de luz de React Bits: un anillo morado y cian que fluye, se ondula al pasar el ratón y se enciende al trabajar.')
    tema = 'negro'
    acento = '#9C43FE'
    aurora = ('#9C43FE', '#4CC2E9', '#101499')
    pal = ('#C69BFF', '#9C43FE', '#4CC2E9', '#8AE4FF', '#FFFFFF')
    modo = 'orbita'
    trazo = False
    cabeza = 2.2
    N = 112
    C1, C2, C3 = (np.array([0.611765, 0.262745, 0.996078], np.float32), np.array([0.298039, 0.760784, 0.913725], np.float32),
                  np.array([0.062745, 0.078431, 0.600000], np.float32))
    INTERIOR, ESCALA_RUIDO = 0.6, 0.65

    def __init__(self):
        super().__init__()
        n = self.N
        yy, xx = np.mgrid[-1.25:1.25:complex(n), -1.25:1.25:complex(n)]
        self._xx, self._yy = xx.astype(np.float32), yy.astype(np.float32)
        self._buf = None
        self._fase = 0.0
        self._hover = 0.0

    def avanzar(self, dt, vel):
        super().avanzar(dt, vel)
        self._fase += dt * (1.0 + 0.6 * min(6.0, vel))

    @staticmethod
    def _ruido(x, y, t):
        """Ruido suave en [0, 1] (sumas de senos desfasados: lo que hace el simplex 3D del shader, más barato)."""
        return 0.5 + 0.125 * (np.sin(x * 3.1 + t * 1.7) + np.sin(y * 2.7 - t * 1.3) + np.sin((x + y) * 2.2 + t * 0.9)
                              + np.sin(np.hypot(x - 0.3, y + 0.2) * 3.4 - t * 1.1))

    def heroe(self, p, R, ctx):
        a = self.atenuar(ctx)
        p.setOpacity(a)
        self._hover += (ctx.hover - self._hover) * 0.12
        t = self._fase * 0.5
        trab = ctx.estado == 'trabajando'
        brillo = 1.0 + (0.5 * ctx.progreso if trab else 0.25 if ctx.estado == 'hecho' else 0.0)
        x, y = self._xx, self._yy
        h = self._hover
        if h > 0.01:                                          # la onda del «hover» de Orb
            x = x + h * 0.08 * np.sin(y * 10.0 + t * 2.0)
            y = y + h * 0.08 * np.sin(x * 10.0 + t * 2.0)
        giro = t * (0.3 + 0.9 * h)
        cg, sg = math.cos(giro), math.sin(giro)
        x, y = x * cg - y * sg, x * sg + y * cg
        ln = np.sqrt(x * x + y * y) + 1e-6
        ang = np.arctan2(y, x)
        n0 = self._ruido(x * self.ESCALA_RUIDO, y * self.ESCALA_RUIDO, t)
        ri = self.INTERIOR
        r0 = (ri + (1.0 - ri) * 0.4) + ((ri + (1.0 - ri) * 0.6) - (ri + (1.0 - ri) * 0.4)) * n0
        d0 = np.abs(ln - r0)                                    # distancia al anillo
        v0 = 1.0 / (1.0 + d0 * 10.0)
        v0 = v0 * np.clip((r0 * 1.05 - ln) / (r0 * 0.05), 0.0, 1.0)
        cl = np.cos(ang + t * 2.0) * 0.5 + 0.5
        pa = -t
        px, py = math.cos(pa), math.sin(pa)
        d = np.hypot(x - px * r0, y - py * r0)
        v1 = (1.5 / (1.0 + d * d * 5.0)) * (1.0 / (1.0 + d0 * 50.0))
        v2 = np.clip((1.0 - ln) / np.maximum(1e-3, 1.0 - (ri + (1.0 - ri) * n0 * 0.5)), 0.0, 1.0)
        v3 = np.clip((ln - ri) / ((1.0 - ri) * 0.5), 0.0, 1.0)
        col = self.C1[None, None, :] * (1.0 - cl[..., None]) + self.C2[None, None, :] * cl[..., None]
        col = self.C3[None, None, :] * (1.0 - v0[..., None]) + col * v0[..., None]
        col = np.clip((col + v1[..., None]) * (v2 * v3)[..., None] * brillo, 0.0, 1.0)
        alfa = col.max(axis=2)
        rgb = col / np.maximum(alfa, 1e-4)[..., None]
        img = np.empty((self.N, self.N, 4), np.uint8)
        img[..., :3] = (rgb * 255.0).astype(np.uint8)
        img[..., 3] = (alfa * 255.0 * a).astype(np.uint8)
        self._buf = np.ascontiguousarray(img)
        qi = QImage(self._buf.data, self.N, self.N, self.N * 4, QImage.Format.Format_RGBA8888)
        rs = R * 1.05
        self.halo(p, R, QColor('#9C43FE'), 40 + 40 * brillo * (0.6 + 0.4 * h), 1.25)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.drawImage(QRectF(-rs * 1.25, -rs * 1.25, rs * 2.5, rs * 2.5), qi)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if trab:
            arco_prog(p, R * 0.94, R * 0.014, ctx.progreso, QColor('#4CC2E9'), QColor('#E9D8FF'), cortes=ctx.cortes)
        centro_estado(p, ctx, R, R * 0.40, QColor('#E9D8FF'), emblema=lambda: play(p, R * 0.28, QColor('#FFFFFF')))
        p.setOpacity(1.0)

    def fondo(self, q, W, H, c, e, t, estado):
        g = QRadialGradient(c, max(W, H) * 0.8)
        g.setColorAt(0.0, QColor(26 + int(20 * e), 14, 52 + int(30 * e)))
        g.setColorAt(0.45, QColor(9, 7, 22))
        g.setColorAt(1.0, QColor(2, 2, 6))
        q.fillRect(QRectF(0, 0, W, H), g)


# --------------------------------------------------------------------------------------------------- registro
ESTILOS = {c.clave: c for c in (Orbe, Astrolabio, Synthwave, Reactor, Agujero, Liquido, Prisma, Ecualizador, Plasma, Carrete, Matrix)}
ORDEN = tuple(ESTILOS.keys())
POR_DEFECTO = 'orbe'                     # v5.5.8: el orbe de React Bits es el Inicio de fábrica (el elegido en Ajustes › Interfaz se respeta)


def crear(clave):
    """Una instancia NUEVA del estilo (cada botón/miniatura lleva la suya: guardan su propia rotación)."""
    return ESTILOS.get(clave, ESTILOS[POR_DEFECTO])()


def clave_guardada():
    try:
        import ajustes_ui
        c = str(ajustes_ui.leer_prefs().get('go_estilo') or POR_DEFECTO)
        return c if c in ESTILOS else POR_DEFECTO
    except Exception:
        return POR_DEFECTO


def dibujar_miniatura(est, ctx, w, h, dpr=1.0, destino=None):
    """Dibuja el estilo `est` (instancia viva) con el contexto `ctx` en un pixmap w x h: fondo + héroe. Sirve para las tarjetas de
    Ajustes (estáticas o animadas al pasar el ratón)."""
    pm = destino or QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    c = QPointF(w * 0.5, h * 0.50)
    bajo = QPixmap(max(8, int(w / 2)), max(8, int(h / 2)))
    q = QPainter(bajo)
    q.scale(bajo.width() / float(w), bajo.height() / float(h))
    est.fondo(q, w, h, c, 0.3 if ctx.estado == 'trabajando' else 0.0, ctx.t, ctx.estado)
    q.end()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawPixmap(QRectF(0, 0, w, h), bajo, QRectF(bajo.rect()))
    est.frente(p, w, h, c, ctx.t, ctx.estado)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    est.dibujar(p, c, h * 0.34, ctx, h * 0.34)
    p.end()
    return pm


def miniatura(clave, w=320, h=180, t=2.4, estado='listo', dpr=1.0):
    """Una imagen del estilo (fondo + héroe) para las tarjetas de Ajustes."""
    est = crear(clave)
    ctx = Ctx()
    ctx.t = t
    ctx.estado = estado
    ctx.progreso = 0.62
    for _ in range(int(t * 30)):
        est.avanzar(1 / 30.0, 1.0 if estado == 'listo' else 4.0)
    return dibujar_miniatura(est, ctx, w, h, dpr)
