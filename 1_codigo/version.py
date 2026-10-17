# CineCaptions · By Cinema Productions
# 1_codigo/version.py — la versión del programa (APP_VERSION) y el autor, en un solo sitio.
"""
version.py
----------
La version del producto, en UN solo sitio.

Por que existe
==============
Hasta la v1.0.28 no habia forma de saber que build estaba corriendo: la
ventana no la enseñaba, el diagnostico tampoco, y el script principal de
Resolve no tenia ni constante de version ni la escribia en su informe. Eso
costo una ronda entera de trabajo: se reporto como fallo algo ya arreglado,
porque ni el usuario ni yo podiamos comprobar que version se habia probado.

En Studio es peor todavia: los scripts que corren salen del bundle de la
propia app (BASE_RECURSOS/resolve_scripts), asi que un .exe viejo ejecuta
scripts viejos — y el instalador, en Studio, reporta que no hay nada
desactualizado. Sin un numero a la vista no hay manera de notarlo.

Se sube A MANO al publicar (y se anota en REGISTRO_DE_CAMBIOS.txt). Al subirla hay que subir también
las líneas VERSION = "x.y.z (...)" de 2_recursos/resolve_scripts (ver LEEME, «Compilar»).
"""

APP_VERSION = '5.5.10'
APP_NOMBRE = 'CineCaptions'
APP_AUTOR = 'Cinema Productions'
APP_CREDITO = 'CineCaptions · By Cinema Productions'
