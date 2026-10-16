# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/banner_inspector.py — el BANNER de CineCaptions arriba de los controles de cada caption en el Inspector de Resolve.
"""
v5.5.8 (pedido: «coloca un banner de CineCaptions para personalizar todo lo que se puso en la línea de tiempo en el Inspector, que quede bien
bonito; aplica para captions y todo»). Cada caption de los packs es una comp de Fusion; el banner es un LabelControl (texto con HTML, como los
«DROP SHADOW» / «GLOW CONTROLS» que ya trae el macro Luxe):
  · con macro (Luxe Shine / Slide): el label va en la herramienta de texto de DENTRO del macro y se publica como su PRIMER control (InstanceInput);
  · sin macro (Kinetic, VIRAL): el label va en el Text+ «Template» (el que GO rellena).
Va ARRIBA DE TODO (pedido: «el banner arriba de todo»): IC_ControlPage = -1 = encima de la fila de pestañas (Texto, Distribución…), visible en
todas; el Inspector de Resolve 21 enseña las pestañas del Text+ aunque el caption sea un macro Luxe. No cambia nada más de la comp (ni el diseño
ni la animación). Idempotente: si ya lleva el banner, lo deja al día (el de antes iba en la página Text, abajo del todo).

    con_banner(tools) -> tools            la comp (texto de Tools) con el banner
    parchear_drb(ruta) -> clips cambiados   reescribe el .drb (cada CompositionBA con el MISMO prefijo y longitudes, como lo guarda Resolve)
    python banner_inspector.py <carpeta o .drb>...
"""
import binascii
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path

NOMBRE = 'CCBanner'
HTML = ("<center><font color='#E8C27A' size='5'><b>CINECAPTIONS</b></font><br>"
        "<font color='#C9CDD8'>Personaliza aquí tu caption: texto, fuente, tamaño, color y animación</font></center>")
LABEL = (f'{NOMBRE} = {{ LINKS_Name = "{HTML}", LINKID_DataType = "Number", INPID_InputControl = "LabelControl", LBLC_MultiLine = true, '
         'INP_External = false, INP_Passive = true, IC_NoLabel = true, IC_NoReset = true, IC_ControlPage = -1, }, ')
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


def _con_label(tools, ini, fin):
    """El label en la herramienta tools[ini:fin] (bloque «X = TextPlus { ... }»): dentro de su UserControls si ya tiene, si no uno nuevo."""
    bloque = tools[ini:fin + 1]
    label = LABEL
    m = re.search(r'UserControls = ordered\(\) \{ ?', bloque)
    if m:
        bloque = bloque[:m.end()] + label + bloque[m.end():]
    else:
        k = bloque.index('{') + 1
        bloque = bloque[:k] + ' UserControls = ordered() { ' + label + '},' + bloque[k:]
    return tools[:ini] + bloque + tools[fin + 1:]


def con_banner(tools):
    if NOMBRE in tools:
        return _VIEJO.sub(lambda m: LABEL, tools)
    m = re.search(r'(\w+) = MacroOperator \{', tools)
    if m:
        abre = tools.index('{', m.start())
        fin_macro = _cerrar(tools, abre)
        t = re.search(r'(\w+) = TextPlus \{', tools[abre:fin_macro])
        if t:
            nombre_t = t.group(1)
            ini_t = abre + t.start()
            fin_t = _cerrar(tools, tools.index('{', ini_t))
            tools = _con_label(tools, ini_t, fin_t)
            k = tools.index('Inputs = ordered() {', abre) + len('Inputs = ordered() {')
            return tools[:k] + f' {NOMBRE} = InstanceInput {{ SourceOp = "{nombre_t}", Source = "{NOMBRE}", }},' + tools[k:]
    t = re.search(r'Template = TextPlus \{', tools) or re.search(r'\w+ = TextPlus \{', tools)
    if not t:
        return tools
    fin_t = _cerrar(tools, tools.index('{', t.start()))
    return _con_label(tools, t.start(), fin_t)


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
