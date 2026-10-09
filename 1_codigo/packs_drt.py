# CineCaptions · By Cinema Productions
# 1_codigo/packs_drt.py — lee los packs .drt/.drb SIN abrir Resolve (sets, formatos, tipografías).
"""\npacks_drt.py — leer un pack .drt SIN abrir Resolve.\n\nPor que existe\n==============\nHasta la v1.0.26 la unica forma de saber que traia un pack era importarlo:\nabrir Resolve, correr el script, esperar, y leer lo que dijera. Si algo\nsalia a medias el usuario se enteraba al mirar el render. El reporte fue\nliteral: \"simula que los importa pero cuando le das a generar no los toma\".\n\nUn .drt es un ZIP. Adentro:\n\n    project.xml                     (metadatos del proyecto, poco util)\n    MediaPool/Master/MpFolder.xml   (SOLO el clip del timeline; los Text+\n                                     NO estan aca -por eso hay que pasarlos\n                                     al Media Pool al usarlo-)\n    SeqContainer/<uuid>.xml         (el timeline: un <Sm2TiVideoClip> por\n                                     clip, con su comp de Fusion adentro)\n\nLa comp de cada clip viaja en <CompositionBA>, en hexadecimal, y son DOS\nzlib anidados: el de fuera trae la cabecera (Composition { ... }) y adentro,\nal final, otro zlib con la lista de nodos, que es donde estan Font y Style.\n\nCon eso se puede decir, en el momento en que el usuario elige el archivo y\nsin tocar Resolve: cuantos sets hay, cuales faltan, cuales estan repetidos\ny que tipografias hacen falta. Nada que pueda mentir.\n\nLo que NO se puede leer aca: la resolucion del timeline. Vive en un blob\nbinario propio de Resolve. Asi que el formato (horizontal / vertical /\ncuadrado) lo elige el usuario y lo confirma el script adentro de Resolve,\nque es donde se sabe de verdad — misma regla que el fps.\n"""
from __future__ import annotations
import binascii
import json
import re
import struct
import zipfile
import zlib
from pathlib import Path
from i18n import tr
ROLES = ('context', 'main', 'complement')
ROL_IMAGEN = 'image'
# v5.3: la estructura de un pack. Nombres que se PIDEN y se muestran: arriba · principal · abajo · imagen
# (+ simple para las palabras sueltas). 'imagen' es el bloque donde va el icono o la imagen (el emoji).
NOMBRES = {'context': 'arriba', 'main': 'principal', 'complement': 'abajo', 'image': 'imagen', 'base': 'simple'}
# Nombres que se ACEPTAN: los de antes (contexto / complemento / base) siguen valiendo, así los packs
# hechos antes no se tocan. Los tres lectores (esta, el .py y el .lua de Resolve) tienen que dar lo mismo.
ALIAS = {
    'context': ('arriba', 'contexto'),
    'main': ('principal',),
    'complement': ('abajo', 'complemento'),
    'image': ('imagen',),
}
ALIAS_BASE = ('simple', 'base')
MAX_SETS = 10            # packs con los nombres de siempre
MAX_VARIANTES = 10       # packs con los nombres nuevos: arriba 1..10, abajo 1..10, imagen 1..10 (v5.9: antes 3; el pack «Referencia» lleva 8 estilos)
_SOLO_NUEVOS = ('arriba', 'abajo', 'imagen')
_CLIP = re.compile('<Sm2TiVideoClip .*?</Sm2TiVideoClip>', re.S)
_NOMBRE = re.compile('<Name>(.*?)</Name>', re.S)
_TIPO = re.compile('<PrettyType>(.*?)</PrettyType>', re.S)
_COMP = re.compile('<CompositionBA>([0-9a-fA-F]*)</CompositionBA>')
_FUENTE = re.compile('Font = Input \\{ Value = \"([^\"]{1,80})\".{0,300}?Style = Input \\{ Value = \"([^\"]{1,80})\"', re.S)
def parsear_nombre(bruto):
    """'Arriba 2' -> ('context', 2).  'simple' -> ('base', 0).  'imagen 3' -> ('image', 3).

    Siguen valiendo los nombres de antes: 'Contexto 8' -> ('context', 8), 'complemento',
    'base'. Devuelve (None, 0) si no es un nombre de rol, y (rol, -1) si el numero se sale
    de 1..MAX_SETS (1..MAX_VARIANTES con los nombres nuevos arriba/abajo/imagen) -para poder
    avisarlo en vez de descartarlo en silencio-.

    Es gemela de parsear_nombre() de los scripts de Resolve (el .py y el .lua). Los tres
    tienen que dar lo mismo o el pack se ve distinto segun quien lo lea; hay un test que
    los compara.
    """
    n = (bruto or '').strip().lower()
    n = re.sub(r'\.[a-z]+$', '', n)
    if n in ALIAS_BASE:
        return ('base', 0)
    for rol, palabras in ALIAS.items():
        for palabra in palabras:
            if n == palabra:
                return (rol, 1)
            m = re.match('^' + re.escape(palabra) + r'[\s\-_.]*0*(\d+)$', n)
            if not m:
                continue
            k = int(m.group(1))
            tope = MAX_VARIANTES if palabra in _SOLO_NUEVOS else MAX_SETS
            if 1 <= k <= tope:
                return (rol, k)
            return (rol, (-1))
    return (None, 0)
def es_nombre_nuevo(bruto):
    """True si el nombre es de la estructura nueva (arriba / abajo / imagen / simple)."""
    n = re.sub(r'\.[a-z]+$', '', (bruto or '').strip().lower())
    if n == 'simple':
        return True
    return any(re.match('^' + p + r'[\s\-_.]*0*\d*$', n) for p in _SOLO_NUEVOS)
_BASICO = re.compile('^(basico|traducc?ion) (inferior|superior) 0*(\\d+)$')
def parsear_nombre_basico(bruto):
    """\'traducion  inferior 2\' -> (\'traducion\', \'inferior\', 2), o None."""
    n = re.sub('\\s+', ' ', (bruto or '').strip().lower())
    n = re.sub('\\.[a-z]+$', '', n)
    m = _BASICO.match(n)
    if not m:
        return
    else:
        tipo = 'basico' if m.group(1) == 'basico' else 'traducion'
        return (tipo, m.group(2), int(m.group(3)))
def _descomprimir(hex_blob):
    """El <CompositionBA> -> (cabecera, nodos) como texto. Puede dar None.\n\n    Nunca lanza: un pack con una comp rara tiene que poder leerse igual\n    -se pierden sus fuentes, no el pack entero-.\n    """
    if not hex_blob:
        return (None, None)
    else:
        try:
            crudo = binascii.unhexlify(hex_blob)
        except (binascii.Error, ValueError):
            return (None, None)
        i = crudo.find(b'x\x9c')
        if i < 0:
            return (None, None)
        else:
            try:
                cabecera = zlib.decompress(crudo[i:])
            except zlib.error:
                return (None, None)
            nodos = None
            for off in range(80, max(80, len(cabecera) - 2)):
                if cabecera[off] != 120 or cabecera[off + 1] not in [1, 94, 156, 218]:
                    continue
                else:
                    try:
                        salida = zlib.decompressobj().decompress(cabecera[off:])
                    except zlib.error:
                        pass
                    else:
                        if len(salida) > 500:
                            nodos = salida
                            break
            return (cabecera.decode('utf-8', 'replace'), nodos.decode('utf-8', 'replace') if nodos else None)
def leer(ruta):
    """Lee un .drt y cuenta lo que trae.

    Devuelve un dict SIEMPRE (nunca lanza). Con ok=False trae 'error' con
    algo que se le pueda enseñar al usuario tal cual.
    """
    ruta = Path(ruta)
    vacio = {'ok': False, 'ruta': str(ruta), 'sets': {}, 'completos': [],
             'huecos': [], 'duplicados': [], 'base': False, 'fuentes': [],
             'tipografias': {}, 'ignorados': [], 'avisos': [], 'clips': 0,
             'imagenes': [], 'nuevo': False}
    if not ruta.is_file():
        return dict(vacio, error=tr('No encuentro el archivo:\n{ruta}',
                                    ruta=ruta))
    try:
        zf = zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError) as exc:
        return dict(vacio, error=tr(
            '«{nombre}» no parece un .drt de Resolve ({exc}).\nTiene que ser el archivo que sale de Archivo > Exportar > Timeline, no un proyecto (.drp) ni una carpeta comprimida.',
            nombre=ruta.name, exc=exc))
    with zf:
        secuencias = [n for n in zf.namelist()
                      if n.startswith('SeqContainer/') and n.endswith('.xml')]
        if not secuencias:
            return dict(vacio, error=tr(
                '«{nombre}» es un ZIP pero no lleva ningun timeline adentro. ¿Seguro que es un .drt exportado de Resolve?',
                nombre=ruta.name))
        avisos = []
        if len(secuencias) > 1:
            avisos.append(tr('El archivo trae {n} timelines; se leen todos juntos.',
                             n=len(secuencias)))
        xml = ''
        for nombre in sorted(secuencias):
            try:
                xml += zf.read(nombre).decode('utf-8', 'replace')
            except (KeyError, OSError, zlib.error) as exc:
                avisos.append(tr("No pude leer '{nombre}' ({exc}).",
                                 nombre=nombre, exc=exc))

    sets, duplicados_por, base, ignorados, fuentes = {}, {}, False, [], {}
    fuera_de_rango, comps_ilegibles, total = [], 0, 0
    tipografias = {}
    imagenes = {}
    bloques_xml = _CLIP.findall(xml)
    nuevo = any(es_nombre_nuevo(_NOMBRE.search(b).group(1) if _NOMBRE.search(b) else '') for b in bloques_xml)
    for bloque in bloques_xml:
        total += 1
        m = _NOMBRE.search(bloque)
        bruto = m.group(1) if m else ''
        m = _TIPO.search(bloque)
        tipo = m.group(1) if m else ''
        rol, n = parsear_nombre(bruto)
        if rol is None:
            if tipo != 'Adjustment Clip':
                ignorados.append(bruto or '(sin nombre)')
            continue
        if n == -1 or (nuevo and n > MAX_VARIANTES):
            fuera_de_rango.append(bruto)
            continue
        if rol == 'image':
            imagenes.setdefault(n, bruto)
            continue
        if rol == 'base':
            base = True
        else:
            hueco = sets.setdefault(n, {})
            if rol in hueco:
                duplicados_por.setdefault((rol, n), [hueco[rol]]).append(bruto)
                continue
            hueco[rol] = bruto
        m = _COMP.search(bloque)
        _, nodos = _descomprimir(m.group(1) if m else '')
        if nodos is None:
            comps_ilegibles += 1
            continue
        primera = True
        for familia, estilo in _FUENTE.findall(nodos):
            fuentes[(familia.strip(), estilo.strip())] = True
            if primera:
                clave = '%s|%d' % (rol, 0 if rol == 'base' else n)
                tipografias.setdefault(
                    clave, (familia.strip(), estilo.strip()))
                primera = False

    completos = sorted(n for n, roles in sets.items()
                       if all(r in roles for r in ROLES))
    huecos = []
    if sets:
        for n in range(1, max(sets) + 1):
            for rol in ROLES:
                if rol not in sets.get(n, {}):
                    huecos.append((rol, n))
    if fuera_de_rango:
        avisos.append(tr('Fuera del rango 1–%d, no se usan: %s.')
                      % (MAX_VARIANTES if nuevo else MAX_SETS, ', '.join(sorted(fuera_de_rango))))
    if comps_ilegibles:
        avisos.append(tr('De %d clips no pude leer el diseño, asi que la lista de tipografias puede estar incompleta.')
                      % comps_ilegibles)
    if ignorados:
        avisos.append(tr('Clips que no son de un rol conocido (se ignoran): %s.')
                      % ', '.join(sorted(set(ignorados))[:8]))
    return {
        'ok': bool(sets or base),
        'error': None if sets or base else tr(
            "«{nombre}» no trae ningun Text+ llamado 'arriba', 'principal' o 'abajo'. Reviso {n} clips.",
            nombre=ruta.name, n=total),
        'ruta': str(ruta),
        'clips': total,
        'sets': sets,
        'completos': completos,
        'huecos': huecos,
        'duplicados': [(rol, n, nombres)
                       for (rol, n), nombres in sorted(duplicados_por.items())],
        'base': base,
        'fuentes': sorted(fuentes),
        'tipografias': tipografias,
        'ignorados': sorted(set(ignorados)),
        'avisos': avisos,
        'imagenes': sorted(imagenes),
        'nuevo': nuevo,
    }
_TEXTPLUS = re.compile('=\\s*TextPlus\\s*\\{')
_V_TEXTO = '{clave} = Input \\{{ Value = \"([^\"]{{0,80}})\"'
_V_NUM = '(?<![A-Za-z0-9_]){clave} = Input \\{{ Value = (-?[0-9.]+)'
_GRAD = re.compile('Colors = \\{ \\[0\\] = \\{ ([0-9.]+), ([0-9.]+), ([0-9.]+)')
def _bloque_balanceado(texto, desde):
    """El bloque { ... } que empieza en \'desde\', contando llaves."""
    nivel, i = (0, desde)
    while i < len(texto):
        c = texto[i]
        if c == '{':
            nivel += 1
        else:
            if c == '}':
                nivel -= 1
                if nivel == 0:
                    return texto[desde:i + 1]
        i += 1
    return texto[desde:]
def _estilo_de_comp(nodos):
    """{font, style, size, tracking, color} del TextPlus de ese comp.\n\n    Se acota al NODO TextPlus contando llaves, no con una ventana de N\n    caracteres: en el comp de un pack hay hasta cinco nodos con \'Font\' y\n    emparejar la fuente de uno con el tamaño de otro daria un estilo que no\n    existe en ningun sitio.\n    """
    m = _TEXTPLUS.search(nodos or '')
    if not m:
        return
    else:
        bloque = _bloque_balanceado(nodos, nodos.index('{', m.start()))
        def texto(clave):
            r = re.search(_V_TEXTO.format(clave=clave), bloque)
            return r.group(1).strip() if r else None
        def numero(clave):
            r = re.search(_V_NUM.format(clave=clave), bloque)
            try:
                return float(r.group(1)) if r else None
            except ValueError:
                return None
        estilo = {}
        for clave, valor in [('font', texto('Font')), ('style', texto('Style'))]:
            if valor:
                estilo[clave] = valor
        for clave, valor in [('size', numero('Size')), ('tracking', numero('CharacterSpacing'))]:
            if valor is not None:
                estilo[clave] = valor
        rgb = [numero('Red1'), numero('Green1'), numero('Blue1')]
        if any((v is None for v in rgb)):
            g = _GRAD.search(bloque)
            if g:
                try:
                    rgb = [float(g.group(i)) for i in [1, 2, 3]]
                except ValueError:
                    rgb = [None, None, None]
        if all((isinstance(v, float) for v in rgb)):
            estilo['color'] = [max(0.0, min(1.0, v)) for v in rgb]
        return estilo or None
def estilos(ruta):
    """Los estilos por valor de un .drt: {\"sets\": {n: {rol: e}}, \"base\": e}.\n\n    Nunca lanza: si algo no se puede leer, ese rol simplemente no sale, y\n    quien llama se queda sin repuesto para ese rol —no con uno inventado—.\n    """
    fuera = {'sets': {}, 'base': None}
    ruta = Path(ruta)
    if not ruta.is_file():
        return fuera
    else:
        try:
            zf = zipfile.ZipFile(ruta)
        except (zipfile.BadZipFile, OSError):
            return fuera
        with zf:
            xml = ''
            for nombre in sorted((n for n in zf.namelist() if n.startswith('SeqContainer/') and n.endswith('.xml'))):
                try:
                    xml += zf.read(nombre).decode('utf-8', 'replace')
                except (KeyError, OSError, zlib.error):
                    pass
                else:
                    pass
        for bloque in _CLIP.findall(xml):
            m = _NOMBRE.search(bloque)
            rol, n = parsear_nombre(m.group(1) if m else '')
            if rol is None or n == (-1) or rol == 'image':
                continue
            else:
                m = _COMP.search(bloque)
                if not m:
                    continue
                else:
                    try:
                        _, nodos = _descomprimir(m.group(1))
                    except Exception:
                        pass
                    else:
                        if not nodos:
                            continue
                        else:
                            estilo = _estilo_de_comp(nodos)
                            if estilo:
                                if rol == 'base':
                                    fuera['base'] = fuera['base'] or estilo
                                else:
                                    fuera['sets'].setdefault(n, {}).setdefault(rol, estilo)
        return fuera
# ---------------------------------------------------------------------------------------------
# v5.3 — la posición y el zoom de cada clip de un .drb, leídos del propio .drb (sin .posiciones.json)
# ---------------------------------------------------------------------------------------------
# En el project.xml del .drb cada clip tiene un blob (Sm2MpItemLockableBlob, zstd + protobuf) con su
# Pan / Tilt / Zoom de la pagina Edicion: campos 40..43 como `4a 0f 08 <id> 1a 0b 0a 09 11 <double>`.
# Sirve para que un pack que el usuario crea (con el bloque «imagen») traiga su posicion sin mas pasos.
_POS_CAMPO = re.compile(rb'\x4a\x0f\x08([\x28-\x2b])\x1a\x0b\x0a\x09\x11(.{8})', re.S)
_BLOB_ITEM = re.compile(r'<Sm2MpItemLockableBlob DbId="[^"]+">\s*<FieldsBlob>([0-9a-f]*)</FieldsBlob>\s*<BlobOwner>([^<]+)</BlobOwner>')
_GENERADOR = re.compile(r'<Sm2Mp[A-Za-z]+ DbId="([^"]+)">(?:(?!</Sm2Mp[A-Za-z]+>).){0,6000}?<Name>(.*?)</Name>', re.S)
_MEMO_POS = {}
def _carga_del_blob(hex_blob):
    """El protobuf (descomprimido) de un FieldsBlob del project.xml, o None."""
    try:
        b = binascii.unhexlify(hex_blob)
        i = 12 + 16 + 4 + 1
        _tam, tipo, largo = struct.unpack('>III', b[i:i + 12])
        if tipo != 10001:
            i = b.find(struct.pack('>I', 10001)) - 4
            _tam, tipo, largo = struct.unpack('>III', b[i:i + 12])
        carga = b[i + 12:i + 12 + largo]
        if carga[:1] == b'\x81':
            from compression import zstd
            return zstd.decompress(carga[1:])
        return carga[1:]
    except Exception:
        return None
def posiciones_de_drb(ruta):
    """{nombre del clip: [x, y, zoom_x, zoom_y]} leido del .drb. Nunca lanza ({} si no se puede).

    x / y: fraccion del ancho / alto (Y positiva = arriba), como el .posiciones.json. Lo que el
    clip no trae es su valor por defecto (0, 0, 1, 1).
    """
    ruta = Path(ruta)
    try:
        st = ruta.stat()
        clave = (str(ruta.resolve()), st.st_size, st.st_mtime_ns)
    except OSError:
        return {}
    if clave in _MEMO_POS:
        return dict(_MEMO_POS[clave])
    fuera = {}
    try:
        with zipfile.ZipFile(ruta) as zf:
            proyecto = zf.read('project.xml').decode('utf-8', 'replace')
            nombres = {}
            for entrada in zf.namelist():
                if entrada.endswith('MpFolder.xml'):
                    xml = zf.read(entrada).decode('utf-8', 'replace')
                    for m in _GENERADOR.finditer(xml):
                        nombres.setdefault(m.group(1), m.group(2))
        for hex_blob, dueno in _BLOB_ITEM.findall(proyecto):
            nombre = nombres.get(dueno)
            if not nombre:
                continue
            carga = _carga_del_blob(hex_blob)
            if not carga:
                continue
            valores = [0.0, 0.0, 1.0, 1.0]
            for m in _POS_CAMPO.finditer(carga):
                valores[m.group(1)[0] - 0x28] = struct.unpack('<d', m.group(2))[0]
            fuera.setdefault(nombre, [round(v, 6) for v in valores])
    except Exception:
        fuera = {}
    _MEMO_POS[clave] = dict(fuera)
    return fuera
_VERSION_CLIP = re.compile('^Versi(?:o|ó)n \\d+$')
_NOMBRE_O_COMP = re.compile('<Name>(.*?)</Name>|<CompositionBA>([0-9a-fA-F]*)</CompositionBA>', re.S)
_MEMO_DRB = {}
def leer_drb(ruta, con_estilos=False):
    """Como _leer_drb, con memo por (ruta, tamaño, fecha) — v3.3.3: el\n    arranque leia los mismos 8 .drb dos o tres veces (0,75 s cada pasada).\n    \'con_estilos\' (el estilo entero de cada TextPlus, v3.3.1) es opcional:\n    era el 70 % del costo y solo lo pide plantillas.estilos_para_medir."""
    try:
        st = Path(ruta).stat()
        clave = (str(Path(ruta).resolve()), st.st_size, st.st_mtime_ns, bool(con_estilos))
    except OSError:
        return _leer_drb(ruta, con_estilos)
    if clave not in _MEMO_DRB:
        _MEMO_DRB[clave] = _leer_drb(ruta, con_estilos)
    salida = _MEMO_DRB[clave]
    if isinstance(salida, dict):
        return dict(salida)
    else:
        return salida
def _leer_drb(ruta, con_estilos=False):
    """Lee un .drb (bin exportado) y cuenta lo que trae, sin abrir Resolve.

    Misma forma que leer() para que resumen()/detalle() y la ventana lo
    traten igual. Existe por la v1.0.57: los packs solo-.drb («Títulos
    dinámicos II», y los .drb que importa el usuario) necesitan
    sets/base/avisos en el momento de elegir el archivo — nada que pueda
    mentir. Desde la v1.0.61 'tipografias' viene lleno como en leer():
    los comps SI se emparejan clip a clip tomando el ultimo <Name> que no
    sea 'Versión N' antes de cada <CompositionBA> — el ciclo del MpFolder
    es regular (verificado 1:1 en los 5 .drb reales) y hace falta para el
    veto de sets cuya tipografia no dibuja tildes (pedido literal: «si la
    palabra tiene tilde no uses la combinación de Tempting»). Si un comp
    aparece sin clip delante, tipografias queda VACIO: mejor sin veto que
    con un veto equivocado.
    """
    ruta = Path(ruta)
    vacio = {'ok': False, 'ruta': str(ruta), 'sets': {}, 'completos': [],
             'huecos': [], 'duplicados': [], 'base': False, 'fuentes': [],
             'tipografias': {}, 'ignorados': [], 'avisos': [], 'clips': 0,
             'basicos': {}, 'estilos': {}, 'imagenes': [], 'nuevo': False}
    if not ruta.is_file():
        return dict(vacio, error=tr('No encuentro el archivo:\n{ruta}',
                                    ruta=ruta))
    try:
        zf = zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError) as exc:
        return dict(vacio, error=tr(
            '«{nombre}» no parece un bin exportado de Resolve ({exc}).\nTiene que ser el archivo del clic derecho sobre el bin → Exportar bandeja…',
            nombre=ruta.name, exc=exc))
    nombres = []
    parejas = []
    emparejado_mal = False
    with zf:
        carpetas = [n for n in zf.namelist() if n.endswith('MpFolder.xml')]
        if not carpetas:
            return dict(vacio, error=tr(
                '«{nombre}» es un ZIP pero no trae ningun bin adentro. ¿Seguro que salio de Exportar bandeja…?',
                nombre=ruta.name))
        for entrada in sorted(carpetas):
            try:
                xml = zf.read(entrada).decode('utf-8', 'replace')
            except (KeyError, OSError, zlib.error):
                continue
            vistos = _NOMBRE.findall(xml)
            nombres.extend(vistos[1:])
            pendiente, primero = None, True
            for m in _NOMBRE_O_COMP.finditer(xml):
                if m.group(1) is not None:
                    if primero:
                        primero = False
                        continue
                    if _VERSION_CLIP.match(m.group(1) or ''):
                        continue
                    pendiente = m.group(1)
                elif pendiente is None:
                    emparejado_mal = True
                else:
                    parejas.append((pendiente, m.group(2)))
                    pendiente = None

    sets, duplicados_por, base = {}, {}, False
    ignorados, fuera_de_rango, total = [], [], 0
    vistos_basicos = {}
    imagenes = {}
    nuevo = any(es_nombre_nuevo(b) for b in nombres if not _VERSION_CLIP.match(b or ''))
    for bruto in nombres:
        if _VERSION_CLIP.match(bruto or ''):
            continue
        total += 1
        pb = parsear_nombre_basico(bruto)
        if pb:
            tipo, pos, num = pb
            vistos_basicos.setdefault(tipo, {}).setdefault(
                pos, set()).add(num)
            continue
        rol, n = parsear_nombre(bruto)
        if rol is None:
            ignorados.append(bruto or '(sin nombre)')
            continue
        if n == -1 or (nuevo and n > MAX_VARIANTES):
            fuera_de_rango.append(bruto)
            continue
        if rol == 'image':
            imagenes.setdefault(n, bruto)
            continue
        if rol == 'base':
            base = True
            continue
        hueco = sets.setdefault(n, {})
        if rol in hueco:
            duplicados_por.setdefault((rol, n), [hueco[rol]]).append(bruto)
            continue
        hueco[rol] = bruto

    completos = sorted(n for n, roles in sets.items()
                       if all(r in roles for r in ROLES))
    huecos = []
    if sets:
        for n in range(1, max(sets) + 1):
            for rol in ROLES:
                if rol not in sets.get(n, {}):
                    huecos.append((rol, n))
    avisos = []
    if fuera_de_rango:
        avisos.append(tr('Fuera del rango 1–%d, no se usan: %s.')
                      % (MAX_VARIANTES if nuevo else MAX_SETS, ', '.join(sorted(fuera_de_rango))))
    if ignorados:
        avisos.append(tr('Clips que no son de un rol conocido (se ignoran): %s.')
                      % ', '.join(sorted(set(ignorados))[:8]))
    basicos = {pos: sorted(nums)
               for pos, nums in vistos_basicos.get('basico', {}).items()
               if nums}
    for pos, nums in sorted(basicos.items()):
        con_trad = vistos_basicos.get('traducion', {}).get(pos, set())
        sin_pareja = [n for n in nums if n not in con_trad]
        if sin_pareja:
            avisos.append(
                tr("Combinaciones de basicos sin su pareja 'traducion' (%s %s): la pista traducida saldria con la plantilla de siempre.")
                % (pos, ', '.join(map(str, sin_pareja))))

    tipografias, estilos = {}, {}
    if not emparejado_mal:
        for bruto, blob in parejas:
            rol, n = parsear_nombre(bruto)
            if rol is None or n == -1 or rol == 'image':
                continue
            try:
                _, nodos = _descomprimir(blob)
            except Exception:
                continue
            if not nodos:
                continue
            clave = '%s|%d' % (rol, 0 if rol == 'base' else n)
            m = _FUENTE.search(nodos)
            if m:
                tipografias.setdefault(
                    clave, (m.group(1).strip(), m.group(2).strip()))
            if not con_estilos:
                continue
            try:
                estilo = _estilo_de_comp(nodos)
            except Exception:
                estilo = None
            if estilo and estilo.get('font') and estilo.get('size'):
                estilos.setdefault(clave, {
                    k: estilo[k] for k in ('font', 'style', 'size', 'tracking')
                    if k in estilo})
    return dict(
        vacio,
        ok=bool(sets or base or basicos),
        error=None if sets or base or basicos else tr(
            "«{nombre}» no trae ningun Text+ llamado 'arriba', 'principal' o 'abajo'. Reviso {n} clips.",
            nombre=ruta.name, n=total),
        basicos=basicos, imagenes=sorted(imagenes), nuevo=nuevo,
        clips=total, sets=sets, completos=completos, huecos=huecos,
        duplicados=[(rol, n, nombres_d)
                    for (rol, n), nombres_d in sorted(duplicados_por.items())],
        base=base, fuentes=fuentes_de_drb(ruta),
        tipografias=tipografias, estilos=estilos,
        ignorados=sorted(set(ignorados)), avisos=avisos,
    )
def fuentes_de_drb(ruta):
    """Las (familia, estilo) que piden las comps de un .drb, sin repetir.

    Un .drb (bin exportado) es un ZIP como el .drt, pero sus comps viven en
    MediaPool/.../MpFolder.xml en vez de SeqContainer/. Existe porque el
    aviso de tipografias y el boton de instalar leian SOLO el .drt — y con
    el .drb embebido mandando (v1.0.55), un diseño nuevo con otras fuentes
    (la Kingsguard) faltaba en el sistema sin que el boton la ofreciera:
    en la Mac del usuario el set salia con otra fuente y no habia forma de
    instalarla desde el programa. Nunca lanza: sin archivo o corrupto,
    lista vacia, y quien llama se queda con las fuentes del .drt.
    """
    fuera = set()
    ruta = Path(ruta)
    if not ruta.is_file():
        return []
    try:
        zf = zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError):
        return []
    with zf:
        for nombre in zf.namelist():
            if not nombre.endswith('MpFolder.xml'):
                continue
            try:
                xml = zf.read(nombre).decode('utf-8', 'replace')
            except (KeyError, OSError, zlib.error):
                continue
            for blob in _COMP.findall(xml):
                try:
                    cabecera, nodos = _descomprimir(blob)
                except Exception:
                    continue
                texto = (nodos or '') + (cabecera or '')
                for familia, estilo in _FUENTE.findall(texto):
                    fuera.add((familia, estilo))
    return sorted(fuera)
_INPUT_CONECTADO = re.compile('[A-Za-z0-9_]+ = Input \\{ SourceOp = \"[^\"]*\", Source = \"[^\"]*\",? ?\\},? ?')
_STYLED_CONECTADO = re.compile('StyledText = Input \\{ SourceOp = \"[^\"]*\", Source = \"[^\"]*\",? ?\\},? ?')
def _setting_de_bloque(bloque):
    """Envuelve un bloque TextPlus del .drt como .setting de Fusion.\n\n    La envoltura es la MISMA que escribe tool:SaveSettings() (verificada\n    contra prueba_textplus.setting, salido del propio Fusion):\n\n        { Tools = ordered() { Template = TextPlus { ... } } }\n\n    Cirugia de conexiones: el StyledText del pack esta CONECTADO a un\n    StyledTextFollower (SourceOp) que no viaja — cargado asi, el texto\n    saldria vacio para siempre. Se sustituye por un Value vacio: el script\n    escribe el texto DESPUES de LoadSettings (el orden ya esta documentado\n    en los dos gemelos). Cualquier otro input conectado se elimina, que es\n    dejarle su valor por defecto en vez de una referencia rota.\n    """
    bloque = _STYLED_CONECTADO.sub('StyledText = Input { Value = \"\" }, ', bloque)
    bloque = _INPUT_CONECTADO.sub('', bloque)
    return '{\n\tTools = ordered() {\n\t\tTemplate = TextPlus ' + bloque + '\n\t}\n}\n'
def settings(ruta):
    """Los .setting de un .drt, fabricados sin abrir Resolve.

    Devuelve {(rol, n): texto_setting} — rol en el vocabulario interno
    ('context'/'main'/'complement'/'base', n=0 para base). Nunca lanza: un
    clip ilegible simplemente no sale, y quien llama degrada a valores.
    """
    fuera = {}
    ruta = Path(ruta)
    if not ruta.is_file():
        return fuera
    try:
        zf = zipfile.ZipFile(ruta)
    except (zipfile.BadZipFile, OSError):
        return fuera
    with zf:
        xml = ''
        for nombre in sorted(n for n in zf.namelist()
                             if n.startswith('SeqContainer/')
                             and n.endswith('.xml')):
            try:
                xml += zf.read(nombre).decode('utf-8', 'replace')
            except (KeyError, OSError, zlib.error):
                continue
    for bloque_clip in _CLIP.findall(xml):
        m = _NOMBRE.search(bloque_clip)
        rol, n = parsear_nombre(m.group(1) if m else '')
        if rol is None or n == -1 or rol == 'image':
            continue
        clave = (rol, 0 if rol == 'base' else n)
        if clave in fuera:
            continue
        m = _COMP.search(bloque_clip)
        if not m:
            continue
        try:
            _, nodos = _descomprimir(m.group(1))
        except Exception:
            continue
        if not nodos:
            continue
        mt = _TEXTPLUS.search(nodos)
        if not mt:
            continue
        try:
            bloque = _bloque_balanceado(nodos, nodos.index('{', mt.start()))
        except ValueError:
            continue
        fuera[clave] = _setting_de_bloque(bloque)
    return fuera
def resumen(info, fuentes_faltantes=None):
    """Una linea corta para la ventana: \'10 sets · base · 2 huecos\'."""
    if not info.get('ok'):
        return info.get('error') or tr('No pude leer el pack.')
    else:
        partes = [tr('%d combinaciones') % len(info['completos'])]
        if info.get('imagenes'):
            partes.append(tr('con imagen'))
        if info['base']:
            partes.append(tr('simple'))
        if info['huecos']:
            partes.append(tr('%d sin completar') % len(info['huecos']))
        if info['duplicados']:
            partes.append(tr('%d repetidos') % len(info['duplicados']))
        if fuentes_faltantes:
            partes.append(tr('faltan %d tipografias') % len(fuentes_faltantes))
        return ' · '.join(partes)
def detalle(info, fuentes_faltantes=None):
    """Las lineas largas, para el aviso al añadir el pack. Lista vacia si\n    todo esta bien: no se inventa un aviso cuando no hay nada que decir."""
    lineas = []
    for rol, n in info.get('huecos', []):
        lineas.append(tr('Falta «%s %d».') % (NOMBRES[rol], n))
    for rol, n, nombres in info.get('duplicados', []):
        lineas.append(tr('«%s %d» esta repetido: %s. Se usa el primero.') % (NOMBRES[rol], n, ', '.join(nombres)))
    for f in fuentes_faltantes or []:
        lineas.append(tr('No tienes instalada la tipografia «%s %s».') % f)
    lineas += info.get('avisos', [])
    return lineas
