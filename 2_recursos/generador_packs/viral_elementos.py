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
    """Silueta negra desenfocada y un poco más abajo, debajo de `origen` (lo que hacía la cinta de Kinetic). Devuelve (nodos, nombre del Merge final)."""
    t = herramienta('BrightnessContrast', prefijo + 'Negro', x, y, [enlace('Input', origen), 'Gain = Input { Value = 0, },', f'Alpha = Input {{ Value = {n(alfa)}, }},'])
    t += herramienta('Blur', prefijo + 'Difumina', x, y + 40, [enlace('Input', prefijo + 'Negro'), f'XBlurSize = Input {{ Value = {n(blur)}, }},', 'Filter = Input { Value = FuID { "Gaussian" }, },'])
    t += herramienta('Transform', prefijo + 'Baja', x, y + 80, [enlace('Input', prefijo + 'Difumina'), f'Center = Input {{ Value = {{ 0.5, {n(0.5 + dy)} }}, }},'])
    t += herramienta('Merge', prefijo + 'Con', x, y + 120, [enlace('Background', prefijo + 'Baja'), enlace('Foreground', origen)])
    return t, prefijo + 'Con'


# ------------------------------------------------------------------------------------------------------------------ línea fina y negrita
def comp_fina():
    extra = E._sombra(2, 0.80, -0.004, 10) + E._contorno(3, 0.019, 0.92)
    t = texto_plus('Template', -220, 40, 'fina', FINA[0], FINA[1], 0.09, color=(1, 1, 1), esp=1.0, extra=extra)
    p = _p(0, 7)
    t += cadena('Template', dict(dy=f'(1 - {_suave(p)}) * (-0.014)', size=f'(0.96 + 0.04 * {_suave(p)}) * (0.92 + 0.08 * {SALIDA})', blend=f'math.min(1, {p} * 2.0) * {SALIDA}'))
    return K.armar_comp(t, 'CineCaptions VIRAL - fina')


def comp_negrita():
    extra = E._sombra(2, 0.85, -0.006, 9) + E._contorno(3, 0.013, 0.95) + _inclinar(1, 2, 3)
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
    """La flecha del ratón (punta arriba a la izquierda) en el espacio de la máscara: x en fracción del ancho; y se corrige por el aspecto para que no se deforme. La punta es el origen."""
    rejilla = [(0, 0), (0, -16), (4.2, -12.2), (7, -19), (9.4, -17.8), (6.6, -11.2), (11.4, -11.2)]       # una flecha clásica en una cuadrícula de 12 × 19
    k = 0.0062
    return V.poligono(nombre, [(px * k, py * k * ASPECTO) for px, py in rejilla], -220, y)


def comp_select(color_caja=''):
    """Máquina de escribir (Write On) → cursor → caja punteada (roja, o azul / verde / naranja: CAJAS_SELECT) que se dibuja desde la esquina de arriba a la izquierda hasta la de abajo a la derecha."""
    dw_m = 'Medida.Output.DataWindow'
    letras = f'(({dw_m} and (({dw_m}[3] - {dw_m}[1]) / {ANCHO_CUADRO}) or 0.2) / ({EM_W} * 0.62))'      # nº de letras estimado por el ancho
    T = tt(34)
    T0 = 3                                                                                        # empieza a escribir
    dur = f'(3 + 1.2 * {letras})'
    escribe = f'math.min(1, math.max(0, ({T} - {T0}) / {dur}))'
    fin_esc = f'({T0} + {dur})'
    caja = f'math.min(1, math.max(0, ({T} - {fin_esc} - 2) / 10))'                                  # progreso de la caja y del cursor
    caja_e = f'(1 - (1 - {caja})^3)'
    extra = ['End = Input { Value = 1, Expression = "%s", },' % K.lua(escribe)]
    extra += _color(E._sombra(2, 0.40, 0.0, 22), 2, (1, 1, 1))                                   # brillo blanco suave (sobre un fondo claro, uno fuerte borra el borde)
    extra += E._contorno(3, 0.012, 0.95) + E._sombra(4, 0.70, -0.008, 14) + ['ElementShape4 = Input { Value = 0, },']      # contorno oscuro y sombra (forma de LETRA: sin esto el elemento 4 sale como un rectángulo)
    t = texto_plus('Template', -220, 40, 'Select', EFECTO[0], EFECTO[1], 0.30, color=(1, 1, 1), esp=0.97, extra=extra)
    ligado = 'StyledText = Input { Value = "Select", Expression = "Template.StyledText", },'
    t += texto_plus('Medida', -220, 120, 'Select', EFECTO[0], EFECTO[1], 0.30, esp=0.97, expr={'Size': 'Template.Size'}).replace('StyledText = Input { Value = "Select", },', ligado)
    rojo = CAJAS_SELECT[color_caja]
    borde = ['Enabled1 = Input { Value = 0, },', 'Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 3, },', 'Level2 = Input { Value = Number { Value = 0 }, },',
             'LineStyle2 = Input { Value = Number { Value = 1 }, },', 'JoinStyle2 = Input { Value = 1, },',
             'Thickness2 = Input { Value = Number { Value = 0.02 }, Expression = "Template.Size * 0.075", },',
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
        f'Size = Input {{ Value = 1, Expression = "{K.lua(f"{EM_W} * 3.2")}", }},'])
    sombra, ult = con_sombra('Raton', 'Cs', 140, 300, alfa=0.55, dy=-0.004, blur=5)
    t += sombra
    t += herramienta('Merge', 'Fundido', 260, 300, [enlace('Background', 'VacioCursor'), enlace('Foreground', ult), f'Blend = Input {{ Value = 0, Expression = "{K.lua(_p(fin_esc, 3, T))}", }},'])
    t += vacio('VacioCursor', 260, 380)
    t += herramienta('Merge', 'M1', 380, 120, [enlace('Background', 'Template'), enlace('Foreground', 'Crece')])
    t += herramienta('Merge', 'M2', 380, 200, [enlace('Background', 'M1'), enlace('Foreground', 'Fundido')])
    p = _p(0, 6)
    t += cadena('M2', dict(size=f'(0.96 + 0.04 * {_suave(p)}) * (0.92 + 0.08 * {SALIDA})', blend=f'math.min(1, {p} * 2.0) * {SALIDA}'), x0=520)
    return K.armar_comp(t, 'CineCaptions VIRAL - select')


# ------------------------------------------------------------------------------------------------------------------ drag
def _mano(nombre, y):
    """Una mano (puño con cuatro dedos y pulgar) hecha con rectángulos redondeados: primero todo en negro un poco más grande (el contorno y las separaciones) y encima en blanco.
    Devuelve (nodos, nombre de la salida). Medidas en fracción del ANCHO; la altura de cada máscara se pasa a fracción del alto con ASPECTO."""
    piezas = [  # cx, cy, ancho, alto, radio, ángulo
        (0.0, -0.014, 0.064, 0.066, 0.30, 0), (-0.0235, 0.034, 0.0125, 0.040, 0.5, 0), (-0.0078, 0.040, 0.0125, 0.046, 0.5, 0),
        (0.0078, 0.040, 0.0125, 0.046, 0.5, 0), (0.0235, 0.034, 0.0125, 0.040, 0.5, 0), (-0.036, -0.006, 0.015, 0.036, 0.5, 38)]

    def rect(nom, cx, cy, ancho, alto, radio, ang, color, yy):
        m = K._mascara('RectangleMask', nom + 'M', -220, yy, [
            f'Center = Input {{ Value = {{ {n(0.5 + cx)}, {n(0.5 + cy * ASPECTO)} }}, }},', f'Width = Input {{ Value = {n(ancho)}, }},', f'Height = Input {{ Value = {n(alto * ASPECTO)}, }},',
            f'CornerRadius = Input {{ Value = {n(radio)}, }},', f'Angle = Input {{ Value = {n(ang)}, }},'])
        return m + K._fondo(nom, -60, yy, color, nom + 'M')
    t, nombres = '', []
    for k, (cx, cy, w, h, r, ang) in enumerate(piezas):          # el contorno negro
        t += rect(f'{nombre}N{k}', cx, cy, w + 0.012, h + 0.012, r, ang, (0, 0, 0), y + 40 * k)
        nombres.append(f'{nombre}N{k}')
    for k, (cx, cy, w, h, r, ang) in enumerate(piezas):          # el relleno blanco
        t += rect(f'{nombre}B{k}', cx, cy, w, h, r, ang, (1, 1, 1), y + 40 * (k + len(piezas)))
        nombres.append(f'{nombre}B{k}')
    prev = nombres[0]
    for k, nom in enumerate(nombres[1:], 1):
        t += herramienta('Merge', f'{nombre}U{k}', 80, y + 40 * k, [enlace('Background', prev), enlace('Foreground', nom)])
        prev = f'{nombre}U{k}'
    return t, prev


def comp_drag(tinte=''):
    """Contorno punteado de la palabra; una mano baja, la agarra y la arrastra de izquierda a derecha mientras el relleno (blanco, o amarillo / cian / rosa: TINTES_DRAG) sube y brilla; la mano se va."""
    color = TINTES_DRAG[tinte]
    T = tt(40)
    llena = f'math.min(1, math.max(0, ({T} - 12) / 18))'
    mano = _p(2, 26, T)
    extra = [f'Opacity1 = Input {{ Value = Number {{ Value = 1 }}, Expression = "{K.lua(llena)}", }},']
    extra += ['Enabled2 = Input { Value = 1, },', 'ElementShape2 = Input { Value = 1, },', 'LineStyle2 = Input { Value = Number { Value = 1 }, },', 'JoinStyle2 = Input { Value = 1, },',
              'Thickness2 = Input { Value = Number { Value = 0.01 }, Expression = "Template.Size * 0.022", },',
              f'Red2 = Input {{ Value = Number {{ Value = {n(color[0])} }}, }},', f'Green2 = Input {{ Value = Number {{ Value = {n(color[1])} }}, }},', f'Blue2 = Input {{ Value = Number {{ Value = {n(color[2])} }}, }},',
              f'Opacity2 = Input {{ Value = Number {{ Value = 0.85 }}, Expression = "{K.lua(f"0.85 * math.min(1, {T} / 5) * (1 - {llena}^2)")}", }},']
    extra += _color(E._sombra(3, 0.8, 0.0, 24), 3, (1, 1, 1))
    extra += E._contorno(4, 0.012, 0.95) + E._sombra(5, 0.70, -0.008, 14) + ['ElementShape5 = Input { Value = 0, },']        # contorno y sombra oscuros (forma de LETRA): aparecen al rellenarse
    exprs = {'Opacity3': f"0.40 * {llena}", 'Opacity4': f"0.95 * {llena}", 'Opacity5': f"0.70 * {llena}"}
    extra = [l if not any(l.startswith(k) for k in exprs) else
             f'{next(k for k in exprs if l.startswith(k))} = Input {{ Value = Number {{ Value = 0 }}, Expression = "{K.lua(exprs[next(k for k in exprs if l.startswith(k))])}", }},' for l in extra]
    t = texto_plus('Template', -220, 40, 'Drag', EFECTO[0], EFECTO[1], 0.30, color=color, esp=0.97, extra=extra)
    nodos, mano_out = _mano('Mano', 300)
    t += nodos
    dw = 'Template.Output.DataWindow'
    ancho_t = f'({dw} and (({dw}[3] - {dw}[1]) / {ANCHO_CUADRO}) or 0.4)'
    cx = f'({dw} and (({dw}[1] + {dw}[3]) / 2 / {ANCHO_CUADRO}) or 0.5)'
    cy = f'({dw} and (({dw}[2] + {dw}[4]) / 2 / {ALTO_CUADRO}) or 0.5)'
    e = _suave(mano)
    # recorrido: arranca encima de la palabra, a la izquierda; baja hasta ella y la arrastra hacia la derecha
    x = f'{cx} + {ancho_t} * (-0.32 + 0.52 * {e})'
    y = f'{cy} + {EM_H} * (0.72 - 0.32 * {_p(2, 8, T)} + 0.06 * math.sin({e} * 6.28))'
    aparece = f'math.min(1, math.max(0, ({T} - 1) / 4)) * (1 - math.min(1, math.max(0, ({T} - 30) / 5)))'
    t += herramienta('Transform', 'Lleva', 40, 300, [
        enlace('Input', mano_out),
        'Pivot = Input { Value = { 0.5, 0.5 }, },',
        f'Center = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "Point({K.lua(x)} , {K.lua(y)})", }},',
        f'Size = Input {{ Value = 1, Expression = "{K.lua(f"{EM_W} * 4.6 * (1 - 0.18 * {_p(14, 12, T)})")}", }},'])
    t += vacio('VacioMano', 160, 380)
    t += herramienta('Merge', 'ManoFin', 160, 300, [enlace('Background', 'VacioMano'), enlace('Foreground', 'Lleva'), f'Blend = Input {{ Value = 0, Expression = "{K.lua(aparece)}", }},'])
    t += herramienta('Merge', 'M1', 280, 120, [enlace('Background', 'Template'), enlace('Foreground', 'ManoFin')])
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
