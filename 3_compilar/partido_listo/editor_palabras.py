# CineCaptions · By Cinema Productions
# 1_codigo/editor_palabras.py — El editor de palabras (Creativo): lienzo, pinceles y WordTagWindow.
"""
editor_palabras.py
------------------
El editor de palabras (Creativo): lienzo, pinceles y WordTagWindow.

Salió de «CineCaptions (script principal).py» (v5.4.44) SIN cambiar su código: el principal conserva la ventana principal (SubtitleApp) y vuelve a importar estos nombres, así que `cc_main.NombreDeClase` sigue existiendo.
"""
import os
import math
import sys
import threading
import time
import traceback
from pathlib import Path
from PySide6.QtCore import QEvent, QEventLoop, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QCursor, QFont, QFontMetricsF, QGuiApplication, QImage, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import QAbstractButton, QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget
import qt_kit as ui
from qt_kit import (BooleanVar, Boton, Casilla, Chip, Combo, Desplazable, Dialogo, Enlace, Entrada, Etiqueta, Interruptor, MarcoVista, Menu, Segmentado, StringVar, Tarjeta, Tooltip, caja_h, cancelar, despues, ejecutar_en_ui, filedialog, limpiar_capa, messagebox, vivo)
from qt_kit import QColor, QColorReal
from i18n import tr
import sugerencias_ia
import emojis_animados
import ortografia
import plantillas
import composicion
import registro
from ui_comun import (ACCENT, CARD_COLOR, MAX_HISTORIAL, TEXT_MUTED, _capa_dialogo, _correr_en_hilo, _hex_de, _titulo, estilo_fijo, familia_legible, fuente, guardar_log_de_error, guardar_marcas, lineas_de_vista)
from selector_emojis import (EmojiPickerWindow)
def _color_de_variante(color, defecto='#FFFFFF'):
    """El color de una variante del pack como '#RRGGBB': viene como texto '#RRGGBB' (packs nuevos) o como [r, g, b] de 0 a 1 (los antiguos)."""
    if isinstance(color, str) and color.startswith('#') and len(color) in (4, 7):
        return color
    return _hex_de(color, defecto) if color else defecto
def _mezclar_hex(color, fondo, fraccion):
    """El color a 'fraccion' del camino entre el fondo y el color (el
    relleno de una ficha: el color del rol al 14 % sobre el fondo)."""
    try:
        c = [int(color[i:i + 2], 16) for i in [1, 3, 5]]
        f = [int(fondo[i:i + 2], 16) for i in [1, 3, 5]]
    except (ValueError, TypeError, IndexError):
        return fondo
    return '#%02X%02X%02X' % tuple((max(0, min(255, round(fb + (cb - fb) * fraccion))) for cb, fb in zip(c, f)))
def _timecode(segundos):
    """\'[1:23]\' — el minuto y segundo donde arranca la frase."""
    try:
        t = max(0, int(float(segundos or 0)))
    except (TypeError, ValueError):
        t = 0
    return '[%d:%02d]' % (t // 60, t % 60)
def _tc_largo(segundos):
    """'00:01:23' — la columna de tiempos del lienzo (v5.0.0)."""
    try:
        t = max(0, int(float(segundos or 0)))
    except (TypeError, ValueError):
        t = 0
    return '%02d:%02d:%02d' % (t // 3600, t % 3600 // 60, t % 60)
def _tc_fino(segundos):
    """'00:00:07,4' — el tramo del bloque en vivo."""
    try:
        s = max(0.0, float(segundos or 0))
    except (TypeError, ValueError):
        s = 0.0
    entero = int(s)
    return '%02d:%02d:%02d,%d' % (entero // 3600, entero % 3600 // 60, entero % 60, int((s - entero) * 10))
class _Ev:
    """Lo que la logica de la v4 leia de un evento de Tk: x, y del lienzo y
    x_root, y_root de la pantalla."""
    __slots__ = ('x', 'y', 'x_root', 'y_root')
    def __init__(self, e):
        p = e.position()
        g = e.globalPosition()
        self.x, self.y = (p.x(), p.y())
        self.x_root, self.y_root = (int(g.x()), int(g.y()))
class _PopupSfx(QLabel):
    """El popup pequeño con el sonido de una palabra (sale al pasar el cursor; clic = elegir otro)."""
    def __init__(self, padre, al_clic):
        super().__init__(padre)
        self._al_clic = al_clic
        self.sobre = False
        self.setStyleSheet('QLabel{background:#0F1A30;color:#E8F1FF;border:1px solid #3AA0FF;border-radius:9px;padding:3px 10px;font-size:12px;font-weight:600;}')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide()
    def enterEvent(self, e):
        self.sobre = True
        super().enterEvent(e)
    def leaveEvent(self, e):
        self.sobre = False
        ui.despues(200, lambda: self.hide() if (ui.vivo(self) and not self.sobre) else None, self)
        super().leaveEvent(e)
    def mousePressEvent(self, e):
        self._al_clic()
class LienzoPalabras(QWidget):
    """El area de palabras del editor (v3.3.2): cada palabra es una FICHA
    redondeada del color de su rol — la referencia del usuario (fichas por
    palabra, el emoji con la palabra, los pinceles con contador).

    Reglas que mandan aqui:
      - Cada palabra RESERVA el ancho de su texto en NEGRITA (la mas ancha
        de las tres fuentes) mas el relleno: cambiar de rol NUNCA mueve nada
        (pintar() solo repinta esa ficha); poner o quitar un emoji redibuja.
      - La geometria vive en _cajas (rectangulos): el clic se resuelve con
        aritmetica y una tolerancia.
    v5.0.0 (imagen 03 de la propuesta): pinta SOLO lo que se ve; una columna
    de tiempos 00:00:00 por frase; en «Fichas» todas las palabras llevan su
    ficha (las sin marcar, en gris), el emoji va ENCIMA de la palabra y las
    dudosas llevan un subrayado ondulado rojo. «Clásica» sigue siendo texto
    coloreado con el emoji dentro, como en la v4.
    """
    PAD_X = 12
    PAD_Y = 7
    HUECO = 8
    HUECO_FILA = 8
    HUECO_FILA_FICHAS = 12
    RADIO = 15
    MARGEN = 14
    PAN_X = 12            # relleno del panel de cada frase
    PAN_Y = 9
    RADIO_PANEL = 20
    HUECO_PANEL = 8
    FONDO = '#0A0F1E'
    FONDO_ALFA = 0        # 0 = sin fondo propio: la tarjeta (editor_ui.MarcoPapel) pone el fondo con las esquinas redondeadas
    TEXTO_SIN_ROL = '#8D9BB5'
    TEXTO_MODO_TEXTO = '#E8F1FF'
    TIEMPO = '#5A6B87'
    DUDOSA = '#FF6B6B'
    CORTE_AUTO = '#3A4E73'
    FICHA_TENUE = '#26334D'
    FICHA_GRIS = '#141E33'
    HOVER = '#FFFFFF'
    BADGE = 10
    EMOJI_ARRIBA = 24
    QUITAR = '#2E3F63'
    QUITAR_HOVER = '#FF6B6B'
    def __init__(self, fuentes, colores_rol, acento, padre=None):
        super().__init__(padre)
        self._fuentes = fuentes
        self._colores = colores_rol
        self._acento = acento
        self.estilo = 'fichas'
        self.factor_filas = 1.0
        self.factor_parrafos = 1.0
        self._cajas = []
        self._items = []
        self._emojis = []
        self._quitar = []
        self._textos = []
        self._extras = []
        self._paneles = []
        self._pastillas = []
        self._datos = None
        self._ancho_dibujado = 0
        self._alto_total = 1
        self._relayout_id = None
        self._hover = None
        self._hover_quitar = None
        self.al_clic = None
        self.al_doble = None
        self.al_arrastrar = None
        self.al_soltar = None
        self.al_menu = None
        self.al_hover = None
        self.capitalizar = False         # v5.4: «Capitalizar palabras de contenido» tambien se ve en el parrafo
        self._t_emojis = time.perf_counter()
        self._reloj_emojis = ui.QTimer(self)        # v5.4: los emojis de las fichas se mueven (solo se repintan los visibles)
        self._reloj_emojis.timeout.connect(self._tic_emojis)
        self.al_seleccion = None
        self.al_sfx = None               # v5.4: clic en el punto de sonido de una palabra -> al_sfx(idx, x_global, y_global)
        self._puntos_sfx = {}            # {idx: (color, nombre)}
        self._popup_sfx = None
        self._popup_idx = None
        self._sel = set()                # v5.4: palabras seleccionadas (recuadro con el boton apretado, Ctrl+clic, Mayus+clic)
        self._banda = None               # (x0, y0, x1, y1) del recuadro mientras se arrastra
        self._banda_base = set()
        self._ancla = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.area = QScrollArea()
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setAutoFillBackground(False)
        self.area.viewport().setAutoFillBackground(False)
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setWidget(self)
        self.setAutoFillBackground(False)               # QScrollArea.setWidget lo enciende: sin esto el lienzo tapa la tarjeta redondeada
        self.area.verticalScrollBar().setSingleStep(24)
    def _texto_visible(self, texto, rol):
        """La palabra como se vera en el bloque: con mayuscula inicial si es de contenido (conectores en baja)."""
        if self.capitalizar and rol in ('context', 'main', 'complement') and texto:
            try:
                import dynamic_subtitles as dyn
                return dyn.capitalizar_contenido(texto)
            except Exception:
                return texto
        return texto

    @staticmethod
    def _glifo_de_emoji(eid):
        try:
            import emojis
            return (emojis.por_id(eid) or {}).get('glifo') or ''
        except Exception:
            return ''

    def _fm(self, clave):
        return QFontMetricsF(self._fuentes[clave])
    def dibujar(self, palabras, roles, dudosas, cortes_auto, modo, imagen_de,
                pausa=0.45):
        """Rehace el layout de flujo con el ancho actual. 'imagen_de(id)' da
        la miniatura del emoji (QPixmap) o None; 'pausa' es
        dyn.PAUSA_SILENCIO (fila extra tras un silencio)."""
        self._datos = (palabras, roles, dudosas, cortes_auto, modo, imagen_de, pausa)
        n = len(palabras)
        self._cajas = [None] * n
        self._items = [None] * n
        self._emojis = [None] * n
        self._quitar = [None] * n
        self._textos = [self._texto_visible(str(w.get('word', '')).strip(), roles[i] if modo == 'marcas' and i < len(roles) else None) for i, w in enumerate(palabras)]
        self._extras = []
        self._paneles = []
        self._pastillas = []
        ancho = self.area.viewport().width()
        if ancho < 120:
            ancho = 760
        self._ancho_dibujado = ancho
        fm_base, fm_main, fm_t = (self._fm('base'), self._fm('main'), self._fm('tiempo'))
        alto_linea = max(fm_main.lineSpacing(), fm_base.lineSpacing())
        fichas = self.estilo == 'fichas'
        alto_ficha = alto_linea + 2 * (self.PAD_Y if fichas else 4)
        pad_x = self.PAD_X if fichas else 2
        hueco = self.HUECO if fichas else max(4, fm_base.horizontalAdvance(' '))
        hueco_fila = self.HUECO_FILA_FICHAS if fichas else self.HUECO_FILA
        pan_x, pan_y = (self.PAN_X, self.PAN_Y)
        hueco_parrafo = max(4, round(self.HUECO_PANEL * self.factor_parrafos))      # entre el panel de una frase y el de la siguiente
        fila_extra = max(0, round(alto_ficha // 4 * self.factor_filas))       # una pausa larga deja un poco más de aire entre paneles
        ancho_pastilla = fm_t.horizontalAdvance('00:00:00') + 20
        alto_pastilla = fm_t.lineSpacing() + 10
        col_tiempos = ancho_pastilla + 12
        x_inicio = self.MARGEN + pan_x + col_tiempos
        limite = ancho - self.MARGEN - pan_x
        x, y = (x_inicio, self.MARGEN + pan_y)
        y_ini = y
        arranca_frase = True
        for i, w in enumerate(palabras):
            texto = self._textos[i]
            if arranca_frase:
                if x > x_inicio:
                    x, y = (x_inicio, y + alto_ficha + hueco_fila)
                y_ini = y
                self._pastillas.append((QRectF(self.MARGEN + pan_x, y + (alto_ficha - alto_pastilla) / 2, ancho_pastilla, alto_pastilla), _tc_largo(w.get('start'))))
                arranca_frase = False
            img = imagen_de(w['emoji']) if w.get('emoji') else None
            ancho_texto = fm_main.horizontalAdvance(texto) if texto else 4
            ancho_img = img.deviceIndependentSize().width() if img is not None else 0
            # v5.2 (pedido: «los emojis no entran bien en los cuadros»): en
            # «Fichas» el emoji va DENTRO de la ficha, a la izquierda de la
            # palabra, con su sitio reservado (antes flotaba encima de la
            # esquina y tapaba el borde, el texto y la fila de arriba)
            lado_ficha = max(14, round(alto_linea * 0.92))
            if img is not None and fichas:
                hueco_emoji = lado_ficha + 7
            elif img is not None:
                hueco_emoji = ancho_img + 6 + self.BADGE
            else:
                hueco_emoji = 0
            ancho_ficha = ancho_texto + 2 * pad_x + hueco_emoji
            marca = None
            if w.get('corte') and i + 1 < n:
                marca = ('⏎', self._acento, 'main')
            else:
                if i in cortes_auto:
                    marca = ('·', self.CORTE_AUTO, 'tiempo')
            ancho_marca = self._fm(marca[2]).horizontalAdvance(marca[0]) + 6 if marca else 0
            if x > x_inicio and x + ancho_ficha + ancho_marca > limite:
                x, y = (x_inicio, y + alto_ficha + hueco_fila)
            x0, y0, x1, y1 = (x, y, x + ancho_ficha, y + alto_ficha)
            cy = (y0 + y1) / 2
            item = {'tx': x0 + pad_x + (hueco_emoji if (img is not None and fichas) else 0),
                    'ancho_texto': ancho_texto, 'img': img, 'img_rect': None,
                    'rol': None, 'dudosa': False, 'modo': modo, 'pad_x': pad_x,
                    'glifo': self._glifo_de_emoji(w['emoji']) if img is not None else ''}
            if img is not None:
                if fichas:
                    lado = lado_ficha
                    ex = x0 + pad_x - 2
                    ey = cy - lado / 2
                    item['img_rect'] = QRectF(ex, ey, lado, lado)
                    self._emojis[i] = (ex, ey, ex + lado, ey + lado)
                    # la ✕ para quitarlo: un circulo chico en la esquina de la
                    # ficha, DENTRO de su caja (solo se ve al pasar el mouse)
                    self._quitar[i] = (x1 - 15, y0 - 5, x1 + 3, y0 + 13)
                else:
                    ex = x1 - pad_x - self.BADGE
                    item['img_rect'] = QRectF(ex - ancho_img, cy - ancho_img / 2, ancho_img, ancho_img)
                    self._emojis[i] = (ex - ancho_img, y0, x1, y1)
                    self._quitar[i] = (ex, y0, ex + self.BADGE + 2, y0 + self.BADGE + 2)
            self._cajas[i] = (x0, y0, x1, y1)
            self._items[i] = item
            item['rol'] = roles[i] if modo == 'marcas' and i < len(roles) else None
            item['dudosa'] = i in dudosas
            x = x1
            if marca:
                t, color, clave = marca
                self._extras.append((QRectF(x + 3, y0, ancho_marca + 2, alto_ficha), t, color, clave))
                x += ancho_marca
            if i + 1 < n:
                if w.get('fin_frase'):
                    try:
                        silencio = float(palabras[i + 1].get('start') or 0) - float(w.get('end') or 0)
                    except (TypeError, ValueError):
                        silencio = 0.0
                    self._paneles.append(QRectF(self.MARGEN, y_ini - pan_y, ancho - 2 * self.MARGEN, (y + alto_ficha) - y_ini + 2 * pan_y))
                    x = x_inicio
                    y += alto_ficha + 2 * pan_y + hueco_parrafo
                    if silencio > pausa:
                        y += fila_extra
                    arranca_frase = True
                else:
                    x += hueco
        if n:
            self._paneles.append(QRectF(self.MARGEN, y_ini - pan_y, ancho - 2 * self.MARGEN, (y + alto_ficha) - y_ini + 2 * pan_y))
        self._alto_total = y + alto_ficha + pan_y + self.MARGEN
        self.setMinimumHeight(int(math.ceil(self._alto_total)))
        self.update()
    def pintar(self, idx, rol, dudosa=False, modo='marcas'):
        """Solo colores y fuente de UNA palabra: nada se mueve."""
        if not 0 <= idx < len(self._items) or self._items[idx] is None:
            return
        it = self._items[idx]
        it['rol'] = rol
        it['dudosa'] = bool(dudosa)
        it['modo'] = modo
        if self.capitalizar and self._datos is not None and 0 <= idx < len(self._textos):
            nuevo = self._texto_visible(str(self._datos[0][idx].get('word', '')).strip(), rol if modo == 'marcas' else None)
            if nuevo != self._textos[idx]:
                self._textos[idx] = nuevo
                cancelar(self._relayout_id)
                self._relayout_id = despues(150, self._relayout, self)      # el ancho de la ficha cambia: se reacomoda
        self._repintar(idx)
    def _repintar(self, idx):
        if idx is None or not 0 <= idx < len(self._cajas) or self._cajas[idx] is None:
            return
        x0, y0, x1, y1 = self._cajas[idx]
        arriba = self.EMOJI_ARRIBA + 8
        self.update(int(x0) - 6, int(y0) - arriba, int(x1 - x0) + 22, int(y1 - y0) + arriba + 8)
    def paintEvent(self, ev):
        p = QPainter(self)
        zona = QRectF(ev.rect())
        if self.FONDO_ALFA:
            _fondo = QColor(self.FONDO)
            _fondo.setAlpha(self.FONDO_ALFA)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(ev.rect(), _fondo)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        alinear = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # cada frase en su panel redondeado; su hora, en una pastilla
        p.setPen(QPen(QColor(255, 255, 255, 14), 1.0))
        p.setBrush(QColor(255, 255, 255, 8))
        for panel in self._paneles:
            if panel.intersects(zona):
                p.drawRoundedRect(panel.adjusted(0.5, 0.5, -0.5, -0.5), self.RADIO_PANEL, self.RADIO_PANEL)
        p.setFont(self._fuentes['tiempo'])
        for rect, texto in self._pastillas:
            if rect.intersects(zona):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 14))
                p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
                p.setPen(QColor('#8D9BB5'))
                p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), texto)
        for rect, texto, color, clave in self._extras:
            if rect.intersects(zona):
                p.setFont(self._fuentes[clave])
                p.setPen(QColor(color))
                p.drawText(rect, alinear, texto)
        margen = self.EMOJI_ARRIBA + 8
        for i, caja in enumerate(self._cajas):
            if caja is None:
                continue
            x0, y0, x1, y1 = caja
            if y1 < zona.top() - 4 or y0 - margen > zona.bottom() + 4:
                continue
            self._pintar_ficha(p, i, caja, self._items[i])
        if self._sel:
            p.setBrush(QColor(58, 160, 255, 38))
            p.setPen(QPen(QColor('#3AA0FF'), 2.0))
            for i in self._sel:
                if 0 <= i < len(self._cajas) and self._cajas[i]:
                    x0, y0, x1, y1 = self._cajas[i]
                    if y1 >= zona.top() - 4 and y0 <= zona.bottom() + 4:
                        p.drawRoundedRect(QRectF(x0 - 1, y0 - 1, x1 - x0 + 2, y1 - y0 + 2), self.RADIO, self.RADIO)
        k_son = getattr(self, '_sonando_idx', None)
        if k_son is not None and 0 <= k_son < len(self._cajas) and self._cajas[k_son]:
            # v5.5: la palabra que SUENA ahora (reproduccion del parrafo): halo ambar que la sigue
            x0, y0, x1, y1 = self._cajas[k_son]
            for grosor, alfa in ((7.0, 40), (4.0, 80), (2.0, 230)):
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 196, 60, alfa), grosor))
                p.drawRoundedRect(QRectF(x0 - 2, y0 - 2, x1 - x0 + 4, y1 - y0 + 4), self.RADIO + 2, self.RADIO + 2)
        if self._banda is not None:
            bx0, by0, bx1, by1 = self._banda
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setBrush(QColor(30, 111, 217, 90))
            p.setPen(QPen(QColor('#1E88E5'), 1.0))
            p.drawRect(QRectF(min(bx0, bx1), min(by0, by1), abs(bx1 - bx0), abs(by1 - by0)))
        p.end()
    def _pintar_ficha(self, p, i, caja, it):
        x0, y0, x1, y1 = caja
        rol = it['rol']
        modo = it['modo']
        color = self._colores.get(rol) if rol else None
        hover = i == self._hover
        f_base = self._fuentes['base']
        fuente_rol = self._fuentes.get(rol, f_base) if rol else f_base
        con_emoji = it['img'] is not None
        rect = QRectF(x0, y0, x1 - x0, y1 - y0)
        r = min(self.RADIO, (y1 - y0) / 2, (x1 - x0) / 2)
        fichas = self.estilo == 'fichas'
        if not fichas:
            sin_rol = (self.TEXTO_MODO_TEXTO if modo == 'texto'
                       else self._colores.get(None) or self.TEXTO_SIN_ROL)
            c_texto = self.HOVER if hover else (color or sin_rol)
        elif color:
            p.setPen(QPen(QColor('#FFFFFF' if hover else color), 2.0 if hover else 1.4))
            p.setBrush(QColorReal(_mezclar_hex(color, ui.tc(self.FONDO), 0.24 if hover else 0.17)))
            p.drawRoundedRect(rect.adjusted(0.7, 0.7, -0.7, -0.7), r, r)
            c_texto = '#F4F7FF'
        else:
            p.setPen(QPen(QColor('#3A4A6A' if hover else self.FICHA_TENUE), 1.2))
            p.setBrush(QColor('#18233A' if hover else self.FICHA_GRIS))
            p.drawRoundedRect(rect.adjusted(0.6, 0.6, -0.6, -0.6), r, r)
            c_texto = self.HOVER if hover else ('#E8F1FF' if modo == 'texto' else '#C9D6EC')
        p.setFont(fuente_rol)
        p.setPen(QColor(c_texto))
        p.drawText(QRectF(it['tx'] - 2, y0, it['ancho_texto'] + 4, y1 - y0),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), self._textos[i])
        if it['dudosa']:
            yl = y1 - (self.PAD_Y if fichas else 4) + 2
            camino = QPainterPath()
            xa, xb = (it['tx'], it['tx'] + it['ancho_texto'])
            camino.moveTo(xa, yl)
            paso, alto_onda, k = (3.0, 1.6, 0)
            xx = xa
            while xx < xb:
                xx = min(xb, xx + paso)
                k += 1
                camino.lineTo(xx, yl + (alto_onda if k % 2 else -alto_onda))
            p.setPen(QPen(QColor(self.DUDOSA), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(camino)
        if con_emoji:
            img = it['img']
            ir = it['img_rect']
            # el emoji ya vive dentro de la ficha (v5.2): sin aro, a su tamaño
            anim = emojis_animados.frame(it['glifo'], time.perf_counter() - self._t_emojis, self._anim_lista) if it.get('glifo') else None
            if anim is not None:
                p.drawPixmap(ir, anim, QRectF(anim.rect()))
            else:
                p.drawPixmap(ir, img, QRectF(img.rect()))
            q = self._quitar[i]
            if q and (not fichas or hover or self._hover_quitar == i):
                bx0, by0, bx1, by1 = q
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(self.QUITAR_HOVER if self._hover_quitar == i else self.QUITAR))
                p.drawEllipse(QRectF(bx0 + 1, by0 + 1, bx1 - bx0 - 2, by1 - by0 - 2))
                p.setPen(QColor('#E0EBFB'))
                p.setFont(fuente(9, True))
                p.drawText(QRectF(bx0, by0 - 1, bx1 - bx0, by1 - by0), int(Qt.AlignmentFlag.AlignCenter), '×')
    def indice_en(self, x, y, tolerancia=0):
        """La palabra en ese punto DEL LIENZO (o a menos de 'tolerancia' px
        de ella), o None. Con varias a tiro gana la mas cercana."""
        cx, cy = (x, y)
        mejor, d_mejor = (None, None)
        for i, caja in enumerate(self._cajas):
            if caja is None:
                continue
            x0, y0, x1, y1 = caja
            d = max(x0 - cx, 0, cx - x1, y0 - cy, cy - y1)
            if d <= tolerancia and (d_mejor is None or d < d_mejor):
                mejor, d_mejor = (i, d)
                if d == 0:
                    break
        return mejor
    def emoji_en(self, x, y):
        """La palabra cuyo EMOJI esta bajo ese punto, o None."""
        for i, caja in enumerate(self._emojis):
            if caja and caja[0] <= x <= caja[2] and caja[1] <= y <= caja[3]:
                return i
        return None
    def quitar_en(self, x, y):
        """La palabra cuya ✕ de emoji esta bajo ese punto, o None (v3.3.4)."""
        for i, caja in enumerate(self._quitar):
            if caja and caja[0] <= x <= caja[2] and (caja[1] <= y <= caja[3]):
                return i
        return None
    def caja_raiz(self, idx):
        """(x, y, ancho, alto) de la ficha EN PANTALLA, o None."""
        if not 0 <= idx < len(self._cajas) or self._cajas[idx] is None:
            return None
        x0, y0, x1, y1 = self._cajas[idx]
        g = self.mapToGlobal(QPoint(int(x0), int(y0)))
        return (g.x(), g.y(), int(x1 - x0), int(y1 - y0))
    def sonando(self, idx):
        """Marca (o desmarca con None) la palabra que esta sonando; se repinta solo lo que cambia."""
        previo = getattr(self, '_sonando_idx', None)
        if previo == idx:
            return
        self._sonando_idx = idx
        for k in (previo, idx):
            if k is not None and 0 <= k < len(self._cajas) and self._cajas[k]:
                x0, y0, x1, y1 = self._cajas[k]
                self.update(int(x0 - 10), int(y0 - 10), int(x1 - x0 + 20), int(y1 - y0 + 20))
    def ver(self, idx):
        """Desplaza lo justo para que la ficha se vea."""
        if not 0 <= idx < len(self._cajas) or self._cajas[idx] is None:
            return
        x0, y0, x1, y1 = self._cajas[idx]
        barra = self.area.verticalScrollBar()
        arriba = barra.value()
        abajo = arriba + max(1, self.area.viewport().height())
        if y0 - self.EMOJI_ARRIBA < arriba or y1 > abajo:
            barra.setValue(max(0, int(y0 - 60)))
    def vista(self):
        return self.area.verticalScrollBar().value()
    def ir_a(self, valor):
        try:
            self.area.verticalScrollBar().setValue(int(valor))
        except Exception:
            pass
    def textos(self):
        return list(self._textos)
    def emojis_dibujados(self):
        return sum((1 for it in self._items if it and it['img'] is not None))
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._datos is None or abs(self.area.viewport().width() - self._ancho_dibujado) < 2:
            return
        cancelar(self._relayout_id)
        self._relayout_id = despues(60, self._relayout, self)
    def _relayout(self):
        self._relayout_id = None
        if self._datos is None:
            return
        vista = self.vista()
        self.dibujar(*self._datos)
        self.ir_a(vista)
    # -- v5.4: el punto de sonido bajo la palabra donde empieza cada efecto --------------------
    def poner_puntos_sfx(self, puntos):
        if puntos != self._puntos_sfx:
            self._puntos_sfx = dict(puntos)
            self.update()

    def showEvent(self, e):
        self._reloj_emojis.start(60)
        super().showEvent(e)

    def hideEvent(self, e):
        self._reloj_emojis.stop()
        super().hideEvent(e)

    def _tic_emojis(self):
        if not ui.vivo(self) or not self.isVisible():
            return
        arriba = self.area.verticalScrollBar().value()
        abajo = arriba + self.area.viewport().height()
        for i, it in enumerate(self._items):
            if it and it.get('glifo') and self._cajas[i]:
                x0, y0, x1, y1 = self._cajas[i]
                if y1 >= arriba and y0 <= abajo:
                    self.update(int(x0), int(y0), int(x1 - x0) + 4, int(y1 - y0) + 2)

    def _anim_lista(self, _g):
        if ui.vivo(self):
            self.update()

    def _popup_sfx_para(self, idx):
        """Al pasar el cursor por una palabra con sonido sale un popup pequeño con el nombre; clic en el popup = cambiarlo."""
        if idx is None or idx not in self._puntos_sfx or not (0 <= idx < len(self._cajas)) or not self._cajas[idx]:
            ui.despues(260, self._ocultar_popup_sfx, self)
            return
        if self._popup_sfx is None:
            self._popup_sfx = _PopupSfx(self, self._clic_popup_sfx)
        pu = self._popup_sfx
        self._popup_idx = idx
        pu.setText('♪  ' + self._puntos_sfx[idx][1])
        pu.adjustSize()
        x0, y0, x1, y1 = self._cajas[idx]
        px = int((x0 + x1) / 2 - pu.width() / 2)
        px = max(2, min(px, max(2, self.width() - pu.width() - 2)))
        pu.move(px, int(y1 + 2))
        pu.show()
        pu.raise_()

    def _ocultar_popup_sfx(self):
        pu = self._popup_sfx
        if pu is not None and not pu.sobre and self._hover != self._popup_idx:
            pu.hide()

    def _clic_popup_sfx(self):
        if self.al_sfx and self._popup_idx is not None and self._popup_sfx is not None:
            g = self.mapToGlobal(self._popup_sfx.geometry().bottomLeft())
            self._popup_sfx.hide()
            self.al_sfx(self._popup_idx, g.x(), g.y())

    # -- v5.4: seleccion de varias palabras -------------------------------------------------
    def seleccion(self):
        return sorted(self._sel)

    def limpiar_seleccion(self, avisar=True):
        if self._sel:
            self._sel = set()
            self.update()
            if avisar and self.al_seleccion:
                self.al_seleccion([])

    def _avisar_seleccion(self):
        if self.al_seleccion:
            self.al_seleccion(sorted(self._sel))

    def _tocadas_por(self, x0, y0, x1, y1):
        a, b = (min(x0, x1), min(y0, y1))
        c, d = (max(x0, x1), max(y0, y1))
        return {i for i, caja in enumerate(self._cajas) if caja and caja[0] <= c and caja[2] >= a and caja[1] <= d and caja[3] >= b}

    def _empezar_seleccion(self, e):
        """True si este clic NO es de pintar una palabra: empieza un recuadro, o suma/quita con Ctrl o Mayus."""
        if e.button() != Qt.MouseButton.LeftButton:
            return False
        pos = e.position()
        mods = e.modifiers()
        h = self.indice_en(pos.x(), pos.y(), 0)
        if h is not None and (mods & Qt.KeyboardModifier.ControlModifier):
            self._sel ^= {h}
            self._ancla = h
            self.update()
            self._avisar_seleccion()
            return True
        if h is not None and (mods & Qt.KeyboardModifier.ShiftModifier) and self._ancla is not None:
            a, b = sorted((self._ancla, h))
            self._sel |= set(range(a, b + 1))
            self.update()
            self._avisar_seleccion()
            return True
        if h is None and self.indice_en(pos.x(), pos.y(), 5) is None and self.quitar_en(pos.x(), pos.y()) is None and self.emoji_en(pos.x(), pos.y()) is None:
            self._banda = (pos.x(), pos.y(), pos.x(), pos.y())
            self._banda_base = set(self._sel) if (mods & Qt.KeyboardModifier.ControlModifier) else set()
            if not (mods & Qt.KeyboardModifier.ControlModifier):
                self._sel = set()
            self.update()
            return True
        return False

    def mousePressEvent(self, e):
        if self._empezar_seleccion(e):
            return
        ev = _Ev(e)
        es_menu = e.button() == Qt.MouseButton.RightButton or (
            sys.platform == 'darwin' and e.button() == Qt.MouseButton.LeftButton
            and e.modifiers() & Qt.KeyboardModifier.MetaModifier)
        if es_menu:
            if self.al_menu:
                self.al_menu(ev)
            return
        if e.button() == Qt.MouseButton.LeftButton and self.al_clic:
            self.al_clic(ev)
    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.al_doble:
            self.al_doble(_Ev(e))
    def mouseMoveEvent(self, e):
        if self._banda is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            pos = e.position()
            x0, y0 = self._banda[0], self._banda[1]
            self._banda = (x0, y0, pos.x(), pos.y())
            self._sel = self._banda_base | self._tocadas_por(x0, y0, pos.x(), pos.y())
            barra = self.area.verticalScrollBar()          # junto al borde de la vista, desplaza
            y_vista = pos.y() - barra.value()
            if y_vista < 24:
                barra.setValue(barra.value() - 24)
            elif y_vista > self.area.viewport().height() - 24:
                barra.setValue(barra.value() + 24)
            self.update()
            return
        if e.buttons() & Qt.MouseButton.LeftButton:
            if self.al_arrastrar:
                self.al_arrastrar(_Ev(e))
            return
        pos = e.position()
        q = self.quitar_en(pos.x(), pos.y())
        h = self.indice_en(pos.x(), pos.y(), 0)
        if h is None and q is not None:
            h = q
        if h is None:
            h = self.emoji_en(pos.x(), pos.y())
        if h != self._hover or q != self._hover_quitar:
            antes, antes_q = (self._hover, self._hover_quitar)
            if h != antes:
                self._popup_sfx_para(h)
            self._hover, self._hover_quitar = (h, q)
            for k in {antes, h, antes_q, q}:
                self._repintar(k)
            if h is not None and self.al_hover:
                self.al_hover(h)
    def mouseReleaseEvent(self, e):
        if self._banda is not None and e.button() == Qt.MouseButton.LeftButton:
            self._banda = None
            self.update()
            self._avisar_seleccion()
            return
        if e.button() == Qt.MouseButton.LeftButton and self.al_soltar:
            self.al_soltar(_Ev(e))
    def leaveEvent(self, e):
        antes, antes_q = (self._hover, self._hover_quitar)
        self._hover = self._hover_quitar = None
        self._repintar(antes)
        self._repintar(antes_q)
        super().leaveEvent(e)
class PincelesBar(QWidget):
    """Los pinceles como pildoras con punto de color, tecla y contador
    (v3.3.2, la referencia: «1 Contexto · 35»). Interfaz minima: set/get,
    _value_list y command(valor) al pulsar. Los contadores llegan por
    contar({valor: n}); el elegido lleva el borde del color de su rol."""
    APAGADO = '#111D33'
    def __init__(self, master, valores, teclas, colores, variable,
                 command=None):
        super().__init__(master)
        self._value_list = list(valores)
        self._teclas = dict(teclas)
        self._colores = dict(colores)
        self._var = variable
        self._command = command
        self._conteos = {}
        self._botones = {}
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(8)
        for valor in self._value_list:
            b = _Pildora(valor, self._colores.get(valor) or ACCENT, lambda v=valor: self._pulsar(v))
            capa.addWidget(b)
            self._botones[valor] = b
        capa.addStretch(1)
        try:
            self._var.observar(self._refrescar, self)
        except Exception:
            pass
        self._refrescar()
    def boton(self, valor):
        return self._botones.get(valor)
    def _pulsar(self, valor):
        self._var.set(valor)
        if self._command:
            self._command(valor)
    def set(self, valor):
        self._var.set(valor)
    def get(self):
        return self._var.get()
    def contar(self, conteos):
        self._conteos = dict(conteos or {})
        self._refrescar()
    def _texto(self, valor):
        partes = [self._teclas[valor]] if self._teclas.get(valor) else []
        partes.append(valor)
        texto = '  '.join(partes)
        n = self._conteos.get(valor)
        return f'{texto} · {n}' if n is not None else texto
    def _refrescar(self):
        elegido = self._var.get()
        for valor, b in self._botones.items():
            b.poner(self._texto(valor), valor == elegido)
class _Pildora(QAbstractButton):
    """Una pildora de pincel: punto de color + texto; la elegida con el borde
    del color del rol."""
    def __init__(self, texto, color, comando):
        super().__init__()
        self.setText(str(texto))
        self._color = QColor(color)
        self._elegida = False
        self._hover = False
        self.setFont(fuente(13, peso='medio'))
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # v5.2: clicked manda «checked» (False) y la lambda del pincel
        # (lambda v=valor: ...) lo recibia como valor -> KeyError: False
        self.clicked.connect(lambda _=False: comando())
    def poner(self, texto, elegida):
        cambio = texto != self.text() or elegida != self._elegida
        self.setText(texto)
        self._elegida = bool(elegida)
        if cambio:
            self.updateGeometry()
            self.update()
    def sizeHint(self):
        return QSize(int(QFontMetricsF(self.font()).horizontalAdvance(self.text()) + 44), 36)
    def minimumSizeHint(self):
        return self.sizeHint()
    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)
    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.8, 0.8, -0.8, -0.8)
        if self._elegida:
            p.setPen(QPen(self._color, 1.6))
            p.setBrush(ui.mezclar(self._color, '#0D1627', 0.16))
        else:
            p.setPen(QPen(QColor('#2A3A58' if self._hover else '#1E2A42'), 1))
            p.setBrush(QColor('#15223D' if self._hover else '#111D33'))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(14, self.height() / 2 - 4.5, 9, 9))
        p.setPen(QColor('#FFFFFF' if self._elegida else '#C9D6EC'))
        p.setFont(self.font())
        p.drawText(QRectF(30, 0, self.width() - 40, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()
def _fuente_puntos(familia, puntos, negrita=False, italica=False):
    """Las letras del lienzo van en PUNTOS (como los tkfont de la v4)."""
    f = QFont(familia)
    f.setPointSizeF(float(puntos))
    if negrita:
        f.setWeight(QFont.Weight.Bold)
    f.setItalic(bool(italica))
    return f
class _SinBarra:
    """Un hueco que acepta cualquier llamada y no hace nada: lo que antes pintaba la barra de abajo del editor (v5.7: ya no existe)."""

    def __getattr__(self, _nombre):
        return lambda *a, **k: None


class _AvisoToast:
    """Las notas cortas del editor (antes en la barra de abajo) salen ahora como un aviso flotante; silencio=True las ignora."""

    def __init__(self, ventana):
        self._v = ventana
        self._ultimo = ('', 0.0)

    def configure(self, text=None, text_color=None, silencio=False, **_):
        if not text or silencio:
            return None
        ahora = time.perf_counter()
        if text == self._ultimo[0] and ahora - self._ultimo[1] < 1.5:
            return None
        self._ultimo = (text, ahora)
        try:
            import ui_toast
            ui_toast.mostrar(self._v, str(text), duracion_ms=3500)
        except Exception:
            return None


class WordTagWindow(QWidget):
    """El editor de palabras: el usuario marca a mano, palabra por palabra,
    cuales van de contexto / principal / complemento.

    Arranca pre-poblado con una sugerencia (el mismo criterio que antes
    decidia todo solo), para no partir de una pantalla en blanco — pero
    cualquier marca se puede cambiar antes de continuar. Lo que quede sin
    marcar sale como subtitulo simple, palabra por palabra.

    Se usa igual que en la v4: se crea, se llama a `esperar()`, y al volver
    `self.result` es (palabras, roles) o None si se cancelo. v5.0.0: en vez
    de una ventana modal es la pantalla «Editor de palabras» del menu
    lateral (decision del rediseño); esperar() mantiene viva la interfaz con
    un bucle de eventos propio, como hacia el modal.
    """
    ROLE_COLOR = {'context': ui.ROL_CONTEXTO, 'main': ui.ROL_PRINCIPAL, 'complement': ui.ROL_COMPLEMENTO, None: ui.ROL_BASE}
    ROLE_LABEL = {'context': tr('Arriba'), 'main': tr('Principal'), 'complement': tr('Abajo'), None: tr('Sin marcar')}
    BRUSH_TO_ROLE = {tr('Arriba'): 'context', tr('Principal'): 'main', tr('Abajo'): 'complement', tr('Simple'): None}
    EDIT_BRUSH = tr('Editar texto')
    EMOJI_BRUSH = tr('Emoji')
    PUNT_PAUSAS = '.,;:…\"\'“”«»()[]'
    PUNT_SIGNOS = '!¡?¿'
    PUNTUACION = PUNT_PAUSAS + PUNT_SIGNOS
    MODO_MARCAS = 'marcas'
    MODO_TEXTO = 'texto'
    def __init__(self, master, palabras, roles_iniciales, project_name=None, modo=MODO_MARCAS, idioma='es'):
        super().__init__()
        self.master = master
        self.modo = modo
        self.idioma = idioma
        self.project_name = project_name
        self.roles = list(roles_iniciales)
        self.dudosas = set()
        self.palabras = [dict(w) for w in palabras]
        for w in self.palabras:
            w.setdefault('orig', w['word'])
        self._marcar_fin_de_frase()
        self.result = None
        self.brush = 'main'
        self.modo_edicion = False
        self.modo_emoji = False
        self._imgs_emoji = {}
        self.caso = 'Original'
        self._rol_previo = None
        self._historial = []
        self._rehacer_pila = []
        self._pintando = None
        self._autoguardado_id = None
        self._contador_id = None
        self._corrigio_auto = False
        self._cerrando = False
        self._bucle = None
        self._proyecto_elegido = None
        self._ultimo_idx = 0
        self._version = 0
        self._cache_bloques = None
        self._hover_id = None
        self._orto_actual = None
        self._orto_eleccion = None
        import dynamic_subtitles as dyn
        self.tamanos = dyn.normalizar_tamanos(getattr(master, 'tamanos_grupo', None))
        self.tam_letra = self._tam_letra_valido(getattr(master, 'tam_letra_palabras', None))
        self.capitalizar_var = BooleanVar(getattr(master, 'capitalizar', True) is not False)
        self.peso_conector = 1.0                  # palabra por palabra: los conectores cuentan como una palabra (v5.7)
        self._roles_auto = True                   # True = los roles los puso la IA/sugerencia y no se tocaron a mano: los máximos los reajustan en vivo
        self._variante_ia = -1
        self._alternativas = None                 # las 4 versiones de la IA para los máximos actuales (listas para cambiar de una)
        self._id_reajuste = None
        self._t_reajuste = 0.0
        self.modo_corte = False
        self._popover = None
        self.estilo_palabras = 'clasico' if getattr(master, 'estilo_palabras', None) == 'clasico' else 'fichas'
        self.espacio_frases = self._espacio_valido(getattr(master, 'espacio_frases', None))
        self.espacio_parrafos = self._espacio_valido(getattr(master, 'espacio_parrafos', None))
        try:
            import emojis
            emojis.estilo(getattr(master, 'emoji_estilo', 'animado'))
            if modo == self.MODO_MARCAS and emojis.catalogo():
                emojis.preparar_minis(al_terminar=self._minis_listas)
        except Exception:
            pass
        self._orto_auto_id = None
        self._orto_pedida = False
        # v5.10: con un pack de estilo «guion» (Referencia…) el editor usa el MISMO planificador que Generar: marcas → bloques → vista exacta
        self._guion = False
        self._fin_video_memo = False
        if modo == self.MODO_MARCAS:
            try:
                import guion_editor
                self._guion = guion_editor.es_guion(getattr(master, 'plantilla_sel', ''), master._formato_forzado() or master._formato_en_juego() or 'v')
            except Exception:
                self._guion = False
        if self._guion and not any(self.roles):
            self.roles = self._roles_del_planificador()         # sin marcas (texto recién transcrito): se pintan las que el planificador pondría solo
        self._build_ui()
        self._llenar_texto()
        self._actualizar_contador()
        self._on_seleccion_toggle()
        self._atajos()
        self._refrescar_botones_historial()
        self._pintar_orto()
        QApplication.instance().installEventFilter(self)
        despues(1200, self._corregir_auto, self)
    def titulo(self):
        return tr('Retocar las palabras')
    def subtitulo(self):
        nombre = self.project_name or tr('sin proyecto')
        if self.modo == self.MODO_MARCAS and getattr(self, '_guion', False):
            return tr('{nombre} · estilo palabra a palabra: marca la palabra GRANDE (Principal) y la negrita (Abajo); lo demás se arma solo', nombre=nombre)
        if self.modo == self.MODO_MARCAS:
            return tr('{nombre} · pinta cada palabra con su rol; el bloque se arma solo', nombre=nombre)
        return tr('{nombre} · corrige el texto y marca dónde termina cada bloque', nombre=nombre)
    def _atajos(self):
        """Teclas para no tener que ir al selector de pincel a cada rato.

        Marcar 180 palabras a puro clic es lento; con 1/2/3/4 se cambia de
        pincel sin soltar el mouse, y con Ctrl+Z se deshace un resbalon. La
        base esta en la 4 y no en la 0 (la 0 queda como alias silencioso por
        la memoria muscular de las versiones anteriores).
        """
        contexto = Qt.ShortcutContext.WidgetWithChildrenShortcut
        teclas = [('1', tr('Arriba')), ('2', tr('Principal')), ('3', tr('Abajo')), ('4', tr('Simple')), ('0', tr('Simple')), ('5', self.EMOJI_BRUSH)]
        self._atajos_vivos = []
        for tecla, valor in teclas:
            a = QShortcut(QKeySequence(tecla), self)
            a.setContext(contexto)
            a.activated.connect(lambda v=valor: self._atajo_pincel(v))
            self._atajos_vivos.append(a)
        for secuencia, fn in [('Ctrl+Z', self._deshacer), ('Ctrl+Y', self._rehacer), ('Ctrl+Shift+Z', self._rehacer), ('Ctrl+S', self._guardar_marcas), ('Esc', self._escape)]:
            a = QShortcut(QKeySequence(secuencia), self)
            a.setContext(contexto)
            a.activated.connect(fn)
            self._atajos_vivos.append(a)
    def _escape(self):
        pop = self._popover
        if pop is not None and pop.existe():
            self._cerrar_popover()
            return
        self._pedir_cierre()
    def _atajo_pincel(self, valor):
        """La tecla 1-6 cambia de pincel... salvo que se este ESCRIBIENDO en
        un buscador de esta misma pantalla (el selector de emoji): ahi «1»
        es texto, no un atajo."""
        try:
            if isinstance(QApplication.focusWidget(), QLineEdit):
                return
            pop = self._popover
            if pop is not None and pop.existe():
                return
        except Exception:
            pass
        self._elegir_pincel(valor)
    def _elegir_pincel(self, valor):
        if self.modo != self.MODO_MARCAS:
            return None
        if valor == self.EMOJI_BRUSH:
            import emojis
            if not emojis.catalogo():
                return None
        self.brush_var.set(valor)
        self._on_brush_change(valor)
        if valor in self.BRUSH_TO_ROLE and len(self.lienzo.seleccion()) > 0:
            self._aplicar_a_seleccion(self.brush)           # v5.4: con palabras seleccionadas, el pincel se aplica a todas
    def _instantanea(self):
        return (list(self.roles), [dict(w) for w in self.palabras])
    def _restaurar(self, estado):
        self.roles, self.palabras = estado
        self._roles_auto = False                 # tras deshacer/rehacer, los roles se tratan como del usuario (no se reajustan solos)
        self._alternativas = None
        self._llenar_texto()
        self._actualizar_contador()
        self._refrescar_botones_historial()
        self._programar_autoguardado()
    def _poner_editor_minimo(self, minimo):
        self._editor_minimo = bool(minimo)
        for w in getattr(self, '_avanzado_editor', []):
            w.setVisible(not minimo)
        barra = getattr(self, 'herr_barra', None)
        if barra is not None:
            barra.mostrar_herramientas(not minimo)          # el tamaño del párrafo y «Generar» se quedan siempre
        if hasattr(self, 'mas_btn'):
            self.mas_btn.configure(text=tr('Más herramientas') if minimo else tr('Menos herramientas'))
    def ajustar_densidad(self, nivel):
        """v5.2: en pantallas chicas la columna de la derecha cede sitio a las palabras."""
        try:
            self._derecha.setFixedWidth({0: 400, 1: 380, 2: 370}.get(nivel, 400))
        except Exception:
            pass
    def _alternar_editor_minimo(self):
        self._poner_editor_minimo(not getattr(self, '_editor_minimo', True))
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'editor_minimo': self._editor_minimo})
        except Exception:
            pass
    def _guardar_para_deshacer(self, manual=True):
        """Guarda el estado antes de un cambio: historial de deshacer, vaciado
        de la pila de rehacer (se abre una rama nueva) y autoguardado. manual=True: es un cambio del usuario (ya no se reajusta solo)."""
        if manual:
            self._roles_auto = False
            self._alternativas = None
        self._historial.append(self._instantanea())
        if len(self._historial) > MAX_HISTORIAL:
            self._historial.pop(0)
        self._rehacer_pila.clear()
        self._refrescar_botones_historial()
        self._programar_autoguardado()
    def _deshacer(self):
        if not self._historial:
            return
        self._rehacer_pila.append(self._instantanea())
        if len(self._rehacer_pila) > MAX_HISTORIAL:
            self._rehacer_pila.pop(0)
        self._restaurar(self._historial.pop())
    def _rehacer(self):
        if not self._rehacer_pila:
            return
        self._historial.append(self._instantanea())
        if len(self._historial) > MAX_HISTORIAL:
            self._historial.pop(0)
        self._restaurar(self._rehacer_pila.pop())
    def _refrescar_botones_historial(self):
        """Apaga las flechas cuando no queda nada que deshacer o rehacer."""
        for boton, pila in [(getattr(self, 'deshacer_btn', None), self._historial), (getattr(self, 'rehacer_btn', None), self._rehacer_pila)]:
            if boton is not None:
                try:
                    boton.configure(state='normal' if pila else 'disabled')
                except Exception:
                    pass
    def _programar_autoguardado(self):
        """Guarda en disco un rato despues del ultimo cambio (marcar
        arrastrando dispara decenas de cambios por segundo: se escribe una
        sola vez cuando la mano para)."""
        if not self.project_name:
            cancelar(getattr(self, '_orto_auto_id', None))
            if getattr(self, '_orto_pedida', False):
                self._orto_auto_id = despues(1800, lambda: self._revisar_ortografia(silencioso=True), self)
            return None
        cancelar(self._autoguardado_id)
        self._autoguardado_id = despues(1500, self._autoguardar, self)
        cancelar(getattr(self, '_orto_auto_id', None))
        if getattr(self, '_orto_pedida', False):
            self._orto_auto_id = despues(1800, lambda: self._revisar_ortografia(silencioso=True), self)
    def _autoguardar(self):
        """Escribe las marcas sin decir nada. Nunca interrumpe al usuario
        (cerrar sin querer borraba TODO el trabajo de marcar)."""
        self._autoguardado_id = None
        if not self.project_name:
            return
        try:
            guardar_marcas(self.project_name, self.palabras, self.roles)
        except Exception:
            return
        else:
            self._avisar_guardado()
    def _avisar_guardado(self):
        """Deja constancia en pantalla de que ya esta a salvo."""
        chip = getattr(self, 'guardado_chip', None)
        if chip is None:
            return
        try:
            chip.poner(texto=tr('Guardado automáticamente ✓'), lleno=True)
            despues(2500, lambda: chip.poner(texto=tr('Autoguardado activo'), lleno=False) if vivo(chip) else None, self)
        except Exception:
            return None
    def esperar(self):
        """No vuelve hasta que se pulse Continuar o Cancelar (el modal de la
        v4: aqui con un bucle de eventos propio, la ventana sigue viva)."""
        if self._cerrando:
            return self.result
        self._bucle = QEventLoop()
        self._bucle.exec()
        self._bucle = None
        return self.result
    def _build_ui(self):
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(14)
        self.brush_var = StringVar(tr('Principal'))
        self.seleccion_var = BooleanVar(False)
        # v5.0.0: las dos barras de arriba SALTAN DE LINEA si no caben (una
        # ventana angosta aplastaba los botones hasta dejarlos ilegibles).
        fila1 = QWidget()
        cf1 = ui.FlujoCapa(fila1, 10, 10)
        if self.modo == self.MODO_MARCAS:
            import emojis
            self.brush_btn = PincelesBar(self, valores=list(self.BRUSH_TO_ROLE.keys()) + ([self.EMOJI_BRUSH] if emojis.catalogo() else []), teclas={tr('Arriba'): '1', tr('Principal'): '2', tr('Abajo'): '3', tr('Simple'): '4', self.EMOJI_BRUSH: '5'}, colores={tr('Arriba'): self.ROLE_COLOR['context'], tr('Principal'): self.ROLE_COLOR['main'], tr('Abajo'): self.ROLE_COLOR['complement'], tr('Simple'): ui.ROL_BASE, self.EMOJI_BRUSH: '#7F8DA8'}, variable=self.brush_var, command=self._on_brush_change)
            cf1.addWidget(self.brush_btn)
            if getattr(self, '_guion', False):
                # v5.10: con el estilo «guion» (palabra a palabra) cada pincel tiene otro papel
                ayudas_pinceles = [(tr('Arriba'), tr('Palabra pequeña en letra FINA. Úsalo para que una palabra NO salga en negrita.')),
                                   (tr('Principal'), tr('La palabra GRANDE del bloque (varias seguidas = una sola palabra grande). El estilo del bloque se elige en la vista de la derecha.')),
                                   (tr('Abajo'), tr('Palabra pequeña en NEGRITA (la que se resalta en su línea).')),
                                   (tr('Simple'), tr('Sin marca: lo decide el planificador, igual que GO (la palabra grande por su peso, la negrita por el ritmo).')),
                                   (self.EMOJI_BRUSH, tr('Un clic elige el emoji de esa palabra (también: clic sobre el emoji, o clic derecho).'))]
            else:
                ayudas_pinceles = [(tr('Arriba'), tr('Las palabras que van ANTES de la principal (arriba).')), (tr('Principal'), tr('La palabra grande del bloque: una sola, con verbo si lo hay.')), (tr('Abajo'), tr('Las palabras que van DESPUÉS de la principal (abajo).')), (tr('Simple'), tr('Subtítulo simple: sin marca.')), (self.EMOJI_BRUSH, tr('Un clic elige el emoji de esa palabra (también: clic sobre el emoji, o clic derecho).'))]
            for valor, ayuda in ayudas_pinceles:
                b = self.brush_btn.boton(valor)
                if b is not None:
                    Tooltip(b, ayuda)
        else:
            self.CORTE_BRUSH = tr('✂ Cortar')
            self.corte_var = StringVar(self.EDIT_BRUSH)
            self.corte_btn = Segmentado([self.EDIT_BRUSH, self.CORTE_BRUSH], self.corte_var, self._on_corte_change, alto=36)
            cf1.addWidget(self.corte_btn)
            pista = Etiqueta(tr('⏎ tu corte  ·  · corte automático'), 13, color=TEXT_MUTED)
            pista.setFixedHeight(36)
            cf1.addWidget(pista)
            Tooltip(pista, tr('Con «✂ Cortar», cada clic en una palabra marca que el bloque termina ahí (⏎); otro clic lo quita. Los puntos tenues son los cortes automáticos según «Palabras por bloque». También con clic derecho.'))
        chips, cch = caja_h(espacio=8, margenes=(14, 4, 0, 4))
        if self.modo == self.MODO_MARCAS:
            self.ia_btn = Chip(tr('Asistencia'), ui.ACCENT_CLARO, self._sugerir_con_ia, alto=28)
            Tooltip(self.ia_btn, tr('En un clic la asistencia corrige el texto, quita puntos, comillas y signos, marca las palabras que cargan el mensaje y pone los emojis. Otra pulsación = otra versión; Ctrl+Z deshace.'))
            cch.addWidget(self.ia_btn)
        self.orto_btn = Chip(tr('Revisar ortografía'), ui.ACCENT_CLARO, self._revisar_ortografia, alto=28)
        self.guardado_chip = None          # el autoguardado sigue activo, pero ya no se muestra el aviso
        # v5.1 (pedido: «el editor por palabras más minimalista»): lo de
        # siempre queda a un clic en «Más herramientas»
        self.mas_btn = Chip(tr('Más herramientas'), '#7F8DA8', self._alternar_editor_minimo, alto=28)
        cch.addWidget(self.mas_btn)
        cf1.addWidget(chips)
        capa.addWidget(fila1)
        import editor_ui
        herr = editor_ui.BarraHerramientas()           # v5.7: una barra de cristal con las herramientas en grupos
        ch = herr
        estilo_boton = dict(alto=34, tam=13, tipo='fantasma')
        if self.modo == self.MODO_MARCAS:
            self.marcar_todo_btn = Boton(tr('Marcar todo'), self._marcar_todo, **estilo_boton)
            ch.addWidget(self.marcar_todo_btn)
            Tooltip(self.marcar_todo_btn, tr('Pinta TODAS las palabras con el pincel elegido arriba'))
        self.puntuacion_btn = Boton(tr('Sin , .'), lambda: self._quitar_puntuacion(self.PUNT_PAUSAS), **estilo_boton)
        ch.addWidget(self.puntuacion_btn)
        Tooltip(self.puntuacion_btn, tr('Quita puntos, comas, comillas y paréntesis. Los ¿? ¡! se quedan.'))
        self.signos_btn = Boton(tr('Sin ¿? ¡!'), lambda: self._quitar_puntuacion(self.PUNT_SIGNOS), **estilo_boton)
        ch.addWidget(self.signos_btn)
        Tooltip(self.signos_btn, tr('Quita solo los signos de pregunta y exclamación. Puntos y comas se quedan.'))
        self._CASOS = {tr('Original'): 'Original', tr('MAYÚSCULAS'): 'MAYÚSCULAS', tr('minúsculas'): 'minúsculas'}
        self.caso_var = StringVar(tr('Original'))
        self.caso_btn = Combo(list(self._CASOS), self.caso_var, self._aplicar_caso, ancho=124, alto=34, tam=13)
        ch.addWidget(self.caso_btn)
        Tooltip(self.caso_btn, tr('Cómo se escriben las palabras en pantalla'))
        ch.separador()
        # v5.4: sin «Reemplazar…», «A−» ni «A+» (pedido); los widgets no se crean
        if self.modo == self.MODO_MARCAS:
            import emojis
            if emojis.catalogo():
                self.emojis_btn = None      # v5.4: sin el boton «✨ Emojis» (pedido); «Asistencia» ya elige los emojis
                self.quitar_emojis_btn = Boton(tr('✕ Emojis'), self._quitar_todos_emojis, **estilo_boton)
                ch.addWidget(self.quitar_emojis_btn)
                Tooltip(self.quitar_emojis_btn, tr('Quita TODOS los emojis del guion de un clic. Ctrl+Z los devuelve.'))
            ch.separador()
            casilla_cap = Interruptor(tr('Capitalizar palabras de contenido'), self.capitalizar_var, self._on_capitalizar_change, tam=13, color='#E8F1FF')
            casilla_cap.setFixedHeight(34)
            Tooltip(casilla_cap, tr('Encendida: cada palabra importante del contexto, la principal y el complemento empieza con mayúscula. Apagada: el texto sale tal cual lo dejaste en la ventana de selección.'))
            ch.addWidget(casilla_cap)
        self.control_tamano = editor_ui.ControlTamano(self.tam_letra, self.TAM_LETRA_RANGO[0], self.TAM_LETRA_RANGO[1], self.TAM_LETRA_DEFECTO, self._poner_tam_letra)
        Tooltip(self.control_tamano, tr('Tamaño de las palabras del párrafo: arrastra para agrandar o achicar.'))
        herr.agregar_fijo(self.control_tamano)
        self.generar_btn = Boton(tr('Generar'), self._continuar, tipo='primario', alto=34, tam=13, negrita=True, ancho=118)
        Tooltip(self.generar_btn, tr('Sigue con tus marcas y genera los subtítulos.'))
        herr.agregar_fijo(self.generar_btn)
        self.herr_barra = herr
        capa.addWidget(herr)
        cuerpo, cc = caja_h(espacio=20)
        lienzo_card = editor_ui.MarcoPapel()
        cl = QVBoxLayout(lienzo_card)
        cl.setContentsMargins(8, 12, 8, 12)
        cl.setSpacing(4)
        self.pista_pincel = editor_ui.PistaPincel()
        cl.addWidget(self.pista_pincel)
        self.pista_pincel.setVisible(self.modo == self.MODO_MARCAS)
        familia = familia_legible()
        # (con el estilo «guion» las palabras «Abajo» van en NEGRITA, no en cursiva: el lienzo las enseña como saldrán)
        self._fuentes = {'base': _fuente_puntos(familia, self.tam_letra), 'main': _fuente_puntos(familia, self.tam_letra, negrita=True),
                         'complement': _fuente_puntos(familia, self.tam_letra, negrita=True) if getattr(self, '_guion', False) else _fuente_puntos(familia, self.tam_letra, italica=True),
                         'tiempo': _fuente_puntos(familia, self.tam_letra - 3)}
        self.lienzo = LienzoPalabras(self._fuentes, self.ROLE_COLOR, ACCENT)
        self.lienzo.FONDO = CARD_COLOR
        self.lienzo.estilo = self.estilo_palabras
        self.lienzo.factor_filas = self.espacio_frases
        self.lienzo.factor_parrafos = self.espacio_parrafos
        self.lienzo.al_clic = self._clic
        self.lienzo.al_doble = self._doble_clic
        self.lienzo.al_arrastrar = self._arrastrar
        self.lienzo.al_soltar = self._soltar
        self.lienzo.al_menu = self._menu_contextual
        self.lienzo.al_hover = self._hover_palabra
        self.lienzo.al_seleccion = self._seleccion_cambio
        self.lienzo.al_sfx = self._menu_sfx
        cl.addWidget(self.lienzo.area, 1)
        self._actualizar_pista_pincel()
        self.atajos_label = Etiqueta((tr('Atajos:  1 fina · 2 GRANDE · 3 negrita · 4 automático · 5 emoji · doble clic corrige la palabra en TODO el texto · Ctrl+Z deshace · Ctrl+Y rehace') if getattr(self, '_guion', False) else tr('Atajos:  1 arriba · 2 principal · 3 abajo · 4 simple · 5 emoji · doble clic corrige la palabra en TODO el texto · Ctrl+Z deshace · Ctrl+Y rehace')) if self.modo == self.MODO_MARCAS else tr('Atajos:  doble clic corrige la palabra en TODO el texto · Ctrl+Z deshace · Ctrl+Y rehace'), 12, color='#5A6B87', envolver=True)
        self.atajos_label.setContentsMargins(14, 0, 14, 0)
        cl.addWidget(self.atajos_label)
        self.ayuda_label = self.atajos_label
        cc.addWidget(lienzo_card, 1)
        derecha = Desplazable(espacio=16, margenes=(0, 0, 8, 0))
        derecha.setFixedWidth(400)
        self._derecha = derecha
        self.tarjeta_bloque = Tarjeta(margenes=(18, 14, 18, 14), espacio=8)
        cab, ccab = caja_h(espacio=8)
        self.tarjeta_bloque.titulo = Etiqueta(tr('Así se verá este bloque'), 16, peso='medio', color='#FFFFFF')
        ccab.addWidget(self.tarjeta_bloque.titulo)
        ccab.addStretch(1)
        self.reproduccion_lbl = Etiqueta('', 12, color=TEXT_MUTED)
        ccab.addWidget(self.reproduccion_lbl)
        self.reproducir_btn = editor_ui.BotonPlay(tr('Reproducir todo'), tr('Detener'), lado=36)
        self.reproducir_btn.clicked.connect(lambda _=False: self._alternar_reproduccion())
        ccab.addWidget(self.reproducir_btn)
        self.tarjeta_bloque.capa.addWidget(cab)
        if getattr(self, '_guion', False):
            import guion_vista
            self.vista_bloque = guion_vista.MarcoVistaGuion(alto_min=200)      # v5.10: el bloque con la geometría real de Resolve
            self.vista_bloque.setFixedHeight(210)
        else:
            self.vista_bloque = MarcoVista(alto_min=150)
            self.vista_bloque.setFixedHeight(156)
        fila_v, cfv = caja_h(espacio=8)
        cfv.addWidget(self.vista_bloque, 1)
        self.mini_pos = editor_ui.MiniPosicion()          # v5.8: dónde cae el bloque en el cuadro del video (arriba / centro / abajo)
        self.mini_pos.setFixedHeight(156)
        self.mini_pos.hide()
        Tooltip(self.mini_pos, tr('Dónde cae este estilo en el cuadro del video. La posición la pone el estilo que elegiste en Proyecto (aproximada).'))
        cfv.addWidget(self.mini_pos)
        self.tarjeta_bloque.capa.addWidget(fila_v)
        fila_b, cfb = caja_h(espacio=8)
        self.tiempo_bloque = Etiqueta('', 13, color=TEXT_MUTED)
        cfb.addWidget(self.tiempo_bloque)
        cfb.addStretch(1)
        self.sfx_bloque = Chip('', ui.ACCENT_CLARO, alto=26, tam=12)
        self.sfx_bloque.hide()
        cfb.addWidget(self.sfx_bloque)
        self.tarjeta_bloque.capa.addWidget(fila_b)
        # v5.8: qué estilo del pack lleva ESTE bloque (lo decide la app, no Resolve) y poder cambiarlo
        self.estilo_w = QWidget()
        ev = QVBoxLayout(self.estilo_w)
        ev.setContentsMargins(0, 2, 0, 0)
        ev.setSpacing(6)
        self.estilo_lbl = Etiqueta('', 13, color='#C9D6EC', envolver=True)
        ev.addWidget(self.estilo_lbl)
        self.estilo_chips_w = QWidget()
        self.estilo_chips = ui.FlujoCapa(self.estilo_chips_w, 6, 6)
        ev.addWidget(self.estilo_chips_w)
        self.estilo_w.hide()
        self.tarjeta_bloque.capa.addWidget(self.estilo_w)
        if getattr(self, '_guion', False):
            # v5.10: la vista rápida es el dibujo exacto; este botón lo comprueba con un render REAL de Resolve (el mismo place_guion_track que Generar)
            self.guion_real_btn = Boton(tr('Comprobar en Resolve (render real)'), self._guion_comprobar_en_resolve, alto=30, tam=12, tipo='fantasma')
            Tooltip(self.guion_real_btn, tr('Resolve coloca ESTE bloque con el mismo script que «Generar» sobre un timeline temporal y te enseña su fotograma real aquí mismo. '
                                            'No toca tu timeline ni tu cola de render.'))
            self.tarjeta_bloque.capa.addWidget(self.guion_real_btn)
        self._bloque_mostrado = None
        self._cache_estilos_pack = None
        self.blocks_label = Etiqueta('', 12, color='#5A6B87')
        self.tarjeta_bloque.capa.addWidget(self.blocks_label)
        derecha.agregar(self.tarjeta_bloque)
        self.tarjeta_orto = Tarjeta(titulo=tr('Revisión de ortografía'), espacio=10)
        fila_o, cfo = caja_h(espacio=8)
        self.orto_estado = Etiqueta('', 13, color=TEXT_MUTED, envolver=True)
        cfo.addWidget(self.orto_estado, 1)
        self.orto_palabra = Enlace('', lambda: self.lienzo.ver(self._orto_actual) if self._orto_actual is not None else None, 14, color=ui.ROJO, color_hover='#FF9B9B', subrayada=False, peso='negrita')
        cfo.addWidget(self.orto_palabra)
        self.tarjeta_orto.capa.addWidget(fila_o)
        self.orto_chips_w = QWidget()
        self.orto_chips = ui.FlujoCapa(self.orto_chips_w, 8, 8)
        self.tarjeta_orto.capa.addWidget(self.orto_chips_w)
        fila_ob, cfob = caja_h(espacio=10)
        self.orto_aplicar = Boton(tr('Aplicar'), self._orto_aplicar, tipo='primario')
        self.orto_ignorar = Boton(tr('Ignorar'), self._orto_ignorar)
        cfob.addWidget(self.orto_aplicar, 1)
        cfob.addWidget(self.orto_ignorar, 1)
        self.orto_botones = fila_ob
        self.tarjeta_orto.capa.addWidget(fila_ob)
        self.tarjeta_ajustes = Tarjeta(titulo=tr('Estilo palabra a palabra') if getattr(self, '_guion', False) else tr('Tamaño del bloque'), espacio=12)
        aj = self.tarjeta_ajustes.capa
        import dynamic_subtitles as dyn
        if self.modo == self.MODO_MARCAS and getattr(self, '_guion', False):
            self._construir_controles_guion(aj, dyn)
        elif self.modo == self.MODO_MARCAS:
            titulo = Etiqueta(tr('Palabras por línea'), 14, peso='negrita', color='#FFFFFF')
            aj.addSpacing(4)
            aj.addWidget(titulo)
            ayuda_t = Etiqueta(tr('El máximo de palabras de cada línea del bloque. Se respeta siempre: si marcas más seguidas, el resto pasa al bloque siguiente.'), 12, color=TEXT_MUTED, envolver=True)
            aj.addWidget(ayuda_t)
            Tooltip(titulo, tr('Cuántas palabras lleva COMO MÁXIMO cada línea del bloque (Arriba / Principal / Abajo). Lo respetan los subtítulos que se generan y la «Asistencia».'))
            self._tamanos_vars = [StringVar(str(v)) for v in self.tamanos]
            self.panel_tamanos = editor_ui.PanelTamanos(self.tamanos, dyn.RANGO_TAMANOS,
                                                        (self.ROLE_COLOR['context'], self.ROLE_COLOR['main'], self.ROLE_COLOR['complement']))
            self.panel_tamanos.cambio.connect(self._al_cambiar_tamano)
            aj.addWidget(self.panel_tamanos)
        self._VISTAS = {tr('Fichas'): 'fichas', tr('Clásica'): 'clasico'}
        self.vista_var = StringVar(next(
            (k for k, v in self._VISTAS.items()
             if v == self.estilo_palabras), tr('Fichas')))
        etiqueta_v = Etiqueta(tr('Vista:'), 13, color='#C9D6EC')        # (v5.4: estos tres controles ya no se muestran)
        Tooltip(etiqueta_v, tr('«Clásica»: las palabras como texto coloreado. «Fichas»: cada palabra marcada en una ficha con su emoji dentro. Se recuerda.'))
        fila_e = QWidget()
        cfe = QGridLayout(fila_e)
        cfe.setContentsMargins(0, 0, 0, 0)
        cfe.setHorizontalSpacing(10)
        cfe.setVerticalSpacing(4)
        self._selector_espacio(cfe)         # se crean (guardan las preferencias) pero no se ponen en pantalla
        derecha.agregar(self.tarjeta_ajustes)
        cc.addWidget(derecha)
        capa.addWidget(cuerpo, 1)
        self._avanzado_editor = [w_ for w_ in (self.guardado_chip, self.tarjeta_ajustes, self.atajos_label) if w_ is not None]
        try:
            import ajustes_ui
            minimo = ajustes_ui.leer_prefs().get('editor_minimo', True) is not False
        except Exception:
            minimo = True
        self._poner_editor_minimo(minimo)
        # v5.7 (pedido: «quita esto y solo deja un botón de generar»): sin la barra de abajo; las notas salen como aviso flotante
        self.avance_lbl = self.avance_barra = self.guardado_label = self.counts_label = _SinBarra()
        self.modo_hint = _AvisoToast(self)
    def _marcar_fin_de_frase(self):
        """Deja anotado en cada palabra si despues de ella termina la frase
        (una sola vez, sobre el texto tal como vino de Whisper; sobrevive a
        quitar los puntos o cambiar a mayusculas)."""
        import dynamic_subtitles as dyn
        total = len(self.palabras)
        for i, w in enumerate(self.palabras):
            if 'fin_frase' in w:
                continue
            siguiente = self.palabras[i + 1] if i + 1 < total else None
            w['fin_frase'] = bool(siguiente is not None and dyn.hay_corte_de_frase(w, siguiente))
    def _llenar_texto(self):
        """(Re)dibuja todas las palabras en el lienzo (cada frase en su fila,
        con su tiempo delante y una fila extra tras un SILENCIO; el corte
        forzado como ⏎ y el automatico como un punto tenue)."""
        self._marcar_fin_de_frase()
        import dynamic_subtitles as dyn
        self.lienzo.capitalizar = bool(self.capitalizar_var.get()) and self.modo == self.MODO_MARCAS
        self.lienzo.dibujar(self.palabras, self.roles, self.dudosas, self._cortes_automaticos(), self.modo, self._mini_emoji, pausa=dyn.PAUSA_SILENCIO)
    @staticmethod
    def _timecode(segundos):
        """\'[1:23]\' — el minuto y segundo donde arranca la frase."""
        return _timecode(segundos)
    def _on_brush_change(self, valor):
        self.modo_edicion = valor == self.EDIT_BRUSH
        self.modo_emoji = valor == self.EMOJI_BRUSH
        if not self.modo_edicion and (not self.modo_emoji):
            self.brush = self.BRUSH_TO_ROLE[valor]
        self._actualizar_pista_pincel()
    def _actualizar_pista_pincel(self):
        """La línea sobre el párrafo: dice qué hace el pincel elegido al tocar una palabra."""
        pista = getattr(self, 'pista_pincel', None)
        if pista is None:
            return
        valor = self.brush_var.get()
        colores = {tr('Arriba'): self.ROLE_COLOR['context'], tr('Principal'): self.ROLE_COLOR['main'], tr('Abajo'): self.ROLE_COLOR['complement']}
        guion = getattr(self, '_guion', False)
        if valor == self.EMOJI_BRUSH:
            texto, color = tr('Toca una palabra para ponerle un emoji. Doble clic corrige la palabra.'), '#F2B84B'
        elif valor == tr('Simple'):
            texto, color = (tr('Toca una palabra para dejarla AUTOMÁTICA (la decide el planificador). Arrastra para elegir varias.') if guion else
                            tr('Toca una palabra para dejarla como texto simple. Arrastra para elegir varias.')), ui.ROL_BASE
        elif guion and valor == tr('Principal'):
            texto, color = tr('Toca una palabra para hacerla la GRANDE del bloque. Arrastra para varias seguidas (una sola palabra grande).'), colores.get(valor, '#8D9BB5')
        elif guion and valor == tr('Abajo'):
            texto, color = tr('Toca una palabra pequeña para ponerla en NEGRITA. Arrastra para elegir varias a la vez.'), colores.get(valor, '#8D9BB5')
        elif guion and valor == tr('Arriba'):
            texto, color = tr('Toca una palabra pequeña para dejarla en letra FINA. Arrastra para elegir varias a la vez.'), colores.get(valor, '#8D9BB5')
        else:
            texto, color = tr('Toca una palabra para pintarla. Arrastra para elegir varias a la vez.'), colores.get(valor, '#8D9BB5')
        pista.poner(valor, color, texto)
    def _marcar_todo(self):
        """Aplica el pincel actual a TODAS las palabras de una sola vez."""
        if self.modo_edicion or self.modo_emoji:
            return None
        self._guardar_para_deshacer()
        self.roles = [self.brush] * len(self.roles)
        self._pintar_todo()
        self._actualizar_contador()
    def _quitar_puntuacion(self, signos=None):
        """Saca signos del principio y del final de todas las palabras (donde
        Whisper los pone). PUNT_PAUSAS o PUNT_SIGNOS; una palabra que quedaria
        vacia se deja como estaba."""
        if signos is None:
            signos = self.PUNTUACION
        self._guardar_para_deshacer()
        for w in self.palabras:
            limpia_orig = w.get('orig', w['word']).strip().strip(signos)
            if limpia_orig:
                w['orig'] = limpia_orig
            limpia = w['word'].strip().strip(signos)
            if limpia:
                w['word'] = limpia
        self._llenar_texto()
        self._actualizar_contador()
    def _aplicar_caso(self, valor):
        """Pasa todo a MAYUSCULAS o a minusculas, siempre desde 'orig' (ir y
        volver no pierde las mayusculas de los nombres propios)."""
        valor = getattr(self, '_CASOS', {}).get(valor, valor)
        self.caso = valor
        for w in self.palabras:
            base = w.get('orig', w['word'])
            if valor == 'MAYÚSCULAS':
                w['word'] = base.upper()
            else:
                if valor == 'minúsculas':
                    w['word'] = base.lower()
                else:
                    w['word'] = base
        self._llenar_texto()
        self._actualizar_contador()
    def _texto_con_caso(self, texto):
        """Aplica el caso elegido a una palabra recien escrita a mano."""
        if self.caso == 'MAYÚSCULAS':
            return texto.upper()
        if self.caso == 'minúsculas':
            return texto.lower()
        return texto
    def _seleccion_cambio(self, indices):
        """v5.4: el lienzo avisa cuando cambia la seleccion de palabras (recuadro, Ctrl+clic, Mayus+clic)."""
        try:
            if len(indices) > 1:
                self.modo_hint.configure(text=tr('{n} palabras seleccionadas · pulsa 1-4 o un pincel para aplicarlo a todas', n=len(indices)), text_color='#8FC7FF', silencio=True)
            else:
                self._on_seleccion_toggle()
        except Exception:
            pass

    def _aplicar_a_seleccion(self, rol):
        """Pinta con ese rol TODAS las palabras seleccionadas (un solo paso de «deshacer»)."""
        sel = self.lienzo.seleccion()
        if not sel or self.modo != self.MODO_MARCAS:
            return
        self._guardar_para_deshacer()
        for i in sel:
            if 0 <= i < len(self.roles):
                self.roles[i] = rol
                self._pintar_palabra(i)
        self._actualizar_contador_pronto()

    def _click_word(self, idx):
        sel = self.lienzo.seleccion()
        if sel:
            if (len(sel) > 1 and idx in sel and self.modo == self.MODO_MARCAS and not self.modo_edicion and not self.modo_emoji):
                self._ultimo_idx = idx
                self._aplicar_a_seleccion(self.brush)
                return
            if idx not in sel:
                self.lienzo.limpiar_seleccion()
        self._ultimo_idx = idx
        if self.modo == self.MODO_TEXTO:
            if self.modo_corte:
                self._alternar_corte(idx)
            else:
                self._editar_palabra(idx)
        else:
            if self.modo_edicion:
                self._editar_palabra(idx)
            else:
                if self.modo_emoji:
                    self._elegir_emoji(idx)
                else:
                    self._poner_rol(idx, self.brush, pintando=True)
    def _poner_rol(self, idx, rol, pintando=False):
        """Pinta un rol (el pincel o el menu de clic derecho). Con 'pintando'
        recuerda la palabra para el arrastre del clic."""
        self._guardar_para_deshacer()
        self._rol_previo = (idx, self.roles[idx])
        if pintando:
            self._pintando = idx
        self.roles[idx] = rol
        self._pintar_palabra(idx)
        self._actualizar_contador_pronto()
    def _actualizar_contador_pronto(self):
        """v5.4: la palabra se colorea al instante, pero contadores, bloques y «Así se verá este bloque» se recalculan
        sobre TODO el texto (~15 ms con 300 palabras, mas con un video largo): pintando de corrido o arrastrando eso iba
        en cada palabra y el clic se notaba pesado. Ahora se hace una vez por rafaga (60 ms despues del ultimo cambio)."""
        self._version += 1
        self._cache_bloques = None
        if self._contador_id is None:
            self._contador_id = despues(60, self._contador_diferido, self)
    def _contador_diferido(self):
        self._contador_id = None
        if not self._cerrando:
            self._actualizar_contador()
    def _alternar_corte(self, idx):
        """Pone o quita el corte forzado tras la palabra (v3.3.1)."""
        self._guardar_para_deshacer()
        w = self.palabras[idx]
        if w.get('corte'):
            w.pop('corte', None)
        else:
            w['corte'] = True
        self._redibujar_manteniendo_vista()
    def _on_corte_change(self, valor):
        self.modo_corte = valor == getattr(self, 'CORTE_BRUSH', None)
        try:
            self.lienzo.setCursor(Qt.CursorShape.CrossCursor if self.modo_corte else Qt.CursorShape.PointingHandCursor)
        except Exception:
            return None
    def _cortes_automaticos(self):
        """Indices donde el agrupado AUTOMATICO del modo normal cierra un
        bloque (v3.3.1): el mismo calculo que despues arma los subtitulos,
        con «Palabras por bloque». Solo en modo texto; deja _n_bloques."""
        self._n_bloques = None
        if self.modo != self.MODO_TEXTO:
            return set()
        try:
            import dynamic_subtitles as dyn
            por_basico = 2
            try:
                por_basico = self.master._palabras_por_basico()
            except AttributeError:
                pass
            bloques = dyn.build_manual_cues(self.palabras, [None] * len(self.palabras), palabras_por_basico=por_basico)
            self._n_bloques = len(bloques)
            por_fin = {}
            for i, w in enumerate(self.palabras):
                try:
                    por_fin[round(float(w.get('end') or 0), 3)] = i
                except (TypeError, ValueError):
                    pass
            fuera = set()
            for b in bloques:
                try:
                    clave = round(float(b.get('fin_hablado') or b.get('end') or 0), 3)
                except (TypeError, ValueError):
                    pass
                else:
                    i = por_fin.get(clave)
                    if i is not None and i + 1 < len(self.palabras) and (not self.palabras[i].get('corte')):
                        fuera.add(i)
            return fuera
        except Exception:
            return set()
    def _menu_contextual(self, evento):
        """Clic derecho sobre una palabra (v3.3.1): emoji, rol, corte y
        editar, sin cambiar de pincel."""
        idx = self._indice_bajo_el_mouse(evento.x, evento.y)
        if idx is None:
            idx = self._palabra_cercana(evento.x, evento.y)
        if idx is None or not 0 <= idx < len(self.palabras):
            return 'break'
        w = self.palabras[idx]
        menu = Menu(self)
        if self.modo == self.MODO_MARCAS:
            import emojis
            if emojis.catalogo():
                menu.agregar(tr('Emoji…'), lambda: self._elegir_emoji(idx))
                if w.get('emoji'):
                    menu.agregar(tr('Quitar emoji'), lambda: self._poner_emoji(idx, None))
                menu.agregar(tr('Mi PNG en esta palabra…'), lambda: self._poner_mi_png(idx))
                eid = w.get('emoji')
                if eid and not str(eid).startswith('mio_'):
                    e = emojis.por_id(eid) or {}
                    menu.agregar(tr('Reemplazar {glifo} por mi PNG…', glifo=e.get('glifo') or eid), lambda: self._reemplazar_emoji_con_png(eid))
                menu.separador()
            sel_ctx = self.lienzo.seleccion()
            for etiqueta, rol in self.BRUSH_TO_ROLE.items():
                if len(sel_ctx) > 1 and idx in sel_ctx:
                    menu.agregar(etiqueta + tr(' ({n} seleccionadas)', n=len(sel_ctx)), lambda r=rol: self._aplicar_a_seleccion(r))
                else:
                    menu.agregar(etiqueta, lambda r=rol: self._poner_rol(idx, r))
            menu.separador()
        menu.agregar(tr('Quitar corte') if w.get('corte') else tr('Cortar después de esta palabra'), lambda: self._alternar_corte(idx))
        menu.agregar(tr('Editar texto…'), lambda: self._editar_palabra(idx))
        menu.mostrar(evento.x_root, evento.y_root)
        return 'break'
    def _colocar_junto_a(self, ventana, idx, ancho, alto):
        """Coloca un dialogo pegado a la palabra idx (v3.3.1; pedido literal:
        «que aparezca sobre la palabra nomás»): debajo, y si no cabe, encima;
        idx None = junto al puntero."""
        panel = hasattr(ventana, 'mostrar_en')
        try:
            caja = None
            if idx is not None:
                self.lienzo.ver(idx)
                caja = self.lienzo.caja_raiz(idx)
            if caja:
                bx, by, _bw, bh = caja
                x = bx
                y_abajo = by + bh + 8
                y_arriba = by - alto - 8
            else:
                puntero = QCursor.pos()
                px, py = (puntero.x(), puntero.y())
                x, y_abajo, y_arriba = (px + 12, py + 12, py - alto - 12)
            if panel:
                origen = self.mapToGlobal(QPoint(0, 0))
                wx, wy = (origen.x(), origen.y())
                ww, wh = (self.width(), self.height())
                x = max(8, min(int(x - wx), ww - ancho - 8))
                if y_abajo - wy + alto <= wh - 8:
                    y = int(y_abajo - wy)
                else:
                    y = max(8, int(y_arriba - wy))
                ventana.mostrar_en(x, y, ancho, alto)
            else:
                pantalla = QGuiApplication.screenAt(QPoint(int(x), int(y_abajo))) or QGuiApplication.primaryScreen()
                area = pantalla.availableGeometry()
                x = max(area.left(), min(int(x), area.right() - ancho - 8))
                y = y_abajo if y_abajo + alto <= area.bottom() - 40 else max(area.top(), y_arriba)
                ventana.colocar(x, y, ancho, alto)
        except Exception:
            try:
                if panel:
                    ventana.mostrar_en(20, 80, ancho, alto)
                else:
                    ventana.resize(int(ancho), int(alto))
            except Exception:
                return
    def _mini_emoji(self, eid):
        """La miniatura del emoji al tamaño de la letra, o None (v5.2: al
        doble de resolucion, el lienzo la reduce: nitida en pantallas HiDPI)."""
        try:
            alto = QFontMetricsF(self._fuentes['main']).lineSpacing()
        except Exception:
            alto = getattr(self, 'tam_letra', 13) * 1.6
        lado = max(28, round(alto * 0.92 * 2)) if self.estilo_palabras == 'fichas' else max(14, round(getattr(self, 'tam_letra', 13) * 1.5))
        clave = (eid, lado)
        if clave not in self._imgs_emoji:
            try:
                import emojis
                self._imgs_emoji[clave] = ui.pixmap_de_archivo(emojis.ruta_mini(eid), lado)
            except Exception:
                self._imgs_emoji[clave] = None
        return self._imgs_emoji[clave]
    def _redibujar_manteniendo_vista(self):
        vista = self.lienzo.vista()
        self._llenar_texto()
        self._actualizar_contador()
        self.lienzo.ir_a(vista)
        despues(0, lambda: self.lienzo.ir_a(vista), self.lienzo)
    def _minis_listas(self):
        """Llega desde el hilo de preparar_minis: repinta el selector si
        esta abierto (en el hilo de la interfaz)."""
        def repintar():
            pop = self._popover
            try:
                if pop is not None and pop.existe():
                    pop._imagenes.clear()
                    pop._pintar()
            except Exception:
                pass
        ejecutar_en_ui(repintar)
    def _cerrar_popover(self):
        pop = self._popover
        self._popover = None
        if pop is not None:
            try:
                if pop.existe():
                    pop.cerrar()
            except Exception:
                pass
    def eventFilter(self, obj, ev):
        """Un clic en cualquier sitio de ESTA pantalla fuera del selector de
        emoji lo cierra (v3.3.2: el _clic_fuera_popover de la v4)."""
        try:
            if ev.type() == QEvent.Type.MouseButtonPress and self._popover is not None:
                if isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj)):
                    g = ev.globalPosition()
                    self._clic_fuera_popover(_EvGlobal(g.x(), g.y()))
        except Exception:
            pass
        return False
    def _clic_fuera_popover(self, evento):
        pop = self._popover
        if pop is None:
            return
        try:
            if pop.existe() and pop.contiene(evento.x_root, evento.y_root):
                return
        except Exception:
            pass
        self._cerrar_popover()
    def _elegir_emoji(self, idx):
        """El selector de emoji de una palabra (v3.3.0): lo abren el pincel
        «Emoji», el clic sobre el emoji de la ficha y el menu de clic
        derecho. Es un panel junto a la ficha, dentro de esta pantalla."""
        w = self.palabras[idx]
        self._cerrar_popover()
        selector = EmojiPickerWindow(self, w.get('word', '').strip(), self.idioma, w.get('emoji'), lambda eid, i=idx: self._poner_emoji(i, eid), idx=idx)
        self._popover = selector
        self._colocar_junto_a(selector, idx, EmojiPickerWindow.ANCHO, EmojiPickerWindow.ALTO)
    def _poner_emoji(self, idx, eid):
        """Pone (o quita, con None) el emoji de una palabra. Un fallo aqui se
        DICE en la pantalla y queda en error_ventana.txt."""
        try:
            actual = self.palabras[idx].get('emoji')
            if (eid or None) == (actual or None):
                return
            self._guardar_para_deshacer()
            if eid:
                self.palabras[idx]['emoji'] = eid
            else:
                self.palabras[idx].pop('emoji', None)
            self._redibujar_manteniendo_vista()
        except Exception as e:
            guardar_log_de_error(traceback.format_exc())
            try:
                self.modo_hint.configure(text=tr('No pude poner el emoji: {e}', e=f'{type(e).__name__}: {e}'), text_color='#FF6B6B')
            except Exception:
                pass
    def _png_del_usuario(self):
        """El dialogo de «Mi PNG» (v3.3.4). None si se cancela."""
        ruta = filedialog.askopenfilename(parent=self, title=tr('Elige tu PNG'), filetypes=[(tr('Imágenes PNG'), '*.png')])
        return ruta or None
    def _refrescar_emojis(self, eid=None):
        """Tras tocar la biblioteca: la mini de ESE archivo, fuera las minis
        cacheadas, redibujar y repintar el selector si esta abierto."""
        import emojis
        if eid:
            try:
                emojis.ruta_mini(eid)
            except Exception:
                pass
        self._imgs_emoji.clear()
        self._redibujar_manteniendo_vista()
        pop = self._popover
        try:
            if pop is not None and pop.existe():
                pop._imagenes.clear()
                pop._pintar()
        except Exception:
            pass
    def _fallo_biblioteca(self, texto):
        """Un fallo de la biblioteca se DICE y queda en error_ventana.txt."""
        guardar_log_de_error(traceback.format_exc())
        try:
            self.modo_hint.configure(text=texto, text_color='#FF6B6B')
        except Exception:
            return None
    def _poner_mi_png(self, idx, ruta=None):
        """«Mi PNG en esta palabra» (v3.3.4): el PNG se copia a la biblioteca
        y queda en esa palabra como un emoji «mio»."""
        import emojis
        ruta = ruta or self._png_del_usuario()
        if not ruta:
            return
        try:
            eid = emojis.guardar_en_biblioteca(ruta)
            emojis.ruta_mini(eid)
        except Exception as e:
            self._fallo_biblioteca(tr('No pude guardar tu PNG: {e}', e=f'{type(e).__name__}: {e}'))
            return
        self._cerrar_popover()
        self._imgs_emoji.clear()
        self._poner_emoji(idx, eid)
    def _reemplazar_emoji_con_png(self, eid, ruta=None):
        """«Reemplazar 🔥 por mi PNG» (v3.3.4): desde ahi tu PNG manda sobre
        la imagen de ese emoji en todas las palabras (y en Resolve)."""
        import emojis
        ruta = ruta or self._png_del_usuario()
        if not ruta:
            return
        try:
            emojis.reemplazar_con_png(eid, ruta)
        except Exception as e:
            self._fallo_biblioteca(tr('No pude usar tu PNG: {e}', e=f'{type(e).__name__}: {e}'))
            return
        self._refrescar_emojis(eid)
        e = emojis.por_id(eid) or {}
        try:
            self.modo_hint.configure(text=tr('Desde ahora {glifo} usa tu PNG en todo el guion. Para volver al original: clic derecho sobre él en el selector.', glifo=e.get('glifo') or eid), text_color='#62D196')
        except Exception:
            pass
    def _quitar_de_biblioteca(self, eid, confirmar=True):
        """«Quitar de mi biblioteca» / «Volver al emoji original» (v3.3.4).
        Se confirma antes; un emoji «mio» borrado se quita tambien de las
        palabras que lo usaban (Ctrl+Z lo devuelve a las palabras)."""
        import emojis
        e = emojis.por_id(eid) or {}
        mio = str(eid).startswith('mio_')
        if confirmar:
            nombre = ((e.get('claves') or {}).get('en') or [eid])[0]
            texto = tr('¿Quitar «{nombre}» de tu biblioteca? Las palabras que lo usan se quedan sin emoji.', nombre=nombre) if mio else tr('¿Volver a la imagen original de {glifo}? Tu PNG se borra de la biblioteca.', glifo=e.get('glifo') or eid)
            if not messagebox.askyesno(tr('Mi biblioteca'), texto, parent=self):
                return
        try:
            emojis.quitar_de_biblioteca(eid)
        except Exception as e:
            self._fallo_biblioteca(tr('No pude quitarlo de la biblioteca: {e}', e=f'{type(e).__name__}: {e}'))
            return
        if mio:
            usan = [i for i, w in enumerate(self.palabras)
                    if w.get('emoji') == eid]
            if usan:
                self._guardar_para_deshacer()
                for i in usan:
                    self.palabras[i].pop('emoji', None)
        self._refrescar_emojis(None if mio else eid)
    def _sugerir_emojis(self):
        """«Emojis»: un emoji para cada PRINCIPAL que no tenga (v3.3.0).
        JAMAS pisa uno elegido a mano; sin nada que aportar no ensucia el
        historial."""
        import emojis
        cambios = {}
        i, n = (0, len(self.palabras))
        while i < n:
            if self.roles[i] != 'main':
                i += 1
                continue
            j = i
            while j + 1 < n and self.roles[j + 1] == 'main':
                j += 1
            tramo = range(i, j + 1)
            if not any((self.palabras[k].get('emoji') for k in tramo)):
                for k in tramo:
                    ids = emojis.sugerir(self.palabras[k].get('word', ''), self.idioma)
                    if ids:
                        cambios[k] = ids[0]
                        break
            i = j + 1
        if not cambios:
            self.modo_hint.configure(text=tr('No encontré un emoji claro para tus principales. Elige uno a mano con el pincel «Emoji» (tecla 6).'), text_color='#F2C14E')
            return
        self._guardar_para_deshacer()
        for k, eid in cambios.items():
            self.palabras[k]['emoji'] = eid
        self._redibujar_manteniendo_vista()
        self.modo_hint.configure(text=tr('Puse {len} emoji(s) en tus principales. Cámbialos con el pincel «Emoji»; Ctrl+Z los quita.', len=len(cambios)), text_color='#62D196')
    def _quitar_todos_emojis(self):
        """«✕ Emojis» (v3.4.0): fuera todos los emojis, en UN paso de
        deshacer."""
        con = [i for i, w in enumerate(self.palabras) if w.get('emoji')]
        if not con:
            self.modo_hint.configure(text=tr('No hay emojis que quitar.'), text_color='#F2C14E')
            return
        self._guardar_para_deshacer()
        for i in con:
            self.palabras[i].pop('emoji', None)
        self._cerrar_popover()
        self._redibujar_manteniendo_vista()
        self.modo_hint.configure(text=tr('Quité {n} emoji(s). Ctrl+Z los devuelve.', n=len(con)), text_color='#62D196')
    def _indice_bajo_el_mouse(self, x, y):
        """Que palabra hay EXACTAMENTE en esa coordenada del lienzo, o None."""
        try:
            return self.lienzo.indice_en(x, y, 0)
        except Exception:
            return None
    TOLERANCIA_CLIC_PX = 14
    TAM_LETRA_DEFECTO = 13
    TAM_LETRA_RANGO = (11, 24)
    @classmethod
    def _tam_letra_valido(cls, valor):
        """El tamaño de letra dentro del rango; cualquier rareza, 13."""
        try:
            n = int(valor)
        except (TypeError, ValueError):
            return cls.TAM_LETRA_DEFECTO
        return min(cls.TAM_LETRA_RANGO[1], max(cls.TAM_LETRA_RANGO[0], n))
    def _tolerancia_clic(self):
        tam = getattr(self, 'tam_letra', self.TAM_LETRA_DEFECTO)
        return round(self.TOLERANCIA_CLIC_PX * tam / self.TAM_LETRA_DEFECTO)
    def _aplicar_tam_letra(self):
        for clave, f in self._fuentes.items():
            f.setPointSizeF(float(self.tam_letra - 3 if clave == 'tiempo' else self.tam_letra))
        if getattr(self, 'lienzo', None) is not None:
            self._imgs_emoji.clear()
            self._redibujar_manteniendo_vista()
    def _poner_tam_letra(self, n):
        """El deslizador del párrafo: aplica el tamaño (junta el vaivén del arrastre) y lo recuerda un momento después."""
        nuevo = self._tam_letra_valido(n)
        if nuevo == self.tam_letra:
            return
        self.tam_letra = nuevo
        cancelar(getattr(self, '_id_tam_letra', None))
        self._id_tam_letra = despues(45, self._aplicar_tam_letra, self)
        cancelar(getattr(self, '_id_guardar_tam', None))
        def _guardar():
            try:
                self.master.tam_letra_palabras = self.tam_letra
                self.master._guardar_preferencias()
            except Exception:
                return None
        self._id_guardar_tam = despues(700, _guardar, self)
    def _cambiar_tam_letra(self, paso):
        """A− / A+ (v3.3.0). Se recuerda en la App SOLO al tocarlo."""
        nuevo = self._tam_letra_valido(self.tam_letra + paso)
        if nuevo == self.tam_letra:
            return
        self.tam_letra = nuevo
        self._aplicar_tam_letra()
        try:
            self.master.tam_letra_palabras = nuevo
            self.master._guardar_preferencias()
        except Exception:
            return None
    def _palabra_cercana(self, x, y):
        """La palabra a menos de TOLERANCIA_CLIC_PX del punto, o None."""
        try:
            return self.lienzo.indice_en(x, y, self._tolerancia_clic())
        except Exception:
            return None
    def _clic(self, evento):
        """Un clic en el lienzo: sobre la ✕ quita el emoji; sobre el EMOJI
        abre su selector con cualquier pincel; sobre una palabra —o a un
        pelo de ella— es el clic de siempre; sobre el vacio, nada."""
        if self.modo == self.MODO_MARCAS:
            q = self.lienzo.quitar_en(evento.x, evento.y)
            if q is not None:
                self._poner_emoji(q, None)
                return 'break'
            e = self.lienzo.emoji_en(evento.x, evento.y)
            if e is not None:
                self._ultimo_idx = e
                self._elegir_emoji(e)
                return 'break'
        idx = self._palabra_cercana(evento.x, evento.y)
        if idx is None:
            return None
        self._click_word(idx)
        if self._contador_id is None:        # v5.4: si se acaba de pintar, la vista previa del bloque la rehace el recalculo agrupado
            self._mostrar_bloque(idx)
        return None
    def _doble_clic(self, evento):
        """El doble clic tambien perdona el pelo de distancia."""
        idx = self._palabra_cercana(evento.x, evento.y)
        if idx is not None:
            self._doble_click_word(idx)
        return 'break'
    def _on_seleccion_toggle(self):
        """Prende o apaga el marcado por arrastre y lo explica en pantalla."""
        if self.seleccion_var.get():
            self.lienzo.setCursor(Qt.CursorShape.CrossCursor)
            self.modo_hint.configure(text=tr('Arrastra para marcar varias'), text_color='#8FC7FF', silencio=True)
        else:
            self.lienzo.setCursor(Qt.CursorShape.PointingHandCursor)
            self.modo_hint.configure(text=tr('Un clic marca una palabra'), text_color='gray60', silencio=True)
    def _arrastrar(self, evento):
        """Arrastrar con el boton apretado va marcando las palabras que toca
        (solo al ENTRAR a una palabra distinta)."""
        if not self.seleccion_var.get():
            return
        if self.modo_edicion or self.modo_emoji or self._pintando is None:
            return None
        idx = self._indice_bajo_el_mouse(evento.x, evento.y)
        if idx is None or idx == self._pintando:
            return None
        self._pintando = idx
        self.roles[idx] = self.brush
        self._pintar_palabra(idx)
        self._actualizar_contador_pronto()      # v5.4: una vez por rafaga, no por cada palabra que toca el arrastre
    def _soltar(self, _evento=None):
        self._pintando = None
    def _doble_click_word(self, idx):
        """Doble clic sobre una palabra: corregirla, con cualquier pincel (el
        clic simple llega antes que el doble: primero se deshace su marca)."""
        if self._rol_previo and self._rol_previo[0] == idx:
            self.roles[idx] = self._rol_previo[1]
            self._pintar_palabra(idx)
            self._actualizar_contador()
            self._rol_previo = None
        if not self.modo_edicion:
            self._editar_palabra(idx)
        return 'break'
    def _reemplazar_masivo(self):
        """Buscar → reemplazar en TODA la transcripcion (v1.0.60): compara el
        NUCLEO sin puntuacion ni mayusculas, conserva la puntuacion de CADA
        aparicion, respeta el caso elegido y un Ctrl+Z lo revierte entero."""
        dlg = Dialogo(self, tr('Reemplazar en toda la transcripción'))
        self._colocar_junto_a(dlg, None, 460, 250)
        capa = _capa_dialogo(dlg, (22, 20, 22, 18), 10)
        capa.addWidget(_titulo(tr('Reemplazar en toda la transcripción'), 16))
        var_buscar = StringVar()
        var_nueva = StringVar()
        entradas = []
        for etiqueta, var in [(tr('Palabra a buscar:'), var_buscar), (tr('Reemplazar por:'), var_nueva)]:
            f, cf = caja_h(espacio=10)
            nombre = Etiqueta(etiqueta, 13)
            nombre.setFixedWidth(140)
            cf.addWidget(nombre)
            entrada = Entrada(var, alto=38)
            cf.addWidget(entrada, 1)
            entradas.append(entrada)
            capa.addWidget(f)
        aviso = Etiqueta('', 12, color='#E0A030')
        capa.addWidget(aviso)
        def cerrar():
            dlg.cerrar()
        def aplicar():
            buscada = ortografia.limpiar(var_buscar.get()).lower()
            nucleo_nuevo = ortografia.limpiar(var_nueva.get())
            if not buscada or not nucleo_nuevo:
                aviso.configure(text=tr('Escribe la palabra y su reemplazo.'))
                return
            indices = [i for i, w in enumerate(self.palabras)
                       if ortografia.limpiar(w['word']).lower() == buscada]
            if not indices:
                aviso.configure(text=tr('No encontré «{strip}».', strip=var_buscar.get().strip()))
                return
            self._guardar_para_deshacer()
            for i in indices:
                base_i = self.palabras[i].get('orig', self.palabras[i]['word'])
                self.palabras[i]['orig'] = ortografia.aplicar(base_i, nucleo_nuevo)
                self.palabras[i]['word'] = self._texto_con_caso(ortografia.aplicar(self.palabras[i]['word'], nucleo_nuevo))
                self.dudosas.discard(i)
            self._llenar_texto()
            self._actualizar_contador()
            self._pintar_orto()
            try:
                self.modo_hint.configure(text=tr('Reemplacé 1 aparición de «{buscada}».', buscada=buscada) if len(indices) == 1 else tr('Reemplacé {len} apariciones de «{buscada}».', len=len(indices), buscada=buscada), text_color='#62D196')
            except Exception:
                pass
            cerrar()
        for entrada in entradas:
            entrada.returnPressed.connect(aplicar)
        botones, cb = caja_h(espacio=10, margenes=(0, 8, 0, 0))
        cb.addWidget(Boton(tr('Reemplazar todas'), aplicar, tipo='primario'))
        cb.addStretch(1)
        cb.addWidget(Boton(tr('Cancelar'), cerrar, tipo='neutro', ancho=100))
        capa.addWidget(botones)
        entradas[0].setFocus()
        dlg.exec()
    def _editar_palabra(self, idx):
        """Ventanita para corregir el texto de una palabra, o borrarla. El
        tiempo de la palabra no se toca."""
        es_dudosa = idx in self.dudosas
        dlg = Dialogo(self, tr('Editar palabra'))
        alto = 220 + (64 if es_dudosa else 0)
        if any(i != idx and ortografia.limpiar(w['word']).lower() ==
               ortografia.limpiar(self.palabras[idx]['word']).lower()
               and ortografia.limpiar(w['word'])
               for i, w in enumerate(self.palabras)):
            alto += 36
        self._colocar_junto_a(dlg, idx, 440, alto)
        capa = _capa_dialogo(dlg, (22, 20, 22, 18), 6)
        capa.addWidget(Etiqueta(tr('Corrige el texto de esta palabra:'), 15, peso='medio'))
        capa.addWidget(Etiqueta(tr('El tiempo no cambia: sigue apareciendo cuando se dice.'), 13, color=TEXT_MUTED))
        capa.addSpacing(6)
        var = StringVar(self.palabras[idx]['word'].strip())
        entry = Entrada(var, alto=40)
        capa.addWidget(entry)
        nucleo = ortografia.limpiar(self.palabras[idx]['word']).lower()
        iguales = [i for i, w in enumerate(self.palabras)
                   if i != idx and nucleo and ortografia.limpiar(w['word']).lower() == nucleo]
        var_todas = BooleanVar(bool(iguales))
        if iguales:
            n = len(iguales)
            capa.addSpacing(4)
            capa.addWidget(Casilla(tr('Cambiar también la otra igual en toda la transcripción') if n == 1 else tr('Cambiar también las otras {n} iguales en toda la transcripción', n=n), var_todas, tam=13))
        def cerrar():
            dlg.cerrar()
        def guardar(_evento=None):
            nuevo = var.get().strip()
            cerrar()
            if nuevo and nuevo != self.palabras[idx]['word'].strip():
                self._guardar_para_deshacer()
                self.palabras[idx]['orig'] = nuevo
                self.palabras[idx]['word'] = self._texto_con_caso(nuevo)
                self.dudosas.discard(idx)
                nucleo_nuevo = ortografia.limpiar(nuevo)
                cambiadas = 1
                if var_todas.get() and nucleo_nuevo:
                    cambiadas += len(iguales)
                    for i in iguales:
                        base_i = self.palabras[i].get('orig', self.palabras[i]['word'])
                        self.palabras[i]['orig'] = ortografia.aplicar(base_i, nucleo_nuevo)
                        self.palabras[i]['word'] = self._texto_con_caso(ortografia.aplicar(self.palabras[i]['word'], nucleo_nuevo))
                        self.dudosas.discard(i)
                self._llenar_texto()
                self._actualizar_contador()
                self._pintar_orto()
                if cambiadas > 1:
                    try:
                        self.modo_hint.configure(text=tr('«{nuevo}» reemplazada en {cambiadas} sitios del texto.', nuevo=nuevo, cambiadas=cambiadas), text_color='#62D196')
                    except Exception:
                        return None
        if es_dudosa:
            fila_sug, cfs = caja_h(espacio=6, margenes=(0, 8, 0, 0))
            cfs.addWidget(Etiqueta(tr('¿Querías decir?'), 13, color='#FFB86B'))
            sugerencias = ortografia.sugerencias_para(self.palabras[idx]['word'], self.idioma, maximo=3)
            if not sugerencias:
                cfs.addWidget(Etiqueta(tr('(no se me ocurre nada mejor)'), 13, color=TEXT_MUTED))
            def _usar_sugerencia(propuesta):
                """Corrige con esa palabra y guarda, sin un segundo clic."""
                var.set(ortografia.aplicar(self.palabras[idx]['word'], propuesta))
                guardar()
            for propuesta in sugerencias:
                cfs.addWidget(Chip(propuesta, ui.VERDE, lambda p=propuesta: _usar_sugerencia(p), alto=28))
            cfs.addStretch(1)
            capa.addWidget(fila_sug)
        def borrar():
            cerrar()
            if len(self.palabras) <= 1:
                messagebox.showwarning(tr('No se puede'), tr('Tiene que quedar al menos una palabra.'), parent=self)
                return
            self._guardar_para_deshacer()
            if self.palabras[idx].get('fin_frase') and idx > 0:
                self.palabras[idx - 1]['fin_frase'] = True
            if self.palabras[idx].get('corte') and idx > 0:
                self.palabras[idx - 1]['corte'] = True
            del self.palabras[idx]
            del self.roles[idx]
            self.dudosas = {i if i < idx else i - 1
                            for i in self.dudosas if i != idx}
            self._llenar_texto()
            self._actualizar_contador()
            self._pintar_orto()
        entry.returnPressed.connect(guardar)
        fila, cf = caja_h(espacio=10, margenes=(0, 14, 0, 0))
        cf.addWidget(Boton(tr('Cancelar'), cerrar, tipo='neutro', ancho=96))
        cf.addWidget(Boton(tr('Borrar palabra'), borrar, tipo='peligro', ancho=130))
        cf.addStretch(1)
        cf.addWidget(Boton(tr('Guardar'), guardar, tipo='primario', ancho=110))
        capa.addWidget(fila)
        entry.setFocus()
        entry.selectAll()
        dlg.exec()
    def _pintar_palabra(self, idx):
        rol = self.roles[idx] if self.modo == self.MODO_MARCAS else None
        self.lienzo.pintar(idx, rol, idx in self.dudosas, self.modo)
    def _revisar_ortografia(self, silencioso=False):
        """Subraya las palabras que el diccionario no conoce (en un hilo:
        cargar el diccionario la primera vez tarda). 'silencioso' es el
        re-barrido AUTOMATICO tras editar: mismo trabajo, sin dialogos."""
        if not ortografia.idioma_soportado(self.idioma):
            if not silencioso:
                messagebox.showinfo(tr('Sin diccionario'), tr('No tengo diccionario para el idioma elegido, así que no puedo revisar la ortografía.\n\nLos subtítulos se generan igual: esto solo afecta al subrayado.'), parent=self)
            return None
        if not silencioso:
            self._orto_pedida = True
            self.orto_btn.configure(state='disabled', text=tr('Revisando...'))
        palabras = [dict(w) for w in self.palabras]
        idioma = self.idioma
        resultado = {}
        def _trabajar():
            try:
                resultado['dudosas'] = ortografia.revisar(palabras, idioma)
            except Exception as e:
                resultado['error'] = str(e)
        hilo = threading.Thread(target=_trabajar, daemon=True)
        hilo.start()
        def _revisar_hilo():
            if hilo.is_alive():
                despues(120, _revisar_hilo, self)
                return
            if resultado.get('error'):
                if not silencioso:
                    self.orto_btn.configure(state='normal', text=tr('Revisar ortografía'))
                    messagebox.showerror(tr('No pude revisar'), tr('La revisión ortográfica falló:\n\n{v}', v=resultado['error']), parent=self)
                return None
            self.dudosas = {i for i in resultado.get('dudosas', set())
                            if i < len(self.palabras)}
            self._pintar_todo()
            self._pintar_orto()
            if not silencioso or self.dudosas:
                self.modo_hint.configure(text=ortografia.resumen(self.dudosas, len(self.palabras)), text_color='#FFB86B' if self.dudosas else '#62D196')
            if not silencioso:
                self._corregir_ahora()          # v5.4: con un clic se analiza TODO y se corrige al momento
        despues(120, _revisar_hilo, self)
    def _corregir_auto(self):
        """v5.4: al abrir el editor se corrige solo la ortografia (sin botones). No si se reabren marcas ya retocadas."""
        if self._cerrando or getattr(self, '_corrigio_auto', False) or getattr(self.master, '_reusando', False):
            return
        self._corrigio_auto = True
        self._corregir_ahora()
    def _corregir_ahora(self):
        """v5.4 (pedido: «con un clic analice todo y lo corrija inmediato»): la IA de texto local (Qwen3) corrige TODA la
        transcripcion palabra por palabra (mismos tiempos); sin IA instalada se aplica la mejor sugerencia del diccionario
        a cada palabra dudosa. Un solo paso de «deshacer» (Ctrl+Z) lo revierte."""
        idioma = self.idioma if self.idioma not in (None, '', 'auto') else 'es'
        base = [dict(w) for w in self.palabras]
        resultado = {}
        self.modo_hint.configure(text=tr('Corrigiendo la ortografía con IA…'), text_color='#8FC7FF')

        def _trabajar():
            try:
                import ia_texto
                if ia_texto.disponible():
                    cambios = dict(ia_texto.correcciones_ortografia(base, idioma))      # solo de ortografia, y solo los trozos nuevos (el resto sale del guardado)
                    resultado['via'] = 'IA'
                    try:
                        for i, nueva in ortografia.corregir_fonetico(base, idioma).items():     # lo que la IA dejo y suena igual que otra palabra
                            cambios.setdefault(i, nueva)
                    except Exception:
                        pass
                else:
                    cambios = {}
                    resultado['via'] = 'diccionario'
                    cambios = ortografia.corregir_fonetico(base, idioma)      # sin IA: diccionario + fonetica del español
                resultado['cambios'] = cambios
            except Exception as e:
                resultado['error'] = f'{type(e).__name__}: {e}'
                resultado['cambios'] = {}

        hilo = threading.Thread(target=_trabajar, daemon=True)
        hilo.start()

        def _fin():
            if not vivo(self) or self._cerrando:
                return
            if hilo.is_alive():
                despues(150, _fin, self)
                return
            cambios = {}
            for i, texto in (resultado.get('cambios') or {}).items():
                texto = str(texto).strip()
                if 0 <= i < len(self.palabras) and texto and texto != self.palabras[i]['word'].strip():
                    cambios[i] = texto
            if cambios:
                self._guardar_para_deshacer()
                for i, texto in cambios.items():
                    self.palabras[i]['word'] = texto
                    self.dudosas.discard(i)
                self._llenar_texto()
                self._actualizar_contador()
                self._pintar_orto()
                self.modo_hint.configure(text=tr('✓ {n} correcciones aplicadas ({via}) · Ctrl+Z las deshace', n=len(cambios), via=resultado.get('via') or ''), text_color='#62D196')
                registro.info('Ortografía: ' + ', '.join(f"{a!r}→{b!r}" for a, b in [(base[i]['word'], t) for i, t in list(cambios.items())[:12]]) + (' …' if len(cambios) > 12 else ''), f"ortografía ({resultado.get('via')})")
            elif resultado.get('error'):
                self.modo_hint.configure(text=tr('No pude corregir: {e}', e=resultado['error']), text_color='#FF6B6B')
                registro.error('La corrección de ortografía falló: ' + str(resultado['error']), 'ortografía')
            else:
                self.modo_hint.configure(text=tr('✓ Todo está bien escrito: no hay nada que corregir.'), text_color='#62D196')
        despues(150, _fin, self)

    def _pintar_orto(self):
        """La tarjeta «Revisión de ortografía» (v5.0.0, imagen 03): la
        primera palabra dudosa, sus sugerencias, Aplicar e Ignorar. Aplicar
        hace lo mismo que la sugerencia del dialogo de editar palabra (con
        «cambiar tambien las otras iguales»)."""
        limpiar_capa(self.orto_chips)
        self.orto_palabra.configure(text='')
        self.orto_botones.hide()
        if not ortografia.idioma_soportado(self.idioma):
            self.orto_estado.configure(text=tr('No hay diccionario para el idioma elegido, así que no puedo revisar la ortografía. Los subtítulos se generan igual.'), text_color=TEXT_MUTED)
            self.orto_btn.setEnabled(False)
            return
        if not self._orto_pedida:
            self.orto_estado.configure(text=tr('Pulsa «Revisar ortografía» para subrayar las palabras que el diccionario no conoce. Nunca cambia nada solo.'), text_color=TEXT_MUTED)
            return
        if not self.dudosas:
            self._orto_actual = None
            self.orto_estado.configure(text=tr('✓ Ninguna palabra dudosa.'), text_color=ui.VERDE)
            return
        if self._orto_actual not in self.dudosas:
            self._orto_actual = min(self.dudosas)
        idx = self._orto_actual
        n = len(self.dudosas)
        self.orto_estado.configure(text=tr('1 palabra dudosa:') if n == 1 else tr('{n} palabras dudosas:', n=n), text_color='#C9D6EC')
        self.orto_palabra.configure(text=self.palabras[idx]['word'].strip())
        sugerencias = ortografia.sugerencias_para(self.palabras[idx]['word'], self.idioma, maximo=3)
        self._orto_sugerencias = sugerencias
        if self._orto_eleccion not in sugerencias:
            self._orto_eleccion = sugerencias[0] if sugerencias else None
        for propuesta in sugerencias:
            chip = Chip(propuesta, ui.VERDE, lambda p=propuesta: self._orto_elegir(p), alto=28, lleno=propuesta == self._orto_eleccion)
            self.orto_chips.addWidget(chip)
        if not sugerencias:
            self.orto_chips.addWidget(Etiqueta(tr('(no se me ocurre nada mejor)'), 12, color=TEXT_MUTED))
        self.orto_botones.show()
        self.orto_aplicar.setEnabled(bool(sugerencias))
    def _orto_elegir(self, propuesta):
        self._orto_eleccion = propuesta
        self._pintar_orto()
    def _orto_aplicar(self):
        idx = self._orto_actual
        propuesta = self._orto_eleccion
        if idx is None or not propuesta or not 0 <= idx < len(self.palabras):
            return
        nucleo = ortografia.limpiar(self.palabras[idx]['word']).lower()
        iguales = [i for i, w in enumerate(self.palabras)
                   if nucleo and ortografia.limpiar(w['word']).lower() == nucleo]
        self._guardar_para_deshacer()
        for i in iguales:
            base_i = self.palabras[i].get('orig', self.palabras[i]['word'])
            self.palabras[i]['orig'] = ortografia.aplicar(base_i, propuesta)
            self.palabras[i]['word'] = self._texto_con_caso(ortografia.aplicar(self.palabras[i]['word'], propuesta))
            self.dudosas.discard(i)
        self._orto_eleccion = None
        self._llenar_texto()
        self._actualizar_contador()
        self._pintar_orto()
        self.modo_hint.configure(text=tr('«{nuevo}» reemplazada en {cambiadas} sitios del texto.', nuevo=propuesta, cambiadas=len(iguales)), text_color='#62D196')
    def _orto_ignorar(self):
        idx = self._orto_actual
        if idx is None:
            return
        self.dudosas.discard(idx)
        self._pintar_palabra(idx)
        self._orto_eleccion = None
        self._pintar_orto()
    def _pintar_todo(self):
        for i in range(len(self.palabras)):
            self._pintar_palabra(i)
    def _actualizar_contador(self):
        self._version += 1
        self._cache_bloques = None
        if self.modo == self.MODO_TEXTO:
            self.counts_label.configure(text=tr('{len} palabras', len=len(self.palabras)))
            n = getattr(self, '_n_bloques', None)
            self.blocks_label.configure(text=tr('{n} bloques de subtítulo', n=n) if n else '')
            self.avance_lbl.configure(text=tr('{len} palabras', len=len(self.palabras)) + (' · ' + tr('{n} bloques de subtítulo', n=n) if n else ''))
            cortes = sum(1 for w in self.palabras if w.get('corte'))
            self.avance_barra.set(min(1.0, cortes / max(1, n or 1)))
        else:
            c = {'context': 0, 'main': 0, 'complement': 0, None: 0}
            for r in self.roles:
                c[r] = c.get(r, 0) + 1
            try:
                self.brush_btn.contar({
                    tr('Arriba'): c['context'], tr('Principal'): c['main'],
                    tr('Abajo'): c['complement'], tr('Simple'): c[None],
                    self.EMOJI_BRUSH: sum(1 for w in self.palabras
                                          if w.get('emoji'))})
            except Exception:
                pass
            total = len(self.roles)
            pintadas = total - c[None]
            self.counts_label.configure(text=tr('{len} palabras', len=total))
            self.avance_lbl.configure(text=tr('Palabras pintadas: {n} de {total}', n=pintadas, total=total))
            self.avance_barra.set(pintadas / max(1, total))
            try:
                n = len(self._bloques_actuales()[0])
                self.blocks_label.configure(text=tr('{n} bloques de subtítulo', n=n))
            except Exception:
                self.blocks_label.configure(text='')
        self._mostrar_bloque(self._ultimo_idx)
        self._pintar_puntos_sfx()
    PALETA_SFX = ('#FF6B6B', '#FFB86B', '#F7E463', '#62D196', '#4FD1C5', '#4C9AFF', '#8B7BFF', '#E879F9')

    def _info_sfx(self):
        """{indice_de_palabra: {'cat', 'nombre', 'original', 'manual'}} de la primera palabra de cada bloque con efecto:
        lo MISMO que se coloca en Resolve (sfx_rules.asignar_sfx + asignar_archivos). Memorizado hasta el proximo cambio."""
        cache = getattr(self, '_cache_sfx_info', None)
        if cache is not None and cache[0] == self._version:
            return cache[1]
        info = {}
        try:
            if self.modo == self.MODO_MARCAS and self.master.sfx_var.get():
                import copy
                import sfx_rules
                bloques, indice = self._bloques_actuales()
                copia = copy.deepcopy(bloques)
                sfx_rules.asignar_sfx(copia, sfx_rules.cargar_reglas(), categoria=getattr(self.master, '_sfx_categoria_elegida', None))
                manuales = {round(float(w.get('start') or 0), 3): w.get('sfx_archivo') for w in self.palabras if 'sfx_archivo' in w}
                sfx_rules.asignar_archivos(copia, manuales, para_resolver=False)
                reales = [i for i, w in enumerate(self.palabras) if w['word'].strip()]
                por_palabra = sfx_rules.asignar_eventos_por_palabra(copia, [self.palabras[i].get('start') or 0 for i in reales], manuales, para_resolver=False)
                if por_palabra:                  # modo simple: un sonido en CADA palabra
                    inicio_de = {i: round(float(self.palabras[i].get('start') or 0), 3) for i in reales}
                    por_t = {}
                    for i in reales:
                        por_t.setdefault(inicio_de[i], i)
                    for b in copia:
                        for ev in b.get('sfx_eventos') or []:
                            i = por_t.get(round(float(ev['t']), 3))
                            if i is not None:
                                info[i] = {'cat': ev['sfx'], 'nombre': ev['sfx_nombre'], 'original': ev.get('sfx_original') or '', 'manual': bool(ev.get('sfx_manual'))}
                    for i in reales:
                        if self.palabras[i].get('sfx_archivo') == '' and i not in info:
                            info[i] = {'cat': '', 'nombre': tr('sin sonido'), 'original': '', 'manual': True}
                    self._cache_sfx_info = (self._version, info)
                    return info
                primera = {}
                for j, k in enumerate(indice):
                    primera.setdefault(k, j)
                for k, b in enumerate(copia):
                    if b.get('sfx') and b.get('sfx_nombre') and k in primera and primera[k] < len(reales):
                        info[reales[primera[k]]] = {'cat': b['sfx'], 'nombre': b['sfx_nombre'], 'original': b.get('sfx_original') or '', 'manual': bool(b.get('sfx_manual'))}
                # un bloque silenciado a mano tambien lleva su punto (gris), para poder devolverle el sonido
                for i, w in enumerate(self.palabras):
                    if w.get('sfx_archivo') == '' and i not in info and w['word'].strip():
                        info[i] = {'cat': '', 'nombre': tr('sin sonido'), 'original': '', 'manual': True}
        except Exception:
            info = {}
        self._cache_sfx_info = (self._version, info)
        return info

    def _pintar_puntos_sfx(self):
        """Los puntos de color bajo las palabras: cada color es una categoria de sonido; el nombre sale al pasar el cursor."""
        try:
            self.master._registrar_sfx_manuales(self.palabras)
        except Exception:
            pass
        puntos = {}
        for i, d in self._info_sfx().items():
            color = '#6B7A99' if not d['cat'] else self.PALETA_SFX[sum(map(ord, d['cat'])) % len(self.PALETA_SFX)]
            puntos[i] = (color, d['nombre'])
        self.lienzo.poner_puntos_sfx(puntos)

    def _menu_sfx(self, idx, gx, gy):
        """Clic en el punto de una palabra: el sonido de ese bloque se puede cambiar por otro de su categoria, por uno de
        otra categoria o quitarlo. Al generar, Resolve coloca exactamente ese archivo."""
        d = self._info_sfx().get(idx)
        if not d:
            return
        import sfx_rules
        menu = Menu(self)
        menu.agregar('♪  ' + d['nombre'] + (('  ·  ' + d['cat']) if d['cat'] else ''), lambda: self._escuchar_sfx(d['original']))
        menu.separador()
        if d['cat']:
            for ruta in sfx_rules._rutas_de(d['cat'])[:30]:
                marca = '✓  ' if os.path.normcase(ruta) == os.path.normcase(d['original']) else '     '
                menu.agregar(marca + Path(ruta).name, lambda r=ruta: self._cambiar_sfx(idx, r))
            menu.separador()
        menu.agregar(tr('Elegir de otra categoría…'), lambda: self._menu_sfx_categorias(idx, gx, gy))
        menu.agregar(tr('Sin sonido en este bloque'), lambda: self._cambiar_sfx(idx, ''))
        if self.palabras[idx].get('sfx_archivo') is not None:
            menu.agregar(tr('Volver al automático'), lambda: self._cambiar_sfx(idx, None))
        menu.mostrar(gx, gy)

    def _menu_sfx_categorias(self, idx, gx, gy):
        import sfx_rules
        menu = Menu(self)
        try:
            cats = sorted(sfx_rules.categorias_disponibles())
        except Exception:
            cats = []
        for cat in cats[:40]:
            menu.agregar(cat, lambda c=cat: self._menu_sfx_archivos(idx, c, gx, gy))
        menu.mostrar(gx, gy)

    def _menu_sfx_archivos(self, idx, cat, gx, gy):
        import sfx_rules
        menu = Menu(self)
        for ruta in sfx_rules._rutas_de(cat)[:40]:
            menu.agregar(Path(ruta).name, lambda r=ruta: self._cambiar_sfx(idx, r))
        menu.mostrar(gx, gy)

    def _escuchar_sfx(self, ruta):
        """Suena el efecto (una vez, con su volumen y recorte) para poder elegir de oido."""
        if not ruta:
            return
        try:
            import sfx_audio
            import sfx_rules
            audio, _sr = sfx_audio.cargar(sfx_rules.para_resolve(ruta))
            if getattr(self, '_repro_sfx', None) is None:
                self._repro_sfx = sfx_audio.Reproductor()
            self._repro_sfx.reproducir(audio)
        except Exception:
            pass

    def _cambiar_sfx(self, idx, ruta):
        """ruta = archivo; '' = sin sonido; None = volver al automatico."""
        self._guardar_para_deshacer()
        if ruta is None:
            self.palabras[idx].pop('sfx_archivo', None)
        else:
            self.palabras[idx]['sfx_archivo'] = ruta
        self._cache_sfx_info = None
        self._actualizar_contador()
        if ruta:
            self._escuchar_sfx(ruta)
        self._programar_autoguardado()

    # -- v5.10: el estilo «guion» en el editor (una sola lógica con Generar: guion_editor.planear) --------------------------------------
    def _construir_controles_guion(self, aj, dyn):
        """La tarjeta de la derecha con el estilo «guion»: qué hace cada pincel, la altura de la pila, «Auto» y «Quitar mis marcas»."""
        import editor_ui
        aj.addSpacing(4)
        aj.addWidget(Etiqueta(tr('Cómo se arma el bloque'), 14, peso='negrita', color='#FFFFFF'))
        aj.addWidget(Etiqueta(tr('Principal = la palabra GRANDE · Abajo = palabra en NEGRITA · Arriba = palabra FINA · Simple = lo decide el programa. '
                                 'Cada palabra entra justo cuando se dice y la pila se va toda junta. El estilo de cada bloque se elige con los chips de arriba.'),
                             12, color=TEXT_MUTED, envolver=True))
        aj.addSpacing(6)
        aj.addWidget(Etiqueta(tr('Altura de los captions'), 13, peso='negrita', color='#FFFFFF'))
        self._anclas_guion = {tr('Alta'): 'alto', tr('Media'): 'medio', tr('Baja'): 'bajo', tr('Alterna'): 'alterna'}
        actual = self._ancla_guion()
        self.ancla_var = StringVar(next((k for k, v in self._anclas_guion.items() if v == actual), tr('Media')))
        self.ancla_seg = Segmentado(list(self._anclas_guion), self.ancla_var, self._guion_poner_ancla, alto=32)
        aj.addWidget(self.ancla_seg)
        Tooltip(self.ancla_seg, tr('Dónde cae la pila de texto en el cuadro: alta, media, baja o alternando. Vale para todos los bloques.'))
        aj.addSpacing(6)
        fila, cf = caja_h(espacio=8)
        self.guion_auto_btn = Boton(tr('Auto (como GO)'), self._guion_auto, alto=32, tam=12, tipo='fantasma')
        Tooltip(self.guion_auto_btn, tr('Pinta lo que el programa elegiría solo (Principal y Abajo). No cambia el resultado: lo deja a la vista para que lo retoques. Ctrl+Z deshace.'))
        self.guion_limpiar_btn = Boton(tr('Quitar mis marcas'), self._guion_limpiar, alto=32, tam=12, tipo='fantasma')
        Tooltip(self.guion_limpiar_btn, tr('Deja TODAS las palabras en «Simple»: el programa decide solo, igual que GO. Ctrl+Z deshace.'))
        cf.addWidget(self.guion_auto_btn)
        cf.addWidget(self.guion_limpiar_btn)
        aj.addWidget(fila)
        # (los controles de «palabras por línea» son del diseño de 3 líneas: se crean pero no se ponen en pantalla)
        self._tamanos_vars = [StringVar(str(v)) for v in self.tamanos]
        self.panel_tamanos = editor_ui.PanelTamanos(self.tamanos, dyn.RANGO_TAMANOS, (self.ROLE_COLOR['context'], self.ROLE_COLOR['main'], self.ROLE_COLOR['complement']))
        self.panel_tamanos.cambio.connect(self._al_cambiar_tamano)
    def _guion_comprobar_en_resolve(self):
        """«Comprobar en Resolve»: el bloque que se está viendo, renderizado de verdad por Resolve (vistas_reales.renderizar_guion). Corre en un hilo."""
        if getattr(self, '_comprobando', False) or not getattr(self, '_guion', False):
            return
        if getattr(self.master, '_go_corriendo', False):
            self.modo_hint.configure(text=tr('GO está trabajando: espera a que termine para comprobar en Resolve.'))
            return
        k = self._bloque_mostrado
        try:
            bloques, indice = self._bloques_actuales()
        except Exception:
            return
        if k is None or not (0 <= k < len(bloques)) or bloques[k].get('cue') is None:
            return
        import copy
        cue = copy.deepcopy(bloques[k]['cue'])
        pack = getattr(self.master, 'plantilla_sel', 'Referencia')
        try:
            import ajustes_ui
            posicion = str(ajustes_ui.leer_prefs().get('emoji_posicion') or 'abajo')
        except Exception:
            posicion = 'abajo'
        self._comprobando = True
        self.guion_real_btn.setText(tr('Renderizando en Resolve…'))
        self.guion_real_btn.setEnabled(False)

        def trabajo():
            import vistas_reales
            return vistas_reales.renderizar_guion(pack, cue, posicion, al_estado=lambda t: None)

        def fin(resultado, error):
            self._comprobando = False
            try:
                self.guion_real_btn.setText(tr('Comprobar en Resolve (render real)'))
                self.guion_real_btn.setEnabled(True)
            except Exception:
                pass
            ruta, mensaje = (resultado or (None, ''))
            if error is not None or not ruta:
                self.modo_hint.configure(text=tr('No pude comprobarlo en Resolve: {m}', m=str(error or mensaje or '—')[:160]), text_color='#FF9B9B')
                return
            img = QImage(ruta)
            if img.isNull() or self._bloque_mostrado != k:
                return
            self.vista_bloque.poner_real(img)
        _correr_en_hilo(self, trabajo, fin)
    def _guion_poner_ancla(self, valor):
        ancla = getattr(self, '_anclas_guion', {}).get(valor, 'medio')
        try:
            import ajustes_ui
            ajustes_ui.guardar_prefs({'guion_ancla': ancla})
        except Exception:
            pass
        self._version += 1
        self._cache_bloques = None
        self._mostrar_bloque(self._ultimo_idx)
    def _guion_auto(self):
        self._guardar_para_deshacer()
        self.roles = self._roles_del_planificador()
        self._pintar_todo()
        self._actualizar_contador()
        self._programar_autoguardado()
    def _guion_limpiar(self):
        self._guardar_para_deshacer()
        self.roles = [None] * len(self.roles)
        self._pintar_todo()
        self._actualizar_contador()
        self._programar_autoguardado()
    def _ancla_guion(self):
        try:
            import ajustes_ui
            return str(ajustes_ui.leer_prefs().get('guion_ancla', 'medio'))
        except Exception:
            return 'medio'
    def _fin_video_guion(self):
        """Donde acaba el video (el último bloque se cierra ahí): la MISMA cifra que usa Generar; se lee una sola vez (abre el archivo)."""
        if self._fin_video_memo is False:
            try:
                self._fin_video_memo = self.master._fin_video()
            except Exception:
                self._fin_video_memo = None
        return self._fin_video_memo
    def _planear_guion(self, automatico=False):
        import guion_editor
        pack = getattr(self.master, 'plantilla_sel', 'Referencia')
        return guion_editor.planear(self.palabras, self.roles, pack, ancla=self._ancla_guion(), fin_video=self._fin_video_guion(), idioma=self.idioma,
                                    automatico=automatico)
    def _roles_del_planificador(self):
        """Los roles que el planificador elegiría solo (Principal = grande, Abajo = negrita, el resto Simple), listos para pintar."""
        import guion_editor
        pack = getattr(self.master, 'plantilla_sel', 'Referencia')
        return guion_editor.roles_automaticos(self.palabras, pack, ancla=self._ancla_guion(), fin_video=self._fin_video_guion(), idioma=self.idioma)
    def _bloques_actuales(self):
        """(bloques, indice_de_bloque_por_palabra) con las marcas de AHORA:
        el mismo build_manual_cues que arma los subtitulos (v5.0.0, para
        «Así se verá este bloque»). Memorizado hasta el proximo cambio.
        v5.10: con un pack «guion», el mismo plan que escribe Generar (guion_editor.planear)."""
        if self._cache_bloques is not None and self._cache_bloques[0] == self._version:
            return self._cache_bloques[1]
        if getattr(self, '_guion', False):
            import guion_editor
            res = self._planear_guion()
            bloques, indice = guion_editor.bloques_para_editor(res, self.palabras)
            self._cache_bloques = (self._version, (bloques, indice))
            return (bloques, indice)
        import dynamic_subtitles as dyn
        por_basico = 2
        try:
            por_basico = self.master._palabras_por_basico()
        except AttributeError:
            pass
        roles = self.roles if self.modo == self.MODO_MARCAS else [None] * len(self.palabras)
        try:
            capitalizar = self.master._capitalizar()
        except Exception:
            capitalizar = True
        bloques = dyn.build_manual_cues(self.palabras, roles, palabras_por_basico=por_basico, capitalizar=capitalizar, tamanos=self.tamanos, peso_conector=self.peso_conector)
        if self.modo == self.MODO_MARCAS:
            self._asignar_estilos(bloques)
        indice = []
        for k, b in enumerate(bloques):
            for linea in b.get('lines') or []:
                indice.extend([k] * len(str(linea.get('text') or '').split()))
        self._cache_bloques = (self._version, (bloques, indice))
        return (bloques, indice)
    def _estilos_pack(self):
        """Las variantes (estilos) del pack elegido para el formato en juego: [{'n', 'nombre', 'color', 'y'…}]. [] si no hay pack (Media Pool, diseño)."""
        pack = getattr(self.master, 'plantilla_sel', 'auto')
        try:
            formato = self.master._formato_en_juego()
        except Exception:
            formato = None
        cache = getattr(self, '_cache_estilos_pack', None)
        if cache and cache[0] == (pack, formato):
            return cache[1]
        lista = plantillas.variantes_de(pack, formato) if self.modo == self.MODO_MARCAS else []
        self._cache_estilos_pack = ((pack, formato), lista)
        return lista
    def _asignar_estilos(self, bloques):
        """Le pone a cada bloque su estilo (la rueda, el fijo o el que elegiste a mano): la MISMA regla con la que se genera."""
        numeros = [v['n'] for v in self._estilos_pack() if v.get('n')]
        if numeros:
            import estilos_bloque
            estilos_bloque.asignar(bloques, self.palabras, numeros, estilo_fijo())
    def _pintar_estilo_bloque(self, k, b, n):
        """Debajo de la vista: «Estilo 2 de 3 · Rosa · automático» y los botones para cambiarlo en este bloque; y dónde cae en el cuadro."""
        estilos = self._estilos_pack()
        actual = next((v for v in estilos if v.get('n') == n), None)
        if n is None or actual is None:
            self.estilo_w.hide()
            self.mini_pos.hide()
            return
        manual = bool(b.get('estilo_manual'))
        fijo = estilo_fijo()
        quien = tr('lo elegiste tú') if manual else (tr('fijo en el pack') if fijo else tr('automático'))
        partes = [tr('Estilo {i} de {t}', i=estilos.index(actual) + 1, t=len(estilos))]
        if actual.get('nombre'):
            partes.append(actual['nombre'])
        partes.append(quien)
        if not composicion.es_defecto(getattr(self.master, 'composicion', None)):
            partes.append(tr('con tu ajuste fino de Proyecto'))
        self.estilo_lbl.configure(text='  ·  '.join(partes))
        limpiar_capa(self.estilo_chips)
        if len(estilos) > 1:
            self.estilo_chips.addWidget(Chip(tr('Automático'), ui.ACCENT_CLARO, lambda: self._poner_estilo_de_bloque(None), alto=26, tam=12, lleno=not manual))
            for pos, v in enumerate(estilos, 1):
                etiqueta = str(pos) + (' · ' + v['nombre'] if v.get('nombre') else '')
                color = _color_de_variante(v.get('color'), ui.ACCENT_CLARO)
                self.estilo_chips.addWidget(Chip(etiqueta, color, lambda nn=v['n']: self._poner_estilo_de_bloque(nn), punto=color, alto=26, tam=12,
                                                 lleno=manual and v['n'] == n))
        self.estilo_chips_w.setVisible(len(estilos) > 1)
        self.estilo_w.show()
        try:
            formato = self.master._formato_en_juego()
        except Exception:
            formato = 'v'
        comp = composicion.valida(getattr(self.master, 'composicion', None))
        if actual.get('y') and not getattr(self, '_guion', False):          # (el estilo «guion» ya enseña su posición real en la propia vista)
            self.mini_pos.poner(formato, actual['y'], _color_de_variante(actual.get('color'), '#F5B84B'), comp)
            self.mini_pos.show()
        else:
            self.mini_pos.hide()
    def _poner_estilo_de_bloque(self, n):
        """El estilo de ESTE bloque: n = el número de la variante, o None = automático. Se guarda en su primera palabra."""
        k = self._bloque_mostrado
        if k is None:
            return
        bloques, indice = self._bloques_actuales()
        primera = next((i for i, kk in enumerate(indice) if kk == k), None)
        if primera is None or primera >= len(self.palabras):
            return
        if n is None:
            self.palabras[primera].pop('estilo', None)
        else:
            self.palabras[primera]['estilo'] = int(n)
        self._version += 1
        self._cache_bloques = None
        self._mostrar_bloque(self._ultimo_idx)
        self._programar_autoguardado()
    def _hover_palabra(self, idx):
        cancelar(self._hover_id)
        self._hover_id = despues(70, lambda i=idx: self._mostrar_bloque(i), self)
    def _mostrar_bloque(self, idx):
        """Pinta en «Así se verá este bloque» el bloque de la palabra idx
        (aprox.: con los estilos del pack elegido)."""
        try:
            bloques, indice = self._bloques_actuales()
        except Exception:
            bloques, indice = ([], [])
        if not bloques:
            self.vista_bloque.poner([])
            self.tiempo_bloque.configure(text='')
            self.sfx_bloque.hide()
            return
        idx = max(0, min(int(idx or 0), len(indice) - 1)) if indice else 0
        self._ultimo_idx = idx
        k = indice[idx] if indice else 0
        b = bloques[min(k, len(bloques) - 1)]
        textos, roles = ([], [])
        for linea in b.get('lines') or []:
            textos.append(linea.get('text') or '')
            roles.append(linea.get('role') or 'base')
        pack = getattr(self.master, 'plantilla_sel', 'auto')
        try:
            formato = self.master._formato_en_juego()
        except Exception:
            formato = None
        n_estilo = b.get('estilo') if self.modo == self.MODO_MARCAS else None
        if getattr(self, '_guion', False) and b.get('cue') is not None:
            # v5.10: el bloque tal como lo colocará Resolve (geometría real de cada palabra), no la maqueta de 3 líneas
            self.vista_bloque.poner_cue(b['cue'], pack, imagen=self._imagen_guion(k, indice, pack, formato))
        else:
            lineas = lineas_de_vista(pack if self.modo == self.MODO_MARCAS else None, formato, textos, roles, n=n_estilo)
            self.vista_bloque.poner(lineas, imagen=self._imagen_del_bloque(k, indice, pack, formato) if self.modo == self.MODO_MARCAS else None)
        self._bloque_mostrado = k
        self._pintar_estilo_bloque(k, b, n_estilo)
        self.tiempo_bloque.configure(text=f"{_tc_fino(b.get('start'))}  ›  {_tc_fino(b.get('end'))}")
        sfx = None
        try:
            if self.modo == self.MODO_MARCAS and self.master.sfx_var.get():
                sfx = self._sfx_de_bloque(k, bloques)
        except Exception:
            sfx = None
        if sfx:
            self.sfx_bloque.poner(texto=tr('SFX: {cat}', cat=sfx))
            self.sfx_bloque.show()
        else:
            self.sfx_bloque.hide()
    # -- v5.4: la vista REAL: reproduce todo el parrafo, bloque a bloque, con sus animaciones, el emoji animado y sus sonidos --
    def _glifo_emoji_de(self, eid):
        try:
            import emojis
            return (emojis.por_id(eid) or {}).get('glifo') or ''
        except Exception:
            return ''

    def _alternar_reproduccion(self):
        if getattr(self, '_repro', None) is not None:
            self._parar_reproduccion()
        else:
            self._empezar_reproduccion()

    def _empezar_reproduccion(self):
        try:
            bloques, indice = self._bloques_actuales()
        except Exception:
            bloques, indice = ([], [])
        if not bloques:
            return
        self._repro = {'bloques': bloques, 'indice': indice, 'k': -1, 't0': time.perf_counter(), 'ini': float(bloques[0]['start']),
                       'sonidos': self._sonidos_para_reproducir(), 'ultimo_t': float(bloques[0]['start']) - 0.01}
        if getattr(self, '_reloj_repro', None) is None:
            self._reloj_repro = ui.QTimer(self)
            self._reloj_repro.timeout.connect(self._tic_reproduccion)
        self._reloj_repro.start(33)
        self.reproducir_btn.poner_activo(True)

    def _sonidos_para_reproducir(self):
        """[(segundo, ruta)] de los sonidos que Resolve colocaria (los mismos del popup de cada palabra)."""
        salida = []
        try:
            for i, d in self._info_sfx().items():
                if d.get('original'):
                    salida.append((float(self.palabras[i].get('start') or 0), d['original']))
        except Exception:
            pass
        return sorted(salida)

    def _parar_reproduccion(self):
        self._repro = None
        try:
            self._reloj_repro.stop()
            self.vista_bloque.animar(None)
            self.lienzo.sonando(None)
            self.reproducir_btn.poner_activo(False)
            self.reproduccion_lbl.configure(text='')
            self._mostrar_bloque(self._ultimo_idx)
        except Exception:
            pass

    def _tic_reproduccion(self):
        r = getattr(self, '_repro', None)
        if r is None or not ui.vivo(self):
            return
        t = r['ini'] + (time.perf_counter() - r['t0'])
        bloques = r['bloques']
        fin = float(bloques[-1]['end'])
        if t > fin + 0.4:
            self._parar_reproduccion()
            return
        k = 0
        for j, b in enumerate(bloques):
            if float(b['start']) <= t:
                k = j
            else:
                break
        b = bloques[k]
        fin_b = min(float(b['end']), float(bloques[k + 1]['start'])) if k + 1 < len(bloques) else float(b['end'])
        if k != r['k']:
            r['k'] = k
            textos, roles = ([], [])
            for linea in b.get('lines') or []:
                textos.append(linea.get('text') or '')
                roles.append(linea.get('role') or 'base')
            pack = getattr(self.master, 'plantilla_sel', 'auto')
            try:
                formato = self.master._formato_en_juego()
            except Exception:
                formato = None
            if getattr(self, '_guion', False) and b.get('cue') is not None:
                r['lineas'], r['cue'], r['pack'] = None, b['cue'], pack            # v5.10: el bloque «guion», palabra a palabra, con su momento
                r['imagen'] = self._imagen_guion(k, r['indice'], pack, formato)
            else:
                r['lineas'] = lineas_de_vista(pack if self.modo == self.MODO_MARCAS else None, formato, textos, roles, n=b.get('estilo') if self.modo == self.MODO_MARCAS else None)
                r['imagen'] = self._imagen_del_bloque(k, r['indice'], pack, formato) if self.modo == self.MODO_MARCAS else None
            r['glifo'] = ''
            for i, kk in enumerate(r['indice']):
                if kk == k and i < len(self.palabras) and self.palabras[i].get('emoji'):
                    r['glifo'] = self._glifo_emoji_de(self.palabras[i]['emoji'])
                    break
            try:
                primera = next(i for i, kk in enumerate(r['indice']) if kk == k)
                self.lienzo.ver(primera)
            except StopIteration:
                pass
            self.tiempo_bloque.configure(text=f"{_tc_fino(b.get('start'))}  ›  {_tc_fino(b.get('end'))}")
            self.reproduccion_lbl.configure(text=tr('bloque {k} de {n}', k=k + 1, n=len(bloques)))
        try:
            son = None
            for i_p, w_p in enumerate(self.palabras):
                a_p = float(w_p.get('start') or 0)
                if a_p <= t < max(a_p + 0.05, float(w_p.get('end') or a_p)):
                    son = i_p
                    break
            self.lienzo.sonando(son)
        except Exception:
            pass
        imagen = dict(r['imagen']) if r.get('imagen') else None
        if imagen is not None and r.get('glifo'):
            cuadro = emojis_animados.frame(r['glifo'], time.perf_counter(), None)
            if cuadro is not None:
                imagen['pix'] = cuadro
        if r.get('lineas') is None and r.get('cue') is not None:
            self.vista_bloque.poner_cue(r['cue'], r.get('pack'), imagen=imagen)
        else:
            self.vista_bloque.poner(r['lineas'], imagen=imagen)
        self.vista_bloque.animar(max(0.0, t - float(b['start'])), salida=max(0.0, min(1.0, (t - (fin_b - 0.12)) / 0.12)))
        for seg, ruta in r['sonidos']:                  # los sonidos que pasaron desde el tic anterior
            if r['ultimo_t'] < seg <= t:
                self._escuchar_sfx(ruta)
        r['ultimo_t'] = t

    def _imagen_guion(self, k, indice, pack, formato):
        """El emoji del bloque k en la vista del estilo «guion»: solo si el bloque lo lleva, encima o debajo de la pila según «Emoji: posición» de
        Ajustes (como lo coloca Resolve). None si no hay."""
        img = self._imagen_del_bloque(k, indice, pack, formato)
        if not img or img.get('pix') is None:
            return None
        try:
            import ajustes_ui
            eleccion = str(ajustes_ui.leer_prefs().get('emoji_posicion') or '')
        except Exception:
            eleccion = ''
        img['donde'] = eleccion if eleccion in ('abajo', 'arriba') else (img.get('donde') or 'abajo')
        return img
    def _imagen_del_bloque(self, k, indice, pack, formato):
        """El espacio «imagen» del bloque k: donde caera el emoji (el bloque «imagen» del pack o, sin el, debajo del
        texto) y el emoji de la palabra si ya lo tiene. Nunca lanza."""
        try:
            info = plantillas.bloque_imagen(pack, formato)
        except Exception:
            info = {'donde': 'abajo', 'zoom': 1.0, 'bloque': False}
        pix = None
        try:
            for i, kk in enumerate(indice):
                if kk == k and i < len(self.palabras) and self.palabras[i].get('emoji'):
                    import emojis
                    pix = ui.pixmap_de_archivo(emojis.ruta_mini(self.palabras[i]['emoji']), 96)
                    break
        except Exception:
            pix = None
        return dict(info, pix=pix)
    def _sfx_de_bloque(self, k, bloques):
        cache = getattr(self, '_cache_sfx', None)
        if cache is None or cache[0] != self._version:
            import copy
            import sfx_rules
            copia = copy.deepcopy(bloques)
            try:
                sfx_rules.asignar_sfx(copia, sfx_rules.cargar_reglas(), categoria=getattr(self.master, '_sfx_categoria_elegida', None))
            except Exception:
                copia = []
            cache = (self._version, [b.get('sfx') for b in copia])
            self._cache_sfx = cache
        lista = cache[1]
        return lista[k] if 0 <= k < len(lista) else None
    def _guardar_marcas(self):
        """Guarda las palabras (ya corregidas) y sus marcas en disco (no
        perder el trabajo, y volver despues con 'Editar marcas y regenerar'
        sin re-transcribir)."""
        if not self.project_name:
            messagebox.showinfo(tr('No se puede guardar'), tr('No sé a qué proyecto pertenecen estas marcas.'), parent=self)
            return
        try:
            ruta = guardar_marcas(self.project_name, self.palabras, self.roles)
        except Exception as e:
            messagebox.showerror(tr('No pude guardar'), str(e), parent=self)
            return None
        messagebox.showinfo(tr('Marcas guardadas'), tr('Guardado en:\n{ruta}\n\nPuedes volver a esta pantalla cuando quieras desde el botón \'Editar marcas y regenerar\' de la ventana principal, sin tener que transcribir de nuevo.', ruta=ruta), parent=self)
    def _sugerir_con_ia(self):
        """«Asistencia» (v5.2, pedido: «que de una vez coloque los emojis,
        que quite puntos, comillas, todos los signos, más inteligente»): en
        UNA pasada la IA local corrige el texto, quita los signos, elige las
        palabras clave con criterio viral y pone los emojis (los elegidos a
        mano no se tocan). Sin la IA instalada, lo mismo con el motor de
        siempre. Otra pulsacion = otra version (el analisis se reutiliza).
        Todo va a _historial: Ctrl+Z lo deshace de un golpe."""
        self._guardar_para_deshacer(manual=False)
        variante = getattr(self, '_variante_ia', (-1))
        variante = (variante + 1) % sugerencias_ia.VARIANTES
        self._variante_ia = variante
        modal = Dialogo(self, tr('Asistencia'), 500, 430, redimensionable=False)
        capa = _capa_dialogo(modal, (0, 0, 0, 0), 0)
        import editor_ui
        panel = editor_ui.PanelAsistencia(
            tr('La asistencia está trabajando'), tr('Listo'), tr('Leyendo tu guion…'),
            (tr('Leer y entender el guion'), tr('Corregir texto y ortografía'), tr('Elegir las palabras clave'), tr('Quitar signos y poner emojis')),
            tr('Versión {v} de {t}', v=variante + 1, t=sugerencias_ia.VARIANTES),
            tr('Otra pulsación = otra versión · Ctrl+Z deshace'))
        capa.addWidget(panel, 1)
        cerrar_flag = {'cerrado': False}
        def _cerrar_modal():
            if cerrar_flag['cerrado']:
                return
            cerrar_flag['cerrado'] = True
            try:
                modal.cerrar()
            except Exception:
                return None
        modal.finished.connect(lambda _r: cerrar_flag.__setitem__('cerrado', True))
        modal.open()
        idioma = self.idioma if self.idioma not in (None, '', 'auto') else 'es'
        estado = {'texto': None, 'fase': 0}
        resultado = {'palabras': None, 'roles': None, 'error': None, 'ia': False, 'correcciones': 0,
                     'emojis': 0, 'signos': 0}
        base = [dict(w) for w in self.palabras]
        tamanos = getattr(self, 'tamanos', None)
        peso_conector = 1.0
        # auditoría v5.11: con el estilo «guion» las palabras clave las elige el planificador (igual que «Auto (como GO)» y que Generar),
        # no los roles de 3 líneas de la IA, que aquí se leerían como grande / fina / negrita al azar
        guion_pack = getattr(self.master, 'plantilla_sel', 'Referencia') if getattr(self, '_guion', False) else None
        guion_ancla, guion_fin = (self._ancla_guion(), self._fin_video_guion()) if guion_pack else ('medio', None)
        def _trabajar():
            try:
                import ia_texto
                palabras = [dict(w) for w in base]
                ia_texto.marcar_fin_de_frase(palabras)
                estado['fase'] = 0
                pesos, propuestos = None, None
                if ia_texto.disponible():
                    # el analisis vale mientras sean las mismas palabras (mismos tiempos)
                    clave = (idioma, len(palabras), tuple(round(float(w.get('start') or 0), 2) for w in palabras))
                    cache = getattr(self, '_ia_cache', None)
                    try:
                        if not cache or cache[0] != clave:
                            r = ia_texto.analizar(palabras, idioma, estado=lambda t: estado.__setitem__('texto', t))
                            try:        # v5.4: «Asistencia» tambien revisa la ortografia (una pasada solo de faltas + fonetica del español)
                                estado['fase'] = 1
                                estado['texto'] = tr('Revisando la ortografía…')
                                ro = ia_texto.analizar(palabras, idioma, modo='ortografia')
                                for i_, t_ in (ro.get('correcciones') or {}).items():
                                    r['correcciones'].setdefault(i_, t_)
                                for i_, t_ in ortografia.corregir_fonetico(palabras, idioma).items():
                                    r['correcciones'].setdefault(i_, t_)
                            except Exception:
                                registro.excepcion(origen='Asistencia · ortografía')
                            cache = (clave, r)
                            self._ia_cache = cache
                        r = cache[1]
                        antes = [w.get('word') for w in palabras]
                        palabras = ia_texto.aplicar_correcciones(palabras, r['correcciones'])
                        resultado['correcciones'] = sum(1 for a, w in zip(antes, palabras) if a != w.get('word'))
                        pesos, propuestos = r['pesos'], r.get('emojis') or {}
                        resultado['ia'] = True
                    except Exception as e:
                        print('IA de texto:', e)
                estado['fase'] = 2
                estado['texto'] = tr('Eligiendo las palabras clave…')
                roles = ia_texto.roles_inteligentes(palabras, idioma, pesos, tamanos, peso_conector,
                                                    densidad=sugerencias_ia.DENSIDAD_POR_DEFECTO, variante=variante)
                if not any(roles):
                    import dynamic_subtitles as dyn
                    roles = list(dyn.suggest_roles(palabras))
                estado['fase'] = 3
                estado['texto'] = tr('Quitando signos y poniendo emojis…')
                resultado['signos'] = ia_texto.sin_signos(palabras)
                if guion_pack:
                    import guion_editor
                    roles = guion_editor.roles_automaticos(palabras, guion_pack, ancla=guion_ancla, fin_video=guion_fin, idioma=idioma)
                elegidos = (ia_texto.emojis_de_ia(palabras, propuestos, idioma, roles) if propuestos is not None
                            else ia_texto.emojis_sin_ia(palabras, roles, idioma))
                resultado['emojis'] = ia_texto.poner_emojis(palabras, elegidos)
                resultado['palabras'], resultado['roles'] = palabras, roles
            except Exception as e:
                guardar_log_de_error(traceback.format_exc())
                resultado['error'] = f'{type(e).__name__}: {e}'
        hilo = threading.Thread(target=_trabajar, daemon=True)
        hilo.start()
        def _revisar():
            if cerrar_flag['cerrado'] and hilo.is_alive():
                return
            if hilo.is_alive():
                panel.poner_fase(estado['fase'])
                if estado['texto']:
                    panel.poner_detalle(estado['texto'])
                despues(100, _revisar, self)
                return
            if resultado['error'] or resultado['palabras'] is None:
                _cerrar_modal()
                messagebox.showerror(tr('La asistencia no pudo marcar'), resultado['error'] or tr('Sin resultado'), parent=self)
                return
            if cerrar_flag['cerrado']:
                _aplicar()
            else:
                panel.terminar()                  # un momento en «Listo» antes de cerrar
                despues(650, _aplicar, self)
        def _aplicar():
            _cerrar_modal()
            self.palabras = resultado['palabras']
            self.roles = list(resultado['roles'])
            self._roles_auto = True
            self._alternativas = None
            self._imgs_emoji.clear()
            self._llenar_texto()
            self._actualizar_contador()
            self._programar_autoguardado()
            marcadas = sum(1 for r in self.roles if r)
            import ui_toast
            motor = 'Qwen3' if resultado['ia'] else tr('motor clásico')
            ui_toast.mostrar(self, tr('Asistencia ({motor}): {c} correcciones · {n} palabras marcadas · {e} emojis · {s} signos fuera · versión {v} de {t}. Ctrl+Z deshace.',
                                      motor=motor, c=resultado['correcciones'], n=marcadas, e=resultado['emojis'],
                                      s=resultado['signos'], v=variante + 1, t=sugerencias_ia.VARIANTES), duracion_ms=6000)
        despues(300, _revisar, self)
    def _al_cambiar_tamano(self, indice, valor):
        self._tamanos_vars[indice].set(str(valor))
        self._on_tamanos_change()
    def _on_tamanos_change(self, _valor=None):
        """«Palabras por línea» cambió: los bloques lo respetan al instante y, si los roles son de la IA (sin marcas a mano), se
        rehacen al instante con los máximos nuevos (v5.7). Se junta el vaivén de varios clics en un solo cálculo."""
        import dynamic_subtitles as dyn
        self.tamanos = dyn.normalizar_tamanos([v.get() for v in self._tamanos_vars])
        self._recordar('tamanos_grupo', self.tamanos)
        self._alternativas = None
        try:
            cancelar(self._id_reajuste)
        except Exception:
            pass
        self._id_reajuste = despues(90, self._reajustar_en_vivo, self)
    def _roles_para(self, variante):
        """Los roles de una versión de la IA con los máximos de ahora. Usa el análisis ya hecho (pesos) si lo hay: es instantáneo."""
        import dynamic_subtitles as dyn
        import ia_texto
        idioma = self.idioma if self.idioma not in (None, '', 'auto') else 'es'
        pesos = None
        try:
            cache = getattr(self, '_ia_cache', None)
            if cache and cache[0] == (idioma, len(self.palabras), tuple(round(float(w.get('start') or 0), 2) for w in self.palabras)):
                pesos = cache[1].get('pesos')
        except Exception:
            pesos = None
        roles = ia_texto.roles_inteligentes(self.palabras, idioma, pesos, self.tamanos, 1.0,
                                            densidad=sugerencias_ia.DENSIDAD_POR_DEFECTO, variante=variante)
        if not any(roles):
            roles = list(dyn.suggest_roles(self.palabras))
        return list(roles)
    def _calcular_alternativas(self):
        self._alternativas = [self._roles_para(v) for v in range(sugerencias_ia.VARIANTES)]
        return self._alternativas
    def _aplicar_roles_auto(self, roles, apilar=True):
        """Pone unos roles de la IA (con deshacer) y refresca todo. Los emojis y el texto se conservan."""
        if apilar:
            import time as _t
            if _t.time() - self._t_reajuste > 2.0:                      # un solo «Ctrl+Z» por tanda de clics en +/-
                self._guardar_para_deshacer(manual=False)
            self._t_reajuste = _t.time()
        self.roles = list(roles)
        self._roles_auto = True
        self._version += 1
        self._cache_bloques = None
        self._llenar_texto()
        self._actualizar_contador()
        self._programar_autoguardado()
        try:
            self._mostrar_bloque(self._ultimo_idx)
        except Exception:
            pass
    def _reajustar_en_vivo(self):
        if self.modo != self.MODO_MARCAS:
            return
        try:
            if self._roles_auto:
                alt = self._calcular_alternativas()
                v = self._variante_ia if self._variante_ia >= 0 else 0
                self._aplicar_roles_auto(alt[v])
            else:                                  # hay marcas a mano: no se pisan; el bloque se reparte con los máximos igual
                self._version += 1
                self._cache_bloques = None
                self._actualizar_contador()
                self._mostrar_bloque(self._ultimo_idx)
        except Exception:
            registro.excepcion(origen='Creativo · palabras por línea')
    def _recordar(self, atributo, valor):
        """Escribe una preferencia en la App y la guarda."""
        try:
            setattr(self.master, atributo, valor)
            self.master._guardar_preferencias()
        except Exception:
            return None
    def _avisar_ajustes_una_vez(self):
        return None                       # v5.7: ya no se avisa; los máximos se respetan siempre y se ven en vivo
    @staticmethod
    def _espacio_valido(valor):
        """0.5 / 1 / 2; cualquier rareza, 1."""
        try:
            v = float(valor)
        except (TypeError, ValueError):
            return 1.0
        return v if v in (0.5, 1.0, 2.0) else 1.0
    def _selector_espacio(self, fila):
        """«Pausas» y «Párrafos», Compacto / Normal / Amplio (v3.3.4:
        «Pausas» es el aire extra tras un silencio del habla y «Párrafos» el
        que hay entre una oracion y la siguiente)."""
        self._ESPACIOS = {tr('Compacto'): 0.5, tr('Normal'): 1.0, tr('Amplio'): 2.0}
        self.espacio_var = StringVar()
        self.parrafos_var = StringVar()
        for k, (etiqueta, ayuda, var, valor, orden) in enumerate([(tr('Pausas:'), tr('Aire extra entre dos oraciones cuando hubo una pausa del habla (más de medio segundo). Se recuerda.'), self.espacio_var, self.espacio_frases, self._on_espacio_change), (tr('Párrafos:'), tr('Aire entre una oración y la siguiente, siempre. Los saltos de línea dentro de una oración no cambian. Se recuerda.'), self.parrafos_var, self.espacio_parrafos, self._on_parrafos_change)]):
            lbl = Etiqueta(etiqueta, 12, color=TEXT_MUTED)
            fila.addWidget(lbl, 0, k)
            Tooltip(lbl, ayuda)
            var.set(next((k2 for k2, v in self._ESPACIOS.items()
                          if v == valor), tr('Normal')))
            fila.addWidget(Combo(list(self._ESPACIOS), var, orden, ancho=110, alto=32, tam=12), 1, k)
            fila.setColumnStretch(k, 1)
    def _on_vista_change(self, _valor=None):
        self.estilo_palabras = self._VISTAS.get(self.vista_var.get(), 'fichas')
        self.lienzo.estilo = self.estilo_palabras
        self._imgs_emoji.clear()
        self._redibujar_manteniendo_vista()
        self._recordar('estilo_palabras', self.estilo_palabras)
    def _on_espacio_change(self, _valor=None):
        self.espacio_frases = self._ESPACIOS.get(self.espacio_var.get(), 1.0)
        self.lienzo.factor_filas = self.espacio_frases
        self._redibujar_manteniendo_vista()
        self._recordar('espacio_frases', self.espacio_frases)
    def _on_parrafos_change(self, _valor=None):
        self.espacio_parrafos = self._ESPACIOS.get(self.parrafos_var.get(), 1.0)
        self.lienzo.factor_parrafos = self.espacio_parrafos
        self._redibujar_manteniendo_vista()
        self._recordar('espacio_parrafos', self.espacio_parrafos)
    def _on_capitalizar_change(self):
        """Aplica y recuerda «Mayúscula inicial» (v3.3.1)."""
        try:
            self.master.capitalizar = bool(self.capitalizar_var.get())
            self.master._guardar_preferencias()
        except Exception:
            return None
        self._version += 1
        self._cache_bloques = None
        self._llenar_texto()                  # v5.4: el parrafo tambien cambia (mayuscula inicial en las palabras de contenido)
        self._mostrar_bloque(self._ultimo_idx)
    def _rango_de_oracion(self, idx):
        """(desde, hasta) de la oracion que contiene la palabra idx."""
        import dynamic_subtitles as dyn
        def cierra(w):
            return bool(w.get('fin_frase')) or dyn.termina_oracion(str(w.get('word') or ''))
        desde = idx
        while desde > 0 and (not cierra(self.palabras[desde - 1])):
            desde -= 1
        hasta = idx
        while hasta < len(self.palabras) - 1 and (not cierra(self.palabras[hasta])):
            hasta += 1
        return (desde, hasta + 1)
    def _ajustar_ancho_textos(self, evento=None):
        """En Qt el ajuste de linea sigue solo al ancho."""
        return None
    def _pedir_cierre(self):
        """Cancelar (Esc o el boton) confirma antes, y guarda pase lo que pase."""
        if self._cerrando:
            return
        self._guardar_ahora()
        if not messagebox.askyesno(tr('Cerrar sin generar'), tr('¿Cierras esta ventana?\n\nTus marcas quedan guardadas: puedes volver desde \'Editar marcas y regenerar\' sin transcribir el vídeo otra vez.'), parent=self):
            return
        self._cancelar()
    def _guardar_ahora(self):
        """Fuerza el autoguardado pendiente, sin esperar al temporizador."""
        if self._autoguardado_id is not None:
            cancelar(self._autoguardado_id)
            self._autoguardado_id = None
        if not self.project_name:
            return
        try:
            guardar_marcas(self.project_name, self.palabras, self.roles)
        except Exception:
            return None
    def _soltar_filtro(self):
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
    def _terminar(self):
        self._cerrando = True
        self._cerrar_popover()
        self._soltar_filtro()
        if self._bucle is not None:
            self._bucle.quit()
    def _cancelar(self):
        self._guardar_ahora()
        self.result = None
        self._terminar()
    def _continuar(self):
        self.result = ([dict(w) for w in self.palabras], list(self.roles))
        self._guardar_ahora()
        self._terminar()
class _EvGlobal:
    __slots__ = ('x_root', 'y_root')
    def __init__(self, x, y):
        self.x_root, self.y_root = (int(x), int(y))
