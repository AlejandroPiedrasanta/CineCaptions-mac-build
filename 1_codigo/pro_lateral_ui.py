# CineCaptions · By Cinema Productions
# 1_codigo/pro_lateral_ui.py — Proyecto con la Edición PRO: a la DERECHA del slider, los motions que GO pondrá (interruptores) y, a la IZQUIERDA,
# un móvil con el ejemplo REAL del que se señala (v5.5.10).
"""
El usuario: «en la página de Proyecto, cuando se active el modo PRO, salgan a los laterales los motions que quiero que aplique (píldora abajo de
captions, B-roll, Magic Mask, Motions completo, intro con overlays…) y al lado izquierdo un ejemplo real de cómo se vería; conectado a la página de
Efectos para que no se contradigan».

    OPCIONES                 -> los interruptores, en el orden en que se enseñan
    ids_de(clave)            -> los motions del catálogo (motions_catalogo) que enciende/apaga ese interruptor
    estado(clave, op=None)   -> bool
    poner(clave, si)         -> guarda en las MISMAS preferencias que la página Efectos (pro_motions_modo / pro_motions, pro_internet,
                                pro_mascara, pro_motions_completo) con edicion_pro.guardar_opciones; Efectos las vuelve a leer al abrirse
    FilaPro(carrusel, …)     -> [ejemplo | slider | interruptores]; los lados solo con la PRO en juego (interruptor o Temas 5/6)

Cada interruptor de motions es un GRUPO del carrusel de Efectos: apagarlo en Automático pasa a «Solo los que elija» con todos menos ese grupo;
encenderlo los vuelve a marcar y, si quedan todos, vuelve a Automático. Nunca deja la lista vacía (motions_catalogo.modo la trataría como «todos»).
Los ejemplos: 2_recursos/edicion_pro/ejemplos_pro/<clave>.mp4 (+ .jpg), hechos con herramientas_dev/hacer_ejemplos_pro.py.
"""
import math
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

import qt_kit as ui
from i18n import tr

OPCIONES = [
    {'clave': 'pildora', 'nombre': 'Píldora bajo captions', 'icono': 'ph.chat-centered-text', 'motions': ['acompanante'],
     'detalle': 'Una píldora animada justo debajo del texto con el lugar, la cifra o el emoji de lo que dices.'},
    {'clave': 'broll', 'nombre': 'B-roll con fotos', 'icono': 'ph.image-square', 'motions': ['escena:foto'], 'pref': 'pro_internet',
     'detalle': 'Fotos de internet con licencia a pantalla completa cuando nombras algo.'},
    {'clave': 'detras', 'nombre': 'Captions detrás de ti', 'icono': 'ph.user-focus', 'mascara': True,
     'detalle': 'Se recorta a la persona (IA local o Magic Mask) y el texto pasa por detrás.'},
    {'clave': 'motions_completo', 'nombre': 'Motions completo', 'icono': 'ph.film-strip', 'pref': 'pro_motions_completo',
     'detalle': 'Un video de motions encima de todo: el titular palabra a palabra y una tarjeta por idea.'},
    {'clave': 'gancho', 'nombre': 'Gancho del inicio', 'icono': 'ph.lightning', 'motions': ['ograf:titular', 'ograf:orbita', 't5:orbita', 't5:sticker'],
     'detalle': 'Los primeros segundos: un titular detrás de ti e iconos que giran alrededor de tu cabeza.'},
    {'clave': 'escenas', 'nombre': 'Escenas completas', 'icono': 'ph.monitor-play',
     'detalle': 'Cuaderno, chat, polaroid, calendario… a pantalla completa cuando cuentas algo.'},
    {'clave': 'kit', 'nombre': 'Kit de motions', 'icono': 'ph.squares-four',
     'detalle': 'Listas, ruletas, títulos neón y cajas misterio sobre el video.'},
    {'clave': 'graficos', 'nombre': 'Gráficos', 'icono': 'ph.chart-line-up',
     'detalle': 'Cifras, mapas con bandera, marcos de cámara y llamadas a la acción.'},
    {'clave': 'plantillas', 'nombre': 'Plantillas por frase', 'icono': 'ph.quotes',
     'detalle': '«¡Hola amigos!», «Guárdalo», encuestas… justo cuando dices esa frase.'},
]
_POR_CLAVE = {o['clave']: o for o in OPCIONES}


def icono_de(o, relleno=True):
    """El icono de Phosphor de una opción: relleno (encendido / señalado) o de trazo (apagado). v5.5.10: iconos más claros (bocadillo, imagen,
    persona enfocada, película, rayo, pantalla con play, cuadrícula, gráfica que sube, comillas)."""
    return o['icono'] + ('-fill' if relleno else '-bold')
_IDS = {}


def carpeta_ejemplos() -> Path:
    try:
        import edicion_pro
        return Path(edicion_pro.carpeta_recursos()) / 'ejemplos_pro'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'ejemplos_pro'


def ejemplo(clave):
    """(mp4, jpg) del ejemplo real de un interruptor (pueden no existir)."""
    c = carpeta_ejemplos()
    return c / f'{clave}.mp4', c / f'{clave}.jpg'


# ----------------------------------------------------------------------------------------------------------------------- estado
def _catalogo_ids():
    try:
        import motions_catalogo as MC
        return [(m['id'], m['grupo']) for m in MC.catalogo()]
    except Exception:
        return []


def ids_de(clave):
    """Los motions del catálogo de ese interruptor: los nombrados y, del resto, por su grupo (Temas 5/6: escena y foco → escenas; lo demás → gráficos)."""
    if not _IDS:
        todos = _catalogo_ids()
        validos = {i for i, _g in todos}
        nombrados = {}
        for o in OPCIONES:
            for i in o.get('motions') or []:
                if i in validos:
                    nombrados[i] = o['clave']
        reparto = {k: [i for i, c in nombrados.items() if c == k] for k in _POR_CLAVE}
        destino = {'escena': 'escenas', 'kit': 'kit', 'grafico': 'graficos', 'plantilla': 'plantillas'}
        for i, g in todos:
            if i in nombrados:
                continue
            k = destino.get(g) or ('escenas' if i in ('t5:escena', 't5:foco') else 'graficos')
            reparto[k].append(i)
        if todos:                                 # (si el catálogo no cargó, no se guarda vacío: se reintenta la próxima vez)
            _IDS.update(reparto)
        return list(reparto.get(clave) or [])
    return list(_IDS.get(clave) or [])


def _op():
    try:
        import edicion_pro
        return edicion_pro.opciones_guardadas()
    except Exception:
        return {}


def estado(clave, op=None):
    o = _POR_CLAVE[clave]
    op = _op() if op is None else op
    if o.get('mascara'):
        return str(op.get('pro_mascara') or 'auto') != 'no'
    ids = ids_de(clave) if o.get('motions') is not None or 'pref' not in o else []
    try:
        import motions_catalogo as MC
        motion = any(MC.permitido(i, op) for i in ids) if ids else True
    except Exception:
        motion = True
    if o.get('pref'):
        return bool(op.get(o['pref'], o['pref'] == 'pro_internet')) and motion
    return motion


def poner(clave, si):
    """Guarda el interruptor. Devuelve False si no se pudo (apagar el último grupo de motions dejaría la lista vacía = «todos»)."""
    import edicion_pro
    import motions_catalogo as MC
    o = _POR_CLAVE[clave]
    op = edicion_pro.opciones_guardadas()
    cambios = {}
    if o.get('mascara'):
        antes = str(op.get('pro_mascara') or 'auto')
        cambios['pro_mascara'] = (antes if antes != 'no' else 'auto') if si else 'no'
    if o.get('pref'):
        cambios[o['pref']] = bool(si)
    ids = ids_de(clave) if (o.get('motions') is not None or 'pref' not in o) and not o.get('mascara') else []
    if ids:
        todos = [i for i, _g in _catalogo_ids()]
        lista = [i for i in (op.get('pro_motions') or []) if i in set(todos)] if MC.modo(op) == 'elegidos' else list(todos)
        if si:
            lista += [i for i in ids if i not in lista]
        else:
            fuera = set(ids)
            lista = [i for i in lista if i not in fuera]
            if not lista:
                return False
        if set(lista) >= set(todos):
            cambios.update(pro_motions_modo='auto', pro_motions=[])
        else:
            cambios.update(pro_motions_modo='elegidos', pro_motions=lista)
    edicion_pro.guardar_opciones(cambios)
    return True


def pro_en_juego():
    try:
        import edicion_pro
        return bool(edicion_pro.en_juego())
    except Exception:
        return False


# ----------------------------------------------------------------------------------------------------------------------- dibujo común
_PIX = {}


def _pix(nombre, color, tam, dpr):
    """El icono de línea ya rasterizado (cacheado): qt_kit.icono_linea crea el QIcon y dibuja el glifo en cada llamada, y estos paneles se
    repintan a 30–60 fps mientras animan."""
    clave = (nombre, color, int(tam), round(float(dpr), 2))
    pm = _PIX.get(clave)
    if pm is None:
        ic = ui.icono_linea(nombre, color)
        pm = ic.pixmap(QSize(int(tam), int(tam)), float(dpr)) if ic is not None else QPixmap()
        if len(_PIX) > 600:
            _PIX.clear()
        _PIX[clave] = pm
    return pm


def _icono(p, w, nombre, color, cx, cy, tam, opacidad=1.0, escala=1.0):
    pm = _pix(nombre, color, tam, w.devicePixelRatioF())
    if pm.isNull() or opacidad <= 0.01:
        return
    t = tam * escala
    p.save()
    p.setOpacity(p.opacity() * min(1.0, opacidad))
    p.drawPixmap(QRectF(cx - t / 2, cy - t / 2, t, t), pm, QRectF(pm.rect()))
    p.restore()


# ----------------------------------------------------------------------------------------------------------------------- iconos 3D a color
# v5.5.10 (el usuario eligió el juego «3D a color» entre 7): los iconos 3D que ya trae el programa (emojis 3D, iconos 3D de los gráficos y los
# Fluent 3D de las escenas). Apagado = en gris y translúcido.
ICONOS_3D = {
    'pildora': ('emojis', 'png', 'rcs_emoji_speech_balloon.png'),
    'broll': ('edicion_pro', 'ograf', 'lib', 'iconos3d', 'picture-dynamic-premium.png'),
    'detras': ('edicion_pro', 'fluent_extra', 'person_raising_hand.png'),         # (la silueta oscura no se veía sobre la barra negra)
    'motions_completo': ('emojis', 'png', 'rcs_emoji_clapper_board.png'),          # (la película gris parecía apagada)
    'gancho': ('emojis', 'png', 'rcs_emoji_fire.png'),
    'escenas': ('emojis', 'png', 'rcs_emoji_television.png'),
    'kit': ('edicion_pro', 'fluent_extra', 'puzzle_piece.png'),
    'graficos': ('emojis', 'png', 'rcs_emoji_chart_increasing.png'),
    'plantillas': ('emojis', 'png', 'rcs_emoji_memo.png'),
}


def _base_recursos():
    try:
        import instalador_scripts
        return Path(instalador_scripts.BASE_RECURSOS)
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos'


def _pix3d(clave, tam, dpr, apagado=False):
    k = ('3d', clave, int(tam), round(float(dpr), 2), bool(apagado))
    pm = _PIX.get(k)
    if pm is None:
        img = QImage(str(_base_recursos().joinpath(*ICONOS_3D.get(clave, ('', '')))))
        if img.isNull():
            pm = QPixmap()
        else:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            if apagado:
                alfa = img.convertToFormat(QImage.Format.Format_Alpha8)
                img = img.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(QImage.Format.Format_ARGB32)
                img.setAlphaChannel(alfa)
            lado = max(1, int(round(tam * dpr)))
            img = img.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(float(dpr))
        _PIX[k] = pm
    return pm


def _icono3d(p, w, clave, cx, cy, tam, opacidad=1.0, escala=1.0, apagado=False):
    pm = _pix3d(clave, tam, w.devicePixelRatioF(), apagado)
    if pm.isNull() or opacidad <= 0.01:
        return
    t = tam * escala
    p.save()
    p.setOpacity(p.opacity() * min(1.0, opacidad))
    p.drawPixmap(QRectF(cx - t / 2, cy - t / 2, t, t), pm, QRectF(pm.rect()))
    p.restore()


def _icono_motion(p, w, clave, cx, cy, tam, on, escala=1.0):
    """El icono 3D de un motion con su estado: a color (encendido) ↔ gris translúcido (apagado), con fundido entre los dos."""
    on = max(0.0, min(1.0, on))
    if on < 0.99:
        _icono3d(p, w, clave, cx, cy, tam, (1.0 - on) * 0.5, escala, apagado=True)
    if on > 0.01:
        _icono3d(p, w, clave, cx, cy, tam, on, escala)


def _cuello(p, x_izq, x_der, y, alto_izq, alto_der, pellizco):
    """Un «cuello» líquido horizontal entre dos cuerpos (como dos gotas que se unen): lados curvos que se pellizcan hacia el centro."""
    if x_der - x_izq < 1 or min(alto_izq, alto_der) < 1:
        return
    mid = (x_izq + x_der) / 2
    medio = min(alto_izq, alto_der) * (1.0 - pellizco) / 2
    c = QPainterPath()
    c.moveTo(x_izq, y - alto_izq / 2)
    c.quadTo(mid, y - medio, x_der, y - alto_der / 2)
    c.lineTo(x_der, y + alto_der / 2)
    c.quadTo(mid, y + medio, x_izq, y + alto_izq / 2)
    c.closeSubpath()
    p.drawPath(c)


# ----------------------------------------------------------------------------------------------------------------------- interruptores (derecha)
class PanelMotionsPro(QWidget):
    """La barra cápsula (propuesta «B» que eligió el usuario): una cápsula negra con SOLO los iconos de los motions (3D a color = GO lo pondrá,
    en gris translúcido = apagado); abajo, el botón a Efectos. Clic en un icono = encender / apagar.
    v5.5.10 animación «Gota» (elegida entre 4 y mejorada): la burbuja blanca es una gota LÍQUIDA: la cabeza va delante y una cola la sigue más
    despacio, unidas por un cuello que se adelgaza al estirarse; los iconos por los que pasa se hinchan un poco; al pulsar se aplasta y rebota;
    el clic deja una onda. El nombre del señalado NO se ve en reposo: al entrar con el ratón (o tras un clic, unos segundos) sale de DENTRO de la
    burbuja como una gota que se separa (con un cuello que se estira y se corta) y se recoge igual al salir. Todo con Resorte + motor_resortes."""
    senalada = Signal(str)
    cambiado = Signal()
    BARRA = 66            # ancho de la cápsula (a escala 1)
    PASO_MAX = 52         # alto de cada icono
    ARRIBA = 18           # margen de arriba de la cápsula
    ABAJO = 70            # sitio del botón de abajo (a Efectos)
    ETIQUETA = 230        # sitio de la píldora con el nombre, a la izquierda de la cápsula
    INFO_TRAS_CLIC_MS = 2200

    def __init__(self, ir_efectos=None, padre=None):
        super().__init__(padre)
        self._s = 1.0
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self._ir_efectos = ir_efectos
        self._on = {o['clave']: True for o in OPCIONES}
        self._k = {o['clave']: ui.Resorte(1.0, 420.0, 17.0) for o in OPCIONES}      # 0 apagado → 1 encendido (rebota un poco al llegar)
        self._hov = {o['clave']: ui.Resorte(0.0, 520.0, 30.0) for o in OPCIONES}
        self._hov['efectos'] = ui.Resorte(0.0, 520.0, 30.0)
        self.activa = OPCIONES[0]['clave']
        self._res = ui.Resorte(0.0, 300.0, 22.0)        # la CABEZA de la gota (índice float): rápida, se pasa un poco y vuelve
        self._cola = ui.Resorte(0.0, 95.0, 19.0)        # la COLA: va detrás, más lenta (de ahí el estiramiento líquido)
        self._pop = ui.Resorte(1.0, 560.0, 15.0)        # el salto del icono señalado
        self._apriete = ui.Resorte(1.0, 700.0, 16.0)    # se aplasta al pulsar y rebota al soltar
        self._onda = ui.Resorte(1.0, 60.0, 16.0)        # 0 → 1: la onda del clic
        self._onda_en = None
        self._info = ui.Resorte(0.0, 210.0, 24.0)       # 0 → 1: la píldora del nombre sale de la burbuja
        self._et_w = ui.Resorte(0.0, 340.0, 30.0)       # ancho de la píldora del nombre
        self._et_f = ui.Resorte(1.0, 260.0, 26.0)       # 0 → 1: fundido del texto viejo al nuevo
        self._et_txt = None
        self._et_prev = None
        self._entrada = ui.Resorte(1.0, 150.0, 21.0)
        self._encima = None
        self._dentro = False
        self._recoger = QTimer(self)                     # la píldora se recoge un poco después de salir (o del clic)
        self._recoger.setSingleShot(True)
        self._recoger.timeout.connect(lambda: self._mostrar_info(False))
        self.poner_escala(1.0)
        self.refrescar(animar=False)

    def poner_escala(self, s):
        """v5.5.10 («que se vea coherente en tamaños»): la barra crece y se achica con el slider (FilaPro le da la escala por el alto)."""
        s = max(0.75, min(1.6, float(s)))
        cambio = abs(s - self._s) > 0.004 or not self.minimumWidth()
        self._s = s
        if cambio:
            self.setFixedWidth(int(round(self.BARRA * s + 14 + self.ETIQUETA * min(s, 1.25))))
            if self._et_txt is not None:
                self._et_w.poner(self._ancho_etiqueta(*self._et_txt[:2]))
            self.update()

    def entrar(self):
        """La barra entra deslizándose desde la derecha (al activar la PRO)."""
        self._entrada.poner(0.0)
        self._entrada.objetivo = 1.0
        ui.motor_resortes.pedir(self)

    def _mostrar_info(self, si):
        self._info.objetivo = 1.0 if si else 0.0
        ui.motor_resortes.pedir(self)

    # -- estado
    def encendido(self, clave):
        return bool(self._on.get(clave))

    def refrescar(self, animar=True):
        op = _op()
        for o in OPCIONES:
            k = o['clave']
            self._on[k] = estado(k, op)
            self._k[k].objetivo = 1.0 if self._on[k] else 0.0
            if not animar:
                self._k[k].poner(self._k[k].objetivo)
        self.senalar(self.activa, animar=animar)
        if animar:
            ui.motor_resortes.pedir(self)
        self.update()

    def _fuentes(self):
        se = min(self._s, 1.25)
        return ui.fuente(13 * se, peso='medio'), ui.fuente(10 * se), se

    def _ancho_etiqueta(self, nombre, sub):
        f1, f2, se = self._fuentes()
        return max(QFontMetricsF(f1).horizontalAdvance(nombre), QFontMetricsF(f2).horizontalAdvance(sub)) + 44 * se

    def _texto_etiqueta(self):
        o = _POR_CLAVE[self.activa]
        si = self.encendido(self.activa)
        return tr(o['nombre']), (tr('Encendido · clic para apagar') if si else tr('Apagado · clic para encender')), si

    def senalar(self, clave, animar=True):
        cambia = clave != self.activa
        self.activa = clave
        i = [o['clave'] for o in OPCIONES].index(clave)
        nuevo = self._texto_etiqueta()
        if nuevo != self._et_txt:
            self._et_prev, self._et_txt = self._et_txt, nuevo
            ancho = self._ancho_etiqueta(*nuevo[:2])
            if animar and self._et_prev is not None:
                self._et_f.poner(0.0)
                self._et_f.objetivo = 1.0
                self._et_w.objetivo = ancho
            else:
                self._et_f.poner(1.0)
                self._et_w.poner(ancho)
        if animar:
            self._res.objetivo = float(i)
            self._cola.objetivo = float(i)
            if cambia:
                self._pop.poner(0.72)                    # el icono nuevo salta (el resorte pasa de 1 y vuelve)
                self._pop.objetivo = 1.0
            ui.motor_resortes.pedir(self)
        else:
            self._res.poner(float(i))
            self._cola.poner(float(i))
        self.update()
        self.senalada.emit(clave)

    def paso_resorte(self, dt):
        sigue = False
        for r in [self._res, self._cola, self._pop, self._apriete, self._onda, self._info, self._et_w, self._et_f, self._entrada] \
                + list(self._k.values()) + list(self._hov.values()):
            sigue = r.paso(dt) or sigue
        self.update()
        return sigue

    def _tocar(self, clave):
        si = not self.encendido(clave)
        ok = False
        try:
            ok = poner(clave, si)
        except Exception:
            import registro
            registro.excepcion(origen='Proyecto · motions de la PRO')
        if not ok and not si:
            import registro
            registro.aviso(tr('La Edición PRO necesita al menos un tipo de motion. Para no poner ninguno, apaga la Edición PRO.'), 'edición pro')
        self.refrescar()
        self.cambiado.emit()

    # -- geometría
    def _geo(self):
        """(cápsula, paso entre iconos, y del primer icono)."""
        n, s = len(OPCIONES), self._s
        arriba, abajo = self.ARRIBA * s, self.ABAJO * s
        paso = max(30.0 * s, min(self.PASO_MAX * s, (self.height() - arriba - abajo - 24) / n))
        alto = arriba + abajo + n * paso
        x = self.width() - self.BARRA * s - 4
        top = max(0.0, (self.height() - alto) / 2)
        return QRectF(x, top, self.BARRA * s, alto), paso, top + arriba

    def _icono_en(self, pos):
        barra, paso, y0 = self._geo()
        if not barra.adjusted(-6, 0, 6, 0).contains(pos):
            return None
        if pos.y() >= barra.bottom() - self.ABAJO * self._s + 8:
            return 'efectos'
        i = int((pos.y() - y0) // paso)
        return OPCIONES[i]['clave'] if 0 <= i < len(OPCIONES) else None

    # -- ratón
    def _poner_encima(self, k):
        if k == self._encima:
            return
        if self._encima in self._hov:
            self._hov[self._encima].objetivo = 0.0
        self._encima = k
        if k in self._hov:
            self._hov[k].objetivo = 1.0
        ui.motor_resortes.pedir(self)

    def mouseMoveEvent(self, e):
        k = self._icono_en(e.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if k else Qt.CursorShape.ArrowCursor)
        sobre_barra = k is not None and k != 'efectos'
        if sobre_barra and not self._dentro:             # entra en los iconos: el nombre sale de la burbuja
            self._dentro = True
            self._recoger.stop()
            self._mostrar_info(True)
        elif not sobre_barra and self._dentro:
            self._dentro = False
            self._recoger.start(350)
        if sobre_barra and k != self.activa:
            self.senalar(k)
        self._poner_encima(k)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._poner_encima(None)
        if self._dentro:
            self._dentro = False
            self._recoger.start(350)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            k = self._icono_en(e.position())
            if k and k != 'efectos':
                self._apriete.objetivo = 0.86             # la gota se aplasta mientras se pulsa
                ui.motor_resortes.pedir(self)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._apriete.objetivo = 1.0                 # y rebota al soltar
            k = self._icono_en(e.position())
            if k == 'efectos':
                if self._ir_efectos is not None:
                    self._ir_efectos()
            elif k:
                self.senalar(k)
                self._tocar(k)
                self._onda_en = k                        # la onda del clic
                self._onda.poner(0.0)
                self._onda.objetivo = 1.0
                self._mostrar_info(True)                 # tras un clic, el nombre (con su nuevo estado) se ve un rato
                if not self._dentro:
                    self._recoger.start(self.INFO_TRAS_CLIC_MS)
            ui.motor_resortes.pedir(self)
        super().mouseReleaseEvent(e)

    # -- dibujo
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        e = max(0.0, min(1.0, self._entrada.x))
        if e < 0.999:                                   # la entrada: desde la derecha y apareciendo
            p.setOpacity(e)
            p.translate((1.0 - e) * 36.0 * self._s, 0.0)
        s = self._s
        barra, paso, y0 = self._geo()
        cx = barra.center().x()
        t_ic = int(round(27 * s))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.setBrush(QColor('#05070C'))
        p.drawRoundedRect(barra, barra.width() / 2, barra.width() / 2)
        p.setPen(Qt.PenStyle.NoPen)
        cabeza = y0 + self._res.x * paso + paso / 2
        cola = y0 + self._cola.x * paso + paso / 2
        rapidez = min(1.0, abs(self._res.v) * 0.09)
        # el brillo suave detrás del icono que tiene el ratón encima
        for i, o in enumerate(OPCIONES):
            h = max(0.0, self._hov[o['clave']].x)
            if h > 0.02 and o['clave'] != self.activa:
                cy = y0 + i * paso + paso / 2
                r = 20 * s * (0.7 + 0.3 * h)
                p.setBrush(QColor(255, 255, 255, int(20 * h)))
                p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        # los iconos 3D (a color = encendido, gris = apagado); los que la gota va rozando se hinchan un poco (una ola)
        for i, o in enumerate(OPCIONES):
            k = o['clave']
            if k == self.activa and abs(cabeza - (y0 + i * paso + paso / 2)) < paso * 0.5:
                continue
            cy = y0 + i * paso + paso / 2
            d = (cy - cabeza) / paso
            ola = math.exp(-d * d * 3.0) * rapidez
            esc = (1.0 + 0.14 * max(0.0, self._hov[k].x)) * (1.0 + 0.2 * ola)
            _icono_motion(p, self, k, cx, cy, t_ic, self._k[k].x, esc)
            r = 3.0 * s * max(0.0, self._k[k].x)        # (el resorte pasa de 1 al llegar: el punto rebota)
            if r > 0.2:
                p.setBrush(QColor('#24D18F'))
                p.drawEllipse(QRectF(cx + 17 * s - r, cy - 12 * s - r, 2 * r, 2 * r))
        # la onda del clic: un anillo que se abre y se apaga
        o_ = max(0.0, min(1.0, self._onda.x))
        if self._onda_en in _POR_CLAVE and o_ < 0.995:
            i = [o['clave'] for o in OPCIONES].index(self._onda_en)
            cy = y0 + i * paso + paso / 2
            r = 22 * s * (1.0 + 1.1 * o_)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(127, 224, 181, int(170 * (1.0 - o_))), 2.0 * s))
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            p.setPen(Qt.PenStyle.NoPen)
        rb = min(22 * s, paso / 2 - 1) * max(0.8, self._apriete.x)
        # el nombre: sale de DENTRO de la burbuja como una gota que se separa y se recoge igual (se dibuja antes que la burbuja: sale de detrás)
        info = max(0.0, min(1.0, self._info.x))
        if info > 0.01:
            self._pintar_etiqueta(p, barra, cabeza, rb, info)
        # la gota: cabeza + cola unidas por un cuello que se adelgaza al estirarse
        p.setBrush(QColor('#FFFFFF'))
        dist = cola - cabeza
        rc = rb * (1.0 - min(0.45, abs(dist) / (paso * 2.4)))
        if abs(dist) > 1.0:
            arriba_y, abajo_y = (cabeza, cola) if dist > 0 else (cola, cabeza)
            r_arr, r_aba = (rb, rc) if dist > 0 else (rc, rb)
            pellizco = min(0.55, abs(dist) / (paso * 3.0))
            c = QPainterPath()
            mid = (arriba_y + abajo_y) / 2
            medio = min(r_arr, r_aba) * (1.0 - pellizco)
            c.moveTo(cx - r_arr, arriba_y)
            c.quadTo(cx - medio, mid, cx - r_aba, abajo_y)
            c.lineTo(cx + r_aba, abajo_y)
            c.quadTo(cx + medio, mid, cx + r_arr, arriba_y)
            c.closeSubpath()
            p.drawPath(c)
            p.drawEllipse(QRectF(cx - rc, cola - rc, 2 * rc, 2 * rc))
        ach = 1.0 + (1.0 - max(0.8, self._apriete.x)) * 0.9          # al pulsar: más ancha y más baja
        p.drawEllipse(QRectF(cx - rb * ach, cabeza - rb / ach, 2 * rb * ach, 2 * rb / ach))
        o = _POR_CLAVE[self.activa]
        _icono_motion(p, self, o['clave'], cx, cabeza, t_ic, self._k[o['clave']].x, max(0.6, self._pop.x) * max(0.8, self._apriete.x))
        # abajo: a la página Efectos (uno por uno)
        c = QRectF(cx - 20 * s, barra.bottom() - 54 * s, 40 * s, 40 * s)
        h = max(0.0, self._hov['efectos'].x)
        c = c.adjusted(-2 * s * h, -2 * s * h, 2 * s * h, 2 * s * h)
        blanco, menta = QColor('#FFFFFF'), QColor('#7FE0B5')
        p.setBrush(QColor(int(blanco.red() + (menta.red() - blanco.red()) * h), int(blanco.green() + (menta.green() - blanco.green()) * h),
                          int(blanco.blue() + (menta.blue() - blanco.blue()) * h)))
        p.drawEllipse(c)
        _icono(p, self, 'ph.sliders-horizontal-bold', '#05070C', cx, c.center().y(), int(round(20 * s)))

    def _pintar_etiqueta(self, p, barra, cabeza, rb, info):
        """La píldora del nombre saliendo de la burbuja: primero asoma y se separa (con un cuello líquido que se estira y se corta), luego crece
        hasta su ancho; el texto aparece cuando ya está fuera."""
        s = self._s
        f1, f2, se = self._fuentes()
        alto = 44 * se
        cx = barra.center().x()
        sale = 1.0 - (1.0 - min(1.0, info / 0.55)) ** 3                  # 0 → 1: de detrás de la burbuja a su sitio
        crece = max(0.0, min(1.0, (info - 0.3) / 0.7))
        crece = crece * crece * (3 - 2 * crece)
        derecha_final = barra.left() - 10 * s
        derecha = cx + (derecha_final - cx) * sale
        ancho = alto + (max(alto, self._et_w.x) - alto) * crece
        et = QRectF(max(2.0, derecha - ancho), cabeza - alto / 2, ancho, alto)
        p.save()
        p.setBrush(QColor('#FFFFFF'))
        # el cuello: une la píldora con la burbuja mientras sale y se corta al separarse
        corte = max(0.0, min(1.0, (info - 0.45) / 0.35))
        if corte < 0.999:
            alto_c = alto * 0.62 * (1.0 - corte)
            _cuello(p, et.right() - alto * 0.3, cx - rb * 0.4, cabeza, alto_c, min(2 * rb, alto_c * 1.25), 0.35 + 0.5 * corte)
        p.drawRoundedRect(et, alto / 2, alto / 2)
        if crece > 0.15:
            p.setClipRect(et.adjusted(4, 2, -4, -2))
            f = max(0.0, min(1.0, self._et_f.x))
            vis = min(1.0, (crece - 0.15) / 0.5)
            izq0 = et.left()
            for txt, op, dy in ((self._et_prev, 1.0 - f, -6.0 * f), (self._et_txt, f, 6.0 * (1.0 - f))):
                if txt is None or op <= 0.01:
                    continue
                nombre, sub, si = txt
                p.setOpacity(op * vis * (self._entrada.x if self._entrada.x < 0.999 else 1.0))
                p.setBrush(QColor('#24D18F') if si else QColor('#9AA7BF'))
                p.drawEllipse(QRectF(izq0 + 16 * se, et.center().y() - 4 * se + dy, 8 * se, 8 * se))
                izq = izq0 + 32 * se
                p.setFont(f1)
                p.setPen(QColor('#05070C'))
                p.drawText(QRectF(izq, et.top() + 4 * se + dy, 400, 20 * se), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, nombre)
                p.setFont(f2)
                p.setPen(QColor('#1E7A56' if si else '#6F7C96'))
                p.drawText(QRectF(izq, et.top() + 22 * se + dy, 400, 16 * se), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)
                p.setPen(Qt.PenStyle.NoPen)
        p.restore()


# ----------------------------------------------------------------------------------------------------------------------- ejemplo real (izquierda)
class PanelEjemploPro(QWidget):
    """Un móvil con el ejemplo real del interruptor señalado (en bucle, sin sonido) y, debajo, qué es y si GO lo pondrá. Sin tarjeta de fondo
    (el usuario: «solo el mockup de vista real y abajo la función que está activa»). v5.5.10 animaciones: al cambiar de motion el clip viejo se
    funde con el nuevo y el nombre de debajo entra deslizándose; apagar/encender atenúa la pantalla con suavidad; el panel entra desde la
    izquierda al activar la PRO. El marco del móvil se escala UNA vez por tamaño (antes, en cada fotograma: 30 por segundo)."""
    TIC_MS = 33

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setFixedWidth(330)                        # (FilaPro lo ajusta: el móvil tan alto como la tarjeta del centro del slider)
        self.setMinimumHeight(300)
        self._clave = None
        self._reprod = None
        self._poster = {}
        self._encendido = True
        self._anterior = None                          # el último cuadro del clip de antes (para el fundido) y su texto
        self._prev_txt = None
        self._fundido = ui.Resorte(1.0, 190.0, 24.0)
        self._apagado = ui.Resorte(0.0, 260.0, 26.0)
        self._entrada = ui.Resorte(1.0, 150.0, 21.0)
        self._marco = None                             # (ancho, alto, dpr, QPixmap)
        self.medida_carta = None                       # FilaPro: CarruselPacks._medidas (para alinear el móvil con la tarjeta del centro)
        self._reloj = QTimer(self)
        self._reloj.setInterval(self.TIC_MS)
        self._reloj.timeout.connect(self.update)

    def _carta(self):
        """(arriba, abajo) de la tarjeta del centro del slider, en las coordenadas de este panel (los dos van en la misma fila), o None."""
        if self.medida_carta is None:
            return None
        try:
            _w, h, _cx, cy = self.medida_carta()
            return cy - h / 2.0, cy + h / 2.0
        except Exception:
            return None

    def entrar(self):
        """El panel entra desde la izquierda (al activar la PRO)."""
        self._entrada.poner(0.0)
        self._entrada.objetivo = 1.0
        ui.motor_resortes.pedir(self)

    def paso_resorte(self, dt):
        sigue = False
        for r in (self._fundido, self._apagado, self._entrada):
            sigue = r.paso(dt) or sigue
        if not sigue:
            self._anterior = None
        self.update()
        return sigue

    def poner(self, clave, encendido):
        self._apagado.objetivo = 0.0 if encendido else 1.0
        if self._encendido != bool(encendido):
            ui.motor_resortes.pedir(self)
        if clave != self._clave:
            if self._clave is not None and self.isVisible():
                img = self._cuadro()
                self._anterior = img.copy() if img is not None and not img.isNull() else None
                self._prev_txt = (self._clave, self._encendido)
                self._fundido.poner(0.0)
                self._fundido.objetivo = 1.0
                ui.motor_resortes.pedir(self)
            self._clave = clave
            if self._reprod is not None:
                self._reprod.parar()
                self._reprod = None
            self._arrancar()
        if self._clave is not None and not self.isVisible():
            self._apagado.poner(self._apagado.objetivo)
        self._encendido = bool(encendido)
        self.update()

    def _arrancar(self):
        if not self.isVisible() or self._clave is None:
            return
        mp4, _jpg = ejemplo(self._clave)
        if mp4.exists():
            import vistas_slider
            self._reprod = vistas_slider.Reproductor(mp4, pausa_s=0.4)
            self._reprod.arrancar()
            if not self._reloj.isActive():
                self._reloj.start()

    def showEvent(self, e):
        super().showEvent(e)
        if self._reprod is None:
            self._arrancar()
        elif not self._reprod.activo:
            self._reprod.arrancar()
        if self._reprod is not None:
            self._reloj.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._reloj.stop()
        if self._reprod is not None:
            self._reprod.parar()

    def _cuadro(self):
        img = self._reprod.imagen() if self._reprod is not None else None
        if img is not None:
            return img
        if self._clave not in self._poster:
            _mp4, jpg = ejemplo(self._clave)
            self._poster[self._clave] = QImage(str(jpg)) if jpg.exists() else None
        return self._poster.get(self._clave)

    def _marco_pm(self, marco, caja):
        dpr = self.devicePixelRatioF()
        w, h = int(round(caja.width() * dpr)), int(round(caja.height() * dpr))
        if self._marco is None or self._marco[:3] != (w, h, round(dpr, 2)):
            pm = QPixmap.fromImage(marco.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
            pm.setDevicePixelRatio(dpr)
            self._marco = (w, h, round(dpr, 2), pm)
        return self._marco[3]

    @staticmethod
    def _cubrir(p, img, pant):
        esc = max(pant.width() / max(1, img.width()), pant.height() / max(1, img.height()))     # cubre la pantalla (sin franjas)
        dw, dh = img.width() * esc, img.height() * esc
        p.drawImage(QRectF(pant.center().x() - dw / 2, pant.center().y() - dh / 2, dw, dh), img)

    def paintEvent(self, _e):
        o = _POR_CLAVE.get(self._clave)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        e = max(0.0, min(1.0, self._entrada.x))
        if e < 0.999:                                              # la entrada: desde la izquierda y apareciendo
            p.setOpacity(e)
            p.translate(-(1.0 - e) * 36.0, 0.0)
        abajo = 58                                                 # la función activa, justo debajo del móvil (van juntos, centrados en el alto)
        disponible = QRectF(self.rect()).adjusted(10, 8, -10, -abajo - 8)
        # el MISMO móvil que Creativo (2_recursos/creativo/movil_marco.png, ~9:19,5 como uno de verdad) y su pantalla LLENA con el ejemplo, que ya
        # se hace a esa proporción (hacer_ejemplos_pro; el usuario: «que encaje bien el mockup, no franjas negras»)
        marco, info, _foto = ui.MarcoVista._recursos_movil()
        asp = float(info.get('aspecto') or 0.5)
        h = min(disponible.height(), disponible.width() / asp)
        w = h * asp
        top = disponible.top() + (disponible.height() - h) / 2
        carta = self._carta()
        if carta is not None:                                      # v5.5.10 («baja más el mockup»): a la altura de la tarjeta del centro
            top = max(disponible.top(), min(carta[1] - h, disponible.bottom() - h))
        caja = QRectF(disponible.center().x() - w / 2, top, w, h)
        a = info.get('pantalla') or [0.0625, 0.0272, 0.9363, 0.9728]
        pant = QRectF(caja.left() + a[0] * w, caja.top() + a[1] * h, (a[2] - a[0]) * w, (a[3] - a[1]) * h)
        radio = float(info.get('radio') or 0.127) * pant.width()
        pantalla = QPainterPath()
        pantalla.addRoundedRect(pant, radio, radio)
        p.save()
        p.setClipPath(pantalla)
        p.fillRect(pant, QColor('#05080F'))
        img = self._cuadro() if o is not None else None
        if img is not None and not img.isNull():
            self._cubrir(p, img, pant)
        elif o is not None:
            _icono3d(p, self, o['clave'], pant.center().x(), pant.center().y(), 56, 0.6, apagado=True)
        f = max(0.0, min(1.0, self._fundido.x))
        if self._anterior is not None and f < 0.999:              # el clip de antes se va fundiendo encima del nuevo
            p.save()
            p.setOpacity(p.opacity() * (1.0 - f))
            self._cubrir(p, self._anterior, pant)
            p.restore()
        apagado = max(0.0, min(1.0, self._apagado.x))
        if apagado > 0.01:                                         # apagado: se ve, pero atenuado y con «no se pondrá»
            p.fillRect(pant, QColor(8, 12, 22, int(150 * apagado)))
        p.restore()
        if marco is not None and not marco.isNull():
            p.drawPixmap(caja.topLeft(), self._marco_pm(marco, caja))
        # la etiqueta «Ejemplo real» arriba a la izquierda del video
        p.setFont(ui.fuente(10, peso='medio'))
        chip = QRectF(pant.left() + 12, pant.top() + pant.height() * 0.075, 86, 20)        # (debajo de la isla de la cámara)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        p.drawRoundedRect(chip, 10, 10)
        p.setPen(QColor('#7FE0B5'))
        p.drawText(chip, Qt.AlignmentFlag.AlignCenter, tr('Ejemplo real'))
        if o is None:
            return
        # debajo: el icono y el nombre de la función señalada y, más pequeño, si GO la pondrá (el de antes sube y se va, el nuevo entra)
        fuente_n, fuente_s = ui.fuente(14, peso='medio'), ui.fuente(11)
        y0 = caja.bottom() + 18
        textos = [(self._clave, self._encendido, f, 8.0 * (1.0 - f))]
        if self._prev_txt is not None and f < 0.999:
            textos.insert(0, (self._prev_txt[0], self._prev_txt[1], 1.0 - f, -8.0 * f))
        base = p.opacity()
        for clave, enc, op, dy in textos:
            oo = _POR_CLAVE.get(clave)
            if oo is None or op <= 0.01:
                continue
            p.setOpacity(base * op)
            nombre = tr(oo['nombre'])
            ancho = QFontMetricsF(fuente_n).horizontalAdvance(nombre) + 26
            x0 = caja.center().x() - ancho / 2
            _icono3d(p, self, clave, x0 + 9, y0 + dy + 10, 20, 1.0 if enc else 0.55, apagado=not enc)
            p.setFont(fuente_n)
            p.setPen(QColor('#FFFFFF' if enc else '#9AA7BF'))
            p.drawText(QRectF(x0 + 26, y0 + dy, ancho, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, nombre)
            p.setFont(fuente_s)
            p.setPen(QColor(ui.VERDE if enc else ui.TEXT_MUTED))
            p.drawText(QRectF(0, y0 + 22 + dy, self.width(), 18), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       tr('GO lo pondrá en tu video') if enc else tr('Apagado: GO no lo pondrá'))


# ----------------------------------------------------------------------------------------------------------------------- la fila de Proyecto
class FilaPro(QWidget):
    """[ejemplo | slider | interruptores]. Los lados se ven solo con la PRO en juego. v5.5.10 («que se vea coherente en tamaños»): crecen y
    se achican CON el slider: el móvil, tan alto como su tarjeta del centro; la barra, a la escala del alto de la fila. Con poco sitio se
    esconde primero el ejemplo y luego la barra."""
    cambiado = Signal()
    ESPACIO = 14
    TEXTO_MOVIL = 74          # lo que ocupa, debajo del móvil, el nombre de la función (y los márgenes del panel)
    MOVIL_MIN = 300           # más bajo que esto el móvil no se lee: se esconde
    CENTRO_MIN = 420          # sitio mínimo para el slider
    ANCHO_LISTA = 860

    def __init__(self, centro, ir_efectos=None, padre=None):
        super().__init__(padre)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(self.ESPACIO)
        self.ejemplo = PanelEjemploPro()
        self.ejemplo.medida_carta = getattr(centro, '_medidas', None)
        self.lista = PanelMotionsPro(ir_efectos=ir_efectos)
        capa.addWidget(self.ejemplo)
        capa.addWidget(centro, 1)
        capa.addWidget(self.lista)
        centro.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lista.senalada.connect(self._senalada)
        self.lista.cambiado.connect(self._cambio)
        self._pro = False
        self.refrescar()

    def _senalada(self, clave):
        self.ejemplo.poner(clave, self.lista.encendido(clave))

    def _cambio(self):
        self._senalada(self.lista.activa)
        self.cambiado.emit()

    def refrescar(self):
        """Vuelve a leer si la PRO está en juego y los interruptores (pueden haber cambiado en Inicio o en Efectos)."""
        antes = self._pro
        self._pro = pro_en_juego()
        if self._pro:
            self.lista.refrescar()
        self._lados()
        if self._pro and not antes and self.isVisible():          # la PRO se acaba de activar: los lados entran animados
            for lado in (self.ejemplo, self.lista):
                if lado.isVisible():
                    lado.entrar()

    def _lados(self):
        w, h = self.width(), self.height()
        self.lista.poner_escala(h / 620.0)
        ver_lista = self._pro and w >= self.ANCHO_LISTA
        lista = self.lista.width() + self.ESPACIO if ver_lista else 0
        # el móvil, del alto de la tarjeta del centro: la misma cuenta que CarruselPacks._medidas con el ancho que le quedaría al slider
        try:
            import estilos_slider as ES
            _marco, info, _foto = ui.MarcoVista._recursos_movil()
            asp = float(info.get('aspecto') or 0.5)
            paso, controles = ES.CarruselPacks.PASO, ES.CarruselPacks.ALTO_CONTROLES
        except Exception:
            ES, asp, paso, controles = None, 0.5, 0.94, 0
        alto_max = max(0.0, h - self.TEXTO_MOVIL)
        movil = alto_max
        for _ in range(4):                        # (el ancho del móvil quita sitio al slider, que achica su tarjeta: se busca el punto fijo)
            centro = w - lista - (movil * asp + 20 + self.ESPACIO)
            carta = max(0.0, centro - 32.0) / (0.88 + 2.0 * paso) / (ES.ASPECTO if ES else 0.5625)
            movil = max(0.0, min(alto_max, h - controles - 16.0, 1040.0, carta))
        ancho_ej = int(round(movil * asp + 20))
        ver_ej = self._pro and movil >= self.MOVIL_MIN and (w - lista - ancho_ej - self.ESPACIO) >= self.CENTRO_MIN
        if ver_ej and self.ejemplo.width() != ancho_ej:
            self.ejemplo.setFixedWidth(ancho_ej)
        self.lista.setVisible(ver_lista)
        self.ejemplo.setVisible(ver_ej)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._lados()

    def showEvent(self, e):
        super().showEvent(e)
        self.refrescar()
