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


def _cadena(origen, anim, x0=140, y0=40):
    """Transform (rebote) + Merge sin fondo (la opacidad) + MediaOut: lo que cierra cada comp."""
    t = herramienta('Transform', 'Anim', x0, y0, [
        enlace('Input', origen),
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + {K.lua(anim["dy"])})", }},',
        f'Size = Input {{ Value = 1, Expression = "{K.lua(anim["size"])}", }},',
        f'Angle = Input {{ Value = 0, Expression = "{K.lua(anim["ang"])}", }},',
    ])
    t += _vacio(x0 + 160, y0 + 90)
    t += herramienta('Merge', 'Salida', x0 + 160, y0, [
        enlace('Background', 'Vacio'),
        enlace('Foreground', 'Anim'),
        f'Blend = Input {{ Value = 1, Expression = "{K.lua(anim["blend"])}", }},',
    ])
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


def comp_texto(nombre, texto, fuente, tam, relleno, esp=1.0, entrada='pop', retardo=0, sombra=True, interlineado=None, contorno=0.0):
    """Un Text+ con relleno (color liso o degradado), sombra y la entrada animada. relleno = (r,g,b) o [(pos, (r,g,b))…]."""
    extra = []
    color = (1, 1, 1)
    if isinstance(relleno, (list, tuple)) and relleno and isinstance(relleno[0], (list, tuple)) and len(relleno[0]) == 2 and isinstance(relleno[0][1], (list, tuple)):
        extra += ['Type1 = Input { Value = 2, },', f'ShadingGradient1 = Input {{ Value = {degradado(relleno)}, }},']
    else:
        color = relleno
    if sombra:
        extra += _sombra(2, 0.8, -0.0065, 7)                 # sombra firme debajo de la letra…
        if contorno > 0:
            extra += _contorno(3, contorno)                  # …y, en el texto pequeño, un contorno oscuro: se lee también sobre una pared blanca
        else:
            extra += _sombra(3, 0.55, -0.002, 34)            # (los héroes llevan un halo ancho)
    t = texto_plus('Template', -220, 40, texto, fuente[0], fuente[1], tam, color=color, esp=esp, extra=extra)
    t += _cadena('Template', animacion(entrada, retardo))
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


CAP = {'Owners Narrow': 0.700, 'DM Serif Text': 0.661, 'Antagon': 0.854, 'Montserrat': 0.700, 'Yellowtail': 0.729}     # altura de las mayúsculas / em (Pillow)
ASPECTO = 1080.0 / 1920.0                                                                       # ancho/alto del cuadro vertical
EM = 640.0 / 1080.0                                                                              # el em de «Size = 1» en fracciones del ancho del cuadro


def comp_cinta(nombre, texto, fuente, tam, caja, color_texto, entrada='giro', retardo=0, esp=1.0, alto_k=1.55, pad_k=0.5, dy_k=0.03, sombra_caja=0.5, radio=0.15):
    """Texto sobre una caja de color que SE AJUSTA AL TEXTO: un RectangleMask cuyo ancho sale del DataWindow del Text+ «Template» más el relleno y cuyo alto
    sale de su Size (alto_k × la altura de las mayúsculas; pad_k × esa altura a cada lado). Así la caja sigue al texto aunque la app cambie el Size o el
    texto, y una cinta de varias palabras es UNA sola caja (la forma «caja por carácter» de Text+ dejaba un hueco en cada espacio)."""
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
    t += herramienta('Merge', 'Juntas', 40, 80, [enlace('Background', 'Caja'), enlace('Foreground', 'Template')])
    # sombra suave de toda la cinta (el mismo recurso que las comps viejas: silueta negra, difuminada y un poco más abajo)
    t += herramienta('BrightnessContrast', 'Negro', 40, 160, [enlace('Input', 'Juntas'), 'Gain = Input { Value = 0, },', f'Alpha = Input {{ Value = {n(sombra_caja)}, }},'])
    t += herramienta('Blur', 'Difumina', 40, 200, [enlace('Input', 'Negro'), 'XBlurSize = Input { Value = 6, },', 'Filter = Input { Value = FuID { "Gaussian" }, },'])
    t += herramienta('Transform', 'Baja', 40, 240, [enlace('Input', 'Difumina'), 'Center = Input { Value = { 0.5, 0.4965 }, },'])
    t += herramienta('Merge', 'ConSombra', 40, 280, [enlace('Background', 'Baja'), enlace('Foreground', 'Juntas')])
    t += _cadena('ConSombra', animacion(entrada, retardo))
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
    avance = f'1 - (1 - math.min(1, math.max(0, time / {dur})))^2.4'
    return (f'\t\t{nombre} = PolylineMask {{\n\t\t\tDrawMode = "InsertAndModify",\n\t\t\tDrawMode2 = "InsertAndModify",\n\t\t\tCtrlWShown = false,\n\t\t\tInputs = {{\n'
            f'\t\t\t\tFilter = Input {{ Value = FuID {{ "Fast Gaussian" }}, }},\n\t\t\t\tMaskWidth = Input {{ Value = {K.ANCHO}, }},\n\t\t\t\tMaskHeight = Input {{ Value = {K.ALTO}, }},\n'
            f'\t\t\t\tPixelAspect = Input {{ Value = {{ 1, 1 }}, }},\n\t\t\t\tUseFrameFormatSettings = Input {{ Value = 1, }},\n\t\t\t\tClippingMode = Input {{ Value = FuID {{ "None" }}, }},\n'
            f'\t\t\t\tSolid = Input {{ Value = 0, }},\n\t\t\t\tBorderWidth = Input {{ Value = {n(grosor)}, }},\n'
            f'\t\t\t\tWriteOnEnd = Input {{ Value = 1, Expression = "{K.lua(avance)}", }},\n'
            f'\t\t\t\tPolyline = Input {{ SourceOp = "{nombre}Poly", Source = "Value", }},\n\t\t\t\tPolyline2 = Input {{ Value = Polyline {{ }}, Disabled = true, }},\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n'
            f'\t\t{nombre}Poly = BezierSpline {{\n\t\t\tSplineColor = {{ Red = 160, Green = 252, Blue = 4 }},\n\t\t\tCtrlWZoom = false,\n\t\t\tNameSet = true,\n\t\t\tKeyFrames = {{\n'
            f'\t\t\t\t[0] = {{ 0, Flags = {{ Linear = true, LockedY = true }}, Value = Polyline {{\n\t\t\t\t\tClosed = false,\n\t\t\t\t\tPoints = {{\n{pts}\n\t\t\t\t\t}}\n\t\t\t\t}} }}\n'
            f'\t\t\t}}\n\t\t}},\n')


def comp_trazo(nombre, color, puntos, grosor=PAL.TRAZO_GROSOR):
    """v5.5.13 (neón) — círculo, lazo o subrayado a mano que se dibuja (kit TEMA 1: `hook()` deco). Sin rebote: el trazo aparece al dibujarse y se va
    con la pila (los 5 últimos fotogramas)."""
    t = _polilinea_abierta('Trazo', puntos, grosor)
    t += texto_plus('Template', -220, 200, ' ', HEROE[0], HEROE[1], 0.05)       # sin conectar: solo para que la app reconozca el clip como suyo
    t += K._fondo('Tinta', -60, 40, color, 'Trazo')
    t += _vacio(140, 130)
    t += herramienta('Merge', 'Salida', 140, 40, [enlace('Background', 'Vacio'), enlace('Foreground', 'Tinta'), f'Blend = Input {{ Value = 1, Expression = "{K.lua(SALIDA)}", }},'])
    t += media_out('Salida', 300, 40)
    return K.armar_comp(t, f'CineCaptions Kinetic - {nombre}')


# ------------------------------------------------------------------------------------------------------------------ el catálogo
def todos():
    """{nombre del clip: texto de la comp}. Los tamaños (Size) son los de partida: la app fija el real por clip."""
    c = {}
    for var in ('blanco', 'lima', 'amarillo', 'magenta', 'rojo'):
        c[f'k hero {var}'] = comp_texto(f'héroe {var}', 'HERO', HEROE, 0.30, GRADIENTES[var], esp=1.0, entrada='pop', contorno=(0.007 if var == 'blanco' else 0.0))
    c['k sup'] = comp_texto('sup', 'SUP', HEROE, 0.12, (1.0, 1.0, 1.0), esp=1.04, entrada='sube', sombra=True, contorno=0.010)
    c['k serif blanco'] = comp_texto('serif', 'Serif', SERIF, 0.20, GRADIENTES['serif'], esp=1.0, entrada='abre', contorno=0.012)
    for var, grad in COLOR_GUION.items():
        c[f'k script {var}'] = comp_texto(f'guion {var}', 'script', GUION, 0.22, grad, esp=1.0, entrada='giro', contorno=0.012)
    for var in ('lima', 'magenta'):                     # v5.5.13 (neón): la palabra a mano del kit, en Yellowtail y color liso
        c[f'k script yt {var}'] = comp_texto(f'pluma {var}', 'script', PLUMA, 0.22, COLOR_GUION[var], esp=1.0, entrada='giro', contorno=0.0)
    c['k label'] = comp_texto('etiqueta', 'LABEL', ETIQUETA, 0.07, (1.0, 1.0, 1.0), esp=1.42, entrada='sube', sombra=True, contorno=0.008)   # versalitas espaciadas (kit: .42em)
    for var, (caja, texto) in COLOR_CINTA.items():
        c[f'k tape {var}'] = comp_cinta(f'cinta {var}', 'TAPE', HEROE, 0.10, caja, texto, entrada='giro')
    for var in ('amarillo', 'magenta', 'blanco'):
        caja, texto = COLOR_CINTA[var]
        c[f'k tapes {var}'] = comp_cinta(f'cinta serif {var}', 'Tape', SERIF, 0.16, caja, texto, entrada='giro', alto_k=1.6, pad_k=0.4)
    for var, col in COLOR_ANILLO.items():
        c[f'k ring {var}'] = comp_anillo(f'anillo {var}', col)
    for var, col in COLOR_LINEA.items():
        c[f'k line {var}'] = comp_linea(f'línea {var}', col)
    for var in ('lima', 'magenta'):                     # v5.5.13 (neón): los trazos a mano que se dibujan («k ring …» / «k line …»: misma capa en Resolve)
        c[f'k ring trazo {var}'] = comp_trazo(f'círculo {var}', PAL.ANILLO[var], PAL.puntos_circulo())
        c[f'k ring lazo {var}'] = comp_trazo(f'lazo {var}', PAL.ANILLO[var], PAL.puntos_circulo(lazo=True))
        c[f'k line trazo {var}'] = comp_trazo(f'subrayado {var}', PAL.LINEA[var], PAL.puntos_subrayado())
    return c


if __name__ == '__main__':
    for nombre in todos():
        print(nombre)
