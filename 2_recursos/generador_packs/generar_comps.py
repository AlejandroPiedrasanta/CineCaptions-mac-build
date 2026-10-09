# CineCaptions - By Cinema Productions
# 4_diseno/packs_nuevos/generar_comps.py — escribe las comps de Fusion (.comp) de los packs «Viral Superior» y «Viral Inferior».
"""
Genera, por rol y por combinacion, la comp de Fusion de cada clip del pack. NO depende de ninguna plantilla de terceros.

Cada clip es un Text+ que recibe el texto como siempre (el script de CineCaptions rellena el PRIMER TextPlus: «Template»),
pero lo que se VE lo dibujan otros dos Text+ derivados por expresion:

    Template (recibe el texto)  ->  W1 = primera palabra (peso 1)   +   W2 = el resto (peso 2)

Asi, en una linea de dos palabras la primera va en peso ligero y la segunda en bold (pedido), sin que el programa tenga que
partir nada. Dos Text+ «de medir» (M1, M2) calculan el ancho de cada palabra para centrarlas juntas, con un hueco corto.
Despues: sombra suave, entrada con rebote (sube + escala + aparece) y ajuste automatico si el grupo no cabe a lo ancho.

Los parametros de cada combinacion estan en PACKS; para otra, se cambia ahi y se vuelve a generar.
"""
import json
import os
import sys

ANCHO, ALTO = 1080, 1920
MAYUS_ACENTOS = (('á', 'Á'), ('é', 'É'), ('í', 'Í'), ('ó', 'Ó'), ('ú', 'Ú'), ('ñ', 'Ñ'), ('ü', 'Ü'))
SALIDA_GLOBAL = 124        # los Text+ no se apagan a los 4 s: un bloque largo sigue a la vista
HUECO = 0.030               # hueco entre las dos palabras, en fracciones del ancho

# colores (r, g, b) 0..1
BLANCO = (1.0, 1.0, 1.0)
CREMA = (0.98, 0.95, 0.88)
ORO = (1.0, 0.80, 0.22)
CIAN = (0.35, 0.92, 1.0)
ROSA = (1.0, 0.36, 0.62)

# Una combinacion = tres roles. Cada rol: fuente/estilo de la palabra 1 y de la 2 (si hay dos), tamaño (fraccion del alto),
# espaciado de caracteres, mayusculas, color, y la entrada (retardo en fotogramas).
# 'y' es la posicion del CENTRO de cada linea, relativa al centro del grupo (se coloca mas abajo segun el pack).
COMBINACIONES = {
    1: {  # IMPACTO: principal Black gigante, arriba ligera, abajo bold (como el ejemplo)
        'nombre': 'Impacto',
        'context': dict(f1=('Inter 18pt', 'Light'), f2=('Montserrat', 'Bold'), tam=0.128, esp=1.02, mayus=True, color=BLANCO, retardo=0),
        'main': dict(f1=('Montserrat', 'Black'), f2=('Montserrat', 'Black'), tam=0.192, esp=0.985, mayus=True, color=BLANCO, retardo=2),
        'complement': dict(f1=('Inter 18pt', 'Light'), f2=('Montserrat', 'Bold'), tam=0.128, esp=1.02, mayus=True, color=BLANCO, retardo=4),
        'entrada': 'pop',
        'luxe': True,      # la palabra principal usa el macro Luxe Shine
    },
    2: {  # ORO: principal en dorado, el resto limpio
        'nombre': 'Oro',
        'context': dict(f1=('Inter 18pt', 'Light'), f2=('Montserrat', 'SemiBold'), tam=0.122, esp=1.03, mayus=True, color=BLANCO, retardo=0),
        'main': dict(f1=('Montserrat', 'ExtraBold'), f2=('Montserrat', 'ExtraBold'), tam=0.198, esp=0.99, mayus=True, color=ORO, retardo=2),
        'complement': dict(f1=('Inter 18pt', 'Light'), f2=('Montserrat', 'SemiBold'), tam=0.122, esp=1.03, mayus=True, color=BLANCO, retardo=4),
        'entrada': 'sube',
        'luxe': True,      # la palabra principal usa el macro Luxe Shine
    },
    3: {  # EDITORIAL: serif cursiva grande + sans pequeña con mucho aire entre letras
        'nombre': 'Editorial',
        'context': dict(f1=('Poppins', 'Regular'), f2=('Poppins', 'Bold'), tam=0.096, esp=1.20, mayus=True, color=CREMA, retardo=0),
        'main': dict(f1=('DM Serif Text', 'Italic'), f2=('DM Serif Text', 'Italic'), tam=0.262, esp=0.99, mayus=False, color=CREMA, retardo=3),
        'complement': dict(f1=('Poppins', 'Regular'), f2=('Poppins', 'Bold'), tam=0.096, esp=1.20, mayus=True, color=CREMA, retardo=6),
        'entrada': 'abre',
        'luxe': True,      # la palabra principal usa el macro Luxe Shine
    },
    4: {  # NEON: principal cian, el resto en blanco
        'nombre': 'Neon',
        'context': dict(f1=('Inter 18pt', 'Light'), f2=('Montserrat', 'Bold'), tam=0.124, esp=1.02, mayus=True, color=BLANCO, retardo=0),
        'main': dict(f1=('Montserrat', 'Black'), f2=('Montserrat', 'Black'), tam=0.19, esp=0.985, mayus=True, color=CIAN, retardo=2),
        'complement': dict(f1=('Inter 18pt', 'Light'), f2=('Montserrat', 'Bold'), tam=0.124, esp=1.02, mayus=True, color=BLANCO, retardo=4),
        'entrada': 'sube',
        'luxe': True,      # la palabra principal usa el macro Luxe Shine
    },
    5: {  # ROSA: principal rosa, el resto en crema
        'nombre': 'Rosa',
        'context': dict(f1=('Poppins', 'Regular'), f2=('Poppins', 'Bold'), tam=0.118, esp=1.04, mayus=True, color=CREMA, retardo=0),
        'main': dict(f1=('Montserrat', 'ExtraBold'), f2=('Montserrat', 'ExtraBold'), tam=0.2, esp=0.99, mayus=True, color=ROSA, retardo=2),
        'complement': dict(f1=('Poppins', 'Regular'), f2=('Poppins', 'Bold'), tam=0.118, esp=1.04, mayus=True, color=CREMA, retardo=4),
        'entrada': 'pop',
        'luxe': True,      # la palabra principal usa el macro Luxe Shine
    },
}

# centro del grupo (y normalizado, 1 = arriba) por pack. «Superior»: tercio de arriba; «Inferior»: tercio de abajo.
PACKS = {
    'superior': {'nombre': 'Viral Superior', 'y_grupo': 0.800},
    'inferior': {'nombre': 'Viral Inferior', 'y_grupo': 0.255},
    'guia': {'nombre': 'Crea tu estilo', 'y_grupo': 0.800},
}
ROLES = ('context', 'main', 'complement')
NOMBRE_ROL = {'context': 'contexto', 'main': 'principal', 'complement': 'complemento', 'base': 'base'}


def _n(v):
    return f'{v:.6g}'


def _lua(texto):
    """Escapa una expresion para ponerla entre comillas dentro del .comp."""
    return texto.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def _texto_plus(nombre, x, y, estilo, texto_expr=None, valor='Texto', centro=None, color=(1, 1, 1), tam=0.05, esp=1.0,
                pos=(0, 0), visible=True, opacidad_expr=None):
    familia, peso = estilo
    entradas = [
        f'GlobalOut = Input {{ Value = {SALIDA_GLOBAL}, }},',
        f'Width = Input {{ Value = {ANCHO}, }},',
        f'Height = Input {{ Value = {ALTO}, }},',
        'UseFrameFormatSettings = Input { Value = 1, },',
        'Wrap = Input { Value = 0, },',
    ]
    if centro:
        entradas.append(f'Center = Input {{ Value = {{ {_n(centro[0])}, {_n(centro[1])} }}, Expression = "{_lua(centro[2])}", }},' if len(centro) > 2
                        else f'Center = Input {{ Value = {{ {_n(centro[0])}, {_n(centro[1])} }}, }},')
    entradas += [
        f'CharacterSpacing = Input {{ Value = {_n(esp)}, }},',
        f'Red1 = Input {{ Value = {_n(color[0])}, }},',
        f'Green1 = Input {{ Value = {_n(color[1])}, }},',
        f'Blue1 = Input {{ Value = {_n(color[2])}, }},',
    ]
    if opacidad_expr:
        entradas.append(f'Opacity1 = Input {{ Value = 1, Expression = "{_lua(opacidad_expr)}", }},')
    if texto_expr:
        entradas.append(f'StyledText = Input {{ Value = "", Expression = "{_lua(texto_expr)}", }},')
    else:
        entradas.append(f'StyledText = Input {{ Value = "{valor}", }},')
    entradas += [
        f'Font = Input {{ Value = "{familia}", }},',
        f'Style = Input {{ Value = "{peso}", }},',
        f'Size = Input {{ Value = {_n(tam)}, }},',
        'VerticalJustificationNew = Input { Value = 3, },',
        'HorizontalJustificationNew = Input { Value = 3, }',
    ]
    cuerpo = '\n\t\t\t\t'.join(entradas)
    return (f'\t\t{nombre} = TextPlus {{\n\t\t\tCtrlWZoom = false,\n\t\t\tInputs = {{\n\t\t\t\t{cuerpo}\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t\tVersion = 1\n\t\t}},\n')


def _herramienta(tipo, nombre, x, y, entradas):
    cuerpo = '\n\t\t\t\t'.join(entradas)
    return (f'\t\t{nombre} = {tipo} {{\n\t\t\tCtrlWZoom = false,\n\t\t\tInputs = {{\n\t\t\t\t{cuerpo}\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n')


def _enlace(nombre, op):
    return f'{nombre} = Input {{ SourceOp = "{op}", Source = "Output", }},'


def comp_de_clip(pack, combinacion, rol, y_rel, texto='Texto de ejemplo', salida='Entrada', centros_fijos=False, tilt_plantilla=0.0):
    """El texto del .comp de UN clip. rol: 'context' | 'main' | 'complement' | 'base'."""
    c = COMBINACIONES[combinacion]
    r = c['main' if rol == 'base' else rol]
    y = PACKS[pack]['y_grupo'] + y_rel - tilt_plantilla     # el .drb ya mueve cada clip (Tilt): se compensa aqui
    t1, t2 = r['f1'], r['f2']
    mayus = r['mayus']
    f_up = 'string.upper' if mayus else ''

    def palabra(n):
        """Primera palabra (n=1) o el resto (n=2) del texto que recibe «Template». Solo expresiones de una linea:
        el motor de Fusion exige tostring() sobre el texto y no admite concatenar con .."""
        base = 'tostring(Template.StyledText.Value)'
        if mayus:
            base = '(' + base + ':upper()' + ''.join(f':gsub("{a}","{b}")' for a, b in MAYUS_ACENTOS) + ')'
        patron = '^%s*(%S+)' if n == 1 else '^%s*%S+%s+(.*)$'
        return f'({base}:match("{patron}") or "")'

    # ancho en fracciones del ancho de cada palabra (de los Text+ «de medir», que no se mueven: sin dependencia circular)
    def ancho(m):
        return (f'(({m}.Output.DataWindow and tostring({m}.StyledText.Value) ~= "") and ({m}.Output.DataWindow[3]-{m}.Output.DataWindow[1])/{ANCHO} or 0)')

    w1, w2 = ancho('M1'), ancho('M2')
    total = f'({w1} + (({w2}) > 0 and {HUECO} or 0) + {w2})'
    centro1 = f'Point(0.5 - {total}/2 + {w1}/2, {_n(y)})'
    centro2 = f'Point(0.5 + {total}/2 - {w2}/2, {_n(y)})'

    d = r['retardo']
    t = f'math.min(1, math.max(0, (time - {d}) / 9))'
    e = f'(1 + 2.70158*(({t})-1)^3 + 1.70158*(({t})-1)^2)'
    entrada = c['entrada']
    if entrada == 'pop':
        tam_expr = f'(0.72 + 0.28*{e})'
        despl = '0'
    elif entrada == 'sube':
        tam_expr = f'(0.94 + 0.06*{e})'
        despl = f'(1 - {e})*(-0.035)'
    else:  # abre: aparece con el espaciado cerrado y se abre
        tam_expr = f'(0.96 + 0.04*{e})'
        despl = f'(1 - {e})*(-0.012)'
    ajuste = f'math.min(1, 0.86/math.max(0.0001, {total}))'      # si el grupo no cabe, se reduce
    fade = f'math.min(1, math.max(0, (time - {d}) / 6))'

    tools = ''
    tools += _texto_plus('Template', -220, 40, t2, valor=texto, centro=(0.5, y), color=r['color'], tam=r['tam'], esp=r['esp'])
    tools += _texto_plus('M1', -220, 120, t1, texto_expr=palabra(1), centro=(0.5, 0.5), color=r['color'], tam=r['tam'], esp=r['esp'])
    tools += _texto_plus('M2', -220, 200, t2, texto_expr=palabra(2), centro=(0.5, 0.5), color=r['color'], tam=r['tam'], esp=r['esp'])
    tools += _texto_plus('W1', -20, 120, t1, texto_expr=palabra(1), centro=((0.5, y) if centros_fijos else (0.5, y, centro1)), color=r['color'], tam=r['tam'], esp=r['esp'], opacidad_expr=fade)
    tools += _texto_plus('W2', -20, 200, t2, texto_expr=palabra(2), centro=((0.5, y) if centros_fijos else (0.5, y, centro2)), color=r['color'], tam=r['tam'], esp=r['esp'], opacidad_expr=fade)
    tools += _herramienta('Merge', 'Juntas', 140, 160, [_enlace('Background', 'W1'), _enlace('Foreground', 'W2')])
    tools += _herramienta('BrightnessContrast', 'Negro', 300, 240, [_enlace('Input', 'Juntas'), 'Gain = Input { Value = 0, },', 'Alpha = Input { Value = 1, },'])
    tools += _herramienta('Blur', 'Difumina', 440, 240, [_enlace('Input', 'Negro'), 'XBlurSize = Input { Value = 7, },', 'Filter = Input { Value = FuID { "Gaussian" }, },'])
    tools += _herramienta('Transform', 'Baja', 580, 240, [_enlace('Input', 'Difumina'), 'Center = Input { Value = { 0.5, 0.495 }, },'])
    tools += _herramienta('Merge', 'ConSombra', 700, 160, [_enlace('Background', 'Baja'), _enlace('Foreground', 'Juntas'), 'Blend = Input { Value = 1, },'])
    tools += _herramienta('Transform', 'Entrada', 840, 160, [
        _enlace('Input', 'ConSombra'),
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + {_lua(despl)})", }},',
        f'Size = Input {{ Value = 1, Expression = "{_lua(f"({tam_expr}) * {ajuste}")}", }},',
        f'Pivot = Input {{ Value = {{ 0.5, {_n(y)} }}, }},',
    ])
    tools += (f'\t\tMediaOut1 = MediaOut {{\n\t\t\tInputs = {{\n\t\t\t\tIndex = Input {{ Value = "0", }},\n'
              f'\t\t\t\tInput = Input {{ SourceOp = "{salida}", Source = "Output", }}\n\t\t\t}},\n'
              f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ 1120, 160 }} }},\n\t\t}}\n')
    cabecera = f'''Composition {{
	CurrentTime = 0,
	RenderRange = {{ 0, {SALIDA_GLOBAL} }},
	GlobalRange = {{ 0, {SALIDA_GLOBAL} }},
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
		TEMPLATE_ID = "CineCaptions {PACKS[pack]['nombre']} - {c['nombre']} - {NOMBRE_ROL[rol]}"
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
				Width = 1080,
				Height = 1920,
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
}''' % SALIDA_GLOBAL
    return cabecera + tools + pie


def y_relativa(combinacion, rol):
    """Posicion del centro de la linea respecto al centro del grupo: pegadas, como el ejemplo (arriba / principal / abajo)."""
    c = COMBINACIONES[combinacion]
    tm, tc, tb = c['main']['tam'], c['context']['tam'], c['complement']['tam']
    if rol in ('main', 'base'):
        return 0.0
    if c.get('rel'):                   # v5.8: separaciones fijas (arriba, abajo) de los ejemplos con un principal de Amro.Films Captions
        return c['rel'][0] if rol == 'context' else -c['rel'][1]
    k = 640.0 / 1920.0                 # Size de Text+ ~ 640 px por unidad en 1080x1920
    hueco = 0.010
    if rol == 'context':
        return 0.36 * k * (tm + tc) + hueco
    return -(0.36 * k * (tm + tb) + hueco)


def generar_prueba(destino, pack, comb, textos):
    """Las tres lineas de una combinacion con un texto de prueba (para ver el aspecto en Resolve)."""
    os.makedirs(destino, exist_ok=True)
    rutas = []
    for rol, texto in zip(ROLES, textos):
        ruta = os.path.join(destino, f'prueba_{pack}_{comb}_{rol}.comp')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(comp_de_clip(pack, comb, rol, y_relativa(comb, rol), texto))
        rutas.append(ruta)
    return rutas


def generar(destino, packs=('superior', 'inferior')):
    os.makedirs(destino, exist_ok=True)
    escritos = []
    for pack in packs:
        for comb in COMBINACIONES:
            for rol in ROLES + ('base',):
                nombre = f'{pack}__{comb}__{NOMBRE_ROL[rol]}.comp'
                ruta = os.path.join(destino, nombre)
                with open(ruta, 'w', encoding='utf-8') as f:
                    f.write(comp_de_clip(pack, comb, rol, y_relativa(comb, rol)))
                escritos.append(ruta)
    return escritos


if __name__ == '__main__':
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'comps')
    for r in generar(dest):
        print(r)
