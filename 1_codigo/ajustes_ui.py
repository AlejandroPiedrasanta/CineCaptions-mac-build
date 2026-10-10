# CineCaptions · By Cinema Productions
# 1_codigo/ajustes_ui.py — Ajustes: panel rápido y ventana completa (General, Interfaz, Atajos, Acerca de, Ayuda) + notas de la versión.
"""
ajustes_ui.py  (v5.1)
---------------------
Lo que se abre con el boton «Ajustes» de la esquina del menu lateral:

  * PanelRapido: la tarjeta flotante «Acerca de CineCaptions» (licencia,
    notas de la version, canal beta, buscar actualizaciones y «Expandir
    ajustes»);
  * VentanaAjustes: los ajustes completos, en pestañas: General, Interfaz,
    Atajos, Acerca de CineCaptions y Ayuda; abajo Cancelar / Aplicar / Listo.

Las dos viven DENTRO de la ventana (CapaModal oscurece el fondo), no son
ventanas aparte: se ven de una pieza con el programa y Esc las cierra.

Lo que no se puede aplicar en caliente (tema, color, tamaño, idioma) se
guarda y se ofrece «Reiniciar ahora».
"""
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

import qt_kit as ui
from qt_kit import (BooleanVar, Boton, Combo, Desplazable, Segmentado, Enlace, Etiqueta, Interruptor, Punto,
                    Separador, StringVar, Tooltip, caja_h, caja_v, correr_en_hilo, ejecutar_en_ui,
                    filedialog, fuente, messagebox)
from qt_kit import QColor, QColorReal
from i18n import tr
import tema

PREFS = Path.home() / 'DaVinciSubtitles' / 'preferencias.json'


def leer_prefs():
    try:
        d = json.loads(PREFS.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def guardar_prefs(cambios):
    """Mezcla 'cambios' en preferencias.json sin tocar lo demas."""
    import archivos_seguros
    return archivos_seguros.mezclar_json(PREFS, cambios)       # atómico y bajo cerrojo (antes un cierre a medias vaciaba las preferencias)


def _version():
    try:
        from version import APP_VERSION
        return APP_VERSION
    except Exception:
        return ''


def texto_canal(beta=None):
    """Siempre «Canal estable»: el canal beta se retiró (v5.3.7)."""
    return tr('Canal estable')


def hace_cuanto(dt):
    if dt is None:
        return ''
    seg = max(0, time.time() - dt.timestamp())
    if seg < 60:
        return tr('hace un momento')
    if seg < 3600:
        return tr('hace {n} min', n=int(seg // 60))
    if seg < 86400:
        return tr('hace {n} h', n=int(seg // 3600))
    dias = int(seg // 86400)
    return tr('hace 1 día') if dias == 1 else tr('hace {n} días', n=dias)


# ---------------------------------------------------------------------------
# Iconos dibujados (trazo fino, como los del menu lateral)
def _pluma(p, color, grosor=1.6):
    pen = QPen(QColor(color), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)


def dibujar_icono(p, clave, r, color):
    """clave: engranaje | chincheta | nube | expandir | cerrar | escudo | notas | recargar"""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _pluma(p, color)
    c = r.center()
    s = min(r.width(), r.height())
    if clave == 'engranaje':
        import math
        camino = QPainterPath()
        dientes, r_ext, r_int = 8, s * 0.46, s * 0.34
        for i in range(dientes * 2):
            ang = math.pi * i / dientes
            rad = r_ext if i % 2 == 0 else r_int
            for d in (-0.16, 0.16):
                pt = QPointF(c.x() + rad * math.cos(ang + d), c.y() + rad * math.sin(ang + d))
                if i == 0 and d < 0:
                    camino.moveTo(pt)
                else:
                    camino.lineTo(pt)
        camino.closeSubpath()
        p.drawPath(camino)
        p.drawEllipse(c, s * 0.14, s * 0.14)
    elif clave == 'chincheta':
        camino = QPainterPath()
        camino.moveTo(c.x() - s * 0.18, c.y() - s * 0.40)
        camino.lineTo(c.x() + s * 0.18, c.y() - s * 0.40)
        camino.lineTo(c.x() + s * 0.12, c.y() - s * 0.06)
        camino.lineTo(c.x() + s * 0.30, c.y() + s * 0.10)
        camino.lineTo(c.x() - s * 0.30, c.y() + s * 0.10)
        camino.lineTo(c.x() - s * 0.12, c.y() - s * 0.06)
        camino.closeSubpath()
        p.drawPath(camino)
        p.drawLine(QPointF(c.x(), c.y() + s * 0.10), QPointF(c.x(), c.y() + s * 0.46))
    elif clave == 'nube':
        camino = QPainterPath()
        base = c.y() + s * 0.22
        camino.moveTo(c.x() - s * 0.30, base)
        camino.cubicTo(c.x() - s * 0.52, base, c.x() - s * 0.50, c.y() - s * 0.12, c.x() - s * 0.26, c.y() - s * 0.08)
        camino.cubicTo(c.x() - s * 0.22, c.y() - s * 0.38, c.x() + s * 0.20, c.y() - s * 0.40, c.x() + s * 0.24, c.y() - s * 0.10)
        camino.cubicTo(c.x() + s * 0.50, c.y() - s * 0.10, c.x() + s * 0.52, base, c.x() + s * 0.30, base)
        p.drawPath(camino)
        p.drawLine(QPointF(c.x(), base + s * 0.04), QPointF(c.x(), c.y() - s * 0.10))
        p.drawLine(QPointF(c.x() - s * 0.10, c.y()), QPointF(c.x(), c.y() - s * 0.10))
        p.drawLine(QPointF(c.x() + s * 0.10, c.y()), QPointF(c.x(), c.y() - s * 0.10))
    elif clave == 'expandir':
        p.drawLine(QPointF(c.x() - s * 0.26, c.y() + s * 0.26), QPointF(c.x() + s * 0.26, c.y() - s * 0.26))
        p.drawLine(QPointF(c.x() - s * 0.06, c.y() - s * 0.26), QPointF(c.x() + s * 0.26, c.y() - s * 0.26))
        p.drawLine(QPointF(c.x() + s * 0.26, c.y() + s * 0.06), QPointF(c.x() + s * 0.26, c.y() - s * 0.26))
    elif clave == 'cerrar':
        d = s * 0.28
        p.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        p.drawLine(QPointF(c.x() + d, c.y() - d), QPointF(c.x() - d, c.y() + d))
    elif clave in ('plegar', 'desplegar'):
        # « o » : dos galones
        signo = -1 if clave == 'plegar' else 1
        for dx in (-s * 0.12, s * 0.14):
            x0 = c.x() + dx
            p.drawLine(QPointF(x0 - signo * s * 0.12, c.y() - s * 0.22), QPointF(x0 + signo * s * 0.10, c.y()))
            p.drawLine(QPointF(x0 + signo * s * 0.10, c.y()), QPointF(x0 - signo * s * 0.12, c.y() + s * 0.22))
    elif clave == 'recargar':
        p.drawArc(QRectF(c.x() - s * 0.32, c.y() - s * 0.32, s * 0.64, s * 0.64), 30 * 16, 290 * 16)
        p.drawLine(QPointF(c.x() + s * 0.30, c.y() - s * 0.26), QPointF(c.x() + s * 0.30, c.y() - s * 0.06))
        p.drawLine(QPointF(c.x() + s * 0.30, c.y() - s * 0.06), QPointF(c.x() + s * 0.10, c.y() - s * 0.06))
    p.restore()


def icono(clave, color='#C9D6EC', lado=18):
    return ui.icono_dibujado(lambda p, l: dibujar_icono(p, clave, QRectF(0, 0, l, l), color), lado)


class BotonIcono(QAbstractButton):
    """Un boton cuadrado con un icono dibujado (el alfiler, la X de cerrar).
    Con 'conmutable' queda resaltado mientras esta activo."""

    def __init__(self, clave, tooltip='', lado=44, conmutable=False, padre=None, radio=12, borde=True):
        super().__init__(padre)
        self._clave = clave
        self._hover = False
        self._radio = radio
        self._borde = borde
        self.setCheckable(conmutable)
        self.setFixedSize(lado, lado)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

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
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        activo = self.isChecked()
        fondo = '#13213D' if activo else ('#14223C' if self._hover else '#0D1627')
        p.setBrush(QColor(fondo))
        p.setPen(QPen(QColor(ui.ACCENT if activo else ('#34507F' if self._hover else '#1E2A42')), 1)
                 if self._borde else Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, self._radio, self._radio)
        lado = min(r.width(), r.height()) * 0.42
        caja = QRectF(r.center().x() - lado / 2, r.center().y() - lado / 2, lado, lado)
        dibujar_icono(p, self._clave, caja, ui.ACCENT_CLARO if activo else ('#FFFFFF' if self._hover else '#B4C0D6'))
        p.end()


class BotonDosLineas(QAbstractButton):
    """El boton grande de la esquina («Crear copia de seguridad»): icono a la
    izquierda y el texto en hasta dos lineas, centrado (como la referencia)."""

    def __init__(self, texto, clave_icono, comando=None, alto=60, padre=None):
        super().__init__(padre)
        self.setText(str(texto))
        self._clave = clave_icono
        self._hover = False
        self.setFixedHeight(alto)
        self.setFont(fuente(14, peso='negrita'))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if comando:
            # clicked manda «checked»: una lambda con argumentos por defecto lo
            # recibiria en su primer parametro
            self.clicked.connect(lambda _=False: comando())

    def sizeHint(self):
        return QSize(180, self.height())

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
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        activo = self.isEnabled()
        p.setBrush(QColor('#14223C' if self._hover and activo else '#111D33'))
        p.setPen(QPen(QColor('#34507F' if self._hover and activo else '#1E2A42'), 1))
        p.drawRoundedRect(r, 10, 10)
        lado = 22
        texto_r = QRectF(r.left() + 16 + lado + 8, r.top() + 4, r.width() - lado - 40, r.height() - 8)
        p.setFont(self.font())
        fm = QFontMetricsF(self.font())
        caja = fm.boundingRect(texto_r, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.text())
        bloque = lado + 8 + caja.width()
        x0 = r.center().x() - bloque / 2
        dibujar_icono(p, self._clave, QRectF(x0, r.center().y() - lado / 2, lado, lado),
                      '#C9D6EC' if activo else '#5A6B87')
        p.setPen(QColor('#FFFFFF' if activo else '#5A6B87'))
        p.drawText(QRectF(x0 + lado + 8, r.top(), caja.width() + 2, r.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap), self.text())
        p.end()


class TextoAjustable(QLabel):
    """Texto que se parte en varias lineas SIN el heightForWidth de Qt (que
    dentro de un QScrollArea hace que las filas se pisen): el alto se
    calcula aqui a mano en cada cambio de ancho."""

    def __init__(self, texto='', tam=13, color=None, padre=None, peso=None, ancho=None):
        super().__init__(padre)
        self._ancho_previsto = ancho
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setFont(fuente(tam, peso=peso))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pal = self.palette()
        pal.setColor(self.foregroundRole(), QColor(ui._color(color or ui.TEXT_MUTED)))
        self.setPalette(pal)
        self.setText(str(texto))

    def hasHeightForWidth(self):
        return False

    def setText(self, texto):
        super().setText(str(texto))
        self._medir()

    def configure(self, text=None, text_color=None, **_):
        if text_color is not None:
            pal = self.palette()
            pal.setColor(self.foregroundRole(), QColor(ui._color(text_color)))
            self.setPalette(pal)
        if text is not None:
            self.setText(text)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._medir()

    def _medir(self):
        # antes de mostrarse el ancho real no se sabe: se usa el previsto
        ancho = self.width() if self.isVisible() or not self._ancho_previsto else self._ancho_previsto
        ancho = max(60, ancho)
        alto = self.fontMetrics().boundingRect(QRect(0, 0, ancho, 10000),
                                               int(Qt.TextFlag.TextWordWrap), self.text()).height()
        if self.minimumHeight() != alto + 2:
            self.setFixedHeight(alto + 2)


def _etiqueta_seccion(texto):
    e = Etiqueta(texto.upper(), 11, peso='negrita', color='#7F8DA8')
    f = e.font()
    f.setLetterSpacing(f.SpacingType.AbsoluteSpacing, 2.2)
    e.setFont(f)
    return e


# ---------------------------------------------------------------------------
# La capa que oscurece la ventana y aloja el panel
class CapaModal(QWidget):
    def __init__(self, ventana, panel, al_cerrar=None, cerrar_fuera=True, posicion=None):
        super().__init__(ventana)
        self._panel = panel
        self._al_cerrar = al_cerrar
        self._cerrar_fuera = cerrar_fuera
        self._posicion = posicion  # funcion(ancho_ventana, alto_ventana, panel) -> QRect
        panel.setParent(self)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        ventana.installEventFilter(self)
        self._opacidad = 0.0
        self._efecto = QGraphicsOpacityEffect(panel)
        self._efecto.setOpacity(0.0)
        panel.setGraphicsEffect(self._efecto)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._paso)
        self._ajustar()
        self.show()
        self.raise_()
        self._animar(1.0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def _paso(self, v):
        self._opacidad = float(v)
        if ui.vivo(self._efecto):
            self._efecto.setOpacity(self._opacidad)
        self.update()

    def _animar(self, hasta, al_final=None):
        self._anim.stop()
        self._anim.setStartValue(self._opacidad)
        self._anim.setEndValue(float(hasta))
        if getattr(self, '_al_final', None) is not None:
            try:
                self._anim.finished.disconnect(self._al_final)
            except Exception:
                pass
        self._al_final = al_final
        if al_final:
            self._anim.finished.connect(al_final)
        self._anim.start()

    def eventFilter(self, obj, ev):
        if obj is self.parentWidget() and ev.type() == QEvent.Type.Resize:
            self._ajustar()
        return False

    def _ajustar(self):
        v = self.parentWidget()
        self.setGeometry(0, 0, v.width(), v.height())
        if self._posicion:
            self._panel.setGeometry(self._posicion(v.width(), v.height(), self._panel))
        else:
            ancho = min(1240, v.width() - 80)
            alto = min(860, v.height() - 60)
            self._panel.setGeometry((v.width() - ancho) // 2, (v.height() - alto) // 2, ancho, alto)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColorReal(2, 4, 9, int(150 * self._opacidad)))
        p.end()

    def mousePressEvent(self, e):
        if self._cerrar_fuera and not self._panel.geometry().contains(e.position().toPoint()):
            self.cerrar()
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cerrar()
            e.accept()
            return
        super().keyPressEvent(e)

    def cerrar(self):
        if getattr(self, '_cerrando', False):
            return
        self._cerrando = True
        try:
            self.parentWidget().removeEventFilter(self)
        except Exception:
            pass
        fn = self._al_cerrar

        def fin():
            if fn:
                try:
                    fn()
                except Exception:
                    pass
            self.deleteLater()
        self._animar(0.0, fin)


class _Panel(QFrame):
    def __init__(self, padre=None, radio=18):
        super().__init__(padre)
        self.setObjectName('panelAjustes')
        self.setStyleSheet(ui.traducir_hoja(
            'QFrame#panelAjustes { background-color: #0B111D; border: 1px solid #22324F; border-radius: %dpx; }'
            ' QFrame#grupoAjustes { background-color: #0D1627; border: 1px solid #1E2A42; border-radius: 14px; }'
            ' QFrame#tarjetaMini { background-color: #0D1627; border: 1px solid #1E2A42; border-radius: 12px; }'
            % radio))


def _cabecera(sobre, titulo, al_cerrar, tam=30):
    w, c = caja_h(espacio=12)
    col, cc = caja_v(espacio=4)
    cc.addWidget(_etiqueta_seccion(sobre))
    cc.addWidget(Etiqueta(titulo, tam, peso='extra', color='#FFFFFF'))
    c.addWidget(col, 1)
    x = BotonIcono('cerrar', tr('Cerrar (Esc)'), lado=36, borde=False, radio=10)
    x.clicked.connect(lambda _=False: al_cerrar())
    c.addWidget(x, 0, Qt.AlignmentFlag.AlignTop)
    return w


# ---------------------------------------------------------------------------
# Licencia: lo que se muestra en el panel rapido y en «Acerca de»
def datos_licencia():
    """v5.2.1: la licencia de Lemon Squeezy guardada en este equipo (sin red)."""
    try:
        import licencia
        d = licencia.resumen()
        detalle = d['detalle']
        datos = licencia.local()
        if datos and d['activa']:
            detalle = licencia.clave_enmascarada(datos.get('clave')) + ' · ' + detalle
        color = {'ok': ui.VERDE, 'aviso': ui.AMBAR}.get(d['nivel'], ui.ROJO)
        return {'color': color, 'estado': d['estado'], 'detalle': detalle, 'activa': d['activa'],
                'hay_clave': d['hay_clave'], 'configurada': True}
    except Exception as ex:
        return {'color': ui.AMBAR, 'estado': tr('Desconocida'), 'detalle': str(ex), 'activa': False,
                'hay_clave': False, 'configurada': True}


def desactivar_licencia(app, al_terminar=None):
    if not messagebox.askyesno(tr('Desactivar este equipo'),
                               tr('CineCaptions dejará de funcionar en esta computadora hasta que vuelvas a '
                                  'activarla, y tu licencia quedará libre para usarla en otra.\n\n¿Desactivar?'),
                               parent=app):
        return

    def trabajo():
        import licencia
        return licencia.seguro(licencia.desactivar)

    def fin(r, error):
        ok = error is None and r is not None and r.ok
        if ok:
            messagebox.showinfo(tr('Equipo desactivado'), r.mensaje, parent=app)
        else:
            messagebox.showerror(tr('No pude desactivar'), str(error) if error is not None else r.mensaje, parent=app)
        try:
            app._licencia_refrescar()
        except Exception:
            pass
        if al_terminar:
            al_terminar()
        if ok:
            # sin licencia CineCaptions no sigue (igual que al abrir): la ventana de activar
            try:
                app._licencia_pedir(tr('Esta computadora ya no tiene la licencia activada.'), verificar=False)
            except Exception:
                pass
    correr_en_hilo(app, trabajo, fin)


NOTAS_VERSION = [
    ('5.4.18', [
        'Resolve Free: al abrirse con la app ya no aparece el falso aviso «Falla al iniciar: MCP de DaVinci Resolve» (el MCP es solo de Studio; Free trabaja por el Puente).',
        'Si tras actualizar el programa quedaba corriendo en Resolve un Puente de la versión anterior, CineCaptions lo releva solo (antes decía «Acción desconocida»).',
        'Al lanzar el Puente en una ventana de Resolve recién abierta, CineCaptions comprueba el foco antes de cada letra y se detiene si se va: ya no puede escribir en otra aplicación. En Mac, si Resolve está cerrado, también lo abre solo.',
    ]),
    ('5.4.17', [
        'DaVinci Resolve gratuito (Free) ya funciona igual que Studio: al soltar un video, CineCaptions crea el proyecto y el timeline con tu video, coloca los subtítulos, emojis y sonidos, aplica los efectos visuales (intro, zoom, transiciones) y quita las pausas, todo por el Puente.',
        'Si Resolve Free está abierto, CineCaptions lanza el Puente solo (ya no hay que ir al menú Área de trabajo > Scripts). Si está cerrado, lo abre; abre o crea un proyecto en Resolve (la pantalla de proyectos no vale) para que siga.',
        'Los mensajes de Inicio y del Registro dicen con claridad qué falló y qué probar; GO sigue sin decir «¡Listo!» si Resolve no colocó nada.',
    ]),
    ('5.4.16', [
        'DaVinci Resolve gratuito (Free): ahora los cinco estilos (VIRAL, Kinetic, Referencia, Base y Viral inferior) colocan sus subtítulos, emojis y sonidos por el Puente. Antes no colocaban nada porque Resolve Free 21.1 no deja a los scripts leer archivos. Los efectos visuales (intro, zoom y transiciones) siguen necesitando Studio y en Free se omiten con un aviso claro.',
        'Al terminar, Resolve se pone al frente (aunque estuviera detrás de otra ventana) y reproduce el timeline desde el principio.',
        'Los mensajes ya dicen la ruta real del menú de Resolve: Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente.',
        'La tarjeta de VIRAL en «Pack de estilos» ahora reproduce un video real, con todos sus captions (la pila de texto, los tres efectos, los emojis y la intro), en vez de una imagen fija.',
    ]),
    ('5.4.14', [
        'GO ya no dice «¡Listo!» si en Resolve no apareció nada: cuenta las líneas que Resolve colocó de verdad. Si no colocó ninguna, intenta repararlo solo (abrir el timeline, volver a Edit) y lo reintenta una vez; si sigue igual, te dice la causa en palabras claras y qué probar, y el Registro lo explica igual.',
        'Inicio dice qué DaVinci Resolve detectó (Studio o Free) y por dónde se conecta, o si está cerrado / falta lanzar el Puente, antes de seguir con el proceso.',
        'Al terminar GO, Resolve queda en la página Edit con tu disposición de pantalla guardada (Ajustes > «Guardar la vista actual de Resolve»: ponla vertical y expandida una vez), el cabezal al inicio y reproduce el timeline desde el principio. Todo se puede apagar en Ajustes.',
        'Un video soltado arma siempre un timeline vertical (1080×1920), sea cual sea su orientación; se apaga en Ajustes con «Abrir siempre en vertical».',
    ]),
    ('5.4.13', [
        'Sonido por palabra: ahora alterna tres sonidos (TAP_POP, typewriter e Iphone Taping) y eliges en qué palabras suena: en cada una, solo en la principal (con un sonido propio por efecto: cristal, selección, arrastre, héroe) o en ninguna. Cada sonido empieza un poco antes de su pico para que el golpe caiga justo cuando entra la palabra.',
        'Intro: el «Viral Hooks Riser» (sus últimos 2 s, hasta su pico) con el destello de luz y un golpe de zoom justo en ese pico (página Efectos). Las transiciones «destello» suenan como el obturador de una cámara (Shuter 11 y 13).',
        'Al elegir VIRAL, Kinetic o Referencia, el sonido y la página Efectos quedan ya configurados como recomendación para ese estilo (lo cambias después donde quieras).',
        'Referencia: el barrido de luz recorre ahora toda la palabra (antes se quedaba a medias) y hay variantes «Screen» y «Sólido» con colores distintos. VIRAL: cada efecto sale en 4 colores (Shatter: azul cielo, rosa, lima y oro; Select: caja roja, azul, verde y naranja; Drag: blanco, amarillo, cian y rosa).',
        'Emojis: elige el estilo en el selector (Animado, 3D de Microsoft Fluent, Google o Sistema); los 3D y los de Google se bajan al usarlos y se pueden bajar todos de una vez. El sonido del emoji sustituye al toque de su palabra para que no suenen dos a la vez.',
    ]),
    ('5.4.11', [
        'VIRAL · «Shatter» rehecho como en la referencia: azul cielo, con un barrido de luz que cruza la palabra y se rompe como un vidrio quebrado en varios fragmentos con bordes inclinados que se separan y giran.',
        'VIRAL · los tres efectos (Select, Shatter y Drag) salen turnándose también en videos de habla rápida: antes, si el efecto que tocaba no cabía en el tiempo del bloque, siempre caía en Shatter.',
        'Soltar un video: si Resolve devuelve un Media Pool vacío justo al crear el proyecto («NoneType… GetClipList»), ahora reintenta en vez de detenerse.',
    ]),
    ('5.4.9', [
        'Estilo nuevo «VIRAL» (carpeta ESTILO VIRAL): subtítulos palabra a palabra con líneas finas y la palabra con peso en negrita cursiva, y tres efectos para la palabra clave: «Shatter» (rosa que se parte en franjas), «Select» (se escribe, un cursor la selecciona y se dibuja una caja roja punteada) y «Drag» (una mano arrastra su contorno punteado y lo rellena de blanco con brillo).',
        'VIRAL funciona en vertical y en horizontal, con los sonidos por palabra, los emojis y los efectos visuales de la página Efectos. En Creativo, las palabras que pintas como «Principal» llevan el efecto (si pintas alguna, solo ellas; sin marcas, GO reparte los efectos solo, uno de cada dos bloques).',
        'El colocador de Resolve que comparten Kinetic y VIRAL ahora acepta packs con otros clips y pone también los emojis; el banco de pruebas ya no borra tu cola de render.',
    ]),
    ('5.4.8', [
        'Efectos con movimiento en la página «Efectos»: zoom lento, temblor con los golpes de sonido, transiciones nuevas en los cortes (zoom desenfocado, barrido y glitch RGB) y fondo desenfocado cuando el video no llena el cuadro. Se aplican con Fusion al propio video, así que tu corrección de color sigue valiendo. Hay una intensidad general y una vista previa de 3 segundos.',
        '«Más efectos» (plegado en la página Efectos): números 1, 2, 3 cuando enumeras, pegatinas en palabras clave, subrayado o círculo dibujado a mano, polvo, grano o luz suave, tus propios efectos (MOV, MP4, PNG, GIF o WebP) y un cierre con tu logo y su sonido. Esquivan los captions y la cara.',
        'Quitar pausas: GO recorta los silencios del video que sueltas en Inicio antes de poner los captions (que ya salen con los tiempos nuevos) y puede alternar un zoom en cada corte.',
        'Sonido extra: un sonido en cada transición, riser y golpe antes de la palabra clave del gancho, música de fondo que baja sola cuando hablas (con detección de BPM para alinear su pulso), volumen de los sonidos igualado y sonido de los emojis según la frase.',
        'B-roll opcional: tomas de apoyo gratuitas de Pexels en las palabras concretas (casa, playa, coche…), debajo de los captions. Necesita tu clave de API gratuita.',
        'GO se puede pausar, cancelar y reanudar; si el programa se cierra a mitad, te ofrece seguir donde se quedó. Dice el idioma que oyó y te deja corregirlo, y te avisa con una notificación del sistema al terminar. El cuadro de Novedades ahora enseña clips en movimiento.',
        'Más rápido y robusto: reutiliza la transcripción de un video ya hecho, usa tu tarjeta gráfica para la voz (se repara desde Ajustes), avisa si Resolve se quedó colgado y las descargas se reanudan si se cortan.',
    ]),
    ('5.4.7', [
        'Nueva página «Efectos» (viene activada): intro con sonido —sube el riser y, cuando llega al final, el destello cubre la imagen; puedes cambiar o silenciar el sonido—, transiciones que esconden cada corte entre tomas e iconos flotantes animados con desenfoque. Se colocan solos al hacer GO, junto a los captions, la música y los emojis, en pistas propias «FX» de Resolve Studio (tu video y tus captions no se tocan).',
        'Iconos flotantes a tu gusto: apágalos o deja solo los packs que quieras y, al hacer clic en un pack, escribe en qué palabras sale. También pueden salir en las frases importantes (un número, un aviso, una pregunta, el gancho).',
        'Chip «Visuales» en Inicio para activar o desactivar todos los efectos de un clic.',
        'Los estilos de fábrica pasan a llamarse «Shine Kinetic» y «Shine Referencia»: vienen con el programa y no se pueden quitar. El slider de Proyecto reproduce un video real con los captions de cada uno, tal como quedan en la línea de tiempo.',
        '«Crea tu estilo» más fácil: cada ejemplo se ve sobre una foto de muestra con su animación completa (entrada, texto y salida) y se ordena con los botones «Texto alto», «Texto medio» y «Texto bajo». En Proyecto se quitó «Mostrar los packs quitados».',
    ]),
    ('5.4.4', [
        'Proyecto más simple: el slider ahora muestra solo tus packs (se quitaron las tarjetas «Mis plantillas del Media Pool» y «Diseño automático») y desaparece el botón «Vista real · Resolve»: las vistas reales se piden solas cuando Resolve está abierto.',
        '«Crea tu estilo» mucho más fácil: una sola galería con todos los estilos (sin filtros, sin botones por tarjeta, sin «Abrir en Resolve» ni «!»). Tocas hasta 3, le pones nombre y pulsas «Crear mi pack».',
    ]),
    ('5.4.3', [
        'Proyecto compacto: el audio (Obtener, archivo, onda y motor de voz) pasa a una sola franja arriba del slider, dentro de la tarjeta de «Pack de estilos». La pantalla ya no se desplaza hacia abajo y el slider se estira con el alto de la ventana para que resalte.',
        'Ajustes > Acerca de más limpio: estando al día solo queda el botón «Buscar actualizaciones» (sin «Leer notas» ni «Tienes la última versión»); si hay una versión nueva aparecen sus notas y el botón «Actualizar».',
    ]),
    ('5.4.2', [
        'Avisa al momento de las versiones nuevas: CineCaptions mira cada 10 segundos (en Windows y en Mac) si hay una actualización y, en cuanto sale, te lo dice con un cuadro que enseña todas sus mejoras y los botones «Actualizar ahora» / «Más tarde». Ya no hace falta ir a buscarla.',
        'Ajustes > Acerca de: «Buscar actualizaciones» ahora es un botón; arriba tiene el texto «Leer notas» con las mejoras de la versión disponible, y cuando hay una nueva el botón pasa a ser «Actualizar a la X».',
        'Al abrir CineCaptions recién actualizado sale un cuadro de «Novedades» con TODAS las mejoras desde tu versión anterior (una sola vez).',
    ]),
    ('5.4.1', [
        'Estilo nuevo «Kinetic» (títulos de gancho): una palabra HÉROE enorme con degradado, líneas pequeñas que la anuncian, cintas de color, serif cursiva, pincel, anillos y subrayados. Cada bloque entra con rebote y sale junto, sin pisar al siguiente. Elígelo en Proyecto (tarjeta «Kinetic») o en el chip «Estilo» de Inicio; con él GO decide solo qué palabra es el héroe y, en Creativo, las palabras que marques como Principal lo son.',
        'Funciona con cualquier video vertical (probado en 1080×1920 y 2160×3840), cualquier duración y cantidad de palabras, y con los sonidos de Sonido. Los demás estilos no cambian.',
        'Proyecto: «Crea tu estilo» pasa a ser un solo botón junto a «Vista real · Resolve» (se quitó la banda de abajo) y la rueda del ratón en esa pantalla mueve el slider de packs en vez de bajar la página.',
        'Si el archivo del video ya no está donde estaba (lo moviste o le cambiaste el nombre), GO lo dice claro en vez de «la transcripción no pudo terminar».',
        'Inicio ahora dice cuánto falta: debajo del porcentaje sale el tiempo restante («~ 75 s») y el paso en curso («Transcribiendo · 2/6»); si un paso tarda más de lo normal lo avisa. Aprende lo que tarda en tu equipo.',
        'Errores que explican: si GO falla dice en qué paso falló y por qué (video renombrado o movido, sin voz, Resolve cerrado o sin responder, pack que no cargó, proyecto que no se pudo crear, archivo dañado) y qué probar. Soltar un archivo que no existe también avisa.',
        'El audio original de tu video se comprueba en la pista A1 al armar el timeline y al terminar GO, y se repone si faltara. Con el idioma en «Detectar», los títulos usan el idioma que se oye (antes un video en inglés podía salir con palabras en español).',
        'Kinetic: el texto pequeño lleva contorno oscuro (se lee sobre fondos claros) y los anillos solo rodean palabras cortas, sin pisar a las líneas de al lado. Si la IA de texto se cuelga, pasa al modelo ligero a los 100 s y lo recuerda.',
    ]),
    ('5.3.9', [
        'Corregido: al actualizar desde el propio programa el instalador a veces fallaba con «algún archivo está en uso». Ahora reemplaza la versión sin problema (y reintenta si el antivirus retiene la carpeta un momento) y CineCaptions se vuelve a abrir solo.',
    ]),
    ('5.3.7', [
        'Ajustes más limpios: se quitaron «Recibir versiones beta» y el recorrido guiado (ya no sale al abrir el programa).',
    ]),
    ('5.3.6', [
        'Proyecto rediseñado: «Pack de estilos» ahora es un slider horizontal de tarjetas verticales con tus fotos de video de fondo; la del centro va grande y con sus captions en movimiento (la vista real de Resolve compuesta sobre la foto), las de los lados giran y se apagan, y todo se desliza con un resorte (arrastra, rueda lateral, flechas o puntos).',
        '«Crea tu estilo» tiene su propia sección justo debajo del slider. Se quitó la tarjeta «Tipografías que usa el pack» (si a un pack le faltan fuentes, el aviso sale bajo el slider con el botón «instalar») y el filtro horizontal/vertical: las vistas son siempre verticales.',
    ]),
    ('5.3.5', [
        'Actualizaciones automáticas: CineCaptions mira solo (como mucho cada 12 horas) si hay una versión nueva y aparece el chip «Nueva versión» en Inicio. Un clic la descarga, comprueba su huella SHA-256 y la instala; el programa se cierra y se abre solo, sin tocar proyectos, licencia ni ajustes. Se puede apagar en Ajustes > Acerca de.',
        'El logo de Cinema Productions está en la esquina de Inicio, en el instalador y en Ajustes > Acerca de.',
    ]),
    ('5.3.4', [
        'Mac: GO por fin encuentra el servidor MCP de DaVinci Resolve (estaba buscándolo en una carpeta equivocada y caía al Puente de Resolve gratuito, que a veces perdía la conexión). Con Resolve Studio ya no hace falta el Puente.',
        'Si Resolve Studio tiene los scripts externos apagados (Preferencias > Sistema > General > External scripting using), el aviso lo dice con los pasos exactos en vez de hablar del Puente.',
    ]),
    ('5.3.3', [
        'Creativo detecta solo lo que hay en Proyecto: si ya trajiste el audio de Resolve o elegiste un video, la pantalla lo muestra; si ya tiene palabras transcritas, el editor se abre solo, y si falta transcribir basta un botón (Transcribir y retocar). También avisa de la línea de tiempo abierta en Resolve.',
    ]),
    ('5.3.2', [
        'Vigilancia: GO y Generar avisan si algo se queda sin avanzar y cierran solos el motor de voz o de IA que no responde; si un modelo falla se cambia solo al de respaldo (Qwen 1.7B → 0.6B → CPU → Whisper; IA de texto → modelo ligero → reglas).',
        'Registro: errores.log con todos los avisos y errores, informe de soporte (Windows y Mac) en «Copiar informe», aviso de si la sesión anterior no llegó a abrir y chequeo de librerías, disco y memoria al iniciar.',
        'Flujo coherente: el pack de Estilos y el de GO son uno solo, «Emojis: no» y «Efectos» de Inicio se respetan en Creativo y Generar, y «Editar marcas» después de GO enseña lo mismo que se colocó.',
        'Desinstalador a fondo: cierra los motores, quita scripts de Resolve, tipografías, accesos, claves de Windows y temporales, y puede borrar también tus datos, tu licencia y los modelos descargados. Lo que no se pueda borrar en ese momento se borra solo al reiniciar sesión.',
        'Los instaladores salen con su versión en el nombre (Instalar_CineCaptions_5.3.2.exe) y los scripts de Resolve se ponen solos a la versión del programa.',
    ]),
    ('5.3.0', [
        'Estructura nueva de los packs (.drb): arriba · principal · abajo · imagen, con hasta 3 variantes (se agrega 2 o 3 al final del nombre) y «simple» para las palabras sueltas. Los packs hechos antes siguen funcionando.',
        'Bloque «imagen»: el emoji o icono que eliges en Creativo va en ese bloque del pack (o debajo del texto si el pack no lo trae), y lo ves en la vista previa del bloque.',
        'Plantilla base nueva, hecha solo con Luxe Slide y Luxe Shine (Joel Van Beek): tres variantes (cian, rosa y fuego) con texto Regular o Bold para resaltar.',
        'Proyecto: «Fuente» pasa a «Audio» con un solo botón, «Obtener», que trae el audio de tu timeline por MCP. En Pack de estilos, cada pack muestra su estructura y hay un botón «Crea tu estilo» que abre en Resolve una guía paso a paso.',
        'Composición y vista previa del estilo incluyen el espacio del icono o la imagen.',
        'Motion Graphics en toda la interfaz: tarjetas que entran con marcas de encuadre, títulos que se escriben letra a letra, traza de luz en las tarjetas y formas que derivan al fondo. Inicio estrena un visor con REC, timecode, dial y órbitas.',
        'GO más rápido: la voz (Qwen3-ASR) y la IA de texto se cargan y se calientan en paralelo mientras Resolve prepara el audio, se transcribe por lotes y la IA de texto trabaja en tramos pequeños; el uso de la GPU se adapta a su memoria.',
        'Audio: elige cómo transcribir (IA Qwen3-ASR o Whisper large-v3-turbo). Se corrigió un cuelgue de Whisper tras un fallo de CUDA y la interfaz baja sola los fotogramas del fondo si va justa, para que GO tenga más CPU.',
        'Se quitaron las plantillas antiguas «Títulos dinámicos II» (inferior y superior) y la composición del bloque se recorre con flechas, con el icono arriba o abajo del texto.',
    ]),
    ('5.2.1', [
        'Licencias de Lemon Squeezy: pega tu clave y se activa en segundos (ya no hace falta el correo ni el código de Hotmart).',
        'Ventana de licencia nueva, con el mismo formato que CineSlide: panel animado, la tienda reconocida por el formato de la clave y confeti al activarla.',
        'Funciona hasta 7 días sin internet y se verifica sola en segundo plano.',
        'Ajustes > Acerca de muestra tu licencia y deja desactivar este equipo para usarla en otra computadora.',
    ]),
    ('5.2.0', [
        'GO abre DaVinci Resolve si está cerrado, carga tu proyecto más reciente y su timeline, todo por el MCP oficial.',
        'Vista previa REAL antes de lanzar: Resolve renderiza los bloques con tu pack sobre tu propio vídeo.',
        'Estilos y composición con vistas reales animadas de cada pack (.drb), renderizadas por Resolve.',
        '«Asistencia» más inteligente, con criterio de subtítulos virales: corrige, quita puntos, comillas y signos, elige las palabras clave y pone los emojis en una sola pasada.',
        'La IA de texto queda cargada unos minutos: la segunda vez responde en segundos.',
        'Los emojis del editor caben dentro de cada ficha, sin taparse.',
        'Inicio espectacular: fondo vivo, botón GO con anillo de energía, demo de subtítulos animados y confeti al terminar.',
        'Las pestañas se unifican: «Proyecto» reúne Nuevo proyecto y Estilos; GO elige pack, idioma, efectos y formato sin salir de Inicio.',
        'La interfaz se adapta a pantallas pequeñas y siempre está en movimiento (con opción de reducir animaciones).',
        'Chequeo de librerías en cada arranque e iconos de línea modernos.',
        'El instalador detecta en segundos la IA ya instalada y no la repite; banner nuevo.',
        'Marca: Cinema Productions.',
    ]),
    ('5.1.0', [
        'Inicio con un solo botón GO: trae el timeline, transcribe, corrige, elige las palabras, aplica el diseño de 3 líneas y los efectos, enseña la vista previa y lo coloca, todo con un clic.',
        'IA de texto local (Qwen3): corrige la transcripción y elige las palabras clave con criterio, sin coste por uso.',
        'Editor de palabras más minimalista, con «Asistencia».',
        'Conexión con DaVinci Resolve 21 por su servidor MCP oficial: sin lanzar el Puente y cada orden en milésimas.',
        'Vista previa del estilo sobre el fotograma real de tu timeline.',
        'Motor de voz Qwen3-ASR (2026) con tiempos por palabra; Whisper large-v3-turbo de respaldo.',
        'Ajustes nuevos: temas, color de resaltado, tamaño de la interfaz, atajos y ayuda.',
        'Copias de seguridad de tus proyectos y ajustes, y canal de versiones beta.',
        'Botón para fijar CineCaptions encima de Resolve.',
    ]),
    ('5.0.0', [
        'Nuevo nombre: CineCaptions. Interfaz nueva en Qt con 5 pantallas y menú lateral.',
        'Editor de palabras y SFX Lab como pantallas; recetas rápidas; estado del sistema.',
    ]),
]


class _CabeceraVersion(QWidget):
    """La cabecera de cada versión en las notas: número, etiqueta «Actual», cuántas novedades trae y un chevron. Un clic abre/cierra."""
    clic = Signal()

    def __init__(self, version, n, actual, padre=None):
        super().__init__(padre)
        self._version, self._n, self._actual = version, n, actual
        self._abierta = False
        self._hover = False
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner_abierta(self, si):
        self._abierta = bool(si)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clic.emit()
        super().mousePressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 8))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 12, 12)
        x = 18.0
        p.setPen(QColor('#FFFFFF'))
        f = fuente(17, peso='negrita')
        p.setFont(f)
        txt = f'{self._version}'
        ancho = QFontMetricsF(f).horizontalAdvance(txt)
        p.drawText(QRectF(x, 0, ancho + 4, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), txt)
        x += ancho + 12
        if self._actual:
            fa = fuente(11, peso='negrita')
            t = tr('ACTUAL')
            wa = QFontMetricsF(fa).horizontalAdvance(t) + 18
            ac = QColor(ui.ACCENT)
            p.setBrush(QColor(ac.red(), ac.green(), ac.blue(), 40))
            p.setPen(QPen(QColor(ac.red(), ac.green(), ac.blue(), 130), 1))
            p.drawRoundedRect(QRectF(x, 16, wa, 22), 11, 11)
            p.setPen(QColor(ui.ACCENT_CLARO))
            p.setFont(fa)
            p.drawText(QRectF(x, 16, wa, 22), int(Qt.AlignmentFlag.AlignCenter), t)
            x += wa + 12
        p.setPen(QColor('#7F8DA8'))
        p.setFont(fuente(13))
        p.drawText(QRectF(x, 0, 260, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   tr('{n} novedades', n=self._n) if self._n != 1 else tr('1 novedad'))
        # chevron
        cx, cy = self.width() - 26.0, self.height() / 2.0
        p.setPen(QPen(QColor('#9FB0CC'), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self._abierta:
            p.drawPolyline([QPointF(cx - 5, cy + 2.5), QPointF(cx, cy - 2.5), QPointF(cx + 5, cy + 2.5)])
        else:
            p.drawPolyline([QPointF(cx - 5, cy - 2.5), QPointF(cx, cy + 2.5), QPointF(cx + 5, cy - 2.5)])
        p.end()


def _item_nota(texto):
    """Una novedad: viñeta del acento y el texto con su primera idea (hasta los dos puntos) en negrita."""
    import html
    fila = QWidget()
    h = QHBoxLayout(fila)
    h.setContentsMargins(20, 0, 18, 0)
    h.setSpacing(12)
    punto = QLabel()
    punto.setFixedSize(8, 8)
    ac = QColor(ui.ACCENT)
    punto.setStyleSheet(f'background: rgb({ac.red()}, {ac.green()}, {ac.blue()}); border-radius: 4px;')
    h.addWidget(punto, 0, Qt.AlignmentFlag.AlignTop)
    h.itemAt(0).widget().setContentsMargins(0, 0, 0, 0)
    corte = texto.find(':')
    if 0 < corte <= 56:
        cuerpo = f'<b style="color:#FFFFFF">{html.escape(texto[:corte])}</b><span style="color:#B7C4DB">{html.escape(texto[corte:])}</span>'
    else:
        cuerpo = f'<span style="color:#C9D6EC">{html.escape(texto)}</span>'
    t = QLabel(cuerpo)
    t.setTextFormat(Qt.TextFormat.RichText)
    t.setWordWrap(True)
    t.setFont(fuente(13))
    t.setStyleSheet('background: transparent;')
    h.addWidget(t, 1)
    # la viñeta baja un poco para alinearse con la primera línea
    punto.setContentsMargins(0, 0, 0, 0)
    fila.layout().setAlignment(punto, Qt.AlignmentFlag.AlignTop)
    punto.setFixedSize(8, 8)
    h.setContentsMargins(20, 0, 18, 0)
    return fila


class DialogoNotas(ui.Dialogo):
    """Las notas de la versión: una sección por versión (la actual abierta, las demás plegadas), novedades con viñeta y su idea en
    negrita. Sustituye al cuadro de texto plano."""

    def __init__(self, padre=None):
        super().__init__(padre, tr('Notas de la versión'), 780, 660, redimensionable=True, minimo=(560, 420))
        from PySide6.QtWidgets import QScrollArea
        capa = QVBoxLayout(self)
        capa.setContentsMargins(28, 24, 28, 20)
        capa.setSpacing(14)
        capa.addWidget(_etiqueta_seccion(tr('Novedades')))
        capa.addWidget(Etiqueta(tr('Notas de la versión'), 26, peso='extra', color='#FFFFFF'))
        capa.addWidget(Etiqueta(tr('Lo nuevo de CineCaptions, de la versión más reciente a la más antigua.'), 13, color='#8D9BB5'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }')
        cont = QWidget()
        v = QVBoxLayout(cont)
        v.setContentsMargins(0, 4, 8, 4)
        v.setSpacing(12)
        self._secciones = []
        for i, (version, lineas) in enumerate(NOTAS_VERSION):
            caja = QFrame()
            caja.setObjectName('notaVersion')
            caja.setStyleSheet(ui.traducir_hoja('QFrame#notaVersion { background: #0E1628; border: 1px solid #1E2A42; border-radius: 14px; }'))
            cv = QVBoxLayout(caja)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(0)
            cab = _CabeceraVersion(version, len(lineas), i == 0)
            cv.addWidget(cab)
            cuerpo = QWidget()
            cb = QVBoxLayout(cuerpo)
            cb.setContentsMargins(0, 0, 0, 16)
            cb.setSpacing(12)
            for linea in lineas:
                cb.addWidget(_item_nota(tr(linea)))
            cv.addWidget(cuerpo)
            abierta = i == 0
            cuerpo.setVisible(abierta)
            cab.poner_abierta(abierta)

            def alternar(c=cuerpo, h=cab):
                c.setVisible(not c.isVisible())
                h.poner_abierta(c.isVisible())
            cab.clic.connect(alternar)
            v.addWidget(caja)
            self._secciones.append((cab, cuerpo))
        v.addStretch(1)
        scroll.setWidget(cont)
        capa.addWidget(scroll, 1)
        pie, cp = caja_h(espacio=10)
        cp.addStretch(1)
        cp.addWidget(Boton(tr('Entendido'), self.accept, tipo='primario', alto=42, ancho=140, tam=14, negrita=True))
        capa.addWidget(pie)


def mostrar_notas(app):
    DialogoNotas(app).exec()


def lineas_de_notas(texto):
    """Las notas que publica el manifiesto (un texto con una mejora por línea, con o sin viñeta) -> lista de líneas."""
    salida = []
    for l in str(texto or '').replace('\r', '').split('\n'):
        l = l.strip().lstrip('•-–·* ').strip()
        if l:
            salida.append(l)
    return salida


def notas_desde(version_vista):
    """[(versión, [líneas])] de lo que cambió desde `version_vista` (exclusive) hasta la instalada; sin versión previa, solo la instalada."""
    import actualizaciones
    actual = _version()
    if not version_vista:                       # primera vez que se anota qué versión se ve (también al venir de una anterior a la 5.4.2): la instalada y la de antes
        return [(v, l) for v, l in NOTAS_VERSION if not actualizaciones.es_mas_nueva(v, actual)][:2] or NOTAS_VERSION[:1]
    return [(v, l) for v, l in NOTAS_VERSION if actualizaciones.es_mas_nueva(v, version_vista) and not actualizaciones.es_mas_nueva(v, actual)] or NOTAS_VERSION[:1]


class DialogoNotasVersion(ui.Dialogo):
    """Un cuadro con las mejoras (viñetas) de una o varias versiones y los botones que se le pasen: lo usan «Hay una versión nueva» (Actualizar ahora /
    Más tarde), «Leer notas» de la versión disponible y las «Novedades» que salen al abrir CineCaptions ya actualizado. `valor` = el botón pulsado."""

    def __init__(self, padre, titulo, subtitulo, secciones, botones, etiqueta=''):
        super().__init__(padre, titulo, 720, 620, redimensionable=True, minimo=(520, 380))
        from PySide6.QtWidgets import QScrollArea
        self.valor = None
        capa = QVBoxLayout(self)
        capa.setContentsMargins(28, 24, 28, 20)
        capa.setSpacing(14)
        if etiqueta:
            capa.addWidget(_etiqueta_seccion(etiqueta))
        capa.addWidget(Etiqueta(titulo, 24, peso='extra', color='#FFFFFF', envolver=True))
        if subtitulo:
            capa.addWidget(Etiqueta(subtitulo, 13, color='#8D9BB5', envolver=True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }')
        cont = QWidget()
        v = QVBoxLayout(cont)
        v.setContentsMargins(0, 4, 8, 4)
        v.setSpacing(12)
        try:                                                  # v5.4.8: lo nuevo se VE: clips cortos en bucle de las versiones que se muestran
            import novedades_visuales
            tira = novedades_visuales.tira(novedades_visuales.clips_de([s[0] for s in secciones if s[0]]))
            if tira is not None:
                v.addWidget(tira)
        except Exception:
            pass
        for version, lineas in secciones:
            caja = QFrame()
            caja.setObjectName('notaVersion')
            caja.setStyleSheet(ui.traducir_hoja('QFrame#notaVersion { background: #0E1628; border: 1px solid #1E2A42; border-radius: 14px; }'))
            cv = QVBoxLayout(caja)
            cv.setContentsMargins(0, 14, 0, 14)
            cv.setSpacing(12)
            if version:
                cab = Etiqueta(f'v{version}', 15, peso='extra', color=ui.ACCENT_CLARO)
                cab.setContentsMargins(20, 0, 20, 0)
                cv.addWidget(cab)
            for linea in lineas:
                cv.addWidget(_item_nota(tr(linea)))
            v.addWidget(caja)
        v.addStretch(1)
        scroll.setWidget(cont)
        capa.addWidget(scroll, 1)
        pie, cp = caja_h(espacio=10)
        cp.addStretch(1)
        for texto, valor, tipo in botones:
            cp.addWidget(Boton(texto, lambda _=None, val=valor: self._elegir(val), tipo=tipo, alto=42, tam=14, negrita=(tipo == 'primario')))
        capa.addWidget(pie)

    def _elegir(self, valor):
        self.valor = valor
        self.accept()


def pedir_actualizacion(app, r):
    """«Hay una versión nueva»: sus mejoras y, abajo, «Actualizar ahora» / «Más tarde». True si el usuario quiere actualizar."""
    lineas = lineas_de_notas(r.get('notas')) or [tr('Mejoras y correcciones.')]
    d = DialogoNotasVersion(app, tr('Hay una versión nueva: {v}', v=r.get('version')),
                            tr('Estás en la {a}. Estas son las mejoras de la {v}:', a=_version(), v=r.get('version')),
                            [(r.get('version'), lineas)], [(tr('Más tarde'), 'luego', 'neutro'), (tr('Actualizar ahora'), 'actualizar', 'primario')], tr('Actualización'))
    d.exec()
    return d.valor == 'actualizar'


def mostrar_notas_version(app, r):
    """«Leer notas» de la versión disponible (sin actualizar todavía)."""
    lineas = lineas_de_notas(r.get('notas')) or [tr('Mejoras y correcciones.')]
    d = DialogoNotasVersion(app, tr('Mejoras de la versión {v}', v=r.get('version')), tr('Esto trae la actualización disponible.'), [(r.get('version'), lineas)],
                            [(tr('Cerrar'), 'cerrar', 'neutro')] + ([(tr('Actualizar ahora'), 'actualizar', 'primario')] if hasattr(app, '_ofrecer_actualizacion') else []), tr('Novedades'))
    d.exec()
    if d.valor == 'actualizar' and hasattr(app, '_ofrecer_actualizacion'):
        app._ofrecer_actualizacion(r, confirmado=True)


def mostrar_novedades(app, version_vista=None):
    """Al abrir CineCaptions ya actualizado: TODAS las mejoras desde la versión que tenías."""
    secciones = notas_desde(version_vista)
    d = DialogoNotasVersion(app, tr('CineCaptions {v} está instalado', v=_version()),
                            tr('Estas son las mejoras que trae.') if len(secciones) == 1 else tr('Estas son todas las mejoras desde tu versión anterior.'),
                            secciones, [(tr('Entendido'), 'ok', 'primario')], tr('Novedades'))
    d.exec()


class ControlActualizacion(QWidget):
    """El bloque «Actualizaciones» de Ajustes > Acerca de: una línea de estado, arriba del botón el texto «Leer notas» (las mejoras de la versión nueva, o las
    de la instalada si no hay) y un botón: «Buscar actualizaciones», o «Actualizar a X» cuando el programa ya sabe que hay una versión nueva (lo vigila solo)."""

    def __init__(self, app, padre=None):
        super().__init__(padre)
        self.app = app
        c = QVBoxLayout(self)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(8)
        self.estado = Etiqueta('', 13, color=ui.TEXT_MUTED, envolver=True)
        c.addWidget(self.estado)
        self.leer = Enlace(tr('Leer notas'), self._leer_notas, 13, color=ui.ACCENT_CLARO, color_hover='#FFFFFF', subrayada=False, peso='negrita')
        c.addWidget(self.leer)
        self.buscar = Boton(tr('Buscar actualizaciones'), lambda: buscar_actualizaciones(self.app, self.estado), tipo='neutro', alto=46, tam=15)
        c.addWidget(self.buscar)
        self.actualizar = Boton('', self._actualizar, tipo='primario', alto=46, tam=15, negrita=True)
        c.addWidget(self.actualizar)
        self._reloj = QTimer(self)
        self._reloj.setInterval(1500)
        self._reloj.timeout.connect(self.refrescar)
        self._reloj.start()
        self.refrescar()

    def _hay(self):
        r = getattr(self.app, '_actualizacion', None)
        return r if isinstance(r, dict) and r.get('version') else None

    def refrescar(self):
        r = self._hay()
        if r:
            self.estado.configure(text=tr('Hay una versión nueva: {v}', v=r['version']))
            self._estado_auto = True
            self.leer.configure(text=tr('Leer notas de la {v}', v=r['version']))
            self.actualizar.configure(text=tr('Actualizar a la {v}', v=r['version']))
        elif getattr(self, '_estado_auto', False):        # la versión nueva ya no está (se instaló): se apaga el aviso
            self.estado.configure(text='')
            self._estado_auto = False
        # al día = nada que decir: sin «tienes la última versión» ni «Leer notas»; el estado solo se ve al buscar a mano o cuando hay una versión nueva
        self.estado.setVisible(bool(self.estado.text()))
        self.leer.setVisible(bool(r))
        self.actualizar.setVisible(bool(r))
        self.buscar.setVisible(not r)

    def _leer_notas(self):
        r = self._hay()
        if r:
            mostrar_notas_version(self.app, r)
        else:
            mostrar_notas(self.app)

    def _actualizar(self):
        r = self._hay()
        if r and hasattr(self.app, '_ofrecer_actualizacion'):
            self.app._ofrecer_actualizacion(r)


def buscar_actualizaciones(app, etiqueta=None):
    import actualizaciones
    beta = False
    if etiqueta is not None:
        etiqueta.configure(text=tr('Buscando actualizaciones…'))

    def fin(r, error):
        if error is not None:
            r = {'estado': 'error', 'mensaje': str(error)}
        estado = r.get('estado')
        if estado == 'al_dia':
            app._act_comprobada = True
        if estado == 'nueva':
            texto = tr('Hay una versión nueva: {v}', v=r.get('version'))
            if etiqueta is not None and ui.vivo(etiqueta):
                etiqueta.configure(text=texto)
            if hasattr(app, '_ofrecer_actualizacion'):
                app._ofrecer_actualizacion(r)           # v5.3.5: la app la descarga, comprueba su huella y la instala (o abre la descarga si no hay archivo para este equipo)
                return
            if messagebox.askyesno(tr('Actualización disponible'),
                                   texto + ('\n\n' + r['notas'] if r.get('notas') else '')
                                   + '\n\n' + tr('¿Abrir la descarga?'), parent=app) and r.get('url'):
                webbrowser.open(r['url'])
            return
        textos = {'al_dia': tr('CineCaptions está actualizado.'),
                  'sin_canal': tr('Todavía no hay un canal de actualizaciones publicado.'),
                  'error': tr('No pude comprobarlo: sin conexión o el servidor no respondió.')}
        if etiqueta is not None and ui.vivo(etiqueta):
            etiqueta.configure(text=textos.get(estado, ''))
    correr_en_hilo(app, lambda: actualizaciones.comprobar(_version(), beta), fin)


# ---------------------------------------------------------------------------
# Panel rapido (imagen 2 de la referencia): se abre con «Ajustes»



class PanelRapido(_Panel):
    ANCHO = 420

    def __init__(self, app, al_expandir):
        super().__init__(radio=20)
        self.app = app
        self._capa = None
        self.setFixedWidth(self.ANCHO)
        c = QVBoxLayout(self)
        c.setContentsMargins(28, 24, 28, 24)
        c.setSpacing(16)
        c.addWidget(_cabecera(tr('Ajustes de la aplicación'), tr('Acerca de CineCaptions'), self.cerrar, tam=26))
        c.addWidget(Separador())
        fila, cf = caja_h(espacio=8)
        cf.addWidget(Etiqueta('CineCaptions', 15, peso='negrita', color='#FFFFFF'))
        cf.addStretch(1)
        self.version_lbl = Etiqueta(f'v{_version()} · ' + texto_canal(), 13, color=ui.TEXT_MUTED)
        cf.addWidget(self.version_lbl)
        c.addWidget(fila)
        # licencia
        lic = QFrame()
        lic.setObjectName('tarjetaMini')
        cl = QVBoxLayout(lic)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(6)
        f1, c1 = caja_h()
        c1.addWidget(Etiqueta(tr('Licencia'), 14, peso='negrita', color='#FFFFFF'))
        c1.addStretch(1)
        self.lic_estado = Etiqueta('', 13, peso='negrita')
        c1.addWidget(self.lic_estado)
        cl.addWidget(f1)
        self.lic_detalle = ui.Elidida('', 13, color=ui.TEXT_MUTED)
        cl.addWidget(self.lic_detalle)
        f2, c2 = caja_h(espacio=18, margenes=(0, 6, 0, 0))
        self.lic_actualizar = Enlace(tr('Actualizar licencia'), self._abrir_licencia, 13, color=ui.ACCENT_CLARO,
                                     color_hover='#FFFFFF', subrayada=False, peso='negrita')
        c2.addWidget(self.lic_actualizar)
        self.lic_desactivar = Enlace(tr('Desactivar dispositivo'), self._desactivar, 13, color='#FF8A80',
                                     color_hover='#FFFFFF', subrayada=False, peso='negrita')
        c2.addWidget(self.lic_desactivar)
        c2.addStretch(1)
        cl.addWidget(f2)
        c.addWidget(lic)
        # notas
        notas = QFrame()
        notas.setObjectName('tarjetaMini')
        cn = QVBoxLayout(notas)
        cn.setContentsMargins(18, 16, 18, 16)
        cn.setSpacing(6)
        f3, c3 = caja_h()
        c3.addWidget(Etiqueta(tr('Notas de la versión'), 14, peso='negrita', color='#FFFFFF'))
        c3.addStretch(1)
        c3.addWidget(Etiqueta(tr('Versión instalada'), 12, color=ui.TEXT_MUTED))
        cn.addWidget(f3)
        cn.addWidget(TextoAjustable(tr('Consulta los cambios de esta versión de CineCaptions incluso sin conexión.'), 13,
                                    ancho=self.ANCHO - 56 - 36))
        cn.addSpacing(4)
        cn.addWidget(Enlace(tr('Leer notas de la versión'), lambda: mostrar_notas(self.app), 13, color=ui.ACCENT_CLARO,
                            color_hover='#FFFFFF', subrayada=False, peso='negrita'))
        c.addWidget(notas)
        self.control_act = ControlActualizacion(self.app)
        self.estado_act = self.control_act.estado
        c.addWidget(self.control_act)
        exp = Boton(tr('Expandir ajustes'), lambda: (self.cerrar(), al_expandir()), tipo='neutro', alto=46)
        exp.setIcon(icono('expandir', '#C9D6EC'))
        exp.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        c.addWidget(exp)
        self.pintar()

    def pintar(self):
        d = datos_licencia()
        self.lic_estado.configure(text=d['estado'], text_color=d['color'])
        self.lic_detalle.configure(text=d['detalle'])
        self.lic_desactivar.setVisible(d['activa'])
        self.lic_actualizar.configure(text=tr('Ver mi licencia') if d['activa'] else tr('Activar licencia'))
        self.lic_actualizar.setVisible(d['configurada'])

    def _abrir_licencia(self):
        self.cerrar()
        try:
            self.app._abrir_licencia()
        except Exception:
            pass

    def _desactivar(self):
        desactivar_licencia(self.app, self.pintar)

    def abrir(self, ancla, rect=None):
        """Con la isla: sale DEBAJO del engranaje, dentro del contenido (centrado en el, sin tocar el borde ni la isla).
        Sin 'rect' (compatibilidad) se coloca encima del boton 'ancla'."""
        def posicion(ancho_v, alto_v, panel):
            panel.adjustSize()
            if rect is not None and not rect.isEmpty():
                y = int(rect.bottom() + 22)
                alto = min(panel.sizeHint().height(), alto_v - y - 20)
                x = int(min(max(16, rect.center().x() - self.ANCHO / 2), ancho_v - self.ANCHO - 16))
                return QRect(x, y, self.ANCHO, max(200, alto))
            alto = min(panel.sizeHint().height(), alto_v - 40)
            esquina = ancla.mapTo(self.app, ancla.rect().topLeft())
            x = max(16, esquina.x())
            y = max(20, esquina.y() - alto - 12)
            return QRect(x, y, self.ANCHO, alto)
        self._capa = CapaModal(self.app, self, posicion=posicion)

    def cerrar(self):
        if self._capa is not None and ui.vivo(self._capa):
            self._capa.cerrar()


# ---------------------------------------------------------------------------
# Ajustes completos (imagen 3 de la referencia)
class _Pestanas(QWidget):
    """La fila de pestañas con la raya de color que se desliza a la elegida."""

    def __init__(self, nombres, al_elegir):
        super().__init__()
        self._nombres = list(nombres)
        self._al_elegir = al_elegir
        self._sel = 0
        self._hover = -1
        self._x = 0.0
        self._w = 0.0
        self.setFixedHeight(56)
        self.setFont(fuente(15, peso='negrita'))
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._mover)

    def _cajas(self):
        fm = QFontMetricsF(self.font())
        x, cajas = 34.0, []
        for n in self._nombres:
            w = fm.horizontalAdvance(n) + 28
            cajas.append(QRectF(x, 0, w, self.height()))
            x += w + 18
        return cajas

    def elegir(self, i, animar=True):
        self._sel = i
        cajas = self._cajas()
        destino = (cajas[i].left() + 10, cajas[i].width() - 20)
        if not animar or not self.isVisible():
            self._x, self._w = destino
            self.update()
        else:
            self._anim.stop()
            self._anim.setStartValue(QPointF(self._x, self._w))
            self._anim.setEndValue(QPointF(*destino))
            self._anim.start()
        self._al_elegir(i)

    def _mover(self, v):
        self._x, self._w = v.x(), v.y()
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        cajas = self._cajas()
        self._x, self._w = cajas[self._sel].left() + 10, cajas[self._sel].width() - 20

    def mouseMoveEvent(self, e):
        h = next((i for i, c in enumerate(self._cajas()) if c.contains(e.position())), -1)
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        for i, c in enumerate(self._cajas()):
            if c.contains(e.position()):
                self.elegir(i)
                return

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#1A2438'))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.setFont(self.font())
        for i, (n, c) in enumerate(zip(self._nombres, self._cajas())):
            color = '#FFFFFF' if i == self._sel else ('#E0EBFB' if i == self._hover else '#8D9BB5')
            p.setPen(QColor(color))
            p.drawText(c, int(Qt.AlignmentFlag.AlignCenter), n)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ui.ACCENT))
        p.drawRoundedRect(QRectF(self._x, self.height() - 3, self._w, 3), 1.5, 1.5)
        p.end()


class _Fila(QFrame):
    """Una fila de ajuste: titulo y explicacion a la izquierda, control a la derecha."""

    def __init__(self, titulo, explicacion='', control=None, ancho_control=None, ultima=False, vertical=False, expandir=False):
        super().__init__()
        self.setObjectName('filaAjuste')
        if not ultima:
            self.setStyleSheet(ui.traducir_hoja('QFrame#filaAjuste { border: none; border-bottom: 1px solid #1A2438; }'))
        c = (QVBoxLayout if vertical else QHBoxLayout)(self)
        c.setContentsMargins(30, 26, 30, 26)
        c.setSpacing(16 if vertical else 30)
        col, cc = caja_v(espacio=6)
        cc.addWidget(Etiqueta(titulo, 17, peso='negrita', color='#FFFFFF'))
        if explicacion:
            self.explicacion = TextoAjustable(explicacion, 14)
            cc.addWidget(self.explicacion)
        if vertical:
            c.addWidget(col)
        else:
            # titulo y explicacion juntos y centrados frente al control
            # (sin esto el sobrante de alto se repartia entre los dos)
            c.addWidget(col, 1, Qt.AlignmentFlag.AlignVCenter)
        if control is not None:
            if ancho_control and not vertical:
                control.setFixedWidth(ancho_control)
            if vertical and expandir:
                c.addWidget(control)                      # ocupa todo el ancho de la fila
            else:
                c.addWidget(control, 0 if not vertical else 0,
                            Qt.AlignmentFlag.AlignVCenter if not vertical else Qt.AlignmentFlag.AlignLeft)


def _grupo(*filas):
    g = QFrame()
    g.setObjectName('grupoAjustes')
    c = QVBoxLayout(g)
    c.setContentsMargins(0, 0, 0, 0)
    c.setSpacing(0)
    for f in filas:
        c.addWidget(f)
    return g


class _TarjetaTema(QAbstractButton):
    """Un perfil de tema con su miniatura (lateral + panel) y su texto."""

    def __init__(self, clave, nombre, desc, fondo, lateral, tarjeta, acento):
        super().__init__()
        self.clave = clave
        self._nombre, self._desc = nombre, desc
        self._cols = (fondo, lateral, tarjeta, acento)
        self._hover = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def sizeHint(self):
        return QSize(340, 110)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        fondo, lateral, tarjeta, acento = (QColorReal(c) for c in self._cols)
        elegido = self.isChecked()
        p.setBrush(QColor('#0F1A2E' if elegido else ('#0F1828' if self._hover else '#0B1220')))
        p.setPen(QPen(QColor(ui.ACCENT) if elegido else QColor('#34507F' if self._hover else '#1E2A42'), 1.6 if elegido else 1))
        p.drawRoundedRect(r, 14, 14)
        mini = QRectF(r.left() + 16, r.top() + 16, 110, r.height() - 32)
        p.setPen(QPen(QColorReal('#2A3A58'), 1))
        p.setBrush(fondo)
        p.drawRoundedRect(mini, 8, 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(lateral)
        p.drawRoundedRect(QRectF(mini.left() + 1, mini.top() + 1, 28, mini.height() - 2), 7, 7)
        p.setBrush(acento)
        p.drawRoundedRect(QRectF(mini.left() + 10, mini.top() + 12, 8, 18), 3, 3)
        p.setBrush(QColorReal(acento.red(), acento.green(), acento.blue(), 120))
        p.drawRoundedRect(QRectF(mini.left() + 10, mini.top() + 38, 8, 18), 3, 3)
        p.setBrush(tarjeta)
        p.drawRoundedRect(QRectF(mini.left() + 36, mini.top() + 12, mini.width() - 46, 16), 4, 4)
        p.drawRoundedRect(QRectF(mini.left() + 36, mini.top() + 34, mini.width() - 46, mini.height() - 46), 5, 5)
        x = mini.right() + 18
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(15, peso='negrita'))
        p.drawText(QRectF(x, r.top() + 22, r.right() - x - 12, 22), int(Qt.AlignmentFlag.AlignLeft), self._nombre)
        p.setPen(QColor('#8D9BB5'))
        p.setFont(fuente(12))
        p.drawText(QRectF(x, r.top() + 48, r.right() - x - 14, r.height() - 56),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), self._desc)
        p.end()


class _TarjetaEstilo(QAbstractButton):
    """Un estilo de Inicio (y de toda la interfaz): su miniatura VIVA (se anima al pasar el ratón), nombre, descripción y el tema que trae."""

    def __init__(self, clave):
        super().__init__()
        import estilos_inicio
        self.clave = clave
        self._est = estilos_inicio.crear(clave)
        self._clase = estilos_inicio.ESTILOS[clave]
        self._ctx = estilos_inicio.Ctx()
        self._ctx.t = 2.4
        self._ctx.progreso = 0.62
        for _ in range(72):
            self._est.avanzar(1 / 30.0, 1.0)
        self._pm = None
        self._clave_pm = None
        self._hover = False
        self._t = 2.4
        self._reloj = QTimer(self)
        self._reloj.setInterval(33)
        self._reloj.timeout.connect(self._tic)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(292, 216)

    def sizeHint(self):
        return QSize(292, 216)

    def _tic(self):
        self._t += 1 / 30.0
        self._est.avanzar(1 / 30.0, 2.0)
        self._ctx.t = self._t
        self._ctx.estado = 'trabajando' if int(self._t / 4.0) % 2 else 'listo'
        self._ctx.progreso = (self._t % 4.0) / 4.0
        self._ctx.texto = ''
        self._pm = None
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self._reloj.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._reloj.stop()
        self._ctx.estado = 'listo'
        self._pm = None
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        import estilos_inicio
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        elegido = self.isChecked()
        ruta = QPainterPath()
        ruta.addRoundedRect(r, 16, 16)
        p.fillPath(ruta, QColor('#0F1A2E' if elegido else ('#0F1828' if self._hover else '#0B1220')))
        # la miniatura (arriba, recortada con las esquinas redondas)
        w, h = int(r.width() - 16), int(r.height() - 74)
        dpr = self.devicePixelRatioF()
        clave = (w, h, round(dpr, 2))
        if self._pm is None or self._clave_pm != clave:
            try:
                self._pm = estilos_inicio.dibujar_miniatura(self._est, self._ctx, w, h, dpr)
                self._clave_pm = clave
            except Exception:
                self._pm = None
        if self._pm is not None:
            p.save()
            mini = QPainterPath()
            mini.addRoundedRect(QRectF(r.left() + 8, r.top() + 8, w, h), 11, 11)
            p.setClipPath(mini)
            p.drawPixmap(QRectF(r.left() + 8, r.top() + 8, w, h), self._pm, QRectF(self._pm.rect()))
            p.restore()
        y = r.top() + 8 + h + 10
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(15, peso='negrita'))
        p.drawText(QRectF(r.left() + 14, y, r.width() - 80, 22), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._clase.nombre)
        # el color de resaltado que trae
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColorReal(self._clase.acento))
        p.drawEllipse(QPointF(r.right() - 22, y + 11), 7, 7)
        p.setPen(QColor('#8D9BB5'))
        p.setFont(fuente(11))
        p.drawText(QRectF(r.left() + 14, y + 23, r.width() - 28, 32), int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), self._clase.descr)
        # borde
        if elegido:
            p.setPen(QPen(QColor(ui.ACCENT), 2.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ruta)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ui.ACCENT))
            p.drawEllipse(QPointF(r.left() + 28, r.top() + 28), 13, 13)
            p.setPen(QPen(QColorReal('#06140E'), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline([QPointF(r.left() + 22, r.top() + 28), QPointF(r.left() + 26.5, r.top() + 32.5), QPointF(r.left() + 34, r.top() + 23)])
        else:
            p.setPen(QPen(QColor('#34507F' if self._hover else '#1E2A42'), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ruta)
        p.end()


class _Flecha(QAbstractButton):
    """Una flecha redonda del carrusel (cristal oscuro, trazo fino)."""

    def __init__(self, derecha, padre=None):
        super().__init__(padre)
        self._der = derecha
        self._hover = False
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

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
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(QPen(QColor(255, 255, 255, 70 if self._hover else 36), 1.0))
        p.setBrush(QColor(14, 20, 32, 235 if self._hover else 205))
        p.drawEllipse(r)
        c = r.center()
        d = 1 if self._der else -1
        p.setPen(QPen(QColor('#FFFFFF' if self._hover else '#C9D6EC'), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline([QPointF(c.x() - 3.2 * d, c.y() - 6), QPointF(c.x() + 3.2 * d, c.y()), QPointF(c.x() - 3.2 * d, c.y() + 6)])
        p.end()


class _Puntos(QWidget):
    """Los puntos de debajo del carrusel: uno por tarjeta, el elegido alargado y con el acento; un clic lleva a esa tarjeta."""
    cambio = Signal(int)

    def __init__(self, n, padre=None):
        super().__init__(padre)
        self._n = n
        self._sel = 0
        self._vis = 0.0
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, sel, visible):
        self._sel, self._vis = sel, visible
        self.update()

    def _x(self, i):
        paso = 18.0
        ancho = (self._n - 1) * paso + 22
        return (self.width() - ancho) / 2.0 + i * paso

    def mousePressEvent(self, e):
        for i in range(self._n):
            if abs(e.position().x() - (self._x(i) + 4)) < 9:
                self.cambio.emit(i)
                return
        super().mousePressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self._n):
            x = self._x(i)
            if i == self._sel:
                p.setBrush(QColor(ui.ACCENT))
                p.drawRoundedRect(QRectF(x - 5, 8, 18, 6), 3, 3)
            else:
                p.setBrush(QColor(255, 255, 255, 70))
                p.drawEllipse(QPointF(x + 4, 11), 3, 3)
        p.end()


class _CarruselEstilos(QWidget):
    """Las tarjetas de estilo en una sola fila que se desliza (flechas, arrastre con el ratón, rueda horizontal y puntos). Ocupa lo
    de una tarjeta en vez de diez."""

    def __init__(self, tarjetas, elegido, padre=None):
        super().__init__(padre)
        from PySide6.QtCore import QPropertyAnimation
        from PySide6.QtWidgets import QScrollArea
        self._tarjetas = tarjetas
        self._arrastra = None
        self._movido = False
        self._anim = None
        self._QPA = QPropertyAnimation
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet('QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }')
        self._scroll.setFixedHeight(226)
        fila = QWidget()
        h = QHBoxLayout(fila)
        h.setContentsMargins(4, 4, 4, 6)
        h.setSpacing(14)
        for t in tarjetas:
            h.addWidget(t)
            t.installEventFilter(self)
        h.addStretch(1)
        self._scroll.setWidget(fila)
        self._scroll.viewport().installEventFilter(self)
        v.addWidget(self._scroll)
        self._puntos = _Puntos(len(tarjetas))
        self._puntos.cambio.connect(self.ir_a)
        v.addWidget(self._puntos)
        self._izq = _Flecha(False, self)
        self._der = _Flecha(True, self)
        self._izq.clicked.connect(lambda: self._mover(-2))
        self._der.clicked.connect(lambda: self._mover(2))
        barra = self._scroll.horizontalScrollBar()
        barra.valueChanged.connect(lambda _v: self._actualizar())
        barra.rangeChanged.connect(lambda *_: self._actualizar())
        self._elegido = elegido
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.ir_a(elegido, animar=False))

    def poner_elegido(self, i):
        self._elegido = i
        self._actualizar()

    def _paso(self):
        return self._tarjetas[0].width() + 14

    def _mover(self, n):
        barra = self._scroll.horizontalScrollBar()
        self._ir(barra.value() + n * self._paso())

    def _ir(self, valor, animar=True):
        barra = self._scroll.horizontalScrollBar()
        valor = max(barra.minimum(), min(barra.maximum(), int(valor)))
        if not animar:
            barra.setValue(valor)
            return
        if self._anim is not None:
            self._anim.stop()
        self._anim = self._QPA(barra, b'value', self)
        self._anim.setDuration(380)
        self._anim.setStartValue(barra.value())
        self._anim.setEndValue(valor)
        from PySide6.QtCore import QEasingCurve
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def ir_a(self, i, animar=True):
        """Lleva la tarjeta i al centro (si cabe)."""
        centro = i * self._paso() + self._tarjetas[0].width() / 2.0 - self._scroll.viewport().width() / 2.0 + 4
        self._ir(centro, animar)

    def _actualizar(self):
        barra = self._scroll.horizontalScrollBar()
        self._izq.setVisible(barra.value() > barra.minimum() + 2 and barra.maximum() > 0)
        self._der.setVisible(barra.value() < barra.maximum() - 2)
        self._puntos.poner(self._elegido, 0.0)
        self._colocar()

    def _colocar(self):
        y = 4 + (self._tarjetas[0].height() - 40) // 2 - 10
        self._izq.move(2, y)
        self._der.move(self.width() - 42, y)
        self._izq.raise_()
        self._der.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._actualizar()

    def wheelEvent(self, e):
        # solo el gesto horizontal desliza el carrusel; la rueda normal sigue moviendo la página
        if abs(e.angleDelta().x()) > abs(e.angleDelta().y()):
            barra = self._scroll.horizontalScrollBar()
            barra.setValue(barra.value() - e.angleDelta().x())
            e.accept()
        else:
            e.ignore()

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
            self._arrastra = (ev.globalPosition().x(), self._scroll.horizontalScrollBar().value())
            self._movido = False
        elif t == QEvent.Type.MouseMove and self._arrastra is not None and (ev.buttons() & Qt.MouseButton.LeftButton):
            dx = ev.globalPosition().x() - self._arrastra[0]
            if abs(dx) > 8:
                self._movido = True
            if self._movido:
                if self._anim is not None:
                    self._anim.stop()
                self._scroll.horizontalScrollBar().setValue(int(self._arrastra[1] - dx))
                return True
        elif t == QEvent.Type.MouseButtonRelease and self._arrastra is not None:
            self._arrastra = None
            if self._movido:
                self._movido = False
                if hasattr(obj, 'setDown'):
                    obj.setDown(False)
                return True
        return super().eventFilter(obj, ev)


class _ChipAcento(QAbstractButton):
    """Un color de resaltado: circulo + nombre, en su pastilla."""

    def __init__(self, clave, nombre, color):
        super().__init__()
        self.clave = clave
        self._nombre = nombre
        self.color = color
        self._hover = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def sizeHint(self):
        return QSize(220, 64)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        c = QColorReal(self.color)
        elegido = self.isChecked()
        p.setBrush(QColorReal(c.red(), c.green(), c.blue(), 30) if elegido else QColor('#0B1220'))
        p.setPen(QPen(c if elegido else QColor('#34507F' if self._hover else '#1E2A42'), 1.6 if elegido else 1))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(r.left() + 34, r.center().y()), 14, 14)
        p.setPen(QColor('#FFFFFF'))
        p.setFont(fuente(15, peso='negrita'))
        p.drawText(QRectF(r.left() + 62, r.top(), r.width() - 70, r.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._nombre)
        p.end()


class VentanaAjustes(_Panel):
    PESTANAS = ('general', 'interfaz', 'atajos', 'acerca', 'ayuda')

    def __init__(self, app, pestana='general'):
        super().__init__(radio=22)
        self.app = app
        self._capa = None
        self._previos = tema.leer()
        prefs = leer_prefs()
        self._borrador = dict(self._previos)
        self._borrador.update(motor_voz=prefs.get('motor_voz') or 'qwen3',
                              canal_beta=False,
                              actualizaciones_auto=prefs.get('actualizaciones_auto', True) is not False,
                              ventana_encima=bool(prefs.get('ventana_encima')),
                              avisos_sistema=prefs.get('avisos_sistema', True) is not False,
                              go_estilo=str(prefs.get('go_estilo') or 'astrolabio'))
        self._inicial = dict(self._borrador)
        self._idioma_inicial = self._idioma_actual()
        self._borrador['idioma_ui'] = self._idioma_inicial
        self._inicial['idioma_ui'] = self._idioma_inicial
        c = QVBoxLayout(self)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(0)
        cab = QWidget()
        cc = QVBoxLayout(cab)
        cc.setContentsMargins(46, 36, 34, 18)
        cc.addWidget(_cabecera(tr('Ajustes de la aplicación'), tr('Ajustes de CineCaptions'), self.cerrar, tam=38))
        c.addWidget(cab)
        nombres = [tr('General'), tr('Interfaz'), tr('Atajos'), tr('Acerca de CineCaptions'), tr('Ayuda')]
        self.pila = QStackedWidget()
        self.pestanas = _Pestanas(nombres, self.pila.setCurrentIndex)
        c.addWidget(self.pestanas)
        for armar in (self._pag_general, self._pag_interfaz, self._pag_atajos, self._pag_acerca, self._pag_ayuda):
            d = Desplazable(espacio=22, margenes=(60, 34, 56, 34), estirar_final=True)
            armar(d.capa)
            self.pila.addWidget(d)
        c.addWidget(self.pila, 1)
        pie = QFrame()
        pie.setObjectName('pieAjustes')
        pie.setStyleSheet(ui.traducir_hoja('QFrame#pieAjustes { border: none; border-top: 1px solid #1A2438; }'))
        cp = QHBoxLayout(pie)
        cp.setContentsMargins(46, 18, 34, 22)
        cp.setSpacing(12)
        self.estado = Etiqueta(tr('Las preferencias están actualizadas.'), 14, color=ui.TEXT_MUTED)
        cp.addWidget(self.estado)
        self.reiniciar_btn = Enlace(tr('Reiniciar ahora'), self._reiniciar, 14, color=ui.ACCENT_CLARO,
                                    color_hover='#FFFFFF', subrayada=False, peso='negrita')
        self.reiniciar_btn.hide()
        cp.addWidget(self.reiniciar_btn)
        cp.addStretch(1)
        cp.addWidget(Boton(tr('Cancelar'), self.cerrar, tipo='neutro', alto=50, ancho=130, tam=17, negrita=True))
        self.aplicar_btn = Boton(tr('Aplicar'), self.aplicar, tipo='suave', alto=50, ancho=130, tam=17, negrita=True)
        self.aplicar_btn.setEnabled(False)
        cp.addWidget(self.aplicar_btn)
        cp.addWidget(Boton(tr('Listo'), self._listo, tipo='primario', alto=50, ancho=130, tam=17, negrita=True))
        c.addWidget(pie)
        i = self.PESTANAS.index(pestana) if pestana in self.PESTANAS else 0
        self.pestanas.elegir(i, animar=False)

    # -- utilidades -----------------------------------------------------------
    def _idioma_actual(self):
        try:
            import i18n
            return i18n.IDIOMAS_UI.get(i18n.idioma(), 'Español')
        except Exception:
            return 'Español'

    def _cambio(self, clave, valor):
        self._borrador[clave] = valor
        pendiente = any(self._borrador.get(k) != self._inicial.get(k) for k in self._borrador)
        self.aplicar_btn.setEnabled(pendiente)
        self.estado.configure(text=tr('Hay cambios sin aplicar.') if pendiente else tr('Las preferencias están actualizadas.'))

    def _cabeza_pagina(self, capa, sobre, titulo, texto):
        capa.addWidget(_etiqueta_seccion(sobre))
        capa.addWidget(Etiqueta(titulo, 34, peso='extra', color='#FFFFFF'))
        capa.addWidget(TextoAjustable(texto, 16))
        capa.addSpacing(6)

    # -- General --------------------------------------------------------------
    def _pag_general(self, capa):
        self._cabeza_pagina(capa, tr('Preferencias generales'), tr('General'),
                            tr('Idioma, motor de voz, conexión con Resolve y copias de seguridad.'))
        import i18n
        idioma_var = StringVar(self._idioma_inicial)
        combo_idioma = Combo(list(i18n.IDIOMAS_UI.values()), var=idioma_var, alto=52, tam=16,
                             comando=lambda v: self._cambio('idioma_ui', v))
        f_idioma = _Fila(tr('Idioma de la interfaz'), tr('Se aplica al reiniciar CineCaptions.'), combo_idioma, 340)
        # motor de voz
        motores ={'qwen3': tr('Qwen3-ASR (recomendado)'), 'whisper': tr('Whisper large-v3-turbo')}
        motor_var = StringVar(motores.get(self._borrador['motor_voz'], motores['qwen3']))
        caja_motor, cm = caja_v(espacio=10)
        cm.addWidget(Combo(list(motores.values()), var=motor_var, alto=52, tam=16,
                           comando=lambda v: self._cambio('motor_voz', next(k for k, n in motores.items() if n == v))))
        self.motor_estado = TextoAjustable('', 13, ancho=340)
        cm.addWidget(self.motor_estado)
        self.motor_btn = Boton(tr('Instalar motor Qwen3-ASR'), self._instalar_motor, tipo='neutro', alto=42, tam=14)
        cm.addWidget(self.motor_btn)
        f_motor = _Fila(tr('Motor de voz'),
                        tr('Qwen3-ASR (2026) transcribe y mide cada palabra en 11 idiomas: español, inglés, '
                           'portugués, francés, alemán, italiano, japonés, coreano, ruso, chino y cantonés. '
                           'Para los demás idiomas, o si no está instalado, se usa Whisper large-v3-turbo.'),
                        caja_motor, 340)
        self._pintar_motor()
        # GPU para la voz (v5.4.8)
        caja_gpu, cg = caja_v(espacio=10)
        self.gpu_estado = TextoAjustable(tr('Comprobando la GPU…'), 13, ancho=340)
        cg.addWidget(self.gpu_estado)
        self.gpu_btn = Boton(tr('Reparar GPU'), self._reparar_gpu, tipo='neutro', alto=42, tam=14)
        self.gpu_btn.hide()
        cg.addWidget(self.gpu_btn)
        f_gpu = _Fila(tr('GPU para la voz'),
                      tr('Whisper usa tu tarjeta NVIDIA si encuentra las librerías de CUDA; si faltan, la voz se transcribe en la CPU (mucho más lenta). «Reparar GPU» usa las que ya trae el motor Qwen o descarga las oficiales de NVIDIA (≈1,3 GB).'),
                      caja_gpu, 340)
        self._pintar_gpu()
        # espacio de las cachés (v5.4.8)
        caja_cache, cch = caja_v(espacio=10)
        self.cache_texto = TextoAjustable(tr('Calculando…'), 13, ancho=340)
        cch.addWidget(self.cache_texto)
        self.cache_btn = Boton(tr('Limpiar ahora'), self._limpiar_caches, tipo='neutro', alto=42, tam=14)
        cch.addWidget(self.cache_btn)
        f_cache = _Fila(tr('Espacio de las cachés'),
                        tr('Efectos animados, emojis, vistas de los packs y transcripciones se guardan para no rehacerlos. Cada una tiene un tope y se borra sola lo menos usado; «Limpiar ahora» aplica los topes ya. Todo se vuelve a crear cuando hace falta.'),
                        caja_cache, 340)
        self._pintar_cache()
        # conexion con Resolve
        caja_con, cc = caja_v(espacio=10)
        fila_con, cfc = caja_h(espacio=10)
        self.con_punto = Punto(ui.TEXT_MUTED, 10)
        cfc.addWidget(self.con_punto, 0, Qt.AlignmentFlag.AlignVCenter)
        self.con_texto = ui.Elidida(tr('Comprobando…'), 15, peso='negrita', color='#FFFFFF')
        cfc.addWidget(self.con_texto, 1)
        cc.addWidget(fila_con)
        self.con_detalle = ui.Elidida('', 13, color=ui.TEXT_MUTED)
        cc.addWidget(self.con_detalle)
        botones, cb = caja_h(espacio=10)
        cb.addWidget(Boton(tr('Comprobar conexión'), self._comprobar_conexion, tipo='neutro', alto=42, tam=14))
        cb.addWidget(Boton(tr('Abrir Resolve'), self._abrir_resolve, tipo='neutro', alto=42, tam=14))
        cc.addWidget(botones)
        f_con = _Fila(tr('Conexión con DaVinci Resolve'),
                      tr('Con Resolve 21.1 o más nuevo CineCaptions usa su servidor MCP oficial: no hace falta '
                         'lanzar el Puente y cada orden tarda milésimas. Con versiones anteriores se usa la API '
                         'de Studio o el Puente, como siempre.'), caja_con, 340)
        self._comprobar_conexion()
        # encima
        encima_var = BooleanVar(self._borrador['ventana_encima'])
        f_encima = _Fila(tr('Mantener CineCaptions encima'),
                         tr('La ventana queda por delante de Resolve (también con el alfiler del menú lateral).'),
                         Interruptor('', var=encima_var, comando=lambda: self._cambio('ventana_encima', bool(encima_var.get()))))
        avisos_var = BooleanVar(self._borrador['avisos_sistema'])
        f_avisos = _Fila(tr('Avisarme al terminar'),
                         tr('Cuando GO termina y CineCaptions no está al frente (estás en Resolve u otro programa), sale un aviso del sistema.'),
                         Interruptor('', var=avisos_var, comando=lambda: self._cambio('avisos_sistema', bool(avisos_var.get()))))
        # v5.5: lo que pasa en Resolve cuando GO termina
        repro_var = BooleanVar(leer_prefs().get('go_reproducir', True) is not False)
        f_repro = _Fila(tr('Reproducir al terminar'),
                        tr('Cuando GO termina, Resolve se pone al frente y reproduce el timeline desde el principio para que veas el resultado.'),
                        Interruptor('', var=repro_var, comando=lambda: guardar_prefs({'go_reproducir': bool(repro_var.get())})))
        vert_var = BooleanVar(leer_prefs().get('go_vertical', True) is not False)
        f_vert = _Fila(tr('Abrir siempre en vertical'),
                       tr('Cada proyecto y timeline que CineCaptions arma para un video queda en vertical (1080×1920), sea cómo sea el video. Apágalo para que respete su orientación.'),
                       Interruptor('', var=vert_var, comando=lambda: guardar_prefs({'go_vertical': bool(vert_var.get())})))
        vista_var = BooleanVar(leer_prefs().get('go_vista_resolve', True) is not False)
        caja_vista, cvi = caja_v(espacio=8)
        cvi.addWidget(Interruptor('', var=vista_var, comando=lambda: guardar_prefs({'go_vista_resolve': bool(vista_var.get())})), 0, Qt.AlignmentFlag.AlignRight)
        self.vista_texto = Etiqueta('', 12, color=ui.TEXT_MUTED, envolver=True)
        cvi.addWidget(self.vista_texto)
        cvi.addWidget(Boton(tr('Guardar la vista actual de Resolve'), self._guardar_vista_resolve, tipo='neutro', alto=42, tam=14))
        f_vista = _Fila(tr('Vista de Resolve al terminar'),
                        tr('Deja Resolve en la página Edit con TU disposición de pantalla (vertical y con la vista expandida). Ponla como la quieres en Resolve y pulsa «Guardar la vista actual»: '
                           'desde entonces GO la aplica cada vez que termina.'), caja_vista, 340)
        # copias
        caja_cop, cco = caja_v(espacio=10)
        self.copias_texto = Etiqueta('', 13, color=ui.TEXT_MUTED)
        cco.addWidget(self.copias_texto)
        fb, cfb = caja_h(espacio=10)
        cfb.addWidget(Boton(tr('Crear copia'), self._crear_copia, tipo='neutro', alto=42, tam=14))
        cfb.addWidget(Boton(tr('Restaurar…'), self._restaurar_copia, tipo='neutro', alto=42, tam=14))
        cfb.addWidget(Boton(tr('Abrir carpeta'), self._abrir_copias, tipo='fantasma', alto=42, tam=14))
        cco.addWidget(fb)
        f_cop = _Fila(tr('Copias de seguridad'),
                      tr('Guarda en un .zip tus proyectos, marcas del editor, recetas, ajustes, reglas de SFX y tus '
                         'packs de estilos, en Documentos > CineCaptions > Copias de seguridad.'), caja_cop, 340,
                      ultima=True)
        self._pintar_copias()
        capa.addWidget(_grupo(f_motor, f_gpu, f_cache, f_con, f_encima, f_avisos, f_repro, f_vert, f_vista, f_cop))

    def _pintar_motor(self):
        import motor_voz
        info = motor_voz.info_instalado()
        if info:
            self.motor_estado.configure(text=tr('Instalado: Qwen3-ASR {m} · {gpu}', m=info.get('modelo', ''),
                                                gpu=info.get('gpu') or 'CPU'), text_color=ui.VERDE)
            self.motor_btn.configure(text=tr('Reparar el motor'))
        elif sys.platform != 'win32':
            self.motor_estado.configure(text=tr('Qwen3-ASR por ahora solo está para Windows: se usa Whisper.'))
            self.motor_btn.hide()
        else:
            self.motor_estado.configure(text=tr('No instalado (descarga de 4 a 15 GB): mientras tanto se usa Whisper.'),
                                        text_color=ui.AMBAR)

    def _pintar_cache(self):
        def trabajo():
            import mantenimiento
            return mantenimiento.resumen()

        def fin(r, error):
            if not ui.vivo(self.cache_texto) or error is not None or not r:
                return
            filas, total = r
            mayores = sorted(filas, key=lambda f: -f[1])[:3]
            self.cache_texto.configure(text=tr('{t} MB en total · ', t=f'{total:,.0f}'.replace(',', '.')) + ' · '.join(f'{n}: {mb:,.0f} MB'.replace(',', '.') for n, mb, _t in mayores if mb >= 1),
                                       text_color=ui.TEXT_MUTED)
        correr_en_hilo(self.app, trabajo, fin)

    def _limpiar_caches(self):
        self.cache_btn.setEnabled(False)

        def trabajo():
            import mantenimiento
            return mantenimiento.limpiar_todo()

        def fin(r, error):
            if not ui.vivo(self.cache_btn):
                return
            self.cache_btn.setEnabled(True)
            if error is None and r:
                self.cache_texto.configure(text=tr('Liberados {mb} MB.', mb=f'{r[0]:,.0f}'.replace(',', '.')), text_color=ui.VERDE)
                ui.despues(2500, self._pintar_cache, self)
        correr_en_hilo(self.app, trabajo, fin)

    def _pintar_gpu(self):
        def trabajo():
            import cuda_libs
            return cuda_libs.diagnostico()

        def fin(d, error):
            if not ui.vivo(self.gpu_estado):
                return
            if error is not None or not d:
                self.gpu_estado.configure(text=tr('No pude comprobar la GPU.'), text_color=ui.AMBAR)
                return
            import cuda_libs
            texto = cuda_libs.texto_diagnostico(d)
            if d['estado'] == 'ok':
                self.gpu_estado.configure(text=texto, text_color=ui.VERDE)
                self.gpu_btn.hide()
            elif d['estado'] == 'faltan':
                self.gpu_estado.configure(text=texto, text_color=ui.AMBAR)
                self.gpu_btn.show()
            else:
                self.gpu_estado.configure(text=texto, text_color=ui.TEXT_MUTED)
                self.gpu_btn.hide()
        correr_en_hilo(self.app, trabajo, fin)

    def _reparar_gpu(self):
        import cuda_libs
        self.gpu_btn.setEnabled(False)

        def progreso(texto):
            ejecutar_en_ui(lambda: self.gpu_estado.configure(text=str(texto), text_color=ui.ACCENT_CLARO) if ui.vivo(self.gpu_estado) else None)

        def trabajo():
            ok, msg = cuda_libs.reparar(aviso=progreso, permitir_descarga=False)
            return ok, msg, False

        def fin(r, error):
            if not ui.vivo(self.gpu_btn):
                return
            self.gpu_btn.setEnabled(True)
            if error is None and r and r[0]:
                self._pintar_gpu()
                return
            # sin copia local: se ofrece la descarga oficial (≈1 GB)
            if not messagebox.askyesno(tr('Reparar GPU'), tr('No encuentro las librerías de CUDA en el equipo. ¿Descargo las oficiales de NVIDIA (cuBLAS y cuDNN, ≈1,3 GB desde PyPI)? Se puede reanudar si se corta.'), parent=self.app):
                self._pintar_gpu()
                return
            self.gpu_btn.setEnabled(False)

            def trabajo2():
                return cuda_libs.reparar(aviso=progreso, permitir_descarga=True)

            def fin2(r2, e2):
                if not ui.vivo(self.gpu_btn):
                    return
                self.gpu_btn.setEnabled(True)
                if e2 is not None:
                    self.gpu_estado.configure(text=tr('No se pudo reparar: {e}', e=str(e2)[:160]), text_color=ui.ROJO)
                else:
                    self.gpu_estado.configure(text=str(r2[1])[:200], text_color=ui.VERDE if r2[0] else ui.AMBAR)
                    if r2[0]:
                        self.gpu_btn.hide()
            correr_en_hilo(self.app, trabajo2, fin2)
        correr_en_hilo(self.app, trabajo, fin)

    def _instalar_motor(self):
        if not messagebox.askyesno(tr('Motor de voz Qwen3-ASR'),
                                   tr('Se descargan PyTorch, los modelos de Qwen3-ASR y la IA de texto (de 4 a 15 GB según '
                                      'tu tarjeta gráfica). Puede tardar un buen rato; puedes seguir usando el programa.\n\n¿Instalar ahora?'),
                                   parent=self.app):
            return
        import motor_voz
        self.motor_btn.setEnabled(False)

        def progreso(f, texto):
            ejecutar_en_ui(lambda: self.motor_estado.configure(text=f'{int(f * 100)} % · {texto}', text_color=ui.ACCENT_CLARO)
                           if ui.vivo(self.motor_estado) else None)

        def fin(_r, error):
            if not ui.vivo(self.motor_btn):
                return
            self.motor_btn.setEnabled(True)
            if error is not None:
                self.motor_estado.configure(text=tr('No se pudo instalar: {e}', e=str(error)[:160]), text_color=ui.ROJO)
            else:
                self._pintar_motor()
                try:
                    self.app._refrescar_estado()
                except Exception:
                    pass
        correr_en_hilo(self.app, lambda: motor_voz.instalar(progreso=progreso), fin)

    def _guardar_vista_resolve(self):
        """Guarda la disposición de pantalla actual de Resolve como la de CineCaptions (en un hilo: habla con Resolve)."""
        self.vista_texto.configure(text=tr('Guardando…'))

        def trabajo():
            import colocacion
            return colocacion.guardar_vista_actual()

        def fin(r, error):
            if not ui.vivo(self.vista_texto):
                return
            ok, texto = r if r else (False, str(error))
            self.vista_texto.poner_color(ui.VERDE if ok else ui.AMBAR)
            self.vista_texto.configure(text=texto)
        correr_en_hilo(self.app, trabajo, fin)

    def _comprobar_conexion(self):
        self.con_punto.poner(ui.TEXT_MUTED)
        self.con_texto.configure(text=tr('Comprobando…'))

        def trabajo():
            import resolve_bridge
            import resolve_mcp
            d = resolve_mcp.estado(refrescar=True)
            d['modo'] = resolve_bridge.modo_actual()
            return d

        def fin(d, error):
            if not ui.vivo(self.con_texto):
                return
            d = d or {}
            if error is None and d.get('conectado'):
                self.con_punto.poner(ui.VERDE)
                self.con_texto.configure(text=tr('Resolve conectado'))
                detalle = f"{d.get('producto', 'DaVinci Resolve')} {d.get('version', '')} · MCP"
                if d.get('proyecto'):
                    detalle += ' · ' + tr('proyecto «{p}»', p=d['proyecto'])
                self.con_detalle.configure(text=detalle)
            elif d.get('modo') in ('studio', 'puente'):
                self.con_punto.poner(ui.VERDE)
                self.con_texto.configure(text=tr('Resolve conectado'))
                self.con_detalle.configure(text=tr('Por la API de Studio') if d['modo'] == 'studio' else tr('Por el Puente'))
            else:
                self.con_punto.poner(ui.AMBAR)
                self.con_texto.configure(text=tr('Resolve sin conectar'))
                self.con_detalle.configure(text=str(d.get('motivo') or error or tr('Abre DaVinci Resolve con tu proyecto.')))
            try:
                self.app._refrescar_estado()
            except Exception:
                pass
        correr_en_hilo(self.app, trabajo, fin)

    def _abrir_resolve(self):
        self.con_texto.configure(text=tr('Abriendo Resolve…'))

        def trabajo():
            import resolve_mcp
            ok, texto = resolve_mcp.abrir_resolve()
            if not ok:
                raise RuntimeError(texto)
        correr_en_hilo(self.app, trabajo, lambda _r, _e: self._comprobar_conexion())

    def _pintar_copias(self):
        import copias
        ult = copias.ultima()
        n = len(copias.listar())
        self.copias_texto.configure(text=(tr('Última copia: {cuando} · {n} guardadas', cuando=hace_cuanto(ult), n=n)
                                          if ult else tr('Todavía no hay copias.')))

    def _crear_copia(self):
        crear_copia(self.app, lambda: self._pintar_copias() if ui.vivo(self.copias_texto) else None)

    def _restaurar_copia(self):
        import copias
        ruta = filedialog.askopenfilename(parent=self.app, title=tr('Elige la copia a restaurar'),
                                          initialdir=str(copias.carpeta_copias()),
                                          filetypes=[(tr('Copias de CineCaptions'), '*.zip')])
        if not ruta:
            return
        if not copias.es_copia(ruta):
            messagebox.showerror(tr('Restaurar copia'), tr('Ese archivo no es una copia de CineCaptions.'), parent=self.app)
            return
        if not messagebox.askyesno(tr('Restaurar copia'),
                                   tr('Se reemplazan tus proyectos y ajustes por los de esa copia. Antes guardo una copia '
                                      'de lo que tienes ahora, por si acaso.\n\n¿Restaurar?'), parent=self.app):
            return

        def fin(previa, error):
            if error is not None:
                messagebox.showerror(tr('Restaurar copia'), str(error), parent=self.app)
                return
            messagebox.showinfo(tr('Copia restaurada'),
                                tr('Listo. Lo que tenías antes quedó en:\n{ruta}\n\nReinicia CineCaptions para verlo todo.',
                                   ruta=previa), parent=self.app)
            self._pintar_copias()
        correr_en_hilo(self.app, lambda: copias.restaurar(ruta), fin)

    def _abrir_copias(self):
        import copias
        d = copias.carpeta_copias()
        d.mkdir(parents=True, exist_ok=True)
        abrir_carpeta(d)

    # -- Interfaz -------------------------------------------------------------
    def _pag_interfaz(self, capa):
        self._cabeza_pagina(capa, tr('Preferencias de interfaz'), tr('Interfaz'),
                            tr('Controla cómo se presenta el espacio de trabajo de CineCaptions al abrirse.'))
        import i18n
        idioma_var = StringVar(self._idioma_inicial)
        combo_idioma = Combo(list(i18n.IDIOMAS_UI.values()), var=idioma_var, alto=52, tam=16,
                             comando=lambda v: self._cambio('idioma_ui', v))
        f_lat = _Fila(tr('Idioma de la interfaz'), tr('Cambia el idioma de TODA la interfaz. Se aplica al reiniciar CineCaptions.'), combo_idioma, 380)
        tam_var = StringVar(f"{self._borrador['tamano']}%")
        f_tam = _Fila(tr('Tamaño de interfaz'), tr('Agranda o achica todo el programa. Se aplica al reiniciar.'),
                      Combo([f'{t}%' for t in tema.TAMANOS], var=tam_var, alto=52, tam=16,
                            comando=lambda v: self._cambio('tamano', int(v.rstrip('%')))), 380)
        # 10 estilos: cada uno es un rediseño completo de Inicio y trae su tema (superficies), su color de resaltado y su aurora
        import estilos_inicio
        self._tarjetas_tema = []
        self._tarjetas_estilo = []
        caja_est = QWidget()
        ce = QVBoxLayout(caja_est)
        ce.setContentsMargins(0, 0, 0, 0)
        ce.setSpacing(0)
        for i, clave in enumerate(estilos_inicio.ORDEN):
            t = _TarjetaEstilo(clave)
            t.setChecked(clave == self._borrador['go_estilo'])
            t.clicked.connect(lambda _=False, k=clave: self._elegir_estilo(k))
            self._tarjetas_estilo.append(t)
        elegido = estilos_inicio.ORDEN.index(self._borrador['go_estilo']) if self._borrador['go_estilo'] in estilos_inicio.ORDEN else 0
        self._carrusel = _CarruselEstilos(self._tarjetas_estilo, elegido)
        ce.addWidget(self._carrusel)
        f_estilos = _Fila(tr('Estilo de la interfaz'),
                          tr('Diez diseños completamente distintos para Inicio, con sus propias animaciones. Cada uno cambia también las '
                             'superficies, el color de resaltado y la luz de fondo de TODAS las páginas. Pasa el ratón por una tarjeta para verla en movimiento.'),
                          caja_est, vertical=True, expandir=True)
        # acentos
        col_a, cca = caja_v(espacio=12)
        cca.addWidget(_etiqueta_seccion(tr('Perfiles rápidos')))
        rejilla = QWidget()
        cg = QGridLayout(rejilla)
        cg.setContentsMargins(0, 0, 0, 0)
        cg.setHorizontalSpacing(14)
        cg.setVerticalSpacing(14)
        self._chips_acento = []
        for i, (clave, (nombre, color)) in enumerate(tema.ACENTOS.items()):
            chip = _ChipAcento(clave, nombre, color)
            chip.setChecked(clave == self._borrador['acento'])
            chip.clicked.connect(lambda _=False, k=clave: self._elegir_acento(k))
            cg.addWidget(chip, i // 3, i % 3)
            self._chips_acento.append(chip)
        cca.addWidget(rejilla)
        cca.addSpacing(6)
        cca.addWidget(_etiqueta_seccion(tr('Color personalizado')))
        fila_p, cfp = caja_h(espacio=12)
        self.chip_personal = _ChipAcento('personal', tr('Mi color'), self._borrador['acento_personal'])
        self.chip_personal.setChecked(self._borrador['acento'] == 'personal')
        self.chip_personal.setFixedWidth(260)
        self.chip_personal.clicked.connect(self._elegir_personal)
        cfp.addWidget(self.chip_personal)
        cfp.addWidget(Boton(tr('Elegir color…'), self._elegir_personal, tipo='neutro', alto=48, tam=15))
        cfp.addStretch(1)
        cca.addWidget(fila_p)
        f_acento = _Fila(tr('Color de resaltado'),
                         tr('Se usa en acciones principales, controles seleccionados y navegación activa. '
                            'Los colores de estado y de los roles del editor no cambian.'),
                         col_a, vertical=True, ultima=True)
        # v5.2: el movimiento de la interfaz (fondo vivo, particulas, confeti)
        anim_var = BooleanVar(not bool(leer_prefs().get('reducir_animaciones')))
        f_anim = _Fila(tr('Animaciones'), tr('El fondo vivo, las partículas, el confeti de GO y las transiciones. '
                                             'Apágalas en equipos lentos. Se aplica al reiniciar.'),
                       Interruptor('', var=anim_var,
                                   comando=lambda: guardar_prefs({'reducir_animaciones': not bool(anim_var.get())})))
        # v5.6: cuánto se mueve Inicio (el astrolabio, las partículas, el final): completo 60 fps / suave 30 fps y la mitad de partículas /
        # mínimo (casi quieto). Se aplica en vivo; además, con la ventana inactiva Inicio baja solo a 30 fps.
        etiquetas_go = {'completo': tr('Completo'), 'suave': tr('Suave'), 'minimo': tr('Mínimo')}
        actual_go = str(leer_prefs().get('go_animaciones') or 'completo')
        go_var = StringVar(etiquetas_go.get(actual_go, etiquetas_go['completo']))
        inverso_go = {v: k for k, v in etiquetas_go.items()}
        f_go = _Fila(tr('Animaciones de Inicio'),
                     tr('Completo: 60 fps con todos los efectos. Suave: 30 fps y la mitad de partículas. Mínimo: casi sin movimiento. '
                        'Con la ventana inactiva Inicio baja solo a 30 fps.'),
                     Segmentado(list(etiquetas_go.values()), go_var,
                                lambda *_: guardar_prefs({'go_animaciones': inverso_go.get(go_var.get(), 'completo')}), alto=34, tam=13))
        capa.addWidget(_grupo(f_estilos, f_go, f_anim, f_lat, f_tam, f_acento))

    def _elegir_estilo(self, clave):
        """Un estilo de Inicio = un conjunto: el diseño de Inicio, el tema de la interfaz y el color de resaltado."""
        import estilos_inicio
        est = estilos_inicio.ESTILOS[clave]
        for t in self._tarjetas_estilo:
            t.setChecked(t.clave == clave)
            t.update()
        self._cambio('go_estilo', clave)
        self._cambio('tema', est.tema)
        try:
            self._carrusel.poner_elegido(estilos_inicio.ORDEN.index(clave))
            self._carrusel.ir_a(estilos_inicio.ORDEN.index(clave))
        except Exception:
            pass
        clave_acento = next((k for k, (_n, col) in tema.ACENTOS.items() if col.lower() == est.acento.lower()), None)
        if clave_acento:
            self._elegir_acento(clave_acento)
        else:
            self.chip_personal.color = QColorReal(est.acento)
            for c in self._chips_acento:
                c.setChecked(False)
            self.chip_personal.setChecked(True)
            self.chip_personal.update()
            self._borrador['acento_personal'] = est.acento.upper()
            self._cambio('acento', 'personal')

    def _elegir_tema(self, clave):
        for t in self._tarjetas_tema:
            t.setChecked(t.clave == clave)
        self._cambio('tema', clave)

    def _elegir_acento(self, clave):
        for c in self._chips_acento:
            c.setChecked(c.clave == clave)
        self.chip_personal.setChecked(False)
        self._cambio('acento', clave)

    def _elegir_personal(self):
        _rgb, color = ui.elegir_color(self.app, self._borrador['acento_personal'], tr('Color de resaltado'))
        if not color:
            self.chip_personal.setChecked(self._borrador['acento'] == 'personal')
            return
        self.chip_personal.color = color
        for c in self._chips_acento:
            c.setChecked(False)
        self.chip_personal.setChecked(True)
        self.chip_personal.update()
        self._borrador['acento_personal'] = color.upper()
        self._cambio('acento', 'personal')

    # -- Atajos ---------------------------------------------------------------
    def _pag_atajos(self, capa):
        self._cabeza_pagina(capa, tr('Teclado'), tr('Atajos'),
                            tr('Los atajos de Creativo funcionan mientras el editor está abierto.'))
        filas = []
        atajos = [('1', tr('Pincel «Contexto»')), ('2', tr('Pincel «Principal»')), ('3', tr('Pincel «Complemento»')),
                  ('4  ·  0', tr('Pincel «Base» (quitar el rol)')), ('5', tr('Editar el texto de una palabra')),
                  ('6', tr('Poner un emoji encima de la palabra')), ('Ctrl + Z', tr('Deshacer')),
                  ('Ctrl + Y  ·  Ctrl + Shift + Z', tr('Rehacer')), ('Esc', tr('Cerrar el panel o globo abierto'))]
        for i, (tecla, que) in enumerate(atajos):
            filas.append(_FilaAtajo(tecla, que, ultima=i == len(atajos) - 1))
        capa.addWidget(_etiqueta_seccion(tr('Creativo')))
        capa.addWidget(_grupo(*filas))
        capa.addWidget(_etiqueta_seccion(tr('Sonido')))
        capa.addWidget(_grupo(_FilaAtajo(tr('Tu atajo'), tr('Insertar el efecto elegido en Resolve. Se configura en '
                                                             'SFX Lab y funciona aunque CineCaptions no tenga el foco.'),
                                         ultima=True)))

    # -- Acerca de ------------------------------------------------------------
    def _pag_acerca(self, capa):
        self._cabeza_pagina(capa, tr('Información'), tr('Acerca de CineCaptions'),
                            tr('Versión, licencia, novedades y actualizaciones.'))
        cab, cc = caja_h(espacio=18, margenes=(30, 26, 30, 26))
        logo = QLabel()
        try:
            import instalador_scripts
            pm = ui.pixmap_de_archivo(instalador_scripts.BASE_RECURSOS / 'logo_cinecaptions.png', 64)
            if pm is not None:
                logo.setPixmap(ui.pixmap_redondeado(pm, 14))
        except Exception:
            pass
        cc.addWidget(logo)
        col, ccol = caja_v(espacio=4)
        ccol.addWidget(Etiqueta('CineCaptions', 26, peso='extra', color='#FFFFFF'))
        self.acerca_version = Etiqueta(f'v{_version()} · ' + texto_canal(self._borrador['canal_beta']), 15, color=ui.TEXT_MUTED)
        ccol.addWidget(self.acerca_version)
        cc.addWidget(col, 1)
        g_cab = _grupo(cab)
        # licencia
        caja_lic, cl = caja_v(espacio=8)
        fl, cfl = caja_h(espacio=10)
        self.lic_punto = Punto(ui.TEXT_MUTED, 10)
        cfl.addWidget(self.lic_punto, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lic_estado = Etiqueta('', 16, peso='negrita', color='#FFFFFF')
        cfl.addWidget(self.lic_estado, 1)
        cl.addWidget(fl)
        self.lic_detalle = TextoAjustable('', 13)
        cl.addWidget(self.lic_detalle)
        fb, cfb = caja_h(espacio=10)
        self.lic_btn = Boton(tr('Actualizar licencia'), self._abrir_licencia, tipo='neutro', alto=42, tam=14)
        cfb.addWidget(self.lic_btn)
        self.lic_desact = Boton(tr('Desactivar este equipo'), lambda: desactivar_licencia(self.app, self._pintar_licencia),
                                tipo='peligro', alto=42, tam=14)
        cfb.addWidget(self.lic_desact)
        cl.addWidget(fb)
        f_lic = _Fila(tr('Licencia'), tr('Tu clave de Lemon Squeezy. Desactiva este equipo para activarla en otra computadora.'),
                      caja_lic, 380)
        self._pintar_licencia()
        # notas
        f_notas = _Fila(tr('Notas de la versión'), tr('Lo nuevo de esta versión, también sin conexión.'),
                        Boton(tr('Leer notas de la versión'), lambda: mostrar_notas(self.app), tipo='neutro', alto=46, tam=15), 380)
        # actualizaciones automáticas (v5.3.5): el aviso de Inicio y la descarga con un clic
        auto_var = BooleanVar(bool(self._borrador.get('actualizaciones_auto', True)))
        f_auto = _Fila(tr('Avisarme de las actualizaciones'),
                       tr('CineCaptions mira solo si hay una versión nueva (cada 10 segundos) y te lo dice al momento; tú decides cuándo instalarla.'),
                       Interruptor('', var=auto_var, comando=lambda: self._cambio('actualizaciones_auto', bool(auto_var.get()))))
        # actualizaciones
        caja_act, ca = caja_v(espacio=8)
        self.control_act = ControlActualizacion(self.app)
        self.act_estado = self.control_act.estado
        ca.addWidget(self.control_act)
        f_act = _Fila(tr('Actualizaciones'), tr('CineCaptions vigila solo si hay una versión nueva (cada 10 segundos) y te avisa; aquí puedes buscarla a mano y leer sus mejoras.'), caja_act, 380)
        # creditos
        cred, ccr = caja_v(espacio=6)
        # v5.3.5: el logo «CINEMA PRODUCTIONS» en vez del texto (si el archivo faltara, vuelve el texto)
        try:
            import instalador_scripts
            from PySide6.QtGui import QPixmap
            ruta_marca = instalador_scripts.BASE_RECURSOS / 'logo_cinema_productions.png'
            pm_marca = QPixmap(str(ruta_marca)) if ruta_marca.exists() else QPixmap()
            if pm_marca.isNull():
                raise OSError('sin logo')
            dpr = max(1.0, float(self.devicePixelRatioF()))
            pm_marca = pm_marca.scaledToHeight(int(round(28 * dpr)), Qt.TransformationMode.SmoothTransformation)
            pm_marca.setDevicePixelRatio(dpr)
            marca = QLabel()
            marca.setPixmap(pm_marca)
            marca.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            marca.setStyleSheet('background: transparent;')
            marca.setAccessibleName('By Cinema Productions')
            ccr.addWidget(marca)
        except Exception:
            ccr.addWidget(Etiqueta('By Cinema Productions', 15, peso='negrita', color='#FFFFFF'))
        ccr.addWidget(Etiqueta('© 2026 Cinema Productions', 13, color=ui.TEXT_MUTED))
        f_cred = _Fila(tr('Créditos'), tr('Transcripción: Qwen3-ASR y Whisper · Traducción: Argos · Interfaz: Qt (PySide6).'),
                       cred, 380, ultima=True)
        capa.addWidget(g_cab)
        capa.addWidget(_grupo(f_lic, f_notas, f_auto, f_act, f_cred))

    def _pintar_licencia(self):
        if not ui.vivo(getattr(self, 'lic_estado', None)):
            return
        d = datos_licencia()
        self.lic_punto.poner(d['color'])
        self.lic_estado.configure(text=d['estado'])
        detalle = d['detalle']
        if d.get('hay_clave'):
            try:
                import licencia
                detalle = licencia.texto() if d['activa'] else detalle + '\n' + licencia.texto()
            except Exception:
                pass
        self.lic_detalle.setText(detalle)
        self.lic_desact.setVisible(d['activa'])
        self.lic_btn.setVisible(d['configurada'])
        self.lic_btn.configure(text=tr('Ver mi licencia') if d['activa'] else tr('Activar licencia'))

    def _abrir_licencia(self):
        try:
            self.app._abrir_licencia()
        except Exception:
            pass

    # -- Ayuda ----------------------------------------------------------------
    def _pag_ayuda(self, capa):
        self._cabeza_pagina(capa, tr('Soporte'), tr('Ayuda'),
                            tr('Si algo no funciona, el diagnóstico junta todo lo necesario para resolverlo.'))
        app = self.app

        def llamar(nombre):
            fn = getattr(app, nombre, None)
            if callable(fn):
                self.cerrar()
                fn()
        f_diag = _Fila(tr('Diagnóstico'), tr('Revisa Resolve, la conexión MCP, el Puente, los scripts, el motor de voz y '
                                             'la licencia, y lo deja listo para copiar y enviar.'),
                       Boton(tr('Ejecutar diagnóstico'), lambda: llamar('_ejecutar_diagnostico'), tipo='neutro', alto=46, tam=15), 340)
        f_scripts = _Fila(tr('Scripts de Resolve'), tr('Vuelve a poner los scripts de CineCaptions en Área de trabajo > '
                                                      'Scripts (para Resolve Free).'),
                          Boton(tr('Reinstalar scripts'), lambda: llamar('_instalar_en_resolve'), tipo='neutro', alto=46, tam=15), 340)
        f_resp = _Fila(tr('Qué respondió Resolve'), tr('El último resultado que dejó un script dentro de Resolve.'),
                       Boton(tr('Ver respuesta'), lambda: llamar('_ver_ultimo_resultado'), tipo='neutro', alto=46, tam=15), 340)
        f_datos = _Fila(tr('Carpeta de datos'), str(Path.home() / 'DaVinciSubtitles'),
                        Boton(tr('Abrir carpeta'), lambda: abrir_carpeta(Path.home() / 'DaVinciSubtitles'), tipo='neutro',
                              alto=46, tam=15), 340)
        f_contacto = _Fila(tr('Contacto'), tr('Copia el diagnóstico y envíalo a Cinema Productions por el canal donde '
                                             'compraste CineCaptions.'),
                           Boton(tr('Copiar diagnóstico'), lambda: llamar('_ejecutar_diagnostico'),
                                 tipo='neutro', alto=46, tam=15), 340, ultima=True)
        capa.addWidget(_grupo(f_diag, f_scripts, f_resp, f_datos, f_contacto))

    # -- aplicar / cerrar -----------------------------------------------------
    def aplicar(self):
        b = self._borrador
        guardar_prefs({'tema': b['tema'], 'acento': b['acento'], 'acento_personal': b['acento_personal'],
                       'tamano_interfaz': b['tamano'], 'lateral_inicio': b['lateral'], 'motor_voz': b['motor_voz'],
                       'canal_beta': False, 'actualizaciones_auto': b.get('actualizaciones_auto', True), 'ventana_encima': b['ventana_encima'], 'avisos_sistema': b['avisos_sistema'], 'go_estilo': b['go_estilo']})
        reiniciar = any(b.get(k) != self._inicial.get(k) for k in ('tema', 'acento', 'acento_personal', 'tamano'))
        if b.get('idioma_ui') != self._inicial.get('idioma_ui'):
            try:
                import i18n
                codigo = next((c for c, n in i18n.IDIOMAS_UI.items() if n == b['idioma_ui']), None)
                if codigo:
                    i18n.guardar_idioma(codigo)
                    reiniciar = True
            except Exception:
                pass
        try:
            self.app.fondo.poner_pagina(self.app._pagina_actual)          # la aurora del estilo elegido, ya
        except Exception:
            pass
        try:
            self.app.poner_encima(b['ventana_encima'])
            self.app._pintar_pie_lateral()
            self.app._refrescar_estado()
        except Exception:
            pass
        self._inicial = dict(b)
        self.aplicar_btn.setEnabled(False)
        if reiniciar:
            self.estado.configure(text=tr('Se aplica al reiniciar CineCaptions.'), text_color=ui.AMBAR)
            self.reiniciar_btn.show()
        else:
            self.estado.configure(text=tr('Las preferencias están actualizadas.'), text_color=ui.TEXT_MUTED)
        return reiniciar

    def _listo(self):
        if self.aplicar_btn.isEnabled():
            if self.aplicar():
                if messagebox.askyesno(tr('Reiniciar CineCaptions'),
                                       tr('Algunos cambios se ven al reiniciar. ¿Reiniciar ahora?'), parent=self.app):
                    self._reiniciar()
                    return
        self.cerrar()

    def _reiniciar(self):
        try:
            self.app.reiniciar_programa()
        except Exception as e:
            messagebox.showerror(tr('Reiniciar'), str(e), parent=self.app)

    def abrir(self):
        self._capa = CapaModal(self.app, self, cerrar_fuera=False)

    def cerrar(self):
        if self._capa is not None and ui.vivo(self._capa):
            self._capa.cerrar()


class _FilaAtajo(QFrame):
    def __init__(self, tecla, que, ultima=False):
        super().__init__()
        self.setObjectName('filaAjuste')
        if not ultima:
            self.setStyleSheet(ui.traducir_hoja('QFrame#filaAjuste { border: none; border-bottom: 1px solid #1A2438; }'))
        c = QHBoxLayout(self)
        c.setContentsMargins(30, 18, 30, 18)
        c.setSpacing(24)
        t = TextoAjustable(que, 15, color='#E0EBFB')
        c.addWidget(t, 1)
        tecla_lbl = Etiqueta(tecla, 14, peso='negrita', color='#FFFFFF')
        tecla_lbl.setStyleSheet(ui.traducir_hoja('QLabel { background-color: #111D33; border: 1px solid #2A3D5D; '
                                                 'border-radius: 8px; padding: 6px 12px; }'))
        c.addWidget(tecla_lbl, 0, Qt.AlignmentFlag.AlignVCenter)


# ---------------------------------------------------------------------------
def abrir_carpeta(ruta):
    try:
        if sys.platform == 'win32':
            os.startfile(str(ruta))
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.Popen(['open', str(ruta)])
        else:
            import subprocess
            subprocess.Popen(['xdg-open', str(ruta)])
    except Exception:
        pass


def crear_copia(app, al_terminar=None, boton=None):
    """La copia de seguridad, en un hilo, con el aviso al final."""
    import copias
    import ui_toast
    if boton is not None:
        boton.setEnabled(False)

    def fin(r, error):
        if boton is not None and ui.vivo(boton):
            boton.setEnabled(True)
        if error is not None:
            messagebox.showerror(tr('Copia de seguridad'), tr('No pude crear la copia: {e}', e=error), parent=app)
        else:
            ruta, n = r
            ui_toast.mostrar(app, tr('Copia creada: {n} archivos en {nombre}', n=n, nombre=ruta.name), duracion_ms=4500)
        if al_terminar:
            al_terminar()
    correr_en_hilo(app, copias.crear, fin)
