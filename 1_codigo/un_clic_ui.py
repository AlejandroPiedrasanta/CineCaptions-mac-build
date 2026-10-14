# CineCaptions · By Cinema Productions
# 1_codigo/un_clic_ui.py — la pantalla de Inicio: botón GO, pasos animados, cinta viral y vista previa.
"""
un_clic_ui.py  (v5.1)
---------------------
La pantalla de Inicio minimalista: UN boton (GO) que lo hace todo de un clic
-traer el timeline de Resolve, transcribir, que la IA corrija y elija las
palabras, el diseño dinamico de 3 lineas, los efectos de sonido, la vista
previa y colocarlo en el timeline-, con cada paso animado a la vista.

Aqui solo vive lo que se VE (el boton, la lista de pasos, la vista previa);
quien encadena los pasos es SubtitleApp (_go y compania), con las mismas
piezas que usa «Nuevo proyecto».
"""
import math

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QConicalGradient, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QSizePolicy,
                               QVBoxLayout, QWidget)

import qt_kit as ui
from qt_kit import Boton, Enlace, Etiqueta, MarcoVista, QColor, QColorReal, caja_h, caja_v, fuente
from i18n import tr


def _anim(padre, duracion, al_cambiar, bucle=False, curva=QEasingCurve.Type.Linear):
    a = QVariantAnimation(padre)
    a.setDuration(duracion)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(curva)
    if bucle:
        a.setLoopCount(-1)
    a.valueChanged.connect(al_cambiar)
    return a


class BotonGo(QAbstractButton):
    """El botón GO: el astrolabio (orbe_mecanica). Estados: listo (respira), apagado, trabajando (cada fase enciende una pieza, el
    engranaje se acelera con el progreso real, ETA), hecho (cierre en tres tiempos: carga y temblor → destello → el engranaje
    se detiene y la palomita se dibuja), error (el orbe se apaga poco a poco). Un solo reloj lo mueve todo (el de la escena);
    el ratón inclina las capas (paralaje) y el tamaño sigue al alto disponible (poner_lado)."""
    CARGA = 0.7                  # s de carga/temblor antes del destello del final

    def __init__(self, padre=None, lado=280):
        super().__init__(padre)
        self.setFixedSize(lado, lado)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.estado = 'listo'
        self.progreso = 0.0
        self._prog_visto = 0.0
        self.texto_centro = ''
        self.texto_bajo = ''
        self.fase = ''
        self._fase_t0 = -9.0
        self.tono = 'ok'                 # 'ok' | 'aviso' (terminó con avisos)
        self._t = 0.0
        self._hover = 0.0
        self._hover_obj = 0.0
        self._presion = 0.0
        self._presion_obj = 0.0
        self._iman = QPointF(0, 0)
        self._iman_obj = QPointF(0, 0)
        self._par = [0.0, 0.0]
        self._marca = 0.0
        self._sacudida = 0.0
        self._flare = 0.0
        self._cierre = -1.0              # segundos desde que terminó (hecho/error); -1 = no terminó
        self._estallo = False
        self._clic_fin = False
        self._apagon = 0.0
        self._residuo = 0.0
        self._vel = 1.0
        self._ent = 0.0                  # segundos desde que apareció: las piezas se ensamblan de fuera hacia dentro
        self._ent_hecha = False
        self._desde = 0.0
        self._suave_t = 1.0
        self._t_ini = None               # cuándo empezó a trabajar (para el tiempo restante)
        self._eta_fin = None
        self._eta_manual = ''            # el tiempo restante que calcula el estimador de GO (manda sobre el cálculo por ritmo)
        self._escena = None
        import efectos_ui
        self._quieto = efectos_ui.reducir_animaciones()
        import estilos_inicio
        self._estilos = estilos_inicio
        self._poner_estilo(estilos_inicio.clave_guardada())
        self._flare_hecho = False
        self._flare = 0.0
        self._lado_obj = lado
        self._lado_f = float(lado)
        self._reloj = QTimer(self)
        self._reloj.setTimerType(Qt.TimerType.PreciseTimer)         # 60 fps parejos (el temporizador normal de Windows da saltos)
        self._reloj.timeout.connect(self._tic)
        self._reloj.start(16)
        import time as _time
        self._time = _time
        self._ultimo = _time.perf_counter()

    def _poner_estilo(self, clave):
        """Cambia el diseño del botón (los 10 estilos de Inicio): cada uno lleva su propia instancia con su movimiento."""
        self._estilo_clave = clave
        self._estilo = self._estilos.crear(clave)
        self._ctx = self._estilos.Ctx()
        self.update()

    def poner_lado(self, lado):
        """El tamaño que debe tener; el botón se acerca a él con suavidad (si aún no se ve, de golpe)."""
        lado = int(max(200, min(620, lado)))
        self._lado_obj = lado
        if not self.isVisible() or not self._ent_hecha:
            self._lado_f = float(lado)
            if lado != self.width():
                self.setFixedSize(lado, lado)

    def _modo(self):
        return getattr(self._escena, 'modo', 'completo') if self._escena is not None else 'completo'

    # -- reloj -------------------------------------------------------------------
    def _tic(self):
        ahora = self._time.perf_counter()
        dt = min(0.05, ahora - self._ultimo)
        self._ultimo = ahora
        self._t += dt
        self._ent += dt
        self._flare = max(0.0, self._flare - dt / 1.0)
        if abs(self._lado_obj - self._lado_f) > 0.4:                      # el orbe cambia de tamaño con suavidad
            self._lado_f += (self._lado_obj - self._lado_f) * min(1.0, dt * 7.0)
            n = int(round(self._lado_f))
            if n != self.width():
                self.setFixedSize(n, n)
        est = self.estado
        # velocidad de giro: lenta en reposo; con el progreso real se acelera; el cierre la sube, la frena en seco y la devuelve
        if est == 'listo':
            obj = 1.0
        elif est == 'apagado':
            obj = 0.2
        elif est == 'trabajando':
            obj = 3.0 + 6.0 * self._prog_visto
        elif est == 'hecho':
            c = max(0.0, self._cierre)
            if c < self.CARGA:
                obj = 4.0 + 8.0 * (c / self.CARGA)
            elif c < 3.2:
                obj = 0.12 + 9.0 * math.exp(-(c - self.CARGA) * 3.4)
            else:
                obj = 1.0
        else:
            obj = 0.7 * (1.0 - self._apagon) + 0.04
        self._vel += (obj - self._vel) * min(1.0, dt * (14.0 if est == 'hecho' and self._cierre < 3.2 else 6.0))
        quieto = self._quieto or bool(getattr(self._escena, '_quieto', False))
        if self._escena is not None and getattr(self._escena, 'estilo_clave', self._estilo_clave) != self._estilo_clave:
            self._poner_estilo(self._escena.estilo_clave)
        self._estilo.avanzar(dt, 0.0 if quieto else self._vel)
        k = min(1.0, dt * 12)
        self._hover += (self._hover_obj - self._hover) * k
        self._presion += (self._presion_obj - self._presion) * min(1.0, dt * 22)
        self._iman = self._iman + (self._iman_obj - self._iman) * min(1.0, dt * 8)
        if self._suave_t < 1.0:
            self._suave_t = min(1.0, self._suave_t + dt / 0.35)
            f = 1 - (1 - self._suave_t) ** 3
            self._prog_visto = self._desde + (self.progreso - self._desde) * f
        # el cierre en tres tiempos
        if self._cierre >= 0.0:
            self._cierre += dt
            if est == 'hecho':
                if self._cierre >= self.CARGA and not self._estallo:
                    self._estallo = True
                    self._flare = 1.0                                   # 2.º tiempo: el destello
                if self._cierre >= self.CARGA + 0.2 and self._marca < 1.0:
                    self._marca = min(1.0, self._marca + dt / 0.85)     # la palomita se dibuja trazo a trazo
                if self._cierre >= 1.9 and not self._clic_fin:
                    self._clic_fin = True
                    self._flare = max(self._flare, 0.4)                 # 3.er tiempo: el «clic» al detenerse el engranaje
            elif est == 'error':
                self._apagon = min(1.0, self._cierre / 2.5)
        if self._residuo > 0.0 and est in ('listo', 'apagado'):
            self._residuo = max(0.0, self._residuo - dt / 1.8)
        if self._sacudida > 0:
            self._sacudida = max(0.0, self._sacudida - dt)
        if self.isVisible():
            self.update()

    def seguir_a(self, escena):
        """Un solo reloj para todo Inicio: el botón avanza cuando avanza la escena, así Qt junta los dos repintados en uno."""
        self._externo = True
        self._escena = escena
        self._reloj.stop()
        escena.al_tic.append(self._tic)

    def showEvent(self, e):
        self._ultimo = self._time.perf_counter()
        if not self._ent_hecha:
            self._ent_hecha = True
            self._ent = 0.0
        if not getattr(self, '_externo', False):
            self._reloj.start(16)
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)

    def enterEvent(self, e):
        self._hover_obj = 1.0
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover_obj = 0.0
        self._iman_obj = QPointF(0, 0)
        super().leaveEvent(e)

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        if self.estado in ('listo', 'hecho', 'error'):
            self._presion_obj = 1.0
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._presion_obj = 0.0
        super().mouseReleaseEvent(e)

    # -- estado ---------------------------------------------------------------
    def poner_estado(self, estado, centro=None, bajo=None, tono=None):
        anterior = self.estado
        self.estado = estado
        if centro is not None:
            self.texto_centro = centro
        if bajo is not None:
            self.texto_bajo = bajo
        self.setCursor(Qt.CursorShape.PointingHandCursor if estado in ('listo', 'hecho', 'error')
                       else Qt.CursorShape.ArrowCursor)
        if estado == 'trabajando' and anterior != 'trabajando':
            self._flare = 1.0
            self._cierre = -1.0
            self._estallo = self._clic_fin = False
            self._apagon = 0.0
            self._residuo = 0.0
            self._marca = 0.0
            self.tono = 'ok'
            self.fase = ''
            self._t_ini = self._time.perf_counter()
            self._eta_fin = None
            self._eta_manual = ''
        if estado == 'hecho' and anterior != 'hecho':
            self._marca = 0.0
            self._cierre = 0.0
            self._estallo = self._clic_fin = False
            self.tono = tono or 'ok'
        if estado == 'error' and anterior != 'error':
            self._cierre = 0.0
            self._apagon = 0.0
            if not self._quieto:
                self._sacudida = 0.5
        if estado in ('listo', 'apagado') and anterior == 'hecho':
            self._residuo = 1.0                                        # la palomita se desvanece mientras vuelve la gema
            self._cierre = -1.0
        elif estado in ('listo', 'apagado'):
            self._cierre = -1.0
        self.update()

    def poner_fase(self, clave):
        """El paso en curso: enciende una pieza distinta del astrolabio y da un pequeño temblor al cambiar."""
        if clave != self.fase:
            self.fase = clave
            self._fase_t0 = self._t

    def poner_progreso(self, f):
        f = max(0.0, min(1.0, float(f)))
        self._desde = self._prog_visto
        self.progreso = f
        self._suave_t = 0.0
        # tiempo restante: se estima con el ritmo hasta ahora y se suaviza (no salta)
        if self.estado == 'trabajando' and self._t_ini is not None and f > 0.08:
            ahora = self._time.perf_counter()
            transcurrido = ahora - self._t_ini
            if transcurrido > 1.0:
                fin = ahora + transcurrido * (1.0 - f) / f
                self._eta_fin = fin if self._eta_fin is None else 0.8 * self._eta_fin + 0.2 * fin

    def poner_eta(self, texto):
        self._eta_manual = str(texto or '')
        self.update()

    def _eta_texto(self):
        if self.estado == 'trabajando' and self._eta_manual:
            return self._eta_manual
        if self.estado != 'trabajando' or self._eta_fin is None or self._t_ini is None:
            return ''
        ahora = self._time.perf_counter()
        if ahora - self._t_ini < 8.0 or self._prog_visto > 0.97:
            return ''
        resto = max(0.0, self._eta_fin - ahora)
        if resto < 10:
            return tr('unos segundos')
        if resto < 90:
            return tr('~ {s} s', s=int(round(resto / 5.0) * 5))
        return tr('~ {m} min', m=int(round(resto / 60.0)))

    def centro_global(self):
        return self.mapToGlobal(self.rect().center())

    # -- dibujo ---------------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        w, h = self.width(), self.height()
        sac = 0.0
        if self._sacudida > 0:
            sac = math.sin(self._t * 60) * 10 * (self._sacudida / 0.5)
        c = QPointF(w / 2 + sac, h / 2)
        escala = 1 - 0.03 * self._presion                                  # solo al PULSAR se hunde un poco; al pasar el ratón no se mueve
        R = min(w, h) * 0.40 * escala
        estado, prog, texto = self.estado, self._prog_visto, self.texto_centro
        vibra = 0.0
        if estado == 'hecho' and 0.0 <= self._cierre < self.CARGA:            # 1.er tiempo: carga y temblor, todavía al 100 %
            estado, prog, texto = 'trabajando', 1.0, tr('Listo')
            vibra = min(1.0, self._cierre / 0.45) * 0.9
        elif self.estado == 'trabajando' and self._t - self._fase_t0 < 0.35:   # al cambiar de fase, un temblor corto
            vibra = 0.5 * (1.0 - (self._t - self._fase_t0) / 0.35)
        cx = self._ctx
        cx.estado, cx.t, cx.progreso, cx.marca, cx.flare = estado, self._t, prog, self._marca, self._flare
        cx.hover, cx.presion, cx.fase, cx.fase_t, cx.tono = self._hover, self._presion, (self.fase if self.estado == 'trabajando' else ''), self._t - self._fase_t0, self.tono
        cx.vibra, cx.apagon, cx.residuo, cx.eta, cx.texto = vibra, self._apagon, self._residuo, self._eta_texto(), texto
        cx.entrada, cx.vel, cx.quieto, cx.cierre = self._ent, self._vel, self._quieto, self._cierre
        if self._estilo_clave != 'astrolabio' and self._ent < 1.2:                # entrada: aparece creciendo (el astrolabio se ensambla pieza a pieza)
            e = min(1.0, self._ent / 0.8)
            p.setOpacity(e)
            R *= 0.86 + 0.14 * (1 - (1 - e) ** 3)
        self._estilo.dibujar(p, c, R, cx, min(w, h) * 0.40)
        p.end()


class TituloGo(QWidget):
    """v5.4: el titulo de Inicio («Un clic y listo»): texto vectorial con degradado blanco->celeste, un halo suave
    detras y una linea de luz bajo el. Misma interfaz que Etiqueta para lo que usa la app (configure(text=...))."""
    def __init__(self, texto, padre=None):
        super().__init__(padre)
        self._texto = texto
        self.setFixedHeight(64)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def configure(self, text=None, **_kw):
        if text is not None and text != self._texto:
            self._texto = text
            self.update()

    def paintEvent(self, _e):
        # el titulo se repinta cada vez que la escena de detras avanza un cuadro (60 por segundo): se dibuja UNA vez a un pixmap
        w, h = self.width(), self.height()
        dpr = self.devicePixelRatioF()
        clave = (self._texto, w, h, round(dpr, 2))
        if getattr(self, '_clave_pm', None) != clave:
            pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            self._dibujar_texto(pm)
            self._pm, self._clave_pm = pm, clave
        q = QPainter(self)
        q.drawPixmap(0, 0, self._pm)
        q.end()

    def _dibujar_texto(self, destino):
        from PySide6.QtGui import QPainterPath, QLinearGradient
        w, h = self.width(), self.height()
        f = fuente(34, peso='extra')
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 102)
        fm = QFontMetricsF(f)
        ancho = fm.horizontalAdvance(self._texto)
        x, y = (w - ancho) / 2, h * 0.62
        ruta = QPainterPath()
        ruta.addText(QPointF(x, y), f, self._texto)
        p = QPainter(destino)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for grosor, alfa in ((9, 14), (5, 22), (2.5, 34)):          # halo
            p.setPen(QPen(QColorReal(90, 190, 255, alfa), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ruta)
        p.setPen(Qt.PenStyle.NoPen)
        p.translate(0, 2)
        p.setBrush(QColorReal(0, 0, 0, 150))
        p.drawPath(ruta)
        p.translate(0, -2)
        g = QLinearGradient(0, y - fm.ascent(), 0, y + fm.descent())
        g.setColorAt(0.0, QColorReal(255, 255, 255))
        g.setColorAt(0.55, QColorReal(226, 240, 255))
        g.setColorAt(1.0, QColorReal(140, 205, 255))
        p.setBrush(g)
        p.drawPath(ruta)
        yl = h - 7                                                   # linea de luz
        lg = QLinearGradient(w / 2 - ancho / 2, 0, w / 2 + ancho / 2, 0)
        lg.setColorAt(0.0, QColorReal(80, 200, 255, 0))
        lg.setColorAt(0.5, QColorReal(120, 220, 255, 190))
        lg.setColorAt(1.0, QColorReal(80, 200, 255, 0))
        p.setBrush(lg)
        p.drawRoundedRect(QRectF(w / 2 - ancho / 2, yl, ancho, 2), 1, 1)
        p.end()


class CintaViral(QWidget):
    """Inicio en reposo: una demo de lo que hace GO, en bucle — subtitulos
    virales de 3 lineas que entran palabra a palabra con rebote, en los
    colores de los roles, con su emoji (Explicacion: muestra el resultado
    antes de pulsar)."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self.FRASES = ((tr('ESTO'), tr('CAMBIA'), tr('todo'), '🔥'), (tr('Hazlo en'), tr('1 CLIC'), tr('y listo'), '🚀'),
                       (tr('Sin'), tr('EDITAR'), tr('nada'), '💸'), (tr('La IA'), tr('ELIGE'), tr('las palabras'), '🧠'))
        self.setFixedHeight(132)
        self.setMinimumWidth(320)
        self._t = 0.0
        self._k = 0
        import time as _time
        self._time = _time
        self._ultimo = _time.perf_counter()
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tic)
        self._reloj.start(33)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _tic(self):
        ahora = self._time.perf_counter()
        self._t += min(0.05, ahora - self._ultimo)
        self._ultimo = ahora
        if self._t > 3.2:
            self._t = 0.0
            self._k = (self._k + 1) % len(self.FRASES)
        if self.isVisible():
            self.update()

    def showEvent(self, e):
        self._ultimo = self._time.perf_counter()
        self._reloj.start(33)
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)

    @staticmethod
    def _rebote(x):
        """0..1 con rebote de salida (OutBack)."""
        x = max(0.0, min(1.0, x))
        s = 1.70158
        x -= 1
        return x * x * ((s + 1) * x + s) + 1

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        ctx, main, cmp_, emoji = self.FRASES[self._k]
        w = self.width()
        cx = w / 2
        t = self._t
        salida = max(0.0, (t - 2.7) / 0.5)
        lineas = [(ctx, 'Montserrat', 'ExtraBold', 17, QColorReal('#FFFFFF'), 0.00, 28),
                  (main, 'Montserrat', 'Black', 36, QColorReal(ui.ROL_PRINCIPAL), 0.22, 74),
                  (cmp_, 'Montserrat', 'SemiBold', 18, QColorReal(ui.ROL_COMPLEMENTO), 0.44, 114)]
        for texto, fam, est, tam, color, retardo, y in lineas:
            f = self._rebote((t - retardo) / 0.42)
            if f <= 0:
                continue
            alfa = max(0.0, min(1.0, (t - retardo) / 0.2)) * (1 - salida)
            fuente_l = QFont(fam)
            fuente_l.setPixelSize(tam)
            fuente_l.setStyleName(est)
            p.save()
            p.setOpacity(alfa)
            p.translate(cx, y + (1 - f) * 16)
            esc = 0.75 + 0.25 * f
            p.scale(esc, esc)
            p.setFont(fuente_l)
            fm = QFontMetricsF(fuente_l)
            ancho = fm.horizontalAdvance(texto)
            if texto == main:
                # la principal en su caja, como en los virales
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColorReal(color.red(), color.green(), color.blue(), 235))
                p.drawRoundedRect(QRectF(-ancho / 2 - 12, -fm.ascent() * 0.82, ancho + 24, fm.ascent() * 1.12), 8, 8)
                p.setPen(QColorReal('#0B0F18'))
            else:
                p.setPen(QColorReal(0, 0, 0, 160))
                p.drawText(QPointF(-ancho / 2, 2), texto)
                p.setPen(color)
            p.drawText(QPointF(-ancho / 2, 0), texto)
            if texto == main:
                fe = self._rebote((t - 0.7) / 0.35)
                if fe > 0:
                    fuente_e = QFont('Segoe UI Emoji')
                    fuente_e.setPixelSize(int(26 * fe))
                    p.setFont(fuente_e)
                    p.translate(ancho / 2 + 18, -6)
                    p.rotate(-12 + 12 * fe)
                    p.drawText(QPointF(0, 0), emoji)
            p.restore()
        p.end()


class PasosAnimados(QWidget):
    """La lista de pasos: cada uno se enciende (arco que gira), se marca (✓)
    o se salta, y entran deslizandose uno tras otro."""
    ALTO_FILA = 40

    def __init__(self, pasos, padre=None):
        super().__init__(padre)
        self.pasos = list(pasos)               # [(clave, texto)]
        self.estado = {c: 'pendiente' for c, _ in self.pasos}
        self.detalle = {c: '' for c, _ in self.pasos}
        self._entrada = [0.0] * len(self.pasos)
        self._giro = 0.0
        self.setFixedHeight(self.ALTO_FILA * len(self.pasos) + 8)
        self.setMinimumWidth(440)
        self._gira = _anim(self, 1000, self._al_girar, bucle=True)
        self._anims = []

    def sizeHint(self):
        return QSize(480, self.height())

    def _al_girar(self, v):
        self._giro = float(v)
        self.update()

    def entrar(self):
        """Reinicia y hace entrar las filas, escalonadas."""
        for c, _ in self.pasos:
            self.estado[c] = 'pendiente'
            self.detalle[c] = ''
        self._entrada = [0.0] * len(self.pasos)
        for a in self._anims:
            a.stop()
        self._anims = []
        for i in range(len(self.pasos)):
            a = _anim(self, 380, lambda v, i=i: self._poner_entrada(i, v), curva=QEasingCurve.Type.OutCubic)
            QTimer.singleShot(70 * i, a.start)
            self._anims.append(a)
        self._gira.start()

    def _poner_entrada(self, i, v):
        self._entrada[i] = float(v)
        self.update()

    def marcar(self, clave, estado, detalle=None):
        if clave not in self.estado:
            return
        # al activar uno, los anteriores que siguieran activos quedan hechos
        if estado == 'activo':
            for c, _ in self.pasos:
                if c == clave:
                    break
                if self.estado[c] in ('activo', 'pendiente'):
                    self.estado[c] = 'hecho' if self.estado[c] == 'activo' else self.estado[c]
        self.estado[clave] = estado
        if detalle is not None:
            self.detalle[clave] = detalle
        if all(e in ('hecho', 'saltado', 'error') for e in self.estado.values()):
            self._gira.stop()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, (clave, texto) in enumerate(self.pasos):
            t = self._entrada[i]
            if t <= 0:
                continue
            y = 4 + i * self.ALTO_FILA + (1 - t) * 14
            p.setOpacity(t)
            est = self.estado[clave]
            cx, cy, rr = 18.0, y + self.ALTO_FILA / 2, 10.0
            if est == 'hecho':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColorReal(ui.VERDE))
                p.drawEllipse(QPointF(cx, cy), rr, rr)
                p.setPen(QPen(QColorReal('#06140E'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawPolyline([QPointF(cx - 4.5, cy + 0.2), QPointF(cx - 1.2, cy + 3.6), QPointF(cx + 5, cy - 3.6)])
            elif est == 'activo':
                p.setPen(QPen(QColor('#22324F'), 2.4))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rr, rr)
                p.setPen(QPen(QColor(ui.ACCENT_CLARO), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr), int(-360 * self._giro * 16), 110 * 16)
            elif est == 'error':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColorReal(ui.ROJO))
                p.drawEllipse(QPointF(cx, cy), rr, rr)
                p.setPen(QPen(QColorReal('#FFFFFF'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(cx - 3.5, cy - 3.5), QPointF(cx + 3.5, cy + 3.5))
                p.drawLine(QPointF(cx + 3.5, cy - 3.5), QPointF(cx - 3.5, cy + 3.5))
            else:
                p.setPen(QPen(QColor('#22324F' if est == 'pendiente' else '#2A3550'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rr, rr)
                if est == 'saltado':
                    p.drawLine(QPointF(cx - 4, cy), QPointF(cx + 4, cy))
            color = {'activo': '#FFFFFF', 'hecho': '#C9D6EC', 'error': '#FF8A80', 'saltado': '#5A6B87'}.get(est, '#5A6B87')
            p.setPen(QColor(color))
            p.setFont(fuente(15, peso='negrita' if est == 'activo' else 'medio'))
            p.drawText(QRectF(42, y, self.width() - 160, self.ALTO_FILA),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), texto)
            if self.detalle[clave]:
                p.setPen(QColor('#7F8DA8'))
                p.setFont(fuente(12))
                p.drawText(QRectF(self.width() - 170, y, 166, self.ALTO_FILA),
                           int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), self.detalle[clave])
        p.setOpacity(1.0)
        p.end()


class ResumenGo(QWidget):
    """Al terminar: contadores que suben (bloques, palabras, duración…). Un número grande y su etiqueta, en fila."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self._items = []                     # [(valor, etiqueta, formato 'n' | 't')]
        self._u = 0.0
        self.setFixedHeight(74)
        self.setMinimumWidth(520)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._anim = _anim(self, 1700, self._paso, curva=QEasingCurve.Type.Linear)

    def poner(self, items):
        self._items = [i for i in items if i[0]]
        self._u = 0.0

    def animar(self):
        self._u = 0.0
        self._anim.stop()
        if self._items:
            self._anim.start()

    def _paso(self, v):
        self._u = float(v)
        self.update()

    @staticmethod
    def _txt(valor, formato):
        if formato == 't':
            s = int(round(valor))
            return f'{s // 60}:{s % 60:02d}'
        return str(int(round(valor)))

    def paintEvent(self, _e):
        n = len(self._items)
        if not n:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ancho = self.width() / n
        for i, (valor, etiqueta, formato) in enumerate(self._items):
            u = max(0.0, min(1.0, (self._u * 1.7 - 0.18 * i) / 1.0))
            e = 1 - (1 - u) ** 3
            x0 = i * ancho
            p.setOpacity(min(1.0, u * 3.0))
            p.setPen(QColorReal('#FFFFFF'))
            p.setFont(fuente(28, peso='extra'))
            p.drawText(QRectF(x0, 4 - (1 - e) * 8, ancho, 40), int(Qt.AlignmentFlag.AlignCenter), self._txt(valor * e, formato))
            p.setPen(QColorReal('#8FA3C7'))
            p.setFont(fuente(12, peso='medio'))
            p.drawText(QRectF(x0, 46, ancho, 22), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), etiqueta)
            if i:
                p.setPen(QPen(QColorReal(255, 255, 255, 28), 1))
                p.drawLine(QPointF(x0, 10), QPointF(x0, 60))
        p.setOpacity(1.0)
        p.end()


class SalidaGo(QWidget):
    """Los botones de después del final («Ver en Resolve», «Editar palabras»…): se abren con un pequeño rebote."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self.capa = QHBoxLayout(self)
        self.capa.setContentsMargins(0, 0, 0, 0)
        self.capa.setSpacing(10)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(520)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._paso)
        self.setFixedHeight(0)

    def configurar(self, botones):
        """botones: [(texto, funcion, tipo)]"""
        while self.capa.count():
            it = self.capa.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        for texto, fn, tipo in botones:
            self.capa.addWidget(Boton(texto, fn, tipo=tipo, alto=42, ancho=190, tam=14, negrita=(tipo == 'primario')))

    def mostrar(self):
        self.show()
        self._anim.stop()
        self._anim.start()

    def ocultar(self):
        self._anim.stop()
        self.setFixedHeight(0)
        self.hide()

    def _paso(self, v):
        self.setFixedHeight(max(0, int(46 * float(v))))


_PERFIL = {'v': None}


def perfil_del_equipo():
    """v5.4.8: «motor de voz + dónde corre» (p. ej. 'whisper-gpu', 'qwen3-cpu'): los pasos tardan MUY distinto en cada perfil (la voz en GPU es ~3× más rápida), así que el
    ritmo aprendido se guarda por perfil y un cambio de motor o de GPU no desajusta el tiempo que sale bajo el porcentaje. Se calcula una vez por sesión."""
    if _PERFIL['v'] is None:
        try:
            import ajustes_ui
            import cuda_libs
            motor = str(ajustes_ui.leer_prefs().get('motor_voz') or 'qwen3')
            _PERFIL['v'] = f"{motor}-{'gpu' if cuda_libs.diagnostico()['estado'] == 'ok' else 'cpu'}"
        except Exception:
            _PERFIL['v'] = 'general'
    return _PERFIL['v']


class EstimadorGo:
    """Cuánto falta en GO. Cada paso tiene una duración esperada (base + lo que cuesta por minuto de video, escalada por lo que tardó en las últimas veces en
    ESTE equipo: se aprende y se guarda en las preferencias, «go_ritmo»). Con eso el porcentaje avanza con el reloj dentro de cada paso (no se queda quieto
    entre un paso y otro) y debajo sale el tiempo que queda; si un paso tarda mucho más de lo normal lo dice."""
    ORDEN = ('timeline', 'voz', 'ia', 'diseno', 'sfx', 'resolve')
    BASE = {'timeline': 8.0, 'voz': 8.0, 'ia': 22.0, 'diseno': 3.0, 'sfx': 6.0, 'resolve': 18.0}
    POR_MIN = {'timeline': 0.0, 'voz': 5.0, 'ia': 6.0, 'diseno': 0.5, 'sfx': 3.0, 'resolve': 6.0}

    def __init__(self):
        import time as _t
        self._time = _t
        self.factor = {k: 1.0 for k in self.ORDEN}
        self.efectos = False
        self.perfil = perfil_del_equipo()
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
            guardado = (prefs.get('go_ritmo_perfiles') or {}).get(self.perfil) or prefs.get('go_ritmo') or {}
            for k in self.ORDEN:
                v = float(guardado.get(k, 1.0))
                if 0.2 <= v <= 6.0:
                    self.factor[k] = v
        except Exception:
            pass
        self.minutos = 1.0
        self.reiniciar()

    def reiniciar(self):
        self.t0 = None
        self.actual = None
        self.t_paso = None
        self.hechos = {}              # clave -> segundos reales (0 si se saltó)
        self.saltados = set()
        self.dentro_f = 0.0

    def empezar(self):
        self.reiniciar()
        self.t0 = self._time.perf_counter()

    def duracion(self, segundos):
        try:
            self.minutos = max(0.2, min(90.0, float(segundos) / 60.0))
        except (TypeError, ValueError):
            pass

    def poner_efectos(self, activos):
        """Con los efectos visuales encendidos, colocar en Resolve cuesta más (secuencias, intro, transiciones, iconos)."""
        self.efectos = bool(activos)

    def _base(self, k):
        extra = (10.0 + 1.5 * self.minutos) if (k == 'resolve' and self.efectos) else 0.0
        return self.BASE[k] + self.POR_MIN[k] * self.minutos + extra

    def esperado(self, k):
        if k in self.saltados:
            return 0.0
        return max(1.0, self._base(k) * self.factor[k])

    def paso(self, clave, estado):
        if clave not in self.ORDEN or self.t0 is None:
            return
        ahora = self._time.perf_counter()
        if estado == 'activo':
            if self.actual and self.actual != clave and self.actual not in self.hechos:
                self.hechos[self.actual] = ahora - (self.t_paso or ahora)
            self.actual, self.t_paso, self.dentro_f = clave, ahora, 0.0
        elif estado in ('hecho', 'saltado'):
            if estado == 'saltado':
                self.saltados.add(clave)
                self.hechos[clave] = 0.0
            else:
                self.hechos[clave] = (ahora - self.t_paso) if (self.actual == clave and self.t_paso) else 0.0
            if self.actual == clave:
                self.actual, self.t_paso, self.dentro_f = None, None, 0.0

    def dentro(self, clave, fraccion):
        if clave == self.actual:
            self.dentro_f = max(self.dentro_f, max(0.0, min(1.0, float(fraccion))))

    def _en_paso(self):
        return (self._time.perf_counter() - self.t_paso) if self.t_paso else 0.0

    def _f_actual(self):
        """Qué parte del paso en curso va hecha: lo que diga el paso (transcribir, IA) o, si no dice, el reloj (sin pasar del 93 %)."""
        if not self.actual:
            return 0.0
        por_reloj = min(0.93, self._en_paso() / self.esperado(self.actual))
        return max(self.dentro_f * 0.97, por_reloj)

    def fraccion(self):
        if self.t0 is None:
            return 0.0
        total = sum(self.esperado(k) for k in self.ORDEN) or 1.0
        hecho = sum(self.esperado(k) for k in self.hechos)
        if self.actual:
            hecho += self.esperado(self.actual) * self._f_actual()
        return max(0.0, min(0.985, hecho / total))

    def restante(self):
        r = sum(self.esperado(k) for k in self.ORDEN if k not in self.hechos and k != self.actual)
        if self.actual:
            e = self.esperado(self.actual)
            r += max(e * (1.0 - self._f_actual()), min(5.0, e * 0.25))
        return r

    def tarda_mas(self):
        return bool(self.actual) and self._en_paso() > max(25.0, 2.2 * self.esperado(self.actual))

    def eta_texto(self):
        if self.t0 is None:
            return ''
        if self._time.perf_counter() - self.t0 < 1.2:
            return tr('calculando…')
        if self.tarda_mas():
            return tr('tarda más de lo normal…')
        r = self.restante()
        if r < 8:
            return tr('unos segundos')
        if r < 90:
            return tr('~ {s} s', s=int(round(r / 5.0) * 5))
        m, s = int(r // 60), int(round((r % 60) / 10.0) * 10)
        if s >= 60:
            m, s = m + 1, 0
        return tr('~ {m} min {s} s', m=m, s=s) if s else tr('~ {m} min', m=m)

    def numero_de_paso(self, clave):
        pend = [k for k in self.ORDEN if k not in self.saltados]
        return (pend.index(clave) + 1, len(pend)) if clave in pend else (0, len(pend))

    def guardar(self):
        """Aprende: cuánto tardó cada paso respecto a lo esperado sin escalar (media móvil) y lo guarda."""
        try:
            nuevo = dict(self.factor)
            for k, real in self.hechos.items():
                if k in self.saltados or real < 0.5:
                    continue
                razon = real / max(1.0, self._base(k))
                nuevo[k] = round(max(0.2, min(6.0, 0.6 * self.factor[k] + 0.4 * razon)), 3)
            import ajustes_ui
            perfiles = dict(ajustes_ui.leer_prefs().get('go_ritmo_perfiles') or {})
            perfiles[self.perfil] = nuevo
            ajustes_ui.guardar_prefs({'go_ritmo': nuevo, 'go_ritmo_perfiles': perfiles})
            self.factor = nuevo
        except Exception:
            pass


class PanelGo(QWidget):
    """Inicio: el boton, una demo viva en reposo, una linea de estado, las
    opciones rapidas (las pone SubtitleApp), los pasos y «Detalles».

    v5.2: se adapta al alto disponible (el boton crece o encoge, la demo se
    retira en pantallas bajas) y avisa con 'celebrar' / 'pulso' (punto
    global) para que el fondo vivo haga el confeti y la onda."""
    go = Signal()
    celebrar = Signal(QPoint)
    pulso = Signal(QPoint)

    def __init__(self, al_detalles=None, padre=None):
        super().__init__(padre)
        self.PASOS = (('timeline', tr('Traer el timeline de Resolve')), ('voz', tr('Transcribir la voz')),
                      ('ia', tr('IA: corregir, quitar signos, palabras y emojis')),
                      ('diseno', tr('Diseño de los captions')),
                      ('sfx', tr('Efectos de sonido')),
                      ('resolve', tr('Colocar en el timeline')))
        self.escena = None                      # EscenaGo (la pone SubtitleApp): esfera 3D, absorción, cometas y explosión
        c = QVBoxLayout(self)
        c.setContentsMargins(0, 6, 0, 6)
        c.setSpacing(0)
        c.addStretch(2)
        self.boton = BotonGo()
        self.boton.clicked.connect(self._pulsado)
        c.addWidget(self.boton, 0, Qt.AlignmentFlag.AlignHCenter)
        c.addSpacing(4)
        self.titulo = TituloGo(tr('Un clic y listo'))
        c.addWidget(self.titulo)
        c.addSpacing(2)
        self.linea = ui.Elidida('', 15, color=ui.TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignCenter)
        self.linea.setFixedWidth(640)
        c.addWidget(self.linea, 0, Qt.AlignmentFlag.AlignHCenter)
        c.addSpacing(14)
        self.resumen = ResumenGo()
        c.addWidget(self.resumen, 0, Qt.AlignmentFlag.AlignHCenter)
        self.resumen.hide()
        c.addSpacing(6)
        self.salida = SalidaGo()
        c.addWidget(self.salida, 0, Qt.AlignmentFlag.AlignHCenter)
        self.salida.hide()
        c.addSpacing(8)
        self.al_ver_resolve = None              # las pone la app: «Ver en Resolve» y «Editar palabras»
        self.al_editar = None
        self.al_pausar = None                   # v5.4.8: «Pausar» y «Cancelar» mientras GO trabaja (los pone la app)
        self.al_cancelar = None
        self._b_pausa = None
        self._inicio_t = 0.0
        self._ficha = 0                         # para cancelar los temporizadores del final si empieza otro GO
        self._texto_reposo = ''
        self._reserva_final = 0                 # alto que ocupan los contadores y botones del final (el orbe cede ese sitio)
        self.estimador = EstimadorGo()
        self.paso_fallido = None                # el paso en que falló GO (lo pone la app antes de terminar(False))
        self._reloj_eta = QTimer(self)
        self._reloj_eta.setInterval(500)
        self._reloj_eta.timeout.connect(self._tic_eta)
        # las opciones rapidas de GO (fuente, idioma, estilo, efectos): las pone la app
        self.opciones = QWidget()
        self.opciones_capa = QHBoxLayout(self.opciones)
        self.opciones_capa.setContentsMargins(0, 0, 0, 0)
        self.opciones_capa.setSpacing(8)
        c.addWidget(self.opciones, 0, Qt.AlignmentFlag.AlignHCenter)
        c.addSpacing(16)
        self.pasos = PasosAnimados(self.PASOS)
        c.addWidget(self.pasos, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pasos.hide()                       # (la lista de pasos ahora la dibuja la escena: cometas que caen y se estrellan)
        self._reserva = QWidget()               # el sitio de las etiquetas de los pasos, abajo
        self._reserva.setFixedHeight(0)
        self._reserva.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        c.addWidget(self._reserva)
        c.addStretch(3)
        if al_detalles:
            self.detalles = Enlace(tr('Detalles y estado del sistema'), al_detalles, 13, color=ui.TEXT_MUTED,
                                   color_hover=ui.ACCENT_CLARO, subrayada=False, peso='medio')
            c.addWidget(self.detalles, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setMinimumHeight(420)

    # -- la escena 3D de fondo ----------------------------------------------------
    ALTO_ETIQUETAS = 34
    CORTO = {'timeline': tr('Trayendo el timeline'), 'voz': tr('Transcribiendo'), 'ia': tr('IA y palabras'), 'diseno': tr('Diseño de captions'),
             'sfx': tr('Efectos de sonido'), 'resolve': tr('Colocando')}

    final_cancelable = False                    # v5.4.47: GO sin Resolve (grabar el video) se puede cancelar hasta el final; colocar en Resolve no

    def renombrar_paso(self, clave, largo, corto):
        """v5.4.47: cambia el texto de un paso antes de empezar (GO sin Resolve: «Grabar el video» en vez de «Colocar en el timeline»)."""
        self.PASOS = tuple((c, largo if c == clave else t) for c, t in self.PASOS)
        self.CORTO = dict(self.CORTO, **{clave: corto})
        try:
            self.pasos.pasos = [(c, largo if c == clave else t) for c, t in self.pasos.pasos]
            self.pasos.update()
        except Exception:
            pass
        if self.escena is not None:
            for p in getattr(self.escena, '_pasos', None) or []:
                if p.get('clave') == clave:
                    p['texto'] = largo

    def conectar_escena(self, escena):
        self.escena = escena
        escena.poner_pasos(self.PASOS)
        escena.proveedor = self.geometria_escena
        escena.etiquetas_ocultas.connect(self._quitar_reserva)
        self.boton.seguir_a(escena)

    def geometria_escena(self):
        """(centro de la esfera, radio, rectángulo de las etiquetas) en coordenadas de la escena."""
        fondo = self.escena.parentWidget()
        centro = self.boton.mapTo(fondo, self.boton.rect().center())
        radio = self.boton.width() * (0.62 if self.boton.estado == 'trabajando' else 0.50)
        arriba = self._reserva.mapTo(fondo, self._reserva.rect().topLeft())
        cx = self._reserva.mapTo(fondo, self._reserva.rect().center()).x()
        alto = len(self.PASOS) * self.ALTO_ETIQUETAS
        if self._reserva.height() > 0:                    # con las etiquetas a la vista, la esfera no las pisa
            radio = min(radio, max(110.0, arriba.y() - centro.y() - 22.0))
        return QPointF(centro), float(radio), QRectF(cx - 240, arriba.y(), 480, alto)

    def _poner_reserva(self, alto):
        if self._reserva.height() != alto:
            self._reserva.setFixedHeight(int(alto))

    def _quitar_reserva(self):
        if self.boton.estado != 'trabajando':
            self._poner_reserva(0)
            self._relayout()

    def explosion_final(self, luego):
        """100 %: la esfera estalla y, en el pico, empieza la colocación directa en la línea de tiempo."""
        if self.escena is not None:
            self.escena.explotar(luego)
        else:
            luego()

    def _pulsado(self):
        self.pulso.emit(self.boton.centro_global())
        self.go.emit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self):
        # trabajando, la lista de pasos necesita sitio: el boton cede
        h, w = self.height(), self.width()
        trabajando = self.boton.estado == 'trabajando'
        reserva = self._reserva.height()
        util = max(200, h - reserva - (84 if trabajando else 110) - self._reserva_final)
        self.boton.poner_lado(min(util * (1.0 if trabajando else 0.98), h * (0.60 if trabajando else 0.60), w * 0.52))
        self.linea.setFixedWidth(int(max(300, min(920, w - 60))))

    def empezar(self):
        import time as _t
        self._inicio_t = _t.time()
        self._ficha += 1
        self._reserva_final = 0
        self.resumen.hide()
        self.salida.ocultar()
        self.titulo.configure(text=tr('Trabajando…'))
        self.paso_fallido = None
        self.estimador.empezar()
        self.boton.poner_estado('trabajando', centro=tr('Preparando'))
        self.boton.poner_progreso(0.0)
        self.boton.poner_eta(self.estimador.eta_texto())
        self._reloj_eta.start()
        self.opciones.hide()
        self.linea.poner_color('#D3E0F5')           # se lee aunque la esfera brille detrás
        self.pasos.entrar()
        botones = []
        if self.al_pausar:
            botones.append((tr('Pausar'), self.al_pausar, 'neutro'))
        if self.al_cancelar:
            botones.append((tr('Cancelar'), self.al_cancelar, 'fantasma'))
        self.salida.configurar(botones)
        self._b_pausa = self.salida.capa.itemAt(0).widget() if (botones and self.al_pausar) else None
        if botones:
            self.salida.mostrar()
            self._reserva_final = 52
        self._poner_reserva(len(self.PASOS) * self.ALTO_ETIQUETAS + 14)
        if self.escena is not None:
            self.escena.empezar()
        self._relayout()

    def poner_pausa(self, en_pausa):
        """«Pausar» ↔ «Reanudar» (y el título lo dice)."""
        if self._b_pausa is not None and ui.vivo(self._b_pausa):
            self._b_pausa.setText(tr('Reanudar') if en_pausa else tr('Pausar'))
        if self.boton.estado == 'trabajando':
            self.titulo.configure(text=tr('En pausa') if en_pausa else tr('Trabajando…'))

    def cancelado(self, texto):
        """El usuario canceló GO: sin alarma (no es un error), con «Reanudar»: lo ya hecho (la voz, en la caché) se conserva."""
        import time as _t
        self._reloj_eta.stop()
        self._ficha += 1
        self._t_fin = _t.time()
        self.paso_fallido = None
        if self.escena is not None:
            self.escena.reposo()
        self.boton.poner_estado('listo')
        self.titulo.configure(text=tr('GO cancelado'))
        self.linea.poner_color(ui.TEXT_MUTED)
        self.linea.configure(text=texto)
        self.opciones.show()
        self.resumen.hide()
        self.salida.configurar([(tr('Reanudar'), self._pulsado, 'primario')])
        self.salida.mostrar()
        self._reserva_final = 52
        self._relayout()

    def paso(self, clave, estado='activo', detalle=None):
        if clave == 'resolve' and estado == 'activo' and self._reserva_final and not self.final_cancelable:   # colocando en Resolve ya no se puede parar: fuera «Pausar / Cancelar»
            self.salida.ocultar()
            self._reserva_final = 0
            self._relayout()
        self.pasos.marcar(clave, estado, detalle)
        self.estimador.paso(clave, estado)
        if self.escena is not None:
            self.escena.paso(clave, estado, detalle)
        if estado == 'activo':
            n, total = self.estimador.numero_de_paso(clave)
            nombre = self.CORTO.get(clave) or dict(self.PASOS).get(clave, '')
            self.boton.poner_estado('trabajando', centro=(f'{nombre} · {n}/{total}' if n else nombre))
            self.boton.poner_fase(clave)
            if self.escena is not None:
                self.escena.poner_fase(clave)
        orden = [k for k, _ in self.PASOS]
        if clave in orden and estado in ('activo', 'hecho', 'saltado'):
            self._tic_eta()

    def avance_dentro(self, clave, fraccion):
        """El progreso DENTRO de un paso (transcribir, IA) mueve el anillo."""
        self.estimador.dentro(clave, fraccion)
        self._tic_eta()

    def estimar_duracion(self, segundos):
        """La duración del audio / video (la manda el hilo de trabajo en cuanto la conoce): los tiempos esperados de cada paso dependen de ella."""
        self.estimador.duracion(segundos)
        self._tic_eta()

    def _tic_eta(self):
        """Cada medio segundo: el porcentaje sigue al reloj dentro del paso y debajo del porcentaje sale lo que falta."""
        if self.boton.estado != 'trabajando':
            self._reloj_eta.stop()
            return
        f = self.estimador.fraccion()
        self.boton.poner_progreso(f)
        self.boton.poner_eta(self.estimador.eta_texto())
        if self.escena is not None:
            self.escena.progreso(f)

    def terminar(self, ok, texto, stats=None):
        """El final. stats: [(valor, etiqueta, 'n'|'t')] para los contadores. Con avisos el orbe se pone ámbar; con error se apaga y se
        propone un primer paso concreto."""
        import registro
        import time as _t
        self._reloj_eta.stop()
        if ok:
            self.estimador.guardar()
        nuevos = [e for e in registro.registro().lista() if e.tiempo >= self._inicio_t]
        n_av = sum(1 for e in nuevos if e.nivel == 'aviso')
        errores = [e for e in nuevos if e.nivel == 'error']
        tono = 'aviso' if (ok and n_av) else 'ok'
        self._t_fin = _t.time()
        if self.escena is not None:
            self.escena.terminar(ok, tono)
        self.boton.poner_estado('hecho' if ok else 'error', tono=tono)
        if ok:
            self.boton.poner_progreso(1.0)
            QTimer.singleShot(120 + int(self.boton.CARGA * 1000), lambda: self.celebrar.emit(self.boton.centro_global()) if ui.vivo(self) else None)
        if ok:
            self.titulo.configure(text=tr('¡Listo, con avisos!') if n_av else tr('¡Listo!'))
            self.linea.configure(text=(texto + '  ·  ' + (tr('1 aviso en el Registro') if n_av == 1 else tr('{n} avisos en el Registro', n=n_av))) if n_av else texto)
        else:
            self.titulo.configure(text=tr('No se pudo terminar'))
            consejo = ''
            if errores:
                try:
                    import registro_ayuda
                    a = registro_ayuda.explicar(errores[-1])
                    consejo = (a.titulo + '. ' + (tr('Prueba esto: {p}', p=a.pasos[0]) if a.pasos else '')).strip()
                    if self.paso_fallido in self.CORTO:
                        consejo = tr('Falló en «{p}»: ', p=self.CORTO[self.paso_fallido]) + consejo
                except Exception:
                    consejo = ''
            self.linea.configure(text=consejo or __import__('i18n').tr_libre(texto))
        self.opciones.show()
        self._relayout()
        # después del cierre: los contadores y los botones de salida entran con calma
        ficha = self._ficha
        botones = []
        if ok:
            if self.al_ver_resolve:
                botones.append((tr('Ver en Resolve'), self.al_ver_resolve, 'primario'))
            if self.al_editar:
                botones.append((tr('Editar palabras'), self.al_editar, 'neutro'))
            if n_av:
                botones.append((tr('Refrescar'), self._refrescar, 'neutro'))
        else:                                                    # v5.5.4 (pedido del usuario): «Refrescar» en vez de «Ver el Registro»
            botones.append((tr('Refrescar'), self._refrescar, 'primario'))
            botones.append((tr('Intentar de nuevo'), self._pulsado, 'neutro'))
        self.salida.configurar(botones)
        if ok and stats:
            self.resumen.poner(stats)

        def entrar():
            if ficha != self._ficha or not ui.vivo(self):
                return
            extra = 0
            if ok and stats and self.resumen._items:
                self.resumen.show()
                self.resumen.animar()
                extra += self.resumen.height() + 6
            if botones:
                self.salida.mostrar()
                extra += 52
            if self.escena is not None and ok:
                self.escena.ocultar_etiquetas()                  # la lista de pasos cede el sitio a los contadores
            self._reserva_final = extra
            self._relayout()
        QTimer.singleShot(1300 if ok else 700, entrar)
        if ok:
            QTimer.singleShot(14000, lambda: self._volver_a_reposo(ficha))

    def _abrir_registro(self):
        try:
            import registro_ui
            registro_ui.abrir_registro(self.window())
        except Exception:
            pass

    def _refrescar(self):
        """v5.5.4: Inicio vuelve a su estado limpio (el orbe en reposo, sin el final de GO) y sin procesos: las IA locales sueltan la GPU (en un hilo:
        cerrarlas puede tardar unos segundos). El Registro sigue en su sitio de la barra."""
        def soltar():
            try:
                import edicion_pro
                edicion_pro.soltar_gpu()
            except Exception:
                pass
        import threading
        threading.Thread(target=soltar, daemon=True, name='refrescar-soltar-gpu').start()
        self.reposo(self._texto_reposo or tr('Pulsa GO para otro.'), forzar=True, tono=getattr(self, '_tono_reposo', None))

    def _volver_a_reposo(self, ficha):
        """Pasado un rato del final: el orbe vuelve solo al reposo (la palomita se desvanece mientras reaparece la gema)."""
        if ficha != self._ficha or not ui.vivo(self) or self.boton.estado != 'hecho':
            return
        self.reposo(self._texto_reposo or tr('Pulsa GO para otro.'), forzar=True, tono=getattr(self, '_tono_reposo', None))

    def reposo(self, texto, listo=True, forzar=False, tono=None):
        """tono: None (gris), 'ok' (verde), 'aviso' (ámbar) o 'error' (rojo): el color de la línea (v5.5: dice qué Resolve hay y si puede trabajar)."""
        if self.boton.estado in ('trabajando',):
            return
        self._reloj_eta.stop()
        self._texto_reposo = texto
        self._tono_reposo = tono
        import time as _t
        # el refresco periódico de la app no debe borrar el final (contadores, botones) nada más aparecer
        if not forzar and self.boton.estado in ('hecho', 'error') and _t.time() - getattr(self, '_t_fin', 0.0) < (14.0 if self.boton.estado == 'hecho' else 45.0):
            return
        self._ficha += 1
        self._reserva_final = 0
        self.resumen.hide()
        self.salida.ocultar()
        if self.escena is not None:
            self.escena.reposo()
        self.boton.poner_estado('listo' if listo else 'apagado')
        self.linea.poner_color({'ok': ui.VERDE, 'aviso': ui.AMBAR, 'error': ui.ROJO}.get(tono, ui.TEXT_MUTED))
        self.titulo.configure(text=tr('Un clic y listo'))
        self.linea.configure(text=texto)
        self.opciones.show()
        self._relayout()


# ---------------------------------------------------------------------------
class VistaPreviaGo(QFrame):
    """«Así quedará en tu timeline»: los bloques con su estilo sobre los
    fotogramas reales del timeline (MCP), pasando solos; abajo «Lanzar al
    timeline» (se lanza solo al terminar la cuenta) o «Revisar en el editor»."""
    CUENTA = 12

    def __init__(self, ejemplos, resumen, al_lanzar, al_editor):
        super().__init__()
        self.setObjectName('panelAjustes')
        self.setStyleSheet(ui.traducir_hoja('QFrame#panelAjustes { background-color: #0B111D; border: 1px solid #22324F; border-radius: 22px; }'))
        self._ejemplos = ejemplos      # [(QImage|None, lineas, texto_tiempo)]
        self._i = 0
        self._al_lanzar = al_lanzar
        self._al_editor = al_editor
        self._capa = None
        self._cuenta = self.CUENTA
        c = QVBoxLayout(self)
        c.setContentsMargins(40, 30, 40, 30)
        c.setSpacing(14)
        import ajustes_ui
        c.addWidget(ajustes_ui._cabecera(tr('Vista previa · IA'), tr('Así quedará en tu timeline'), self._editor, tam=30))
        self.marco = MarcoVista(alto_min=360, aprox=True)
        c.addWidget(self.marco, 1)
        self._efecto = QGraphicsOpacityEffect(self.marco)
        self._efecto.setOpacity(1.0)
        self.marco.setGraphicsEffect(self._efecto)
        fila, cf = caja_h(espacio=10)
        self.donde = Etiqueta('', 13, color=ui.TEXT_MUTED)
        cf.addWidget(self.donde)
        cf.addStretch(1)
        self.puntos = Etiqueta('', 16, color=ui.ACCENT_CLARO)
        cf.addWidget(self.puntos)
        c.addWidget(fila)
        # v5.2: los chips saltan de linea si no caben (pantallas chicas, mas datos)
        chips = QWidget()
        cc = ui.FlujoCapa(chips, 10, 8)
        for texto in resumen:
            ch = Etiqueta(texto, 13, peso='medio', color='#E0EBFB')
            aviso = texto.startswith(tr('Ojo:').rstrip(':'))
            ch.setStyleSheet(ui.traducir_hoja('QLabel { background-color: %s; border: 1px solid %s; border-radius: 12px; padding: 5px 12px; }'
                                              % (('#3A2A10', '#F5B84B') if aviso else ('#111D33', '#22324F'))))
            cc.addWidget(ch)
        c.addWidget(chips)
        botones, cb = caja_h(espacio=12)
        self.aviso = Etiqueta('', 14, color=ui.TEXT_MUTED)
        cb.addWidget(self.aviso)
        cb.addStretch(1)
        cb.addWidget(Boton(tr('Revisar en el editor'), self._editor, tipo='neutro', alto=52, ancho=210, tam=16, negrita=True))
        self.lanzar = Boton(tr('Lanzar al timeline  ▶'), self._lanzar, tipo='primario', alto=52, ancho=250, tam=16, negrita=True)
        cb.addWidget(self.lanzar)
        c.addWidget(botones)
        self._fundido = _anim(self, 420, self._al_fundir, curva=QEasingCurve.Type.InOutCubic)
        self._reloj = QTimer(self)
        self._reloj.setInterval(1000)
        self._reloj.timeout.connect(self._tic)
        self._pase = QTimer(self)
        self._pase.setInterval(2400)
        self._pase.timeout.connect(self._siguiente)
        self._mostrar(0)

    def _mostrar(self, i):
        if not self._ejemplos:
            return
        self._i = i % len(self._ejemplos)
        ejemplo = self._ejemplos[self._i]
        imagen, lineas, donde = ejemplo[:3]
        real = len(ejemplo) > 3 and bool(ejemplo[3])
        # v5.2: un render real de Resolve ya trae los subtitulos: no se dibujan encima
        self.marco.poner_fondo(imagen, real=real)
        self.marco.poner([] if real else lineas)
        self.donde.configure(text=donde)
        self.puntos.configure(text=' '.join('●' if k == self._i else '○' for k in range(len(self._ejemplos))))

    def _siguiente(self):
        self._fundido.stop()
        self._fundido.start()

    def _al_fundir(self, v):
        v = float(v)
        if v < 0.5:
            self._efecto.setOpacity(1 - v * 2)
        else:
            if not getattr(self, '_cambiado', False):
                self._cambiado = True
                self._mostrar(self._i + 1)
            self._efecto.setOpacity((v - 0.5) * 2)
        if v >= 1.0:
            self._cambiado = False

    def _tic(self):
        self._cuenta -= 1
        if self._cuenta <= 0:
            self._lanzar()
            return
        self.aviso.configure(text=tr('Se lanza solo en {n} s', n=self._cuenta))

    def mousePressEvent(self, e):
        # tocar la vista previa para mirarla con calma detiene la cuenta
        if self._reloj.isActive():
            self._reloj.stop()
            self.aviso.configure(text=tr('Cuenta detenida: lanza cuando quieras.'))
        super().mousePressEvent(e)

    def _lanzar(self):
        self._parar()
        self.cerrar()
        if self._al_lanzar:
            self._al_lanzar()

    def _editor(self):
        self._parar()
        self.cerrar()
        if self._al_editor:
            self._al_editor()

    def _parar(self):
        self._reloj.stop()
        self._pase.stop()

    def abrir(self, ventana):
        import ajustes_ui

        def posicion(ancho_v, alto_v, _panel):
            ancho = min(1100, ancho_v - 80)
            alto = min(820, alto_v - 60)
            from PySide6.QtCore import QRect
            return QRect((ancho_v - ancho) // 2, (alto_v - alto) // 2, ancho, alto)
        self._capa = ajustes_ui.CapaModal(ventana, self, cerrar_fuera=False, posicion=posicion)
        self.aviso.configure(text=tr('Se lanza solo en {n} s', n=self._cuenta))
        self._reloj.start()
        if len(self._ejemplos) > 1:
            self._pase.start()

    def cerrar(self):
        if self._capa is not None and ui.vivo(self._capa):
            self._capa.cerrar()
