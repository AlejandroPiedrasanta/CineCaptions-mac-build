# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/leer_comp.py — lee la comp de Fusion (texto) que lleva un clip de un .drb: para ver cómo escribe Resolve cada herramienta.
"""
Uso:  python leer_comp.py <pack.drb> [<nombre del clip>] [--tipos] [--herramienta <ID>]

Sin nombre de clip lista los clips. Con el nombre vuelca la comp (cabecera + Tools). --tipos: solo los tipos de herramienta que usa.
--herramienta ID: los bloques de ese tipo (p. ej. RectangleMask) tal como los guarda Resolve. Sirve para copiar la sintaxis REAL en vez de adivinarla.
"""
import binascii
import re
import struct
import sys
import zipfile
import zlib

_ELEMENTO = re.compile(r'<Sm2MpGenerator DbId="[^"]+">.*?</Sm2MpGenerator>', re.S)
_NOMBRE = re.compile(r'<Name>(.*?)</Name>')
_BA = re.compile(r'<CompositionBA>([0-9a-fA-F]*)</CompositionBA>')


def clips(ruta):
    z = zipfile.ZipFile(ruta)
    xml = z.read(next(n for n in z.namelist() if n.endswith('MpFolder.xml') and '/Master/0' in '/' + n)).decode('utf-8')
    return {_NOMBRE.search(m.group(0)).group(1): m.group(0) for m in _ELEMENTO.finditer(xml)}


def comp_de_blob(hex_ba):
    """(cabecera, tools) de un CompositionBA."""
    b = binascii.unhexlify(hex_ba)
    cab = zlib.decompress(b[4:])
    i = cab.index(b'Composition {')
    resto = cab[i:]
    # la cabecera acaba en el byte 0 y luego viene LE32(len) + zlib(tools)
    j = resto.index(b'\x00')
    cabecera = resto[:j].decode('utf-8', 'replace')
    ln = struct.unpack('<I', resto[j + 1:j + 5])[0]
    tools = zlib.decompress(resto[j + 5:])
    return cabecera, tools.decode('utf-8', 'replace')


def comp_de_clip(ruta, nombre):
    bloque = clips(ruta)[nombre]
    return comp_de_blob(_BA.search(bloque).group(1))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ruta = args[0]
    if len(args) == 1:
        for n in clips(ruta):
            print(n)
        raise SystemExit
    cab, tools = comp_de_clip(ruta, args[1])
    if '--tipos' in sys.argv:
        print(sorted(set(re.findall(r'=\s*([A-Za-z0-9_]+)\s*\{\s*\n?\s*(?:CtrlWZoom|NameSet|Inputs|CtrlWShown|Version|ViewInfo)', tools))))
    elif '--herramienta' in sys.argv:
        ident = sys.argv[sys.argv.index('--herramienta') + 1]
        for m in re.finditer(r'\n\t\t(\w+) = ' + re.escape(ident) + r' \{.*?\n\t\t\},?\n', tools, re.S):
            print(m.group(0))
    else:
        print(cab)
        print(tools)
