# CineCaptions · By Cinema Productions
# 1_codigo/menu_estilo_ui.py — el panel del chip «Estilo» de Inicio: los estilos en una tira de pósters.
"""
El usuario («mejora esto, dame más propuestas» → eligió la C): en vez de la lista de píldoras «Estilo 1 … Estilo 6», una tira con el póster real
de cada estilo (2_recursos/vistas_slider/<pack>_captions.jpg, el de «Solo captions» del slider), su número arriba a la izquierda y el elegido con
anillo y ✓. Debajo, el nombre, la frase corta y qué hace (plantillas.TEMAS_INFO) del póster que se señala (o del elegido) y «Ver los estilos».

    abrir(padre, packs, actual, elegir, ver_estilos, ancla=None)  -> PanelEstilo (ya visible)
        packs = [{'nombre', 'etiqueta', 'sirve'}] en orden; elegir(nombre) al hacer clic; ver_estilos() en «Ver los estilos».
        ancla = el chip: el panel sale encima, centrado (debajo si no cabe); sin ancla, junto al cursor.

Teclado: ← → para señalar, Intro para elegir, Esc para cerrar. Sin tooltips (la información va en el propio panel). Un clic fuera lo cierra
(ventana Popup). Los pósters se escalan una vez por tamaño y pantalla (_CACHE). Todo se pinta a mano: sin efectos Qt.
"""
import re

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QCursor, QFontMetricsF, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

import qt_kit as ui
from i18n import tr

PAD = 14            # margen interior del panel
SOMBRA = 22         # margen del widget para pintar la sombra alrededor del panel
GAP = 10            # entre pósters
ANCHO_P, ALTO_P = 97, 172      # un póster (≈ 9:16)
ANCHO_MAX = 760     # con más de 6 packs (los del usuario) los pósters se estrechan hasta caber aquí
INFO_ARRIBA, INFO_ALTO, ABAJO = 14, 66, 12     # (el alto no cambia al señalar otro póster: 2 líneas de descripción como mucho)
SEPARA = 12         # entre el panel y el chip
_CACHE = {}         # (ruta, w, h, dpr) -> QPixmap ya recortado


def _poster(nombre):
    try:
        import vistas_slider
        return vistas_slider.ruta_poster_captions(nombre) or vistas_slider.ruta_poster(nombre)
    except Exception:
        return None


def _pix(ruta, w, h, dpr):
    """El póster recortado a w×h (cubriendo, centrado), a la resolución de la pantalla; None si no hay imagen."""
    if not ruta:
        return None
    clave = (str(ruta), int(w), int(h), round(float(dpr), 2))
    if clave not in _CACHE:
        img = QImage(str(ruta))
        pm = None
        if not img.isNull():
            W, H = max(1, int(round(w * dpr))), max(1, int(round(h * dpr)))
            esc = img.scaled(W, H, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            esc = esc.copy((esc.width() - W) // 2, (esc.height() - H) // 2, W, H)
            pm = QPixmap.fromImage(esc)
            pm.setDevicePixelRatio(dpr)
        _CACHE[clave] = pm
    return _CACHE[clave]


def pintar_fondo(p, r):
    """La sombra (capas cada vez más grandes y más tenues) y el panel redondeado de `r` (también lo usa menu_pro_ui)."""
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(10, 0, -1):
        s = i * 2.0
        p.setBrush(QColor(0, 0, 0, int(14 * (1.0 - i / 11.0) ** 1.6) + 2))
        p.drawRoundedRect(r.adjusted(-s * 0.7, -s * 0.3, s * 0.7, s * 0.9), 18 + s * 0.6, 18 + s * 0.6)
    p.setPen(QPen(QColor(ui.BORDER_COLOR), 1.0))
    p.setBrush(QColor(ui.CARD_COLOR))
    p.drawRoundedRect(r, 18, 18)


def colocar(w, ancla=None):
    """Mueve la ventana `w` (con SOMBRA px de margen alrededor de su panel) encima del chip `ancla`, centrada, SEPARA px por encima;
    debajo si no cabe; sin ancla, junto al cursor. Siempre dentro de la pantalla."""
    if ancla is not None:
        g = ancla.mapToGlobal(ancla.rect().topLeft())
        cx, arriba_chip, abajo_chip = g.x() + ancla.width() / 2.0, g.y(), g.y() + ancla.height()
    else:
        c = QCursor.pos()
        cx, arriba_chip, abajo_chip = c.x(), c.y(), c.y()
    pantalla = QGuiApplication.screenAt(QCursor.pos()) or w.screen() or QGuiApplication.primaryScreen()
    zona = pantalla.availableGeometry()
    x = int(round(cx - w.width() / 2.0))
    y = int(round(arriba_chip - SEPARA - (w.height() - SOMBRA)))
    if y + SOMBRA < zona.top():
        y = int(round(abajo_chip + SEPARA - SOMBRA))
    x = max(zona.left() - SOMBRA, min(zona.right() + SOMBRA - w.width(), x))
    y = max(zona.top() - SOMBRA, min(zona.bottom() + SOMBRA - w.height(), y))
    w.move(x, y)


def _numero(etiqueta, nombre=None):
    """El número del póster. v5.83: la etiqueta va traducida (plantillas.nombre_para_ui) y en coreano el número va DELANTE («4 스타일»):
    en los de fábrica se saca de su nombre en español («Estilo 4»); los del usuario, de su etiqueta como siempre."""
    try:
        import plantillas
        if nombre and plantillas.es_de_fabrica(nombre):
            etiqueta = plantillas.nombre_visible(nombre)
    except Exception:
        pass
    m = re.search(r'(\d+)\s*$', str(etiqueta or ''))
    return m.group(1) if m else None


def _lineas(texto, fm, ancho, maximo):
    """Parte `texto` en líneas de `ancho` px como mucho; la última, recortada con «…» si sobra."""
    palabras, lineas, actual = str(texto or '').split(), [], ''
    for p in palabras:
        prueba = (actual + ' ' + p).strip()
        if fm.horizontalAdvance(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    if len(lineas) > maximo:
        lineas = lineas[:maximo]
        lineas[-1] = fm.elidedText(lineas[-1] + ' …', Qt.TextElideMode.ElideRight, ancho)
    return lineas


class PanelEstilo(QWidget):
    def __init__(self, padre, packs, actual, elegir, ver_estilos):
        super().__init__(padre, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._packs = [dict(p) for p in packs or []]
        self._actual, self._elegir, self._ver = actual, elegir, ver_estilos
        self.al_cerrar = None
        self._hov = None                    # índice del póster señalado, o 'ver'
        self._k = 0.0                       # la entrada (0 → 1): sube 8 px y aparece
        n = max(1, len(self._packs))
        aw = (ANCHO_MAX - 2 * PAD - (n - 1) * GAP) / n
        self._pw = int(min(ANCHO_P, max(60, aw)))
        self._ph = int(round(self._pw * ALTO_P / ANCHO_P))
        ancho = 2 * PAD + n * self._pw + (n - 1) * GAP
        alto = PAD + self._ph + INFO_ARRIBA + INFO_ALTO + ABAJO
        self.setFixedSize(ancho + 2 * SOMBRA, alto + 2 * SOMBRA)
        self._f_num = ui.fuente(12, peso='negrita')
        self._f_nombre = ui.fuente(15, peso='negrita')
        self._f_frase = ui.fuente(15, peso='medio')
        self._f_desc = ui.fuente(12.5)
        self._f_ver = ui.fuente(13, peso='medio')
        self._f_aviso = ui.fuente(10.5, peso='medio')
        self._ico_ver = {}
        self._a = QVariantAnimation(self)
        self._a.setDuration(170)
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a.valueChanged.connect(self._paso)
        sel = self._indice(actual)
        self._teclado = sel if sel is not None else 0

    # -- geometría ---------------------------------------------------------------------------------------------------------------------------
    def _panel(self):
        return QRectF(SOMBRA + 0.5, SOMBRA + 0.5, self.width() - 2 * SOMBRA - 1.0, self.height() - 2 * SOMBRA - 1.0)

    def _carta(self, i):
        return QRectF(SOMBRA + PAD + i * (self._pw + GAP), SOMBRA + PAD, self._pw, self._ph)

    def _info(self):
        r = self._panel()
        return QRectF(r.left() + PAD + 4, SOMBRA + PAD + self._ph + INFO_ARRIBA, r.width() - 2 * PAD - 8, INFO_ALTO)

    def _rect_ver(self):
        txt = self._texto_ver()
        w = 16 + 7 + QFontMetricsF(self._f_ver).horizontalAdvance(txt) + 8
        info = self._info()
        return QRectF(info.right() - w, info.top() + 10, w, 30)

    def _texto_ver(self):
        return tr('Ver los estilos…').rstrip('…. ')

    def _indice(self, nombre):
        return next((i for i, p in enumerate(self._packs) if p.get('nombre') == nombre), None)

    def _en(self, pos):
        if self._rect_ver().adjusted(-6, -4, 6, 4).contains(pos):
            return 'ver'
        return next((i for i in range(len(self._packs)) if self._carta(i).contains(pos)), None)

    # -- mostrar -----------------------------------------------------------------------------------------------------------------------------
    def mostrar(self, ancla=None):
        colocar(self, ancla)
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self._a.start()

    def _paso(self, v):
        self._k = float(v)
        self.update()

    # -- eventos -----------------------------------------------------------------------------------------------------------------------------
    def mouseMoveEvent(self, e):
        h = self._en(e.position())
        if h != self._hov:
            self._hov = h
            if isinstance(h, int):
                self._teclado = h
            self.setCursor(Qt.CursorShape.PointingHandCursor if h is not None else Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hov is not None:
            self._hov = None
            self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            h = self._en(e.position())
            if h == 'ver':
                self._salir(self._ver)
                return
            if isinstance(h, int):
                self._salir(lambda n=self._packs[h].get('nombre'): self._elegir(n))
                return
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        k = e.key()
        n = len(self._packs)
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Right) and n:
            self._teclado = (self._teclado + (1 if k == Qt.Key.Key_Right else -1)) % n
            self._hov = self._teclado
            self.update()
            return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and n:
            self._salir(lambda n=self._packs[self._teclado].get('nombre'): self._elegir(n))
            return
        if k == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def _salir(self, fn):
        """Se cierra y DESPUÉS hace lo pedido (elegir un estilo repinta Inicio: con el panel ya fuera)."""
        self.close()
        if fn:
            QTimer.singleShot(0, fn)

    def hideEvent(self, e):
        if callable(self.al_cerrar):
            try:
                self.al_cerrar()
            except Exception:
                pass
            self.al_cerrar = None
        super().hideEvent(e)

    # -- pintar ------------------------------------------------------------------------------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setOpacity(self._k)
        p.translate(0, (1.0 - self._k) * 8.0)
        verde, verde_claro = QColor(ui.ACCENT), QColor(ui.ACCENT_CLARO)
        pintar_fondo(p, self._panel())
        dpr = self.devicePixelRatioF()
        sel = self._indice(self._actual)
        for i, pk in enumerate(self._packs):
            self._pintar_carta(p, i, pk, i == sel, self._hov == i, verde, verde_claro, dpr)
        self._pintar_info(p, sel, verde_claro)
        p.end()

    def _pintar_carta(self, p, i, pk, elegido, senalado, verde, verde_claro, dpr):
        rc = self._carta(i)
        camino = QPainterPath()
        camino.addRoundedRect(rc, 12, 12)
        p.save()
        p.setClipPath(camino)
        pm = _pix(_poster(pk.get('nombre')), rc.width(), rc.height(), dpr)
        if pm is not None and not pm.isNull():
            p.drawPixmap(rc.topLeft(), pm)
        else:                                                               # un pack del usuario sin póster: su nombre sobre azul noche
            p.fillRect(rc, QColor(ui.CARD_2))
            p.setPen(QColor(ui.TEXT_COLOR))
            p.setFont(self._f_nombre)
            p.drawText(rc.adjusted(8, 8, -8, -8), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), str(pk.get('etiqueta') or ''))
        if not elegido and not senalado:                                    # los demás, un poco apagados
            p.fillRect(rc, QColor(5, 9, 16, 70))
        if not pk.get('sirve', True):                                       # no sirve en el formato del video: «Solo vertical»
            p.fillRect(rc, QColor(5, 9, 16, 90))
            txt = tr('  (solo vertical)').strip().strip('()').strip()
            txt = txt[:1].upper() + txt[1:]
            fm = QFontMetricsF(self._f_aviso)
            w = fm.horizontalAdvance(txt) + 14
            ra = QRectF(rc.center().x() - w / 2.0, rc.bottom() - 28, w, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(8, 12, 20, 210))
            p.drawRoundedRect(ra, 10, 10)
            p.setPen(QColor(ui.TEXT_COLOR))
            p.setFont(self._f_aviso)
            p.drawText(ra, int(Qt.AlignmentFlag.AlignCenter), txt)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        if elegido:                                                         # anillo y halo del acento
            for ancho, alfa in ((8.0, 30), (5.0, 55), (2.0, 255)):
                c = QColor(verde_claro)
                c.setAlpha(alfa)
                p.setPen(QPen(c, ancho))
                p.drawRoundedRect(rc.adjusted(-1, -1, 1, 1), 13, 13)
        elif senalado:
            p.setPen(QPen(QColor(255, 255, 255, 150), 1.5))
            p.drawRoundedRect(rc.adjusted(-0.5, -0.5, 0.5, 0.5), 12.5, 12.5)
        else:
            p.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
            p.drawRoundedRect(rc.adjusted(0.5, 0.5, -0.5, -0.5), 11.5, 11.5)
        num = _numero(pk.get('etiqueta'), pk.get('nombre'))
        if num:                                                             # el número, arriba a la izquierda (el elegido, con ✓)
            fm = QFontMetricsF(self._f_num)
            w = max(22.0, fm.horizontalAdvance(num) + 14 + (14 if elegido else 0))
            rb = QRectF(rc.left() + 7, rc.top() + 7, w, 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(verde_claro if elegido else QColor(8, 12, 20, 200))
            p.drawRoundedRect(rb, 11, 11)
            oscuro = QColor('#05150E')
            x = rb.left() + (7 if elegido else 0)
            if elegido:
                cy = rb.center().y()
                p.setPen(QPen(oscuro, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawLine(QPointF(x, cy + 0.2), QPointF(x + 3.0, cy + 3.0))
                p.drawLine(QPointF(x + 3.0, cy + 3.0), QPointF(x + 8.5, cy - 3.0))
                x += 12
                p.setPen(oscuro)
                p.setFont(self._f_num)
                p.drawText(QRectF(x, rb.top(), rb.right() - x - 5, rb.height()), int(Qt.AlignmentFlag.AlignCenter), num)
            else:
                p.setPen(QColor('#FFFFFF'))
                p.setFont(self._f_num)
                p.drawText(rb, int(Qt.AlignmentFlag.AlignCenter), num)

    def _pintar_info(self, p, sel, verde_claro):
        i = self._hov if isinstance(self._hov, int) else sel
        info = self._info()
        rv = self._rect_ver()
        if i is not None and 0 <= i < len(self._packs):                     # nombre, frase corta y qué hace (del señalado o del elegido)
            pk = self._packs[i]
            nombre = str(pk.get('etiqueta') or pk.get('nombre') or '')
            try:
                import plantillas
                frase, desc = plantillas.info_de_tema(pk.get('nombre'))
            except Exception:
                frase, desc = '', ''
            frase, desc = (tr(frase) if frase else ''), (tr(desc) if desc else '')
            fm_n = QFontMetricsF(self._f_nombre)
            x, y = info.left(), info.top()
            p.setFont(self._f_nombre)
            p.setPen(QColor(ui.TEXT_COLOR))
            wn = fm_n.horizontalAdvance(nombre)
            p.drawText(QRectF(x, y, wn + 2, 22), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), nombre)
            if frase:
                p.setFont(self._f_frase)
                p.setPen(verde_claro)
                p.drawText(QRectF(x + wn + 8, y, rv.left() - (x + wn + 8) - 12, 22),
                           int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), frase)
            if desc:
                fm = QFontMetricsF(self._f_desc)
                p.setFont(self._f_desc)
                p.setPen(QColor(ui.TEXT_MUTED))
                lh = fm.height() + 3
                for k, linea in enumerate(_lineas(desc, fm, rv.left() - x - 20, 2)):
                    p.drawText(QRectF(x, y + 27 + k * lh, rv.left() - x - 16, lh), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), linea)
        c = QColor(verde_claro)                                             # «Ver los estilos»
        if self._hov == 'ver':
            fondo = QColor(verde_claro)
            fondo.setAlpha(28)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fondo)
            p.drawRoundedRect(rv.adjusted(-8, -1, 6, 1), 15, 15)
        clave = (c.name(), round(self.devicePixelRatioF(), 2))
        if clave not in self._ico_ver:
            ic = ui.icono_linea('ph.squares-four', c.name())
            self._ico_ver[clave] = ic.pixmap(QSize(16, 16), self.devicePixelRatioF()) if ic is not None else None
        pm = self._ico_ver[clave]
        if pm is not None and not pm.isNull():
            p.drawPixmap(QPointF(rv.left(), rv.center().y() - 8), pm)
        p.setFont(self._f_ver)
        p.setPen(c)
        p.drawText(QRectF(rv.left() + 23, rv.top(), rv.width() - 23, rv.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   self._texto_ver())


def abrir(padre, packs, actual, elegir, ver_estilos, ancla=None):
    """Abre el panel (encima del chip `ancla` si lo hay) y lo devuelve. El chip, si sabe, gira su flecha mientras está abierto."""
    panel = PanelEstilo(padre, packs, actual, elegir, ver_estilos)
    if ancla is not None and hasattr(ancla, 'poner_abierto'):
        ancla.poner_abierto(True)
        panel.al_cerrar = lambda: ancla.poner_abierto(False)
    ui.no_reabrir(panel, ancla)                  # v5.84: volver a pulsar el chip lo cierra (antes se cerraba y se abría otra vez)
    panel.mostrar(ancla)
    return panel
