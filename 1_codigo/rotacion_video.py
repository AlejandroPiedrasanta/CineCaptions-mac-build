# CineCaptions · By Cinema Productions
# 1_codigo/rotacion_video.py — los videos del celular vienen «acostados» con su giro guardado aparte (display matrix): Resolve lo aplica, PyAV no.
"""
rotacion_video.py
-----------------
v5.5.8 (pedido: «cada vez que sucede, la foto se voltea»): un video vertical de iPhone/Android se graba como 1920×1080 con una rotación de
-90° guardada en el archivo. Resolve lo muestra derecho; PyAV entrega los cuadros tal cual, ACOSTADOS. Lo que sacaba fotogramas del video
(la foto de la tarjeta del Tema 5, el sticker, la pantalla final, la detección de la persona y su recorte, la caja de la cara de Efectos) los
usaba de lado, y el formato del timeline salía horizontal porque se miraba `metadata['rotate']`, que el ffmpeg nuevo ya no rellena.

    cuartos(fr)               cuartos de vuelta ANTIHORARIOS (0-3) que hay que dar al cuadro para verlo como Resolve (el giro del cuadro)
    giro(ruta)                lo mismo mirando el primer cuadro del archivo (con caché por ruta, tamaño y fecha)
    derecho_nd(arr, k)        el array del cuadro ya derecho (np.rot90)
    derecho_img(img, k)       la imagen PIL ya derecha
    medidas(w, h, k)          (ancho, alto) como se ve: con 1 o 3 cuartos se intercambian
"""
import os

_CACHE = {}


def cuartos(fr):
    """Cuartos de vuelta antihorarios que lleva el cuadro de PyAV (frame.rotation es el giro de su display matrix, en grados antihorarios)."""
    try:
        return int(round(float(getattr(fr, 'rotation', 0) or 0) / 90.0)) % 4
    except (TypeError, ValueError):
        return 0


def giro(ruta):
    """cuartos() del primer cuadro de video de `ruta` (0 si no hay video o no se puede leer)."""
    try:
        st = os.stat(ruta)
        clave = (str(ruta), st.st_size, st.st_mtime)
    except OSError:
        return 0
    if clave in _CACHE:
        return _CACHE[clave]
    k = 0
    try:
        import av
        with av.open(str(ruta)) as c:
            if c.streams.video:
                fr = next(c.decode(c.streams.video[0]), None)
                k = cuartos(fr) if fr is not None else 0
    except Exception:
        k = 0
    _CACHE[clave] = k
    return k


def derecho_nd(arr, k):
    if not k:
        return arr
    import numpy as np
    return np.ascontiguousarray(np.rot90(arr, k=k))


def derecho_img(img, k):
    return img.rotate(90 * k, expand=True) if k else img          # PIL gira en sentido antihorario, como np.rot90


def medidas(w, h, k):
    return (h, w) if k % 2 else (w, h)
