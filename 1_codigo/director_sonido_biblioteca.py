# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_biblioteca.py — «AI Sound Director»: el ÍNDICE de TODO el material del autor (no solo UTILES) para SFX, música y ambiente.
"""
indice(refrescar=False)   → {'version', 'fecha', 'raices', 'archivos': [{'ruta', 'cat', 'modo', 'tono', 'pack'}]}
de_categoria(cat, n=60, brillo=None) → rutas de esa categoría que encajan por su nombre (semántica primero), repartidas entre packs
camas(brillo, n=14)       → pads/drones de las colecciones de Film Score, del modo que va con el video (mayor si es luminoso)
ambientes(contexto)       → grabaciones de ambiente que son de ESE entorno (nunca unas aves en un interior)

Categorías: whoosh · golpe · riser · ui · tonal · trazo (SFX) · cama (cama musical tonal: pads/drones) · ambiente · None (no se usa: canciones,
memes, gritos, aplausos, animales, melodías…). La categoría sale de las CARPETAS (el autor ordenó su material: «IMPACTOS», «Pads_Drones»,
«AMBIENTE»…) y, si la carpeta no dice nada, de las palabras núcleo del nombre (director_sonido_fuentes.NUCLEO).

RAICES: las bibliotecas del autor (licencias: el autor responde, memoria recursos-del-autor) + «Mis sonidos» (~/DaVinciSubtitles/sound_director/
biblioteca: lo que el usuario añada o descargue con licencia). Lo que no exista se ignora (en otra máquina, el índice sale vacío y todo sigue igual).
El índice va a disco (sound_director/cache/indice_biblioteca.json) y se rehace si cambia alguna carpeta de primer nivel o tiene más de 7 días.
"""
import hashlib
import re
import time
import unicodedata
from pathlib import Path

VERSION = 2
RAICES = (Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\EFECTOS SONIDO'),
          Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\RECURSOS PREMIUN\BODAS  & XV RECURSOS\SONIDOS'))
EXT = ('.wav', '.mp3', '.aif', '.aiff', '.flac', '.ogg', '.m4a')
MAX_DIAS = 7
# carpeta (texto normalizado de la ruta relativa) → categoría; en orden: lo primero que encaja manda
EXCLUIR = ('canciones', 'songs sfx', 'meme', 'gritos', 'aplausos', 'pirotecnia', 'fuegos artificiales', 'animales', 'netflix', 'cumpleanos',
           'fiestas', 'riffs_melodies', 'chord progressions', 'melodies & improvs', 'melody -', 'latidos', 'dinero', 'error', 'cronometro',
           'transition - vocal', 'censura', 'camara')                         # (un obturador en cada palabra suena a foto, no a gráfico)
REGLAS = (('cama', ('pads_drones', 'textures & drones', 'drone -')),
          ('tonal', ('chord hits', 'single note hits', 'pulses', 'positivo')),
          ('riser', ('risers & swells', 'riser', 'risex', 'tension')),
          ('whoosh', ('whoosh', 'transitions')),
          ('golpe', ('impactos', 'impact', '/hits')),
          ('ui', ('clicks y ui', 'menus', 'seleccion', 'textos')),
          ('ambiente', ('ambiente', 'ambient', 'naturaleza', 'lluvia', 'agua')))
ANIMALES = ('bear', 'cat', 'dog', 'elephant', 'horse', 'leapord', 'leopard', 'snake', 'wolf', 'meow', 'bark', 'roar', 'howl', 'purr', 'goldendoodle')
OSCURO_CAMA = ('ghost', 'ghostly', 'frozen', 'storm', 'ash', 'night', 'dark', 'low light', 'strain', 'unveil', 'sub drone', 'dune', 'church', 'organ')
# entorno de la escena (director_sonido_ambiente) → palabras de las grabaciones que son de ese entorno
AMBIENTE_DE = {'STREET': ('city', 'traffic', 'street', 'calle', 'ciudad', 'nightlife'), 'CITY': ('city', 'traffic', 'nightlife', 'ciudad'),
               'TRAFFIC': ('traffic', 'city'), 'NATURE': ('forest', 'field', 'birds', 'aves', 'natural', 'crickets', 'mountain', 'sunny'),
               'FOREST': ('forest', 'birds', 'aves', 'natural'), 'PARK': ('park', 'citypark', 'birds', 'aves', 'field', 'sunny'),
               'OUTDOOR': ('field', 'sunny', 'mountain', 'natural', 'park', 'wind', 'viento'), 'WIND': ('wind', 'viento', 'mountain'),
               'WATER': ('river', 'stream', 'agua', 'waves', 'beach'), 'CROWD': ('crowd', 'gente', 'restaurant', 'party'),
               'CAFE': ('restaurant', 'cafe'), 'EVENT': ('crowd', 'party', 'church', 'restaurant', 'gente'), 'RAIN': ('rain', 'lluvia', 'thunder')}
_MEM = {}


def _norma(texto):
    t = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('ascii').lower()
    return t.replace('\\', '/')


def mis_sonidos():
    """La carpeta del usuario para material propio o descargado con licencia (se crea al pedirla)."""
    import director_sonido_estado as E
    d = E.CARPETA / 'biblioteca'
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def raices():
    return [r for r in (*RAICES, mis_sonidos()) if r.is_dir()]


def categoria(ruta, raiz):
    """La categoría de un archivo por sus carpetas y, si no dicen nada, por su nombre."""
    import director_sonido_fuentes as F
    rel = Path(ruta).relative_to(raiz)
    carpeta = '/' + _norma('/'.join(rel.parts[:-1])) + '/'
    nombre = F._palabras(ruta)
    if any(x in carpeta for x in EXCLUIR) or any(F._tiene(nombre, a) for a in ANIMALES):
        return None
    cat = next((c for c, claves in REGLAS if any(x in carpeta for x in claves)), None)
    if cat is None:                                                   # (núcleo del nombre: «Reverse Wind Riser» es riser, no golpe)
        cat = next((c for c in ('riser', 'whoosh', 'golpe', 'trazo', 'tonal', 'ui') if any(F._tiene(nombre, p) for p in F.NUCLEO.get(c, ()))), None)
    if cat in ('whoosh', 'golpe', 'tonal', 'ui', 'trazo') and re.search(r'\d+\s*bpm|\bloop', Path(ruta).stem, re.I):
        return None                                                   # un bucle a tempo es música, no el sonido de un movimiento
    return cat


def _modo_y_tono(ruta):
    """(«mayor»/«menor»/None, tonalidad «A#» o None) de los nombres de Film Score: «Low Aerial (A#m_Bbm)», «Horizon Major C#_Db», «(Minor)»."""
    t = str(Path(ruta).parent.name) + ' ' + Path(ruta).stem
    modo = ('menor' if re.search(r'\bminor\b', t, re.I) or re.search(r'\b[A-G][#b]?m[_)\s]', t) else
            ('mayor' if re.search(r'\bmajor\b', t, re.I) or re.search(r'\([A-G][#b]?[_)]', t) else None))
    m = re.search(r'\b([A-G][#b]?)m?(?:_[A-G][#b]?m?)?\)?\s*$', Path(ruta).stem) or re.search(r'\(([A-G][#b]?)', Path(ruta).stem)
    return modo, (m.group(1) if m else None)


def _firma():
    """Lo que, si cambia, obliga a rehacer el índice: las carpetas de primer nivel de cada raíz y su fecha."""
    partes = []
    for r in raices():
        try:
            partes += [f'{r}|{d.name}|{int(d.stat().st_mtime)}' for d in sorted(r.iterdir()) if d.is_dir()]
        except OSError:
            pass
    return hashlib.sha1('\n'.join(partes).encode('utf-8')).hexdigest()[:16]


def _ruta_cache():
    import director_sonido_estado as E
    return E.CARPETA / 'cache' / 'indice_biblioteca.json'


def indice(refrescar=False):
    """El índice (en memoria, en disco y, si cambió algo, rehecho)."""
    import archivos_seguros
    firma = _firma()
    if not refrescar and _MEM.get('firma') == firma:
        return _MEM['indice']
    datos = None if refrescar else archivos_seguros.leer_json(_ruta_cache(), None)
    if not (isinstance(datos, dict) and datos.get('version') == VERSION and datos.get('firma') == firma
            and time.time() - float(datos.get('t') or 0) < MAX_DIAS * 86400):
        archivos = []
        for r in raices():
            for p in sorted(r.rglob('*')):
                if p.suffix.lower() not in EXT or not p.is_file():
                    continue
                try:
                    cat = categoria(p, r)
                except Exception:
                    cat = None
                if cat is None:
                    continue
                modo, tono = _modo_y_tono(p) if cat == 'cama' else (None, None)
                rel = p.relative_to(r).parts
                archivos.append({'ruta': str(p), 'cat': cat, 'modo': modo, 'tono': tono, 'pack': '/'.join(rel[:2 if len(rel) > 2 else 1])})
        datos = {'version': VERSION, 'firma': firma, 't': time.time(), 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'raices': [str(r) for r in raices()],
                 'archivos': archivos}
        try:
            archivos_seguros.escribir_json(_ruta_cache(), datos)
        except Exception:
            pass
    _MEM.update(firma=firma, indice=datos)
    return datos


def resumen():
    """{categoría: cuántos} (para la página y el Registro)."""
    cuenta = {}
    for a in indice().get('archivos') or []:
        cuenta[a['cat']] = cuenta.get(a['cat'], 0) + 1
    return cuenta


def _repartir(lista, n, clave):
    """n elementos repartidos por turnos entre sus grupos (packs), no los n primeros por orden alfabético."""
    grupos = {}
    for x in lista:
        grupos.setdefault(clave(x), []).append(x)
    for g in grupos.values():                                          # dentro de cada pack, espaciados (no los «01 …» de cada serie)
        paso = max(1, len(g) // max(1, n))
        g[:] = g[::paso] + [x for k, x in enumerate(g) if k % paso]
    salida, k = [], 0
    while len(salida) < n and any(grupos.values()):
        for g in list(grupos.values()):
            if k < len(g) and len(salida) < n:
                salida.append(g[k])
        k += 1
        if all(k >= len(g) for g in grupos.values()):
            break
    return salida


def de_categoria(cat, n=60, brillo=None):
    """Rutas de esa categoría con buena semántica por su nombre (≥ 0,5: la misma vara que elegir), repartidas entre packs."""
    import director_sonido_fuentes as F
    buenos = [a for a in indice().get('archivos') or [] if a['cat'] == cat]
    if cat in F.SEMANTICA:
        buenos = [a for a in buenos if F.semantica(a['ruta'], cat, brillo) >= 0.5]
    return [a['ruta'] for a in _repartir(buenos, n, lambda a: a['pack'])]


def camas(brillo=0.5, n=14):
    """Pads/drones del modo que va con el video: mayor (luminoso) o menor (sobrio/oscuro); en un video luminoso, nada de nombres oscuros."""
    todas = [a for a in indice().get('archivos') or [] if a['cat'] == 'cama']
    modo = 'mayor' if float(brillo) >= 0.45 else 'menor'
    import director_sonido_fuentes as F
    def vale(a):
        w = F._palabras(a['ruta']) + F._palabras(Path(a['ruta']).parent)
        if any(F._tiene(w, p) for p in F.NUNCA):
            return False
        if modo == 'mayor' and any(F._tiene(w, p) for p in OSCURO_CAMA):
            return False
        return a['modo'] in (modo, None)
    return _repartir([a for a in todas if vale(a)], n, lambda a: str(Path(a['ruta']).parent))


def ambientes(contexto):
    """Las grabaciones de ambiente de ESE entorno (por su nombre); un entorno sin grabación propia → [] (mejor silencio)."""
    claves = AMBIENTE_DE.get(str(contexto or '').upper())
    if not claves:
        return []
    import director_sonido_fuentes as F
    salida = []
    for a in indice().get('archivos') or []:
        if a['cat'] != 'ambiente':
            continue
        w = re.findall(r'[a-z]+', _norma(re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', Path(a['ruta']).stem)))     # «CityTraffic» → city traffic
        if any(F._tiene(w, p) for p in F.NUNCA) or (contexto != 'RAIN' and any(F._tiene(w, p) for p in ('rain', 'lluvia', 'thunder', 'thunderstorm', 'storm'))):
            continue                                                  # (la lluvia solo donde llueve)
        if any(F._tiene(w, c) for c in claves):
            salida.append(a['ruta'])
    return salida
