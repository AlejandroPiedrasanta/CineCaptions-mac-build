# CineCaptions · By Cinema Productions
# 1_codigo/aviso_mac.py — v5.90 (el usuario: «en Mac sigue sin recibir actualizaciones… que cuando salga una actualización DE VERDAD
# notifique en la Mac, que tenga más permiso y control»). Con el programa CERRADO, el servicio del sistema (actualizar_fondo, de root)
# avisaba con `osascript display notification`: en macOS esas notificaciones salen a nombre del «Editor de Scripts» y, si nunca se le
# dieron permisos, no se ven nunca (y nadie se entera de que hubo versión nueva). Ahora el aviso es una ventana del PROPIO CineCaptions que
# el servicio abre en la sesión de quien está frente a la Mac (`open -n … --args --tarea aviso_mac /dev/null <aviso.json>`): no necesita
# permisos de notificaciones y deja elegir.
"""
Una tarjeta arriba a la derecha (donde salen las notificaciones de macOS), siempre encima:
  preguntar   «Nueva versión de CineCaptions» · 5.89 → 5.90 · sus novedades · «Más tarde» / «Actualizar ahora»; si nadie elige nada en
              `espera_s` se instala sola (pedido de la 5.87: «que se descarguen e instalen solas»)
  instalando  la barra que avanza mientras el servicio instala; se cierra sola cuando el servicio termina (lo lee en su estado.json)
  hecha       «CineCaptions se actualizó a la 5.90» · «Abrir CineCaptions»
  fallo       por qué no se pudo · «Descargar» (la página de la versión) · se reintenta solo
La respuesta vuelve al servicio como un pedido en /Users/Shared/CineCaptions/pedidos: {"accion": "instalar"|"luego", "id": …}.
Todo se carga al empezar: mientras la tarjeta dice «instalando», el .pkg reemplaza la app de la que salió este proceso.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import actualizar_fondo                        # (aquí y no al responder: para entonces el .pkg puede estar reemplazando la app)

ESTADO_SERVICIO = Path('/Library/Application Support/CineCaptions/actualizar/estado.json')
APP_MAC = '/Applications/CineCaptions.app'
TOPE_S = 6 * 3600                              # una tarjeta olvidada no se queda abierta para siempre
TOPE_INSTALANDO_S = 20 * 60                    # «instalando» sin noticias del servicio: se cierra (el servicio abre la del final)
ANCHO = 392
LINEAS_NOVEDAD = 2


def partir(texto, fm, ancho, maximo=LINEAS_NOVEDAD):
    """Las líneas de `texto` que caben en `ancho` (palabra a palabra), como mucho `maximo`; la última con «…» si no cabe todo."""
    lineas, actual = [], ''
    palabras = str(texto).split()
    for i, p in enumerate(palabras):
        prueba = (actual + ' ' + p).strip()
        if fm.horizontalAdvance(prueba) <= ancho or not actual:
            actual = prueba
            continue
        lineas.append(actual)
        actual = p
        if len(lineas) == maximo:
            break
    else:
        if actual:
            lineas.append(actual)
        return lineas[:maximo]
    ultima = lineas[-1]
    while ultima and fm.horizontalAdvance(ultima + '…') > ancho:
        ultima = ultima[:-1].rstrip()
    lineas[-1] = ultima + '…'
    return lineas


def leer(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def responder(accion, ident):
    """Deja la respuesta al servicio (lo despierta si no estaba esperando). True si quedó."""
    try:
        carpeta = actualizar_fondo.PEDIDOS_MAC
        datos = {'accion': accion, 'id': str(ident), 'pid': os.getpid(), 'ts': time.time()}
        tmp = carpeta / f'.respuesta_{os.getpid()}.tmp'
        tmp.write_text(json.dumps(datos), encoding='utf-8')
        tmp.rename(carpeta / f'respuesta_{os.getpid()}_{int(time.time() * 1000)}.json')
        return True
    except Exception:
        return False


def resultado(estado, version, desde):
    """'hecha' | 'fallo' | None según lo que el servicio dejó en su estado.json DESPUÉS de `desde`."""
    if str(estado.get('instalada') or '') == str(version):
        return 'hecha'
    if str(estado.get('version') or '') == str(version) and float(estado.get('fallo_ts') or 0) >= desde - 5:
        return 'fallo'
    return None


def mostrar(ruta_aviso):
    """La tarjeta (bloquea hasta que se cierra). Devuelve lo que pasó, para el registro de la tarea."""
    aviso = leer(ruta_aviso)
    if not aviso.get('version') or aviso.get('modo') not in ('preguntar', 'instalando', 'hecha', 'fallo'):
        return 'aviso vacío'
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
    from PySide6.QtGui import QFontMetricsF, QGuiApplication, QLinearGradient, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

    import qt_kit as ui
    from i18n import tr
    from qt_kit import QColor, fuente
    import actualizar_ui
    try:
        from sfx_rules import base_recursos
        recursos = Path(base_recursos())
    except Exception:
        recursos = Path(__file__).resolve().parent.parent / '2_recursos'
    app = ui.crear_app(sys.argv[:1], carpeta_fuentes=recursos / 'fonts')
    logo = QPixmap(str(recursos / 'logo_cinecaptions.png'))
    try:
        ui.poner_icono_app(str(recursos / 'logo_cinecaptions.png'))
    except Exception:
        pass
    iconos = {}
    for nombre, color in (('ph.arrow-right', ui.TEXT_MUTED), ('ph.sparkle-fill', ui.VERDE), ('ph.check-bold', '#05080E'),
                          ('ph.warning-fill', ui.AMBAR), ('ph.x', ui.TEXT_MUTED)):
        ic = ui.icono_linea(nombre, color)
        iconos[nombre] = ic.pixmap(16, 16) if ic is not None else None
    try:                                                             # (las notas del manifiesto, una por línea, traducidas como en el aviso del programa)
        import ajustes_ui
        novedades = [tr(n) for n in ajustes_ui.lineas_de_notas(aviso.get('notas'))][:3]
    except Exception:
        novedades = actualizar_ui.novedades(aviso.get('notas'), 3)
    fm12 = QFontMetricsF(fuente(12))
    ancho_nov = ANCHO - 14 - 18 - 30 - 9
    novedades = [partir(n, fm12, ancho_nov) for n in novedades]
    textos = {                                                       # (traducidos AHORA: luego la app puede estar a medio reemplazar)
        'titulo': tr('Nueva versión de CineCaptions'), 'hecha': tr('CineCaptions se actualizó'), 'fallo': tr('No se pudo actualizar'),
        'instalando': tr('Actualizando CineCaptions…'), 'luego': tr('Más tarde'), 'ahora': tr('Actualizar ahora'),
        'abrir': tr('Abrir CineCaptions'), 'cerrar': tr('Cerrar'), 'descargar': tr('Descargar'),
        'cuenta': tr('Se instala sola en {t} si no eliges nada.'),
        'nota_inst': tr('No hace falta tu contraseña. Tus proyectos y ajustes no se tocan.'),
        'nota_hecha': tr('Ya tienes la {v}. Al abrir CineCaptions verás sus novedades.', v=aviso['version']),
        'nota_fallo': tr('Lo vuelve a intentar solo más tarde. También puedes descargarla e instalarla tú.'),
    }

    class Tarjeta(QWidget):
        def __init__(self):
            super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setWindowTitle('CineCaptions')
            self.modo = aviso['modo']
            self.inicio = time.time()
            self.limite = self.inicio + max(10, int(aviso.get('espera_s') or 120))
            self.t = 0.0
            self.ult = time.perf_counter()
            self.motivo = str(aviso.get('motivo') or '')
            self._arrastre = None
            v = QVBoxLayout(self)
            v.setContentsMargins(18, 16, 18, 16)
            v.setSpacing(0)
            v.addStretch(1)
            fila = QHBoxLayout()
            fila.setSpacing(8)
            fila.addStretch(1)
            self.b2 = ui.Boton('', None, tipo='neutro', alto=34, tam=13)
            self.b1 = ui.Boton('', None, tipo='primario', alto=34, tam=13, negrita=True)
            self.b2.clicked.connect(lambda: self._pulsar(2))
            self.b1.clicked.connect(lambda: self._pulsar(1))
            fila.addWidget(self.b2)
            fila.addWidget(self.b1)
            v.addLayout(fila)
            self.reloj = QTimer(self)
            self.reloj.setInterval(33)                               # (solo mientras anima: la entrada y la barra de «instalando»)
            self.inicio_inst = time.time()
            self.reloj.timeout.connect(self._tic)
            self.sondeo = QTimer(self)
            self.sondeo.setInterval(1000)
            self.sondeo.timeout.connect(self._sondear)
            self._poner_modo(self.modo)

        # ── estado
        def _poner_modo(self, modo):
            self.modo = modo
            if modo == 'instalando':
                self.inicio_inst = time.time()
                if self.isVisible() and not self.reloj.isActive():
                    self.ult = time.perf_counter()
                    self.reloj.start()
            botones = {'preguntar': (textos['ahora'], textos['luego']), 'instalando': (None, None),
                       'hecha': (textos['abrir'], textos['cerrar']), 'fallo': (textos['descargar'], textos['cerrar'])}[modo]
            for b, texto in zip((self.b1, self.b2), botones):
                b.setVisible(bool(texto))
                if texto:
                    b.setText(texto)
            fm = QFontMetricsF(fuente(12))
            nota = self._nota()
            alto_nota = fm.boundingRect(QRectF(0, 0, ANCHO - 36 - 52, 1000), int(Qt.TextFlag.TextWordWrap), nota).height() if nota else 0
            alto_nov = sum(len(n) * 17 + 6 for n in novedades) if modo == 'preguntar' and novedades else 0
            alto = int(16 + 64 + (alto_nov + 8 if alto_nov else 0) + (alto_nota + 10 if nota else 0) + (24 if modo == 'instalando' else 0)
                       + (50 if botones[0] else 6) + 12)
            self.setFixedSize(ANCHO, alto)
            self._colocar()
            self.update()

        def _nota(self):
            if self.modo == 'preguntar':
                return textos['cuenta'].format(t=self._quedan())
            return {'instalando': textos['nota_inst'], 'hecha': textos['nota_hecha'],
                    'fallo': (self.motivo + '\n' if self.motivo else '') + textos['nota_fallo']}[self.modo]

        def _quedan(self):
            s = max(0, int(round(self.limite - time.time())))
            return f'{s // 60}:{s % 60:02d}'

        def _colocar(self):
            pantalla = QGuiApplication.primaryScreen()
            if pantalla is None:
                return
            g = pantalla.availableGeometry()
            self.move(g.right() - self.width() - 14, g.top() + 12)

        def _pulsar(self, k):
            if self.modo == 'preguntar':
                if k == 1:
                    responder('instalar', aviso.get('id'))
                    self._poner_modo('instalando')
                else:
                    responder('luego', aviso.get('id'))
                    self.close()
            elif self.modo == 'hecha':
                if k == 1:
                    try:
                        subprocess.Popen(['/usr/bin/open', APP_MAC], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except OSError:
                        pass
                self.close()
            elif self.modo == 'fallo':
                if k == 1 and aviso.get('url'):
                    try:
                        subprocess.Popen(['/usr/bin/open', str(aviso['url'])], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except OSError:
                        pass
                self.close()

        def _sondear(self):
            if time.time() - self.inicio > TOPE_S:
                self.close()
                return
            otro = leer(ruta_aviso)                                  # el servicio abrió otra tarjeta: esta sobra
            if otro.get('id') and otro.get('id') != aviso.get('id'):
                self.close()
                return
            if self.modo == 'preguntar':
                if time.time() >= self.limite:                       # nadie eligió: se instala sola (el servicio también lo decide al acabar el plazo)
                    responder('instalar', aviso.get('id'))
                    self._poner_modo('instalando')
                else:
                    self.update()
            elif self.modo == 'instalando':
                if resultado(leer(ESTADO_SERVICIO), aviso['version'], self.inicio) or time.time() - self.inicio_inst > TOPE_INSTALANDO_S:
                    self.close()                                     # el servicio abre la tarjeta del final (con la versión NUEVA)

        # ── dibujo
        def showEvent(self, e):
            self.ult = time.perf_counter()
            self.reloj.start()
            self.sondeo.start()
            super().showEvent(e)

        def _tic(self):
            ahora = time.perf_counter()
            self.t += min(0.05, ahora - self.ult)
            self.ult = ahora
            self.update()
            if self.modo != 'instalando' and self.t >= 1.0:
                self.reloj.stop()                                    # quieta: sin despertar el proceso 30 veces por segundo

        def paintEvent(self, _e):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            entrada = actualizar_ui._suave(self.t / 0.35)
            p.setOpacity(entrada)
            p.translate(0, -8.0 * (1.0 - entrada))
            r = QRectF(self.rect()).adjusted(4.5, 4.5, -4.5, -4.5)
            for i, alfa in enumerate((10, 18, 28)):                  # sombra suave
                d = 4.0 - i * 1.3
                p.setPen(QPen(QColor(0, 0, 0, alfa), 1.4))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(-d, -d + 1, d, d + 1), 16 + d, 16 + d)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0.0, QColor('#0E1830'))
            g.setColorAt(1.0, QColor(ui.BG_COLOR))
            color_borde = {'fallo': QColor(245, 184, 75, 120), 'hecha': QColor(36, 209, 143, 140)}.get(self.modo, QColor('#24304A'))
            p.setPen(QPen(color_borde, 1.0))
            p.setBrush(g)
            p.drawRoundedRect(r, 16, 16)
            x0, y0 = r.left() + 14, r.top() + 14
            if not logo.isNull():
                p.drawPixmap(QRectF(x0, y0, 44, 44), logo, QRectF(logo.rect()))
            xt = x0 + 56
            ancho_t = r.right() - xt - 12
            titulo = {'preguntar': textos['titulo'], 'instalando': textos['instalando'], 'hecha': textos['hecha'], 'fallo': textos['fallo']}[self.modo]
            p.setFont(fuente(14, True))
            p.setPen(QColor(ui.TEXT_COLOR))
            fmt = QFontMetricsF(fuente(14, True))
            p.drawText(QRectF(xt, y0 - 1, ancho_t, 22), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       fmt.elidedText(titulo, Qt.TextElideMode.ElideRight, ancho_t))
            # versión vieja → nueva
            y = y0 + 34
            x = xt
            p.setFont(fuente(12))
            fm = QFontMetricsF(fuente(12))
            vieja = str(aviso.get('vieja') or '')
            if vieja and self.modo != 'hecha':
                p.setPen(QColor(ui.TEXT_MUTED))
                p.drawText(QPointF(x, y + 4), vieja)
                x += fm.horizontalAdvance(vieja) + 6
                if iconos.get('ph.arrow-right'):
                    p.drawPixmap(QPointF(x, y - 7), iconos['ph.arrow-right'])
                x += 22
            chip = f"v{aviso['version']}"
            fmc = QFontMetricsF(fuente(11, True))
            rc = QRectF(x, y - 10, fmc.horizontalAdvance(chip) + 30, 20)
            p.setPen(QPen(QColor(36, 209, 143, 120), 1.0))
            p.setBrush(QColor(36, 209, 143, 30))
            p.drawRoundedRect(rc, 10, 10)
            if iconos.get('ph.sparkle-fill'):
                p.drawPixmap(QRectF(rc.left() + 6, rc.center().y() - 6, 12, 12), iconos['ph.sparkle-fill'], QRectF(0, 0, 16, 16))
            p.setFont(fuente(11, True))
            p.setPen(QColor(ui.VERDE))
            p.drawText(rc.adjusted(18, 0, -4, 0), int(Qt.AlignmentFlag.AlignCenter), chip)
            y = r.top() + 14 + 64
            # novedades (solo al preguntar)
            if self.modo == 'preguntar' and novedades:
                p.setFont(fuente(12))
                for lineas in novedades:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(ui.VERDE))
                    p.drawEllipse(QPointF(x0 + 6, y + 8.5), 2.6, 2.6)
                    p.setPen(QColor('#C9D6EC'))
                    for linea in lineas:
                        p.drawText(QRectF(x0 + 18, y, r.right() - x0 - 30, 17), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), linea)
                        y += 17
                    y += 6
                y += 8
            # barra mientras instala
            if self.modo == 'instalando':
                barra = QRectF(x0, y + 4, r.right() - x0 - 14, 6)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor('#18233A'))
                p.drawRoundedRect(barra, 3, 3)
                fase = (self.t * 0.6) % 1.0
                ancho_b = barra.width() * 0.32
                xb = barra.left() - ancho_b + (barra.width() + ancho_b) * fase
                tramo = QRectF(max(barra.left(), xb), barra.top(), min(barra.right(), xb + ancho_b) - max(barra.left(), xb), barra.height())
                if tramo.width() > 0:
                    gb = QLinearGradient(tramo.topLeft(), tramo.topRight())
                    gb.setColorAt(0.0, QColor(36, 209, 143, 60))
                    gb.setColorAt(1.0, QColor('#7AF0C2'))
                    p.setBrush(gb)
                    p.drawRoundedRect(tramo, 3, 3)
                y += 24
            nota = self._nota()
            if nota:
                p.setFont(fuente(12))
                p.setPen(QColor(ui.AMBAR) if self.modo == 'fallo' else QColor(ui.TEXT_MUTED))
                p.drawText(QRectF(x0, y, r.right() - x0 - 14, 200), int(Qt.TextFlag.TextWordWrap), nota)
            p.end()

        def mousePressEvent(self, e):
            if e.button() == Qt.MouseButton.LeftButton:
                self._arrastre = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

        def mouseMoveEvent(self, e):
            if self._arrastre is not None and e.buttons() & Qt.MouseButton.LeftButton:
                self.move(e.globalPosition().toPoint() - self._arrastre)

        def mouseReleaseEvent(self, _e):
            self._arrastre = None

        def closeEvent(self, e):
            self.reloj.stop()
            self.sondeo.stop()
            QTimer.singleShot(0, app.quit)                          # (no «la última ventana»: en una prueba puede haber otras abiertas)
            super().closeEvent(e)

    tarjeta = Tarjeta()
    tarjeta.show()
    tarjeta.raise_()
    tarjeta.activateWindow()
    app.exec()
    return 'tarjeta ' + tarjeta.modo
