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
# v5.54 «B · Premium» (la propuesta que eligió el usuario para los 6 temas): la grande lleva un REFLEJO claro en lo alto de la letra y un brillo de su
# color alrededor; la pegatina, un degradado de su color (más clara arriba, más honda abajo). El pack y la vista leen estas mismas funciones.
REFLEJO = (0.86, 0.55)           # el degradado de siempre hasta el 86 % de la letra y, arriba del todo, su color de arriba un 55 % hacia el blanco
BRILLO_HEROE = (0.42, 30)        # (opacidad, difuminado en px de Text+) del brillo del color de la grande


def con_reflejo(paradas):
    """Las paradas de un degradado de grande con el reflejo de arriba."""
    hasta, k = REFLEJO
    arriba = paradas[-1][1]
    return [(round(p * hasta, 4), c) for p, c in paradas] + [(1.0, tuple(round(v + (1.0 - v) * k, 4) for v in arriba))]


def color_medio(paradas):
    """El color del degradado más cercano a la mitad de la letra (el del brillo)."""
    return min(paradas, key=lambda pc: abs(pc[0] - 0.5))[1]


def cinta_degradado(caja):
    """(clara, honda) de una pegatina: arriba su color un 40 % hacia el blanco; abajo un poco más hondo y cálido (un blanco baja a gris frío)."""
    clara = tuple(round(v + (1.0 - v) * 0.4, 4) for v in caja)
    if max(caja) - min(caja) < 0.08:
        honda = (round(caja[0] * 0.9, 4), round(caja[1] * 0.9, 4), round(caja[2] * 0.93, 4))
    else:
        honda = (round(caja[0] * 0.95, 4), round(caja[1] * 0.88, 4), round(caja[2] * 0.85, 4))
    return clara, honda


ANILLO = {'lima': LIMA, 'magenta': MAGENTA, 'naranja': (1.0, 0.45, 0.15), 'amarillo': (1.0, 0.92, 0.10), 'rosa': (0.95, 0.30, 0.65)}
LINEA = {'lima': LIMA, 'magenta': MAGENTA, 'amarillo': (1.0, 0.90, 0.05)}

# los trazos a mano (círculo, lazo, subrayado) del kit: medidas a 1080 px de ancho
TRAZO_NOMINAL = (0.42, 0.16)     # tamaño del círculo a zoom 1 (× ANCHO del cuadro las dos medidas: así zx/zy dan los píxeles justos)
TRAZO_GROSOR = 0.0065            # grosor del trazo (× ancho) ≈ 7 px
SUBRAYADO_NOMINAL = 0.34         # ancho del subrayado a zoom 1 (× ancho)


ASPECTOS_TRAZO = (0.20, 0.25, 0.30, 0.36, 0.42, 0.50, 0.60, 0.72, 0.86, 1.0)   # v5.45: alto/ancho de las variantes del círculo y el lazo
TRAZO_VARIANTE_ANCHO = 0.84      # v5.45: ancho de esas variantes a zoom 1 (× ancho): el tamaño real de un aro, así el zoom queda cerca de 1 y el trazo en ~7 px


def puntos_circulo(lazo=False, n=64, aspecto=None):
    """La elipse dibujada a mano del kit (motor.js: 1,1 vueltas, radio que ondula un 3,5 % y un giro de −4° o −8° el lazo), en fracciones del ANCHO, centro
    (0, 0), y hacia ABAJO. Empieza arriba a la izquierda y se pasa un poco de la vuelta, como un trazo de rotulador.
    v5.45: con `aspecto` (alto/ancho) la elipse ya tiene su forma y su tamaño real (TRAZO_VARIANTE_ANCHO): se escala por igual y el trazo no se deforma
    (estirada con ZoomX ≠ ZoomY salía gruesa a los lados y fina arriba y abajo)."""
    import math
    rx, ry = TRAZO_NOMINAL[0] / 2.0, TRAZO_NOMINAL[1] / 2.0
    if aspecto:
        rx = TRAZO_VARIANTE_ANCHO / 2.0
        ry = rx * float(aspecto)
    giro = math.radians(-8.0 if lazo else -4.0)
    pts = []
    for k in range(n + 1):
        a = -1.9 + k / n * math.pi * 2 * 1.1
        f = 1 + 0.035 * math.sin(3 * a + 0.7)
        x, y = rx * f * math.cos(a), ry * f * math.sin(a)
        pts.append((x * math.cos(giro) - y * math.sin(giro), x * math.sin(giro) + y * math.cos(giro)))
    return pts


SUBRAYADO_ANCHOS = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)   # v5.47: anchos (× ancho del cuadro) de las variantes del subrayado («k line trazo lima 60»)
SUBRAYADO_GROSOR = 12.0 / 1080.0  # v5.47: la pincelada es más gruesa que el aro (12 px a 1080)


def puntos_subrayado(n=40, ancho=None):
    """v5.47 (el usuario eligió la «pincelada con remate»): casi plana, sube al final y vuelve con un golpe corto, para un ancho `ancho` (× ANCHO del cuadro;
    por defecto SUBRAYADO_NOMINAL), en fracciones del ANCHO, centro (0, 0) e y hacia ABAJO. Antes: la curva del kit (M x0−14,y1+4 Q medio,y1+36 x1+26,y1−8)
    estirada en x, fina, muy curva y lejos de la palabra."""
    w = float(ancho or SUBRAYADO_NOMINAL)
    px = 1.0 / 1080.0
    p0, c1, c2, p3 = (-w / 2 - 10 * px, 10 * px), (-w / 4, 22 * px), (w / 4, 16 * px), (w / 2 + 18 * px, -6 * px)     # el barrido
    q1, q2 = (w / 2 + 34 * px, -16 * px), (w / 2 - 30 * px, 2 * px)                                                    # el remate
    pts = []
    m = max(8, int(n * 0.8))
    for k in range(m + 1):
        t = k / m
        pts.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, c1, c2, p3)))
    r = max(4, n - m)
    for k in range(1, r + 1):
        t = k / r
        pts.append(tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(p3, q1, q2)))
    return pts
