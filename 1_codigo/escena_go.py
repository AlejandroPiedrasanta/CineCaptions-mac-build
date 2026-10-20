# CineCaptions · By Cinema Productions
# 1_codigo/escena_go.py — la escena de Inicio: esfera de partículas 3D, absorción, cometas de pasos y explosión final.
"""
escena_go.py  (v5.2.1)
----------------------
El fondo vivo de la pantalla de Inicio, a pantalla completa y DEBAJO del botón GO:

  REPOSO     Una esfera de ~7000 partículas que gira en 3D con ondas orgánicas (como la imagen de referencia
             2_recursos/fondo_esfera.jpg), polvo estelar que flota y anillos de luz que se expanden muy suaves.
  GO         La esfera gana gravedad y gira rápido. Objetos en 3D vienen desde fuera de la pantalla en espiral y la
             esfera los absorbe: textos neón, cámaras de cine, lentes, estrellas, notas, iconos de volumen y emojis.
  PASOS      Cada paso del proceso cae desde arriba como un cometa encendido y se estrella abajo: onda expansiva, chispas
             y la etiqueta del paso queda con un resplandor.
  SONIDO     En el paso de efectos de sonido la esfera absorbe notas musicales y barras de frecuencia y se hipercarga:
             núcleo blanco, anillos de lente gravitacional y rayos.
  EXPLOSIÓN  Al 100 % estalla (destello + onda de choque + las partículas salen despedidas) y justo ahí empieza la colocación
             directa en la línea de tiempo de DaVinci Resolve (el panel recibe el aviso en `luego`).

Cómo se dibuja (sin web ni OpenGL, para que el instalador siga pesando lo mismo y funcione en cualquier equipo):
las partículas se proyectan con numpy, se acumulan en un búfer de luz a menor resolución, se les saca un resplandor (bloom)
con desenfoques de caja, se colorean con una tabla de color (azul → cian → blanco al cargarse) y se suman sobre el fondo con
CompositionMode_Plus. Encima, QPainter dibuja lo vectorial (objetos absorbidos, cometas, ondas de choque, etiquetas).
Mide su propio tiempo por cuadro y baja la calidad sola si el equipo va justo. Con «Reducir animaciones» queda casi quieta.
Los sonidos del impacto y de la explosión son sintéticos (numpy) y muy suaves; se apagan con la preferencia go_sonidos.
"""
import math
import random
import time
from pathlib import Path

import numpy as np

import ritmo_ui
from PySide6.QtCore import QEvent, QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                           QRadialGradient, QTransform)
from PySide6.QtWidgets import QWidget

import qt_kit as ui


def _quieto():
    try:
        import efectos_ui
        return bool(efectos_ui.reducir_animaciones())
    except Exception:
        return False


def _col(hexa, alfa=255):
    c = QColor(hexa)
    c.setAlpha(max(0, min(255, int(alfa))))
    return c


# --------------------------------------------------------------------------------------------- color y bloom
def _tabla_color(hot):
    """LUT 256x3 uint8: negro → azul marino → azul → cian → blanco. hot=1 empuja todo hacia blanco/violeta (carga máxima)."""
    paradas = np.array([0.0, 0.22, 0.45, 0.72, 1.0])
    base = np.array([[0, 0, 0], [4, 26, 96], [12, 110, 255], [96, 214, 255], [255, 255, 255]], dtype=np.float32)
    calor = np.array([[0, 0, 0], [24, 40, 150], [90, 150, 255], [210, 235, 255], [255, 255, 255]], dtype=np.float32)
    x = np.linspace(0, 1, 256)
    a = np.stack([np.interp(x, paradas, base[:, i]) for i in range(3)], axis=1)
    b = np.stack([np.interp(x, paradas, calor[:, i]) for i in range(3)], axis=1)
    return (a * (1.0 - hot) + b * hot).astype(np.uint8)


def _tabla_roja():
    """LUT para el error: la esfera se pone roja."""
    paradas = np.array([0.0, 0.25, 0.55, 0.8, 1.0])
    col = np.array([[0, 0, 0], [70, 8, 14], [230, 40, 60], [255, 130, 130], [255, 235, 235]], dtype=np.float32)
    x = np.linspace(0, 1, 256)
    return np.stack([np.interp(x, paradas, col[:, i]) for i in range(3)], axis=1).astype(np.uint8)


def _caja(a, r, eje):
    """Desenfoque de caja de radio r a lo largo de un eje (con sumas acumuladas: O(n))."""
    if r < 1:
        return a
    k = 2 * r + 1
    if a.shape[eje] <= k + 1:
        return a
    c = np.cumsum(a, axis=eje, dtype=np.float32)
    salida = np.zeros_like(a)
    if eje == 1:
        salida[:, r:-r] = (c[:, k - 1:] - np.concatenate([np.zeros((a.shape[0], 1), np.float32), c[:, :-k]], axis=1)) / k
    else:
        salida[r:-r, :] = (c[k - 1:, :] - np.concatenate([np.zeros((1, a.shape[1]), np.float32), c[:-k, :]], axis=0)) / k
    return salida


# --------------------------------------------------------------------------------------------- sonidos sintéticos
def _sonido(nombre):
    """Sonidos del impacto, la absorción y la explosión, generados con numpy (muy suaves)."""
    sr = 44100
    rng = np.random.default_rng(7)
    if nombre == 'impacto':
        n = int(sr * 0.32)
        t = np.arange(n) / sr
        f = 120.0 * np.exp(-t * 14) + 48.0
        tono = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 11)
        ruido = rng.standard_normal(n) * np.exp(-t * 60) * 0.35
        x = (tono + ruido) * 0.34
    elif nombre == 'whoosh':
        n = int(sr * 0.55)
        t = np.arange(n) / sr
        env = np.sin(np.pi * np.clip(t / 0.55, 0, 1)) ** 2
        r = rng.standard_normal(n)
        r = np.convolve(r, np.ones(40) / 40, mode='same')
        x = r * env * 0.22 * (1 + 2 * t)
    else:                                              # boom
        n = int(sr * 1.5)
        t = np.arange(n) / sr
        f = 70.0 * np.exp(-t * 2.2) + 32.0
        tono = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 2.6)
        r = rng.standard_normal(n)
        r = np.convolve(r, np.ones(24) / 24, mode='same') * np.exp(-t * 4.5) * 0.9
        x = (tono * 0.95 + r * 0.55) * 0.5
    x = np.clip(x, -1, 1).astype(np.float32)
    paso = min(len(x) // 2, 200)
    x[:paso] *= np.linspace(0, 1, paso, dtype=np.float32)
    x[-paso:] *= np.linspace(1, 0, paso, dtype=np.float32)
    return x


# --------------------------------------------------------------------------------------------- dibujos vectoriales
def _neon(p, color, escala, dibujar, brillo=1.0):
    """Un trazo con resplandor: tres pasadas (ancha tenue → fina brillante)."""
    for ancho, alfa in ((0.30, 26), (0.15, 70), (0.055, 255)):
        p.setPen(QPen(_col(color, alfa * brillo), max(0.9, escala * ancho), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        dibujar()


def _dib_camara(p, color, s, brillo=1.0):
    def forma():
        p.drawRoundedRect(QRectF(-0.85 * s, -0.30 * s, 1.30 * s, 0.85 * s), 0.12 * s, 0.12 * s)
        p.drawPolygon(QPolygonF([QPointF(0.45 * s, -0.12 * s), QPointF(0.98 * s, -0.40 * s), QPointF(0.98 * s, 0.62 * s), QPointF(0.45 * s, 0.38 * s)]))
        p.drawEllipse(QPointF(-0.50 * s, -0.62 * s), 0.30 * s, 0.30 * s)
        p.drawEllipse(QPointF(0.02 * s, -0.62 * s), 0.30 * s, 0.30 * s)
    _neon(p, color, s, forma, brillo)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col(color, 90 * brillo))
    p.drawEllipse(QPointF(0.72 * s, 0.12 * s), 0.13 * s, 0.13 * s)


def _dib_lente(p, color, s, brillo=1.0):
    def forma():
        p.drawEllipse(QPointF(0, 0), s, s)
        p.drawEllipse(QPointF(0, 0), 0.66 * s, 0.66 * s)
        p.drawEllipse(QPointF(0, 0), 0.30 * s, 0.30 * s)
        p.drawArc(QRectF(-0.82 * s, -0.82 * s, 1.64 * s, 1.64 * s), 40 * 16, 70 * 16)
    _neon(p, color, s, forma, brillo)


def _dib_estrella(p, color, s, brillo=1.0):
    pts = [(0, -1), (0.2, -0.2), (1, 0), (0.2, 0.2), (0, 1), (-0.2, 0.2), (-1, 0), (-0.2, -0.2)]
    poli = QPolygonF([QPointF(x * s, y * s) for x, y in pts])
    g = QRadialGradient(QPointF(0, 0), s * 1.7)
    g.setColorAt(0.0, _col(color, 110 * brillo))
    g.setColorAt(1.0, _col(color, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(0, 0), s * 1.7, s * 1.7)
    p.setBrush(_col('#FFFFFF', 255 * brillo))
    p.drawPolygon(poli)


def _dib_volumen(p, color, s, brillo=1.0):
    def forma():
        p.drawPolygon(QPolygonF([QPointF(-0.9 * s, -0.28 * s), QPointF(-0.45 * s, -0.28 * s), QPointF(0.05 * s, -0.7 * s),
                                 QPointF(0.05 * s, 0.7 * s), QPointF(-0.45 * s, 0.28 * s), QPointF(-0.9 * s, 0.28 * s)]))
        for k in range(2):
            r = (0.4 + 0.34 * k) * s
            p.drawArc(QRectF(0.1 * s - r * 0.35, -r, r * 1.4, 2 * r), -50 * 16, 100 * 16)
    _neon(p, color, s, forma, brillo)


def _dib_nota(p, color, s, brillo=1.0, doble=False):
    def forma():
        p.drawEllipse(QPointF(-0.32 * s, 0.62 * s), 0.34 * s, 0.25 * s)
        p.drawLine(QPointF(0.0, 0.58 * s), QPointF(0.0, -0.85 * s))
        ruta = QPainterPath(QPointF(0.0, -0.85 * s))
        ruta.cubicTo(QPointF(0.2 * s, -0.7 * s), QPointF(0.55 * s, -0.55 * s), QPointF(0.5 * s, -0.1 * s))
        p.drawPath(ruta)
        if doble:
            p.drawEllipse(QPointF(0.62 * s, 0.38 * s), 0.34 * s, 0.25 * s)
    _neon(p, color, s, forma, brillo)


def _dib_onda(p, color, s, brillo=1.0, t=0.0):
    def forma():
        for i, h in enumerate((0.35, 0.8, 0.55, 1.0, 0.45, 0.7, 0.3)):
            hh = h * (0.7 + 0.3 * math.sin(t * 9 + i * 1.3))
            x = (-0.9 + i * 0.3) * s
            p.drawLine(QPointF(x, -hh * s), QPointF(x, hh * s))
    _neon(p, color, s, forma, brillo)


def _dib_texto(p, color, s, texto, brillo=1.0):
    f = QFont(ui.fuente(10, peso='extra'))
    f.setPixelSize(max(8, int(s * 0.9)))
    ruta = QPainterPath()
    ruta.addText(0, 0, f, texto)
    caja = ruta.boundingRect()
    ruta.translate(-caja.center().x(), -caja.center().y())
    for ancho, alfa in ((0.5, 24), (0.26, 70)):
        p.setPen(QPen(_col(color, alfa * brillo), max(1.2, s * ancho * 0.22), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(ruta)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col('#FFFFFF', 255 * brillo))
    p.drawPath(ruta)
    p.setPen(QPen(_col(color, 255 * brillo), 1.1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(ruta)


def _dib_emoji(p, color, s, texto, brillo=1.0):
    f = QFont('Segoe UI Emoji')
    f.setPixelSize(max(10, int(s * 1.5)))
    p.setFont(f)
    p.setPen(_col('#FFFFFF', 255 * brillo))
    p.drawText(QRectF(-s * 1.2, -s * 1.2, s * 2.4, s * 2.4), int(Qt.AlignmentFlag.AlignCenter), texto)


_SPRITES = {}


def _sprite(tipo, color, texto, dpr):
    """El dibujo de un objeto UNA sola vez (con resplandor), listo para girarlo en 3D cuadro a cuadro: (pixmap, ancho, alto)."""
    clave = (tipo, color, texto, round(dpr, 1))
    hecho = _SPRITES.get(clave)
    if hecho is not None:
        return hecho
    S = 34.0
    if tipo == 'texto':
        f = QFont(ui.fuente(10, peso='extra'))
        f.setPixelSize(max(8, int(S * 0.9)))
        w, h = int(QFontMetricsF(f).horizontalAdvance(texto) + 2.2 * S), int(3.0 * S)
    else:
        w = h = int(3.6 * S)
    pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    q = QPainter(pm)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    q.translate(w / 2.0, h / 2.0)
    if tipo == 'camara':
        _dib_camara(q, color, S)
    elif tipo == 'lente':
        _dib_lente(q, color, S)
    elif tipo == 'estrella':
        _dib_estrella(q, color, S)
    elif tipo == 'volumen':
        _dib_volumen(q, color, S)
    elif tipo == 'nota':
        _dib_nota(q, color, S)
    elif tipo == 'nota2':
        _dib_nota(q, color, S, doble=True)
    elif tipo == 'onda':
        _dib_onda(q, color, S, t=0.8)
    elif tipo == 'emoji':
        _dib_emoji(q, color, S, texto)
    else:
        _dib_texto(q, color, S, texto or 'GO')
    q.end()
    if len(_SPRITES) > 400:
        _SPRITES.clear()
    _SPRITES[clave] = (pm, w, h)
    return _SPRITES[clave]


EMOJIS_FIN = ('🎵', '🎶', '🎧', '✨', '🎉', '🔥', '🎬')
PALABRAS = ('SUBTÍTULOS', 'VIRAL', 'IA', 'GO', '3 LÍNEAS', 'AUDIO', 'CORTES', 'TIMELINE', 'SFX', 'RITMO', 'EMOJI')
EMOJIS = ('🎬', '🔥', '✨', '😮', '🎧', '💥', '🚀', '⭐')
COLORES = ('#4FD8FF', '#4589FF', '#B388FF', '#FF7BD5', '#7DFFB2', '#FFD166')
FASES = {
    'timeline': ('camara', 'lente', 'estrella', 'texto'),
    'voz': ('texto', 'onda', 'volumen', 'estrella', 'texto'),
    'ia': ('estrella', 'emoji', 'texto', 'estrella', 'emoji'),
    'diseno': ('texto', 'estrella', 'camara', 'texto'),
    'sfx': ('nota', 'volumen', 'onda', 'nota2', 'estrella', 'nota'),
    'resolve': ('estrella', 'lente', 'camara'),
}


class _Objeto:
    """Un objeto 3D que cae en espiral hacia la esfera (gravedad: acelera al acercarse)."""
    __slots__ = ('tipo', 't0', 'dur', 'th0', 'r0', 'giro', 'esc', 'color', 'texto', 'rot')

    def __init__(self, tipo, t0, dur, th0, r0, giro, esc, color, texto, rot):
        self.tipo, self.t0, self.dur, self.th0, self.r0, self.giro, self.esc, self.color, self.texto, self.rot = \
            tipo, t0, dur, th0, r0, giro, esc, color, texto, rot

    def u(self, ahora):
        return (ahora - self.t0) / self.dur

    def pos(self, u, c):
        e = max(0.0, min(1.0, u)) ** 2.2
        r = self.r0 * (1.0 - e)
        th = self.th0 + self.giro * e
        return QPointF(c.x() + r * math.cos(th), c.y() + r * 0.82 * math.sin(th)), e


class _Cometa:
    __slots__ = ('i', 't0', 'dur', 'x0', 'x1', 'y1', 'color')

    def __init__(self, i, t0, dur, x0, x1, y1, color):
        self.i, self.t0, self.dur, self.x0, self.x1, self.y1, self.color = i, t0, dur, x0, x1, y1, color


class _Impacto:
    __slots__ = ('x', 'y', 't0', 'color', 'chispas')

    def __init__(self, x, y, t0, color):
        self.x, self.y, self.t0, self.color = x, y, t0, color
        self.chispas = [(random.uniform(-1.0, 1.0) * 260.0, -random.uniform(120.0, 360.0), random.uniform(0.5, 1.0)) for _ in range(26)]


class EscenaGo(QWidget):
    """La escena. El panel de Inicio le dice qué pasa (empezar / paso / progreso / explotar / terminar) y le presta la
    geometría (centro y radio de la esfera, rectángulo de las etiquetas) con `proveedor`."""
    etiquetas_ocultas = Signal()
    ALTO_FILA = 34
    FILAS_MAX = 7

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.proveedor = None                   # () -> (centro QPointF en coords de la escena, radio px, QRectF de las etiquetas)
        self._rng = np.random.default_rng(3)
        self.calidad = 1.0
        self._quieto = _quieto()
        self._n = 7000
        self._armar_esfera()
        self._armar_polvo(260)
        self._t = 0.0                           # reloj de la escena (s)
        self._ult = time.perf_counter()
        self._estado = 'reposo'                 # reposo | trabajando | explotando | hecho | error
        self.energia = 0.0
        self.meta = 0.0
        self.gravedad = 0.0
        self.expl = 0.0                         # 0..1 de la explosión
        self.t_expl = None
        self.reaparecer = 1.0
        self.destello = 0.0
        self._luego = None
        self._objetos = []
        self.al_tic = []                        # funciones que avanzan con el reloj de la escena (el botón GO)
        self.al_pulso = None                    # () -> None: un destello en el orbe (llega una chispa de un paso terminado)
        self.datos_barra = None                 # v5.22: () -> dict | None (PanelGo._datos_barra): la barra de progreso de abajo
        self._barra_d = None
        self._barra_a = 0.0
        self.modo = 'completo'                  # 'completo' | 'suave' | 'minimo' (Ajustes > Interfaz)
        self.par = (0.0, 0.0)                   # el ratón respecto al orbe (-1..1): inclina los haces de luz
        self._fase_t0 = -9.0
        self._chispas_paso = []                 # chispas que viajan de un paso terminado al orbe
        self._t_final = None                    # el destello del final (tras la carga)
        self._tono_final = 'ok'
        self._carga_final = False
        self._t_politica = 0.0
        self._t_prefs = -9.0
        self._inactiva = False
        self._ms_reloj = 16
        self._fondo_pm = None                   # el fondo a 1/3 de resolución (ver _fondo_bajo)
        self._salida = []                       # el final festivo (notas, ondas, emojis)
        self._nb = 360                          # rafagas de luz (clic y final): chispas rapidas y brasas que suben
        self._b = None
        self._bi = 0
        self._cur = QPointF(-999, -999)         # el cursor (en coordenadas de la escena), suavizado: repele las particulas
        self._cur_k = 0.0
        import estilos_inicio
        self.estilo_clave = ''
        self.estilo = None
        self.poner_estilo(estilos_inicio.clave_guardada())
        self._cometas = []
        self._impactos = []
        self._ondas = []                        # ondas de choque: (t0, centro, color, grueso)
        self._anillos = []                      # anillos suaves del fondo
        self._rayos = []
        self._pasos = []
        self._t_spawn = 0.0
        self._fase = ''
        self._t_ocultar = None
        self._sacudida = 0.0
        self._fin_pendiente = None
        self._post = False                      # después de la explosión: sigue colocando en Resolve
        self._cache_fondo = None
        self._img_ref = None
        self._buf = None
        self._luts = (_tabla_color(0.0), _tabla_color(1.0))
        self._lut_e = -1.0
        self._lut = self._luts[0]
        self._ms_cuadro = 12.0
        self._dt_med = 0.016               # v5.5.8: el intervalo REAL entre cuadros (si no llega a 60 fps, 30 parejos: se ven mejor que 40 a saltos)
        self._lento_hasta = 0.0
        self._lento_n = 0
        self._gracia_hasta = 0.0           # v5.22: tras volver a verse, los tirones de la transición no cuentan como «equipo lento»
        self._esc_cuadro = 1.0                  # escala de resolución interna de la escena (adaptativa, 0,62..1)
        self._cuadros = 0
        self._cuadro = None                     # el ultimo cuadro dibujado (QPixmap) y cuando: ver paintEvent
        self._cuadro_clave = None
        self._cuadro_t = 0.0
        self._sonidos = {}
        self._rep = None
        self.sonido = True
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)
        self._cargar_referencia()

    # ------------------------------------------------------------------ preparación
    def _armar_esfera(self):
        n = int(self._n)
        i = np.arange(n, dtype=np.float32) + 0.5
        phi = np.arccos(1.0 - 2.0 * i / n)
        th = np.pi * (1.0 + 5.0 ** 0.5) * i
        self._th = (th % (2 * np.pi)).astype(np.float32)
        self._phi = phi.astype(np.float32)
        self._bx = (np.cos(th) * np.sin(phi)).astype(np.float32)
        self._by = (np.sin(th) * np.sin(phi)).astype(np.float32)
        self._bz = np.cos(phi).astype(np.float32)
        self._azar = self._rng.random(n).astype(np.float32)

    def _armar_polvo(self, n):
        self._px = (self._rng.random(n) * 1.0).astype(np.float32)        # 0..1 de la pantalla
        self._py = (self._rng.random(n) * 1.0).astype(np.float32)
        self._pvx = ((self._rng.random(n) - 0.5) * 0.01).astype(np.float32)
        self._pvy = ((self._rng.random(n) - 0.5) * 0.01).astype(np.float32)
        self._pb = (0.25 + self._rng.random(n) * 0.75).astype(np.float32)

    def _cargar_referencia(self):
        """La imagen de referencia, muy desenfocada, como luz ambiente detrás de la esfera."""
        try:
            import sys
            base = Path(getattr(sys, '_MEIPASS', '')) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent / '2_recursos'
            ruta = base / 'fondo_esfera.jpg'
            if not ruta.is_file():
                ruta = Path(__file__).resolve().parent.parent / '2_recursos' / 'fondo_esfera.jpg'
            if ruta.is_file():
                img = QImage(str(ruta))
                if not img.isNull():
                    chico = img.scaled(max(8, img.width() // 14), max(8, img.height() // 14), Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                    ref = chico.scaled(img.width() // 2, img.height() // 2, Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                    placa = QImage(ref.width(), ref.height(), QImage.Format.Format_ARGB32_Premultiplied)
                    placa.fill(0)
                    q = QPainter(placa)
                    q.drawImage(0, 0, ref)
                    q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)    # bordes que se funden con el fondo
                    q.translate(ref.width() * 0.5, ref.height() * 0.42)
                    q.scale(1.0, ref.height() / float(ref.width()))             # máscara elíptica: ningún borde llega a verse
                    m = QRadialGradient(QPointF(0, 0), ref.width() * 0.5)
                    m.setColorAt(0.0, QColor(0, 0, 0, 255))
                    m.setColorAt(0.35, QColor(0, 0, 0, 150))
                    m.setColorAt(0.7, QColor(0, 0, 0, 26))
                    m.setColorAt(1.0, QColor(0, 0, 0, 0))
                    q.fillRect(QRectF(-ref.width(), -ref.width(), ref.width() * 2.0, ref.width() * 2.0), m)
                    q.end()
                    self._img_ref = placa
        except Exception:
            self._img_ref = None

    # ------------------------------------------------------------------ API para el panel
    def activar(self, si):
        if si:
            if not self._reloj.isActive():
                self._ult = time.perf_counter()
                self._reanudar()
                self._reloj.setTimerType(Qt.TimerType.PreciseTimer)       # 60 fps parejos: el temporizador normal de Windows da saltos
                self._ms_reloj = 16 if not self._quieto else 160
                self._reloj.start(self._ms_reloj)
        else:
            self._reloj.stop()

    def _reanudar(self):
        """v5.22 (el usuario: «al volver a Inicio las animaciones van trabadas»): al volver de otra página o a la ventana, el primer
        segundo trae cuadros lentos (la transición, Qt rehaciendo cachés). Antes contaban como «equipo lento» y la escena se quedaba a
        30 fps 8 s, y más cada vez (16, 32… hasta 2 min). Ahora ese segundo no cuenta y la medida empieza limpia."""
        self._gracia_hasta = time.perf_counter() + 1.2
        self._dt_med = min(self._dt_med, 0.016)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.ActivationChange and self._reloj.isActive() and self.isVisible():
            # vuelve a la ventana (o la deja): el ritmo cambia YA (60 ↔ 30 fps), sin esperar a la política de cada segundo
            if self.window().isActiveWindow():
                self._ult = time.perf_counter()
                self._reanudar()
            self._politica()

    def poner_pasos(self, pasos):
        """[(clave, texto)] en el orden en que van a ir cayendo."""
        self._pasos = [{'clave': c, 'texto': t, 'estado': 'pendiente', 'detalle': '', 'aterrizo': None, 'brillo': 0.0, 'pend': None}
                       for c, t in pasos]

    def reposo(self):
        if self._estado in ('trabajando', 'explotando'):
            return
        self._post = False
        self._estado = 'reposo'
        self.meta = 0.0
        self.gravedad = 0.0

    def empezar(self):
        self._estado = 'trabajando'
        self._post = False
        self.meta = 0.08
        self.gravedad = 1.0
        self.expl = 0.0
        self.t_expl = None
        self.reaparecer = 1.0
        self._objetos.clear()
        self._cometas.clear()
        self._impactos.clear()
        self._t_ocultar = None
        for p in self._pasos:
            p.update(estado='pendiente', detalle='', aterrizo=None, brillo=0.0, pend=None)
        self._fase = 'timeline'
        self._salida.clear()
        if getattr(self, '_pviva', None) is not None:
            self._pviva[:] = False
        c = self._geometria()[0]
        # el choque: tres ondas escalonadas + resplandor + rafaga de chispas; despues empieza la absorcion
        self._ondas.append((self._t, QPointF(c), '#FFFFFF', 0.95, False))
        self._ondas.append((self._t + 0.10, QPointF(c), '#4FFFB0', 0.75, False))
        self._ondas.append((self._t + 0.22, QPointF(c), '#4FD8FF', 0.55, False))
        self.destello = 0.30
        self._sacudida = 0.30
        self._t_spawn = 0.55
        todos = tuple(range(len(self.estilo.pal)))
        self._lanzar_burst(c, 70, (380, 880), (0.7, 1.2), todos, 0.0, 0)
        self._lanzar_burst(c, 50, (60, 240), (1.2, 2.0), todos, -70.0, 1)

    def progreso(self, f):
        """0..1 del proceso: la esfera se carga con él."""
        if self._estado == 'trabajando':
            self.meta = max(self.meta, 0.08 + 0.80 * max(0.0, min(1.0, float(f))))

    def ocultar_etiquetas(self):
        """Las etiquetas de los pasos se retiran ya (en vez de esperar unos segundos)."""
        if self._t_ocultar is not None:
            self._t_ocultar = self._t

    def poner_fase(self, clave):
        if clave != self._fase:
            self._fase = clave
            self._fase_t0 = self._t

    def paso(self, clave, estado='activo', detalle=None):
        i = next((k for k, p in enumerate(self._pasos) if p['clave'] == clave), None)
        if i is None:
            return
        p = self._pasos[i]
        if detalle is not None:
            p['detalle'] = detalle
        if estado == 'activo':
            self._fase = clave
            if clave == 'sfx':
                self.meta = max(self.meta, 0.94)
                self._sonar('whoosh')
            if p['aterrizo'] is None and p['estado'] != 'cayendo':
                p['estado'] = 'cayendo'
                self._lanzar_cometa(i)
        elif estado in ('hecho', 'saltado', 'error'):
            if p['aterrizo'] is None:
                p['pend'] = estado                    # llega con el cometa
                if p['estado'] == 'pendiente':
                    p['estado'] = 'cayendo'
                    self._lanzar_cometa(i)
            else:
                p['estado'] = estado
                p['brillo'] = 1.0
                if estado == 'hecho':
                    self._onda_choque(0.25, '#24D18F', rect_fila=i)
                    self._chispa_paso(i)

    def explotar(self, luego=None):
        """100 %: estalla la esfera. `luego()` se llama en el pico de la explosión (ahí empieza la colocación en Resolve)."""
        self._estado = 'explotando'
        self.t_expl = self._t
        self.meta = 1.0
        self._luego = luego
        self._sonar('boom')

    def terminar(self, ok, tono='ok'):
        self._tono_final = tono
        if self._estado == 'explotando' and self.t_expl is not None and self._t - self.t_expl < 1.6:
            self._fin_pendiente = ok                 # se aplica al acabar la explosión
            return
        self._cerrar(ok)

    def _cerrar(self, ok):
        self._post = False
        self._estado = 'hecho' if ok else 'error'
        self.meta = 0.22 if ok else 0.35
        self.gravedad = 0.0
        self._fin_pendiente = None
        self._t_ocultar = self._t + (7.0 if ok else 12.0)
        self._objetos.clear()
        if ok and not self._quieto:
            # 1.er tiempo: el orbe se carga (las partículas se aceleran hacia él); 2.º: el destello y el festejo
            self._carga_final = True
            self._t_final = self._t + 0.7
        if not ok:
            self._sacudida = 0.6
            self._ondas.append((self._t, QPointF(self._geometria()[0]), '#FF6B6B', 0.7, False))
            self.meta = 0.12
        for p in self._pasos:
            if p['estado'] in ('cayendo', 'activo'):
                p['estado'] = 'error' if not ok else 'hecho'

    def _final_festivo(self):
        """Al terminar bien: ondas de luz y una corona de chispas y brasas que suben y se apagan (ámbar si terminó con avisos)."""
        c = self._geometria()[0]
        aviso = self._tono_final == 'aviso'
        cols = ('#FFC857', '#FFD98A', '#FFB35C') if aviso else ('#7DFFB2', '#4FD8FF', '#B388FF')
        self._ondas.append((self._t, QPointF(c), '#FFFFFF', 0.9, False))
        for k in range(3):
            self._ondas.append((self._t + 0.05 + k * 0.28, QPointF(c), cols[k], 0.55, False))
        self.destello = max(self.destello, 0.30)
        n_pal = len(self.estilo.pal)
        paleta = (n_pal, n_pal + 1, n_pal + 2) if aviso else tuple(range(n_pal))
        self._lanzar_burst(c, 80, (300, 680), (0.8, 1.3), paleta, 0.0, 0)
        self._lanzar_burst(c, 110, (60, 300), (1.8, 3.0), paleta, -110.0, 1)

    # ------------------------------------------------------------------ rafagas de luz (numpy)
    def _lanzar_burst(self, c, n, vel, vida, cols, grav, tipo):
        """n partículas desde c: tipo 0 = chispas rápidas con estela, tipo 1 = brasas que frenan y suben (grav < 0 = hacia arriba)."""
        if self._b is None:
            m = self._nb
            self._b = dict(t0=np.full(m, -1e9, np.float32), vida=np.ones(m, np.float32), x0=np.zeros(m, np.float32), y0=np.zeros(m, np.float32),
                           ang=np.zeros(m, np.float32), vel=np.zeros(m, np.float32), col=np.zeros(m, np.int8), grav=np.zeros(m, np.float32),
                           tipo=np.zeros(m, np.int8))
        b, rng, m = self._b, self._rng, self._nb
        idx = (self._bi + np.arange(n)) % m
        self._bi = int((self._bi + n) % m)
        b['t0'][idx] = self._t
        b['vida'][idx] = rng.uniform(vida[0], vida[1], n)
        b['x0'][idx] = c.x()
        b['y0'][idx] = c.y()
        b['ang'][idx] = rng.uniform(0.0, math.tau, n)
        b['vel'][idx] = rng.uniform(vel[0], vel[1], n)
        b['col'][idx] = rng.choice(cols, n)
        b['grav'][idx] = grav
        b['tipo'][idx] = tipo

    # ------------------------------------------------------------------ efectos
    def _sonar(self, nombre):
        return                              # Inicio no suena (pedido del usuario)
        if not self.sonido or self._quieto:
            return
        try:
            import ajustes_ui
            if ajustes_ui.leer_prefs().get('go_sonidos', True) is False:
                return
        except Exception:
            pass
        try:
            import sfx_audio
            if self._rep is None:
                self._rep = sfx_audio.Reproductor()
            if nombre not in self._sonidos:
                self._sonidos[nombre] = _sonido(nombre)
            self._rep.reproducir(self._sonidos[nombre])
        except Exception:
            pass

    def _geometria(self):
        W, H = float(self.width()), float(self.height())
        try:
            if self.proveedor is not None:
                c, r, rect = self.proveedor()
                return QPointF(c), float(r), QRectF(rect)
        except Exception:
            pass
        return QPointF(W / 2, H * 0.38), min(W * 0.28, H * 0.32), QRectF(W / 2 - 230, H - 270, 460, 240)

    def _onda_choque(self, grueso, color, rect_fila=None):
        c, _r, rect = self._geometria()
        if rect_fila is not None:
            c = QPointF(rect.center().x(), rect.top() + self.ALTO_FILA * rect_fila + self.ALTO_FILA / 2)
        self._ondas.append((self._t, QPointF(c), color, grueso, rect_fila is not None))

    def _chispa_paso(self, i):
        """Un paso terminó: una chispa verde viaja de su etiqueta al orbe y lo hace brillar."""
        if self._quieto:
            return
        c, _r, rect = self._geometria()
        x0, y0 = rect.center().x() - 120, rect.top() + self.ALTO_FILA * i + self.ALTO_FILA / 2
        self._chispas_paso.append((self._t, x0, y0, COLORES[i % len(COLORES)]))

    def _dibujar_chispas_paso(self, p, c):
        vivas = []
        for t0, x0, y0, col in self._chispas_paso:
            u = (self._t - t0) / 0.7
            if u >= 1.0:
                if self.al_pulso is not None:
                    try:
                        self.al_pulso()
                    except Exception:
                        pass
                self.meta = min(1.0, self.meta + 0.01)
                continue
            vivas.append((t0, x0, y0, col))
            for k in range(7):                                  # la estela: la misma curva, un poco antes
                uu = max(0.0, u - k * 0.035)
                e = uu * uu * (3 - 2 * uu)
                x = x0 + (c.x() - x0) * e
                y = y0 + (c.y() - y0) * e - 70.0 * math.sin(e * math.pi)
                a = (1 - k / 7.0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_col('#FFFFFF' if k == 0 else '#7DFFB2', 255 * a))
                rad = (4.2 if k == 0 else 3.0) * a + 0.8
                p.drawEllipse(QPointF(x, y), rad, rad)
        self._chispas_paso = vivas

    def _lanzar_cometa(self, i):
        c, _r, rect = self._geometria()
        x1 = rect.center().x()
        y1 = rect.top() + self.ALTO_FILA * i + self.ALTO_FILA / 2
        color = COLORES[i % len(COLORES)]
        self._cometas.append(_Cometa(i, self._t, 0.95, x1 + random.uniform(-140, 140), x1, y1, color))

    def _soltar_objeto(self):
        c, r, _rect = self._geometria()
        fase = (FASES.get(self._fase) or ('estrella', 'texto', 'camara')) + ('emoji', 'nota', 'nota2', 'estrella', 'volumen')
        tipo = random.choice(fase)
        W, H = float(self.width()), float(self.height())
        r0 = max(W, H) * random.uniform(0.42, 0.62)
        th0 = random.uniform(0, math.tau)
        giro = random.choice((-1, 1)) * random.uniform(2.2, 4.2)
        esc = random.uniform(64, 100) * (max(0.7, min(1.5, r / 230.0)))
        color = random.choice(COLORES)
        texto = ''
        if tipo == 'texto':
            texto = random.choice(PALABRAS)
            esc *= 0.9
        elif tipo == 'emoji':
            texto = random.choice(EMOJIS)
        elif tipo in ('nota', 'nota2', 'volumen', 'onda'):
            color = random.choice(('#FF7BD5', '#B388FF', '#4FD8FF'))
        elif tipo == 'camara':
            color = '#4FD8FF'
        self._objetos.append(_Objeto(tipo, self._t, random.uniform(1.5, 2.2), th0, r0, giro, esc, color, texto, random.uniform(-0.5, 0.5)))

    def _absorbido(self, o):
        self.meta = min(1.0, self.meta + 0.006)
        self.energia = min(1.0, self.energia + 0.004)
        if len(self._anillos) < 5:
            self._anillos.append((self._t, 0.35))

    # ------------------------------------------------------------------ reloj
    def _tic(self):
        ahora = time.perf_counter()
        dt = min(0.08, ahora - self._ult)
        self._ult = ahora
        self._dt_med += (dt - self._dt_med) * 0.08
        if not self.isVisible() or self.window().isMinimized():
            if self._ms_reloj != 250:                    # v5.5.7: minimizada u oculta, el reloj despierta 4 veces por segundo (no 60) solo para ver si vuelve
                self._ms_reloj = 250
                self._reloj.setInterval(250)
            return
        if self._ms_reloj == 250:                        # vuelve a verse: el ritmo bueno (60 / 30 fps) ya, sin esperar a la política
            self._ms_reloj = 0
            self._reanudar()
            dt = min(dt, 1 / 60)                         # (el salto de la pausa no se nota como un brinco)
            self._politica()
        self.avanzar(dt)
        for f in self.al_tic:
            try:
                f()
            except RuntimeError:
                pass
        t0 = time.perf_counter()
        self.update()
        self._medir(t0)

    def _medir(self, t0):
        pass

    def _politica(self):
        """Cada ~1 s: el modo elegido en Ajustes (completo / suave / mínimo), la ventana inactiva y la calidad adaptativa deciden la
        frecuencia del reloj (60 o 30 fps) y cuántas partículas hay."""
        import time as _tm
        ahora = _tm.perf_counter()
        if ahora - self._t_prefs > 2.0:
            self._t_prefs = ahora
            try:
                import ajustes_ui
                modo = str(ajustes_ui.leer_prefs().get('go_animaciones') or 'completo')
            except Exception:
                modo = 'completo'
            self.modo = modo if modo in ('completo', 'suave', 'minimo') else 'completo'
            import estilos_inicio
            clave = estilos_inicio.clave_guardada()
            if clave != self.estilo_clave:
                self.poner_estilo(clave)
            try:
                import efectos_ui
                self._quieto = bool(efectos_ui.reducir_animaciones()) or self.modo == 'minimo'
            except Exception:
                pass
        try:
            self._inactiva = not self.window().isActiveWindow()
        except Exception:
            self._inactiva = False
        if self._ms_reloj == 16 and self._dt_med > 0.0205 and ahora >= self._lento_hasta and ahora >= self._gracia_hasta:
            # no llega a 60 fps (pantalla con escala alta, GO trabajando, equipo justo): 30 parejos un rato (8 s, 16 s… hasta 2 min) y vuelve a probar
            self._lento_n = min(self._lento_n + 1, 5)
            self._lento_hasta = ahora + 8.0 * 2 ** (self._lento_n - 1)
        elif self._ms_reloj == 16 and self._dt_med < 0.0185 and ahora > self._lento_hasta + 6.0:
            self._lento_n = 0
        lento = ahora < self._lento_hasta
        ms = 160 if self._quieto else (33 if (self.modo == 'suave' or self._inactiva or self.calidad < 0.5 or lento) else 16)
        if ms != self._ms_reloj:
            self._dt_med = ms / 1000.0
        if ms != self._ms_reloj and self._reloj.isActive():
            self._ms_reloj = ms
            self._reloj.setInterval(ms)

    def avanzar(self, dt):
        """Avanza el estado de la escena dt segundos (la prueba lo llama a mano, sin reloj)."""
        self._t_politica += dt
        if self._t_politica > 1.0:
            self._t_politica = 0.0
            self._politica()
        self._avanzar_barra(dt)
        if self._quieto and self._estado != 'explotando':
            dt *= 0.15                                   # «Reducir animaciones»: todo casi quieto
        self._t += dt
        # energía hacia su meta
        self.energia += (self.meta - self.energia) * min(1.0, dt * (1.6 if self._estado != 'explotando' else 6.0))
        # explosión
        if self._estado == 'explotando' and self.t_expl is not None:
            u = (self._t - self.t_expl) / 1.7
            self.expl = max(0.0, min(1.0, u))
            if self._luego is not None and self._t - self.t_expl >= 0.28:
                f, self._luego = self._luego, None
                try:
                    f()
                except Exception:
                    pass
            if self._t - self.t_expl < 0.05 and not self._ondas_expl_hechas():
                self._ondas.append((self._t, self._geometria()[0], '#FFFFFF', 1.0, False))
                self._ondas.append((self._t + 0.12, self._geometria()[0], '#4FD8FF', 0.8, False))
                self._ondas.append((self._t + 0.26, self._geometria()[0], '#4589FF', 0.6, False))
                self.destello = 1.0
                self._sacudida = 0.7
            if u >= 1.0:
                fin = getattr(self, '_fin_pendiente', None)
                self.reaparecer = 0.0
                self.expl = 0.0
                self.t_expl = None
                self.energia = 0.2
                if fin is None:
                    # la colocación en Resolve sigue en marcha: la esfera renace tranquila y los pasos siguen a la vista
                    self._estado = 'trabajando'
                    self._post = True
                    self.meta = 0.3
                else:
                    self._cerrar(bool(fin))
        if (self._estado in ('hecho', 'reposo') or self._post) and self.reaparecer < 1.0:
            self.reaparecer = min(1.0, self.reaparecer + dt / 1.8)
        self.destello = max(0.0, self.destello - dt * 2.8)
        self._sacudida = max(0.0, self._sacudida - dt)
        # gravedad: sube sola mientras trabaja
        meta_g = 1.0 if (self._estado == 'trabajando' and not self._post) else 0.0
        self.gravedad += (meta_g - self.gravedad) * min(1.0, dt * 2.0)
        # el cursor: foco de luz sobre el fondo y repele las partículas cercanas
        if self.modo == 'completo' and not self._quieto and self.isVisible():
            from PySide6.QtGui import QCursor
            pt = self.mapFromGlobal(QCursor.pos())
            dentro = 0 <= pt.x() <= self.width() and 0 <= pt.y() <= self.height() and not self._inactiva
            self._cur_k += ((1.0 if dentro else 0.0) - self._cur_k) * min(1.0, dt * 6.0)
            if dentro:
                if self._cur.x() < -900:
                    self._cur = QPointF(pt)
                self._cur = QPointF(self._cur.x() + (pt.x() - self._cur.x()) * min(1.0, dt * 14.0), self._cur.y() + (pt.y() - self._cur.y()) * min(1.0, dt * 14.0))
        else:
            self._cur_k = max(0.0, self._cur_k - dt * 4.0)
        # particulas: caen en espiral hacia el orbe mientras trabaja; en reposo, motas de luz lentas
        c, r, _rect = self._geometria()
        if not self._quieto:
            self._avanzar_particulas(dt, self._estado == 'trabajando' or self._carga_final,
                                     self._estado in ('reposo', 'hecho') and not self._carga_final and self.modo == 'completo')
        vivos = []
        for o in self._objetos:
            if o.u(self._t) >= 1.0:
                self._absorbido(o)
            else:
                vivos.append(o)
        self._objetos = vivos
        # cometas → impactos
        vivos = []
        for k in self._cometas:
            if (self._t - k.t0) >= k.dur:
                p = self._pasos[k.i]
                p['aterrizo'] = self._t
                p['brillo'] = 1.0
                p['estado'] = p['pend'] or 'activo'
                if p['pend'] == 'hecho':
                    self._chispa_paso(k.i)
                p['pend'] = None
                self._impactos.append(_Impacto(k.x1, k.y1, self._t, k.color))
                self._ondas.append((self._t, QPointF(k.x1, k.y1), k.color, 0.45, True))
                self._sonar('impacto')
                self._sacudida = max(self._sacudida, 0.16)
            else:
                vivos.append(k)
        self._cometas = vivos
        self._impactos = [im for im in self._impactos if self._t - im.t0 < 1.1]
        if self._t_final is not None and self._t >= self._t_final:
            self._t_final = None
            self._carga_final = False
            self._final_festivo()
        self._ondas = [o for o in self._ondas if self._t - o[0] < 1.7]
        self._anillos = [a for a in self._anillos if self._t - a[0] < 1.6]
        for p in self._pasos:
            p['brillo'] = max(0.0, p['brillo'] - dt * 0.8)
        # anillos suaves del fondo (ondas de luz sutiles)
        if self._estado in ('reposo', 'hecho') and int(self._t * 10) % 46 == 0 and (not self._anillos or self._t - self._anillos[-1][0] > 3.0):
            self._anillos.append((self._t, 0.12))
        # rayos al estar hipercargada
        if self.energia > 0.8 and self._estado == 'trabajando' and random.random() < dt * 5.0:
            self._rayos.append((self._t, random.uniform(0, math.tau)))
        self._rayos = [x for x in self._rayos if self._t - x[0] < 0.22]
        # ocultar etiquetas pasado un rato
        if self._t_ocultar is not None and self._t >= self._t_ocultar:
            self._t_ocultar = None
            for p in self._pasos:
                p.update(estado='pendiente', aterrizo=None, brillo=0.0, detalle='', pend=None)
            self.etiquetas_ocultas.emit()
        # polvo
        self._avanzar_polvo(dt, c)

    # ------------------------------------------------------------------ particulas (numpy): cada estilo elige su movimiento y su paleta
    N_PART = 240
    # perfiles por fase (solo el astrolabio los usa para el color; los demás estilos usan su paleta y su modo)
    PERFIL = {
        'reposo': dict(col=(0, 1, 4, 3), giro=(0.8, 1.8), dur=(2.6, 4.2), ritmo=1.0, cabeza=2.0),                # motas de luz, lentas
        'timeline': dict(col=(0, 1, 2, 3), giro=(2.2, 4.0), dur=(0.9, 1.7), ritmo=1.0, cabeza=2.4),
        'voz': dict(col=(2, 3, 4, 2), giro=(0.8, 1.8), dur=(1.1, 1.9), ritmo=1.0, cabeza=2.0),         # casi rectas: ondas de voz
        'ia': dict(col=(6, 9, 7, 3), giro=(3.0, 5.5), dur=(0.8, 1.4), ritmo=1.1, cabeza=3.6),           # destellos
        'diseno': dict(col=(5, 8, 3, 5), giro=(0.3, 1.1), dur=(0.8, 1.3), ritmo=1.0, cabeza=2.6),       # trazos rectos, ámbar
        'sfx': dict(col=(7, 6, 2, 7), giro=(2.5, 4.5), dur=(0.9, 1.6), ritmo=1.0, cabeza=3.0),
        'resolve': dict(col=(0, 3, 4, 1), giro=(2.0, 3.5), dur=(0.6, 1.0), ritmo=1.5, cabeza=2.6),      # rápidas: ya casi está
    }
    # duración y ritmo según el modo de movimiento del estilo
    MODOS = {'espiral': ((0.9, 1.7), 1.0), 'ascenso': ((2.4, 4.4), 0.55), 'caida': ((1.2, 2.2), 0.9), 'orbita': ((1.8, 3.2), 0.8)}

    def poner_estilo(self, clave):
        """Cambia el estilo de Inicio (fondo, partículas, HUD): las partículas en vuelo se borran y se rehace el fondo."""
        import estilos_inicio
        self.estilo_clave = clave if clave in estilos_inicio.ESTILOS else estilos_inicio.POR_DEFECTO
        self.estilo = estilos_inicio.crear(self.estilo_clave)
        self._pal = list(self.estilo.pal) + ['#FFC857', '#FFE3A3', '#FFB35C']          # las 3 últimas: el ámbar del final con avisos
        self._pal_claro = [QColor(h).lighter(165).name() for h in self._pal]
        if getattr(self, '_pviva', None) is not None:
            self._pviva[:] = False
        if self._b is not None:
            self._b['t0'][:] = -1e9
        self._fondo_pm = None

    def _avanzar_particulas(self, dt, emitir, ambiente=False):
        n = self.N_PART
        if getattr(self, '_pt0', None) is None:
            self._pt0 = np.full(n, -1e9, dtype=np.float32)       # instante de nacimiento (-1e9 = libre)
            self._pdur = np.ones(n, dtype=np.float32)
            self._pr0 = np.zeros(n, dtype=np.float32)
            self._pth0 = np.zeros(n, dtype=np.float32)
            self._pgiro = np.zeros(n, dtype=np.float32)
            self._pcol = np.zeros(n, dtype=np.int8)
            self._pviva = np.zeros(n, dtype=bool)
            self._pamb = np.zeros(n, dtype=bool)                 # motas de reposo (más tenues)
            self._pcarry = 0.0
        # las que llegaron al final de su recorrido: se absorben (cargan su energia) y quedan libres
        u = (self._t - self._pt0) / self._pdur
        llegaron = self._pviva & (u >= 1.0)
        cuantas = int(llegaron.sum())
        if cuantas:
            self._pviva[llegaron] = False
            self.meta = min(1.0, self.meta + 0.0007 * cuantas)
            self.energia = min(1.0, self.energia + 0.0005 * cuantas)
        if not (emitir or ambiente):
            return
        modo = self.estilo.modo
        dur_modo, ritmo_modo = self.MODOS.get(modo, self.MODOS['espiral'])
        astro = self.estilo_clave == 'astrolabio'
        ligero = 0.5 if (self.modo == 'suave' or self._inactiva or self.calidad < 0.55) else 1.0
        if emitir:
            perfil = (self.PERFIL.get(self._fase) or self.PERFIL['timeline']) if astro else None
            carga = 3.0 if self._carga_final else 1.0
            ritmo = (perfil['ritmo'] if perfil else ritmo_modo)
            self._pcarry += (95.0 + 150.0 * self.energia) * dt * ritmo * carga * ligero
        else:
            perfil = self.PERFIL['reposo'] if astro else None
            self._pcarry += 15.0 * dt * ligero
        k = int(self._pcarry)
        self._pcarry -= k
        if k <= 0:
            return
        libres = np.flatnonzero(~self._pviva)[:k]
        m = len(libres)
        if not m:
            return
        W, H = float(self.width()), float(self.height())
        rng = self._rng
        npal = len(self.estilo.pal)
        dur = perfil['dur'] if perfil else ((dur_modo[0] * 1.5, dur_modo[1] * 1.5) if not emitir else dur_modo)
        self._pt0[libres] = self._t
        self._pdur[libres] = rng.uniform(*dur, m) * (0.7 if (emitir and self._carga_final) else 1.0)
        self._pcol[libres] = rng.choice(perfil['col'], m) if perfil else rng.integers(0, npal, m)
        if modo in ('ascenso', 'caida'):
            self._pth0[libres] = rng.uniform(0.02, 0.98, m)               # posición horizontal (fracción del ancho)
            self._pr0[libres] = rng.uniform(6.0, 34.0, m)                 # balanceo (ascenso) o largo de la estela (caída)
            self._pgiro[libres] = rng.uniform(0.0, math.tau, m)           # fase del balanceo
        else:
            self._pr0[libres] = max(W, H) * rng.uniform(0.16, 0.40, m) * (0.6 + 0.4 * rng.random(m))
            self._pth0[libres] = rng.uniform(0.0, math.tau, m)
            self._pgiro[libres] = rng.uniform(*(perfil['giro'] if perfil else ((2.2, 4.0) if modo == 'espiral' else (3.0, 6.0))), m) * (1.0 if modo == 'espiral' else rng.choice((-1.0, 1.0), m))
        self._pviva[libres] = True
        self._pamb[libres] = not emitir

    def _posiciones_particulas(self, idx, u, c, W, H):
        """(x, y, x2, y2, alfa): la cabeza, la cola de la estela y la opacidad de cada partícula según el modo del estilo."""
        modo = self.estilo.modo
        pr0, th0, gi = self._pr0[idx], self._pth0[idx], self._pgiro[idx]
        u2 = np.maximum(u - 0.04, 0.0)
        cx, cy = c.x(), c.y()
        if modo == 'ascenso':
            def pos(uu):
                return th0 * W + np.sin(uu * 5.0 + gi) * pr0, H * 1.03 - uu * H * 1.08
            alfa = np.minimum(1.0, u * 8.0) * (1.0 - u ** 3)
        elif modo == 'caida':
            def pos(uu):
                return th0 * W + 0 * uu, -30.0 + (uu ** 1.25) * (H + 60.0)
            alfa = np.minimum(1.0, u * 8.0) * (0.35 + 0.65 * u) * (1.0 - u ** 6)
            x, y = pos(u)
            x2, y2 = x, y - pr0 * 3.0                                    # la estela es vertical y larga
            return x, y, x2, y2, alfa
        elif modo == 'orbita':
            def pos(uu):
                e_ = uu ** 1.2
                r = pr0 * (1.0 - 0.45 * e_)
                th = th0 + gi * uu
                return cx + r * np.cos(th), cy + 0.82 * r * np.sin(th)
            alfa = np.minimum(1.0, u * 6.0) * (1.0 - u ** 4)
        else:                                                            # espiral hacia el centro (gravedad)
            def pos(uu):
                e_ = uu ** 1.8
                r = pr0 * (1.0 - e_)
                th = th0 + gi * e_
                return cx + r * np.cos(th), cy + 0.82 * r * np.sin(th)
            e = u ** 1.8
            alfa = np.minimum(1.0, u * 6.0) * (0.25 + 0.75 * np.sqrt(e)) * (1.0 - e ** 6)
        x, y = pos(u)
        x2, y2 = pos(u2)
        return x, y, x2, y2, alfa

    def _dibujar_particulas(self, p, c):
        """Partículas con estela: las mueve el estilo (espiral, ascenso, caída u órbita). Todo en numpy: sin objetos por partícula,
        solo líneas y puntos agrupados por color."""
        if getattr(self, '_pviva', None) is None or not self._pviva.any():
            return
        idx = np.flatnonzero(self._pviva)
        u = ((self._t - self._pt0[idx]) / self._pdur[idx]).astype(np.float32)
        ok = (u >= 0) & (u < 1)
        idx, u = idx[ok], u[ok]
        if not len(idx):
            return
        W, H = float(self.width()), float(self.height())
        x, y, x2, y2, alfa = self._posiciones_particulas(idx, u, c, W, H)
        amb = self._pamb[idx]
        if self._cur_k > 0.03:                             # el cursor aparta las partículas cercanas (como una mano en el agua)
            for xs, ys in ((x, y), (x2, y2)):
                dx, dy = xs - self._cur.x(), ys - self._cur.y()
                d = np.hypot(dx, dy) + 1e-3
                f = np.clip(1.0 - d / 200.0, 0.0, 1.0) ** 2 * 80.0 * self._cur_k
                xs += dx / d * f
                ys += dy / d * f
        brillante = alfa > (0.45 if not amb.any() else 0.3)
        col = self._pcol[idx] % len(self._pal)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cab = self.estilo.cabeza
        trazo = self.estilo.trazo
        for k, hexa in enumerate(self._pal):
            m = col == k
            if not m.any():
                continue
            if trazo:
                for esamb in (False, True):
                    ma = m & (amb == esamb)
                    if ma.any():
                        p.setPen(QPen(_col(hexa, 80 if esamb else 170), 1.2 if esamb else 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
                        p.drawLines([QLineF(float(a), float(b), float(cc), float(d)) for a, b, cc, d in zip(x2[ma], y2[ma], x[ma], y[ma])])
                mb = m & brillante & ~amb
            else:
                mb = m & (alfa > 0.12)
            if mb.any():
                p.setPen(QPen(_col(self._pal_claro[k], 255 if trazo else 150), cab, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPoints(QPolygonF([QPointF(float(a), float(b)) for a, b in zip(x[mb], y[mb])]))

    def _ondas_expl_hechas(self):
        return any(o[2] == '#FFFFFF' and self._t - o[0] < 0.2 for o in self._ondas)

    def _avanzar_polvo(self, dt, c):
        W, H = max(1.0, float(self.width())), max(1.0, float(self.height()))
        g = self.gravedad
        cx, cy = c.x() / W, c.y() / H
        if g > 0.01:
            dx, dy = cx - self._px, cy - self._py
            d2 = np.maximum(dx * dx + dy * dy, 0.002)
            ac = g * 0.9 * dt
            self._pvx += (dx / np.sqrt(d2)) * ac * 0.35 + (-dy) * ac * 0.7
            self._pvy += (dy / np.sqrt(d2)) * ac * 0.35 + (dx) * ac * 0.7
        self._pvx *= (1.0 - 0.8 * dt)
        self._pvy *= (1.0 - 0.8 * dt)
        self._px += self._pvx * dt * 12
        self._py += self._pvy * dt * 12
        # los que llegan al centro o se salen reaparecen en el borde
        d = (self._px - cx) ** 2 + (self._py - cy) ** 2
        fuera = (d < 0.0009) | (self._px < -0.1) | (self._px > 1.1) | (self._py < -0.1) | (self._py > 1.1)
        if fuera.any():
            n = int(fuera.sum())
            ang = self._rng.random(n) * math.tau
            self._px[fuera] = (0.5 + 0.75 * np.cos(ang)).astype(np.float32)
            self._py[fuera] = (0.5 + 0.75 * np.sin(ang)).astype(np.float32)
            self._pvx[fuera] = 0
            self._pvy[fuera] = 0
        # flotación orgánica
        self._pvx += (np.sin(self._t * 0.4 + self._py * 9.0) * 0.0006).astype(np.float32)
        self._pvy += (np.cos(self._t * 0.35 + self._px * 7.0) * 0.0006).astype(np.float32)

    # ------------------------------------------------------------------ la esfera con numpy
    def _luz_esfera(self, Ws, Hs, cx, cy, Rs):
        """El búfer de luz (float32 Hs x Ws) con la esfera + el polvo, y su bloom."""
        t = self._t
        e = self.energia
        g = self.gravedad
        n = len(self._bx)
        # ondas orgánicas: patrón de pétalos que gira + respiración
        amp = 0.016 + 0.030 * e + 0.006 * np.sin(t * 0.7)
        lobulos = 6.0 + (2.0 if e > 0.6 else 0.0)
        onda_a = np.sin(lobulos * self._th + 0.55 * t) * np.sin(5.0 * self._phi - 0.8 * t)
        onda_b = np.sin(3.0 * self._phi + 1.1 * t + self._th * 2.0)
        d = amp * (onda_a + 0.55 * onda_b)
        d += 0.008 * np.sin(31.0 * self._th + 9.0 * t) * e
        # el dibujo de la esfera: anillos que viajan por los polos y pétalos que giran (como en la imagen de referencia)
        anillos = np.sin(15.0 * self._phi - 2.2 * t + 2.2 * np.sin(2.0 * self._th + 0.7 * t))
        petalos = np.sin(lobulos * 1.5 * self._th + 0.9 * t) * np.sin(7.0 * self._phi - 1.1 * t)
        patron = np.clip(0.55 * anillos + 0.45 * petalos, 0.0, 1.0) ** 1.6
        radio = 1.0 + d
        # explosión: las partículas salen despedidas
        u = self.expl
        if u > 0:
            radio = radio * (1.0 + 7.5 * (u ** 1.6) * (0.4 + self._azar))
        escala_vida = 1.0
        if self.reaparecer < 1.0 and u == 0:
            escala_vida = 0.2 + 0.8 * (1.0 - (1.0 - self.reaparecer) ** 3)
        x, y, z = self._bx * radio, self._by * radio, self._bz * radio
        # giro: más rápido con la gravedad y la energía
        ay = t * (0.18 + 1.5 * g + 1.2 * e)
        ax = 0.30 + 0.07 * math.sin(t * 0.21)
        cay, say = math.cos(ay), math.sin(ay)
        x1 = x * cay + z * say
        z1 = -x * say + z * cay
        cax, sax = math.cos(ax), math.sin(ax)
        y1 = y * cax - z1 * sax
        z2 = y * sax + z1 * cax
        persp = 1.0 / (1.0 - 0.22 * z2)
        pulso = 1.0 + 0.03 * math.sin(t * 22.0) * e * e
        sx = cx + Rs * escala_vida * pulso * x1 * persp
        sy = cy - Rs * escala_vida * pulso * y1 * persp
        # brillo: cara delantera, borde (efecto vidrio), crestas de la onda
        frente = 0.5 + 0.5 * z2
        borde = (1.0 - np.abs(z2)) ** 2
        inten = (0.07 + 0.13 * frente + 0.55 * borde + 0.62 * patron * (0.5 + 0.5 * frente)) * (0.75 + 0.45 * e)
        if u > 0:
            inten = inten * max(0.0, 1.0 - u * 0.9)
        inten = inten * (0.55 + 0.45 * self.reaparecer if self._estado in ('hecho', 'reposo') else 1.0)
        # el polvo
        W = Ws
        H = Hs
        sx_p = self._px * W
        sy_p = self._py * H
        inten_p = self._pb * (0.18 + 0.5 * g + 0.25 * e)
        X = np.concatenate([sx, sx_p])
        Y = np.concatenate([sy, sy_p])
        V = (np.concatenate([inten, inten_p]) * ((Hs / 248.0) ** 2)).astype(np.float32)   # v5.4: misma luz por area a cualquier resolucion
        # splat bilineal en un búfer plano
        x0 = np.floor(X).astype(np.int32)
        y0 = np.floor(Y).astype(np.int32)
        fx = (X - x0).astype(np.float32)
        fy = (Y - y0).astype(np.float32)
        ok = (x0 >= 0) & (x0 < W - 1) & (y0 >= 0) & (y0 < H - 1)
        x0, y0, fx, fy, V = x0[ok], y0[ok], fx[ok], fy[ok], V[ok]
        base = y0 * W + x0
        tam = W * H
        buf = (np.bincount(base, V * (1 - fx) * (1 - fy), tam) + np.bincount(base + 1, V * fx * (1 - fy), tam)
               + np.bincount(base + W, V * (1 - fx) * fy, tam) + np.bincount(base + W + 1, V * fx * fy, tam)).astype(np.float32)
        buf = buf.reshape(H, W)
        # bloom barato: el resplandor se calcula en 1/4 de resolución y Qt lo agranda suavizado
        h4, w4 = (H // 4) * 4, (W // 4) * 4
        tiny = buf[:h4, :w4].reshape(h4 // 4, 4, w4 // 4, 4).sum(axis=(1, 3))
        glow = _caja(_caja(tiny, 3, 1), 3, 0)
        glow = _caja(_caja(glow, 3, 1), 3, 0)
        return buf, glow

    def _tablas(self):
        """Tablas de color 1024 → RGB (curva suave tipo exposición + color de la energía). Se rehacen si cambia la energía."""
        e = self.energia
        err = self._estado == 'error'
        if abs(e - self._lut_e) > 0.01 or not hasattr(self, '_tab_s') or err != getattr(self, '_lut_err', False):
            self._lut_e = e
            self._lut_err = err
            hot = max(0.0, min(1.0, (e - 0.5) * 2.0))
            lut = (self._luts[0] * (1 - hot) + self._luts[1] * hot).astype(np.uint8)
            if err:
                lut = _tabla_roja()
            i = np.arange(1024, dtype=np.float32) / 256.0                       # luz 0..4
            tono_s = (255.0 * (1.0 - np.exp(-i * (0.95 + 0.25 * e)))).astype(np.uint8)
            tono_g = (255.0 * (1.0 - np.exp(-i * (0.34 + 0.22 * e)))).astype(np.uint8)
            self._tab_s = lut[tono_s]
            self._tab_g = lut[tono_g]

    def _a_imagen(self, luz, tabla, escala, nombre):
        idx = np.minimum(luz * escala, 1023.0).astype(np.int32)
        rgb = np.ascontiguousarray(tabla[idx])
        setattr(self, nombre, rgb)
        h, w = idx.shape
        return QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)

    # ------------------------------------------------------------------ dibujo
    def paintEvent(self, _e):
        """v5.4: la escena solo se vuelve a calcular y dibujar cuando le toca un cuadro nuevo (cada ~33 ms, desde _tic).
        Cualquier otro repintado (el destello de un boton, el cursor sobre una tarjeta, escribir en un campo: todo lo que
        se mueve ENCIMA de la escena repinta tambien la escena) solo copia el ultimo cuadro ya dibujado. Antes cada uno de
        esos repintados repetia todo el calculo de la esfera (numpy) y el HUD."""
        W, H = self.width(), self.height()
        if W < 10 or H < 10:
            return
        t0 = time.perf_counter()
        dpr = self.devicePixelRatioF()
        esc = self._esc_cuadro
        clave = (W, H, round(dpr, 3), round(esc, 2))
        cuadro = self._cuadro
        if cuadro is None or self._cuadro_clave != clave or t0 - self._cuadro_t >= max(0.012, self._ms_reloj * 0.0009):
            if cuadro is None or self._cuadro_clave != clave:
                # la escena se pinta a una fracción de la resolución real si el equipo no da los 60 fps (pantallas 4K o con escala
                # alta): el fondo es borroso por naturaleza y se nota mucho menos que los tirones
                cuadro = QPixmap(max(1, int(math.ceil(W * dpr * esc))), max(1, int(math.ceil(H * dpr * esc))))
                cuadro.setDevicePixelRatio(dpr * esc)
                self._cuadro, self._cuadro_clave = cuadro, clave
            q = QPainter(cuadro)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self.dibujar(q, W, H)
            q.end()
            self._cuadro_t = t0
            ms = (time.perf_counter() - t0) * 1000.0
            self._ms_cuadro = self._ms_cuadro * 0.88 + ms * 0.12
            self._cuadros += 1
            if self._cuadros % 24 == 0:
                if self._ms_cuadro > 11.0 and self._esc_cuadro > 0.62:
                    self._esc_cuadro = max(0.62, self._esc_cuadro - 0.1)
                elif self._ms_cuadro < 6.0 and self._esc_cuadro < 1.0:
                    self._esc_cuadro = min(1.0, self._esc_cuadro + 0.05)
                # los detalles del HUD bajan solo si ni así llega
                if self._ms_cuadro > 15.0 and self.calidad > 0.45:
                    self.calidad = max(0.45, self.calidad - 0.15)
                elif self._ms_cuadro < 8.0 and self.calidad < 1.0:
                    self.calidad = min(1.0, self.calidad + 0.1)
        p = QPainter(self)
        if esc < 0.999:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(QRectF(0, 0, W, H), cuadro, QRectF(cuadro.rect()))
        else:
            p.drawPixmap(0, 0, cuadro)
        p.end()

    def dibujar(self, p, W, H):
        c, Rs, rect = self._geometria()
        sac = self._sacudida
        if sac > 0:
            p.translate(math.sin(self._t * 90) * 5 * min(1.0, sac * 2), math.cos(self._t * 77) * 4 * min(1.0, sac * 2))
        # fondo (degradado + haces + velo + viñeta): se pinta a 1/3 de resolución, que es borroso por naturaleza, y se escala
        e = self.energia
        bajo = self._fondo_bajo(W, H, c, e)
        p.drawPixmap(QRectF(-10, -10, W + 20, H + 20), bajo, QRectF(bajo.rect()))
        self.estilo.frente(p, W, H, c, self._t, self._estado)
        # anillos de luz muy suaves
        for t0, fuerza in self._anillos:
            u = (self._t - t0) / 1.6
            rr = Rs * (0.9 + 2.4 * u)
            p.setPen(QPen(_col('#4589FF', 255 * fuerza * (1 - u) ** 2 * 0.5), 2.0 + 6 * u))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, rr, rr)
        # sombra suave bajo los textos del botón (se leen aunque la esfera pase por detrás)
        if self._estado in ('trabajando', 'explotando', 'hecho', 'error', 'reposo'):
            sombra = QRadialGradient(QPointF(c.x(), c.y() + Rs * 0.82), Rs * 0.95)
            sombra.setColorAt(0.0, QColor(2, 6, 16, 150))
            sombra.setColorAt(1.0, QColor(2, 6, 16, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(sombra)
            p.save()
            p.translate(c.x(), c.y() + Rs * 0.82)
            p.scale(1.0, 0.34)
            p.translate(-c.x(), -(c.y() + Rs * 0.82))
            p.drawEllipse(QPointF(c.x(), c.y() + Rs * 0.82), Rs * 0.95, Rs * 0.95)
            p.restore()
        try:
            if self.estilo.hud:
                import mograf_ui
                mograf_ui.dibujar_hud(p, W, H, c, Rs, 3.0 if self._quieto else self._t, self.energia, self._estado,
                                      self.calidad, self.meta)
        except Exception as ex:
            if not getattr(self, '_aviso_hud', False):
                self._aviso_hud = True
                try:
                    import registro
                    registro.aviso(f'HUD de Inicio: {type(ex).__name__}: {ex}', 'escena_go')
                except Exception:
                    pass
        self._dibujar_gravedad(p, c, Rs)
        self._dibujar_particulas(p, c)
        self._dibujar_chispas_paso(p, c)
        self._dibujar_chispas(p)
        for r in self._rayos:
            self._dibujar_rayo(p, c, Rs, r)
        for onda in self._ondas:
            self._dibujar_onda(p, onda, W, H)
        self._dibujar_pasos(p, rect)
        for k_ in self._cometas:
            self._dibujar_cometa(p, k_)
        for im in self._impactos:
            self._dibujar_impacto(p, im)
        if self._barra_d is not None and self._barra_a > 0.01:
            self._dibujar_barra(p, W, H, rect.bottom())
        if self.destello > 0.01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_col('#DFF1FF', 235 * self.destello ** 1.4))
            p.drawRect(QRectF(-10, -10, W + 20, H + 20))

    # ------------------------------------------------------------------ la barra de progreso de abajo
    def _avanzar_barra(self, dt):
        """Lee los datos de la barra (el panel) y la hace aparecer / irse con suavidad; al terminar GO se queda llena 1,4 s y se va."""
        d = None
        if self.datos_barra is not None:
            try:
                d = self.datos_barra()
            except Exception:
                d = None
        obj = 0.0
        if d is not None:
            self._barra_d = d
            obj = 1.0 if d['estado'] == 'trabajando' else max(0.0, 1.0 - max(0.0, d.get('cierre', 0.0) - 1.4) / 1.0)
        self._barra_a += (obj - self._barra_a) * min(1.0, dt * 7.0)
        if obj == 0.0 and self._barra_a < 0.01:
            self._barra_a, self._barra_d = 0.0, None

    def _dibujar_barra(self, p, W, H, bajo_pasos):
        """v5.22 (el usuario: «mejora su barra de progreso… abajo»): la barra de GO al pie de Inicio. Antes era una línea de 2 px del HUD
        que seguía la energía de la esfera (no el %: marcaba ~60 con el centro en 45) y desaparecía en equipos lentos y en los estilos sin
        HUD. Ahora lleva el MISMO % que el centro del botón (PanelGo._datos_barra), un tramo por paso con el peso de lo que tarda cada uno
        (los pasos muy cortos se funden con el anterior: si no, quedaban puntitos), un brillo que recorre el tramo en curso, la cabeza
        que brilla y, a sus lados, «3/6 · paso» y «45 % · ~2 min». Va siempre por debajo de la lista de pasos (`bajo_pasos`)."""
        d, a = self._barra_d, self._barra_a
        total = min(W - 96.0, 980.0)
        if total < 220.0:
            return
        alto = 6.0
        y = min(H - 14.0, max(H - 30.0, bajo_pasos + 18.0))
        textos = total >= 640.0 and bool(d.get('izq') or d.get('der'))
        lado = 196.0 if textos else 0.0                                            # el sitio de cada texto (fijo: la barra no salta)
        x0 = (W - total) / 2.0 + (lado + 14.0 if textos else 0.0)
        ancho = total - 2 * (lado + 14.0 if textos else 0.0)
        prog = max(0.0, min(1.0, float(d.get('prog', 0.0))))
        trabaja = d['estado'] == 'trabajando'
        base = QColor('#FF6B6B') if d['estado'] == 'error' else QColor(getattr(self.estilo, 'acento', '#22D3EE'))
        claro = QColor(min(255, base.red() + 110), min(255, base.green() + 110), min(255, base.blue() + 110))
        xp = x0 + ancho * prog
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        # una sombra suave detrás (se lee sobre la esfera, los haces y las partículas)
        sombra = QRectF((W - total) / 2.0 - 24, y - 20, total + 48, alto + 40)
        g0 = QLinearGradient(0, sombra.top(), 0, sombra.bottom())
        g0.setColorAt(0.0, QColor(2, 6, 14, 0))
        g0.setColorAt(0.5, QColor(2, 6, 14, int(135 * a)))
        g0.setColorAt(1.0, QColor(2, 6, 14, 0))
        p.setBrush(g0)
        p.drawRoundedRect(sombra, 22, 22)
        relleno = QLinearGradient(x0, 0, x0 + ancho, 0)
        relleno.setColorAt(0.0, _col(base.name(), 255 * a))
        relleno.setColorAt(1.0, _col(claro.name(), 255 * a))
        hueco = 4.0
        piezas = []                                                                # (x desde, x hasta, estado) en píxeles
        for _clave, i0, i1, est in (d.get('tramos') or ()):
            a0, a1 = x0 + ancho * i0, x0 + ancho * i1
            if a1 - a0 < 0.5:
                continue
            if piezas and (a1 - a0 < 18.0 or piezas[-1][1] - piezas[-1][0] < 18.0):  # un paso muy corto se funde con el de al lado
                piezas[-1] = (piezas[-1][0], a1, 'activo' if 'activo' in (piezas[-1][2], est) else est)
            else:
                piezas.append((a0, a1, est))
        piezas = piezas or [(x0, x0 + ancho, 'activo')]
        en_curso = None
        for a0, a1, est in piezas:
            sx0 = a0 + (hueco / 2 if a0 > x0 + 0.5 else 0.0)
            sx1 = a1 - (hueco / 2 if a1 < x0 + ancho - 0.5 else 0.0)
            if sx1 - sx0 < 1.0:
                continue
            p.setBrush(QColor(255, 255, 255, int(30 * a)))                      # la pista del tramo
            p.drawRoundedRect(QRectF(sx0, y, sx1 - sx0, alto), alto / 2, alto / 2)
            fin = min(sx1, xp)
            if fin > sx0 + 0.5:                                                    # lo hecho del tramo
                p.setBrush(relleno)
                p.drawRoundedRect(QRectF(sx0, y, fin - sx0, alto), alto / 2, alto / 2)
                if est == 'activo':
                    en_curso = (sx0, fin)
        if en_curso and trabaja and not self._quieto and en_curso[1] - en_curso[0] > 12.0:
            s0, s1 = en_curso                                                      # un brillo recorre lo hecho del paso en curso
            cx = s0 - 40.0 + (s1 - s0 + 80.0) * ((self._t * 0.55) % 1.0)
            gb = QLinearGradient(cx - 40.0, 0, cx + 40.0, 0)
            gb.setColorAt(0.0, QColor(255, 255, 255, 0))
            gb.setColorAt(0.5, QColor(255, 255, 255, int(150 * a)))
            gb.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.save()
            p.setClipRect(QRectF(s0, y - 1, s1 - s0, alto + 2))
            p.setBrush(gb)
            p.drawRoundedRect(QRectF(s0, y, s1 - s0, alto), alto / 2, alto / 2)
            p.restore()
        if trabaja and prog > 0.002:                                               # la cabeza
            gc = QRadialGradient(QPointF(xp, y + alto / 2), 15.0)
            gc.setColorAt(0.0, QColor(255, 255, 255, int(235 * a)))
            gc.setColorAt(0.35, _col(claro.name(), 150 * a))
            gc.setColorAt(1.0, _col(base.name(), 0))
            p.setBrush(gc)
            p.drawEllipse(QPointF(xp, y + alto / 2), 15.0, 15.0)
        if textos:                                                                 # «3/6 · IA y palabras» [ barra ] «45 % · ~2 min»
            izq = QRectF((W - total) / 2.0, y + alto / 2 - 10, lado, 20)
            der = QRectF(x0 + ancho + 14.0, y + alto / 2 - 10, lado, 20)
            f = ui.fuente(12, peso='medio')
            p.setFont(f)
            p.setPen(QColor(226, 236, 250, int(225 * a)))
            p.drawText(izq, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       QFontMetricsF(f).elidedText(d.get('izq') or '', Qt.TextElideMode.ElideRight, lado))
            f = ui.fuente(12, peso='negrita')
            try:
                f.setFeature(QFont.Tag('tnum'), 1)                                 # cifras de ancho fijo: el % no baila
            except Exception:
                pass
            p.setFont(f)
            p.setPen(_col(claro.name(), 245 * a))
            p.drawText(der, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       QFontMetricsF(f).elidedText(d.get('der') or '', Qt.TextElideMode.ElideRight, lado))
        p.restore()

    def _fondo_bajo(self, W, H, c, e):
        """El fondo entero de la escena a 1/3 de resolución (~0,6 ms): lo pinta el estilo elegido (estilos_inicio)."""
        w, h = max(8, int(W / 3.0)), max(8, int(H / 3.0))
        pm = self._fondo_pm
        if pm is None or pm.width() != w or pm.height() != h:
            pm = self._fondo_pm = QPixmap(w, h)
        q = QPainter(pm)
        q.scale(w / float(W), h / float(H))
        self.estilo.fondo(q, W, H, c, e, self._t, self._estado)
        q.end()
        return pm

    def _dibujar_gravedad(self, p, c, Rs):
        """Lente gravitacional y masa crítica: anillos que se estiran y un núcleo que se pone blanco al cargarse."""
        e = self.energia
        if e < 0.25 or self.expl > 0:
            return
        p.setPen(Qt.PenStyle.NoPen)
        k = (e - 0.25) / 0.75
        g = QRadialGradient(c, Rs * 0.95)
        g.setColorAt(0.0, _col('#FFFFFF', 120 * k ** 2))
        g.setColorAt(0.35, _col('#7FB5FF', 80 * k))
        g.setColorAt(1.0, _col('#4589FF', 0))
        p.setBrush(g)
        p.drawEllipse(c, Rs * 0.95, Rs * 0.95)
        if e > 0.55:
            for j in range(3):
                ph = (self._t * (0.6 + 0.2 * j) + j * 0.33) % 1.0
                rr = Rs * (1.05 + 0.5 * ph)
                p.setPen(QPen(_col('#9CC8FF', 120 * (e - 0.5) * (1 - ph) ** 1.5), 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(c, rr, rr * (0.86 - 0.12 * math.sin(self._t * 3 + j)))

    def _dibujar_rayo(self, p, c, Rs, r):
        t0, ang = r
        u = (self._t - t0) / 0.22
        a = 1.0 - u
        pts = []
        x, y = c.x() + math.cos(ang) * Rs * 0.95, c.y() + math.sin(ang) * Rs * 0.8
        for k in range(9):
            ang2 = ang + random.uniform(-0.28, 0.28)
            x += math.cos(ang2) * Rs * 0.12
            y += math.sin(ang2) * Rs * 0.1
            pts.append(QPointF(x, y))
        for ancho, alfa in ((6, 40), (3, 90), (1.3, 255)):
            p.setPen(QPen(_col('#BFE0FF', alfa * a), ancho, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(pts)

    def _dibujar_objeto(self, p, o, c):
        u = o.u(self._t)
        if u < 0:
            return
        pos, e = o.pos(u, c)
        escala = o.esc * (1.0 - 0.75 * e)
        alfa = min(1.0, u * 5.0) * (1.0 - e ** 3)
        if escala < 1.5 or alfa <= 0.02:
            return
        # estela
        for k in range(1, 7):
            pu = max(0.0, u - k * 0.014)
            q, _ = o.pos(pu, c)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_col(o.color, 80 * alfa * (1 - k / 7.0)))
            rad = 3.6 * (1 - k / 7.0) + 0.6
            p.drawEllipse(q, rad, rad)
        pm, w, h = _sprite(o.tipo, o.color, o.texto, self.devicePixelRatioF())
        k = escala / 34.0
        # 3D: el objeto da vueltas sobre sus ejes y la proyeccion en perspectiva de QTransform lo achica y estira
        tf = QTransform()
        tf.translate(pos.x(), pos.y())
        tf.rotate(math.degrees(o.rot) * 0.5 + u * o.giro * 22.0)
        tf.rotate(u * o.giro * 150.0 + o.th0 * 25.0, Qt.Axis.YAxis)
        tf.rotate(24.0 * math.sin(self._t * 2.1 + o.th0), Qt.Axis.XAxis)
        tf.scale(k, k)
        p.save()
        p.setTransform(tf, True)
        p.setOpacity(alfa)
        p.drawPixmap(QPointF(-w / 2.0, -h / 2.0), pm)
        p.restore()
        p.setOpacity(1.0)

    def _dibujar_salida(self, p):
        """El final festivo: notas, ondas de sonido y algún emoji salen del orbe, flotan en 3D y se desvanecen."""
        dpr = self.devicePixelRatioF()
        for o in self._salida:
            tt = self._t - o['t0']
            if tt < 0:
                continue
            u = tt / o['dur']
            f = (1.0 - math.exp(-2.6 * tt)) / 2.6
            x = o['x0'] + o['vx'] * f
            y = o['y0'] + o['vy'] * f - 40.0 * tt
            alfa = min(1.0, tt * 7.0) * (1.0 - max(0.0, (u - 0.55) / 0.45) ** 1.4)
            if alfa <= 0.02:
                continue
            pm, w, h = _sprite(o['tipo'], o['color'], o['texto'], dpr)
            k = o['esc'] / 34.0 * (0.55 + 0.6 * min(1.0, tt * 3.0))
            tf = QTransform()
            tf.translate(x, y)
            tf.rotate(o['rot'] + tt * 40.0 * o['spin'])
            tf.rotate(tt * 220.0 * o['spin'], Qt.Axis.YAxis)
            tf.rotate(18.0 * math.sin(self._t * 2.4 + o['rot']), Qt.Axis.XAxis)
            tf.scale(k, k)
            p.save()
            p.setTransform(tf, True)
            p.setOpacity(alfa)
            p.drawPixmap(QPointF(-w / 2.0, -h / 2.0), pm)
            p.restore()
        p.setOpacity(1.0)

    def _dibujar_chispas(self, p):
        """Las ráfagas de luz: chispas rápidas con estela (tipo 0) y brasas que frenan, suben y se apagan (tipo 1). Todo agrupado por color."""
        b = self._b
        if b is None:
            return
        tt = (self._t - b['t0'])
        vivas = (tt >= 0) & (tt < b['vida'])
        if not vivas.any():
            return
        idx = np.flatnonzero(vivas)
        tt, vida = tt[idx], b['vida'][idx]
        f = tt / vida

        def pos(ff, tcur):
            d = b['vel'][idx] * (1.0 - (1.0 - ff) ** 2.2) * vida
            x = b['x0'][idx] + np.cos(b['ang'][idx]) * d
            y = b['y0'][idx] + np.sin(b['ang'][idx]) * d + b['grav'][idx] * tcur * tcur * 0.5
            return x, y
        x, y = pos(f, tt)
        f0 = np.maximum(f - 0.06, 0.0)
        x0, y0 = pos(f0, f0 * vida)
        tipo, col = b['tipo'][idx], b['col'][idx] % len(self._pal)
        alfa = (1.0 - f) ** 1.3
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k, hexa in enumerate(self._pal):
            mk = col == k
            if not mk.any():
                continue
            m0 = mk & (tipo == 0)
            if m0.any():
                for sub, al in ((alfa[m0] > 0.45, 255), (alfa[m0] <= 0.45, 120)):
                    mm = np.flatnonzero(m0)[sub]
                    if not len(mm):
                        continue
                    p.setPen(QPen(_col(hexa, al), 1.8 if al > 200 else 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    p.drawLines([QLineF(float(a_), float(b_), float(c_), float(d_)) for a_, b_, c_, d_ in zip(x0[mm], y0[mm], x[mm], y[mm])])
            m1 = mk & (tipo == 1)
            if m1.any():
                for lim, al, gr in ((0.6, 230, 3.4), (0.3, 120, 2.6)):
                    mm = np.flatnonzero(m1 & (alfa > lim) & (alfa <= (1.0 if lim == 0.6 else 0.6)))
                    if len(mm):
                        p.setPen(QPen(_col(hexa, al), gr, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                        p.drawPoints(QPolygonF([QPointF(float(a_), float(b_)) for a_, b_ in zip(x[mm], y[mm])]))

    def _dibujar_onda(self, p, onda, W, H):
        t0, c, color, grueso, plana = onda
        u = (self._t - t0) / (0.8 if plana else 1.5)
        if u < 0 or u > 1:
            return
        rr = (260 if plana else max(W, H) * 0.95) * (1 - (1 - u) ** 2.4)
        a = (1.0 - u) ** 1.6
        ry = rr * (0.16 if plana else 1.0)
        for ancho, alfa in ((16 * grueso, 40), (3.0 * grueso, 230)):
            p.setPen(QPen(_col(color, alfa * a), ancho))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, rr, ry)

    def _dibujar_cometa(self, p, k):
        u = (self._t - k.t0) / k.dur
        if u < 0:
            return
        e = u ** 1.7
        x = k.x0 + (k.x1 - k.x0) * (1 - (1 - e) ** 2)
        y = -70.0 + (k.y1 + 70.0) * e
        # dirección del movimiento (para la cola)
        e2 = max(0.0, (u - 0.02)) ** 1.7
        xp = k.x0 + (k.x1 - k.x0) * (1 - (1 - e2) ** 2)
        yp = -70.0 + (k.y1 + 70.0) * e2
        vx, vy = x - xp, y - yp
        n = math.hypot(vx, vy) or 1.0
        vx, vy = vx / n, vy / n
        largo = 260.0 * (0.4 + 0.6 * min(1.0, u * 2))
        cabeza = QPointF(x, y)
        cola = QPointF(x - vx * largo, y - vy * largo)
        g = QLinearGradient(cola, cabeza)
        g.setColorAt(0.0, _col(k.color, 0))
        g.setColorAt(0.7, _col(k.color, 120))
        g.setColorAt(1.0, _col('#FFFFFF', 255))
        for ancho, alfa in ((20, 0.18), (9, 0.5), (3.2, 1.0)):
            gg = QLinearGradient(cola, cabeza)
            gg.setColorAt(0.0, _col(k.color, 0))
            gg.setColorAt(1.0, _col(k.color if ancho > 3.2 else '#FFFFFF', 255 * alfa))
            p.setPen(QPen(gg, ancho, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(cola, cabeza)
        halo = QRadialGradient(cabeza, 30)
        halo.setColorAt(0.0, _col('#FFFFFF', 255))
        halo.setColorAt(0.25, _col(k.color, 200))
        halo.setColorAt(1.0, _col(k.color, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(cabeza, 30, 30)
        for j in range(6):                                   # chispas de la cola
            f = random.random()
            q = QPointF(cabeza.x() - vx * largo * f * 0.8 + random.uniform(-7, 7), cabeza.y() - vy * largo * f * 0.8 + random.uniform(-7, 7))
            p.setBrush(_col('#FFFFFF', 190 * (1 - f)))
            p.drawEllipse(q, 1.5, 1.5)

    def _dibujar_impacto(self, p, im):
        u = (self._t - im.t0) / 1.1
        a = (1.0 - u)
        # destello del choque
        g = QRadialGradient(QPointF(im.x, im.y), 120 * (0.3 + u))
        g.setColorAt(0.0, _col('#FFFFFF', 200 * a ** 2))
        g.setColorAt(0.4, _col(im.color, 110 * a ** 2))
        g.setColorAt(1.0, _col(im.color, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(im.x, im.y), 120 * (0.3 + u), 120 * (0.3 + u))
        for vx, vy, vida in im.chispas:                      # chispas con gravedad
            tt = (self._t - im.t0)
            if tt > vida:
                continue
            x = im.x + vx * tt
            y = im.y + vy * tt + 520 * tt * tt
            f = 1.0 - tt / vida
            p.setBrush(_col('#FFFFFF' if f > 0.5 else im.color, 255 * f))
            p.drawEllipse(QPointF(x, y), 2.2 * f + 0.4, 2.2 * f + 0.4)

    def _dibujar_pasos(self, p, rect):
        """Las etiquetas de los pasos que ya aterrizaron."""
        if not self._pasos:
            return
        ancho = min(480.0, max(300.0, rect.width()))
        x0 = rect.center().x() - ancho / 2
        for i, st in enumerate(self._pasos):
            if st['aterrizo'] is None:
                continue
            y = rect.top() + i * self.ALTO_FILA
            ent = min(1.0, (self._t - st['aterrizo']) / 0.35)
            ent = 1 - (1 - ent) ** 3
            est = st['estado']
            color = {'activo': self.estilo.acento, 'hecho': '#24D18F', 'saltado': '#6C7B96', 'error': '#FF6B6B'}.get(est, self.estilo.acento)
            caja = QRectF(x0, y + 2, ancho, self.ALTO_FILA - 6)
            p.save()
            p.translate(0, (1 - ent) * -10)
            p.setOpacity(ent)
            # resplandor del aterrizaje
            if st['brillo'] > 0.02:
                halo = QRadialGradient(caja.center(), ancho * 0.6)
                halo.setColorAt(0.0, _col(color, 120 * st['brillo']))
                halo.setColorAt(1.0, _col(color, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawRoundedRect(caja.adjusted(-30, -14, 30, 14), 16, 16)
            respira = (0.5 + 0.5 * math.sin(self._t * 4.2)) if est == 'activo' else 0.0
            p.setPen(QPen(_col(color, 70 + 140 * st['brillo'] + 70 * respira), 1.0 + 1.4 * st['brillo'] + 0.5 * respira))
            p.setBrush(_col('#07201A', 205))
            p.drawRoundedRect(caja, 12, 12)
            # icono de estado
            cx, cy = caja.left() + 20, caja.center().y()
            if est == 'hecho':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_col('#24D18F'))
                p.drawEllipse(QPointF(cx, cy), 8.5, 8.5)
                p.setPen(QPen(_col('#04140C'), 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawPolyline([QPointF(cx - 3.6, cy + 0.2), QPointF(cx - 1.0, cy + 2.8), QPointF(cx + 3.8, cy - 2.8)])
            elif est == 'error':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_col('#FF6B6B'))
                p.drawEllipse(QPointF(cx, cy), 8.5, 8.5)
                p.setPen(QPen(_col('#FFFFFF'), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(cx - 3, cy - 3), QPointF(cx + 3, cy + 3))
                p.drawLine(QPointF(cx + 3, cy - 3), QPointF(cx - 3, cy + 3))
            elif est == 'activo':
                p.setPen(QPen(_col('#22324F'), 2.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), 8.5, 8.5)
                p.setPen(QPen(_col('#7DFFB2'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(QRectF(cx - 8.5, cy - 8.5, 17, 17), int(-self._t * 360 * 16 * 1.1), 110 * 16)
            else:
                p.setPen(QPen(_col('#3A4A66'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), 8.5, 8.5)
                p.drawLine(QPointF(cx - 3.5, cy), QPointF(cx + 3.5, cy))
            fuente = ui.fuente(14, peso='negrita' if est == 'activo' else 'medio')
            p.setFont(fuente)
            p.setPen(_col({'activo': '#FFFFFF', 'hecho': '#E6EEFB', 'error': '#FFB4AC'}.get(est, '#8392AD')))
            p.drawText(QRectF(cx + 20, caja.top(), ancho - 60 - 130, caja.height()),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), st['texto'])
            if st['detalle']:
                p.setFont(ui.fuente(11))
                p.setPen(_col('#8392AD'))
                p.drawText(QRectF(caja.right() - 140, caja.top(), 128, caja.height()),
                           int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), st['detalle'])
            p.restore()
            p.setOpacity(1.0)

    # ------------------------------------------------------------------ eventos
    def showEvent(self, e):
        super().showEvent(e)
        self.activar(True)

    def hideEvent(self, e):
        self.activar(False)
        super().hideEvent(e)
