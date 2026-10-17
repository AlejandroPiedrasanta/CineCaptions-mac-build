# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/drfx_motions.py — «CineCaptions Motions.drfx»: motions EDITABLES en el Inspector de Resolve (Efectos › Títulos ›
# CineCaptions), con el banner de CineCaptions (su logo) arriba de todo.
"""
v5.5.9 (pedido: «en DaVinci Resolve aún no tiene un banner y mi logo; no se crea .drfx para personalizar; los motions en el Inspector tienen
que ser para editar, y abajo poder colocar otro motion»). Cada motion es un título de Fusion (.setting con un MacroOperator, como los del Luxe
Title Pack): sus textos, fuente, colores, posición y tamaño están PUBLICADOS en el Inspector, y la animación de entrada y de salida va por
expresiones relativas a la duración del clip (comp.RenderStart / comp.RenderEnd): editar el texto, alargar o recortar el clip no la rompe.
El banner (banner_inspector.LABEL, con el logo) va en los controles de usuario del propio macro con IC_ControlPage = -1: arriba de todo.

    MOTIONS                          los motions (nombre del archivo → función que arma su macro)
    construir(salida=None) -> ruta   escribe 2_recursos/motions_resolve/Edit/Titles/CineCaptions/*.setting + miniaturas y motions_resolve/CineCaptions Motions.drfx
    python drfx_motions.py

El .drfx es un zip con la misma estructura que los de Resolve (Edit/Titles/<carpeta>/<nombre>.setting + .png); la app copia la carpeta
CineCaptions a Fusion/Templates/Edit/Titles del usuario (instalador_scripts.instalar_motions_en_resolve), y el .drfx sirve para pasarlo a mano.
"""
import os
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RECURSOS = AQUI.parent
sys.path.insert(0, str(AQUI))
import banner_inspector as B  # noqa: E402

CARPETA = 'CineCaptions'
SALIDA_DIR = RECURSOS / 'motions_resolve'
DRFX = SALIDA_DIR / 'CineCaptions Motions.drfx'           # (va con el programa: el usuario puede pasarlo a otro equipo)
ACENTO = (0.30, 0.49, 1.0)
# el banner de los motions: el mismo logo, con su ayuda («tu motion»)
LABEL = B._label(f"<center><img src='data:image/png;base64,{B._B64}' width='300'><br><font color='#9AA3B5'>Personaliza aquí tu motion: "
                 "textos, colores, posición y tamaño</font></center>")
BLANCO = (1.0, 1.0, 1.0)


# ------------------------------------------------------------------------------------------------------------------ escritura
def n(v):
    return f'{float(v):.6g}'


def lua(texto):
    return str(texto).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def I(nombre, valor=None, expr=None, numero=False):
    """«Nombre = Input { Value = …, Expression = "…", },»; valor: número, texto, (x, y) o un literal ya escrito (FuID…)."""
    if valor is None:
        v = '0'
    elif isinstance(valor, tuple):
        v = '{ ' + ', '.join(n(x) for x in valor) + ' }'
    elif isinstance(valor, str) and not valor.startswith(('FuID', 'Number', 'Gradient')):
        v = '"' + lua(valor) + '"'
    elif isinstance(valor, str):
        v = valor
    else:
        v = f'Number {{ Value = {n(valor)} }}' if numero else n(valor)
    return f'{nombre} = Input {{ Value = {v}' + (f', Expression = "{lua(expr)}"' if expr else '') + ', },'


def L(nombre, op, fuente='Output'):
    return f'{nombre} = Input {{ SourceOp = "{op}", Source = "{fuente}", }},'


def herr(tipo, nombre, x, y, entradas, extra=''):
    cuerpo = '\n\t\t\t\t\t'.join(entradas)
    return (f'\t\t\t\t{nombre} = {tipo} {{\n\t\t\t\t\tCtrlWZoom = false,\n{extra}\t\t\t\t\tInputs = {{\n\t\t\t\t\t{cuerpo}\n\t\t\t\t\t}},\n'
            f'\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t\t\t}},\n')


# ------------------------------------------------------------------------------------------------------------------ animación (fotogramas)
def P(retardo, dur):
    """Progreso de la entrada 0 → 1 (desde el inicio del clip + retardo)."""
    return f'math.min(1, math.max(0, (time - comp.RenderStart - {retardo}) / {dur}))'


def S(dur=8):
    """1 durante el clip y baja a 0 en sus últimos `dur` fotogramas (la salida)."""
    return f'math.min(1, math.max(0, (comp.RenderEnd - time) / {dur}))'


def EO(p):
    return f'(1 - (1 - ({p}))^3)'


def BK(p):
    """easeOutBack: pasa un poco de 1 y se asienta (el «pop»)."""
    return f'(1 + 2.70158*(({p})-1)^3 + 1.70158*(({p})-1)^2)'


# ------------------------------------------------------------------------------------------------------------------ piezas
def texto(nombre, x, y, cadena, fuente, estilo, tam, centro, color=BLANCO, extra=(), expr=None, controles=''):
    expr = expr or {}
    lineas = [
        I('UseFrameFormatSettings', 1), I('Wrap', 0),
        I('Center', centro, expr.get('Center')),
        I('Red1', color[0], expr.get('Red1')), I('Green1', color[1], expr.get('Green1')), I('Blue1', color[2], expr.get('Blue1')),
        I('StyledText', cadena, expr.get('StyledText')), I('Font', fuente, expr.get('Font')), I('Style', estilo, expr.get('Style')),
        I('Size', tam, expr.get('Size')),
        I('VerticalJustificationNew', 3), I('HorizontalJustificationNew', 3),
    ] + list(extra)
    return herr('TextPlus', nombre, x, y, lineas, controles)


def color_de(origen, prefijo='TopLeft'):
    """Expresiones para seguir el color de un Background «holder» (Acento)."""
    return {'r': f'{origen}.{prefijo}Red', 'g': f'{origen}.{prefijo}Green', 'b': f'{origen}.{prefijo}Blue'}


def caja(num, fondo, extiende=(0.32, 0.22), redondo=1.0, alfa=1.0):
    """Elemento de sombreado `num` del Text+ como caja del tamaño del texto (forma 2 = relleno del borde, medido en Resolve 21.1.1).
    fondo: (r, g, b) o el nombre de un Background del que copiar el color."""
    col = color_de(fondo) if isinstance(fondo, str) else None
    def c(canal, i):
        return I(f'{canal}{num}', 0 if col else fondo[i], col[canal[0].lower()] if col else None, numero=True)
    return [I(f'Enabled{num}', 1), I(f'ElementShape{num}', 2), I(f'Level{num}', 0, numero=True),
            I(f'ExtendHorizontal{num}', extiende[0], numero=True), I(f'ExtendVertical{num}', extiende[1], numero=True),
            I(f'Round{num}', redondo, numero=True), c('Red', 0), c('Green', 1), c('Blue', 2), I(f'Opacity{num}', alfa, numero=True)]


def sombra(num, opacidad=0.55, dy=-0.006, blur=10):
    return [I(f'Enabled{num}', 1), I(f'Red{num}', 0, numero=True), I(f'Green{num}', 0, numero=True), I(f'Blue{num}', 0, numero=True),
            I(f'Opacity{num}', opacidad, numero=True), f'Offset{num} = Input {{ Value = Point {{ X = 0, Y = {n(dy)} }}, }},',
            I(f'Softness{num}', 1, numero=True), I(f'SoftnessX{num}', blur, numero=True), I(f'SoftnessY{num}', blur, numero=True)]


def acento(nombre='Acento', color=ACENTO, x=-220, y=-80):
    """Un Background sin conectar que guarda el color de acento (lo publica el macro; las piezas lo copian por expresión)."""
    return herr('Background', nombre, x, y, [I('UseFrameFormatSettings', 1), I('TopLeftRed', color[0]), I('TopLeftGreen', color[1]),
                                              I('TopLeftBlue', color[2]), I('TopLeftAlpha', 1)])


def forma(nombre, mascara, x, y, color_origen='Acento'):
    """Un Background del color de acento recortado por una máscara (una barra, un punto…)."""
    c = color_de(color_origen)
    return herr('Background', nombre, x, y, [I('UseFrameFormatSettings', 1), I('TopLeftRed', 1, c['r']), I('TopLeftGreen', 1, c['g']),
                                              I('TopLeftBlue', 1, c['b']), I('TopLeftAlpha', 1), L('EffectMask', mascara, 'Mask')])


def rect(nombre, x, y, centro, ancho, alto, radio=0.5, expr=None):
    expr = expr or {}
    return herr('RectangleMask', nombre, x, y, [I('UseFrameFormatSettings', 1), I('SoftEdge', 0.0006), I('Center', centro, expr.get('Center')),
                                                 I('Width', ancho, expr.get('Width')), I('Height', alto, expr.get('Height')),
                                                 I('CornerRadius', radio)])


def elipse(nombre, x, y, centro, lado, expr=None):
    expr = expr or {}
    return herr('EllipseMask', nombre, x, y, [I('UseFrameFormatSettings', 1), I('SoftEdge', 0.0008), I('Center', centro, expr.get('Center')),
                                               I('Width', lado, expr.get('Width')), I('Height', lado, expr.get('Height'))])


class Capas:
    """Encadena capas animadas: cada una pasa por su Transform (posición / tamaño / giro por expresión) y un Merge con su opacidad (Blend) sobre
    lo anterior; al final, el Transform «Encuadre» (Posición y Tamaño del macro)."""

    def __init__(self):
        self.txt = herr('Background', 'Vacio', 0, 260, [I('UseFrameFormatSettings', 1), I('TopLeftAlpha', 0)])
        self.ultima = 'Vacio'
        self.k = 0

    def poner(self, origen, size='1', dy='0', dx='0', ang='0', blend='1', pivote=(0.5, 0.5)):
        self.k += 1
        t, m = f'Anim{self.k}', f'Capa{self.k}'
        x = 160 * self.k
        self.txt += herr('Transform', t, x, 120, [L('Input', origen), I('Center', (0.5, 0.5), f'Point(0.5 + {dx}, 0.5 + {dy})'),
                                                  I('Pivot', pivote), I('Size', 1, size), I('Angle', 0, ang)])
        self.txt += herr('Merge', m, x, 260, [L('Background', self.ultima), L('Foreground', t), I('Blend', 1, blend), I('PerformDepthMerge', 0)])
        self.ultima = m

    def cerrar(self):
        self.txt += herr('Transform', 'Encuadre', 160 * (self.k + 1), 260, [L('Input', self.ultima), I('Center', (0.5, 0.5)), I('Size', 1)])
        return self.txt


def macro(nombre, herramientas, publicadas):
    """El .setting: MacroOperator con el banner (logo) arriba de todo y los controles publicados en orden.
    publicadas: [(tool, input, nombre visible o None, grupo de control o None, extra)]."""
    entradas = []
    for k, (tool, inp, visible, grupo, extra) in enumerate(publicadas, 1):
        campos = [f'SourceOp = "{tool}"', f'Source = "{inp}"']
        if visible:
            campos.append(f'Name = "{lua(visible)}"')
        if grupo:
            campos.append(f'ControlGroup = {grupo}')
        campos += list(extra or [])
        entradas.append(f'\t\t\t\tInput{k} = InstanceInput {{ ' + ', '.join(campos) + ', },')
    cuerpo = '\n'.join(entradas)
    return (f'{{\n\tTools = ordered() {{\n\t\t{nombre} = MacroOperator {{\n\t\t\tCtrlWZoom = false,\n'
            f'\t\t\tInputs = ordered() {{\n{cuerpo}\n\t\t\t}},\n'
            f'\t\t\tOutputs = {{\n\t\t\t\tMainOutput1 = InstanceOutput {{ SourceOp = "Encuadre", Source = "Output", }}\n\t\t\t}},\n'
            f'\t\t\tViewInfo = GroupInfo {{ Pos = {{ 0, 0 }} }},\n'
            f'\t\t\tTools = ordered() {{\n{herramientas}\t\t\t}},\n'
            f'\t\t\tUserControls = ordered() {{ {LABEL}}}\n'
            f'\t\t}}\n\t}},\n\tActiveTool = "{nombre}"\n}}\n')


def _color(tool, prefijo, nombre, grupo):
    """Las tres entradas de un color publicadas juntas (rueda de color en el Inspector)."""
    return [(tool, f'{prefijo}Red', nombre, grupo, None), (tool, f'{prefijo}Green', None, grupo, None), (tool, f'{prefijo}Blue', None, grupo, None)]


def _encuadre(grupo):
    return [('Encuadre', 'Center', 'Posición', None, None), ('Encuadre', 'Size', 'Tamaño', None, ['Default = 1'])]


# ------------------------------------------------------------------------------------------------------------------ los motions
def titular():
    """Un titular grande que sube con rebote, una barra del acento que se abre y un subtítulo debajo."""
    h = acento()
    h += texto('Titulo', 0, 0, 'TU TÍTULO AQUÍ', 'Montserrat', 'ExtraBold', 0.085, (0.5, 0.53), extra=sombra(4))
    h += texto('Sub', 0, 60, 'Escribe aquí el subtítulo', 'Inter 18pt', 'Medium', 0.045, (0.5, 0.445), color=(0.86, 0.89, 0.96), extra=sombra(4, 0.5))
    h += rect('BarraMask', -160, 140, (0.5, 0.488), 0.42, 0.012, expr={'Width': f'0.42 * {EO(P(6, 12))} * {S()}'})
    h += forma('Barra', 'BarraMask', -60, 140)
    c = Capas()
    c.poner('Barra', blend=S())
    e = BK(P(0, 12))
    c.poner('Titulo', size=f'(0.85 + 0.15*{e}) * (0.94 + 0.06*{S()})', dy=f'(1 - {e}) * (-0.035)', blend=f'math.min(1, {P(0, 12)} * 2.2) * {S()}')
    e2 = EO(P(8, 12))
    c.poner('Sub', dy=f'(1 - {e2}) * (-0.02)', blend=f'{e2} * {S()}')
    h += c.cerrar()
    pub = [('Titulo', 'StyledText', 'Título', None, None), ('Titulo', 'Font', 'Fuente', 2, None), ('Titulo', 'Style', None, 2, None)]
    pub += _color('Titulo', '', 'Color del título', 3)
    pub += [('Sub', 'StyledText', 'Subtítulo', None, None)]
    pub += _color('Acento', 'TopLeft', 'Color de acento', 4)
    pub += _encuadre(5)
    return macro('CCTitular', h, [(t, i if i not in ('Red', 'Green', 'Blue') else i, v, g, x) for t, i, v, g, x in _fix(pub)])


def _fix(pub):
    """«Red» de un Text+ es «Red1» (el color de su texto)."""
    out = []
    for t, i, v, g, x in pub:
        if i in ('Red', 'Green', 'Blue'):
            i = i + '1'
        out.append((t, i, v, g, x))
    return out


def pildoras():
    """Tres píldoras con el texto encima de una caja redondeada del color de acento: entran una a una con un «pop»."""
    h = acento()
    ys = (0.6, 0.5, 0.4)
    textos = ('Primera idea', 'Segunda idea', 'Tercera idea')
    for k, (y, t) in enumerate(zip(ys, textos), 1):
        expr = None if k == 1 else {'Font': 'P1.Font', 'Style': 'P1.Style', 'Red1': 'P1.Red1', 'Green1': 'P1.Green1', 'Blue1': 'P1.Blue1', 'Size': 'P1.Size'}
        h += texto(f'P{k}', 0, 70 * k, t, 'Inter 24pt', 'Bold', 0.066, (0.5, y), extra=caja(2, 'Acento', (0.45, 0.32)) + sombra(4, 0.45), expr=expr)
    c = Capas()
    for k in range(1, 4):
        p = P(6 * (k - 1), 11)
        e = BK(p)
        c.poner(f'P{k}', size=f'(0.5 + 0.5*{e}) * (0.9 + 0.1*{S()})', blend=f'math.min(1, {p} * 2.5) * {S()}', pivote=(0.5, ys[k - 1]))
    h += c.cerrar()
    pub = [('P1', 'StyledText', 'Píldora 1', None, None), ('P2', 'StyledText', 'Píldora 2', None, None), ('P3', 'StyledText', 'Píldora 3', None, None),
           ('P1', 'Font', 'Fuente', 2, None), ('P1', 'Style', None, 2, None), ('P1', 'Size', 'Tamaño del texto', None, None)]
    pub += _fix(_color('P1', '', 'Color del texto', 3))
    pub += _color('Acento', 'TopLeft', 'Color de las píldoras', 4)
    pub += _encuadre(5)
    return macro('CCPildoras', h, pub)


def tercio():
    """Tercio inferior: el nombre sobre una caja oscura, el cargo en el color de acento y una barra; entra deslizándose."""
    h = acento()
    h += texto('Nombre', 0, 0, 'Nombre Apellido', 'Montserrat', 'Bold', 0.066, (0.5, 0.24), extra=caja(2, (0.06, 0.07, 0.11), (0.5, 0.42), 0.35, 0.88))
    h += texto('Cargo', 0, 60, 'CARGO O DESCRIPCIÓN', 'Inter 18pt', 'Medium', 0.04, (0.5, 0.168), color=ACENTO,
               expr={'Red1': 'Acento.TopLeftRed', 'Green1': 'Acento.TopLeftGreen', 'Blue1': 'Acento.TopLeftBlue'}, extra=sombra(4, 0.6))
    h += rect('LineaMask', -160, 140, (0.5, 0.203), 0.36, 0.007, expr={'Width': f'0.36 * {EO(P(8, 12))} * {S()}'})
    h += forma('Linea', 'LineaMask', -60, 140)
    c = Capas()
    e = EO(P(0, 13))
    c.poner('Nombre', dx=f'(1 - {e}) * (-0.3)', blend=f'{e} * {S()}')
    c.poner('Linea', blend=S())
    e2 = EO(P(6, 12))
    c.poner('Cargo', dx=f'(1 - {e2}) * (-0.2)', blend=f'{e2} * {S()}')
    h += c.cerrar()
    pub = [('Nombre', 'StyledText', 'Nombre', None, None), ('Cargo', 'StyledText', 'Cargo', None, None),
           ('Nombre', 'Font', 'Fuente', 2, None), ('Nombre', 'Style', None, 2, None)]
    pub += _fix(_color('Nombre', '', 'Color del nombre', 3))
    pub += _color('Acento', 'TopLeft', 'Color de acento', 4)
    pub += _encuadre(5)
    return macro('CCTercio', h, pub)


def cifra():
    """Un número grande que CUENTA desde 0 hasta el valor (con lo que va antes y después: «+», «%», «$»…), su etiqueta y una barra."""
    h = acento()
    controles = ('\t\t\t\t\tUserControls = ordered() {\n'
                 '\t\t\t\t\t\tValor = { LINKS_Name = "Número", LINKID_DataType = "Number", INPID_InputControl = "SliderControl", INP_Integer = false, '
                 'INP_MinScale = 0, INP_MaxScale = 1000, INP_Default = 250, ICS_ControlPage = "Text", },\n'
                 '\t\t\t\t\t\tPrefijo = { LINKS_Name = "Antes del número", LINKID_DataType = "Text", INPID_InputControl = "TextEditControl", '
                 'TEC_Lines = 1, ICS_ControlPage = "Text", },\n'
                 '\t\t\t\t\t\tSufijo = { LINKS_Name = "Después del número", LINKID_DataType = "Text", INPID_InputControl = "TextEditControl", '
                 'TEC_Lines = 1, ICS_ControlPage = "Text", },\n'
                 '\t\t\t\t\t},\n')
    cuenta = EO(P(4, 34))
    # (el motor de expresiones de Fusion no admite concatenar con «..» y exige tostring() sobre el texto: medido en generar_comps.palabra)
    expr = {'StyledText': f"('%s%d%s'):format(tostring(Numero.Prefijo.Value), math.floor(Numero.Valor * {cuenta} + 0.5), tostring(Numero.Sufijo.Value))",
            'Red1': 'Acento.TopLeftRed', 'Green1': 'Acento.TopLeftGreen', 'Blue1': 'Acento.TopLeftBlue'}
    h += texto('Numero', 0, 0, '+250%', 'Montserrat', 'ExtraBold', 0.16, (0.5, 0.53), color=ACENTO, expr=expr,
               extra=sombra(4, 0.5) + [I('Valor', 250), I('Prefijo', '+'), I('Sufijo', '%')], controles=controles)
    h += texto('Etiqueta', 0, 60, 'seguidores nuevos', 'Inter 18pt', 'Medium', 0.052, (0.5, 0.425), extra=sombra(4, 0.5))
    h += rect('BarraMask', -160, 140, (0.5, 0.465), 0.3, 0.008, expr={'Width': f'0.3 * {EO(P(10, 14))} * {S()}'})
    h += forma('Barra', 'BarraMask', -60, 140)
    c = Capas()
    e = BK(P(0, 12))
    c.poner('Numero', size=f'(0.6 + 0.4*{e}) * (0.92 + 0.08*{S()})', blend=f'math.min(1, {P(0, 12)} * 2.5) * {S()}', pivote=(0.5, 0.53))
    c.poner('Barra', blend=S())
    e2 = EO(P(10, 12))
    c.poner('Etiqueta', dy=f'(1 - {e2}) * (-0.02)', blend=f'{e2} * {S()}')
    h += c.cerrar()
    pub = [('Numero', 'Valor', 'Número', None, None), ('Numero', 'Prefijo', 'Antes del número', None, None),
           ('Numero', 'Sufijo', 'Después del número', None, None), ('Etiqueta', 'StyledText', 'Etiqueta', None, None),
           ('Numero', 'Font', 'Fuente', 2, None), ('Numero', 'Style', None, 2, None)]
    pub += _color('Acento', 'TopLeft', 'Color de acento', 4)
    pub += _encuadre(5)
    return macro('CCCifra', h, pub)


def lista():
    """Un título y tres puntos en cajas oscuras, numerados, que entran uno tras otro desde la izquierda."""
    h = acento()
    h += texto('Titulo', 0, 0, '3 CLAVES', 'Montserrat', 'ExtraBold', 0.09, (0.5, 0.68), extra=sombra(4),
               expr={'Red1': 'Acento.TopLeftRed', 'Green1': 'Acento.TopLeftGreen', 'Blue1': 'Acento.TopLeftBlue'}, color=ACENTO)
    ys = (0.575, 0.485, 0.395)
    for k, (y, t) in enumerate(zip(ys, ('1   Primera clave', '2   Segunda clave', '3   Tercera clave')), 1):
        expr = None if k == 1 else {'Font': 'L1.Font', 'Style': 'L1.Style', 'Red1': 'L1.Red1', 'Green1': 'L1.Green1', 'Blue1': 'L1.Blue1', 'Size': 'L1.Size'}
        h += texto(f'L{k}', 0, 70 * k, t, 'Inter 24pt', 'Bold', 0.06, (0.5, y), extra=caja(2, (0.07, 0.08, 0.12), (0.6, 0.34), 0.45, 0.9), expr=expr)
    c = Capas()
    e = BK(P(0, 12))
    c.poner('Titulo', size=f'(0.8 + 0.2*{e})', blend=f'math.min(1, {P(0, 12)} * 2.2) * {S()}', pivote=(0.5, 0.68))
    for k in range(1, 4):
        ek = EO(P(8 + 7 * (k - 1), 12))
        c.poner(f'L{k}', dx=f'(1 - {ek}) * (-0.25)', blend=f'{ek} * {S()}')
    h += c.cerrar()
    pub = [('Titulo', 'StyledText', 'Título', None, None), ('L1', 'StyledText', 'Punto 1', None, None), ('L2', 'StyledText', 'Punto 2', None, None),
           ('L3', 'StyledText', 'Punto 3', None, None), ('L1', 'Font', 'Fuente', 2, None), ('L1', 'Style', None, 2, None)]
    pub += _fix(_color('L1', '', 'Color del texto', 3))
    pub += _color('Acento', 'TopLeft', 'Color de acento', 4)
    pub += _encuadre(5)
    return macro('CCLista', h, pub)


def llamada():
    """Una llamada: un punto que late, una línea que se dibuja desde él y la etiqueta al final (en una caja del acento)."""
    h = acento()
    h += elipse('PuntoMask', -160, 0, (0.3, 0.5), 0.042, expr={'Width': f'0.042 * {BK(P(0, 10))}', 'Height': f'0.042 * {BK(P(0, 10))}'})
    h += forma('Punto', 'PuntoMask', -60, 0)
    largo = f'0.34 * {EO(P(6, 14))}'
    h += rect('LineaMask', -160, 80, (0.47, 0.5), 0.34, 0.009, radio=0.5, expr={'Width': largo, 'Center': f'Point(0.3 + ({largo}) / 2, 0.5)'})
    h += forma('Linea', 'LineaMask', -60, 80)
    h += texto('Etiqueta', 0, 160, 'Mira esto', 'Inter 24pt', 'Bold', 0.062, (0.64, 0.545), extra=caja(2, 'Acento', (0.45, 0.32)) + sombra(4, 0.45))
    c = Capas()
    c.poner('Punto', size='(1 + 0.12 * math.sin((time - comp.RenderStart) * 0.25))', blend=S(), pivote=(0.3, 0.5))
    c.poner('Linea', blend=S())
    e = BK(P(16, 11))
    c.poner('Etiqueta', size=f'(0.5 + 0.5*{e})', blend=f'math.min(1, {P(16, 11)} * 2.5) * {S()}', pivote=(0.64, 0.545))
    h += c.cerrar()
    pub = [('Etiqueta', 'StyledText', 'Texto', None, None), ('Etiqueta', 'Font', 'Fuente', 2, None), ('Etiqueta', 'Style', None, 2, None)]
    pub += _fix(_color('Etiqueta', '', 'Color del texto', 3))
    pub += _color('Acento', 'TopLeft', 'Color de acento', 4)
    pub += [('Anim1', 'Center', 'Posición del punto', None, None), ('Anim3', 'Center', 'Posición del texto', None, None)]
    pub += _encuadre(5)
    return macro('CCLlamada', h, pub)


MOTIONS = {'CC Titular': titular, 'CC Pildoras': pildoras, 'CC Tercio inferior': tercio, 'CC Cifra': cifra, 'CC Lista': lista, 'CC Llamada': llamada}


# ------------------------------------------------------------------------------------------------------------------ miniaturas
def miniatura(nombre, ruta):
    """La miniatura de la biblioteca de efectos (como las del Luxe): fondo oscuro, la forma del motion en el color de acento y su nombre."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 320, 180
    im = Image.new('RGB', (W, H), (12, 14, 22))
    d = ImageDraw.Draw(im)
    ac = tuple(int(c * 255) for c in ACENTO)
    fuentes = RECURSOS / 'fonts'
    f_b = ImageFont.truetype(str(fuentes / 'Montserrat-ExtraBold.ttf'), 22)
    f_s = ImageFont.truetype(str(fuentes / 'Inter_18pt-Medium.ttf'), 13)
    clave = nombre.replace('CC ', '')
    if clave == 'Titular':
        d.text((W / 2, 70), 'TÍTULO', font=ImageFont.truetype(str(fuentes / 'Montserrat-ExtraBold.ttf'), 34), fill=(255, 255, 255), anchor='mm')
        d.rounded_rectangle([90, 94, 230, 99], 3, fill=ac)
        d.text((W / 2, 116), 'subtítulo', font=f_s, fill=(200, 205, 220), anchor='mm')
    elif clave == 'Pildoras':
        for k, y in enumerate((52, 90, 128)):
            d.rounded_rectangle([95, y - 14, 225, y + 14], 14, fill=ac)
            d.text((W / 2, y), ('Primera', 'Segunda', 'Tercera')[k], font=f_s, fill=(255, 255, 255), anchor='mm')
    elif clave == 'Tercio inferior':
        d.rounded_rectangle([70, 108, 250, 136], 8, fill=(30, 34, 48))
        d.text((W / 2, 122), 'Nombre Apellido', font=f_s, fill=(255, 255, 255), anchor='mm')
        d.rounded_rectangle([110, 141, 210, 144], 2, fill=ac)
        d.text((W / 2, 155), 'CARGO', font=ImageFont.truetype(str(fuentes / 'Inter_18pt-Medium.ttf'), 10), fill=ac, anchor='mm')
    elif clave == 'Cifra':
        d.text((W / 2, 72), '+250%', font=ImageFont.truetype(str(fuentes / 'Montserrat-ExtraBold.ttf'), 44), fill=ac, anchor='mm')
        d.rounded_rectangle([115, 100, 205, 103], 2, fill=ac)
        d.text((W / 2, 120), 'seguidores nuevos', font=f_s, fill=(255, 255, 255), anchor='mm')
    elif clave == 'Lista':
        d.text((W / 2, 34), '3 CLAVES', font=f_b, fill=ac, anchor='mm')
        for k, y in enumerate((70, 102, 134)):
            d.rounded_rectangle([90, y - 12, 230, y + 12], 9, fill=(30, 34, 48))
            d.text((W / 2, y), f'{k + 1}   Clave', font=f_s, fill=(255, 255, 255), anchor='mm')
    elif clave == 'Llamada':
        d.ellipse([88, 92, 102, 106], fill=ac)
        d.rounded_rectangle([95, 97, 205, 101], 2, fill=ac)
        d.rounded_rectangle([170, 66, 260, 90], 12, fill=ac)
        d.text((215, 78), 'Mira esto', font=f_s, fill=(255, 255, 255), anchor='mm')
    d.text((10, H - 8), nombre, font=ImageFont.truetype(str(fuentes / 'Inter_18pt-Medium.ttf'), 11), fill=(120, 128, 150), anchor='ls')
    im.save(ruta, optimize=True)


# ------------------------------------------------------------------------------------------------------------------ construir
def construir(salida=None):
    destino = SALIDA_DIR / 'Edit' / 'Titles' / CARPETA
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob('*'):
        if viejo.suffix in ('.setting', '.png') and viejo.stem not in MOTIONS:
            viejo.unlink()
    for nombre, f in MOTIONS.items():
        (destino / f'{nombre}.setting').write_text(f(), encoding='utf-8', newline='\n')
        miniatura(nombre, destino / f'{nombre}.png')
    drfx = Path(salida) if salida else DRFX
    tmp = drfx.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for carpeta in ('Edit/', 'Edit/Titles/', f'Edit/Titles/{CARPETA}/'):
            z.writestr(carpeta, '')
        for archivo in sorted(destino.iterdir()):
            z.write(archivo, f'Edit/Titles/{CARPETA}/{archivo.name}')
    os.replace(tmp, drfx)
    return drfx


if __name__ == '__main__':
    r = construir(sys.argv[1] if len(sys.argv) > 1 else None)
    print(r, r.stat().st_size, 'bytes;', ', '.join(MOTIONS))
