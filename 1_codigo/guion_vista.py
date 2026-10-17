# CineCaptions · By Cinema Productions
# 1_codigo/guion_vista.py — «Así se verá este bloque» del estilo «guion»: dibuja el bloque con la MISMA geometría que coloca Resolve (cada palabra en su x, y y tamaño).
"""
guion_vista.py  (v5.10)
-----------------------
MarcoVistaGuion pinta un bloque del estilo «guion» (un `cue` del .json de place_guion_track) con los datos reales del plan:

  * la posición de cada palabra (x, y = su centro en fracción del cuadro 9:16) y su zoom,
  * el tamaño de letra de verdad (Size × 640 px a 1080 de ancho, el mismo que usa el planificador para medir),
  * el peso (fina / negrita) y la tipografía, el color y las mayúsculas de la variante del pack,
  * los acentos de Amro (pastilla, tachado, subrayado, fuego),
  * el emoji, encima o debajo de la pila, y la entrada palabra a palabra (cada una a su momento) en la vista animada.

Se enseña la franja del cuadro donde cae la pila a todo el ANCHO del cuadro (para que márgenes y proporciones sean los reales). Lo que no se puede
reproducir en Qt es el brillo de los macros de Luxe: eso lo enseña el «Render real · Resolve» (MarcoVista.poner_fondo con real=True).
"""
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen

import guion_captions as G
import qt_kit

ALTO_CUADRO, ANCHO_CUADRO = 1920.0, 1080.0
EMOJI_ALTO, EMOJI_MARGEN = 0.085, 0.065            # los mismos de colocar_emojis (CineCaptions.py), formato vertical
_FAMILIAS = {}


def fuente_qt(familia, estilo, px):
    """QFont con el archivo REAL de esa familia y estilo (el mismo que usa Resolve), tamaño en píxeles."""
    clave = (str(familia), str(estilo))
    fam = _FAMILIAS.get(clave)
    if fam is None:
        fam = ''
        try:
            import fuentes_sistema
            ruta = fuentes_sistema.ruta_de_fuente(familia, estilo)
            if ruta:
                fid = QFontDatabase.addApplicationFont(str(ruta))
                nombres = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
                fam = nombres[0] if nombres else ''
        except Exception:
            fam = ''
        _FAMILIAS[clave] = fam or str(familia)
        fam = _FAMILIAS[clave]
    f = QFont(fam)
    f.setPixelSize(max(6, int(round(px))))
    # Qt agrupa los archivos de una familia («Poppins»: Light, Bold, ExtraBold…): hay que pedirle el estilo, si no sale el normal
    pedido = str(estilo).replace(' ', '').lower()
    for nombre in QFontDatabase.styles(fam):
        if nombre.replace(' ', '').lower() == pedido:
            f.setStyleName(nombre)
            return f
    for clave, w in (('extrabold', QFont.Weight.ExtraBold), ('black', QFont.Weight.Black), ('semibold', QFont.Weight.DemiBold), ('bold', QFont.Weight.Bold),
                     ('medium', QFont.Weight.Medium), ('light', QFont.Weight.Light), ('thin', QFont.Weight.Thin)):
        if clave in pedido:
            f.setWeight(w)
            break
    f.setItalic('italic' in pedido)
    return f


def _color(h, por_defecto='#FFFFFF'):
    c = QColor(str(h or por_defecto))
    return c if c.isValid() else QColor(por_defecto)


class MarcoVistaGuion(qt_kit.MarcoVista):
    """El marco de «Así se verá este bloque» para el estilo «guion». Sin bloque (poner_cue(None)) se comporta como el MarcoVista de siempre."""

    def __init__(self, padre=None, alto_min=160, aprox=True, movil=False):
        super().__init__(padre, alto_min, aprox, movil)
        self._cue = None
        self._pack = 'Referencia'
        self._real_img = None

    def poner_cue(self, cue, pack='Referencia', imagen=None):
        """Un bloque nuevo: vuelve a la vista rápida (si había un render real de otro bloque, se quita)."""
        self._cue = cue
        self._pack = pack
        self._imagen = dict(imagen) if imagen else None
        self._real_img = None
        self.update()

    def poner_real(self, imagen):
        """El fotograma que renderizó Resolve de ESTE bloque (QImage 9:16): se enseña en vez del dibujo, con el mismo encuadre."""
        self._real_img = imagen if imagen is not None and not imagen.isNull() else None
        self.update()

    def hay_cue(self):
        return self._cue is not None

    # -- geometría ---------------------------------------------------------------------------------------------------
    def _caja(self):
        """(arriba, abajo) de la pila en fracción del alto del cuadro: la caja del planificador (donde Resolve ancla el emoji)."""
        c = self._cue or {}
        caja = c.get('caja')
        ys = [float(r['y']) for r in c.get('runs') or [] if isinstance(r.get('y'), (int, float))]
        if isinstance(caja, (list, tuple)) and len(caja) == 2:
            return float(caja[0]), float(caja[1])
        if ys:
            return min(ys) - 0.04, max(ys) + 0.04
        return 0.45, 0.65

    def _extension(self):
        """(arriba, abajo) de lo que realmente se pinta (la tinta de cada palabra con su tamaño), en fracción del alto: para encuadrar la vista sin cortar nada."""
        c = self._cue or {}
        arriba, abajo = [], []
        for r in c.get('runs') or []:
            if not isinstance(r.get('y'), (int, float)):
                continue
            if r.get('rol') == 'main':
                d = G.datos_variantes(self._pack).get(int(r.get('estilo') or c.get('estilo') or 1)) or {}
                px = float(d.get('tam') or 0.2) * G.K_PX * float(r.get('zoom') or 1.0)
            else:
                px = G.TAM_PEQUENA * G.K_PX * float(r.get('zoom') or 1.0)
            mitad = 0.70 * px / ALTO_CUADRO
            arriba.append(float(r['y']) - mitad)
            abajo.append(float(r['y']) + mitad)
        a, b = self._caja()
        return (min(arriba + [a]) if arriba else a), (max(abajo + [b]) if abajo else b)

    def _marco_cuadro(self, dentro):
        """(escala px/px-del-timeline, x0, y0 del cuadro) para que la franja de la pila quepa a todo el ancho del cuadro."""
        y0, y1 = self._extension()
        cy0, cy1 = self._caja()
        con_emoji = 1 if self._imagen else 0
        extra = EMOJI_ALTO + EMOJI_MARGEN + 0.01
        arriba_f = (min(y0, cy0 - (extra if (con_emoji and self._emoji_arriba()) else 0)) - 0.015) * ALTO_CUADRO
        abajo_f = (max(y1, cy1 + (extra if (con_emoji and not self._emoji_arriba()) else 0)) + 0.015) * ALTO_CUADRO
        s = min((dentro.width() - 6) / ANCHO_CUADRO, (dentro.height() - 6) / max(1.0, abajo_f - arriba_f))
        centro_f = (arriba_f + abajo_f) / 2.0
        return s, dentro.center().x() - ANCHO_CUADRO * s / 2.0, dentro.center().y() - centro_f * s

    def _emoji_arriba(self):
        return bool(self._imagen and self._imagen.get('donde') == 'arriba')

    # -- v5.5.10: dentro del móvil, el cuadro 9:16 entero a lo ancho de la pantalla (las palabras en su sitio REAL del video) ----------
    def _imagen_en_pantalla(self):
        if self._real_img is not None:
            return self._real_img, True
        return super()._imagen_en_pantalla()

    def _pintar_en_pantalla(self, p, pant):
        if self._cue is None:
            return super()._pintar_en_pantalla(p, pant)
        s = pant.width() / ANCHO_CUADRO
        self._pintar_corridas(p, s, pant.left(), pant.center().y() - ALTO_CUADRO * s / 2.0)

    def _pintar_corridas(self, p, s, x0, y0):
        """Cada palabra del bloque (con su entrada si se está animando) y el emoji, en el cuadro de escala s con origen (x0, y0)."""
        c = self._cue
        t = self._t_anim
        t_ini = float(c.get('start') or 0.0)
        corridas = sorted(c.get('runs') or [], key=lambda r: float(r.get('t') or t_ini))
        salida = max(0.0, min(1.0, float(self._salida or 0.0)))
        for run in corridas:
            texto = str(run.get('texto') or '')
            if not texto:
                continue
            entra = float(run.get('t') or t_ini) - t_ini
            alfa, escala_extra, sube = 1.0, 1.0, 0.0
            if t is not None:
                if t < entra:
                    continue
                k = max(0.0, min(1.0, (t - entra) / 0.24))
                alfa = k
                escala_extra = 0.88 + 0.12 * self._rebote(k)
                sube = (1.0 - k) * 14.0 * s
            alfa *= (1.0 - salida)
            if alfa <= 0.01:
                continue
            self._dibujar_palabra(p, run, c, s, x0, y0, alfa, escala_extra, sube)
        self._dibujar_emoji(p, s, x0, y0, t, c)

    # -- dibujo ------------------------------------------------------------------------------------------------------
    def paintEvent(self, e):
        if self._movil or self._cue is None or (getattr(self, '_real', False) and self._fondo is not None):
            return super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(qt_kit.BORDER_COLOR), 1))
        p.setBrush(QColor('#0B1220'))
        p.drawRoundedRect(r, 12, 12)
        dentro = r.adjusted(8, 8, -8, -8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#05080F'))
        p.drawRoundedRect(dentro, 8, 8)
        p.save()
        camino = QPainterPath()
        camino.addRoundedRect(dentro, 8, 8)
        p.setClipPath(camino)
        s, x0, y0 = self._marco_cuadro(dentro)
        if self._real_img is not None:
            # el render REAL de Resolve de este bloque, con el mismo encuadre que el dibujo
            p.drawImage(QRectF(x0, y0, ANCHO_CUADRO * s, ALTO_CUADRO * s), self._real_img)
            p.restore()
            p.setFont(qt_kit.fuente(10, peso='negrita'))
            p.setPen(QColor(qt_kit.ACCENT_CLARO))
            p.drawText(dentro.adjusted(0, 0, -10, -6), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), qt_kit.tr('Render real · Resolve'))
            p.end()
            return
        # el cuadro (9:16): sus bordes laterales se ven finos para que se aprecien los márgenes reales
        p.setPen(QPen(QColor(255, 255, 255, 38), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(x0, dentro.top()), QPointF(x0, dentro.bottom()))
        p.drawLine(QPointF(x0 + ANCHO_CUADRO * s, dentro.top()), QPointF(x0 + ANCHO_CUADRO * s, dentro.bottom()))
        self._pintar_corridas(p, s, x0, y0)
        p.restore()
        if self._aprox:
            p.setFont(qt_kit.fuente(10))
            p.setPen(QColor(qt_kit.TEXT_MUTED))
            p.drawText(dentro.adjusted(0, 0, -10, -6), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), qt_kit.tr('aprox.'))
        p.end()

    def _dibujar_palabra(self, p, run, cue, s, x0, y0, alfa, escala_extra, sube):
        rol = run.get('rol')
        zoom = float(run.get('zoom') or 1.0) * escala_extra
        cx = x0 + float(run.get('x', 0.5)) * ANCHO_CUADRO * s
        cy = y0 + float(run.get('y', 0.5)) * ALTO_CUADRO * s - sube
        texto = str(run.get('texto') or '')
        if rol == 'main':
            n = int(run.get('estilo') or cue.get('estilo') or 1)
            d = G.datos_variantes(self._pack).get(n) or {}
            familia, estilo = d.get('fuente') or ('Poppins', 'Bold')
            px = float(d.get('tam') or 0.2) * G.K_PX * zoom * s
            color = _color(d.get('color'))
            f = fuente_qt(familia, estilo, px)
            amro = bool(d.get('amro'))
        else:
            familia, estilo = G.FINA if rol == 'context' else G.NEGRITA
            px = G.TAM_PEQUENA * G.K_PX * zoom * s
            color = QColor('#FFFFFF')
            f = fuente_qt(familia, estilo, px)
            amro, n = False, 0
        fm = QFontMetricsF(f)
        ancho = fm.horizontalAdvance(texto)
        base_x = cx - ancho / 2.0
        base_y = cy - fm.height() / 2.0 + fm.ascent()
        p.save()
        p.setOpacity(max(0.0, min(1.0, alfa)))
        if rol == 'main' and amro:
            self._acento_amro(p, n, base_x, base_y, ancho, fm, px)
        # sombra suave (los textos de Resolve llevan sombra) y el texto
        trazo = QPainterPath()
        trazo.addText(QPointF(base_x, base_y), f, texto)
        sombra = QColor(0, 0, 0, 120)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sombra)
        p.drawPath(trazo.translated(0, max(1.0, px * 0.05)))
        if rol == 'main' and n in (1, 2, 4, 5):
            glow = QColor(color)
            glow.setAlpha(58)
            p.setPen(QPen(glow, max(1.5, px * 0.06)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(trazo)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(trazo)
        p.restore()

    @staticmethod
    def _acento_amro(p, n, x, base_y, ancho, fm, px):
        """Los presets de Amro, a grandes rasgos: pastilla dorada (3), fuego rojo (6), tachado (7) y subrayado (8)."""
        alto = fm.height()
        p.setPen(Qt.PenStyle.NoPen)
        if n == 3:
            p.setBrush(QColor('#F2A81D'))
            p.drawRoundedRect(QRectF(x - px * 0.28, base_y - fm.ascent() - px * 0.04, ancho + px * 0.56, alto + px * 0.08), px * 0.18, px * 0.18)
        elif n == 7:
            p.setBrush(QColor('#E02020'))
            p.drawRoundedRect(QRectF(x - px * 0.06, base_y - fm.ascent() * 0.42, ancho + px * 0.12, max(2.0, px * 0.09)), 2, 2)
        elif n == 8:
            p.setBrush(QColor('#35D52B'))
            p.drawRoundedRect(QRectF(x, base_y + px * 0.07, ancho, max(2.0, px * 0.09)), 2, 2)

    def _dibujar_emoji(self, p, s, x0, y0, t, cue):
        img = self._imagen
        if not img:
            return
        y_top, y_bot = self._caja()
        lado = EMOJI_ALTO * ALTO_CUADRO * s
        if img.get('donde') == 'arriba':
            cy_f = y_top - EMOJI_MARGEN - EMOJI_ALTO / 2.0
        else:
            cy_f = y_bot + EMOJI_MARGEN + EMOJI_ALTO / 2.0
        cx = x0 + ANCHO_CUADRO * s / 2.0
        cy = y0 + cy_f * ALTO_CUADRO * s
        if t is not None:
            ini = float(cue.get('emoji_ini') if cue.get('emoji_ini') is not None else cue.get('start') or 0.0) - float(cue.get('start') or 0.0)
            if t < ini:
                return
        caja = QRectF(cx - lado / 2.0, cy - lado / 2.0, lado, lado)
        pix = img.get('pix')
        if pix is not None and not pix.isNull():
            p.drawPixmap(caja, pix, QRectF(pix.rect()))
        else:
            p.save()
            pen = QPen(QColor(qt_kit.ROL_IMAGEN), 1.4, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(caja, lado * 0.24, lado * 0.24)
            p.restore()
