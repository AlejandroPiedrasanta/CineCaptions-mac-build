# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/kinetic_pack.py — arma un .drb con clips de nombre libre y una comp de Fusion propia en cada uno (pack «Kinetic»).
"""
construir_pack.py arma los packs de 3 líneas (arriba / principal / abajo) con nombres fijos. El estilo «Kinetic» necesita otros clips
(héroe, serie, cinta, anillo…), así que aquí se toma el mismo contenedor (un .drb de Resolve con clips «Título - Fusion») y se CLONA su primer
clip tantas veces como haga falta: cada clon con id nuevos, su nombre (en el XML y en el FieldsBlob, ajustando los largos del protobuf), su blob
de posición (Tilt 0: centrado) y su comp.

    construir_clips(contenedor, salida, nombre_bin, {'k hero blanco': texto_de_comp, ...}) -> [nombres]

Los nombres deben ser ASCII y de menos de 100 bytes (los largos del protobuf caben en un byte).
"""
import binascii
import os
import re
import struct
import sys
import uuid
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', '..', '1_codigo'))
import construir_pack as C


def blob_con_nombre(hex_blob, viejo, nuevo):
    """El FieldsBlob (hex) de un clip con otro nombre. Estructura: BE32(2) BE32(largo) 0x80 0x0a <len sub> 0x12 <len nombre> <nombre> 0x30 0x04 ...:
    al cambiar el largo del nombre hay que corregir el del submensaje (1 byte) y el largo total (BE32)."""
    raw = binascii.unhexlify(hex_blob)
    nv, nn = viejo.encode('utf-8'), nuevo.encode('utf-8')
    marca = bytes([0x12, len(nv)]) + nv
    i = raw.index(marca)
    d = len(nn) - len(nv)
    if d == 0:
        return binascii.hexlify(raw[:i + 2] + nn + raw[i + 2 + len(nv):]).decode()
    if not (raw[8] == 0x80 and raw[9] == 0x0a and i == 11):
        raise ValueError('FieldsBlob con una estructura que no conozco: no se puede cambiar el largo del nombre')
    sub = raw[10] + d
    if not (0 < sub < 128 and 0 < len(nn) < 128):
        raise ValueError('nombre demasiado largo')
    total = struct.unpack('>I', raw[4:8])[0] + d
    nuevo_raw = raw[:4] + struct.pack('>I', total) + raw[8:10] + bytes([sub]) + bytes([0x12, len(nn)]) + nn + raw[i + 2 + len(nv):]
    return binascii.hexlify(nuevo_raw).decode()


def _uuids(texto):
    return list(dict.fromkeys(re.findall(r'(?:DbId="|<UniqueMediaPoolItemId>)([0-9a-f\-]{36})', texto)))


def construir_clips(contenedor, salida, nombre_bin, comps, clip_base=None):
    """Arma `salida` (.drb) con un clip por entrada de `comps` ({nombre: texto de la comp}). Devuelve la lista de nombres."""
    zin = zipfile.ZipFile(contenedor)
    ruta_xml = next(n for n in zin.namelist() if n.endswith('MpFolder.xml') and '/Master/0' in '/' + n)
    xml = zin.read(ruta_xml).decode('utf-8')
    proyecto = zin.read('project.xml').decode('utf-8')
    elementos = {C._NOMBRE.search(m.group(0)).group(1): m for m in C._ELEMENTO.finditer(xml)}
    base_nombre = clip_base or next(iter(elementos))
    m_base = elementos[base_nombre]
    bloque_base, db_base = m_base.group(0), m_base.group(1)
    hex_comp_base = C._BA.search(bloque_base).group(2)
    # blob de posición del clip base (project.xml)
    mb = re.search(r'[ \t]*<Element>\s*<Sm2MpItemLockableBlob DbId="([^"]+)">(?:(?!</Sm2MpItemLockableBlob>).)*?<BlobOwner>' + re.escape(db_base)
                   + r'</BlobOwner>(?:(?!</Sm2MpItemLockableBlob>).)*</Sm2MpItemLockableBlob>\s*</Element>\s*', proyecto, re.S)
    if not mb:
        raise SystemExit(f'el clip base «{base_nombre}» no trae blob de posición')
    # 1) clones nuevos (con su comp) delante del bloque base; 2) fuera todos los elementos originales
    clones_xml, clones_blob = [], []
    for nombre, texto in comps.items():
        copia, mapa = bloque_base, {}
        for i in _uuids(bloque_base):
            mapa[i] = str(uuid.uuid4())
            copia = copia.replace(i, mapa[i])
        copia = copia.replace(f'<Name>{base_nombre}</Name>', f'<Name>{nombre}</Name>', 1)
        # el FieldsBlob con el nombre (el primero que lo lleva)
        def _cambiar(mm):
            return mm.group(1) + blob_con_nombre(mm.group(2), base_nombre, nombre) + mm.group(3)
        copia, n = re.subn(r'(<FieldsBlob>)(' + binascii.hexlify(base_nombre.encode()).decode().join(['[0-9a-f]*', '[0-9a-f]*']) + r')(</FieldsBlob>)', _cambiar, copia, count=1)
        if n != 1:
            raise ValueError(f'no encuentro el FieldsBlob con el nombre de «{base_nombre}»')
        hex_nuevo = C.blob_de_comp(texto, hex_comp_base)
        copia = C._BA.sub(lambda mm: mm.group(1) + hex_nuevo + mm.group(3), copia, count=1)
        clones_xml.append(copia)
        blob = mb.group(0).replace(mb.group(1), str(uuid.uuid4())).replace(db_base, mapa[db_base])
        # posición centrada (Tilt 0): el script de Resolve coloca cada elemento con Pan/Tilt
        blob = re.sub(r'(<FieldsBlob>)([0-9a-f]*)(</FieldsBlob>)', lambda mm: mm.group(1) + C.blob_con_tilt(mm.group(2), 0.0) + mm.group(3), blob, count=1)
        clones_blob.append(blob)
    # los clones ocupan el sitio del clip base y salen todos los demás elementos originales
    nuevo_xml = xml.replace(bloque_base, ''.join(clones_xml), 1)
    for nombre, m in elementos.items():
        if nombre != base_nombre:
            nuevo_xml = nuevo_xml.replace(m.group(0), '', 1)
    antiguo_bin = re.search(r'<Sm2MpFolder DbId="[^"]+">\s*<FieldsBlob/>\s*<Name>(.*?)</Name>', nuevo_xml).group(1)
    nuevo_xml = nuevo_xml.replace(f'<Name>{antiguo_bin}</Name>', f'<Name>{nombre_bin}</Name>', 1)
    # project.xml: fuera los blobs de los clips que ya no están; el blob base se sustituye por los de los clones
    dueños_vivos = set()
    for blob in clones_blob:
        dueños_vivos.add(re.search(r'<BlobOwner>([^<]+)</BlobOwner>', blob).group(1))

    def _limpia(mm):
        d = re.search(r'<BlobOwner>([^<]+)</BlobOwner>', mm.group(0))
        return mm.group(0) if (d and d.group(1) in dueños_vivos) else ''
    proyecto2 = proyecto.replace(mb.group(0), ''.join(clones_blob), 1)
    proyecto2 = re.sub(r'[ \t]*<Element>\s*<Sm2MpItemLockableBlob .*?</Sm2MpItemLockableBlob>\s*</Element>\n?', _limpia, proyecto2, flags=re.S)
    proyecto2 = proyecto2.replace(f'<ProjectName>{antiguo_bin}</ProjectName>', f'<ProjectName>{nombre_bin}</ProjectName>')
    carpeta_vieja = ruta_xml.rsplit('/', 1)[0].split('/')
    carpeta_vieja[-1] = '000_' + nombre_bin
    carpeta_nueva = '/'.join(carpeta_vieja)
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            datos = zin.read(info.filename)
            nombre_zip = info.filename
            if info.filename == 'project.xml':
                datos = proyecto2.encode('utf-8')
            elif info.filename == ruta_xml:
                datos = nuevo_xml.encode('utf-8')
                nombre_zip = carpeta_nueva + '/MpFolder.xml'
            zout.writestr(nombre_zip, datos)
    return list(comps)
