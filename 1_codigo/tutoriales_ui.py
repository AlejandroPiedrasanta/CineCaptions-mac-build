# CineCaptions · By Cinema Productions
# 1_codigo/tutoriales_ui.py — el reproductor de los videos tutoriales (guía y Ajustes) y el panel «Tutoriales» de Ajustes: el video grande y la lista de las páginas.
"""
tutoriales_ui.py  (v5.82)
-------------------------
    VideoTutorial(ancho, alto)     un video del tutorial: esquinas redondas, en bucle, barra de avance y tiempo; un clic lo pausa / sigue.
                                   Encima, el subtítulo del momento (tutoriales.subtitulos, traducido): una píldora oscura centrada sobre la
                                   barra (estilo A que eligió el usuario), con un fundido corto al entrar y salir.
                                   v5.82: con su LOCUCIÓN (tutoriales.ruta_voz, en el idioma de la interfaz): suena sincronizada con el video en
                                   la primera vuelta (las siguientes van sin voz); el altavoz de la barra la apaga o la enciende (se recuerda).
        .poner(id)                 cambia de video (tutoriales.ruta_video); sin archivo se ve su miniatura o un fondo oscuro
        .tamano(ancho, alto)
    PanelTutoriales()              Ajustes › Tutoriales (propuesta B2 que eligió el usuario): a la izquierda el video elegido con su título y
                                   explicación; a la derecha la lista (miniatura, nombre y duración) en dos grupos, «Las páginas» y «Paso a
                                   paso», con su propio desplazamiento para que el video no se vaya de la vista. Un clic en una fila la pone.

El video lo decodifica vistas_slider.Reproductor en UN hilo y solo mientras se ve (hideEvent lo para: cambiar de pestaña o cerrar Ajustes).
La interfaz solo copia el cuadro ya escalado al tamaño del widget (Reproductor.tam). Las miniaturas (.jpg) se leen en un hilo. La voz
(_Voz) se decodifica y suena en OTRO hilo (winsound en Windows, afplay en Mac, como el resto de sonidos del programa: sin Qt multimedia):
la interfaz solo le manda «suena desde t» o «calla».
"""
import os
import queue
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

import qt_kit as ui
import tutoriales
from i18n import tr


def _mmss(s):
    s = max(0, int(round(float(s or 0))))
    return f'{s // 60}:{s % 60:02d}'


def _cubrir(p, img, dest):
    """Pinta `img` (QImage o QPixmap) cubriendo `dest` sin deformarla."""
    iw, ih = img.width(), img.height()
    if iw <= 0 or ih <= 0:
        return
    ad, ai = dest.width() / max(1.0, dest.height()), iw / float(ih)
    if ai > ad:
        sw, sh = ih * ad, float(ih)
    else:
        sw, sh = float(iw), iw / ad
    src = QRectF((iw - sw) / 2.0, (ih - sh) / 2.0, sw, sh)
    if isinstance(img, QImage):
        p.drawImage(dest, img, src)
    else:
        p.drawPixmap(dest, img, src)


_POSTERS = {}


def poster(ident, al_listo, contexto):
    """La miniatura de un tutorial (QImage) leída en un hilo; `al_listo(img)` en el hilo de la interfaz (o enseguida si ya estaba)."""
    if ident in _POSTERS:
        al_listo(_POSTERS[ident])
        return

    def leer():
        ruta = tutoriales.ruta_poster(ident)
        img = QImage(str(ruta)) if ruta else QImage()
        return img if not img.isNull() else None

    def fin(img, _e):
        _POSTERS[ident] = img
        al_listo(img)
    ui.correr_en_hilo(contexto, leer, fin)


class _Voz:
    """v5.82: la locución de un tutorial. Su hilo la decodifica UNA vez (PyAV → mono de 16 bits a 24 kHz) y la hace sonar desde el segundo
    que se le pida con lo que trae el sistema (winsound en Windows, afplay en Mac). La interfaz solo encola órdenes: nunca espera."""
    SR = 24000

    def __init__(self, ruta):
        self.ruta = str(ruta)
        self._ordenes = queue.Queue()
        self._hilo = threading.Thread(target=self._correr, name='voz-tutorial', daemon=True)
        self._hilo.start()

    def sonar(self, desde):
        self._ordenes.put(('sonar', float(desde)))

    def callar(self):
        self._ordenes.put(('callar', 0.0))

    def cerrar(self):
        self._ordenes.put(('cerrar', 0.0))

    def _decodificar(self):
        import av
        import numpy as np
        partes = []
        with av.open(self.ruta) as c:
            rs = av.AudioResampler(format='s16', layout='mono', rate=self.SR)
            for fr in c.decode(c.streams.audio[0]):
                for g in rs.resample(fr):
                    partes.append(np.ascontiguousarray(g.to_ndarray().reshape(-1)).astype('<i2').tobytes())
            for g in rs.resample(None):
                partes.append(np.ascontiguousarray(g.to_ndarray().reshape(-1)).astype('<i2').tobytes())
        return b''.join(partes)

    @staticmethod
    def _wav(ruta, pcm, sr):
        import wave
        with wave.open(str(ruta), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm)

    def _correr(self):
        pcm, proc, sonando, k = None, None, False, 0
        tmp = [os.path.join(tempfile.gettempdir(), f'cinecaptions_tutorial_{os.getpid()}_{id(self)}_{i}.wav') for i in (0, 1)]
        try:
            while True:
                orden, desde = self._ordenes.get()
                while True:                                      # solo vale la última orden (p. ej. pausar y seguir muy rápido)
                    try:
                        orden, desde = self._ordenes.get_nowait()
                    except queue.Empty:
                        break
                if sonando:
                    try:
                        if proc is not None:
                            proc.terminate()
                        elif sys.platform.startswith('win'):
                            import winsound
                            winsound.PlaySound(None, 0)
                    except Exception:
                        pass
                    proc, sonando = None, False
                if orden == 'cerrar':
                    return
                if orden != 'sonar':
                    continue
                if pcm is None:
                    try:
                        pcm = self._decodificar()
                    except Exception:
                        pcm = b''
                i = int(max(0.0, desde) * self.SR) * 2
                if i >= len(pcm) - self.SR // 5:                   # (menos de 0,1 s: no vale la pena)
                    continue
                k = 1 - k                                          # dos archivos: nunca se escribe el que aún suena
                try:
                    self._wav(tmp[k], pcm[i:], self.SR)
                    if sys.platform.startswith('win'):
                        import winsound
                        winsound.PlaySound(tmp[k], winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                    elif sys.platform == 'darwin':
                        import subprocess
                        proc = subprocess.Popen(['afplay', tmp[k]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        continue
                    sonando = True
                except Exception:
                    proc, sonando = None, False
        finally:
            for r in tmp:
                try:
                    os.remove(r)
                except OSError:
                    pass


class VideoTutorial(QWidget):
    """Un video del tutorial. Se reproduce solo mientras se ve; un clic lo pausa o lo sigue."""

    def __init__(self, ancho=344, alto=215, radio=12, padre=None):
        super().__init__(padre)
        self._radio = radio
        self._id = None
        self._rep = None
        self._subs = []
        self._subs_lineas = {}
        self._img = None
        self._poster = None
        self._ultima = None
        # v5.82: la locución (ver _sincronizar_voz)
        self._voz = None
        self._voz_caja = [None]                 # (para cerrarla si el widget se destruye sin esconderse)
        self._voz_on = tutoriales.voz_activa()
        self._voz_sonando = False
        self._voz_ref = (0.0, 0.0)              # (reloj, segundo del video) cuando empezó a sonar
        self._voz_vuelta = 0                    # la vuelta del bucle que lleva voz (la primera; o la que estaba al encender el altavoz)
        self._r_altavoz = None
        self.destroyed.connect(lambda *_a, caja=self._voz_caja: caja[0].cerrar() if caja[0] is not None else None)
        self.setFixedSize(int(ancho), int(alto))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reloj = QTimer(self)
        self._reloj.setInterval(33)
        self._reloj.timeout.connect(self._tic)

    # -- qué video
    def poner(self, ident):
        if ident == self._id:
            return
        self._parar()
        self._id = ident
        self._img = None
        self._ultima = None
        self._poster = None
        self._subs = tutoriales.subtitulos(ident)
        self._subs_lineas = {}
        ruta = tutoriales.ruta_video(ident)
        self._rep = None
        if self._voz is not None:
            self._voz.cerrar()
        self._voz = None
        if ruta:
            import vistas_slider
            self._rep = vistas_slider.Reproductor(ruta, pausa_s=1.0)
            self._ajustar_tam()
            voz = tutoriales.ruta_voz(ident)
            if voz:
                self._voz = _Voz(voz)
        self._voz_caja[0] = self._voz
        self._voz_vuelta = 0
        poster(ident, self._poner_poster, self)
        if self.isVisible():
            self._arrancar()
        self.update()

    def _poner_poster(self, img):
        if not ui.vivo(self):
            return
        self._poster = img
        self.update()

    def tamano(self, ancho, alto):
        ancho, alto = int(ancho), int(alto)
        if (ancho, alto) != (self.width(), self.height()):
            self.setFixedSize(ancho, alto)
            self._subs_lineas = {}
            self._ajustar_tam()

    # -- subtítulos (v5.76, el usuario eligió el estilo A: una píldora oscura centrada encima de la barra de avance)
    def _fuente_sub(self):
        return ui.fuente(int(round(max(12.5, min(19.0, self.width() * 0.040)))), peso='negrita')

    def _lineas_sub(self, frase):
        """La frase traducida y partida en líneas (≤ 80 % del ancho); se calcula una vez por frase y tamaño."""
        if frase in self._subs_lineas:
            return self._subs_lineas[frase]
        fm = QFontMetricsF(self._fuente_sub())
        ancho = self.width() * 0.80
        out, cur = [], ''
        for pal in tr(frase).split():
            prueba = (cur + ' ' + pal).strip()
            if not cur or fm.horizontalAdvance(prueba) <= ancho:
                cur = prueba
            else:
                out.append(cur)
                cur = pal
        if cur:
            out.append(cur)
        self._subs_lineas[frase] = out
        return out

    def _pintar_subtitulo(self, p, r, pos):
        cue = next(((a, b, f) for a, b, f in self._subs if a <= pos < b), None)
        if cue is None:
            return
        a, b, frase = cue
        alfa = max(0.0, min(1.0, (pos - a) / 0.18, (b - pos) / 0.18))          # entra y sale con un fundido corto
        if alfa <= 0.01:
            return
        lineas = self._lineas_sub(frase)
        if not lineas:
            return
        f = self._fuente_sub()
        fm = QFontMetricsF(f)
        tam = float(f.pixelSize() if f.pixelSize() > 0 else fm.height() * 0.75)
        alto_l = fm.height()
        w = max(fm.horizontalAdvance(x) for x in lineas) + tam * 1.6
        h = alto_l * len(lineas) + tam * 0.9
        caja = QRectF(r.center().x() - w / 2, r.bottom() - 52 - h, w, h)
        rad = min(h / 2.0, 14.0)
        p.setOpacity(alfa)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor(4, 8, 16, 215))
        p.drawRoundedRect(caja, rad, rad)
        p.setFont(f)
        p.setPen(QColor('#FFFFFF'))
        for i, x in enumerate(lineas):
            p.drawText(QRectF(caja.left(), caja.top() + tam * 0.45 + i * alto_l, caja.width(), alto_l), int(Qt.AlignmentFlag.AlignCenter), x)
        p.setOpacity(1.0)

    @staticmethod
    def _pintar_altavoz(p, caja, encendido):
        """v5.82: un altavoz blanco (con dos ondas si suena, tachado si está apagado), del alto de los iconos de la barra."""
        x, y, s = caja.x(), caja.y(), caja.height()
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#FFFFFF'))
        p.drawPolygon(QPolygonF([QPointF(x + s * 0.08, y + s * 0.36), QPointF(x + s * 0.30, y + s * 0.36), QPointF(x + s * 0.56, y + s * 0.12),
                                 QPointF(x + s * 0.56, y + s * 0.88), QPointF(x + s * 0.30, y + s * 0.64), QPointF(x + s * 0.08, y + s * 0.64)]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor('#FFFFFF'), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        if encendido:
            for rad in (0.20, 0.36):
                rr = QRectF(x + s * 0.56 - s * rad, y + s * 0.5 - s * rad, 2 * s * rad, 2 * s * rad)
                p.drawArc(rr, -50 * 16, 100 * 16)
        else:
            p.drawLine(QPointF(x + s * 0.70, y + s * 0.34), QPointF(x + s * 0.98, y + s * 0.66))
            p.drawLine(QPointF(x + s * 0.70, y + s * 0.66), QPointF(x + s * 0.98, y + s * 0.34))
        p.restore()

    def _ajustar_tam(self):
        if self._rep is not None:
            dpr = self.devicePixelRatioF() or 1.0
            self._rep.tam = (int(round(self.width() * dpr)), int(round(self.height() * dpr)))

    # -- reproducir solo mientras se ve
    def _arrancar(self):
        if self._rep is not None:
            self._ajustar_tam()
            if not self._rep.activo:                  # (arrancar() empieza desde el principio: la voz vuelve a la primera vuelta)
                self._voz_vuelta = 0
            self._rep.arrancar()
            self._reloj.start()

    def _parar(self):
        self._reloj.stop()
        if self._rep is not None:
            self._rep.parar()
        self._callar()

    def _callar(self):
        if self._voz is not None and self._voz_sonando:
            self._voz.callar()
        self._voz_sonando = False

    def showEvent(self, e):
        super().showEvent(e)
        self._arrancar()

    def hideEvent(self, e):
        self._parar()
        super().hideEvent(e)

    def _tic(self):
        if self._rep is None:
            return
        img = self._rep.imagen()
        if img is not None and img is not self._ultima:
            self._ultima = img
            self._img = img
            self.update()
        self._sincronizar_voz()

    def _sincronizar_voz(self):
        """v5.82: la voz sigue al video. Suena en la vuelta que toca (la primera) mientras el video avanza; en pausa, al esconderse o con el
        altavoz apagado calla; si el video se atrasó o se adelantó más de 0,35 s (el equipo se trabó), vuelve a empezar desde el segundo
        del video."""
        voz, rep = self._voz, self._rep
        if voz is None or rep is None:
            return
        pos = float(rep.posicion or 0.0)
        quiere = (self._voz_on and self._img is not None and rep.activo and not rep.en_pausa and rep.vueltas == self._voz_vuelta)
        if not quiere:
            self._callar()
            return
        ahora = time.perf_counter()
        if self._voz_sonando and abs(self._voz_ref[1] + (ahora - self._voz_ref[0]) - pos) <= 0.35:
            return
        voz.sonar(pos)
        self._voz_sonando = True
        self._voz_ref = (ahora, pos)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._rep is not None:
            if self._r_altavoz is not None and self._r_altavoz.adjusted(-8, -8, 8, 8).contains(e.position()):
                self._voz_on = not self._voz_on                # el altavoz: se recuerda para los demás videos
                tutoriales.poner_voz_activa(self._voz_on)
                if self._voz_on:
                    self._voz_vuelta = self._rep.vueltas       # (encenderlo en otra vuelta: suena desde aquí)
                self._sincronizar_voz()
            else:
                self._rep.pausar(not self._rep.en_pausa)
                self._sincronizar_voz()
            self.update()
            e.accept()
            return
        super().mousePressEvent(e)

    # -- pintado
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        cam = QPainterPath()
        cam.addRoundedRect(r, self._radio, self._radio)
        p.setClipPath(cam)
        p.fillRect(r, QColor(ui.tc('#05080F')))
        img = self._img if self._img is not None else self._poster
        if img is not None:
            _cubrir(p, img, r)
        rep = self._rep
        if rep is not None and self._subs and self._img is not None:
            self._pintar_subtitulo(p, r, rep.posicion or 0.0)
        if rep is not None:
            pausa = rep.en_pausa
            g = QLinearGradient(0, r.bottom() - 46, 0, r.bottom())
            g.setColorAt(0, QColor(0, 0, 0, 0))
            g.setColorAt(1, QColor(0, 0, 0, 175))
            p.fillRect(QRectF(0, r.bottom() - 46, r.width(), 46), g)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#FFFFFF'))
            y = r.bottom() - 22
            if pausa:
                p.drawPolygon(QPolygonF([QPointF(13, y), QPointF(13, y + 12), QPointF(23, y + 6)]))
            else:
                p.drawRoundedRect(QRectF(13, y, 3.4, 11), 1, 1)
                p.drawRoundedRect(QRectF(19.5, y, 3.4, 11), 1, 1)
            dur = rep.duracion or 0.0
            pos = min(dur, rep.posicion or 0.0) if dur else 0.0
            texto = f'{_mmss(pos)} / {_mmss(dur)}' if dur else ''
            p.setFont(ui.fuente(11, peso='medio'))
            tw = p.fontMetrics().horizontalAdvance(texto) if texto else 0
            if texto:
                p.setPen(QColor('#E6ECF5'))
                p.drawText(QRectF(r.right() - tw - 13, r.bottom() - 26, tw + 2, 18), int(Qt.AlignmentFlag.AlignVCenter), texto)
            hueco = 0.0
            self._r_altavoz = None
            if self._voz is not None:                  # v5.82: el altavoz (apaga o enciende la voz), entre la barra y el tiempo
                caja = QRectF(r.right() - tw - 13 - 26, r.bottom() - 26, 18, 18)
                self._r_altavoz = caja
                self._pintar_altavoz(p, caja, self._voz_on)
                hueco = 28.0
            pista = QRectF(32, r.bottom() - 18, max(10.0, r.width() - tw - 32 - 22 - hueco), 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 60))
            p.drawRoundedRect(pista, 2, 2)
            u = (pos / dur) if dur else 0.0
            p.setBrush(QColor(ui.ACCENT_CLARO))
            p.drawRoundedRect(QRectF(pista.left(), pista.top(), pista.width() * u, 4), 2, 2)
            p.setBrush(QColor('#FFFFFF'))
            p.drawEllipse(QPointF(pista.left() + pista.width() * u, pista.center().y()), 5, 5)
            if pausa:
                c, L = r.center(), min(56.0, r.height() * 0.28)
                p.setPen(QPen(QColor(255, 255, 255, 110), 1.5))
                p.setBrush(QColor(6, 10, 20, 160))
                p.drawEllipse(c, L / 2, L / 2)
                t = L * 0.36
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#FFFFFF'))
                p.drawPolygon(QPolygonF([QPointF(c.x() - t * 0.38, c.y() - t * 0.5), QPointF(c.x() - t * 0.38, c.y() + t * 0.5),
                                         QPointF(c.x() + t * 0.55, c.y())]))
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), self._radio, self._radio)
        p.end()


class _Miniatura(QWidget):
    """La miniatura de una fila: el .jpg del tutorial con esquinas redondas y, si no es la que suena, el botón de play."""

    def __init__(self, ident, ancho=112, alto=70):
        super().__init__()
        self.setFixedSize(ancho, alto)
        self._img = None
        self.elegida = False
        poster(ident, self._poner, self)

    def _poner(self, img):
        if ui.vivo(self):
            self._img = img
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        cam = QPainterPath()
        cam.addRoundedRect(r, 8, 8)
        p.setClipPath(cam)
        p.fillRect(r, QColor(ui.tc('#05080F')))
        if self._img is not None:
            _cubrir(p, self._img, r)
        if not self.elegida:
            c, L = r.center(), 26.0
            p.setPen(QPen(QColor(255, 255, 255, 110), 1.2))
            p.setBrush(QColor(6, 10, 20, 160))
            p.drawEllipse(c, L / 2, L / 2)
            t = L * 0.36
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#FFFFFF'))
            p.drawPolygon(QPolygonF([QPointF(c.x() - t * 0.38, c.y() - t * 0.5), QPointF(c.x() - t * 0.38, c.y() + t * 0.5),
                                     QPointF(c.x() + t * 0.55, c.y())]))
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        p.end()


class _FilaTutorial(QFrame):
    """Una fila de la lista: miniatura, nombre de la página y duración («Reproduciendo · 0:12» en la elegida)."""
    clic = Signal(str)

    def __init__(self, ident, titulo, duracion):
        super().__init__()
        self.ident = ident
        self._dur = duracion
        self.setObjectName('tutFila')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        c = QHBoxLayout(self)
        c.setContentsMargins(10, 8, 12, 8)
        c.setSpacing(14)
        self.mini = _Miniatura(ident)
        c.addWidget(self.mini)
        col, cc = ui.caja_v(espacio=3)
        cc.addWidget(ui.Etiqueta(titulo, 15, peso='negrita', color='#FFFFFF'))
        self.detalle = ui.Etiqueta(duracion, 12, color=ui.TEXT_MUTED)
        cc.addWidget(self.detalle)
        c.addWidget(col, 1, Qt.AlignmentFlag.AlignVCenter)
        self._hover = False
        self.poner_elegida(False)

    def poner_elegida(self, si):
        self.mini.elegida = si
        self.mini.update()
        a = QColor(ui.ACCENT_CLARO)
        if si:
            css = f'background-color: rgba({a.red()},{a.green()},{a.blue()},30); border: 1px solid rgba({a.red()},{a.green()},{a.blue()},120);'
        elif self._hover:
            css = 'background-color: rgba(255,255,255,10); border: 1px solid transparent;'
        else:
            css = 'background: transparent; border: 1px solid transparent;'
        self.setStyleSheet(f'QFrame#tutFila {{ {css} border-radius: 12px; }}')
        texto = (tr('Reproduciendo') + '  ·  ' + self._dur) if (si and self._dur) else (tr('Reproduciendo') if si else self._dur)
        self.detalle.configure(text=texto, text_color=ui.ACCENT_CLARO if si else ui.TEXT_MUTED)
        self._elegida = si

    def enterEvent(self, e):
        self._hover = True
        self.poner_elegida(getattr(self, '_elegida', False))
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.poner_elegida(getattr(self, '_elegida', False))
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clic.emit(self.ident)
        super().mouseReleaseEvent(e)


def _seccion(texto):
    """El rótulo de un grupo de la lista («LAS PÁGINAS»), como los de las secciones de Ajustes."""
    e = ui.Etiqueta(texto.upper(), 11, peso='negrita', color='#7F8DA8')
    f = e.font()
    f.setLetterSpacing(f.SpacingType.AbsoluteSpacing, 2.2)
    e.setFont(f)
    return e


class PanelTutoriales(QWidget):
    """Ajustes › Tutoriales (B2): el video elegido grande, con su título y explicación, y la lista de los tutoriales a la derecha.
    v5.82: la lista va en dos grupos («Las páginas» y «Paso a paso») y se desplaza sola, del alto del video y su texto: así el video
    nunca se sale de la vista al buscar uno de abajo."""
    ANCHO_LISTA = 380

    def __init__(self, padre=None):
        super().__init__(padre)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(22)
        izq, ci = ui.caja_v(espacio=10)
        self.video = VideoTutorial(650, 406, radio=14)
        ci.addWidget(self.video)
        ci.addSpacing(4)
        self.titulo = ui.Etiqueta('', 20, peso='extra', color='#FFFFFF', envolver=True)
        ci.addWidget(self.titulo)
        self.texto = ui.Etiqueta('', 14, color='#C9D6EC', envolver=True)
        ci.addWidget(self.texto)
        ci.addStretch(1)
        fila.addWidget(izq, 1)
        lista = QFrame()
        lista.setObjectName('grupoAjustes')
        lista.setFixedWidth(self.ANCHO_LISTA)
        cl = QVBoxLayout(lista)
        cl.setContentsMargins(4, 6, 2, 6)
        cl.setSpacing(0)
        self._desplazable = ui.Desplazable(margenes=(6, 6, 8, 6), espacio=4, estirar_final=True)
        cl.addWidget(self._desplazable)
        self.filas = []
        nombres = dict((i, t) for i, t, _x in tutoriales.TUTORIALES)
        for k, (grupo, ids) in enumerate(tutoriales.GRUPOS):
            cab = QWidget()
            cc = QVBoxLayout(cab)
            cc.setContentsMargins(8, 16 if k else 6, 0, 4)
            cc.addWidget(_seccion(tr(grupo)))
            self._desplazable.agregar(cab)
            for ident in ids:
                if ident not in nombres:
                    continue
                d = tutoriales.duracion(ident)
                f = _FilaTutorial(ident, tr(nombres[ident]), _mmss(d) if d else '')
                f.clic.connect(self.elegir)
                self._desplazable.agregar(f)
                self.filas.append(f)
        fila.addWidget(lista, 0, Qt.AlignmentFlag.AlignTop)
        self._lista = lista
        self._izq = izq
        self.elegir(tutoriales.ORDEN[0])

    def elegir(self, ident):
        titulo, texto = tutoriales.datos(ident)
        self.titulo.configure(text=tr(titulo))
        self.texto.configure(text=tr(texto))
        for f in self.filas:
            f.poner_elegida(f.ident == ident)
            if f.ident == ident:
                try:
                    self._desplazable.ensureWidgetVisible(f, 0, 24)
                except Exception:
                    pass
        self.video.poner(ident)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        ancho = max(360, self.width() - self.ANCHO_LISTA - 22)
        self.video.tamano(ancho, ancho / 1.6)
        self._lista.setFixedHeight(int(max(380, ancho / 1.6 + 110)))      # del alto del video y su título y texto
