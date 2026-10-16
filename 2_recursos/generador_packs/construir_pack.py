# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/construir_pack.py — arma los .drb (bin de Resolve) de los packs nuevos con los macros reales Luxe Shine / Luxe Slide (luxe_macro.py).
"""
Un .drb es un ZIP con project.xml y un MpFolder.xml donde cada clip (Sm2MpGenerator) lleva su comp de Fusion en
<CompositionBA>. Resolve NO deja crear estos clips por la API, asi que se toma un .drb existente como CONTENEDOR (sus
clips ya son «Titulo - Fusion») y a cada clip se le cambia el nombre y la comp:

    CompositionBA = BE32(len(cab)) + zlib(cab)
    cab           = prefijo del contenedor + BE32(len(datos)) + datos
    datos         = cabecera de la comp (sin Tools, con «Compressed = true,») + 00 + LE32(len(tools)) + zlib(tools)

Uso:  python construir_pack.py <plantilla.drb> <salida.drb> <nombre del bin> --pack superior|inferior
La plantilla debe traer clips llamados contexto/principal/complemento (+2, +3) y base: se usan sus posiciones (Pan/Tilt),
que se compensan dentro de la comp para que el texto caiga donde pide el pack.
"""
import binascii
import os
import re
import struct
import sys
import uuid
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '1_codigo'))
import generar_comps as g

_BA = re.compile(r'(<CompositionBA>)([0-9a-fA-F]*)(</CompositionBA>)')
_ELEMENTO = re.compile(r'[ \t]*<Element>\s*<Sm2MpGenerator DbId="([^"]+)">.*?</Sm2MpGenerator>\s*</Element>\n?', re.S)
_NOMBRE = re.compile(r'<Name>(.*?)</Name>')


def _cerrar_llave(texto, abre):
    """Indice de la llave que cierra la de 'abre' (salta los textos entre comillas)."""
    nivel, i, en_texto = 0, abre, False
    while i < len(texto):
        c = texto[i]
        if en_texto:
            if c == '\\':
                i += 1
            elif c == '"':
                en_texto = False
        else:
            if c == '"':
                en_texto = True
            elif c == '{':
                nivel += 1
            elif c == '}':
                nivel -= 1
                if nivel == 0:
                    return i
        i += 1
    raise ValueError('llaves sin cerrar')


_NOMBRE_NUEVO = {'contexto': 'arriba', 'complemento': 'abajo', 'base': 'simple'}


def nombre_de_estructura(nombre):
    """'contexto 2' -> 'arriba 2', 'complemento' -> 'abajo', 'base' -> 'simple', 'principal 3' -> 'principal 3': los nombres que lee el programa."""
    palabra, _, resto = nombre.partition(' ')
    return _NOMBRE_NUEVO.get(palabra, palabra) + (' ' + resto if resto else '')


_COMPS_DRB = {}


def comp_de_drb(ruta, clip):
    """El <CompositionBA> (hex) del clip 'clip' de otro .drb (la comp de un texto principal de Amro.Films Captions, que se copia tal cual)."""
    clave = (str(ruta), clip)
    if clave not in _COMPS_DRB:
        z = zipfile.ZipFile(ruta)
        xml = z.read(next(n for n in z.namelist() if n.endswith('MpFolder.xml') and '/Master/0' in '/' + n)).decode('utf-8')
        for m in _ELEMENTO.finditer(xml):
            if _NOMBRE.search(m.group(0)).group(1) == clip:
                _COMPS_DRB[clave] = _BA.search(m.group(0)).group(2)
                break
        else:
            raise SystemExit(f'no encuentro el clip {clip!r} en {ruta}')
    return _COMPS_DRB[clave]


def blob_con_tilt(hex_blob, tilt):
    """El FieldsBlob (hex) de un clip con su Tilt cambiado. tilt = fracción del alto, positivo = arriba (como packs_drt.posiciones_de_drb).
    El blob es: cabecera + (tam, 10001, largo) + 0x81 + zstd(protobuf); el Tilt es un double dentro del protobuf (campo 0x29), así que
    el largo del protobuf no cambia y solo se rehacen los dos tamaños de la cabecera."""
    from compression import zstd
    import packs_drt
    b = binascii.unhexlify(hex_blob)
    i = 12 + 16 + 4 + 1
    _tam, tipo, largo = struct.unpack('>III', b[i:i + 12])
    if tipo != 10001:
        i = b.find(struct.pack('>I', 10001)) - 4
        _tam, tipo, largo = struct.unpack('>III', b[i:i + 12])
    carga = b[i + 12:i + 12 + largo]
    if carga[:1] != b'\x81':
        raise ValueError('el blob de posicion no viene comprimido: formato no previsto')
    plano = bytearray(zstd.decompress(carga[1:]))
    for m in packs_drt._POS_CAMPO.finditer(bytes(plano)):
        if m.group(1)[0] == 0x29:
            plano[m.start(2):m.start(2) + 8] = struct.pack('<d', float(tilt))
            break
    else:
        raise ValueError('el clip de la plantilla no trae Tilt')
    nuevo = b'\x81' + zstd.compress(bytes(plano))
    return binascii.hexlify(b[:i] + struct.pack('>III', len(nuevo) + 8, 10001, len(nuevo)) + nuevo + b[i + 12 + largo:]).decode()


def blob_de_comp(texto_comp, hex_plantilla):
    """El CompositionBA (hex) de una comp, con la estructura que Resolve espera."""
    # --- trocear la comp: cabecera (todo menos Tools) y Tools
    k = texto_comp.index('Tools = {')
    abre = texto_comp.index('{', k)
    cierra = _cerrar_llave(texto_comp, abre)
    tools = texto_comp[abre:cierra + 1]
    import banner_inspector                                                # v5.5.8: el banner de CineCaptions arriba de los controles del Inspector
    tools = banner_inspector.con_banner(tools)
    resto = texto_comp[:k] + texto_comp[cierra + 1:].lstrip(',')
    cabecera = re.sub(r'\s+', ' ', resto).strip()
    cabecera = re.sub(r',\s*}$', ' }', cabecera) if False else cabecera
    ultimo = cabecera.rindex('}')
    cabecera = cabecera[:ultimo].rstrip().rstrip(',') + ', Compressed = true, }'
    cabecera = cabecera.replace(', ,', ',')
    # --- el contenedor: prefijo QDataStream de la plantilla
    cab_plantilla = zlib.decompress(binascii.unhexlify(hex_plantilla)[4:])
    prefijo = cab_plantilla[:cab_plantilla.index(b'Composition {') - 4]
    tools_b = tools.encode('utf-8')
    anidado = struct.pack('<I', len(tools_b)) + zlib.compress(tools_b, 9)
    datos = cabecera.encode('utf-8') + b'\x00' + anidado
    cab = prefijo + struct.pack('>I', len(datos)) + datos
    return binascii.hexlify(struct.pack('>I', len(cab)) + zlib.compress(cab, 6)).decode()


def _blob_con_nombre(copia, origen, destino):
    """Cambia el nombre del clip dentro de su FieldsBlob (de donde Resolve lo lee). El blob es protobuf con LARGOS: el total (4 bytes, big-endian, en el byte 4) y los dos del nombre
    (0a <largo externo> 12 <largo interno> <nombre>); si el nombre nuevo tiene otra longitud («contexto 10» frente a «contexto 3») hay que corregir los tres. Sin esto los clips de la
    combinación 10 en adelante salían corruptos en Resolve (sin su Text+): sólo funcionaban las 9 primeras."""
    import struct
    o, d = origen.encode(), destino.encode()

    def sustituir(m):
        raw = bytearray(binascii.unhexlify(m.group(2)))
        i = bytes(raw).find(o)
        if i < 3:
            return m.group(0)
        delta = len(d) - len(o)
        raw[i:i + len(o)] = d
        if delta:
            raw[i - 1] += delta
            raw[i - 3] += delta
            raw[4:8] = struct.pack('>I', struct.unpack('>I', bytes(raw[4:8]))[0] + delta)
        return m.group(1) + binascii.hexlify(bytes(raw)).decode() + m.group(3)
    return re.sub(r'(<FieldsBlob>)([0-9a-f]+)(</FieldsBlob>)', sustituir, copia)


def _clonar_combinaciones(xml, proyecto, hasta):
    """v5.9: el contenedor trae solo las combinaciones 1-3; para un pack de hasta N variantes se CLONAN los clips de la 3 (contexto / principal /
    complemento) con ids nuevos, el nombre «contexto 4»… (en el XML y dentro del FieldsBlob, que es de donde Resolve lee el nombre) y su blob de posicion."""
    for comb in range(4, int(hasta) + 1):
        for base in ('contexto', 'principal', 'complemento'):
            origen, destino = f'{base} 3', f'{base} {comb}'
            if any(_NOMBRE.search(m.group(0)).group(1) == destino for m in _ELEMENTO.finditer(xml)):
                continue
            m = next(mm for mm in _ELEMENTO.finditer(xml) if _NOMBRE.search(mm.group(0)).group(1) == origen)
            bloque, db_gen = m.group(0), m.group(1)
            copia, mapa = bloque, {}
            for i in dict.fromkeys(re.findall(r'(?:DbId="|<UniqueMediaPoolItemId>)([0-9a-f\-]{36})', bloque)):
                mapa[i] = str(uuid.uuid4())
                copia = copia.replace(i, mapa[i])
            copia = copia.replace(f'<Name>{origen}</Name>', f'<Name>{destino}</Name>', 1)
            viejo_hex = binascii.hexlify(origen.encode()).decode()
            if viejo_hex not in copia:
                raise ValueError(f'el FieldsBlob de «{origen}» no lleva su nombre: no se puede clonar')
            copia = _blob_con_nombre(copia, origen, destino)
            xml = xml.replace(bloque, bloque + copia, 1)
            mb = re.search(r'[ 	]*<Element>\s*<Sm2MpItemLockableBlob DbId="([^"]+)">(?:(?!</Sm2MpItemLockableBlob>).)*?<BlobOwner>' + re.escape(db_gen)
                           + r'</BlobOwner>\s*</Sm2MpItemLockableBlob>\s*</Element>\s*', proyecto, re.S)
            if mb:
                bl = mb.group(0).replace(mb.group(1), str(uuid.uuid4())).replace(db_gen, mapa[db_gen])
                proyecto = proyecto.replace(mb.group(0), mb.group(0) + bl, 1)
    return xml, proyecto


def construir(plantilla, salida, nombre_bin, pack, combinaciones=(1, 2, 3), y_por_comb=None, nombres_nuevos=False, guia=False):
    """y_por_comb {variante: y del centro del grupo (1 = arriba)}: cada variante lleva su propia posicion (el Tilt de sus clips se
    reescribe en el .drb y la comp queda centrada). nombres_nuevos: los clips se llaman arriba / principal / abajo / simple.
    guia: comps para la guía «Crea tu estilo» de Resolve (el tamaño y el texto se cambian desde fuera: sin ajuste automático ni mayúsculas)."""
    from packs_drt import posiciones_de_drb
    pos = posiciones_de_drb(plantilla)
    zin = zipfile.ZipFile(plantilla)
    ruta_xml = next(n for n in zin.namelist() if n.endswith('MpFolder.xml') and '/Master/0' in '/' + n)
    xml = zin.read(ruta_xml).decode('utf-8')
    proyecto_xml = zin.read('project.xml').decode('utf-8')
    if max(combinaciones) > 3:
        xml, proyecto_xml = _clonar_combinaciones(xml, proyecto_xml, max(combinaciones))
    elementos = {}
    for m in _ELEMENTO.finditer(xml):
        nombre = _NOMBRE.search(m.group(0)).group(1)
        elementos[nombre] = m
    # clips que lleva el pack nuevo: nombre en el bin -> (combinacion, rol)
    nombres = {}
    for comb in combinaciones:
        sufijo = '' if comb == 1 else f' {comb}'
        nombres['contexto' + sufijo] = (comb, 'context')
        nombres['principal' + sufijo] = (comb, 'main')
        nombres['complemento' + sufijo] = (comb, 'complement')
    nombres['base'] = (1, 'base')
    faltan = [n for n in nombres if n not in elementos]
    if faltan:
        raise SystemExit(f'La plantilla no trae estos clips: {faltan}')
    vistos = {}
    nuevo = xml
    conservar = set()
    tilts = {}                                  # DbId del clip -> Tilt nuevo (solo con y_por_comb)
    for nombre, m in elementos.items():
        if nombre not in nombres:
            nuevo = nuevo.replace(m.group(0), '', 1)
            continue
        comb, rol = nombres[nombre]
        conservar.add(m.group(1))
        x, y_tilt, zx, zy = pos.get(nombre, [0.0, 0.0, 1.0, 1.0])
        # v5.8: TODO clip es un macro REAL del Luxe Title Pack: Luxe Shine (principal y palabra suelta) o Luxe Slide (contexto/complemento).
        # La imitación con Text+ sueltos (g.comp_de_clip) ya no se usa en ningun pack.
        import luxe_macro
        r = g.COMBINACIONES[comb]['main' if rol == 'base' else rol]
        y_grupo = g.PACKS[pack]['y_grupo']
        if y_por_comb == 'centro':
            # v5.9: todos los clips CENTRADOS en el cuadro (Tilt 0, comp en el centro): la posición de cada línea la pone el script con Pan/Tilt
            y_tilt = 0.0
            tilts[m.group(1)] = 0.0
            y_grupo = 0.5
            y_abs = 0.5
        elif y_por_comb and comb in y_por_comb:
            y_grupo = y_por_comb[comb]
            y_tilt = y_grupo + g.y_relativa(comb, rol) - 0.5       # el clip lleva la posicion (Tilt) y la comp queda centrada
            tilts[m.group(1)] = y_tilt
        if y_por_comb != 'centro':
            y_abs = y_grupo + g.y_relativa(comb, rol) - y_tilt
        fuente = g.COMBINACIONES[comb].get('principal_drb') if rol in ('main', 'base') else None
        if fuente:
            texto = None                                    # el principal es un preset de Amro.Films Captions: su comp se copia tal cual
        elif rol in ('main', 'base'):
            mayus = r['mayus'] if g.COMBINACIONES[comb].get('mayus_real') else True
            texto = luxe_macro.comp_luxe_shine(r['f1'][0], r['f1'][1], r['tam'], r['color'], y_abs, mayus=mayus and not guia, esp=r['esp'], ajustar=not guia, anim=g.COMBINACIONES[comb].get('anim'),
                                               barrido=g.COMBINACIONES[comb].get('barrido'), brillo=g.COMBINACIONES[comb].get('brillo'))
        else:
            texto = luxe_macro.comp_luxe_slide(r['f1'][0], r['f1'][1], r['tam'], r['color'], y_abs, mayus=r['mayus'] and not guia, esp=r['esp'], ajustar=not guia, anim=g.COMBINACIONES[comb].get('anim'), brillo=g.COMBINACIONES[comb].get('brillo'))
        bloque = m.group(0)
        hex_viejo = _BA.search(bloque).group(2)
        hex_nuevo = comp_de_drb(fuente['drb'], fuente['clip']) if fuente else blob_de_comp(texto, hex_viejo)
        bloque_nuevo = _BA.sub(lambda mm: mm.group(1) + hex_nuevo + mm.group(3), bloque, count=1)
        if nombres_nuevos:
            bloque_nuevo = bloque_nuevo.replace(f'<Name>{nombre}</Name>', f'<Name>{nombre_de_estructura(nombre)}</Name>', 1)
        nuevo = nuevo.replace(bloque, bloque_nuevo, 1)
    antiguo_bin = re.search(r'<Sm2MpFolder DbId="[^"]+">\s*<FieldsBlob/>\s*<Name>(.*?)</Name>', nuevo).group(1)
    nuevo = nuevo.replace(f'<Name>{antiguo_bin}</Name>', f'<Name>{nombre_bin}</Name>', 1)
    # project.xml: nombre del proyecto y blobs de posicion de los clips que ya no estan
    proyecto = proyecto_xml
    proyecto = proyecto.replace(f'<ProjectName>{antiguo_bin}</ProjectName>', f'<ProjectName>{nombre_bin}</ProjectName>')
    def _limpia(m):
        dueno = re.search(r'<BlobOwner>([^<]+)</BlobOwner>', m.group(0))
        return m.group(0) if (dueno and dueno.group(1) in conservar) else ''
    proyecto = re.sub(r'[ \t]*<Element>\s*<Sm2MpItemLockableBlob .*?</Sm2MpItemLockableBlob>\s*</Element>\n?', _limpia, proyecto, flags=re.S)
    if tilts:
        def _mover(m):
            return (m.group(1) + blob_con_tilt(m.group(2), tilts[m.group(4)]) + m.group(3)) if m.group(4) in tilts else m.group(0)
        proyecto = re.sub(r'(<Sm2MpItemLockableBlob DbId="[^"]+">\s*<FieldsBlob>)([0-9a-f]*)(</FieldsBlob>\s*<BlobOwner>([^<]+)</BlobOwner>)', _mover, proyecto)
    carpeta_vieja = ruta_xml.rsplit('/', 1)[0]
    carpeta_nueva = carpeta_vieja.split('/')
    carpeta_nueva[-1] = '000_' + nombre_bin
    carpeta_nueva = '/'.join(carpeta_nueva)
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            datos = zin.read(info.filename)
            nombre_zip = info.filename
            if info.filename == 'project.xml':
                datos = proyecto.encode('utf-8')
            elif info.filename == ruta_xml:
                datos = nuevo.encode('utf-8')
                nombre_zip = carpeta_nueva + '/MpFolder.xml'
            zout.writestr(nombre_zip, datos)
    # <salida>.variantes.json: nombre, color y la tipografia de cada rol (la vista previa de la app dibuja las dos palabras con sus dos pesos)
    import json
    def hexa(c):
        return '#%02X%02X%02X' % tuple(int(round(v * 255)) for v in c[:3])
    extra = {}
    for comb in combinaciones:
        c = g.COMBINACIONES[comb]
        roles = {}
        for rol in g.ROLES:
            r = c[rol]
            # el macro real lleva UNA sola tipografia por linea: la vista previa tambien (f2 = f1)
            roles[rol] = {'f1': list(r['f1']), 'f2': list(r['f1']), 'tam': r['tam'], 'color': hexa(r['color']), 'mayus': bool(r['mayus'])}
        extra[str(comb)] = {'nombre': c['nombre'], 'color': hexa(c['main']['color']), 'roles': roles, 'amro': bool(c.get('principal_drb'))}
    with open(os.path.splitext(salida)[0] + '.variantes.json', 'w', encoding='utf-8') as fh:
        json.dump(extra, fh, ensure_ascii=False, indent=1)
    return sorted(nombres), {n: pos.get(n) for n in nombres}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('plantilla')
    ap.add_argument('salida')
    ap.add_argument('nombre_bin')
    ap.add_argument('--pack', required=True, choices=sorted(g.PACKS))
    ap.add_argument('--combs', default='1,2,3', help='combinaciones a incluir, p. ej. 1,2,3,4,5')
    a = ap.parse_args()
    creados, posiciones = construir(a.plantilla, a.salida, a.nombre_bin, a.pack, tuple(int(x) for x in a.combs.split(',')))
    print('clips:', creados)
    print('tilts de la plantilla:', {n: (p[1] if p else None) for n, p in posiciones.items()})
