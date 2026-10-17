# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/banner_inspector.py — el BANNER de CineCaptions (con su logo) arriba de los controles de cada caption en el Inspector.
"""
v5.5.8 (pedido: «coloca un banner de CineCaptions para personalizar todo lo que se puso en la línea de tiempo en el Inspector, que quede bien
bonito») y v5.5.9 («en DaVinci Resolve aún no tiene un banner y mi logo»). PROBADO en Resolve Studio 21.1.1: en una comp de caption de los packs
el PRIMER tool es el Text+ «Template» (el macro Luxe lee su texto con la expresión `Template.StyledText`), y el Inspector del Edit enseña ESE tool
(sus pestañas Texto, Distribución…), NO el macro: por eso el banner de la 5.5.8 (dentro del macro) no se veía. Ahora:
  · Text+ «Template» (o el primer Text+ si no hay): un LabelControl con el LOGO (PNG en base64, como la cabecera del macro Luxe) y una línea de
    ayuda, con IC_ControlPage = -1 = ENCIMA de la fila de pestañas, visible en todas;
  · con macro (Luxe Shine / Slide): además, un banner de solo texto dentro de su Text+ y publicado como PRIMER control del macro (por si se abre
    el macro en la página Fusion).
No cambia nada más de la comp (ni el diseño ni la animación). Idempotente: si ya lleva el banner, lo deja al día.

    banner_png() -> ruta             el PNG del banner (icono + «CINECAPTIONS» + «By Cinema Productions»), hecho una vez desde el logo
    con_banner(tools) -> tools       la comp (texto de Tools) con el banner
    parchear_drb(ruta) -> clips cambiados   reescribe el .drb (cada CompositionBA con el MISMO prefijo y longitudes, como lo guarda Resolve)
    python banner_inspector.py <carpeta o .drb>...
"""
import base64
import binascii
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RECURSOS = AQUI.parent
PNG = AQUI / 'banner_cinecaptions.png'
NOMBRE = 'CCBanner'
AYUDA = 'Personaliza aquí tu caption: texto, fuente, tamaño y color'


def banner_png(rehacer=False):
    """El banner (600×150, se ve a 300 px de ancho: nítido en pantallas con escala): tarjeta oscura con el borde en los colores del logo, el
    icono de CineCaptions, «CINECAPTIONS» y «By Cinema Productions». Paleta de 128 colores: pocos KB dentro de cada caption."""
    if PNG.exists() and not rehacer:
        return PNG
    from PIL import Image, ImageDraw, ImageFont
    W, H, R = 600, 150, 30
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    borde = Image.new('RGBA', (W, H))
    colores = [(47, 99, 214), (0, 214, 236), (230, 74, 25), (150, 50, 214)]
    for x in range(W):                                                   # el degradado del borde: azul → cian → naranja → morado
        u = x / (W - 1) * (len(colores) - 1)
        a, z = colores[int(u)], colores[min(len(colores) - 1, int(u) + 1)]
        f = u - int(u)
        ImageDraw.Draw(borde).line([(x, 0), (x, H)], fill=tuple(int(a[k] + (z[k] - a[k]) * f) for k in range(3)) + (255,))
    mascara = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, W - 1, H - 1], R, fill=255)
    im.paste(borde, (0, 0), mascara)
    ImageDraw.Draw(im).rounded_rectangle([4, 4, W - 5, H - 5], R - 4, fill=(14, 16, 24, 255))
    logo = Image.open(RECURSOS / 'logo_cinecaptions.png').convert('RGBA').resize((112, 112), Image.LANCZOS)
    im.alpha_composite(logo, (20, 19))
    fuentes = RECURSOS / 'fonts'
    titulo = ImageFont.truetype(str(fuentes / 'Montserrat-ExtraBold.ttf'), 50)
    sub = ImageFont.truetype(str(fuentes / 'Inter_18pt-Medium.ttf'), 25)
    d = ImageDraw.Draw(im)
    d.text((152, 26), 'CINECAPTIONS', font=titulo, fill=(255, 255, 255, 255))
    d.text((155, 90), 'By Cinema Productions', font=sub, fill=(154, 163, 181, 255))
    im.quantize(colors=128, method=Image.Quantize.FASTOCTREE).save(PNG, optimize=True)
    return PNG


def _label(html):
    return (f'{NOMBRE} = {{ LINKS_Name = "{html}", LINKID_DataType = "Number", INPID_InputControl = "LabelControl", LBLC_MultiLine = true, '
            'INP_External = false, INP_Passive = true, IC_NoLabel = true, IC_NoReset = true, IC_ControlPage = -1, }, ')


_B64 = base64.b64encode(banner_png().read_bytes()).decode('ascii')
LABEL = _label(f"<center><img src='data:image/png;base64,{_B64}' width='300'><br><font color='#9AA3B5'>{AYUDA}</font></center>")
LABEL_TEXTO = _label(f"<center><font color='#E8C27A' size='5'><b>CINECAPTIONS</b></font><br><font color='#9AA3B5'>{AYUDA}</font></center>")
_VIEJO = re.compile(NOMBRE + r' = \{ LINKS_Name = ".*?", LINKID_DataType = "Number", INPID_InputControl = "LabelControl".*?IC_NoReset = true, '
                    r'(?:ICS_ControlPage = "\w+", |IC_ControlPage = -?\d+, )?\}, ')


def _cerrar(texto, abre):
    """El índice de la llave que cierra la que abre en `abre` (sin contar las de dentro de cadenas)."""
    n, i, en_cadena = 0, abre, False
    while i < len(texto):
        c = texto[i]
        if en_cadena:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                en_cadena = False
        elif c == '"':
            en_cadena = True
        elif c == '{':
            n += 1
        elif c == '}':
            n -= 1
            if n == 0:
                return i
        i += 1
    raise ValueError('llave sin cerrar')


def _con_label(tools, ini, fin, label):
    """El label en la herramienta tools[ini:fin] (bloque «X = TextPlus { ... }»): dentro de su UserControls si ya tiene, si no uno nuevo."""
    bloque = tools[ini:fin + 1]
    m = re.search(r'UserControls = ordered\(\) \{ ?', bloque)
    if m:
        bloque = bloque[:m.end()] + label + bloque[m.end():]
    else:
        k = bloque.index('{') + 1
        bloque = bloque[:k] + ' UserControls = ordered() { ' + label + '},' + bloque[k:]
    return tools[:ini] + bloque + tools[fin + 1:]


def con_banner(tools):
    tools = _VIEJO.sub(lambda m: LABEL_TEXTO, tools)                      # los que ya había, al día (de texto; el del Template, abajo)
    # 1) el Text+ que enseña el Inspector del Edit: «Template» (o el primero si no hay): el banner con el LOGO
    t = re.search(r'(?m)^\s*Template = TextPlus \{', tools) or re.search(r'\w+ = TextPlus \{', tools)
    if t:
        ini = t.start() + len(t.group(0)) - len(t.group(0).lstrip())
        fin = _cerrar(tools, tools.index('{', ini))
        bloque = tools[ini:fin + 1]
        if LABEL_TEXTO in bloque:
            tools = tools[:ini] + bloque.replace(LABEL_TEXTO, LABEL) + tools[fin + 1:]
        elif NOMBRE not in bloque:
            tools = _con_label(tools, ini, fin, LABEL)
    # 2) con macro: también dentro de su Text+ (de texto) y publicado como su primer control
    m = re.search(r'(\w+) = MacroOperator \{', tools)
    if m:
        abre = tools.index('{', m.start())
        fin_macro = _cerrar(tools, abre)
        if NOMBRE not in tools[abre:fin_macro]:
            tt = re.search(r'(\w+) = TextPlus \{', tools[abre:fin_macro])
            if tt:
                nombre_t = tt.group(1)
                ini_t = abre + tt.start()
                fin_t = _cerrar(tools, tools.index('{', ini_t))
                tools = _con_label(tools, ini_t, fin_t, LABEL_TEXTO)
                k = tools.index('Inputs = ordered() {', abre) + len('Inputs = ordered() {')
                tools = tools[:k] + f' {NOMBRE} = InstanceInput {{ SourceOp = "{nombre_t}", Source = "{NOMBRE}", }},' + tools[k:]
    return tools


# ------------------------------------------------------------------------------------------------------------------------------- .drb
_BA = re.compile(r'(<CompositionBA>)([0-9a-fA-F]+)(</CompositionBA>)')


def _blob_con_banner(hex_ba):
    b = binascii.unhexlify(hex_ba)
    cab = zlib.decompress(b[4:])
    i = cab.index(b'Composition {')
    prefijo, resto = cab[:i - 4], cab[i:]
    j = resto.index(b'\x00')
    cabecera = resto[:j]
    tools = zlib.decompress(resto[j + 5:]).decode('utf-8')
    nuevo = con_banner(tools)
    if nuevo == tools:
        return None
    tb = nuevo.encode('utf-8')
    datos = cabecera + b'\x00' + struct.pack('<I', len(tb)) + zlib.compress(tb, 9)
    cab2 = prefijo + struct.pack('>I', len(datos)) + datos
    return binascii.hexlify(struct.pack('>I', len(cab2)) + zlib.compress(cab2, 6)).decode()


def parchear_drb(ruta):
    ruta = Path(ruta)
    zin = zipfile.ZipFile(ruta)
    cambios, entradas = 0, []
    for info in zin.infolist():
        datos = zin.read(info.filename)
        if info.filename.endswith('.xml') and b'<CompositionBA>' in datos:
            xml = datos.decode('utf-8')

            def poner(m):
                nonlocal cambios
                nuevo = _blob_con_banner(m.group(2))
                if nuevo is None:
                    return m.group(0)
                cambios += 1
                return m.group(1) + nuevo + m.group(3)
            datos = _BA.sub(poner, xml).encode('utf-8')
        entradas.append((info, datos))
    zin.close()
    if cambios:
        tmp = ruta.with_suffix('.tmp')
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info, datos in entradas:
                zout.writestr(info, datos)
        tmp.replace(ruta)
    return cambios


if __name__ == '__main__':
    total = 0
    for a in sys.argv[1:]:
        p = Path(a)
        for drb in ([p] if p.is_file() else sorted(p.rglob('*.drb'))):
            n = parchear_drb(drb)
            total += n
            print(f'{drb.name}: {n} clips con el banner')
    print('total', total)
