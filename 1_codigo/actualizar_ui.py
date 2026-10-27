# CineCaptions · By Cinema Productions
# 1_codigo/actualizar_ui.py — la ventana «Actualizando CineCaptions» (v5.49, propuesta A + B elegida por el usuario; pulida: «más profesional,
# iconos y animaciones»): anillo con degradado y destello, versión vieja → nueva, datos de la descarga con iconos, los pasos como línea de
# tiempo con su icono, las novedades de la versión con el suyo y «Cancelar».
"""
PanelActualizacion(version_vieja, version_nueva, notas, al_cancelar)
    poner_descarga(hechos, total)   bytes descargados / total (calcula la velocidad de los últimos ~4 s y el tiempo que falta)
    poner_fase(k)                   0 descargar · 1 comprobar · 2 instalar · 3 todo hecho
    terminar(texto)                 el anillo se cierra con ✓ (con rebote) y el botón se apaga
Todo va pintado en un solo QWidget (sin efectos Qt sobre la página: reglas de rendimiento), con un reloj de 16 ms solo mientras se ve.
Animaciones: entrada escalonada de las secciones, destello que recorre el anillo, cifras que suben suaves, barrido de luz en el paso activo,
✓ que aparece con rebote, línea de los pasos que se llena de verde.
"""
import math
import re
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QConicalGradient, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QVBoxLayout, QWidget

import qt_kit as ui
from i18n import tr
from qt_kit import QColor, fuente

VERDE = QColor(ui.VERDE)
AGUA = QColor('#7AF0C2')
PASOS = (('Descargar la versión nueva', 'ph.cloud-arrow-down'), ('Comprobar que es auténtica', 'ph.shield-check'),
         ('Instalarla y volver a abrir', 'ph.rocket-launch'))
# icono y color de cada novedad según de qué hable (la primera regla que encaje)
TEMAS_NOVEDAD = ((r'sonido|m[uú]sica|audio', 'ph.music-notes', '#B388FF'), (r'n[uú]mero|moneda|cantidad|\$', 'ph.currency-dollar', '#F5B84B'),
                 (r'tema|caption|texto|l[ií]nea|palabra', 'ph.text-aa', '#4589FF'), (r'r[aá]pid|veloc', 'ph.lightning', '#00C8FF'),
                 (r'.', 'ph.sparkle', '#24D18F'))


def novedades(notas, maximo=3):
    """Las novedades en frases cortas: las notas del manifiesto vienen en un párrafo («Tema 2 renovado…: … . Página Sonido…»)."""
    frases = [f.strip(' .') for f in re.split(r'(?<=[.!?])\s+', str(notas or '').strip()) if f.strip(' .')]
    return frases[:maximo]


def _icono_de(frase):
    for patron, icono, color in TEMAS_NOVEDAD:
        if re.search(patron, frase, re.I):
            return icono, color
    return 'ph.sparkle', ui.VERDE


def _mb(n):
    return f'{n / 1048576:.0f}'


def _tiempo(s):
    if s is None:
        return '—'
    s = max(1, int(round(s)))
    return f'{s} s' if s < 60 else f'{s // 60} min {s % 60:02d} s'


def _suave(x):
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3


def _rebote(x):
    """0 → 1 con un poco de pasada (el ✓ y los iconos que aparecen)."""
    x = max(0.0, min(1.0, x))
    return 1.0 + 2.2 * (x - 1.0) ** 3 + 1.2 * (x - 1.0) ** 2 if x < 1.0 else 1.0


class _Lienzo(QWidget):
    """Todo lo que no es el botón: cabecera con anillo, datos, pasos y novedades."""
    SECCIONES = 4

    def __init__(self, panel):
        super().__init__(panel)
        self.p = panel
        self._f_titulo, self._f_dato, self._f_pct = fuente(19, True), fuente(15, True), fuente(18, peso='extra')
        self._f_texto, self._f_chico, self._f_paso, self._f_paso_a = fuente(13), fuente(11), fuente(13), fuente(13, True)
        self._f_cab, self._f_mini = fuente(11, True), fuente(9)
        self._pix = {}

    def _icono(self, nombre, color, lado):
        clave = (nombre, color, lado)
        if clave not in self._pix:
            ic = ui.icono_linea(nombre, color)
            # (Qt 6: QIcon.pixmap(lado) ya sale a la escala de la pantalla; pedirlo × dpr lo inflaba 1,5× a 150 %)
            self._pix[clave] = ic.pixmap(lado, lado) if ic is not None else None
        return self._pix[clave]

    def _poner_icono(self, p, nombre, color, cx, cy, lado):
        pm = self._icono(nombre, color, lado)
        if pm is not None and not pm.isNull():
            p.drawPixmap(QPointF(cx - lado / 2.0, cy - lado / 2.0), pm)

    def _entrada(self, p, i):
        """Entrada escalonada: cada sección aparece y sube 8 px un poco después de la anterior."""
        a = _suave((self.p._t - 0.06 * i) / 0.38)
        p.setOpacity(a)
        p.translate(0, 8.0 * (1.0 - a))

    # ------------------------------------------------------------------------------------------------ anillo
    def _anillo(self, p, cx, cy, r):
        P = self.p
        halo = QRadialGradient(cx, cy, r * 1.38)
        halo.setColorAt(0.0, QColor(36, 209, 143, 46 if not P._fin else 70))
        halo.setColorAt(1.0, QColor(36, 209, 143, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), r * 1.38, r * 1.38)
        caja = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor('#131D31'), 8.0))
        p.drawEllipse(QPointF(cx, cy), r, r)
        prog = 1.0 if P._fin else max(0.015, P._prog)
        barrido = 360.0 * prog
        grad = QConicalGradient(cx, cy, 90.0)
        grad.setColorAt(0.0, AGUA)
        grad.setColorAt(max(0.02, 1.0 - prog), QColor('#1FB6A6'))
        grad.setColorAt(1.0, AGUA)
        for ancho, alfa in ((16.0, 26), (12.0, 40)):                    # brillo alrededor del arco (barato: dos trazos anchos y tenues)
            p.setPen(QPen(QColor(36, 209, 143, alfa), ancho, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(caja, 90 * 16, -int(barrido * 16))
        p.setPen(QPen(grad, 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(caja, 90 * 16, -int(barrido * 16))
        if not P._fin:
            ang = math.radians(90.0 - barrido)                              # la punta del arco, con luz
            hx, hy = cx + math.cos(ang) * r, cy - math.sin(ang) * r
            luz = QRadialGradient(hx, hy, 10.0)
            luz.setColorAt(0.0, QColor(255, 255, 255, 230))
            luz.setColorAt(0.4, QColor(122, 240, 194, 120))
            luz.setColorAt(1.0, QColor(122, 240, 194, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(luz)
            p.drawEllipse(QPointF(hx, hy), 10.0, 10.0)
            a0 = (P._t * 140.0) % 360.0                                     # destello que recorre la pista
            dest = QConicalGradient(cx, cy, -a0)
            dest.setColorAt(0.0, QColor(255, 255, 255, 0))
            dest.setColorAt(0.06, QColor(255, 255, 255, 70))
            dest.setColorAt(0.12, QColor(255, 255, 255, 0))
            dest.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(dest, 8.0))
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setFont(self._f_pct)
            p.setPen(QColor(ui.TEXT_COLOR))
            p.drawText(QRectF(cx - r, cy - r - 6, 2 * r, 2 * r), int(Qt.AlignmentFlag.AlignCenter), f'{round(P._prog * 100)}%')
            p.setFont(self._f_mini)
            p.setPen(QColor(ui.TEXT_MUTED))
            p.drawText(QRectF(cx - r - 12, cy + 6, 2 * r + 24, 16), int(Qt.AlignmentFlag.AlignCenter),
                       (tr('descargando'), tr('comprobando'), tr('instalando'), '')[min(3, P._fase)])
        else:
            k = _rebote((P._t - (P._t_fin or 0.0)) / 0.45)
            p.save()
            p.translate(cx, cy)
            p.scale(k, k)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(36, 209, 143, 40))
            p.drawEllipse(QPointF(0, 0), r * 0.62, r * 0.62)
            v = QPainterPath()
            v.moveTo(-r * 0.3, 0.5)
            v.lineTo(-r * 0.07, r * 0.24)
            v.lineTo(r * 0.34, -r * 0.24)
            p.setPen(QPen(QColor('#FFFFFF'), 4.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(v)
            p.restore()

    # ------------------------------------------------------------------------------------------------ todo
    def paintEvent(self, _e):
        P = self.p
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w = self.width()
        suave, texto = QColor(ui.TEXT_MUTED), QColor(ui.TEXT_COLOR)
        # ── 0 · cabecera
        p.save()
        self._entrada(p, 0)
        self._anillo(p, 48.0, 48.0, 34.0)
        x0 = 106.0
        p.setFont(self._f_titulo)
        p.setPen(texto)
        p.drawText(QRectF(x0, 12, w - x0, 28), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   tr('Listo para instalar') if P._fin else tr('Actualizando CineCaptions'))
        x, yb = x0, 60.0
        if P._vieja:
            p.setFont(self._f_texto)
            p.setPen(suave)
            fm = QFontMetricsF(self._f_texto)
            ancho = fm.horizontalAdvance(P._vieja)
            p.drawText(QPointF(x, yb + 4), P._vieja)
            p.drawLine(QPointF(x, yb - 0.5), QPointF(x + ancho, yb - 0.5))
            self._poner_icono(p, 'ph.arrow-right', ui.TEXT_MUTED, x + ancho + 13, yb, 14)
            x += ancho + 26
        chip = f'v{P._nueva}'
        fm = QFontMetricsF(self._f_cab)
        rc = QRectF(x, yb - 11, fm.horizontalAdvance(chip) + 34, 22)
        g = QLinearGradient(rc.topLeft(), rc.topRight())
        g.setColorAt(0.0, QColor(36, 209, 143, 40))
        g.setColorAt(1.0, QColor(122, 240, 194, 18))
        p.setPen(QPen(QColor(36, 209, 143, 120), 1.0))
        p.setBrush(g)
        p.drawRoundedRect(rc, 11, 11)
        self._poner_icono(p, 'ph.sparkle-fill', ui.VERDE, rc.left() + 13, rc.center().y(), 12)
        p.setFont(self._f_cab)
        p.setPen(VERDE)
        p.drawText(rc.adjusted(22, 0, 0, 0), int(Qt.AlignmentFlag.AlignCenter), chip)
        p.restore()
        # ── 1 · datos con icono
        y = 100.0
        p.save()
        self._entrada(p, 1)
        datos = (('ph.download-simple', f'{_mb(P._ver_hechos)} / {_mb(P._total)} MB' if P._total else f'{_mb(P._ver_hechos)} MB', tr('descargado'), '#4589FF'),
                 ('ph.gauge', (f'{P._ver_vel / 1048576:.1f} MB/s'.replace('.', ',') if P._ver_vel > 1 else '—') if P._fase == 0 else '—', tr('velocidad'), '#00C8FF'),
                 ('ph.timer', tr('listo') if P._fase >= 1 else _tiempo(P._quedan), tr('quedan'), '#B388FF'))
        hueco = 8.0
        ancho = (w - 2 * hueco) / 3.0
        for i, (icono, valor, rotulo, color) in enumerate(datos):
            rc = QRectF(i * (ancho + hueco), y, ancho, 56)
            g = QLinearGradient(rc.topLeft(), rc.bottomLeft())
            g.setColorAt(0.0, QColor('#101B2F'))
            g.setColorAt(1.0, QColor(ui.CARD_COLOR))
            p.setPen(QPen(QColor(ui.BORDER_COLOR), 1.0))
            p.setBrush(g)
            p.drawRoundedRect(rc.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
            c = QColor(color)
            tile = QRectF(rc.left() + 10, rc.top() + 13, 30, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c.red(), c.green(), c.blue(), 34))
            p.drawRoundedRect(tile, 8, 8)
            self._poner_icono(p, icono, color, tile.center().x(), tile.center().y(), 17)
            p.setFont(self._f_dato)
            p.setPen(texto)
            fmd = QFontMetricsF(self._f_dato)
            p.drawText(QRectF(tile.right() + 9, rc.top() + 9, rc.right() - tile.right() - 14, 22),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       fmd.elidedText(valor, Qt.TextElideMode.ElideRight, rc.right() - tile.right() - 14))
            p.setFont(self._f_chico)
            p.setPen(suave)
            p.drawText(QRectF(tile.right() + 9, rc.top() + 30, rc.right() - tile.right() - 14, 16),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), rotulo)
        p.restore()
        # ── 2 · pasos (línea de tiempo)
        y += 70
        p.save()
        self._entrada(p, 2)
        paso_h = 38.0
        icx = 22.0
        for j in range(len(PASOS) - 1):                                     # la línea que une los iconos y se llena de verde
            ya, yb2 = y + j * paso_h + paso_h / 2 + 14, y + (j + 1) * paso_h + paso_h / 2 - 14
            p.setPen(QPen(QColor('#22304A'), 2.0))
            p.drawLine(QPointF(icx, ya), QPointF(icx, yb2))
            lleno = 1.0 if (j + 1 < P._fase or P._fin) else (P._llenado[j] if j < len(P._llenado) else 0.0)
            if lleno > 0:
                p.setPen(QPen(VERDE, 2.0))
                p.drawLine(QPointF(icx, ya), QPointF(icx, ya + (yb2 - ya) * lleno))
        for j, (nombre, icono) in enumerate(PASOS):
            rc = QRectF(0, y + j * paso_h, w, paso_h - 4)
            activo = j == P._fase and not P._fin
            hecho = j < P._fase or P._fin
            if activo:
                p.setPen(QPen(QColor('#1D3352'), 1.0))
                p.setBrush(QColor('#0F1B2E'))
                p.drawRoundedRect(rc.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
                fase = (P._t * 0.55) % 1.0                                   # barrido de luz que cruza el paso activo
                bx = rc.left() - 120 + (rc.width() + 240) * fase
                barr = QLinearGradient(bx - 90, 0, bx + 90, 0)
                barr.setColorAt(0.0, QColor(36, 209, 143, 0))
                barr.setColorAt(0.5, QColor(36, 209, 143, 30))
                barr.setColorAt(1.0, QColor(36, 209, 143, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(barr)
                p.drawRoundedRect(rc.adjusted(1, 1, -1, -1), 9, 9)
            icy = rc.center().y()
            if hecho:
                k = _rebote((P._t - P._t_hecho[j]) / 0.4) if P._t_hecho[j] is not None else 1.0
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(36, 209, 143, 40))
                p.drawEllipse(QPointF(icx, icy), 13.0 * k, 13.0 * k)
                p.setBrush(VERDE)
                p.drawEllipse(QPointF(icx, icy), 10.0 * k, 10.0 * k)
                v = QPainterPath()
                v.moveTo(icx - 4.3 * k, icy + 0.3)
                v.lineTo(icx - 1.2 * k, icy + 3.4 * k)
                v.lineTo(icx + 4.6 * k, icy - 3.3 * k)
                p.setPen(QPen(QColor('#05080E'), 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(v)
            else:
                p.setPen(QPen(QColor('#2A3650') if not activo else QColor(36, 209, 143, 90), 1.5))
                p.setBrush(QColor('#0D1627') if not activo else QColor(36, 209, 143, 26))
                p.drawEllipse(QPointF(icx, icy), 13.0, 13.0)
                if activo:
                    pulso = 1.0 + 0.06 * math.sin(P._t * 5.0)
                    p.setPen(QPen(VERDE, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawArc(QRectF(icx - 16 * pulso, icy - 16 * pulso, 32 * pulso, 32 * pulso), int(-(P._t * 280) % 360) * 16, 100 * 16)
                self._poner_icono(p, icono, ui.VERDE if activo else '#5C6B88', icx, icy, 15)
            p.setFont(self._f_paso_a if activo else self._f_paso)
            p.setPen(texto if activo else (suave if hecho else QColor('#C9D6EC')))
            p.drawText(rc.adjusted(48, 0, -96, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), tr(nombre))
            dur = P._duracion(j)
            if dur:
                p.setFont(self._f_chico)
                p.setPen(VERDE if activo else suave)
                p.drawText(rc.adjusted(0, 0, -12, 0), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), dur)
        p.restore()
        # ── 3 · novedades de la versión
        if P._novedades:
            y += 3 * paso_h + 8
            p.save()
            self._entrada(p, 3)
            fm = QFontMetricsF(self._f_texto)
            anch_txt = w - 70
            cajas = [fm.boundingRect(QRectF(0, 0, anch_txt, 1000), int(Qt.TextFlag.TextWordWrap), f).height() for f in P._novedades]
            alto = min(self.height() - y, 42 + sum(max(26.0, c) for c in cajas) + 10 * (len(cajas) - 1) + 14)
            rc = QRectF(0, y, w, alto)
            g = QLinearGradient(rc.topLeft(), rc.bottomRight())
            g.setColorAt(0.0, QColor('#0F1C31'))
            g.setColorAt(1.0, QColor(ui.CARD_COLOR))
            p.setPen(QPen(QColor(ui.BORDER_COLOR), 1.0))
            p.setBrush(g)
            p.drawRoundedRect(rc.adjusted(0.5, 0.5, -0.5, -0.5), 13, 13)
            self._poner_icono(p, 'ph.sparkle-fill', ui.VERDE, rc.left() + 24, rc.top() + 21, 14)
            p.setFont(self._f_cab)
            p.setPen(VERDE)
            p.drawText(QRectF(rc.left() + 38, rc.top() + 12, w, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       tr('QUÉ TRAE LA {v}', v=P._nueva))
            yy = rc.top() + 42
            for i, (frase, caja) in enumerate(zip(P._novedades, cajas)):
                if yy + caja > rc.bottom() - 6:
                    break
                a = _suave((P._t - 0.35 - 0.12 * i) / 0.4)                  # cada novedad entra un poco después
                p.save()
                p.setOpacity(p.opacity() * a)
                p.translate(10.0 * (1.0 - a), 0)
                icono, color = _icono_de(frase)
                c = QColor(color)
                tile = QRectF(rc.left() + 14, yy, 26, 26)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(c.red(), c.green(), c.blue(), 38))
                p.drawRoundedRect(tile, 7, 7)
                self._poner_icono(p, icono, color, tile.center().x(), tile.center().y(), 15)
                p.setFont(self._f_texto)
                p.setPen(QColor('#C9D6EC'))
                p.drawText(QRectF(tile.right() + 12, yy + max(0.0, (26 - caja) / 2), anch_txt, caja + 2),
                           int(Qt.TextFlag.TextWordWrap), frase)
                p.restore()
                yy += max(26.0, caja) + 10
            p.restore()
        p.end()


class BotonPildora(QAbstractButton):
    """Botón en forma de píldora pintado a mano: verde en reposo y rojo con halo al pasar el ratón o pulsar (vas a cancelar), icono + texto,
    encoge un poco al pulsar y se atenúa apagado. Se anima con el reloj del panel (avanzar(dt)), sin efectos Qt."""

    def __init__(self, texto, icono=None, comando=None, padre=None):
        super().__init__(padre)
        self.setText(str(texto))
        self._icono = icono
        self._f = fuente(13, True)
        self._hover = 0.0
        self._pulsado = 0.0
        self._pix = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        fm = QFontMetricsF(self._f)
        self.setFixedSize(int(fm.horizontalAdvance(self.text()) + (60 if icono else 40)), 40)
        if comando:
            self.clicked.connect(comando)

    def avanzar(self, dt):
        meta_h = 1.0 if (self.underMouse() and self.isEnabled()) else 0.0
        meta_p = 1.0 if self.isDown() else 0.0
        antes = (self._hover, self._pulsado)
        self._hover += (meta_h - self._hover) * min(1.0, dt * 12.0)
        self._pulsado += (meta_p - self._pulsado) * min(1.0, dt * 22.0)
        if abs(antes[0] - self._hover) > 0.002 or abs(antes[1] - self._pulsado) > 0.002:
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        h, k = self._hover, self._pulsado
        if not self.isEnabled():
            p.setOpacity(0.38)
        esc = 1.0 - 0.035 * k
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.scale(esc, esc)
        p.translate(-self.width() / 2.0, -self.height() / 2.0)
        r = QRectF(self.rect()).adjusted(3.5, 3.5, -3.5, -3.5)
        radio = r.height() / 2.0
        # v5.49 (pedido: «el botón en verde y rojo al cancelar»): VERDE en reposo y ROJO con el ratón encima / al pulsar (= vas a cancelar)
        rojo = max(h, k)
        def mezcla(a, b):
            return QColor(*(int(a[i] + (b[i] - a[i]) * rojo) for i in range(3)))
        halo = mezcla((36, 209, 143), (255, 92, 92))
        for i, alfa in enumerate((16, 26)):                          # halo suave alrededor (más fuerte en rojo)
            d = 3.0 - i * 1.5
            p.setPen(QPen(QColor(halo.red(), halo.green(), halo.blue(), int(alfa * (0.45 + 0.55 * rojo))), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-d, -d, d, d), radio + d, radio + d)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, mezcla((18, 64, 50), (92, 26, 32)))
        g.setColorAt(1.0, mezcla((11, 40, 33), (60, 16, 22)))
        borde = mezcla((36, 209, 143), (255, 107, 107))
        p.setPen(QPen(borde, 1.2))
        p.setBrush(g)
        p.drawRoundedRect(r, radio, radio)
        brillo = QLinearGradient(r.topLeft(), QPointF(r.left(), r.center().y()))   # luz arriba (aspecto de cristal)
        brillo.setColorAt(0.0, QColor(255, 255, 255, 22 + int(14 * h)))
        brillo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brillo)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -r.height() / 2.0), radio - 1, radio - 1)
        color_txt = mezcla((214, 255, 236), (255, 228, 228))
        fm = QFontMetricsF(self._f)
        ancho_txt = fm.horizontalAdvance(self.text())
        lado = 15
        total = ancho_txt + ((lado + 8) if self._icono else 0)
        x = r.center().x() - total / 2.0
        if self._icono:
            if self._pix is None:
                ic = ui.icono_linea(self._icono, '#E8F1FF')
                self._pix = ic.pixmap(lado, lado) if ic is not None else False
            if self._pix:
                p.setOpacity(p.opacity() * (0.75 + 0.25 * h))
                p.drawPixmap(QPointF(x, r.center().y() - lado / 2.0), self._pix)
                p.setOpacity(0.38 if not self.isEnabled() else 1.0)
            x += lado + 8
        p.setFont(self._f)
        p.setPen(color_txt)
        p.drawText(QRectF(x, r.top(), ancho_txt + 2, r.height()), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.text())
        p.end()


class BotonCerrar(QAbstractButton):
    """La ✕ de la esquina (v5.49, pedido: «quita la barra de título, deja metida la X»): un círculo que se enciende al pasar el ratón."""

    def __init__(self, comando=None, padre=None):
        super().__init__(padre)
        self._hover = 0.0
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        if comando:
            self.clicked.connect(comando)

    def avanzar(self, dt):
        meta = 1.0 if self.underMouse() else 0.0
        antes = self._hover
        self._hover += (meta - self._hover) * min(1.0, dt * 12.0)
        if abs(antes - self._hover) > 0.002:
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self._hover
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        p.setPen(QPen(QColor(int(255 * h + 255 * (1 - h)), int(107 * h + 255 * (1 - h)), int(107 * h + 255 * (1 - h)), int(18 + 70 * h)), 1.0))
        p.setBrush(QColor(int(255 * h + 255 * (1 - h)), int(92 * h + 255 * (1 - h)), int(92 * h + 255 * (1 - h)), int(8 + 30 * h)))
        p.drawEllipse(c, 14.0, 14.0)
        d = 4.6
        p.setPen(QPen(QColor(int(141 + 114 * h), int(155 - 45 * h), int(181 - 71 * h)), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        p.drawLine(QPointF(c.x() + d, c.y() - d), QPointF(c.x() - d, c.y() + d))
        p.end()


class PanelActualizacion(QWidget):
    """sin_marco=True: la ventana va SIN la barra de título de Windows; el panel pinta su fondo con esquinas redondeadas, lleva la ✕ dentro
    y se arrastra desde cualquier parte que no sea un botón."""

    def __init__(self, version_vieja, version_nueva, notas='', al_cancelar=None, padre=None, sin_marco=False):
        super().__init__(padre)
        self._sin_marco = sin_marco
        self._arrastre = None
        self._vieja, self._nueva = str(version_vieja or ''), str(version_nueva or '')
        self._novedades = novedades(notas)
        self._hechos = self._total = 0
        self._ver_hechos = 0.0                               # lo que se ENSEÑA: sube suave hacia el valor real
        self._vel = self._ver_vel = 0.0
        self._quedan = None
        self._muestras = []
        self._fase = 0
        self._inicio_fase = [time.perf_counter(), None, None, None]
        self._t_hecho = [None] * len(PASOS)
        self._llenado = [0.0] * (len(PASOS) - 1)
        self._fin = False
        self._t = 0.0
        self._t_fin = None
        self._prog = 0.0
        self._ult = time.perf_counter()
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 16)
        v.setSpacing(12)
        self.lienzo = _Lienzo(self)
        v.addWidget(self.lienzo, 1)
        pie = QHBoxLayout()
        pie.setSpacing(10)
        escudo = ui.Etiqueta('', 11)
        ic = ui.icono_linea('ph.shield-check', ui.TEXT_MUTED)
        if ic is not None:
            escudo.setPixmap(ic.pixmap(16, 16))
        pie.addWidget(escudo, 0, Qt.AlignmentFlag.AlignVCenter)
        nota = ui.Etiqueta(tr('Tu proyecto de Resolve no se toca. CineCaptions se cierra y se vuelve a abrir solo.'), 11, color=ui.TEXT_MUTED)
        nota.setWordWrap(True)
        pie.addWidget(nota, 1)
        self.boton = BotonPildora(tr('Cancelar'), 'ph.x', al_cancelar)
        pie.addWidget(self.boton, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(pie)
        self.cerrar = BotonCerrar(al_cancelar, self) if sin_marco else None
        self._reloj = ui.QTimer(self)
        self._reloj.setInterval(16)
        self._reloj.setTimerType(Qt.TimerType.PreciseTimer)
        self._reloj.timeout.connect(self._tic)
        self.setMinimumSize(480, 520)

    def resizeEvent(self, e):
        if self.cerrar is not None:
            self.cerrar.move(self.width() - self.cerrar.width() - 12, 12)
        super().resizeEvent(e)

    def paintEvent(self, _e):
        if not self._sin_marco:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, QColor('#0A1020'))
        g.setColorAt(1.0, QColor(ui.BG_COLOR))
        p.setPen(QPen(QColor('#24304A'), 1.0))
        p.setBrush(g)
        p.drawRoundedRect(r, 14, 14)
        p.end()

    def mousePressEvent(self, e):
        if self._sin_marco and e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._arrastre is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._arrastre)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._arrastre = None
        super().mouseReleaseEvent(e)

    def showEvent(self, e):
        self._ult = time.perf_counter()
        self._reloj.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj.stop()
        super().hideEvent(e)

    def poner_descarga(self, hechos, total):
        ahora = time.perf_counter()
        self._hechos, self._total = int(hechos or 0), int(total or 0)
        self._muestras.append((ahora, self._hechos))
        while len(self._muestras) > 2 and ahora - self._muestras[0][0] > 4.0:          # la velocidad de los últimos ~4 s
            self._muestras.pop(0)
        (t0, b0), (t1, b1) = self._muestras[0], self._muestras[-1]
        if t1 - t0 > 0.4 and b1 > b0:
            vel = (b1 - b0) / (t1 - t0)
            self._vel = vel if not self._vel else self._vel * 0.7 + vel * 0.3
            self._quedan = (self._total - self._hechos) / self._vel if self._total and self._vel else None

    def poner_fase(self, k):
        k = max(0, min(len(PASOS), int(k)))
        ahora = time.perf_counter()
        for j in range(self._fase, k):
            if self._t_hecho[j] is None:
                self._t_hecho[j] = self._t
        for j in range(self._fase + 1, k + 1):
            self._inicio_fase[j] = ahora
        self._fase = max(self._fase, k)

    def terminar(self, _texto=''):
        self.poner_fase(len(PASOS))
        self._fin = True
        self._t_fin = self._t
        self.boton.setEnabled(False)

    def _duracion(self, j):
        """El tiempo que tardó un paso hecho, o lo que falta del que está en marcha (la descarga)."""
        if j < self._fase and j < len(PASOS) - 1 and self._inicio_fase[j] and self._inicio_fase[j + 1]:
            return _tiempo(self._inicio_fase[j + 1] - self._inicio_fase[j])
        if j == self._fase == 0 and self._quedan is not None:
            return tr('quedan {t}', t=_tiempo(self._quedan))
        return ''

    def _meta(self):
        if self._fin:
            return 1.0
        descarga = (self._hechos / self._total) if self._total else 0.0
        return min(0.99, (0.9 * descarga) if self._fase == 0 else (0.92 if self._fase == 1 else 0.97))

    def _tic(self):
        ahora = time.perf_counter()
        dt = min(0.05, ahora - self._ult)
        self._ult = ahora
        self._t += dt
        k = min(1.0, dt * 5.0)
        self._prog += (self._meta() - self._prog) * k
        self._ver_hechos += (self._hechos - self._ver_hechos) * k
        self._ver_vel += (self._vel - self._ver_vel) * k
        for j in range(len(self._llenado)):                     # la línea entre pasos se llena cuando el de abajo empieza
            meta = 1.0 if (j + 1 <= self._fase or self._fin) else 0.0
            self._llenado[j] += (meta - self._llenado[j]) * min(1.0, dt * 6.0)
        self.lienzo.update()
        self.boton.avanzar(dt)
        if self.cerrar is not None:
            self.cerrar.avanzar(dt)
