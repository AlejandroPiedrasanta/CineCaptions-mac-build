# CineCaptions · By Cinema Productions
# 1_codigo/guion_referencia.py — los 15 bloques de REFERENCIA.mp4 medidos a mano (tiempos, palabras, pesos, estilos y sitios): la «verdad» contra la que se prueba el planificador.
"""
guion_referencia.py  (v5.9)
---------------------------
Lo que se ve en REFERENCIA.mp4, bloque a bloque, medido cuadro a cuadro (30 fps, 2160×3840, 24 s):

  * tiempos en segundos (cuándo entra cada palabra y cuándo se va la pila entera),
  * 'S' = línea pequeña de varios tramos ('L' fina, 'B' negrita), centrada en cx (fracción del ancho) a la altura y (fracción desde arriba),
  * 'M' = palabra grande, con la variante (estilo) del pack «Referencia»: 1 Impacto cian, 2 Editorial rosa, 3 Amro Highlight naranja,
    4 Moderno blanco, 5 Editorial azul, 6 Amro Fire, 7 Amro Strike rojo, 8 Amro Underline lima.

Sirve para dos cosas: (1) generar EXACTAMENTE esa referencia con el pack (cues_de_la_referencia) y comparar el render con el video real, y
(2) medir qué tan parecido sale el planificador automático (guion_planificador.py) a lo que hizo la referencia.
"""
import guion_captions as G

BLOQUES = [
    {'t0': 0.2, 't1': 1.40, 'estilo': 1, 'lineas': [
        ('M', [('EMPEZAMOS', 0.2)], 0.500, 0.688, 0.83),
        ('S', [('Tempranito', 'L', 0.6), ('con el', 'B', 0.85)], 0.475, 0.745, 0.635)]},
    {'t0': 1.55, 't1': 2.55, 'estilo': 2, 'lineas': [
        ('M', [('Maquillaje', 1.55)], 0.510, 0.557, 0.685),
        ('S', [('de la', 'L', 1.75), ('novia', 'B', 2.2)], 0.470, 0.640, 0.407)]},
    {'t0': 2.8, 't1': 4.25, 'estilo': 2, 'lineas': [
        ('S', [('que por', 'L', 2.8), ('cierto', 'B', 3.0), ('quedó', 'L', 3.2)], 0.526, 0.640, 0.756),
        ('M', [('Guapísima', 3.35)], 0.500, 0.563, 0.717)]},
    {'t0': 4.4, 't1': 5.55, 'estilo': 4, 'lineas': [
        ('S', [('La ceremonia', 'L', 4.4)], 0.287, 0.640, 0.48),
        ('M', [('preciosa', 5.0)], 0.602, 0.662, 0.315)]},
    {'t0': 5.8, 't1': 7.70, 'estilo': None, 'lineas': [
        ('S', [('Pero en la', 'L', 5.8)], 0.260, 0.599, 0.333),
        ('M', [('Fiesta', 6.2, 3)], 0.410, 0.661, None, 1.0),
        ('S', [('se desató el', 'L', 6.4)], 0.495, 0.724, 0.417),
        ('M', [('SHOW', 6.8, 2)], 0.510, 0.563, 0.463)]},
    {'t0': 8.55, 't1': 9.95, 'estilo': 5, 'lineas': [
        ('S', [('Verdaderos', 'L', 8.55), ('dueños', 'B', 9.2), ('de la', 'L', 9.4)], 0.490, 0.278, 0.847),
        ('M', [('Pista', 9.6)], 0.506, 0.362, 0.387)]},
    {'t0': 10.0, 't1': 11.40, 'estilo': 5, 'lineas': [
        ('S', [('no', 'L', 10.0), ('fueron', 'B', 10.4), ('los', 'L', 10.6)], 0.430, 0.278, 0.44),
        ('M', [('Novios', 10.8)], 0.460, 0.348, 0.525)]},
    {'t0': 11.6, 't1': 12.90, 'estilo': 5, 'lineas': [
        ('S', [('Fueron', 'L', 11.6), ('estas', 'B', 11.8), ('niñas', 'L', 12.0)], 0.430, 0.505, 0.64),
        ('M', [('Adueñándose', 12.4)], 0.460, 0.575, 0.853)]},
    {'t0': 13.2, 't1': 14.50, 'estilo': 6, 'lineas': [
        ('S', [('De la', 'L', 13.2), ('máquina', 'B', 13.4), ('de', 'L', 13.6)], 0.460, 0.510, 0.635),
        ('M', [('Humo', 13.8)], 0.490, 0.594, 0.675)]},
    {'t0': 14.7, 't1': 15.45, 'estilo': None, 'lineas': [
        ('S', [('jajaja se', 'L', 14.7), ('pasaron', 'B', 14.8)], 0.430, 0.510, 0.585)]},
    {'t0': 15.6, 't1': 16.75, 'estilo': None, 'lineas': [
        ('S', [('me', 'L', 15.6), ('hicieron', 'B', 15.8), ('el día', 'L', 16.0)], 0.475, 0.510, 0.61)]},
    {'t0': 17.0, 't1': 17.75, 'estilo': None, 'lineas': [
        ('S', [('a ver', 'B', 17.0)], 0.446, 0.510, 0.1675)]},
    {'t0': 18.0, 't1': 20.10, 'estilo': 7, 'lineas': [
        ('S', [('Seamos', 'L', 18.0), ('sinceros', 'B', 18.2), ('tú', 'L', 18.8)], 0.420, 0.512, 0.655),
        ('M', [('llevarías', 19.0)], 0.475, 0.592, 0.68),
        ('S', [('niños a tu', 'L', 19.2), ('boda', 'B', 19.6)], 0.420, 0.635, 0.5175)]},
    {'t0': 20.2, 't1': 22.20, 'estilo': 8, 'lineas': [
        ('S', [('Prefieres', 'L', 20.2), ('fiesta', 'B', 20.6), ('tranquila', 'L', 20.8), ('sin', 'L', 21.0)], 0.496, 0.510, 0.818),
        ('M', [('Berrinches', 21.2)], 0.500, 0.573, 0.80)]},
    {'t0': 22.35, 't1': 23.93, 'estilo': 5, 'lineas': [
        ('S', [('Te leo', 'L', 22.35), ('en los', 'B', 22.6)], 0.310, 0.515, 0.375),
        ('M', [('Comentarios', 22.8)], 0.500, 0.570, 0.775)]},
]


# lo que transcribe la voz de REFERENCIA.mp4 (palabra, inicio, fin): la entrada con la que se prueba el planificador
PALABRAS = [
    ('Empezamos', 0.00, 0.64), ('tempranito', 0.64, 1.12), ('con', 1.20, 1.28), ('el', 1.36, 1.44),
    ('maquillaje', 1.44, 1.92), ('de', 1.92, 2.00), ('la', 2.00, 2.08), ('novia,', 2.08, 2.40),
    ('que', 2.64, 2.72), ('por', 2.80, 2.96), ('cierto', 2.96, 3.28), ('quedó', 3.36, 3.52),
    ('guapísimo.', 3.60, 4.00), ('La', 4.32, 4.40), ('ceremonia', 4.40, 4.88), ('preciosa,', 4.88, 5.36),
    ('pero', 5.60, 5.84), ('en', 5.84, 5.92), ('la', 5.92, 6.00), ('fiesta', 6.00, 6.40),
    ('se', 6.40, 6.56), ('desató', 6.56, 6.88), ('el', 6.88, 6.96), ('show.', 7.04, 7.20),
    ('Los', 8.32, 8.48), ('verdaderos', 8.48, 8.96), ('dueños', 9.04, 9.36), ('de', 9.36, 9.44),
    ('la', 9.44, 9.60), ('pista', 9.60, 9.92), ('no', 10.16, 10.32), ('fueron', 10.32, 10.64),
    ('los', 10.64, 10.80), ('novios,', 10.80, 11.20), ('fueron', 11.44, 11.68), ('estas', 11.68, 12.00),
    ('niñas', 12.00, 12.40), ('adueñándose', 12.40, 13.04), ('de', 13.04, 13.12), ('la', 13.12, 13.20),
    ('máquina', 13.20, 13.52), ('de', 13.52, 13.60), ('humo.', 13.60, 13.84), ('Se', 14.80, 14.88),
    ('pasaron,', 14.88, 15.28), ('me', 15.52, 15.68), ('hicieron', 15.68, 16.00), ('el', 16.00, 16.08),
    ('día.', 16.16, 16.48), ('A', 17.36, 17.36), ('ver,', 17.36, 17.68), ('seamos', 17.76, 18.08),
    ('sinceros,', 18.08, 18.48), ('¿tú', 18.64, 18.80), ('llevarías', 18.80, 19.20), ('niños', 19.20, 19.44),
    ('a', 19.44, 19.52), ('tu', 19.52, 19.60), ('boda', 19.60, 19.84), ('o', 20.08, 20.08),
    ('prefieres', 20.08, 20.48), ('fiesta', 20.48, 20.72), ('tranquila', 20.72, 21.20), ('sin', 21.20, 21.36),
    ('barriches?', 21.36, 21.84), ('Te', 22.16, 22.24), ('leo', 22.24, 22.56), ('en', 22.56, 22.56),
    ('los', 22.56, 22.72), ('comentarios.', 22.72, 23.44),
]


def palabras_de_la_referencia():
    """Las palabras de la referencia como las entrega la voz: [{'word', 'start', 'end'}]."""
    return [{'word': w, 'start': a, 'end': b} for w, a, b in PALABRAS]


def cues_de_la_referencia(ancho_tl=1080):
    """Los 15 bloques listos para place_guion_track."""
    return G.construir_cues(BLOQUES, 'Referencia', ancho_tl)
