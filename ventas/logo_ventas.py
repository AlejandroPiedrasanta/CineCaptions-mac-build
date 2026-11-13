"""Ícono propio de «CineCaptions Ventas»: cuadro verde con el signo de dólar, para no confundirlo con el de CineCaptions.

Se pinta con código, así sale nítido en cualquier tamaño. La app lo usa para la ventana y el encabezado, y
`python logo_ventas.py <ruta.ico>` genera el .ico del exe (PyInstaller toma build\\cinecaptions.ico).
"""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QTransform

VERDE_ARRIBA = '#34d399'
VERDE_ABAJO = '#047857'
TAMANOS_ICO = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _fuente_signo():
    f = QFont()
    f.setFamilies(['Inter', 'Segoe UI'])
    f.setPixelSize(400)
    f.setWeight(QFont.Weight.Black)
    try:   # Inter es una fuente variable: se pide el grosor también por su eje
        f.setVariableAxis(QFont.Tag('wght'), 900.0)
    except (AttributeError, TypeError):
        pass
    return f


def pintar_logo(tam):
    """El ícono como imagen cuadrada de tam × tam píxeles, con fondo transparente."""
    img = QImage(tam, tam, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    m = 0 if tam <= 20 else tam * 0.04   # en 16 y 20 px el cuadro ocupa todo
    r = QRectF(m, m, tam - 2 * m, tam - 2 * m)
    radio = r.width() * 0.23
    caja = QPainterPath()
    caja.addRoundedRect(r, radio, radio)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor(VERDE_ARRIBA))
    g.setColorAt(1, QColor(VERDE_ABAJO))
    p.fillPath(caja, g)
    if tam >= 40:   # borde claro muy fino, como luz desde arriba
        p.setClipPath(caja)
        p.setPen(QPen(QColor(255, 255, 255, 70), max(1.0, tam / 64)))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radio, radio)
        p.setClipping(False)
    signo = QPainterPath()
    signo.addText(0, 0, _fuente_signo(), '$')
    b = signo.boundingRect()
    escala = r.height() * (0.70 if tam <= 24 else 0.64) / b.height()
    t = QTransform()
    t.translate(r.center().x(), r.center().y())
    t.scale(escala, escala)
    t.translate(-b.center().x(), -b.center().y())
    signo = t.map(signo)
    if tam >= 48:
        p.fillPath(signo.translated(0, tam * 0.025), QColor(2, 60, 40, 90))
    p.fillPath(signo, QColor('#ffffff'))
    p.end()
    return img


def pixmap_logo(tam, dpr=3):
    """Para el encabezado: pintado al triple y marcado así, nítido también con Windows al 150 % o 200 %."""
    pm = QPixmap.fromImage(pintar_logo(tam * dpr))
    pm.setDevicePixelRatio(dpr)
    return pm


def icono_app():
    ic = QIcon()
    for tam in TAMANOS_ICO:
        ic.addPixmap(QPixmap.fromImage(pintar_logo(tam)))
    return ic


def _png(img):
    datos = QByteArray()
    buf = QBuffer(datos)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    buf.close()
    return bytes(datos)


def guardar_ico(ruta):
    """Un .ico con cada tamaño pintado aparte (no reducido desde el grande), en PNG como acepta Windows desde Vista."""
    pngs = [(tam, _png(pintar_logo(tam))) for tam in TAMANOS_ICO]
    cabecera = struct.pack('<HHH', 0, 1, len(pngs))
    entradas, cuerpo = b'', b''
    inicio = 6 + 16 * len(pngs)
    for tam, png in pngs:
        lado = 0 if tam >= 256 else tam   # 0 significa 256 en el formato ICO
        entradas += struct.pack('<BBBBHHII', lado, lado, 0, 0, 1, 32, len(png), inicio + len(cuerpo))
        cuerpo += png
    Path(ruta).write_bytes(cabecera + entradas + cuerpo)


if __name__ == '__main__':
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    app = QGuiApplication(sys.argv[:1])
    QFontDatabase.addApplicationFont(str(Path(__file__).resolve().parent / 'fuentes' / 'Inter.ttf'))
    destino = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent / 'build' / 'cinecaptions.ico')
    guardar_ico(destino)
    print('ícono guardado:', destino)
