# CineCaptions Ventas · By Cinema Productions
# programa/mac/dmg/ajustes_dmg.py — la ventana del .dmg de Mac (dmgbuild): «Arrástralo a Aplicaciones», como el de CineCaptions 5.90
# (2.10, el dueño con una captura: «así hazlo»). Lo usa mac/construir_ventas_mac.sh:
#   dmgbuild -s mac/dmg/ajustes_dmg.py -D app=<CineCaptions Ventas.app> -D fondo=<fondo.tiff> -D icono=<.icns> "<volumen>" <salida.dmg>
# El fondo (fondo.png + fondo@2x.png → fondo.tiff con tiffutil) sale de fondo_dmg.html: 600 × 360 puntos. Si se mueve algo del fondo
# (la flecha va de x 258 a 344 en y 168), mover aquí el icono que le toca: las coordenadas son el CENTRO del icono, en puntos, desde
# arriba a la izquierda. dmgbuild escribe el .DS_Store él mismo (sin el Finder ni AppleScript, que en las Mac de GitHub no son de fiar).
# Sin barras: los nombres de los iconos acaban en y ≈ 240, lejos de los bordes; lo de abajo del fondo (334-360) es de reserva.
import os

app = defines['app']                                       # noqa: F821 (lo pone dmgbuild)
NOMBRE = os.path.basename(app.rstrip('/'))                 # «CineCaptions Ventas.app»

format = 'UDZO'
filesystem = 'HFS+'
files = [app]
symlinks = {'Aplicaciones': '/Applications'}
hide_extensions = [NOMBRE]
icon = defines.get('icono') or None                        # noqa: F821 (el icono del disco: el de la app)
background = defines['fondo']                              # noqa: F821
# (el alto es el de la ventana ENTERA: 360 del fondo + 28 de la barra del título de macOS 15; la «y» se cuenta desde ABAJO de la pantalla)
window_rect = ((240, 260), (600, 388))
default_view = 'icon-view'
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
show_icon_preview = False
arrange_by = None
icon_size = 100
text_size = 13
icon_locations = {
    NOMBRE: (185, 168),                                    # a la izquierda de la flecha
    'Aplicaciones': (415, 168),                            # a la derecha
}
