# CineCaptions · By Cinema Productions
# 7_mac/dmg/ajustes_dmg.py — la ventana del .dmg de la Mac (dmgbuild): fondo con los dos pasos, dónde va cada icono y nada de barras.
# v5.87 (el usuario: «en Mac el instalador hazlo más intuitivo, se verá mejor», con una captura del de VirtualBox). Lo usa
# Construir_Instalador_Mac.sh:  dmgbuild -s ajustes_dmg.py -D stage=<carpeta> -D fondo=<fondo.tiff> -D icono=<.icns> "<volumen>" <salida.dmg>
# El fondo (fondo.png + fondo@2x.png → fondo.tiff con tiffutil) sale de 4_diseno/instalador_mac/fondo_dmg.html: 660 × 520 puntos. Si se
# mueve algo del fondo, mover aquí el icono que le toca (las coordenadas son el CENTRO del icono, en puntos, desde arriba a la izquierda).
# El fondo es CLARO a propósito: con una imagen de fondo el Finder escribe los nombres de los iconos en negro (también en modo oscuro).
#
# Nada al milímetro (v5.87, «pule los instaladores y en mac que sea así»: en la Mac del usuario salían barras de desplazamiento, el pie cortado
# y «Desinstalar» encima de los consejos). El Finder pone barras en cuanto un icono, su nombre y SU MARGEN (~20-30 puntos) no caben en lo
# que enseña, y lo que enseña depende de la barra de título de cada macOS (28 puntos en macOS 15; más alta desde macOS 26). Así que: todo lo
# que importa del fondo acaba antes de y = 460 (la franja 460-520 es de reserva y puede cortarse), el último nombre de icono acaba en ~447 y
# ningún nombre se acerca a los bordes; «Desinstalar» (nombre corto) tiene su hueco propio en el pie, lejos de los consejos.
import os

stage = defines['stage']                                   # noqa: F821 (lo pone dmgbuild)
PKG = 'Instalar CineCaptions.pkg'                          # (actualizaciones._pkg_de_dmg busca cualquier *.pkg en la raíz: el nombre da igual)
DESINSTALAR = 'Desinstalar.command'

format = 'UDZO'
filesystem = 'HFS+'
files = [os.path.join(stage, PKG), os.path.join(stage, DESINSTALAR)]
symlinks = {'Aplicaciones': '/Applications'}
hide_extensions = [PKG, DESINSTALAR]
icon = defines.get('icono') or None                        # noqa: F821 (el icono del disco: el de la app)
background = defines['fondo']                              # noqa: F821
# (el alto es el de la ventana ENTERA: 520 del fondo + 28 de la barra del título de macOS 15; la «y» se cuenta desde ABAJO de la pantalla)
window_rect = ((200, 240), (660, 548))
default_view = 'icon-view'
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
show_icon_preview = False
arrange_by = None
icon_size = 72
text_size = 12
icon_locations = {
    PKG: (165, 226),                                       # tarjeta 1: «Doble clic para instalar» (la tarjeta va de y 92 a 308)
    'Aplicaciones': (495, 226),                            # tarjeta 2: «Ábrelo desde Aplicaciones»
    DESINSTALAR: (556, 392),                               # su hueco del pie (x 480-632, y 342-454), lejos de los consejos
}
