# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/viral_elementos.py — los elementos del estilo «VIRAL»: línea fina, negrita, shatter, select y drag.
"""
Cada elemento es UN clip del pack (nombre «v <tipo>») con su comp de Fusion y un Text+ «Template» (el que recibe el texto y el tamaño: lo escribe place_kinetic_track):

    v fina      palabra fina (Inter Medium) que sube un poco y aparece: las palabras de enlace de la frase
    v negrita   palabra en negrita cursiva (Inter ExtraBold inclinada): la palabra con peso de la línea
    v shatter   palabra azul cielo con brillo y barrido de luz que se parte en trozos desplazados (glitch)  ← «ESTILO VIRAL (1)»
    v select    máquina de escribir + cursor + caja roja punteada que se dibuja                  ← «ESTILO VIRAL (2)»
    v drag      contorno punteado que una mano arrastra y rellena de blanco con brillo          ← «ESTILO VIRAL (4)»

La pila de líneas finas + negrita (ESTILO VIRAL (3)) la arma viral_captions.py con «v fina» y «v negrita».
Todo es relativo al TAMAÑO del Text+ (Size) y al cuadro (se lee con comp:GetPrefs), así el mismo clip sirve a cualquier tamaño de palabra.
Entrada y salida van dentro de cada comp (la salida, vía comp.RenderEnd: los 5 últimos fotogramas del clip). Las animaciones largas (select, drag) se COMPRIMEN en el tiempo si
el clip dura menos de lo que necesitan (TT): una palabra dicha deprisa llega igual al estado final. Las expresiones NO pueden usar string.len ni # (ver viral_comps.py).
"""
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import kinetic_comps as K
import kinetic_elementos as E
import viral_comps as V
from kinetic_comps import degradado, enlace, herramienta, media_out, n, texto_plus

FINA = ('Inter 18pt', 'Medium')
NEGRITA = ('Inter 28pt', 'ExtraBold')
EFECTO = ('Inter 28pt', 'Black')
INCLINACION = -0.21                     # ShearX de cada elemento de la negrita (cursiva sintética sobre una Inter recta: lo que vale en cualquier equipo)
EM = 0.6397                             # el em de «Size = 1» en fracciones del ANCHO del cuadro (691 px a 1080 de ancho; ver viral_captions.K_PX)
SALIDA = E.SALIDA                       # 1 durante el clip y baja a 0 en los 5 últimos fotogramas
FORMATOS = {'v': (1080, 1920), 'h': (1920, 1080)}


def configurar(formato='v'):
    """Pone las medidas del cuadro en las que se escriben las comps: 'v' = 1080×1920 (vertical) o 'h' = 1920×1080 (horizontal). Lo que cambia: el aspecto (las máscaras y los polígonos son
    fracciones del ancho en X y del alto en Y, así que una flecha o una mano se dibujan con él para no deformarse) y el em de «Size» en fracciones del cuadro."""
    global ASPECTO, ANCHO_CUADRO, ALTO_CUADRO, EM_W, EM_H
    K.ANCHO, K.ALTO = FORMATOS[formato]
    ASPECTO = K.ANCHO / K.ALTO                      # ancho/alto del cuadro (9/16 en vertical): el Height de una máscara es fracción del ALTO, el Width del ANCHO
    ANCHO_CUADRO = '(comp:GetPrefs("Comp.FrameFormat.Width") or %d)' % K.ANCHO
    ALTO_CUADRO = '(comp:GetPrefs("Comp.FrameFormat.Height") or %d)' % K.ALTO
    EM_W = f'(Template.Size * {n(EM)})'            # el em en fracciones del ancho del cuadro
    EM_H = f'(Template.Size * {n(EM * ASPECTO)})'   # … y del alto


configurar('v')


def tt(frames_necesarios):
    """El fotograma «interno» de una animación que necesita `frames_necesarios` fotogramas: si el clip dura menos, el tiempo corre más deprisa (hasta ×2,5)."""
    return f'(time / math.min(1, math.max(0.4, (comp.RenderEnd - 5) / {frames_necesarios})))'


def t24(fotogramas):
    """v5.55: como tt() pero en fotogramas de 24 fps (los de las referencias TEMA3 (1) y (2)): la animación dura lo mismo a 24, 30 o 60 fps."""
    return f'(time * 24 / {E.FPS} / math.min(1, math.max(0.4, (comp.RenderEnd - 5) * 24 / {E.FPS} / {fotogramas})))'


def _p(retardo, dur, t='time'):
    return f'math.min(1, math.max(0, ({t} - {retardo}) / {dur}))'


def _suave(p):
    """easeOutCubic del progreso p (sin rebote)."""
    return f'(1 - (1 - ({p}))^3)'


def _rebote(p):
    return E._rebote(p)


def cadena(origen, anim, x0=140, y0=40):
    """Transform (desplazamiento, tamaño, giro) + Merge sin fondo (la opacidad) + MediaOut: lo que cierra cada comp. `anim`: expresiones dx, dy (fracción del cuadro), size, ang, blend."""
    t = herramienta('Transform', 'Anim', x0, y0, [
        enlace('Input', origen),
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + {K.lua(anim.get("dx", "0"))}, 0.5 + {K.lua(anim.get("dy", "0"))})", }},',
        f'Size = Input {{ Value = 1, Expression = "{K.lua(anim["size"])}", }},',
        f'Angle = Input {{ Value = 0, Expression = "{K.lua(anim.get("ang", "0"))}", }},',
    ])
    t += E._vacio(x0 + 160, y0 + 90)
    t += herramienta('Merge', 'Salida', x0 + 160, y0, [enlace('Background', 'Vacio'), enlace('Foreground', 'Anim'), f'Blend = Input {{ Value = 1, Expression = "{K.lua(anim["blend"])}", }},'])
    t += media_out('Salida', x0 + 320, y0)
    return t


def _inclinar(*nums):
    """El ShearX de cada elemento de sombreado: una cursiva sintética para cualquier fuente recta."""
    return [f'ShearX{k} = Input {{ Value = Number {{ Value = {n(INCLINACION)} }}, }},' for k in nums]


def _color(lineas, num, rgb):
    """Cambia el color (Red/Green/Blue{num}) de un elemento de sombreado ya escrito (las funciones de E las traen en negro)."""
    out = []
    for l in lineas:
        for c, v in zip(('Red', 'Green', 'Blue'), rgb):
            if l.startswith(f'{c}{num} = Input'):
                l = f'{c}{num} = Input {{ Value = Number {{ Value = {n(v)} }}, }},'
        out.append(l)
    return out


def vacio(nombre, x, y):
    """Un fondo transparente del tamaño del cuadro con nombre propio (el Merge que da la opacidad necesita un Background)."""
    return herramienta('Background', nombre, x, y, [
        f'Width = Input {{ Value = {K.ANCHO}, }},', f'Height = Input {{ Value = {K.ALTO}, }},', 'UseFrameFormatSettings = Input { Value = 1, },',
        'TopLeftRed = Input { Value = 0, },', 'TopLeftGreen = Input { Value = 0, },', 'TopLeftBlue = Input { Value = 0, },', 'TopLeftAlpha = Input { Value = 0, },'])


def con_sombra(origen, prefijo, x, y, alfa=0.5, dy=-0.004, blur=6):
    """Silueta negra desenfocada y un poco más abajo, debajo de `origen` (lo que hacía la cinta de Kinetic). Devuelve (nodos, nombre del Merge final).
    v5.55: la opacidad va en un Merge. El «Alpha» de BrightnessContrast es la CASILLA del canal alfa: con Gain 0 dejaba el alfa en 0 y la sombra no se veía
    (render de Resolve 21.1.2)."""
    t = herramienta('BrightnessContrast', prefijo + 'Negro', x, y, [enlace('Input', origen), 'Gain = Input { Value = 0, },'])
    t += herramienta('Blur', prefijo + 'Difumina', x, y + 40, [enlace('Input', prefijo + 'Negro'), f'XBlurSize = Input {{ Value = {n(blur)}, }},', 'Filter = Input { Value = FuID { "Gaussian" }, },'])
    t += herramienta('Transform', prefijo + 'Baja', x, y + 80, [enlace('Input', prefijo + 'Difumina'), f'Center = Input {{ Value = {{ 0.5, {n(0.5 + dy)} }}, }},'])
    t += vacio(prefijo + 'Vacio', x - 120, y + 120)
    t += herramienta('Merge', prefijo + 'Op', x, y + 120, [enlace('Background', prefijo + 'Vacio'), enlace('Foreground', prefijo + 'Baja'), f'Blend = Input {{ Value = {n(alfa)}, }},'])
    t += herramienta('Merge', prefijo + 'Con', x, y + 160, [enlace('Background', prefijo + 'Op'), enlace('Foreground', origen)])
    return t, prefijo + 'Con'


# ------------------------------------------------------------------------------------------------------------------ línea fina y negrita
# v5.54 «B · Premium» (la propuesta que eligió el usuario para los 6 temas): la fina al 90 % de blanco; la negrita con un degradado frío (blanca
# arriba, azul hielo en la base: la parada 0 es la base de la letra) y un brillo suave de ese azul detrás de su contorno.
FINA_COLOR = (0.9, 0.9, 0.9)
NEGRITA_DEGRADADO = [(0.0, (0.812, 0.878, 1.0)), (0.6, (1.0, 1.0, 1.0)), (1.0, (1.0, 1.0, 1.0))]      # #CFE0FF → blanco
NEGRITA_BRILLO = ((0.75, 0.85, 1.0), 0.38, 24)                                                         # (color, opacidad, difuminado)


def comp_fina():
    extra = E._sombra(2, 0.80, -0.004, 10) + E._contorno(3, 0.019, 0.92)
    t = texto_plus('Template', -220, 40, 'fina', FINA[0], FINA[1], 0.09, color=FINA_COLOR, esp=1.0, extra=extra)
    p = _p(0, 7)
    t += cadena('Template', dict(dy=f'(1 - {_suave(p)}) * (-0.014)', size=f'(0.96 + 0.04 * {_suave(p)}) * (0.92 + 0.08 * {SALIDA})', blend=f'math.min(1, {p} * 2.0) * {SALIDA}'))
    return K.armar_comp(t, 'CineCaptions VIRAL - fina')


def comp_negrita():
    color_b, op_b, blur_b = NEGRITA_BRILLO
    extra = (['Type1 = Input { Value = 2, },', f'ShadingGradient1 = Input {{ Value = {degradado(NEGRITA_DEGRADADO)}, }},'] + E._sombra(2, 0.85, -0.006, 9)
             + E._contorno(3, 0.013, 0.95) + E._sombra(4, op_b, 0.0, blur_b, color=color_b) + ['ElementShape4 = Input { Value = 0, },']   # (4: forma de LETRA, no la caja)
             + _inclinar(1, 2, 3, 4))
    t = texto_plus('Template', -220, 40, 'negrita', NEGRITA[0], NEGRITA[1], 0.16, color=(1, 1, 1), esp=0.99, extra=extra)
    p = _p(0, 9)
    t += cadena('Template', dict(dx=f'(1 - {_suave(p)}) * (-0.018)', size=f'(0.82 + 0.18 * {_rebote(p)}) * (0.9 + 0.1 * {SALIDA})', blend=f'math.min(1, {p} * 2.4) * {SALIDA}'))
    return K.armar_comp(t, 'CineCaptions VIRAL - negrita')


# ------------------------------------------------------------------------------------------------------------------ shatter
AZUL = [(0.0, (0.10, 0.52, 0.98)), (0.5, (0.42, 0.74, 1.0)), (1.0, (0.78, 0.92, 1.0))]      # azul cielo; la parte de abajo de la letra es la parada 0
# v5.5: las 4 paletas del Shatter (el primero, azul cielo, es el de siempre): degradado de la letra (de abajo a arriba), color base, borde oscuro (el bisel), halo, brillo y luz del barrido
PALETAS_SHATTER = {
    '': dict(degradado=AZUL, base=(0.42, 0.74, 1.0), bisel=(0.05, 0.38, 0.86), halo=(0.30, 0.72, 1.0), brillo=(0.92, 0.97, 1.0), luz=(0.93, 0.98, 1.0)),
    'rosa': dict(degradado=[(0.0, (0.93, 0.18, 0.55)), (0.5, (1.0, 0.46, 0.73)), (1.0, (1.0, 0.84, 0.93))], base=(1.0, 0.46, 0.73), bisel=(0.72, 0.05, 0.34), halo=(1.0, 0.35, 0.66),
                 brillo=(1.0, 0.96, 0.98), luz=(1.0, 0.95, 0.98)),
    'lima': dict(degradado=[(0.0, (0.30, 0.74, 0.08)), (0.5, (0.60, 0.94, 0.28)), (1.0, (0.88, 1.0, 0.70))], base=(0.60, 0.94, 0.28), bisel=(0.18, 0.50, 0.04), halo=(0.55, 1.0, 0.25),
                 brillo=(0.97, 1.0, 0.92), luz=(0.96, 1.0, 0.90)),
    'oro': dict(degradado=[(0.0, (0.93, 0.50, 0.03)), (0.5, (1.0, 0.77, 0.24)), (1.0, (1.0, 0.94, 0.68))], base=(1.0, 0.77, 0.24), bisel=(0.68, 0.32, 0.0), halo=(1.0, 0.68, 0.10),
                brillo=(1.0, 0.98, 0.90), luz=(1.0, 0.97, 0.88)),
}
CAJAS_SELECT = {'': (1.0, 0.04, 0.04), 'azul': (0.10, 0.45, 1.0), 'verde': (0.05, 0.85, 0.35), 'naranja': (1.0, 0.50, 0.05)}          # el color de la caja punteada
TINTES_DRAG = {'': (1.0, 1.0, 1.0), 'amarillo': (1.0, 0.92, 0.25), 'cian': (0.30, 0.92, 1.0), 'rosa': (1.0, 0.55, 0.80)}              # el color del relleno y del contorno
# v5.55 (pedido: «pule más el Tema 3, no se parece a estos captions»: TEMA3 (1).mp4 = Select, TEMA3 (2).mp4 = Drag, 1920×1080 a 24 fps). Medido en ellas:
# la palabra NO lleva contorno: blanco roto (~0,95) con un brillo blanco suave que se apaga a ~0,1 de su alto; caja roja de guiones GRUESOS (~0,05 em);
# cursor grande (~0,55 em) con una sombra ancha que oscurece la esquina de la caja. Drag: una mano entra abierta por la derecha, agarra la palabra punteada
# y la arrastra ~0,9 em desde arriba a la izquierda; ya en su sitio se rellena de gris oscuro a blanco y la mano se va por detrás.
# El espaciado (0,97) ya era el de la referencia: Text+ SUMA (CharacterSpacing − 1) × ~1,5 em por letra («Select» mide 3,82 de ancho/alto; la referencia, 3,79).
EFECTO_RELLENO = 0.955
EFECTO_BRILLO = (0.21, 14)                  # el brillo blanco de la letra: opacidad, difuminado (Softness del Text+; medido en Resolve: 41/15/9/4 como la referencia)
EFECTO_SOMBRA = (0.55, -0.006, 12)          # la sombra oscura debajo (se ve solo sobre un fondo claro): opacidad, bajada, difuminado
SIZE_CALIBRADO = 0.3035                     # el Size del Text+ con el que se midieron esos difuminados: el Softness de Text+ va contra el CUADRO, no contra la letra,
                                            # así que crece con Template.Size (una palabra pequeña salía con el brillo el doble de ancho, en proporción)
VOLUMEN_EFECTO = [(0.0, 0.92), (0.5, 0.965), (1.0, 0.92)]      # el relleno del Select de abajo (parada 0) a arriba: el leve volumen de la referencia


def _region(nombre, x0, x1, y0, y1, angulo, y_pos):
    """Una máscara rectangular que cubre x ∈ [x0, x1], y ∈ [y0, y1] (fracciones del cuadro; y desde ABAJO; expresiones de Fusion), con un giro opcional en grados."""
    return K._mascara('RectangleMask', nombre, -220, y_pos, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(({K.lua(x0)} + {K.lua(x1)}) / 2, ({K.lua(y0)} + {K.lua(y1)}) / 2)", }},',
        f'Width = Input {{ Value = 1, Expression = "({K.lua(x1)}) - ({K.lua(x0)})", }},',
        f'Height = Input {{ Value = 0.05, Expression = "({K.lua(y1)}) - ({K.lua(y0)})", }},',
        f'Angle = Input {{ Value = {n(angulo)}, }},', 'CornerRadius = Input { Value = 0, },'])


def comp_shatter(paleta=''):
    """Azul cielo con degradado y brillo; entra con un fundido, un BARRIDO DE LUZ cruza las letras y, a los 12 fotogramas, la palabra se parte como en «ESTILO VIRAL (1)»:
    un corte vertical entre la «a» y la «t» (la mitad izquierda se desliza a la izquierda y la derecha casi no se mueve) y, en la mitad izquierda, cortes horizontales inclinados:
    arriba casi quieta, una franja finísima muy a la izquierda (el «-» de la referencia) y abajo algo menos. Cada trozo se recorta ANTES de moverse (si se moviera todo con una
    máscara, las letras vecinas se colarían en los huecos). `paleta`: '' (azul cielo), 'rosa', 'lima' u 'oro' (PALETAS_SHATTER)."""
    P = PALETAS_SHATTER[paleta]
    extra = ['Type1 = Input { Value = 2, },', f'ShadingGradient1 = Input {{ Value = {degradado(P["degradado"])}, }},']
    extra += ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', 'Thickness2 = Input { Value = Number { Value = 0.0055 }, },',   # 2: borde más oscuro (el bisel)
              f'Red2 = Input {{ Value = Number {{ Value = {n(P["bisel"][0])} }}, }},', f'Green2 = Input {{ Value = Number {{ Value = {n(P["bisel"][1])} }}, }},',
              f'Blue2 = Input {{ Value = Number {{ Value = {n(P["bisel"][2])} }}, }},', 'Opacity2 = Input { Value = Number { Value = 0.9 }, },']
    extra += _color(E._sombra(3, 0.65, 0.0, 26), 3, P['halo'])                          # 3: el halo del color de la palabra
    t = texto_plus('Template', -220, 40, 'Shatter', EFECTO[0], EFECTO[1], 0.30, color=P['base'], esp=0.97, extra=extra)
    ligado = 'StyledText = Input { Value = "Shatter", Expression = "Template.StyledText", },'
    t += texto_plus('Medida', -220, 120, 'Shatter', EFECTO[0], EFECTO[1], 0.30, esp=0.97, expr={'Size': 'Template.Size'}).replace('StyledText = Input { Value = "Shatter", },', ligado)
    dw = 'Medida.Output.DataWindow'
    WW = f'(({dw} and (({dw}[3] - {dw}[1]) / {ANCHO_CUADRO})) or 0.4)'                # el ancho de la palabra (fracción del ancho del cuadro)
    T = tt(28)
    # --- brillo fijo: una copia blanca del texto, translúcida, solo en la mitad de arriba de las letras
    t += texto_plus('BrilloTxt', -220, 320, 'Shatter', EFECTO[0], EFECTO[1], 0.30, color=P['brillo'], esp=0.97, expr={'Size': 'Template.Size'}).replace('StyledText = Input { Value = "Shatter", },', ligado)
    t += K._mascara('RectangleMask', 'MBrillo', -220, 400, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + 0.20 * {K.lua(EM_H)})", }},', 'Width = Input { Value = 3, },',
        f'Height = Input {{ Value = 0.05, Expression = "0.30 * {K.lua(EM_H)}", }},', 'Angle = Input { Value = 0, },', 'CornerRadius = Input { Value = 0, },'])
    t += herramienta('Merge', 'Brillo', -60, 320, [enlace('Background', 'Template'), enlace('Foreground', 'BrilloTxt'), 'Blend = Input { Value = 0.22, },', 'EffectMask = Input { SourceOp = "MBrillo", Source = "Mask", },'])
    # --- barrido de luz: una banda blanca inclinada y de borde suave que cruza la palabra de izquierda a derecha (solo se ve sobre las letras: Operator «Atop»)
    s = f'math.min(1, math.max(0, ({T} - 3) / 9))'
    t += K._mascara('RectangleMask', 'MBarrido', -220, 480, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 - 0.5 * {K.lua(WW)} - 0.12 + ({s}) * ({K.lua(WW)} + 0.24), 0.5)", }},',
        f'Width = Input {{ Value = 0.1, Expression = "0.16 * {K.lua(WW)} + 0.03", }},', 'Height = Input { Value = 3, },', 'Angle = Input { Value = 18, },',
        'SoftEdge = Input { Value = 0.045, },', 'CornerRadius = Input { Value = 0, },'])
    t += K._fondo('LuzFondo', -60, 480, P['luz'], 'MBarrido')
    sweep_blend = f'0.60 * math.min(1, ({s}) * 5) * (1 - math.min(1, math.max(0, ({T} - 16) / 6)))'
    t += herramienta('Merge', 'Barrido', 60, 400, [enlace('Background', 'Brillo'), enlace('Foreground', 'LuzFondo'), 'Operator = Input { Value = FuID { "Atop" }, },',
                                                  f'Blend = Input {{ Value = 0, Expression = "{K.lua(sweep_blend)}", }},'])
    # --- los fragmentos: un ÁRBOL de cortes (como un vidrio que se quiebra). Cada corte es un semiplano (una RectangleMask enorme, girada unos grados: el borde queda inclinado, como una
    # esquirla); cada hoja es la intersección de los semiplanos de su camino, así que los fragmentos encajan sin huecos ni solapes hasta que se separan. Cada fragmento se recorta
    # ANTES de moverse (si se moviera todo con una máscara, las letras vecinas se colarían en los huecos). Las posiciones están en anchos de palabra (WW) y ems (E) desde su centro.
    E_W = EM_W
    ARBOL = ('corte', (-0.02, 0.0), 4, [                                   # corte vertical principal, entre la «a» y la «t», inclinado 4°
        ('izq', ('corte', (-0.30, 0.0), -5, [
            ('izq', ('corte', (-0.42, 0.02), -3, [('arr', 'LLt'), ('aba', ('corte', (-0.42, -0.08), -3, [('arr', 'LLs'), ('aba', 'LLb')]))])),      # LLs = la franja finísima
            ('der', ('corte', (-0.16, -0.04), 4, [('arr', 'LRt'), ('aba', 'LRb')])),
        ])),
        ('der', ('corte', (0.30, 0.0), 5, [
            ('izq', ('corte', (0.14, 0.04), -2, [('arr', 'RLt'), ('aba', 'RLb')])),
            ('der', ('corte', (0.42, -0.03), 3, [('arr', 'RRt'), ('aba', 'RRb')])),
        ])),
    ])
    # hoja: (dx en WW, dy en E, giro en grados, centro del fragmento (x en WW, y en E) = el eje del giro)
    HOJAS = {
        'LLt': (-0.045, 0.006, 1.4, (-0.44, 0.20)), 'LLs': (-0.135, -0.012, -0.6, (-0.44, -0.03)), 'LLb': (-0.072, -0.022, -1.2, (-0.44, -0.20)),
        'LRt': (-0.020, 0.010, 0.9, (-0.17, 0.20)), 'LRb': (-0.036, -0.032, -1.6, (-0.17, -0.20)),
        'RLt': (0.006, 0.016, -0.8, (0.16, 0.20)), 'RLb': (0.014, -0.028, 1.2, (0.16, -0.20)),
        'RRt': (0.026, 0.012, 1.8, (0.40, 0.20)), 'RRb': (0.042, -0.036, -2.2, (0.40, -0.20)),
    }
    TONO = {'LLt': 1.05, 'LLs': 1.12, 'LLb': 0.90, 'LRt': 1.00, 'LRb': 0.93, 'RLt': 1.07, 'RLb': 0.91, 'RRt': 1.03, 'RRb': 0.88}      # facetas: cada fragmento un poco más claro u oscuro
    LARGO = 4.0
    cuenta = {'n': 0, 'y': 560}

    def semiplano(px, py, ang, lado):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        nx, ny = {'izq': (-c, -s), 'der': (c, s), 'arr': (-s, c), 'aba': (s, -c)}[lado]
        x_c = f'(({px}) + {n(nx * LARGO / 2)})'
        y_c = f'(({py}) + {n(ny * LARGO / 2)})'
        cuenta['n'] += 1
        nombre = f'Sp{cuenta["n"]}'
        nodos = K._mascara('RectangleMask', nombre, -220, cuenta['y'], [
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + {K.lua(x_c)}, 0.5 + ({K.lua(y_c)}) * {n(ASPECTO)})", }},',
            f'Width = Input {{ Value = {n(LARGO)}, }},', f'Height = Input {{ Value = {n(LARGO * ASPECTO)}, }},', f'Angle = Input {{ Value = {n(ang)}, }},', 'CornerRadius = Input { Value = 0, },'])
        cuenta['y'] += 80
        return nombre, nodos

    cortes = []                                                           # (hoja, nombre de su recorte)
    nodos_arbol = ''

    def recorrer(nodo, padre):
        nonlocal nodos_arbol
        _, (ax, ay), ang, hijos = nodo
        px, py = f'({n(ax)} * {WW})', f'({n(ay)} * {E_W})'
        for lado, sub in hijos:
            mascara, nodos = semiplano(px, py, ang, lado)
            nodos_arbol += nodos
            recorte = f'R{cuenta["n"]}'
            nodos_arbol += herramienta('Merge', recorte, 140, cuenta['y'] - 80, [enlace('Background', 'VacioP'), enlace('Foreground', padre), f'EffectMask = Input {{ SourceOp = "{mascara}", Source = "Mask" }},'])
            if isinstance(sub, str):
                cortes.append((sub, recorte))
            else:
                recorrer(sub, recorte)
    t += vacio('VacioP', 420, 600)
    recorrer(ARBOL, 'Barrido')
    t += nodos_arbol
    p = f'math.min(1, math.max(0, ({T} - 12) / 5))'                        # a partir del fotograma 12 los fragmentos se separan
    e = E._rebote(p)
    salidas = []
    for k, (hoja, recorte) in enumerate(cortes):
        dx, dy, giro, (cx, cy) = HOJAS[hoja]
        t += herramienta('Transform', 'T' + hoja, 300, 560 + 80 * k, [
            enlace('Input', recorte),
            f'Pivot = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + {n(cx)} * {K.lua(WW)}, 0.5 + {n(cy)} * {K.lua(E_W)} * {n(ASPECTO)})", }},',
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + {n(dx)} * {K.lua(WW)} * {K.lua(e)}, 0.5 + {n(dy)} * {K.lua(EM_H)} * {K.lua(e)})", }},',
            f'Angle = Input {{ Value = 0, Expression = "{n(giro)} * {K.lua(e)}", }},'])
        t += herramienta('BrightnessContrast', 'B' + hoja, 380, 560 + 80 * k, [enlace('Input', 'T' + hoja), f'Gain = Input {{ Value = {n(TONO[hoja])}, }},'])
        salidas.append('B' + hoja)
    prev = salidas[0]
    for k, nom in enumerate(salidas[1:], 1):
        t += herramienta('Merge', f'U{k}', 520, 560 + 80 * k, [enlace('Background', prev), enlace('Foreground', nom)])
        prev = f'U{k}'
    # entera hasta el fotograma 12; luego, los fragmentos (el cambio es instantáneo: al principio encajan y se ven solo las grietas)
    antes = f'(({T}) < 12) and 1 or 0'
    t += herramienta('Merge', 'Entera', 640, 480, [enlace('Background', 'VacioP'), enlace('Foreground', 'Barrido'), f'Blend = Input {{ Value = 1, Expression = "{K.lua(antes)}", }},'])
    t += herramienta('Merge', 'Rota', 640, 560, [enlace('Background', 'Entera'), enlace('Foreground', prev), f'Blend = Input {{ Value = 0, Expression = "1 - ({K.lua(antes)})", }},'])
    pa = _p(0, 5)
    t += cadena('Rota', dict(size=f'(0.94 + 0.06 * {_suave(pa)}) * (0.9 + 0.1 * {SALIDA})', blend=f'math.min(1, {pa} * 1.6) * {SALIDA}'), x0=800)
    return K.armar_comp(t, 'CineCaptions VIRAL - shatter')


# ------------------------------------------------------------------------------------------------------------------ select
def _flecha(nombre, y):
    """La flecha del ratón (punta arriba a la izquierda) en el espacio de la máscara: x en fracción del ancho; y se corrige por el aspecto para que no se deforme. La punta es el origen.
    v5.55: la punta de flecha SIN cola de TEMA3 (1).mp4 (medida: 0,37 × 0,54 em, con la muesca abajo a la derecha)."""
    rejilla = [(0, 0), (0, -19), (4.94, -12.73), (12.8, -13.8)]                                          # en una cuadrícula de 12,8 × 19
    k = 0.0062
    return V.poligono(nombre, [(px * k, py * k * ASPECTO) for px, py in rejilla], -220, y)


def _halo(num, color, opacidad, dy, blur):
    """Un elemento de sombreado con la forma de la LETRA (ElementShape 0; si no, del 3 en adelante sale como un rectángulo) desenfocado: brillo o sombra.
    v5.55: con SoftnessBlend 1. El 0 de E._sombra deja el elemento SIN desenfocar (en el render de Resolve el «brillo» era una copia nítida de la letra).
    El difuminado sigue al tamaño de la palabra: `blur` es el de Size = SIZE_CALIBRADO."""
    cambios = {f'SoftnessBlend{num} = Input {{ Value = Number {{ Value = 0 }}, }},': f'SoftnessBlend{num} = Input {{ Value = Number {{ Value = 1 }}, }},'}
    for eje in ('X', 'Y'):
        cambios[f'Softness{eje}{num} = Input {{ Value = Number {{ Value = {n(blur)} }}, }},'] = (
            f'Softness{eje}{num} = Input {{ Value = Number {{ Value = {n(blur)} }}, Expression = "Template.Size * {n(blur / SIZE_CALIBRADO)}", }},')
    return [cambios.get(l, l) for l in E._sombra(num, opacidad, dy, blur, color=color)] + [f'ElementShape{num} = Input {{ Value = 0, }},']


def _letra_efecto(primero):
    """v5.55: el acabado de la palabra de Select y Drag (como la referencia): brillo blanco suave y, debajo, la sombra oscura (sin contorno).
    `primero`: el nº del elemento del brillo (la sombra va en el siguiente: el de nº menor se dibuja encima)."""
    return (_halo(primero, (1, 1, 1), EFECTO_BRILLO[0], 0.0, EFECTO_BRILLO[1])
            + _halo(primero + 1, (0.0, 0.0, 0.0), EFECTO_SOMBRA[0], EFECTO_SOMBRA[1], EFECTO_SOMBRA[2]))


def comp_select(color_caja=''):
    """Máquina de escribir (Write On) → cursor → caja punteada (roja, o azul / verde / naranja: CAJAS_SELECT) que se dibuja desde la esquina de arriba a la izquierda hasta la de abajo a la derecha.
    v5.55: tiempos de la referencia (24 fps): la «S» sale en el fotograma 1-2, escribe en ~10, el cursor aparece a media palabra y la caja se abre en 8.
    La letra lleva un leve volumen (más oscura arriba y abajo: 235 / 245 / 235 en la referencia)."""
    dw_m = 'Medida.Output.DataWindow'
    letras = f'(({dw_m} and (({dw_m}[3] - {dw_m}[1]) / {ANCHO_CUADRO}) or 0.2) / ({EM_W} * 0.62))'      # nº de letras estimado por el ancho
    T = t24(26)
    T0 = 0.5                                                                                      # empieza a escribir
    dur = f'(2.5 + 1.15 * {letras})'
    escribe = f'math.min(1, math.max(0, ({T} - {T0}) / {dur}))'
    fin_esc = f'({T0} + {dur})'
    caja = f'math.min(1, math.max(0, ({T} - {fin_esc} - 1) / 8))'                                   # progreso de la caja y del cursor
    caja_e = f'(1 - (1 - {caja})^3)'
    extra = (['End = Input { Value = 1, Expression = "%s", },' % K.lua(escribe), 'Type1 = Input { Value = 2, },',
              f'ShadingGradient1 = Input {{ Value = {degradado([(p, (v,) * 3) for p, v in VOLUMEN_EFECTO])}, }},'] + _letra_efecto(2))
    t = texto_plus('Template', -220, 40, 'Select', EFECTO[0], EFECTO[1], 0.30, color=(EFECTO_RELLENO,) * 3, esp=0.97, extra=extra)
    ligado = 'StyledText = Input { Value = "Select", Expression = "Template.StyledText", },'
    t += texto_plus('Medida', -220, 120, 'Select', EFECTO[0], EFECTO[1], 0.30, esp=0.97, expr={'Size': 'Template.Size'}).replace('StyledText = Input { Value = "Select", },', ligado)
    rojo = CAJAS_SELECT[color_caja]
    borde = ['Enabled1 = Input { Value = 0, },', 'Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 3, },', 'Level2 = Input { Value = Number { Value = 0 }, },',
             'LineStyle2 = Input { Value = Number { Value = 1 }, },', 'JoinStyle2 = Input { Value = 1, },',
             'Thickness2 = Input { Value = Number { Value = 0.04 }, Expression = "Template.Size * 0.135", },',              # v5.55: guiones gruesos (0,075 → 0,135, ~0,05 em)
             'ExtendHorizontal2 = Input { Value = Number { Value = 0.03 }, Expression = "Template.Size * 0.1", },', 'ExtendVertical2 = Input { Value = Number { Value = 0.02 }, Expression = "Template.Size * 0.07", },',
             f'Red2 = Input {{ Value = Number {{ Value = {n(rojo[0])} }}, }},', f'Green2 = Input {{ Value = Number {{ Value = {n(rojo[1])} }}, }},', f'Blue2 = Input {{ Value = Number {{ Value = {n(rojo[2])} }}, }},']
    t += texto_plus('Caja', -220, 200, 'Select', EFECTO[0], EFECTO[1], 0.30, esp=0.97, extra=borde, expr={'Size': 'Template.Size'}).replace('StyledText = Input { Value = "Select", },', ligado)
    dw_c = 'Caja.Output.DataWindow'
    arriba_izq = f'Point(({dw_c} and ({dw_c}[1] / {ANCHO_CUADRO}) or 0.3), ({dw_c} and ({dw_c}[4] / {ALTO_CUADRO}) or 0.6))'
    abajo_der = f'Point(({dw_c} and ({dw_c}[3] / {ANCHO_CUADRO}) or 0.7), ({dw_c} and ({dw_c}[2] / {ALTO_CUADRO}) or 0.4))'
    t += herramienta('Transform', 'Crece', -60, 200, [
        enlace('Input', 'Caja'),
        f'Pivot = Input {{ Value = {{ 0.3, 0.6 }}, Expression = "{K.lua(arriba_izq)}", }},',
        f'Size = Input {{ Value = 0, Expression = "math.max(0.001, {K.lua(caja_e)})", }},'])
    # el cursor: la flecha (punta en el origen = centro del cuadro) con sombra, llevada de la esquina de arriba a la izquierda a la de abajo a la derecha de la caja
    t += _flecha('Flecha', 300)
    t += K._fondo('Cursor', -60, 300, (0.98, 0.98, 0.98), 'Flecha')
    lerp = lambda a, b: f'(({a}) + ({caja_e}) * (({b}) - ({a})))'
    centro = f'Point({lerp(f"({dw_c} and ({dw_c}[1] / {ANCHO_CUADRO}) or 0.3)", f"({dw_c} and ({dw_c}[3] / {ANCHO_CUADRO}) or 0.7)")}, {lerp(f"({dw_c} and ({dw_c}[4] / {ALTO_CUADRO}) or 0.6)", f"({dw_c} and ({dw_c}[2] / {ALTO_CUADRO}) or 0.4)")})'
    t += herramienta('Transform', 'Raton', 40, 300, [
        enlace('Input', 'Cursor'),
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "{K.lua(centro)}", }},',
        'Pivot = Input { Value = { 0.5, 0.5 }, },',
        f'Size = Input {{ Value = 1, Expression = "{K.lua(f"{EM_W} * 4.6")}", }},'])            # v5.55: más grande (3,2 → 4,6: ~0,55 em, como la referencia)
    sombra, ult = con_sombra('Raton', 'Cs', 140, 300, alfa=0.8, dy=-0.012, blur=40)                 # … y con la sombra ancha que oscurece la esquina de la caja
    t += sombra
    t += herramienta('Merge', 'Fundido', 260, 300, [enlace('Background', 'VacioCursor'), enlace('Foreground', ult),
                                                   f'Blend = Input {{ Value = 0, Expression = "{K.lua(_p(f"({T0} + 0.5 * {dur})", 4, T))}", }},'])     # aparece a media palabra
    t += vacio('VacioCursor', 260, 380)
    # v5.55: la caja se oscurece junto al cursor, como en la referencia (medido: su esquina a 1/4 de luz, 41 % más oscura a 0,64 em y 26 % a 0,88 em): una elipse
    # muy suave en la punta del cursor que oscurece SOLO la caja (no el video). Medido en Resolve: el SoftEdge desenfoca con sigma ≈ 0,45 × su valor y, como el
    # Height de una EllipseMask, va contra el ANCHO del cuadro (ver _mano). Disco de 0,75 em + SoftEdge 0,8 em + Gain 0,15 ≈ 75/43/24 % (medido: 77/34/21 %)
    t += K._mascara('EllipseMask', 'Penumbra', -60, 250, [
        f'Center = Input {{ Value = {{ 0.7, 0.4 }}, Expression = "{K.lua(centro)}", }},',
        f'Width = Input {{ Value = 0.25, Expression = "{K.lua(f"{EM_W} * 1.5")}", }},',
        f'Height = Input {{ Value = 0.25, Expression = "{K.lua(f"{EM_W} * 1.5")}", }},',
        f'SoftEdge = Input {{ Value = 0.13, Expression = "{K.lua(f"{EM_W} * 0.8")}", }},'])
    t += herramienta('BrightnessContrast', 'Oscura', 40, 200, [enlace('Input', 'Crece'), 'Gain = Input { Value = 0.15, },', enlace('EffectMask', 'Penumbra', 'Mask')])
    t += herramienta('Merge', 'M1', 380, 120, [enlace('Background', 'Template'), enlace('Foreground', 'Oscura')])
    t += herramienta('Merge', 'M2', 380, 200, [enlace('Background', 'M1'), enlace('Foreground', 'Fundido')])
    p = _p(0, 6)
    t += cadena('M2', dict(size=f'(0.96 + 0.04 * {_suave(p)}) * (0.92 + 0.08 * {SALIDA})', blend=f'math.min(1, {p} * 2.0) * {SALIDA}'), x0=520)
    return K.armar_comp(t, 'CineCaptions VIRAL - select')


# ------------------------------------------------------------------------------------------------------------------ drag
MANO_EM = 0.25          # en la máscara de la mano, 1 em de la palabra = esta fracción del ancho del cuadro (el Transform «Lleva» la escala con EM_W / MANO_EM)
# v5.55: la mano de TEMA3 (2).mp4 medida en em de la palabra, cada forma sobre su caja (x a la derecha, y hacia ABAJO) y con su origen = el centro de la palma
# (el punto por el que agarra). ABIERTA (f_010, 0,43 × 0,60 em): cuatro dedos finos de 0,047 em con rayas negras igual de anchas, el corazón el más alto,
# el pulgar abajo a la izquierda separado de la palma y el fondo redondo. CERRADA (f_015, 0,48 × 0,56 em): dedos cortos de 0,07 em, la punta del pulgar
# asomando a la izquierda y el fondo ovalado y cortado en diagonal abajo a la izquierda (la elipse casa con sus filas medidas al 1-2 %).
# palma = (x0, x1, y0, y1, radio de las esquinas o None = redondo del todo); elipse = (cx, cy, ancho, alto) (en la abierta queda dentro de la palma);
# dedos = (x0, x1, punta) hasta base_dedos; pulgar = (x0, x1, y0, y1); corte = su contorno negro, que lo separa de la palma (va encima de ella).
MANO_ABIERTA = dict(origen=(0.215, 0.4505), palma=(0.0, 0.430, 0.325, 0.601, 0.13), elipse=(0.215, 0.47, 0.30, 0.20), base_dedos=0.47,
                    dedos=[(0.095, 0.142, 0.078), (0.189, 0.237, 0.0), (0.284, 0.331, 0.051), (0.380, 0.430, 0.198)],
                    pulgar=(0.0, 0.047, 0.337, 0.560), corte=(-0.022, 0.094, 0.290, 0.500))
MANO_CERRADA = dict(origen=(0.242, 0.354), palma=(0.077, 0.484, 0.150, 0.400, 0.03), elipse=(0.26, 0.358, 0.46, 0.40), base_dedos=0.25,
                    dedos=[(0.077, 0.145, 0.050), (0.189, 0.257, 0.0), (0.300, 0.373, 0.050), (0.416, 0.484, 0.073)],
                    pulgar=(0.0, 0.045, 0.234, 0.310), corte=(-0.022, 0.067, 0.212, 0.270))
MANO_CONTORNO = 0.022   # el contorno negro (em)


def _piezas_mano(forma):
    """Las 14 piezas de una forma de la mano, en el orden en que se apilan: el contorno negro de la palma, la elipse y los dedos; lo mismo en blanco; el corte del
    pulgar y el pulgar. Cada una (máscara, cx, cy, ancho, alto, CornerRadius) en em desde el origen, y hacia ARRIBA (CornerRadius 1 = el lado corto redondo del todo)."""
    ox, oy = forma['origen']
    O = MANO_CONTORNO

    def caja(x0, x1, y0, y1, radio=None):
        w, h = x1 - x0, y1 - y0
        return ('RectangleMask', (x0 + x1) / 2 - ox, oy - (y0 + y1) / 2, w, h, 1.0 if radio is None else min(1.0, radio / (min(w, h) / 2)))

    def elipse(cx, cy, w, h, crece=0.0):
        return ('EllipseMask', cx - ox, oy - cy, w + 2 * crece, h + 2 * crece, 0.0)
    x0, x1, y0, y1, r = forma['palma']
    base = forma['base_dedos']
    piezas = [caja(x0 - O, x1 + O, y0 - O, y1 + O, None if r is None else r + O), elipse(*forma['elipse'], crece=O)]
    piezas += [caja(a - O, b + O, punta - O, base) for a, b, punta in forma['dedos']]
    piezas += [caja(x0, x1, y0, y1, r), elipse(*forma['elipse'])] + [caja(a, b, punta, base) for a, b, punta in forma['dedos']]
    return piezas + [caja(*forma['corte']), caja(*forma['pulgar'])]


def _mano(nombre, y, cierra='0'):
    """La mano del Drag hecha con rectángulos redondeados (RectangleMask + Background), apilados: debajo en negro y un poco más grandes (el contorno y las rayas
    entre los dedos), encima en blanco, y al final el pulgar con su propio contorno. Devuelve (nodos, nombre de la salida).
    v5.55: la mano de la referencia (MANO_ABIERTA → MANO_CERRADA): `cierra` = expresión 0 → 1 que lleva cada pieza de una forma a la otra."""
    negro, blanco = (0, 0, 0), (0.98, 0.98, 0.98)
    colores = [negro] * 6 + [blanco] * 6 + [negro, blanco]

    def entre(a, b):
        return n(a) if abs(a - b) < 1e-9 else f'({n(a)} + {n(b - a)} * {cierra})'

    def rect(nom, abierta, cerrada, color, yy):
        (tipo, ax, ay, aw, ah, ar), (_t, bx, by, bw, bh, br) = abierta, cerrada
        # el centro va en fracciones del ancho y del alto; el Height de una RectangleMask es fracción del ALTO del cuadro, pero el de una EllipseMask lo es del
        # ANCHO (medido en Resolve 21.1.2: con «× aspecto» la elipse salía 1,78 veces más alta en horizontal y 0,56 veces más baja en vertical)
        k, ky = MANO_EM, MANO_EM * ASPECTO
        kh = ky if tipo == 'RectangleMask' else MANO_EM
        m = K._mascara(tipo, nom + 'M', -220, yy, [
            f'Center = Input {{ Value = {{ {n(0.5 + k * ax)}, {n(0.5 + ky * ay)} }}, Expression = "{K.lua(f"Point(0.5 + {n(k)} * {entre(ax, bx)}, 0.5 + {n(ky)} * {entre(ay, by)})")}", }},',
            f'Width = Input {{ Value = {n(k * aw)}, Expression = "{K.lua(f"{n(k)} * {entre(aw, bw)}")}", }},',
            f'Height = Input {{ Value = {n(kh * ah)}, Expression = "{K.lua(f"{n(kh)} * {entre(ah, bh)}")}", }},']
            + ([f'CornerRadius = Input {{ Value = {n(ar)}, Expression = "{K.lua(entre(ar, br))}", }},'] if tipo == 'RectangleMask' else []))
        return m + K._fondo(nom, -60, yy, color, nom + 'M')
    t, nombres = '', []
    for k, (a, b, color) in enumerate(zip(_piezas_mano(MANO_ABIERTA), _piezas_mano(MANO_CERRADA), colores)):
        nom = f'{nombre}{"N" if color == negro else "B"}{k}'
        t += rect(nom, a, b, color, y + 40 * k)
        nombres.append(nom)
    prev = nombres[0]
    for k, nom in enumerate(nombres[1:], 1):
        t += herramienta('Merge', f'{nombre}U{k}', 80, y + 40 * k, [enlace('Background', prev), enlace('Foreground', nom)])
        prev = f'{nombre}U{k}'
    return t, prev


def comp_drag(tinte=''):
    """Contorno punteado de la palabra; una mano entra abierta por la derecha, la agarra y la ARRASTRA a su sitio (llega desde arriba a la izquierda); ya en su sitio
    se rellena de gris oscuro a blanco (o amarillo / cian / rosa: TINTES_DRAG) con su brillo y la mano se va por DETRÁS de la palabra.
    v5.55: tiempos y recorridos medidos en TEMA3 (2).mp4 (fotogramas de 24 fps): la mano llega en 1-9 (desde 0,78 em a la derecha y 0,24 más abajo), la palabra
    asoma en 8-11, la mano la agarra en 10-13 y la arrastra en 10-19 (0,9 em a la derecha y 0,36 hacia abajo); se rellena en 18-24 y la mano se va en 21-30."""
    color = TINTES_DRAG[tinte]
    T = t24(32)
    llega = _suave(_p(1, 8, T))                   # la mano abierta llega
    cierra = _suave(_p(10, 3, T))                 # … la agarra
    q = _p(10, 9, T)
    mov = f'(0.5 * math.sin({q} * 1.5708) + 0.25 * (1 - math.cos({q} * 3.1416)))'      # … y la arrastra (curva de la referencia: 10, 25, 40, 55, 69, 82, 92, 98 %)
    llena = _p(18, 6, T)                          # ya en su sitio: de gris oscuro a su color (lineal, como la referencia)
    se_va = _p(21, 9, T)                          # la mano se va…
    detras = _p(21, 2, T)                         # … por detrás de la palabra
    G0 = 0.08
    fin = [EFECTO_RELLENO * c for c in color]
    gris = [0.85 * c for c in color]
    # el contorno punteado es el elemento 1 y el relleno el 2: en Text+ el de número menor va encima y en la referencia los guiones se ven SOBRE el relleno gris,
    # hasta que está casi blanco. «CleanIntersections»: sin trazos de más donde la fuente solapa piezas (el palo y la panza de la «D» salían con una raya dentro)
    extra = ['ElementShape1 = Input { Value = 1, },', 'LineStyle1 = Input { Value = Number { Value = 1 }, },', 'JoinStyle1 = Input { Value = 1, },',
             'CleanIntersections1 = Input { Value = 1, },',
             'Thickness1 = Input { Value = Number { Value = 0.013 }, Expression = "Template.Size * 0.046", },',                  # v5.55: guiones gruesos (0,022 → 0,046)
             f'Opacity1 = Input {{ Value = Number {{ Value = 0.95 }}, Expression = "{K.lua(f"0.95 * {_p(8, 10, T)} * math.min(1, (1 - {llena}) * 5)")}", }},']
    extra += ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 0, },',
              f'Opacity2 = Input {{ Value = Number {{ Value = 1 }}, Expression = "{K.lua(f"math.min(1, {llena} * 5)")}", }},']
    extra += [f'{canal}2 = Input {{ Value = Number {{ Value = {n(v)} }}, Expression = "{K.lua(f"{n(G0)} + {n(v - G0)} * {llena}")}", }},'
              for canal, v in zip(('Red', 'Green', 'Blue'), fin)]                    # el relleno va del gris oscuro a su color
    extra += _letra_efecto(3)                     # brillo (3) y sombra (4): aparecen al rellenarse
    exprs = {'Opacity3': f'{n(EFECTO_BRILLO[0])} * {llena}^2', 'Opacity4': f'{n(EFECTO_SOMBRA[0])} * {llena}'}
    extra = [l if not any(l.startswith(k + ' ') for k in exprs) else
             f'{next(k for k in exprs if l.startswith(k + " "))} = Input {{ Value = Number {{ Value = 0 }}, Expression = "{K.lua(exprs[next(k for k in exprs if l.startswith(k + " "))])}", }},' for l in extra]
    t = texto_plus('Template', -220, 40, 'Drag', EFECTO[0], EFECTO[1], 0.30, color=gris, esp=0.97, extra=extra)
    # la medida de la palabra (el Template está transparente hasta que asoma): un Text+ igual que no se compone
    ligado = 'StyledText = Input { Value = "Drag", Expression = "Template.StyledText", },'
    t += texto_plus('Medida', -220, 120, 'Drag', EFECTO[0], EFECTO[1], 0.30, esp=0.97, expr={'Size': 'Template.Size'}).replace('StyledText = Input { Value = "Drag", },', ligado)
    # la palabra llega arrastrada (desde arriba a la izquierda) hasta su sitio
    dx = f'(-0.90 * {EM_W} * (1 - {mov}))'
    dy = f'(0.36 * {EM_H} * (1 - {mov}))'
    t += herramienta('Transform', 'Arrastre', -60, 40, [enlace('Input', 'Template'),
                                                       f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + {K.lua(dx)}, 0.5 + {K.lua(dy)})", }},'])
    nodos, mano_out = _mano('Mano', 300, cierra)
    t += nodos
    dw = 'Medida.Output.DataWindow'
    cx = f'({dw} and (({dw}[1] + {dw}[3]) / 2 / {ANCHO_CUADRO}) or 0.5)'
    cy = f'({dw} and (({dw}[2] + {dw}[4]) / 2 / {ALTO_CUADRO}) or 0.5)'
    # la mano: llega a su punto de agarre (el centro de la palabra, un poco arriba) desde la derecha y algo más abajo, y luego va con la palabra
    x = f'{cx} + {dx} + {EM_W} * 0.78 * (1 - {llega})'
    y = f'{cy} + {EM_H} * 0.05 + {dy} - {EM_H} * 0.24 * (1 - {llega})'
    aparece = f'{_p(1, 6, T)} * (1 - {se_va})'
    t += herramienta('Transform', 'Lleva', 40, 300, [
        enlace('Input', mano_out),
        'Pivot = Input { Value = { 0.5, 0.5 }, },',
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point({K.lua(x)} , {K.lua(y)})", }},',
        f'Size = Input {{ Value = 1, Expression = "{K.lua(f"{EM_W} / {n(MANO_EM)}")}", }},'])
    t += vacio('VacioMano', 160, 380)
    t += herramienta('Merge', 'ManoEncima', 160, 300, [enlace('Background', 'VacioMano'), enlace('Foreground', 'Lleva'),
                                                       f'Blend = Input {{ Value = 0, Expression = "{K.lua(f"{aparece} * (1 - {detras})")}", }},'])
    t += herramienta('Merge', 'ManoDebajo', 160, 220, [enlace('Background', 'VacioMano'), enlace('Foreground', 'Lleva'),
                                                       f'Blend = Input {{ Value = 0, Expression = "{K.lua(f"{aparece} * {detras}")}", }},'])
    t += herramienta('Merge', 'M0', 280, 40, [enlace('Background', 'ManoDebajo'), enlace('Foreground', 'Arrastre')])
    t += herramienta('Merge', 'M1', 280, 120, [enlace('Background', 'M0'), enlace('Foreground', 'ManoEncima')])
    p = _p(0, 6)
    t += cadena('M1', dict(size=f'(0.97 + 0.03 * {_suave(p)}) * (0.92 + 0.08 * {SALIDA})', blend=f'math.min(1, {p} * 2.0) * {SALIDA}'), x0=420)
    return K.armar_comp(t, 'CineCaptions VIRAL - drag')


# ------------------------------------------------------------------------------------------------------------------ el catálogo
def todos(formato='v'):
    """{nombre del clip: texto de la comp} para el formato 'v' (vertical) o 'h' (horizontal). Los tamaños (Size) son los de partida: la app fija el real por clip."""
    configurar(formato)
    import viral_captions as VC
    comps = {'v fina': comp_fina(), 'v negrita': comp_negrita()}
    for base, hacer in (('v shatter', comp_shatter), ('v select', comp_select), ('v drag', comp_drag)):
        for color in VC.COLORES[base]:                       # cada efecto en sus 4 colores: 'v shatter', 'v shatter rosa', …
            comps[base + (' ' + color if color else '')] = hacer(color)
    return comps


if __name__ == '__main__':
    for nombre in todos():
        print(nombre)
