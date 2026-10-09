# CineCaptions · By Cinema Productions
# 1_codigo/sfx_studio.py — la pantalla SFX Lab (biblioteca, pad XY, marcadores por color, reemplazar).
"""
sfx_studio.py
--------------
El SFX Lab: escuchar los efectos de sonido, retocarles el tono y la
velocidad, guardarlos, y (con Resolve abierto) mandarlos al timeline.

Lo importante:
  * Todos los sonidos de sfx_library/ aparecen en el arbol de la izquierda,
    agrupados por su carpeta (esenciales, extra/risers, extra/clics, etc.).
  * El usuario puede agregar sus propias carpetas de sonidos con "+".
    Quedan recordadas entre sesiones.
  * Los sonidos que uno usa mas se marcan con estrellita y aparecen arriba,
    en una seccion "Favoritos".
  * El pad XY es el corazon del estudio: soltar el mouse en cualquier lado
    ajusta tono (eje X) y velocidad (eje Y) y reproduce en el momento.
  * "Enviar a Resolve" guarda el WAV y le deja una orden al script que corre
    dentro de Resolve, que lo importa a una pista de audio vacia.

v5.0.0 (Qt, imagen 05 de la propuesta): deja de ser una ventana aparte y es
la pantalla «SFX Lab» del menu lateral, con tres columnas: biblioteca, el
sonido elegido (onda + pad + controles) y las reglas automaticas + los
efectos por color de marcador (antes un dialogo). La logica — ordenes para
Resolve, favoritos, carpetas, atajo global — es la de la v4.1.0.
"""
import json
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QKeySequence, QLinearGradient, QPainter, QPen, QRadialGradient, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QBoxLayout, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
                               QSizePolicy, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import qt_kit as ui
from qt_kit import (BooleanVar, Boton, Casilla, Chip, Combo, Deslizador, Desplazable, Enlace, Entrada,
                    Etiqueta, Onda, Punto, Segmentado, StringVar, Tarjeta, Tooltip, caja_h, caja_v,
                    cancelar, despues, ejecutar_en_ui, filedialog, limpiar_capa, messagebox)
from qt_kit import QColor  # v5.1: el QColor que sigue al tema (Ajustes > Interfaz)
import sfx_audio
import sidecar_lua
from i18n import tr
ACCENT = ui.ACCENT
ACCENT_HOVER = ui.ACCENT_HOVER
BG_COLOR = ui.BG_COLOR
CARD_COLOR = ui.CARD_COLOR
BORDER_COLOR = ui.BORDER_COLOR
TEXT_COLOR = ui.TEXT_COLOR
TEXT_MUTED = ui.TEXT_MUTED
RANGO_TONO = ((-12.0), 12.0)
RANGO_VELOCIDAD = (0.5, 2.0)
CARPETA_PREFS = Path.home() / 'DaVinciSubtitles'
from sfx_rules import ARCHIVO_FAVORITOS, ARCHIVO_CARPETAS, _leer_lista, _escribir_lista, cargar_favoritos, guardar_favoritos, cargar_carpetas_usuario, guardar_carpetas_usuario
ARCHIVO_PENDIENTE = CARPETA_PREFS / 'sfx_pendiente.json'
ARCHIVO_RECIENTES = CARPETA_PREFS / 'sfx_recientes.json'
# Ajustes rápidos del estudio: nombre, (tono en semitonos, velocidad, volumen), color del chip
AJUSTES_RAPIDOS = (('Normal', (0.0, 1.0, 1.0), '#4589FF'), ('Grave', (-5.0, 0.9, 1.0), '#B388FF'),
                   ('Agudo', (5.0, 1.0, 1.0), '#22D3EE'), ('Rápido', (0.0, 1.5, 1.0), '#24D18F'),
                   ('Lento', (0.0, 0.7, 1.0), '#F5B84B'), ('Radio', (3.0, 1.15, 0.9), '#FB7185'),
                   ('Épico', (-3.0, 0.8, 1.3), '#FDE047'))
ARCHIVO_REEMPLAZO = CARPETA_PREFS / 'sfx_reemplazo_pendiente.json'
ARCHIVO_MARCADORES = CARPETA_PREFS / 'sfx_marcadores_pendiente.json'
def dejar_orden(ruta, datos):
    """Deja una orden para Resolve: el .json de siempre Y su sidecar .lua.

    v3.1.9: en Free 21.1 el menu de Scripts no tiene io y los scripts SFX
    solo pueden leer la orden con loadfile (el patron de los subtitulos,
    v3.1.5). Lanza OSError como el write_text de antes.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    sidecar_lua.escribir_par(ruta, datos)
def retirar_orden(ruta):
    """Borra la orden y su sidecar tras un EXITO (v3.1.9).

    Sin io el script no puede borrarla, y una orden vieja volveria a
    colocar en la siguiente corrida manual. Con io el script ya borro el
    .json; el sidecar lo borra esto igual.
    """
    for f in [ruta, ruta.with_name(ruta.name + '.lua')]:
        try:
            f.unlink()
        except OSError:
            pass
def orden_reemplazo_marcadores(color_api, wav):
    """La orden de «⟲ Reemplazar» sobre los marcadores de UN color (v3.1.9).

    Pedido literal: «que tambien se pueda reemplazar efectos en los
    marcadores». Es la orden de siempre de «SFX en marcadores» con ese
    color -> el sonido del Lab, 'reemplazar' (quita el efecto nuestro que ya
    suena en el marcador) y 'solo_reemplazar' (un marcador sin efecto no
    recibe uno nuevo: esto CAMBIA efectos, no los pone). Module-level y sin
    interfaz: se prueba sin abrir el Lab.
    """
    mapa = {color_api: {'categoria': 'SFX Lab', 'archivos': [str(wav)]}}
    return {'mapa': mapa, 'ondas': analizar_ondas(mapa), 'reemplazar': True, 'solo_reemplazar': True, 'creado_en': time.time()}
def analizar_ondas(pendiente):
    """{ruta: {"pico": s, "dur": s}} para cada archivo de la orden.

    v1.0.69 (reporte literal 12-09: «detecte las ondas de audio y donde
    esta mas alto ponga junto al marcador... a veces se corta antes de
    que suene»): el gemelo ancla el PICO al marcador (arrancando antes)
    y conoce la duracion real — el respaldo de 0.5 s truncaba los mp3
    recien importados cuyo GetClipProperty("Frames") aun no responde.
    En SEGUNDOS: el fps solo se conoce dentro de Resolve (regla de la
    casa). Un archivo que no se puede analizar SE OMITE y el gemelo
    degrada a la conducta de siempre para ese archivo — el analisis
    jamas aborta la colocacion. Module-level y sin interfaz a proposito: se
    prueba sin abrir el Lab (mismo motivo que para_manifiesto).
    """
    import numpy as np
    ondas = {}
    for datos in pendiente.values():
        for ruta in datos.get('archivos') or ():
            if ruta in ondas:
                continue
            else:
                try:
                    audio, sr = sfx_audio.cargar(ruta)
                    if len(audio) and sr > 0:
                            ondas[ruta] = {'pico': round(float(np.argmax(np.abs(audio))) / sr, 3), 'dur': round(len(audio) / sr, 3)}
                except Exception:
                    pass
    return ondas
ARCHIVO_PICOS = CARPETA_PREFS / 'cache_picos.json'
_PICOS = {'datos': None, 'sucio': False}


def _picos_cargar():
    if _PICOS['datos'] is None:
        try:
            _PICOS['datos'] = json.loads(ARCHIVO_PICOS.read_text(encoding='utf-8'))
        except Exception:
            _PICOS['datos'] = {}
    return _PICOS['datos']


def picos_de_archivo(ruta, n=64, calcular=True):
    """v5.5: los picos de la onda de un sonido, guardados en disco (por ruta, tamaño y fecha): la onda de cada tarjeta sale al
    instante y no se vuelve a decodificar el audio. calcular=False solo mira lo ya guardado (para el hilo de la interfaz)."""
    try:
        st = Path(ruta).stat()
        clave = f'{ruta}|{st.st_size}|{st.st_mtime_ns}|{n}'
    except OSError:
        return []
    datos = _picos_cargar()
    if clave in datos:
        return datos[clave]
    if not calcular:
        return []
    audio, _ = sfx_audio.cargar(ruta)
    picos = [round(v, 3) for v in picos_de(audio, n)]
    datos[clave] = picos
    _PICOS['sucio'] = True
    return picos


def guardar_picos():
    if not _PICOS['sucio']:
        return
    try:
        datos = _picos_cargar()
        if len(datos) > 6000:
            for k in list(datos)[:len(datos) - 6000]:
                datos.pop(k, None)
        ARCHIVO_PICOS.parent.mkdir(parents=True, exist_ok=True)
        temporal = ARCHIVO_PICOS.with_suffix('.tmp')
        temporal.write_text(json.dumps(datos), encoding='utf-8')
        temporal.replace(ARCHIVO_PICOS)
        _PICOS['sucio'] = False
    except Exception:
        pass


def precalentar_picos(rutas):
    """Calcula en un hilo los picos de esos sonidos (los de la biblioteca que se ven primero)."""
    import threading

    def trabajo():
        for r in rutas:
            try:
                picos_de_archivo(r)
            except Exception:
                pass
        guardar_picos()
    threading.Thread(target=trabajo, daemon=True, name='picos-sfx').start()


def picos_de(audio, n=120):
    """n barras 0..1 de un audio (la onda del sonido elegido)."""
    try:
        import numpy as np
        a = np.abs(np.asarray(audio, dtype=np.float32))
        if a.ndim > 1:
            a = a.max(axis=1)
        if not a.size:
            return []
        trozos = np.array_split(a, min(n, a.size))
        picos = [float(t.max()) if t.size else 0.0 for t in trozos]
        tope = max(picos) or 1.0
        return [min(1.0, (p / tope) ** 0.8) for p in picos]
    except Exception:
        return []
def _texto_regla(cuando):
    """La condicion de una regla de sfx_rules.json, en palabras."""
    partes = []
    for nombre, valor in (cuando or {}).items():
        if nombre == 'es_ultimo_bloque':
            partes.append(tr('Última palabra del video') if valor else tr('No es la última palabra'))
        elif nombre == 'es_primer_bloque':
            partes.append(tr('Primera palabra del video') if valor else tr('No es la primera palabra'))
        elif nombre == 'texto_termina_en':
            partes.append(tr('Termina en {s}', s=' '.join(map(str, valor or []))))
        elif nombre == 'texto_contiene':
            partes.append(tr('Contiene «{p}»', p=', '.join(map(str, (valor or [])[:3]))))
        elif nombre == 'texto_contiene_numero':
            partes.append(tr('Contiene una cifra') if valor else tr('Sin cifras'))
        elif nombre == 'pausa_antes_mayor_a':
            partes.append(tr('Pausa antes mayor a {s} s', s=f'{float(valor):g}'.replace('.', ',')))
        elif nombre == 'solo_una_palabra':
            partes.append(tr('Una sola palabra') if valor else tr('Más de una palabra'))
        elif nombre == 'roles_incluyen':
            roles = set(valor or [])
            partes.append(tr('Bloque de 3 líneas') if {'context', 'main', 'complement'} <= roles else tr('Con {roles}', roles=', '.join(sorted(roles))))
        else:
            partes.append(str(nombre))
    return ' · '.join(partes) or tr('Siempre')

def _fuente_icono(px):
    f = ui.fuente(max(6, int(px)), peso='extra')
    return f
_ENTRADA = [True]          # False cuando solo se repinta (guardar un sonido): sin animación de entrada
def _reducir_anim():
    try:
        import efectos_ui
        return bool(efectos_ui.reducir_animaciones())
    except Exception:
        return False
def _seg_txt(v):
    return f'{float(v):.2f} s'.replace('.', ',')
def _mezcla(a, b, t):
    a, b = QColor(a), QColor(b)
    t = max(0.0, min(1.0, float(t)))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))
def _opacidad(efecto, v):
    try:
        efecto.setOpacity(float(v))
    except RuntimeError:
        pass
def _quitar_efecto(widget):
    try:
        if ui.vivo(widget):
            widget.setGraphicsEffect(None)
    except RuntimeError:
        pass
def _aparecer(widget, retraso=0, dur=320):
    """Fundido de entrada con retraso: las tarjetas entran una tras otra. El efecto se quita al terminar (no cuesta nada después)."""
    if not _ENTRADA[0] or _reducir_anim():
        return
    try:
        ef = QGraphicsOpacityEffect(widget)
        ef.setOpacity(0.0)
        widget.setGraphicsEffect(ef)
        anim = QVariantAnimation(widget)
        anim.setDuration(int(dur))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v, e=ef: _opacidad(e, v))
        anim.finished.connect(lambda w=widget: _quitar_efecto(w))
        despues(int(retraso), anim.start, widget)
    except Exception:
        pass
class _TarjetaViva(QFrame):
    """Una tarjeta que reacciona: al pasar el cursor se ilumina el borde, sube un reflejo y el icono/escena que lleva dentro
    se anima más; ``destello()`` hace un pulso de color (se usa al guardar un sonido en su espacio)."""
    def __init__(self, color='#4589FF', radio=12, fondo='#0B1426', fondo_hover='#0F1B33', padre=None):
        super().__init__(padre)
        self.setObjectName('tarjetaViva')
        self.setStyleSheet('QFrame#tarjetaViva { background: transparent; border: none; }')
        self._color = QColor(color)
        self._radio = float(radio)
        self._fondo = QColor(fondo)
        self._fondo2 = QColor(fondo_hover)
        self._h = 0.0
        self._fl = 0.0
        self._enlazados = []
        self._a_h = QVariantAnimation(self)
        self._a_h.setDuration(170)
        self._a_h.valueChanged.connect(self._paso_h)
        self._a_f = QVariantAnimation(self)
        self._a_f.setDuration(1000)
        self._a_f.setStartValue(1.0)
        self._a_f.setEndValue(0.0)
        self._a_f.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_f.valueChanged.connect(self._paso_f)
    def enlazar(self, *widgets):
        self._enlazados.extend(widgets)
    def _paso_h(self, v):
        self._h = float(v)
        self.update()
    def _paso_f(self, v):
        self._fl = float(v)
        self.update()
    def _ir(self, meta):
        for w in self._enlazados:
            try:
                w.poner_hover(meta > 0.5)
            except (RuntimeError, AttributeError):
                pass
        if _reducir_anim():
            self._h = meta
            self.update()
            return
        self._a_h.stop()
        self._a_h.setStartValue(self._h)
        self._a_h.setEndValue(float(meta))
        self._a_h.start()
    def enterEvent(self, e):
        self._ir(1.0)
        super().enterEvent(e)
    def leaveEvent(self, e):
        self._ir(0.0)
        super().leaveEvent(e)
    def destello(self):
        if _reducir_anim():
            return
        self._a_f.stop()
        self._a_f.start()
    def paintEvent(self, _e):
        W, H = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h, fl = self._h, self._fl
        borde = _mezcla(_mezcla('#1E2A42', self._color, 0.55 * h), self._color, fl)
        p.setBrush(_mezcla(self._fondo, self._fondo2, h))
        p.setPen(QPen(borde, 1.0 + 0.5 * h + 0.8 * fl))
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), self._radio, self._radio)
        p.setPen(Qt.PenStyle.NoPen)
        if h > 0.02:
            brillo = QLinearGradient(0, 0, 0, H * 0.55)
            c1, c2 = QColor(self._color), QColor(self._color)
            c1.setAlpha(int(34 * h))
            c2.setAlpha(0)
            brillo.setColorAt(0.0, c1)
            brillo.setColorAt(1.0, c2)
            p.setBrush(brillo)
            p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), self._radio, self._radio)
        if fl > 0.02:
            c = QColor(self._color)
            c.setAlpha(int(54 * fl))
            p.setBrush(c)
            p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), self._radio, self._radio)
        p.end()
class _IconoSfx(QWidget):
    """Un icono animado que enseña QUÉ PASARÁ (un riser que sube, un boom que se expande, un «?»...). Todos comparten un solo
    reloj de 25 fps y solo se mueven los que se ven; en «reducir animaciones» se quedan quietos."""
    _vivos = None
    _reloj = None
    def __init__(self, tipo, color='#4589FF', lado=46, activo=True, padre=None, flexible=False, retraso=0):
        super().__init__(padre)
        if flexible:        # llena el alto que le sobre y dibuja el icono cuadrado y centrado
            self.setMinimumSize(lado, lado)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedSize(lado, lado)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._tipo = tipo
        self._color = QColor(color)
        self._activo = bool(activo)
        self._t = (hash(tipo) % 100) / 100.0
        self._quieto = _reducir_anim()
        self._kv = 1.0 if self._activo else 0.38          # brillo (se enciende y se apaga suave)
        self._h = 0.0                                      # 0..1: el cursor está sobre su tarjeta
        self._h_meta = 0.0
        self._ap = 1.0 if (self._quieto or not _ENTRADA[0]) else -0.07 * float(retraso)   # entrada con rebote
        if _IconoSfx._vivos is None:
            import weakref
            _IconoSfx._vivos = weakref.WeakSet()
            from PySide6.QtCore import QTimer
            _IconoSfx._reloj = QTimer()
            _IconoSfx._reloj.setInterval(40)
            _IconoSfx._reloj.timeout.connect(_IconoSfx._avanzar)
            _IconoSfx._reloj.start()
        _IconoSfx._vivos.add(self)
    @staticmethod
    def _avanzar():
        for w in list(_IconoSfx._vivos or ()):
            try:
                if not w.isVisible():
                    continue
                cambio = False
                if w._activo and not w._quieto:
                    w._t = (w._t + 0.04 / 2.4 * (1.0 + 1.3 * w._h)) % 1.0
                    cambio = True
                meta_k = 1.0 if w._activo else 0.38
                if abs(w._kv - meta_k) > 0.004:
                    w._kv = meta_k if w._quieto else w._kv + (meta_k - w._kv) * 0.22
                    cambio = True
                if abs(w._h - w._h_meta) > 0.004:
                    w._h = w._h_meta if w._quieto else w._h + (w._h_meta - w._h) * 0.25
                    cambio = True
                if w._ap < 1.0:
                    w._ap = min(1.0, w._ap + 0.07)
                    cambio = True
                if cambio:
                    w.update()
            except RuntimeError:
                pass
    def poner_activo(self, si):
        self._activo = bool(si)
        self.update()
    def poner_hover(self, si):
        self._h_meta = 1.0 if si else 0.0
    def paintEvent(self, _e):
        import math
        L = float(min(self.width(), self.height()))
        t = self._t if self._activo else 0.62
        if self._quieto:
            t = 0.62
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ap = max(0.0, min(1.0, self._ap))
        if ap <= 0.0:
            p.end()
            return
        p.setOpacity(min(1.0, ap * 2.2))
        p.translate((self.width() - L) / 2.0, (self.height() - L) / 2.0)
        rebote = 1.0 + 2.70158 * (ap - 1.0) ** 3 + 1.70158 * (ap - 1.0) ** 2        # easeOutBack
        esc = rebote * (1.0 + 0.07 * self._h)
        p.translate(L / 2.0, L / 2.0)
        p.scale(esc, esc)
        p.translate(-L / 2.0, -L / 2.0)
        base = QColor(self._color)
        k = self._kv
        arriba, abajo = QColor(base), QColor(base)
        arriba.setAlpha(int(78 * k + 8))
        abajo.setAlpha(int(16 * k + 4))
        degradado = QLinearGradient(0, 0, 0, L)
        degradado.setColorAt(0.0, arriba)
        degradado.setColorAt(1.0, abajo)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(degradado)
        p.drawRoundedRect(QRectF(0, 0, L, L), L * 0.26, L * 0.26)
        brillo = QRadialGradient(QPointF(L * 0.5, L * 0.5), L * 0.55)
        centro = QColor(base)
        centro.setAlpha(int((46 + 70 * self._h) * k))
        brillo.setColorAt(0.0, centro)
        centro.setAlpha(0)
        brillo.setColorAt(1.0, centro)
        p.setBrush(brillo)
        p.drawRoundedRect(QRectF(0, 0, L, L), L * 0.26, L * 0.26)
        borde = QColor(base)
        borde.setAlpha(int((110 + 90 * self._h) * k + 16))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(borde, 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, L - 1, L - 1), L * 0.26, L * 0.26)
        p.setPen(Qt.PenStyle.NoPen)

        def col(a=1.0):
            c = QColor(base)
            c.setAlpha(max(0, min(255, int(255 * a * k))))
            return c

        def barra(x, y, w, h, a=1.0):
            p.setBrush(col(a))
            p.drawRoundedRect(QRectF(x * L, y * L, w * L, h * L), w * L * 0.45, w * L * 0.45)

        def texto(txt, tam, dx=0.0, dy=0.0, a=1.0):
            p.setPen(col(a))
            p.setFont(_fuente_icono(L * tam))
            p.drawText(QRectF(dx * L, dy * L, L, L), int(Qt.AlignmentFlag.AlignCenter), txt)
            p.setPen(Qt.PenStyle.NoPen)

        def anillo(cx, cy, r, a, ancho=0.05):
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(col(a), max(1.0, L * ancho)))
            p.drawEllipse(QPointF(cx * L, cy * L), r * L, r * L)
            p.setPen(Qt.PenStyle.NoPen)

        tp = self._tipo
        if tp == 'inicio':                       # puntos que van apareciendo, uno por palabra
            for i in range(3):
                a = max(0.22, 1.0 - abs((t * 3.0) % 3.0 - i) * 0.75)
                r = 0.065 + 0.035 * a
                p.setBrush(col(a))
                p.drawEllipse(QPointF((0.27 + 0.23 * i) * L, 0.5 * L), r * L, r * L)
        elif tp == 'intro':                      # riser: barras que suben y se encienden en cadena
            for i in range(5):
                alto = 0.16 + 0.11 * i
                brillo = 0.35 + 0.65 * max(0.0, 1.0 - abs(((t * 5.0) % 5.0) - i) * 0.6)
                barra(0.18 + 0.135 * i, 0.78 - alto, 0.09, alto, brillo)
        elif tp == 'final':                      # boom: núcleo y ondas que se expanden
            for desfase in (0.0, 0.5):
                f = (t + desfase) % 1.0
                anillo(0.5, 0.5, 0.08 + f * 0.36, (1.0 - f) ** 1.5)
            nucleo = 0.10 + 0.06 * (1.0 - t) ** 2
            p.setBrush(col(0.95))
            p.drawEllipse(QPointF(0.5 * L, 0.5 * L), nucleo * L, nucleo * L)
        elif tp == 'primero':                    # bandera ondeando
            barra(0.26, 0.2, 0.05, 0.62, 1.0)
            p.setBrush(col(0.9))
            onda = 0.04 * math.sin(t * math.tau * 2)
            from PySide6.QtGui import QPolygonF
            p.drawPolygon(QPolygonF([QPointF(0.31 * L, 0.22 * L), QPointF(0.72 * L, (0.30 + onda) * L),
                                     QPointF(0.31 * L, 0.46 * L)]))
        elif tp == 'ultimo':                     # power down: las barras se apagan de derecha a izquierda
            for i in range(5):
                f = max(0.12, 1.0 - max(0.0, (t * 1.4 - (4 - i) * 0.16)))
                barra(0.18 + 0.135 * i, 0.78 - (0.62 - 0.08 * i) * f, 0.09, (0.62 - 0.08 * i) * f, 0.4 + 0.6 * f)
        elif tp == 'pregunta':                   # «?» con la tensión que sube
            texto('?', 0.62, 0.0, -0.03 - 0.03 * math.sin(t * math.tau))
            f = t
            anillo(0.5, 0.42, 0.18 + 0.22 * f, 0.6 * (1.0 - f), 0.035)
        elif tp == 'exclamacion':                # «!» con el golpe: tiembla y salen rayitas
            golpe = max(0.0, 1.0 - t * 2.2)
            texto('!', 0.66, 0.035 * math.sin(t * 60) * golpe, 0.0)
            for ang in range(0, 360, 60):
                r1, r2 = 0.30 + 0.05 * (1 - golpe), 0.30 + 0.12 * (1 - golpe) + 0.04
                dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                p.setPen(QPen(col(0.8 * golpe), max(1.0, L * 0.035)))
                p.drawLine(QPointF((0.5 + dx * r1) * L, (0.5 + dy * r1) * L), QPointF((0.5 + dx * r2) * L, (0.5 + dy * r2) * L))
            p.setPen(Qt.PenStyle.NoPen)
        elif tp == 'gritos':                     # MAYÚSCULAS que crecen
            texto('AA', 0.40 + 0.08 * math.sin(t * math.tau))
        elif tp == 'cifras':                     # cifras con una barra que se llena
            texto('123', 0.30, 0.0, -0.07)
            barra(0.2, 0.68, 0.6 * (0.25 + 0.75 * t), 0.07, 0.9)
        elif tp in ('pausa_larga', 'pausa_media'):   # onda — silencio — onda; un punto cruza el hueco
            hueco = 0.38 if tp == 'pausa_larga' else 0.20
            lado = (0.64 - hueco) / 2.0
            alturas = (0.18, 0.34, 0.24, 0.40)
            n = 3
            for i in range(n):
                h = alturas[i % 4] * (0.8 + 0.2 * math.sin(t * math.tau * 2 + i))
                barra(0.18 + i * lado / n, 0.5 - h / 2, 0.05, h, 0.9)
                barra(0.82 - 0.05 - i * lado / n, 0.5 - h / 2, 0.05, h, 0.9)
            x0, x1 = 0.18 + lado, 0.82 - lado
            p.setBrush(col(0.95))
            p.drawEllipse(QPointF((x0 + (x1 - x0) * t) * L, 0.5 * L), 0.035 * L, 0.035 * L)
        elif tp == 'una_palabra':                # un solo punto que salta
            f = abs(math.sin(t * math.pi))
            r = 0.09 + 0.07 * f
            anillo(0.5, 0.5, r + 0.10 * f, 0.55 * f, 0.03)
            p.setBrush(col(1.0))
            p.drawEllipse(QPointF(0.5 * L, 0.5 * L), r * L, r * L)
        elif tp == 'largo':                      # líneas de texto que se escriben
            for i in range(4):
                f = max(0.0, min(1.0, t * 4.4 - i * 0.9))
                barra(0.2, 0.26 + i * 0.14, 0.6 * (0.35 + 0.65 * f) if i < 3 else 0.36 * f, 0.06, 0.45 + 0.55 * f)
        elif tp == 'cada_5':                     # 5 puntos: el quinto marca el ritmo
            activo = int((t * 5.0) % 5.0)
            for i in range(5):
                esq = (i == 4)
                a = 1.0 if i == activo else 0.35
                r = (0.07 if esq else 0.052) + (0.02 if i == activo else 0.0)
                p.setBrush(col(a))
                p.drawEllipse(QPointF((0.17 + 0.165 * i) * L, 0.5 * L), r * L, r * L)
            if activo == 4:
                anillo(0.17 + 0.165 * 4, 0.5, 0.13, 0.7, 0.03)
        elif tp == 'tres_lineas':                # contexto / principal / complemento: la del medio destella
            fuerte = 0.55 + 0.45 * abs(math.sin(t * math.tau))
            barra(0.24, 0.26, 0.40, 0.09, 0.45)
            barra(0.18, 0.44, 0.64, 0.12, fuerte)
            barra(0.30, 0.65, 0.36, 0.09, 0.45)
        p.end()

class _Escena(_IconoSfx):
    """La escena de una sección del modo simple: una línea de tiempo con bloques de texto, el cabezal que avanza y la ONDA del
    efecto en el punto exacto donde suena (en cada bloque, solo en el primero o solo en el último). Lo que ya sonó se enciende;
    lo que falta se ve tenue, así se ve la forma del sonido antes de que llegue. Comparte el reloj de los iconos."""
    def __init__(self, tipo, color='#4589FF', alto=120, padre=None):
        super().__init__(tipo, color, 10, True, padre)
        self._ap = 1.0
        self.setMinimumSize(180, alto)
        self.setMaximumSize(16777215, 520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    def paintEvent(self, _e):
        import math
        W, H = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QColor(self._color)
        t = 0.88 if self._quieto else self._t
        # panel
        fondo = QLinearGradient(0, 0, 0, H)
        c1 = QColor(base)
        c1.setAlpha(34)
        fondo.setColorAt(0.0, c1)
        fondo.setColorAt(1.0, QColor('#0A1224'))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0A1224'))
        p.drawRoundedRect(QRectF(0, 0, W, H), 14, 14)
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(0, 0, W, H), 14, 14)
        borde = QColor(base)
        borde.setAlpha(int(70 + 110 * self._h))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(borde, 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 14, 14)
        p.setPen(Qt.PenStyle.NoPen)
        m = 16.0
        x0, x1 = m, W - m
        n, gap = 7, 6.0
        bw = (x1 - x0 - gap * (n - 1)) / n
        bh = max(26.0, min(40.0, H * 0.22))
        yb = H - m - bh                                     # línea de bloques
        ancho_onda = yb - m - 8                              # zona de la onda
        yc = m + ancho_onda / 2.0                            # eje de la onda
        izq = [x0 + i * (bw + gap) for i in range(n)]
        if self._tipo == 'inicio':
            golpes = [(x, 0.62 if i % 2 == 0 else 0.9, i % 2) for i, x in enumerate(izq)]
        elif self._tipo == 'intro':
            golpes = [(izq[0], 1.0, 0)]
        else:
            golpes = [(izq[-1], 1.0, 0)]
        largo_riser = (x1 - x0) * 0.62
        ph = min(1.0, t * 1.12)                              # el cabezal llega al final y se queda un instante
        xp = x0 + ph * (x1 - x0)

        def amplitud(x):
            a = 0.0
            for xi, fuerza, _alt in golpes:
                if self._tipo == 'inicio':
                    if x >= xi:
                        a = max(a, fuerza * math.exp(-(x - xi) / (bw * 0.5)))
                elif self._tipo == 'intro':
                    if xi <= x <= xi + largo_riser:
                        u = (x - xi) / largo_riser
                        a = max(a, (0.10 + 0.9 * u ** 1.8) * (0.86 + 0.14 * math.sin(x * 0.9)))
                else:
                    if x >= xi:
                        a = max(a, math.exp(-(x - xi) / (bw * 0.9)) * (0.88 + 0.12 * math.sin(x * 1.3)))
            return a
        # onda: barritas; lo que ya pasó por el cabezal se enciende, lo que falta se ve tenue
        paso = 5.0
        total = int((x1 - x0) / paso)
        alto_max = ancho_onda * 0.5
        for j in range(total):
            x = x0 + j * paso + 1.0
            a = amplitud(x)
            h = 2.0 + a * (alto_max - 2.0)
            ya = x <= xp
            col = QColor(base)
            if self._tipo == 'inicio':
                for xi, _f, alt in golpes:
                    if x >= xi and alt == 1:
                        col = QColor(base).lighter(140)
            col.setAlpha(235 if ya else 62)
            if a < 0.02:
                col.setAlpha(60 if ya else 26)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x, yc - h, 3.0, h * 2), 1.5, 1.5)
        # bloques (los subtítulos)
        for i in range(n):
            x = izq[i]
            suena = any(abs(x - xi) < 1.0 for xi, _f, _a in golpes)
            f = 0.0
            if suena:
                f = max(0.0, 1.0 - max(0.0, xp - x) / (bw * 2.4)) if xp >= x else 0.0
            col = QColor('#1B2845')
            if suena:
                col = QColor(base)
                col.setAlpha(int(70 + 175 * f) if xp >= x else 70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x, yb, bw, bh), 7, 7)
            raya = QColor('#FFFFFF')
            raya.setAlpha(120 if suena and xp >= x else 46)
            p.setBrush(raya)
            p.drawRoundedRect(QRectF(x + bw * 0.16, yb + bh * 0.30, bw * 0.68, 3.0), 1.5, 1.5)
            p.drawRoundedRect(QRectF(x + bw * 0.16, yb + bh * 0.58, bw * (0.34 + 0.2 * ((i * 7) % 3) / 2.0), 3.0), 1.5, 1.5)
            if f > 0.04:                                     # el pulso del golpe
                aro = QColor(base)
                aro.setAlpha(int(190 * f))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(aro, 1.6))
                r = (1.0 - f) * 7.0
                p.drawRoundedRect(QRectF(x - r, yb - r, bw + 2 * r, bh + 2 * r), 7 + r, 7 + r)
                p.setPen(Qt.PenStyle.NoPen)
                for kk in range(6 if self._tipo != 'final' else 9):         # chispitas que salen del golpe
                    ang = math.radians(-90 + (kk - 2.5) * (26 if self._tipo != 'final' else 20))
                    dd = (1.0 - f) * (30.0 if self._tipo != 'final' else 46.0) + 5.0
                    chispa = QColor(base).lighter(150)
                    chispa.setAlpha(int(210 * f))
                    p.setBrush(chispa)
                    p.drawEllipse(QPointF(x + bw / 2.0 + math.cos(ang) * dd, yb + math.sin(ang) * dd), 1.9, 1.9)
        if self._tipo == 'final':                           # el boom: onda expansiva y destello
            xe = izq[-1] + bw / 2.0
            f = max(0.0, 1.0 - max(0.0, xp - izq[-1]) / (bw * 5.0)) if xp >= izq[-1] else 0.0
            for d in (0.0, 0.35):
                g = max(0.0, min(1.0, (1.0 - f) * 1.6 - d)) if xp >= izq[-1] else 0.0
                if 0.0 < g < 1.0:
                    aro = QColor(base)
                    aro.setAlpha(int(200 * (1.0 - g)))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(aro, 2.0))
                    p.drawEllipse(QPointF(xe, yb + bh / 2.0), 8 + g * ancho_onda * 0.9, 8 + g * ancho_onda * 0.9)
                    p.setPen(Qt.PenStyle.NoPen)
            if f > 0.0:
                flash = QColor(base)
                flash.setAlpha(int(46 * f))
                p.setBrush(flash)
                p.drawRoundedRect(QRectF(0, 0, W, H), 14, 14)
        # estela detrás del cabezal
        estela = QLinearGradient(xp - 130, 0, xp, 0)
        e0, e1 = QColor(base), QColor(base)
        e0.setAlpha(0)
        e1.setAlpha(int(40 + 46 * self._h))
        estela.setColorAt(0.0, e0)
        estela.setColorAt(1.0, e1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(estela)
        p.drawRoundedRect(QRectF(max(3.0, xp - 130), m, min(130.0, xp - 3.0), yb + bh - m), 6, 6)
        # cabezal
        cab = QColor('#FFFFFF')
        cab.setAlpha(210)
        p.setPen(QPen(cab, 1.6))
        p.drawLine(QPointF(xp, m - 2), QPointF(xp, yb + bh + 6))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cab)
        from PySide6.QtGui import QPolygonF
        p.drawPolygon(QPolygonF([QPointF(xp - 5, m - 6), QPointF(xp + 5, m - 6), QPointF(xp, m + 2)]))
        p.end()

COLORES_REGLA = {'primero': '#22D3EE', 'ultimo': '#FB7185', 'pregunta': '#B388FF', 'exclamacion': '#F5B84B', 'gritos': '#FDE047',
                'cifras': '#24D18F', 'pausa_larga': '#4589FF', 'pausa_media': '#38BDF8', 'una_palabra': '#EC4899',
                'largo': '#A855F7', 'cada_5': '#22C55E', 'tres_lineas': '#F97316'}
class _EstadoRegistro:
    """Los mensajes de la pantalla Sonido ya no ocupan una línea abajo: van al registro (aparecen en la barra de título de la
    pantalla y quedan en cinecaptions.log). «Listo.» y los textos vacíos no se anotan."""
    def configure(self, text=None, text_color=None, **_):
        t = str(text or '').strip()
        if not t or t in ('Listo.', tr('Listo.')):
            return
        import registro
        c = str(text_color or '').upper()
        nivel = 'aviso' if c == '#E0A030' else ('ok' if c in ('#7EE0A8', '#FFD166') else 'info')
        registro.anotar(nivel, t, 'Sonido')
    def setText(self, t):
        self.configure(text=t)
class _Nota(Etiqueta):
    """Un texto que se ajusta en hasta 'lineas' lineas con un ALTO FIJO.

    Un QLabel con ajuste de linea hace que su layout calcule el alto «segun
    el ancho», y en el Lab eso descuadraba la rejilla (las filas quedaban
    mas bajas que su minimo y se montaban). Con alto fijo, no."""
    def __init__(self, texto='', tam=12, lineas=2, **kw):
        super().__init__(texto, tam, envolver=True, **kw)
        self.setFixedHeight(int(self.fontMetrics().lineSpacing() * lineas + 4))
        self.setAlignment(self.alignment() | Qt.AlignmentFlag.AlignTop)
    def hasHeightForWidth(self):
        return False
class _PadXY(QWidget):
    """El pad: X = tono, Y = velocidad. Suena al soltar."""
    def __init__(self, lab):
        super().__init__()
        self._lab = lab
        self.setMinimumSize(260, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
    def sizeHint(self):
        return QSize(440, 300)
    def minimumSizeHint(self):
        return QSize(260, 240)
    def _rect(self):
        return QRectF(self.rect()).adjusted(34, 6, -6, -24)
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._rect()
        p.setPen(QPen(QColor(BORDER_COLOR), 1))
        p.setBrush(QColor('#0A1120'))
        p.drawRoundedRect(r, 10, 10)
        for k in (0.25, 0.75):
            p.setPen(QPen(QColor('#16223A'), 1))
            p.drawLine(QPointF(r.left() + r.width() * k, r.top()), QPointF(r.left() + r.width() * k, r.bottom()))
            p.drawLine(QPointF(r.left(), r.top() + r.height() * k), QPointF(r.right(), r.top() + r.height() * k))
        p.setPen(QPen(QColor('#2A3A58'), 1.2))
        p.drawLine(QPointF(r.center().x(), r.top()), QPointF(r.center().x(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
        p.setFont(ui.fuente(10))
        p.setPen(QColor('#4F607A'))
        esquinas = ((Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, tr('grave · rápido')),
                    (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, tr('agudo · rápido')),
                    (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, tr('grave · lento')),
                    (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, tr('agudo · lento')))
        for alinear, texto in esquinas:
            p.drawText(r.adjusted(10, 8, -10, -8), int(alinear), texto)
        p.setPen(QColor(TEXT_MUTED))
        p.drawText(QRectF(r.left(), r.bottom() + 4, r.width(), 18), int(Qt.AlignmentFlag.AlignCenter), tr('Tono  (−12 a +12 semitonos)'))
        p.save()
        p.translate(r.left() - 22, r.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-80, -9, 160, 18), int(Qt.AlignmentFlag.AlignCenter), tr('Velocidad'))
        p.restore()
        cx = r.left() + self._lab._pad_x * r.width()
        cy = r.top() + self._lab._pad_y * r.height()
        halo = QColor(ACCENT)
        halo.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), 24, 24)
        p.setBrush(QColor(ACCENT))
        p.drawEllipse(QPointF(cx, cy), 11, 11)
        p.setBrush(QColor('#FFFFFF'))
        p.drawEllipse(QPointF(cx, cy), 4, 4)
        p.end()
    def _normal(self, pos):
        r = self._rect()
        return (max(0.0, min(1.0, (pos.x() - r.left()) / max(1.0, r.width()))),
                max(0.0, min(1.0, (pos.y() - r.top()) / max(1.0, r.height()))))
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._lab._mover_pad(*self._normal(e.position()), reproducir=False)
    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._lab._mover_pad(*self._normal(e.position()), reproducir=False)
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._lab._pad_release(None)
class _EntradaAtajo(Entrada):
    """El campo del atajo global: se escribe pulsando la combinacion."""
    def __init__(self, lab, var):
        super().__init__(var, alto=30, tam=12, centrada=True)
        self._lab = lab
    def keyPressEvent(self, e):
        teclas = []
        mods = e.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            teclas.append('ctrl')
        if mods & Qt.KeyboardModifier.AltModifier:
            teclas.append('alt')
        if mods & Qt.KeyboardModifier.ShiftModifier:
            teclas.append('shift')
        if mods & Qt.KeyboardModifier.MetaModifier:
            teclas.append('cmd')
        k = e.key()
        if k in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta, Qt.Key.Key_AltGr):
            return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not teclas:
            self._lab._actualizar_atajo_teclado()
            return
        if k == Qt.Key.Key_Space:
            teclas.append('space')
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            teclas.append('enter')
        elif Qt.Key.Key_F1 <= k <= Qt.Key.Key_F24:
            teclas.append(f'f{k - Qt.Key.Key_F1 + 1}')
        else:
            texto = QKeySequence(k).toString().lower()
            if len(texto) != 1:
                return
            teclas.append(texto)
        if len(teclas) < 2:
            return
        self._lab.hotkey_var.set('+'.join(teclas))
        self._lab._actualizar_atajo_teclado()
        self.clearFocus()
    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._lab._actualizar_atajo_teclado()
_CODIGO_PONER_MUSICA = r"""
p = project
mp = p.GetMediaPool()
tl = p.GetCurrentTimeline()
if tl is None:
    result = 'no hay timeline abierto'
else:
    items = mp.ImportMedia([RUTA])
    tl.AddTrack('audio')
    idx = tl.GetTrackCount('audio')
    try:
        tl.SetTrackName('audio', idx, 'MUSICA')
    except Exception:
        pass
    ok = mp.AppendToTimeline([{'mediaPoolItem': items[0], 'mediaType': 2, 'trackIndex': idx, 'recordFrame': tl.GetStartFrame()}]) if items else None
    result = 'ok' if ok else 'no pude colocarla'
"""


class SfxStudio(QWidget):
    def __init__(self, master, carpeta_libreria, carpeta_destino_por_defecto=None, video_actual=None, carpeta_scripts_resolve=None, origen_scripts_resolve=None):
        super().__init__()
        self.master = master
        self.carpeta_libreria = Path(carpeta_libreria)
        self._destino_por_defecto = carpeta_destino_por_defecto
        self.poner_video(video_actual)
        self.carpeta_scripts_resolve = Path(carpeta_scripts_resolve) if carpeta_scripts_resolve else None
        self.origen_scripts_resolve = Path(origen_scripts_resolve) if origen_scripts_resolve else None
        self.carpetas_usuario = cargar_carpetas_usuario()
        self.favoritos = cargar_favoritos()
        self.shortcut_path = CARPETA_PREFS / 'sfx_hotkey.json'
        self.shortcut_str = 'ctrl+alt+a'
        if self.shortcut_path.exists():
            try:
                datos = json.loads(self.shortcut_path.read_text(encoding='utf-8'))
                self.shortcut_str = datos.get('hotkey', 'ctrl+alt+a')
            except Exception:
                pass
        self._listener_sfx = None
        self._atajo_registrado = None
        self._atajos_mac = []
        self.reproductor = sfx_audio.Reproductor()
        self.audio_original = None
        self.sonido_seleccionado = None
        self._temporizador_previa = None
        self._pad_x = 0.5
        self._pad_y = 0.5
        self._rutas_de_fila = []
        self.modo_reemplazo = BooleanVar(False)
        self.topmost_var = BooleanVar(False)
        self._build_ui()
        self._recargar_arbol()
        self._actualizar_valores()
        self._registrar_hotkey(self.shortcut_str)
        self._aplicar_topmost()
    def poner_video(self, video_actual):
        """La carpeta donde se guardan los WAV retocados: junto al video
        elegido, o en Descargas (v5.0.0: el Lab vive mientras la app, y el
        video puede cambiar)."""
        if video_actual:
            self.carpeta_destino = Path(video_actual).expanduser().resolve().parent / 'SFX Modificado por CineCaptions'
        elif self._destino_por_defecto:
            self.carpeta_destino = Path(self._destino_por_defecto)
        else:
            self.carpeta_destino = Path.home() / 'Downloads' / 'SFX Modificado por CineCaptions'
    # -- armado --------------------------------------------------------------
    def _build_ui(self):
        # Diseño «C»: arriba la barra de la biblioteca (buscador + categorías), al centro el estudio (sin pad XY ni
        # onda: tarjetas de Tono / Velocidad / Volumen) y a la derecha las reglas y los marcadores. Si la
        # pantalla es angosta, la columna de la derecha pasa debajo (_acomodar).
        self._rejilla = QGridLayout(self)
        self._rejilla.setContentsMargins(0, 0, 12, 0)
        self._rejilla.setSpacing(20)
        self._angosto = None
        self._cat_activa = None
        self._sig_chips = None
        self._recientes = [x for x in _leer_lista(ARCHIVO_RECIENTES) if Path(x).is_file()][:10]
        # --- barra de la biblioteca
        riel = Tarjeta(margenes=(16, 12, 16, 12), espacio=10)
        self._riel = riel
        fila_riel, crl = caja_h(espacio=10)
        self.filtro_var = StringVar('')
        self.filtro_entry = Entrada(self.filtro_var, placeholder=tr('Buscar sonido…'), alto=38, tam=13)
        self.filtro_entry.setMinimumWidth(220)
        self.filtro_entry.textEdited.connect(lambda _t: self._recargar_arbol())
        crl.addWidget(self.filtro_entry, 1)
        self.hotkey_frame, chk = caja_h(espacio=8)
        if sys.platform == 'darwin':
            self._registrar_atajo_local()
            chk.addWidget(Etiqueta(tr('Atajo: ⌘↩ (con esta ventana al frente)'), 12, color=TEXT_MUTED))
            self.hotkey_var = StringVar('')
            self.hotkey_entry = None
        else:
            lbl = Etiqueta(tr('Atajo global (Enviar):'), 12, color=TEXT_MUTED)
            chk.addWidget(lbl)
            self.hotkey_var = StringVar(self.shortcut_str)
            self.hotkey_entry = _EntradaAtajo(self, self.hotkey_var)
            self.hotkey_entry.setFixedWidth(124)
            Tooltip(self.hotkey_entry, tr('Haz clic aquí y pulsa la combinación (por ejemplo Ctrl+Alt+A). Funciona aunque el programa esté minimizado.'))
            chk.addWidget(self.hotkey_entry)
        crl.addWidget(self.hotkey_frame)
        mi_carpeta = Boton(tr('+ Mi carpeta'), self._agregar_carpeta, alto=38, tam=13)
        Tooltip(mi_carpeta, tr('Agrega una carpeta tuya con sonidos a la biblioteca.'))
        crl.addWidget(mi_carpeta)
        riel.capa.addWidget(fila_riel)
        self.chips_cat_w = QWidget()
        self.chips_cat = ui.FlujoCapa(self.chips_cat_w, 8, 8)
        riel.capa.addWidget(self.chips_cat_w)
        # --- la lista de sonidos (vive abajo del estudio)
        self.arbol = QTreeWidget()
        self.arbol.setHeaderHidden(True)
        self.arbol.setColumnCount(2)
        self.arbol.setIndentation(16)
        self.arbol.setRootIsDecorated(True)
        self.arbol.setAnimated(True)
        self.arbol.setFont(ui.fuente(13))
        self.arbol.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.arbol.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.arbol.header().setStretchLastSection(False)
        self.arbol.header().setSectionResizeMode(0, self.arbol.header().ResizeMode.Stretch)
        self.arbol.header().setSectionResizeMode(1, self.arbol.header().ResizeMode.ResizeToContents)
        self.arbol.currentItemChanged.connect(lambda actual, _antes: self._al_elegir(actual))
        self.arbol.itemDoubleClicked.connect(lambda it, _c: self._doble_clic_arbol(it))
        self.arbol.setMinimumHeight(210)
        self._nodo_a_ruta = {}
        # el pad XY y la onda ya no se muestran; los objetos siguen vivos porque el resto del código los lee
        self.pad = _PadXY(self)
        self.pad.hide()
        self.onda = None
        # --- el centro (5.3): arriba las reglas automáticas por bloque, en horizontal; abajo el sonido elegido y la lista
        centro = Tarjeta(margenes=(22, 20, 22, 18), espacio=14)
        self._centro = centro
        # Los controles del estudio de antes (tono, velocidad, enviar, guardar WAV...) ya no se ven, pero siguen vivos en este
        # contenedor oculto porque el atajo global, los marcadores y el resto del código los leen.
        legacy = QWidget(self)
        legacy.hide()
        lc = QVBoxLayout(legacy)
        # --- el estudio
        cab, cc = caja_h(espacio=10)
        info, ci = caja_v(espacio=2)
        self.sel_label = ui.Elidida(tr('(elige un sonido arriba)'), 22, peso='extra', color='#FFFFFF')
        self.sel_meta = ui.Elidida('', 13, color=TEXT_MUTED)
        ci.addWidget(self.sel_label)
        ci.addWidget(self.sel_meta)
        cc.addWidget(info, 1)
        self.fav_btn = Chip(tr('☆ Favorito'), ui.AMBAR, self._toggle_favorito, alto=28, tam=12)
        Tooltip(self.fav_btn, tr('Marcar / quitar de favoritos (también: doble clic en la lista)'))
        cc.addWidget(self.fav_btn)
        self.pin_btn = Chip(tr('📌 Siempre delante'), ui.ACCENT_CLARO, self._toggle_topmost, alto=28, tam=12)
        Tooltip(self.pin_btn, tr('Deja la ventana del programa por encima de Resolve mientras retocas.'))
        cc.addWidget(self.pin_btn)
        lc.addWidget(cab)
        # reproducir + ajustes rápidos
        fila, cf = caja_h(espacio=14)
        reproducir = Boton(tr('▶  Reproducir'), self._reproducir, tipo='primario', alto=56, tam=17, negrita=True)
        reproducir.setMinimumWidth(max(150, reproducir.sizeHint().width()))
        cf.addWidget(reproducir, 0)
        rap, cr = caja_v(espacio=6)
        cr.addWidget(Etiqueta(tr('AJUSTES RÁPIDOS'), 11, peso='negrita', color=TEXT_MUTED))
        chips, cch = caja_h(espacio=8)
        for nombre, valores, color in AJUSTES_RAPIDOS:
            cch.addWidget(Chip(tr(nombre), color, lambda n=nombre: self._ajuste_rapido(n), alto=30, tam=13))
        cch.addStretch(1)
        cr.addWidget(chips)
        cf.addWidget(rap, 1)
        lc.addWidget(fila)
        # tres tarjetas de control
        self.tono_valor = StringVar('0.0 st')
        self.velocidad_valor = StringVar('1.00 x')
        self.volumen_valor = StringVar('100 %')
        # (estas dos etiquetas ya no se ven: el valor grande vive en cada tarjeta)
        self.tono_lbl = Etiqueta('', 14, peso='negrita', color='#FFFFFF')
        self.velocidad_lbl = Etiqueta('', 14, peso='negrita', color='#FFFFFF')
        controles, ccs = caja_h(espacio=12)
        tarjeta, self.tono_slider, self.tono_big = self._tarjeta_control(tr('Tono'), 'st', RANGO_TONO, 0.0, 0.5, (tr('grave'), tr('agudo')), '#B388FF')
        ccs.addWidget(tarjeta, 1)
        tarjeta, self.velocidad_slider, self.velocidad_big = self._tarjeta_control(tr('Velocidad'), '×', RANGO_VELOCIDAD, 1.0, 0.05, (tr('lento'), tr('rápido')), '#24D18F')
        ccs.addWidget(tarjeta, 1)
        tarjeta, self.volumen_slider, self.volumen_big = self._tarjeta_control(tr('Volumen'), '%', (0.0, 2.0), 1.0, 0.05, (tr('silencio'), '200 %'), '#F5B84B')
        ccs.addWidget(tarjeta, 1)
        lc.addWidget(controles)
        # destino
        dest, cd = caja_h(espacio=12)
        cd.addWidget(Etiqueta(tr('Enviar a Resolve'), 14, peso='medio', color='#E0EBFB'))
        self.ENVIOS = [tr('Insertar'), tr('Reemplazar')]
        self.envio_var = StringVar(self.ENVIOS[0])
        self.envio_btn = Segmentado(self.ENVIOS, self.envio_var, self._on_envio, alto=36, tam=13)
        Tooltip(self.envio_btn, tr('Insertar: pone el sonido en el cabezal, en una pista nueva. Reemplazar: cambia el efecto que ya hay bajo el cabezal (o en los marcadores de un color).'))
        cd.addWidget(self.envio_btn)
        cd.addStretch(1)
        lc.addWidget(dest)
        self.reemplazo_destino = StringVar(self.DESTINO_CABEZAL)
        self.destino_menu = Combo([self.DESTINO_CABEZAL] + list(self._destinos_marcador()), self.reemplazo_destino, self._on_destino_reemplazo, ancho=170, alto=34, tam=13)
        self.fila_destino, cfd = caja_h(espacio=10)
        cfd.addWidget(Etiqueta(tr('Reemplazar en:'), 13, color=TEXT_MUTED))
        cfd.addWidget(self.destino_menu)
        cfd.addStretch(1)
        self.fila_destino.hide()
        lc.addWidget(self.fila_destino)
        # acciones
        botones, cb = caja_h(espacio=10)
        reiniciar = Boton('⟲', self._reiniciar, tipo='icono', alto=46, ancho=46, tam=18)
        reiniciar.setFixedWidth(46)
        Tooltip(reiniciar, tr('Reiniciar: tono 0, velocidad 1x, volumen 100 %'))
        cb.addWidget(reiniciar)
        guardar = Boton(tr('Guardar WAV'), self._guardar, alto=46, tam=14)
        cb.addWidget(guardar, 1)
        self.agregar_btn = Boton(tr('⟲ Reemplazar'), self._enviar_a_resolve, tipo='primario', alto=46, tam=14, negrita=True)
        self.agregar_btn.setMinimumWidth(self.agregar_btn.sizeHint().width())
        self.agregar_btn.configure(text=tr('Enviar a Resolve'))
        cb.addWidget(self.agregar_btn, 2)
        lc.addWidget(botones)
        # reglas automáticas por bloque, repartidas en horizontal por toda la zona
        self.tarjeta_reglas = QWidget()
        self.tarjeta_reglas.capa = QVBoxLayout(self.tarjeta_reglas)
        self.tarjeta_reglas.capa.setContentsMargins(0, 0, 0, 0)
        self.tarjeta_reglas.capa.setSpacing(12)
        centro.capa.addWidget(self.tarjeta_reglas, 1)
        # el sonido elegido: nombre, escuchar, favorito y SU volumen (queda guardado y se usa en la línea de tiempo)
        barra = QFrame()
        barra.setObjectName('barraSonido')
        barra.setStyleSheet(ui.traducir_hoja('QFrame#barraSonido { background-color: #0F1A30; border: 1px solid #1E2A42; border-radius: 12px; }'))
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(12)
        info_s, ci_s = caja_v(espacio=0)
        ci_s.addWidget(self.sel_label)
        ci_s.addWidget(self.sel_meta)
        bl.addWidget(info_s, 2)
        oir_s = Boton(tr('▶  Escuchar'), self._reproducir, tipo='primario', alto=38, tam=13, negrita=True)
        oir_s.setMinimumWidth(max(120, oir_s.sizeHint().width()))
        bl.addWidget(oir_s, 0)
        bl.addWidget(self.fav_btn, 0)
        bl.addSpacing(8)
        bl.addWidget(Etiqueta(tr('Volumen del efecto'), 13, peso='medio', color='#E0EBFB'), 0)
        self.vol_efecto = Deslizador(0.0, 2.0, 200, self._vol_efecto_cambio, 1.0)
        self.vol_efecto.setMinimumWidth(180)
        bl.addWidget(self.vol_efecto, 2)
        self.vol_efecto_txt = Etiqueta('100 %', 15, peso='extra', color='#FFFFFF')
        self.vol_efecto_txt.setMinimumWidth(58)
        bl.addWidget(self.vol_efecto_txt, 0)
        reset_v = Boton('↺', lambda _=False: self._vol_efecto_reiniciar(), tipo='icono', alto=30, ancho=34, tam=14)
        reset_v.setFixedWidth(34)
        Tooltip(reset_v, tr('Volumen original del sonido (100 %)'))
        bl.addWidget(reset_v, 0)
        Tooltip(self.vol_efecto, tr('Baja o sube el volumen de ESTE sonido. Se guarda y se usa en la línea de tiempo cada vez que genera efectos.'))
        lc.addWidget(barra)
        # la lista de sonidos ya no se muestra (arriba, al buscar o elegir una categoría, salen los sonidos); el árbol sigue
        # vivo en el contenedor oculto porque la selección, los favoritos y los recientes lo usan.
        self.lista_titulo = Etiqueta(tr('SONIDOS'), 11, peso='negrita', color=TEXT_MUTED)
        lc.addWidget(self.lista_titulo)
        lc.addWidget(self.arbol)
        self.banner_texto = _Nota(tr('Busca arriba y toca un sonido para oírlo; úsalo en una sección o bájale el volumen (queda guardado)'), 12, lineas=1, color=TEXT_MUTED, alineacion=Qt.AlignmentFlag.AlignHCenter)
        lc.addWidget(self.banner_texto)
        self.status = _EstadoRegistro()
        # --- columna derecha: reglas y marcadores
        der, cd2 = caja_v(espacio=20)
        self._der, self._der_capa = (der, cd2)
        self.tarjeta_marcadores = Tarjeta(espacio=10, margenes=(20, 18, 20, 18))
        # realce: borde y fondo en el acento del programa
        self.tarjeta_marcadores.setStyleSheet(ui.traducir_hoja(
            'QFrame#tarjeta { background-color: #0E1A33; border: 1px solid #2F5FB8; border-radius: 14px; }'))
        cd2.addWidget(self.tarjeta_marcadores, 1)
        self._acomodar(True)
        self._pintar_reglas()
        self._pintar_marcadores()
    def _tarjeta_control(self, titulo, unidad, rango, inicial, paso, extremos, color):
        """Una tarjeta del estudio: valor en grande, − / + , deslizador, reset y los extremos.
        Devuelve (tarjeta, deslizador, etiqueta del valor)."""
        t = Tarjeta(margenes=(16, 14, 16, 14), espacio=6)
        cab, cc = caja_h(espacio=6)
        cc.addWidget(Punto(color, 10))
        cc.addWidget(Etiqueta(titulo, 14, peso='medio', color='#E0EBFB'))
        cc.addStretch(1)
        fila, cf = caja_h(espacio=6)
        cf.addStretch(1)
        grande = Etiqueta('', 34, peso='extra', color='#FFFFFF')
        cf.addWidget(grande)
        cf.addWidget(Etiqueta(unidad, 15, color=TEXT_MUTED))
        cf.addStretch(1)
        s = Deslizador(rango[0], rango[1], 200, self._slider_cambio, inicial)
        reset = Boton('↺', lambda _=False, sl=s, v=inicial: self._reiniciar_uno(sl, v), tipo='icono', alto=26, ancho=30, tam=13)
        reset.setFixedWidth(30)
        Tooltip(reset, tr('Volver al valor normal'))
        cc.addWidget(reset)
        t.capa.addWidget(cab)
        t.capa.addWidget(fila)
        paso_w, cp = caja_h(espacio=8)
        menos = Boton('−', lambda _=False, sl=s, d=-paso, rg=rango: self._dar_paso(sl, d, rg), tipo='icono', alto=34, ancho=36, tam=16)
        mas = Boton('+', lambda _=False, sl=s, d=paso, rg=rango: self._dar_paso(sl, d, rg), tipo='icono', alto=34, ancho=36, tam=16)
        menos.setFixedWidth(36)
        mas.setFixedWidth(36)
        cp.addWidget(menos)
        cp.addWidget(s, 1)
        cp.addWidget(mas)
        t.capa.addWidget(paso_w)
        ext, ce = caja_h(espacio=4)
        ce.addWidget(Etiqueta(extremos[0], 11, color=TEXT_MUTED))
        ce.addStretch(1)
        ce.addWidget(Etiqueta(extremos[1], 11, color=TEXT_MUTED))
        t.capa.addWidget(ext)
        return (t, s, grande)
    def _dar_paso(self, deslizador, delta, rango):
        deslizador.set(max(rango[0], min(rango[1], deslizador.get() + delta)))
        self._slider_cambio(None)
    def _reiniciar_uno(self, deslizador, valor):
        deslizador.set(valor)
        self._slider_cambio(None)
    def _ajuste_rapido(self, nombre):
        for n, (tono, vel, vol), _c in AJUSTES_RAPIDOS:
            if n == nombre:
                self.tono_slider.set(tono)
                self.velocidad_slider.set(vel)
                self.volumen_slider.set(vol)
                self._slider_cambio(None)
                return
    ANCHO_TRES_COLUMNAS = 1120
    ANCHO_MARCADORES = 380
    def _acomodar(self, forzar=False):
        """Barra de la biblioteca arriba; abajo, el estudio y, a su derecha, reglas y marcadores. Si la
        pantalla es angosta, reglas y marcadores van debajo del estudio, uno al lado del otro."""
        # (5.3) el ancho mínimo ya no es fijo: son las tarjetas del centro las que mandan (si no caben las tres columnas, los
        # marcadores bajan debajo en vez de salirse de la ventana)
        r = self._rejilla
        minimo = self._centro.minimumSizeHint().width() + self.ANCHO_MARCADORES + r.horizontalSpacing() + r.contentsMargins().right()
        angosto = 50 < self.width() < max(self.ANCHO_TRES_COLUMNAS, minimo)
        if angosto == self._angosto and not forzar:
            return
        self._angosto = angosto
        r = self._rejilla
        for w in (self._riel, self._centro, self._der):
            r.removeWidget(w)
        r.addWidget(self._riel, 0, 0, 1, 2)
        r.addWidget(self._centro, 1, 0)
        if angosto:
            self._der_capa.setDirection(QBoxLayout.Direction.LeftToRight)
            self._der.setMinimumSize(0, 440)
            self._der.setMaximumSize(16777215, 16777215)
            r.addWidget(self._der, 2, 0, 1, 2)
        else:
            self._der_capa.setDirection(QBoxLayout.Direction.TopToBottom)
            self._der.setMinimumSize(0, 0)
            self._der.setFixedWidth(self.ANCHO_MARCADORES)
            r.addWidget(self._der, 1, 1)
        r.setColumnStretch(0, 1)
        r.setColumnStretch(1, 0)
        r.setRowStretch(0, 0)
        r.setRowStretch(1, 1)
        r.setRowStretch(2, 0)
    def _ajustar_riel(self):
        """La barra de arriba (buscador + categorías) crece cuando los chips saltan de línea; el alto mínimo de la pantalla tiene
        que saberlo o las tarjetas de abajo se montan encima."""
        r = self._riel
        try:
            if r.hasHeightForWidth() and r.width() > 100:
                h = r.heightForWidth(r.width())
                if h > 0 and h != r.minimumHeight():
                    r.setMinimumHeight(h)
        except Exception:
            pass
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._ajustar_riel()
        self._acomodar()
    def hasHeightForWidth(self):
        # Dentro de la pantalla con desplazamiento, un «alto segun el ancho»
        # hacia que el Lab tomara su alto PREFERIDO (mas que la ventana) en
        # vez de llenarla: el pad se estiraba y los marcadores quedaban fuera.
        return False
    def _slider(self, parent, fila, texto, rango, inicial, var, cb):
        parent.addWidget(Etiqueta(texto, 13, color='#B4C0D6'), fila, 0)
        s = Deslizador(rango[0], rango[1], 200, cb, inicial)
        parent.addWidget(s, fila, 1)
        valor = Etiqueta(var.get(), 13, color='#E0EBFB', alineacion=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        valor.setFixedWidth(72)
        var.observar(lambda: valor.configure(text=var.get()), valor)
        parent.addWidget(valor, fila, 2)
        parent.setColumnStretch(1, 1)
        return s
    # -- reglas y marcadores (columna derecha) ---------------------------------
    def _pintar_reglas(self, animar=True):
        """«Reglas automáticas por bloque», repartidas en HORIZONTAL por toda la zona, con dos modos:
        Simple   — un efecto al PRINCIPIO de cada palabra (o solo de la principal), alternando tres sonidos (los de fábrica son TAP_POP, typewriter e Iphone Taping).
        Avanzado — interruptores por regla (preguntas, cifras, pausas, mayúsculas…) y ajustes de cuándo y cuánto suena."""
        import sfx_rules
        _ENTRADA[0] = bool(animar)
        t = self.tarjeta_reglas.capa
        limpiar_capa(t)
        modo = sfx_rules.cargar_modo()['modo']
        ver_emojis = bool(getattr(self, '_ver_emojis', False))      # v5.8: tercera opción, el sonido de cada emoji (no cambia el modo de las reglas)
        cab, cc = caja_h(espacio=12)
        cc.addWidget(Etiqueta(tr('Reglas automáticas por palabra'), 20, peso='extra', color='#FFFFFF'))
        self._modos_reglas = [tr('Simple'), tr('Avanzado'), tr('Emojis')]
        var = StringVar(self._modos_reglas[2 if ver_emojis else (0 if modo == 'simple' else 1)])

        def elegir(_v=None):
            self._ver_emojis = var.get() == self._modos_reglas[2]
            if not self._ver_emojis:
                sfx_rules.guardar_modo('simple' if var.get() == self._modos_reglas[0] else 'avanzado')
            despues(0, self._pintar_reglas, self)
        seg = Segmentado(self._modos_reglas, var, elegir, alto=34, tam=13)
        Tooltip(seg, tr('Simple: un efecto al principio de CADA PALABRA (o solo de la principal), alternando tres sonidos (si se pisan, pasan a otra pista: SFX 2, SFX 3…). Avanzado: reglas por PALABRA (todas apagadas hasta que enciendas las que quieras) y ajustes de cuándo y cuánto suenan; si dos suenan juntos, pasan a otra pista. Emojis: todos los emojis y el sonido de cada uno, para cambiarlo emoji por emoji.'))
        cc.addWidget(seg)
        # v5.5: dos ideas nuevas del ritmo: la curva de energia (cuantas palabras suenan) y la musica con ducking
        try:
            import ajustes_ui
            curva_var = BooleanVar(bool(ajustes_ui.leer_prefs().get('sfx_curva_energia')))
            curva = ui.Interruptor(tr('Curva de energía'), var=curva_var, tam=12,
                                   comando=lambda: ajustes_ui.guardar_prefs({'sfx_curva_energia': bool(curva_var.get())}))
            Tooltip(curva, tr('El ritmo del habla decide cuántas palabras suenan: en los tramos rápidos suena casi cada palabra y en los calmados solo las importantes (la principal, la primera y la última). El video respira en vez de sonar igual de principio a fin.'))
            cc.addSpacing(10)
            cc.addWidget(curva)
            emo_var = BooleanVar(ajustes_ui.leer_prefs().get('sfx_emojis', True) is not False)
            emo = ui.Interruptor(tr('Sonidos de emojis'), var=emo_var, tam=12,
                                 comando=lambda: ajustes_ui.guardar_prefs({'sfx_emojis': bool(emo_var.get())}))
            Tooltip(emo, tr('Cada emoji suena a lo que es: 🔥 fuego, 😘 beso, 💰 dinero, 👏 aplausos… Los sonidos vienen en el programa; para usar una grabación tuya deja un .wav con el mismo nombre en la carpeta DaVinciSubtitles/sfx_emoji.'))
            cc.addSpacing(10)
            cc.addWidget(emo)
        except Exception:
            pass
        duck = Boton(tr('Música con ducking…'), self._musica_ducking, alto=34, tam=12)
        Tooltip(duck, tr('Elige una música y crea una copia que BAJA SOLA ~14 dB mientras hablas y vuelve a subir en las pausas (calculado desde tu transcripción). Resolve no deja cambiar volúmenes por script, así que el ducking va dentro de la copia.'))
        cc.addSpacing(8)
        cc.addWidget(duck)
        cc.addStretch(1)
        self.resumen_reglas = Etiqueta('', 18, peso='medio', color='#FFFFFF')      # v5.5: la cifra se lee de lejos
        cc.addWidget(self.resumen_reglas)
        t.addWidget(cab)
        if ver_emojis:
            self.resumen_reglas.configure(text=tr('Se usa al generar (GO).'))
            self._pintar_reglas_emojis(t)
        elif modo == 'simple':
            self.resumen_reglas.configure(text=tr('Se usa al generar (GO).'))
            self._pintar_reglas_simple(t)
        else:
            self._pintar_reglas_avanzado(t, None)
    def _pintar_reglas_emojis(self, t):
        """La pestaña «Emojis»: todos los emojis y el sonido de cada uno (emojis_sfx_ui.PanelEmojis)."""
        import emojis_sfx_ui
        panel = emojis_sfx_ui.PanelEmojis(self._oir_ruta, lambda: self.sonido_seleccionado,
                                          lambda texto, color='#8FC7FF': self.status.configure(text=texto, text_color=color))
        t.addWidget(panel, 1)
        _aparecer(panel)
        despues(0, lambda: self._acomodar(True), self)
    def _tarjeta_regla(self, margenes=(14, 12, 14, 12), espacio=8):
        caja = QFrame()
        caja.setObjectName('filaSonidoSimple')
        caja.setStyleSheet(ui.traducir_hoja('QFrame#filaSonidoSimple { background-color: #0F1A30; border: 1px solid #1E2A42; border-radius: 12px; }'))
        cv = QVBoxLayout(caja)
        cv.setContentsMargins(*margenes)
        cv.setSpacing(espacio)
        return caja, cv
    SECCIONES_UI = (
        ('inicio', 'Sonido por palabra', 'Suena cuando entra cada palabra (o solo la principal: elígelo arriba). Los tres sonidos se alternan; si se pisan, pasan a otra pista.', '#4589FF'),
        ('intro', 'Introducción', 'Un riser sube la tensión en el primer bloque del video. Cámbialo o agrega otro.', '#B388FF'),
        ('final', 'Final', 'Un boom cierra el video en el último bloque. Elige al azar entre los dos.', '#FB7185'),
    )
    def _resumen_edicion(self, ruta):
        """Lo que se le hizo a un sonido en «Editar» (recorte y volumen), o '' si va tal cual."""
        import sfx_rules
        partes = []
        rec = sfx_rules.recorte_de(ruta)
        if rec:
            partes.append(tr('parte {a} – {b}', a=_seg_txt(rec[0]), b=_seg_txt(rec[1])))
        v = sfx_rules.volumen_de(ruta)
        if abs(v - 1.0) > 0.005:
            partes.append(f'{int(round(v * 100))} %')
        return '  ·  '.join(partes)
    def _pintar_reglas_simple(self, t):
        import sfx_rules
        # v5.5: en QUÉ palabras suena el modo simple (cada palabra / solo la principal / ninguna); la introducción y el final siguen sonando
        opciones_donde = [('todas', tr('Cada palabra')), ('principal', tr('Solo la principal')), ('ninguna', tr('Ninguna'))]
        var_donde = StringVar(next(n for k, n in opciones_donde if k == sfx_rules.cargar_modo()['donde']))
        def cambio_donde(_v=None):
            sfx_rules.guardar_modo(donde=next((k for k, n in opciones_donde if n == var_donde.get()), 'todas'))
        fila_d, cd_ = caja_h(espacio=12)
        cd_.addWidget(Etiqueta(tr('Sonido por palabra'), 14, peso='medio', color='#FFFFFF'))
        seg_d = Segmentado([n for _k, n in opciones_donde], var_donde, cambio_donde, alto=34, tam=13)
        Tooltip(seg_d, tr('Cada palabra: suena una vez por cada palabra que entra. Solo la principal: suena únicamente en la palabra grande de cada bloque (la que lleva el efecto), así hay menos sonidos y cada uno pesa más. Ninguna: no suenan las palabras; la introducción y el final se mantienen.'))
        cd_.addWidget(seg_d)
        cd_.addStretch(1)
        t.addWidget(fila_d)
        fila = QWidget()
        lay = QHBoxLayout(fila)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        flash = getattr(self, '_flash_slot', None)
        self._flash_slot = None
        for idx, (seccion, titulo, nota, color) in enumerate(self.SECCIONES_UI):
            caja = _TarjetaViva(color, 14, '#0F1A30', '#12203A')
            cv = QVBoxLayout(caja)
            cv.setContentsMargins(16, 14, 16, 14)
            cv.setSpacing(12)
            caja.setMinimumWidth(270)
            cab, cc = caja_h(espacio=12)
            icono = _IconoSfx(seccion, color, 54, retraso=idx * 3)
            cc.addWidget(icono, 0, Qt.AlignmentFlag.AlignVCenter)
            titulo_w = Etiqueta(tr(titulo), 17, peso='extra', color='#FFFFFF', envolver=True)
            cc.addWidget(titulo_w, 1)
            cab.setFixedHeight(56)
            cv.addWidget(cab)
            cv.addWidget(_Nota(tr(nota), 12, lineas=3, color='#9FB0CC'))
            for_ = Etiqueta(tr('ASÍ SONARÁ EN EL VIDEO'), 10, peso='negrita', color=TEXT_MUTED)
            for_.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            cv.addWidget(for_)
            escena = _Escena(seccion, color, 130)
            cv.addWidget(escena, 1)
            caja.enlazar(icono, escena)
            Tooltip(caja, tr({'inicio': 'Suena al inicio de CADA palabra (o solo de la principal), alternando los tres sonidos de abajo. Si dos caen juntos, el segundo pasa a otra pista (SFX 2, SFX 3…) para que no se pisen.',
                              'intro': 'Suena UNA vez, en la primera palabra del video (un riser que abre). Si hay dos sonidos, se usa el primero.',
                              'final': 'Suena UNA vez, en la última palabra del video (un golpe que cierra). Si hay dos sonidos, se usa el primero.'}.get(seccion, nota)))   # al pasar el mouse: el icono se anima y este texto explica qué hace
            sn_ = Etiqueta(tr('SONIDOS · SE ALTERNAN') if seccion == 'inicio' else tr('SONIDOS · UNO AL AZAR'), 10, peso='negrita', color=TEXT_MUTED)
            sn_.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            cv.addWidget(sn_)
            sonidos = sfx_rules.sonidos_simples(seccion)
            for i in range(sfx_rules.CUANTOS_SIMPLES[seccion]):
                ruta = sonidos[i] if i < len(sonidos) else None
                sub = _TarjetaViva(color, 10, '#0B1426', '#0E1930')
                sl = QVBoxLayout(sub)
                sl.setContentsMargins(10, 8, 10, 8)
                sl.setSpacing(6)
                f1, cf = caja_h(espacio=8)
                cf.addWidget(Chip(str(i + 1), color, alto=22, tam=11))
                col_n, cn = caja_v(espacio=0)
                nombre = ui.Elidida(ruta.name if ruta else tr('(sin sonido)'), 13, peso='medio', color='#FFFFFF')
                if ruta:
                    nombre.setToolTip(str(ruta))
                cn.addWidget(nombre)
                extra = self._resumen_edicion(ruta) if ruta else ''
                if extra:
                    cn.addWidget(ui.Elidida(tr('Editado: ') + extra, 11, color=ui.ACCENT_CLARO))
                cf.addWidget(col_n, 1)
                oir = Boton('▶', (lambda _=False, r_=ruta: self._oir_ruta(r_)) if ruta else (lambda _=False: None), tipo='icono', alto=28, ancho=32, tam=12)
                oir.setFixedWidth(32)
                Tooltip(oir, tr('Escuchar este sonido'))
                cf.addWidget(oir)
                editar = Boton(tr('Editar'), lambda _=False, sc=seccion, k=i: self._editar_sonido_simple(sc, k), alto=28, tam=12)
                editar.setMinimumWidth(70)
                editar.setEnabled(bool(ruta))
                Tooltip(editar, tr('Elige la parte del sonido que se usa y baja o sube su volumen.'))
                cf.addWidget(editar)
                sl.addWidget(f1)
                f2, cf2 = caja_h(espacio=6)
                usar = Boton(tr('Usar el elegido'), lambda _=False, sc=seccion, k=i: self._sonido_simple_elegido(sc, k), alto=30, tam=12)
                Tooltip(usar, tr('Cambia este sonido por el que elegiste arriba (busca o toca una categoría).'))
                cf2.addWidget(usar, 1)
                otro = Boton(tr('Archivo…'), lambda _=False, sc=seccion, k=i: self._sonido_simple_archivo(sc, k), alto=30, tam=12)
                Tooltip(otro, tr('Elige un archivo de audio de tu computadora.'))
                cf2.addWidget(otro, 1)
                sl.addWidget(f2)
                cv.addWidget(sub)
                if flash == (seccion, i):
                    despues(140, sub.destello, sub)
            if [str(x) for x in sonidos] != [str(x) for x in sfx_rules.sonidos_de_fabrica(seccion)]:
                cv.addWidget(Enlace(tr('Volver a los de fábrica'), lambda sc=seccion: self._sonidos_simples_de_fabrica(sc), 12, color=TEXT_MUTED, color_hover=ui.ACCENT_CLARO))
            lay.addWidget(caja, 1)
            _aparecer(caja, 90 * idx)
        t.addWidget(fila, 1)
        despues(0, lambda: self._acomodar(True), self)
    def _guardar_sonido_simple(self, seccion, indice, ruta):
        import sfx_rules
        actuales = [str(x) for x in sfx_rules.sonidos_simples(seccion)]
        fabrica = [str(x) for x in sfx_rules.sonidos_de_fabrica(seccion)]
        while len(actuales) < sfx_rules.CUANTOS_SIMPLES[seccion]:
            actuales.append(fabrica[len(actuales)])
        actuales[indice] = str(ruta)
        clave = {'inicio': 'sonidos'}.get(seccion, seccion)
        sfx_rules.guardar_modo(**{clave: actuales})
        self.status.configure(text=tr('Sonido {n} guardado: {name}', n=indice + 1, name=Path(ruta).name), text_color='#8FC7FF')
        self._flash_slot = (seccion, indice)
        self._pintar_reglas(animar=False)
    def _sonido_simple_elegido(self, seccion, indice):
        if not self.sonido_seleccionado:
            self.status.configure(text=tr('Elige primero un sonido arriba (busca o toca una categoría).'), text_color='#E0A030')
            return
        self._guardar_sonido_simple(seccion, indice, self.sonido_seleccionado)
    def _sonido_simple_archivo(self, seccion, indice):
        ruta = filedialog.askopenfilename(parent=self, title=tr('Elige un sonido'),
                                          filetypes=[(tr('Audio'), '*.wav *.mp3 *.flac *.ogg *.m4a *.aif *.aiff')])
        if ruta:
            self._guardar_sonido_simple(seccion, indice, ruta)
    def _sonidos_simples_de_fabrica(self, seccion='inicio'):
        import sfx_rules
        sfx_rules.guardar_modo(**{{'inicio': 'sonidos'}.get(seccion, seccion): []})
        self._pintar_reglas(animar=False)
    # -- «Editar»: elegir de forma visual la parte del sonido que se usa + su volumen
    def _oir_ruta(self, ruta):
        """Suena un sonido tal como viajará a la línea de tiempo (con su recorte y su volumen)."""
        import sfx_rules
        if not ruta:
            return
        try:
            audio, _ = sfx_audio.cargar(sfx_rules.con_volumen(Path(ruta)))
            if len(audio):
                self.reproductor.reproducir(audio)
        except Exception as e:
            self.status.configure(text=tr('No pude reproducir: {e}', e=e), text_color='#E0A030')
    def _editar_sonido_simple(self, seccion, indice):
        import sfx_editor
        import sfx_rules
        sonidos = sfx_rules.sonidos_simples(seccion)
        if indice >= len(sonidos):
            return
        ruta = Path(sonidos[indice])
        color = next((c for sc, _t, _n, c in self.SECCIONES_UI if sc == seccion), '#4589FF')
        dlg = sfx_editor.DialogoEditarSonido(self, ruta, al_guardar=lambda _r, sc=seccion, k=indice: self._tras_editar_simple(sc, k),
                                             color=color, titulo=ruta.name, icono=_IconoSfx(seccion, color, 56))
        dlg.show()
    def _tras_editar_simple(self, seccion, indice):
        self._flash_slot = (seccion, indice)
        self.status.configure(text=tr('Listo: el recorte y el volumen se usarán al generar (GO).'), text_color='#7EE0A8')
        self._pintar_reglas(animar=False)
    def _es_categoria_interna(self, nombre):
        import sfx_rules
        return nombre in (sfx_rules.CATEGORIA_INTRO, sfx_rules.CATEGORIA_FINAL) or str(nombre).startswith(sfx_rules.PREFIJO_REGLA)
    def _archivos_de_categoria(self, categoria):
        """Las rutas de los sonidos de una categoría (biblioteca, carpeta tuya o favoritos)."""
        import sfx_rules
        propias = sfx_rules.fuentes_del_usuario()
        if categoria in propias:
            return [Path(x) for x in propias[categoria]]
        base = Path(self.carpeta_libreria) / categoria
        if not base.is_dir():
            return []
        return [a for a in sorted(base.iterdir()) if a.is_file() and a.suffix.lower() in sfx_rules.EXTENSIONES_AUDIO]
    def _texto_sonido_regla(self, id_):
        import sfx_rules
        concreto = sfx_rules.sonido_de_regla(id_)
        if concreto:
            extra = self._resumen_edicion(concreto)
            return tr('Sonido: ') + Path(concreto).name + (f'  ·  {extra}' if extra else '')
        return tr('Sonido: variado (cualquiera de la categoría)')
    def _regla_sonido(self, id_, ruta):
        import sfx_rules
        reglas = dict(sfx_rules.cargar_avanzado()['reglas'])
        previo = dict(reglas.get(id_) or {})
        if ruta:
            previo['sonido'] = str(ruta)
        else:
            previo.pop('sonido', None)
        reglas[id_] = previo
        sfx_rules.guardar_avanzado(reglas=reglas)
    def _refrescar_resumen_regla(self, id_):
        lbl = getattr(self, '_lbl_regla', {}).get(id_)
        if lbl is not None and ui.vivo(lbl):
            lbl.setText(self._texto_sonido_regla(id_))
            lbl.setToolTip(lbl.text())
        try:
            import sfx_rules
            for r in sfx_rules.REGLAS_PREDEFINIDAS:
                if r['id'] == id_:
                    self._poner_onda_regla(r)
        except Exception:
            pass
    def _categoria_de_regla(self, r):
        import sfx_rules
        return (sfx_rules.cargar_avanzado()['reglas'].get(r['id']) or {}).get('categoria', r['categoria'])
    def _musica_ducking(self):
        """Crea la copia de una musica con el ducking de la ultima transcripcion y ofrece ponerla en Resolve."""
        f = getattr(self.master, 'palabras_de_la_ultima_transcripcion', None)
        palabras = f() if callable(f) else []
        if not palabras:
            messagebox.showinfo(tr('Música con ducking'), tr('Primero transcribe un video (o abre uno ya transcrito): el ducking se calcula con los tiempos de tus palabras.'), parent=self)
            return
        ruta = filedialog.askopenfilename(parent=self, title=tr('Elige la música'),
                                          filetypes=[(tr('Audio'), '*.mp3 *.wav *.m4a *.aac *.flac *.ogg'), (tr('Todos los archivos'), '*.*')])
        if not ruta:
            return
        self.status.configure(text=tr('Preparando la música con ducking…'), text_color='#8FC7FF')
        import threading

        def trabajo():
            try:
                import ducking
                destino = ducking.aplicar(ruta, palabras)
                error = None
            except Exception as e:
                destino, error = None, f'{type(e).__name__}: {e}'
            ejecutar_en_ui(lambda: self._fin_ducking(destino, error))
        threading.Thread(target=trabajo, daemon=True).start()

    def _fin_ducking(self, destino, error):
        if error or not destino:
            self.status.configure(text=tr('No pude preparar la música: {e}', e=error), text_color='#E0A030')
            return
        self.status.configure(text=tr('Música lista: {n}', n=Path(destino).name), text_color='#6FE3AE')
        pregunta = tr('Lista:') + '\n' + str(destino) + '\n\n' + tr('¿La pongo ahora en Resolve, en una pista de audio nueva desde el inicio del timeline?')
        if not messagebox.askyesno(tr('Música con ducking'), pregunta, parent=self):
            return
        import threading

        def poner():
            import resolve_mcp
            codigo = ("RUTA = " + repr(str(destino)) + "\n" + _CODIGO_PONER_MUSICA)
            ok, r, err = resolve_mcp.script(codigo, timeout=40)
            bien = bool(ok and r == 'ok')
            texto = tr('Música colocada en la pista MUSICA.') if bien else tr('No pude colocarla: {e}', e=(err or r))
            ejecutar_en_ui(lambda: self.status.configure(text=texto, text_color='#6FE3AE' if bien else '#E0A030'))
        threading.Thread(target=poner, daemon=True).start()

    def _ruta_de_regla(self, r, al_azar=False):
        import random
        import sfx_rules
        ruta = sfx_rules.sonido_de_regla(r['id'])
        if not ruta:
            archivos = self._archivos_de_categoria(self._categoria_de_regla(r) or '')
            ruta = (random.choice(archivos) if al_azar else archivos[0]) if archivos else None
        return ruta
    def _poner_onda_regla(self, r):
        """La onda de la tarjeta: de lo guardado al instante; si no estaba, se calcula en un hilo y aparece sola."""
        onda = getattr(self, '_ondas_regla', {}).get(r['id'])
        ruta = self._ruta_de_regla(r)
        if onda is None or not ruta:
            return
        picos = picos_de_archivo(ruta, calcular=False)
        if picos:
            onda.poner_picos(picos)
            return
        import threading

        def trabajo():
            try:
                p = picos_de_archivo(ruta)
                guardar_picos()
            except Exception:
                return
            ejecutar_en_ui(lambda: onda.poner_picos(p) if ui.vivo(onda) else None)
        threading.Thread(target=trabajo, daemon=True).start()
    def _oir_regla(self, r):
        import random
        import sfx_rules
        ruta = sfx_rules.sonido_de_regla(r['id'])
        if not ruta:
            archivos = self._archivos_de_categoria(self._categoria_de_regla(r) or '')
            ruta = random.choice(archivos) if archivos else None
        if not ruta:
            self.status.configure(text=tr('Esta regla no tiene sonidos: elige una categoría.'), text_color='#E0A030')
            return
        self._oir_ruta(ruta)
        onda = getattr(self, '_ondas_regla', {}).get(r['id'])
        if onda is not None:
            try:
                audio, sr = sfx_audio.cargar(ruta)
                onda.reproducir(len(audio) / float(sr or 1))
            except Exception:
                pass
    def _editar_regla(self, r, color):
        import sfx_editor
        import sfx_rules
        cat = self._categoria_de_regla(r)
        if not cat:
            self.status.configure(text=tr('Elige primero una categoría para esta regla.'), text_color='#E0A030')
            return
        actual = sfx_rules.sonido_de_regla(r['id'])
        fuente = {'categoria': cat, 'archivos': self._archivos_de_categoria(cat), 'actual': actual,
                  'al_elegir': lambda ruta, i=r['id']: self._regla_sonido(i, ruta)}
        dlg = sfx_editor.DialogoEditarSonido(self, Path(actual) if actual else None,
                                             al_guardar=lambda _r, i=r['id']: self._tras_editar_regla(i),
                                             color=color, titulo=tr(r['nombre']), icono=_IconoSfx(r['id'], color, 56),
                                             fuente=fuente, contexto=tr('Regla: {n}', n=tr(r['nombre'])))
        dlg.show()
    def _tras_editar_regla(self, id_):
        self._refrescar_resumen_regla(id_)
        self.status.configure(text=tr('Listo: el sonido, el recorte y el volumen de la regla se usarán al generar (GO).'), text_color='#7EE0A8')
    def _pintar_reglas_avanzado(self, t, _cfg):
        import sfx_rules
        av = sfx_rules.cargar_avanzado()
        try:
            categorias = sorted(c for c in sfx_rules.categorias_disponibles() if not self._es_categoria_interna(c))
        except Exception:
            categorias = []
        sin_efecto = tr('— sin efecto —')
        self._lbl_regla = {}
        self._ondas_regla = {}
        cont = QWidget()
        cr = QVBoxLayout(cont)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(10)
        cab_r, ccr = caja_h(espacio=8)
        ccr.addWidget(Etiqueta(tr('Reglas por palabra'), 15, peso='medio', color='#E0EBFB'))
        ccr.addWidget(Etiqueta(tr('· gana la primera que se cumple · «Editar» elige la parte del sonido y su volumen'), 12, color=TEXT_MUTED))
        ccr.addStretch(1)
        cr.addWidget(cab_r)
        flujo_w = QWidget()
        flujo = QGridLayout(flujo_w)         # 4 por fila: las tarjetas llenan todo el ancho y el alto de la zona
        flujo.setContentsMargins(0, 0, 0, 0)
        flujo.setHorizontalSpacing(12)
        flujo.setVerticalSpacing(12)
        COLUMNAS = 4
        for c in range(COLUMNAS):
            flujo.setColumnStretch(c, 1)
        guardado = av['reglas']
        n_on = 0
        for k, r in enumerate(sfx_rules.REGLAS_PREDEFINIDAS):
            g = guardado.get(r['id']) or {}
            activa = bool(g.get('on', r['on']))
            cat = g.get('categoria', r['categoria'])
            n_on += activa
            color = COLORES_REGLA.get(r['id'], '#4589FF')
            tarj = _TarjetaViva(color, 14, '#0B1426', '#0F1B33')
            tarj.setMinimumWidth(200)
            tarj.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            tl = QVBoxLayout(tarj)
            tl.setContentsMargins(14, 12, 14, 12)
            tl.setSpacing(7)
            v_on = BooleanVar(activa)
            icono = _IconoSfx(r['id'], color, 84, activa, flexible=True, retraso=k * 2)
            icono.setMaximumHeight(160)
            tl.addWidget(icono, 1)
            onda_r = Onda(color, alto=26, barra=2.4, hueco=2.0)           # v5.5: la onda REAL del sonido de la regla
            onda_r.setMaximumHeight(30)
            tl.addWidget(onda_r)
            self._ondas_regla[r['id']] = onda_r
            self._poner_onda_regla(r)
            nombre_r = Etiqueta(tr(r['nombre']), 14, peso='medio', color='#FFFFFF', alineacion=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            nombre_r.setWordWrap(True)
            tl.addWidget(nombre_r)
            tl.addWidget(_Nota(tr(r['descripcion']), 11, lineas=2, color='#8FA2C2', alineacion=Qt.AlignmentFlag.AlignHCenter))
            resumen = ui.Elidida(self._texto_sonido_regla(r['id']), 11, color=ui.ACCENT_CLARO, alineacion=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            resumen.setToolTip(resumen.text())
            self._lbl_regla[r['id']] = resumen
            tl.addWidget(resumen)
            fila_e, cfe = caja_h(espacio=8)
            oir = Boton('▶', lambda _=False, rr=r: self._oir_regla(rr), tipo='icono', alto=30, ancho=34, tam=12)
            oir.setFixedWidth(34)
            Tooltip(oir, tr('Escuchar el sonido de esta regla'))
            cfe.addWidget(oir)
            editar = Boton(tr('Editar'), lambda _=False, rr=r, cc_=color: self._editar_regla(rr, cc_), alto=30, tam=12)
            Tooltip(editar, tr('Elige un sonido, la parte que se usa y su volumen.'))
            cfe.addWidget(editar, 1)
            tl.addWidget(fila_e)
            fila_c, cfc = caja_h(espacio=10)

            def cambiar(i=r['id'], v=v_on, ic=icono):
                self._regla_activa(i, bool(v.get()))
                ic.poner_activo(bool(v.get()))
            cfc.addWidget(ui.Interruptor('', v_on, cambiar, tam=12), 0)
            v_cat = StringVar(cat if cat in categorias else (sin_efecto if not cat else cat))
            valores = [sin_efecto] + categorias + ([cat] if cat and cat not in categorias else [])
            combo = Combo(valores, v_cat, lambda v, i=r['id']: self._regla_categoria(i, None if v == sin_efecto else v), ancho=120, alto=30, tam=12)
            combo.setMinimumContentsLength(6)
            combo.setSizeAdjustPolicy(combo.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cfc.addWidget(combo, 1)
            tl.addWidget(fila_c)
            tarj.enlazar(icono)
            Tooltip(tarj, tr(r.get('explicacion') or r['descripcion']))      # al pasar el mouse: el icono se anima y este texto dice qué hace
            flujo.addWidget(tarj, k // COLUMNAS, k % COLUMNAS)
            _aparecer(tarj, 30 * k)
        cr.addWidget(flujo_w, 1)
        for fila_g in range(3):
            flujo.setRowStretch(fila_g, 1)
        t.addWidget(cont, 1)
        self.resumen_reglas.configure(text=tr('{n} reglas activas', n=n_on))
        despues(0, lambda: self._acomodar(True), self)
    def _ajuste_avanzado(self, clave, valor, etiqueta=None, formato=None):
        import sfx_rules
        if isinstance(valor, float) and clave in ('probabilidad', 'max_por_minuto'):
            valor = int(round(valor))
        sfx_rules.guardar_avanzado(**{clave: valor})
        if etiqueta is not None and formato is not None:
            etiqueta.configure(text=formato(float(valor)))
        self.status.configure(text=tr('Ajuste guardado: se usa la próxima vez que generes (GO).'), text_color='#8FC7FF')
    def _regla_activa(self, id_, activa):
        import sfx_rules
        reglas = dict(sfx_rules.cargar_avanzado()['reglas'])
        reglas[id_] = dict(reglas.get(id_) or {}, on=bool(activa))
        sfx_rules.guardar_avanzado(reglas=reglas)
        n = sum(1 for r in sfx_rules.REGLAS_PREDEFINIDAS if (reglas.get(r['id']) or {}).get('on', r['on']))
        self.resumen_reglas.configure(text=tr('{n} reglas activas', n=n))
    def _regla_categoria(self, id_, categoria):
        import sfx_rules
        reglas = dict(sfx_rules.cargar_avanzado()['reglas'])
        previo = dict(reglas.get(id_) or {}, categoria=categoria)
        previo.pop('sonido', None)              # otra categoría = vuelve a sonar cualquiera de ella
        reglas[id_] = previo
        sfx_rules.guardar_avanzado(reglas=reglas)
        self._refrescar_resumen_regla(id_)
    # -- volumen del sonido elegido (se guarda y se usa en la línea de tiempo)
    def _vol_efecto_texto(self, v):
        self.vol_efecto_txt.configure(text=f'{int(round(v * 100))} %')
    def _vol_efecto_cambio(self, v):
        self._vol_efecto_texto(v)
        self.volumen_slider.set(v)
        self._slider_cambio(None)              # actualiza lo oculto y suena a los 200 ms
        cancelar(getattr(self, '_t_guardar_vol', None))
        self._t_guardar_vol = despues(450, self._guardar_vol_efecto, self)
    def _vol_efecto_reiniciar(self):
        if not self.sonido_seleccionado:
            return
        self.vol_efecto.set(1.0)
        self._vol_efecto_cambio(1.0)
    def _guardar_vol_efecto(self):
        import sfx_rules
        if not self.sonido_seleccionado:
            return
        v = self.vol_efecto.get()
        sfx_rules.guardar_volumen(self.sonido_seleccionado, v)
        if abs(v - 1.0) < 0.005:
            self.status.configure(text=tr('{name}: volumen original', name=self.sonido_seleccionado.name), text_color='#8FC7FF')
        else:
            self.status.configure(text=tr('Volumen guardado: {name} al {p} % — se usará en la línea de tiempo', name=self.sonido_seleccionado.name, p=int(round(v * 100))), text_color='#7EE0A8')
    def _sincronizar_volumen(self):
        """Al elegir un sonido: su volumen guardado en la barra (y los controles ocultos en neutro)."""
        import sfx_rules
        v = sfx_rules.volumen_de(self.sonido_seleccionado) if self.sonido_seleccionado else 1.0
        self.tono_slider.set(0.0)
        self.velocidad_slider.set(1.0)
        self.volumen_slider.set(v)
        self.vol_efecto.set(v)
        self._vol_efecto_texto(v)
        self._actualizar_valores()
    def _abrir_reglas(self):
        """Abre el sfx_rules.json que el usuario SI puede editar (la copia de
        ~/DaVinciSubtitles; si no existe, se crea igual al que trae el
        programa)."""
        import shutil
        import sfx_rules
        propia = sfx_rules.CARPETA_USUARIO / 'sfx_rules.json'
        try:
            if not propia.exists():
                propia.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(sfx_rules.ruta_reglas(), propia)
            if sys.platform.startswith('win'):
                import os
                os.startfile(str(propia))
            else:
                import subprocess
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(propia)])
        except Exception as e:
            self.status.configure(text=tr('No pude abrir las reglas: {e}', e=e), text_color='#E0A030')
    COLORES_MARCADOR = (('Blue', tr('Azul'), '#3B82F6'), ('Cyan', tr('Cian'), '#22D3EE'), ('Green', tr('Verde'), '#22C55E'), ('Yellow', tr('Amarillo'), '#EAB308'), ('Red', tr('Rojo'), '#EF4444'), ('Pink', tr('Rosa'), '#EC4899'), ('Purple', tr('Morado'), '#A855F7'), ('Fuchsia', tr('Fucsia'), '#D946EF'), ('Rose', tr('Rosado'), '#FB7185'), ('Lavender', tr('Lavanda'), '#C4B5FD'), ('Sky', tr('Celeste'), '#38BDF8'), ('Mint', tr('Menta'), '#6EE7B7'), ('Lemon', tr('Limón'), '#FDE047'), ('Sand', tr('Arena'), '#D4A373'), ('Cocoa', tr('Cacao'), '#8B5E3C'), ('Cream', tr('Crema'), '#F5F5DC'))
    SIN_MAPA_SFX = tr('— ignorar —')
    def _ruta_mapa_marcadores(self):
        return CARPETA_PREFS / 'sfx_marcadores.json'
    def _pintar_marcadores(self):
        """«Efectos en los marcadores» (v1.0.59; v5.0.0 deja de ser un
        dialogo): el usuario asigna UNA VEZ una fuente de sonidos a cada
        color de marcador («rojo = golpes, azul = whoosh…»); se guarda en
        ~/DaVinciSubtitles/sfx_marcadores.json al tocarlo. «Colocar» deja la
        orden RESUELTA (rutas absolutas por color — el patron de
        sfx_pendiente.json: el 'datos' del job no llega al Lua) y corre la
        accion sfx_marcadores por el camino de siempre (API en Studio,
        Puente en Free). «Reemplazar» hace lo mismo cambiando los efectos
        del programa que ya suenan en esos marcadores."""
        import sfx_rules
        t = self.tarjeta_marcadores.capa
        limpiar_capa(t)
        cab, cc = caja_h(espacio=8)
        cc.addWidget(Etiqueta(tr('Efectos en los marcadores'), 18, peso='extra', color='#FFFFFF'))
        cc.addStretch(1)
        for _c, _n, muestra in self.COLORES_MARCADOR[:5]:
            cc.addWidget(Punto(muestra, 11))
        t.addWidget(cab)
        t.addWidget(_Nota(tr('Pon marcadores en tu timeline (tecla M) y asigna qué carpeta de sonidos va con cada color.'), 13, lineas=2, color='#C9D6EC'))
        try:
            categorias = sorted(sfx_rules.categorias_disponibles())
        except Exception:
            categorias = []
        try:
            guardado = json.loads(self._ruta_mapa_marcadores().read_text(encoding='utf-8'))
        except Exception:
            guardado = {}
        if not isinstance(guardado, dict):
            guardado = {}
        mapa_guardado = guardado.get('mapa') or {}
        self._reemplazar_marcadores = guardado.get('reemplazar') is True
        opciones = [self.SIN_MAPA_SFX] + categorias
        self._vars_marcadores = {}
        lista = Desplazable(espacio=8, margenes=(0, 4, 8, 4))
        for color_api, etiqueta, muestra in self.COLORES_MARCADOR:
            fila = QFrame()
            fila.setObjectName('filaColor')
            fila.setStyleSheet(ui.traducir_hoja('QFrame#filaColor { background-color: #12213D; border: 1px solid #1F3157; border-radius: 10px; }'))
            cf = QHBoxLayout(fila)
            cf.setContentsMargins(12, 5, 8, 5)
            cf.setSpacing(10)
            cf.addWidget(Punto(muestra, 13))
            nombre = Etiqueta(etiqueta, 14, peso='medio', color='#FFFFFF')
            nombre.setFixedWidth(76)
            cf.addWidget(nombre)
            valor = mapa_guardado.get(color_api) or self.SIN_MAPA_SFX
            if valor not in opciones:
                valor = self.SIN_MAPA_SFX
            var = StringVar(valor)
            self._vars_marcadores[color_api] = var
            combo_m = Combo(opciones, var, lambda _v=None: self._guardar_mapa(), alto=34, tam=13)
            combo_m.setMinimumContentsLength(6)
            combo_m.setSizeAdjustPolicy(combo_m.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cf.addWidget(combo_m, 1)
            lista.agregar(fila)
        t.addWidget(lista, 1)
        self.estado_marcadores = _Nota('', 12, lineas=2, color=TEXT_MUTED)
        t.addWidget(self.estado_marcadores)
        fila_b, cfb = caja_h(espacio=10)
        self.colocar_btn = Boton(tr('Colocar'), lambda: self._colocar_marcadores(False), tipo='primario', alto=46, tam=14, negrita=True)
        Tooltip(self.colocar_btn, tr('Pone un sonido en cada marcador de los colores asignados.'))
        cfb.addWidget(self.colocar_btn, 3)
        self.reemplazar_marcadores_btn = Boton(tr('Reemplazar'), lambda: self._colocar_marcadores(True), alto=46, tam=14)
        Tooltip(self.reemplazar_marcadores_btn, tr('Igual, pero cambia los efectos que ya hay en esos marcadores (solo los del programa).'))
        cfb.addWidget(self.reemplazar_marcadores_btn, 2)
        t.addWidget(fila_b)
        if not categorias:
            self.estado_marcadores.configure(text=tr('No encontré ningún sonido para usar (ni los del programa ni carpetas tuyas).'), text_color='#E0A030')
            self.colocar_btn.setEnabled(False)
            self.reemplazar_marcadores_btn.setEnabled(False)
    def _mapa_actual(self):
        return {c: v.get() for c, v in self._vars_marcadores.items()
                if v.get() != self.SIN_MAPA_SFX}
    def _guardar_mapa(self, reemplazar=None):
        if reemplazar is not None:
            self._reemplazar_marcadores = bool(reemplazar)
        mapa = self._mapa_actual()
        try:
            ruta = self._ruta_mapa_marcadores()
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(json.dumps({'mapa': mapa, 'reemplazar': bool(self._reemplazar_marcadores)}, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as e:
            self.estado_marcadores.configure(text=tr('No pude guardar el mapa: {e}', e=e), text_color='#E0A030')
            return None
        return mapa
    def _abrir_sfx_marcadores(self):
        """Compat v4: el dialogo es ahora la tarjeta de la derecha."""
        self.tarjeta_marcadores.setFocus()
    def _colocar_marcadores(self, reemplazar):
        import sfx_rules
        mapa = self._guardar_mapa(reemplazar)
        if mapa is None:
            return
        if not mapa:
            self.estado_marcadores.configure(text=tr('Asigna al menos un color antes de colocar.'), text_color='#E0A030')
            return
        pendiente, perdidas = {}, []
        for color_api, cat in mapa.items():
            archivos = [str(r) for r in sfx_rules.archivos_de(cat)]
            if archivos:
                pendiente[color_api] = {'categoria': cat, 'archivos': archivos}
            else:
                perdidas.append(cat)
        if not pendiente:
            self.estado_marcadores.configure(text=tr('Ninguna de las carpetas asignadas tiene sonidos ya ({join}).', join=', '.join(perdidas)), text_color='#E0A030')
            return
        self.estado_marcadores.configure(text=tr('Analizando las ondas de los sonidos…'), text_color=TEXT_MUTED)
        for b in (self.colocar_btn, self.reemplazar_marcadores_btn):
            b.setEnabled(False)
        aviso_perdidas = (' ' + tr('(sin sonidos, se saltan: {lista})', lista=', '.join(perdidas))
                          if perdidas else '')
        def trabajo():
            ondas = analizar_ondas(pendiente)
            try:
                dejar_orden(ARCHIVO_MARCADORES, {
                    'mapa': pendiente,
                    'ondas': ondas,
                    'reemplazar': bool(reemplazar),
                    'creado_en': time.time(),
                })
            except OSError as e:
                return (False, tr('No pude dejar la orden: {e}', e=e), True)
            ejecutar_en_ui(lambda: self.estado_marcadores.configure(text=tr('Colocando en Resolve…') + aviso_perdidas, text_color=TEXT_MUTED) if ui.vivo(self) else None)
            import resolve_bridge
            try:
                exito, err = resolve_bridge.ejecutar('sfx_marcadores', timeout=180)
            except Exception as e:
                exito, err = (False, f'{type(e).__name__}: {e}')
            if exito:
                retirar_orden(ARCHIVO_MARCADORES)
            return (exito, err, False)
        def mostrar(resultado, error):
            for b in (self.colocar_btn, self.reemplazar_marcadores_btn):
                b.setEnabled(True)
            exito, err, propio = resultado if resultado else (False, str(error), False)
            if exito:
                self.estado_marcadores.configure(text=tr('✓ Sonidos colocados en tus marcadores. Revisa Resolve.'), text_color='#8FC7FF')
            elif propio:
                self.estado_marcadores.configure(text=err, text_color='#E0A030')
            else:
                primera = (err or '').strip().splitlines()
                self.estado_marcadores.configure(text=tr('No se pudo: {detalle}  (el registro completo está en «Qué respondió Resolve»).', detalle=primera[0][:180] if primera else tr('sin detalle')), text_color='#E0A030')
        ui.correr_en_hilo(self, trabajo, mostrar)
    # -- pad y controles -------------------------------------------------------
    def _mover_pad(self, x, y, reproducir):
        self._pad_x = max(0.0, min(1.0, x))
        self._pad_y = max(0.0, min(1.0, y))
        self._pintar_marcador()
        tono = RANGO_TONO[0] + self._pad_x * (RANGO_TONO[1] - RANGO_TONO[0])
        vel = RANGO_VELOCIDAD[1] - self._pad_y * (RANGO_VELOCIDAD[1] - RANGO_VELOCIDAD[0])
        self.tono_slider.set(tono)
        self.velocidad_slider.set(vel)
        self._actualizar_valores()
        if reproducir:
            self._reproducir()
    def _pad_release(self, _evento):
        self._reproducir()
    def _pintar_marcador(self):
        self.pad.update()
    def _actualizar_valores(self):
        tono = self.tono_slider.get()
        vel = self.velocidad_slider.get()
        self.tono_valor.set(f'{tono:+.1f} st')
        self.velocidad_valor.set(f'{vel:.2f} x')
        self.volumen_valor.set(f'{int(self.volumen_slider.get() * 100)} %')
        self.tono_lbl.configure(text=tr('Tono {v}', v=f'{tono:+.1f}'.replace('.', ',')))
        self.velocidad_lbl.configure(text=tr('Velocidad {v}x', v=f'{vel:.2f}'.replace('.', ',')))
        self.tono_big.configure(text=f'{tono:+.1f}'.replace('.', ','))
        self.velocidad_big.configure(text=f'{vel:.2f}'.replace('.', ','))
        self.volumen_big.configure(text=f'{int(round(self.volumen_slider.get() * 100))}')
    def _slider_cambio(self, _valor):
        self._pad_x = (self.tono_slider.get() - RANGO_TONO[0]) / (RANGO_TONO[1] - RANGO_TONO[0])
        self._pad_y = (RANGO_VELOCIDAD[1] - self.velocidad_slider.get()) / (RANGO_VELOCIDAD[1] - RANGO_VELOCIDAD[0])
        self._pintar_marcador()
        self._actualizar_valores()
        cancelar(self._temporizador_previa)
        self._temporizador_previa = despues(200, self._reproducir, self)
    @staticmethod
    def _fold(texto):
        """minusculas y sin tildes, para que el buscador no exija acentos."""
        texto = str(texto).lower()
        for a, b in [('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ü', 'u'), ('ñ', 'n')]:
            texto = texto.replace(a, b)
        return texto
    # -- biblioteca ------------------------------------------------------------
    def _recargar_arbol(self):
        """(Re)construye el arbol colapsable.

        Cada categoria es un nodo padre que se puede plegar/desplegar; los
        sonidos son sus hijos. Se recuerda que categorias estaban abiertas
        para no cerrarlas cada vez que se marca un favorito.

        Con texto en el buscador (v1.0.62) solo entran los sonidos cuyo
        nombre O carpeta lo contienen, y las categorias con resultados se
        abren solas.
        """
        abiertos_previos = set()
        for i in range(self.arbol.topLevelItemCount()):
            it = self.arbol.topLevelItem(i)
            if it.isExpanded():
                abiertos_previos.add(it.data(0, Qt.ItemDataRole.UserRole + 1))
        seleccionado = str(self.sonido_seleccionado) if self.sonido_seleccionado else None
        self.arbol.blockSignals(True)
        self.arbol.clear()
        self._nodo_a_ruta = {}
        filtro = self._fold(self.filtro_var.get().strip()) if hasattr(self, 'filtro_var') else ''
        activa = None if filtro else self._cat_activa      # buscando, se mira en todas las categorías

        def pasa(ruta, categoria=''):
            if not filtro:
                return True
            return filtro in self._fold(ruta.stem) or filtro in self._fold(categoria)

        def nodo(texto, clave, cuenta=None, color=None):
            it = QTreeWidgetItem([texto, str(cuenta) if cuenta is not None else ''])
            it.setData(0, Qt.ItemDataRole.UserRole + 1, clave)
            it.setFont(0, ui.fuente(13, peso='medio'))
            it.setForeground(1, QColor('#5A6B87'))
            if color:
                it.setForeground(0, QColor(color))
            self.arbol.addTopLevelItem(it)
            it.setExpanded(bool(filtro) or activa is not None or clave in abiertos_previos)
            return it

        def hoja(padre, ruta, texto):
            it = QTreeWidgetItem([texto, ''])
            it.setData(0, Qt.ItemDataRole.UserRole, str(ruta))
            padre.addChild(it)
            self._nodo_a_ruta[id(it)] = ruta
            if seleccionado and str(ruta) == seleccionado:
                self.arbol.setCurrentItem(it)
            return it

        cat = sfx_audio.catalogo(self.carpeta_libreria, self.carpetas_usuario)
        if not cat:
            self.arbol.addTopLevelItem(QTreeWidgetItem([tr('(no encuentro ningún sonido)'), '']))
            self.arbol.blockSignals(False)
            return
        favoritos_validos = [Path(r) for r in sorted(self.favoritos)
                             if Path(r).is_file() and pasa(Path(r), 'favoritos')]
        self._pintar_chips(cat, filtro, activa)
        if favoritos_validos and activa in (None, '__favoritos__'):
            n = nodo(tr('★  Favoritos'), '__favoritos__', len(favoritos_validos), ui.AMBAR)
            for p in favoritos_validos:
                hoja(n, p, f'★  {p.stem}')
        if activa == '__recientes__':
            recientes = [Path(x) for x in self._recientes if Path(x).is_file()]
            n = nodo(tr('Recientes'), '__recientes__', len(recientes), '#B388FF')
            for p in recientes:
                hoja(n, p, p.stem)
        con_resultados = False
        for categoria in sorted(cat):
            if activa is not None and categoria != activa:
                continue
            visibles = [r for r in cat[categoria] if pasa(r, categoria)]
            if filtro and not visibles:
                continue
            con_resultados = con_resultados or bool(visibles)
            visible = categoria[:1].upper() + categoria[1:] if categoria else categoria
            n = nodo(visible, categoria, len(visibles))
            for ruta in visibles:
                marca = '★  ' if str(ruta) in self.favoritos else ''
                hoja(n, ruta, f'{marca}{ruta.stem}')
        if filtro and not con_resultados and not favoritos_validos:
            self.arbol.addTopLevelItem(QTreeWidgetItem([tr('(nada con «{filtro}»)', filtro=filtro), '']))
        self.arbol.blockSignals(False)
        total = sum(self.arbol.topLevelItem(k).childCount() for k in range(self.arbol.topLevelItemCount()))
        nombre = {None: tr('todas las categorías'), '__favoritos__': tr('Favoritos'), '__recientes__': tr('Recientes')}.get(activa, activa)
        self.lista_titulo.configure(text=tr('SONIDOS · {n} · {c}', n=nombre, c=total))
    def _ruta_de(self, item):
        if item is None:
            return None
        valor = item.data(0, Qt.ItemDataRole.UserRole)
        return Path(valor) if valor else None
    def _al_elegir(self, item):
        ruta = self._ruta_de(item)
        if ruta is None:
            return
        self._cargar_sonido(ruta)
    def _doble_clic_arbol(self, item):
        """Doble clic en un sonido = alternar favorito.
        En una categoria = plegar/desplegar (lo hace el arbol)."""
        if self._ruta_de(item) is not None:
            self._toggle_favorito()
    def _cargar_sonido(self, ruta):
        try:
            self.audio_original, _ = sfx_audio.cargar(ruta)
        except Exception as e:
            self.status.configure(text=tr('No pude cargar {name}: {e}', name=ruta.name, e=e), text_color='#E0A030')
            return
        self.sonido_seleccionado = ruta
        self._sincronizar_volumen()
        dur = len(self.audio_original) / sfx_audio.SAMPLE_RATE
        try:
            relativo = ruta.relative_to(self.carpeta_libreria)
            texto = ' · '.join(relativo.parts[:-1] + (relativo.name,))
        except ValueError:
            texto = ruta.name
        self.sel_label.configure(text=ruta.name)
        self.sel_label.setToolTip(str(ruta))
        try:
            carpeta_txt = ' · '.join(ruta.relative_to(self.carpeta_libreria).parts[:-1]) or ruta.parent.name
        except ValueError:
            carpeta_txt = ruta.parent.name
        self.sel_meta.configure(text=f'{carpeta_txt}  ·  {dur:.2f} s'.replace('.', ','))
        self._refrescar_fav()
        self._anotar_reciente(ruta)
        despues(0, self._recargar_arbol, self)      # el chip del sonido elegido se resalta
        self.status.configure(text=tr('{name} · {dur:.2f} s · listo', name=ruta.name, dur=dur), text_color='gray60')
        self._reproducir()
    def _anotar_reciente(self, ruta):
        """Los últimos sonidos que abriste (los 10 más recientes, sin repetir)."""
        antes = bool(self._recientes)
        self._recientes = [str(ruta)] + [x for x in self._recientes if x != str(ruta)]
        self._recientes = self._recientes[:10]
        _escribir_lista(ARCHIVO_RECIENTES, self._recientes)
        if not antes:
            despues(0, self._recargar_arbol, self)
    def _elegir_categoria(self, clave):
        self._cat_activa = clave
        if self.filtro_var.get():
            self.filtro_var.set('')
        despues(0, self._recargar_arbol, self)
    MAX_CHIPS_SONIDOS = 48
    def _volver_categorias(self):
        self._elegir_categoria(None)
        self.filtro_var.set('')
        self._recargar_arbol()
    def _pintar_chips(self, cat, filtro, activa):
        """Arriba, bajo el buscador: las CATEGORÍAS, y en cuanto escribes (o eliges una categoría) pasan a ser los SONIDOS que
        coinciden, para tocarlos y oírlos."""
        sel = str(self.sonido_seleccionado) if self.sonido_seleccionado else ''
        firma = (filtro, activa, tuple(sorted(cat)), tuple(sorted(self.favoritos)), tuple(self._recientes), sel)
        if firma == getattr(self, '_sig_chips2', None):
            return
        self._sig_chips2 = firma
        if not filtro and activa is None:
            self._sig_chips = None
            self._pintar_categorias(cat, bool(self.favoritos))
            return
        self._sig_chips = None
        capa = self.chips_cat
        limpiar_capa(capa)
        rutas = []
        if filtro:
            vistos = set()
            for categoria in sorted(cat):
                for r in cat[categoria]:
                    if (filtro in self._fold(r.stem) or filtro in self._fold(categoria)) and str(r) not in vistos:
                        vistos.add(str(r))
                        rutas.append(r)
            for r in sorted(self.favoritos):
                if Path(r).is_file() and filtro in self._fold(Path(r).stem) and str(r) not in vistos:
                    rutas.append(Path(r))
        elif activa == '__favoritos__':
            rutas = [Path(r) for r in sorted(self.favoritos) if Path(r).is_file()]
        elif activa == '__recientes__':
            rutas = [Path(x) for x in self._recientes if Path(x).is_file()]
        else:
            rutas = list(cat.get(activa, []))
        volver = Chip(tr('← Categorías'), ui.AMBAR, self._volver_categorias, alto=30, tam=13)
        capa.addWidget(volver)
        for r in rutas[:self.MAX_CHIPS_SONIDOS]:
            capa.addWidget(Chip(r.stem, ui.ACCENT_CLARO, lambda ruta=r: self._cargar_sonido(ruta), alto=30, tam=13,
                                lleno=str(r) == sel, estrella=str(r) in self.favoritos))
        if len(rutas) > self.MAX_CHIPS_SONIDOS:
            capa.addWidget(Etiqueta(tr('+{n} más: escribe más letras para afinar', n=len(rutas) - self.MAX_CHIPS_SONIDOS), 12, color=TEXT_MUTED))
        if not rutas:
            capa.addWidget(Etiqueta(tr('(nada con «{filtro}»)', filtro=filtro), 13, color=TEXT_MUTED))
    def _pintar_categorias(self, cat, hay_favoritos):
        """Las categorías como chips (Todas · ★ Favoritos · Recientes · cada carpeta)."""
        firma = (self._cat_activa, tuple(sorted(cat)), bool(hay_favoritos), bool(self._recientes))
        if firma == self._sig_chips:
            return
        self._sig_chips = firma
        capa = self.chips_cat
        limpiar_capa(capa)

        def chip(texto, clave, color):
            capa.addWidget(Chip(texto, color, lambda k=clave: self._elegir_categoria(k), alto=30, tam=13,
                                lleno=self._cat_activa == clave))
        chip(tr('Todas'), None, ui.ACCENT_CLARO)
        if hay_favoritos:
            chip(tr('★ Favoritos'), '__favoritos__', ui.AMBAR)
        if self._recientes:
            chip(tr('Recientes'), '__recientes__', '#B388FF')
        for categoria in sorted(cat):
            chip(categoria[:1].upper() + categoria[1:] if categoria else categoria, categoria, ui.ACCENT_CLARO)
    def _refrescar_fav(self):
        es = bool(self.sonido_seleccionado) and str(self.sonido_seleccionado) in self.favoritos
        self.fav_btn.poner(texto=tr('★ Favorito') if es else tr('☆ Favorito'), lleno=es)
    def _toggle_favorito(self, _evento=None):
        if not self.sonido_seleccionado:
            self.status.configure(text=tr('Elige un sonido antes de marcar favorito.'), text_color='#E0A030')
            return
        clave = str(self.sonido_seleccionado)
        if clave in self.favoritos:
            self.favoritos.discard(clave)
            self.status.configure(text=tr('Quitado de favoritos: {name}', name=Path(clave).name), text_color='gray70')
        else:
            self.favoritos.add(clave)
            self.status.configure(text=tr('★ Agregado a favoritos: {name}', name=Path(clave).name), text_color='#FFD166')
        guardar_favoritos(self.favoritos)
        self._recargar_arbol()
        self._refrescar_fav()
    def _agregar_carpeta(self):
        carpeta = filedialog.askdirectory(parent=self, title=tr('Elige una carpeta con sonidos'), mustexist=True)
        if not carpeta:
            return
        if carpeta in self.carpetas_usuario:
            self.status.configure(text=tr('La carpeta ya estaba en la biblioteca: {carpeta}', carpeta=carpeta), text_color='gray70')
            return
        if not sfx_audio._sonidos_de(Path(carpeta)):
            hay = any(sfx_audio._sonidos_de(sub)
                      for sub in Path(carpeta).iterdir()
                      if sub.is_dir())
            if not hay:
                messagebox.showwarning(tr('Sin sonidos'), tr('No encontré archivos de audio en:\n{carpeta}\n\nElige la carpeta que contiene los .wav/.mp3.', carpeta=carpeta), parent=self)
                return
        self.carpetas_usuario.append(carpeta)
        guardar_carpetas_usuario(self.carpetas_usuario)
        self._recargar_arbol()
        self._pintar_marcadores()
        self.status.configure(text=tr('Carpeta agregada (queda recordada): {carpeta}', carpeta=carpeta), text_color='#8FC7FF')
    # -- sonido ----------------------------------------------------------------
    def _procesar_actual(self):
        if self.audio_original is None:
            return
        return sfx_audio.procesar(self.audio_original, semitonos=self.tono_slider.get(), velocidad=self.velocidad_slider.get(), volumen=self.volumen_slider.get())
    def _reproducir(self):
        if self.audio_original is None:
            return
        audio = self._procesar_actual()
        if audio is None or len(audio) == 0:
            return None
        try:
            self.reproductor.reproducir(audio)
        except Exception as e:
            self.status.configure(text=tr('No pude reproducir: {e}', e=e), text_color='#E0A030')
    def _reiniciar(self):
        self.tono_slider.set(0.0)
        self.velocidad_slider.set(1.0)
        self.volumen_slider.set(1.0)
        self._pad_x = 0.5
        self._pad_y = 0.5
        self._pintar_marcador()
        self._actualizar_valores()
        if self.audio_original is not None:
            self._reproducir()
    def _nombre_procesado(self):
        base = self.sonido_seleccionado.stem if self.sonido_seleccionado else 'sfx'
        tono = self.tono_slider.get()
        vel = self.velocidad_slider.get()
        vol = self.volumen_slider.get()
        marca = []
        if abs(tono) > 0.1:
            marca.append(f't{int(round(tono)):+d}'.replace('+', 'p').replace('-', 'm'))
        if abs(vel - 1.0) > 0.01:
            marca.append(f'v{int(vel * 100)}')
        if abs(vol - 1.0) > 0.01:
            marca.append(f'g{int(vol * 100)}')
        sufijo = '_' + '_'.join(marca) if marca else '_editado'
        return f'{base}{sufijo}.wav'
    def _guardar_wav_procesado(self):
        """Devuelve la ruta del wav guardado, o None si no habia nada.

        Guarda SOLO en la carpeta destino (al lado del video, o Descargas).
        No toca la biblioteca de sonidos original — antes copiaba tambien a
        sfx_library/personalizados/ y eso ensuciaba la biblioteca del
        usuario con archivos que no eran suyos.
        """
        audio = self._procesar_actual()
        if audio is None:
            self.status.configure(text=tr('Elige primero un sonido.'), text_color='#E0A030')
            return
        destino = self.carpeta_destino / self._nombre_procesado()
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            sfx_audio.guardar_wav(audio, destino)
        except Exception as e:
            self.status.configure(text=tr('No pude guardar: {e}', e=e), text_color='#E0A030')
            return None
        return destino
    def _guardar(self):
        destino = self._guardar_wav_procesado()
        if destino:
            self.status.configure(text=tr('Guardado en {destino}', destino=destino), text_color='#8FC7FF')
    def _instalar_script_de_resolve(self):
        """Copia el script 'Insertar SFX' a la carpeta de Scripts de Resolve.

        Devuelve (ruta_instalada, se_acaba_de_copiar, mensaje_de_error).

        Sin este script en Resolve, 'Enviar a Resolve' es inutil: la ventana
        deja la orden pendiente pero no hay nadie del lado de Resolve para
        leerla. Se instala automaticamente cada vez, para no depender de que
        el usuario recuerde hacerlo desde el otro boton.
        """
        try:
            import instalador_scripts as ins
        except Exception as e:
            return (None, False, tr('No pude cargar el instalador de scripts: {e}', e=e))
        try:
            copiados, error, _detalle = ins.instalar_scripts_en_resolve()
        except Exception as e:
            return (None, False, f'{type(e).__name__}: {e}')
        if error:
            return (None, False, error)
        recien = any((n.startswith('CineCaptions_InsertarSFX') for n in copiados))
        return (ins.carpeta_scripts_resolve(), recien, None)
    def _aplicar_topmost(self):
        """«📌 Siempre delante»: la ventana del programa (el Lab es una
        pantalla de ella) por encima de Resolve."""
        activo = bool(self.topmost_var.get())
        ventana = self.window()
        try:
            if sys.platform.startswith('win') and ventana.isVisible():
                import ctypes
                HWND_TOPMOST, HWND_NOTOPMOST = (-1, -2)
                ctypes.windll.user32.SetWindowPos(int(ventana.winId()), HWND_TOPMOST if activo else HWND_NOTOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            elif ventana is not self and bool(ventana.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != activo:
                ventana.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, activo)
                ventana.show()
        except Exception:
            pass
        try:
            self.pin_btn.poner(texto=tr('📌 Siempre delante') if activo else tr('📌 Delante: apagado'), lleno=activo)
        except Exception:
            return None
    def _toggle_topmost(self):
        self.topmost_var.set(not self.topmost_var.get())
        self._aplicar_topmost()
    DESTINO_CABEZAL = tr('Bajo el cabezal')
    TEXTO_BANNER_CABEZAL = tr('Modo REEMPLAZAR activo: aparca el cabezal sobre el efecto en Resolve y pulsa «⟲ Reemplazar».')
    def _destinos_marcador(self):
        """Etiqueta del menu -> (color de la API, nombre del color).

        v3.3.0: hasta la v3.2 el color salia de partir la etiqueta por «: »
        y buscar el nombre en español; con la interfaz traducida la etiqueta
        es otra, asi que se busca por la etiqueta ENTERA.
        """
        return {tr('Marcadores: {color}', color=nombre): (color, nombre) for color, nombre, _ in self.COLORES_MARCADOR}
    def _on_destino_reemplazo(self, valor):
        if valor == self.DESTINO_CABEZAL:
            texto = self.TEXTO_BANNER_CABEZAL
        else:
            nombre = self._destinos_marcador().get(valor, (None, valor))[1]
            texto = tr('Modo REEMPLAZAR activo: pulsa «⟲ Reemplazar» y el efecto de cada marcador {color} pasa a ser el sonido elegido (solo efectos del programa).', color=nombre)
        self.banner_texto.configure(text=texto, text_color='#C4B5FD')
    def _on_envio(self, valor):
        """El segmentado Insertar / Reemplazar (v5.0.0; en la v4 era el boton
        «⟲ Reemplazar bajo el cabezal…»)."""
        if (valor == self.ENVIOS[1]) != bool(self.modo_reemplazo.get()):
            self._toggle_reemplazo()
    def _toggle_reemplazo(self):
        activo = not self.modo_reemplazo.get()
        self.modo_reemplazo.set(activo)
        self.envio_var.set(self.ENVIOS[1] if activo else self.ENVIOS[0])
        self.fila_destino.setVisible(activo)
        if activo:
            self._on_destino_reemplazo(self.reemplazo_destino.get())
            self.agregar_btn.configure(text=tr('⟲ Reemplazar'), tipo='violeta')
            self.status.configure(text='', text_color=TEXT_MUTED)
        else:
            self.banner_texto.configure(text=tr('Arrastra el punto del pad: suena al soltar'), text_color=TEXT_MUTED)
            self.agregar_btn.configure(text=tr('Enviar a Resolve'), tipo='primario')
            self.status.configure(text=tr('Listo.'), text_color=TEXT_MUTED)
    def _efectos_neutros(self):
        return abs(self.tono_slider.get()) <= 0.1 and abs(self.velocidad_slider.get() - 1.0) <= 0.01 and (abs(self.volumen_slider.get() - 1.0) <= 0.01)
    def _ruta_para_enviar(self):
        """La ruta que viaja a Resolve: el ORIGINAL si no tocaste nada.

        v1.0.62: antes SIEMPRE se re-guardaba un wav «_editado» aunque
        tono/velocidad/volumen estuvieran neutros — el proyecto se iba
        llenando de copias identicas del sonido de la biblioteca.

        v3.3.0: el original de la biblioteca vive DENTRO del programa, y esa
        ruta muere al cerrarlo (.exe de un solo archivo, Mac desde
        Descargas): el clip quedaba desconectado en Resolve. Viaja la copia
        persistente (sfx_rules.ruta_persistente).
        """
        if self.sonido_seleccionado and self._efectos_neutros():
            import sfx_rules
            return Path(sfx_rules.ruta_persistente(self.sonido_seleccionado))
        return self._guardar_wav_procesado()
    def _enviar_reemplazo(self):
        """Sustituye el SFX bajo el cabezal de Resolve por el elegido.

        Deja la orden en ARCHIVO_REEMPLAZO y corre la accion
        'sfx_reemplazar' (gemelos CineCaptions_SfxReemplazar). El script SOLO toca
        clips nuestros (pistas SFX / SFX-Modificado / SFX-Marcadores y
        menos de 20 s): un clip del usuario bajo el cabezal se respeta y
        el error lo dice — la regla suprema es no destruir su trabajo.
        """
        if self.reemplazo_destino.get() != self.DESTINO_CABEZAL:
            self._reemplazar_en_marcadores()
            return
        destino = self._ruta_para_enviar()
        if not destino:
            return
        self._instalar_script_de_resolve()
        try:
            dejar_orden(ARCHIVO_REEMPLAZO, {
                'wav': str(destino),
                'creado_en': time.time(),
            })
        except Exception as e:
            self.status.configure(
                text=tr('No pude dejar la orden de reemplazo: {e}', e=e),
                text_color='#E0A030')
            return
        try:
            import resolve_bridge
            import ui_toast
            exito, err = resolve_bridge.ejecutar('sfx_reemplazar',
                                                 timeout=60)
        except Exception as e:
            exito, err = False, str(e)
        if exito:
            retirar_orden(ARCHIVO_REEMPLAZO)
            self.status.configure(
                text=tr('⟲ Reemplazado bajo el cabezal: {name}', name=destino.name),
                text_color='#8FC7FF')
            try:
                ui_toast.mostrar(
                    self,
                    tr("'{name}' sustituyó al efecto bajo el cabezal. Revisa Resolve.",
                       name=destino.name),
                    duracion_ms=3500)
            except Exception:
                pass
            return
        primera = (err or '').strip().splitlines()
        primera = primera[0][:180] if primera else tr('sin detalle')
        self.status.configure(
            text=tr('No pude reemplazar: {primera}', primera=primera),
            text_color='#E0A030')
        messagebox.showinfo(
            tr('Reemplazar SFX'),
            tr('No pude hacer el reemplazo automático.\n\nMotivo: {primera}\n\nRevisa que el cabezal esté SOBRE el efecto a sustituir (solo toco efectos puestos por el programa, en las pistas SFX). En la versión Free, relanza CineCaptions_Puente una vez (Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español)) para que aprenda esta función nueva.',
               primera=primera),
            parent=self)
    def _reemplazar_en_marcadores(self):
        """«⟲ Reemplazar» con un color de marcador como destino (v3.1.9).

        Corre la accion sfx_marcadores con orden_reemplazo_marcadores en un
        hilo (el patron de «Colocar ahora»): Resolve puede tardar con muchos
        marcadores y el Lab no se congela.
        """
        color_api, etiqueta = self._destinos_marcador().get(
            self.reemplazo_destino.get(), (None, ''))
        destino = self._ruta_para_enviar()
        if not destino or not color_api:
            return None
        self._instalar_script_de_resolve()
        try:
            dejar_orden(ARCHIVO_MARCADORES,
                        orden_reemplazo_marcadores(color_api, destino))
        except Exception as e:
            self.status.configure(
                text=tr('No pude dejar la orden de reemplazo: {e}', e=e),
                text_color='#E0A030')
            return
        self.status.configure(
            text=tr('Reemplazando en los marcadores {etiqueta}…', etiqueta=etiqueta),
            text_color='#C4B5FD')

        def trabajo():
            try:
                import resolve_bridge
                exito, err = resolve_bridge.ejecutar('sfx_marcadores',
                                                     timeout=180)
            except Exception as e:
                exito, err = False, f'{type(e).__name__}: {e}'
            if exito:
                retirar_orden(ARCHIVO_MARCADORES)

            def mostrar():
                if not ui.vivo(self):
                    return
                if exito:
                    self.status.configure(
                        text=tr('⟲ Marcadores {etiqueta}: ahora suenan con {name}. Revisa Resolve.',
                                etiqueta=etiqueta, name=destino.name),
                        text_color='#8FC7FF')
                    return
                primera = (err or '').strip().splitlines()
                self.status.configure(
                    text=tr('No pude reemplazar: {primera}',
                            primera=primera[0][:180] if primera
                            else tr('sin detalle')),
                    text_color='#E0A030')

            ejecutar_en_ui(mostrar)

        threading.Thread(target=trabajo, daemon=True).start()
    def _enviar_a_resolve(self):
        """Guarda el WAV, deja la orden y — si es Studio — inserta el
        clip solo, sin pedirle nada al usuario.

        En Studio: se conecta a Resolve via scripting externo y llama al
        script del proyecto pasandole el 'resolve' que devuelve la API.
        Todo automatico: guardar, insertar, listo.

        En Free (no hay scripting externo): guarda, instala el script en la
        carpeta de Scripts de Resolve si no estaba, deja la orden pendiente
        y muestra un mensaje corto explicando que corran el script del menu.

        Con el modo REEMPLAZAR activo (v1.0.62) este mismo boton (y el
        atajo) sustituye el efecto bajo el cabezal en vez de añadir.
        """
        if self.modo_reemplazo.get():
            self._enviar_reemplazo()
            return
        destino = self._ruta_para_enviar()
        if not destino:
            return
        ruta_script, recien_copiado, error_instalacion = \
            self._instalar_script_de_resolve()
        try:
            dejar_orden(ARCHIVO_PENDIENTE, {
                'wav': str(destino),
                'nombre_pista': 'SFX-Modificado',
                'creado_en': time.time(),
            })
        except Exception as e:
            self.status.configure(
                text=tr('Guardado, pero no pude dejar la orden para Resolve: {e}', e=e),
                text_color='#E0A030')
            return
        try:
            import resolve_bridge
            import ui_toast
            exito, err = resolve_bridge.ejecutar('sfx', timeout=60)
            if exito:
                retirar_orden(ARCHIVO_PENDIENTE)
                self.status.configure(
                    text=tr('✓ Insertado en Resolve: {name}', name=destino.name),
                    text_color='#8FC7FF')
                ui_toast.mostrar(
                    self,
                    tr("'{name}' insertado en tu timeline en el cabezal. Revisa Resolve.",
                       name=destino.name),
                    duracion_ms=3500)
                return
            self.status.configure(
                text=tr('No se pudo insertar solo: {v}', v=err.splitlines()[0][:140]),
                text_color='#E0A030')
        except Exception:
            pass
        self.status.configure(
            text=tr('WAV guardado. Corre CineCaptions_InsertarSFX en Scripts.'),
            text_color='#FFD166')
        mensaje = tr('Sonido guardado con éxito:\n{destino}',
                     destino=destino) + '\n\n'
        if error_instalacion:
            mensaje += tr('OJO: no pude copiar el script a Resolve.\nMotivo: {motivo}',
                          motivo=error_instalacion) + '\n\n'
        elif recien_copiado:
            mensaje += tr('Instalé el script de inserción en Resolve por primera vez.') + '\n\n'
        try:
            import instalador_scripts as _ins
            edicion = _ins.edicion_de_resolve()
        except Exception:
            edicion = 'desconocida'
        if edicion == 'studio':
            mensaje += tr('No pude insertarlo automáticamente esta vez. Revisa que Resolve esté abierto con un proyecto y una línea de tiempo, y vuelve a intentarlo.')
        else:
            mensaje += tr('Para que se inserte solo, corre una vez en Resolve:\n    Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente\n\n(En inglés: Workspace > Scripts.)\n\nO insértalo ahora a mano desde:\n    Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_InsertarSFX')
        messagebox.showinfo(tr('Agregar sonido a Resolve'), mensaje,
                            parent=self)
    # -- cierre y atajos ---------------------------------------------------------
    def _al_cerrar(self):
        """Lo llama la ventana principal al cerrarse."""
        self._parar_hotkey()
        try:
            self.reproductor.detener()
        except Exception:
            pass
    def _registrar_hotkey(self, shortcut_str):
        if sys.platform == 'darwin':
            return
        self._parar_hotkey()
        try:
            from pynput import keyboard

            def to_pynput_format(shortcut: str) -> str:
                parts = shortcut.lower().replace(' ', '').split('+')
                res = []
                for p in parts:
                    if p in ['ctrl', 'control']:
                        res.append('<ctrl>')
                    elif p == 'alt':
                        res.append('<alt>')
                    elif p == 'shift':
                        res.append('<shift>')
                    elif p in ['cmd', 'win', 'command', 'windows', 'super']:
                        res.append('<cmd>')
                    elif p == 'space':
                        res.append('<space>')
                    elif p == 'enter':
                        res.append('<enter>')
                    elif len(p) > 1 and p.startswith('f') and p[1:].isdigit():
                        res.append(f'<{p}>')
                    else:
                        res.append(p)
                return '+'.join(res)

            pynput_str = to_pynput_format(shortcut_str)

            def trigger():
                # pynput dispara en SU hilo: la interfaz solo se toca desde
                # el hilo de la interfaz
                ejecutar_en_ui(lambda: self._enviar_a_resolve() if ui.vivo(self) else None)

            self._listener_sfx = keyboard.GlobalHotKeys({
                pynput_str: trigger
            })
            self._listener_sfx.start()
            self._atajo_registrado = shortcut_str
            print(f'[Hotkey] Registrado atajo global: {shortcut_str} (como {pynput_str})')
        except BaseException as e:
            print(f'[Hotkey] Error registrando atajo global: {e}')
    def _registrar_atajo_local(self):
        """Atajo que funciona con la ventana al frente (Mac).

        No pasa por pynput: no hace falta ningun permiso del sistema y no hay
        hilos de por medio, que es lo que rompia la app en macOS con el
        atajo global. Se aceptan ⌘↩ y ⌘G (en Qt, Ctrl es ⌘ en Mac), en toda
        la ventana aunque el foco este en la lista o en un campo de texto.
        """
        for secuencia in ('Ctrl+Return', 'Ctrl+G'):
            try:
                a = QShortcut(QKeySequence(secuencia), self)
                a.setContext(Qt.ShortcutContext.WindowShortcut)
                a.activated.connect(self._enviar_a_resolve)
                self._atajos_mac.append(a)
            except Exception:
                pass
    def _abrir_accesibilidad_mac(self):
        """Abre la pantalla de Accesibilidad en Ajustes del Sistema de macOS."""
        if sys.platform == 'darwin':
            try:
                import subprocess
                subprocess.Popen(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])
            except Exception:
                return None
    def _parar_hotkey(self):
        if getattr(self, '_listener_sfx', None) is not None:
            try:
                self._listener_sfx.stop()
            except Exception:
                pass
            self._listener_sfx = None
            self._atajo_registrado = None
    def _actualizar_atajo_teclado(self):
        if self.hotkey_entry is None:
            return
        shortcut = self.hotkey_var.get().strip().lower()
        if not shortcut:
            shortcut = 'ctrl+alt+a'
            self.hotkey_var.set(shortcut)
        partes = shortcut.split('+')
        if len(partes) < 2:
            self.status.configure(text=tr('Atajo inválido. Usa modificadores, ej: ctrl+alt+a'), text_color='#E0A030')
            return
        if shortcut == self._atajo_registrado:
            return
        try:
            self.shortcut_path.parent.mkdir(parents=True, exist_ok=True)
            self.shortcut_path.write_text(json.dumps({'hotkey': shortcut}, ensure_ascii=False), encoding='utf-8')
            self._registrar_hotkey(shortcut)
            self.status.configure(text=tr('Atajo global registrado: {shortcut} (funciona minimizado)', shortcut=shortcut), text_color='#8FC7FF')
        except Exception as e:
            self.status.configure(text=tr('Error guardando atajo: {e}', e=e), text_color='#E0A030')
    def showEvent(self, e):
        super().showEvent(e)
        try:
            self._pintar_reglas()
        except Exception:
            pass
