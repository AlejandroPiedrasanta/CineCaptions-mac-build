# CineCaptions · By Cinema Productions
# 1_codigo/posiciones_pro.py — «Posición» de cada efecto de la Edición PRO: el usuario marca en la línea de tiempo de SU video (con sus
# fotogramas) los segundos donde quiere cada efecto y GO lo pone ahí: solo ahí o, además, donde lo elige el automático.
"""
posiciones_pro.py
-----------------
v5.22 (el usuario: «en la página de Efectos, al hacer doble clic o con el botón Posición, la sección cambia y me muestra la línea de tiempo
con sus fotogramas para indicar dónde lo quiero; en todas las secciones; por ejemplo "detrás de ti" en el segundo tal; varias veces; que
sea interactivo y útil» y «deja un botón para decidir: solo mis marcas o mis marcas + automático»).

Datos: ~/DaVinciSubtitles/posiciones_pro.json = {clave del video: {'video': ruta, 'secciones': {sección: {'modo': 'solo'|'suma',
'ts': [s, …]}}}} (siempre con archivos_seguros). Los segundos son del ARCHIVO de video; GO los pasa a su timeline (con las pausas
quitadas, pausas.mapear) con para_plan().

    leer(ruta) / guardar(ruta, sección, ts, modo)     las marcas de un video
    para_plan(ruta, recorte)                           {sección: {'modo', 'ts' (s del timeline de GO)}} de las secciones ENCENDIDAS
    fotogramas(ruta)                                   las miniaturas del video (PyAV, en caché; derechas aunque el móvil grabe «acostado»)
    palabras(ruta)                                     lo que se dice y cuándo (de la caché de la voz, si ese video ya se transcribió)
    VistaPosiciones                                    la vista de Efectos: la línea de tiempo con fotogramas, las marcas y el modo

En GO (edicion_pro): las secciones «ligadas» a un caption (detrás de ti, píldora) eligen el bloque de captions de ese segundo; las demás
(gancho, escenas, kit, gráficos, B-roll) empiezan JUSTO en la marca con la pieza más cercana a lo que se dice ahí; «Motions completo» solo
sale en los tramos marcados (con «+ automático», en todo el video, como siempre).
"""
import hashlib
import json
import os
from pathlib import Path

from i18n import tr

ARCHIVO = Path.home() / 'DaVinciSubtitles' / 'posiciones_pro.json'
CACHE = Path.home() / 'DaVinciSubtitles' / 'cache_posiciones'
MODOS = ('solo', 'suma')
SECCIONES = ('detras', 'gancho', 'pildora', 'broll', 'motions_completo', 'escenas', 'kit', 'graficos')
LIGADAS = ('detras', 'pildora')          # van con un bloque de captions: la marca elige el bloque de ese segundo
N_FOTOS = 60
ALTO_FOTO = 120
PASO = 0.1                               # las marcas van en décimas de segundo
_PROVEEDOR = None


# ======================================================================================================================== datos
def clave_video(ruta):
    try:
        return os.path.normcase(os.path.abspath(str(ruta)))
    except Exception:
        return str(ruta)


def _todo():
    try:
        import archivos_seguros
        d = archivos_seguros.leer_json(ARCHIVO, defecto={})
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def leer(ruta):
    """{sección: {'modo': 'solo'|'suma', 'ts': [s ordenados]}} de ese video ({} si no tiene marcas)."""
    if not ruta:
        return {}
    e = _todo().get(clave_video(ruta)) or {}
    out = {}
    for sec, m in (e.get('secciones') or {}).items():
        if not isinstance(m, dict):
            continue
        ts = sorted(round(float(t), 2) for t in m.get('ts') or [] if isinstance(t, (int, float)) and t >= 0)
        out[sec] = {'modo': m.get('modo') if m.get('modo') in MODOS else 'solo', 'ts': ts}
    return out


def guardar(ruta, seccion, ts, modo='solo'):
    """Guarda las marcas de una sección de ese video (las demás secciones y videos no se tocan). True si se guardó."""
    if not ruta or seccion not in SECCIONES:
        return False
    clave = clave_video(ruta)
    e = dict(_todo().get(clave) or {})
    secciones = dict(e.get('secciones') or {})
    limpias = sorted({round(max(0.0, float(t)), 2) for t in ts or []})
    if limpias or modo != 'solo':
        secciones[seccion] = {'modo': modo if modo in MODOS else 'solo', 'ts': limpias}
    else:
        secciones.pop(seccion, None)
    e.update(video=str(ruta), secciones=secciones)
    try:
        import archivos_seguros
        return bool(archivos_seguros.mezclar_json(ARCHIVO, {clave: e}))
    except Exception:
        return False


def resumen(ruta, seccion):
    """(cuántas marcas, modo) de una sección de ese video."""
    m = leer(ruta).get(seccion) or {}
    return len(m.get('ts') or []), m.get('modo') or 'solo'


def _mapear(t, segmentos):
    """El segundo `t` de la fuente en el timeline recortado; si cae en una pausa quitada, el instante con voz más cercano."""
    import pausas
    n = pausas.mapear(t, segmentos)
    if n is not None:
        return n
    for d in range(1, 31):
        for s in (+1, -1):
            n = pausas.mapear(t + s * d * 0.1, segmentos)
            if n is not None:
                return n
    return None


def para_plan(ruta, recorte=None):
    """Las marcas de ese video para GO: {sección: {'modo', 'ts' (segundos de SU timeline)}}, solo de las secciones encendidas en GO."""
    datos = leer(ruta)
    if not datos:
        return {}
    try:
        import pro_lateral_ui as LAT
        encendida = LAT.estado
    except Exception:
        encendida = None
    segs = (recorte or {}).get('segmentos') if recorte else None
    out = {}
    for sec, m in datos.items():
        if not m['ts']:
            continue
        try:
            if encendida is not None and not encendida(sec):
                continue
        except Exception:
            pass
        ts = []
        for t in m['ts']:
            n = _mapear(t, segs) if segs else t
            if n is not None:
                ts.append(round(float(n), 3))
        if ts:
            out[sec] = {'modo': m['modo'], 'ts': sorted(set(ts))}
    return out


def poner_proveedor(fn):
    """El programa dice cuál es el video de Inicio (el que va a usar GO)."""
    global _PROVEEDOR
    _PROVEEDOR = fn


def video_actual():
    """La ruta del video de Inicio (sin mirar el disco: se llama desde la interfaz; si no existe, la vista lo dice al leerlo en su hilo)."""
    try:
        r = _PROVEEDOR() if _PROVEEDOR else None
        r = str(r or '').strip().strip('"')
        return r or None
    except Exception:
        return None


# ======================================================================================================================== fotogramas y voz
AUDIO = ('.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.aif', '.aiff')


def _carpeta_de(ruta, extra=''):
    st = os.stat(ruta)
    return CACHE / hashlib.sha1(f'{clave_video(ruta)}|{st.st_size}|{st.st_mtime_ns}|{extra}'.encode('utf-8')).hexdigest()[:16]


def _duracion(ruta):
    import av
    with av.open(str(ruta)) as c:
        if c.duration:
            return float(c.duration / 1e6)
        s = (c.streams.audio or c.streams.video or [None])[0]
        return float(s.duration * s.time_base) if s is not None and s.duration else 0.0


def fuente_imagen(ruta):
    """v5.23 (el usuario: «cuando obtenga el audio debe traer el video, para que Efectos tenga el video»): (archivo con imagen, desfase s,
    duración del audio s | None). Un video: él mismo. El audio que «Obtener» renderiza del timeline de Resolve: el clip principal de V1
    (video_detectado.json), con el segundo del archivo que suena al empezar ese audio (`clip_principal_desde`; recortado o con zona no es
    0). (None, 0, None) si no hay imagen. En un HILO (lee el disco)."""
    if Path(str(ruta)).suffix.lower() not in AUDIO:
        return str(ruta), 0.0, None
    try:
        import resolve_bridge
        d = resolve_bridge.video_detectado() or {}
    except Exception:
        d = {}
    clip = d.get('clip_principal')
    if clip and clave_video(d.get('video_path') or '') == clave_video(ruta) and Path(str(clip)).is_file():
        try:
            return str(clip), float(d.get('clip_principal_desde') or 0.0), _duracion(ruta)
        except Exception:
            return str(clip), float(d.get('clip_principal_desde') or 0.0), None
    return None, 0.0, None


def fotogramas(ruta, n=N_FOTOS, alto=ALTO_FOTO):
    """{'dur', 'ancho', 'alto', 'fotos': [(t, ruta .jpg)], 'imagen': archivo} sobre el TIEMPO de `ruta` (en caché) o None si no tiene
    imagen. Con el audio de un timeline, la imagen sale de su clip principal (fuente_imagen). Corre en un HILO (PyAV)."""
    img, desde, dur_audio = fuente_imagen(ruta)
    if not img:
        return None
    carpeta = _carpeta_de(img, f'{ruta}|{desde}|{dur_audio}')
    meta = carpeta / 'meta.json'
    try:
        d = json.loads(meta.read_text(encoding='utf-8'))
        if d.get('fotos') and all((carpeta / f).exists() for _t, f in d['fotos']):
            return dict(d, fotos=[(t, str(carpeta / f)) for t, f in d['fotos']], imagen=img)
    except Exception:
        pass
    import av
    import rotacion_video
    k = rotacion_video.giro(img)
    fotos = []
    with av.open(str(img)) as c:
        if not c.streams.video:
            return None
        vs = c.streams.video[0]
        vs.thread_type = 'AUTO'
        dur_v = float(c.duration / 1e6) if c.duration else (float(vs.duration * vs.time_base) if vs.duration else 0.0)
        dur = float(dur_audio) if dur_audio else dur_v          # (la línea de tiempo es la del AUDIO que transcribe GO)
        if dur <= 0 or dur_v <= 0:
            return None
        carpeta.mkdir(parents=True, exist_ok=True)
        tb = float(vs.time_base)
        w = h = 0
        for i in range(n):
            t_linea = dur * (i + 0.5) / n
            t = min(max(0.0, t_linea + desde), dur_v - 0.05)     # el segundo del ARCHIVO que se ve en ese momento
            try:
                c.seek(int(t / tb), stream=vs, backward=True, any_frame=False)
                fr = None
                for j, f in enumerate(c.decode(vs)):          # desde el fotograma clave, unos pocos hacia el segundo pedido
                    fr = f
                    if (f.time is not None and f.time >= t - 0.05) or j >= 10:
                        break
                if fr is None:
                    continue
                foto = rotacion_video.derecho_img(fr.to_image(), k)
                w, h = foto.size
                foto.thumbnail((max(1, int(alto * w / max(1, h))), alto))
                nombre = f'{i:03d}.jpg'
                foto.convert('RGB').save(carpeta / nombre, quality=82)
                fotos.append((round(t_linea, 3), nombre))
            except Exception:
                continue
    if not fotos:
        return None
    d = {'dur': round(dur, 3), 'ancho': w, 'alto': h, 'fotos': fotos}
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(meta, d)
    except Exception:
        pass
    return dict(d, fotos=[(t, str(carpeta / f)) for t, f in fotos], imagen=img)


def palabras(ruta):
    """[(segundo, palabra)] de lo que se dice en ese video, si GO ya lo transcribió (la caché de la voz); [] si no."""
    try:
        import cache_voz
        nombre = Path(ruta).name
        archivos = sorted(cache_voz.CARPETA.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:120]
        for f in archivos:
            try:
                d = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            if d.get('video') == nombre and isinstance(d.get('palabras'), list):
                return [(float(p['start']), str(p.get('word') or '').strip()) for p in d['palabras'] if p.get('start') is not None]
    except Exception:
        pass
    return []


def texto_t(t):
    """0:12.4 · 1:05.0"""
    t = max(0.0, float(t))
    return f'{int(t // 60)}:{t % 60:04.1f}'


# ======================================================================================================================== la vista
try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
    from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
    import qt_kit as ui
    from qt_kit import Boton, Etiqueta, QColor, QColorReal, Segmentado, StringVar, correr_en_hilo, fuente
    _QT = True
except Exception:                                   # (GO y las pruebas sin interfaz importan solo los datos)
    _QT = False


if _QT:
    class LineaTiempo(QWidget):
        """Los fotogramas del video en una tira, la regla de tiempo y las marcas. Arriba, el fotograma bajo el ratón en grande y lo que se
        dice en ese momento. Clic = marca nueva (y se puede arrastrar) · arrastrar una marca = moverla · doble clic o clic derecho = quitarla ·
        ← → la mueven una décima (con Mayús, un segundo) · Supr la quita. Todo se guarda al momento."""
        cambio = Signal()
        cargado = Signal(str)                        # el archivo del que salen los fotogramas (con el audio de un timeline, su clip de V1)
        ALTO_TIRA, MARGEN, ALTO_REGLA = 64, 18, 22

        def __init__(self, seccion, padre=None):
            super().__init__(padre)
            self.seccion = seccion
            self.ruta = None
            self.modo = 'solo'
            self.dur = 0.0
            self.fotos = []                          # [(t, QPixmap)]
            self.palabras = []
            self.marcas = []
            self.aviso = ''
            self._t_sobre = None
            self._arr = None
            self._sel = None
            self._movido = False
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setMinimumHeight(340)

        # -- datos
        def cargar(self, ruta):
            self.ruta = ruta
            m = leer(ruta).get(self.seccion) or {}
            self.marcas = list(m.get('ts') or [])
            self.modo = m.get('modo') or 'solo'
            self.fotos, self.palabras, self.dur = [], [], 0.0
            self._sel = None
            self.aviso = tr('Leyendo los fotogramas del video…')
            self.update()

            def trabajo():
                return fotogramas(ruta), palabras(ruta)

            def fin(r, error):
                if ruta != self.ruta:
                    return
                if error is not None or not r or not r[0]:
                    self.aviso = (tr('Este audio no trae imagen: pulsa «Obtener» con tu timeline abierto en Resolve (trae su video) o «Elegir video…».')
                                  if Path(str(ruta)).suffix.lower() in AUDIO else tr('No pude leer la imagen de este video.'))
                    self.update()
                    return
                d, pals = r
                self.dur = float(d['dur'])
                self.fotos = [(t, QPixmap(f)) for t, f in d['fotos']]
                self.palabras = pals
                self.aviso = ''
                self.marcas = [t for t in self.marcas if t <= self.dur + 0.05]
                self.update()
                self.cargado.emit(str(d.get('imagen') or ruta))
            correr_en_hilo(self, trabajo, fin)

        def _guardar(self):
            if self.ruta:
                guardar(self.ruta, self.seccion, self.marcas, self.modo)
            self.cambio.emit()

        def poner_modo(self, modo):
            self.modo = modo if modo in MODOS else 'solo'
            self._guardar()

        def quitar_todas(self):
            self.marcas, self._sel = [], None
            self._guardar()
            self.update()

        # -- geometría
        def _tira(self):
            y = self.height() - self.ALTO_REGLA - self.ALTO_TIRA
            return QRectF(self.MARGEN, y, self.width() - 2 * self.MARGEN, self.ALTO_TIRA)

        def _x(self, t):
            r = self._tira()
            return r.left() + (t / self.dur) * r.width() if self.dur > 0 else r.left()

        def _t(self, x):
            r = self._tira()
            if self.dur <= 0 or r.width() <= 0:
                return 0.0
            t = (x - r.left()) / r.width() * self.dur
            return round(max(0.0, min(self.dur, t)) / PASO) * PASO

        def _marca_en(self, pos):
            r = self._tira()
            if not (r.top() - 44 <= pos.y() <= r.bottom() + 4):
                return None
            mejor, dist = None, 9.0
            for i, t in enumerate(self.marcas):
                d = abs(self._x(t) - pos.x())
                if d <= dist:
                    mejor, dist = i, d
            return mejor

        def _en_tira(self, pos):
            r = self._tira()
            return r.left() - 6 <= pos.x() <= r.right() + 6 and r.top() - 44 <= pos.y() <= r.bottom() + self.ALTO_REGLA

        # -- ratón y teclado
        def mousePressEvent(self, e):
            if self.dur <= 0:
                return
            pos = e.position()
            i = self._marca_en(pos)
            if e.button() == Qt.MouseButton.RightButton:
                if i is not None:
                    self._quitar(i)
                return
            if e.button() != Qt.MouseButton.LeftButton or not self._en_tira(pos):
                return
            self.setFocus()
            if i is None:                            # marca nueva donde se pulsó (y se puede arrastrar en el mismo gesto)
                self.marcas.append(self._t(pos.x()))
                i = len(self.marcas) - 1
                self._movido = True
            else:
                self._movido = False
            self._arr = self._sel = i
            self.update()

        def mouseMoveEvent(self, e):
            pos = e.position()
            if self.dur > 0 and self._en_tira(pos):
                self._t_sobre = self._t(pos.x())
            else:
                self._t_sobre = None
            if self._arr is not None:
                t = self._t(pos.x())
                if t != self.marcas[self._arr]:
                    self.marcas[self._arr] = t
                    self._movido = True
            hay = self._marca_en(pos) is not None or self._en_tira(pos)
            self.setCursor(Qt.CursorShape.SizeHorCursor if self._marca_en(pos) is not None else
                           Qt.CursorShape.PointingHandCursor if hay else Qt.CursorShape.ArrowCursor)
            self.update()

        def mouseReleaseEvent(self, e):
            if self._arr is not None:
                t = self.marcas[self._arr]
                self.marcas.sort()
                self._sel = self.marcas.index(t)
                self._arr = None
                if self._movido:
                    self._guardar()
                self.update()

        def mouseDoubleClickEvent(self, e):
            i = self._marca_en(e.position())
            if i is not None:
                self._quitar(i)

        def leaveEvent(self, e):
            self._t_sobre = None
            self.update()

        def keyPressEvent(self, e):
            if self._sel is None or self._sel >= len(self.marcas):
                return super().keyPressEvent(e)
            k = e.key()
            if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self._quitar(self._sel)
            elif k in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                paso = 1.0 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else PASO
                t = self.marcas[self._sel] + (paso if k == Qt.Key.Key_Right else -paso)
                self.marcas[self._sel] = round(max(0.0, min(self.dur, t)) / PASO) * PASO
                self._t_sobre = self.marcas[self._sel]
                t = self.marcas[self._sel]
                self.marcas.sort()
                self._sel = self.marcas.index(t)
                self._guardar()
                self.update()
            else:
                super().keyPressEvent(e)

        def _quitar(self, i):
            if 0 <= i < len(self.marcas):
                self.marcas.pop(i)
                self._sel = None
                self._arr = None
                self._guardar()
                self.update()

        # -- dibujo
        def _foto_en(self, t):
            if not self.fotos:
                return None
            return min(self.fotos, key=lambda f: abs(f[0] - t))[1]

        def _dicho_en(self, t):
            """Las palabras de ±2,5 s alrededor de t y cuál suena en t."""
            cerca = [(s, w) for s, w in self.palabras if t - 2.5 <= s <= t + 2.5]
            actual = max((s for s, _w in cerca if s <= t + 0.05), default=None)
            return cerca, actual

        def paintEvent(self, _e):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            tira = self._tira()
            acento = QColor(ui.ACCENT)
            if self.aviso or self.dur <= 0:
                p.setPen(QColor('#8EA2C6'))
                p.setFont(fuente(14, peso='medio'))
                p.drawText(QRectF(self.rect()), int(Qt.AlignmentFlag.AlignCenter), self.aviso or tr('Sin video.'))
                p.end()
                return
            # ---- arriba: el fotograma en grande y lo que se dice
            t_ver = self._t_sobre if self._t_sobre is not None else (self.marcas[self._sel] if self._sel is not None and self._sel < len(self.marcas) else
                                                                    (self.marcas[0] if self.marcas else 0.0))
            alto_prev = max(60.0, tira.top() - 58)
            pm = self._foto_en(t_ver)
            x_txt = self.MARGEN
            if pm is not None and not pm.isNull():
                ancho_prev = alto_prev * pm.width() / max(1, pm.height())
                caja = QRectF(self.MARGEN, 6, ancho_prev, alto_prev)
                camino = QPainterPath()
                camino.addRoundedRect(caja, 12, 12)
                p.save()
                p.setClipPath(camino)
                p.drawPixmap(caja.toRect(), pm)
                p.restore()
                p.setPen(QPen(QColorReal(255, 255, 255, 40), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(camino)
                x_txt = caja.right() + 22
            ancho_txt = self.width() - x_txt - self.MARGEN
            p.setPen(QColor('#FFFFFF'))
            p.setFont(fuente(26, peso='negrita'))
            p.drawText(QRectF(x_txt, 6, ancho_txt, 40), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto_t(t_ver))
            y = 52
            cerca, actual = self._dicho_en(t_ver)
            if cerca:
                p.setFont(fuente(15, peso='medio'))
                fm = QFontMetricsF(p.font())
                x, linea = x_txt, 0
                for s, w in cerca:
                    ancho = fm.horizontalAdvance(w + ' ')
                    if x + ancho > x_txt + ancho_txt:
                        linea += 1
                        x = x_txt
                        if linea >= 3:
                            break
                    p.setPen(acento if s == actual else (QColor('#E6EEFB') if s <= t_ver else QColor('#7D8DAA')))
                    p.drawText(QPointF(x, y + 20 + linea * 24), w)
                    x += ancho
                y += 20 + 3 * 24
            else:
                p.setPen(QColor('#7D8DAA'))
                p.setFont(fuente(13))
                p.drawText(QRectF(x_txt, y, ancho_txt, 40), int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
                           tr('Lo que dices saldrá aquí cuando GO haya transcrito este video.'))
                y += 52
            p.setPen(QColor('#8EA2C6'))
            p.setFont(fuente(12))
            ayuda = tr('Clic en la tira: añadir · arrastrar: mover · doble clic o clic derecho: quitar · ← → afinan (Mayús: 1 s)')
            p.drawText(QRectF(x_txt, max(y, alto_prev - 30), ancho_txt, 40), int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), ayuda)
            # ---- la tira de fotogramas
            camino = QPainterPath()
            camino.addRoundedRect(tira, 10, 10)
            p.save()
            p.setClipPath(camino)
            p.fillRect(tira, QColor('#0A1120'))
            if self.fotos:
                f0 = self.fotos[0][1]
                ancho_f = tira.height() * f0.width() / max(1, f0.height())
                n = max(1, int(tira.width() // max(8.0, ancho_f)) + 1)
                for j in range(n):
                    x = tira.left() + j * ancho_f
                    t = (x + ancho_f / 2 - tira.left()) / tira.width() * self.dur
                    pmj = self._foto_en(t)
                    if pmj is not None:
                        p.drawPixmap(QRectF(x, tira.top(), ancho_f, tira.height()).toRect(), pmj)
            p.fillRect(tira, QColorReal(5, 10, 20, 70))
            p.restore()
            p.setPen(QPen(QColorReal(255, 255, 255, 34), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(camino)
            # ---- la regla
            p.setFont(fuente(11))
            paso = next((s for s in (1, 2, 5, 10, 15, 30, 60, 120, 300) if tira.width() / max(1.0, self.dur / s) >= 70), 600)
            t = 0.0
            while t <= self.dur + 1e-6:
                x = self._x(t)
                p.setPen(QPen(QColorReal(255, 255, 255, 60), 1))
                p.drawLine(QPointF(x, tira.bottom() + 2), QPointF(x, tira.bottom() + 7))
                p.setPen(QColor('#7D8DAA'))
                p.drawText(QRectF(x - 30, tira.bottom() + 6, 60, 16), int(Qt.AlignmentFlag.AlignCenter), f'{int(t // 60)}:{int(t % 60):02d}')
                t += paso
            # ---- el ratón
            if self._t_sobre is not None and self._arr is None:
                x = self._x(self._t_sobre)
                p.setPen(QPen(QColorReal(255, 255, 255, 150), 1.4))
                p.drawLine(QPointF(x, tira.top() - 4), QPointF(x, tira.bottom() + 2))
            # ---- las marcas
            p.setFont(fuente(11, peso='negrita'))
            fm = QFontMetricsF(p.font())
            for i, t in enumerate(self.marcas):
                x = self._x(t)
                sel = i == self._sel
                p.setPen(QPen(acento, 2.4 if sel else 1.8))
                p.drawLine(QPointF(x, tira.top() - 12), QPointF(x, tira.bottom()))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(acento)
                p.drawEllipse(QPointF(x, tira.top() - 14), 6.5 if sel else 5.5, 6.5 if sel else 5.5)
                txt = texto_t(t)
                w = fm.horizontalAdvance(txt) + 14
                caja = QRectF(min(max(tira.left(), x - w / 2), tira.right() - w), tira.top() - 42, w, 20)
                p.setBrush(acento if sel else QColorReal(10, 18, 34, 230))
                p.setPen(QPen(acento, 1.2))
                p.drawRoundedRect(caja, 10, 10)
                p.setPen(QColorReal('#0B1220') if sel else QColor('#FFFFFF'))
                p.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), txt)
            p.end()

    class VistaPosiciones(QWidget):
        """La vista «Posición» de una sección de Efectos: el video, el modo (solo mis marcas / + automático), la línea de tiempo y «Listo»."""
        cambio = Signal()
        listo = Signal()
        MODOS_UI = (('solo', 'Solo mis marcas'), ('suma', 'Mis marcas + automático'))

        def __init__(self, seccion, padre=None):
            super().__init__(padre)
            self.seccion = seccion
            capa = QVBoxLayout(self)
            capa.setContentsMargins(0, 2, 0, 4)
            capa.setSpacing(10)
            fila = QHBoxLayout()
            fila.setSpacing(10)
            self._lbl_video = ui.Elidida('', 13, color='#C9D6EC') if hasattr(ui, 'Elidida') else Etiqueta('', 13, color='#C9D6EC')
            fila.addWidget(self._lbl_video, 1)
            nombres = [tr(n) for _k, n in self.MODOS_UI]
            self._v_modo = StringVar(nombres[0])
            self._seg = Segmentado(nombres, self._v_modo, self._cambio_modo, alto=32, tam=12)
            fila.addWidget(self._seg)
            fila.addWidget(Boton(tr('Elegir video…'), self._elegir_video, tipo='neutro', alto=32, tam=12))
            fila.addWidget(Boton(tr('Quitar todas'), self._quitar_todas, tipo='fantasma', alto=32, tam=12))
            fila.addWidget(Boton(tr('Listo'), self.listo.emit, tipo='primario', alto=32, tam=12))
            capa.addLayout(fila)
            self._lbl_modo = Etiqueta('', 12, color='#8EA2C6', envolver=True)
            capa.addWidget(self._lbl_modo)
            self.linea = LineaTiempo(seccion)
            self.linea.cambio.connect(self._al_cambiar)
            self.linea.cargado.connect(self._al_cargar)
            capa.addWidget(self.linea)

        def _al_cargar(self, imagen):
            ruta = self.linea.ruta or ''
            if imagen and clave_video(imagen) != clave_video(ruta):     # el audio de «Obtener»: la imagen es el clip de su timeline
                self._lbl_video.setText(tr('Video del timeline: ') + Path(imagen).name)

        def abrir(self, ruta=None):
            ruta = ruta or video_actual()
            if not ruta:
                self.linea.ruta = None
                self.linea.dur = 0.0
                self.linea.aviso = tr('Suelta un video en Inicio (o pulsa «Elegir video…») para marcar dónde va este efecto.')
                self._lbl_video.setText('')
                self.linea.update()
                self._pintar_modo()
                return
            self._lbl_video.setText(tr('Video: ') + Path(ruta).name)
            self.linea.cargar(ruta)
            self._v_modo.set(tr(dict(self.MODOS_UI)[self.linea.modo]))
            try:
                self._seg.refrescar() if hasattr(self._seg, 'refrescar') else self._seg.update()
            except Exception:
                pass
            self._pintar_modo()
            self.linea.setFocus()

        def _pintar_modo(self):
            ligada = self.seccion in LIGADAS
            if self.linea.modo == 'solo':
                txt = tr('GO pone este efecto SOLO en tus marcas (sin marcas, donde lo elija el automático).')
            else:
                txt = tr('GO lo pone en tus marcas y, además, donde lo elija el automático.')
            if self.seccion == 'motions_completo':
                txt = (tr('Solo mis marcas: el video de motions sale solo en los tramos que marques.') if self.linea.modo == 'solo'
                       else tr('Con «+ automático», el video de motions va en todo el video, como siempre.'))
            elif ligada:
                txt += ' ' + tr('Se usa el bloque de captions que suena en ese segundo.')
            n = len(self.linea.marcas)
            if n:
                txt += ' · ' + (tr('1 marca') if n == 1 else tr('{n} marcas', n=n))
            self._lbl_modo.setText(txt)

        def _cambio_modo(self, *_a):
            inv = {tr(n): k for k, n in self.MODOS_UI}
            self.linea.poner_modo(inv.get(str(self._v_modo.get()), 'solo'))
            self._pintar_modo()

        def _quitar_todas(self):
            self.linea.quitar_todas()
            self._pintar_modo()

        def _al_cambiar(self):
            self._pintar_modo()
            self.cambio.emit()

        def _elegir_video(self):
            from qt_kit import filedialog
            ruta = filedialog.askopenfilename(parent=self.window(), title=tr('Elige el video'),
                                              filetypes=[(tr('Videos'), '*.mp4 *.mov *.m4v *.mkv *.avi *.mxf'), (tr('Todos'), '*.*')])
            if ruta:
                self._a_mano = True
                self.abrir(ruta)

        def al_volver(self):
            """Al volver a Efectos: si el video de Inicio cambió (soltaste otro o pulsaste «Obtener»), se carga ese (salvo uno elegido a mano)."""
            actual = video_actual()
            if actual and not getattr(self, '_a_mano', False) and clave_video(actual) != clave_video(self.linea.ruta or ''):
                self.abrir(actual)
