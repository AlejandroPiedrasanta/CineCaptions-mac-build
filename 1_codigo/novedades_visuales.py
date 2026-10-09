"""«Novedades» con imagen (v5.4.8): bajo el título del cuadro de novedades sale una tira de clips cortos en bucle (los mismos mp4 de vista previa que ya trae el
programa en 2_recursos) con lo nuevo de la versión: ver la mejora vale más que leerla. Un clip solo se mueve mientras se ve (como en la página Efectos).

`CLIPS_POR_VERSION` dice qué clips enseña cada versión: (carpeta dentro de 2_recursos, nombre sin extensión, texto). Si el archivo no existe (versión compilada
sin esa carpeta) el clip simplemente no sale. `clips_de(versiones)` junta los de las versiones que se muestran, sin repetir y con un máximo.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QWidget

import qt_kit as ui
from i18n import tr

CLIPS_POR_VERSION = {
    '5.4.8': [('efectos/previas', 'corte_glitch', 'Glitch RGB en los cortes'),
              ('efectos/previas', 'corte_zoom_blur', 'Zoom desenfocado'),
              ('efectos/previas', 'corte_whip', 'Barrido rápido')],
    '5.4.7': [('efectos/previas', 'intro_destello', 'Intro con destello y sonido'),
              ('efectos/previas', 'corte_destello', 'Transición en cada corte'),
              ('efectos/previas', 'iconos_pack1', 'Iconos flotantes en las palabras que tú eliges'),
              ('vistas_slider', 'Referencia', 'Estilos Shine con vista en movimiento')],
}
MAXIMO = 4


def _base():
    try:
        import instalador_scripts
        return Path(instalador_scripts.BASE_RECURSOS)
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos'


def clips_de(versiones):
    """[(ruta_mp4, texto)] de las versiones dadas (las más nuevas primero), solo los que existen, sin repetir, hasta MAXIMO."""
    base = _base()
    salida, vistos = [], set()
    for v in versiones:
        for carpeta, nombre, texto in CLIPS_POR_VERSION.get(v, []):
            ruta = base.joinpath(*carpeta.split('/')) / f'{nombre}.mp4'
            try:
                if ruta in vistos or not ruta.is_file() or ruta.stat().st_size < 1000:
                    continue
            except OSError:
                continue
            vistos.add(ruta)
            salida.append((ruta, texto))
            if len(salida) >= MAXIMO:
                return salida
    return salida


class ClipNovedad(QWidget):
    """Un clip 9:16 en bucle con su texto debajo; solo decodifica mientras el cuadro está a la vista."""
    ANCHO = 132
    ALTO_IMAGEN = 234

    def __init__(self, ruta, texto, padre=None):
        super().__init__(padre)
        import vistas_slider
        self._texto = tr(texto)
        self._reprod = vistas_slider.Reproductor(ruta)
        self.setFixedSize(self.ANCHO, self.ALTO_IMAGEN + 66)
        self._reloj = QTimer(self)
        self._reloj.setInterval(40)
        self._reloj.timeout.connect(self.update)

    def showEvent(self, e):
        self._reprod.arrancar()
        self._reloj.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._reprod.parar()
        self._reloj.stop()
        super().hideEvent(e)

    def closeEvent(self, e):
        self._reprod.parar()
        self._reloj.stop()
        super().closeEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(0, 0, self.ANCHO, self.ALTO_IMAGEN)
        camino = QPainterPath()
        camino.addRoundedRect(rect, 12, 12)
        p.save()
        p.setClipPath(camino)
        p.fillRect(rect, QColor('#0B1424'))
        img = self._reprod.imagen()
        if img is not None and not img.isNull():
            origen = QRectF(0, 0, img.width(), img.height())
            if img.width() * self.ALTO_IMAGEN > img.height() * self.ANCHO:       # más ancho que el marco: recorta a los lados
                ancho = img.height() * self.ANCHO / self.ALTO_IMAGEN
                origen = QRectF((img.width() - ancho) / 2, 0, ancho, img.height())
            else:
                alto = img.width() * self.ALTO_IMAGEN / self.ANCHO
                origen = QRectF(0, (img.height() - alto) / 2, img.width(), alto)
            p.drawImage(rect, img, origen)
        p.restore()
        p.setPen(QColor('#E8EEFB'))
        p.setFont(ui.fuente(11, True))
        p.drawText(QRectF(2, self.ALTO_IMAGEN + 6, self.ANCHO - 4, 58), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), self._texto)
        p.end()


def tira(clips, padre=None):
    """La fila de clips (None si no hay ninguno)."""
    if not clips:
        return None
    fila = QWidget(padre)
    h = QHBoxLayout(fila)
    h.setContentsMargins(0, 4, 0, 4)
    h.setSpacing(14)
    h.addStretch(1)
    for ruta, texto in clips:
        h.addWidget(ClipNovedad(ruta, texto))
    h.addStretch(1)
    return fila
