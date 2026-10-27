# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_ui.py — la página SONIDO = «AI Sound Director» (fase 6): la IA hace el 95 % del sonido; el usuario lo dirige (5 %).
"""
Al pulsar SONIDO se abre esta página directamente (la de antes —Simple / Emojis / Edición PRO— ya no se ve; su código sigue como motor interno).
v5.42 (diseño C elegido por el usuario: «la página de sonido me estresa»): nada técnico a la vista. Escuchas y eliges.

    cabecera     «Sonido», el video y su tema, y una pastilla con el estado (al día en Resolve / cambios sin aplicar)
    video        el cuadro del video en su formato, con ▶ y «Antes | Con sonido» (la previa del tramo, como antes)
    versiones    Suave · Cinemática (la que diseñó la IA, recomendada) · Con energía: cada una es un juego de los controles de siempre
                 (estilo, intensidad, densidad, música); elegirla o darle ▶ la rehace y deja los cambios pendientes de «Aplicar a Resolve»
    a mano       plegado: interruptor del director, línea de sonido con su inspector y los seis controles

Todo lo que cuesta (leer el estado, rehacer una versión, mezclas A/B, el cuadro del video, Resolve) va por correr_en_hilo; sin globos ni avisos
flotantes: una línea de estado. El motor: director_sonido_sesion.
"""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGridLayout, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget

import qt_kit as ui
from qt_kit import Boton, Combo, Enlace, Etiqueta, IconoEstado, Interruptor, Menu, Segmentado, StringVar, Tarjeta, caja_h
from qt_kit import QColor
from i18n import tr

TEXT_MUTED = ui.TEXT_MUTED
COLOR_TIPO = {'golpe': '#F5B84B', 'whoosh': '#00C8FF', 'giro': '#7FDBFF', 'riser': '#B388FF', 'trazo': '#4ADE80', 'acento': '#FFB86B',
              'tick': '#4589FF', 'pop': '#FF8FB1'}
OPCIONES = {   # control → [(valor, etiqueta)]
    'estilo': [('auto', 'Auto'), ('limpio', 'Limpio'), ('cinematico', 'Cinemático'), ('energico', 'Enérgico'), ('minimo', 'Mínimo')],
    'intensidad': [('auto', 'Auto'), ('poco', 'Suave'), ('medio', 'Media'), ('mucho', 'Potente')],
    'densidad': [('auto', 'Auto'), ('poco', 'Mínima'), ('medio', 'Media'), ('mucho', 'Rica')],
    'voz': [('auto', 'Auto'), ('poco', 'Equilibrio'), ('medio', 'Alta'), ('mucho', 'Máxima')],
    'musica': [('auto', 'Auto'), ('nada', 'Sin'), ('poco', 'Suave'), ('medio', 'Media'), ('mucho', 'Enérgica')],
    'ambiente': [('auto', 'Auto'), ('nada', 'Sin'), ('poco', 'Mínimo'), ('medio', 'Sutil'), ('mucho', 'Inmersivo')],
}
TITULO_CONTROL = {'estilo': 'Estilo', 'intensidad': 'Intensidad', 'densidad': 'Densidad de sonidos', 'voz': 'Prioridad de la voz', 'musica': 'Música',
                  'ambiente': 'Ambiente'}
# las tres versiones: (clave, nombre, qué es, controles). Los que no nombra quedan en Auto; voz y ambiente no los tocan (son del usuario)
VERSIONES = (
    ('suave', 'Suave', 'Pocos efectos · música tranquila · la voz manda', {'estilo': 'limpio', 'intensidad': 'poco', 'densidad': 'poco', 'musica': 'poco'}),
    ('ia', 'Cinemática', 'La que diseñó la IA: golpes en los textos grandes · música que acompaña', {}),
    ('energia', 'Con energía', 'Más efectos · música con ritmo', {'estilo': 'energico', 'intensidad': 'mucho', 'densidad': 'mucho', 'musica': 'mucho'}),
)
CLAVES_VERSION = ('estilo', 'intensidad', 'densidad', 'musica')


def _tiempo(t):
    t = max(0.0, float(t or 0.0))
    return f'{int(t // 60)}:{t % 60:04.1f}'.replace('.', ',')


def version_de(controles):
    """La versión que dicen los controles guardados (o None si se ajustaron a mano)."""
    c = controles or {}
    for clave, _n, _d, preset in VERSIONES:
        if all(c.get(k, 'auto') == preset.get(k, 'auto') for k in CLAVES_VERSION):
            return clave
    return None


def cuadro_del_video(ruta, ancho_max=540):
    """(En un hilo) un cuadro del video a ~1/4 de su duración como QImage (QImage sí se puede crear fuera del hilo de la interfaz)."""
    import av
    with av.open(str(ruta)) as c:
        vs = c.streams.video[0]
        dur = float(c.duration or 0) / 1e6
        if dur > 2:
            c.seek(int(dur * 0.25 * 1e6))
        for f in c.decode(video=0):
            rot = 0
            try:
                rot = int(round(float(f.rotation or 0))) % 360
            except Exception:
                pass
            img = f.to_image().convert('RGB')
            if rot:
                img = img.rotate(rot, expand=True)
            if img.width > ancho_max:
                img = img.resize((ancho_max, max(1, round(img.height * ancho_max / img.width))))
            datos = img.tobytes()
            q = QImage(datos, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            return q.copy()
    return None


# ====================================================================================== piezas
class Pildora(QWidget):
    """La pastilla de estado de la cabecera: punto con brillo + texto, del color del estado."""
    def __init__(self, padre=None):
        super().__init__(padre)
        self._texto, self._color = '', ui.VERDE
        self.setFont(ui.fuente(13, peso='medio'))
        self.setFixedHeight(36)

    def poner(self, texto, color):
        self._texto, self._color = str(texto or ''), color
        self.setFixedWidth(int(self.fontMetrics().horizontalAdvance(self._texto)) + 52 if self._texto else 0)
        self.setAccessibleName(self._texto)
        self.update()

    def paintEvent(self, _e):
        if not self._texto:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._color)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        fondo = QColor(c)
        fondo.setAlpha(30)
        borde = QColor(c)
        borde.setAlpha(95)
        p.setPen(QPen(borde, 1))
        p.setBrush(fondo)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        halo = QColor(c)
        halo.setAlpha(70)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QRectF(13, self.height() / 2 - 7, 14, 14))
        p.setBrush(c)
        p.drawEllipse(QRectF(16, self.height() / 2 - 4, 8, 8))
        p.setPen(c)
        p.drawText(QRectF(34, 0, self.width() - 40, self.height()), int(Qt.AlignmentFlag.AlignVCenter), self._texto)
        p.end()


def _triangulo(p, cx, cy, lado, color):
    """El ▶ de reproducir, centrado ópticamente."""
    ruta = QPainterPath()
    ruta.moveTo(cx - lado * 0.38, cy - lado * 0.5)
    ruta.lineTo(cx + lado * 0.62, cy)
    ruta.lineTo(cx - lado * 0.38, cy + lado * 0.5)
    ruta.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(ruta)


class VistaVideo(QWidget):
    """El cuadro del video en su formato (vertical como un móvil, horizontal como una pantalla) con un ▶ encima. Clic = oír."""
    clic = Signal()

    def __init__(self, padre=None):
        super().__init__(padre)
        self._img = None
        self._pm = None
        self._activo = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr('Reproducir el tramo'))
        self._formato(True)

    def _formato(self, vertical):
        self.setFixedSize(252, 448) if vertical else self.setFixedSize(360, 203)

    def poner(self, imagen):
        self._img = imagen
        self._pm = None
        if imagen is not None and not imagen.isNull():
            self._formato(imagen.height() >= imagen.width())
        self.update()

    def setEnabled(self, si):
        super().setEnabled(si)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clic.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.isEnabled():
            self.clic.emit()
            e.accept()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radio = 26 if self.height() > self.width() else 16
        marco = QPainterPath()
        marco.addRoundedRect(r, radio, radio)
        p.setClipPath(marco)
        p.fillRect(r, QColor('#0B1424'))
        if self._img is not None and not self._img.isNull():
            dpr = self.devicePixelRatioF()
            clave = (self.width(), self.height(), round(dpr, 2))
            if self._pm is None or self._pm[0] != clave:                 # (escalar UNA vez: «cubrir», recortando lo que sobra)
                im = self._img.scaled(int(self.width() * dpr), int(self.height() * dpr), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                      Qt.TransformationMode.SmoothTransformation)
                pm = QPixmap.fromImage(im)
                pm.setDevicePixelRatio(dpr)
                self._pm = (clave, pm)
            pm = self._pm[1]
            w, h = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            p.drawPixmap(QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), pm, QRectF(pm.rect()))
        p.setClipping(False)
        p.setPen(QPen(QColor(ui.BORDER_COLOR), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, radio, radio)
        cx, cy = self.width() / 2, self.height() / 2                     # el ▶ en un círculo oscuro
        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.setBrush(QColor(8, 12, 20, 165 if self.isEnabled() else 110))
        p.drawEllipse(QRectF(cx - 32, cy - 32, 64, 64))
        _triangulo(p, cx, cy, 22, '#FFFFFF' if self.isEnabled() else '#8D9BB5')
        p.end()


class TarjetaVersion(QWidget):
    """Una versión del sonido: ▶, nombre (con «Recomendada»), qué es, la voz del video y —en la elegida— dónde suena cada efecto.
    Clic en ▶ = oírla (si no es la elegida, primero se rehace); clic en el resto = elegirla."""
    elegir = Signal(str)
    oir = Signal(str)
    ALTO = 132

    def __init__(self, clave, nombre, descripcion, recomendada=False, padre=None):
        super().__init__(padre)
        self.clave, self.nombre, self.descripcion = clave, nombre, descripcion
        self._recomendada = bool(recomendada)
        self._elegida = False
        self._trabajando = False
        self._hover = False
        self._res = {}
        self.setFixedHeight(self.ALTO)
        self.setMinimumWidth(320)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr('Versión {n}', n=nombre))

    def poner(self, res, elegida, descripcion=None, trabajando=False):
        self._res, self._elegida, self._trabajando = res or {}, bool(elegida), bool(trabajando)
        if descripcion:
            self.descripcion = descripcion
        self.setAccessibleDescription(self.descripcion + (' · ' + tr('elegida') if elegida else ''))
        self.update()

    def elegida(self):
        return self._elegida

    def _zona_play(self):
        return QRectF(20, 20, 44, 44)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def setEnabled(self, si):
        super().setEnabled(si)
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return
        if self._zona_play().adjusted(-6, -6, 6, 6).contains(e.position()):
            self.oir.emit(self.clave)
        else:
            self.elegir.emit(self.clave)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.isEnabled():
            self.oir.emit(self.clave)
        elif e.key() == Qt.Key.Key_Space and self.isEnabled():
            self.elegir.emit(self.clave)
        else:
            super().keyPressEvent(e)
            return
        e.accept()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        activa = self.isEnabled()
        r = QRectF(1.5, 1.5, w - 3, h - 3)
        if self._elegida:                                                # el anillo de la elegida
            anillo = QColor(ui.ACCENT_CLARO)
            anillo.setAlpha(40)
            p.setPen(QPen(anillo, 6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 18, 18)
        p.setPen(QPen(QColor(ui.ACCENT_CLARO if self._elegida else ('#2D4677' if self._hover and activa else ui.BORDER_COLOR)), 2 if self._elegida else 1))
        p.setBrush(QColor(ui.CARD_COLOR))
        p.drawRoundedRect(r, 18, 18)
        z = self._zona_play()                                            # ▶
        p.setPen(QPen(QColor(ui.BORDER_COLOR), 1))
        p.setBrush(QColor(ui.CARD_2))
        p.drawEllipse(z)
        _triangulo(p, z.center().x(), z.center().y(), 14, '#FFFFFF' if activa else '#55617A')
        x = 80                                                           # nombre (+ «Recomendada») y qué es
        p.setFont(ui.fuente(16, peso='negrita'))
        p.setPen(QColor('#FFFFFF' if activa else '#8D9BB5'))
        p.drawText(QRectF(x, 20, w - x - 60, 24), int(Qt.AlignmentFlag.AlignVCenter), tr(self.nombre))
        if self._recomendada:
            xb = x + p.fontMetrics().horizontalAdvance(tr(self.nombre)) + 12
            p.setFont(ui.fuente(11, peso='medio'))
            tb = tr('Recomendada')
            ancho = p.fontMetrics().horizontalAdvance(tb) + 20
            fondo = QColor(ui.ACCENT_CLARO)
            fondo.setAlpha(38)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fondo)
            p.drawRoundedRect(QRectF(xb, 21, ancho, 22), 11, 11)
            p.setPen(QColor(ui.ACCENT_CLARO))
            p.drawText(QRectF(xb, 21, ancho, 22), int(Qt.AlignmentFlag.AlignCenter), tb)
        p.setFont(ui.fuente(13))
        p.setPen(QColor(ui.ACCENT_CLARO if self._trabajando else TEXT_MUTED))
        texto = tr('Preparando esta versión…') if self._trabajando else tr(self.descripcion)
        p.drawText(QRectF(x, 46, w - x - 60, 20), int(Qt.AlignmentFlag.AlignVCenter), p.fontMetrics().elidedText(texto, Qt.TextElideMode.ElideRight, w - x - 60))
        c = QRectF(w - 44, 31, 22, 22)                                   # ✓ de la elegida / círculo vacío
        if self._elegida:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ui.ACCENT_CLARO))
            p.drawEllipse(c)
            p.setPen(QPen(QColor('#FFFFFF'), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            ruta = QPainterPath()
            ruta.moveTo(c.left() + 6.2, c.center().y() + 0.3)
            ruta.lineTo(c.left() + 9.6, c.center().y() + 3.6)
            ruta.lineTo(c.right() - 5.8, c.top() + 7.4)
            p.drawPath(ruta)
        else:
            p.setPen(QPen(QColor(ui.BORDER_COLOR), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c.adjusted(1, 1, -1, -1))
        self._pintar_linea(p, QRectF(20, 82, w - 40, 32), activa)
        p.end()

    def _pintar_linea(self, p, r, activa):
        """La voz del video (tramos) y, en la elegida, cada efecto que suena (puntos ámbar)."""
        d = self._res
        dur = float(d.get('duracion') or 0.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0B1424'))
        p.drawRoundedRect(r, 8, 8)
        if dur <= 0:
            return
        x = lambda t: r.left() + 6 + max(0.0, min(1.0, float(t or 0) / dur)) * (r.width() - 12)
        voz = QColor('#1F5FA8')
        voz.setAlpha(210 if self._elegida else 120)
        p.setBrush(voz)
        for a, b in (d.get('carriles') or {}).get('voz') or []:
            p.drawRoundedRect(QRectF(x(a), r.top() + 9, max(2.0, x(b) - x(a)), r.height() - 18), 3, 3)
        if not self._elegida or not activa:
            return
        for e in d.get('eventos') or []:
            if not e.get('suena'):
                continue
            cx = x(e.get('ancla'))
            p.setPen(QPen(QColor(ui.BG_COLOR), 2))
            p.setBrush(QColor(COLOR_TIPO.get(e.get('tipo'), ui.AMBAR)))
            p.drawEllipse(QRectF(cx - 5, r.center().y() - 5, 10, 10))


class LineaSonido(QWidget):
    """La línea de tiempo simple: VIDEO · VOZ · MÚSICA · AMBIENTE · SONIDOS IA · MOTIONS PRO (los sonidos de los motions de la PRO, rehechos por el
    director al colocarlos: se ven, no se eligen). Clic = elegir el evento más cercano (y el instante del A/B)."""
    elegido = Signal(object)                 # el evento (dict) o None
    IZQ, DER, ARRIBA, CARRIL, HUECO = 104, 14, 22, 24, 7
    CARRILES = ('VIDEO', 'VOZ', 'MÚSICA', 'AMBIENTE', 'SONIDOS IA', 'MOTIONS PRO')

    def __init__(self, padre=None):
        super().__init__(padre)
        self._d = {}
        self._sel = None
        self._hover = None
        self._cursor = 0.0
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(self.ARRIBA + len(self.CARRILES) * (self.CARRIL + self.HUECO) + 8)

    def poner(self, res, seleccion=None):
        self._d = res or {}
        self._sel = seleccion
        self.update()

    def cursor(self):
        return self._cursor

    def _x(self, t):
        dur = max(0.5, float(self._d.get('duracion') or 1.0))
        return self.IZQ + (float(t or 0.0) / dur) * max(10.0, self.width() - self.IZQ - self.DER)

    def _t(self, x):
        dur = max(0.5, float(self._d.get('duracion') or 1.0))
        return max(0.0, min(dur, (x - self.IZQ) / max(10.0, self.width() - self.IZQ - self.DER) * dur))

    def _y(self, i):
        return self.ARRIBA + i * (self.CARRIL + self.HUECO)

    def _cerca(self, x, y, siguiente=False):
        """El evento bajo el clic: de los bloques que lo contienen, el de ancla más cercana y, si empatan, el más corto (un riser que acaba en un golpe
        no tapa al golpe); si ninguno lo contiene, el ancla más cercana. `siguiente`: otro clic en el mismo sitio pasa al siguiente solapado."""
        if y < self._y(4) - 4 or y > self._y(5) - 2:
            return None
        visibles = [e for e in self._d.get('eventos') or [] if e.get('suena') or e.get('silenciado')]
        dentro = [e for e in visibles if self._x(e.get('t')) - 3 <= x <= max(self._x(e.get('t')) + 5, self._x(float(e.get('t') or 0) + float(e.get('dur') or 0))) + 3]
        if dentro:
            dentro.sort(key=lambda e: (round(abs(self._x(e.get('ancla')) - x) / 4.0), float(e.get('dur') or 0)))
            claves = [e.get('clave') for e in dentro]
            if siguiente and self._sel in claves:
                return dentro[(claves.index(self._sel) + 1) % len(dentro)]
            return dentro[0]
        mejor, dmin = None, 9.0
        for e in visibles:
            d = abs(self._x(e.get('ancla')) - x)
            if d < dmin:
                mejor, dmin = e, d
        return mejor

    def mouseMoveEvent(self, e):
        h = self._cerca(e.position().x(), e.position().y())
        if (h or {}).get('clave') != (self._hover or {}).get('clave'):
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self._d.get('hay'):
            return
        x = e.position().x()
        self._cursor = self._t(x)
        ev = self._cerca(x, e.position().y(), siguiente=True)
        if ev is not None:
            self._cursor = max(0.0, float(ev.get('ancla') or 0.0))
        self._sel = (ev or {}).get('clave')
        self.update()
        self.elegido.emit(ev)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        d = self._d
        car = d.get('carriles') or {}
        dur = float(d.get('duracion') or 0.0)
        p.setFont(ui.fuente(10, True))
        for i, nombre in enumerate(self.CARRILES):                       # fondos y nombres de los carriles
            y = self._y(i)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#0B1424'))
            p.drawRoundedRect(QRectF(self.IZQ, y, w - self.IZQ - self.DER, self.CARRIL), 6, 6)
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(QRectF(0, y, self.IZQ - 10, self.CARRIL), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), tr(nombre))
        if not d.get('hay') or dur <= 0:
            p.end()
            return
        p.setFont(ui.fuente(9))                                          # regla: cada 10 s
        p.setPen(QColor('#4A5A78'))
        paso = 10.0 if dur <= 120 else (30.0 if dur <= 600 else 120.0)
        t = 0.0
        while t <= dur + 0.01:
            x = self._x(t)
            p.drawLine(int(x), 14, int(x), 19)
            p.drawText(QRectF(x - 30, 0, 60, 13), int(Qt.AlignmentFlag.AlignCenter), _tiempo(t).split(',')[0])
            t += paso
        y0 = self._y(0)                                                  # VIDEO: cortes y captions (los que suenan, más vivos)
        p.setPen(QPen(QColor('#3A4C70'), 1))
        for tc in car.get('cortes') or []:
            p.drawLine(int(self._x(tc)), int(y0 + 3), int(self._x(tc)), int(y0 + self.CARRIL - 3))
        for t_c, dec, _txt in car.get('captions') or []:
            suena = dec not in ('LEAVE_SILENT',)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ui.AMBAR if suena else '#55617A'))
            r = 3.2 if suena else 2.0
            p.drawEllipse(QRectF(self._x(t_c) - r, y0 + self.CARRIL / 2 - r, 2 * r, 2 * r))
        y1 = self._y(1)                                                  # VOZ
        p.setBrush(QColor(0, 200, 255, 110))
        for a, b in car.get('voz') or []:
            p.drawRoundedRect(QRectF(self._x(a), y1 + 5, max(2.0, self._x(b) - self._x(a)), self.CARRIL - 10), 4, 4)
        y2 = self._y(2)                                                  # MÚSICA
        if car.get('musica'):
            p.setBrush(QColor(179, 136, 255, 120))
            for a, b, _q in car['musica']:
                p.drawRoundedRect(QRectF(self._x(a), y2 + 6, max(2.0, self._x(b) - self._x(a)), self.CARRIL - 12), 4, 4)
        else:
            p.setPen(QColor('#4A5A78'))
            p.drawText(QRectF(self.IZQ + 10, y2, 300, self.CARRIL), int(Qt.AlignmentFlag.AlignVCenter), tr('sin música'))
        y3 = self._y(3)                                                  # AMBIENTE: escenas
        for a, b, ctx, dec in car.get('ambiente') or []:
            x0, x1 = self._x(a), self._x(b)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(74, 222, 128, 70 if dec in ('ADD_SUBTLE_AMBIENCE', 'REPLACE_AMBIENCE') else 30))
            p.drawRoundedRect(QRectF(x0 + 1, y3 + 4, max(2.0, x1 - x0 - 2), self.CARRIL - 8), 4, 4)
            if x1 - x0 > 60:
                p.setPen(QColor('#9FB0CC'))
                p.drawText(QRectF(x0 + 6, y3, x1 - x0 - 8, self.CARRIL), int(Qt.AlignmentFlag.AlignVCenter), tr(str(ctx or '')))
        y4 = self._y(4)                                                  # SONIDOS IA
        for e in d.get('eventos') or []:
            if not (e.get('suena') or e.get('silenciado')):
                continue
            x = self._x(e.get('t'))
            ancho = max(5.0, self._x(float(e.get('t') or 0) + float(e.get('dur') or 0.2)) - x)
            color = QColor(COLOR_TIPO.get(e.get('tipo'), ui.ACCENT_CLARO))
            rect = QRectF(x, y4 + 4, ancho, self.CARRIL - 8)
            if e.get('silenciado'):
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#55617A'), 1, Qt.PenStyle.DashLine))
            else:
                color.setAlpha(230 if e.get('clave') in (self._sel, (self._hover or {}).get('clave')) else 170)
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect, 4, 4)
            if e.get('clave') == self._sel:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#FFFFFF'), 1.6))
                p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 5, 5)
            if e.get('bloqueado'):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#FFFFFF'))
                p.drawEllipse(QRectF(x + ancho / 2 - 2, y4 - 1, 4, 4))
        y5 = self._y(5)                                                  # MOTIONS PRO (rehechos por el director; los callados, en hueco)
        pro = d.get('pro_eventos') or []
        for t_p, dur_p, tipo_p, dec_p in pro:
            x = self._x(t_p)
            rect = QRectF(x, y5 + 6, max(4.0, self._x(float(t_p or 0) + float(dur_p or 0.2)) - x), self.CARRIL - 12)
            if dec_p == 'GENERATE':
                color = QColor(COLOR_TIPO.get(tipo_p, ui.ACCENT_CLARO))
                color.setAlpha(140)
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#55617A'), 1, Qt.PenStyle.DashLine))
            p.drawRoundedRect(rect, 3, 3)
        if not pro:
            p.setPen(QColor('#4A5A78'))
            p.drawText(QRectF(self.IZQ + 10, y5, 400, self.CARRIL), int(Qt.AlignmentFlag.AlignVCenter), tr('sin motions de la PRO en este GO'))
        xc = self._x(self._cursor)                                       # el instante del A/B
        p.setPen(QPen(QColor(255, 255, 255, 150), 1))
        p.drawLine(int(xc), int(self.ARRIBA - 4), int(xc), int(self._y(5) + self.CARRIL))
        p.end()


# ====================================================================================== la página
class PaginaDirector(QWidget):
    """La página SONIDO. `video` = función que da el video de Inicio; `offset` = función con el desplazamiento de GO en el timeline (Aplicar)."""

    def __init__(self, padre=None, video=None, offset=None):
        super().__init__(padre)
        self._video_fn = video or (lambda: '')
        self._offset_fn = offset or (lambda: 0)
        self._res = {}
        self._ev = None
        self._ocupado = False
        self._pintando = False
        self._cargando = False
        self._mensaje_estado = ''
        self._ancho_distribuido = None
        self._version_trabajando = None
        self._video_cuadro = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(14)
        # ---- cabecera: «Sonido», video · tema y la pastilla de estado
        cab, cc_ = caja_h(espacio=14)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(Etiqueta(tr('Sonido'), 24, peso='extra', color='#FFFFFF'))
        self._lbl_video = ui.Elidida('', 13, color=TEXT_MUTED)
        col.addWidget(self._lbl_video)
        cc_.addLayout(col, 1)
        self._pildora = Pildora()
        cc_.addWidget(self._pildora, 0, Qt.AlignmentFlag.AlignVCenter)
        capa.addWidget(cab)
        self._lbl_estado = Etiqueta(tr('Abre esta página después de GO para elegir cómo suena tu video.'), 12, color=TEXT_MUTED, envolver=True)
        capa.addWidget(self._lbl_estado)
        # ---- vacío (sin GO con el director todavía)
        self._vacio = Tarjeta(espacio=8, margenes=(22, 18, 22, 18))
        self._lbl_vacio = Etiqueta(tr('Haz GO con un video: la IA le pone sonido y aquí eliges la versión que más te guste.'), 14, color='#E0EBFB', envolver=True)
        self._vacio.capa.addWidget(self._lbl_vacio)
        capa.addWidget(self._vacio)
        # ---- el resto (solo con diseño)
        self._cuerpo = QWidget()
        cc = QVBoxLayout(self._cuerpo)
        cc.setContentsMargins(0, 0, 0, 0)
        cc.setSpacing(14)
        principal, cp = caja_h(espacio=24)
        izq = Tarjeta(espacio=14, margenes=(22, 22, 22, 22))
        self._vista = VistaVideo()
        self._vista.clic.connect(self._oir_vista)
        izq.capa.addWidget(self._vista, 0, Qt.AlignmentFlag.AlignHCenter)
        self._var_ab = StringVar(tr('Con sonido'))
        self._ab = Segmentado([tr('Antes'), tr('Con sonido')], self._var_ab, alto=40, tam=13, iguales=True)
        izq.capa.addWidget(self._ab)
        izq.capa.addStretch(1)
        cp.addWidget(izq, 0, Qt.AlignmentFlag.AlignTop)
        der = QVBoxLayout()
        der.setSpacing(14)
        der.addWidget(Etiqueta(tr('Escucha y elige la que más te guste'), 18, peso='negrita', color='#FFFFFF'))
        self._tarjetas = {}
        for clave, nombre, desc, _preset in VERSIONES:
            t = TarjetaVersion(clave, nombre, desc, recomendada=clave == 'ia')
            t.elegir.connect(self._elegir_version)
            t.oir.connect(self._oir_version)
            self._tarjetas[clave] = t
            der.addWidget(t)
        pie, cpie = caja_h(espacio=12)
        self._b_mano = Enlace(tr('Ajustar a mano'), self._alternar_mano, 14, color=ui.ACCENT_CLARO, color_hover='#FFFFFF', subrayada=False, peso='medio')
        cpie.addWidget(self._b_mano)
        cpie.addStretch(1)
        self._b_aplicar = Boton(tr('Aplicar a Resolve'), self._aplicar, tipo='primario', alto=44, tam=14, negrita=True)
        cpie.addWidget(self._b_aplicar)
        der.addWidget(pie)
        der.addStretch(1)
        cp.addLayout(der, 1)
        cc.addWidget(principal)
        # ---- «Ajustar a mano» (plegado): el director, la línea con su inspector y los controles de siempre
        self._mano = QWidget()
        cm = QVBoxLayout(self._mano)
        cm.setContentsMargins(0, 0, 0, 0)
        cm.setSpacing(12)
        on = Tarjeta(espacio=12, margenes=(20, 12, 20, 12), horizontal=True)
        on.capa.addWidget(Etiqueta(tr('AI Sound Director en los próximos GO'), 13, peso='medio', color='#E0EBFB'), 1)
        self._var_on = ui.BooleanVar(False)
        self._sw = Interruptor(tr('Activado'), self._var_on, self._cambio_on, tam=13, color='#E0EBFB')
        on.capa.addWidget(self._sw)
        cm.addWidget(on)
        zona = QWidget()
        self._zona_layout = QGridLayout(zona)
        self._zona_layout.setContentsMargins(0, 0, 0, 0)
        self._zona_layout.setSpacing(12)
        self._tarjeta_linea = lt = Tarjeta(espacio=8, margenes=(18, 14, 18, 14))
        fila, cf = caja_h(espacio=10)
        cf.addWidget(Etiqueta(tr('Línea de sonido'), 15, peso='medio', color='#FFFFFF'), 1)
        lt.capa.addWidget(fila)
        self._fila_resolve, cr = caja_h(espacio=8)
        self._ico_resolve = IconoEstado('ok')
        cr.addWidget(self._ico_resolve)
        self._lbl_resolve = Etiqueta('', 12, peso='medio', color='#E0EBFB', envolver=True)
        cr.addWidget(self._lbl_resolve, 1)
        lt.capa.addWidget(self._fila_resolve)
        self._lbl_destino = ui.Elidida('', 11, color=TEXT_MUTED)
        lt.capa.addWidget(self._lbl_destino)
        self._lbl_tramo = Etiqueta('', 11, color=TEXT_MUTED)
        lt.capa.addWidget(self._lbl_tramo)
        self._linea = LineaSonido()
        self._linea.elegido.connect(self._elegir)
        self._linea.setAccessibleName(tr('Línea de sonido. Usa la lista de eventos para seleccionar con el teclado.'))
        lt.capa.addWidget(self._linea)
        self._lbl_eventos = Etiqueta('', 12, peso='medio', color='#B4C0D6')
        lt.capa.addWidget(self._lbl_eventos)
        self._lista_eventos = QListWidget()
        self._lista_eventos.setFont(ui.fuente(12))
        self._lista_eventos.setFixedHeight(100)
        self._lista_eventos.setMinimumWidth(0)
        self._lista_eventos.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._lista_eventos.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._lista_eventos.setAccessibleName(tr('Eventos de sonido. Flechas para elegir y Enter para oír el momento.'))
        self._lista_eventos.currentItemChanged.connect(self._evento_de_lista)
        self._lista_eventos.itemActivated.connect(lambda _item: self._oir_evento())
        lt.capa.addWidget(self._lista_eventos)
        self._tarjeta_inspector = ins = Tarjeta(espacio=8, margenes=(18, 16, 18, 16))
        ins.capa.addWidget(Etiqueta(tr('Este sonido'), 13, peso='medio', color=TEXT_MUTED))
        self._lbl_ev = Etiqueta('', 16, peso='medio', color='#FFFFFF', envolver=True)
        self._lbl_diseno = Etiqueta('', 13, color=ui.ACCENT_CLARO, envolver=True)
        self._lbl_porque = Etiqueta('', 12, color='#B4C0D6', envolver=True)
        for w in (self._lbl_ev, self._lbl_diseno, self._lbl_porque):
            w.setMinimumWidth(0)
            w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            ins.capa.addWidget(w)
        cb = QGridLayout()
        cb.setSpacing(8)
        self._b_oir_ev = Boton(tr('▶  Oír'), self._oir_evento, tipo='fantasma', alto=32, tam=12)
        self._b_menos = Boton(tr('Menos…'), lambda: self._menu('menos'), alto=32, tam=12)
        self._b_mas = Boton(tr('Más…'), lambda: self._menu('mas'), alto=32, tam=12)
        self._b_regen = Boton(tr('Regenerar'), lambda: self._retocar('regenerar'), alto=32, tam=12)
        self._b_silencio = Boton(tr('Silenciar'), lambda: self._retocar('silenciar'), tipo='fantasma', alto=32, tam=12)
        self._b_bloq = Boton(tr('Bloquear'), lambda: self._retocar('bloquear'), tipo='fantasma', alto=32, tam=12)
        for i, b in enumerate((self._b_menos, self._b_mas, self._b_regen, self._b_oir_ev, self._b_silencio, self._b_bloq)):
            cb.addWidget(b, i // 2, i % 2)
        ins.capa.addLayout(cb)
        ins.capa.addStretch(1)
        self._botones_ev = (self._b_oir_ev, self._b_menos, self._b_mas, self._b_regen, self._b_silencio, self._b_bloq)
        self._zona_layout.addWidget(lt, 0, 0)
        self._zona_layout.addWidget(ins, 1, 0)
        cm.addWidget(zona)
        ctl = Tarjeta(espacio=10, margenes=(18, 14, 18, 14))
        ctl.capa.addWidget(Etiqueta(tr('Controles'), 15, peso='medio', color='#FFFFFF'))
        ctl.capa.addWidget(Etiqueta(tr('Para este video y próximos GO · En Auto decide la IA'), 11, color=TEXT_MUTED, envolver=True))
        self._controles_layout = QGridLayout()
        self._controles_layout.setHorizontalSpacing(16)
        self._controles_layout.setVerticalSpacing(10)
        self._vars, self._controles, self._grupos_control = {}, {}, []
        for k in OPCIONES:
            grupo = QWidget()
            g = QVBoxLayout(grupo)
            g.setContentsMargins(0, 0, 0, 0)
            g.setSpacing(4)
            g.addWidget(Etiqueta(tr(TITULO_CONTROL[k]), 12, color=TEXT_MUTED))
            self._vars[k] = StringVar(tr('Auto'))
            control = Combo([tr(t) for _v, t in OPCIONES[k]], self._vars[k], lambda etiqueta, k=k: self._cambio_control(k, etiqueta), alto=32, tam=12)
            control.setAccessibleName(tr(TITULO_CONTROL[k]))
            g.addWidget(control)
            self._controles[k] = control
            self._grupos_control.append(grupo)
        ctl.capa.addLayout(self._controles_layout)
        acciones, ca = caja_h(espacio=8)
        self._b_redisenar = Boton(tr('Crear otra variación'), self._redisenar, alto=34, tam=12)
        self._b_deshacer = Boton(tr('Volver a lo de la IA'), self._deshacer, tipo='fantasma', alto=34, tam=12)
        ca.addWidget(self._b_redisenar)
        ca.addWidget(self._b_deshacer)
        ca.addStretch(1)
        ctl.capa.addWidget(acciones)
        cm.addWidget(ctl)
        self._mano.hide()
        cc.addWidget(self._mano)
        capa.addWidget(self._cuerpo)
        capa.addStretch(1)                                           # (el sobrante, abajo: las tarjetas con su alto natural)
        self._acciones = (self._b_redisenar, self._b_aplicar, self._b_deshacer) + self._botones_ev
        self._distribuir()
        self._pintar_evento(None)
        self._cuerpo.hide()
        self._actualizar_disponibles()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._distribuir()

    def _distribuir(self):
        """Solo redistribuye widgets de esta página; no modifica el marco de la aplicación."""
        ancho = self.width()
        modo = (ancho >= 1000, 3 if ancho >= 740 else (2 if ancho >= 480 else 1))
        if self._ancho_distribuido == modo:
            return
        self._ancho_distribuido = modo
        lateral, columnas = modo
        for w in (self._tarjeta_linea, self._tarjeta_inspector):
            self._zona_layout.removeWidget(w)
        self._zona_layout.addWidget(self._tarjeta_linea, 0, 0)
        self._zona_layout.addWidget(self._tarjeta_inspector, 0 if lateral else 1, 1 if lateral else 0)
        self._zona_layout.setColumnStretch(0, 3 if lateral else 1)
        self._zona_layout.setColumnStretch(1, 2 if lateral else 0)
        for w in self._grupos_control:
            self._controles_layout.removeWidget(w)
        for c in range(3):
            self._controles_layout.setColumnStretch(c, 1 if c < columnas else 0)
        for i, w in enumerate(self._grupos_control):
            self._controles_layout.addWidget(w, i // columnas, i % columnas)

    def _alternar_mano(self):
        abierto = not self._mano.isVisible()
        self._mano.setVisible(abierto)
        self._b_mano.setText(tr('Ocultar ajustes') if abierto else tr('Ajustar a mano'))

    # ---------------------------------------------------------------- datos
    def video(self):
        try:
            return str(self._video_fn() or '')
        except Exception:
            return ''

    def _video_mostrado(self):
        """El video cuyo diseño se ve (el de Inicio o, si ese aún no pasó por GO con el director, el último que sí): las acciones van sobre él."""
        return str(self._res.get('video') or self.video())

    def poner_video(self, _ruta=None):
        self.refrescar()

    def refrescar(self):
        """Lee el diseño del video de Inicio (en un hilo) y lo pinta."""
        if self._ocupado or self._cargando:
            return
        import director_sonido_sesion as S
        v = self.video()
        self._cargando = True
        self._estado(tr('Leyendo el sonido del video…'))
        if not self._res.get('hay'):
            self._lbl_vacio.setText(tr('Cargando el sonido del video…'))
            self._vacio.show()
        self._actualizar_disponibles()
        ui.correr_en_hilo(self, lambda: S.resumen(v), self._al_resumen)

    def _al_resumen(self, res, err):
        self._cargando = False
        if err is not None:
            if not self._res.get('hay'):
                self._lbl_vacio.setText(tr('No se pudo cargar el sonido. Vuelve a abrir Sonido para reintentar.'))
            self._estado(tr('No pude leer el sonido del video: {e}', e=err))
            self._actualizar_disponibles()
            return
        self._mensaje_estado = ''
        self._pintar(res)

    def _pedir_cuadro(self):
        """El cuadro del video para la vista de la izquierda (una vez por video, en un hilo)."""
        v = self._video_mostrado()
        if not v or v == self._video_cuadro:
            return
        self._video_cuadro = v

        def fin(img, err):
            if err is None and img is not None and self._video_cuadro == v:
                self._vista.poner(img)
        ui.correr_en_hilo(self, lambda: cuadro_del_video(v), fin)

    def version_actual(self):
        return version_de(self._res.get('controles'))

    def _pintar(self, res):
        self._res = res or {}
        self._pintando = True
        try:
            self._var_on.set(bool(self._res.get('activo')))
            for k, (_v, etiqueta) in ((k, next(((v, t) for v, t in OPCIONES[k] if v == (self._res.get('controles') or {}).get(k, 'auto')), OPCIONES[k][0]))
                                      for k in OPCIONES):
                self._vars[k].set(tr(etiqueta))
        finally:
            self._pintando = False
        hay = bool(self._res.get('hay'))
        self._vacio.setVisible(not hay)
        self._cuerpo.setVisible(hay)
        self._lbl_estado.setText(self._mensaje_estado or self._texto_on())
        if not hay:
            self._ev = None
            self._linea.poner({})
            self._lbl_video.setText(tr('La IA le pone sonido en GO; aquí eliges cómo suena.'))
            self._lbl_vacio.setText(tr(self._res.get('motivo') or 'Haz GO con un video para empezar.'))
            self._pildora.poner('', ui.VERDE)
            self._actualizar_disponibles()
            return
        nombre = self._res.get('nombre_video') or self._res.get('video') or tr('Video sin nombre')
        tema = self._res.get('tema') or ''
        self._lbl_video.setText(' · '.join(x for x in (str(nombre) + (' · ' + tr('último video con GO') if self._res.get('otro_video') else ''), str(tema)) if x))
        self._pedir_cuadro()
        self._pintar_resolve()
        self._pintar_versiones()
        sel = (self._ev or {}).get('clave')
        self._ev = next((e for e in self._res.get('eventos') or [] if e.get('clave') == sel), None)
        if self._ev is None:                                         # el tramo de «Antes | Con sonido»: desde el primer sonido
            primero = next((e for e in sorted(self._res.get('eventos') or [], key=lambda e: float(e.get('ancla') or 0)) if e.get('suena')), None)
            self._linea._cursor = max(0.0, float((primero or {}).get('ancla') or 0.0))
        self._linea.poner(self._res, sel if self._ev else None)
        self._llenar_eventos()
        self._pintar_evento(self._ev)
        self._pintar_tramo()
        self._actualizar_disponibles()

    def _pintar_versiones(self):
        actual = self.version_actual()
        musica_del_video = any(m[2] == 'del video' for m in (self._res.get('carriles') or {}).get('musica') or [])
        for clave, _n, desc, _preset in VERSIONES:
            if musica_del_video:                                     # (si el video ya trae música, ninguna le pone otra encima)
                desc = desc.split(' · música')[0] + ' · ' + tr('respeta la música del video')
            self._tarjetas[clave].poner(self._res, clave == actual, desc, trabajando=clave == self._version_trabajando)

    def _pintar_resolve(self):
        """La pastilla de la cabecera (y la fila de «Ajustar a mano»): al día en Resolve, cambios sin aplicar o sin destino."""
        hay = bool(self._res.get('hay'))
        self._fila_resolve.setVisible(hay)
        pendiente = bool(self._res.get('pendiente_resolve'))
        if not hay:
            return
        if pendiente:
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Cambios pendientes · pulsa Aplicar a Resolve'))
            self._pildora.poner(tr('Cambios sin aplicar'), ui.AMBAR)
        elif self._res.get('puede_aplicar') and self._res.get('en_resolve'):
            self._ico_resolve.poner('ok')
            cuando = str(self._res.get('en_resolve') or '')[-8:-3]
            self._lbl_resolve.setText(tr('En Resolve y al día') + (f'  ·  {cuando}' if cuando else ''))
            self._pildora.poner(tr('En Resolve y al día'), ui.VERDE)
        elif self._res.get('puede_aplicar'):
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Listo para aplicar · envío a Resolve sin confirmar'))
            self._pildora.poner(tr('Listo para aplicar'), ui.ACCENT_CLARO)
        else:
            self._ico_resolve.poner('aviso')
            self._lbl_resolve.setText(tr('Haz GO con AI Sound Director encendido para ponerlo en Resolve'))
            self._pildora.poner(tr('Haz GO para ponerlo en Resolve'), TEXT_MUTED)
        destino = self._res.get('destino') or self._res.get('destination') or {}
        if isinstance(destino, dict):
            destino = ' · '.join(str(destino[k]) for k in ('proyecto', 'timeline') if destino.get(k))
        self._lbl_destino.setText(tr('Destino: {d}', d=destino) if destino else '')
        self._lbl_destino.setVisible(bool(destino))

    def _texto_on(self):
        if self._res.get('activo'):
            return tr('Elige una versión y pulsa «Aplicar a Resolve» para ponerla en tu timeline.')
        return tr('AI Sound Director está apagado para los próximos GO (en «Ajustar a mano»). Puedes seguir eligiendo para este video.')

    def _llenar_eventos(self):
        seleccion = (self._ev or {}).get('clave')
        self._lista_eventos.blockSignals(True)
        try:
            self._lista_eventos.clear()
            eventos = [e for e in self._res.get('eventos') or [] if e.get('suena') or e.get('silenciado')]
            for e in sorted(eventos, key=lambda e: float(e.get('ancla') or 0)):
                estado = (' · ' + tr('Silenciado') if e.get('silenciado') else '') + (' · ' + tr('Bloqueado') if e.get('bloqueado') else '')
                item = QListWidgetItem(f"{_tiempo(e.get('ancla'))}   {e.get('nombre') or tr('Sonido')}{estado}")
                item.setData(Qt.ItemDataRole.UserRole, e.get('clave'))
                self._lista_eventos.addItem(item)
                if e.get('clave') == seleccion:
                    self._lista_eventos.setCurrentItem(item)
            if not eventos:
                item = QListWidgetItem(tr('Esta versión no tiene efectos de sonido.'))
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self._lista_eventos.addItem(item)
            self._lbl_eventos.setText(tr('Efectos · {n} · elige con clic o con las flechas', n=len(eventos)))
        finally:
            self._lista_eventos.blockSignals(False)

    def _evento_de_lista(self, item, _anterior):
        if item is None or self._ocupado or self._cargando:
            return
        clave = item.data(Qt.ItemDataRole.UserRole)
        evento = next((e for e in self._res.get('eventos') or [] if e.get('clave') == clave), None)
        self._elegir(evento)

    def _tramo(self, segundos=15.0, ancla=None):
        dur = max(0.0, float(self._res.get('duracion') or 0.0))
        cursor = self._linea.cursor() if ancla is None else float(ancla or 0.0)
        inicio = max(0.0, min(dur, cursor) - 2.0)
        return inicio, min(dur, inicio + segundos)

    def _pintar_tramo(self):
        inicio, fin = self._tramo()
        self._lbl_tramo.setText(tr('El ▶ de arriba suena {a} – {b} · clic en la línea para moverlo', a=_tiempo(inicio), b=_tiempo(fin)))

    def _actualizar_disponibles(self):
        libre = not (self._ocupado or self._cargando)
        hay = bool(self._res.get('hay'))
        for b in self._acciones:
            b.setEnabled(libre and hay)
        self._b_aplicar.setEnabled(libre and hay and bool(self._res.get('puede_aplicar')))
        for w in (self._linea, self._lista_eventos, self._vista, self._ab) + tuple(self._tarjetas.values()):
            w.setEnabled(libre and hay)
        self._sw.setEnabled(libre)
        for w in self._controles.values():
            w.setEnabled(libre and hay)
        self._pintar_evento(self._ev)

    def _pintar_evento(self, e):
        if not e:
            self._lbl_ev.setText(tr('Elige un efecto'))
            self._lbl_diseno.setText('')
            self._lbl_porque.setText(tr('Toca un efecto en la línea o en la lista para oírlo y ajustarlo.'))
            for b in self._botones_ev:
                b.setEnabled(False)
            return
        self._lbl_ev.setText(f"{e.get('nombre')}  ·  {_tiempo(e.get('ancla'))}")
        self._lbl_diseno.setText(tr(e.get('diseno') or ''))
        self._lbl_porque.setText(tr('Por qué: {p}', p=e.get('por_que') or ''))
        self._b_silencio.setText(tr('Que suene') if e.get('silenciado') else tr('Silenciar'))
        self._b_bloq.setText(tr('Desbloquear') if e.get('bloqueado') else tr('Bloquear'))
        libre = not (self._ocupado or self._cargando)
        for b in self._botones_ev:
            b.setEnabled(libre)
        bloq = bool(e.get('bloqueado'))
        for b in (self._b_menos, self._b_mas, self._b_regen):
            b.setEnabled(libre and not bloq and not e.get('silenciado'))
        self._b_oir_ev.setEnabled(libre and bool(e.get('suena')))

    def _estado(self, texto):
        self._mensaje_estado = str(texto)
        self._lbl_estado.setText(self._mensaje_estado)

    def _offset(self):
        try:
            return self._offset_fn()
        except Exception:
            return 0

    def _trabajar(self, texto, trabajo, al_terminar=None):
        """Acepta un único trabajo y conserva los errores al repintar. Solo _aplicar envía a Resolve."""
        if self._ocupado or self._cargando:
            return False
        self._ocupado = True
        self._actualizar_disponibles()
        self._estado(texto)

        def fin(r, err):
            self._ocupado = False
            self._version_trabajando = None
            if err is not None:
                self._pintar(self._res)
                self._estado(tr('No se pudo: {e}', e=err))
                self._actualizar_disponibles()
                return
            if al_terminar:
                al_terminar(r)
            else:
                self._pintar(r)
            self._actualizar_disponibles()
        try:
            ui.correr_en_hilo(self, trabajo, fin)
        except Exception as err:
            self._ocupado = False
            self._version_trabajando = None
            self._actualizar_disponibles()
            self._estado(tr('No se pudo iniciar: {e}', e=err))
            return False
        return True

    # ---------------------------------------------------------------- versiones
    def _trabajo_version(self, clave):
        """(En un hilo) deja los controles de esa versión y rehace el sonido (también música y ambiente)."""
        import director_sonido_sesion as S
        preset = next(p for c, _n, _d, p in VERSIONES if c == clave)
        v = self._video_mostrado()
        for k in CLAVES_VERSION:
            S.poner_control(k, preset.get(k, 'auto'))
        return S._rehacer(v, capas=True)

    def _elegir_version(self, clave, y_oir=False):
        if self._ocupado or self._cargando:
            return
        nombre = next(n for c, n, _d, _p in VERSIONES if c == clave)
        if clave == self.version_actual():
            if y_oir:
                self._oir('ai')
            return
        self._version_trabajando = clave
        self._pintar_versiones()
        self._ev = None

        def fin(r):
            self._pintar(r)
            self._estado(tr('Versión «{n}» lista. Pulsa «Aplicar a Resolve» para ponerla en tu timeline.', n=tr(nombre)))
            if y_oir:
                self._oir('ai')
        self._trabajar(tr('Preparando la versión «{n}»…', n=tr(nombre)), lambda: self._trabajo_version(clave), fin)

    def _oir_version(self, clave):
        self._var_ab.set(tr('Con sonido'))
        self._elegir_version(clave, y_oir=True)

    def _oir_vista(self):
        self._oir('original' if self._var_ab.get() == tr('Antes') else 'ai')

    # ---------------------------------------------------------------- acciones
    def _cambio_on(self):
        import director_sonido_sesion as S
        si = bool(self._var_on.get())
        if self._pintando:
            return
        if self._ocupado or self._cargando:
            self._var_on.set(bool(self._res.get('activo')))
            return
        v = self._video_mostrado()

        def trabajo():
            S.poner_activo(si)
            return S.resumen(v)
        self._trabajar(tr('Guardando…'), trabajo, lambda r: (self._pintar(r), self._estado(self._texto_on())))

    def _cambio_control(self, clave, etiqueta):
        if self._pintando:
            return
        if self._ocupado or self._cargando:
            self._pintar(self._res)
            return
        import director_sonido_sesion as S
        valor = next((v for v, t in OPCIONES[clave] if tr(t) == etiqueta), 'auto')
        v = self._video_mostrado()

        def trabajo():
            S.poner_control(clave, valor)
            return S._rehacer(v, capas=clave in ('musica', 'ambiente')) if self._res.get('hay') else S.resumen(v)
        self._trabajar(tr('Rehaciendo con «{c}: {v}»…', c=tr(TITULO_CONTROL[clave]), v=etiqueta), trabajo,
                       lambda r: (self._pintar(r), self._estado(tr('Guardado: {c} en «{v}». Aplica los cambios cuando termines.', c=tr(TITULO_CONTROL[clave]), v=etiqueta))))

    def _elegir(self, e):
        if self._ocupado or self._cargando:
            return
        self._ev = e
        if e:
            self._linea._cursor = max(0.0, float(e.get('ancla') or 0.0))
        clave = (e or {}).get('clave')
        self._linea.poner(self._res, clave)
        self._lista_eventos.blockSignals(True)
        try:
            if e is None:
                self._lista_eventos.clearSelection()
                self._lista_eventos.setCurrentRow(-1)
            else:
                for i in range(self._lista_eventos.count()):
                    item = self._lista_eventos.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == clave:
                        self._lista_eventos.setCurrentItem(item)
                        self._lista_eventos.scrollToItem(item)
                        break
        finally:
            self._lista_eventos.blockSignals(False)
        self._pintar_evento(e)
        self._pintar_tramo()

    def _menu(self, cual):
        import director_sonido_sesion as S
        if not self._ev or self._ocupado or self._cargando:
            return
        m = Menu(self)
        for op, texto in (S.MENOS if cual == 'menos' else S.MAS):
            m.agregar(tr(texto), lambda op=op: self._retocar(f'{cual}:{op}'))
        b = self._b_menos if cual == 'menos' else self._b_mas
        m.mostrar(b.mapToGlobal(b.rect().bottomLeft()))

    def _retocar(self, accion):
        import director_sonido_sesion as S
        if not self._ev or self._ocupado or self._cargando:
            return
        v, clave = self._video_mostrado(), self._ev.get('clave')
        res = {}

        def trabajo():
            r, hecho = S.retocar(v, clave, accion)
            res['hecho'] = hecho
            return r
        self._trabajar(tr('Rehaciendo solo este sonido…'), trabajo, lambda r: (self._pintar(r), self._estado(tr(res.get('hecho') or 'Hecho.'))))

    def _redisenar(self):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        self._trabajar(tr('Creando otra variación (lo bloqueado se queda)…'), lambda: S.redisenar(v),
                       lambda r: (self._pintar(r), self._estado(tr('Otra variación lista. Los sonidos bloqueados se conservan.'))))

    def _deshacer(self):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        self._trabajar(tr('Volviendo a lo que decidió la IA…'), lambda: S.deshacer_todo(v),
                       lambda r: (self._pintar(r), self._estado(tr('De vuelta a lo de la IA: sin retoques y controles en Auto, también para próximos GO.'))))

    def _aplicar(self):
        import director_sonido_sesion as S
        v, off = self._video_mostrado(), self._offset()

        def trabajo():
            ok, msg = S.aplicar(v, offset_frames=off)
            return ok, msg, (S.resumen(v) if ok else None)

        def fin(r):
            ok, msg, nuevo = r or (False, '', None)
            self._pintar(nuevo or self._res)
            self._estado(tr('Puesto en Resolve: sonidos, música, ambiente y voz del director; los de siempre, apagados.') if ok
                         else tr('No se pudo poner en Resolve: {m}', m=str(msg)[:160]))
        self._trabajar(tr('Poniendo el sonido en Resolve…'), trabajo, fin)

    def _oir(self, cual):
        import director_sonido_sesion as S
        v = self._video_mostrado()
        t0, t1 = self._tramo()
        if t1 <= t0:
            self._estado(tr('Este video no tiene un tramo de audio para escuchar.'))
            return

        def trabajo():
            ruta = S.previa(v, cual, t0, t1)
            S.reproducir(ruta)
            return ruta
        etiqueta = tr('Antes') if cual == 'original' else tr('Con sonido')
        self._trabajar(tr('Preparando «{c}»…', c=etiqueta), trabajo,
                       lambda _r: (self._pintar(self._res), self._estado(tr('Sonando «{c}»: {a} – {b}.', c=etiqueta, a=_tiempo(t0), b=_tiempo(t1)))))

    def _oir_evento(self):
        import director_sonido_sesion as S
        if not self._ev or self._ocupado or self._cargando:
            return
        v = self._video_mostrado()
        t0, t1 = self._tramo(4.5, self._ev.get('ancla'))
        if t1 <= t0:
            return
        self._trabajar(tr('Preparando este momento…'), lambda: (S.reproducir(S.previa(v, 'ai', t0, t1)), None)[1],
                       lambda _r: (self._pintar(self._res), self._estado(tr('Sonando este momento: {a} – {b}.', a=_tiempo(t0), b=_tiempo(t1)))))

    def hideEvent(self, e):
        try:
            import director_sonido_sesion as S
            S.detener()
        except Exception:
            pass
        super().hideEvent(e)
