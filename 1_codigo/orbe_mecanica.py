# CineCaptions · By Cinema Productions
# 1_codigo/orbe_mecanica.py — el botón GO como un astrolabio mecánico: anillo de runas, engranaje de bronce, filigrana y gema de esmeralda.
"""
Todo es VECTOR (QPainter), nada es una imagen escalada: las piezas estáticas se dibujan UNA vez en capas con sobremuestreo (1,5x-2x
los píxeles reales de la pantalla) y cada cuadro solo las gira con interpolación suave; la gema, los rayos y las luces se dibujan en
vivo. Por eso se ve nítido en cualquier tamaño y pantalla 4K.

Capas (de afuera hacia adentro):
  1. runas       anillo oscuro de vidrio con 28 runas esmeralda y marcas; gira muy lento (+)
  2. engranaje   rueda dentada de bronce (36 dientes) con remaches y 4 botones; gira en sentido contrario (-)
  3. filigrana   celosía de bronce entrelazada; gira a otra velocidad (+)
  4. domo        cristal esmeralda con reflejos y borde de bronce (fijo)
  5. gema        triángulo «play» facetado con rayos de luz que laten (en vivo)
Estados: listo (todo gira lento y respira) · trabajando (gira rápido, el progreso es un arco de luz en el anillo y el porcentaje va en el
domo) · hecho (la gema se vuelve una palomita) · error (tinte rojo y «!») · apagado (sin luz).
"""
import math
import random
import threading
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)

import qt_kit as ui
from qt_kit import fuente


def _cifras(f):
    """v5.22: cifras de ancho fijo (tnum): el porcentaje no baila mientras cuenta."""
    try:
        f.setFeature(QFont.Tag('tnum'), 1)
    except Exception:
        pass
    return f

BRONCE = ((0.00, '#4a2e16'), (0.09, '#b27a41'), (0.20, '#f3c98f'), (0.29, '#8a5629'), (0.41, '#3b220f'), (0.54, '#c58a4c'),
          (0.65, '#f7d6a4'), (0.75, '#7b4a22'), (0.88, '#b87d42'), (1.00, '#4a2e16'))
ESM = QColor(58, 230, 140)
ESM_CLARO = QColor(150, 255, 200)
ROJO = QColor(255, 90, 90)
AMBAR = QColor(255, 190, 70)
CIAN = QColor(79, 216, 255)
VIOLETA = QColor(190, 140, 255)
ROSA = QColor(255, 123, 213)
# cada paso de GO enciende una pieza distinta del astrolabio: (pieza, color)
FASES_ORBE = {'timeline': ('runas', ESM_CLARO), 'voz': ('fili', CIAN), 'ia': ('gema', VIOLETA), 'diseno': ('engr', QColor(255, 205, 120)),
              'sfx': ('botones', ROSA), 'resolve': ('domo', QColor(220, 255, 235))}


def _bronce(cx, cy, giro=0.0, mate=1.0):
    g = QConicalGradient(QPointF(cx, cy), giro)
    for pos, c in BRONCE:
        col = QColor(c)
        if mate != 1.0:
            col = col.darker(int(100 + (1.0 - mate) * 120))
        g.setColorAt(pos, col)
    return g


def _poligono_polar(cx, cy, puntos):
    path = QPainterPath()
    for i, (ang, rad) in enumerate(puntos):
        x, y = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def _anillo(cx, cy, r_ext, r_int):
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), r_ext, r_ext)
    hueco = QPainterPath()
    hueco.addEllipse(QPointF(cx, cy), r_int, r_int)
    return path.subtracted(hueco)


def _lienzo(lado):
    img = QImage(lado, lado, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    return img, p


# -- capas estaticas (en un sistema de coordenadas de radio R=1000, escalado al tamaño pedido) -------------------------------------
def _capa_runas(lado):
    img, p = _lienzo(lado)
    k = lado / 2300.0
    p.translate(lado / 2, lado / 2)
    p.scale(k, k)
    # cuerpo del anillo: vidrio oscuro verdoso
    cuerpo = _anillo(0, 0, 985, 800)
    g = QRadialGradient(QPointF(-250, -300), 1300)
    g.setColorAt(0.0, QColor('#10261c'))
    g.setColorAt(0.6, QColor('#08140f'))
    g.setColorAt(1.0, QColor('#040a07'))
    p.fillPath(cuerpo, QBrush(g))
    # luz del borde (conico): arcos brillantes en el filo de afuera y de adentro
    for r, ancho, alfa in ((978, 7, 150), (808, 5, 120)):
        cg = QConicalGradient(QPointF(0, 0), 30)
        cg.setColorAt(0.00, QColor(ESM.red(), ESM.green(), ESM.blue(), alfa))
        cg.setColorAt(0.18, QColor(ESM.red(), ESM.green(), ESM.blue(), 20))
        cg.setColorAt(0.5, QColor(ESM.red(), ESM.green(), ESM.blue(), alfa // 2))
        cg.setColorAt(0.72, QColor(ESM.red(), ESM.green(), ESM.blue(), 20))
        cg.setColorAt(1.00, QColor(ESM.red(), ESM.green(), ESM.blue(), alfa))
        p.setPen(QPen(QBrush(cg), ancho))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), r, r)
    # marcas finas
    p.setPen(QPen(QColor(ESM.red(), ESM.green(), ESM.blue(), 80), 3))
    for i in range(180):
        a = i * math.tau / 180
        largo = 22 if i % 5 == 0 else 11
        p.drawLine(QPointF(812 * math.cos(a), 812 * math.sin(a)), QPointF((812 + largo) * math.cos(a), (812 + largo) * math.sin(a)))
    # runas
    azar = random.Random(11)
    for i in range(28):
        a = i * math.tau / 28
        p.save()
        p.rotate(math.degrees(a) + 90)
        p.translate(0, -905)
        alto, ancho = 78, 36
        trazos = [((0, -alto / 2), (0, alto / 2))]
        for _ in range(azar.randint(1, 2)):
            y0 = azar.uniform(-0.45, 0.2) * alto
            signo = azar.choice((-1, 1))
            trazos.append(((0, y0), (signo * ancho * azar.uniform(0.6, 1.0), y0 + azar.uniform(0.25, 0.55) * alto * azar.choice((-1, 1)))))
        for ancho_l, alfa in ((16, 36), (8, 90), (4.2, 255)):
            col = ESM_CLARO if ancho_l < 5 else ESM
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), alfa), ancho_l, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for (x0, y0), (x1, y1) in trazos:
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        p.restore()
    p.end()
    return img                                  # (QImage: se puede hacer en un hilo de fondo; OrbeMecanica la pasa a QPixmap)


def _capa_engranaje(lado):
    img, p = _lienzo(lado)
    k = lado / 2300.0
    p.translate(lado / 2, lado / 2)
    p.scale(k, k)
    n = 36
    puntos = []
    paso = math.tau / n
    for i in range(n):
        a0 = i * paso
        puntos += [(a0 + paso * 0.02, 700), (a0 + paso * 0.17, 770), (a0 + paso * 0.47, 770), (a0 + paso * 0.62, 700)]
    dientes = _poligono_polar(0, 0, puntos)
    cuerpo = dientes.subtracted(QPainterPath())
    hueco = QPainterPath()
    hueco.addEllipse(QPointF(0, 0), 560, 560)
    rueda = cuerpo.subtracted(hueco)
    # sombra de la rueda sobre el fondo
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 90))
    p.save(); p.translate(10, 22); p.drawPath(rueda); p.restore()
    p.fillPath(rueda, QBrush(_bronce(0, 0, 20)))
    # relieve: borde interior luminoso + exterior oscuro + degradado radial de volumen
    vol = QRadialGradient(QPointF(0, 0), 780)
    vol.setColorAt(0.70, QColor(0, 0, 0, 0))
    vol.setColorAt(0.93, QColor(255, 220, 160, 30))
    vol.setColorAt(1.0, QColor(0, 0, 0, 110))
    p.fillPath(rueda, QBrush(vol))
    vol2 = QRadialGradient(QPointF(0, 0), 700)
    vol2.setColorAt(0.78, QColor(0, 0, 0, 0))
    vol2.setColorAt(1.0, QColor(255, 235, 190, 60))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(vol2))
    p.drawPath(rueda)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 224, 170, 170), 5))
    p.drawEllipse(QPointF(0, 0), 562, 562)
    p.setPen(QPen(QColor(30, 16, 6, 220), 8))
    p.drawEllipse(QPointF(0, 0), 556, 556)
    p.setPen(QPen(QColor(255, 230, 190, 110), 3))
    p.drawPath(dientes)
    # remaches
    for i in range(12):
        a = i * math.tau / 12 + math.tau / 24
        x, y = 636 * math.cos(a), 636 * math.sin(a)
        rg = QRadialGradient(QPointF(x - 8, y - 10), 30)
        rg.setColorAt(0, QColor('#fbe3bd'))
        rg.setColorAt(0.5, QColor('#a8703a'))
        rg.setColorAt(1, QColor('#3a2210'))
        p.setPen(QPen(QColor(25, 12, 4, 200), 2))
        p.setBrush(QBrush(rg))
        p.drawEllipse(QPointF(x, y), 24, 24)
    p.end()
    return img                                  # (QImage: se puede hacer en un hilo de fondo; OrbeMecanica la pasa a QPixmap)


def _capa_filigrana(lado):
    img, p = _lienzo(lado)
    k = lado / 2300.0
    p.translate(lado / 2, lado / 2)
    p.scale(k, k)
    # fondo oscuro de la celosia
    cuerpo = _anillo(0, 0, 548, 436)
    g = QRadialGradient(QPointF(0, 0), 560)
    g.setColorAt(0.78, QColor('#06110c'))
    g.setColorAt(1.0, QColor('#0b1c14'))
    p.fillPath(cuerpo, QBrush(g))
    p.save()
    p.setClipPath(cuerpo)
    # celosia: 12 elipses entrelazadas
    for pasada, (ancho, alfa) in enumerate(((22, 255), (8, 200))):
        for fino, (n_l, desfase, rx, ry) in enumerate(((12, 0, 150, 82), (12, 15, 116, 56))):
            for i in range(n_l):
                p.save()
                p.rotate(i * 360 / n_l + desfase)
                p.translate(0, -492)
                p.setBrush(Qt.BrushStyle.NoBrush)
                if pasada == 0:
                    p.setPen(QPen(QBrush(_bronce(0, 0, 60 + i * 20)), ancho * (0.55 if fino else 1.0)))
                else:
                    p.setPen(QPen(QColor(255, 226, 176, 150), 3 if fino else 4))
                p.drawEllipse(QPointF(0, 0), rx, ry)
                p.restore()
    # destellos de esmeralda entre los lazos
    for i in range(12):
        a = (i + 0.5) * math.tau / 12
        x, y = 492 * math.cos(a), 492 * math.sin(a)
        rg = QRadialGradient(QPointF(x, y), 46)
        rg.setColorAt(0, QColor(ESM.red(), ESM.green(), ESM.blue(), 170))
        rg.setColorAt(1, QColor(ESM.red(), ESM.green(), ESM.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(rg))
        p.drawEllipse(QPointF(x, y), 46, 46)
    p.restore()
    # filos de bronce
    for r, ancho in ((548, 14), (436, 12)):
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QBrush(_bronce(0, 0, 40)), ancho))
        p.drawEllipse(QPointF(0, 0), r, r)
        p.setPen(QPen(QColor(255, 232, 190, 130), 3))
        p.drawEllipse(QPointF(0, 0), r - ancho / 2 + 2, r - ancho / 2 + 2)
    p.end()
    return img                                  # (QImage: se puede hacer en un hilo de fondo; OrbeMecanica la pasa a QPixmap)


def _capa_domo(lado):
    img, p = _lienzo(lado)
    k = lado / 2300.0
    p.translate(lado / 2, lado / 2)
    p.scale(k, k)
    # cristal esmeralda oscuro con luz interior
    g = QRadialGradient(QPointF(0, 40), 440)
    g.setColorAt(0.0, QColor('#1c6a45'))
    g.setColorAt(0.55, QColor('#0d3a26'))
    g.setColorAt(1.0, QColor('#04120c'))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(0, 0), 428, 428)
    # borde de bronce
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QBrush(_bronce(0, 0, 200)), 22))
    p.drawEllipse(QPointF(0, 0), 428, 428)
    p.setPen(QPen(QColor(255, 232, 190, 140), 3))
    p.drawEllipse(QPointF(0, 0), 418, 418)
    p.setPen(QPen(QColor(0, 0, 0, 160), 5))
    p.drawEllipse(QPointF(0, 0), 441, 441)
    p.end()
    return img                                  # (QImage: se puede hacer en un hilo de fondo; OrbeMecanica la pasa a QPixmap)


def _capa_vidrio(lado):
    """El reflejo del domo (va POR ENCIMA de la gema): un arco de luz arriba a la izquierda y un resplandor verde abajo."""
    img, p = _lienzo(lado)
    k = lado / 2300.0
    p.translate(lado / 2, lado / 2)
    p.scale(k, k)
    p.save()
    clip = QPainterPath()
    clip.addEllipse(QPointF(0, 0), 416, 416)
    p.setClipPath(clip)
    lg = QLinearGradient(QPointF(-260, -380), QPointF(120, -40))
    lg.setColorAt(0.0, QColor(255, 255, 255, 120))
    lg.setColorAt(0.55, QColor(255, 255, 255, 14))
    lg.setColorAt(1.0, QColor(255, 255, 255, 0))
    arco = QPainterPath()
    arco.moveTo(-370, -150)
    arco.cubicTo(-300, -330, -60, -410, 150, -330)
    arco.cubicTo(-40, -300, -250, -240, -330, -60)
    arco.closeSubpath()
    p.fillPath(arco, QBrush(lg))
    rg = QRadialGradient(QPointF(0, 440), 360)
    rg.setColorAt(0.0, QColor(ESM.red(), ESM.green(), ESM.blue(), 110))
    rg.setColorAt(1.0, QColor(ESM.red(), ESM.green(), ESM.blue(), 0))
    p.fillRect(QRectF(-420, -420, 840, 840), QBrush(rg))
    p.restore()
    p.end()
    return img                                  # (QImage: se puede hacer en un hilo de fondo; OrbeMecanica la pasa a QPixmap)


def _capa_botones(lado):
    """Los 4 botones de bronce sobre el engranaje (fijos): siguiente, volumen, ajustes, anterior."""
    img, p = _lienzo(lado)
    k = lado / 2300.0
    p.translate(lado / 2, lado / 2)
    p.scale(k, k)
    for i, tipo in enumerate(('sig', 'vol', 'aju', 'ant')):
        a = math.radians(-45 + i * 90)
        x, y = 690 * math.cos(a), 690 * math.sin(a)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawEllipse(QPointF(x + 4, y + 12), 74, 74)
        g = QRadialGradient(QPointF(x - 22, y - 26), 96)
        g.setColorAt(0, QColor('#f7d6a4'))
        g.setColorAt(0.45, QColor('#b57a3e'))
        g.setColorAt(1, QColor('#3c2410'))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(30, 16, 6, 230), 3))
        p.drawEllipse(QPointF(x, y), 72, 72)
        p.setBrush(QColor(8, 22, 15))
        p.setPen(QPen(QColor(255, 226, 176, 150), 3))
        p.drawEllipse(QPointF(x, y), 52, 52)
        p.setPen(QPen(ESM_CLARO, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QColor(ESM_CLARO.red(), ESM_CLARO.green(), ESM_CLARO.blue(), 200))
        if tipo in ('sig', 'ant'):
            s = 1 if tipo == 'sig' else -1
            for dx in (-16, 6):
                tri = QPainterPath()
                tri.moveTo(x + s * (dx - 12), y - 22)
                tri.lineTo(x + s * (dx + 12), y)
                tri.lineTo(x + s * (dx - 12), y + 22)
                tri.closeSubpath()
                p.drawPath(tri)
        elif tipo == 'vol':
            cuerpo = QPainterPath()
            cuerpo.moveTo(x - 28, y - 10); cuerpo.lineTo(x - 12, y - 10); cuerpo.lineTo(x + 6, y - 26); cuerpo.lineTo(x + 6, y + 26)
            cuerpo.lineTo(x - 12, y + 10); cuerpo.lineTo(x - 28, y + 10); cuerpo.closeSubpath()
            p.drawPath(cuerpo)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(x - 6, y - 22, 40, 44), -50 * 16, 100 * 16)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x, y), 20, 20)
            for j in range(8):
                aj = j * math.tau / 8
                p.drawLine(QPointF(x + 26 * math.cos(aj), y + 26 * math.sin(aj)), QPointF(x + 36 * math.cos(aj), y + 36 * math.sin(aj)))
    # los 4 rombos cardinales de la filigrana
    for i in range(4):
        a = math.radians(i * 90)
        x, y = 492 * math.cos(a), 492 * math.sin(a)
        rombo = QPainterPath()
        rombo.moveTo(x, y - 50); rombo.lineTo(x + 36, y); rombo.lineTo(x, y + 50); rombo.lineTo(x - 36, y); rombo.closeSubpath()
        p.setBrush(QBrush(_bronce(x, y, 30)))
        p.setPen(QPen(QColor(28, 14, 5, 230), 3))
        p.drawPath(rombo)
        p.setBrush(QColor(ESM.red(), ESM.green(), ESM.blue(), 230))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x, y), 11, 11)
    p.end()
    return img                                  # (QImage: se puede hacer en un hilo de fondo; OrbeMecanica la pasa a QPixmap)


class OrbeMecanica:
    """Dibuja el orbe. Una sola instancia por boton; las capas se cachean por tamaño y densidad de pantalla."""
    LADO_BASE = 2300           # las capas se hacen en este sistema de coordenadas (radio 1000 = el radio del orbe)

    def __init__(self):
        self._capas = {}
        self._clave = None
        self._pedido = None                  # (lado, desde cuándo) el tamaño que se pide ahora
        self._hilo = None
        self._nuevas = None                  # (lado, {capa: QImage}) que dejó listas el hilo de fondo
        self.rot = {'runas': 0.0, 'engr': 0.0, 'fili': 0.0, 'rayos': 0.0}

    @staticmethod
    def _hacer(pix):
        return {'runas': _capa_runas(pix), 'engr': _capa_engranaje(pix), 'fili': _capa_filigrana(pix),
                'domo': _capa_domo(pix), 'vidrio': _capa_vidrio(pix), 'botones': _capa_botones(pix)}

    def _asegurar(self, R, dpr):
        """Las capas del tamaño que toca. v5.5.10 (el usuario: «la página de inicio tiene fallas con la animación, se queda congelado»):
        antes, cada vez que el tamaño cambiaba un poco (redimensionar, maximizar, otra pantalla) se rehacían LAS SEIS capas aquí mismo, en el
        hilo de la interfaz: ~2,5 s con la animación quieta (el vigía de congelaciones lo anotó en _capa_filigrana). Ahora: la primera vez se
        hacen rápido a baja resolución; las buenas se hacen en un hilo de fondo (QImage) cuando el tamaño se queda quieto 0,25 s y, mientras,
        se dibujan las que había (escaladas: se ven igual). Si las que hay sirven (no son más pequeñas ni el doble de grandes), no se rehacen."""
        pix = max(256, int(round(2.3 * R * dpr * 1.25 / 64.0)) * 64)        # 1,25x los pixeles reales: nitidez al girar sin pasarse de coste
        pix = min(pix, 3072)
        listas = self._nuevas
        if listas is not None:                                               # el hilo terminó: a QPixmap (en el hilo de la interfaz) y se cambian
            self._nuevas = None
            self._capas = {k: QPixmap.fromImage(v) for k, v in listas[1].items()}
            self._clave = listas[0]
        if not self._capas:                                                  # la primera vez no hay nada que enseñar: rápido, a baja resolución
            rapido = min(pix, 768)
            self._capas = {k: QPixmap.fromImage(v) for k, v in self._hacer(rapido).items()}
            self._clave = rapido
        if self._clave / 1.8 <= pix <= self._clave * 1.06:
            self._pedido = None
            return self._capas
        ahora = time.monotonic()
        if self._pedido is None or self._pedido[0] != pix:
            self._pedido = (pix, ahora)                                      # (arrastrando el borde de la ventana cambia en cada cuadro)
        elif ahora - self._pedido[1] >= 0.25 and (self._hilo is None or not self._hilo.is_alive()):
            def trabajo(lado=pix):
                try:
                    self._nuevas = (lado, self._hacer(lado))
                except Exception:
                    pass
            self._hilo = threading.Thread(target=trabajo, name='orbe-capas', daemon=True)
            self._hilo.start()
        return self._capas

    def avanzar(self, dt, velocidad):
        """Los giros (grados/s): lentos en reposo; 'velocidad' (1 = reposo) los acelera al pasar el mouse o al trabajar."""
        self.rot['runas'] = (self.rot['runas'] + 2.6 * velocidad * dt) % 360
        self.rot['engr'] = (self.rot['engr'] - 4.2 * velocidad * dt) % 360
        self.rot['fili'] = (self.rot['fili'] + 7.0 * velocidad * dt) % 360
        self.rot['rayos'] = (self.rot['rayos'] + 10.0 * velocidad * dt) % 360

    @staticmethod
    def _capa(p, pm, R, giro=0.0, alfa=1.0, esc=1.0, dx=0.0, dy=0.0):
        d = 2.3 * R * esc
        p.save()
        if dx or dy:
            p.translate(dx, dy)
        p.rotate(giro)
        p.setOpacity(max(0.0, min(1.0, alfa)))
        p.drawPixmap(QRectF(-d / 2, -d / 2, d, d), pm, QRectF(pm.rect()))
        p.restore()

    # el orden de las capas, cuando entra cada una (s) y cuanto las mueve el raton (paralaje, en radios)
    ENTRADA = {'runas': 0.0, 'engr': 0.15, 'fili': 0.30, 'botones': 0.38, 'domo': 0.45, 'vidrio': 0.55, 'gema': 0.62}
    PARALAJE = {'runas': 0.010, 'engr': 0.018, 'fili': 0.028, 'botones': 0.018, 'domo': 0.040, 'vidrio': 0.052, 'gema': 0.060}

    def dibujar(self, p, c, R, t, estado, hover=0.0, presion=0.0, progreso=0.0, marca=0.0, texto='', rojo=0.0, quieto=False,
                flare=0.0, R_base=None, fase='', fase_t=9.0, tono='ok', entrada=9.0, vibra=0.0, par=(0.0, 0.0), residuo=0.0,
                apagon=0.0, eta='', luz=None, cortes=()):
        """estado: listo | apagado | trabajando | hecho | error.  fase: el paso en curso (resalta una pieza distinta del astrolabio);
        fase_t: segundos desde que cambió; tono 'aviso' = terminó con avisos (ámbar); entrada: segundos desde que apareció (las
        piezas se ensamblan de fuera hacia dentro); vibra 0..1: temblor de carga; par: posición del ratón -1..1 (paralaje);
        luz: (x, y) del cursor respecto al centro, en radios (o None): el metal y el cristal lo reflejan, sin mover nada;
        residuo 0..1: la palomita que se desvanece al volver al reposo; apagon 0..1: el orbe se apaga tras un error."""
        dpr = p.device().devicePixelRatioF() if hasattr(p.device(), 'devicePixelRatioF') else 1.0
        capas = self._asegurar(R_base or R, dpr)
        respira = 0.5 - 0.5 * math.cos(t * math.tau / 3.2)
        apagado = estado == 'apagado'
        acento = AMBAR if (tono == 'aviso' and estado in ('hecho',)) else (ROJO if estado == 'error' else ESM)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(c)
        if vibra > 0.01:                                             # temblor de carga antes del estallido
            p.translate(math.sin(t * 71.0) * vibra * R * 0.007, math.cos(t * 83.0) * vibra * R * 0.006)
        # halo exterior que respira
        if not apagado:
            a = (0.16 + 0.12 * respira + 0.10 * hover + (0.14 if estado == 'trabajando' else 0.0) + 0.16 * vibra) * (1.0 - 0.7 * apagon)
            g = QRadialGradient(QPointF(0, 0), R * 1.24)
            g.setColorAt(0.45, QColor(acento.red(), acento.green(), acento.blue(), int(255 * min(1.0, a))))
            g.setColorAt(1.0, QColor(acento.red(), acento.green(), acento.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(0, 0), R * 1.24, R * 1.24)
        base = (0.45 if apagado else 1.0) * (1.0 - 0.55 * apagon)
        ensamblando = entrada < 1.4

        def pieza(nombre, giro=0.0, alfa=1.0):
            """alfa/escala/giro de entrada + paralaje del ratón para una capa."""
            e_ = 1.0
            esc_ = 1.0
            if ensamblando:
                e_ = max(0.0, min(1.0, (entrada - self.ENTRADA[nombre]) / 0.55))
                esc_ = 1.0 + 0.22 * (1.0 - e_) ** 2
                giro += (1.0 - e_) ** 2 * (-50.0 if nombre in ('runas', 'fili') else 50.0)
                e_ = e_ ** 1.4
            k = self.PARALAJE[nombre] * R
            self._capa(p, capas[nombre], R, giro, alfa * base * e_, esc_, par[0] * k, par[1] * k)

        pieza('runas', self.rot['runas'])
        pieza('engr', self.rot['engr'])
        pieza('fili', self.rot['fili'])
        pieza('botones')
        pieza('domo')
        # --- el cursor como foco de luz: se refleja en el bronce, las runas y el cristal (nada se mueve)
        if hover > 0.02 and estado in ('listo', 'trabajando', 'hecho', 'error'):          # al pasar el ratón: solo se enciende el borde
            p.save()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for rad, ancho, al in ((0.995, 0.05, 28), (0.995, 0.014, 150), (0.43, 0.02, 110)):
                p.setPen(QPen(QColor(acento.red(), acento.green(), acento.blue(), int(al * hover)), R * ancho))
                p.drawEllipse(QPointF(0, 0), R * rad, R * rad)
            p.restore()
        # --- el resalte de la fase en curso (cada paso enciende una pieza distinta del astrolabio)
        if estado == 'trabajando' and fase in FASES_ORBE:
            self._resalte(p, R, fase, fase_t, t)
        # --- respiracion en reposo: una luz recorre los anillos cada pocos segundos
        if estado == 'listo' and not quieto and not ensamblando:
            for desfase, rad, ancho in ((0.0, 0.905, 0.05), (3.5, 0.665, 0.07)):
                f = ((t + desfase) % 7.0) / 7.0 * 4.4
                if f < 1.0:
                    s_ = math.sin(f * math.pi)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(ESM_CLARO.red(), ESM_CLARO.green(), ESM_CLARO.blue(), int(120 * s_)), R * ancho, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    p.drawArc(QRectF(-R * rad, -R * rad, 2 * R * rad, 2 * R * rad), int((90 - 360 * f) * 16), 55 * 16)
        # --- progreso: un arco de luz en el filo interior del anillo de runas
        # v5.22: sobre su pista (se ve lo que falta), más grueso, aclarándose hacia la cabeza y con un corte donde acaba cada paso
        if estado == 'trabajando':
            rad = R * 0.805
            caja = QRectF(-rad, -rad, 2 * rad, 2 * rad)
            pr = max(0.004, min(1.0, progreso))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(2, 14, 10, 120), R * 0.05))
            p.drawEllipse(QPointF(0, 0), rad, rad)
            p.setPen(QPen(QColor(ESM.red(), ESM.green(), ESM.blue(), 52), R * 0.012))
            p.drawEllipse(QPointF(0, 0), rad, rad)
            for grosor, al in ((R * 0.08, 26), (R * 0.045, 72)):
                p.setPen(QPen(QColor(ESM.red(), ESM.green(), ESM.blue(), al), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(caja, 90 * 16, -int(360 * 16 * pr))
            g_ = QConicalGradient(QPointF(0, 0), 90)
            g_.setColorAt(0.0, ESM)
            g_.setColorAt(max(0.0005, 1.0 - pr), QColor(235, 255, 244))
            g_.setColorAt(1.0, ESM)
            p.setPen(QPen(QBrush(g_), R * 0.022, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(caja, 90 * 16, -int(360 * 16 * pr))
            if cortes:
                p.setPen(QPen(QColor(2, 14, 10, 235), max(1.4, R * 0.011)))
                for f_ in cortes:
                    a_ = math.radians(90 - 360 * f_)
                    u_ = QPointF(math.cos(a_), -math.sin(a_))
                    p.drawLine(u_ * (rad - R * 0.03), u_ * (rad + R * 0.03))
            ang = math.radians(90 - 360 * min(1.0, progreso))
            cab = QPointF(rad * math.cos(ang), -rad * math.sin(ang))
            hg = QRadialGradient(cab, R * 0.07)
            hg.setColorAt(0, QColor(255, 255, 255, 255))
            hg.setColorAt(0.4, QColor(ESM_CLARO.red(), ESM_CLARO.green(), ESM_CLARO.blue(), 160))
            hg.setColorAt(1, QColor(ESM.red(), ESM.green(), ESM.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(hg))
            p.drawEllipse(cab, R * 0.07, R * 0.07)
        # --- el contenido del domo
        r_domo = R * 0.428
        gema_a = 1.0
        if ensamblando:
            gema_a = max(0.0, min(1.0, (entrada - self.ENTRADA['gema']) / 0.5)) ** 1.4
        kp = self.PARALAJE['gema'] * R
        if estado in ('listo', 'apagado'):
            p.save()
            p.translate(par[0] * kp, par[1] * kp)
            self._gema(p, R, t, hover, respira, (0.45 if apagado else 1.0) * gema_a * (1.0 - residuo * 0.0))
            p.restore()
            if residuo > 0.01:                                       # la palomita del final se desvanece al volver al reposo
                self._palomita(p, R, r_domo, 1.0, residuo, acento)
        elif estado == 'trabajando':
            self._gema(p, R, t, hover, respira, 0.10)
            # v5.22: un velo oscuro en el domo para que el texto se lea, cifras de ancho fijo y textos de 12 px como mínimo
            velo = QRadialGradient(QPointF(0, r_domo * 0.1), r_domo * 0.98)
            velo.setColorAt(0.0, QColor(1, 10, 8, 150))
            velo.setColorAt(0.75, QColor(1, 10, 8, 90))
            velo.setColorAt(1.0, QColor(1, 10, 8, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(velo))
            p.drawEllipse(QPointF(0, r_domo * 0.1), r_domo * 0.98, r_domo * 0.98)
            p.setPen(QColor(255, 255, 255, 255))
            p.setFont(_cifras(fuente(max(22, int(R * 0.27)), peso='extra')))
            p.drawText(QRectF(-r_domo, -r_domo * 0.66, 2 * r_domo, r_domo * 0.95), int(Qt.AlignmentFlag.AlignCenter), f'{int(round(progreso * 100))}%')
            # justo debajo del porcentaje: cuánto falta; debajo de eso, qué se está haciendo. Cada uno en UNA línea que quepa en el
            # domo; si no cabe ni a 10 px se omite (la barra de abajo de Inicio lo dice): antes se partía o se salía del cristal
            from estilos_inicio import fuente_que_cabe
            f_eta = fuente_que_cabe(eta, r_domo * 1.8, max(12, int(R * 0.078)), 10, 'extra', True) if eta else None
            if f_eta is not None:
                p.setPen(QColor(255, 236, 170, 250))
                p.setFont(f_eta)
                p.drawText(QRectF(-r_domo, r_domo * 0.18, 2 * r_domo, r_domo * 0.3), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), eta)
            f_txt = fuente_que_cabe(texto, r_domo * 1.7, max(12, int(R * 0.066)), 10, 'medio') if texto else None
            if f_txt is not None:
                p.setPen(QColor(200, 245, 222, 245))
                p.setFont(f_txt)
                p.drawText(QRectF(-r_domo, r_domo * (0.48 if f_eta is not None else 0.24), 2 * r_domo, r_domo * 0.3), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), texto)
        elif estado == 'hecho':
            self._gema(p, R, t, hover, respira, 0.0)
            self._palomita(p, R, r_domo, marca, 1.0, acento)
        elif estado == 'error':
            self._gema(p, R, t, hover, respira, 0.2 * (1.0 - apagon))
            p.setPen(QColor(255, 150, 150, int(255 * (1.0 - 0.5 * apagon))))
            p.setFont(fuente(max(36, int(R * 0.5)), peso='extra'))
            p.drawText(QRectF(-r_domo, -r_domo, 2 * r_domo, 2 * r_domo), int(Qt.AlignmentFlag.AlignCenter), '!')
        pieza('vidrio', 0.0, 1.0 if not apagado else 0.5)
        if flare > 0.01:                                  # el destello del clic: un resplandor que se expande y un anillo de luz
            f = 1.0 - flare
            col = acento if estado in ('hecho', 'error') else ESM
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            g = QRadialGradient(QPointF(0, 0), R * (0.6 + 1.1 * f))
            g.setColorAt(0.0, QColor(235, 255, 240, int(150 * flare ** 1.5)))
            g.setColorAt(0.5, QColor(col.red(), col.green(), col.blue(), int(90 * flare)))
            g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(0, 0), R * (0.6 + 1.1 * f), R * (0.6 + 1.1 * f))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(235, 255, 240, int(220 * flare)), max(1.5, R * 0.03 * flare)))
            p.drawEllipse(QPointF(0, 0), R * (0.45 + 0.85 * f), R * (0.45 + 0.85 * f))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if estado == 'error' and rojo > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 60, 60, int(60 * rojo + 50 * apagon)))
            p.drawEllipse(QPointF(0, 0), R * 0.99, R * 0.99)
        p.restore()

    def _luz_cursor(self, p, R, lx, ly, k):
        """Un foco de luz en la posición del cursor: reflejo cálido en el engranaje, verde en las runas y un brillo en el cristal."""
        L = math.hypot(lx, ly)
        if L < 1e-3:
            return
        ux, uy = lx / L, ly / L
        inten = k * (0.30 + 0.70 * max(0.0, 1.0 - max(0.0, L - 0.3) / 1.5))
        if inten < 0.03:
            return
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setPen(Qt.PenStyle.NoPen)
        for r_ext, r_int, dist, radio, col, al in ((0.77, 0.56, 0.665, 0.30, (255, 226, 170), 85), (0.985, 0.80, 0.90, 0.26, (110, 255, 190), 55)):
            p.setClipPath(_anillo(0, 0, R * r_ext, R * r_int))
            cx, cy = ux * R * dist, uy * R * dist
            g = QRadialGradient(QPointF(cx, cy), R * radio)
            g.setColorAt(0.0, QColor(col[0], col[1], col[2], int(al * inten)))
            g.setColorAt(1.0, QColor(col[0], col[1], col[2], 0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx, cy), R * radio, R * radio)
        clip = QPainterPath()
        clip.addEllipse(QPointF(0, 0), R * 0.41, R * 0.41)
        p.setClipPath(clip)
        d = min(L, 1.0) * R * 0.30
        cx, cy = ux * d, uy * d
        g = QRadialGradient(QPointF(cx, cy), R * 0.34)
        g.setColorAt(0.0, QColor(235, 255, 245, int(95 * inten)))
        g.setColorAt(1.0, QColor(235, 255, 245, 0))
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), R * 0.34, R * 0.34)
        p.restore()

    def _palomita(self, p, R, r_domo, marca, alfa, acento):
        """La palomita, que se dibuja trazo a trazo (marca 0..1)."""
        tm = 1 - (1 - max(0.0, min(1.0, marca))) ** 3
        if tm <= 0.001:
            return
        cam = QPainterPath()
        a_, b_, d_ = QPointF(-r_domo * 0.42, r_domo * 0.02), QPointF(-r_domo * 0.1, r_domo * 0.34), QPointF(r_domo * 0.5, -r_domo * 0.32)
        cam.moveTo(a_)
        if tm < 0.4:
            cam.lineTo(a_ + (b_ - a_) * (tm / 0.4))
        else:
            cam.lineTo(b_)
            cam.lineTo(b_ + (d_ - b_) * ((tm - 0.4) / 0.6))
        clara = QColor(min(255, acento.red() + 90), min(255, acento.green() + 25), min(255, acento.blue() + 60))
        for grosor, al in ((R * 0.16, 40), (R * 0.1, 90), (R * 0.055, 255)):
            col = clara if grosor < R * 0.06 else acento
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(al * alfa)), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(cam)

    def _resalte(self, p, R, fase, fase_t, t):
        """El paso en curso enciende una pieza distinta del astrolabio. Al cambiar de fase hay un fogonazo que se asienta."""
        capa, col = FASES_ORBE[fase]
        k = 0.55 + 0.45 * max(0.0, 1.0 - fase_t / 0.9) ** 2 + 0.12 * math.sin(t * 4.0)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setBrush(Qt.BrushStyle.NoBrush)

        def aro(rad, ancho, alfa):
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(max(0, min(255, alfa)))), R * ancho))
            p.drawEllipse(QPointF(0, 0), R * rad, R * rad)

        if capa == 'runas':                                  # la corona de runas: un arco brillante la recorre
            aro(0.905, 0.10, 34 * k)
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(210 * k)), R * 0.03, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(-R * 0.905, -R * 0.905, 1.81 * R, 1.81 * R), int(-t * 140 * 16), 70 * 16)
        elif capa == 'engr':                                 # el engranaje: sus dientes se encienden
            aro(0.665, 0.20, 40 * k)
            aro(0.76, 0.03, 120 * k)
        elif capa == 'fili':                                 # la voz: ondas que salen del domo hacia la filigrana
            aro(0.49, 0.12, 46 * k)
            for i in range(3):
                f = ((t * 0.9) + i / 3.0) % 1.0
                aro(0.43 + 0.40 * f, 0.016, 190 * (1.0 - f) ** 1.5 * k)
        elif capa == 'gema':                                 # la IA: destellos de cuatro puntas alrededor de la gema
            aro(0.34, 0.14, 40 * k)
            for i in range(7):
                a = i * math.tau / 7 + t * 0.6
                rr = R * (0.53 + 0.05 * math.sin(t * 2.2 + i))  # v5.22: por FUERA del domo (antes pasaban por encima del % y del tiempo)
                x, y = rr * math.cos(a), rr * math.sin(a)
                s_ = R * (0.02 + 0.03 * (0.5 + 0.5 * math.sin(t * 5.0 + i * 2.1))) * (0.5 + k)
                p.setPen(QPen(QColor(255, 235, 255, int(235 * min(1.0, k))), max(1.0, R * 0.008), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(x - s_, y), QPointF(x + s_, y))
                p.drawLine(QPointF(x, y - s_), QPointF(x, y + s_))
        elif capa == 'botones':                              # el sonido: los cuatro botones laten en cadena
            for i in range(4):
                a = math.radians(-45 + i * 90)
                x, y = 0.69 * R * math.cos(a), 0.69 * R * math.sin(a)
                f = 0.5 + 0.5 * math.sin(t * 6.0 - i * 1.4)
                g = QRadialGradient(QPointF(x, y), R * 0.17)
                g.setColorAt(0.0, QColor(col.red(), col.green(), col.blue(), int(230 * f * min(1.0, k + 0.2))))
                g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(g))
                p.drawEllipse(QPointF(x, y), R * 0.17, R * 0.17)
        else:                                                # 'domo': el marco de cristal se enciende al colocar en Resolve
            aro(0.43, 0.05, 150 * k)
            g = QRadialGradient(QPointF(0, 0), R * 0.43)
            g.setColorAt(0.5, QColor(col.red(), col.green(), col.blue(), 0))
            g.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), int(110 * k)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(0, 0), R * 0.43, R * 0.43)
        p.restore()

    def _gema(self, p, R, t, hover, respira, alfa):
        """La gema «play» facetada con sus rayos. alfa 0 = no se dibuja."""
        if alfa <= 0.01:
            return
        esc = 1.0 + 0.035 * respira
        p.save()
        p.setOpacity(alfa)
        # rayos que giran y laten (detras de la gema)
        n = 16
        for i in range(n):
            a = math.radians(self.rot['rayos'] + i * 360 / n)
            largo = R * (0.34 + 0.07 * math.sin(t * 2.0 + i * 1.3))
            ancho = math.radians(2.6 if i % 2 else 1.6)
            tri = QPainterPath()
            tri.moveTo(QPointF(R * 0.10 * math.cos(a), R * 0.10 * math.sin(a)))
            tri.lineTo(QPointF(largo * math.cos(a - ancho), largo * math.sin(a - ancho)))
            tri.lineTo(QPointF(largo * math.cos(a + ancho), largo * math.sin(a + ancho)))
            tri.closeSubpath()
            lg = QLinearGradient(QPointF(0, 0), QPointF(largo * math.cos(a), largo * math.sin(a)))
            lg.setColorAt(0, QColor(220, 255, 180, 190))
            lg.setColorAt(1, QColor(ESM.red(), ESM.green(), ESM.blue(), 0))
            p.fillPath(tri, QBrush(lg))
        halo = QRadialGradient(QPointF(0, 0), R * 0.33)
        halo.setColorAt(0, QColor(190, 255, 190, 170))
        halo.setColorAt(0.5, QColor(ESM.red(), ESM.green(), ESM.blue(), 70))
        halo.setColorAt(1, QColor(ESM.red(), ESM.green(), ESM.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(0, 0), R * 0.33, R * 0.33)
        # la gema: triangulo con 3 facetas
        s = R * 0.30 * esc
        A, B, C, P = QPointF(-0.44 * s, -0.62 * s), QPointF(-0.44 * s, 0.62 * s), QPointF(0.78 * s, 0.0), QPointF(-0.04 * s, 0.0)
        caras = ((A, B, P, ('#2fd488', '#0b6b44')), (B, C, P, ('#5cf0a8', '#0f8a58')), (C, A, P, ('#aaf7cf', '#15a56a')))
        for (u, v, w, (c1, c2)) in caras:
            path = QPainterPath()
            path.moveTo(u); path.lineTo(v); path.lineTo(w); path.closeSubpath()
            g = QLinearGradient(u, w)
            g.setColorAt(0, QColor(c1)); g.setColorAt(1, QColor(c2))
            p.fillPath(path, QBrush(g))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(235, 255, 240, 220), max(1.4, R * 0.006), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for (u, v, w, _) in caras:
            p.drawLine(u, v); p.drawLine(v, w); p.drawLine(w, u)
        # chispa que cruza la gema
        f = (t % 3.4) / 3.4
        if f < 0.3:
            x = -0.5 * s + (f / 0.3) * 1.3 * s
            brillo = math.sin(f / 0.3 * math.pi)
            sp = QRadialGradient(QPointF(x, -0.1 * s), s * 0.28)
            sp.setColorAt(0, QColor(255, 255, 255, int(240 * brillo)))
            sp.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(sp))
            p.drawEllipse(QPointF(x, -0.1 * s), s * 0.28, s * 0.28)
        p.restore()
