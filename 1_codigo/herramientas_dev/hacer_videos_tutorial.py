# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_videos_tutorial.py — graba los videos de los tutoriales (2_recursos/tutoriales) con la interfaz REAL, sin pantalla: cursor, clics de verdad y cámara.
"""
hacer_videos_tutorial.py  (v5.82)
---------------------------------
    python hacer_videos_tutorial.py [ids...] [--salida CARPETA] [--voz NOMBRE] [--voz-idiomas es,en,…]
                                    (sin ids: todos; ids en tutoriales.ORDEN)

La ventana real (QT_QPA_PLATFORM=offscreen, 1440×900 a escala 1,5) hace lo que pide el guion de cada página con clics y movimientos de
ratón DE VERDAD (QTest sobre su QWindow: hover, clics, arrastres, rueda, teclas). Cada 33 ms se copia su búfer (~2 ms) y un hilo pinta encima
el cursor, la onda de cada clic y el archivo arrastrado, encuadra con la «cámara» (un rectángulo 16:10 que se acerca a lo que importa) y
codifica a <id>.mp4 (960×600, H.264, 30 fps, sin audio) + <id>.jpg (el cuadro que el guion marca como miniatura).

No ensucia nada del usuario: prefs, Registro y archivos_seguros parcheados, sin Resolve, Premiere ni scripts; además copia los .json/.txt de
~/DaVinciSubtitles antes y devuelve los que hubieran cambiado. Dentro de los videos no hay texto añadido: lo que el guion dice con
`yield from g.decir(frase)` va a subtitulos.json con su tiempo real y lo pinta el reproductor encima, traducido (el mismo video vale para los
10 idiomas); la interfaz grabada es la española. Una frase nueva necesita su traducción en 2_recursos/locales.

v5.82, la voz: cada frase de g.decir() es también LOCUCIÓN. Antes de grabar se hacen las frases con voz_tutoriales.py (ElevenLabs por el
conector de Higgsfield, voz «Andre», hombre enérgico y alegre: --voz el_andre, la de fábrica); aquí se lee su índice: el guion espera a que acabe cada frase antes de lo siguiente (la más larga de --voz-idiomas, para que quepan
todas) y, al terminar, cada idioma tiene su pista con cada frase en el segundo en que se dijo: voz/<idioma>/<id>.m4a (AAC mono 24 kHz).
Sin índice se graba igual (con una duración estimada por letras) y sin pista.
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

# v5.82: lo que ESTE proceso escribe (gancho de auditoría de Python: open para escribir, os.replace/rename, copias, borrados). Al final solo se
# devuelve eso: otras sesiones o la app del usuario pueden estar haciendo un GO a la vez y sus archivos (go_en_curso, kit7_historial…) no se pisan.
_ESCRITOS = set()


def _auditar(evento, args):
    try:
        if evento == 'open':
            ruta, modo, flags = args[0], args[1], args[2]
            if isinstance(ruta, int) or ruta is None:
                return
            escribe = any(c in str(modo or '') for c in 'wax+') or (modo is None and isinstance(flags, int) and
                                                                   flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT))
            if escribe:
                _ESCRITOS.add(os.path.normcase(os.path.abspath(os.fspath(ruta))))
        elif evento in ('os.rename', 'shutil.copyfile', 'shutil.copymode', 'shutil.copystat'):
            _ESCRITOS.add(os.path.normcase(os.path.abspath(os.fspath(args[1]))))
        elif evento == 'os.remove':
            _ESCRITOS.add(os.path.normcase(os.path.abspath(os.fspath(args[0]))))
    except Exception:
        pass


sys.addaudithook(_auditar)

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
    """Los .json/.txt de ~/DaVinciSubtitles que ESTE proceso cambió vuelven a como estaban; lo que cambió otro programa a la vez (otra sesión
    o la app con un GO en marcha) se deja como está y solo se dice."""
    cambiados = []
    mios = set(_ESCRITOS)
    try:
        for e in os.scandir(DATOS):
            propio = os.path.normcase(os.path.abspath(e.path)) in mios
            if e.is_file() and e.name in firmas:
                st = e.stat()
                if (st.st_mtime_ns, st.st_size) != firmas[e.name]:
                    if propio:
                        shutil.copy2(copia / e.name, e.path)
                        cambiados.append(e.name)
                    else:
                        cambiados.append(e.name + ' (lo cambió otro programa: se deja)')
            elif e.is_file() and e.name.lower().endswith(('.json', '.txt')) and e.name not in firmas:
                cambiados.append(e.name + (' (nuevo, de este proceso: revisar)' if propio else ' (nuevo, de otro programa: se deja)'))
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
# v5.82: los videos viajan con la app: ni la clave, ni el nombre, el correo o el equipo del dueño (salían en el panel rápido y en Ayuda)
_LIC_DEMO = {'clave': 'CC-0000-000-0000', 'ultima_ok': time.time(), 'visto': time.time(), 'usados': 1, 'limite': 2, 'expira_ts': None,
             'prueba': False}
licencia.local = lambda *a, **k: dict(_LIC_DEMO)
licencia.nombre_equipo = lambda *a, **k: 'Mi PC'
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
# v5.82: Premiere e idioma sin tocar nada real (encender Premiere en Ajustes instala su panel en %APPDATA% y toca el registro de Adobe;
# «Aplicar» con otro idioma escribe idioma.ini): los videos enseñan Premiere «conectado» sin que esté instalado
try:
    import premiere
    _PREMIERE_FALSO = {'instalado': True, 'nombre': 'Adobe Premiere Pro 2026', 'abierto': True, 'conectado': True, 'version': '', 'proyecto': ''}
    premiere.estado = lambda *a, **k: dict(_PREMIERE_FALSO)
    premiere.instalar_panel = lambda *a, **k: {'ok': True, 'instalado': False, 'ruta': '', 'texto': ''}
    premiere.preparar = lambda *a, **k: {'ok': True, 'premiere': None, 'reiniciar': False, 'texto': ''}
    premiere.abrir = lambda *a, **k: None
except Exception:
    pass
ajustes_ui.VentanaAjustes._preparar_premiere = lambda self, *a, **k: None
try:
    import i18n
    i18n.guardar_idioma = lambda *a, **k: False
except Exception:
    pass
M.SubtitleApp.reiniciar_programa = lambda *a, **k: None              # («Listo» con cambios pregunta si reiniciar: nunca)
try:
    ajustes_ui.messagebox.askyesno = lambda *a, **k: False
except Exception:
    pass
import webbrowser                                                   # noqa: E402  (nada se abre fuera: WhatsApp, la web…)
webbrowser.open = webbrowser.open_new = webbrowser.open_new_tab = lambda *a, **k: False
try:
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: False)
except Exception:
    pass
import tutoriales_ui                                                # noqa: E402  (la pestaña Tutoriales grabada: el altavoz se ve, no suena)
tutoriales_ui._Voz.sonar = lambda self, *a, **k: None
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
        self.voces = []                      # v5.82: [(t, frase)]: lo que se dice (g.decir); va a la pista de voz de cada idioma
        self._fin_voz = 0.0                  # cuándo acaba de sonar la última frase (reloj del guion)
        self.despues = []                    # v5.82: lo que se deshace al acabar de grabar (no sale en el video)
        self.dlg = None
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

    def decir(self, frase, pausa=0.28):
        """v5.82: la locución (y su subtítulo). Espera a que acabe la frase anterior más `pausa`, la marca aquí y la cuenta como sonando lo
        que dura dicha (duracion_voz). Va con `yield from g.decir('…')` y SOLO con el texto literal: voz_tutoriales.py lo lee del código."""
        if self._fin_voz > 0:
            resto = self._fin_voz + pausa - (time.perf_counter() - self.t0)
            if resto > 0.02:
                yield resto
        t = time.perf_counter() - self.t0
        self.subs.append((t, frase))
        self.voces.append((t, frase))
        self._fin_voz = t + duracion_voz(frase)

    def esperar_voz(self, extra=0.0):
        """Lo que falta para que acabe la frase que suena (+ extra): `yield g.esperar_voz()` antes de lo que deba ir después de oírla."""
        return max(0.0, self._fin_voz - (time.perf_counter() - self.t0)) + float(extra)

    def apretar(self):
        """v5.82: aprieta el botón donde está el cursor (para arrastrar: los movimientos que siguen llevan el botón apretado)."""
        win, pt = self._ventana(), self.cursor.toPoint()
        self.apretado = True
        self.hover = True
        QTimer.singleShot(0, lambda: QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt))
        return 0.0

    def soltar(self):
        win, pt = self._ventana(), self.cursor.toPoint()
        self.apretado = False
        QTimer.singleShot(0, lambda: QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt))
        return 0.0

    def rueda(self, widget, pasos=1):
        """v5.82: un golpe de rueda sobre `widget` donde está el cursor (pasos > 0: hacia abajo / la tarjeta siguiente)."""
        from PySide6.QtGui import QWheelEvent
        local = widget.mapFrom(self.fuente, self.cursor.toPoint())
        glob = self.fuente.mapToGlobal(self.cursor.toPoint())
        ev = QWheelEvent(QPointF(local), QPointF(glob), QPoint(0, 0), QPoint(0, -120 * int(pasos)), Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QTimer.singleShot(0, lambda: QApplication.sendEvent(widget, ev) if ui.vivo(widget) else None)
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


# ---------------------------------------------------------------------------------------------------- la voz (v5.82)
VOZ = {'nombre': 'el_andre', 'idiomas': ['es'], 'carpeta': None, 'indice': {}}
SR_VOZ = 24000


def cargar_voz(nombre, idiomas):
    """El índice de voz_tutoriales.py (~/.cache/cinecaptions_tts/frases/<voz>/indice.json): {idioma: {frase: [archivo, segundos]}}."""
    import json
    carpeta = Path.home() / '.cache' / 'cinecaptions_tts' / 'frases' / nombre
    try:
        indice = json.loads((carpeta / 'indice.json').read_text(encoding='utf-8'))
    except Exception:
        indice = {}
    VOZ.update(nombre=nombre, idiomas=list(idiomas), carpeta=carpeta, indice=indice)
    hay = [i for i in idiomas if indice.get(i)]
    print(f'voz «{nombre}»: ' + (', '.join(f'{i} ({len(indice[i])} frases)' for i in hay) if hay else 'sin índice (se graba sin voz)'), flush=True)


def duracion_voz(frase):
    """Lo que dura dicha (la más larga de los idiomas pedidos, para que quepan todas); sin índice, una estimación por letras."""
    durs = [float(t[frase][1]) for t in ((VOZ['indice'].get(i) or {}) for i in VOZ['idiomas']) if frase in t]
    return max(durs) if durs else 0.35 + 0.068 * len(frase)


def montar_voz(ident, voces, fin_v, salida):
    """v5.82: la pista de cada idioma: cada frase dicha (g.decir) en su segundo, nivelada (ya lo viene de voz_tutoriales.py) y sin pasar de
    −1 dBFS, en <salida>/voz/<idioma>/<id>.m4a (AAC mono 24 kHz, 64 kb/s). Un idioma al que le falte alguna frase se salta (sin pista
    a medias). Si una frase de otro idioma no cupiera hasta la siguiente, se corta con un fundido (se avisa: hay que grabar con ese idioma
    en --voz-idiomas para que el guion la espere)."""
    import wave
    import av
    import numpy as np
    hechos = []
    for idioma in VOZ['idiomas']:
        tabla = VOZ['indice'].get(idioma) or {}
        faltan = [f for _t, f in voces if f not in tabla]
        if not voces or faltan:
            if voces:
                print(f'  {ident}: sin voz en {idioma} (faltan {len(faltan)} frases: corre voz_tutoriales.py --idiomas {idioma})', flush=True)
            continue
        n = int(math.ceil(fin_v * SR_VOZ)) + 1
        pista = np.zeros(n, dtype=np.float32)
        for k, (t, f) in enumerate(voces):
            with wave.open(str(VOZ['carpeta'] / tabla[f][0]), 'rb') as w:
                x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32768.0
            i0 = int(round(t * SR_VOZ))
            tope = min(n, int(round(voces[k + 1][0] * SR_VOZ)) if k + 1 < len(voces) else n)
            if i0 >= tope:
                continue
            if i0 + len(x) > tope:
                print(f'  {ident} [{idioma}]: «{f}» no cabe ({len(x) / SR_VOZ:.2f} s en {(tope - i0) / SR_VOZ:.2f} s): se corta', flush=True)
                x = x[:tope - i0].copy()
                fade = min(len(x), int(0.08 * SR_VOZ))
                if fade > 1:
                    x[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
            pista[i0:i0 + len(x)] += x
        pico = float(np.max(np.abs(pista))) if len(pista) else 0.0
        if pico > 0.891:
            pista *= 0.891 / pico
        destino = salida / 'voz' / idioma / f'{ident}.m4a'
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.stem + '.tmp.m4a')
        with av.open(str(tmp), 'w') as o:
            s = o.add_stream('aac', rate=SR_VOZ)
            s.bit_rate = 64000
            try:
                s.layout = 'mono'
            except Exception:
                s.codec_context.layout = 'mono'
            paso = 1024 * 8
            for i in range(0, len(pista), paso):
                fr = av.AudioFrame.from_ndarray(pista[i:i + paso].reshape(1, -1), format='fltp', layout='mono')
                fr.sample_rate = SR_VOZ
                fr.pts = i
                for paq in s.encode(fr):
                    o.mux(paq)
            for paq in s.encode(None):
                o.mux(paq)
        os.replace(tmp, destino)
        hechos.append(idioma)
    return hechos


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
# v5.82: cada guion CUENTA lo que hace (g.decir: voz + subtítulo) y la acción va con la frase: mientras se dice, el cursor va; lo que debe
# oírse antes de verse espera con g.esperar_voz(). Frases cortas y claras, de tú, en el español neutro de la interfaz.
def _trabajar(p, pasos, cada):
    """Los pasos de GO, uno tras otro (la escena de Inicio los va cantando)."""
    orden = [k for k, _n in p.PASOS]
    for i, k in enumerate(pasos):
        QTimer.singleShot(int(i * cada * 1000), lambda k=k, i=i: (i and p.paso(orden[orden.index(k) - 1], 'hecho'), p.paso(k, 'activo')))
    return len(pasos) * cada


def _reposo(p, modo='resolve'):
    """La línea bajo GO como con el editor abierto (el arnés no tiene Resolve ni Premiere: diría «cerrado» o «no encuentro»). Los textos son
    los de la app (_pintar_go_reposo / premiere.textos_estado)."""
    p.boton.poner_estado('listo')
    if modo == 'premiere':
        p.reposo(M.tr('{n} detectado · conectado', n='Adobe Premiere Pro 2026') + ' · ' + M.tr('suelta un video aquí'), forzar=True, tono='ok')
    elif modo == 'mp4':
        p.reposo(M.tr('GO te devuelve el video con los subtítulos (Ajustes)') + ' · ' + M.tr('suelta un video aquí'), forzar=True)
    else:
        p.reposo('DaVinci Resolve Studio 21.2 detectado', forzar=True, tono='ok')


def _pasos_de(p, modo):
    """Los nombres de los pasos de GO en cada modo (los mismos que pone _go_lanzar)."""
    if modo == 'premiere':
        p.renombrar_paso('timeline', M.tr('Leer tu video'), M.tr('Leyendo tu video'))
        p.renombrar_paso('resolve', M.tr('Colocar en Premiere Pro'), M.tr('Colocando en Premiere'))
    elif modo == 'mp4':
        p.renombrar_paso('timeline', M.tr('Leer tu video'), M.tr('Leyendo tu video'))
        p.renombrar_paso('resolve', M.tr('Grabar el video con los subtítulos'), M.tr('Grabando el video'))
    else:
        p.renombrar_paso('timeline', M.tr('Traer el timeline de Resolve'), M.tr('Trayendo el timeline'))
        p.renombrar_paso('resolve', M.tr('Colocar en el timeline'), M.tr('Colocando'))


def _abrir_ajustes(g, pestana='general', expandir=True):
    """El camino de verdad: el engranaje de la barra → «Expandir ajustes» → la pestaña. Deja la ventana en g.dlg (o None)."""
    v = g.v
    g.dlg = None
    r = v.isla.rect_de('ajustes')
    yield g.mover(QPointF(r.center()), 1.0)
    yield 0.2
    g.clic()                                          # el panel rápido
    yield 0.9
    boton = por_texto(v, M.tr('Expandir ajustes'), QAbstractButton) if expandir else None
    if boton is not None:
        yield g.mover(lambda: g.centro(boton), 0.8)
        yield 0.2
        g.clic()
        yield 1.1
    dlg = getattr(v, '_ventana_ajustes', None)
    if dlg is None or not ui.vivo(dlg):
        dlg = next((x for x in v.findChildren(ajustes_ui.VentanaAjustes) if x.isVisible()), None)
    if dlg is None:
        return
    g.dlg = dlg
    i = dlg.PESTANAS.index(pestana) if pestana in dlg.PESTANAS else 0
    if i:
        yield g.mover(lambda: _pestana(g, dlg, i), 0.9)
        yield 0.2
        g.clic()
        yield 0.9


def _pestana(g, dlg, i):
    c = dlg.pestanas.mapTo(g.fuente, dlg.pestanas._cajas()[i].center().toPoint())
    return QPointF(c.x(), c.y())


def _fila(dlg, titulo):
    """La fila de Ajustes con ese título (su _Fila) o None."""
    t = M.tr(titulo)
    for e in dlg.findChildren(QLabel):
        try:
            if e.isVisible() and (e.text() or '').strip() == t:
                w = e.parentWidget()
                while w is not None and type(w).__name__ != '_Fila':
                    w = w.parentWidget()
                if w is not None:
                    return w
        except Exception:
            pass
    return None


def _llave(fila):
    return next((x for x in fila.findChildren(QWidget) if type(x).__name__ == 'Interruptor' and x.isVisible()), None) if fila else None


def _punto_llave(g, llave):
    return g.centro(llave, -llave.width() / 2 + 22, 0) if llave.width() > 60 else g.centro(llave)


def _desplazar(barra, hasta, ms=900):
    """Mueve una barra de desplazamiento con suavidad (como la rueda de verdad)."""
    a, pasos = barra.value(), 28
    b = max(barra.minimum(), min(barra.maximum(), int(hasta)))
    for i in range(pasos + 1):
        QTimer.singleShot(int(i * ms / pasos), lambda i=i: barra.setValue(int(a + (b - a) * _suave2(i / pasos))))
    return ms / 1000.0 + 0.1


def _cerrar_ajustes(g):
    dlg = getattr(g, 'dlg', None)
    if dlg is not None:
        try:
            dlg.cerrar()
        except Exception:
            pass
    g.dlg = None


def g_inicio(g):
    v = g.v
    p = v.go_panel
    v._pintar_go_reposo = lambda *a, **k: None
    v.ir_a('inicio', animar=False)
    _pasos_de(p, 'resolve')
    _reposo(p)
    g.cursor = QPointF(-60, 640)
    g.con_archivo(True)
    yield 0.5
    yield from g.decir('Arrastra tu video a la ventana de CineCaptions')
    yield g.mover(QPointF(470, 520), 1.8)
    g.poster()
    yield 0.2
    yield g.soltar_archivo(0.3)
    yield from g.decir('Al soltarlo, crea su proyecto en Resolve y empieza solo')
    p.empezar()
    yield _trabajar(p, ['timeline', 'voz'], 1.3)
    yield g.esperar_voz(0.2)
    _reposo(p)                                        # la otra manera: con tu timeline abierto, GO
    yield from g.decir('¿Ya tienes tu timeline abierto en DaVinci Resolve?')
    boton = p.boton
    g.camara_a(g.rect(boton).adjusted(-40, -30, 40, 170), 1.2, aire=1.12)
    yield g.mover(lambda: g.centro(boton, 8, 4), 1.4)
    yield g.esperar_voz(0.1)
    yield from g.decir('Solo pulsa GO')
    yield 0.75
    g.clic(real=False)
    p.empezar()
    yield g.esperar_voz(0.1)
    yield from g.decir('Transcribe tu voz, diseña los subtítulos y los coloca')
    yield _trabajar(p, ['timeline', 'voz', 'ia', 'diseno', 'sfx', 'resolve'], 0.62)
    yield g.esperar_voz()
    p.paso('resolve', 'hecho')
    p.terminar(True, 'Todo colocado en tu timeline', [(12, 'bloques', 'n'), (48, 'palabras', 'n'), (18.5, 'duración', 't')])
    yield from g.decir('¡Listo! Todo queda en tu timeline')
    yield g.esperar_voz(0.9)
    g.camara_a(None, 1.0)
    yield 1.1
    _reposo(p)


def _carrusel(v):
    return v._plantillas_ventana.carrusel


def _centro_carta(g, carr, k):
    w, h, cx, cy = carr._medidas()
    r = carr._transformar(k - carr._pos, w, h, cx, cy)[0]
    c = carr.mapTo(g.fuente, r.center().toPoint())
    return QPointF(c.x(), c.y() + r.height() * 0.12)


def _carrusel_en(carr, k):
    """Deja el carrusel en la tarjeta k AL MOMENTO (sin la animación de girar): lo que un video movió no se arrastra al siguiente."""
    carr._ir_a(k)
    carr._pos = float(carr._obj)
    carr.update()


def _al_en_uso(carr):
    """El carrusel en la tarjeta del estilo en uso, al momento: cada video de Estilo empieza igual, haga lo que haga el anterior."""
    k = next((i for i, c in enumerate(carr._cartas) if c.valor == carr._elegido and c.tipo != 'anadir'), None)
    if k is not None:
        _carrusel_en(carr, k)


def _rect_carta(g, carr, k):
    w, h, cx, cy = carr._medidas()
    r = carr._transformar(k - carr._pos, w, h, cx, cy)[0]
    esq = carr.mapTo(g.fuente, QPoint(0, 0))
    return QRectF(r).translated(esq.x(), esq.y())


def g_estilo(g):
    v = g.v
    v.ir_a('nuevo', animar=False)
    carr = _carrusel(v)
    _al_en_uso(carr)
    yield 0.4
    yield from g.decir('Cada tarjeta es un estilo, con subtítulos de verdad')
    yield g.esperar_voz(0.3)
    k0 = int(round(carr._pos))
    yield from g.decir('Toca una tarjeta de los lados para pasarlas')
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 1), 1.1)
    yield 0.2
    g.clic()
    yield 1.3
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 2), 0.8)
    yield 0.2
    g.clic()
    yield 1.1
    yield from g.decir('Haz clic en la del centro para usarla')
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 2), 0.8)
    yield 0.5
    g.clic()                                          # la del centro: se usa («En uso»)
    g.poster()
    yield g.esperar_voz(0.2)
    yield from g.decir('La que usas dice «En uso»')
    yield g.esperar_voz(0.5)
    yield from g.decir('Puedes cambiarlo cuando quieras')
    yield g.mover(lambda: _centro_carta(g, carr, k0 + 1), 0.9)
    yield 0.2
    g.clic()
    yield 1.0
    yield g.mover(lambda: _centro_carta(g, carr, k0), 0.8)
    yield 0.2
    g.clic()
    yield 1.2
    g.clic()                                          # (vuelve a usar el de antes)
    yield g.esperar_voz(0.8)


def g_crea(g):
    v = g.v
    v.ir_a('nuevo', animar=False)
    carr = _carrusel(v)
    _al_en_uso(carr)
    n = len(carr._cartas)
    k = next((i for i, c in enumerate(carr._cartas) if c.tipo == 'anadir'), n - 1)
    k_antes = int(round(carr._pos))
    g.despues.append(lambda: _carrusel_en(carr, k_antes))      # (el siguiente video no empieza en «Crea tu estilo»)
    yield 0.3
    yield from g.decir('La última tarjeta de Estilo es «Crea tu estilo»')
    carr._ir_a(k)
    yield 1.3
    yield g.mover(lambda: _centro_carta(g, carr, k), 1.0)
    yield g.esperar_voz(0.1)
    g.clic(real=False)
    yield 0.25
    v._plantillas_ventana._crear_estilo()
    dlg = v._plantillas_ventana._galeria_estilo
    yield 0.6
    g.poner_fuente(dlg)
    g.cursor = QPointF(dlg.width() * 0.55, dlg.height() * 0.62)
    yield 1.8                                                   # (las miniaturas de la galería tardan en salir: antes se veían negras)
    base, prin = dlg._rej_base, dlg._rej_prin
    previa = next((x for x in dlg.findChildren(QWidget) if type(x).__name__ == '_Previa' and x.isVisible()), None)

    def celda(rej, i):
        r = rej._rect(i)
        c = rej.mapTo(dlg, r.center().toPoint())
        return QPointF(c.x(), c.y())
    g.camara_a(g.rect(base).united(g.rect(prin)), 1.0, aire=1.04)       # de cerca: las tarjetas
    yield from g.decir('Elige un texto base: las palabras normales')
    yield g.mover(lambda: celda(base, 1), 1.0)
    yield 0.3
    g.clic()
    yield g.esperar_voz(0.2)
    yield from g.decir('Y los textos principales que quieras: se turnan frase a frase')
    yield g.mover(lambda: celda(prin, 0), 0.8)
    yield 0.2
    g.clic()
    yield 0.9
    yield g.mover(lambda: celda(prin, 3), 0.7)
    yield 0.2
    g.clic()
    yield 0.8
    yield g.mover(lambda: celda(prin, 4), 0.6)
    yield 0.2
    g.clic()
    yield g.esperar_voz(0.2)
    if previa is not None:                                              # la previa vertical: se turnan frase a frase
        g.camara_a(g.rect(previa).adjusted(-200, 0, 0, 0), 1.1, aire=1.08)
        g.poster()
        yield from g.decir('La previa te enseña cómo queda')
        yield g.esperar_voz(1.4)
    g.camara_a(None, 1.0)
    nombre = next((e for e in dlg.findChildren(QLineEdit) if e.isVisible()), None)
    if nombre is not None:
        yield from g.decir('Ponle un nombre y créalo')
        yield g.mover(lambda: g.centro(nombre), 1.0)
        g.clic()
        yield 0.2
        nombre.selectAll()
        yield g.teclear('Mi estilo de reels', nombre, 55)
        yield 0.3
        crear = por_texto(dlg, 'Crear mi estilo', QAbstractButton)
        if crear is not None:
            yield g.mover(lambda: g.centro(crear), 0.8)
        yield g.esperar_voz(1.0)
    try:
        dlg.close()
    except Exception:
        pass
    g.poner_fuente(v)


def g_probar(g):
    """v5.82: probar los estilos en la página Estilo: arrastrar, la rueda, «Solo captions | Con PRO» y usar uno."""
    v = g.v
    v.ir_a('nuevo', animar=False)
    carr = _carrusel(v)
    _al_en_uso(carr)
    k_crea = next((i for i, c in enumerate(carr._cartas) if c.tipo == 'anadir'), len(carr._cartas))
    k0 = k_uso = int(round(carr._pos))
    if k0 > k_crea - 3:                               # (sitio a la derecha: arrastre y rueda nunca llegan a «Crea tu estilo»)
        _carrusel_en(carr, max(0, k_crea - 3))
    yield 0.4
    k0 = int(round(carr._pos))

    def pildora(cual):
        geo = carr._pill_geo
        if not geo:
            return _centro_carta(g, carr, round(carr._pos))
        r = geo[1] if cual == 'pro' else geo[2]
        c = carr.mapTo(g.fuente, r.center().toPoint())
        return QPointF(c.x(), c.y())
    yield from g.decir('Pasa los estilos arrastrando las tarjetas')
    centro = _centro_carta(g, carr, k0)
    yield g.mover(centro, 1.0)
    g.apretar()
    yield 0.12
    paso = carr._medidas()[0] * carr.PASO                # una tarjeta justa, despacio (sin inercia al soltar)
    yield g.mover(QPointF(centro.x() - paso, centro.y() + 6), 1.0)
    yield 0.15
    g.soltar()
    yield 1.3
    yield g.esperar_voz(0.1)
    yield from g.decir('O con la rueda del ratón')
    yield g.mover(lambda: _centro_carta(g, carr, round(carr._pos)), 0.6)
    g.rueda(carr, 1)
    yield 1.2
    if carr._cartas[int(round(carr._pos))].tipo == 'anadir':   # (por si acaso: nunca la tarjeta de «Crea tu estilo»)
        g.rueda(carr, -1)
        yield 1.0
    yield g.esperar_voz(0.2)
    k = round(carr._pos)
    g.camara_a(_rect_carta(g, carr, k).adjusted(-60, -10, 60, 90), 1.0, aire=1.05)
    yield from g.decir('«Solo captions» enseña solo los subtítulos')
    yield g.mover(lambda: pildora('sin'), 1.0)
    yield 0.2
    g.clic()
    yield g.esperar_voz(0.8)
    yield from g.decir('La opción «Con PRO» suma la edición de video: zooms, efectos y más')     # («Con PRO» solo sonaba a «compró»)
    yield g.mover(lambda: pildora('pro'), 0.7)
    yield 0.2
    g.clic()
    g.poster()
    yield g.esperar_voz(1.2)
    g.camara_a(None, 1.0)
    pro = next((x for x in v.findChildren(QAbstractButton) if type(x).__name__ == 'BotonCompacto' and getattr(x, 'tipo', '') == 'pro'
                and x.isVisible()), None)
    if pro is not None:
        yield from g.decir('Y con «Activar edición PRO», GO también edita tu video')
        yield g.mover(lambda: g.centro(pro), 1.0)
        yield g.esperar_voz(0.4)
    yield from g.decir('Cuando te guste uno, haz clic en el del centro para usarlo')
    yield g.mover(lambda: _centro_carta(g, carr, round(carr._pos)), 1.0)
    yield 0.5
    if carr._cartas[int(round(carr._pos))].tipo != 'anadir':
        g.clic()
    yield g.esperar_voz(1.0)
    valor0 = carr._cartas[k_uso].valor if 0 <= k_uso < len(carr._cartas) else None

    def volver():                                     # (ya sin grabar: el estilo de antes vuelve a estar en uso, para los demás videos)
        _carrusel_en(carr, k_uso)
        if valor0 is not None:
            carr.elegida.emit(valor0)
    g.despues.append(volver)


def g_premiere(g):
    """v5.82: cambiar GO de DaVinci Resolve a Premiere Pro (Ajustes › General) y un GO en Premiere."""
    v = g.v
    p = v.go_panel
    v._pintar_go_reposo = lambda *a, **k: None
    v.ir_a('inicio', animar=False)
    _pasos_de(p, 'resolve')
    _reposo(p)
    ver = p.al_ver_resolve                            # (con Premiere, «Ver en Resolve» no pinta nada al final: no se enseña)
    p.al_ver_resolve = None
    g.despues += [lambda: setattr(p, 'al_ver_resolve', ver), lambda: _pasos_de(p, 'resolve'), lambda: _reposo(p)]
    yield 0.4
    yield from g.decir('¿Editas en Premiere Pro? Abre los ajustes')
    yield from _abrir_ajustes(g, 'general')
    dlg = g.dlg
    if dlg is None:
        return
    f_res, f_pre, f_mp4 = _fila(dlg, 'Usar con DaVinci Resolve'), _fila(dlg, 'Usar con Premiere Pro'), _fila(dlg, 'Video sin editores (DaVinci y Premiere)')
    if f_res is not None and f_mp4 is not None:
        g.camara_a(g.rect(f_res).united(g.rect(f_mp4)), 1.0, aire=1.08)
    yield g.esperar_voz(0.1)
    llave = _llave(f_pre)
    yield from g.decir('En General, enciende «Usar con Premiere Pro»')
    if llave is not None:
        yield g.mover(lambda: _punto_llave(g, llave), 1.1)
        yield g.esperar_voz(0.1)
        g.clic()
        g.poster()
    yield 0.8
    yield from g.decir('Solo uno va encendido: el de DaVinci Resolve se apaga solo')
    llave_r = _llave(f_res)
    if llave_r is not None:
        yield g.mover(lambda: _punto_llave(g, llave_r), 1.0)
    yield g.esperar_voz(0.3)
    yield from g.decir('Para volver, enciende otra vez el de DaVinci Resolve')
    yield g.esperar_voz(0.3)
    g.camara_a(None, 1.0)
    listo = por_texto(dlg, M.tr('Listo'), QAbstractButton)
    if listo is not None:
        yield g.mover(lambda: g.centro(listo), 1.0)
        yield 0.2
        g.clic()
        yield 0.9
    _cerrar_ajustes(g)
    _pasos_de(p, 'premiere')
    _reposo(p, 'premiere')
    g.camara_a(g.rect(p.boton).adjusted(-60, -40, 60, 190), 1.1, aire=1.1)
    yield from g.decir('Inicio ya dice que trabajas con Premiere Pro')
    yield g.esperar_voz(0.3)
    g.camara_a(None, 1.0)
    g.cursor = QPointF(-60, 640)
    g.con_archivo(True)
    yield from g.decir('Suelta tu video y GO arma la secuencia: video, subtítulos y sonidos')
    yield g.mover(QPointF(470, 520), 1.6)
    yield 0.2
    yield g.soltar_archivo(0.3)
    p.empezar()
    yield _trabajar(p, ['timeline', 'voz', 'ia', 'diseno', 'sfx', 'resolve'], 0.6)
    yield g.esperar_voz()
    p.paso('resolve', 'hecho')
    p.terminar(True, M.tr('Listo: en Premiere Pro, secuencia «{s}». Pulsa GO para otro.', s='mi_video'),
               [(12, 'bloques', 'n'), (48, 'palabras', 'n'), (18.5, 'duración', 't')])
    yield from g.decir('Si Premiere está cerrado, CineCaptions lo abre solo')
    yield g.esperar_voz(1.0)
    _pasos_de(p, 'resolve')
    _reposo(p)


def g_sin_editores(g):
    """v5.82: cambiar a «Video sin editores (DaVinci y Premiere)»: GO devuelve una copia MP4 con los subtítulos."""
    v = g.v
    p = v.go_panel
    v._pintar_go_reposo = lambda *a, **k: None
    v.ir_a('inicio', animar=False)
    _pasos_de(p, 'resolve')
    _reposo(p)
    ver = p.al_ver_resolve                            # (sin editores, «Ver en Resolve» no pinta nada al final: no se enseña)
    p.al_ver_resolve = None
    g.despues += [lambda: setattr(p, 'al_ver_resolve', ver), lambda: _pasos_de(p, 'resolve'), lambda: _reposo(p)]
    yield 0.4
    yield from g.decir('¿No usas editor de video? Abre los ajustes')
    yield from _abrir_ajustes(g, 'general')
    dlg = g.dlg
    if dlg is None:
        return
    f_res, f_mp4 = _fila(dlg, 'Usar con DaVinci Resolve'), _fila(dlg, 'Video sin editores (DaVinci y Premiere)')
    if f_res is not None and f_mp4 is not None:
        g.camara_a(g.rect(f_res).united(g.rect(f_mp4)), 1.0, aire=1.08)
    yield g.esperar_voz(0.1)
    llave = _llave(f_mp4)
    yield from g.decir('Enciende «Video sin editores»')
    if llave is not None:
        yield g.mover(lambda: _punto_llave(g, llave), 1.1)
        yield g.esperar_voz(0.05)
        g.clic()
        g.poster()
    yield g.esperar_voz(0.5)
    yield from g.decir('GO graba los subtítulos y los sonidos en una copia MP4 de tu video')
    yield g.esperar_voz(0.3)
    g.camara_a(None, 1.0)
    listo = por_texto(dlg, M.tr('Listo'), QAbstractButton)
    if listo is not None:
        yield g.mover(lambda: g.centro(listo), 1.0)
        yield 0.2
        g.clic()
        yield 0.9
    _cerrar_ajustes(g)
    _pasos_de(p, 'mp4')
    _reposo(p, 'mp4')
    g.cursor = QPointF(-60, 640)
    g.con_archivo(True)
    yield from g.decir('Suelta tu video y pulsa GO: no hace falta DaVinci ni Premiere')
    yield g.mover(QPointF(470, 520), 1.6)
    yield 0.2
    yield g.soltar_archivo(0.3)
    p.empezar()
    yield _trabajar(p, ['timeline', 'voz', 'ia', 'diseno', 'sfx', 'resolve'], 0.6)
    yield g.esperar_voz()
    p.paso('resolve', 'hecho')
    p.terminar(True, M.tr('Listo: «{n}», junto a tu video. Pulsa GO para otro.', n='mi_video (CineCaptions).mp4'),
               [(12, 'bloques', 'n'), (48, 'palabras', 'n'), (18.5, 'duración', 't')])
    g.camara_a(g.rect(p.boton).adjusted(-80, -40, 80, 210), 1.1, aire=1.1)
    yield from g.decir('Tu video con subtítulos queda junto al original')
    yield g.esperar_voz(1.0)
    g.camara_a(None, 0.8)
    yield 0.6
    _pasos_de(p, 'resolve')
    _reposo(p)


def g_interfaz(g):
    """v5.82: Ajustes › Interfaz: la escena de Inicio (pasar el ratón la mueve), el fondo y el color de resaltado."""
    v = g.v
    v.ir_a('inicio', animar=False)
    yield 0.3
    yield from g.decir('En los ajustes, Interfaz cambia cómo se ve CineCaptions')
    yield from _abrir_ajustes(g, 'interfaz')
    dlg = g.dlg
    if dlg is None:
        return
    tarjetas = list(getattr(dlg, '_tarjetas_estilo', []) or [])
    if tarjetas:
        g.camara_a(g.rect(tarjetas[0]).united(g.rect(tarjetas[-1])), 1.0, aire=1.12)
    yield g.esperar_voz(0.1)
    yield from g.decir('Pasa el ratón por una escena para verla en movimiento')
    if tarjetas:
        yield g.mover(lambda: g.centro(tarjetas[0], 0, -20), 1.0)
        yield 1.6
        yield g.mover(lambda: g.centro(tarjetas[-1], 0, -20), 1.0)
        yield 1.2
    yield g.esperar_voz(0.1)
    elegida = next((t for t in tarjetas if t.isChecked()), tarjetas[0] if tarjetas else None)
    otra = next((t for t in reversed(tarjetas) if t is not elegida), None)
    if otra is not None:
        yield from g.decir('Haz clic en la que más te guste')
        yield g.mover(lambda: g.centro(otra, 0, -20), 0.5)
        yield 0.2
        g.clic()
        g.poster()
        yield g.esperar_voz(0.6)
    zona = dlg.pila.currentWidget()
    barra = zona.verticalScrollBar() if hasattr(zona, 'verticalScrollBar') else None
    f_fondo = _fila(dlg, 'Fondo de la interfaz')
    f_acento = _fila(dlg, 'Color de resaltado')
    g.camara_a(None, 0.9)
    if barra is not None:
        yield _desplazar(barra, barra.maximum(), 900)
    seg = next((x for x in f_fondo.findChildren(QWidget) if type(x).__name__ == 'Segmentado'), None) if f_fondo else None
    if f_fondo is not None and f_acento is not None:
        g.camara_a(g.rect(f_fondo).united(g.rect(f_acento)), 1.0, aire=1.15)
    if seg is not None:
        yield from g.decir('Elige el fondo: azul o negro')
        actual = seg._indice()
        for i in ([1 - actual, actual] if actual in (0, 1) else [0]):
            r = seg._rect(i)
            yield g.mover(lambda r=r: g.centro(seg, r.center().x() - seg.width() / 2, 0), 0.8)
            yield 0.2
            g.clic()
            yield 0.9
        yield g.esperar_voz(0.2)
    muestras = getattr(dlg, '_muestras', None)
    if muestras is not None:
        yield from g.decir('Y el color de resaltado que más te guste')
        paso = getattr(muestras, 'PASO', 42)
        for i in (2, 4):
            yield g.mover(lambda i=i: g.centro(muestras, (i + 0.5) * paso - muestras.width() / 2, -11), 0.7)
            yield 0.5
        yield g.esperar_voz(0.2)
    aplicar = por_texto(dlg, M.tr('Aplicar'), QAbstractButton)
    g.camara_a(None, 1.0)
    yield from g.decir('Pulsa «Aplicar»: el fondo, el color, el idioma y el tamaño se ven al reiniciar')
    if aplicar is not None:
        yield g.mover(lambda: g.centro(aplicar), 1.2)
    yield g.esperar_voz(0.9)
    _cerrar_ajustes(g)
    yield 0.4


def g_ayuda(g):
    """v5.82: Ajustes › Ayuda (soporte por WhatsApp, diagnóstico, versión y licencia). Solo se señala: ningún clic abre nada."""
    v = g.v
    v.ir_a('inicio', animar=False)
    yield 0.3
    yield from g.decir('¿Algo no funciona? Abre Ayuda en los ajustes')
    yield from _abrir_ajustes(g, 'ayuda')
    dlg = g.dlg
    if dlg is None:
        return
    wa = por_texto(dlg, M.tr('Escribir por WhatsApp'), QAbstractButton)
    if wa is None:
        wa = next((b for b in dlg.findChildren(QAbstractButton) if b.isVisible() and 'WhatsApp' in (b.text() or '')), None)
    tarjeta = wa.parentWidget() if wa is not None else None
    while tarjeta is not None and tarjeta.width() < 700:
        tarjeta = tarjeta.parentWidget()
    if tarjeta is not None:
        g.camara_a(tarjeta, 1.0, aire=1.15)
    yield g.esperar_voz(0.1)
    yield from g.decir('Escríbenos por WhatsApp: el informe de tu equipo va listo para enviar')
    if wa is not None:
        yield g.mover(lambda: g.centro(wa), 1.1)
    g.poster()
    yield g.esperar_voz(0.3)
    diag = por_texto(dlg, M.tr('Ejecutar diagnóstico'), QAbstractButton)
    if diag is not None:
        g.camara_a(g.rect(diag).adjusted(-760, -60, 40, 160), 1.0, aire=1.05)
        yield from g.decir('«Ejecutar diagnóstico» revisa Resolve, el motor de voz y tu licencia')
        yield g.mover(lambda: g.centro(diag), 1.0)
        yield g.esperar_voz(0.3)
    zona = dlg.pila.currentWidget()
    barra = zona.verticalScrollBar() if hasattr(zona, 'verticalScrollBar') else None
    g.camara_a(None, 1.0)
    if barra is not None:
        yield _desplazar(barra, barra.maximum(), 1000)
    yield from g.decir('Y abajo ves tu versión y tu licencia')
    yield g.mover(QPointF(g.tam()[0] * 0.5, g.tam()[1] * 0.62), 1.0)
    yield g.esperar_voz(1.0)
    _cerrar_ajustes(g)
    yield 0.3


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
    yield 0.4
    yield from g.decir('Después de GO, tus palabras aparecen aquí')
    yield g.esperar_voz(0.3)
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
    yield 0.5
    yield from g.decir('Elige un pincel: Principal es la palabra grande')
    destino = pincel('Principal')
    if destino is not None:
        yield g.mover(destino, 1.0)
        yield 0.25
        g.clic()
    yield g.esperar_voz(0.1)
    yield from g.decir('Toca una palabra para marcarla')
    yield g.mover(lambda: palabra(2), 0.9)
    yield 0.25
    g.clic()
    yield g.esperar_voz(0.3)
    yield from g.decir('Arriba es el texto pequeño de encima')
    destino = pincel('Arriba')
    if destino is not None:
        yield g.mover(destino, 0.9)
        yield 0.25
        g.clic()
    yield 0.6
    yield g.mover(lambda: palabra(0), 0.9)
    yield 0.25
    g.clic()
    g.poster()
    yield g.esperar_voz(0.3)
    destino = pincel('Principal')
    if destino is not None:
        yield g.mover(destino, 0.8)
        g.clic()
        yield 0.4
    yield g.mover(lambda: palabra(3), 0.7)
    g.clic()
    yield 0.8
    # corregir lo que se oyó mal: doble clic y escribir
    yield from g.decir('Con doble clic corriges lo que se oyó mal')
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
    yield g.esperar_voz(0.3)
    yield from g.decir('Y listo: palabra corregida')
    yield g.esperar_voz(0.8)
    g.camara_a(None, 1.0)
    yield 1.0
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
    yield 1.0
    pag = getattr(v, '_director_pagina', None) or v
    estilos = _de_clase(pag, 'TarjetaEstilo')            # Automático, Elegante, Dinámico, Lista, Cinética
    llaves = {x.text(): x for x in _de_clase(pag, 'Interruptor')}
    aplicar = por_texto(pag, 'Aplicar a Resolve', QAbstractButton)
    if estilos:                                          # v5.82: de cerca (antes la columna entera: la letra no se leía)
        g.camara_a(g.rect(estilos[0]).united(g.rect(estilos[-1])).adjusted(-30, -70, 260, 40), 1.0, aire=1.05)
    yield from g.decir('Elige cómo suena tu video')
    yield g.esperar_voz(0.2)
    def elegir(k):                                       # (las frases van literales en g.decir: voz_tutoriales.py las lee del código)
        yield g.mover(lambda: g.centro(estilos[k], -60, 0), 1.0)
        yield 0.2
        g.clic()
        yield g.esperar_voz(0.3)
    if len(estilos) > 2:
        yield from g.decir('Dinámico pone un efecto en cada palabra clave')
        yield from elegir(2)
    if len(estilos) > 1:
        yield from g.decir('Elegante usa pocos efectos, y suaves')
        yield from elegir(1)
    g.poster()
    fiesta = llaves.get('Fiesta o mar') or next(iter(llaves.values()), None)
    if fiesta is not None:
        g.camara_a(g.rect(fiesta).adjusted(-40, -150, 300, 150), 1.0, aire=1.05)
        yield from g.decir('Enciende o apaga cada opción con su interruptor')
        yield g.mover(lambda: g.centro(fiesta, -fiesta.width() / 2 + 22, 0), 1.0)
        yield 0.2
        g.clic()
        yield 1.1
        g.clic()
        yield g.esperar_voz(0.3)
    if aplicar is not None:
        g.camara_a(g.rect(aplicar).adjusted(-40, -170, 40, 60), 1.0, aire=1.1)
        yield from g.decir('«Aplicar a Resolve» pone los cambios en tu timeline')
        yield g.mover(lambda: g.centro(aplicar), 1.0)
        yield g.esperar_voz(0.3)
    if estilos:
        g.camara_a(g.rect(estilos[0]).united(g.rect(estilos[-1])).adjusted(-30, -70, 260, 40), 1.0, aire=1.05)
        yield from g.decir('Automático elige según tu estilo')
        yield g.mover(lambda: g.centro(estilos[0], -60, 0), 1.0)
        yield 0.2
        g.clic()
        yield g.esperar_voz(0.6)
    g.camara_a(None, 1.0)
    yield 1.0


def g_efectos(g):
    v = g.v
    v.ir_a('efectos', animar=False)
    yield 1.0
    pag = getattr(v, '_efectos_widget', None) or v
    secciones = _de_clase(pag, 'SeccionEstilo')
    if not secciones:
        return
    s1 = secciones[0]
    cartas = sorted([x for x in s1.findChildren(QWidget) if type(x).__name__ == 'TarjetaEfecto' and x.isVisible()],
                    key=lambda x: x.mapTo(v, QPoint(0, 0)).x())
    llave = next(iter(_de_clase(s1, 'Interruptor')), None)
    yield from g.decir('Aquí eliges los efectos que GO pone solo')
    g.camara_a(g.rect(s1), 1.0, aire=1.02)
    yield g.esperar_voz(0.2)
    yield from g.decir('El gancho del inicio es el primer segundo de tu video')
    yield g.esperar_voz(0.2)
    yield from g.decir('Toca una tarjeta para elegirla')
    elegida = next((i for i, c in enumerate(cartas) if getattr(c, 'elegida', getattr(c, '_elegida', False))), 4)
    for k in (5, 2):                                   # Fuego, Lima eléctrica
        if len(cartas) > k:
            yield g.mover(lambda k=k: g.centro(cartas[k], 0, -40), 1.0)
            yield 0.2
            g.clic()
            if k == 5:
                g.poster()
            yield 1.3
    yield g.esperar_voz(0.1)
    if llave is not None:                              # apagar y volver a encender en GO
        yield from g.decir('Apágalo o enciéndelo con su interruptor')
        yield g.mover(lambda: g.centro(llave, -llave.width() / 2 + 22, 0), 1.0)
        yield 0.2
        g.clic()
        yield 1.0
        g.clic()
        yield g.esperar_voz(0.3)
    if len(cartas) > elegida:                          # vuelve a la que estaba
        yield g.mover(lambda: g.centro(cartas[elegida], 0, -40), 0.9)
        g.clic()
        yield 0.6
    zona = next((s for s in v.findChildren(QScrollArea) if s.isVisible() and s.height() > 500), None)
    if zona is not None and len(secciones) > 1:
        g.camara_a(None, 1.0)
        yield from g.decir('Más abajo: captions detrás de ti, emojis y más')
        barra = zona.verticalScrollBar()
        a = barra.value()
        b = min(barra.maximum(), a + int(secciones[1].mapTo(zona.widget(), QPoint(0, 0)).y() - 20))
        yield _desplazar(barra, b, 1050)
        yield 0.3
        s2 = secciones[1]
        cartas2 = sorted([x for x in s2.findChildren(QWidget) if type(x).__name__ == 'TarjetaEfecto' and x.isVisible()],
                         key=lambda x: x.mapTo(v, QPoint(0, 0)).x())
        g.camara_a(g.rect(s2), 1.0, aire=1.02)
        if len(cartas2) > 2:
            yield g.mover(lambda: g.centro(cartas2[2], 0, -40), 1.0)
            yield 0.2
            g.clic()
            yield g.esperar_voz(0.2)
            yield from g.decir('GO aplica solo lo que elijas')
            yield g.mover(lambda: g.centro(cartas2[1], 0, -40), 0.8)
            g.clic()
            yield g.esperar_voz(0.6)
        g.camara_a(None, 1.0)
        yield _desplazar(barra, a, 900)
        yield 0.4


def g_ajustes(g):
    v = g.v
    v.ir_a('inicio', animar=False)
    yield 0.4
    yield from g.decir('El engranaje abre los ajustes rápidos')
    r = v.isla.rect_de('ajustes')
    yield g.mover(QPointF(r.center()), 1.2)
    yield 0.2
    g.clic()                                          # el panel rápido
    yield g.esperar_voz(0.3)
    expandir = por_texto(v, M.tr('Expandir ajustes'), QAbstractButton)
    if expandir is not None:
        yield from g.decir('«Expandir ajustes» los abre todos')
        yield g.mover(lambda: g.centro(expandir), 1.0)
        yield 0.2
        g.clic()
        yield g.esperar_voz(0.2)
    dlg = getattr(v, '_ventana_ajustes', None)
    if dlg is None:
        dlg = next((x for x in v.findChildren(ajustes_ui.VentanaAjustes) if x.isVisible()), None)
    if dlg is None:
        return
    g.dlg = dlg
    f_res, f_mp4 = _fila(dlg, 'Usar con DaVinci Resolve'), _fila(dlg, 'Video sin editores (DaVinci y Premiere)')
    if f_res is not None and f_mp4 is not None:
        g.camara_a(g.rect(f_res).united(g.rect(f_mp4)), 1.0, aire=1.1)
    yield from g.decir('En General eliges con qué trabaja GO: Resolve, Premiere o solo el video')
    yield g.esperar_voz(0.3)
    g.camara_a(None, 1.0)
    k = dlg.PESTANAS.index('interfaz') if 'interfaz' in dlg.PESTANAS else 1
    yield from g.decir('En Interfaz, el idioma, el fondo y la escena de Inicio')
    yield g.mover(lambda: _pestana(g, dlg, k), 1.0)
    yield 0.2
    g.clic()
    yield g.esperar_voz(0.4)
    k = dlg.PESTANAS.index('tutoriales') if 'tutoriales' in dlg.PESTANAS else len(dlg.PESTANAS) - 2
    yield from g.decir('En Tutoriales están todos estos videos')
    yield g.mover(lambda: _pestana(g, dlg, k), 1.0)
    yield 0.2
    g.clic()
    g.poster()
    yield 1.2
    lista = getattr(dlg, '_tut_filas', None) or []
    if len(lista) > 2:
        yield g.mover(lambda: g.centro(lista[1]), 1.0)
        yield 0.2
        g.clic()
    yield g.esperar_voz(0.6)
    guia = getattr(dlg, '_tut_interruptor', None)
    if guia is not None:
        zona = next((s for s in dlg.findChildren(QScrollArea) if s.isVisible() and s.height() > 300), None)
        if zona is not None:
            zona.ensureWidgetVisible(guia, 20, 60)
            yield 0.4
        yield from g.decir('Y aquí apagas o enciendes esta guía')
        yield g.mover(lambda: g.centro(guia), 1.0)
        yield 0.2
        g.clic()
        yield 0.9
        g.clic()
        yield g.esperar_voz(0.8)
    _cerrar_ajustes(g)
    yield 0.6


GUIONES = {'inicio': g_inicio, 'estilo': g_estilo, 'crea': g_crea, 'corrector': g_corrector, 'sonido': g_sonido, 'efectos': g_efectos,
           'ajustes': g_ajustes, 'probar': g_probar, 'premiere': g_premiere, 'sin_editores': g_sin_editores, 'interfaz': g_interfaz,
           'ayuda': g_ayuda}


def grabar(v, ident, salida):
    print(f'· {ident}…', flush=True)
    _PREFS_MEM.clear()                                # v5.82: cada video empieza con las prefs reales (Premiere / sin editores no se arrastran)
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
    for fn in g.despues:                              # v5.82: deshacer lo del guion, ya sin grabar
        try:
            fn()
        except Exception:
            pass
    for _ in range(30):
        app.processEvents()
        time.sleep(0.01)
    print(f'  {ident}: {t:.1f} s, {graba.cuadros} cuadros' + (f'  FALLO {graba.fallo}' if graba.fallo else ''), flush=True)
    if not graba.fallo and not graba.jpg.is_file():   # v5.82: el guion no marcó miniatura: un cuadro a un tercio del video
        try:
            import av
            with av.open(str(graba.mp4)) as c:
                s = c.streams.video[0]
                objetivo = graba.cuadros / float(FPS) / 3.0
                for fr in c.decode(s):
                    if float(fr.pts * s.time_base) >= objetivo:
                        fr.to_image().save(str(graba.jpg), quality=86)
                        break
        except Exception:
            pass
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
        try:                                          # v5.82: la locución de cada idioma
            hechos = montar_voz(ident, sorted(g.voces), fin_v, salida)
            if hechos:
                print(f'  {ident}: voz en {", ".join(hechos)}', flush=True)
        except Exception:
            import traceback
            traceback.print_exc()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--salida', default=str(tutoriales.carpeta()))
    ap.add_argument('--voz', default='el_andre', help='la voz de voz_tutoriales.py (su índice de frases): ElevenLabs «Andre», la que viaja')
    ap.add_argument('--voz-idiomas', default='es', help='los idiomas con locución (el guion espera a la frase más larga de todos)')
    a = ap.parse_args()
    ids = a.ids or list(GUIONES)
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    cargar_voz(a.voz, [x.strip() for x in a.voz_idiomas.split(',') if x.strip()])
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
