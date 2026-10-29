# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/kinetic_elementos.py — los elementos del estilo «Kinetic»: héroe, serie, serif, guion, etiqueta, cinta, anillo y subrayado.
"""
Cada elemento es UN clip del pack (nombre «k <tipo> <variante>») con su comp de Fusion:

    héroe     palabra gigante condensada (Owners Narrow Black) con degradado y sombra: blanco metálico, lima, amarillo→naranja, magenta→violeta, rojo
    sup       línea pequeña condensada blanca («PEOPLE», «IS WON», «DON'T MAKE THEM»)
    serif     acento en serif cursiva (DM Serif Text Italic): «Captions», «ON HOOK»
    guion     acento manuscrito de pincel (Antagon): «you.», «Feel.», «No»
    etiqueta  letras pequeñas muy separadas («FOCUS», «NOT»)
    cinta     texto sobre una caja de color pegada al texto (la caja es un elemento de sombreado del propio Text+: siempre del tamaño del texto)
    cintas    lo mismo con serif cursiva
    anillo    elipse sin relleno (rodea una palabra: «NO RESULT», «ADD»)
    linea     trazo de subrayado que se dibuja de izquierda a derecha

El texto lo recibe el Text+ «Template» (get_text_plus_tool de los scripts de Resolve) y el tamaño también es una entrada de ese Text+ (Size): la app lo
fija por clip, así el texto siempre se rasteriza al tamaño final (nada de ampliar un bitmap). La posición, el giro y el zoom de los trazos son
propiedades del clip (Pan / Tilt / RotationAngle / ZoomX / ZoomY).
Entrada con rebote y salida (los 5 últimos fotogramas del clip, vía comp.RenderEnd) van dentro de cada comp.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', '..', '1_codigo'))
import kinetic_comps as K
import kinetic_paleta as PAL
from kinetic_comps import degradado, enlace, herramienta, media_out, n, punto, texto_plus

HEROE = ('Owners Narrow', 'Black')
SERIF = ('DM Serif Text', 'Italic')
GUION = ('Antagon', 'Regular')
PLUMA = ('Yellowtail', 'Regular')          # v5.5.13 (neón): la palabra escrita a mano del kit («trae a», «en vivo»)
ETIQUETA = ('Montserrat', 'ExtraBold')

# v5.5.13: los colores salen de 1_codigo/kinetic_paleta.py (tema NEÓN; la vista y GO sin Resolve leen los mismos)
GRADIENTES = PAL.GRADIENTES
COLOR_CINTA = PAL.CINTA
COLOR_GUION = PAL.GUION
COLOR_ANILLO = PAL.ANILLO
COLOR_LINEA = PAL.LINEA


# ------------------------------------------------------------------------------------------------------------------ animación
def _p(retardo, dur):
    return f'math.min(1, math.max(0, (time - {retardo}) / {dur}))'


def _rebote(p):
    """easeOutBack del progreso p (texto de una expresión de Fusion): sube de 0 a ~1,1 y se asienta en 1."""
    return f'(1 + 2.70158*(({p})-1)^3 + 1.70158*(({p})-1)^2)'


SALIDA = 'math.min(1, math.max(0, (comp.RenderEnd - time) / 5))'      # 1 durante el clip y baja a 0 en los 5 últimos fotogramas


FPS = '(comp:GetPrefs("Comp.FrameFormat.Rate") or 30)'
ASP_EXPR = '((comp:GetPrefs("Comp.FrameFormat.Width") or 1080) / (comp:GetPrefs("Comp.FrameFormat.Height") or 1920))'
EM_ALTO = f'(Template.Size * 0.592593 * {ASP_EXPR})'      # el em del Text+ (Size × 640 px a 1080 de ancho) en fracción del ALTO del cuadro


def _muelle(p, z=0.72, w=7.6):
    """spring() del kit (motor.ts) sobre el progreso p ya acotado a [0, 1]: 0 → 1 con su pequeño rebote."""
    wd = w * (1 - z * z) ** 0.5
    return f'(({p}) >= 1 and 1 or (1 - math.exp(-{n(z * w)}*({p})) * (math.cos({n(wd)}*({p})) + {n(z * w / wd)}*math.sin({n(wd)}*({p})))))'


def _sale(q):
    """sale() del kit (easeInOutCubic) sobre q ya acotado."""
    return f'(({q}) < 0.5 and 4*({q})^3 or 1 - (-2*({q})+2)^3/2)'


def _ent(retardo, seg):
    return f'math.min(1, math.max(0, (time - {retardo}) / ({n(seg)} * {FPS})))'


def _fuera(seg):
    """Progreso de la salida del kit: 0 hasta los últimos `seg` s del clip y 1 al final (todo el bloque sale a la vez: los clips acaban juntos)."""
    return f'math.min(1, math.max(0, 1 - (comp.RenderEnd - time) / ({n(seg)} * {FPS})))'


def animacion_kit(tipo, retardo=0, direccion=1, giro=0.0):
    """v5.44 — las entradas/salidas del motor del kit «TEMA 1» (motor.ts), para que los Text+ se muevan como los clips neón:
    'revela' (revela2: la línea entra por su MÁSCARA desde abajo —direccion 1— o desde arriba —−1— con muelle de 0,55 s y sale hacia arriba por la
    máscara en 0,32 s: nada se queda medio transparente), 'pega' (pegatina: cae 70 px girando 18° y se asienta; sale desvaneciéndose en 0,3 s) y
    'pluma' (la palabra a mano se escribe de izquierda a derecha en 0,5 s y sale borrándose y subiendo). Devuelve las expresiones de _cadena."""
    if tipo == 'revela':
        p, q = _ent(retardo, 0.55), _fuera(0.32)
        s = _muelle(p)
        h = f'(1.12 * {EM_ALTO})'
        return dict(size='1', dy=f'(-({direccion}) * {h} * (1 - {s}) + 1.08 * {h} * {_sale(q)})', ang=f'(-({n(giro)}) * (1 - {s}))',
                    blend=f'math.min(1, (time - {retardo}) / (0.06 * {FPS}))', mascara=f'(1.6 * {EM_ALTO})', desenfoque=True)
    if tipo == 'pega':
        p, q = _ent(retardo, 0.55), _fuera(0.30)
        s = _muelle(p, 0.62, 8)
        return dict(size='1', dy=f'(0.036458 * (1 - {s}))', ang=f'(18 * (1 - {s}))',
                    blend=f'math.min(1, math.max(0, (time - {retardo}) / (0.07 * {FPS}))) * (1 - {_sale(q)})', desenfoque=True)
    # 'pluma'
    p, q = _ent(retardo, 0.55), _fuera(0.30)
    s = _muelle(p)
    po = _sale(q)
    return dict(size='1', dy=f'(-0.008333 * (1 - {s}) + 0.036458 * {po})', ang='0',
                blend=f'math.min(1, math.max(0, (time - {retardo}) / (0.06 * {FPS}))) * (1 - ({po})^2)',
                pluma=(f'(1 - (1 - math.min(1, math.max(0, (time - {retardo}) / (0.5 * {FPS}))))^2.2)', po), desenfoque=True)


def animacion(tipo, retardo=0):
    """Expresiones (Size del Transform, desplazamiento y de la Y, Angle, Blend) de la entrada `tipo` + la salida común."""
    if tipo == 'sube':           # línea pequeña: sube un poco y aparece
        p = _p(retardo, 7)
        e = _rebote(p)
        return dict(size=f'(0.92 + 0.08*{e}) * (0.9 + 0.1*{SALIDA})', dy=f'(1 - {e}) * (-0.03)', ang='0', blend=f'math.min(1, {p} * 2.2) * {SALIDA}')
    if tipo == 'giro':           # cinta: entra girada y grande y se asienta
        p = _p(retardo, 9)
        e = _rebote(p)
        return dict(size=f'(0.6 + 0.4*{e}) * (0.9 + 0.1*{SALIDA})', dy='0', ang=f'(1 - {e}) * (-9)', blend=f'math.min(1, {p} * 3) * {SALIDA}')
    if tipo == 'abre':           # serif: aparece con calma
        p = _p(retardo, 10)
        e = _rebote(p)
        return dict(size=f'(0.88 + 0.12*{e}) * (0.92 + 0.08*{SALIDA})', dy=f'(1 - {e}) * (-0.012)', ang=f'(1 - {e}) * 3', blend=f'math.min(1, {p} * 2) * {SALIDA}')
    p = _p(retardo, 10)          # 'pop' (héroe): gran rebote
    e = _rebote(p)
    return dict(size=f'(0.38 + 0.62*{e}) * (0.86 + 0.14*{SALIDA})', dy=f'(1 - {e}) * (-0.03)', ang=f'(1 - {e}) * (-4)', blend=f'math.min(1, {p} * 2.4) * {SALIDA}')


def _vacio(x, y):
    """Un fondo transparente del tamaño del cuadro: el Merge que da la opacidad necesita un Background (sin él no saca nada)."""
    return herramienta('Background', 'Vacio', x, y, [
        f'Width = Input {{ Value = {K.ANCHO}, }},', f'Height = Input {{ Value = {K.ALTO}, }},', 'UseFrameFormatSettings = Input { Value = 1, },',
        'TopLeftRed = Input { Value = 0, },', 'TopLeftGreen = Input { Value = 0, },', 'TopLeftBlue = Input { Value = 0, },', 'TopLeftAlpha = Input { Value = 0, },'])


def _cadena(origen, anim, x0=140, y0=40, despues=None):
    """Transform (rebote) + Merge sin fondo (la opacidad) + MediaOut: lo que cierra cada comp.
    v5.47: `despues(nodo, anim)` -> (texto, nodo final) se pone DETRÁS del Transform (el relleno vivo): delante, el desenfoque de movimiento lo renderizaba
    3 veces por fotograma sin caché posible (la ronda de 33 s pasó de ~5 a ~18 min en Resolve)."""
    t = herramienta('Transform', 'Anim', x0, y0, [
        enlace('Input', origen),
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + {K.lua(anim["dy"])})", }},',
        f'Size = Input {{ Value = 1, Expression = "{K.lua(anim["size"])}", }},',
        f'Angle = Input {{ Value = 0, Expression = "{K.lua(anim["ang"])}", }},',
    ] + (['MotionBlur = Input { Value = 1, },', 'Quality = Input { Value = 3, },', 'ShutterAngle = Input { Value = 180, },']
         if anim.get('desenfoque') else []))      # v5.45: el kit se mueve con desenfoque de movimiento (KitNeon: 5 muestras; aquí 3: con 5 el render tardaba 3,6× y la reproducción en Resolve se resiente)
    t += _vacio(x0 + 160, y0 + 90)
    mascara = []
    if anim.get('mascara'):      # v5.44 (kit: cada línea entra y sale por su caja, overflow hidden): una franja fija a lo ancho, centrada en el texto
        t += K._mascara('RectangleMask', 'Caja', x0 + 160, y0 - 80, [
            'Center = Input { Value = { 0.5, 0.5 }, },', 'Width = Input { Value = 1.4, },',
            f'Height = Input {{ Value = 0.2, Expression = "{K.lua(anim["mascara"])}", }},'])
        mascara = ['EffectMask = Input { SourceOp = "Caja", Source = "Mask", },']
    elif anim.get('pluma'):      # v5.44 (kit: la palabra a mano se escribe de izquierda a derecha y se borra al salir): ventana sobre la tinta del Text+
        pw, po = anim['pluma']
        dw = 'Template.Output.DataWindow'
        ancho_cuadro = '(comp:GetPrefs("Comp.FrameFormat.Width") or ' + str(K.ANCHO) + ')'
        izq, der = f'({dw} and {dw}[1] / {ancho_cuadro} or 0.2)', f'({dw} and {dw}[3] / {ancho_cuadro} or 0.8)'
        xa = f'({izq} + (-0.15 + 1.3 * {po}) * ({der} - {izq}))'
        xb = f'({der} - (1 - {pw}) * ({der} - {izq}))'
        t += K._mascara('RectangleMask', 'Caja', x0 + 160, y0 - 80, [
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(({K.lua(xa)} + {K.lua(xb)}) / 2, 0.5)", }},',
            f'Width = Input {{ Value = 0.5, Expression = "math.max(0.0001, {K.lua(xb)} - {K.lua(xa)})", }},', 'Height = Input { Value = 1.2, },'])
        mascara = ['EffectMask = Input { SourceOp = "Caja", Source = "Mask", },']
    fin = 'Anim'
    if despues:
        extra, fin = despues('Anim', anim)
        t += extra
    t += herramienta('Merge', 'Salida', x0 + 160, y0, [
        enlace('Background', 'Vacio'),
        enlace('Foreground', fin),
        f'Blend = Input {{ Value = 1, Expression = "{K.lua(anim["blend"])}", }},',
    ] + mascara)
    t += media_out('Salida', x0 + 320, y0)
    return t


# ------------------------------------------------------------------------------------------------------------------ elementos de texto
def _sombra(num, opacidad=0.72, dy=-0.0065, blur=10, color=PAL.SOMBRA):
    """Los 8 campos de un elemento de sombreado que hace de sombra suave (morado casi negro del neón, desplazado hacia abajo)."""
    return [
        f'Enabled{num} = Input {{ Value = 1, }},',
        f'Red{num} = Input {{ Value = Number {{ Value = {n(color[0])} }}, }},',
        f'Green{num} = Input {{ Value = Number {{ Value = {n(color[1])} }}, }},',
        f'Blue{num} = Input {{ Value = Number {{ Value = {n(color[2])} }}, }},',
        f'Opacity{num} = Input {{ Value = Number {{ Value = {n(opacidad)} }}, }},',
        f'Offset{num} = Input {{ Value = {punto(0, dy)}, }},',
        f'Softness{num} = Input {{ Value = Number {{ Value = 1 }}, }},',
        f'SoftnessX{num} = Input {{ Value = Number {{ Value = {n(blur)} }}, }},',
        f'SoftnessY{num} = Input {{ Value = Number {{ Value = {n(blur)} }}, }},',
        f'SoftnessBlend{num} = Input {{ Value = Number {{ Value = 0 }}, }},',
    ]


def _contorno(num, grosor, opacidad=0.9):
    """Un elemento de sombreado que dibuja el CONTORNO oscuro de la letra (ElementShape 1 = contorno del texto): el texto pequeño blanco se lee también sobre una pared clara."""
    return [
        f'Enabled{num} = Input {{ Value = 1, }},',
        f'ElementShape{num} = Input {{ Value = 1, }},',
        f'Thickness{num} = Input {{ Value = Number {{ Value = {n(grosor)} }}, }},',
        f'Red{num} = Input {{ Value = Number {{ Value = {n(PAL.SOMBRA[0])} }}, }},',
        f'Green{num} = Input {{ Value = Number {{ Value = {n(PAL.SOMBRA[1])} }}, }},',
        f'Blue{num} = Input {{ Value = Number {{ Value = {n(PAL.SOMBRA[2])} }}, }},',
        f'Opacity{num} = Input {{ Value = Number {{ Value = {n(opacidad)} }}, }},',
    ]


def comp_texto(nombre, texto, fuente, tam, relleno, esp=1.0, entrada='pop', retardo=0, sombra=True, interlineado=None, contorno=0.0, kit=None, trama=False,
               vivo=False, premium=False):
    """Un Text+ con relleno (color liso o degradado), sombra y la entrada animada. relleno = (r,g,b) o [(pos, (r,g,b))…].
    v5.44: `kit` = las expresiones de animacion_kit (la entrada/salida del motor del kit en vez de `entrada`).
    v5.47: `vivo` = el relleno se mueve por dentro (_vivo).
    v5.54: `premium` («B · Premium», las grandes) = el degradado con el reflejo de arriba (PAL.con_reflejo) y un brillo de su color delante del halo oscuro."""
    extra = []
    color = (1, 1, 1)
    degradado_ = isinstance(relleno, (list, tuple)) and relleno and isinstance(relleno[0], (list, tuple)) and len(relleno[0]) == 2 and isinstance(relleno[0][1], (list, tuple))
    if degradado_:
        extra += ['Type1 = Input { Value = 2, },', f'ShadingGradient1 = Input {{ Value = {degradado(PAL.con_reflejo(relleno) if premium else relleno)}, }},']
    else:
        color = relleno
    def brillo(num):
        return _sombra(num, PAL.BRILLO_HEROE[0], 0.0, PAL.BRILLO_HEROE[1], color=PAL.color_medio(relleno) if degradado_ else relleno)
    # (del elemento 4 en adelante Text+ dibuja por defecto una CAJA, no la letra: ElementShape = 0. Medido en Resolve 21.1.2: sin él salía un
    # recuadro gris u oscuro detrás de la grande)
    letra4 = ['ElementShape4 = Input { Value = 0, },']
    if sombra:
        extra += _sombra(2, 0.8, -0.0065, 7)                 # sombra firme debajo de la letra…
        if contorno > 0:
            extra += _contorno(3, contorno)                  # …y, en el texto pequeño, un contorno oscuro: se lee también sobre una pared blanca
            if premium:
                extra += brillo(4) + letra4
        elif premium:
            extra += brillo(3) + _sombra(4, 0.55, -0.002, 34) + letra4      # el brillo de su color (3) delante del halo oscuro ancho (4)
        else:
            extra += _sombra(3, 0.55, -0.002, 34)            # (los héroes llevan un halo ancho)
    t = texto_plus('Template', -220, 40, texto, fuente[0], fuente[1], tam, color=color, esp=esp, extra=extra)
    despues = None
    if vivo or trama:                            # vivo = el tinte (el otro tono del degradado) que sube y baja dentro de la letra
        t += _relleno()
        despues = _vivo_despues('Relleno', vivo or None, trama)
    t += _cadena('Template', kit or animacion(entrada, retardo), despues=despues)
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


def _custom(nombre, origen, r, g, b, a, x, y):
    """Un Custom Tool con sus cuatro expresiones por píxel (fijas: v5.47, ni `time` ni NumberIn1 = time lo animaban en Resolve, medido)."""
    return (f'\t\t{nombre} = Custom {{\n\t\t\tCtrlWZoom = false,\n\t\t\tInputs = {{\n'
            f'\t\t\t\tRedExpression = Input {{ Value = "{K.lua(r)}", }},\n'
            f'\t\t\t\tGreenExpression = Input {{ Value = "{K.lua(g)}", }},\n'
            f'\t\t\t\tBlueExpression = Input {{ Value = "{K.lua(b)}", }},\n'
            f'\t\t\t\tAlphaExpression = Input {{ Value = "{K.lua(a)}", }},\n'
            f'\t\t\t\tImage1 = Input {{ SourceOp = "{origen}", Source = "Output", }},\n'
            f'\t\t\t}},\n\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n')


TINTE_BLANCO = (0.84, 0.78, 0.97)      # v5.47: el tono que se mueve dentro del héroe blanco (lavanda del degradado, un poco más vivo)


def _relleno(x=-220, y=-140):
    """v5.47: una copia del Text+ «Template» SIN sombras (texto, tamaño, fuente y espaciado enlazados por expresión): la forma justa del relleno de
    la letra. El halftone y el movimiento de color se recortan con ella (operador «In»): sin eso también teñían la sombra y el halo de la palabra."""
    t = texto_plus('Relleno', x, y, 'HERO', HEROE[0], HEROE[1], 0.30, expr={'Size': 'Template.Size'})
    # (Font y Style NO se enlazan: con esas expresiones de texto la comp entera salía negra en Resolve; el Tema 1 no cambia la tipografía)
    for campo, valor in (('StyledText', '"HERO"'), ('CharacterSpacing', '1')):
        viejo = f'{campo} = Input {{ Value = {valor}, }},'
        assert viejo in t, viejo
        t = t.replace(viejo, f'{campo} = Input {{ Value = {valor}, Expression = "Template.{campo}", }},')
    return t


def _vivo_despues(matte, tinte=None, trama=False, prefijo=''):
    """v5.47: el relleno vivo y la trama DETRÁS del Transform «Anim»: el matte (`matte`: el relleno sin sombras o la caja de la pegatina) se mueve igual
    que el texto con un Transform con las mismas expresiones de Center, Size y Angle que «Anim» (sin desenfoque de movimiento: ese es el ahorro)."""
    def poner(nodo, anim):
        mov = f'{prefijo}MatteMov'
        # (las MISMAS expresiones que «Anim», escritas otra vez: enlazarlas con «Anim.Center»/«Anim.Size»/«Anim.Angle» tumbó Resolve 21.1.1 al
        # colocar los clips, con volcado; medido el 2026-10-26)
        t = herramienta('Transform', mov, 300, -260, [
            enlace('Input', matte),
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + {K.lua(anim["dy"])})", }},',
            f'Size = Input {{ Value = 1, Expression = "{K.lua(anim["size"])}", }},',
            f'Angle = Input {{ Value = 0, Expression = "{K.lua(anim["ang"])}", }},'])
        origen = nodo
        if tinte:
            t += _vivo(f'{prefijo}Vivo', origen, mov, tinte, 380, -260)
            origen = f'{prefijo}Vivo'
        if trama:
            t += _trama(origen, mov, 380, -60)
            origen = 'ConTrama'
        return t, origen
    return poner


def _dentro(nombre, capa, matte, x, y):
    """Merge con operador «In»: `capa` solo donde está `matte` (y sin dibujar el matte)."""
    return herramienta('Merge', nombre, x, y, [enlace('Background', matte), enlace('Foreground', capa), 'Operator = Input { Value = FuID { "In" }, },'])


def _vivo(nombre, origen, matte, tinte, x=-140, y=-260):
    """v5.47 (el usuario: «que los colores sólidos tuvieran un movimiento de color sutil, no el caption sino lo que está adentro»; vista elegida): dentro
    de la letra sube y baja despacio una franja suave de `tinte` (el otro tono de su degradado: el color «se mueve») y cada 3 s la cruza un brillo
    blanco en diagonal. Las dos capas se recortan con `matte` (el relleno, no la sombra) y se ponen encima con poca opacidad: el caption ni se mueve ni
    cambia de forma. Con máscaras animadas por expresión (lo que ya anima el resto del pack): el Custom Tool con `time` no se movía en Resolve (medido)."""
    ph = f'(time / (3 * {FPS}) - math.floor(time / (3 * {FPS})))'
    t = K._mascara('RectangleMask', f'{nombre}MTinte', x, y, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + 0.045 * math.sin(time / {K.lua(FPS)} * 2.6))", }},',
        'Width = Input { Value = 3, },', 'Height = Input { Value = 0.03, },', 'SoftEdge = Input { Value = 0.035, },'])
    t += K._fondo(f'{nombre}Tinte', x + 80, y, tinte, f'{nombre}MTinte')
    t += _dentro(f'{nombre}TinteEn', f'{nombre}Tinte', matte, x + 160, y)
    t += K._mascara('RectangleMask', f'{nombre}MLuz', x, y + 60, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(-0.3 + 1.6 * {K.lua(ph)}, 0.5)", }},',
        'Width = Input { Value = 0.05, },', 'Height = Input { Value = 3, },', 'Angle = Input { Value = 18, },', 'SoftEdge = Input { Value = 0.035, },'])
    t += K._fondo(f'{nombre}Luz', x + 80, y + 60, (1.0, 1.0, 1.0), f'{nombre}MLuz')
    t += _dentro(f'{nombre}LuzEn', f'{nombre}Luz', matte, x + 160, y + 60)
    t += herramienta('Merge', f'{nombre}1', x + 240, y, [enlace('Background', origen), enlace('Foreground', f'{nombre}TinteEn'), 'Blend = Input { Value = 0.45, },'])
    t += herramienta('Merge', nombre, x + 320, y, [enlace('Background', f'{nombre}1'), enlace('Foreground', f'{nombre}LuzEn'), 'Blend = Input { Value = 0.22, },'])
    return t


def _trama(origen, matte, x=-60, y=-60):
    """v5.44 (el usuario: «faltan los halftone»): la trama del blanco del kit (.f-blanco: puntos rgba(30,14,60,.24) de ~1,6 px en una rejilla de 8 px a
    1080 de ancho) con un Custom Tool escalado con el ancho del cuadro.
    v5.47 (el usuario: «que los halftone se muevan un poco»): la rejilla (fija, sobre un lienzo del cuadro) la desliza un Transform en diagonal, despacio
    (0,35 y 0,2 px por fotograma a 1080), y se recorta con el relleno de la letra («In»: no cae en la sombra)."""
    celda = '(8 * w / 1080)'
    fx = f'(x * w - floor(x * w / {celda}) * {celda} - {celda} / 2)'
    fy = f'(y * h - floor(y * h / {celda}) * {celda} - {celda} / 2)'
    radio = '(1.65 * w / 1080)'
    punto = f'max(0, min(1, ({radio} - sqrt({fx}*{fx} + {fy}*{fy})) / (0.5 * w / 1080 + 0.0001)))'
    alfa = f'{punto} * 0.24'
    t = herramienta('Background', 'Lienzo', x - 100, y - 80, [
        f'Width = Input {{ Value = {K.ANCHO}, }},', f'Height = Input {{ Value = {K.ALTO}, }},', 'UseFrameFormatSettings = Input { Value = 1, },',
        'TopLeftAlpha = Input { Value = 1, },'])
    t += _custom('Trama', 'Lienzo', f'{alfa} * 0.1176', f'{alfa} * 0.0549', f'{alfa} * 0.2353', alfa, x, y - 80)
    t += herramienta('Transform', 'TramaMov', x + 60, y - 80, [
        enlace('Input', 'Trama'),
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + time * 0.35 / 1080, 0.5 - time * 0.2 / 1920)", }},'])
    t += _dentro('TramaEn', 'TramaMov', matte, x + 120, y - 80)
    t += herramienta('Merge', 'ConTrama', x + 100, y, [enlace('Background', origen), enlace('Foreground', 'TramaEn')])
    return t


CAP = {'Owners Narrow': 0.700, 'DM Serif Text': 0.661, 'Antagon': 0.854, 'Montserrat': 0.700, 'Yellowtail': 0.729}     # altura de las mayúsculas / em (Pillow)
ASPECTO = 1080.0 / 1920.0                                                                       # ancho/alto del cuadro vertical
EM = 640.0 / 1080.0                                                                              # el em de «Size = 1» en fracciones del ancho del cuadro


def comp_cinta(nombre, texto, fuente, tam, caja, color_texto, entrada='giro', retardo=0, esp=1.0, alto_k=1.55, pad_k=0.5, dy_k=0.03, sombra_caja=0.5, radio=0.15,
               kit=None, premium=False):
    """Texto sobre una caja de color que SE AJUSTA AL TEXTO: un RectangleMask cuyo ancho sale del DataWindow del Text+ «Template» más el relleno y cuyo alto
    sale de su Size (alto_k × la altura de las mayúsculas; pad_k × esa altura a cada lado). Así la caja sigue al texto aunque la app cambie el Size o el
    texto, y una cinta de varias palabras es UNA sola caja (la forma «caja por carácter» de Text+ dejaba un hueco en cada espacio).
    v5.54 `premium` («B · Premium»): la caja con un degradado de su color (PAL.cinta_degradado): una franja clara de borde suave en su mitad de arriba
    y una más honda en la de abajo, recortadas con la propia caja (las mismas piezas del relleno vivo: máscara, fondo, Merge «In»)."""
    cap = CAP[fuente[0]]
    em = f'(Template.Size * {n(EM)})'
    dw = 'Template.Output.DataWindow'
    # el DataWindow viene en píxeles del cuadro de la comp (1080 o 2160 de ancho…): se divide por el ancho REAL, no por 1080
    ancho_cuadro = '(comp:GetPrefs("Comp.FrameFormat.Width") or ' + str(K.ANCHO) + ')'
    ancho = f'(({dw} and (({dw}[3] - {dw}[1]) / {ancho_cuadro}) or 0.25) + 2 * {em} * {n(cap * pad_k)})'
    alto = f'({em} * {n(cap * alto_k * ASPECTO)})'          # el Height de una máscara es fracción del ALTO del cuadro (el Width, del ancho): 9/16 en vertical
    t = texto_plus('Template', -220, 40, texto, fuente[0], fuente[1], tam, color=color_texto, esp=esp)
    t += K._mascara('RectangleMask', 'Rec', -220, 120, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + {K.lua(em)} * {n(dy_k * ASPECTO)})", }},',
        f'Width = Input {{ Value = 0.3, Expression = "{K.lua(ancho)}", }},',
        f'Height = Input {{ Value = 0.05, Expression = "{K.lua(alto)}", }},',
        f'CornerRadius = Input {{ Value = {n(radio)}, }},'])                  # v5.5.13: las pegatinas del neón tienen las esquinas algo redondeadas
    t += K._fondo('Caja', -60, 120, caja, 'Rec')
    fondo_caja = 'Caja'
    if premium:
        centro = f'0.5 + {em} * {n(dy_k * ASPECTO)}'
        for k, (parte, color_parte, signo) in enumerate(zip(('Luz', 'Honda'), PAL.cinta_degradado(caja), ('+', '-'))):
            y0 = 200 + 80 * k
            t += K._mascara('RectangleMask', f'Rec{parte}', -220, y0, [
                f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, {K.lua(centro)} {signo} {K.lua(alto)} * 0.3)", }},',
                f'Width = Input {{ Value = 0.3, Expression = "{K.lua(ancho)}", }},',
                f'Height = Input {{ Value = 0.03, Expression = "{K.lua(alto)} * 0.5", }},',
                'SoftEdge = Input { Value = 0.012, },'])
            t += K._fondo(f'Caja{parte}', -60, y0, color_parte, f'Rec{parte}')
            t += _dentro(f'Caja{parte}En', f'Caja{parte}', 'Caja', 40, y0)
            t += herramienta('Merge', f'CajaCon{parte}', 120, y0, [enlace('Background', fondo_caja), enlace('Foreground', f'Caja{parte}En'),
                                                                  'Blend = Input { Value = 0.85, },'])
            fondo_caja = f'CajaCon{parte}'
    t += herramienta('Merge', 'Juntas', 40, 80, [enlace('Background', fondo_caja), enlace('Foreground', 'Template')])
    # sombra suave de toda la cinta (el mismo recurso que las comps viejas: silueta negra, difuminada y un poco más abajo)
    t += herramienta('BrightnessContrast', 'Negro', 40, 160, [enlace('Input', 'Juntas'), 'Gain = Input { Value = 0, },', f'Alpha = Input {{ Value = {n(sombra_caja)}, }},'])
    t += herramienta('Blur', 'Difumina', 40, 200, [enlace('Input', 'Negro'), 'XBlurSize = Input { Value = 6, },', 'Filter = Input { Value = FuID { "Gaussian" }, },'])
    t += herramienta('Transform', 'Baja', 40, 240, [enlace('Input', 'Difumina'), 'Center = Input { Value = { 0.5, 0.4965 }, },'])
    t += herramienta('Merge', 'ConSombra', 40, 280, [enlace('Background', 'Baja'), enlace('Foreground', 'Juntas')])
    # v5.47: el color de la pegatina se mueve por dentro (como las grandes), detrás del Transform y recortado con su caja
    t += _cadena('ConSombra', kit or animacion(entrada, retardo), despues=_vivo_despues('Caja', tuple(c + (1 - c) * 0.45 for c in caja), prefijo='Caja'))
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


# ------------------------------------------------------------------------------------------------------------------ trazos (sin texto)
def comp_anillo(nombre, color, ancho=0.42, alto=0.16, grosor=0.012, retardo=0):
    t = K._mascara('EllipseMask', 'Ell', -220, 40, ['Center = Input { Value = { 0.5, 0.5 }, },', f'Width = Input {{ Value = {n(ancho)}, }},',
                                                 f'Height = Input {{ Value = {n(alto)}, }},', 'Solid = Input { Value = 0, },',
                                                 f'BorderWidth = Input {{ Value = {n(grosor)}, }},'])
    t += texto_plus('Template', -220, 200, ' ', HEROE[0], HEROE[1], 0.05)       # sin conectar: solo para que la app reconozca el clip como suyo (busca un Text+ «Template»)
    t += K._fondo('Trazo', -60, 40, color, 'Ell')
    a = animacion('pop', retardo)
    a['size'] = a['size']
    t += _cadena('Trazo', a)
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


def comp_linea(nombre, color, ancho=0.34, alto=0.0075, retardo=0):
    """Subrayado que se dibuja de izquierda a derecha (Width y Center con expresión)."""
    p = _p(retardo, 9)
    e = _rebote(p)
    avance = f'math.min(1, {p} * 1.15)'
    t = K._mascara('RectangleMask', 'Rec', -220, 40, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 - {n(ancho)}/2 + {n(ancho)}*({avance})/2, 0.5)", }},',
        f'Width = Input {{ Value = {n(ancho)}, Expression = "{n(ancho)} * ({avance})", }},', f'Height = Input {{ Value = {n(alto * ASPECTO)}, }},',
        'CornerRadius = Input { Value = 0.5, },'])
    t += texto_plus('Template', -220, 200, ' ', HEROE[0], HEROE[1], 0.05)       # sin conectar: solo para que la app reconozca el clip como suyo (busca un Text+ «Template»)
    t += K._fondo('Trazo', -60, 40, color, 'Rec')
    t += _vacio(140, 130)
    t += herramienta('Merge', 'Salida', 140, 40, [enlace('Background', 'Vacio'), enlace('Foreground', 'Trazo'), f'Blend = Input {{ Value = 1, Expression = "{K.lua(SALIDA)}", }},'])
    t += media_out('Salida', 300, 40)
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


# v5.47: cuánto se ha BORRADO un trazo (0 → 1 entre 0,46 y 0,16 s antes del final del clip, con la curva sale() del kit)
BORRA_TRAZO = _sale(f'math.min(1, math.max(0, ((time - (comp.RenderEnd - 0.46 * {FPS})) / (0.30 * {FPS}))))')


def _polilinea_abierta(nombre, puntos, grosor, x=-220, y=40, dur=13):
    """v5.5.13 (neón) — un trazo a mano que SE DIBUJA: PolylineMask ABIERTA (la sintaxis probada de viral_comps.poligono: la Polyline sale de un
    BezierSpline) con borde y sin relleno, y su WriteOnEnd de 0 a 1 en `dur` fotogramas con frenada (kit: 0,45 s, 1 − (1 − p)^2,4).
    `puntos` = [(x, y)] en fracciones del ANCHO, centro (0, 0) e y hacia ABAJO; aquí se pasan al espacio de la máscara (Y en fracción del ALTO, hacia arriba)."""
    k = len(puntos)
    asp = K.ANCHO / float(K.ALTO)
    pm = [(px, -py * asp) for px, py in puntos]
    filas = []
    for i, (px, py) in enumerate(pm):
        ax, ay = pm[max(0, i - 1)]
        bx, by = pm[min(k - 1, i + 1)]
        filas.append(f'\t\t\t\t\t\t{{ Linear = true, X = {n(px)}, Y = {n(py)}, LX = {n((ax - px) / 3)}, LY = {n((ay - py) / 3)}, RX = {n((bx - px) / 3)}, RY = {n((by - py) / 3)} }}')
    pts = ',\n'.join(filas)
    avance = f'1 - (1 - math.min(1, math.max(0, time / (0.45 * {FPS}))))^2.4'      # (v5.45: 0,45 s como el kit a cualquier fps; antes `dur` fotogramas)
    borra = BORRA_TRAZO
    return (f'\t\t{nombre} = PolylineMask {{\n\t\t\tDrawMode = "InsertAndModify",\n\t\t\tDrawMode2 = "InsertAndModify",\n\t\t\tCtrlWShown = false,\n\t\t\tInputs = {{\n'
            f'\t\t\t\tFilter = Input {{ Value = FuID {{ "Fast Gaussian" }}, }},\n\t\t\t\tMaskWidth = Input {{ Value = {K.ANCHO}, }},\n\t\t\t\tMaskHeight = Input {{ Value = {K.ALTO}, }},\n'
            f'\t\t\t\tPixelAspect = Input {{ Value = {{ 1, 1 }}, }},\n\t\t\t\tUseFrameFormatSettings = Input {{ Value = 1, }},\n\t\t\t\tClippingMode = Input {{ Value = FuID {{ "None" }}, }},\n'
            f'\t\t\t\tSolid = Input {{ Value = 0, }},\n\t\t\t\tBorderWidth = Input {{ Value = {n(grosor)}, }},\n'
            # v5.45: Resolve 21 dibuja el trazo con WriteLength (cuánto) y WritePosition (el centro de lo escrito); WriteOnEnd ya no hace nada
            # (medido: GetInput devolvía None y el aro salía entero de golpe). WritePosition es el INICIO del tramo (con p/2 el subrayado arrancaba a
            # mitad de camino, medido en la ronda 10): inicio 0 y largo p.
            # v5.47: y al salir se DESDIBUJA desde su inicio (WritePosition avanza y el largo se acorta) antes que el texto: nunca queda un aro vacío
            f'\t\t\t\tWriteLength = Input {{ Value = 1, Expression = "math.max(0, ({K.lua(avance)}) - ({K.lua(borra)}))", }},\n'
            f'\t\t\t\tWritePosition = Input {{ Value = 0, Expression = "{K.lua(borra)}", }},\n'
            f'\t\t\t\tPolyline = Input {{ SourceOp = "{nombre}Poly", Source = "Value", }},\n\t\t\t\tPolyline2 = Input {{ Value = Polyline {{ }}, Disabled = true, }},\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n'
            f'\t\t{nombre}Poly = BezierSpline {{\n\t\t\tSplineColor = {{ Red = 160, Green = 252, Blue = 4 }},\n\t\t\tCtrlWZoom = false,\n\t\t\tNameSet = true,\n\t\t\tKeyFrames = {{\n'
            f'\t\t\t\t[0] = {{ 0, Flags = {{ Linear = true, LockedY = true }}, Value = Polyline {{\n\t\t\t\t\tClosed = false,\n\t\t\t\t\tPoints = {{\n{pts}\n\t\t\t\t\t}}\n\t\t\t\t}} }}\n'
            f'\t\t\t}}\n\t\t}},\n')


def comp_trazo(nombre, color, puntos, grosor=PAL.TRAZO_GROSOR):
    """v5.5.13 (neón) — círculo, lazo o subrayado a mano que se dibuja (kit TEMA 1: `hook()` deco). Sin rebote: el trazo aparece al dibujarse.
    v5.47 (el usuario: «sale el caption y deja el ring vacío»): se desdibuja desde su inicio entre 0,46 y 0,16 s antes del final (el texto empieza a
    salir a 0,32 s): cuando el texto va por la mitad el trazo ya no está. Con un halo suave de su color (el neón del tema; vista elegida: «aro B»)."""
    t = _polilinea_abierta('Trazo', puntos, grosor)
    t += texto_plus('Template', -220, 200, ' ', HEROE[0], HEROE[1], 0.05)       # sin conectar: solo para que la app reconozca el clip como suyo
    t += K._fondo('Tinta', -60, 40, color, 'Trazo')
    t += herramienta('Blur', 'Halo', -60, 120, [enlace('Input', 'Tinta'), 'XBlurSize = Input { Value = 9, },', 'Filter = Input { Value = FuID { "Gaussian" }, },'])
    t += herramienta('BrightnessContrast', 'HaloSuave', 40, 120, [enlace('Input', 'Halo'), 'Gain = Input { Value = 1.15, },', 'Alpha = Input { Value = 0.7, },'])
    t += herramienta('Merge', 'ConHalo', 40, 40, [enlace('Background', 'HaloSuave'), enlace('Foreground', 'Tinta')])
    t += _vacio(140, 130)
    # (con el trazo ya borrado la polilínea dejaba un punto de su remate redondo: el último tramo del borrado también apaga el clip)
    apaga = f'1 - math.max(0, ({BORRA_TRAZO}) - 0.8) / 0.2'
    t += herramienta('Merge', 'Salida', 140, 40, [enlace('Background', 'Vacio'), enlace('Foreground', 'ConHalo'),
                                                  f'Blend = Input {{ Value = 1, Expression = "{K.lua(apaga)}", }},'])
    t += media_out('Salida', 300, 40)
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


# ------------------------------------------------------------------------------------------------------------------ el catálogo
def todos():
    """{nombre del clip: texto de la comp}. Los tamaños (Size) son los de partida: la app fija el real por clip."""
    c = {}
    # v5.44: las entradas y salidas del kit (animacion_kit): grande desde arriba girada −4°, versalitas desde abajo, serif desde abajo +4°,
    # pegatinas que caen y se asientan, la palabra a mano que se escribe
    grande, chica, serif = animacion_kit('revela', direccion=-1, giro=-4), animacion_kit('revela'), animacion_kit('revela', giro=4)
    for var in ('blanco', 'lima', 'amarillo', 'magenta', 'rojo'):
        c[f'k hero {var}'] = comp_texto(f'héroe {var}', 'HERO', HEROE, 0.30, GRADIENTES[var], esp=1.0, contorno=(0.007 if var == 'blanco' else 0.0), kit=grande,
                                        trama=(var == 'blanco'), vivo=TINTE_BLANCO if var == 'blanco' else GRADIENTES[var][-1][1], premium=True)
    c['k sup'] = comp_texto('sup', 'SUP', HEROE, 0.12, (1.0, 1.0, 1.0), esp=1.04, sombra=True, contorno=0.010, kit=chica)
    c['k serif blanco'] = comp_texto('serif', 'Serif', SERIF, 0.20, GRADIENTES['serif'], esp=1.0, contorno=0.012, kit=serif)
    for var, grad in COLOR_GUION.items():
        c[f'k script {var}'] = comp_texto(f'guion {var}', 'script', GUION, 0.22, grad, esp=1.0, contorno=0.012, kit=animacion_kit('pluma'))
    for var in ('lima', 'magenta'):                     # v5.5.13 (neón): la palabra a mano del kit, en Yellowtail y color liso
        c[f'k script yt {var}'] = comp_texto(f'pluma {var}', 'script', PLUMA, 0.22, COLOR_GUION[var], esp=1.0, contorno=0.0, kit=animacion_kit('pluma'))
    c['k label'] = comp_texto('etiqueta', 'LABEL', ETIQUETA, 0.07, (1.0, 1.0, 1.0), esp=1.218, sombra=True, contorno=0.008, kit=chica)   # versalitas espaciadas (kit: .42em = 1 + 0,42/1,93 en Text+, v5.45)
    for var, (caja, texto) in COLOR_CINTA.items():
        c[f'k tape {var}'] = comp_cinta(f'cinta {var}', 'TAPE', HEROE, 0.10, caja, texto, kit=animacion_kit('pega'), premium=True)
    for var in ('amarillo', 'magenta', 'blanco'):
        caja, texto = COLOR_CINTA[var]
        c[f'k tapes {var}'] = comp_cinta(f'cinta serif {var}', 'Tape', SERIF, 0.16, caja, texto, alto_k=1.6, pad_k=0.4, kit=animacion_kit('pega'), premium=True)
    for var, col in COLOR_ANILLO.items():
        c[f'k ring {var}'] = comp_anillo(f'anillo {var}', col)
    for var, col in COLOR_LINEA.items():
        c[f'k line {var}'] = comp_linea(f'línea {var}', col)
    for var in ('lima', 'magenta'):                     # v5.5.13 (neón): los trazos a mano que se dibujan («k ring …» / «k line …»: misma capa en Resolve)
        c[f'k ring trazo {var}'] = comp_trazo(f'círculo {var}', PAL.ANILLO[var], PAL.puntos_circulo())
        c[f'k ring lazo {var}'] = comp_trazo(f'lazo {var}', PAL.ANILLO[var], PAL.puntos_circulo(lazo=True))
        for a in PAL.ASPECTOS_TRAZO:                    # v5.45: con su forma ya hecha (zoom igual en x e y: el trazo no se deforma)
            c[f'k ring trazo {var} {int(round(a * 100))}'] = comp_trazo(f'círculo {var} {int(round(a * 100))}', PAL.ANILLO[var], PAL.puntos_circulo(aspecto=a))
            c[f'k ring lazo {var} {int(round(a * 100))}'] = comp_trazo(f'lazo {var} {int(round(a * 100))}', PAL.ANILLO[var], PAL.puntos_circulo(lazo=True, aspecto=a))
        c[f'k line trazo {var}'] = comp_trazo(f'subrayado {var}', PAL.LINEA[var], PAL.puntos_subrayado(), PAL.SUBRAYADO_GROSOR)
        for a in PAL.SUBRAYADO_ANCHOS:                  # v5.47: la pincelada a su ancho real (zoom igual en x e y: no se estira ni adelgaza)
            c[f'k line trazo {var} {int(round(a * 100))}'] = comp_trazo(f'subrayado {var} {int(round(a * 100))}', PAL.LINEA[var], PAL.puntos_subrayado(ancho=a),
                                                                        PAL.SUBRAYADO_GROSOR)
    return c


if __name__ == '__main__':
    for nombre in todos():
        print(nombre)
