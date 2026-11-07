# CineCaptions · By Cinema Productions
# 1_codigo/zona_segura.py — la zona que la interfaz de TikTok / Reels / Shorts deja libre en un video vertical (v5.76): ningún caption sale de ella.
"""
zona_segura.py  (v5.76)
-----------------------
Pedido (2026-11-06): «APLICA ZONA SEGURA PARA TODOS LOS ESTILOS Y AL CREAR ESTILO, PARA QUE CUANDO SE CREE RESPETE ESAS ZONAS» (con la captura de un
reel). En un 9:16 la interfaz del reel tapa arriba la barra de estado y la de búsqueda, a la derecha la columna de iconos (me gusta, comentar,
guardar, compartir) y abajo el nombre, la descripción, la música y la barra de comentarios. El usuario eligió la propuesta A: la zona CENTRADA,
13 % libre arriba, 25 % abajo y 16 % a cada lado (simétrica: los captions siguen centrados, como el Estilo 2, que va siempre en el centro).
«NO TIENES QUE MOSTRAR LA ZONA SEGURA, ES SOLO REFERENCIA PARA VOS Y LOS ESTILOS»: no se dibuja en ninguna pantalla.

Cada planificador la usa con SU forma de encajar (la que ya tenía para el borde del cuadro): el ancho máximo de una línea o de la pila pasa a ser
ANCHO (achica la línea o la parte, como antes con el borde) y la caja del bloque entero queda entre ARRIBA y ABAJO. La Edición PRO tampoco
saca un caption de ella cuando lo mueve (la regla de la cara, «detrás de ti», las escenas, el Tema 1 neón).
Solo en vertical: en un horizontal esas apps no ponen su interfaz encima y cada estilo sigue como antes.
Los emojis del tema que coloca el script de Resolve (CineCaptions.py y su gemelo CineCaptions_Subtitulos.lua) repiten estos números a mano
(x ≤ 0,84; y entre 0,37 y −0,25 desde el centro): si cambia la zona, cambiarlos allí también.

    vertical(ancho, alto)                    -> ¿se aplica? (alto > ancho)
    ancho(defecto, ancho_tl, alto_tl)        -> el ancho máximo (fracción) de un estilo, sin pasar de ANCHO en vertical
    ancho_tinta(defecto, ...)                -> lo mismo, descontando lo que sobresale su dibujo (AIRE_TINTA): Estilos 1 y 2
    limites_y(ancho_tl, alto_tl, defecto)    -> (arriba, abajo) que puede ocupar un bloque (fracción del alto, desde arriba)
    limites_x(ancho_tl, alto_tl, defecto)    -> (izquierda, derecha)
    meter_y(arriba, abajo, ...)              -> cuánto mover (fracción del alto, + = abajo) la caja para que quede dentro
    encaje(x0, y0, x1, y1, ...)              -> (s, origen, destino): escala y centro nuevos para meter una caja en la zona (achica, nunca agranda)
    mover_punto(x, y, t)                     -> un punto de la caja tras el encaje
    dentro(caja, ...)                        -> ¿la caja [arriba, abajo] o [x0, y0, x1, y1] ya está dentro? (para las pruebas)
"""

IZQ, DER = 0.16, 0.84          # la columna de iconos tapa ~14-16 % del ancho a la derecha; la zona es simétrica (los captions van centrados)
ARRIBA, ABAJO = 0.13, 0.75     # la barra de estado y la de búsqueda (~12-13 %); el nombre, la descripción, la música y los comentarios (~22-25 %)
ANCHO = DER - IZQ
ALTO = ABAJO - ARRIBA
CENTRO_X, CENTRO_Y = (IZQ + DER) / 2.0, (ARRIBA + ABAJO) / 2.0
AIRE_TINTA = 0.02              # lo que el dibujo de la grande del Estilo 1 (degradado) y del Estilo 2 (barrido del Luxe, cursiva, línea fina) sobresale, a cada lado,
                               # de lo que miden sus planificadores (fracción del ancho; medido con render_temas sobre palabras reales)


def vertical(ancho_tl=1080, alto_tl=1920):
    try:
        return float(alto_tl) > float(ancho_tl)
    except (TypeError, ValueError):
        return True


def ancho(defecto, ancho_tl=1080, alto_tl=1920):
    """El ancho máximo (fracción del ancho del cuadro) que puede ocupar una línea o un bloque: el del estilo, sin pasar de la zona en vertical."""
    return min(float(defecto), ANCHO) if vertical(ancho_tl, alto_tl) else float(defecto)


def ancho_tinta(defecto, ancho_tl=1080, alto_tl=1920):
    """Como ancho(), descontando AIRE_TINTA a cada lado: para los estilos cuyo dibujo sobresale de lo que miden."""
    return min(float(defecto), ANCHO - 2.0 * AIRE_TINTA) if vertical(ancho_tl, alto_tl) else float(defecto)


def limites_y(ancho_tl=1080, alto_tl=1920, defecto=(0.0, 1.0)):
    """(arriba, abajo): lo que puede ocupar un bloque (fracción del alto, desde arriba); en vertical, nunca fuera de la zona."""
    a, b = float(defecto[0]), float(defecto[1])
    return (max(a, ARRIBA), min(b, ABAJO)) if vertical(ancho_tl, alto_tl) else (a, b)


def limites_x(ancho_tl=1080, alto_tl=1920, defecto=(0.0, 1.0)):
    """(izquierda, derecha): lo que puede ocupar un bloque (fracción del ancho); en vertical, nunca fuera de la zona."""
    a, b = float(defecto[0]), float(defecto[1])
    return (max(a, IZQ), min(b, DER)) if vertical(ancho_tl, alto_tl) else (a, b)


def meter_y(arriba, abajo, ancho_tl=1080, alto_tl=1920, defecto=(0.0, 1.0)):
    """Cuánto mover (fracción del alto, + = abajo) la caja [arriba, abajo] para que quede dentro de los límites (0 si ya cabe). Una caja más alta
    que la zona queda centrada en ella (el que la arma la achica antes: encaje)."""
    lo, hi = limites_y(ancho_tl, alto_tl, defecto)
    arriba, abajo = float(arriba), float(abajo)
    if abajo - arriba > hi - lo:
        return (lo + hi) / 2.0 - (arriba + abajo) / 2.0
    if arriba < lo:
        return lo - arriba
    if abajo > hi:
        return hi - abajo
    return 0.0


def encaje(x0, y0, x1, y1, ancho_tl=1080, alto_tl=1920, defecto_x=(0.0, 1.0), defecto_y=(0.0, 1.0)):
    """La caja de un bloque entero (fracciones: x del ancho, y del alto, desde arriba) -> (s, (ox, oy), (nx, ny)): se achica s (≤ 1, la misma en x
    y en y, en píxeles) alrededor de su centro (ox, oy) hasta caber en los límites y su centro pasa a (nx, ny) (lo justo para quedar dentro; centrada
    en x si no cabía de ancho). Un punto p del bloque va a destino + (p − origen) · s (mover_punto). s = 1 y destino = origen si ya cabía."""
    lx0, lx1 = limites_x(ancho_tl, alto_tl, defecto_x)
    ly0, ly1 = limites_y(ancho_tl, alto_tl, defecto_y)
    x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
    w, h = max(1e-6, x1 - x0), max(1e-6, y1 - y0)
    s = min(1.0, (lx1 - lx0) / w, (ly1 - ly0) / h)
    ox, oy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, h = w * s, h * s
    nx = min(max(ox, lx0 + w / 2.0), lx1 - w / 2.0)
    ny = min(max(oy, ly0 + h / 2.0), ly1 - h / 2.0)
    return s, (ox, oy), (nx, ny)


def mover_punto(x, y, t):
    """(x, y) de un punto del bloque tras el encaje `t` = (s, origen, destino)."""
    s, (ox, oy), (nx, ny) = t
    return nx + (float(x) - ox) * s, ny + (float(y) - oy) * s


def sin_cambio(t, tol=1e-4):
    s, (ox, oy), (nx, ny) = t
    return abs(s - 1.0) < tol and abs(nx - ox) < tol and abs(ny - oy) < tol


def dentro(caja, ancho_tl=1080, alto_tl=1920, tol=0.004):
    """¿La caja [arriba, abajo] (2 valores) o [x0, y0, x1, y1] (4) está dentro de la zona? (en horizontal, siempre)."""
    if not vertical(ancho_tl, alto_tl) or not caja:
        return True
    if len(caja) == 2:
        return ARRIBA - tol <= float(caja[0]) and float(caja[1]) <= ABAJO + tol
    x0, y0, x1, y1 = (float(v) for v in caja)
    return IZQ - tol <= x0 and x1 <= DER + tol and ARRIBA - tol <= y0 and y1 <= ABAJO + tol
