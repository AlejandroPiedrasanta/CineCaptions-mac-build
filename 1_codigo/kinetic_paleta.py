# CineCaptions · By Cinema Productions
# 1_codigo/kinetic_paleta.py — v5.5.13: los colores del Tema 1 (Kinetic) en UN solo sitio: el pack (generador_packs/kinetic_elementos.py), la vista
# aproximada (kinetic_vista.py) y GO sin Resolve (render_temas.py) los leen de aquí.
"""
Tema NEÓN (pedido: «aplica el tema-neon al Tema 1», kit Escritorio/TEMA 1/graficos/tema-neon.css): lima #D6FF3B y magenta #FF2DCB, pegatinas roja, lima,
magenta y blanca, palabra manuscrita en lima o magenta, trazos a mano en lima o magenta y sombras moradas oscuras (rgba(10,5,22)).
Las paradas de un degradado van de la BASE de la letra (0) a su parte de arriba (1), como las dibuja Text+. Los colores viejos que ya no usa ninguna
receta (amarillo, cian, rosa, naranja) se quedan: hay proyectos de Resolve con esos clips.
"""


def _hex(h):
    h = h.lstrip('#')
    return tuple(round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4))


LIMA = _hex('#D6FF3B')
MAGENTA = _hex('#FF2DCB')
ROJO = _hex('#EE2B36')
TINTA = _hex('#14101E')          # el texto oscuro de las pegatinas claras
SOMBRA = _hex('#0A0516')         # la sombra de todo (morado casi negro)
BLANCO = (1.0, 1.0, 1.0)

GRADIENTES = {
    'blanco': [(0.0, _hex('#E4DEF3')), (0.65, BLANCO), (1.0, BLANCO)],
    'lima': [(0.0, _hex('#9BE81C')), (0.48, LIMA), (1.0, _hex('#F4FF72'))],
    'magenta': [(0.0, _hex('#7A2BF2')), (0.52, MAGENTA), (1.0, _hex('#FF7BE6'))],
    'amarillo': [(0.0, (1.0, 0.52, 0.08)), (0.55, (1.0, 0.84, 0.10)), (1.0, (1.0, 0.93, 0.22))],
    'rojo': [(0.0, (0.88, 0.14, 0.08)), (1.0, (1.0, 0.30, 0.20))],
    'serif': [(0.0, (0.93, 0.92, 0.97)), (0.5, BLANCO), (1.0, BLANCO)],
}
CINTA = {                                                      # (caja, texto)
    'rojo': (ROJO, BLANCO),
    'lima': (LIMA, TINTA),
    'magenta': (MAGENTA, BLANCO),
    'blanco': (BLANCO, TINTA),
    'amarillo': ((1.0, 0.90, 0.04), (0.04, 0.04, 0.05)),
}
GUION = {
    'lima': [(0.0, LIMA), (1.0, LIMA)],
    'magenta': [(0.0, MAGENTA), (1.0, MAGENTA)],
    'amarillo': [(0.0, (1.0, 0.55, 0.10)), (0.6, (1.0, 0.86, 0.12)), (1.0, (1.0, 0.93, 0.25))],
    'cian': [(0.0, (0.15, 0.62, 1.0)), (1.0, (0.35, 0.95, 1.0))],
    'rosa': [(0.0, (0.95, 0.30, 0.75)), (1.0, (1.0, 0.55, 0.85))],
}
ANILLO = {'lima': LIMA, 'magenta': MAGENTA, 'naranja': (1.0, 0.45, 0.15), 'amarillo': (1.0, 0.92, 0.10), 'rosa': (0.95, 0.30, 0.65)}
LINEA = {'lima': LIMA, 'magenta': MAGENTA, 'amarillo': (1.0, 0.90, 0.05)}

# los trazos a mano (círculo, lazo, subrayado) del kit: medidas a 1080 px de ancho
TRAZO_NOMINAL = (0.42, 0.16)     # tamaño del círculo a zoom 1 (× ANCHO del cuadro las dos medidas: así zx/zy dan los píxeles justos)
TRAZO_GROSOR = 0.0065            # grosor del trazo (× ancho) ≈ 7 px
SUBRAYADO_NOMINAL = 0.34         # ancho del subrayado a zoom 1 (× ancho)


def puntos_circulo(lazo=False, n=64):
    """La elipse dibujada a mano del kit (motor.js: 1,1 vueltas, radio que ondula un 3,5 % y un giro de −4° o −8° el lazo), en fracciones del ANCHO, centro
    (0, 0), y hacia ABAJO. Empieza arriba a la izquierda y se pasa un poco de la vuelta, como un trazo de rotulador."""
    import math
    rx, ry = TRAZO_NOMINAL[0] / 2.0, TRAZO_NOMINAL[1] / 2.0
    giro = math.radians(-8.0 if lazo else -4.0)
    pts = []
    for k in range(n + 1):
        a = -1.9 + k / n * math.pi * 2 * 1.1
        f = 1 + 0.035 * math.sin(3 * a + 0.7)
        x, y = rx * f * math.cos(a), ry * f * math.sin(a)
        pts.append((x * math.cos(giro) - y * math.sin(giro), x * math.sin(giro) + y * math.cos(giro)))
    return pts


def puntos_subrayado(n=24):
    """El subrayado curvo del kit (M x0−14,y1+4 Q medio,y1+36 x1+26,y1−8) para un ancho nominal, en fracciones del ANCHO, centro (0, 0), y hacia ABAJO."""
    w = SUBRAYADO_NOMINAL
    px = 1.0 / 1080.0
    p0, p1, p2 = (-w / 2 - 14 * px, 4 * px), (0.0, 36 * px), (w / 2 + 26 * px, -8 * px)
    pts = []
    for k in range(n + 1):
        t = k / n
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return pts
