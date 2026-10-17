# CineCaptions · By Cinema Productions
# 1_codigo/estilos_slider.py — el carrusel horizontal de «Pack de estilos»: tarjetas verticales sobre fotos de video con los captions de Resolve encima.
"""
estilos_slider.py  (v5.3.6)
---------------------------
La pantalla Proyecto muestra los packs como un slider horizontal (como las galerías de referencia): la tarjeta del centro grande y con sus
captions en movimiento, las de los lados más chicas y apagadas, y todo se desliza con un resorte (arrastrar, rueda lateral, ← →, clic en la vecina).

Cada tarjeta es VERTICAL (9:16) y lleva de fondo una foto de video real (2_recursos/fondos_estilos/fondo_NN.jpg) para que se vea cómo queda un
caption de verdad sobre un video:
  · con la vista REAL del pack (vistas_reales: fotogramas que renderizó Resolve sobre negro) se compone en modo «Screen» sobre la foto, a su
    tiempo real de entrada, y se repite en bucle por cada variante;
  · sin vista real todavía, las líneas aproximadas del pack (lineas_de_vista) se dibujan sobre la foto con la misma animación de entrada.

Todo se pinta en UN solo widget (sin un widget por tarjeta ni efectos de Qt): un temporizador de 16 ms solo mientras algo se mueve y de 33 ms
mientras el centro anima sus captions; se apaga solo cuando el widget no se ve.

    CarruselPacks.poner_cartas([Carta, …], elegido)   las tarjetas y cuál está en uso
    CarruselPacks.elegida(valor)                       señal: clic en la tarjeta del centro (usar este estilo)
    CarruselPacks.centrada(carta)                      señal: otra tarjeta llegó al centro (el panel de abajo se actualiza)
    CarruselPacks.anadir()                             señal: clic en «Añadir plantilla»
"""
import math
import time
import zlib
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient, QTransform)
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

import qt_kit as ui
from i18n import tr

CUADROS_S = (0.08, 0.2, 0.36, 0.6, 1.0)        # cuándo llega cada fotograma renderizado (vistas_reales.CUADROS)
SOSTENER_S = 1.9                                # lo que se queda quieto el caption terminado
SALIDA_S = 0.30                                 # fundido antes de pasar a la siguiente variante
ASPECTO = 9 / 16

_FOTOS = None


def _carpeta_fotos():
    try:
        import instalador_scripts
        return Path(instalador_scripts.BASE_RECURSOS) / 'fondos_estilos'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'fondos_estilos'


def fotos():
    """Las fotos de fondo (QImage), en orden. Se leen una sola vez."""
    global _FOTOS
    if _FOTOS is None:
        lista = []
        try:
            for ruta in sorted(_carpeta_fotos().glob('fondo_*.jpg')):
                img = QImage(str(ruta))
                if not img.isNull():
                    lista.append(img)
        except Exception:
            pass
        _FOTOS = lista
    return _FOTOS


def _color_medio(img):
    c = QColor(img.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).pixelColor(0, 0))
    return c


class Carta:
    """Lo que el carrusel sabe de un estilo (el script principal lo arma desde un Pack)."""

    def __init__(self, valor, titulo, tipo='pack', lineas=None, real=None, formatos='', meta='', estado=None, color_estado=None,
                 nota='', aviso=None, acciones=None, menu=None, estructura=None, extra=None, detalle='', pack=None, video=None, poster=None,
                 video_sin=None, poster_sin=None):
        self.valor = valor
        self.titulo = titulo
        self.tipo = tipo                      # 'pack' | 'anadir'
        self.lineas = list(lineas or [])
        self.real = real                      # (sets {numero: [rutas]}, recortes) o None
        self.formatos = formatos or ''
        self.meta = meta or ''
        self.estado = estado
        self.color_estado = color_estado
        self.nota = nota or ''
        self.aviso = aviso
        self.acciones = list(acciones or [])  # [(icono, glifo, ayuda, fn)]
        self.menu = list(menu or [])          # [(texto, fn)]
        self.estructura = estructura
        self.extra = extra                    # fn() -> QWidget con lo propio de esa tarjeta (p. ej. las combinaciones de básicos)
        self.detalle = detalle
        self.pack = pack
        self.video = video                    # v5.4.5: mp4 con los captions REALES de Resolve (vistas_slider); se reproduce cuando la tarjeta está al centro
        self.poster = poster                  # el fotograma que se ve cuando no está al centro
        self.video_sin = video_sin            # v5.5.9: el mismo ejemplo SOLO con captions (sin la Edición PRO): la píldora de la tarjeta
        self.poster_sin = poster_sin
        self._poster_sin_img = None
        self.foto = 0
        self._marco = None
        self._cuadros = None
        self._poster_img = None

    def imagen_poster(self, sin=False):
        if sin and self.poster_sin:
            if self._poster_sin_img is None:
                img = QImage(str(self.poster_sin))
                self._poster_sin_img = img if not img.isNull() else False
            if self._poster_sin_img:
                return self._poster_sin_img
        if self._poster_img is None and self.poster:
            img = QImage(str(self.poster))
            self._poster_img = img if not img.isNull() else False
        return self._poster_img or None

    def cuadros_reales(self):
        """[[QImage, …] por variante] de la vista real (cargados una vez)."""
        if self._cuadros is None:
            sets = []
            try:
                if self.real and self.real[0]:
                    for numero in sorted(self.real[0]):
                        imgs = [QImage(str(r)) for r in self.real[0][numero]]
                        imgs = [i for i in imgs if not i.isNull()]
                        if imgs:
                            sets.append(imgs)
            except Exception:
                sets = []
            self._cuadros = sets
        return self._cuadros

    def marco(self):
        """El MarcoVista que sabe dibujar las líneas aproximadas (nunca se muestra: solo pinta)."""
        if self._marco is None:
            m = ui.MarcoVista(alto_min=10, aprox=False)
            m.poner(self.lineas)
            self._marco = m
        return self._marco


class CarruselPacks(QWidget):
    elegida = Signal(str)
    centrada = Signal(object)
    anadir = Signal()
    vista_pro = Signal(bool)                      # v5.5.9: la píldora de la tarjeta: True = el ejemplo con la Edición PRO, False = solo captions

    GIRO = 24.0                                   # grados de giro de las tarjetas vecinas
    PASO = 0.94                                   # separación de las tarjetas vecinas, en anchos de tarjeta
    ALTO_CONTROLES = 0                            # v5.5.10: sin flechas ni puntos debajo (lo pidió el usuario); se mueve arrastrando, con la rueda,
                                                  # con ← → o con un clic en la vecina

    def __init__(self, alto=600, padre=None, flexible=False):
        super().__init__(padre)
        self._cartas = []
        self._elegido = None
        self._pos = 0.0
        self._vel = 0.0
        self._obj = 0
        self._t0_centro = time.perf_counter()
        self._ultimo = time.perf_counter()
        self._arrastre = None
        self._hover = None                       # ('pildora', 'pro'|'sin') | ('carta', i)
        self._entrada_t0 = None
        self._entro = False
        self._rueda = 0
        self._ult_rueda = 0.0
        self._px = {}
        self._reprod = {}                        # valor de la carta -> vistas_slider.Reproductor (solo suena el de la tarjeta del centro)
        self._glow = QColor(ui.ACCENT)
        # v5.5.9 (el usuario: «más animaciones; cuando selecciono un tema, una mejor animación; una píldora para ver con o sin modo PRO»)
        self.modo_pro = True                     # qué ejemplo se ve en la tarjeta del centro
        self.al_mostrar = None                   # fn() al aparecer el slider (Proyecto: la píldora vuelve a lo que hará GO, aunque la PRO se cambiara en Inicio)
        self._pill_k = 1.0                       # la píldora, animada (1 = «Con PRO»)
        self._pill_geo = None                    # (toda, «Con PRO», «Solo captions») de la tarjeta del centro, para el clic
        self._cambio_t0 = None                   # fundido entre los dos ejemplos al cambiar la píldora
        self._img_previa = None
        self._sel_t0 = None                      # la animación de «elegir este tema»
        self._sel_valor = None
        self._tilt = [0.0, 0.0]                  # la del centro se inclina un poco hacia el ratón
        self._tilt_obj = [0.0, 0.0]
        self._motas = [((i * 0.6180339) % 1.0, (i * 0.3819660 + 0.13) % 1.0, 0.6 + (i % 5) * 0.35, 1.4 + (i % 4) * 0.9) for i in range(26)]
        # v5.5.10: con `flexible` el alto pedido es solo el preferido: el mínimo baja para que la página quepa en pantallas pequeñas
        self.setMinimumHeight(int(min(alto, 300)) if flexible else int(alto))
        self._alto_pref = int(alto)
        if flexible:                                  # Proyecto: ocupa todo el alto que sobra (las tarjetas se escalan con él)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setFixedHeight(int(alto))
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)

    # -- datos ----------------------------------------------------------------------------------------------------------
    def poner_cartas(self, cartas, elegido=None, centrar=None):
        """Cambia las tarjetas. Se queda en la que estaba al centro (o en `centrar`, o en la que está en uso)."""
        previa = self._cartas[int(self._obj)].valor if self._cartas and 0 <= self._obj < len(self._cartas) else None
        self._cartas = list(cartas)
        self._elegido = elegido
        fs = fotos()
        anterior = -1
        for carta in self._cartas:
            if not fs:
                carta.foto = 0
                continue
            i = zlib.crc32(str(carta.valor).encode('utf-8')) % len(fs)
            if i == anterior and len(fs) > 1:
                i = (i + 1) % len(fs)
            carta.foto = i
            anterior = i
        destino = centrar if centrar is not None else (previa if previa is not None else elegido)
        idx = next((k for k, c in enumerate(self._cartas) if c.valor == destino), 0)
        self._obj = idx
        if not self._entro:
            self._pos = float(idx) - 3.2                 # la primera vez las tarjetas entran deslizando desde la izquierda
            self._vel = 0.0
        else:
            self._pos = max(-0.5, min(len(self._cartas) - 0.5, self._pos))
        self._px.clear()
        self._t0_centro = time.perf_counter() + 0.1
        self._actualizar_glow()
        self._arrancar()
        self._emitir_centro()
        self._gestionar_video()
        self.update()

    def poner_elegida(self, valor):
        if valor != self._elegido:
            if self._entro and valor is not None and self.isVisible():
                self._sel_t0, self._sel_valor = time.perf_counter(), valor          # v5.5.9: pulso, anillo, brillo y destellos
                self._arrancar()
            self._elegido = valor
            self.update()

    def poner_vista_pro(self, pro, animar=True):
        """Qué ejemplo se ve: con la Edición PRO o solo con los captions (si la tarjeta trae los dos)."""
        pro = bool(pro)
        if pro == self.modo_pro:
            return
        c = self.carta_central()
        if animar and c is not None:
            r = self._reprod.get(c.valor)
            self._img_previa = (r.imagen() if r is not None else None) or c.imagen_poster(sin=not self.modo_pro)
            self._cambio_t0 = time.perf_counter()
        else:
            self._pill_k = 1.0 if pro else 0.0
        self.modo_pro = pro
        self._gestionar_video()
        self._arrancar()
        self.update()

    def _video_de(self, carta):
        return carta.video_sin if (not self.modo_pro and getattr(carta, 'video_sin', None)) else getattr(carta, 'video', None)

    def carta_central(self):
        return self._cartas[self._obj] if self._cartas and 0 <= self._obj < len(self._cartas) else None

    def ir_a_valor(self, valor):
        for k, c in enumerate(self._cartas):
            if c.valor == valor:
                self._ir_a(k)
                return

    # -- movimiento -----------------------------------------------------------------------------------------------------
    def _ir_a(self, k):
        if not self._cartas:
            return
        k = max(0, min(len(self._cartas) - 1, int(k)))
        if k != self._obj:
            self._obj = k
            self._t0_centro = time.perf_counter() + 0.22        # el caption arranca cuando la tarjeta ya casi llegó
            self._emitir_centro()
            self._gestionar_video()
        self._arrancar()

    def _emitir_centro(self):
        c = self.carta_central()
        if c is not None:
            self.centrada.emit(c)

    def _arrancar(self):
        if self.isVisible() and not self._reloj.isActive():
            self._ultimo = time.perf_counter()
            self._reloj.start(16)

    def showEvent(self, e):
        if callable(self.al_mostrar):
            try:
                self.al_mostrar()
            except Exception:
                pass
        if self._entrada_t0 is None:
            self._entrada_t0 = time.perf_counter()
        self._entro = True
        self._arrancar()
        self._gestionar_video()
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        self._gestionar_video()
        super().hideEvent(e)

    def _gestionar_video(self):
        """Solo la tarjeta del centro reproduce su video (desde el principio al llegar); las demás se paran. Con el slider oculto no suena ninguno."""
        centro = self.carta_central() if self.isVisible() else None
        for valor, r in self._reprod.items():
            if centro is None or valor != centro.valor:
                r.parar()
        ruta = self._video_de(centro) if centro is not None else None
        if ruta:
            r = self._reprod.get(centro.valor)
            if r is None or r.ruta != str(ruta):
                if r is not None:
                    r.parar()
                import vistas_slider
                r = self._reprod[centro.valor] = vistas_slider.Reproductor(ruta)
            r.arrancar()

    def _cuadro_video(self, carta, centro):
        """El cuadro del video si la tarjeta está al centro y ya suena; si no, su fotograma fijo (o None = se pinta con la foto y los captions de siempre)."""
        if centro:
            r = self._reprod.get(carta.valor)
            img = r.imagen() if r is not None else None
            if img is not None:
                return img
        return carta.imagen_poster(sin=not self.modo_pro)

    def _en_movimiento(self):
        ahora = time.perf_counter()
        animando = ((self._sel_t0 is not None and ahora - self._sel_t0 < 1.0) or (self._cambio_t0 is not None and ahora - self._cambio_t0 < 0.4)
                    or abs(self._pill_k - (1.0 if self.modo_pro else 0.0)) > 0.002
                    or abs(self._tilt[0] - self._tilt_obj[0]) + abs(self._tilt[1] - self._tilt_obj[1]) > 0.02)
        return animando or self._arrastre is not None or abs(self._obj - self._pos) > 0.0008 or abs(self._vel) > 0.004

    def _tic(self):
        if not self.isVisible():
            self._reloj.stop()
            return
        ahora = time.perf_counter()
        dt = min(0.05, max(0.001, ahora - self._ultimo))
        self._ultimo = ahora
        if self._arrastre is None:
            # resorte casi crítico: llega rápido y con un rebote mínimo
            a = 190.0 * (self._obj - self._pos) - 25.0 * self._vel
            self._vel += a * dt
            self._pos += self._vel * dt
            if abs(self._obj - self._pos) < 0.0008 and abs(self._vel) < 0.004:
                self._pos, self._vel = float(self._obj), 0.0
        k = min(1.0, dt * 14.0)
        self._pill_k += ((1.0 if self.modo_pro else 0.0) - self._pill_k) * k
        for i in (0, 1):
            self._tilt[i] += (self._tilt_obj[i] - self._tilt[i]) * min(1.0, dt * 8.0)
        self._actualizar_glow()
        self._reloj.setInterval(16 if self._en_movimiento() else 33)
        self.update()

    def _actualizar_glow(self):
        fs = fotos()
        if not fs or not self._cartas:
            return
        a = max(0, min(len(self._cartas) - 1, int(math.floor(self._pos))))
        b = max(0, min(len(self._cartas) - 1, a + 1))
        f = max(0.0, min(1.0, self._pos - a))
        ca = _color_medio(fs[self._cartas[a].foto % len(fs)])
        cb = _color_medio(fs[self._cartas[b].foto % len(fs)])
        self._glow = QColor(int(ca.red() + (cb.red() - ca.red()) * f), int(ca.green() + (cb.green() - ca.green()) * f),
                            int(ca.blue() + (cb.blue() - ca.blue()) * f))

    # -- geometría ------------------------------------------------------------------------------------------------------
    def sizeHint(self):
        return QSize(900, getattr(self, '_alto_pref', 540))

    def _medidas(self):
        # v5.4.22: crecen con la ventana; v5.5.9: más grandes (tope 1040). v5.5.10: también caben a lo ANCHO (la del centro y sus dos vecinas
        # enteras: 2,76 anchos de tarjeta) y el grupo se centra en el alto que sobra; antes en ventanas estrechas se pisaban y desbordaban.
        disponible = self.height() - self.ALTO_CONTROLES - 16.0
        por_ancho = max(0.0, self.width() - 32.0) / (0.88 + 2.0 * self.PASO) / ASPECTO
        h_carta = max(180.0, min(1040.0, disponible, por_ancho))
        arriba = 14.0 + max(0.0, (disponible - h_carta) / 2.0)
        return h_carta * ASPECTO, h_carta, self.width() / 2.0, arriba + h_carta / 2.0

    def _transformar(self, d, w, h, cx, cy):
        """(rect, escala, opacidad) de la tarjeta a la distancia `d` del centro (en tarjetas)."""
        ad = abs(d)
        esc = 1.0 - 0.12 * min(ad, 1.0) - 0.12 * max(0.0, min(ad - 1.0, 1.0)) - 0.05 * max(0.0, min(ad - 2.0, 1.0))
        despl = (self.PASO * min(ad, 1.0) + 0.50 * max(0.0, min(ad - 1.0, 1.0)) + 0.40 * max(0.0, ad - 2.0)) * w
        x = cx + math.copysign(despl, d)
        op = 1.0 - 0.30 * min(ad, 1.0) - 0.45 * max(0.0, min(ad - 1.0, 1.0)) - 0.25 * max(0.0, min(ad - 2.0, 1.0))
        wc, hc = w * esc, h * esc
        y = cy + 16.0 * min(ad, 1.6)
        return QRectF(x - wc / 2, y - hc / 2, wc, hc), esc, max(0.0, op)

    def _foto_px(self, idx, w, h):
        """La foto ya escalada a cubrir w×h (cache; se rehace si cambia el tamaño o la densidad de pantalla)."""
        fs = fotos()
        if not fs:
            return None
        dpr = self.devicePixelRatioF()
        clave = (idx % len(fs), int(w), int(h), round(dpr, 2))
        px = self._px.get(clave)
        if px is None:
            img = fs[idx % len(fs)]
            escala = max(w * dpr / img.width(), h * dpr / img.height())
            pw, ph = int(img.width() * escala + 1), int(img.height() * escala + 1)
            px = QPixmap.fromImage(img.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
            px.setDevicePixelRatio(dpr)
            if len(self._px) > 160:
                self._px.clear()
            self._px[clave] = px
        return px

    # -- pintado --------------------------------------------------------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h, cx, cy = self._medidas()
        n = len(self._cartas)
        if n == 0:
            p.setPen(QColor(ui.TEXT_MUTED))
            p.setFont(ui.fuente(14))
            p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), tr('Todavía no hay estilos'))
            p.end()
            return
        # el resplandor detrás de la tarjeta del centro: el color medio de su foto, que va cambiando al deslizar (una elipse que se apaga antes de los bordes)
        radio_g = w * 1.7
        p.save()
        p.translate(cx, cy + 20)
        p.scale(1.0, max(0.2, (self.height() / 2.0 - 4.0) / radio_g))
        g = QRadialGradient(QPointF(0, 0), radio_g)
        c0 = QColor(self._glow)
        c0.setAlpha(88)
        c1 = QColor(self._glow)
        c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(1.0, c1)
        p.fillRect(QRectF(-radio_g, -radio_g, radio_g * 2, radio_g * 2), QBrush(g))
        p.restore()
        self._pill_geo = None
        self._dibujar_motas(p)
        entrada = 1.0
        if self._entrada_t0 is not None:
            entrada = max(0.0, min(1.0, (time.perf_counter() - self._entrada_t0) / 0.55))
        orden = sorted((k for k in range(n) if abs(k - self._pos) <= 3.2), key=lambda k: -abs(k - self._pos))
        for k in orden:
            self._dibujar_carta(p, self._cartas[k], k - self._pos, w, h, cx, cy, entrada)
        p.end()

    def _dibujar_carta(self, p, carta, d, w, h, cx, cy, entrada):
        rect, esc, op = self._transformar(d, w, h, cx, cy)
        op *= entrada
        if op <= 0.01:
            return
        ad = abs(d)
        radio = 26.0 * esc
        sel = self._progreso_sel(carta)
        if sel is not None:                                                     # v5.5.9: al elegirla, un pulso (crece un poco y vuelve)
            pulso = 1.0 + 0.05 * math.sin(math.pi * min(1.0, sel / 0.45)) * (1.0 - sel)
            c0 = rect.center()
            rect = QRectF(c0.x() - rect.width() * pulso / 2, c0.y() - rect.height() * pulso / 2, rect.width() * pulso, rect.height() * pulso)
        p.save()
        p.setOpacity(op)
        if ad < 0.5 and (abs(self._tilt[0]) > 0.01 or abs(self._tilt[1]) > 0.01):
            f = 1.0 - ad * 2.0
            t = QTransform()
            t.translate(rect.center().x(), rect.center().y())
            t.rotate(self._tilt[0] * f, Qt.Axis.XAxis)
            t.rotate(self._tilt[1] * f, Qt.Axis.YAxis)
            t.translate(-rect.center().x(), -rect.center().y())
            p.setTransform(t, True)
        # un giro suave sobre el eje vertical (tipo coverflow): las tarjetas de los lados miran hacia la del centro
        giro = max(-1.0, min(1.0, d)) * self.GIRO
        if abs(giro) > 0.2:
            t = QTransform()
            t.translate(rect.center().x(), rect.center().y())
            t.rotate(giro, Qt.Axis.YAxis)
            t.translate(-rect.center().x(), -rect.center().y())
            p.setTransform(t, True)
        # sombra suave debajo (capas translúcidas; las lejanas no la llevan)
        if ad < 1.4:
            for i in range(3):
                s = QColor(0, 0, 0, int(34 * (1.0 - i / 3.0) * (1.0 - 0.5 * min(ad, 1.0))))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(s)
                p.drawRoundedRect(rect.adjusted(-i * 6.0, 8.0 + i * 5.0, i * 6.0, 12.0 + i * 8.0), radio + i * 4, radio + i * 4)
        if carta.tipo == 'anadir':
            camino = QPainterPath()
            camino.addRoundedRect(rect, radio, radio)
            self._dibujar_anadir(p, carta, rect, esc, camino, ad)
            p.restore()
            return
        if ad >= 0.5:
            # las tarjetas de los lados no cambian de contenido: se pintan una vez en un pixmap y aquí solo se estiran (mucho más barato)
            pm = self._pixmap_estatico(carta, w, h)
            p.drawPixmap(rect, pm, QRectF(pm.rect()))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(4, 8, 16, int(120 * min(ad, 1.0))))              # apagadas
            p.drawRoundedRect(rect, radio, radio)
        else:
            self._pintar_cuerpo(p, carta, rect, esc, d, True, w, h)
            if ad > 0.02:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(4, 8, 16, int(120 * min(ad, 1.0))))
                p.drawRoundedRect(rect, radio, radio)
        # borde: el de la que está en uso, resaltado
        if carta.valor == self._elegido:
            for i, a in enumerate((34, 60, 120)):
                col = QColor(ui.VERDE)
                col.setAlpha(a)
                p.setPen(QPen(col, (7 - i * 2.4) * esc))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radio, radio)
            p.setPen(QPen(QColor(ui.VERDE), 2.4 * esc))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radio, radio)
        else:
            p.setPen(QPen(QColor(255, 255, 255, 46 if ad < 0.5 else 24), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(0.6, 0.6, -0.6, -0.6), radio, radio)
        if sel is not None:
            self._dibujar_seleccion(p, rect, radio, sel)
        p.restore()

    def _pintar_cuerpo(self, p, carta, rect, esc, d, centro, w, h):
        """La foto (con paralaje), el sombreado, los captions y los textos de una tarjeta dentro de `rect` (w×h = su tamaño sin escalar)."""
        radio = 26.0 * esc
        camino = QPainterPath()
        camino.addRoundedRect(rect, radio, radio)
        p.save()
        p.setClipPath(camino)
        # v5.4.5: con video, el video (captions de Resolve ya puestos) ocupa la tarjeta; sin él, la foto de siempre con los captions encima
        fuente = self._cuadro_video(carta, centro) if (getattr(carta, 'video', None) or getattr(carta, 'poster', None)) else None
        # la foto, un poco más grande que la tarjeta y desplazada al revés que el deslizamiento (paralaje)
        px = self._foto_px(carta.foto, w * 1.14, h * 1.14) if fuente is None else None
        if fuente is not None:
            p.drawImage(rect, fuente)
            if centro and self._cambio_t0 is not None and self._img_previa is not None:
                q = (time.perf_counter() - self._cambio_t0) / 0.35
                if q < 1.0:
                    o = p.opacity()
                    p.setOpacity(o * (1.0 - q * q * (3.0 - 2.0 * q)))
                    p.drawImage(rect, self._img_previa)
                    p.setOpacity(o)
                else:
                    self._img_previa = None
        elif px is not None:
            pw, ph = px.width() / px.devicePixelRatio(), px.height() / px.devicePixelRatio()
            desp = max(-1.5, min(1.5, d)) * -0.05 * w * esc
            p.drawPixmap(QRectF(rect.center().x() - pw * esc / 2 + desp, rect.center().y() - ph * esc / 2, pw * esc, ph * esc), px, QRectF(px.rect()))
        else:
            p.fillRect(rect, QColor('#10192B'))
        # sombreado para que se lea el caption y el nombre
        v = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if fuente is None:
            v.setColorAt(0.0, QColor(0, 0, 0, 70))
            v.setColorAt(0.34, QColor(0, 0, 0, 0))
            v.setColorAt(0.60, QColor(0, 0, 0, 40))
            v.setColorAt(1.0, QColor(0, 0, 0, 205))
        else:                                          # con video los captions de Resolve se ven tal cual: solo se oscurece el pie para el nombre
            v.setColorAt(0.0, QColor(0, 0, 0, 36))
            v.setColorAt(0.12, QColor(0, 0, 0, 0))
            v.setColorAt(0.78, QColor(0, 0, 0, 0))
            v.setColorAt(1.0, QColor(0, 0, 0, 200))
        p.fillRect(rect, QBrush(v))
        if fuente is None:
            self._dibujar_captions(p, carta, rect, centro)
        self._dibujar_textos(p, carta, rect, esc, centro and abs(d) < 0.05)
        p.restore()

    def _pixmap_estatico(self, carta, w, h):
        """La tarjeta ya pintada (foto + captions finales + textos) a su tamaño completo; se rehace si cambia el tamaño, la densidad o si pasa a estar en uso."""
        dpr = self.devicePixelRatioF()
        clave = ('est', carta.valor, int(w), int(h), round(dpr, 2), carta.valor == self._elegido)
        pm = self._px.get(clave)
        if pm is None:
            pm = QPixmap(int(w * dpr) + 1, int(h * dpr) + 1)
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            self._pintar_cuerpo(q, carta, QRectF(0, 0, w, h), 1.0, 0.0, False, w, h)
            q.end()
            if len(self._px) > 160:
                self._px.clear()
            self._px[clave] = pm
        return pm

    def _dibujar_captions(self, p, carta, rect, centro):
        """Los captions del pack sobre la foto: vista REAL (Screen) si Resolve ya la renderizó, si no las líneas aproximadas."""
        t = time.perf_counter() - self._t0_centro if centro else None
        sets = carta.cuadros_reales()
        if sets:
            if centro and t is not None:
                if t < 0:
                    return
                dur = CUADROS_S[-1] + SOSTENER_S
                ciclo = dur + SALIDA_S
                k = int(t // ciclo) % len(sets)
                tl = t % ciclo
                imgs = sets[k]
                fin = max(0.0, min(1.0, 1.0 - (tl - dur) / SALIDA_S)) if tl > dur else 1.0
                j = -1
                for q, marca in enumerate(CUADROS_S[:len(imgs)]):
                    if tl >= marca - 0.02:
                        j = q
                if j < 0:
                    return
                if len(imgs) < len(CUADROS_S):
                    j = min(len(imgs) - 1, j)
                self._pintar_real(p, imgs[j], rect, fin)
            else:
                self._pintar_real(p, sets[0][-1], rect, 1.0)
            return
        if not carta.lineas:
            return
        marco = carta.marco()
        zona = QRectF(rect.left() + 2, rect.top() + rect.height() * 0.50, rect.width() - 4, rect.height() * 0.30)
        # un sombreado suave detrás de las líneas aproximadas (sobre una foto clara el texto del pack no se lee)
        banda = QLinearGradient(QPointF(0, zona.top() - zona.height() * 0.35), QPointF(0, zona.bottom() + zona.height() * 0.35))
        banda.setColorAt(0.0, QColor(0, 0, 0, 0))
        banda.setColorAt(0.5, QColor(0, 0, 0, 125))
        banda.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(rect.left(), zona.top() - zona.height() * 0.35, rect.width(), zona.height() * 1.7), QBrush(banda))
        if centro and t is not None:
            if t < 0:
                return
            ciclo = 3.4
            tl = t % ciclo
            marco.animar(tl, salida=max(0.0, min(1.0, (tl - (ciclo - 0.4)) / 0.3)))
        else:
            marco.animar(None)
        marco._pintar_contenido(p, zona)

    @staticmethod
    def _pintar_real(p, img, rect, alfa):
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        p.setOpacity(p.opacity() * alfa)
        p.drawImage(rect, img)
        p.restore()

    def _dibujar_textos(self, p, carta, rect, esc, centro=False):
        pad = 16.0 * esc
        # (v5.5.9: sin la «V» del formato arriba: el usuario la quitó) · la píldora «Con PRO / Solo captions» en la del centro
        # v5.5.10 (pedido: «quita el título y el subtítulo de la tarjeta: abajo ya dice el tema; solo las píldoras, más abajo»): la píldora va
        # al pie, centrada, y la tarjeta no lleva textos (arriba solo «✓ En uso» si es el tema elegido)
        if centro and getattr(carta, 'video_sin', None) and getattr(carta, 'video', None):
            self._dibujar_pildora(p, rect, esc, rect.bottom() - pad)
        if carta.valor == self._elegido:
            f = ui.fuente(11.5 * esc, peso='negrita')
            p.setFont(f)
            fm = QFontMetricsF(f)
            texto = '✓ ' + tr('En uso')
            tw = fm.horizontalAdvance(texto) + 18 * esc
            pill = QRectF(rect.right() - pad - tw, rect.top() + pad, tw, 22 * esc)
            sel = self._progreso_sel(carta)
            if sel is not None:                                                 # «✓ En uso» salta (con un pequeño rebote)
                u = min(1.0, sel / 0.5)
                s = 1.0 + 2.70158 * (u - 1.0) ** 3 + 1.70158 * (u - 1.0) ** 2
                c0 = pill.center()
                pill = QRectF(c0.x() - pill.width() * s / 2, c0.y() - pill.height() * s / 2, pill.width() * s, pill.height() * s)
                p.setFont(ui.fuente(max(1.0, 11.5 * esc * s), peso='negrita'))
            p.setPen(Qt.PenStyle.NoPen)
            col = QColor(ui.VERDE)
            p.setBrush(col)
            p.drawRoundedRect(pill, 11 * esc, 11 * esc)
            p.setPen(QColor('#06251A'))
            p.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), texto)

    def _dibujar_anadir(self, p, carta, rect, esc, camino, ad):
        fondo = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fondo.setColorAt(0.0, QColor('#101B31'))
        fondo.setColorAt(1.0, QColor('#0A1120'))
        p.fillPath(camino, QBrush(fondo))
        pen = QPen(QColor(ui.ACCENT_CLARO if self._hover == ('carta', self._cartas.index(carta)) else '#34507F'), 1.8 * esc)
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 26 * esc, 26 * esc)
        c = rect.center()
        r = 30 * esc
        p.setPen(Qt.PenStyle.NoPen)
        col = QColor(ui.VERDE)
        col.setAlpha(34)
        p.setBrush(col)
        p.drawEllipse(QPointF(c.x(), c.y() - 26 * esc), r, r)
        p.setPen(QPen(QColor(ui.VERDE), 3.2 * esc, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() - 11 * esc, c.y() - 26 * esc), QPointF(c.x() + 11 * esc, c.y() - 26 * esc))
        p.drawLine(QPointF(c.x(), c.y() - 37 * esc), QPointF(c.x(), c.y() - 15 * esc))
        p.setPen(QColor(255, 255, 255, 235))
        # v5.5.10: el título se achica hasta caber en la tarjeta (en pantallas pequeñas se salía por los lados)
        titulo, tam = tr('Añadir plantilla (.drb)'), 16 * esc
        p.setFont(ui.fuente(tam, peso='negrita'))
        while tam > 8 and p.fontMetrics().horizontalAdvance(titulo) > rect.width() - 28:
            tam -= 0.5
            p.setFont(ui.fuente(tam, peso='negrita'))
        p.drawText(QRectF(rect.left() + 14, c.y() + 18 * esc, rect.width() - 28, 26 * esc), int(Qt.AlignmentFlag.AlignCenter), titulo)
        p.setPen(QColor(ui.TEXT_MUTED))
        p.setFont(ui.fuente(min(12 * esc, tam * 0.78)))
        p.drawText(QRectF(rect.left() + 22, c.y() + 48 * esc, rect.width() - 44, 70 * esc),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop) | int(Qt.TextFlag.TextWordWrap), tr('En Resolve: clic derecho sobre el bin > Exportar bandeja…'))

    # -- elegir (la animación) y la píldora ------------------------------------------------------------------------------
    def _progreso_sel(self, carta):
        """0→1 durante la animación de «elegir este tema» de esa tarjeta; None si no está animando."""
        if self._sel_t0 is None or carta.valor != self._sel_valor:
            return None
        q = (time.perf_counter() - self._sel_t0) / 0.95
        return q if 0.0 <= q < 1.0 else None

    def _dibujar_seleccion(self, p, rect, radio, q):
        """v5.5.9, al elegir un tema: dos anillos verdes que se abren, un brillo que cruza la tarjeta y destellos que salen de los bordes."""
        e = 1.0 - (1.0 - q) ** 3
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        for retraso, grosor in ((0.0, 3.0), (0.14, 2.0)):
            u = max(0.0, min(1.0, (q - retraso) / (1.0 - retraso)))
            if u <= 0.0:
                continue
            eu = 1.0 - (1.0 - u) ** 3
            col = QColor(ui.VERDE)
            col.setAlpha(int(210 * (1.0 - u)))
            p.setPen(QPen(col, grosor))
            m = 6.0 + 44.0 * eu
            p.drawRoundedRect(rect.adjusted(-m, -m, m, m), radio + m * 0.6, radio + m * 0.6)
        if 0.04 < q < 0.62:                                                     # el brillo en diagonal
            u = (q - 0.04) / 0.58
            camino = QPainterPath()
            camino.addRoundedRect(rect, radio, radio)
            p.setClipPath(camino)
            x = rect.left() - rect.width() * 0.6 + rect.width() * 2.2 * u
            g = QLinearGradient(QPointF(x - rect.width() * 0.25, rect.top()), QPointF(x + rect.width() * 0.25, rect.bottom()))
            g.setColorAt(0.0, QColor(255, 255, 255, 0))
            g.setColorAt(0.5, QColor(255, 255, 255, int(90 * math.sin(math.pi * u))))
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(rect, QBrush(g))
            p.setClipping(False)
        c0 = rect.center()
        for i in range(12):                                                    # destellos de cuatro puntas
            a = i / 12.0 * math.tau + 0.3
            rx, ry = rect.width() / 2.0, rect.height() / 2.0
            d = 1.0 + 0.18 * e + 0.05 * (i % 3)
            x = c0.x() + math.cos(a) * rx * d
            y = c0.y() + math.sin(a) * ry * d
            s = (5.0 + 3.0 * (i % 2)) * math.sin(math.pi * min(1.0, q * 1.25))
            if s <= 0.2:
                continue
            col = QColor('#FFFFFF' if i % 3 else ui.VERDE)
            col.setAlpha(int(230 * (1.0 - q)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            estrella = QPainterPath()
            estrella.moveTo(x, y - s)
            estrella.quadTo(x, y, x + s, y)
            estrella.quadTo(x, y, x, y + s)
            estrella.quadTo(x, y, x - s, y)
            estrella.quadTo(x, y, x, y - s)
            p.drawPath(estrella)
        p.restore()

    def _dibujar_pildora(self, p, rect, esc, y_pie):
        """v5.5.9: «Solo captions | ✦ Con PRO» al pie de la tarjeta del centro: qué ejemplo se ve (quizá el usuario solo quiere captions).
        v5.5.10: «Con PRO» a la DERECHA, para que cuadre con los botones de abajo («En uso» | «Edición PRO»)."""
        pad = 14.0 * esc
        f = ui.fuente(12.0 * esc, peso='negrita')
        fm = QFontMetricsF(f)
        textos = ('✦ ' + tr('Con PRO'), tr('Solo captions'))
        anchos = [fm.horizontalAdvance(t) + 26.0 * esc for t in textos]
        alto = 32.0 * esc
        total = anchos[0] + anchos[1] + 6.0 * esc
        x0, y0 = max(rect.left() + pad * 0.5, rect.center().x() - total / 2.0), y_pie - alto          # v5.5.10: centrada al pie
        toda = QRectF(x0, y0, total, alto)
        r_sin = QRectF(x0 + 3.0 * esc, y0 + 3.0 * esc, anchos[1], alto - 6.0 * esc)
        r_pro = QRectF(r_sin.right(), y0 + 3.0 * esc, anchos[0], alto - 6.0 * esc)
        self._pill_geo = (toda, r_pro, r_sin)
        k = max(0.0, min(1.0, self._pill_k))
        p.save()
        p.setPen(QPen(QColor(255, 255, 255, 46), 1.0))
        p.setBrush(QColor(8, 12, 22, 175))
        p.drawRoundedRect(toda, alto / 2, alto / 2)
        sel = QRectF(r_sin.left() + (r_pro.left() - r_sin.left()) * k, r_pro.top(), r_sin.width() + (r_pro.width() - r_sin.width()) * k, r_pro.height())
        oro, azul = QColor('#E7C27D'), QColor(ui.ACCENT)
        mezcla = QColor(int(azul.red() + (oro.red() - azul.red()) * k), int(azul.green() + (oro.green() - azul.green()) * k),
                       int(azul.blue() + (oro.blue() - azul.blue()) * k))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mezcla)
        p.drawRoundedRect(sel, sel.height() / 2, sel.height() / 2)
        p.setFont(f)
        for r, texto, activo, clave in ((r_pro, textos[0], k > 0.5, 'pro'), (r_sin, textos[1], k <= 0.5, 'sin')):
            if activo:
                p.setPen(QColor('#1C1406') if clave == 'pro' else QColor('#FFFFFF'))
            else:
                p.setPen(QColor(255, 255, 255, 235 if self._hover == ('pildora', clave) else 160))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), texto)
        p.restore()

    def _dibujar_motas(self, p):
        """v5.5.9: motas de luz que suben despacio detrás de las tarjetas, del color del resplandor (más vida en Proyecto)."""
        t = time.perf_counter()
        W, H = float(self.width()), float(self.height())
        base = QColor(self._glow).lighter(170)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for sx, sy, vel, r in self._motas:
            y = H - ((sy * H + t * 9.0 * vel) % (H + 20.0)) + 10.0
            x = sx * W + math.sin(t * 0.35 * vel + sx * 9.0) * 14.0
            vida = math.sin(math.pi * max(0.0, min(1.0, y / H)))
            col = QColor(base)
            col.setAlpha(int(70 * vida))
            p.setBrush(col)
            p.drawEllipse(QPointF(x, y), r, r)
        p.restore()

    # -- ratón y teclado ------------------------------------------------------------------------------------------------
    def _en_carta(self, x, y):
        w, h, cx, cy = self._medidas()
        mejor = None
        for k in sorted(range(len(self._cartas)), key=lambda k: abs(k - self._pos)):
            rect, _esc, op = self._transformar(k - self._pos, w, h, cx, cy)
            if op > 0.05 and rect.contains(x, y):
                mejor = k
                break
        return mejor

    def _en_control(self, x, y):
        if self._pill_geo is not None and self._pill_geo[0].contains(x, y):
            return ('pildora', 'pro' if self._pill_geo[1].contains(x, y) else 'sin')
        return None

    def mouseMoveEvent(self, e):
        x, y = e.position().x(), e.position().y()
        if self._arrastre is not None:
            a = self._arrastre
            w = self._medidas()[0]
            if abs(x - a['x0']) > 6:
                a['mov'] = True
            crudo = a['pos0'] - (x - a['x0']) / (w * self.PASO)
            ultimo = max(0, len(self._cartas) - 1)
            if crudo < 0:                                 # v5.5.10: pasado el borde, resistencia elástica (como iOS) en vez de un tope seco
                crudo = -0.45 * (1.0 - 1.0 / (1.0 + 0.9 * -crudo))
            elif crudo > ultimo:
                crudo = ultimo + 0.45 * (1.0 - 1.0 / (1.0 + 0.9 * (crudo - ultimo)))
            self._pos = crudo
            ahora = time.perf_counter()
            a['muestras'].append((ahora, x))
            a['muestras'] = [m for m in a['muestras'] if ahora - m[0] < 0.12]
            a['x'] = x
            self._actualizar_glow()
            self.update()
            return
        c = self._en_control(x, y)
        if c is None:
            k = self._en_carta(x, y)
            c = ('carta', k) if k is not None else None
        if c != self._hover:
            self._hover = c
            self.setCursor(Qt.CursorShape.PointingHandCursor if c else Qt.CursorShape.ArrowCursor)
            self.update()
            self._arrancar()
        # v5.5.10: la del centro YA NO se inclina hacia el ratón (al usuario no le gustaba que el slider se moviera al pasar por encima)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._tilt_obj = [0.0, 0.0]
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self._cartas:
            super().mousePressEvent(e)
            return
        self.setFocus()
        x, y = e.position().x(), e.position().y()
        self._arrastre = {'x0': x, 'x': x, 'pos0': self._pos, 'mov': False, 'control': self._en_control(x, y), 'carta': self._en_carta(x, y),
                          'muestras': [(time.perf_counter(), x)]}
        self._vel = 0.0
        self._arrancar()
        e.accept()

    def mouseReleaseEvent(self, e):
        a, self._arrastre = self._arrastre, None
        if a is None or e.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(e)
            return
        n = len(self._cartas)
        if not a['mov']:
            self._pos = a['pos0']
            c = a['control']
            if c and c[0] == 'pildora':
                quiere = c[1] == 'pro'
                if quiere != self.modo_pro:
                    self.poner_vista_pro(quiere)
                    self.vista_pro.emit(quiere)
            elif a['carta'] is not None:
                k = a['carta']
                if k == self._obj:
                    carta = self._cartas[k]
                    if carta.tipo == 'anadir':
                        self.anadir.emit()
                    else:
                        self.elegida.emit(carta.valor)
                else:
                    self._ir_a(k)
            else:
                self._ir_a(round(self._pos))
        else:
            m = a['muestras']
            v = 0.0
            if len(m) >= 2 and m[-1][0] > m[0][0]:
                v = (m[-1][1] - m[0][1]) / (m[-1][0] - m[0][0])          # px/s
            cartas_s = -v / (self._medidas()[0] * self.PASO)
            self._vel = cartas_s * 0.35
            self._ir_a(max(0, min(n - 1, round(self._pos + cartas_s * 0.16))))
        self._arrancar()
        e.accept()

    def desplazar_con_rueda(self, e):
        """La rueda mueve el slider de una tarjeta en una (rueda abajo / derecha = la siguiente), en cualquier dirección. Devuelve True."""
        d = e.angleDelta()
        paso = d.y() if abs(d.y()) >= abs(d.x()) else d.x()
        ahora = time.perf_counter()
        if ahora - self._ult_rueda > 0.16 and paso:
            self._ult_rueda = ahora
            self._ir_a(self._obj + (-1 if paso > 0 else 1))
        return True

    def wheelEvent(self, e):
        self.desplazar_con_rueda(e)
        e.accept()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Left:
            self._ir_a(self._obj - 1)
        elif k == Qt.Key.Key_Right:
            self._ir_a(self._obj + 1)
        elif k == Qt.Key.Key_Home:
            self._ir_a(0)
        elif k == Qt.Key.Key_End:
            self._ir_a(len(self._cartas) - 1)
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            c = self.carta_central()
            if c is not None and c.tipo == 'anadir':
                self.anadir.emit()
            elif c is not None:
                self.elegida.emit(c.valor)
        else:
            super().keyPressEvent(e)
            return
        e.accept()


class HeroCrear(QFrame):
    """La sección «Crea tu estilo» (debajo del slider): una banda con degradado, un halo con destellos a la izquierda y el texto y los
    botones encima (los pone quien la arma). El icono y el halo los pinta ella; el contenido deja ~100 px de margen izquierdo."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setObjectName('heroCrear')
        self.setMinimumHeight(128)
        self._icono = ui.icono_linea('ph.sparkle-bold', '#FFFFFF')

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        camino = QPainterPath()
        camino.addRoundedRect(r, 22, 22)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        verde = QColor(ui.VERDE)
        g.setColorAt(0.0, QColor(int(verde.red() * 0.16 + 8), int(verde.green() * 0.16 + 14), int(verde.blue() * 0.16 + 22)))
        g.setColorAt(0.55, QColor('#0C1830'))
        g.setColorAt(1.0, QColor('#150F33'))
        p.fillPath(camino, QBrush(g))
        p.setClipPath(camino)
        # el halo del icono (verde) y una luz violeta lejana arriba a la derecha
        h = QRadialGradient(QPointF(r.left() + 54, r.center().y()), 150)
        c0 = QColor(ui.VERDE)
        c0.setAlpha(80)
        c1 = QColor(ui.VERDE)
        c1.setAlpha(0)
        h.setColorAt(0.0, c0)
        h.setColorAt(1.0, c1)
        p.fillRect(self.rect(), QBrush(h))
        v = QRadialGradient(QPointF(r.right() - 90, r.top() + 10), 240)
        v0 = QColor('#8C6CFF')
        v0.setAlpha(46)
        v1 = QColor('#8C6CFF')
        v1.setAlpha(0)
        v.setColorAt(0.0, v0)
        v.setColorAt(1.0, v1)
        p.fillRect(self.rect(), QBrush(v))
        # destellos sueltos
        p.setPen(Qt.PenStyle.NoPen)
        for dx, dy, rad, a in ((0.12, 0.2, 2.2, 150), (0.2, 0.78, 1.6, 110), (0.34, 0.3, 1.4, 90), (0.62, 0.82, 1.8, 70), (0.9, 0.3, 1.6, 90), (0.78, 0.18, 1.2, 80)):
            p.setBrush(QColor(255, 255, 255, a))
            p.drawEllipse(QPointF(r.left() + r.width() * dx, r.top() + r.height() * dy), rad, rad)
        p.setClipping(False)
        # el círculo del icono
        c = QPointF(r.left() + 54, r.center().y())
        anillo = QColor(ui.VERDE)
        anillo.setAlpha(150)
        p.setPen(QPen(anillo, 1.6))
        fondo = QColor(ui.VERDE)
        fondo.setAlpha(46)
        p.setBrush(fondo)
        p.drawEllipse(c, 30, 30)
        if self._icono is not None:
            pm = self._icono.pixmap(30, 30)
            p.drawPixmap(QPointF(c.x() - 15, c.y() - 15), pm)
        borde = QColor(255, 255, 255, 30)
        p.setPen(QPen(borde, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 22, 22)
        p.end()
