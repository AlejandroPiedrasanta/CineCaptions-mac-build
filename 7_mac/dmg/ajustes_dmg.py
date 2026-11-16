# CineCaptions · By Cinema Productions
# 7_mac/dmg/ajustes_dmg.py — la ventana del .dmg de la Mac (dmgbuild): «Arrástralo a Aplicaciones», dónde va cada icono y nada de barras.
# Lo usa Construir_Instalador_Mac.sh:  dmgbuild -s ajustes_dmg.py -D stage=<carpeta> -D fondo=<fondo.tiff> -D icono=<.icns> "<volumen>" <salida.dmg>
# El fondo (fondo.png + fondo@2x.png → fondo.tiff con tiffutil) sale de 4_diseno/instalador_mac/fondo_dmg.html: 600 × 360 puntos. Si se
# mueve algo del fondo, mover aquí el icono que le toca (las coordenadas son el CENTRO del icono, en puntos, desde arriba a la izquierda).
# El fondo es CLARO a propósito: con una imagen de fondo el Finder escribe los nombres de los iconos en negro (también en modo oscuro).
#
# v5.91 (el usuario: «omite que pida contraseña para poderse instalar» y «propuestas más minimalistas»; eligió «arrastrar a Aplicaciones» y la
# propuesta C): ya no hay .pkg que abrir (instalar en /Applications con un .pkg SIEMPRE pide la contraseña de la Mac). El disco trae la app y
# el enlace a Aplicaciones: arrastrar no pide contraseña a un usuario administrador. Lo que hacía el .pkg lo hace el programa al abrirse
# (scripts de Resolve, tipografías, motor de IA y el servicio de actualizaciones del usuario: actualizar_fondo.asegurar_programada).
#
# El paquete OCULTO (nombre con punto: el Finder no lo enseña) es para las Mac que ya tienen la 5.87-5.90: su servicio de root busca un
# *.pkg en el disco y lo instala con `installer -target /`. Ese paquete no trae la app: su postinstall la copia de este mismo disco.
#
# Nada al milímetro: el Finder pone barras en cuanto un icono, su nombre y su margen no caben en lo que enseña, y lo que enseña depende de la
# barra de título de cada macOS (28 puntos en macOS 15; más alta desde macOS 26). Los nombres acaban en ~y 240 y el consejo del pie antes de
# y 335: los últimos puntos pueden cortarse sin perder nada.
import os

stage = defines['stage']                                   # noqa: F821 (lo pone dmgbuild)
APP = 'CineCaptions.app'
PKG_OCULTO = '.Actualizar CineCaptions.pkg'                # (5.87-5.90: actualizaciones._pkg_de_dmg busca *.pkg con pathlib, que SÍ ve los ocultos)

# LZFSE (ULFO) y no lzma (ULMO): macOS comprueba el disco al abrirlo y luego se copia la app; con lzma las dos cosas iban lentas (v5.91, el
# usuario: «que no tenga tiempo de abrir, que de una vez abra… todo inmediato»). Ocupa algo más, pero se abre y se copia mucho antes.
format = 'ULFO'
# APFS y no HFS+: HFS+ reescribe los nombres con tildes en otra forma Unicode (NFD) y la firma de la app ya no cuadra («a sealed resource is
# missing or invalid», medido en Macs de GitHub: sfx_library/«Cámara», «Selección»…); con la app en cuarentena macOS diría «está dañada»
filesystem = 'APFS'
files = [os.path.join(stage, APP), os.path.join(stage, PKG_OCULTO)]
symlinks = {'Aplicaciones': '/Applications'}
# (sin hide_extensions: le pone com.apple.FinderInfo a la app y la firma estricta lo rechaza; el Finder ya no enseña «.app» en las apps)
icon = defines.get('icono') or None                        # noqa: F821 (el icono del disco: el de la app)
background = defines['fondo']                              # noqa: F821
# (el alto es el de la ventana ENTERA: 360 del fondo + 28 de la barra del título de macOS 15; la «y» se cuenta desde ABAJO de la pantalla)
window_rect = ((240, 300), (600, 388))
default_view = 'icon-view'
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
show_icon_preview = False
arrange_by = None
icon_size = 104
text_size = 12
icon_locations = {
    APP: (185, 168),                                       # a la izquierda de la flecha (x 258-342, y 168)
    'Aplicaciones': (415, 168),                            # a la derecha
    PKG_OCULTO: (560, 250),                                # (oculto; si alguien enseña los ocultos, que no tape nada)
}
