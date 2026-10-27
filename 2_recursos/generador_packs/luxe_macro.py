# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/luxe_macro.py — pone los macros REALES «Luxe Shine» (principal) y «Luxe Slide» (el resto) del Luxe Title Pack en cada clip, con la tipografía, el color y la posición de cada variante.
"""
Los macros del Luxe Title Pack viajan DENTRO de la comp: se toman tal cual de un .drb del pack
(luxe_shine_*.lua / luxe_slide_*.lua + su cabecera, extraídos una vez con extraer_base) y se le cambian solo los valores:

    Text1.Font / Style / color / texto        (la herramienta Text+ que hay dentro del macro)
    sizeCtrl.RestingSize                      (tamaño en reposo)
    positionCtrl.RestingCenter + Text1.Center (posición)

La app escribe el texto en el primer Text+ que encuentra (Text1), igual que con los packs Luxe de antes.
"""
import os
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
# v5.8 (pedido: «todos los textos plus deben ser del paquete Luxe Title Pack, sin excepción»): además del macro Luxe Shine ahora viaja
# el Luxe Slide REAL (sacado del clip «arriba» de «Base titulos dinamicos vertical.drb»). Antes contexto/complemento/base eran una
# imitación hecha con Text+ sueltos que solo se llamaba «Luxe Slide».
# v5.48: los tres macros salen del Luxe Title Pack v1.09 (extraer_de_setting) y se suma «Luxe Count» (números que suben contando).
ARCHIVOS = {'shine': ('luxe_shine_base.lua', 'luxe_shine_cabecera.txt'), 'slide': ('luxe_slide_base.lua', 'luxe_slide_cabecera.txt'),
            'count': ('luxe_count_base.lua', 'luxe_count_cabecera.txt')}
MACROS_V109 = {'shine': 'Luxe Shine', 'slide': 'Luxe Slide', 'count': 'Luxe Count'}
TEMPLATE_V109 = 'VBT - Luxe Title Pack/Edit/Titles/Van Beek Tools/Luxe Title Pack/'
BASE = os.path.join(AQUI, ARCHIVOS['shine'][0])
CABECERA = os.path.join(AQUI, ARCHIVOS['shine'][1])


def _rutas(tipo):
    base, cabecera = ARCHIVOS[tipo]
    return os.path.join(AQUI, base), os.path.join(AQUI, cabecera)


def extraer_base(drb, clip='principal', tipo='shine'):
    """Guarda el macro y la cabecera de la comp de ese clip del .drb (una sola vez). tipo: 'shine' | 'slide'."""
    BASE, CABECERA = _rutas(tipo)
    import binascii
    import struct
    import zipfile
    import zlib
    z = zipfile.ZipFile(drb)
    ruta = next(n for n in z.namelist() if n.endswith('MpFolder.xml') and '/Master/0' in '/' + n)
    xml = z.read(ruta).decode('utf-8')
    for m in re.finditer(r'<Sm2MpGenerator.*?</Sm2MpGenerator>', xml, re.S):
        if re.search(r'<Name>' + re.escape(clip) + '</Name>', m.group(0)):
            h = re.search(r'<CompositionBA>([0-9a-f]*)</CompositionBA>', m.group(0)).group(1)
            cab = zlib.decompress(binascii.unhexlify(h)[4:])
            i = cab.index(b'Composition {')
            n = struct.unpack('>I', cab[i - 4:i])[0]
            datos = cab[i:i + n]
            z0 = datos.index(b'\x00')
            cabecera = datos[:z0].decode('utf-8', 'replace')
            tools = zlib.decompress(datos[z0 + 5:]).decode('utf-8', 'replace')
            open(BASE, 'w', encoding='utf-8').write(tools)
            open(CABECERA, 'w', encoding='utf-8').write(cabecera)
            return len(tools), len(cabecera)
    raise SystemExit('no encuentro el clip ' + clip)


def extraer_de_setting(drfx, tipo):
    """v5.48: guarda la base de ese macro sacándola del .setting del .drfx del Luxe Title Pack (v1.09), con la misma forma que las sacadas de un .drb
    (todo en una línea, espacios simples fuera de las cadenas). La cabecera de la comp es la de siempre con el TEMPLATE_ID del macro nuevo."""
    import zipfile
    BASE, CABECERA = _rutas(tipo)
    nombre = MACROS_V109[tipo]
    z = zipfile.ZipFile(drfx)
    s = z.read(next(n for n in z.namelist() if n.endswith('/' + nombre + '.setting'))).decode('utf-8')
    # todo lo que hay en el «Tools = ordered()» de arriba: el macro y, a su lado, sus curvas (LUTLookup) y modificadores
    i = s.index('{', s.index('Tools = ordered()'))
    prof, k, en_cadena = 0, i, False
    while True:                                   # la llave que cierra ese bloque (saltando las de dentro de las cadenas)
        ch = s[k]
        if ch == '"' and s[k - 1] != '\\':
            en_cadena = not en_cadena
        elif not en_cadena and ch in '{}':
            prof += 1 if ch == '{' else -1
            if prof == 0:
                break
        k += 1
    partes = re.split(r'("(?:[^"\\]|\\.)*")', s[i:k + 1])
    for n in range(0, len(partes), 2):
        partes[n] = re.sub(r',\s*\}', ', }', re.sub(r'\s+', ' ', partes[n]))
    tools = ''.join(partes)
    m = re.search(r'MainOutput1 = InstanceOutput \{ SourceOp = "([^"]+)", Source = "Output", \}', tools)
    if not tools.startswith('{ ' + nombre.replace(' ', '') + ' = MacroOperator {') or not m or not tools.endswith(' }'):
        raise SystemExit(f'{nombre}: el .setting no tiene la forma esperada')
    # el .setting es solo el macro: la comp de un título necesita además su MediaOut (sin él Resolve pinta el clip NEGRO, probado en 5.48)
    tools = tools[:-2].rstrip().rstrip(',') + (', MediaOut1 = MediaOut { Inputs = { Index = Input { Value = "0", }, Input = Input { SourceOp = "%s", '
                                               'Source = "Output", } }, ViewInfo = OperatorInfo { Pos = { 440, 49.5 } }, } }' % m.group(1))
    cabecera = open(_rutas('slide')[1], encoding='utf-8').read()
    cabecera = re.sub(r'TEMPLATE_ID = "[^"]*"', f'TEMPLATE_ID = "{TEMPLATE_V109}{nombre}"', cabecera, count=1)
    open(BASE, 'w', encoding='utf-8').write(tools)
    open(CABECERA, 'w', encoding='utf-8').write(cabecera)
    return len(tools), len(cabecera)


# v5.48 — REPARACIÓN AUTOMÁTICA del «Anim Engine» del macro. Si la entrada + la salida no caben en el clip, el macro marca «Error! Animation too long!»
# y el texto no llega a verse (su botón «Fix Animations» solo reparte el clip entero entre entrada y salida). Aquí InLength / OutLength llevan una
# expresión: nunca más del 30 % de lo que dura el clip, así cualquier palabra, por corta que sea, entra, se queda quieta un rato y sale.
# v5.50: cada pack puede dar su tope (entrada, salida) en los dos últimos valores de su 'anim' (la suma nunca llega al clip entero).
PARTE_ANIM = 0.3


def _anim_auto(tools, partes=None):
    dur = '((comp.RenderEnd - comp.RenderStart + 1)/comp:GetPrefs(\\"Comp.FrameFormat.Rate\\"))'
    tope = dict(zip(('InLength', 'OutLength'), partes or (PARTE_ANIM, PARTE_ANIM)))
    return re.sub(r'\b(InLength|OutLength) = Input \{ Value = ([0-9.eE+-]+), \}',
                  lambda m: f'{m.group(1)} = Input {{ Value = {m.group(2)}, Expression = "min({m.group(2)}, {dur}*{_n(tope[m.group(1)])})", }}', tools)


def _n(v):
    return f'{v:.6g}'


def comp_luxe_shine(familia, estilo, tam, color, y, texto='Texto', mayus=True, esp=0.985, ajustar=True, anim=None, barrido=None, brillo=None, trama=None):
    """Texto de la comp completa (cabecera + Tools) con el macro Luxe Shine ya personalizado."""
    t = comp_luxe('shine', familia, estilo, tam, color, y, texto, mayus, esp, ajustar, anim, barrido, brillo)
    return _trama(t, tam, y, trama) if trama else t


def _trama(texto, tam, y, trama):
    """v5.50 (pedido: «agrega halftone»; luego «están feos: debe ser todo, sutil y difuminado»): toda la letra lleva una trama de puntos de color
    `trama['color']` de bordes suaves (`suave` px de degradado) y poca opacidad: `opacidad` = (abajo, arriba), un poco más marcada en la base que se
    desvanece hacia arriba. Entre la salida del macro y MediaOut1: «TramaPuntos» (Custom sobre un Background) dibuja la rejilla de `celda` px (a 1080
    de ancho) sin depender del fotograma (Fusion no la rehace en cada uno); «Trama» (Custom simple) la pinta sobre la letra solo donde es casi opaca
    (ni el halo ni la sombra del macro se puntean). El degradado va de la base a la parte alta de las mayúsculas: centradas en `y` (Text+ centra la
    caja ascent/descent y, en Poppins, eso deja las mayúsculas a ±0,35 em), con el em de Size 1 = 640/1080 del ancho."""
    mitad = 0.35 * tam * 640.0 / 1920.0                                    # media altura de las mayúsculas, en fracción del alto
    arriba, abajo = y + mitad, y - mitad                                    # (y de Fusion: 0 abajo)
    px = '(w / 1080)'
    celda = f'({_n(trama.get("celda", 9))} * {px})'
    fx = f'(x * w - floor(x * w / {celda}) * {celda} - {celda} / 2)'
    fy = f'(y * h - floor(y * h / {celda}) * {celda} - {celda} / 2)'
    op_abajo, op_arriba = trama.get('opacidad', (0.4, 0.12))
    t = f'max(0, min(1, ({_n(arriba)} - y) / {_n(arriba - abajo)}))'
    opacidad = f'({_n(op_arriba)} + {_n(op_abajo - op_arriba)} * {t})'
    radio = f'({_n(trama.get("radio", 2.4))} * {px})'
    punto = f'max(0, min(1, ({radio} - sqrt({fx} * {fx} + {fy} * {fy})) / ({_n(trama.get("suave", 1.6))} * {px}))) * {opacidad}'
    k = 'a2 * max(0, min(1, (a1 - 0.6) * 3.3))'
    cr, cg, cb = trama['color']
    nodo = (f'TramaLienzo = Background {{ Inputs = {{ UseFrameFormatSettings = Input {{ Value = 1, }}, TopLeftAlpha = Input {{ Value = 1, }}, }}, '
            f'ViewInfo = OperatorInfo {{ Pos = {{ 220, 120 }} }}, }}, '
            f'TramaPuntos = Custom {{ CtrlWZoom = false, Inputs = {{ RedExpression = Input {{ Value = "0", }}, GreenExpression = Input {{ Value = "0", }}, '
            f'BlueExpression = Input {{ Value = "0", }}, AlphaExpression = Input {{ Value = "{punto}", }}, '
            f'Image1 = Input {{ SourceOp = "TramaLienzo", Source = "Output", }}, }}, ViewInfo = OperatorInfo {{ Pos = {{ 330, 120 }} }}, }}, '
            f'Trama = Custom {{ CtrlWZoom = false, Inputs = {{ '
            f'RedExpression = Input {{ Value = "r1 + ({_n(cr)} * a1 - r1) * {k}", }}, '
            f'GreenExpression = Input {{ Value = "g1 + ({_n(cg)} * a1 - g1) * {k}", }}, '
            f'BlueExpression = Input {{ Value = "b1 + ({_n(cb)} * a1 - b1) * {k}", }}, '
            f'AlphaExpression = Input {{ Value = "a1", }}, '
            f'Image1 = Input {{ SourceOp = "{{fuente}}", Source = "Output", }}, Image2 = Input {{ SourceOp = "TramaPuntos", Source = "Output", }}, }}, '
            f'ViewInfo = OperatorInfo {{ Pos = {{ 330, 49.5 }} }}, }}, ')
    patron = r'MediaOut1 = MediaOut \{ Inputs = \{ Index = Input \{ Value = "0", \}, Input = Input \{ SourceOp = "([^"]+)", Source = "Output", \}'
    m = re.search(patron, texto)
    if not m:
        raise SystemExit('el macro no trae MediaOut1 con la forma esperada (trama)')
    nuevo = m.group(0).replace(f'SourceOp = "{m.group(1)}"', 'SourceOp = "Trama"')
    return texto[:m.start()] + nodo.replace('{fuente}', m.group(1)) + nuevo + texto[m.end():]


def comp_luxe_slide(familia, estilo, tam, color, y, texto='Texto', mayus=True, esp=0.985, ajustar=True, anim=None, brillo=None, deslizar=None):
    """Lo mismo con el macro Luxe Slide (contexto, complemento). deslizar='derecha': entra y sale moviéndose hacia la derecha (ver _deslizar)."""
    t = comp_luxe('slide', familia, estilo, tam, color, y, texto, mayus, esp, ajustar, anim, None, brillo)
    return _deslizar(t) if deslizar == 'derecha' else t


def _deslizar(texto):
    """v5.48 (pedido del usuario, Tema 2): POSITION del macro con «Mirror Out» desactivado y la dirección «→» (Start Direction 180; la salida sigue
    hacia la derecha: End Direction 0). Las palabras de una línea se suceden de izquierda a derecha y así el movimiento fluye. Desmarcar «Mirror Out»
    en el Inspector ejecuta el Script de positionCtrl, que cambia las expresiones de positionVector: aquí se dejan como las pone ese Script."""
    texto, n0 = re.subn(r'(positionCtrl = AlphaDivide \{ CtrlWShown = false, NameSet = true, Inputs = \{[^{]*?(?:\{[^}]*\}[^{]*?)*?)MirrorOut = Input \{ Value = 1, \}',
                        r'\g<1>MirrorOut = Input { Value = 0, }', texto, count=1)
    if not n0:
        raise SystemExit('el macro Luxe Slide no trae positionCtrl con la forma esperada')
    texto, n1 = re.subn(r'(positionCtrl = AlphaDivide \{.*?)StartDirection = Input \{ Value = [0-9.eE+-]+, \}', r'\g<1>StartDirection = Input { Value = 180, }', texto, count=1, flags=re.S)
    texto, n2 = re.subn(r'(positionCtrl = AlphaDivide \{.*?)EndDirection = Input \{ Value = [0-9.eE+-]+, \}', r'\g<1>EndDirection = Input { Value = 0, }', texto, count=1, flags=re.S)
    dist = 'Distance = Input { Expression = "positionCtrl.StartDistance*(1-AnimEngine.Output1)", }'
    ang = 'Angle = Input { Value = -90, Expression = "positionCtrl.StartDirection", }'
    if not (n1 and n2 and texto.count(dist) == 1 and texto.count(ang) == 1):
        raise SystemExit('el macro Luxe Slide no trae positionVector con la forma esperada')
    texto = texto.replace(dist, 'Distance = Input { Expression = "AnimEngine.Output2 == 0 and (positionCtrl.StartDistance*(1-AnimEngine.Output1)) or '
                                '(positionCtrl.EndDistance*(1-AnimEngine.Output1))", }', 1)
    return texto.replace(ang, 'Angle = Input { Value = 180, Expression = "AnimEngine.Output2 == 0 and positionCtrl.StartDirection or positionCtrl.EndDirection", }', 1)


def comp_luxe_count(familia, estilo, tam, color, y, texto='Texto', mayus=True, esp=0.985, ajustar=True, anim=None, brillo=None):
    """v5.48: el macro Luxe Count (números): cuenta de 0 hasta la cifra que lleve el texto del clip."""
    return comp_luxe('count', familia, estilo, tam, color, y, texto, mayus, esp, ajustar, anim, None, brillo)


# v5.5 — EL BARRIDO DE LUZ del macro Luxe Shine. De fábrica empieza a los 0,25 s y tarda 1,5 s (termina a los 1,75 s): las palabras grandes de «Referencia» se ven 0,3-0,9 s (mediana
# 0,55 s), así que casi todas se quedaban con el barrido a medias. Aquí se acorta (y el script de Resolve lo ajusta además a lo que dura cada palabra, con las entradas
# inputOffset / inputLength del macro) y se le dan TRES formas: 'brillo' (el original: realza el brillo del texto, es sutil), 'screen' (una banda de luz de ese color que se SUMA al
# texto: se ve claramente) y 'solido' (una banda opaca del color elegido que tapa el texto a su paso). La banda de color es un Background + un Merge limitados por la máscara del
# propio barrido (banda ∩ letras), así que sólo pinta dentro de las letras.
BARRIDO_POR_DEFECTO = {'modo': 'brillo', 'inicio': 0.06, 'largo': 0.40, 'ancho': None, 'color': (1.0, 1.0, 1.0), 'mezcla': 1.0}


def _barrido(tools, b):
    b = dict(BARRIDO_POR_DEFECTO, **(b or {}))
    i = tools.index('shineCtrl = AlphaDivide {')
    j = tools.index('UserControls', i)
    seg = tools[i:j]
    seg = re.sub(r'Offset = Input \{ Value = [0-9.eE+-]+, \}', f'Offset = Input {{ Value = {_n(b["inicio"])}, }}', seg, count=1)
    seg = re.sub(r'Length = Input \{ Value = [0-9.eE+-]+, \}', f'Length = Input {{ Value = {_n(b["largo"])}, }}', seg, count=1)
    if b.get('ancho'):
        seg = re.sub(r'ShineWidth = Input \{ Value = [0-9.eE+-]+, \}', f'ShineWidth = Input {{ Value = {_n(b["ancho"])}, }}', seg, count=1)
    tools = tools[:i] + seg + tools[j:]
    # la curva del barrido: de fábrica es un «ease» cúbico (4x³): la banda se queda ~60 % del tiempo en los extremos, fuera de las letras, y cruza la palabra en ~0,1 s. Medido en Resolve:
    # EaseIn/EaseOut «Linear» dan una salida lineal (0,1 / 0,3 / 0,5 / 0,7 / 0,9), así cruza la palabra a velocidad constante durante casi todo el barrido.
    i2 = tools.index('AnimCurves2 = LUTLookup {')
    j2 = tools.index('Lookup = Input { SourceOp = "AnimCurves2Lookup"', i2)
    tramo = tools[i2:j2]
    tramo = re.sub(r'EaseIn = Input \{ Value = FuID \{ "[A-Za-z]+" \}, \}', 'EaseIn = Input { Value = FuID { "Linear" }, }', tramo, count=1)
    tramo = re.sub(r'EaseOut = Input \{ Value = FuID \{ "[A-Za-z]+" \}, \}', 'EaseOut = Input { Value = FuID { "Linear" }, }', tramo, count=1)
    tools = tools[:i2] + tramo + tools[j2:]
    if b['modo'] in ('screen', 'solido'):
        r, g_, bl = b['color']
        modo_merge = 'ApplyMode = Input { Value = FuID { "Screen" }, }, ' if b['modo'] == 'screen' else ''
        # la máscara (banda ∩ letras) va en el propio Background: pinta el color SOLO ahí y deja el resto transparente; el Merge lo pone encima (Normal = sólido, Screen = suma de luz).
        # (Un EffectMask directamente en el Merge dejaba fuera el texto de debajo: sólo se veía la banda.)
        nuevas = ('sweepColor = Background { CtrlWShown = false, NameSet = true, Inputs = { EffectMask = Input { SourceOp = "shineCombine", Source = "Mask", }, '
                  'Width = Input { Value = 1080, }, Height = Input { Value = 1920, }, '
                  'UseFrameFormatSettings = Input { Value = 1, }, TopLeftRed = Input { Value = %s, }, TopLeftGreen = Input { Value = %s, }, TopLeftBlue = Input { Value = %s, }, '
                  'TopLeftAlpha = Input { Value = 1, } }, ViewInfo = OperatorInfo { Pos = { 495, 247.5 } }, }, '
                  'sweepMerge = Merge { CtrlWShown = false, NameSet = true, Inputs = { Blend = Input { Value = %s, }, Background = Input { SourceOp = "clamp", Source = "Output", }, '
                  'Foreground = Input { SourceOp = "sweepColor", Source = "Output", }, %sPerformDepthMerge = Input { Value = 0, } }, ViewInfo = OperatorInfo { Pos = { 495, 280 } }, }, '
                  % (_n(r), _n(g_), _n(bl), _n(b['mezcla']), modo_merge))
        marca = ' mbCtrl = AlphaDivide {'
        if tools.count(marca) != 1 or 'Source = Input { SourceOp = "clamp", Source = "Output", }' not in tools:
            raise SystemExit('el macro Luxe Shine no tiene la forma esperada para añadir el barrido de color')
        tools = tools.replace(marca, ' ' + nuevas + marca.lstrip(), 1)
        tools = tools.replace('Source = Input { SourceOp = "clamp", Source = "Output", }', 'Source = Input { SourceOp = "sweepMerge", Source = "Output", }', 1)
    return tools


def comp_luxe(tipo, familia, estilo, tam, color, y, texto='Texto', mayus=True, esp=0.985, ajustar=True, anim=None, barrido=None, brillo=None):
    """Texto de la comp completa (cabecera + Tools) con el macro del Luxe Title Pack (tipo 'shine' o 'slide') ya personalizado.
    ajustar=False deja el tamaño en reposo como un valor suelto (sin la expresión que encoge el texto largo): así se puede cambiar desde fuera
    con sizeCtrl.RestingSize (lo hace la guía «Crea tu estilo» en Resolve)."""
    ruta_base, ruta_cab = _rutas(tipo)
    tools = open(ruta_base, encoding='utf-8').read().replace(chr(0), '').rstrip()
    cabecera = open(ruta_cab, encoding='utf-8').read()
    i = tools.index('Text1 = TextPlus {')
    j = tools.index('glow1 = Glow', i)
    t1 = tools[i:j]
    t1 = re.sub(r'Font = Input \{ Value = "[^"]*", \}', f'Font = Input {{ Value = "{familia}", }}', t1, count=1)
    t1 = re.sub(r'Style = Input \{ Value = "[^"]*", \}', f'Style = Input {{ Value = "{estilo}", }}', t1, count=1)
    # el texto llega a un Text+ de primer nivel llamado «Template» (es lo que busca el script); el del macro lo lee de ahi
    base = 'tostring(Template.StyledText.Value)'
    if mayus:
        import generar_comps as g
        base = '(' + base + ':upper()' + ''.join(f':gsub("{x}","{y_}")' for x, y_ in g.MAYUS_ACENTOS) + ')'
    barra = chr(92)
    expr = base.replace(barra, barra * 2).replace('"', barra + '"')
    t1 = re.sub(r'StyledText = Input \{ Value = "[^"]*", \}', lambda m: f'StyledText = Input {{ Value = "", Expression = "{expr}", }}', t1, count=1)
    # (el Luxe Count ya calcula su texto: el número va a su «CountEnd», más abajo)
    t1 = re.sub(r'CharacterSpacing = Input \{ Value = [^,]*,', f'CharacterSpacing = Input {{ Value = {_n(esp)},', t1, count=1)
    t1 = re.sub(r'(Center = Input \{ Value = \{ )[^}]*( \},)', lambda m: f'{m.group(1)}0.5, {_n(y)}{m.group(2)}', t1, count=1)
    # v5.48: el Luxe Shine v1.09 trae su propio color (azul verdoso) en Text1; si se deja, va DESPUÉS del nuestro y gana (salían azules el «Moderno
    # blanco» y los rosa): se quita antes de poner el del estilo
    t1 = re.sub(r'\b(Red1|Green1|Blue1) = Input \{ Value = [0-9.eE+-]+, \}, ', '', t1)
    colores = f'Red1 = Input {{ Value = {_n(color[0])}, }}, Green1 = Input {{ Value = {_n(color[1])}, }}, Blue1 = Input {{ Value = {_n(color[2])}, }}, '
    # v5.5.10: sombra oscura suave (elemento 4, forma de LETRA) para que el texto claro se lea sobre fondos claros; el halo del macro solo no basta.
    import kinetic_elementos as E
    sombra = ' '.join(E._sombra(4, 0.55, -0.006, 12) + ['ElementShape4 = Input { Value = 0, },']) + ' '
    t1 = t1.replace('UseFrameFormatSettings = Input { Value = 1, }, ', 'UseFrameFormatSettings = Input { Value = 1, }, ' + colores + sombra, 1)
    tools = tools[:i] + t1 + tools[j:]
    # el tamaño se reduce solo si el texto (varias palabras principales) no cabe en el 90 % del ancho
    # ancho aproximado por numero de letras (el DataWindow de un Text+ suelto no llega dentro del macro): 0,80 em por letra
    ancho = f'(tostring(Template.StyledText.Value):len() * 0.80 * {_n(tam)} * 640 / 1080)'
    ajuste = f'{_n(tam)}*math.min(1, 0.86/math.max(0.0001, {ancho}))'.replace(chr(34), chr(92) + chr(34))
    tools = re.sub(r'(sizeCtrl = AlphaDivide \{.*?RestingSize = Input \{ Value = )[^,]*(, \})',
                   lambda m: m.group(1) + _n(tam) + ((', Expression = "' + ajuste + '"') if ajustar else '') + m.group(2), tools, count=1, flags=re.S)
    marca = 'positionCtrl = AlphaDivide { CtrlWShown = false, NameSet = true, Inputs = { '
    if marca not in tools:
        raise SystemExit('el macro no trae positionCtrl con la forma esperada')
    tools = tools.replace(marca, marca + f'RestingCenter = Input {{ Value = {{ 0.5, {_n(y)} }}, }}, ', 1)
    import generar_comps as g
    plantilla = g._texto_plus('Template', 0, 0, (familia, estilo), valor=texto, tam=tam, color=color, centro=(0.5, y))
    tools = '{ ' + plantilla.strip() + ' ' + tools.lstrip()[1:].lstrip()
    if barrido is not None and tipo == 'shine':
        tools = _barrido(tools, barrido)
    if anim:
        # v5.9: duración de la entrada y la salida del macro (AnimEngine.InLength / OutLength, en segundos; de fábrica 0,7 s cada una: una palabra que dura menos
        # de 1,4 s ni se ve, porque el macro se esconde si entrada + salida no caben en el clip). Los captions rápidos usan ~0,12 s.
        entrada, salida = anim[:2]
        tools = re.sub(r'InLength = Input \{ Value = [0-9.eE+-]+, \}', f'InLength = Input {{ Value = {_n(entrada)}, }}', tools, count=1)
        tools = re.sub(r'OutLength = Input \{ Value = [0-9.eE+-]+, \}', f'OutLength = Input {{ Value = {_n(salida)}, }}', tools, count=1)
    tools = _anim_auto(tools, tuple(anim[2:4]) if anim and len(anim) >= 4 else None)
    if tipo == 'count':
        # cuenta de 0 a la cifra del texto (el macro quita solo lo que no sea número y pone las comas de miles)
        tools, n = re.subn(r'CountEnd = Input \{ Value = "[^"]*", \}', 'CountEnd = Input { Value = "0", Expression = "tostring(Template.StyledText.Value)", }', tools, count=1)
        tools = re.sub(r'CountStart = Input \{ Value = "[^"]*", \}', 'CountStart = Input { Value = "0", }', tools, count=1)
        if not n:
            raise SystemExit('el macro Luxe Count no trae CountEnd con la forma esperada')
        # de fábrica: prefijo «$», 2 decimales y 1,5 s de cuenta. Aquí todo sale del TEXTO del clip (lo escribe el planificador): el prefijo es lo que
        # va antes de la cifra («$», «Q», «€»), el sufijo lo que va detrás («%») y los decimales, los que trae («9.99» -> 2; «430,000» -> 0).
        # La cuenta dura como mucho 0,9 s (la mitad del clip si es corto).
        dur = '((comp.RenderEnd - comp.RenderStart + 1)/comp:GetPrefs(\\"Comp.FrameFormat.Rate\\"))'
        txt = 'tostring(Template.StyledText.Value)'
        prefijo = f'(string.match({txt}, \\"^[^%d%-]*\\") or \\"\\")'
        sufijo = f'(string.match({txt}, \\"[^%d]*$\\") or \\"\\")'
        decimales = f'(string.match({txt}, \\"%.(%d%d?)[^%d]*$\\") or \\"\\"):len()'
        marca = 'countCtrl = AlphaDivide { CtrlWShown = false, NameSet = true, Inputs = { '
        if marca not in tools or 'Prefix = Input { Value = "$", }' not in tools:
            raise SystemExit('el macro Luxe Count no trae countCtrl con la forma esperada')
        tools = tools.replace('Prefix = Input { Value = "$", }', f'Prefix = Input {{ Value = "", Expression = "{prefijo}", }}', 1)
        tools = tools.replace(marca, marca + f'Precision = Input {{ Value = 0, Expression = "{decimales}", }}, '
                                             f'Append = Input {{ Value = "", Expression = "{sufijo}", }}, ', 1)
        tools = re.sub(r'(countCtrl = AlphaDivide \{.*?)Length = Input \{ Value = [0-9.eE+-]+, \}',
                       lambda m: m.group(1) + f'Length = Input {{ Value = 0.9, Expression = "min(0.9, {dur}*0.5)", }}', tools, count=1, flags=re.S)
    if brillo:
        # v5.4.33: el halo suave que traen los dos macros (nodo glow1: GlowSize 17,3 · GlowIntensity 0,48) se puede reforzar: brillo = (tamaño, intensidad). El Tema 4 lo pide más fuerte.
        tamano_b, intensidad_b = brillo
        tools = re.sub(r'(glow1 = Glow \{.*?GlowSize = Input \{ Value = )[0-9.eE+-]+(, \})', lambda m: m.group(1) + _n(tamano_b) + m.group(2), tools, count=1, flags=re.S)
        tools = re.sub(r'(glow1 = Glow \{.*?GlowIntensity = Input \{ Value = )[0-9.eE+-]+(, \})', lambda m: m.group(1) + _n(intensidad_b) + m.group(2), tools, count=1, flags=re.S)
    cab = re.sub(r',?\s*Compressed = true,?\s*\}\s*$', ' }', cabecera.rstrip())
    return cab[:-1].rstrip().rstrip(',') + ',\n\tTools = ' + tools + '\n}'
