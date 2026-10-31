# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/macro_kinetic.py — v5.57: cada comp del Tema 1 dentro de un macro «CineCaptions» con los controles de Luxe Slide y SOLO el banner de CineCaptions.
"""
El Inspector del Edit enseña el PRIMER tool de la comp (banner_inspector): hasta la v5.56 en el Tema 1 era el Text+ «Template» en bruto (o la máscara
de un aro o un trazo). El usuario, con capturas: «utiliza las herramientas de Luxe Slide y solo le pones el banner, ya que actualmente los Text+ se
ven así» y «DROP SHADOW y GLOW, que funcionen; al final yo decido». Ahora:

  · toda la comp va DENTRO de un MacroOperator «CineCaptions» (el primer tool; MediaOut1 sigue fuera, a primer nivel: sin él el clip sale negro);
  · el Text+ «Template» sigue llamándose así y es el PRIMER tool del macro: la app lo encuentra con FindTool("Template") y le escribe el texto, el
    Size y la letra como siempre (por eso esas entradas se publican DIRECTAS, nunca por expresión como en el Luxe Slide: la expresión pisaría el
    SetInput de GO sin avisar);
  · se publica la pestaña «Controles» de Luxe Slide, en su orden y con sus agrupaciones: texto, fuente y estilo, Size, Tracking, interlineado,
    Center, Align, Text Shading (Solid / Gradient), Color, Shading Gradient, DROP SHADOW y GLOW CONTROLS. Sin la pestaña Anim (chocaría con la
    animación propia del kit) ni la rama «Apply»;
  · detrás de la salida de siempre van las herramientas de Luxe Slide: Posicion (el Center: mueve la caption ENTERA, caja y relleno incluidos), glow1 y
    glow2 (el GLOW de Luxe, con sus casillas y tamaños) y dropShadow (la DROP SHADOW con Strength, Angle, Distance, Blur y Color; con el Shadow NATIVO
    de Fusion en vez de la ResolveFX: nada de marca de agua en Resolve Free), y clamp. Todas APAGADAS de fábrica (PassThrough): el clip se ve
    exactamente igual que antes hasta que el usuario las enciende en el Inspector;
  · el banner (banner_inspector.LABEL, con el logo) va en los UserControls del propio macro con IC_ControlPage = -1: encima de las pestañas, como la
    cabecera de Luxe Slide (que no viaja). En el Template no va nada (banner_inspector.con_banner salta estas comps).

    envolver(tools) -> tools      el texto de las tools de una comp del Tema 1 (con MediaOut1 al final) ya dentro del macro
También el Tema 3 (viral_elementos, «Sí, en los 6»): envolver publica solo lo que siguen las copias del texto (Medida, BrilloTxt, Caja).
"""
import re

import banner_inspector as BI
from kinetic_comps import n

NOMBRE = 'CineCaptions'                  # (nunca «Template»: FindTool("Template") devolvería el macro y la app caería al bucle lento)
TEXTO = 'Template'
NUEVAS = ('Posicion', 'glow1', 'glow2', 'dropShadow', 'clamp')


def _bloques(t):
    """[(nombre, tipo, texto)] de las tools de primer nivel del texto de Tools que arman kinetic_comps / kinetic_elementos (cada una empieza con dos
    tabuladores y su nombre; su texto incluye la coma y el salto de línea que la cierran)."""
    out, i = [], 0
    for m in re.finditer(r'(?m)^\t\t(\w+) = (\w+) \{', t):
        if m.start() < i:
            continue
        fin = BI._cerrar(t, t.index('{', m.start()))
        j = fin + 1
        j += t.startswith(',', j)
        j += t.startswith('\n', j)
        out.append((m.group(1), m.group(2), t[m.start():j]))
        i = j
    if ''.join(b[2] for b in out).strip() != t.strip():
        raise ValueError('macro_kinetic: el texto de las tools no tiene la forma esperada')
    return out


def _valor(bloque, entrada, defecto):
    m = re.search(r'\b' + entrada + r' = Input \{ Value = ([0-9.eE+-]+)', bloque)
    return n(float(m.group(1))) if m else n(defecto)


def _con_input(bloque, linea):
    """Una entrada más en el «Inputs = {» de la tool."""
    k = bloque.index('Inputs = {') + len('Inputs = {')
    return bloque[:k] + '\n\t\t\t\t' + linea + bloque[k:]


def _con_controles(bloque, controles):
    """UserControls en la tool (junto a CtrlWZoom, el primer campo que escriben kinetic_comps.herramienta / texto_plus)."""
    k = bloque.index('{') + 1
    return bloque[:k] + '\n\t\t\tUserControls = ordered() { ' + controles + ' },' + bloque[k:]


# ------------------------------------------------------------------------------------------------------------------ los controles de Luxe Slide
# «Text Shading» del Luxe Slide (MultiButton de su Text1) sin «Apply» (la rama del fondo de la línea de tiempo no casa con la animación del kit):
# Solid = el color de «Color» (Type1 = 0) · Gradient = «Shading Gradient» (Type1 = 2, lo que ya llevan los héroes, el serif y el pincel)
TEXT_SHADING = (
    'TextShading = { { MBTNC_AddButton = "Solid" }, { MBTNC_AddButton = "Gradient" }, INP_MaxAllowed = 1000000, INP_Integer = false, '
    'INPID_InputControl = "MultiButtonControl", INP_MaxScale = 1, MBTNC_ShowBasicButton = true, INP_SplineType = "Default", INP_External = false, '
    'INPS_ExecuteOnChange = "local mode = Template:GetInput(\'TextShading\')\\n\\nif mode == 0 then\\n    Template.Type1 = 0\\nelseif mode == 1 then\\n'
    '    Template.Type1 = 2\\nend", INP_MinScale = 0, INP_MinAllowed = -1000000, LINKID_DataType = "Number", MBTNC_ShowName = false, '
    'MBTNC_StretchToFit = false, MBTNC_ShowToolTip = false, LINKS_Name = "Text Shading", }')

# el clamp de Luxe (que nada pase de blanco con el brillo) solo trabaja si GLOW o DROP SHADOW están encendidos
_CLAMP = "\\nclamp:SetAttrs( { TOOLB_PassThrough = not (enabled == 1 or %s) } )"

CONTROLES_GLOW = (
    'Enabled = { INP_MaxAllowed = 1000000, INP_Integer = false, INPID_InputControl = "CheckboxControl", INP_MaxScale = 1, INP_SplineType = "Default", '
    'INP_MinScale = 0, INP_External = false, LINKID_DataType = "Number", INPS_ExecuteOnChange = "local enabled = glow1:GetInput(\'Enabled\')\\n\\n'
    'if enabled == 1 then\\n    glow1:SetAttrs( { TOOLB_PassThrough = false } )\\n    glow2:SetAttrs( { TOOLB_PassThrough = false } )\\nelseif enabled == 0 then\\n'
    '    glow1:SetAttrs( { TOOLB_PassThrough = true } )\\n    glow2:SetAttrs( { TOOLB_PassThrough = true } )\\nend'
    + _CLAMP % "dropShadow:GetInput('Shadow') == 1" + '", CBC_TriState = false, INP_MinAllowed = -1000000, LINKS_Name = "Enabled", }, '
    'GlowSize = { INP_Integer = false, INP_MinScale = 0, LINKID_DataType = "Number", INP_MaxScale = 100, INPID_InputControl = "SliderControl", '
    'INP_SplineType = "Default", LINKS_Name = "Glow Size", }, '
    'GlowIntensity = { INP_Integer = false, LINKID_DataType = "Number", INPID_InputControl = "SliderControl", INP_SplineType = "Default", '
    'LINKS_Name = "Glow Intensity", }, '
    'glowLabel = { LBLC_DropDownButton = true, LINKID_DataType = "Number", LBLC_NumInputs = 5, INPID_InputControl = "LabelControl", '
    'LINKS_Name = "GLOW CONTROLS", }, '
    'glowHidden1 = { LBLC_DropDownButton = true, LINKID_DataType = "Number", LBLC_NumInputs = 3, LINKS_Name = "HiddenLabel", '
    'INPID_InputControl = "LabelControl", IC_Visible = false, }')

CONTROLES_SOMBRA = (
    'Shadow = { CBC_TriState = false, INP_Integer = false, INP_External = false, INPID_InputControl = "CheckboxControl", INPS_ExecuteOnChange = '
    '"local enabled = dropShadow:GetInput(\'Shadow\')\\n\\nif enabled == 1 then\\n    dropShadow:SetAttrs( { TOOLB_PassThrough = false } )\\n'
    'elseif enabled == 0 then\\n    dropShadow:SetAttrs( { TOOLB_PassThrough = true } )\\nend' + _CLAMP % "glow1:GetInput('Enabled') == 1"
    + '", LINKID_DataType = "Number", INP_SplineType = "Default", LINKS_Name = "Shadow", }, '
    'dropLabel = { LBLC_DropDownButton = true, LINKID_DataType = "Number", LBLC_NumInputs = 11, INPID_InputControl = "LabelControl", '
    'LINKS_Name = "DROP SHADOW", }, '
    'dropHidden1 = { LBLC_DropDownButton = true, LINKID_DataType = "Number", LBLC_NumInputs = 9, LINKS_Name = "HiddenLabel", '
    'INPID_InputControl = "LabelControl", IC_Visible = false, }, '
    'shadowAngle = { INP_Integer = false, INP_External = false, LINKID_DataType = "Number", INPID_InputControl = "SliderControl", INP_MinScale = -180, '
    'INP_MaxScale = 180, INP_Default = 25.1, INP_SplineType = "Default", LINKS_Name = "Drop Angle", }, '
    'ShadowDistance = { INP_Integer = false, INP_External = false, LINKID_DataType = "Number", INPID_InputControl = "SliderControl", INP_MinScale = 0, '
    'INP_MaxScale = 0.2, INP_MinAllowed = 0, INP_Default = 0, INP_SplineType = "Default", LINKS_Name = "Drop Distance", }')

# la DROP SHADOW de Luxe (ResolveFX: Shadow Strength, Drop Angle, Drop Distance, Blur, Color) con el Shadow nativo: Strength = Blend, Blur = Softness y el
# Offset sale del ángulo y la distancia. El ángulo se mide hacia ABAJO como en pantalla (la sombra CAE: con 25,1° abajo a la derecha; en Fusion la Y
# crece hacia arriba, de ahí el «−»; la revisión midió que con «+» subía) y la Y va en fracción del alto (se corrige con el aspecto del cuadro)
_OFFSET = ('Point(0.5 + ShadowDistance*math.cos(math.rad(shadowAngle)), 0.5 - ShadowDistance*math.sin(math.rad(shadowAngle))'
           '*((comp:GetPrefs(\\"Comp.FrameFormat.Width\\") or 1080)/(comp:GetPrefs(\\"Comp.FrameFormat.Height\\") or 1920)))')


def _nuevas(origen):
    """Posicion → glow1 → glow2 → dropShadow → clamp detrás de `origen` (la tool que hoy entra en MediaOut1). Todo en PassThrough salvo Posicion
    (un Transform quieto, que el Center del Inspector mueve)."""
    return (
        f'\t\tPosicion = Transform {{\n\t\t\tCtrlWShown = false,\n\t\t\tNameSet = true,\n\t\t\tInputs = {{\n'
        f'\t\t\t\tInput = Input {{ SourceOp = "{origen}", Source = "Output", }},\n\t\t\t}},\n\t\t\tViewInfo = OperatorInfo {{ Pos = {{ 460, 40 }} }},\n\t\t}},\n'
        '\t\tglow1 = Glow {\n\t\t\tPassThrough = true,\n\t\t\tCtrlWShown = false,\n\t\t\tNameSet = true,\n\t\t\tInputs = {\n'
        '\t\t\t\tBlend = Input { Value = 0.24, Expression = "glow1.GlowIntensity*.5", },\n'
        '\t\t\t\tFilter = Input { Value = FuID { "Fast Gaussian" }, },\n'
        '\t\t\t\tXGlowSize = Input { Value = 2.595, Expression = "glow1.GlowSize*.15", },\n'
        '\t\t\t\tGlow = Input { Value = 0.488, },\n'
        '\t\t\t\tInput = Input { SourceOp = "Posicion", Source = "Output", },\n'
        '\t\t\t\tGlowSize = Input { Value = 17.3, },\n\t\t\t\tGlowIntensity = Input { Value = 0.48, },\n'
        '\t\t\t\tglowHidden1 = Input { Expression = "Enabled", },\n\t\t\t},\n'
        '\t\t\tViewInfo = OperatorInfo { Pos = { 620, 40 } },\n'
        f'\t\t\tUserControls = ordered() {{ {CONTROLES_GLOW} }},\n\t\t}},\n'
        '\t\tglow2 = Glow {\n\t\t\tPassThrough = true,\n\t\t\tCtrlWShown = false,\n\t\t\tNameSet = true,\n\t\t\tInputs = {\n'
        '\t\t\t\tBlend = Input { Value = 0.24, Expression = "glow1.GlowIntensity*.5", },\n'
        '\t\t\t\tFilter = Input { Value = FuID { "Fast Gaussian" }, },\n'
        '\t\t\t\tXGlowSize = Input { Value = 34.6, Expression = "glow1.GlowSize*2", },\n'
        '\t\t\t\tGlow = Input { Value = 0.638, },\n'
        '\t\t\t\tInput = Input { SourceOp = "glow1", Source = "Output", },\n\t\t\t},\n'
        '\t\t\tViewInfo = OperatorInfo { Pos = { 780, 40 } },\n\t\t},\n'
        '\t\tdropShadow = Shadow {\n\t\t\tPassThrough = true,\n\t\t\tCtrlWShown = false,\n\t\t\tNameSet = true,\n\t\t\tInputs = {\n'
        '\t\t\t\tBlend = Input { Value = 0.882, },\n'
        f'\t\t\t\tShadowOffset = Input {{ Value = {{ 0.5, 0.5 }}, Expression = "{_OFFSET}", }},\n'
        '\t\t\t\tSoftness = Input { Value = 0.02, },\n'
        '\t\t\t\tRed = Input { Value = 0, },\n\t\t\t\tGreen = Input { Value = 0, },\n\t\t\t\tBlue = Input { Value = 0, },\n\t\t\t\tAlpha = Input { Value = 1, },\n'
        '\t\t\t\tInput = Input { SourceOp = "glow2", Source = "Output", },\n'
        '\t\t\t\tshadowAngle = Input { Value = 25.1, },\n\t\t\t\tShadowDistance = Input { Value = 0, },\n\t\t\t\tShadow = Input { Value = 0, },\n'
        '\t\t\t\tdropHidden1 = Input { Value = 0, Expression = "Shadow", },\n\t\t\t},\n'
        '\t\t\tViewInfo = OperatorInfo { Pos = { 940, 40 } },\n'
        f'\t\t\tUserControls = ordered() {{ {CONTROLES_SOMBRA} }},\n\t\t}},\n'
        '\t\tclamp = BrightnessContrast {\n\t\t\tPassThrough = true,\n\t\t\tCtrlWShown = false,\n\t\t\tNameSet = true,\n\t\t\tInputs = {\n'
        '\t\t\t\tAlpha = Input { Value = 1, },\n\t\t\t\tClipBlack = Input { Value = 1, },\n\t\t\t\tClipWhite = Input { Value = 1, },\n'
        '\t\t\t\tInput = Input { SourceOp = "dropShadow", Source = "Output", },\n\t\t\t},\n'
        '\t\t\tViewInfo = OperatorInfo { Pos = { 1100, 40 } },\n\t\t},\n')


def _ii(clave, tool, entrada, *extra):
    return f'\t\t\t\t{clave} = InstanceInput {{ SourceOp = "{tool}", Source = "{entrada}", ' + ''.join(e + ', ' for e in extra) + '},'


def _divisor(clave):
    return _ii(clave, TEXTO, 'Blank5')


def _sombra_y_brillo():
    """DROP SHADOW (11 controles detrás de su etiqueta; 9 detrás de la oculta) y GLOW CONTROLS (5; 3): los recuentos de LBLC_NumInputs del Luxe Slide."""
    return [
        _ii('dropLabel', 'dropShadow', 'dropLabel'),
        _ii('Input26', 'dropShadow', 'Shadow', 'Default = 0'),
        _ii('dropHidden1', 'dropShadow', 'dropHidden1', 'Expression = "Shadow"'),
        _divisor('Divider04'),
        _ii('Input19', 'dropShadow', 'Blend', 'Name = "Shadow Strength"', 'Default = 0.882'),
        _ii('Input20', 'dropShadow', 'shadowAngle', 'Default = 25.1'),
        _ii('Input21', 'dropShadow', 'ShadowDistance', 'MaxScale = 0.2', 'Default = 0'),
        _ii('Input22', 'dropShadow', 'Softness', 'Name = "Blur"', 'MaxScale = 0.1', 'Default = 0.02'),
        _divisor('Divider05'),
        _ii('Input23', 'dropShadow', 'Red', 'Name = "Color"', 'ControlGroup = 19', 'Default = 0'),
        _ii('Input24', 'dropShadow', 'Green', 'ControlGroup = 19', 'Default = 0'),
        _ii('Input25', 'dropShadow', 'Blue', 'ControlGroup = 19', 'Default = 0'),
        _ii('glowLabel', 'glow1', 'glowLabel'),
        _ii('Input27', 'glow1', 'Enabled', 'Name = "Glow"'),
        _ii('glowHidden1', 'glow1', 'glowHidden1', 'Expression = "Enabled"'),
        _divisor('Divider06'),
        _ii('Input28', 'glow1', 'GlowSize', 'Default = 17.3'),
        _ii('Input29', 'glow1', 'GlowIntensity', 'Default = 0.48'),
    ]


def _controles_texto(plantilla, fuente=True, alinear=True, interlineado=True, tracking=True, color=True):
    """La pestaña «Controles» de Luxe Slide sobre el Text+ «Template» (el «reinicio» de cada control = el valor del clip en el pack).
    `fuente` / `interlineado` / `tracking` = False donde una copia del texto no los sigue (el «Relleno» del héroe: solo sigue texto, Size y
    Tracking; Font y Style por expresión dejaban la comp negra en Resolve, kinetic_elementos._relleno); `alinear` = False también en las cintas (su
    caja sigue el ANCHO del texto, no su sitio: con «Align» izquierda el texto se salía de la cinta, revisión v5.57). `color`: True = Text Shading +
    Color + Shading Gradient; 'solo' = solo Color (el drag del Tema 3: su relleno sigue a Red1, el degradado solo pintaría el contorno); False = nada."""
    lineas = [_ii('Input1', TEXTO, 'StyledText')]
    if fuente:
        lineas += [_ii('Input2', TEXTO, 'Font', 'ControlGroup = 2'), _ii('Input3', TEXTO, 'Style', 'ControlGroup = 2')]
    lineas.append(_ii('Input4', TEXTO, 'Size', 'Name = "Size"', 'Default = ' + _valor(plantilla, 'Size', 0.1)))
    if tracking:
        lineas.append(_ii('Input5', TEXTO, 'CharacterSpacingClone', 'Name = "Tracking"', 'Default = ' + _valor(plantilla, 'CharacterSpacing', 1)))
    if interlineado:
        lineas.append(_ii('Input6', TEXTO, 'LineSpacingClone', 'Default = ' + _valor(plantilla, 'LineSpacing', 1)))
    lineas += [
        _ii('Input7', 'Posicion', 'Center', 'Name = "Center"'),
        _divisor('Divider01'),
    ]
    if alinear:
        lineas += [_ii('InputLeft', TEXTO, 'HorizontalJustificationLeft', 'Name = "Align"', 'ControlGroup = 132'),
                   _ii('InputCenter', TEXTO, 'HorizontalJustificationCenter', 'ControlGroup = 132'),
                   _ii('InputRight', TEXTO, 'HorizontalJustificationRight', 'ControlGroup = 132'),
                   _divisor('Divider15')]
    rgba = [
        _ii('Input8', TEXTO, 'Red1', 'Name = "Color"', 'ControlGroup = 7', 'Default = ' + _valor(plantilla, 'Red1', 1)),
        _ii('Input9', TEXTO, 'Green1', 'ControlGroup = 7', 'Default = ' + _valor(plantilla, 'Green1', 1)),
        _ii('Input10', TEXTO, 'Blue1', 'ControlGroup = 7', 'Default = ' + _valor(plantilla, 'Blue1', 1)),
        _ii('Input11', TEXTO, 'Alpha1', 'ControlGroup = 7', 'Default = 1'),
    ]
    if color is True:
        degradado = bool(re.search(r'\bType1 = Input \{ Value = 2,', plantilla))
        lineas += [_ii('Input17', TEXTO, 'TextShading', 'Default = ' + ('1' if degradado else '0')), _divisor('Divider02')] + rgba + [
            _ii('Input12', TEXTO, 'ShadingGradient1', 'Name = "Shading Gradient"'),
            _ii('Input13', TEXTO, 'ShadingMappingAngle1', 'Name = "Mapping Angle"', 'Default = 0'),
            _ii('Input14', TEXTO, 'ShadingMappingSize1', 'Name = "Mapping Size"', 'Default = 1'),
            _ii('Input15', TEXTO, 'ShadingMappingAspect1', 'Name = "Mapping Aspect"', 'Default = 1'),
            _ii('Input16', TEXTO, 'ShadingMappingLevel1', 'Name = "Mapping Level"', 'Default = 4'),
        ]
    elif color == 'solo':
        lineas += rgba + [_divisor('Divider02')]
    return lineas + _sombra_y_brillo()


def _controles_trazo(relleno, bloque):
    """Aros, líneas y trazos (sin texto): su Center, su color (el Background `relleno` que pinta el trazo; reinicio = su color) y DROP SHADOW / GLOW."""
    return [
        _ii('Input7', 'Posicion', 'Center', 'Name = "Center"'),
        _divisor('Divider01'),
        _ii('Input8', relleno, 'TopLeftRed', 'Name = "Color"', 'ControlGroup = 7', 'Default = ' + _valor(bloque, 'TopLeftRed', 1)),
        _ii('Input9', relleno, 'TopLeftGreen', 'ControlGroup = 7', 'Default = ' + _valor(bloque, 'TopLeftGreen', 1)),
        _ii('Input10', relleno, 'TopLeftBlue', 'ControlGroup = 7', 'Default = ' + _valor(bloque, 'TopLeftBlue', 1)),
        _divisor('Divider02'),
    ] + _sombra_y_brillo()


# ------------------------------------------------------------------------------------------------------------------ el macro
def _sigue(bloque, entrada):
    """¿La tool `bloque` lleva `entrada` enlazada a la del Template («Size = Input { …, Expression = "Template.Size", }»)?"""
    return re.search(r'(?m)^\s*' + entrada + r' = Input \{[^\n]*Expression = "' + TEXTO + r'\.' + entrada + '"', bloque) is not None


def envolver(tools, fuente=None, tracking=None, interlineado=None, alinear=None, color=True):
    """Las tools de una comp del Tema 1 o del Tema 3 (texto de kinetic_elementos / viral_elementos, con MediaOut1 al final) dentro del macro
    «CineCaptions». None = automático: con COPIAS del texto (Text+ con StyledText = Template.StyledText: el «Relleno» del héroe; Medida, BrilloTxt y
    Caja de VIRAL) la fuente, el Tracking y el interlineado se publican SOLO si todas las copias los siguen (si no, la copia se descuadra: la caja,
    los trozos del shatter, la medida de la palabra); Align, solo sin copias ni cinta («Rec»). `color`: ver _controles_texto."""
    bloques = _bloques(tools)
    nombres = [b[0] for b in bloques]
    if NOMBRE in nombres or any(x in nombres for x in NUEVAS) or nombres.count('MediaOut1') != 1 or TEXTO not in nombres:
        raise ValueError('macro_kinetic: comp inesperada (' + ', '.join(nombres) + ')')
    media = next(b for b in bloques if b[0] == 'MediaOut1')
    origen = re.search(r'Input = Input \{ SourceOp = "(\w+)", Source = "Output", \}', media[2]).group(1)
    dentro = [b for b in bloques if b[0] != 'MediaOut1']
    dentro.sort(key=lambda b: b[0] != TEXTO)              # el Template, el PRIMERO (la app y packs_drt buscan el primer Text+)
    plantilla = dentro[0][2]
    if re.search(r'StyledText = Input \{ Value = "([^"]*)"', plantilla).group(1).strip():     # (aros, líneas y trazos: un Template « » sin conectar)
        copias = [b for b in dentro if b[1] == 'TextPlus' and b[0] != TEXTO and _sigue(b[2], 'StyledText')]

        def todas(*entradas):
            return all(_sigue(c[2], e) for c in copias for e in entradas)
        publicadas = _controles_texto(plantilla, fuente=todas('Font', 'Style') if fuente is None else fuente,
                                      alinear=(not copias and 'Rec' not in nombres) if alinear is None else alinear,
                                      interlineado=todas('LineSpacing') if interlineado is None else interlineado,
                                      tracking=todas('CharacterSpacing') if tracking is None else tracking, color=color)
        if color is True:
            plantilla = _con_controles(plantilla, TEXT_SHADING)
            if re.search(r'\bType1 = Input \{ Value = 2,', plantilla):
                plantilla = _con_input(plantilla, 'TextShading = Input { Value = 1, },')   # (el botón, en «Gradient»: es lo que ya lleva)
        dentro[0] = (TEXTO, dentro[0][1], plantilla)
    else:
        pinta = next((b for b in dentro if b[0] in ('Tinta', 'Trazo') and b[1] == 'Background'), None)
        if pinta is None:
            raise ValueError('macro_kinetic: trazo sin su Background (Tinta/Trazo)')
        publicadas = _controles_trazo(pinta[0], pinta[2])
    cuerpo = ''.join(b[2] for b in dentro)
    if not cuerpo.endswith(',\n'):
        cuerpo = cuerpo.rstrip().rstrip(',') + ',\n'
    macro = (f'\t\t{NOMBRE} = MacroOperator {{\n\t\t\tCtrlWZoom = false,\n\t\t\tInputs = ordered() {{\n' + '\n'.join(publicadas) + '\n\t\t\t},\n'
             '\t\t\tOutputs = {\n\t\t\t\tMainOutput1 = InstanceOutput { SourceOp = "clamp", Source = "Output", }\n\t\t\t},\n'
             '\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },\n'
             f'\t\t\tTools = ordered() {{\n{cuerpo}{_nuevas(origen)}\t\t\t}},\n'
             f'\t\t\tUserControls = ordered() {{ {BI.LABEL}}}\n\t\t}},\n')
    salida = media[2].replace(f'SourceOp = "{origen}", Source = "Output"', 'SourceOp = "clamp", Source = "Output"', 1)
    return macro + salida
