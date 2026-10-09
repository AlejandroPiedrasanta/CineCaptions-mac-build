# CineCaptions · By Cinema Productions
# 1_codigo/fuentes_sistema.py — encuentra en el disco el archivo .ttf/.otf de una familia y estilo.
"""\nfuentes_sistema.py\n-------------------\nEncontrar en el disco el archivo .ttf/.otf que corresponde a una familia y\nun estilo. Sin esto, \"Open Sans Bold\" es solo un nombre: para dibujar algo\ncon Pillow, o para copiar la fuente a otra maquina, hace falta la RUTA.\n\nEste modulo SI entra en el instalador -lo usa medir_texto.py para el modo\ndestacados \'pintado\'-, a diferencia de extraer_tipografias.py, que es una\nherramienta personal y no se empaqueta. Antes esta logica vivia duplicada\nadentro de esa herramienta; se separo para que el programa la use sin\narrastrar el resto del extractor (recorrer timelines, hacer zips, etc).\n"""
import json
import os
import struct
import sys
import threading
from pathlib import Path
EXTENSIONES = {'.ttf', '.otc', '.otf', '.ttc'}
_NAME_IDS = (1, 2, 4, 16, 17)
def normalizar(texto):
    return ''.join(str(texto).lower().split()).replace('-', '').replace('_', '')
def _decodificar(platform_id, crudo):
    if platform_id in (0, 3):
        try:
            return crudo.decode('utf-16-be').replace('\x00', '').strip()
        except Exception:
            return ''
    else:
        try:
            return crudo.decode('latin-1').strip()
        except Exception:
            return ''
def _leer_cara(f, offset):
    """(familia16, estilo17, familia1, estilo2, completo) de una cara sfnt."""
    f.seek(offset)
    cabecera = f.read(12)
    if len(cabecera) < 12:
        return None
    if cabecera[:4] not in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1'):
        return None
    num_tablas, = struct.unpack('>H', cabecera[4:6])
    tabla = None
    for _ in range(min(num_tablas, 512)):
        registro = f.read(16)
        if len(registro) < 16:
            return None
        if registro[:4] == b'name':
            _, _, inicio, largo = struct.unpack('>4sIII', registro)
            tabla = (inicio, largo)
            break
    if not tabla:
        return None
    inicio, largo = tabla
    f.seek(inicio)
    datos = f.read(largo)
    if len(datos) < 6:
        return None
    _, cantidad, inicio_textos = struct.unpack('>HHH', datos[:6])
    nombres, preferidos = {}, set()
    for i in range(cantidad):
        base = 6 + i * 12
        if base + 12 > len(datos):
            break
        pid, _eid, lid, nid, largo_n, off_n = struct.unpack(
            '>HHHHHH', datos[base:base + 12])
        if nid not in _NAME_IDS:
            continue
        desde = inicio_textos + off_n
        texto = _decodificar(pid, datos[desde:desde + largo_n])
        if not texto:
            continue
        ingles = (pid == 3 and lid == 1033) or (pid == 1 and lid == 0)
        if nid not in nombres or (ingles and nid not in preferidos):
            nombres[nid] = texto
            if ingles:
                preferidos.add(nid)
    if not nombres.get(16) and not nombres.get(1):
        return None
    return (nombres.get(16), nombres.get(17),
            nombres.get(1), nombres.get(2), nombres.get(4))
def _caras_del_archivo(ruta):
    try:
        with open(ruta, 'rb') as f:
            etiqueta = f.read(4)
            offsets = [0]
            if etiqueta == b'ttcf':
                f.seek(8)
                cuantas, = struct.unpack('>I', f.read(4))
                cuantas = min(cuantas, 64)
                offsets = list(struct.unpack(f'>{cuantas}I', f.read(4 * cuantas)))
            caras = []
            for off in offsets:
                cara = _leer_cara(f, off)
                if cara:
                    caras.append(cara)
            return caras
    except Exception:
        return []
def _base_recursos():
    """La carpeta desde donde leer datos: el bundle si esta compilado.\n\n    Misma logica que en CineCaptions (script principal).py, instalador_scripts.py\n    y sfx_rules.py. Se repite (cuatro lineas) en vez de importar la app,\n    porque este modulo tiene que poder usarse suelto -lo usan medir_texto,\n    previsualizaciones y los tests-.\n    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent.parent / '2_recursos'
def carpeta_incluida():
    """La carpeta \'fonts/\' que viaja DENTRO del programa, o None.\n\n    Son las tipografias de los packs que se entregan con el producto. Estan\n    ahi para que Pillow pueda medirlas y dibujarlas sin depender de que el\n    usuario las tenga instaladas — pero OJO: que esten aca NO significa que\n    Resolve las vea. Fusion lee del registro de fuentes del sistema\n    operativo, no de una carpeta cualquiera. Para eso esta\n    instalar_fuentes.py; para saber cual es cual, esta_en_el_sistema().\n    """
    carpeta = _base_recursos() / 'fonts'
    try:
        return carpeta if carpeta.is_dir() else None
    except OSError:
        return None
def caras_de(ruta):
    """[(familia16, estilo17, familia1, estilo2, nombre_completo), ...].\n\n    Publica porque instalar_fuentes.py necesita el nombre completo (nameID\n    4) para registrar la fuente en Windows con el nombre que el sistema\n    espera. Un .ttc trae varias caras en un archivo.\n    """
    return _caras_del_archivo(ruta)
def carpetas_de_fuentes(extras=(), incluidas=True):
    candidatas = []
    if sys.platform.startswith('win'):
        candidatas.append(Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Fonts')
        local = os.environ.get('LOCALAPPDATA')
        if local:
            candidatas.append(Path(local) / 'Microsoft' / 'Windows' / 'Fonts')
    else:
        if sys.platform == 'darwin':
            candidatas += [Path('/Library/Fonts'), Path.home() / 'Library/Fonts', Path('/System/Library/Fonts')]
        else:
            candidatas += [Path('/usr/share/fonts'), Path.home() / '.fonts', Path.home() / '.local/share/fonts']
    if incluidas:
        propia = carpeta_incluida()
        if propia is not None:
            candidatas.append(propia)
    candidatas += [Path(e).expanduser() for e in extras]
    vistas, salida = (set(), [])
    for c in candidatas:
        try:
            if c.is_dir() and c not in vistas:
                    vistas.add(c)
                    salida.append(c)
        except OSError:
            pass
    return salida
_LOCK = threading.RLock()
_DISCO = {'cargado': False, 'datos': {}, 'sucio': False}   # {ruta: [tamaño, mtime_ns, caras]}: lo ya leido de cada archivo
def _archivo_cache():
    return Path.home() / 'DaVinciSubtitles' / 'cache_fuentes.json'
def _cargar_disco():
    """v5.4: leer los nombres de ~1100 fuentes del sistema tardaba ~3 s y congelaba la ventana al abrir «Estilos».
    Lo leido de cada archivo se guarda en disco con su tamaño y fecha: solo se vuelve a leer lo que cambia."""
    if _DISCO['cargado']:
        return
    _DISCO['cargado'] = True
    try:
        datos = json.loads(_archivo_cache().read_text(encoding='utf-8'))
        if isinstance(datos, dict) and datos.get('v') == 1 and isinstance(datos.get('f'), dict):
            _DISCO['datos'] = datos['f']
    except Exception:
        _DISCO['datos'] = {}
def _guardar_disco():
    if not _DISCO['sucio']:
        return
    try:
        destino = _archivo_cache()
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix('.tmp')
        temporal.write_text(json.dumps({'v': 1, 'f': _DISCO['datos']}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        os.replace(temporal, destino)
        _DISCO['sucio'] = False
    except Exception:
        pass
def _caras_con_cache(ruta, st):
    llave = str(ruta)
    previo = _DISCO['datos'].get(llave)
    if previo and previo[0] == st.st_size and previo[1] == st.st_mtime_ns:
        return [tuple(c) for c in previo[2]]
    caras = _caras_del_archivo(ruta)
    _DISCO['datos'][llave] = [st.st_size, st.st_mtime_ns, [list(c) for c in caras]]
    _DISCO['sucio'] = True
    return caras
def _archivos_de_fuente(carpeta):
    """(ruta, stat) de cada .ttf/.otf/.ttc/.otc bajo la carpeta (scandir: el stat sale gratis del listado)."""
    pendientes = [str(carpeta)]
    while pendientes:
        actual = pendientes.pop()
        try:
            with os.scandir(actual) as it:
                entradas = list(it)
        except OSError:
            continue
        subcarpetas = []
        for e in entradas:
            try:
                if e.is_dir(follow_symlinks=False):
                    subcarpetas.append(e.path)
                elif os.path.splitext(e.name)[1].lower() in EXTENSIONES and e.is_file():
                    yield (Path(e.path), e.stat())
            except OSError:
                continue
        pendientes.extend(reversed(subcarpetas))
def indexar(carpetas):
    """{familia_normalizada: {estilo_normalizado: ruta}} + nombres legibles."""
    indice, legibles, archivos = {}, {}, 0

    def anotar(familia, estilo, ruta):
        if not familia:
            return
        fam = normalizar(familia)
        est = normalizar(estilo or 'Regular')
        indice.setdefault(fam, {}).setdefault(est, ruta)
        legibles.setdefault(fam, familia)

    leidos_ahora = 0
    with _LOCK:
        _cargar_disco()
        for carpeta in carpetas:
            for ruta, st in _archivos_de_fuente(carpeta):
                caras = _caras_con_cache(ruta, st)
                leidos_ahora += 1
                if leidos_ahora % 120 == 0:
                    _guardar_disco()                 # v5.4.8: el progreso del primer índice se conserva aunque se cierre el programa
                if caras:
                    archivos += 1
                for fam16, est17, fam1, est2, completo in caras:
                    anotar(fam16, est17, ruta)
                    anotar(fam1, est2, ruta)
                    if completo:
                        anotar(completo, 'Regular', ruta)
        _guardar_disco()
    return indice, legibles, archivos
_CACHES = {}
def _indice(extras=(), incluidas=True):
    llave = (tuple((str(e) for e in extras)), bool(incluidas))
    with _LOCK:
        if llave not in _CACHES:
            _CACHES[llave] = indexar(carpetas_de_fuentes(extras, incluidas=incluidas))[0]
        return _CACHES[llave]
def invalidar_cache():
    """Para cuando se acaba de instalar una fuente y hay que verla ya."""
    with _LOCK:
        _CACHES.clear()
_ESTADO_INDICE = {'listo': threading.Event(), 'precalentando': False}


def indice_listo():
    """v5.4.8: True si el índice de fuentes ya está armado (o si nadie lo está armando en segundo plano: entonces se arma al pedirlo, como siempre). La interfaz lo usa para
    NO esperar al primer índice (en un equipo nuevo son ~1000 archivos): enseña «Comprobando tipografías…» y se refresca sola con `al_estar_listo`."""
    return _ESTADO_INDICE['listo'].is_set() or not _ESTADO_INDICE['precalentando']


def al_estar_listo(funcion, espera_max_s=180):
    """Llama a `funcion()` (en un hilo) cuando el índice termine (o tras `espera_max_s`)."""
    def esperar():
        _ESTADO_INDICE['listo'].wait(espera_max_s)
        try:
            funcion()
        except Exception:
            pass
    threading.Thread(target=esperar, name='fuentes-al-estar-listo', daemon=True).start()


def precalentar():
    """Arma los indices en un hilo (al abrir el programa), para que ningun clic pague la lectura de las fuentes."""
    _ESTADO_INDICE['precalentando'] = True
    _ESTADO_INDICE['listo'].clear()

    def trabajo():
        try:
            _indice(incluidas=False)
            _indice_incluidas()
            _indice()
        except Exception:
            pass
        finally:
            _ESTADO_INDICE['listo'].set()
    threading.Thread(target=trabajo, name='fuentes-precalentar', daemon=True).start()
def _buscar(indice, familia, estilo, exacto=False):
    estilos = indice.get(normalizar(familia))
    if not estilos:
        return
    else:
        ruta = estilos.get(normalizar(estilo))
        if ruta is not None or exacto:
            return ruta
        else:
            return next(iter(estilos.values()), None)
def ruta_de_fuente(familia, estilo='Regular', extras=()):
    """La ruta al .ttf/.otf de esa familia+estilo, o None si no esta.\n\n    Mira las del sistema Y las que viajan dentro del programa. Es lo que\n    hay que usar para MEDIR y DIBUJAR (Pillow abre un archivo y le da igual\n    de donde salga). Para saber si Resolve la va a poder usar, no sirve:\n    para eso esta esta_en_el_sistema().\n    """
    return _buscar(_indice(extras), familia, estilo)
def esta_en_el_sistema(familia, estilo='Regular', exacto=False):
    """True si esa familia+estilo esta instalada en el SISTEMA operativo.\n\n    Deliberadamente ignora la carpeta \'fonts/\' del programa. Fusion resuelve\n    las tipografias por el registro del sistema, no por una carpeta suelta:\n    una fuente que solo esta en nuestro bundle se dibuja bien en la vista\n    previa y Resolve la sustituye igual. Dar por \"instalada\" una de esas\n    seria mentir en el unico aviso que el usuario tiene para enterarse.\n\n    \'exacto\' exige ESE estilo (v2.0.6). Por defecto basta la familia (otro\n    corte instalado cuenta), y eso es lo correcto para el aviso de Arial\n    (plantillas._fuentes_respaldo: Fusion cae dentro de la familia y no se\n    pisa una fuente variable) — pero era FALSO para decidir que instalar:\n    con cualquier otro corte de «Inter 24pt» en el sistema, la Bold se\n    daba por instalada y el instalador no la copiaba nunca. La Mac de\n    el usuario siguio sin Inter 24pt Bold tras dos versiones «ofreciendola»\n    (reporte 14-09: «sigue sin reconocerlo en la Mac»).\n    """
    return _buscar(_indice(incluidas=False), familia, estilo, exacto=exacto) is not None
def se_puede_instalar(familia, estilo='Regular'):
    """La ruta dentro de \'fonts/\' si la traemos nosotros y NO esta instalada.\n\n    O sea: \"esta es la que el boton de instalar puede arreglar\". None si ya\n    esta en el sistema (no hay nada que hacer) o si no la traemos (no hay\n    nada que ofrecer).\n    """
    if esta_en_el_sistema(familia, estilo, exacto=True):
        return
    else:
        return _buscar(_indice_incluidas(), familia, estilo, exacto=True)
def _indice_incluidas():
    """Solo la carpeta \'fonts/\' del programa, cacheada aparte.\n\n    Cacheada porque se pregunta una vez por cada tipografia del pack (21 en\n    el pack base) y cada indexado byte-parsea todos los .ttf de la carpeta.\n    """
    with _LOCK:
        if 'solo_incluidas' not in _CACHES:
            propia = carpeta_incluida()
            _CACHES['solo_incluidas'] = indexar([propia])[0] if propia else {}
        return _CACHES['solo_incluidas']
def _codigos_formato4(d, off):
    try:
        seg2, = struct.unpack('>H', d[off + 6:off + 8])
    except struct.error:
        return set()
    p_end = off + 14
    p_start = p_end + seg2 + 2
    p_delta = p_start + seg2
    p_rango = p_delta + seg2
    codigos = set()
    for i in range(seg2 // 2):
        try:
            fin, = struct.unpack('>H', d[p_end + 2 * i:p_end + 2 * i + 2])
            ini, = struct.unpack(
                '>H', d[p_start + 2 * i:p_start + 2 * i + 2])
            delta, = struct.unpack(
                '>h', d[p_delta + 2 * i:p_delta + 2 * i + 2])
            rango, = struct.unpack(
                '>H', d[p_rango + 2 * i:p_rango + 2 * i + 2])
        except struct.error:
            break
        if ini == 65535:
            continue
        for c in range(ini, min(fin, 65534) + 1):
            if rango == 0:
                if (c + delta) & 65535 != 0:
                    codigos.add(c)
            else:
                p = p_rango + 2 * i + rango + 2 * (c - ini)
                if p + 2 <= len(d):
                    g, = struct.unpack('>H', d[p:p + 2])
                    if g != 0:
                        codigos.add(c)
    return codigos
def _codigos_formato12(d, off):
    try:
        n, = struct.unpack('>I', d[off + 12:off + 16])
    except struct.error:
        return set()
    codigos = set()
    p = off + 16
    for _ in range(min(n, 10000)):
        if p + 12 > len(d):
            break
        ini, fin, _g = struct.unpack('>III', d[p:p + 12])
        p += 12
        for c in range(ini, min(fin, ini + 65535) + 1):
            codigos.add(c)
            if len(codigos) > 200000:
                return codigos
    return codigos
def _codigos_de_cmap(ruta):
    """El conjunto de codepoints con glifo real, o None si no se pudo leer.

    None NO es 'no tiene nada': es 'no se sabe'.
    """
    try:
        with open(ruta, 'rb') as f:
            etiqueta = f.read(4)
            offset = 0
            if etiqueta == b'ttcf':
                f.seek(12)
                offset, = struct.unpack('>I', f.read(4))
            f.seek(offset)
            cabecera = f.read(12)
            if len(cabecera) < 12 or cabecera[:4] not in (
                    b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1'):
                return None
            num_tablas, = struct.unpack('>H', cabecera[4:6])
            tabla = None
            for _ in range(min(num_tablas, 512)):
                registro = f.read(16)
                if len(registro) < 16:
                    return None
                if registro[:4] == b'cmap':
                    _, _, inicio, largo = struct.unpack('>4sIII', registro)
                    tabla = (inicio, largo)
                    break
            if not tabla:
                return None
            f.seek(tabla[0])
            datos = f.read(tabla[1])
        if len(datos) < 4:
            return None
        cuantas, = struct.unpack('>H', datos[2:4])
        prioridad = {(3, 10): 0, (0, 6): 0, (0, 4): 0,
                     (3, 1): 1, (0, 3): 1, (0, 2): 1, (0, 1): 1, (0, 0): 1}
        subtablas = []
        for i in range(min(cuantas, 64)):
            base = 4 + i * 8
            if base + 8 > len(datos):
                break
            pid, eid, off = struct.unpack('>HHI', datos[base:base + 8])
            subtablas.append((prioridad.get((pid, eid), 9), off))
        for _, off in sorted(subtablas):
            if off + 2 > len(datos):
                continue
            formato, = struct.unpack('>H', datos[off:off + 2])
            if formato == 4:
                codigos = _codigos_formato4(datos, off)
            elif formato == 12:
                codigos = _codigos_formato12(datos, off)
            else:
                continue
            if codigos:
                return codigos
        return None
    except Exception:
        return None
_CACHE_CMAP = {}
def puede_dibujar(familia, estilo, caracteres, extras=()):
    """Si esa fuente tiene glifo para TODOS esos caracteres.\n\n    Devuelve True, False, o None cuando no se pudo saber (no hay archivo\n    a la vista, o su cmap no se dejo leer). El que llama NUNCA debe\n    tratar None como False: vetar un set por una fuente que no pudimos\n    leer recorta diseño sano sin motivo.\n    """
    ruta = ruta_de_fuente(familia, estilo, extras)
    if not ruta:
        return
    else:
        llave = str(ruta)
        if llave not in _CACHE_CMAP:
            _CACHE_CMAP[llave] = _codigos_de_cmap(ruta)
        codigos = _CACHE_CMAP[llave]
        if codigos is None:
            return
        else:
            return all((ord(c) in codigos for c in caracteres))
