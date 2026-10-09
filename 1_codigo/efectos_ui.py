# CineCaptions · By Cinema Productions
# 1_codigo/efectos_ui.py — animaciones de la interfaz: fondo vivo, vistas reales animadas, entrada escalonada de tarjetas.
"""
efectos_ui.py  (v5.2)
---------------------
El movimiento de la interfaz (pedido: «que la página de inicio sea todo un
espectáculo, con más animaciones... aplica lo mismo a las pestañas y siempre
tienen que tener movimiento»).

  * FondoVivo: el escenario detras de todas las pantallas. Auroras de color
    que derivan despacio (pintadas en una imagen chica y ampliada: el
    desenfoque sale gratis), una rejilla de puntos con paralaje, particulas
    que suben y titilan, y los golpes de efecto: explosion de confeti (GO
    terminado) y ondas expansivas (un clic). En Inicio va a toda intensidad;
    en las demas pantallas, tenue y a menos fotogramas (no compite con lo que
    se lee ni repinta de mas).
  * entrada_escalonada(): las tarjetas de una pantalla entran una tras otra
    (fundido + subida corta) al cambiar de pestaña.

Criterio (las skills de movimiento): curvas de salida (OutCubic / OutQuint),
nada de animaciones en lo que se usa cien veces por minuto (los atajos de
teclado no animan), el espectaculo en los momentos raros (GO, el exito).
Respeta «Reducir animaciones» (Ajustes > Interfaz).
"""
import math
import random
import time

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap, QRadialGradient, QRegion
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QWidget

import qt_kit as ui
import ritmo_ui
from qt_kit import QColor, QColorReal


def reducir_animaciones():
    try:
        import ajustes_ui
        return bool(ajustes_ui.leer_prefs().get('reducir_animaciones'))
    except Exception:
        return False


def _paleta_de(clave):
    """Las 3 luces de fondo de una página: las del ESTILO elegido (cada página las rota para no ser idénticas) o las de siempre."""
    try:
        import ajustes_ui
        import estilos_inicio
        if not ajustes_ui.leer_prefs().get('go_estilo'):          # sin estilo elegido en Ajustes: las luces de siempre
            raise KeyError('sin estilo')
        est = estilos_inicio.ESTILOS[estilos_inicio.clave_guardada()]
        i = ('inicio', 'nuevo', 'estilos', 'editor', 'sfx').index(clave) if clave in ('inicio', 'nuevo', 'estilos', 'editor', 'sfx') else 1
        a = est.aurora
        return tuple(a[(i + k) % 3] for k in range(3))
    except Exception:
        return PALETAS_PAGINA.get(clave) or PALETAS_PAGINA['nuevo']


def _apagar(color, k=0.42):
    """El color mezclado hacia un gris frío: pierde saturación (el fondo no se tiñe de verde chillón, violeta, etc.)."""
    c = QColor(color)
    g = (120, 132, 150)
    return QColorReal(int(c.red() * (1 - k) + g[0] * k), int(c.green() * (1 - k) + g[1] * k), int(c.blue() * (1 - k) + g[2] * k))


def _rgba(color, alfa):
    c = QColor(color)
    return QColorReal(c.red(), c.green(), c.blue(), max(0, min(255, int(alfa))))


class _Particula:
    __slots__ = ('x', 'y', 'vx', 'vy', 'r', 'fase', 'color', 'vida', 'grav', 'giro', 'forma')

    def __init__(self, x, y, vx, vy, r, color, vida=None, grav=0.0, forma='punto'):
        self.x, self.y, self.vx, self.vy, self.r = x, y, vx, vy, r
        self.fase = random.random() * math.tau
        self.color = color
        self.vida = vida            # None = eterna (ambiente); si no, segundos que le quedan
        self.grav = grav
        self.giro = random.uniform(-6, 6)
        self.forma = forma


# v5.5 «Aurora»: cada pagina tiene su bloque de luz (como el color que cambia de bloque en el video de referencia): al cambiar de
# pagina las manchas del fondo PASAN de un color al otro con un resorte lento (k=26, c=7: unos 0,9 s, con un leve rebote).
PALETAS_PAGINA = {
    'inicio': ('#7C3AED', '#0891B2', '#DB2777'),
    'nuevo': ('#16A34A', '#0D9488', '#65A30D'),
    'estilos': ('#16A34A', '#0D9488', '#65A30D'),
    'editor': ('#7C3AED', '#DB2777', '#4F46E5'),
    'sfx': ('#F5832F', '#DB2777', '#EAB308'),
}


_GRANO = [None]


def _hacer_grano(lado=192):
    """Una baldosa de ruido blanco/negro casi transparente (determinista: la misma en cada arranque)."""
    import random as _r
    azar = _r.Random(5)
    img = QImage(lado, lado, QImage.Format.Format_ARGB32)
    for y in range(lado):
        for x in range(lado):
            v = azar.randint(0, 255)
            img.setPixel(x, y, (azar.randint(5, 16) << 24) | (v << 16) | (v << 8) | v)
    return QPixmap.fromImage(img)


def _rgb(hexa):
    h = str(hexa).lstrip('#')
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


class FondoVivo(QWidget):
    """El escenario animado. Sus hijos (las pantallas) se pintan encima."""
    FPS_LLENO = 30            # (5.3) antes 60: cada cuadro repinta TODAS las tarjetas que hay encima; a 30 se ve igual de fluido
    FPS_TENUE = 15

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._t0 = time.perf_counter()
        self._t = 0.0
        self._ultimo = self._t0
        self._intensidad = 1.0
        self._objetivo = 1.0
        self._ambiente = []
        self._efimeras = []
        import mograf_ui
        self._formas = mograf_ui.sembrar_formas()      # v5.3: formas de Motion Graphics que derivan detras de todo
        self._ondas = []          # [(x, y, t_inicio, color)]
        self._rejilla = None
        self._mancha = None
        self._aurora = None       # (5.3) la aurora se mueve lentisimo: se redibuja ~5 veces por segundo, no en cada cuadro
        self._aurora_t = -1.0
        self._aurora_k = -1.0
        self._vineta = None       # (5.3) la viñeta es fija: una sola imagen por tamaño
        self._reducido = reducir_animaciones()
        self._cubierto = False
        # los 3 colores secundarios de las auroras, como resortes (r, g, b) hacia la paleta de la pagina actual
        self._col_resortes = [[ui.Resorte(v, 26.0, 7.0) for v in _rgb(c)] for c in _paleta_de('inicio')]
        self._col_mueve = False
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)
        self._fps = self.FPS_LLENO
        self._reloj.start(int(1000 / self._fps))
        ritmo_ui.ritmo.poner(self._reloj, int(1000 / self._fps))     # v5.3: si la interfaz va justa, el regulador alarga el intervalo
        # las tarjetas opacas de la pantalla actual NO se repintan con el fondo
        # (el editor con cientos de fichas no tiene por que redibujarse 20 veces
        # por segundo): proveedor de rectangulos en coordenadas de este widget
        self.proveedor_excluidas = None
        self._excluidas = None
        self._excluidas_t = -1.0
        self._tarjetas_t = 0.0
        ui.Tarjeta.fondo = self
        self._sembrar()

    # -- control ------------------------------------------------------------
    def poner_intensidad(self, valor):
        """1.0 = Inicio (todo el espectaculo); ~0.35 = las demas pantallas."""
        self._objetivo = max(0.0, min(1.0, float(valor)))
        fps = self.FPS_LLENO if self._objetivo >= 0.7 else self.FPS_TENUE
        if self._reducido:
            fps = 10
        if fps != self._fps:
            self._fps = fps
            ritmo_ui.ritmo.poner(self._reloj, int(1000 / fps))

    def poner_pagina(self, clave):
        """El bloque de luz de esa pagina: las manchas del fondo van hacia su paleta con resorte."""
        paleta = _paleta_de(clave)
        for resortes, c in zip(self._col_resortes, paleta):
            for rs, v in zip(resortes, _rgb(c)):
                if self._reducido:
                    rs.poner(v)
                else:
                    rs.objetivo = v
        self._col_mueve = True
        self._aurora_t = -1.0

    def _color_resorte(self, i):
        r, g, b = (max(0.0, min(1.0, rs.x)) for rs in self._col_resortes[i])
        return '#%02X%02X%02X' % (round(r * 255), round(g * 255), round(b * 255))

    def poner_cubierto(self, si):
        """v5.4: en Inicio la escena 3D (opaca y a todo el tamaño) tapa el fondo entero; se comprobó pixel a pixel que la
        imagen es identica con o sin pintarlo. Con su propio reloj el fondo repintaba toda la pila (escena 3D incluida)
        unas 30 veces por segundo para nada, ademas de las 30 de la escena: el hilo de la interfaz iba al doble."""
        si = bool(si)
        if si == self._cubierto:
            return
        self._cubierto = si
        if si:
            self._reloj.stop()
            self._efimeras = []
            self._ondas = []
        else:
            if self.isVisible() and not self._reloj.isActive():
                self._ultimo = time.perf_counter()
                self._reloj.start()
            self.update()

    def explosion(self, x, y, n=90, colores=None):
        """Confeti desde (x, y) en coordenadas de este widget (el exito)."""
        if self._reducido or self._cubierto:
            return
        colores = colores or [ui.ACCENT_CLARO, ui.ROL_PRINCIPAL, ui.ROL_COMPLEMENTO, ui.VERDE, '#FFFFFF', '#22D3EE']
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            vel = random.uniform(180, 620)
            self._efimeras.append(_Particula(
                x, y, math.cos(ang) * vel, math.sin(ang) * vel - random.uniform(80, 260),
                random.uniform(2.2, 5.5), random.choice(colores), vida=random.uniform(1.1, 2.2),
                grav=620.0, forma=random.choice(('punto', 'tira', 'tira'))))

    def onda(self, x, y, color=None):
        """Onda expansiva desde (x, y) (un clic con peso: GO)."""
        if self._reducido or self._cubierto:
            return
        self._ondas.append((x, y, self._t, color or ui.ACCENT_CLARO))

    # -- motor --------------------------------------------------------------
    def _sembrar(self):
        random.seed(7)
        self._ambiente = []
        paleta = [ui.ACCENT_CLARO, '#8B5CF6', '#22D3EE', '#FFFFFF', ui.ROL_PRINCIPAL]
        for _ in range(110):
            self._ambiente.append(_Particula(random.random(), random.random(), random.uniform(-0.004, 0.004),
                                             -random.uniform(0.006, 0.022), random.uniform(0.6, 2.1),
                                             random.choice(paleta)))
        random.seed()

    def showEvent(self, e):
        if not self._reloj.isActive() and not self._cubierto:
            self._ultimo = time.perf_counter()
            self._reloj.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)

    def resizeEvent(self, e):
        self._rejilla = None
        self._aurora = None
        self._vineta = None
        super().resizeEvent(e)

    def _tic(self):
        ahora = time.perf_counter()
        dt = min(0.1, ahora - self._ultimo)
        self._ultimo = ahora
        self._t += dt
        if self._t - self._tarjetas_t > 0.5:
            self._tarjetas_t = self._t
            self._refrescar_tarjetas()
        self._intensidad += (self._objetivo - self._intensidad) * min(1.0, dt * 3.0)
        if self._col_mueve:
            mueve = False
            for resortes in self._col_resortes:
                for rs in resortes:
                    mueve = rs.paso(dt) or mueve
            self._col_mueve = mueve
            self._aurora_t = -1.0            # los colores cambian: la imagen de las auroras se rehace en este cuadro
        for p in self._ambiente:
            p.x = (p.x + p.vx * dt) % 1.0
            p.y = (p.y + p.vy * dt) % 1.0
        vivas = []
        for p in self._efimeras:
            p.vida -= dt
            if p.vida <= 0:
                continue
            p.vx *= (1 - 1.2 * dt)
            p.vy += p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            vivas.append(p)
        self._efimeras = vivas
        self._ondas = [o for o in self._ondas if self._t - o[2] < 1.1]
        if self._objetivo < 0.7 and self.proveedor_excluidas is not None and not self._efimeras and not self._ondas:
            if self._t - self._excluidas_t > 0.5 or self._excluidas is None:
                self._excluidas_t = self._t
                try:
                    region = QRegion(self.rect())
                    for r in self.proveedor_excluidas() or []:
                        region -= QRegion(r)
                    self._excluidas = region
                except Exception:
                    self._excluidas = None
            if self._excluidas is not None:
                self.update(self._excluidas)
                return
        self._excluidas = None
        self.update()

    # -- dibujo -------------------------------------------------------------
    def _mapa_auroras(self, w, h):
        """Las auroras en una imagen de 1/8 (el escalado las difumina)."""
        iw, ih = max(8, w // 8), max(8, h // 8)
        img = QImage(iw, ih, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        t = self._t
        k = self._intensidad
        # v5.7 (pedido: «que no sea naco, que se vea profesional»): la luz de fondo es una sugerencia, no un baño de color. Tres manchas
        # amplias y muy tenues, con los colores mezclados hacia un gris frío (desaturados) para que el fondo siga siendo casi neutro.
        manchas = [
            (0.18 + 0.10 * math.sin(t * 0.13), 0.12 + 0.08 * math.cos(t * 0.11), 0.72, _apagar(ui.ACCENT), 40),
            (0.88 + 0.06 * math.cos(t * 0.09), 0.20 + 0.08 * math.sin(t * 0.15), 0.55, _apagar(self._color_resorte(0)), 24),
            (0.62 + 0.12 * math.sin(t * 0.07 + 1.3), 0.98 + 0.04 * math.cos(t * 0.12), 0.70, _apagar(self._color_resorte(1)), 20),
        ]
        p.setPen(Qt.PenStyle.NoPen)
        for cx, cy, r, color, alfa in manchas:
            g = QRadialGradient(QPointF(cx * iw, cy * ih), r * max(iw, ih))
            g.setColorAt(0.0, _rgba(color, alfa * k))
            g.setColorAt(1.0, _rgba(color, 0))
            p.setBrush(g)
            p.drawRect(0, 0, iw, ih)
        p.end()
        return img

    def muestra_aurora(self, rect):
        """Para el Liquid Glass de las tarjetas: (imagen de la aurora en baja resolucion, parte que queda bajo `rect`)."""
        w, h = max(1, self.width()), max(1, self.height())
        if self._aurora is None:
            self._aurora, self._aurora_t, self._aurora_k = self._mapa_auroras(w, h), self._t, self._intensidad
        f = self._aurora.width() / float(w)
        return self._aurora, QRectF(rect.x() * f, rect.y() * f, rect.width() * f, rect.height() * f)

    def _refrescar_tarjetas(self):
        for t in list(ui.Tarjeta._vivas):
            try:
                if t.isVisible() and t.graphicsEffect() is None:
                    t.update()
            except RuntimeError:
                pass

    def _hacer_rejilla(self, w, h):
        pm = QPixmap(w + 64, h + 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_rgba('#8FB4FF', 26))
        paso = 32
        for y in range(0, h + 64, paso):
            for x in range(0, w + 64, paso):
                p.drawEllipse(QPointF(x, y), 1.0, 1.0)
        p.end()
        return pm

    def paintEvent(self, _e):
        if self._cubierto:
            return
        w, h = self.width(), self.height()
        zona = _e.rect().adjusted(-4, -4, 4, 4)       # (5.3) solo se dibuja lo que de verdad se repinta
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(ui.BG_COLOR))
        k = self._intensidad
        if k > 0.01:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            if (self._aurora is None or self._t - self._aurora_t > 0.2 or abs(k - self._aurora_k) > 0.02):
                self._aurora, self._aurora_t, self._aurora_k = self._mapa_auroras(w, h), self._t, k
            p.drawImage(QRectF(0, 0, w, h), self._aurora)
            if self._rejilla is None:
                self._rejilla = self._hacer_rejilla(w, h)
            dx = (self._t * 6.0) % 32
            dy = (self._t * 3.5) % 32
            p.setOpacity(0.05 + 0.09 * k)
            p.drawPixmap(QPointF(-dx, -dy), self._rejilla)
            p.setOpacity(1.0)
            # v5.5: sin las formas geometricas a la deriva (hexagonos, cruces, triangulos): el fondo queda en luz, grano y puntos
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        if k > 0.01:
            for part in self._ambiente:
                px, py = part.x * w, part.y * h
                if not zona.contains(int(px), int(py)):
                    continue
                tw = 0.5 + 0.5 * math.sin(self._t * 1.7 + part.fase)
                p.setBrush(_rgba(part.color, (14 + 70 * tw) * k))
                p.drawEllipse(QPointF(px, py), part.r, part.r)
        for (x, y, t_ini, color) in self._ondas:
            f = (self._t - t_ini) / 1.1
            radio = 30 + f * max(w, h) * 0.45
            pen = QPen(_rgba(color, 180 * (1 - f) ** 2), 2.5 * (1 - f) + 0.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x, y), radio, radio)
        p.setPen(Qt.PenStyle.NoPen)
        for part in self._efimeras:
            alfa = 255 * min(1.0, part.vida / 0.6)
            p.setBrush(_rgba(part.color, alfa))
            if part.forma == 'tira':
                p.save()
                p.translate(part.x, part.y)
                p.rotate((self._t * 90 * part.giro) % 360)
                p.drawRoundedRect(QRectF(-part.r * 1.6, -part.r * 0.5, part.r * 3.2, part.r), 1.2, 1.2)
                p.restore()
            else:
                p.drawEllipse(QPointF(part.x, part.y), part.r, part.r)
        # viñeta: el centro respira, los bordes se apagan
        if self._vineta is None or self._vineta.size() != self.size():
            pm = QPixmap(self.size())
            pm.fill(Qt.GlobalColor.transparent)
            pv = QPainter(pm)
            vin = QRadialGradient(QPointF(w / 2, h * 0.45), max(w, h) * 0.75)
            vin.setColorAt(0.55, _rgba(ui.BG_COLOR, 0))
            vin.setColorAt(1.0, _rgba(ui.BG_COLOR, 170))
            pv.setPen(Qt.PenStyle.NoPen)
            pv.setBrush(vin)
            pv.drawRect(pm.rect())
            pv.end()
            self._vineta = pm
        p.drawPixmap(0, 0, self._vineta)
        # v5.5: el grano fino de las referencias (una sola baldosa de ruido, repetida: casi no cuesta)
        if _GRANO[0] is None:
            _GRANO[0] = _hacer_grano()
        p.setOpacity(0.55)
        p.drawTiledPixmap(self.rect(), _GRANO[0])
        p.setOpacity(1.0)
        p.end()


class VistaRealAnimada(QWidget):
    """La vista previa REAL de un pack (fotogramas renderizados por Resolve,
    vistas_reales): reproduce la animacion de entrada de cada set, la
    sostiene y pasa al siguiente set con un fundido. Siempre en movimiento,
    como pidio el usuario; se detiene sola cuando no se ve."""
    CUADRO_MS = 110
    SOSTENER_MS = 1700

    def __init__(self, sets, recortes=None, padre=None, alto=122):
        super().__init__(padre)
        self.setFixedHeight(alto)
        self.setMinimumWidth(120)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._sets = []
        for numero in sorted(sets):
            rutas = sets[numero]
            caja = (recortes or {}).get(numero)
            cuadros = []
            for r in rutas:
                img = QImage(str(r))
                if img.isNull():
                    continue
                if caja:
                    x, y, w, h = caja
                    img = img.copy(int(x * img.width()), int(y * img.height()),
                                   max(1, int(w * img.width())), max(1, int(h * img.height())))
                cuadros.append(img)
            if cuadros:
                self._sets.append((numero, cuadros))
        self._k = 0
        self._cuadro = 0
        self._ms = 0
        self._fundido = 0.0
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)
        self._reloj.start(40)
        import random as _r
        self._k = _r.randrange(len(self._sets)) if self._sets else 0

    def vacia(self):
        return not self._sets

    def showEvent(self, e):
        self._reloj.start(40)
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)

    def _tic(self):
        if not self._sets:
            return
        self._ms += 40
        _, cuadros = self._sets[self._k]
        duracion = len(cuadros) * self.CUADRO_MS + self.SOSTENER_MS
        self._cuadro = min(len(cuadros) - 1, self._ms // self.CUADRO_MS)
        if self._ms >= duracion:
            self._ms = 0
            self._k = (self._k + 1) % len(self._sets)
            self._fundido = 1.0
        self._fundido = max(0.0, self._fundido - 0.12)
        if self.isVisible():
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColorReal(5, 8, 15))
        p.drawRoundedRect(r, 8, 8)
        if self._sets:
            numero, cuadros = self._sets[self._k]
            img = cuadros[self._cuadro]
            esc = min(r.width() / max(1, img.width()), r.height() / max(1, img.height()))
            w, h = img.width() * esc, img.height() * esc
            p.setOpacity(1.0 - self._fundido)
            p.drawImage(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), img)
            p.setOpacity(1.0)
            from qt_kit import fuente
            from i18n import tr
            p.setFont(fuente(9, peso='negrita'))
            texto = tr('REAL · set {n}', n=numero)
            ancho = p.fontMetrics().horizontalAdvance(texto) + 14
            p.setBrush(_rgba(ui.ACCENT, 210))
            p.drawRoundedRect(QRectF(r.left() + 6, r.top() + 6, ancho, 17), 8.5, 8.5)
            p.setPen(QColorReal(255, 255, 255))
            p.drawText(QRectF(r.left() + 6, r.top() + 6, ancho, 17), int(Qt.AlignmentFlag.AlignCenter), texto)
        p.end()


def entrada_escalonada(widgets, retardo=45, duracion=320, subida=14):
    """Las tarjetas entran una tras otra: fundido + subida corta (OutCubic).
    Las tarjetas son QFrame opacos: el efecto se quita al terminar."""
    if reducir_animaciones():
        return
    for k, w in enumerate(widgets):
        if w is None or not w.isVisible():
            continue
        efecto = QGraphicsOpacityEffect(w)
        efecto.setOpacity(0.0)
        w.setGraphicsEffect(efecto)
        anim = QVariantAnimation(w)
        anim.setDuration(duracion)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def paso(v, w=w, efecto=efecto):
            if ui.vivo(efecto):
                efecto.setOpacity(float(v))

        anim.valueChanged.connect(paso)
        anim.finished.connect(lambda w=w: w.setGraphicsEffect(None) if ui.vivo(w) else None)
        QTimer.singleShot(k * retardo, anim.start)
        w._anim_entrada = anim


def tarjetas_de(pagina, maximo=10):
    """Las tarjetas visibles de primer nivel de una pantalla (para animarlas)."""
    salida = []
    for w in pagina.findChildren(QFrame):
        if w.objectName() in ('tarjeta', 'tarjetaEstado', 'mosaico') and w.isVisible():
            padre = w.parentWidget()
            # solo las de primer nivel (una tarjeta dentro de otra entra con su madre)
            anidada = False
            while padre is not None and padre is not pagina:
                if isinstance(padre, QFrame) and padre.objectName() in ('tarjeta', 'tarjetaEstado', 'mosaico'):
                    anidada = True
                    break
                padre = padre.parentWidget()
            if not anidada:
                salida.append(w)
        if len(salida) >= maximo:
            break
    salida.sort(key=lambda w: (w.mapTo(pagina, w.rect().topLeft()).y() // 40, w.mapTo(pagina, w.rect().topLeft()).x()))
    return salida
