# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_videos_tutorial.py — graba los videos de los tutoriales (2_recursos/tutoriales) con la interfaz REAL, sin pantalla: cursor, clics de verdad y cámara.
"""
hacer_videos_tutorial.py  (v5.76)
---------------------------------
    python hacer_videos_tutorial.py [ids...] [--salida CARPETA]        (sin ids: todos; ids en tutoriales.ORDEN)

La ventana real (QT_QPA_PLATFORM=offscreen, 1440×900 a escala 1,5) hace lo que pide el guion de cada página con clics y movimientos de
ratón DE VERDAD (QTest sobre su QWindow: hover, clics, teclas). Cada 33 ms se copia su búfer (~2 ms) y un hilo pinta encima el cursor, la onda
de cada clic y el archivo arrastrado, encuadra con la «cámara» (un rectángulo 16:10 que se acerca a lo que importa) y codifica a
<id>.mp4 (960×600, H.264, 30 fps, sin audio) + <id>.jpg (el cuadro que el guion marca como miniatura).

No ensucia nada del usuario: prefs, Registro y archivos_seguros parcheados, sin Resolve ni scripts; además copia los .json/.txt de
~/DaVinciSubtitles antes y devuelve los que hubieran cambiado. Dentro de los videos no hay texto añadido: los subtítulos que el guion marca
con g.texto(frase) van a subtitulos.json con su tiempo real y los pinta el reproductor encima, traducidos (el mismo video vale para los 10
idiomas); la interfaz grabada es la española. Una frase nueva necesita su traducción en 2_recursos/locales.
"""
import argparse
import faulthandler
import importlib.util
import math
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent                       # 1_codigo
os.environ.update(QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR='1.5', QT_QPA_FONTDIR='C:/Windows/Fonts', CINECAPTIONS_SIN_MCP='1')
sys.path.insert(0, str(AQUI))
os.chdir(AQUI)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
faulthandler.dump_traceback_later(900, exit=True)

W_OUT, H_OUT, FPS = 960, 600, 30
ANCHO_V, ALTO_V = 1440, 900
TMP = Path(tempfile.mkdtemp(prefix='cc_tutoriales_'))
DATOS = Path.home() / 'DaVinciSubtitles'

# ---------------------------------------------------------------------------------------------------- nada del usuario se toca
import registro                                                    # noqa: E402
registro.CARPETA = TMP
registro.ARCHIVO = TMP / 'cinecaptions.log'
registro.ARCHIVO_ERRORES = TMP / 'errores.log'


def _copia_datos():
    copia = TMP / 'copia_datos'
    copia.mkdir(exist_ok=True)
    firmas = {}
    try:
        for e in os.scandir(DATOS):
            if e.is_file() and e.name.lower().endswith(('.json', '.txt')):
                shutil.copy2(e.path, copia / e.name)
                st = e.stat()
                firmas[e.name] = (st.st_mtime_ns, st.st_size)
    except OSError:
        pass
    return copia, firmas


def _devolver_datos(copia, firmas):
    cambiados = []
    try:
        for e in os.scandir(DATOS):
            if e.is_file() and e.name in firmas:
                st = e.stat()
                if (st.st_mtime_ns, st.st_size) != firmas[e.name]:
                    shutil.copy2(copia / e.name, e.path)
                    cambiados.append(e.name)
            elif e.is_file() and e.name.lower().endswith(('.json', '.txt')) and e.name not in firmas:
                cambiados.append(e.name + ' (nuevo: revisar)')
    except OSError:
        pass
    return cambiados


COPIA, FIRMAS = _copia_datos()

spec = importlib.util.spec_from_file_location('cc_main', str(AQUI / 'CineCaptions (script principal).py'))
M = importlib.util.module_from_spec(spec)
sys.modules['cc_main'] = M
spec.loader.exec_module(M)
import ajustes_ui, archivos_seguros, licencia, resolve_mcp, sfx_rules, tutoriales   # noqa: E402,E401
_PREFS_MEM = {}
licencia.vigente = lambda: True
M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
M.SubtitleApp._recorrido_auto = lambda s, *a, **k: None
ajustes_ui.guardar_prefs = lambda cambios, *a, **k: _PREFS_MEM.update(cambios or {})
_leer_prefs_orig = ajustes_ui.leer_prefs
ajustes_ui.leer_prefs = lambda: {**_leer_prefs_orig(), **_PREFS_MEM}      # lo elegido en el video se ve elegido (sin tocar el archivo)
if hasattr(ajustes_ui, 'mezclar_prefs'):
    ajustes_ui.mezclar_prefs = lambda *a, **k: None
archivos_seguros.escribir_json = lambda *a, **k: None
archivos_seguros.mezclar_json = lambda *a, **k: None
sfx_rules.guardar_modo = lambda *a, **k: None
resolve_mcp.ruta_exe = lambda: None
resolve_mcp.estado_cacheado = lambda *a, **k: {}
if hasattr(M, 'instalar_scripts_en_resolve'):
    M.instalar_scripts_en_resolve = lambda *a, **k: None
try:
    import resolve_bridge
    resolve_bridge.asegurar_conexion = lambda *a, **k: None
except Exception:
    pass
for nombre in ('_programar_autoguardado', '_autoguardar', '_guardar_marcas', '_guardar_ahora', '_sugerir_con_ia', '_corregir_auto', '_corregir_ahora'):
    if hasattr(M.WordTagWindow, nombre):                           # (sin guardar marcas ni la IA de ortografía: escribe orto_cache.json y tarda)
        setattr(M.WordTagWindow, nombre, lambda self, *a, **k: None)
_colocar_orig = M.WordTagWindow._colocar_junto_a


def _colocar_junto_a(self, ventana, idx, ancho, alto):
    """Sin pantalla la «pantalla» mide 800×600 y Qt arrinconaba «Editar palabra»: va donde la pone el programa, bajo la palabra
    (+31: la barra de título de Windows, que el grabador pinta encima de la ventana)."""
    if hasattr(ventana, 'mostrar_en') or idx is None:
        return _colocar_orig(self, ventana, idx, ancho, alto)
    self.lienzo.ver(idx)
    caja = self.lienzo.caja_raiz(idx)
    if not caja:
        return _colocar_orig(self, ventana, idx, ancho, alto)
    bx, by, _bw, bh = caja
    ventana.resize(int(ancho), int(alto))
    ventana.move(int(bx), int(by + bh + 8 + 31))


M.WordTagWindow._colocar_junto_a = _colocar_junto_a
try:
    import vocabulario                                              # corregir una palabra a mano la «aprende» (archivo del usuario)
    vocabulario.aprender_par = lambda *a, **k: None
except Exception:
    pass

import qt_kit as ui                                                 # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer   # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF   # noqa: E402
from PySide6.QtTest import QTest                                    # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QScrollArea, QWidget   # noqa: E402

app = ui.crear_app([sys.argv[0]], carpeta_fuentes=M.BASE_RECURSOS / 'fonts')
DPR = 1.5


# ---------------------------------------------------------------------------------------------------- dibujos (hechos UNA vez en el hilo de la interfaz)
def _sprite_cursor(escala=1.35):
    """La flecha de Windows (blanca con borde negro), a la escala de la ventana grabada."""
    pts = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.6), (9.6, 18.5), (6.9, 12.2), (12.4, 12.2)]
    lado = int(26 * escala * DPR) + 4
    im = QImage(lado, lado, QImage.Format.Format_ARGB32_Premultiplied)
    im.fill(0)
    p = QPainter(im)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    k = escala * DPR
    p.setPen(QPen(QColor(0, 0, 0, 230), 1.25 * k))
    p.setBrush(QColor('#FFFFFF'))
    p.drawPolygon(QPolygonF([QPointF(1.5 + a * k, 1.5 + b * k) for a, b in pts]))
    p.end()
    return im


def _sprite_archivo():
    """El archivo que se arrastra: miniatura del video + «mi_video.mp4» (como el fantasma de arrastre del Explorador)."""
    w, h = 176, 50
    im = QImage(int(w * DPR), int(h * DPR), QImage.Format.Format_ARGB32_Premultiplied)
    im.setDevicePixelRatio(DPR)
    im.fill(0)
    p = QPainter(im)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setPen(QPen(QColor(255, 255, 255, 80), 1))
    p.setBrush(QColor(14, 22, 38, 236))
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 11, 11)
    foto = QImage(str(Path(M.BASE_RECURSOS) / 'vistas_slider' / 'Kinetic_captions.jpg'))
    th = QRectF(7, 6, 28, 38)
    if not foto.isNull():
        cam = QPainterPath()
        cam.addRoundedRect(th, 5, 5)
        p.save()
        p.setClipPath(cam)
        esc = max(th.width() / foto.width(), th.height() / foto.height())
        sw, sh = th.width() / esc, th.height() / esc
        p.drawImage(th, foto, QRectF((foto.width() - sw) / 2, (foto.height() - sh) / 2, sw, sh))
        p.restore()
    p.setPen(QColor('#FFFFFF'))
    p.setFont(ui.fuente(13, peso='negrita'))
    p.drawText(QRectF(44, 7, 130, 20), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), 'mi_video.mp4')
    p.setPen(QColor('#8D9BB5'))
    p.setFont(ui.fuente(11))
    p.drawText(QRectF(44, 26, 130, 17), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), '0:32 · 24 MB')
    p.end()
    return im


# ---------------------------------------------------------------------------------------------------- el hilo que compone y codifica
class Grabadora:
    """Recibe (t, búfer, estado) y escribe el mp4 a 30 fps fijos: cada cuadro de salida usa el último búfer llegado (los tirones de la
    interfaz se ven como son; no se aceleran). Encima: contorno de soltar, ondas de clic, archivo arrastrado y cursor."""

    def __init__(self, mp4, jpg, acento):
        self.mp4, self.jpg = Path(mp4), Path(jpg)
        self.cola = queue.Queue(maxsize=120)
        self.cursor = _sprite_cursor()
        self.archivo = _sprite_archivo()
        self.acento = QColor(acento)
        self.t_poster = None
        self.fallo = None
        self.cuadros = 0
        self.hilo = threading.Thread(target=self._correr, name='grabadora', daemon=True)
        self.hilo.start()

    def poner(self, t, img, estado):
        self.cola.put((t, img, estado))

    def terminar(self):
        self.cola.put(None)
        self.hilo.join()

    def _componer(self, img, est, T):
        if est.get('encima'):                         # las ventanitas abiertas encima («Editar palabra»…), con su sombra
            img = img.copy()
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            for im2, x, y in est['encima']:
                w2, h2 = im2.width() / DPR, im2.height() / DPR
                for k, a in ((14, 18), (8, 30), (3, 50)):
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(0, 0, 0, a))
                    p.drawRoundedRect(QRectF(x - k, y - k + 6, w2 + 2 * k, h2 + 2 * k), 10 + k, 10 + k)
                p.drawImage(QPointF(x, y), im2)
            p.end()
        cam = QRectF(est['camara'])
        fuente = QRectF(cam.x() * DPR, cam.y() * DPR, cam.width() * DPR, cam.height() * DPR).toAlignedRect()
        fuente = fuente.intersected(QRect(0, 0, img.width(), img.height()))
        lienzo = img.copy(fuente).scaled(W_OUT, H_OUT, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        lienzo = lienzo.convertToFormat(QImage.Format.Format_RGB32)
        lienzo.setDevicePixelRatio(1.0)               # (la copia hereda el 1,5 de la ventana: sin esto el cursor caía 1,5 veces más lejos)
        p = QPainter(lienzo)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        k = W_OUT / (fuente.width() / DPR)
        x0, y0 = fuente.x() / DPR, fuente.y() / DPR

        def a_salida(x, y):
            return QPointF((x - x0) * k, (y - y0) * k)
        if est['contorno'] > 0.01:
            a = int(230 * est['contorno'])
            c = QColor(self.acento)
            c.setAlpha(a)
            pen = QPen(c, 2.6 * k)
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            f = QColor(self.acento)
            f.setAlpha(int(30 * est['contorno']))
            p.setBrush(f)
            esq = a_salida(8, 8)
            fin = a_salida(est['ancho'] - 8, est['alto'] - 8)
            p.drawRoundedRect(QRectF(esq, fin), 14 * k, 14 * k)
        for (x, y, t0) in est['ondas']:
            edad = T - t0
            if 0 <= edad < 0.65:
                u = edad / 0.65
                r = (7 + 30 * (1 - (1 - u) ** 3)) * k
                c = QColor(self.acento)
                c.setAlpha(int(235 * (1 - u)))
                p.setPen(QPen(c, 2.6 * k))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(a_salida(x, y), r, r)
                if u < 0.35:
                    c2 = QColor(255, 255, 255, int(120 * (1 - u / 0.35)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(c2)
                    p.drawEllipse(a_salida(x, y), 9 * k, 9 * k)
        cur = est['cursor']
        if est['archivo'] is not None and cur is not None:
            alfa, esc = est['archivo']
            if alfa > 0.01:
                p.setOpacity(alfa)
                aw, ah = self.archivo.width() / DPR * esc * k, self.archivo.height() / DPR * esc * k
                o = a_salida(cur[0] + 4, cur[1] + 6)
                p.drawImage(QRectF(o.x() - aw * 0.10, o.y() - ah * 0.30, aw, ah), self.archivo)
                p.setOpacity(1.0)
        if cur is not None:
            o = a_salida(cur[0], cur[1])
            e = (0.88 if est['apretado'] else 1.0) * k / DPR
            p.drawImage(QRectF(o.x() - 1.5 * e, o.y() - 1.5 * e, self.cursor.width() * e, self.cursor.height() * e), self.cursor)
        p.end()
        return lienzo

    def _correr(self):
        try:
            import av
            import numpy as np
            self.mp4.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.mp4.with_suffix('.tmp.mp4')
            with av.open(str(tmp), 'w', options={'movflags': 'faststart'}) as o:
                s = o.add_stream('libx264', rate=FPS)
                s.width, s.height, s.pix_fmt = W_OUT, H_OUT, 'yuv420p'
                s.options = {'crf': '24', 'preset': 'slow', 'tune': 'animation'}
                T, previo, poster_hecho = 0.0, None, False

                def emitir(img, est, T):
                    nonlocal poster_hecho
                    lienzo = self._componer(img, est, T)
                    a = np.frombuffer(lienzo.constBits(), dtype=np.uint8, count=lienzo.sizeInBytes()).reshape(H_OUT, lienzo.bytesPerLine() // 4, 4)[:, :W_OUT]
                    for paq in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(a), format='bgra')):
                        o.mux(paq)
                    self.cuadros += 1
                    if not poster_hecho and self.t_poster is not None and T >= self.t_poster:
                        lienzo.save(str(self.jpg), 'JPG', 86)
                        poster_hecho = True
                while True:
                    it = self.cola.get()
                    if it is None:
                        break
                    t, img, est = it
                    if previo is not None:
                        while T <= t:
                            emitir(previo[0], previo[1], T)
                            T += 1.0 / FPS
                    previo = (img, est)
                if previo is not None:
                    emitir(previo[0], previo[1], T)
                for paq in s.encode():
                    o.mux(paq)
            os.replace(tmp, self.mp4)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.fallo = e


# ---------------------------------------------------------------------------------------------------- el guion (hilo de la interfaz)
def _suave(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _suave2(u):
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


class Tween:
    def __init__(self, a, b, dur, curva=_suave2):
        self.a, self.b, self.t0, self.dur, self.curva = a, b, time.perf_counter(), max(0.001, dur), curva

    def valor(self):
        u = self.curva((time.perf_counter() - self.t0) / self.dur)
        if isinstance(self.a, QRectF):
            return QRectF(self.a.x() + (self.b.x() - self.a.x()) * u, self.a.y() + (self.b.y() - self.a.y()) * u,
                          self.a.width() + (self.b.width() - self.a.width()) * u, self.a.height() + (self.b.height() - self.a.height()) * u)
        if isinstance(self.a, QPointF):
            # arco suave (la mano no va en línea recta): se curva un poco hacia arriba a mitad de camino
            d = self.b - self.a
            curva = math.sin(math.pi * u) * min(60.0, 0.12 * math.hypot(d.x(), d.y()))
            return QPointF(self.a.x() + d.x() * u, self.a.y() + d.y() * u - curva)
        return self.a + (self.b - self.a) * u

    @property
    def fin(self):
        return time.perf_counter() - self.t0 >= self.dur


class Guion:
    """Lo que el guion de cada video puede hacer. Cada método que lleva tiempo DEVUELVE los segundos que dura: el guion los cede (`yield`)."""

    def __init__(self, ventana, grabadora):
        self.v = ventana
        self.fuente = ventana
        self.g = grabadora
        self.t0 = time.perf_counter()
        self.cursor = QPointF(ANCHO_V + 40, ALTO_V * 0.7)
        self.visible = True
        self.apretado = False
        self.ondas = []
        self.archivo = None                  # [alfa, escala] o None
        self.contorno = 0.0
        self._cur = None
        self._cam = None
        self._ar = None
        self.camara = QRectF(0, 0, ANCHO_V, ALTO_V)
        self.subs = []                       # [(t, frase o None)]: los subtítulos (los pinta el reproductor)
        self.hover = True
        self._ultimo_mov = None
        self._reloj = QTimer()
        self._reloj.setTimerType(Qt.TimerType.PreciseTimer)
        self._reloj.setInterval(16)
        self._reloj.timeout.connect(self._tic)
        self._grabar = QTimer()
        self._grabar.setTimerType(Qt.TimerType.PreciseTimer)
        self._grabar.setInterval(33)
        self._grabar.timeout.connect(self._capturar)

    # -- utilidades de geometría (coordenadas de la ventana grabada)
    def centro(self, widget, dx=0.0, dy=0.0):
        r = widget.rect()
        c = widget.mapTo(self.fuente, r.center()) if widget is not self.fuente else r.center()
        return QPointF(c.x() + dx, c.y() + dy)

    def rect(self, widget, margen=0.0):
        esq = widget.mapTo(self.fuente, QPoint(0, 0)) if widget is not self.fuente else QPoint(0, 0)
        return QRectF(esq.x() - margen, esq.y() - margen, widget.width() + 2 * margen, widget.height() + 2 * margen)

    def tam(self):
        return self.fuente.width(), self.fuente.height()

    def encuadre(self, r, aire=1.0):
        """r ampliado a 16:10 alrededor de su centro (y `aire` de más), sin salirse de la ventana."""
        W, H = self.tam()
        r = QRectF(r)
        w, h = r.width() * aire, r.height() * aire
        if w / h > 1.6:
            h = w / 1.6
        else:
            w = h * 1.6
        w, h = min(w, W), min(h, W / 1.6, H)
        w = h * 1.6 if w / h > 1.6 else w
        h = w / 1.6
        c = r.center()
        x = max(0.0, min(W - w, c.x() - w / 2))
        y = max(0.0, min(H - h, c.y() - h / 2))
        return QRectF(x, y, w, h)

    def todo(self):
        return self.encuadre(QRectF(0, 0, *self.tam()))

    # -- acciones
    def poner_fuente(self, widget):
        self.fuente = widget
        self.camara = self.todo()
        self._cam = None

    def mover(self, destino, dur=0.9):
        if callable(destino):
            destino = destino()
        self._cur = Tween(QPointF(self.cursor), QPointF(destino), dur)
        return dur

    def camara_a(self, rect_o_widget=None, dur=0.9, aire=1.25):
        if rect_o_widget is None:
            dest = self.todo()
        elif isinstance(rect_o_widget, QWidget):
            dest = self.encuadre(self.rect(rect_o_widget), aire)
        else:
            dest = self.encuadre(QRectF(rect_o_widget), aire)
        self._cam = Tween(QRectF(self.camara), dest, dur)
        return 0.0

    def _ventana(self):
        return self.fuente.windowHandle()

    def ventanas_encima(self):
        """Las ventanas propias abiertas encima de la grabada (sus hijas: «Editar palabra», menús…), visibles."""
        res = []
        for tw in QApplication.topLevelWidgets():
            if tw is self.fuente or not tw.isVisible():
                continue
            p = tw.parentWidget()
            while p is not None and p is not self.fuente:
                p = p.parentWidget()
            if p is self.fuente:
                res.append(tw)
        return res

    def _marco(self, tw):
        """Su imagen y, si en Windows lleva barra de título, la barra oscura (la de barra_oscura: el arnés sin pantalla no la pinta)."""
        im = tw.backingStore().paintDevice().copy()
        f = tw.windowFlags()
        if not (f & Qt.WindowType.WindowTitleHint) or (f & Qt.WindowType.FramelessWindowHint) or (f & Qt.WindowType.Popup) == Qt.WindowType.Popup:
            return im, 0
        alto_b = 31
        w, h = tw.width(), tw.height()
        out = QImage(int(w * DPR), int((h + alto_b) * DPR), QImage.Format.Format_ARGB32_Premultiplied)
        out.setDevicePixelRatio(DPR)
        out.fill(QColor('#202020'))
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(ui.fuente(12))
        p.drawText(QRectF(12, 0, w - 60, alto_b), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), tw.windowTitle())
        p.setPen(QPen(QColor('#E6E6E6'), 1.1))
        cx, cy = w - 23, alto_b / 2
        p.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
        p.drawLine(QPointF(cx - 5, cy + 5), QPointF(cx + 5, cy - 5))
        p.drawImage(QPointF(0, alto_b), im)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(0.5, 0.5, w - 1, h + alto_b - 1))
        p.end()
        return out, alto_b

    def a_fuente(self, widget):
        """Centro de un widget (de la ventana grabada o de una ventanita encima) en coordenadas de la ventana grabada."""
        c = widget.mapToGlobal(widget.rect().center())
        o = self.fuente.mapToGlobal(QPoint(0, 0))
        return QPointF(c.x() - o.x(), c.y() - o.y())

    def clic(self, real=True, doble=False):
        self.ondas.append((self.cursor.x(), self.cursor.y(), time.perf_counter() - self.t0))
        self.apretado = True
        QTimer.singleShot(140, lambda: setattr(self, 'apretado', False))
        if real:
            win, pt = self._ventana(), self.cursor.toPoint()
            o = self.fuente.mapToGlobal(QPoint(0, 0))
            for tw in reversed(self.ventanas_encima()):            # el clic cae en la ventanita si el cursor está sobre ella
                g = tw.mapToGlobal(QPoint(0, 0)) - o
                if QRect(g, tw.size()).contains(pt):
                    win, pt = tw.windowHandle(), pt - g
                    break
            # en diferido: si el clic abre una ventana con exec() (bucle propio), el guion ya está parado en su yield y sigue desde ese bucle
            if doble:
                QTimer.singleShot(0, lambda: QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt))
            else:
                QTimer.singleShot(0, lambda: QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt))
        return 0.0

    def teclear(self, texto, widget=None, ms=70):
        """Escribe letra a letra (como una persona) en el widget con el foco o en `widget`."""
        dest = widget or QApplication.focusWidget()
        for i, ch in enumerate(texto):
            QTimer.singleShot(int(i * ms), lambda c=ch: QTest.keyClicks(dest, c) if ui.vivo(dest) else None)
        return len(texto) * ms / 1000.0 + 0.1

    def tecla(self, tecla, widget=None):
        dest = widget or QApplication.focusWidget()
        if dest is not None:
            QTimer.singleShot(0, lambda: QTest.keyClick(dest, tecla) if ui.vivo(dest) else None)
        return 0.0

    def con_archivo(self, si=True):
        self.archivo = [1.0, 1.0] if si else None
        return 0.0

    def soltar_archivo(self, dur=0.35):
        self._ar = Tween(1.0, 0.0, dur)
        self.ondas.append((self.cursor.x(), self.cursor.y(), time.perf_counter() - self.t0))
        return dur

    def poster(self):
        self.g.t_poster = time.perf_counter() - self.t0
        return 0.0

    def texto(self, frase):
        """v5.76 (el usuario eligió el estilo A): desde ahora sale este subtítulo (None = ninguno). NO se pinta en el video: va a
        subtitulos.json con su tiempo y lo pinta el reproductor encima, traducido (tutoriales_ui.VideoTutorial)."""
        self.subs.append((time.perf_counter() - self.t0, frase))
        return 0.0

    # -- relojes
    def empezar(self):
        self.t0 = time.perf_counter()
        self._reloj.start()
        self._grabar.start()

    def parar(self):
        self._reloj.stop()
        self._grabar.stop()

    def _tic(self):
        if self._cur is not None:
            self.cursor = self._cur.valor()
            if self._cur.fin:
                self._cur = None
        if self._cam is not None:
            self.camara = self._cam.valor()
            if self._cam.fin:
                self._cam = None
        if self._ar is not None and self.archivo is not None:
            a = self._ar.valor()
            self.archivo = [a, 0.6 + 0.4 * a]
            if self._ar.fin:
                self._ar = None
                self.archivo = None
        W, H = self.tam()
        dentro = self.archivo is not None and 0 <= self.cursor.x() <= W and 0 <= self.cursor.y() <= H
        meta = 1.0 if dentro else 0.0
        self.contorno += (meta - self.contorno) * 0.18
        if self.hover and self.archivo is None and 0 <= self.cursor.x() < W and 0 <= self.cursor.y() < H:
            pt = self.cursor.toPoint()
            if pt != self._ultimo_mov:
                self._ultimo_mov = pt
                try:
                    QTest.mouseMove(self._ventana(), pt)
                except Exception:
                    pass

    def _capturar(self):
        try:
            img = self.fuente.backingStore().paintDevice().copy()
        except Exception:
            return
        W, H = self.tam()
        t = time.perf_counter() - self.t0
        self.ondas = [o for o in self.ondas if t - o[2] < 1.0]
        encima = []
        o = self.fuente.mapToGlobal(QPoint(0, 0))
        for tw in self.ventanas_encima():
            try:
                im2, barra = self._marco(tw)
                g = tw.mapToGlobal(QPoint(0, 0)) - o
                encima.append((im2, g.x(), g.y() - barra))
            except Exception:
                pass
        est = {'camara': QRectF(self.camara), 'cursor': (self.cursor.x(), self.cursor.y()) if self.visible else None,
               'apretado': self.apretado, 'ondas': list(self.ondas), 'archivo': tuple(self.archivo) if self.archivo else None,
               'contorno': self.contorno, 'ancho': W, 'alto': H, 'encima': encima}
        if os.environ.get('CC_TUT_DEPURAR') and int(t * 30) % 15 == 0:
            print(f'    t={t:5.2f} cursor={est["cursor"]} cam={est["camara"]}', flush=True)
        self.g.poner(t, img, est)


from PySide6.QtWidgets import QApplication   # noqa: E402


# ---------------------------------------------------------------------------------------------------- ayudas para encontrar widgets
def por_texto(raiz, texto, clase=QWidget):
    for w in raiz.findChildren(clase):
        try:
            if w.isVisible() and hasattr(w, 'text') and (w.text() or '').strip() == texto:
                return w
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------------------------------- los guiones
def g_inicio(g):
    v = g.v
    p = v.go_panel
    v._pintar_go_reposo = lambda *a, **k: None

    def reposo():                                     # como con Resolve abierto (el arnés no tiene Resolve: la línea diría «cerrado»)
        p.boton.poner_estado('listo')
        p.reposo('DaVinci Resolve Studio 21.2 detectado', forzar=True, tono='ok')

    def trabajar(pasos, cada):
        orden = [k for k, _n in p.PASOS]
        for i, k in enumerate(pasos):
            QTimer.singleShot(int(i * cada * 1000), lambda k=k, i=i: (i and p.paso(orden[orden.index(k) - 1], 'hecho'), p.paso(k, 'activo')))
        return len(pasos) * cada
    v.ir_a('inicio', animar=False)
    reposo()
    g.cursor = QPointF(-60, 640)
    g.con_archivo(True)
    g.texto('Arrastra tu video a la ventana')
    yield 1.0
    yield g.mover(QPointF(470, 520), 1.7)
    g.poster()
    yield 0.5
    yield g.soltar_archivo(0.3)
    g.texto('CineCaptions crea el proyecto y empieza solo')
    p.empezar()
    yield trabajar(['timeline', 'voz'], 1.3)
    yield 0.5
    # la otra manera: con Resolve abierto, GO
    reposo()
    g.texto('¿Ya tienes tu timeline abierto en Resolve?')
    yield 0.8
    boton = p.boton
    g.camara_a(g.rect(boton).adjusted(-40, -30, 40, 170), 1.2, aire=1.12)
    yield g.mover(lambda: g.centro(boton, 8, 4), 1.4)
    yield 0.5
    g.clic(real=False)
    g.texto('Pulsa GO: transcribe, diseña y coloca todo')
    p.empezar()
    yield trabajar(['timeline', 'voz', 'ia', 'diseno', 'sfx', 'resolve'], 0.75)
    p.paso('resolve', 'hecho')
    p.terminar(True, 'Todo colocado en tu timeline', [(12, 'bloques', 'n'), (48, 'palabras', 'n'), (18.5, 'duración', 't')])
    g.texto('¡Listo! Todo queda en tu timeline')
    yield 2.6
    g.camara_a(None, 1.0)
    yield 1.6
    reposo()


def _carrusel(v):
    return v._plantillas_ventana.carrusel


def _centro_carta(g, carr, k):
    w, h, cx, cy = carr._medidas()
    r = carr._transformar(k - carr._pos, w, h, cx, cy)[0]
    c = carr.mapTo(g.fuente, r.center().toPoint())
    return QPointF(c.x(), c.y() + r.height() * 0.12)


def g_estilo(g):
    v = g.v
    v.ir_a('nuevo', animar=False)
    carr = _carrusel(v)
    g.texto('Cada tarjeta es un estilo con subtítulos reales')
    yield 2.2
    k0 = int(round(carr._pos))
    g.texto('Toca una tarjeta de los lados para pasarlas')
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 1), 1.2)
    yield 0.3
    g.clic()
    yield 1.6
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 2), 0.9)
    yield 0.3
    g.clic()
    yield 1.4
    g.texto('Clic en la del centro para usarla')
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 2), 0.9)
    yield 0.5
    g.clic()                                          # la del centro: se usa («En uso»)
    g.poster()
    yield 0.4
    g.texto('La que usas dice «En uso»')
    yield 1.8
    g.texto('Puedes cambiarlo cuando quieras')
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 1), 0.9)
    yield 0.3
    g.clic()
    yield 1.0
    yield g.mover(lambda: _centro_carta(g, carr, k0), 0.8)
    yield 0.3
    g.clic()
    yield 1.4


def g_crea(g):
    v = g.v
    v.ir_a('nuevo', animar=False)
    carr = _carrusel(v)
    g.texto('La última tarjeta: «Crea tu estilo»')
    yield 1.0
    n = len(carr._cartas)
    k = next((i for i, c in enumerate(carr._cartas) if c.tipo == 'anadir'), n - 1)
    carr._ir_a(k)
    yield 1.4
    yield g.mover(lambda: _centro_carta(g, carr, k), 1.1)
    yield 0.4
    g.clic(real=False)
    yield 0.25
    v._plantillas_ventana._crear_estilo()
    dlg = v._plantillas_ventana._galeria_estilo
    yield 0.6
    g.poner_fuente(dlg)
    g.cursor = QPointF(dlg.width() * 0.55, dlg.height() * 0.62)
    yield 1.0
    base, prin = dlg._rej_base, dlg._rej_prin
    previa = next((x for x in dlg.findChildren(QWidget) if type(x).__name__ == '_Previa' and x.isVisible()), None)

    def celda(rej, i):
        r = rej._rect(i)
        c = rej.mapTo(dlg, r.center().toPoint())
        return QPointF(c.x(), c.y())
    g.camara_a(g.rect(base).united(g.rect(prin)), 1.0, aire=1.04)       # de cerca: las tarjetas
    g.texto('Elige un texto base: las palabras normales')
    yield g.mover(lambda: celda(base, 1), 1.0)
    yield 0.3
    g.clic()
    yield 1.1
    g.texto('Elige los textos principales: se turnan')
    yield g.mover(lambda: celda(prin, 0), 0.8)
    yield 0.3
    g.clic()
    yield 1.0
    yield g.mover(lambda: celda(prin, 3), 0.7)
    yield 0.3
    g.clic()
    yield 0.9
    yield g.mover(lambda: celda(prin, 4), 0.6)
    yield 0.3
    g.clic()
    yield 0.6
    if previa is not None:                                              # la previa vertical: se turnan frase a frase
        g.camara_a(g.rect(previa).adjusted(-200, 0, 0, 0), 1.1, aire=1.08)
        g.poster()
        g.texto('La previa enseña cómo queda')
        yield 2.6
    g.camara_a(None, 1.0)
    nombre = next((e for e in dlg.findChildren(QLineEdit) if e.isVisible()), None)
    if nombre is not None:
        g.texto('Ponle nombre y créalo')
        yield g.mover(lambda: g.centro(nombre), 1.0)
        g.clic()
        yield 0.2
        nombre.selectAll()
        yield g.teclear('Mi estilo de reels', nombre, 55)
        yield 0.4
        crear = por_texto(dlg, 'Crear mi estilo', QAbstractButton)
        if crear is not None:
            yield g.mover(lambda: g.centro(crear), 0.8)
            yield 1.2
    try:
        dlg.close()
    except Exception:
        pass
    g.poner_fuente(v)


PALABRAS = 'Así ganamoz 10.000 euros en un mes con este truco que nadie te cuenta'.split()


def g_corrector(g):
    v = g.v
    palabras = [{'word': t, 'start': 0.6 + i * 0.38, 'end': 0.6 + i * 0.38 + 0.33} for i, t in enumerate(PALABRAS)]
    roles = [None] * len(palabras)
    ed = M.WordTagWindow(v, palabras, roles, 'zz_tutorial_guia', idioma='es')
    v._editor = ed
    v._editor_vacio.hide()
    try:
        v._cielo_corrector.hide()
    except Exception:
        pass
    v._editor_capa.addWidget(ed, 1)
    try:
        t, s = v._cabeceras['editor']
        t.configure(text=ed.titulo())
        s.configure(text=ed.subtitulo())
    except Exception:
        pass
    v.ir_a('editor', animar=False)
    g.texto('Después de GO tus palabras salen aquí')
    yield 2.0
    lienzo = next((x for x in ed.findChildren(M.LienzoPalabras) if x.isVisible()), None)

    def palabra(i):
        x0, y0, x1, y1 = lienzo._cajas[i]
        c = lienzo.mapTo(g.fuente, QPoint(int((x0 + x1) / 2), int((y0 + y1) / 2)))
        return QPointF(c.x(), c.y())

    def pincel(nombre):
        try:
            b = ed.brush_btn.boton(M.tr(nombre))
            return g.centro(b)
        except Exception:
            return None
    if lienzo is None:
        return
    zona = g.rect(lienzo)
    zona.setHeight(min(zona.height(), 260))
    try:
        zona = zona.united(g.rect(ed.brush_btn))
    except Exception:
        pass
    g.camara_a(zona, 1.0, aire=1.08)                  # de cerca: los pinceles y las palabras
    yield 0.6
    for nombre_pincel, idx, f_pincel, f_palabra in (('Principal', 2, 'Elige un pincel: Principal es la palabra grande', 'Toca la palabra para marcarla'),
                                                    ('Arriba', 0, 'Arriba: el texto pequeño de encima', None)):
        g.texto(f_pincel)
        destino = pincel(nombre_pincel)
        if destino is not None:
            yield g.mover(destino, 1.0)
            yield 0.25
            g.clic()
            yield 0.7
        if f_palabra:
            g.texto(f_palabra)
        yield g.mover(lambda i=idx: palabra(i), 0.9)
        yield 0.25
        g.clic()
        yield 1.0
    g.poster()
    destino = pincel('Principal')
    if destino is not None:
        yield g.mover(destino, 0.9)
        g.clic()
        yield 0.4
    yield g.mover(lambda: palabra(3), 0.7)
    g.clic()
    yield 1.0
    # corregir lo que se oyó mal: doble clic y escribir
    g.texto('Doble clic para corregir lo que se oyó mal')
    yield g.mover(lambda: palabra(1), 1.0)
    yield 0.3
    g.clic(doble=True)
    yield 0.9
    dlg = next((tw for tw in g.ventanas_encima() if tw.windowTitle() == M.tr('Editar palabra')), None)
    if dlg is not None:
        chip = por_texto(dlg, 'ganamos')                          # «¿Querías decir?» → la sugerencia
        if chip is not None:
            yield g.mover(lambda: g.a_fuente(chip), 0.9)
            yield 0.3
            g.clic()
        else:
            entrada = next((e for e in dlg.findChildren(QLineEdit) if e.isVisible()), None)
            if entrada is not None:
                yield g.mover(lambda: g.a_fuente(entrada), 0.8)
                g.clic()
                yield 0.2                                       # (el clic va en diferido: seleccionar DESPUÉS, si no escribe al final)
                entrada.selectAll()
                yield g.teclear('ganamos', entrada, 80)
                yield 0.4
                g.tecla(Qt.Key.Key_Return, entrada)
    yield 0.3
    g.texto('Palabra corregida')
    yield 1.6
    g.camara_a(None, 1.0)
    yield 1.4
    try:
        v._editor = None
        ed.hide()
        v._editor_capa.removeWidget(ed)
        ed.setParent(None)
        ed.deleteLater()
        v._editor_vacio.show()
    except Exception:
        pass


def _de_clase(raiz, nombre):
    """Los widgets visibles de esa clase, de arriba abajo y de izquierda a derecha."""
    xs = [x for x in raiz.findChildren(QWidget) if type(x).__name__ == nombre and x.isVisible()]
    xs.sort(key=lambda x: (x.mapTo(raiz.window(), QPoint(0, 0)).y(), x.mapTo(raiz.window(), QPoint(0, 0)).x()))
    return xs


def g_sonido(g):
    v = g.v
    v.ir_a('sfx', animar=False)
    yield 1.6
    pag = getattr(v, '_director_pagina', None) or v
    estilos = _de_clase(pag, 'TarjetaEstilo')            # Automático, Elegante, Dinámico, Lista, Cinética
    llaves = {x.text(): x for x in _de_clase(pag, 'Interruptor')}
    aplicar = por_texto(pag, 'Aplicar a Resolve', QAbstractButton)
    izq = estilos[0].parentWidget() if estilos else None
    while izq is not None and type(izq).__name__ != 'Tarjeta':
        izq = izq.parentWidget()
    if izq is not None:
        g.camara_a(g.rect(izq).adjusted(0, 0, 360, 0), 1.0, aire=1.02)
    g.texto('Elige cómo suena tu video')
    yield 0.6
    for k, espera, frase in ((2, 1.5, 'Dinámico: un efecto en cada palabra clave'), (1, 1.4, 'Elegante: pocos efectos y suaves')):
        if len(estilos) > k:
            yield g.mover(lambda k=k: g.centro(estilos[k], -60, 0), 1.0)
            yield 0.25
            g.clic()
            g.texto(frase)
            yield espera
    g.poster()
    fiesta = llaves.get('Fiesta o mar')
    if fiesta is not None:
        g.texto('Activa o quita opciones con su interruptor')
        yield g.mover(lambda: g.centro(fiesta, -fiesta.width() / 2 + 22, 0), 1.0)
        yield 0.3
        g.clic()
        yield 1.2
        g.clic()
        yield 0.8
    if aplicar is not None:
        g.texto('«Aplicar a Resolve» pone los cambios en tu timeline')
        yield g.mover(lambda: g.centro(aplicar), 1.0)
        yield 1.8
    if estilos:
        g.texto('Automático: según el estilo elegido')
        yield g.mover(lambda: g.centro(estilos[0], -60, 0), 1.0)
        yield 0.25
        g.clic()
        yield 1.0
    g.camara_a(None, 1.0)
    yield 1.4


def g_efectos(g):
    v = g.v
    v.ir_a('efectos', animar=False)
    yield 1.8
    pag = getattr(v, '_efectos_widget', None) or v
    secciones = _de_clase(pag, 'SeccionEstilo')
    if not secciones:
        return
    s1 = secciones[0]
    cartas = sorted([x for x in s1.findChildren(QWidget) if type(x).__name__ == 'TarjetaEfecto' and x.isVisible()],
                    key=lambda x: x.mapTo(v, QPoint(0, 0)).x())
    llave = next(iter(_de_clase(s1, 'Interruptor')), None)
    g.camara_a(g.rect(s1), 1.0, aire=1.02)
    g.texto('El gancho del inicio: el primer segundo del video')
    yield 1.6
    g.texto('Toca una tarjeta para elegirla')
    elegida = next((i for i, c in enumerate(cartas) if getattr(c, 'elegida', getattr(c, '_elegida', False))), 4)
    for k in (5, 2):                                   # Fuego, Lima eléctrica
        if len(cartas) > k:
            yield g.mover(lambda k=k: g.centro(cartas[k], 0, -40), 1.0)
            yield 0.3
            g.clic()
            if k == 5:
                g.poster()
            yield 1.6
    if llave is not None:                              # apagar y volver a encender en GO
        g.texto('Apágalo o enciéndelo con su interruptor')
        yield g.mover(lambda: g.centro(llave, -llave.width() / 2 + 22, 0), 1.0)
        yield 0.3
        g.clic()
        yield 1.0
        g.clic()
        yield 0.8
    if len(cartas) > elegida:                          # vuelve a la que estaba
        yield g.mover(lambda: g.centro(cartas[elegida], 0, -40), 1.0)
        g.clic()
        yield 0.8
    zona = next((s for s in v.findChildren(QScrollArea) if s.isVisible() and s.height() > 500), None)
    if zona is not None and len(secciones) > 1:
        g.camara_a(None, 1.0)
        g.texto('Más abajo: captions detrás de ti y más')
        barra = zona.verticalScrollBar()
        a = barra.value()
        b = min(barra.maximum(), a + int(secciones[1].mapTo(zona.widget(), QPoint(0, 0)).y() - 20))
        pasos = 30
        for i in range(pasos + 1):
            QTimer.singleShot(int(i * 35), lambda i=i: barra.setValue(int(a + (b - a) * _suave2(i / pasos))))
        yield 1.5
        s2 = secciones[1]
        cartas2 = sorted([x for x in s2.findChildren(QWidget) if type(x).__name__ == 'TarjetaEfecto' and x.isVisible()],
                         key=lambda x: x.mapTo(v, QPoint(0, 0)).x())
        g.camara_a(g.rect(s2), 1.0, aire=1.02)
        if len(cartas2) > 2:
            yield g.mover(lambda: g.centro(cartas2[2], 0, -40), 1.0)
            yield 0.3
            g.clic()
            g.texto('GO aplica solo lo que elijas')
            yield 1.8
            yield g.mover(lambda: g.centro(cartas2[1], 0, -40), 0.8)
            g.clic()
            yield 0.8
        g.camara_a(None, 1.0)
        for i in range(pasos + 1):
            QTimer.singleShot(int(i * 30), lambda i=i: barra.setValue(int(b + (a - b) * _suave2(i / pasos))))
        yield 1.4


def g_ajustes(g):
    v = g.v
    v.ir_a('inicio', animar=False)
    g.texto('El engranaje abre los ajustes')
    yield 1.0
    r = v.isla.rect_de('ajustes')
    yield g.mover(QPointF(r.center()), 1.2)
    yield 0.3
    g.clic()                                          # el panel rápido
    yield 1.2
    expandir = por_texto(v, M.tr('Expandir ajustes'), QAbstractButton)
    if expandir is not None:
        g.texto('«Expandir ajustes» los abre todos')
        yield g.mover(lambda: g.centro(expandir), 1.0)
        yield 0.3
        g.clic()
        yield 1.3
    dlg = getattr(v, '_ventana_ajustes', None)
    if dlg is None:
        dlg = next((x for x in v.findChildren(ajustes_ui.VentanaAjustes) if x.isVisible()), None)
    if dlg is None:
        return
    pest = dlg.pestanas
    cajas = pest._cajas()

    def pestana(i):
        c = pest.mapTo(g.fuente, cajas[i].center().toPoint())
        return QPointF(c.x(), c.y())
    yield g.mover(lambda: pestana(1), 1.0)
    yield 0.2
    g.clic()
    g.texto('Idioma, fondo y estilo de la interfaz')
    yield 1.8
    k = dlg.PESTANAS.index('tutoriales') if 'tutoriales' in dlg.PESTANAS else len(cajas) - 2
    yield g.mover(lambda: pestana(k), 1.0)
    yield 0.2
    g.clic()
    g.poster()
    g.texto('En Tutoriales están todos estos videos')
    yield 2.2
    lista = getattr(dlg, '_tut_filas', None) or []
    if len(lista) > 2:
        yield g.mover(lambda: g.centro(lista[1]), 1.0)
        yield 0.2
        g.clic()
        yield 1.8
    guia = getattr(dlg, '_tut_interruptor', None)
    if guia is not None:
        zona = next((s for s in dlg.findChildren(QScrollArea) if s.isVisible()), None)
        if zona is not None:
            zona.ensureWidgetVisible(guia, 20, 60)
            yield 0.4
        g.texto('Aquí apagas o enciendes esta guía')
        yield g.mover(lambda: g.centro(guia), 1.0)
        yield 0.3
        g.clic()
        yield 0.9
        g.clic()
        yield 1.2
    try:
        dlg.cerrar()
    except Exception:
        pass
    yield 0.6


GUIONES = {'inicio': g_inicio, 'estilo': g_estilo, 'crea': g_crea, 'corrector': g_corrector, 'sonido': g_sonido, 'efectos': g_efectos,
           'ajustes': g_ajustes}


def grabar(v, ident, salida):
    print(f'· {ident}…', flush=True)
    graba = Grabadora(salida / f'{ident}.mp4', salida / f'{ident}.jpg', ui.ACCENT_CLARO)
    g = Guion(v, graba)
    gen = GUIONES[ident](g)
    fin = {'listo': False}

    def acabar(motivo=None):
        if fin['listo']:
            return
        if motivo:
            print(f'  {ident}: {motivo}', flush=True)
        g.parar()
        fin['listo'] = True
        for tw in g.ventanas_encima():                # nada abierto (una ventana con exec() dejaría el bucle de fuera parado)
            try:
                tw.close()
            except Exception:
                pass

    def avanzar():
        if fin['listo']:
            return
        try:
            espera = next(gen)
        except StopIteration:
            acabar()
            return
        except Exception:
            import traceback
            traceback.print_exc()
            acabar('el guion falló')
            return
        QTimer.singleShot(max(1, int(float(espera or 0) * 1000)), avanzar)
    g.empezar()
    QTimer.singleShot(1, avanzar)
    QTimer.singleShot(90000, lambda: acabar('el guion no terminó en 90 s: se corta'))
    while not fin['listo']:
        app.processEvents()
        time.sleep(0.002)
    t = time.perf_counter() - g.t0
    graba.terminar()
    print(f'  {ident}: {t:.1f} s, {graba.cuadros} cuadros' + (f'  FALLO {graba.fallo}' if graba.fallo else ''), flush=True)
    if not graba.fallo:                               # la duración de cada video (la lista de Ajustes › Tutoriales la enseña sin abrir el mp4)
        import json
        ruta = salida / 'duraciones.json'
        try:
            d = json.loads(ruta.read_text(encoding='utf-8'))
        except Exception:
            d = {}
        d[ident] = round(graba.cuadros / float(FPS), 2)
        ruta.write_text(json.dumps(dict(sorted(d.items())), ensure_ascii=False, indent=1), encoding='utf-8')
        # los subtítulos: cada frase desde que el guion la marcó hasta la siguiente (o casi el final); en español, se traducen al pintarse
        fin_v = graba.cuadros / float(FPS)
        marcas = sorted(g.subs)
        cues = []
        for i, (t0, frase) in enumerate(marcas):
            t1 = marcas[i + 1][0] if i + 1 < len(marcas) else fin_v - 0.25
            if frase and t1 - t0 >= 0.6:
                cues.append([round(t0, 2), round(t1, 2), frase])
        ruta = salida / 'subtitulos.json'
        try:
            s = json.loads(ruta.read_text(encoding='utf-8'))
        except Exception:
            s = {}
        s[ident] = cues
        ruta.write_text(json.dumps(dict(sorted(s.items())), ensure_ascii=False, indent=1), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--salida', default=str(tutoriales.carpeta()))
    a = ap.parse_args()
    ids = a.ids or list(GUIONES)
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    v = M.SubtitleApp()
    v._guardar_preferencias = lambda *a, **k: None
    v._emojis_anim_anotado = True
    v.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    v.resize(ANCHO_V, ALTO_V)
    v.show()
    v.isActiveWindow = lambda: True
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 6:
        app.processEvents()
        time.sleep(0.005)
    try:
        for ident in ids:
            grabar(v, ident, salida)
    finally:
        cambiados = _devolver_datos(COPIA, FIRMAS)
        print('datos del usuario devueltos:' if cambiados else 'datos del usuario: sin cambios', ', '.join(cambiados), flush=True)
        shutil.rmtree(TMP, ignore_errors=True)
    os._exit(0)


if __name__ == '__main__':
    main()
