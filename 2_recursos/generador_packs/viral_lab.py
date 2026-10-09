# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/viral_lab.py — laboratorio del estilo «VIRAL»: comps de PRUEBA para ver en Resolve qué admite Fusion (herramienta de desarrollo, no va en el pack).
"""
Cada función devuelve el texto de UNA comp. `pack_viral.py --lab` las mete como clips «v lab …» en el pack para colocarlas con probar_viral.py lab.
Qué se quiere saber:
  fuentes    ¿cómo se ve una negrita cursiva: Montserrat ExtraBold Italic, Inter + Shear del elemento, Inter «ExtraBold Italic» del sistema?
  escribir   Write On (Start/End) con expresión y el largo del texto (string.len)
  punteado   contorno de letra punteado (LineStyle) y caja punteada (borde)
  flecha     flecha poligonal (PolylineMask)
Valores medidos en Resolve 21.1.1: ElementShape 0 relleno · 1 contorno · 2 relleno del borde · 3 contorno del borde; LineStyle 0 sólido · 1 guion · 2 punto;
Type 0 sólido · 1 imagen · 2 degradado; Level 0 texto · 1 línea · 2 palabra · 3 carácter; JoinStyle 0 biselado · 1 redondo.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import kinetic_comps as K
from kinetic_comps import enlace, herramienta, media_out, n, texto_plus


def _fusion(nombre, items):
    """Une varios Text+ (ya escritos) con Merge en cadena y cierra con MediaOut1."""
    t = ''.join(x for x, _ in items)
    prev = items[0][1]
    for k, (_, nom) in enumerate(items[1:], 1):
        t += herramienta('Merge', f'M{k}', 140, 40 + 80 * k, [enlace('Background', prev), enlace('Foreground', nom)])
        prev = f'M{k}'
    t += media_out(prev)
    return K.armar_comp(t, f'CineCaptions VIRAL - {nombre}')


def _shear(num, v):
    return [f'ShearX{num} = Input {{ Value = Number {{ Value = {n(v)} }}, }},']


def comp_fuentes():
    filas = [
        ('Template', 'Montserrat', 'ExtraBold Italic', 0.86, []),
        ('T1', 'Inter 28pt', 'ExtraBold', 0.74, _shear(1, -0.22)),
        ('T2', 'Inter', 'ExtraBold Italic', 0.62, []),
        ('T3', 'Inter 28pt', 'ExtraBold', 0.50, []),
        ('T4', 'Inter 18pt', 'Medium', 0.38, []),
        ('T5', 'Inter 28pt', 'Black', 0.26, []),
        ('T6', 'Inter', 'Black Italic', 0.14, []),
    ]
    items = []
    for nombre, fam, est, y, extra in filas:
        items.append((texto_plus(nombre, -220, 40 + 80 * len(items), 'Bakery Shatter', fam, est, 0.17, centro=(0.5, y), extra=extra or None), nombre))
    return _fusion('lab fuentes', items)


def comp_escribir():
    """Write On con expresión y largo del texto."""
    expr_end = 'math.min(1, math.max(0, (time - 2) / (string.len(Template.StyledText) * 1.5)))'
    t = texto_plus('Template', -220, 40, 'Select', 'Inter 28pt', 'Black', 0.25, centro=(0.5, 0.7), extra=[f'End = Input {{ Value = 1, Expression = "{K.lua(expr_end)}", }},'])
    t += texto_plus('Fijo', -220, 120, 'Select', 'Inter 28pt', 'Black', 0.25, centro=(0.5, 0.4), extra=['End = Input { Value = 0.5, },'])
    t += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Fijo')])
    t += media_out('M1')
    return K.armar_comp(t, 'CineCaptions VIRAL - lab escribir')


def comp_punteado():
    """Contorno de letra punteado (LineStyle) y caja punteada (borde)."""
    dash = ['Enabled1 = Input { Value = 0, },', 'Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', 'Thickness2 = Input { Value = Number { Value = 0.012 }, },',
            'LineStyle2 = Input { Value = Number { Value = 1 }, },', 'Red2 = Input { Value = Number { Value = 1 }, },', 'Green2 = Input { Value = Number { Value = 0.2 }, },',
            'Blue2 = Input { Value = Number { Value = 0.2 }, },']
    t = texto_plus('Template', -220, 40, 'Drag', 'Inter 28pt', 'Black', 0.25, centro=(0.5, 0.7), extra=dash)
    caja = ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 3, },', 'Thickness2 = Input { Value = Number { Value = 0.02 }, },',
            'LineStyle2 = Input { Value = Number { Value = 1 }, },', 'Level2 = Input { Value = Number { Value = 0 }, },', 'ExtendHorizontal2 = Input { Value = Number { Value = 0.15 }, },',
            'ExtendVertical2 = Input { Value = Number { Value = 0.25 }, },', 'Red2 = Input { Value = Number { Value = 1 }, },', 'Green2 = Input { Value = Number { Value = 0.0 }, },',
            'Blue2 = Input { Value = Number { Value = 0.0 }, },']
    t += texto_plus('Caja', -220, 120, 'Caja', 'Inter 28pt', 'Black', 0.2, centro=(0.5, 0.4), extra=caja)
    t += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Caja')])
    t += media_out('M1')
    return K.armar_comp(t, 'CineCaptions VIRAL - lab punteado')


def poligono(nombre, puntos, x=-220, y=280):
    """Una PolylineMask cerrada de lados rectos. `puntos` = [(x, y)] con el centro del cuadro en (0, 0) y y hacia ARRIBA."""
    pts = ',\n'.join(f'\t\t\t\t\t\t{{ Linear = true, X = {n(px)}, Y = {n(py)} }}' for px, py in puntos)
    return f'''\t\t{nombre} = PolylineMask {{
\t\t\tDrawMode = "InsertAndModify",
\t\t\tInputs = {{
\t\t\t\tFilter = Input {{ Value = FuID {{ "Fast Gaussian" }}, }},
\t\t\t\tMaskWidth = Input {{ Value = {K.ANCHO}, }},
\t\t\t\tMaskHeight = Input {{ Value = {K.ALTO}, }},
\t\t\t\tPixelAspect = Input {{ Value = {{ 1, 1 }}, }},
\t\t\t\tUseFrameFormatSettings = Input {{ Value = 1, }},
\t\t\t\tClippingMode = Input {{ Value = FuID {{ "None" }}, }},
\t\t\t\tPolyline = Input {{ SourceOp = "{nombre}Polyline", Source = "Value", }},
\t\t\t}},
\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},
\t\t}},
\t\t{nombre}Polyline = PolylineStroke {{
\t\t\tInputs = {{
\t\t\t\tPoints = Input {{
\t\t\t\t\tValue = Polyline {{
\t\t\t\t\t\tClosed = true,
\t\t\t\t\t\tPoints = {{
{pts}
\t\t\t\t\t\t}},
\t\t\t\t\t}},
\t\t\t\t}},
\t\t\t}},
\t\t}},
'''


def comp_flecha():
    """Flecha poligonal (PolylineMask) rellena de blanco."""
    t = texto_plus('Template', -220, 40, 'Flecha', 'Inter 28pt', 'Black', 0.2, centro=(0.5, 0.7))
    t += poligono('Flecha', [(-0.05, -0.08), (-0.05, 0.10), (0.0, 0.055), (0.035, 0.12), (0.06, 0.105), (0.025, 0.04), (0.085, 0.035)])
    t += K._fondo('Cursor', -60, 280, (1, 1, 1), 'Flecha')
    t += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Cursor')])
    t += media_out('M1')
    return K.armar_comp(t, 'CineCaptions VIRAL - lab flecha')


def comp_prueba(nombre, extra_template=None, extra_nodos='', salida='Template', texto='Test'):
    """Una comp mínima de un Text+ «Template» (con `extra_template` en sus entradas) y, opcionalmente, nodos extra ya escritos; `salida` = el nodo que va a MediaOut."""
    t = texto_plus('Template', -220, 40, texto, 'Inter 28pt', 'Black', 0.25, centro=(0.5, 0.5), extra=extra_template)
    t += extra_nodos
    t += media_out(salida)
    return K.armar_comp(t, f'CineCaptions VIRAL - {nombre}')


def _flecha_nodos(pts, extra_mascara=''):
    nodos = poligono('Flecha', pts)
    nodos += K._fondo('Cursor', -60, 280, (1, 1, 1), 'Flecha')
    nodos += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Cursor')])
    return nodos


FLECHA = [(-0.05, -0.08), (-0.05, 0.10), (0.0, 0.055), (0.035, 0.12), (0.06, 0.105), (0.025, 0.04), (0.085, 0.035)]


def poligono_variante(nombre, puntos, v, x=-220, y=280):
    """Variantes de la sintaxis de PolylineMask para averiguar cuál acepta Resolve."""
    T = '\t\t\t\t\t\t'
    if v == 1:      # con manijas a cero
        pts = ',\n'.join(f'{T}{{ Linear = true, X = {n(px)}, Y = {n(py)}, LX = 0, LY = 0, RX = 0, RY = 0 }}' for px, py in puntos)
    elif v == 2:    # sin Linear
        pts = ',\n'.join(f'{T}{{ X = {n(px)}, Y = {n(py)}, LX = 0, LY = 0, RX = 0, RY = 0 }}' for px, py in puntos)
    else:
        pts = ',\n'.join(f'{T}{{ Linear = true, X = {n(px)}, Y = {n(py)} }}' for px, py in puntos)
    cierre = 'Closed = true,\n' + T if v != 4 else ''
    if v == 3:
        entradas = ''
    else:
        entradas = (f'\t\t\t\tFilter = Input {{ Value = FuID {{ "Fast Gaussian" }}, }},\n\t\t\t\tMaskWidth = Input {{ Value = {K.ANCHO}, }},\n\t\t\t\tMaskHeight = Input {{ Value = {K.ALTO}, }},\n'
                    f'\t\t\t\tPixelAspect = Input {{ Value = {{ 1, 1 }}, }},\n\t\t\t\tClippingMode = Input {{ Value = FuID {{ "None" }}, }},\n')
    return (f'\t\t{nombre} = PolylineMask {{\n\t\t\tDrawMode = "InsertAndModify",\n\t\t\tInputs = {{\n{entradas}'
            f'\t\t\t\tPolyline = Input {{ SourceOp = "{nombre}Polyline", Source = "Value", }},\n\t\t\t}},\n\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n'
            f'\t\t{nombre}Polyline = PolylineStroke {{\n\t\t\tInputs = {{\n\t\t\t\tPoints = Input {{\n\t\t\t\t\tValue = Polyline {{\n{T}{cierre}Points = {{\n{pts}\n{T}}},\n\t\t\t\t\t}},\n\t\t\t\t}},\n\t\t\t}},\n\t\t}},\n')


def _flecha_v(v):
    nodos = poligono_variante('Flecha', FLECHA, v)
    nodos += K._fondo('Cursor', -60, 280, (1, 1, 1), 'Flecha')
    nodos += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Cursor')])
    return nodos


def _poli(puntos, color=(1, 1, 1)):
    import viral_comps as V
    nodos = V.poligono('Flecha', puntos)
    nodos += K._fondo('Cursor', -60, 280, color, 'Flecha')
    nodos += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Cursor')])
    return nodos


def todos():
    # typewriter: el largo del texto se estima por el ancho de un Text+ «Medida» (sin Write On) dividido por el ancho medio de una letra
    ancho_cuadro = '(comp:GetPrefs("Comp.FrameFormat.Width") or 1080)'
    dw = 'Medida.Output.DataWindow'
    letras = f'(({dw} and (({dw}[3] - {dw}[1]) / {ancho_cuadro}) or 0.2) / (Template.Size * 0.5926 * 0.62))'
    exp_end = f'math.min(1, math.max(0, (time - 2) / (3 + 1.5 * {letras})))'
    medida = texto_plus('Medida', -220, 120, 'Test', 'Inter 28pt', 'Black', 0.25, centro=(0.5, 0.5), expr={'Size': 'Template.Size'})
    medida = medida.replace('StyledText = Input { Value = "Test", },', 'StyledText = Input { Value = "Test", Expression = "Template.StyledText", },')
    cuadrado = [(-0.25, -0.25), (0.25, -0.25), (0.25, 0.25), (-0.25, 0.25)]
    return {
        'v lab e4': comp_prueba('e4', [f'End = Input {{ Value = 1, Expression = "{K.lua(exp_end)}", }},'], medida),
        'v lab g1': comp_prueba('g1', None, _poli(FLECHA), 'M1'),
        'v lab g2': comp_prueba('g2', None, _poli(cuadrado, (1, 0.3, 0.3)), 'M1'),
    }
