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
v5.57 («Sí, en los 6»): cada comp va dentro del macro «CineCaptions» de macro_kinetic, como el Tema 1: el Inspector enseña los controles de Luxe Slide con DROP
SHADOW / GLOW apagados y solo el banner. Las copias del texto (Medida, BrilloTxt, Caja) siguen también su Tracking, y el relleno del drag sigue al «Color».
"""
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import kinetic_comps as K
import kinetic_elementos as E
import macro_kinetic as MK
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
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - fina')


def comp_negrita():
    color_b, op_b, blur_b = NEGRITA_BRILLO
    extra = (['Type1 = Input { Value = 2, },', f'ShadingGradient1 = Input {{ Value = {degradado(NEGRITA_DEGRADADO)}, }},'] + E._sombra(2, 0.85, -0.006, 9)
             + E._contorno(3, 0.013, 0.95) + E._sombra(4, op_b, 0.0, blur_b, color=color_b) + ['ElementShape4 = Input { Value = 0, },']   # (4: forma de LETRA, no la caja)
             + _inclinar(1, 2, 3, 4))
    t = texto_plus('Template', -220, 40, 'negrita', NEGRITA[0], NEGRITA[1], 0.16, color=(1, 1, 1), esp=0.99, extra=extra)
    p = _p(0, 9)
    t += cadena('Template', dict(dx=f'(1 - {_suave(p)}) * (-0.018)', size=f'(0.82 + 0.18 * {_rebote(p)}) * (0.9 + 0.1 * {SALIDA})', blend=f'math.min(1, {p} * 2.4) * {SALIDA}'))
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - negrita')


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
GRIS_DRAG = 0.85                            # el contorno punteado del drag (y el gris de antes de rellenarse) = 0,85 × su tinte


def _copia(nombre, y, texto, color=(1, 1, 1), extra=None, fuente=None):
    """v5.57: una copia del Template (Medida, BrilloTxt, Caja) que sigue su texto, su Size y su Tracking (CharacterSpacing): con el «Tracking» del Inspector
    (macro_kinetic) la medida de la palabra, el brillo y la caja siguen a las letras. La letra NO: con Font/Style por expresión la comp salía negra."""
    fuente = fuente or EFECTO
    t = texto_plus(nombre, -220, y, texto, fuente[0], fuente[1], 0.30, color=color, esp=0.97, extra=extra, expr={'Size': 'Template.Size'})
    for campo, valor in (('StyledText', f'"{texto}"'), ('CharacterSpacing', '0.97')):
        viejo = f'{campo} = Input {{ Value = {valor}, }},'
        if viejo not in t:
            raise ValueError(f'viral_elementos: la copia {nombre} no trae «{viejo}»')
        t = t.replace(viejo, f'{campo} = Input {{ Value = {valor}, Expression = "Template.{campo}", }},', 1)
    return t


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
    t += _copia('Medida', 120, 'Shatter')
    dw = 'Medida.Output.DataWindow'
    WW = f'(({dw} and (({dw}[3] - {dw}[1]) / {ANCHO_CUADRO})) or 0.4)'                # el ancho de la palabra (fracción del ancho del cuadro)
    T = tt(28)
    # --- brillo fijo: una copia blanca del texto, translúcida, solo en la mitad de arriba de las letras
    t += _copia('BrilloTxt', 320, 'Shatter', color=P['brillo'])
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
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - shatter')


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
    t += _copia('Medida', 120, 'Select')
    rojo = CAJAS_SELECT[color_caja]
    borde = ['Enabled1 = Input { Value = 0, },', 'Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 3, },', 'Level2 = Input { Value = Number { Value = 0 }, },',
             'LineStyle2 = Input { Value = Number { Value = 1 }, },', 'JoinStyle2 = Input { Value = 1, },',
             'Thickness2 = Input { Value = Number { Value = 0.04 }, Expression = "Template.Size * 0.135", },',              # v5.55: guiones gruesos (0,075 → 0,135, ~0,05 em)
             'ExtendHorizontal2 = Input { Value = Number { Value = 0.03 }, Expression = "Template.Size * 0.1", },', 'ExtendVertical2 = Input { Value = Number { Value = 0.02 }, Expression = "Template.Size * 0.07", },',
             f'Red2 = Input {{ Value = Number {{ Value = {n(rojo[0])} }}, }},', f'Green2 = Input {{ Value = Number {{ Value = {n(rojo[1])} }}, }},', f'Blue2 = Input {{ Value = Number {{ Value = {n(rojo[2])} }}, }},']
    t += _copia('Caja', 200, 'Select', extra=borde)
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
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - select')


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
    gris = [GRIS_DRAG * c for c in color]
    # el contorno punteado es el elemento 1 y el relleno el 2: en Text+ el de número menor va encima y en la referencia los guiones se ven SOBRE el relleno gris,
    # hasta que está casi blanco. «CleanIntersections»: sin trazos de más donde la fuente solapa piezas (el palo y la panza de la «D» salían con una raya dentro)
    extra = ['ElementShape1 = Input { Value = 1, },', 'LineStyle1 = Input { Value = Number { Value = 1 }, },', 'JoinStyle1 = Input { Value = 1, },',
             'CleanIntersections1 = Input { Value = 1, },',
             'Thickness1 = Input { Value = Number { Value = 0.013 }, Expression = "Template.Size * 0.046", },',                  # v5.55: guiones gruesos (0,022 → 0,046)
             f'Opacity1 = Input {{ Value = Number {{ Value = 0.95 }}, Expression = "{K.lua(f"0.95 * {_p(8, 10, T)} * math.min(1, (1 - {llena}) * 5)")}", }},']
    extra += ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 0, },',
              f'Opacity2 = Input {{ Value = Number {{ Value = 1 }}, Expression = "{K.lua(f"math.min(1, {llena} * 5)")}", }},']
    # el relleno va del gris oscuro a su color. v5.57: su color sale del «Color» del Inspector (Red1, el del contorno: × EFECTO_RELLENO / GRIS_DRAG; con el
    # de fábrica, el de siempre; math.min: con un «Color» blanco no pasa de 1). pack_personalizado.color_viral lee esa razón de la expresión
    extra += [f'{canal}2 = Input {{ Value = Number {{ Value = {n(v)} }}, Expression = "{K.lua(f"{n(G0)} + (math.min(1, Template.{canal}1 / {n(GRIS_DRAG)} * {n(EFECTO_RELLENO)}) - {n(G0)}) * {llena}")}", }},'
              for canal, v in zip(('Red', 'Green', 'Blue'), fin)]
    extra += _letra_efecto(3)                     # brillo (3) y sombra (4): aparecen al rellenarse
    exprs = {'Opacity3': f'{n(EFECTO_BRILLO[0])} * {llena}^2', 'Opacity4': f'{n(EFECTO_SOMBRA[0])} * {llena}'}
    extra = [l if not any(l.startswith(k + ' ') for k in exprs) else
             f'{next(k for k in exprs if l.startswith(k + " "))} = Input {{ Value = Number {{ Value = 0 }}, Expression = "{K.lua(exprs[next(k for k in exprs if l.startswith(k + " "))])}", }},' for l in extra]
    t = texto_plus('Template', -220, 40, 'Drag', EFECTO[0], EFECTO[1], 0.30, color=gris, esp=0.97, extra=extra)
    # la medida de la palabra (el Template está transparente hasta que asoma): un Text+ igual que no se compone
    t += _copia('Medida', 120, 'Drag')
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
    return K.armar_comp(MK.envolver(t, color='solo'), 'CineCaptions VIRAL - drag')     # (el degradado solo pintaría el contorno punteado)


# ------------------------------------------------------------------------------------------------------------------ v5.75: relieve, corte y shine
# Pedido del usuario (2026-11-06): «crea este tal cual, exactamente igual» con Downloads/EJEMPLO 2.mp4 (Shatter rosa → «v corte») y EJEMPLO3.mp4
# (shine → «v shine»), y «el ejemplo es volumétrico, tipo 3D en 2D». Medidas en scratchpad/crea/efectos/MEDIDAS.md (1920×1080 a 24 fps).
# Probado en Resolve (laboratorio «v lab …»): el Follower de Text+ gira cada letra en Y con una expresión de tiempo, y un CustomTool ilumina la
# forma desenfocada de la letra (bisel 2D de verdad; Merge con ApplyMode HardLight + Atop dejaba la letra gris: la luz se calcula DENTRO del Custom).


def _curva(puntos, t):
    """Expresión de una curva de TRAMOS RECTOS por `puntos` [(t, v)] en la variable `t` (plana antes del primero y después del último): suma de
    «bisagras» math.max(0, t - ti) (sin tablas ni funciones de Lua: lo que Fusion evalúa seguro)."""
    puntos = sorted(puntos)
    t0, v0 = puntos[0]
    pend = [(puntos[i + 1][1] - puntos[i][1]) / (puntos[i + 1][0] - puntos[i][0]) for i in range(len(puntos) - 1)] + [0.0]
    partes = [n(v0)]
    previa = 0.0
    for (ti, _v), s in zip(puntos, pend):
        c = s - previa
        if abs(c) > 1e-9:
            partes.append(f'{n(c)} * math.max(0, ({t}) - {n(ti)})')
        previa = s
    return '(' + ' + '.join(partes) + ')'


def _relieve(origen, prefijo, x, y, luz, sombra, blur_em, fuerza, k_luz=1.0, k_sombra=1.0, signo=1, cara=None, numeros=None):
    """Bisel 2D (volumen) sobre la imagen `origen` (letra ya de color, alfa premultiplicado): la ALTURA es su alfa desenfocado (`blur_em` em) y la luz
    llega de arriba a la izquierda: donde da, el color va hacia `luz`; donde no, hacia `sombra` (solo dentro de la letra).
    `cara`: (r, g, b) expresiones del color de la cara (sin premultiplicar) en lugar del de `origen`; `numeros`: {2: expr, ...} -> NumberIn2... (n2, ...).
    Dos Custom: «Pend» calcula una vez por píxel la luz (R) y la sombra (G), topadas a 1; «Luz» colorea. Devuelve (nodos, nombre del último)."""
    radio = f'({n(blur_em)} * {EM_W} * {ANCHO_CUADRO})'                 # en píxeles del cuadro: sigue al tamaño de la palabra
    t = herramienta('Blur', prefijo + 'Alto', x, y + 80, [enlace('Input', origen), 'XBlurSize = Input { Value = 8, Expression = "%s", },' % K.lua(radio),
                                                          'Filter = Input { Value = FuID { "Gaussian" }, },'])
    # pendiente del alfa con 1,5 px de paso. Sin variables intermedias (i1 no salía: ronda 1) ni min/max: las partes y los topes, con abs
    g = n(-fuerza * signo * 0.7071)        # (en Fusion la y crece hacia ARRIBA: sin el signo la luz salía abajo a la derecha; medido en la ronda 7)
    s = f'({g} * n1 * ((geta1b(x - s1, y) - geta1b(x + s1, y)) - (geta1b(x, y - s1) - geta1b(x, y + s1))))'
    pos, neg = f'(({s} + abs({s})) / 2)', f'((abs({s}) - {s}) / 2)'

    def tope(p):
        return f'(({p} + 1 - abs({p} - 1)) / 2)'
    t += herramienta('Custom', prefijo + 'Pend', x + 140, y + 80, [
        enlace('Image1', prefijo + 'Alto'), 'Setup1 = Input { Value = "1.5 / w", },', 'NumberIn1 = Input { Value = 10, Expression = "%s", },' % K.lua(radio),
        f'RedExpression = Input {{ Value = "{K.lua(tope(pos))}", }},', f'GreenExpression = Input {{ Value = "{K.lua(tope(neg))}", }},',
        'BlueExpression = Input { Value = "0", },', 'AlphaExpression = Input { Value = "1", },'])
    kl, ks = (k if isinstance(k, str) else n(k) for k in (k_luz, k_sombra))
    canal = []
    for i, (c, lv, sv) in enumerate(zip('rgb', luz, sombra)):
        base = f'{c}2' if cara is None else f'(({cara[i]}) * a2)'
        canal.append(f'{base} + r1 * {kl} * ({n(lv)} * a2 - {base}) - g1 * {ks} * ({base} - {n(sv)} * a2)')
    nums = [f'NumberIn{k} = Input {{ Value = 0, Expression = "{K.lua(e)}", }},' for k, e in sorted((numeros or {}).items())]
    t += herramienta('Custom', prefijo + 'Luz', x + 280, y, [
        enlace('Image1', prefijo + 'Pend'), enlace('Image2', origen)] + nums + [
        f'RedExpression = Input {{ Value = "{K.lua(canal[0])}", }},', f'GreenExpression = Input {{ Value = "{K.lua(canal[1])}", }},',
        f'BlueExpression = Input {{ Value = "{K.lua(canal[2])}", }},', 'AlphaExpression = Input { Value = "a2", },'])
    return t, prefijo + 'Luz'


CORTE_BASE = (0.992, 0.120, 0.820)          # #FD1FD1: el magenta de la entrada (interior medido #FD37D1 con la luz encima)
CORTE_LUZ_CENTRO = (1.0, 0.86, 0.96)       # el claro del centro (#FBA5E9 medido con la luz encima)
CORTE_BISEL = (0.706, 0.071, 0.541)        # #B4128A: el filo oscuro
CORTE_BRILLO, CORTE_SOMBRA = (1.0, 0.95, 0.99), (0.62, 0.06, 0.46)
# Trozos (em; y hacia ARRIBA), medidos en el cuadro 40 con em = 388 px: (dx, dy). La curva g(T) = 0,37 + 0,193·ln(T − 14) los separa desde el 15.
CORTE_TROZOS = {'AI': (-0.222, 0.036), 'MI': (-0.443, 0.0), 'BI': (-0.103, -0.031), 'AD': (0.240, 0.0), 'MD': (0.376, -0.010), 'BD': (0.149, -0.067)}
CORTE_ARRIBA = (0.027, 0.7)                 # el corte de arriba: altura (em sobre el centro) y giro (grados): de +0,005 em a la izquierda a +0,05 a la derecha
CORTE_ABAJO = (-0.082, 0.0)
CORTE_GRIETA = (0.046, 4.0)                 # la grieta: x (fracción del ANCHO de la palabra desde su centro) y giro


def comp_corte():
    """EJEMPLO 2 (Shatter rosa) tal cual: entra fundiéndose desde un magenta oscuro (c3-c9) mientras se desliza ~0,064 em a la izquierda y vuelve
    0,031 em (c4-c14); la luz del centro sube en c7-c13; en el c15 se parte en 6 trozos (arriba / franja / abajo a cada lado de la grieta) que se
    siguen separando: g = 0,37 + 0,193·ln(T − 14). Relieve 2D con luz de arriba a la izquierda y filos claros en los cortes."""
    T = t24(32)
    extra = ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', 'Thickness2 = Input { Value = Number { Value = 0.005 }, },',
             f'Red2 = Input {{ Value = Number {{ Value = {n(CORTE_BISEL[0])} }}, }},', f'Green2 = Input {{ Value = Number {{ Value = {n(CORTE_BISEL[1])} }}, }},',
             f'Blue2 = Input {{ Value = Number {{ Value = {n(CORTE_BISEL[2])} }}, }},', 'Opacity2 = Input { Value = Number { Value = 0.85 }, },']
    t = texto_plus('Template', -220, 40, 'Corte', EFECTO[0], EFECTO[1], 0.31, color=CORTE_BASE, esp=0.97, extra=extra)
    t += _copia('Medida', 120, 'Corte')
    dw = 'Medida.Output.DataWindow'
    WW = f'(({dw} and (({dw}[3] - {dw}[1]) / {ANCHO_CUADRO})) or 0.4)'
    # --- la luz del centro (claro en el medio, magenta en los bordes): un fondo claro con una máscara suave, solo sobre las letras
    t += K._mascara('RectangleMask', 'MLuz', -220, 200, [
        'Center = Input { Value = { 0.5, 0.5 }, },', f'Width = Input {{ Value = 0.2, Expression = "0.50 * {K.lua(WW)}", }},',
        'Height = Input { Value = 3, },', f'SoftEdge = Input {{ Value = 0.1, Expression = "0.50 * {K.lua(WW)}", }},', 'CornerRadius = Input { Value = 0, },'])
    t += K._fondo('LuzFondo', -60, 200, CORTE_LUZ_CENTRO, 'MLuz')
    luz = f'math.min(1, math.max(0, (({T}) - 7) / 5))'
    t += herramienta('Merge', 'Luz', 60, 120, [enlace('Background', 'Template'), enlace('Foreground', 'LuzFondo'), 'Operator = Input { Value = FuID { "Atop" }, },',
                                                f'Blend = Input {{ Value = 0, Expression = "{K.lua(f"1.0 * {luz}")}", }},'])
    nodos, relieve = _relieve('Luz', 'Rel', 60, 280, CORTE_BRILLO, CORTE_SOMBRA, 0.009, 1.4, k_luz='(0.5 + 0.45 * n4)', k_sombra=0.85,
                             numeros={4: luz})            # (el filo claro crece con la luz del centro: en c9 la referencia apenas brilla)
    t += nodos
    # --- los trozos: grieta (izq/der) × corte de arriba × corte de abajo; cada uno se RECORTA antes de moverse
    t += vacio('VacioP', 420, 600)
    LARGO = 4.0
    cuenta = {'n': 0, 'y': 600}

    def semiplano(px, py, ang, lado):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        nx, ny = {'izq': (-c, -s), 'der': (c, s), 'arr': (-s, c), 'aba': (s, -c)}[lado]
        cuenta['n'] += 1
        nombre = f'Cp{cuenta["n"]}'
        nodos = K._mascara('RectangleMask', nombre, -220, cuenta['y'], [
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + ({K.lua(px)}) + {n(nx * LARGO / 2)}, 0.5 + (({K.lua(py)}) + {n(ny * LARGO / 2)}) * {n(ASPECTO)})", }},',
            f'Width = Input {{ Value = {n(LARGO)}, }},', f'Height = Input {{ Value = {n(LARGO * ASPECTO)}, }},', f'Angle = Input {{ Value = {n(ang)}, }},',
            'CornerRadius = Input { Value = 0, },'])
        cuenta['y'] += 80
        return nombre, nodos

    def recorta(origen, mascara, nombre):
        return herramienta('Merge', nombre, 140, cuenta['y'] - 80, [enlace('Background', 'VacioP'), enlace('Foreground', origen),
                                                                     f'EffectMask = Input {{ SourceOp = "{mascara}", Source = "Mask" }},'])
    gx = f'({n(CORTE_GRIETA[0])} * {WW})'
    ya, aa = f'({n(CORTE_ARRIBA[0])} * {EM_W})', CORTE_ARRIBA[1]
    yb, ab = f'({n(CORTE_ABAJO[0])} * {EM_W})', CORTE_ABAJO[1]
    hojas = {}
    for lado, L in (('izq', 'I'), ('der', 'D')):
        m, nd = semiplano(gx, '0', 90 + CORTE_GRIETA[1] - 90, lado)
        t += nd + recorta(relieve, m, 'Lado' + L)
        m, nd = semiplano('0', ya, aa, 'arr')
        t += nd + recorta('Lado' + L, m, 'Trozo' + 'A' + L)
        hojas['A' + L] = 'Trozo' + 'A' + L
        m, nd = semiplano('0', ya, aa, 'aba')
        t += nd + recorta('Lado' + L, m, 'Resto' + L)
        m, nd = semiplano('0', yb, ab, 'arr')
        t += nd + recorta('Resto' + L, m, 'Trozo' + 'M' + L)
        hojas['M' + L] = 'Trozo' + 'M' + L
        m, nd = semiplano('0', yb, ab, 'aba')
        t += nd + recorta('Resto' + L, m, 'Trozo' + 'B' + L)
        hojas['B' + L] = 'Trozo' + 'B' + L
    # filos claros: una franja blanca finísima justo debajo de cada corte, solo sobre las letras de la franja y de abajo
    for k, (corte_y, ang) in enumerate(((ya, aa), (yb, ab))):
        t += K._mascara('RectangleMask', f'MFilo{k}', -220, cuenta['y'], [
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5, 0.5 + (({K.lua(corte_y)}) - 0.006 * {K.lua(EM_W)}) * {n(ASPECTO)})", }},',
            'Width = Input { Value = 3, },', f'Height = Input {{ Value = 0.01, Expression = "0.010 * {K.lua(EM_H)}", }},', f'Angle = Input {{ Value = {n(ang)}, }},',
            'SoftEdge = Input { Value = 0.0015, },', 'CornerRadius = Input { Value = 0, },'])
        t += K._fondo(f'Filo{k}', -60, cuenta['y'], (1.0, 0.96, 0.99), f'MFilo{k}')
        cuenta['y'] += 80
    roto = f'(({T}) >= 15 and 1 or 0)'
    g = f'(({roto}) * (0.37 + 0.193 * math.log(math.max(1, ({T}) - 14))))'
    salidas = []
    for k, (hoja, nodo) in enumerate(hojas.items()):
        origen = nodo
        if hoja[0] in 'MB':                                                  # el filo del corte de encima de este trozo
            filo = 'Filo0' if hoja[0] == 'M' else 'Filo1'
            t += herramienta('Merge', 'F' + hoja, 260, 600 + 80 * k, [enlace('Background', nodo), enlace('Foreground', filo), 'Operator = Input { Value = FuID { "Atop" }, },',
                                                                      f'Blend = Input {{ Value = 0, Expression = "{K.lua(f"0.85 * {roto}")}", }},'])
            origen = 'F' + hoja
        dx, dy = CORTE_TROZOS[hoja]
        t += herramienta('Transform', 'T' + hoja, 380, 600 + 80 * k, [
            enlace('Input', origen),
            f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point(0.5 + {n(dx)} * {K.lua(EM_W)} * {K.lua(g)}, 0.5 + {n(dy)} * {K.lua(EM_H)} * {K.lua(g)})", }},'])
        salidas.append('T' + hoja)
    prev = salidas[0]
    for k, nom in enumerate(salidas[1:], 1):
        t += herramienta('Merge', f'U{k}', 520, 600 + 80 * k, [enlace('Background', prev), enlace('Foreground', nom)])
        prev = f'U{k}'
    t += herramienta('Merge', 'Entera', 640, 480, [enlace('Background', 'VacioP'), enlace('Foreground', relieve),
                                                   f'Blend = Input {{ Value = 1, Expression = "{K.lua(f"1 - {roto}")}", }},'])
    t += herramienta('Merge', 'Rota', 640, 560, [enlace('Background', 'Entera'), enlace('Foreground', prev), f'Blend = Input {{ Value = 0, Expression = "{K.lua(roto)}", }},'])
    desliza = _curva([(4, 0), (10, -0.064), (14, -0.033), (16, -0.033)], T)
    entra = f'math.min(1, math.max(0, (({T}) - 3) / 6))'
    t += cadena('Rota', dict(dx=f'{desliza} * {EM_W}', size=f'(0.92 + 0.08 * {SALIDA})', blend=f'(3 - 2 * {entra}) * {entra} * {entra} * {SALIDA}'), x0=800)
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - corte')


SHINE_BASE = (0.992, 0.30, 0.0)             # (solo da la forma: el color de la cara lo pone SHINE_CARA)
# La CARA (medida en EJEMPLO3, c22): naranja #FD4D00 con dos franjas amarillas #FDBA08 inclinadas «/» a ±0,23 del ANCHO de la palabra
# (anchura a media altura 0,2) que suben de intensidad en c3-c14; filo fino: claro amarillo arriba a la izquierda, rojo abajo a la derecha.
SHINE_CARA = ((0.992, 0.30, 0.0), (0.992, 0.73, 0.03))
SHINE_FRANJAS = [(3, 0.1), (7, 0.25), (9, 0.45), (14, 1.0)]
SHINE_LUZ, SHINE_SOMBRA = (1.0, 0.85, 0.25), (0.85, 0.16, 0.0)
SHINE_FILO = (7, 7)                          # el filo claro entra en c7-c14 (antes de c7 la referencia no tiene brillos: claro #FD8902)
# La palabra (em; x a la derecha, y hacia ARRIBA) por fotogramas de 24 fps, medida en EJEMPLO3 (centro de la tinta respecto al de reposo, giro, tamaño)
SHINE_X = [(1, -0.366), (2, -0.367), (3, -0.243), (4, -0.028), (5, 0.120), (6, 0.096), (7, 0.112), (8, 0.067), (9, 0.030), (10, 0.005), (11, -0.015), (12, -0.034),
           (13, -0.047), (14, -0.052), (15, -0.050), (16, -0.044), (17, -0.033), (18, -0.024), (19, -0.015), (20, -0.008), (21, -0.002), (22, 0.0)]
SHINE_Y = [(1, 0.465), (2, 0.339), (3, 0.212), (4, 0.084), (5, 0.0), (6, -0.073), (7, -0.092), (8, -0.066), (9, -0.014), (10, 0.029), (11, 0.060), (12, 0.078),
           (13, 0.089), (14, 0.092), (15, 0.085), (16, 0.072), (17, 0.055), (18, 0.038), (19, 0.022), (20, 0.011), (21, 0.004), (22, 0.0)]
SHINE_GIRO = [(1, 38.5), (2, 38.5), (3, 33.5), (4, 17.2), (5, 15.6), (6, 5.2), (7, -2.8), (8, -6.1), (9, -5.3), (10, -4.0), (11, -2.8), (12, -1.9), (13, -1.1),
              (14, -0.4), (15, 0.3), (16, 0.7), (17, 0.8), (18, 0.8), (19, 0.5), (20, 0.1), (21, 0.0)]
SHINE_TAM = [(0, 0.30), (2, 0.36), (3, 0.47), (4, 0.63), (5, 0.78), (6, 0.86), (7, 0.93), (8, 0.97), (9, 0.997), (10, 1.011), (11, 1.013), (12, 1.010),
             (13, 1.006), (14, 1.004), (16, 1.003), (22, 1.0)]
# Cada letra (fotogramas de 24 fps; la «s» empieza ya abierta en c1 y cada letra va 1,6 fotogramas detrás): se abre en Y, se endereza en Z y deja de
# verse oscura. El Follower SOLO reparte el retraso con FOTOGRAMAS CLAVE y DelayType = 1 («entre cada letra»; con 0 no hay retraso; Order 0 = de
# izquierda a derecha, 1 = al revés, 2 = desde el centro: laboratorio, rondas 3-6). Un TimeStretcher le da el tiempo en fotogramas de 24 fps (t24) MÁS
# SHINE_ADELANTO, para que dure lo mismo a 24, 30 o 60 fps y las claves no tengan tiempos negativos.
SHINE_LETRA_Y = [(-3.5, 90), (-2, 70), (-1, 48), (0, 30), (1, 16), (2, 6), (3, 0), (4, -3), (5, -2), (7, 0)]
SHINE_LETRA_Z = [(-3.5, 22), (-1, 10), (1.5, -3), (3, -2), (5, 0)]
SHINE_LETRA_OP = [(-3.5, 0.1), (-2, 0.3), (-1, 0.55), (0, 0.8), (1, 1.0)]
SHINE_LETRA_ESP = [(-3.5, 0.66), (-2, 0.74), (-1, 0.87), (0, 0.95), (1, 0.985), (2, 0.996), (3, 1.0)]
SHINE_RETRASO = 1.6
SHINE_ADELANTO = 4.0


def _spline(nombre, puntos):
    """BezierSpline lineal con los `puntos` [(fotograma, valor)]."""
    cuerpo = ', '.join(f'[{n(f)}] = {{ {n(v)}, Flags = {{ Linear = true }} }}' for f, v in puntos)
    return f'\t\t{nombre} = BezierSpline {{\n\t\t\tSplineColor = {{ Red = 240, Green = 120, Blue = 20 }},\n\t\t\tKeyFrames = {{ {cuerpo} }}\n\t\t}},\n'


def comp_shine():
    """EJEMPLO3 (shine) tal cual: letras naranjas con VOLUMEN que se abren una tras otra (Follower: giro en Y y algo en Z, 1 fotograma de retraso)
    mientras la palabra llega desde arriba a la izquierda girada +38°, crece, se pasa abajo a la derecha, vuelve y se queda quieta en el c22.
    Relieve 2D ancho (luz amarilla, sombra rojiza) y un brillo naranja alrededor."""
    T = t24(26)
    t = texto_plus('Template', -220, 40, 'Shine', EFECTO[0], EFECTO[1], 0.31, color=SHINE_BASE, esp=0.97, extra=['Opacity1 = Input { Value = 0, },'])
    t += herramienta('StyledTextFollower', 'Seguidor', -220, 120, [
        'Text = Input { Value = StyledText { Value = "Shine" }, Expression = "Template.StyledText", },',
        'Order = Input { Value = 0, },', 'DelayType = Input { Value = 1, },', f'Delay = Input {{ Value = {n(SHINE_RETRASO)}, }},',
        'SelectTransform = Input { Value = 0, },',
        'TransformRotation = Input { Value = 1, },',
        'CharacterAngleY = Input { SourceOp = "SeguidorGiroY", Source = "Value", },',
        'CharacterAngleZ = Input { SourceOp = "SeguidorGiroZ", Source = "Value", },',
        'Opacity1 = Input { SourceOp = "SeguidorOpacidad", Source = "Value", },',
        'CharacterSpacing = Input { SourceOp = "SeguidorEspacio", Source = "Value", },'])     # de canto se ve oscura (como la referencia)
    t += ''.join(_spline(nombre, [(f + SHINE_ADELANTO, v) for f, v in puntos])
                 for nombre, puntos in (('SeguidorGiroY', SHINE_LETRA_Y), ('SeguidorGiroZ', SHINE_LETRA_Z), ('SeguidorOpacidad', SHINE_LETRA_OP),
                                         ('SeguidorEspacio', SHINE_LETRA_ESP)))
    letras = texto_plus('Letras', -60, 120, 'Shine', EFECTO[0], EFECTO[1], 0.31, color=SHINE_BASE, esp=0.97, expr={'Size': 'Template.Size'})
    letras = letras.replace('StyledText = Input { Value = "Shine", },', 'StyledText = Input { SourceOp = "Seguidor", Source = "StyledText", },')
    letras = letras.replace('CharacterSpacing = Input { Value = 0.97, },', 'CharacterSpacing = Input { Value = 0.97, Expression = "Template.CharacterSpacing", },')
    t += letras
    # el tiempo de las letras en fotogramas de 24 fps (las claves del Follower son de 24 fps)
    t += herramienta('TimeStretcher', 'Tiempo', 60, 120, [enlace('Input', 'Letras'), f'SourceTime = Input {{ Value = 0, Expression = "{K.lua(f"({T}) + {n(SHINE_ADELANTO)}")}", }},',
                                                          'InterpolateBetweenFrames = Input { Value = 0, },'])
    t += _copia('Medida', 280, 'Shine')
    dw = 'Medida.Output.DataWindow'
    WW = f'(({dw} and (({dw}[3] - {dw}[1]) / {ANCHO_CUADRO})) or 0.4)'
    u = '(((x - 0.5) * w - 0.57 * (y - 0.5) * h) / (n2 * w))'          # a lo ancho de la palabra, inclinado «/»
    q = f'(abs(abs({u}) - 0.23) / 0.1)'
    franja = f'(n3 / (1 + {q} * {q} * {q} * {q}))'
    (o, a_) = SHINE_CARA
    cara = tuple(f'({n(o[i])} + {n(a_[i] - o[i])} * {franja})' for i in range(3))
    nodos, relieve = _relieve('Tiempo', 'Rel', 60, 200, SHINE_LUZ, SHINE_SOMBRA, 0.007, 1.0, k_luz='(0.15 + 0.85 * n4)', k_sombra=0.6, cara=cara,
                              numeros={2: WW, 3: _curva(SHINE_FRANJAS, T), 4: f'math.min(1, math.max(0, (({T}) - {SHINE_FILO[0]}) / {SHINE_FILO[1]}))'})
    t += nodos
    # el brillo naranja alrededor: la letra iluminada desenfocada, debajo
    t += herramienta('Blur', 'Halo', 300, 280, [enlace('Input', relieve), 'XBlurSize = Input { Value = 20, Expression = "%s", },' % K.lua(f'0.03 * {EM_W} * {ANCHO_CUADRO}'),
                                                'Filter = Input { Value = FuID { "Gaussian" }, },'])
    t += vacio('VacioH', 300, 360)
    t += herramienta('Merge', 'HaloOp', 420, 280, [enlace('Background', 'VacioH'), enlace('Foreground', 'Halo'), 'Blend = Input { Value = 0.15, },'])
    t += herramienta('Merge', 'ConHalo', 540, 200, [enlace('Background', 'HaloOp'), enlace('Foreground', relieve)])
    entra = f'math.min(1, math.max(0, ({T}) / 1.5))'
    t += cadena('ConHalo', dict(dx=f'{_curva(SHINE_X, T)} * {EM_W}', dy=f'{_curva(SHINE_Y, T)} * {EM_H}', size=f'{_curva(SHINE_TAM, T)} * (0.92 + 0.08 * {SALIDA})',
                                ang=_curva(SHINE_GIRO, T), blend=f'{entra} * {SALIDA}'), x0=700)
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - shine')


# «Resaltado» (v5.75): la selección de texto del iPhone, de la imagen del usuario («hello» con «he» seleccionado), medida en em (Inter: el centro del
# Text+ es el de las mayúsculas). Caja azul #0500F5 (v5.75: más fina a pedido del usuario: de 0,08 em sobre el ascendente a 0,17 em bajo la base
# y 0,05 em a los lados); asa celeste: raya de 0,032 em desde arriba de la caja hasta una bolita de 0,16 em en su borde de abajo. Hasta que llegue el video del usuario, el movimiento es supuesto:
# la palabra entra en c0-c3, el asa aparece en c4 y la selección barre la palabra de izquierda a derecha en c5-c17.
RESALTA_FUENTE = ('Inter 28pt', 'ExtraBold')
RESALTA_CAJA, RESALTA_ASA, RESALTA_TEXTO = (0.02, 0.0, 0.96), (0.10, 0.62, 0.90), (0.98, 0.98, 0.98)
RESALTA_ARRIBA, RESALTA_ABAJO, RESALTA_LADO = 0.47, 0.534, 0.05      # em desde el centro del Text+ (arriba de la caja / abajo) y a cada lado de la tinta
RESALTA_RAYA, RESALTA_BOLA, RESALTA_BOLA_Y = 0.032, 0.16, 0.56
RESALTA_BARRE = (5, 17)


def comp_resalta():
    """Imagen del usuario (selección del iPhone): palabra blanca; una caja azul crece detrás de ella de izquierda a derecha y el asa celeste
    (raya + bolita abajo) va en su borde derecho."""
    T = t24(22)
    t = texto_plus('Template', -220, 40, 'Resalta', RESALTA_FUENTE[0], RESALTA_FUENTE[1], 0.31, color=RESALTA_TEXTO, esp=0.97)
    t += _copia('Medida', 120, 'Resalta', fuente=RESALTA_FUENTE)
    dw = 'Medida.Output.DataWindow'
    izq = f'((({dw} and ({dw}[1] / {ANCHO_CUADRO})) or 0.3) - {n(RESALTA_LADO)} * {EM_W})'
    der = f'((({dw} and ({dw}[3] / {ANCHO_CUADRO})) or 0.7) + {n(RESALTA_LADO)} * {EM_W})'
    p = f'math.min(1, math.max(0, (({T}) - {RESALTA_BARRE[0]}) / {RESALTA_BARRE[1] - RESALTA_BARRE[0]}))'
    p = f'((3 - 2 * {p}) * {p} * {p})'
    borde = f'({izq} + {p} * ({der} - {izq}))'
    alto = RESALTA_ARRIBA + RESALTA_ABAJO
    yc = (RESALTA_ARRIBA - RESALTA_ABAJO) / 2
    t += K._mascara('RectangleMask', 'MCaja', -220, 200, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "{K.lua(f"Point(({izq} + {borde}) / 2, 0.5 + {n(yc)} * {EM_H})")}", }},',
        f'Width = Input {{ Value = 0, Expression = "{K.lua(f"{borde} - {izq}")}", }},',
        f'Height = Input {{ Value = 0.1, Expression = "{K.lua(f"{n(alto)} * {EM_H}")}", }},',            # (RectangleMask: alto en fracción del ALTO; ronda 6)
        'SoftEdge = Input { Value = 0.0006, },', 'CornerRadius = Input { Value = 0, },'])
    t += K._fondo('Caja', -60, 200, RESALTA_CAJA, 'MCaja')
    t += herramienta('Merge', 'ConTexto', 60, 120, [enlace('Background', 'Caja'), enlace('Foreground', 'Template')])
    # el asa: raya desde arriba de la caja hasta la bolita
    y_raya = (RESALTA_ARRIBA - RESALTA_BOLA_Y) / 2
    t += K._mascara('RectangleMask', 'MRaya', -220, 280, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "{K.lua(f"Point({borde}, 0.5 + {n(y_raya)} * {EM_H})")}", }},',
        f'Width = Input {{ Value = 0.004, Expression = "{K.lua(f"{n(RESALTA_RAYA)} * {EM_W}")}", }},',
        f'Height = Input {{ Value = 0.1, Expression = "{K.lua(f"{n(RESALTA_ARRIBA + RESALTA_BOLA_Y)} * {EM_H}")}", }},',
        'SoftEdge = Input { Value = 0.0004, },', 'CornerRadius = Input { Value = 0, },'])
    t += K._mascara('EllipseMask', 'MBola', -220, 360, [
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "{K.lua(f"Point({borde}, 0.5 - {n(RESALTA_BOLA_Y)} * {EM_H})")}", }},',
        f'Width = Input {{ Value = 0.02, Expression = "{K.lua(f"{n(RESALTA_BOLA)} * {EM_W}")}", }},',
        f'Height = Input {{ Value = 0.02, Expression = "{K.lua(f"{n(RESALTA_BOLA)} * {EM_W}")}", }},',
        'SoftEdge = Input { Value = 0.0004, },'])
    t += K._fondo('Raya', -60, 280, RESALTA_ASA, 'MRaya')
    t += K._fondo('Bola', -60, 360, RESALTA_ASA, 'MBola')
    t += herramienta('Merge', 'Asa', 60, 320, [enlace('Background', 'Raya'), enlace('Foreground', 'Bola')])
    asa = f'math.min(1, math.max(0, (({T}) - {RESALTA_BARRE[0] - 1}) / 1.5))'
    t += herramienta('Merge', 'ConAsa', 180, 120, [enlace('Background', 'ConTexto'), enlace('Foreground', 'Asa'),
                                                   f'Blend = Input {{ Value = 0, Expression = "{K.lua(asa)}", }},'])
    entra = f'math.min(1, math.max(0, ({T}) / 3))'
    t += cadena('ConAsa', dict(size=f'(0.94 + 0.06 * (3 - 2 * {entra}) * {entra} * {entra}) * (0.92 + 0.08 * {SALIDA})', blend=f'{entra} * {SALIDA}'), x0=400)
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - resalta')


# «Línea» (v5.75, el Tema 3 nuevo: referencia del usuario «ESTE ES EL ACABADO FINO»): toda la frase en UNA línea de mayúsculas condensadas blancas
# con contorno y sombra oscuros, y una caja negra redondeada que salta de palabra en palabra con la voz. Cada palabra es un clip «v linea» desde que
# empieza el bloque; la que suena lleva ENCIMA un «v linea activa» (la misma palabra + la caja) que dura exactamente lo que dura (corte seco, sin
# entrada ni salida: el colocador lo pone sin el mínimo de 0,45 s, run['exacto']). Caja medida en la referencia: 0,53 mayúsculas sobre ellas, 0,52 bajo
# la base, 0,35 a los lados, esquinas de 0,17.
LINEA_FUENTE = ('Barlow Semi Condensed', 'Bold')
LINEA_ESP = 0.975
LINEA_TEXTO, LINEA_BORDE, LINEA_CAJA = (0.98, 0.98, 0.98), (0.078, 0.078, 0.078), (0.075, 0.075, 0.075)
LINEA_CAJA_AZUL = (0.12, 0.36, 1.0)            # #1F5CFF: la del look de «Crea tu estilo» (el usuario: «en el ejemplo deja azul para que se aprecie»)


def _elementos_linea(caja, color_caja=None):
    """Elementos de sombreado del Text+ de la línea: 2 contorno oscuro, 3 sombra suave alrededor (forma de letra) y, con caja, 4 = caja negra redondeada."""
    r, g, b = LINEA_BORDE
    e = ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', 'Thickness2 = Input { Value = Number { Value = 0.03 }, },',
         f'Red2 = Input {{ Value = Number {{ Value = {n(r)} }}, }},', f'Green2 = Input {{ Value = Number {{ Value = {n(g)} }}, }},',
         f'Blue2 = Input {{ Value = Number {{ Value = {n(b)} }}, }},', 'Opacity2 = Input { Value = Number { Value = 1 }, },']
    e += _halo(3, (0.0, 0.0, 0.0), 0.65, 0.0, 9)
    if caja:
        r, g, b = color_caja or LINEA_CAJA
        e += ['Enabled4 = Input { Value = 1, },', 'ElementShape4 = Input { Value = 2, },', 'Level4 = Input { Value = Number { Value = 0 }, },',
              f'Red4 = Input {{ Value = Number {{ Value = {n(r)} }}, }},', f'Green4 = Input {{ Value = Number {{ Value = {n(g)} }}, }},',
              f'Blue4 = Input {{ Value = Number {{ Value = {n(b)} }}, }},', 'Opacity4 = Input { Value = Number { Value = 1 }, },',
              'ExtendHorizontal4 = Input { Value = Number { Value = 0 }, },',      # (el Extend va en em de la letra; sin él ya sale 0,36 mayúsculas a los lados)
              'ExtendVertical4 = Input { Value = Number { Value = 0.067 }, },',
              'Offset4 = Input { Value = { 0, -0.003 }, Expression = "Point(0, -Template.Size * 0.0301)", },',       # (fracción del ANCHO) 0,53 arriba y 0,52 abajo
              'Round4 = Input { Value = Number { Value = 0.1 }, },']      # esquinas sutiles (el usuario: «no es un óvalo»; 0,25 daba radio de 0,45 mayúsculas)
    return e


def comp_linea(activa=False, color_caja=None):
    """«v linea»: la palabra blanca (entra de golpe con la línea entera y se va con la salida de 5 fotogramas). «v linea activa»: la misma palabra con la
    caja negra detrás, sin animación (va encima de su «v linea» mientras suena)."""
    t = texto_plus('Template', -220, 40, 'LINEA', LINEA_FUENTE[0], LINEA_FUENTE[1], 0.09, color=LINEA_TEXTO, esp=LINEA_ESP, extra=_elementos_linea(activa, color_caja))
    if activa:
        t += cadena('Template', dict(size='1', blend='1'))
    else:                        # (entra de golpe, como la caja: con un fundido la palabra con caja salía 1-2 fotogramas antes que las demás; GO real)
        t += cadena('Template', dict(size=f'(0.96 + 0.04 * {SALIDA})', blend=f'{SALIDA}'))
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - linea' + (' activa' if activa else '') + (' azul' if color_caja else ''))


# «Rojo» (v5.78, el Estilo 7: referencia del usuario, un video de captions de 2-3 palabras): la frase en UNA línea de Anton (minúscula normal), blanca
# con contorno negro y una sombra negra DURA abajo a la derecha; la palabra que suena va en ROJO. Como «Línea»: cada palabra es un «v rojo» desde que
# empieza el bloque hasta que acaba y la que suena lleva ENCIMA un «v rojo activa» (la misma palabra en rojo) que dura exactamente lo que dura.
ROJO_FUENTE = ('Anton', 'Regular')
ROJO_BLANCO, ROJO_ROJO, ROJO_BORDE = (0.98, 0.98, 0.98), (0.886, 0.024, 0.071), (0.0, 0.0, 0.0)     # #E20612: el rojo de la referencia
ROJO_CONTORNO = 0.035                           # Thickness del contorno negro
ROJO_SOMBRA = (0.022, 0.030)                    # la sombra dura: desplazamiento × Size (fracción del ANCHO), a la derecha y hacia abajo


def _elementos_rojo():
    """2 = contorno negro; 3 y 4 = la sombra dura (el contorno y la letra, desplazados y sin difuminar: la sombra es la de la palabra entera)."""
    dx, dy = ROJO_SOMBRA

    def color(k):
        r, g, b = ROJO_BORDE
        return [f'Red{k} = Input {{ Value = Number {{ Value = {n(r)} }}, }},', f'Green{k} = Input {{ Value = Number {{ Value = {n(g)} }}, }},',
                f'Blue{k} = Input {{ Value = Number {{ Value = {n(b)} }}, }},', f'Opacity{k} = Input {{ Value = Number {{ Value = 1 }}, }},']

    def desplazado(k):
        return f'Offset{k} = Input {{ Value = {{ 0, 0 }}, Expression = "Point(Template.Size * {n(dx)}, -Template.Size * {n(dy)})", }},'

    grosor = f'Number {{ Value = {n(ROJO_CONTORNO)} }}'
    e = ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', f'Thickness2 = Input {{ Value = {grosor}, }},'] + color(2)
    e += ['Enabled3 = Input { Value = 1, },', 'ElementShape3 = Input { Value = 1, },', f'Thickness3 = Input {{ Value = {grosor}, }},', desplazado(3)] + color(3)
    e += ['Enabled4 = Input { Value = 1, },', 'ElementShape4 = Input { Value = 0, },', desplazado(4)] + color(4)      # (≥ 4: con forma de LETRA, no la caja)
    return e


def comp_rojo(activa=False):
    """«v rojo»: la palabra blanca, de golpe al entrar y al salir con su bloque. «v rojo activa»: la misma palabra en rojo, sin animación (va encima
    de su «v rojo» mientras suena). El color de la letra es el del Template (Red1…): lo cambia «Crea tu estilo».
    v5.80 (el usuario: «el estilo 7 desaparece palabras»): la blanca ya NO se va con la salida de 5 fotogramas: al final del bloque las blancas se
    borraban antes que la roja (que no tiene salida) y la línea se quedaba con una sola palabra. Corte seco las dos, como eligió (la A, «fiel»)."""
    t = texto_plus('Template', -220, 40, 'rojo', ROJO_FUENTE[0], ROJO_FUENTE[1], 0.09, color=ROJO_ROJO if activa else ROJO_BLANCO, extra=_elementos_rojo())
    t += cadena('Template', dict(size='1', blend='1'))
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - rojo' + (' activa' if activa else ''))


# «Tipo» (v5.76, el Tema 5 nuevo: referencia del usuario «cómo hacer ESTA TIPOGRAFÍA en capcut», propuesta B con bisel): un bloque de hasta 3 líneas,
# la palabra clave GRANDE (Montserrat Black, mayúsculas) y lo demás en serif cursiva (DM Serif Text Italic) encima y debajo, que se va escribiendo
# palabra a palabra con la voz; la serif «muerde» la grande (un hueco con su contorno) y todo lleva un bisel de luz y una sombra suave.
# UN clip por bloque: el texto del Template (invisible) trae el bloque entero codificado (tipo_planificador.codificar):
#     «arriba|GRANDE|abajo|size;cx;cy|size;cx;cy|size;cx;cy|t:f,t:f|t:f|t:f,t:f»
# los 3 textos, el Size y el centro de cada línea (fracciones del cuadro, y desde abajo) y cuándo se escribe cada palabra (segundos desde el inicio del
# clip : fracción de letras del Write On). Cada pieza saca lo suyo con una función de Lua en su expresión (laboratorio, Resolve 21.2: rondas 8 y 9).
TIPO_GRANDE = ('Montserrat', 'Black')
TIPO_SERIF = ('DM Serif Text', 'Italic')
TIPO_HUECO = 0.08                               # Thickness del contorno de la copia de la serif que hace el hueco en la grande
TIPO_VOLUMEN = (0.012, 1.0, 0.45, 0.30)         # bisel: difuminado (em de la grande), fuerza, cuánto aclara la luz, cuánto oscurece la sombra
TIPO_TONO_SOMBRA = (0.10, 0.13, 0.22)           # hacia dónde va la cara en la sombra del bisel (azul noche: blanco → #B5B8C2 como la propuesta)
TIPO_SOMBRA = (0.40, -0.003, 14)                # sombra suave debajo: opacidad, bajada (fracción del alto), difuminado


def _campo_tipo(k):
    """Expresión de Lua: el campo k (1…9) del texto del Template, partido por «|»."""
    return ('(function() local s = Template.StyledText.Value .. "|"; local i = 0; for c in s:gmatch("([^|]*)|") do i = i + 1; '
            f'if i == {k} then return c end end; return "" end)()')


def _num_tipo(k, j, defecto):
    """Expresión: el número j del campo k («size;cx;cy»)."""
    return ('(function() local s = Template.StyledText.Value .. "|"; local i = 0; for c in s:gmatch("([^|]*)|") do i = i + 1; '
            f'if i == {k} then local j = 0; for v in c:gmatch("([^;]+)") do j = j + 1; if j == {j} then return tonumber(v) or {defecto} end end end end; '
            f'return {defecto} end)()')


def _escrito_tipo(k):
    """Expresión: la fracción de letras escritas (Write On «End») de la tabla «t:f,t:f» del campo k en el segundo actual del clip."""
    return ('(function() local s = Template.StyledText.Value .. "|"; local i = 0; local tab = ""; for c in s:gmatch("([^|]*)|") do i = i + 1; '
            f'if i == {k} then tab = c end end; local t = time / {E.FPS}; local e = 0; '
            'for tt, ff in tab:gmatch("([%d%.]+):([%d%.]+)") do if t >= tonumber(tt) then e = tonumber(ff) end end; return e end)()')


def _pieza_tipo(nombre, x, y, k, fuente, hueco=False):
    """La línea k (1 arriba, 2 la grande, 3 abajo) con sus expresiones. `hueco`: la copia de la serif con un contorno grueso (su silueta es el
    hueco que muerde a la grande); la cara normal toma el color del Template (el «color principal» de «Crea tu estilo»)."""
    extra = [f'End = Input {{ Value = 1, Expression = "{K.lua(_escrito_tipo(k + 6))}", }},']
    if hueco:
        extra += ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', f'Thickness2 = Input {{ Value = Number {{ Value = {n(TIPO_HUECO)} }}, }},',
                  'Opacity2 = Input { Value = Number { Value = 1 }, },']
    t = texto_plus(nombre, x, y, 'x', fuente[0], fuente[1], 0.1, centro=(0.5, 0.5),
                   expr={'Center': f'Point({_num_tipo(k + 3, 2, 0.5)}, {_num_tipo(k + 3, 3, 0.5)})', 'Size': _num_tipo(k + 3, 1, 0.1)}, extra=extra)
    viejo = 'StyledText = Input { Value = "x", },'
    assert viejo in t
    t = t.replace(viejo, f'StyledText = Input {{ Value = Text {{ Value = "x" }}, Expression = "{K.lua("Text(" + _campo_tipo(k) + ")")}", }},')
    if not hueco:
        for c in ('Red', 'Green', 'Blue'):
            viejo = f'{c}1 = Input {{ Value = 1, }},'
            assert viejo in t
            t = t.replace(viejo, f'{c}1 = Input {{ Value = 1, Expression = "Template.{c}1", }},')
    return t


def comp_tipo():
    """«v tipo»: el bloque entero del Tema 5 (ver arriba). La grande pierde lo que tapa el contorno de las serif (Custom «Muerde»), las tres se juntan,
    llevan el bisel (_relieve, a la escala de la grande: el Size del Template = el de la grande) y la sombra; el bloque aparece en 2 fotogramas y se va
    con la salida de siempre."""
    t = texto_plus('Template', -220, 40, 'que esto|IMPORTA|de verdad|0.09;0.42;0.6|0.2;0.5;0.53|0.09;0.6;0.45|0:0.5,0.3:1|0.6:1|0.9:1',
                   TIPO_GRANDE[0], TIPO_GRANDE[1], 0.2, extra=['Opacity1 = Input { Value = 0, },'])
    t += _pieza_tipo('P1', -60, 120, 1, TIPO_SERIF)
    t += _pieza_tipo('P2', -60, 200, 2, TIPO_GRANDE)
    t += _pieza_tipo('P3', -60, 280, 3, TIPO_SERIF)
    t += _pieza_tipo('H1', -60, 360, 1, TIPO_SERIF, hueco=True)
    t += _pieza_tipo('H3', -60, 440, 3, TIPO_SERIF, hueco=True)
    t += herramienta('Merge', 'Huecos', 60, 400, [enlace('Background', 'H1'), enlace('Foreground', 'H3')])
    t += herramienta('Custom', 'Muerde', 60, 200, [enlace('Image1', 'P2'), enlace('Image2', 'Huecos'),
                                                   'RedExpression = Input { Value = "r1 * (1 - a2)", },', 'GreenExpression = Input { Value = "g1 * (1 - a2)", },',
                                                   'BlueExpression = Input { Value = "b1 * (1 - a2)", },', 'AlphaExpression = Input { Value = "a1 * (1 - a2)", },'])
    t += herramienta('Merge', 'Con1', 180, 160, [enlace('Background', 'Muerde'), enlace('Foreground', 'P1')])
    t += herramienta('Merge', 'Con3', 180, 240, [enlace('Background', 'Con1'), enlace('Foreground', 'P3')])
    blur, fuerza, k_luz, k_sombra = TIPO_VOLUMEN
    nodos, vol = _relieve('Con3', 'Vol', 300, 200, (1.0, 1.0, 1.0), TIPO_TONO_SOMBRA, blur, fuerza, k_luz=k_luz, k_sombra=k_sombra)
    t += nodos
    alfa, dy, difu = TIPO_SOMBRA
    sombra, ult = con_sombra(vol, 'Sm', 640, 200, alfa=alfa, dy=dy, blur=difu)
    t += sombra
    entra = _p(0, 2, t=f'(time * 24 / {E.FPS})')
    t += cadena(ult, dict(size=f'(0.98 + 0.02 * {SALIDA})', blend=f'{entra} * {SALIDA}'), x0=820)
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - tipo')


# ------------------------------------------------------------------------------------------------------------------ Estilo 8 «ámbar»
# v5.80 (el usuario, con un TikTok de referencia: una línea pequeña y elegante): cada palabra es un «v ambar» (Montserrat Regular ámbar claro) o,
# la clave, un «v ambar clave» (Montserrat ExtraBold ámbar); entra cuando se dice, subiendo un poco, enfocándose y apareciendo en 7 fotogramas, y
# todas se van a la vez con la salida de 5 fotogramas (las dos clases de clip la llevan: ninguna palabra se va antes que otra). Los colores, medidos
# en la referencia; los planifica ambar_planificador.
AMBAR_FUENTE, AMBAR_FUENTE_CLAVE = ('Montserrat', 'Regular'), ('Montserrat', 'ExtraBold')
AMBAR_COLOR, AMBAR_COLOR_CLAVE = (0.949, 0.761, 0.459), (0.965, 0.722, 0.337)       # #F2C275 y #F6B856
AMBAR_SOMBRA = (0.45, -0.003, 8)             # la sombra suave (opacidad, bajada, difuminado)
AMBAR_DESENFOQUE = 6                         # el desenfoque con el que empieza a entrar (XBlurSize)


def comp_ambar(clave=False):
    par = AMBAR_FUENTE_CLAVE if clave else AMBAR_FUENTE
    alfa, dy, blur = AMBAR_SOMBRA
    extra = E._sombra(2, alfa, dy, blur, color=(0.0, 0.0, 0.0))
    t = texto_plus('Template', -220, 40, 'ambar', par[0], par[1], 0.06, color=AMBAR_COLOR_CLAVE if clave else AMBAR_COLOR, esp=1.0, extra=extra)
    p = _p(0, 7)
    t += herramienta('Blur', 'Enfoca', -60, 40, [enlace('Input', 'Template'), 'Filter = Input { Value = FuID { "Gaussian" }, },',
                                                 'XBlurSize = Input { Value = 0, Expression = "%s", },' % K.lua(f'{AMBAR_DESENFOQUE} * (1 - {_suave(p)})')])
    t += cadena('Enfoca', dict(dy=f'(1 - {_suave(p)}) * (-0.008)', size='1', blend=f'{_suave(p)} * {SALIDA}'))
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - ambar' + (' clave' if clave else ''))


# ------------------------------------------------------------------------------------------------------------------ Estilo 9 «editorial»
# v5.80 (el usuario, con un TikTok de referencia «Polish your reels», y «el estilo 9 debe estar centrado y abajo»): el bloque de tres líneas
# centradas —palo seco fino arriba, la palabra clave GRANDE en serif cursiva y debajo palo seco con la última palabra en serif cursiva pequeña—.
# Cada palabra es un «v edi» (Inter Regular blanca) o un «v edi serif» (DM Serif Text Italic blanca); entran con un fundido cuando se dicen y se van
# todas a la vez. La sombra es ancha y suave (abajo suele haber fondos claros). Los planifica editorial_planificador.
EDI_SANS, EDI_SERIF = ('Inter 18pt', 'Regular'), ('DM Serif Text', 'Italic')
EDI_SOMBRA = ((0.70, -0.003, 16), (0.45, -0.002, 5))      # la ancha y la corta, pegada a la letra


def comp_edi(serif=False):
    par = EDI_SERIF if serif else EDI_SANS
    (a1, d1, b1), (a2, d2, b2) = EDI_SOMBRA
    extra = E._sombra(2, a1, d1, b1, color=(0.0, 0.0, 0.0)) + E._sombra(3, a2, d2, b2, color=(0.0, 0.0, 0.0))
    t = texto_plus('Template', -220, 40, 'editorial', par[0], par[1], 0.06, color=(1.0, 1.0, 1.0), esp=1.0, extra=extra)
    p = _p(0, 8)
    t += cadena('Template', dict(dy=f'(1 - {_suave(p)}) * (-0.004)', size='1', blend=f'{_suave(p)} * {SALIDA}'))
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - editorial' + (' serif' if serif else ''))


# ------------------------------------------------------------------------------------------------------------------ Estilo 4 «pila»
# v5.82 (el usuario, con su referencia «ESTILO 4.mp4»: «crea este estilo… y reemplázalo por el Estilo 4»): la pila de tres alturas de
# pila_planificador. «v pila» = la grande (Inter 28pt ExtraBold lima con su brillo lima), «v pila peq» = las pequeñas (Inter 24pt Bold blanco algo
# cálido) y «v pila lima» = la que remata abajo en lima (con brillo). Todas con la sombra negra suave de la referencia; colores, brillo y sombra
# medidos en ella (la lima de «Understand» 224,251,88; el blanco 255,255,248; brillo ~22 px y sombra de 12 px bajada 5 a 1080). Cada palabra entra
# en 2 fotogramas, sin desenfoque ni rebote, y NO tiene salida: el bloque entero se va de golpe al acabar (corte seco, como la referencia).
PILA_GRANDE, PILA_PEQ = ('Inter 28pt', 'ExtraBold'), ('Inter 24pt', 'Bold')
PILA_ESP = {'v pila': 0.97, 'v pila peq': 0.98, 'v pila lima': 0.98}     # (= pila_planificador.ESP_G / ESP_P: −0,046 y −0,031 em por letra)
PILA_LIMA, PILA_BLANCO = (0.878, 0.984, 0.345), (1.0, 1.0, 0.973)
PILA_SOMBRA = (0.55, -0.0026, 5.7)           # la negra (opacidad, bajada, Softness): 12 px de desenfoque a 1080
PILA_BRILLO = (0.44, 10.5)                   # el brillo lima (opacidad, Softness): ~22 px. (Softness ≈ px / 2,1 a 1080: 14 = ~29 px, ver SIZE_CALIBRADO)


def _difuso(num, color, opacidad, dy, blur):
    """Como _halo (la forma de la letra y SoftnessBlend 1: sin él no se desenfoca), pero con el difuminado FIJO en el cuadro: los mismos px en la
    grande y en las pequeñas, como la referencia (el Softness de Text+ va contra el cuadro)."""
    cambios = {f'SoftnessBlend{num} = Input {{ Value = Number {{ Value = 0 }}, }},': f'SoftnessBlend{num} = Input {{ Value = Number {{ Value = 1 }}, }},'}
    return [cambios.get(l, l) for l in E._sombra(num, opacidad, dy, blur, color=color)] + [f'ElementShape{num} = Input {{ Value = 0, }},']


def comp_pila(tipo='v pila'):
    par = PILA_GRANDE if tipo == 'v pila' else PILA_PEQ
    lima = tipo in ('v pila', 'v pila lima')
    a, dy, blur = PILA_SOMBRA
    extra = (_difuso(2, PILA_LIMA, PILA_BRILLO[0], 0.0, PILA_BRILLO[1]) if lima else []) + _difuso(3 if lima else 2, (0.0, 0.0, 0.0), a, dy, blur)
    t = texto_plus('Template', -220, 40, 'pila', par[0], par[1], 0.06, color=PILA_LIMA if lima else PILA_BLANCO, esp=PILA_ESP[tipo], extra=extra)
    t += cadena('Template', dict(size='1', blend=_suave(_p(0, 2))))
    return K.armar_comp(MK.envolver(t), 'CineCaptions VIRAL - pila' + {'v pila': '', 'v pila peq': ' peq', 'v pila lima': ' lima'}[tipo])


# ------------------------------------------------------------------------------------------------------------------ el catálogo
def todos(formato='v'):
    """{nombre del clip: texto de la comp} para el formato 'v' (vertical) o 'h' (horizontal). Los tamaños (Size) son los de partida: la app fija el real por clip."""
    configurar(formato)
    import viral_captions as VC
    comps = {'v fina': comp_fina(), 'v negrita': comp_negrita()}
    for base, hacer in (('v shatter', comp_shatter), ('v select', comp_select), ('v drag', comp_drag)):
        for color in VC.COLORES[base]:                       # cada efecto en sus 4 colores: 'v shatter', 'v shatter rosa', …
            comps[base + (' ' + color if color else '')] = hacer(color)
    comps['v corte'] = comp_corte()                         # v5.75: copias exactas de EJEMPLO 2 y EJEMPLO3 (un solo color: el de la referencia)
    comps['v shine'] = comp_shine()
    comps['v resalta'] = comp_resalta()                     # v5.75: la selección del iPhone (imagen del usuario)
    comps['v linea'] = comp_linea()                         # v5.75: el Tema 3 nuevo (una línea y la caja negra que salta de palabra en palabra)
    comps['v linea activa'] = comp_linea(True)
    comps['v linea activa azul'] = comp_linea(True, LINEA_CAJA_AZUL)  # (el look 't3:linea' de «Crea tu estilo»)
    comps['v tipo'] = comp_tipo()                           # v5.76: el Tema 5 nuevo (grande + serif que la muerde, palabra a palabra, con bisel)
    comps['v rojo'] = comp_rojo()                           # v5.78: el Estilo 7 (Anton blanca y la palabra que suena en rojo)
    comps['v rojo activa'] = comp_rojo(True)
    comps['v ambar'] = comp_ambar()                         # v5.80: el Estilo 8 (Montserrat ámbar, la clave en ExtraBold)
    comps['v ambar clave'] = comp_ambar(True)
    comps['v edi'] = comp_edi()                             # v5.80: el Estilo 9 (palo seco fino y la clave grande en serif cursiva)
    comps['v edi serif'] = comp_edi(True)
    for tipo in ('v pila', 'v pila peq', 'v pila lima'):      # v5.82: el Estilo 4 nuevo (la pila de tres alturas)
        comps[tipo] = comp_pila(tipo)
    return comps


if __name__ == '__main__':
    for nombre in todos():
        print(nombre)
