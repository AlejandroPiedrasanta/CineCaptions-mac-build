# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/kinetic_comps.py — escribe las comps de Fusion (.comp) de los elementos del estilo «Kinetic» (héroe, serie, cinta, anillo, subrayado…).
"""
Cada elemento del estilo «Kinetic» (los títulos de gancho de la referencia: palabra gigante condensada, línea pequeña, acento en serif cursiva,
cinta de color, anillo, subrayado) es un clip del pack con su propia comp: un Text+ llamado «Template» (el que recibe el texto) más lo que lo
decora (caja pegada al texto, sombra, brillo) y una entrada animada. Todo se escribe con los nombres de entrada REALES de Resolve (copiados de
comps que guardó el propio Resolve: ver leer_comp.py).

Este módulo solo escribe texto de comp; kinetic_pack.py lo mete en un .drb.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

ANCHO, ALTO = 1080, 1920
FIN = 124           # los Text+ no se apagan a los 4 s: el clip lo recorta Resolve


def n(v):
    return f'{v:.6g}'


def lua(texto):
    """Una expresión entre comillas dentro del .comp."""
    return texto.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def punto(x, y):
    return f'Point {{ X = {n(x)}, Y = {n(y)} }}'


def entrada(valor, expr=None):
    """Input { Value = ..., Expression = "..." }"""
    if expr:
        return f'Input {{ Value = {valor}, Expression = "{lua(expr)}", }}'
    return f'Input {{ Value = {valor}, }}'


def degradado(paradas):
    """Gradient { Colors = { [pos] = { r, g, b, a } } } — paradas [(pos, (r, g, b))]."""
    cuerpo = ', '.join(f'[{n(p)}] = {{ {n(c[0])}, {n(c[1])}, {n(c[2])}, 1 }}' for p, c in paradas)
    return f'Gradient {{ Colors = {{ {cuerpo} }} }}'


def herramienta(tipo, nombre, x, y, entradas, extra=''):
    """Una herramienta de Fusion. entradas: líneas «Nombre = Input {...},»."""
    cuerpo = '\n\t\t\t\t'.join(entradas)
    return (f'\t\t{nombre} = {tipo} {{\n\t\t\tCtrlWZoom = false,\n{extra}\t\t\tInputs = {{\n\t\t\t\t{cuerpo}\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n')


def enlace(nombre, op, fuente='Output'):
    return f'{nombre} = Input {{ SourceOp = "{op}", Source = "{fuente}", }},'


def texto_plus(nombre, x, y, texto, fuente, estilo, tam, color=(1, 1, 1), centro=(0.5, 0.5), esp=1.0, extra=None, expr=None):
    """Un Text+. `extra` = líneas Input adicionales (elementos de sombreado 2..8, degradados…); `expr` {'Center': '...', 'Size': '...'} expresiones."""
    expr = expr or {}
    lineas = [
        f'GlobalOut = Input {{ Value = {FIN}, }},',
        f'Width = Input {{ Value = {ANCHO}, }},',
        f'Height = Input {{ Value = {ALTO}, }},',
        'UseFrameFormatSettings = Input { Value = 1, },',
        'Wrap = Input { Value = 0, },',
        f'Center = Input {{ Value = {{ {n(centro[0])}, {n(centro[1])} }}' + (f', Expression = "{lua(expr["Center"])}"' if 'Center' in expr else '') + ', },',
        f'CharacterSpacing = Input {{ Value = {n(esp)}, }},',
        f'Red1 = Input {{ Value = {n(color[0])}, }},',
        f'Green1 = Input {{ Value = {n(color[1])}, }},',
        f'Blue1 = Input {{ Value = {n(color[2])}, }},',
        f'StyledText = Input {{ Value = "{texto}", }},',
        f'Font = Input {{ Value = "{fuente}", }},',
        f'Style = Input {{ Value = "{estilo}", }},',
        f'Size = Input {{ Value = {n(tam)}' + (f', Expression = "{lua(expr["Size"])}"' if 'Size' in expr else '') + ', },',
        'VerticalJustificationNew = Input { Value = 3, },',
        'HorizontalJustificationNew = Input { Value = 3, }',
    ]
    if extra:
        lineas[-1] += ','
        lineas += list(extra)
        lineas[-1] = lineas[-1].rstrip(',')
    cuerpo = '\n\t\t\t\t'.join(lineas)
    return (f'\t\t{nombre} = TextPlus {{\n\t\t\tCtrlWZoom = false,\n\t\t\tInputs = {{\n\t\t\t\t{cuerpo}\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t\tVersion = 1\n\t\t}},\n')


def media_out(origen, x=1120, y=160):
    return (f'\t\tMediaOut1 = MediaOut {{\n\t\t\tInputs = {{\n\t\t\t\tIndex = Input {{ Value = "0", }},\n'
            f'\t\t\t\tInput = Input {{ SourceOp = "{origen}", Source = "Output", }}\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}}\n')


def armar_comp(herramientas, id_plantilla, fin=FIN):
    """La comp completa (cabecera + Tools + pie) con las herramientas ya escritas (la última debe ser MediaOut1)."""
    cabecera = f'''Composition {{
	CurrentTime = 0,
	RenderRange = {{ 0, {fin} }},
	GlobalRange = {{ 0, {fin} }},
	CurrentID = 40,
	HiQ = true,
	PlaybackUpdateMode = 0,
	StereoMode = false,
	Version = "DaVinci Resolve Studio 21.1.1.0010",
	SavedOutputs = 1,
	HeldTools = 0,
	DisabledTools = 0,
	LockedTools = 0,
	AudioOffset = 0,
	Resumable = true,
	OutputClips = {{
	}},
	CustomData = {{
		TEMPLATE_ID = "{id_plantilla}"
	}},
	Tools = {{
'''
    pie = '''	},
	Frames = {
	},
	Prefs = {
		Comp = {
			Interactive = {
				Proxy = {
					Scale = 1,
				},
			},
			Views = {
				View1 = {
				},
			},
			Paths = {
				Map = {
				},
			},
			FrameFormat = {
				Width = %d,
				Height = %d,
				GuideRatio = 1.77777777777778,
				DepthFull = 3,
				DepthPreview = 3,
				DepthInteractive = 3,
			},
			Unsorted = {
				GlobalEnd = %d
			},
			SpellCheck = {
			},
		}
	},
}''' % (ANCHO, ALTO, fin)
    return cabecera + herramientas + pie


# ------------------------------------------------------------------------------------------------------------------ laboratorio
def comp_laboratorio():
    """Una comp de PRUEBA para ver en Resolve qué hace cada cosa que el estilo necesita:
       · «Template»: un Text+ con 8 elementos de sombreado, cada uno con una forma distinta (ElementShape 0..7) y su color, desplazados en vertical;
       · «Grad»: un Text+ con relleno degradado (Type1 = 2 + ShadingGradient1);
       · «Fin»: un Text+ cuyo tamaño depende de comp.RenderEnd (¿se puede animar la salida desde el final del clip?)."""
    colores = [(1, 0.2, 0.2), (1, 0.6, 0.1), (1, 1, 0.1), (0.3, 1, 0.3), (0.2, 0.9, 1), (0.3, 0.4, 1), (0.8, 0.3, 1), (1, 0.4, 0.8)]
    extra = []
    for k in range(8):
        e = k + 1
        r, g, b = colores[k]
        extra += [
            f'Enabled{e} = Input {{ Value = 1, }},',
            f'ElementShape{e} = Input {{ Value = Number {{ Value = {k} }}, }},',
            f'Red{e} = Input {{ Value = Number {{ Value = {n(r)} }}, }},',
            f'Green{e} = Input {{ Value = Number {{ Value = {n(g)} }}, }},',
            f'Blue{e} = Input {{ Value = Number {{ Value = {n(b)} }}, }},',
            f'Offset{e} = Input {{ Value = {punto(0, (k - 3.5) * 0.085)}, }},',
            f'ExtendHorizontal{e} = Input {{ Value = Number {{ Value = 0.2 }}, }},',
            f'ExtendVertical{e} = Input {{ Value = Number {{ Value = 0.12 }}, }},',
            f'Round{e} = Input {{ Value = Number {{ Value = 0.15 }}, }},',
            f'Thickness{e} = Input {{ Value = Number {{ Value = 0.05 }}, }},',
        ]
    t = ''
    t += texto_plus('Template', -220, 40, 'BOX', 'Owners Narrow', 'Black', 0.05, color=(0, 0, 0), centro=(0.5, 0.62), extra=extra)
    grad = degradado([(0, (0.26, 0.26, 0.27)), (0.35, (0.91, 0.91, 0.93)), (0.5, (1, 1, 1))])
    t += texto_plus('Grad', -220, 120, 'GRAD', 'Owners Narrow', 'Black', 0.13, centro=(0.5, 0.25),
                    extra=['Type1 = Input { Value = 2, },', f'ShadingGradient1 = Input {{ Value = {grad}, }},'])
    t += texto_plus('Fin', -220, 200, 'FIN', 'Owners Narrow', 'Black', 0.1, color=(1, 1, 0), centro=(0.5, 0.42),
                    expr={'Size': '0.1 * math.min(1, math.max(0, (comp.RenderEnd - time) / 12))'})
    t += herramienta('Merge', 'M1', 140, 40, [enlace('Background', 'Template'), enlace('Foreground', 'Grad')])
    t += herramienta('Merge', 'M2', 300, 40, [enlace('Background', 'M1'), enlace('Foreground', 'Fin')])
    t += media_out('M2')
    return armar_comp(t, 'CineCaptions Kinetic - laboratorio')


def comp_laboratorio_formas():
    """Ocho Text+ «BOX» en columna: en cada uno el elemento 2 (amarillo) tiene la forma k (ElementShape 0..7) bajo el texto negro (elemento 1)."""
    t = ''
    nombres = []
    for k in range(8):
        nombre = 'Template' if k == 0 else f'T{k}'
        nombres.append(nombre)
        extra = [
            'Enabled2 = Input { Value = 1, },',
            f'ElementShape2 = Input {{ Value = Number {{ Value = {k} }}, }},',
            'Red2 = Input { Value = Number { Value = 1 }, },',
            'Green2 = Input { Value = Number { Value = 0.85 }, },',
            'Blue2 = Input { Value = Number { Value = 0.05 }, },',
            'ExtendHorizontal2 = Input { Value = Number { Value = 0.25 }, },',
            'ExtendVertical2 = Input { Value = Number { Value = 0.15 }, },',
            'Round2 = Input { Value = Number { Value = 0.3 }, },',
            'Thickness2 = Input { Value = Number { Value = 0.06 }, },',
        ]
        t += texto_plus(nombre, -220, 40 + 80 * k, 'BOX', 'Owners Narrow', 'Black', 0.07, color=(0, 0, 0), centro=(0.5, 0.92 - 0.115 * k), extra=extra)
    prev = 'Template'
    for k in range(1, 8):
        t += herramienta('Merge', f'M{k}', 140, 40 + 80 * k, [enlace('Background', prev), enlace('Foreground', f'T{k}')])
        prev = f'M{k}'
    t += media_out(prev)
    return armar_comp(t, 'CineCaptions Kinetic - laboratorio formas')


def _mascara(tipo, nombre, x, y, entradas):
    return herramienta(tipo, nombre, x, y, [
        'Filter = Input { Value = FuID { "Fast Gaussian" }, },',
        f'MaskWidth = Input {{ Value = {ANCHO}, }},', f'MaskHeight = Input {{ Value = {ALTO}, }},',
        'PixelAspect = Input { Value = { 1, 1 }, },', 'UseFrameFormatSettings = Input { Value = 1, },',
        'ClippingMode = Input { Value = FuID { "None" }, },'] + list(entradas), extra='\t\t\tCtrlWShown = false,\n')


def _fondo(nombre, x, y, color, mascara):
    return herramienta('Background', nombre, x, y, [
        f'Width = Input {{ Value = {ANCHO}, }},', f'Height = Input {{ Value = {ALTO}, }},', 'UseFrameFormatSettings = Input { Value = 1, },',
        f'TopLeftRed = Input {{ Value = {n(color[0])}, }},', f'TopLeftGreen = Input {{ Value = {n(color[1])}, }},',
        f'TopLeftBlue = Input {{ Value = {n(color[2])}, }},', 'TopLeftAlpha = Input { Value = 1, },',
        f'EffectMask = Input {{ SourceOp = "{mascara}", Source = "Mask", }},'])


def comp_laboratorio_figuras():
    """Un anillo (EllipseMask sin relleno), una cinta rectangular girada (RectangleMask con Angle) y un texto girado con Transform."""
    t = ''
    t += _mascara('EllipseMask', 'Ell1', -220, 40, ['Center = Input { Value = { 0.5, 0.75 }, },', 'Width = Input { Value = 0.5, },', 'Height = Input { Value = 0.18, },',
                                                    'Solid = Input { Value = 0, },', 'BorderWidth = Input { Value = 0.012, },'])
    t += _fondo('Anillo', -60, 40, (1, 0.5, 0.1), 'Ell1')
    t += _mascara('RectangleMask', 'Rec1', -220, 120, ['Center = Input { Value = { 0.5, 0.55 }, },', 'Width = Input { Value = 0.5, },', 'Height = Input { Value = 0.06, },',
                                                      'Angle = Input { Value = 6, },', 'CornerRadius = Input { Value = 0.0, },'])
    t += _fondo('Cinta', -60, 120, (1, 0.85, 0.05), 'Rec1')
    t += _mascara('EllipseMask', 'Ell2', -220, 200, ['Center = Input { Value = { 0.5, 0.35 }, },', 'Width = Input { Value = 0.2, },', 'Height = Input { Value = 0.2, },',
                                                    'Solid = Input { Value = 1, },'])
    t += _fondo('Disco', -60, 200, (0.9, 0.2, 0.7), 'Ell2')
    t += texto_plus('Template', -220, 280, 'GIRO', 'Owners Narrow', 'Black', 0.1, centro=(0.5, 0.2))
    t += herramienta('Transform', 'Gira', -60, 280, [enlace('Input', 'Template'), 'Angle = Input { Value = 8, },', 'Size = Input { Value = 1, },'])
    t += herramienta('Merge', 'A1', 140, 40, [enlace('Background', 'Anillo'), enlace('Foreground', 'Cinta')])
    t += herramienta('Merge', 'A2', 300, 40, [enlace('Background', 'A1'), enlace('Foreground', 'Disco')])
    t += herramienta('Merge', 'A3', 460, 40, [enlace('Background', 'A2'), enlace('Foreground', 'Gira')])
    t += media_out('A3')
    return armar_comp(t, 'CineCaptions Kinetic - laboratorio figuras')


if __name__ == '__main__':
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, 'kinetic_lab.comp')
    with open(destino, 'w', encoding='utf-8') as f:
        f.write(comp_laboratorio())
    print(destino)
