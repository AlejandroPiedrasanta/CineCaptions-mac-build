"""El ícono de «CineCaptions Ventas» para Mac (.icns), pintado con el mismo código que el .ico de Windows (logo_ventas.py).

Cada tamaño se pinta aparte y va como PNG dentro del .icns (el formato que usa macOS desde 10.7). Con el margen de los
íconos de macOS (el cuadro ocupa ~82 % del lienzo), para que en el Dock no se vea más grande que los demás.
    python mac/icono_mac.py build/ventas.icns
"""
import struct
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication, QImage, QPainter  # noqa: E402

import logo_ventas  # noqa: E402

# tipo del .icns → lado en píxeles (los @2x son el mismo tamaño en una pantalla Retina)
TIPOS = [('icp4', 16), ('icp5', 32), ('icp6', 64), ('ic07', 128), ('ic08', 256), ('ic09', 512), ('ic10', 1024),
         ('ic11', 32), ('ic12', 64), ('ic13', 256), ('ic14', 512)]


def pintar_mac(tam):
    """El logo con el margen de macOS: el cuadro al 82 % del lienzo, centrado (en 16 y 32 px, casi lleno)."""
    lienzo = QImage(tam, tam, QImage.Format.Format_ARGB32_Premultiplied)
    lienzo.fill(Qt.GlobalColor.transparent)
    lado = round(tam * (0.94 if tam <= 32 else 0.82))
    logo = logo_ventas.pintar_logo(lado)
    p = QPainter(lienzo)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF((tam - lado) / 2, (tam - lado) / 2, lado, lado), logo)
    p.end()
    return lienzo


def guardar_icns(ruta):
    cuerpo = b''
    for tipo, tam in TIPOS:
        png = logo_ventas._png(pintar_mac(tam))
        cuerpo += tipo.encode('ascii') + struct.pack('>I', 8 + len(png)) + png
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_bytes(b'icns' + struct.pack('>I', 8 + len(cuerpo)) + cuerpo)


if __name__ == '__main__':
    app = QGuiApplication(sys.argv[:1])
    QFontDatabase.addApplicationFont(str(AQUI.parent / 'fuentes' / 'Inter.ttf'))
    destino = sys.argv[1] if len(sys.argv) > 1 else str(AQUI.parent / 'build' / 'ventas.icns')
    guardar_icns(destino)
    print('ícono de Mac guardado:', destino)
